#!/usr/bin/env python3
"""Render a normalized BI report markdown from JSON input."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def as_list(value: Any) -> List[Any]:
    if isinstance(value, list):
        return value
    if value is None:
        return []
    return [value]


def read_json(path: Path) -> Dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Input JSON must be an object.")
    return payload


def render_bullets(items: Iterable[Any]) -> List[str]:
    lines: List[str] = []
    for item in items:
        if isinstance(item, dict):
            label = str(item.get("label") or item.get("name") or item.get("item") or "Item")
            text = str(item.get("text") or item.get("summary") or item.get("value") or "")
            lines.append(f"- {label}: {text}".rstrip(": "))
        else:
            lines.append(f"- {item}")
    return lines


def render_top_trends(trends: List[Dict[str, Any]]) -> List[str]:
    lines = [
        "## Top Trends With Evidence Grade",
        "",
        "| Trend | Evidence Grade | Score | Claim Label | Summary |",
        "|---|---:|---:|---|---|",
    ]
    for trend in trends:
        name = str(trend.get("name") or trend.get("trend") or "Unnamed Trend")
        grade = str(trend.get("evidence_grade") or "N/A")
        score = str(trend.get("score") or trend.get("total_score") or "N/A")
        label = str(trend.get("claim_label") or trend.get("claim_type") or "[INFERENCE]")
        summary = str(trend.get("summary") or "").replace("\n", " ").strip()
        lines.append(f"| {name} | {grade} | {score} | {label} | {summary} |")
    lines.append("")

    for trend in trends:
        name = str(trend.get("name") or trend.get("trend") or "Unnamed Trend")
        sources = as_list(trend.get("sources"))
        if not sources:
            continue
        lines.append(f"### Sources: {name}")
        for src in sources:
            if isinstance(src, dict):
                url = str(src.get("url") or "N/A")
                date = str(src.get("date") or "N/A")
                lines.append(f"- {url} ({date})")
            else:
                lines.append(f"- {src}")
        lines.append("")
    return lines


def render_decision_matrix(items: List[Dict[str, Any]]) -> List[str]:
    lines = [
        "## Decision Matrix",
        "",
        "| Action | Impact | Feasibility | Evidence | Effort | Time to Value | Owner | Confidence Note |",
        "|---|---:|---:|---:|---:|---:|---|---|",
    ]
    for item in items:
        action = str(item.get("action") or "N/A")
        impact = str(item.get("impact") or item.get("expected_impact") or "N/A")
        feasibility = str(item.get("feasibility") or "N/A")
        evidence = str(item.get("evidence") or item.get("evidence_strength") or "N/A")
        effort = str(item.get("effort") or "N/A")
        ttv = str(item.get("time_to_value") or "N/A")
        owner = str(item.get("owner") or "Unassigned")
        note = str(item.get("confidence_note") or "")
        lines.append(
            f"| {action} | {impact} | {feasibility} | {evidence} | {effort} | {ttv} | {owner} | {note} |"
        )
    lines.append("")
    return lines


def render_decision_lanes(payload: Dict[str, Any]) -> List[str]:
    lanes = payload.get("decision_lanes", {})
    if not isinstance(lanes, dict):
        lanes = {}
    lines = ["## Decision Lanes", ""]
    for key, title in (
        ("adopt_now", "### Adopt Now"),
        ("prototype_next", "### Prototype Next"),
        ("monitor", "### Monitor"),
    ):
        lines.append(title)
        entries = as_list(lanes.get(key))
        if entries:
            lines.extend(render_bullets(entries))
        else:
            lines.append("- None")
        lines.append("")
    return lines


def render_companion_skill_fit(payload: Dict[str, Any]) -> List[str]:
    entries = as_list(payload.get("companion_skill_fit"))
    lines = ["## Companion Skill Fit", ""]
    if not entries:
        lines.append("- None")
        lines.append("")
        return lines

    for item in entries:
        if isinstance(item, dict):
            skill = str(item.get("skill") or item.get("name") or "Skill")
            fit = str(item.get("fit") or "fit")
            why = str(item.get("why") or item.get("summary") or "").strip()
            lines.append(f"- {skill} ({fit}): {why}".rstrip(": "))
        else:
            lines.append(f"- {item}")
    lines.append("")
    return lines


def render_backlog(payload: Dict[str, Any]) -> List[str]:
    backlog = payload.get("backlog", {})
    if not isinstance(backlog, dict):
        backlog = {}
    lines = ["## 30/60/90-Day Action Backlog", ""]

    for key, title in (
        ("30_days", "### 30 Days"),
        ("60_days", "### 60 Days"),
        ("90_days", "### 90 Days"),
    ):
        lines.append(title)
        entries = as_list(backlog.get(key))
        if entries:
            lines.extend(render_bullets(entries))
        else:
            lines.append("- None")
        lines.append("")
    return lines


def render_risks_unknowns(payload: Dict[str, Any]) -> List[str]:
    lines = ["## Risks and Unknowns", "", "### Risks"]
    risks = as_list(payload.get("risks"))
    if risks:
        lines.extend(render_bullets(risks))
    else:
        lines.append("- None")
    lines.append("")
    lines.append("### Unknowns")
    unknowns = as_list(payload.get("unknowns"))
    if unknowns:
        lines.extend(render_bullets(unknowns))
    else:
        lines.append("- None")
    lines.append("")
    return lines


def render_profile_appendix(payload: Dict[str, Any]) -> List[str]:
    appendix = payload.get("profile_appendix")
    if appendix is None:
        return []

    lines = ["## Optional Project Profile Appendix", ""]
    if isinstance(appendix, dict):
        profile_name = str(appendix.get("profile") or "Profile")
        lines.append(f"### {profile_name}")
        lines.append("")
        notes = as_list(appendix.get("notes"))
        if notes:
            lines.extend(render_bullets(notes))
        else:
            lines.append("- None")
        lines.append("")
        return lines

    entries = as_list(appendix)
    if entries:
        lines.extend(render_bullets(entries))
    else:
        lines.append("- None")
    lines.append("")
    return lines


def build_markdown(payload: Dict[str, Any]) -> str:
    generated_at = str(payload.get("generated_at") or now_iso())
    evidence_window = payload.get("evidence_window") or {}
    oldest = str(evidence_window.get("oldest") or "N/A")
    newest = str(evidence_window.get("newest") or "N/A")
    assumptions = as_list(payload.get("assumptions"))

    lines: List[str] = ["# Agent BI Strategic Report", "", f"Generated At: {generated_at}", ""]

    lines.append("## Executive Summary")
    lines.append("")
    summary = payload.get("executive_summary")
    if isinstance(summary, str) and summary.strip():
        lines.append(summary.strip())
    else:
        summary_lines = render_bullets(as_list(summary))
        if summary_lines:
            lines.extend(summary_lines)
        else:
            lines.append("- No executive summary provided.")
    lines.append("")

    trends = [t for t in as_list(payload.get("top_trends")) if isinstance(t, dict)]
    lines.extend(render_top_trends(trends))

    lines.extend(render_decision_lanes(payload))
    lines.extend(render_companion_skill_fit(payload))

    matrix = [m for m in as_list(payload.get("decision_matrix")) if isinstance(m, dict)]
    lines.extend(render_decision_matrix(matrix))

    lines.extend(render_backlog(payload))
    lines.extend(render_risks_unknowns(payload))
    lines.extend(render_profile_appendix(payload))

    lines.append("## Metadata")
    lines.append("")
    lines.append(f"- Evidence Window: {oldest} to {newest}")
    if assumptions:
        lines.append("- Assumptions:")
        for assumption in assumptions:
            lines.append(f"  - {assumption}")
    else:
        lines.append("- Assumptions: None")
    lines.append("")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Render a normalized BI report markdown.")
    parser.add_argument("--input", required=True, help="Input JSON path.")
    parser.add_argument("--output", required=True, help="Output markdown path.")
    args = parser.parse_args()

    payload = read_json(Path(args.input))
    markdown = build_markdown(payload)
    Path(args.output).write_text(markdown + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
