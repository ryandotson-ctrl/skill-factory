#!/usr/bin/env python3
"""Normalize experiment events into immutable run-ledger artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stable_hash(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _parse_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        value = json.loads(line)
        if isinstance(value, dict):
            records.append(value)
    return records


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(row, sort_keys=True, separators=(",", ":")) for row in rows]
    path.write_text("\n".join(lines) + ("\n" if lines else ""))


def _optional_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes", "y", "on"}:
            return True
        if lowered in {"false", "0", "no", "n", "off"}:
            return False
    return None


def _governance_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    policy_modes = sorted({str(row.get("policy_mode")) for row in rows if row.get("policy_mode")})
    frontier_classes = sorted({str(row.get("frontier_class")) for row in rows if row.get("frontier_class")})

    latest_launch_recommendation = ""
    latest_reentry_go: bool | None = None
    latest_contract_go: bool | None = None
    for row in reversed(rows):
        if not latest_launch_recommendation and row.get("launch_recommendation"):
            latest_launch_recommendation = str(row.get("launch_recommendation"))
        if latest_reentry_go is None and isinstance(row.get("reentry_go"), bool):
            latest_reentry_go = bool(row.get("reentry_go"))
        if latest_contract_go is None and isinstance(row.get("contract_go"), bool):
            latest_contract_go = bool(row.get("contract_go"))
        if latest_launch_recommendation and latest_reentry_go is not None and latest_contract_go is not None:
            break

    return {
        "policy_modes": policy_modes,
        "frontier_classes": frontier_classes,
        "frontier_counts": {
            "near_miss_frontier": sum(1 for row in rows if row.get("frontier_class") == "near_miss_frontier"),
            "success_frontier": sum(1 for row in rows if row.get("frontier_class") == "success_frontier"),
            "below_frontier": sum(1 for row in rows if row.get("frontier_class") == "below_frontier"),
            "unknown_frontier": sum(1 for row in rows if row.get("frontier_class") == "unknown_frontier"),
        },
        "latest_launch_recommendation": latest_launch_recommendation or None,
        "latest_reentry_go": latest_reentry_go,
        "latest_contract_go": latest_contract_go,
    }


def normalize(events: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    normalized: list[dict[str, Any]] = []

    prev_hash = "GENESIS"
    for index, event in enumerate(events):
        run_id = str(event.get("run_id", "unknown_run"))
        stage = str(event.get("stage", "unknown_stage"))
        config_hash = str(event.get("config_hash") or _stable_hash(event.get("config", {})))
        inputs_hash = str(event.get("inputs_hash") or _stable_hash(event.get("inputs", {})))
        outputs_hash = str(event.get("outputs_hash") or _stable_hash(event.get("outputs", {})))
        status = str(event.get("status", "ok"))
        error_code = event.get("error_code")
        ts = str(event.get("ts", f"event-{index:06d}"))
        policy_mode_raw = str(event.get("policy_mode", "")).strip()
        frontier_class_raw = str(event.get("frontier_class", "")).strip()
        launch_recommendation_raw = str(event.get("launch_recommendation", "")).strip()

        base_row = {
            "schema": "RunLedgerEntryV1",
            "run_id": run_id,
            "stage": stage,
            "config_hash": config_hash,
            "inputs_hash": inputs_hash,
            "outputs_hash": outputs_hash,
            "status": status,
            "error_code": error_code,
            "ts": ts,
            "prev_hash": prev_hash,
            "policy_mode": policy_mode_raw or None,
            "frontier_class": frontier_class_raw or None,
            "launch_recommendation": launch_recommendation_raw or None,
            "reentry_go": _optional_bool(event.get("reentry_go")),
            "contract_go": _optional_bool(event.get("contract_go")),
        }
        entry_hash = _stable_hash(base_row)
        row = {**base_row, "entry_hash": entry_hash}
        normalized.append(row)
        prev_hash = entry_hash

    stage_order: list[str] = []
    for row in normalized:
        if row["stage"] not in stage_order:
            stage_order.append(row["stage"])

    status_counts: dict[str, int] = {}
    for row in normalized:
        status_counts[row["status"]] = status_counts.get(row["status"], 0) + 1

    run_ids = sorted({row["run_id"] for row in normalized})
    ledger_hash = _stable_hash(normalized)
    root_hash = normalized[-1]["entry_hash"] if normalized else "GENESIS"
    governance = _governance_summary(normalized)

    decision_context = {
        "schema": "DecisionContextV1",
        "generated_at": _utc_now(),
        "entry_count": len(normalized),
        "stage_order": stage_order,
        "status_counts": status_counts,
        "run_ids": run_ids,
        "ledger_hash": ledger_hash,
        "hash_chain_root": root_hash,
        "governance": governance,
    }

    signature_payload = {
        "ledger_hash": ledger_hash,
        "hash_chain_root": root_hash,
        "entry_count": len(normalized),
        "run_ids": run_ids,
        "governance": governance,
    }

    replay_manifest = {
        "schema": "ReplayManifestV1",
        "generated_at": _utc_now(),
        "entry_count": len(normalized),
        "run_ids": run_ids,
        "stage_order": stage_order,
        "ledger_hash": ledger_hash,
        "hash_chain_root": root_hash,
        "governance": governance,
        "signature_bundle": {
            "algorithm": "sha256",
            "signature": _stable_hash(signature_payload),
            "payload_hash": _stable_hash(signature_payload),
            "detached": True,
        },
        "replay_contract": {
            "ordering": "input_jsonl_order",
            "hashing": "sha256(canonical_json)",
            "chain": "prev_hash -> entry_hash",
            "deterministic": True,
        },
    }

    return normalized, decision_context, replay_manifest


def _run_self_test() -> None:
    events = [
        {
            "run_id": "r1",
            "stage": "baseline",
            "config": {"a": 1},
            "inputs": {"prompt": "hello"},
            "outputs": {"text": "world"},
            "status": "ok",
            "ts": "2026-01-01T00:00:00Z",
        },
        {
            "run_id": "r1",
            "stage": "quantum",
            "config": {"a": 2},
            "inputs": {"prompt": "hello"},
            "outputs": {"text": "world2"},
            "status": "ok",
            "ts": "2026-01-01T00:01:00Z",
            "policy_mode": "success_comparison",
            "frontier_class": "success_frontier",
            "launch_recommendation": "run_prepare_quantum_rerank_one_shot_and_launch",
            "reentry_go": True,
            "contract_go": True,
        },
    ]
    n1, c1, m1 = normalize(events)
    n2, c2, m2 = normalize(events)
    assert n1 == n2
    assert c1["ledger_hash"] == c2["ledger_hash"]
    assert m1["signature_bundle"]["signature"] == m2["signature_bundle"]["signature"]
    assert n1[0]["prev_hash"] == "GENESIS"
    assert n1[1]["prev_hash"] == n1[0]["entry_hash"]
    assert c1["governance"]["latest_reentry_go"] is True
    assert c1["governance"]["latest_contract_go"] is True
    assert "success_frontier" in c1["governance"]["frontier_classes"]


def main() -> None:
    parser = argparse.ArgumentParser(description="Package run events into immutable ledger artifacts")
    parser.add_argument("--events", type=Path, help="Path to input events JSONL")
    parser.add_argument("--out-dir", type=Path, default=Path("."), help="Output directory")
    parser.add_argument("--self-test", action="store_true", help="Run built-in tests")
    args = parser.parse_args()

    if args.self_test:
        _run_self_test()
        print("self-test passed")
        return

    if not args.events:
        raise SystemExit("--events is required unless --self-test is used")

    events = _parse_jsonl(args.events)
    run_record, decision_context, replay_manifest = normalize(events)

    _write_jsonl(args.out_dir / "run_record.jsonl", run_record)
    _write_json(args.out_dir / "decision_context.json", decision_context)
    _write_json(args.out_dir / "replay_manifest.json", replay_manifest)
    print(str(args.out_dir.resolve()))


if __name__ == "__main__":
    main()
