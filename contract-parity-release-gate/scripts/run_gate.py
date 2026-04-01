#!/usr/bin/env python3
"""Aggregate domain parity states into a deterministic release-gate result."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


DEFAULT_REQUIRED = [
    "chat_runtime",
    "search_grounding",
    "rag",
    "model_lifecycle",
    "training_pipeline",
]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def normalize_status(value: Any) -> str:
    status = str(value or "").strip().lower()
    if status in {"pass", "warning", "blocker"}:
        return status
    return "warning"


def load_input(path: Path) -> Dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Input payload must be a JSON object.")
    return payload


def to_domain_map(entries: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for item in entries:
        domain = str(item.get("domain", "")).strip()
        if not domain:
            continue
        out[domain] = item
    return out


def gate(payload: Dict[str, Any]) -> Dict[str, Any]:
    required = payload.get("required_domains", DEFAULT_REQUIRED)
    if not isinstance(required, list) or not required:
        required = DEFAULT_REQUIRED
    required = [str(domain) for domain in required]

    domain_results = payload.get("domain_results", [])
    if not isinstance(domain_results, list):
        domain_results = []
    typed = [item for item in domain_results if isinstance(item, dict)]
    by_domain = to_domain_map(typed)

    normalized: List[Dict[str, Any]] = []
    blocking_domains: List[str] = []

    for domain in required:
        row = by_domain.get(domain)
        if row is None:
            normalized.append(
                {
                    "domain": domain,
                    "status": "blocker",
                    "evidence_ref": "",
                    "summary": "Required domain result missing.",
                    "remediation": "Provide parity result for this domain.",
                }
            )
            blocking_domains.append(domain)
            continue

        status = normalize_status(row.get("status"))
        normalized.append(
            {
                "domain": domain,
                "status": status,
                "evidence_ref": str(row.get("evidence_ref", "")),
                "summary": str(row.get("summary", "")),
                "remediation": str(row.get("remediation", "")),
            }
        )
        if status == "blocker":
            blocking_domains.append(domain)

    global_status = "pass"
    if blocking_domains:
        global_status = "blocker"
    elif any(item["status"] == "warning" for item in normalized):
        global_status = "warning"

    recommendation = (
        "Hold release until blockers are resolved."
        if global_status == "blocker"
        else "Proceed with caution; warnings require tracking."
        if global_status == "warning"
        else "Release gate passed."
    )

    return {
        "generated_at": now_iso(),
        "status": global_status,
        "required_domains": required,
        "domain_results": normalized,
        "blocking_domains": blocking_domains,
        "release_recommendation": recommendation,
        "assumptions": [str(item) for item in payload.get("assumptions", []) if str(item).strip()],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run contract parity release gate.")
    parser.add_argument("--input", required=True, help="Path to input JSON.")
    parser.add_argument("--output", required=True, help="Path to output JSON.")
    args = parser.parse_args()

    payload = load_input(Path(args.input))
    result = gate(payload)
    Path(args.output).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
