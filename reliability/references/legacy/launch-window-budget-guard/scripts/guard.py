#!/usr/bin/env python3
"""Deterministic launch-window and budget guard."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


TEMPLATES: dict[str, list[dict[str, Any]]] = {
    "quantum_one_shot": [
        {"name": "credentials_locked", "passed": False, "detail": "Credential set frozen before launch", "severity": "error"},
        {"name": "dry_run_complete", "passed": False, "detail": "Deterministic dry-run completed", "severity": "error"},
        {"name": "rollback_plan_documented", "passed": False, "detail": "Fallback/rollback instructions stored", "severity": "warning"},
        {"name": "human_go_nogo_confirmed", "passed": False, "detail": "Explicit go/no-go confirmation recorded", "severity": "error"},
    ],
    "default_irreversible": [
        {"name": "launch_owner_confirmed", "passed": False, "detail": "Named launch owner confirmed", "severity": "error"},
        {"name": "failure_policy_bound", "passed": False, "detail": "Hard-stop policy declared", "severity": "error"},
    ],
    "quantum_success_comparison_one_shot": [
        {"name": "classical_success_frontier_locked", "passed": False, "detail": "Classical success frontier and baseline locked", "severity": "error"},
        {"name": "comparative_hypothesis_documented", "passed": False, "detail": "Explicit comparative quantum hypothesis recorded", "severity": "warning"},
        {"name": "stop_on_pass_acknowledged", "passed": False, "detail": "Stop-on-pass policy acknowledged before launch", "severity": "error"},
        {"name": "paid_run_limit_acknowledged", "passed": False, "detail": "One-shot paid run limit acknowledged", "severity": "error"},
    ],
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        raise ValueError("request JSON must be an object")
    return payload


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _normalize_check(item: dict[str, Any], default_severity: str = "error") -> dict[str, Any]:
    severity = str(item.get("severity", default_severity)).lower()
    if severity not in {"info", "warning", "error"}:
        severity = default_severity
    return {
        "name": str(item.get("name", "unnamed_check")),
        "passed": bool(item.get("passed", False)),
        "detail": str(item.get("detail", "")),
        "severity": severity,
    }


def _template_checks(template_name: str | None) -> list[dict[str, Any]]:
    if not template_name:
        return []
    return [dict(item) for item in TEMPLATES.get(template_name, [])]


def _normalize_queue_policy(request: dict[str, Any]) -> dict[str, Any]:
    raw = request.get("queue_defer_policy", request.get("queue_policy", {}))
    if not isinstance(raw, dict):
        raw = {}

    allow_defer = bool(raw.get("allow_defer", raw.get("enabled", True)))
    recheck_after_sec = int(raw.get("recheck_after_sec", raw.get("retry_after_sec", 900)) or 900)
    max_rechecks = int(raw.get("max_rechecks", raw.get("retry_limit", 3)) or 3)
    action_if_exhausted = str(raw.get("action_if_exhausted", "abort")).lower()
    if action_if_exhausted not in {"abort", "manual_review"}:
        action_if_exhausted = "abort"

    return {
        "allow_defer": allow_defer,
        "recheck_after_sec": max(1, recheck_after_sec),
        "max_rechecks": max(0, max_rechecks),
        "action_if_exhausted": action_if_exhausted,
    }


def _normalize_launch_mode(request: dict[str, Any]) -> str:
    raw = str(request.get("launch_mode", request.get("mode", "standard"))).strip().lower()
    if raw in {"standard", "near_miss", "success_comparison"}:
        return raw
    return "standard"


def _normalize_launch_policy(request: dict[str, Any], launch_mode: str) -> dict[str, Any]:
    raw = request.get("launch_policy", {})
    if not isinstance(raw, dict):
        raw = {}

    stop_on_pass_enabled = bool(raw.get("stop_on_pass_enabled", False))
    default_planned_paid_runs = 1 if launch_mode == "success_comparison" else 0
    planned_paid_runs = int(raw.get("planned_paid_runs", default_planned_paid_runs) or default_planned_paid_runs)
    default_max_paid_runs = 1 if launch_mode == "success_comparison" else max(planned_paid_runs, 0)
    max_paid_runs = int(raw.get("max_paid_runs", default_max_paid_runs) or default_max_paid_runs)

    if planned_paid_runs < 0:
        planned_paid_runs = 0
    if max_paid_runs < 0:
        max_paid_runs = 0

    return {
        "stop_on_pass_enabled": stop_on_pass_enabled,
        "planned_paid_runs": planned_paid_runs,
        "max_paid_runs": max_paid_runs,
    }


def _is_queue_related_check(name: str) -> bool:
    lowered = name.lower()
    return "queue" in lowered


def evaluate(request: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    budget = request.get("budget", {})
    forecast = request.get("forecast", {})
    policy = request.get("hard_stop_policy", {})

    budget_time = int(budget.get("time_sec", 0) or 0)
    budget_cost = float(budget.get("cost_usd", 0.0) or 0.0)
    forecast_time = int(forecast.get("time_sec", 0) or 0)
    forecast_cost = float(forecast.get("cost_usd", 0.0) or 0.0)
    queue_time = int(forecast.get("queue_time_sec", request.get("queue_forecast_sec", 0)) or 0)
    queue_policy = _normalize_queue_policy(request)
    launch_mode = _normalize_launch_mode(request)
    launch_policy = _normalize_launch_policy(request, launch_mode)

    checks: list[dict[str, Any]] = []
    checks.append(
        {
            "name": "launch_mode_declared",
            "passed": True,
            "detail": f"launch_mode={launch_mode}",
            "severity": "info",
        }
    )

    checks.append(
        {
            "name": "time_within_budget",
            "passed": forecast_time <= budget_time,
            "detail": f"forecast_time_sec={forecast_time} budget_time_sec={budget_time}",
            "severity": "error",
        }
    )
    checks.append(
        {
            "name": "queue_time_within_budget",
            "passed": (forecast_time + queue_time) <= budget_time,
            "detail": (
                f"forecast_plus_queue_sec={forecast_time + queue_time} "
                f"budget_time_sec={budget_time} queue_time_sec={queue_time}"
            ),
            "severity": "error",
        }
    )
    checks.append(
        {
            "name": "cost_within_budget",
            "passed": forecast_cost <= budget_cost,
            "detail": f"forecast_cost_usd={forecast_cost:.6f} budget_cost_usd={budget_cost:.6f}",
            "severity": "error",
        }
    )

    stop_on_pass_required = launch_mode != "success_comparison" or launch_policy["stop_on_pass_enabled"]
    checks.append(
        {
            "name": "stop_on_pass_required_for_success_comparison",
            "passed": stop_on_pass_required,
            "detail": (
                f"launch_mode={launch_mode} stop_on_pass_enabled={launch_policy['stop_on_pass_enabled']}"
            ),
            "severity": "error",
        }
    )

    paid_run_plan_within_limit = launch_policy["planned_paid_runs"] <= launch_policy["max_paid_runs"]
    checks.append(
        {
            "name": "paid_run_plan_within_limit",
            "passed": paid_run_plan_within_limit,
            "detail": (
                f"planned_paid_runs={launch_policy['planned_paid_runs']} "
                f"max_paid_runs={launch_policy['max_paid_runs']}"
            ),
            "severity": "error",
        }
    )

    for raw in request.get("preflight_checks", []):
        if isinstance(raw, dict):
            checks.append(_normalize_check(raw, default_severity="error"))

    template_name = str(request.get("irreversible_template", "")).strip() or None
    irreversible_template_checks = _template_checks(template_name)
    for item in irreversible_template_checks:
        checks.append(_normalize_check(item, default_severity="error"))

    for raw in request.get("irreversible_checks", []):
        if isinstance(raw, dict):
            checks.append(_normalize_check(raw, default_severity="error"))

    block_on_warning = bool(policy.get("block_on_warning", False))

    failed_error = [c for c in checks if (not c["passed"] and c["severity"] == "error")]
    failed_warning = [c for c in checks if (not c["passed"] and c["severity"] == "warning")]

    go = not failed_error and (not block_on_warning or not failed_warning)

    stop_reason = "all_checks_passed"
    if failed_error:
        stop_reason = f"error_checks_failed:{','.join(sorted(c['name'] for c in failed_error))}"
    elif failed_warning and block_on_warning:
        stop_reason = f"warning_checks_failed:{','.join(sorted(c['name'] for c in failed_warning))}"

    blocking_checks = list(failed_error)
    if block_on_warning:
        blocking_checks.extend(failed_warning)

    queue_only_block = bool(blocking_checks) and all(_is_queue_related_check(c["name"]) for c in blocking_checks)
    recommended_action = "launch_now" if go else "abort"
    retry_recommendation: dict[str, Any] = {
        "eligible": False,
        "reason": "launch_not_blocked" if go else "non_queue_blockers_present",
        "recheck_after_sec": 0,
        "max_rechecks": 0,
        "remaining_rechecks": 0,
    }
    if not go and queue_only_block and queue_policy["allow_defer"] and queue_policy["max_rechecks"] > 0:
        recommended_action = "defer_and_recheck"
        retry_recommendation = {
            "eligible": True,
            "reason": "queue_pressure_predicted",
            "recheck_after_sec": queue_policy["recheck_after_sec"],
            "max_rechecks": queue_policy["max_rechecks"],
            "remaining_rechecks": queue_policy["max_rechecks"],
        }
    elif not go and queue_only_block and not queue_policy["allow_defer"]:
        retry_recommendation = {
            "eligible": False,
            "reason": "queue_defer_disabled_by_policy",
            "recheck_after_sec": 0,
            "max_rechecks": 0,
            "remaining_rechecks": 0,
        }
    elif not go and queue_only_block and queue_policy["max_rechecks"] <= 0:
        retry_recommendation = {
            "eligible": False,
            "reason": "queue_recheck_budget_exhausted",
            "recheck_after_sec": 0,
            "max_rechecks": 0,
            "remaining_rechecks": 0,
        }

    if not go and queue_only_block and recommended_action != "defer_and_recheck":
        if queue_policy["action_if_exhausted"] == "manual_review":
            recommended_action = "abort"
        else:
            recommended_action = "abort"

    launch_contract = {
        "schema": "LaunchContractV1",
        "checked_at": _utc_now(),
        "launch_mode": launch_mode,
        "launch_policy": launch_policy,
        "budget": {"time_sec": budget_time, "cost_usd": budget_cost},
        "forecast": {
            "time_sec": forecast_time,
            "queue_time_sec": queue_time,
            "total_time_sec": forecast_time + queue_time,
            "cost_usd": forecast_cost,
        },
        "hard_stop_policy": {"block_on_warning": block_on_warning},
        "queue_policy": queue_policy,
        "forecast_margin": {
            "time_sec": budget_time - (forecast_time + queue_time),
            "cost_usd": round(budget_cost - forecast_cost, 6),
        },
        "irreversible_template": template_name,
        "irreversible_template_checks": irreversible_template_checks,
        "recommended_action": recommended_action,
        "retry_recommendation": retry_recommendation,
        "post_launch_policy": {
            "stop_after_first_pass": bool(launch_policy["stop_on_pass_enabled"]),
        },
    }

    launch_report = {
        "schema": "LaunchGateV1",
        "go": go,
        "launch_mode": launch_mode,
        "launch_policy": launch_policy,
        "checks": checks,
        "budget": {"time_sec": budget_time, "cost_usd": budget_cost},
        "checked_at": _utc_now(),
        "stop_reason": stop_reason,
        "recommended_action": recommended_action,
        "retry_recommendation": retry_recommendation,
        "queue_policy": queue_policy,
        "post_launch_policy": {
            "stop_after_first_pass": bool(launch_policy["stop_on_pass_enabled"]),
        },
    }

    return launch_contract, launch_report


def _run_self_test() -> None:
    request = {
        "budget": {"time_sec": 600, "cost_usd": 10.0},
        "forecast": {"time_sec": 520, "queue_time_sec": 120, "cost_usd": 12.0},
        "preflight_checks": [
            {"name": "dataset_present", "passed": True, "detail": "ok"},
        ],
        "irreversible_template": "quantum_one_shot",
        "irreversible_checks": [
            {"name": "human_go_nogo_confirmed", "passed": True, "detail": "ok"},
        ],
        "hard_stop_policy": {"block_on_warning": False},
    }
    _, report = evaluate(request)
    assert report["go"] is False
    failed_names = {c["name"] for c in report["checks"] if not c["passed"]}
    assert "queue_time_within_budget" in failed_names
    assert "cost_within_budget" in failed_names
    assert report["recommended_action"] == "abort"

    queue_only_request = {
        "budget": {"time_sec": 600, "cost_usd": 10.0},
        "forecast": {"time_sec": 520, "queue_time_sec": 120, "cost_usd": 9.0},
        "queue_defer_policy": {
            "allow_defer": True,
            "recheck_after_sec": 180,
            "max_rechecks": 2,
        },
        "hard_stop_policy": {"block_on_warning": False},
    }
    _, queue_only_report = evaluate(queue_only_request)
    assert queue_only_report["go"] is False
    assert queue_only_report["recommended_action"] == "defer_and_recheck"
    assert queue_only_report["retry_recommendation"]["eligible"] is True
    assert queue_only_report["retry_recommendation"]["recheck_after_sec"] == 180

    success_compare_request = {
        "launch_mode": "success_comparison",
        "budget": {"time_sec": 600, "cost_usd": 10.0},
        "forecast": {"time_sec": 320, "queue_time_sec": 40, "cost_usd": 1.5},
        "launch_policy": {
            "stop_on_pass_enabled": True,
            "planned_paid_runs": 1,
            "max_paid_runs": 1,
        },
        "hard_stop_policy": {"block_on_warning": False},
    }
    _, success_compare_report = evaluate(success_compare_request)
    assert success_compare_report["go"] is True
    assert success_compare_report["launch_mode"] == "success_comparison"

    invalid_success_compare = {
        "launch_mode": "success_comparison",
        "budget": {"time_sec": 600, "cost_usd": 10.0},
        "forecast": {"time_sec": 320, "queue_time_sec": 40, "cost_usd": 1.5},
        "launch_policy": {
            "stop_on_pass_enabled": False,
            "planned_paid_runs": 2,
            "max_paid_runs": 1,
        },
        "hard_stop_policy": {"block_on_warning": False},
    }
    _, invalid_success_compare_report = evaluate(invalid_success_compare)
    assert invalid_success_compare_report["go"] is False


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate launch window and budget gates")
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
    launch_contract, launch_report = evaluate(request)

    _write_json(args.out_dir / "launch_contract.json", launch_contract)
    _write_json(args.out_dir / "launch_readiness_report.json", launch_report)
    print(str(args.out_dir.resolve()))


if __name__ == "__main__":
    main()
