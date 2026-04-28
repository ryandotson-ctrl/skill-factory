#!/usr/bin/env python3
"""Combine proof artifacts and launch policy into deterministic go/no-go contract."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError("request JSON must be an object")
    return value


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def evaluate(request: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    invariants = [item for item in request.get("invariants", []) if isinstance(item, dict)]
    gradient_checks = [item for item in request.get("gradient_checks", []) if isinstance(item, dict)]

    mode = str(request.get("mode", "near_miss")).strip().lower()
    if mode not in {"near_miss", "success_comparison"}:
        mode = "near_miss"

    evidence = request.get("evidence_provenance", {})
    if not isinstance(evidence, dict):
        evidence = {}
    mock_runtime_runs = int(evidence.get("mock_runtime_runs", 0) or 0)
    real_runtime_runs = int(evidence.get("real_runtime_runs", 0) or 0)
    mock_counts_toward_paid_budget = bool(evidence.get("mock_counts_toward_paid_budget", False))

    comparison_guard = request.get("comparison_guard", {})
    if not isinstance(comparison_guard, dict):
        comparison_guard = {}
    classical_success_gate_pass = bool(comparison_guard.get("classical_success_gate_pass", False))

    launch_policy = request.get("launch_policy", {})
    if not isinstance(launch_policy, dict):
        launch_policy = {}
    stop_on_pass_enabled = bool(launch_policy.get("stop_on_pass_enabled", False))
    default_planned_paid_runs = 1 if mode == "success_comparison" else 0
    planned_paid_runs = int(launch_policy.get("planned_paid_runs", default_planned_paid_runs) or default_planned_paid_runs)
    default_max_paid_runs = 1 if mode == "success_comparison" else max(planned_paid_runs, 0)
    max_paid_runs = int(launch_policy.get("max_paid_runs", default_max_paid_runs) or default_max_paid_runs)
    if planned_paid_runs < 0:
        planned_paid_runs = 0
    if max_paid_runs < 0:
        max_paid_runs = 0

    budget = request.get("budget", {})
    time_sec = float(budget.get("time_sec", 0.0) or 0.0)
    cost_usd = float(budget.get("cost_usd", 0.0) or 0.0)
    limit_time_sec = float(budget.get("limit_time_sec", 0.0) or 0.0)
    limit_cost_usd = float(budget.get("limit_cost_usd", 0.0) or 0.0)

    gates = request.get("gates", {})
    max_abs_err = float(gates.get("max_abs_err", 0.0) or 0.0)
    max_rel_err = float(gates.get("max_rel_err", 0.0) or 0.0)
    require_all_invariants = bool(gates.get("require_all_invariants", True))

    checks: list[dict[str, Any]] = []

    checks.append(
        {
            "name": "launch_mode_declared",
            "passed": True,
            "detail": f"mode={mode}",
            "severity": "info",
        }
    )

    invariants_pass = all(bool(item.get("pass", False)) for item in invariants) if invariants else False
    checks.append(
        {
            "name": "invariants_pass",
            "passed": invariants_pass,
            "detail": f"count={len(invariants)} require_all={require_all_invariants}",
            "severity": "error",
        }
    )

    gradients_pass = True
    for item in gradient_checks:
        abs_err = float(item.get("abs_err", 0.0) or 0.0)
        rel_err = float(item.get("rel_err", 0.0) or 0.0)
        if not (abs_err <= max_abs_err or rel_err <= max_rel_err):
            gradients_pass = False
            break

    checks.append(
        {
            "name": "gradient_checks_pass",
            "passed": gradients_pass,
            "detail": f"count={len(gradient_checks)} max_abs_err={max_abs_err} max_rel_err={max_rel_err}",
            "severity": "error",
        }
    )

    budget_pass = (time_sec <= limit_time_sec) and (cost_usd <= limit_cost_usd)
    checks.append(
        {
            "name": "budget_pass",
            "passed": budget_pass,
            "detail": (
                f"time_sec={time_sec} limit_time_sec={limit_time_sec} "
                f"cost_usd={cost_usd} limit_cost_usd={limit_cost_usd}"
            ),
            "severity": "error",
        }
    )

    stop_on_pass_guard = True
    if mode == "success_comparison":
        stop_on_pass_guard = stop_on_pass_enabled
    checks.append(
        {
            "name": "stop_on_pass_guard",
            "passed": stop_on_pass_guard,
            "detail": f"mode={mode} stop_on_pass_enabled={stop_on_pass_enabled}",
            "severity": "error",
        }
    )

    paid_run_budget_guard = planned_paid_runs <= max_paid_runs
    checks.append(
        {
            "name": "paid_run_budget_guard",
            "passed": paid_run_budget_guard,
            "detail": f"planned_paid_runs={planned_paid_runs} max_paid_runs={max_paid_runs}",
            "severity": "error",
        }
    )

    success_frontier_guard = True
    if mode == "success_comparison":
        success_frontier_guard = classical_success_gate_pass
    checks.append(
        {
            "name": "success_frontier_guard",
            "passed": success_frontier_guard,
            "detail": (
                f"mode={mode} classical_success_gate_pass={classical_success_gate_pass} "
                "(required for success_comparison mode)"
            ),
            "severity": "error",
        }
    )

    mock_provenance_guard = not mock_counts_toward_paid_budget
    checks.append(
        {
            "name": "mock_provenance_guard",
            "passed": mock_provenance_guard,
            "detail": (
                f"mock_runtime_runs={mock_runtime_runs} real_runtime_runs={real_runtime_runs} "
                f"mock_counts_toward_paid_budget={mock_counts_toward_paid_budget}"
            ),
            "severity": "error",
        }
    )

    go = all(check["passed"] for check in checks)
    stop_reason = "all_checks_passed" if go else "failed:" + ",".join(sorted(check["name"] for check in checks if not check["passed"]))

    proof_artifact = {
        "schema": "ProofArtifactV1",
        "generated_at": _utc_now(),
        "launch_mode": mode,
        "invariants": invariants,
        "gradient_checks": gradient_checks,
        "evidence_provenance": {
            "mock_runtime_runs": mock_runtime_runs,
            "real_runtime_runs": real_runtime_runs,
            "mock_counts_toward_paid_budget": mock_counts_toward_paid_budget,
        },
        "comparison_guard": {
            "classical_success_gate_pass": classical_success_gate_pass,
        },
        "budget_proof": {
            "pass": budget_pass,
            "time_sec": time_sec,
            "cost_usd": cost_usd,
            "stop_on_pass_enabled": stop_on_pass_enabled,
            "planned_paid_runs": planned_paid_runs,
            "max_paid_runs": max_paid_runs,
        },
    }

    launch_contract = {
        "schema": "LaunchGateV1",
        "go": go,
        "mode": mode,
        "checks": checks,
        "budget": {
            "time_sec": limit_time_sec,
            "cost_usd": limit_cost_usd,
        },
        "launch_policy": {
            "stop_on_pass_enabled": stop_on_pass_enabled,
            "planned_paid_runs": planned_paid_runs,
            "max_paid_runs": max_paid_runs,
        },
        "evidence_provenance": {
            "mock_runtime_runs": mock_runtime_runs,
            "real_runtime_runs": real_runtime_runs,
            "mock_counts_toward_paid_budget": mock_counts_toward_paid_budget,
        },
        "checked_at": _utc_now(),
        "stop_reason": stop_reason,
    }

    return proof_artifact, launch_contract


def _run_self_test() -> None:
    request = {
        "invariants": [
            {"name": "encoding", "pass": True, "evidence_hash": "abc"},
            {"name": "fail_closed", "pass": True, "evidence_hash": "def"},
        ],
        "gradient_checks": [
            {"target": "theta[0]", "abs_err": 0.001, "rel_err": 0.01, "tolerance": 0.01, "pass": True}
        ],
        "budget": {
            "time_sec": 240,
            "cost_usd": 0.0,
            "limit_time_sec": 600,
            "limit_cost_usd": 1.0,
        },
        "gates": {"max_abs_err": 0.01, "max_rel_err": 0.05, "require_all_invariants": True},
    }
    proof, contract = evaluate(request)
    assert proof["budget_proof"]["pass"] is True
    assert contract["go"] is True

    success_compare_request = {
        "mode": "success_comparison",
        "invariants": [{"name": "encoding", "pass": True, "evidence_hash": "abc"}],
        "gradient_checks": [{"target": "theta[0]", "abs_err": 0.0, "rel_err": 0.0, "tolerance": 0.01, "pass": True}],
        "budget": {
            "time_sec": 120,
            "cost_usd": 0.5,
            "limit_time_sec": 300,
            "limit_cost_usd": 1.0,
        },
        "gates": {"max_abs_err": 0.01, "max_rel_err": 0.05, "require_all_invariants": True},
        "comparison_guard": {"classical_success_gate_pass": True},
        "launch_policy": {
            "stop_on_pass_enabled": True,
            "planned_paid_runs": 1,
            "max_paid_runs": 1,
        },
        "evidence_provenance": {
            "mock_runtime_runs": 1,
            "real_runtime_runs": 0,
            "mock_counts_toward_paid_budget": False,
        },
    }
    _, success_contract = evaluate(success_compare_request)
    assert success_contract["go"] is True

    invalid_provenance = dict(success_compare_request)
    invalid_provenance["evidence_provenance"] = {
        "mock_runtime_runs": 1,
        "real_runtime_runs": 0,
        "mock_counts_toward_paid_budget": True,
    }
    _, invalid_contract = evaluate(invalid_provenance)
    assert invalid_contract["go"] is False


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate proof and launch assurance gates")
    parser.add_argument("--request", type=Path, help="Path to request JSON")
    parser.add_argument("--out-dir", type=Path, default=Path("."), help="Output directory")
    parser.add_argument("--self-test", action="store_true", help="Run built-in tests")
    args = parser.parse_args()

    if args.self_test:
        _run_self_test()
        print("self-test passed")
        return

    if not args.request:
        raise SystemExit("--request is required unless --self-test is used")

    request = _read_json(args.request)
    proof_artifact, launch_contract = evaluate(request)

    _write_json(args.out_dir / "proof_artifact.json", proof_artifact)
    _write_json(args.out_dir / "launch_contract.json", launch_contract)
    print(str(args.out_dir.resolve()))


if __name__ == "__main__":
    main()
