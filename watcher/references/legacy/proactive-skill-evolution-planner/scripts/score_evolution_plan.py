#!/usr/bin/env python3
"""Deterministically score update-vs-new skill evolution candidates."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

SIGNAL_TAGS = {
    "reference_parity",
    "source_truth",
    "manual_audit",
    "performance_incident",
    "render_pressure",
    "public_first_data",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def clamp_1_5(value: Any, default: int = 3) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(1, min(5, parsed))


def clamp_non_negative_int(value: Any, default: int = 0) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(0, parsed)


def normalize_signal_tags(value: Any) -> List[str]:
    if not value:
        return []
    raw = value if isinstance(value, list) else [value]
    normalized: List[str] = []
    for item in raw:
        tag = str(item).strip().lower().replace("-", "_").replace(" ", "_")
        if tag in SIGNAL_TAGS and tag not in normalized:
            normalized.append(tag)
    return normalized


def load_candidates(path: Path) -> List[Dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        items = payload.get("candidates", [])
        if isinstance(items, list):
            return [item for item in items if isinstance(item, dict)]
    raise ValueError("Input must be a candidate list or object with 'candidates'.")


def parse_git_status_line(line: str) -> tuple[str, str] | None:
    if len(line) < 4:
        return None
    status = line[:2]
    path = line[3:].strip()
    if not path:
        return None
    if " -> " in path:
        path = path.split(" -> ", 1)[1].strip()
    return status, path


def list_git_status(workspace_root: Path) -> List[tuple[str, str]]:
    cmd = [
        "git",
        "-C",
        str(workspace_root),
        "status",
        "--short",
        "--untracked-files=all",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        return []
    rows: List[tuple[str, str]] = []
    for raw in result.stdout.splitlines():
        parsed = parse_git_status_line(raw.rstrip("\n"))
        if parsed is None:
            continue
        rows.append(parsed)
    return rows


def extract_skill_ref(path_text: str) -> tuple[str, str] | None:
    normalized = path_text.strip().replace("\\", "/")
    parts = [p for p in normalized.split("/") if p]
    patterns = [
        ([".agent", "skills"], "workspace_local"),
        (["global-skills", "codex"], "workspace_global"),
        ([".codex", "skills"], "codex_global"),
        (["skills"], "generic_skills"),
    ]
    for prefix, root_tag in patterns:
        if len(parts) <= len(prefix):
            continue
        if parts[: len(prefix)] != prefix:
            continue
        skill_id = parts[len(prefix)]
        if not skill_id:
            continue
        return root_tag, skill_id
    return None


def synthesize_update_candidate(skill_id: str, signal: Dict[str, Any]) -> Dict[str, Any]:
    file_count = int(signal.get("file_count", 0))
    roots = set(signal.get("roots", []))
    touched_types = set(signal.get("types", []))
    status_codes = set(signal.get("status_codes", []))

    demand = min(5, 2 + min(file_count, 8) // 2 + (1 if len(roots) >= 2 else 0))
    impact = 2
    if "manifest" in touched_types:
        impact += 1
    if "script" in touched_types:
        impact += 1
    if file_count >= 4:
        impact += 1
    impact = min(5, impact)

    confidence = 2
    if file_count >= 2:
        confidence += 1
    if len(roots) >= 2:
        confidence += 1
    if "skill_doc" in touched_types:
        confidence += 1
    confidence = min(5, confidence)

    reason = (
        f"Detected active skill edits for {skill_id}: "
        f"{file_count} file(s), roots={sorted(roots)}, types={sorted(touched_types)}."
    )
    if status_codes == {"??"}:
        reason = (
            f"Detected new untracked files for {skill_id}; treat as update candidate unless explicit new-skill intent is provided."
        )

    return {
        "name": f"Update {skill_id} from git activity",
        "target_skill_id": skill_id,
        "overlap_score": 5,
        "demand_score": demand,
        "impact_score": impact,
        "reuse_fit_score": 5,
        "confidence_score": confidence,
        "reason": reason,
        "evidence_refs": [
            "git:status_short",
            f"git:skill:{skill_id}",
            f"git:roots:{','.join(sorted(roots)) or 'unknown'}",
        ],
    }


def infer_candidates_from_git(workspace_root: Path) -> List[Dict[str, Any]]:
    rows = list_git_status(workspace_root)
    by_skill: Dict[str, Dict[str, Any]] = {}

    for status, path_text in rows:
        ref = extract_skill_ref(path_text)
        if ref is None:
            continue
        root_tag, skill_id = ref
        signal = by_skill.setdefault(
            skill_id,
            {"file_count": 0, "roots": set(), "types": set(), "status_codes": set()},
        )
        signal["file_count"] += 1
        signal["roots"].add(root_tag)
        signal["status_codes"].add(status)

        name = Path(path_text).name
        parts = set(path_text.replace("\\", "/").split("/"))
        if name in {"manifest.json", "manifest.v2.json"}:
            signal["types"].add("manifest")
        if name == "SKILL.md":
            signal["types"].add("skill_doc")
        if "scripts" in parts:
            signal["types"].add("script")
        if "references" in parts:
            signal["types"].add("reference")

    candidates: List[Dict[str, Any]] = []
    for skill_id in sorted(by_skill.keys()):
        signal = by_skill[skill_id]
        candidates.append(synthesize_update_candidate(skill_id, signal))
    return candidates


def merge_candidates(candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    merged: Dict[str, Dict[str, Any]] = {}
    for candidate in candidates:
        key = str(
            candidate.get("target_skill_id")
            or candidate.get("proposed_skill_id")
            or candidate.get("name")
            or "candidate"
        )
        existing = merged.get(key)
        if existing is None:
            merged[key] = candidate
            continue

        # Keep the stronger confidence/impact signal when duplicates exist.
        if clamp_1_5(candidate.get("confidence_score")) > clamp_1_5(existing.get("confidence_score")):
            merged[key] = candidate
            continue
        if clamp_1_5(candidate.get("impact_score")) > clamp_1_5(existing.get("impact_score")):
            merged[key] = candidate
    return [merged[key] for key in sorted(merged.keys())]


def decide_action(
    overlap: int,
    demand: int,
    reuse_fit: int,
    confidence: int,
    repeat_evidence_count: int,
    signal_tags: List[str],
) -> str:
    if confidence <= 2:
        return "defer"
    if overlap >= 4 and reuse_fit >= 4:
        return "update_existing"
    if overlap <= 2 and demand >= 4:
        if repeat_evidence_count < 2:
            return "defer"
        return "create_new"
    if overlap >= 2 and signal_tags:
        return "update_existing"
    if overlap >= 3:
        return "update_existing"
    return "defer"


def score_candidate(candidate: Dict[str, Any]) -> Dict[str, Any]:
    overlap = clamp_1_5(candidate.get("overlap_score"))
    demand = clamp_1_5(candidate.get("demand_score"))
    impact = clamp_1_5(candidate.get("impact_score"))
    reuse_fit = clamp_1_5(candidate.get("reuse_fit_score"))
    confidence = clamp_1_5(candidate.get("confidence_score"))
    signal_tags = normalize_signal_tags(candidate.get("signal_tags"))
    repeat_evidence_count = clamp_non_negative_int(candidate.get("repeat_evidence_count"), default=0)

    signal_boost = 1 if signal_tags else 0
    if len(signal_tags) >= 3:
        signal_boost += 1
    repeat_boost = 1 if repeat_evidence_count >= 2 else 0
    impact = min(5, impact + signal_boost)
    confidence = min(5, confidence + signal_boost)
    demand = min(5, demand + repeat_boost)

    # Weighted score on 0-100 scale.
    score = 0.0
    score += 30.0 * (overlap / 5.0)
    score += 20.0 * (demand / 5.0)
    score += 20.0 * (impact / 5.0)
    score += 15.0 * (reuse_fit / 5.0)
    score += 15.0 * (confidence / 5.0)

    action = decide_action(overlap, demand, reuse_fit, confidence, repeat_evidence_count, signal_tags)
    enriched = dict(candidate)
    enriched["score_breakdown"] = {
        "overlap_score": overlap,
        "demand_score": demand,
        "impact_score": impact,
        "reuse_fit_score": reuse_fit,
        "confidence_score": confidence,
    }
    enriched["total_score"] = round(score, 2)
    enriched["recommended_action"] = action
    enriched["normalized_signal_tags"] = signal_tags
    enriched["repeat_evidence_count"] = repeat_evidence_count
    return enriched


def rank(candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    scored = [score_candidate(item) for item in candidates]
    scored.sort(
        key=lambda item: (
            -float(item.get("total_score", 0.0)),
            item.get("recommended_action", ""),
            str(item.get("target_skill_id") or item.get("proposed_skill_id") or item.get("name") or ""),
        )
    )
    for idx, item in enumerate(scored, start=1):
        item["rank"] = idx
    return scored


def summarize(scored: List[Dict[str, Any]]) -> Dict[str, int]:
    summary = {"update_existing": 0, "create_new": 0, "defer": 0}
    for item in scored:
        action = str(item.get("recommended_action", "defer"))
        if action not in summary:
            action = "defer"
        summary[action] += 1
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Score proactive skill evolution candidates.")
    parser.add_argument("--input", help="Path to candidate input JSON.")
    parser.add_argument(
        "--auto-from-git",
        action="store_true",
        help="Infer candidates from git changed skill paths in --workspace-root.",
    )
    parser.add_argument(
        "--workspace-root",
        default=os.getcwd(),
        help="Workspace root for git-signal inference (default: cwd).",
    )
    parser.add_argument("--output", required=True, help="Path to output JSON.")
    args = parser.parse_args()

    candidates: List[Dict[str, Any]] = []
    if args.input:
        candidates.extend(load_candidates(Path(args.input)))
    if args.auto_from_git:
        workspace_root = Path(args.workspace_root).expanduser().resolve()
        candidates.extend(infer_candidates_from_git(workspace_root))

    candidates = merge_candidates(candidates)
    if not candidates:
        if args.auto_from_git and not args.input:
            payload = {
                "generated_at": now_iso(),
                "count": 0,
                "summary": {"update_existing": 0, "create_new": 0, "defer": 0},
                "candidates": [],
                "note": "No skill-path git signals detected in workspace.",
            }
            Path(args.output).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            return
        raise ValueError("No candidates found. Provide --input and/or --auto-from-git.")

    scored = rank(candidates)
    payload = {
        "generated_at": now_iso(),
        "count": len(scored),
        "summary": summarize(scored),
        "candidates": scored,
    }
    Path(args.output).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
