#!/usr/bin/env python3
"""Index docs/contracts and emit deterministic parity gate checklist."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List


DOMAIN_MAP = {
    "chat_runtime": "chat_runtime.md",
    "search_grounding": "search_grounding.md",
    "rag": "rag.md",
    "model_lifecycle": "model_lifecycle.md",
    "training_pipeline": "training_pipeline.md",
    "filesystem_actions": "filesystem_actions.md",
    "sessions": "sessions.md",
    "workspaces": "workspaces.md",
    "model_catalog": "model_catalog.md",
    "browser_automation": "browser_automation.md",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def classify_contract(path: Path) -> Dict[str, str]:
    if not path.exists():
        return {
            "status": "warning",
            "parity_gate": "Contract missing in workspace.",
            "schema_evidence": "No contract file found.",
            "remediation": "Add contract file or mark domain as out of scope.",
        }

    text = path.read_text(encoding="utf-8", errors="replace")
    has_gate = "Parity Gates" in text or "Parity Gate" in text
    has_error_taxonomy = "Error Taxonomy" in text
    if has_gate and has_error_taxonomy:
        return {
            "status": "pass",
            "parity_gate": "Contract includes parity gates and error taxonomy.",
            "schema_evidence": "Structured gate language detected.",
            "remediation": "None",
        }
    return {
        "status": "warning",
        "parity_gate": "Contract exists but gate structure is incomplete.",
        "schema_evidence": "Missing parity or error taxonomy headings.",
        "remediation": "Add explicit parity gates and error taxonomy section.",
    }


def build_report(contracts_root: Path) -> Dict[str, object]:
    domains: List[Dict[str, str]] = []
    blocker_count = 0
    warning_count = 0

    for domain, filename in DOMAIN_MAP.items():
        file_path = contracts_root / filename
        result = classify_contract(file_path)
        status = str(result["status"])
        if status == "warning":
            warning_count += 1
        if status == "blocker":
            blocker_count += 1
        domains.append(
            {
                "domain": domain,
                "contract_file": str(file_path),
                "status": status,
                "parity_gate": result["parity_gate"],
                "schema_evidence": result["schema_evidence"],
                "remediation": result["remediation"],
            }
        )

    overall = "pass"
    if blocker_count > 0:
        overall = "blocker"
    elif warning_count > 0:
        overall = "warning"

    return {
        "generated_at": now_iso(),
        "contracts_root": str(contracts_root),
        "overall_status": overall,
        "summary": {
            "domains": len(domains),
            "warnings": warning_count,
            "blockers": blocker_count,
        },
        "domains": domains,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Check contract parity coverage.")
    parser.add_argument("--contracts-root", required=True, help="Path to docs/contracts directory.")
    parser.add_argument("--output", required=True, help="Output JSON path.")
    args = parser.parse_args()

    report = build_report(Path(args.contracts_root).resolve())
    Path(args.output).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
