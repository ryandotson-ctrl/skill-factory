#!/usr/bin/env python3
"""Deterministically score and rank trend candidates."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def clamp_score(value: Any, default: int = 3) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(1, min(5, parsed))


def load_candidates(path: Path) -> List[Dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        trends = payload.get("trends", [])
        if isinstance(trends, list):
            return [item for item in trends if isinstance(item, dict)]
    raise ValueError("Input must be a list of trend objects or an object with a 'trends' list.")


def weighted_score(candidate: Dict[str, Any]) -> Dict[str, Any]:
    impact = clamp_score(candidate.get("impact"))
    feasibility = clamp_score(candidate.get("feasibility"))
    evidence = clamp_score(candidate.get("evidence"))
    effort = clamp_score(candidate.get("effort"))
    time_to_value = clamp_score(candidate.get("time_to_value"))

    score = 0.0
    score += 25.0 * (impact / 5.0)
    score += 25.0 * (feasibility / 5.0)
    score += 20.0 * (evidence / 5.0)
    score += 15.0 * ((6 - effort) / 5.0)
    score += 15.0 * ((6 - time_to_value) / 5.0)

    enriched = dict(candidate)
    enriched["normalized_scores"] = {
        "impact": impact,
        "feasibility": feasibility,
        "evidence": evidence,
        "effort": effort,
        "time_to_value": time_to_value,
    }
    enriched["total_score"] = round(score, 2)
    return enriched


def rank_candidates(candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    scored = [weighted_score(item) for item in candidates]

    def sort_key(item: Dict[str, Any]) -> Any:
        name = str(item.get("name") or item.get("trend") or item.get("title") or "").lower()
        evidence = item.get("normalized_scores", {}).get("evidence", 0)
        return (-float(item.get("total_score", 0.0)), -int(evidence), name)

    scored.sort(key=sort_key)
    for idx, item in enumerate(scored, start=1):
        item["rank"] = idx
    return scored


def build_output(ranked: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "generated_at": now_iso(),
        "count": len(ranked),
        "ranking_model": {
            "impact": 25,
            "feasibility": 25,
            "evidence": 20,
            "effort_inverse": 15,
            "time_to_value_inverse": 15,
        },
        "trends": ranked,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Score and rank trend candidates.")
    parser.add_argument("--input", required=True, help="Path to input JSON.")
    parser.add_argument("--output", help="Path for output JSON. If omitted, prints to stdout.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print output JSON.")
    args = parser.parse_args()

    input_path = Path(args.input)
    candidates = load_candidates(input_path)
    ranked = rank_candidates(candidates)
    output = build_output(ranked)

    indent = 2 if args.pretty else None
    body = json.dumps(output, indent=indent, ensure_ascii=True)
    if args.output:
        Path(args.output).write_text(body + ("\n" if indent is not None else ""), encoding="utf-8")
    else:
        print(body)


if __name__ == "__main__":
    main()
