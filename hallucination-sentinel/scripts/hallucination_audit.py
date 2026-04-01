#!/usr/bin/env python3
import argparse
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

OWNER_MAP = {
    "action_hallucination": ["model-ux-orchestrator", "qa-automation-engineer"],
    "evidence_hallucination": ["web-search-grounding-specialist", "model-ux-orchestrator", "qa-automation-engineer"],
    "context_drop_hallucination": ["web-search-grounding-specialist", "conversation-skill-evolution-director", "qa-automation-engineer"],
    "confidence_miscalibration": ["model-ux-orchestrator", "web-search-grounding-specialist"],
    "truth_guard_blocked_false_success": ["model-ux-orchestrator", "qa-automation-engineer"],
    "deterministic_executor_gap": ["model-ux-orchestrator", "qa-automation-engineer", "principal_code_auditor_worldclass"],
    "no_finding": []
}

CODE_CHANGE_MAP = {
    "action_hallucination": [
        "Require tool/result-backed completion language before user-visible success prose.",
        "Audit timeline completion semantics so failed or unverified actions never render as completed."
    ],
    "evidence_hallucination": [
        "Increase corroboration breadth for time-sensitive answers.",
        "Prefer official and first-party sources before tertiary commentary.",
        "Add evidence sufficiency gating before confident answer generation."
    ],
    "context_drop_hallucination": [
        "Expand follow-up query generation to preserve prior entities and claims.",
        "Improve short-follow-up continuity heuristics."
    ],
    "confidence_miscalibration": [
        "Downgrade certainty wording when evidence is thin, stale, or conflicting.",
        "Add abstain-or-clarify wording policy when proof is insufficient."
    ],
    "truth_guard_blocked_false_success": [
        "Keep truthfulness guard intact and review whether upstream executor/routing can be improved.",
        "Tune the blocked-response wording so it remains useful and precise."
    ],
    "deterministic_executor_gap": [
        "Strengthen deterministic operand resolution for recent context references.",
        "Classify actionable follow-ups before free-form generation can intervene."
    ],
    "no_finding": []
}

TEST_MAP = {
    "action_hallucination": ["No-tool fabricated success claim regression.", "Tool-confirmed action completion regression."],
    "evidence_hallucination": ["Multi-source corroboration threshold regression.", "Official-source ranking regression for current/latest queries."],
    "context_drop_hallucination": ["Short follow-up continuity regression.", "Bare fact-check contextual expansion regression."],
    "confidence_miscalibration": ["Thin-evidence wording regression.", "Conflict-and-staleness abstain regression."],
    "truth_guard_blocked_false_success": ["Truth-guard block regression when no tool proof exists."],
    "deterministic_executor_gap": ["Actionable routing regression for recent listed entities.", "Folder-to-folder move operand resolution regression."],
    "no_finding": []
}

STRONG_CONFIDENCE_PATTERNS = [
    r"\bdone\b",
    r"\bcompleted\b",
    r"\bdefinitely\b",
    r"\bconfirmed\b",
    r"\bcurrent is\b",
    r"\bmoved\b",
    r"\bcreated\b"
]

FILESYSTEM_PATTERNS = [r"\bmove\b", r"\bput\b", r"\bcreate\b", r"\bopen\b", r"\bfolder\b", r"\bfile\b"]
FOLLOWUP_PATTERNS = [r"^fact[ -]?check", r"^verify", r"^is that true", r"^check that", r"\bit\b", r"\bthat\b", r"\bthose\b"]


def sanitize_text(text: str) -> str:
    if not isinstance(text, str):
        return ""
    text = re.sub(r"/Users/[^/\s]+", "/Users/<user>", text)
    text = re.sub(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", "<redacted-email>", text)
    text = re.sub(r"(?i)\b(?:token|api[_-]?key|secret|password)\b\s*[:=]\s*\S+", "<redacted-secret>", text)
    return text


def load_input(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return sanitize_payload(data)


def sanitize_payload(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): sanitize_payload(v) for k, v in value.items()}
    if isinstance(value, list):
        return [sanitize_payload(v) for v in value]
    if isinstance(value, str):
        return sanitize_text(value)
    return value


def count_successful_tool_results(payload: Dict[str, Any]) -> Tuple[int, int, bool, List[str]]:
    tool_calls = payload.get("tool_calls") or payload.get("run_tool_calls") or []
    tool_results = payload.get("tool_results") or payload.get("run_tool_results") or []
    run_events = payload.get("run_events") or []
    verification_present = bool(payload.get("verification_present"))
    notes: List[str] = []

    call_count = len(tool_calls)
    ok_results = 0
    for item in tool_results:
        if isinstance(item, dict) and item.get("ok"):
            ok_results += 1
    if not tool_results and run_events:
        for event in run_events:
            if isinstance(event, dict) and event.get("type") == "run.tool.result" and event.get("ok"):
                ok_results += 1
        call_count = max(call_count, sum(1 for event in run_events if isinstance(event, dict) and event.get("type") == "run.tool.call"))

    if ok_results > 0:
        notes.append(f"Detected {ok_results} successful tool result(s).")
    if verification_present:
        notes.append("Explicit verification evidence was provided.")
    return call_count, ok_results, verification_present, notes


def extract_search_evidence(payload: Dict[str, Any], args: argparse.Namespace) -> Dict[str, Any]:
    evidence = payload.get("search_evidence") or {}
    distinct_domains = int(evidence.get("distinct_domains") or payload.get("distinct_domains") or 0)
    official = bool(evidence.get("official_source_present") or payload.get("official_source_present"))
    finance = bool(evidence.get("finance_priority_present") or payload.get("finance_priority_present"))
    notes = [sanitize_text(note) for note in (evidence.get("notes") or [])]

    if distinct_domains <= 0:
        web_context = sanitize_text(payload.get("web_context") or payload.get("final_answer") or "")
        match = re.search(r"\[SEARCH COVERAGE\]\s+domains=(\d+)\s+official=(yes|no)\s+finance_priority=(yes|no)", web_context, re.IGNORECASE)
        if match:
            distinct_domains = int(match.group(1))
            official = match.group(2).lower() == "yes"
            finance = match.group(3).lower() == "yes"
            notes.append("Derived search coverage from embedded search coverage marker.")

    user_message = sanitize_text(payload.get("user_message") or payload.get("request_summary") or "")
    lowered = user_message.lower()
    finance_query = any(token in lowered for token in ["price", "ticker", "stock", "quote", "trading at"])
    needs_breadth = finance_query or any(token in lowered for token in ["latest", "current", "today", "president", "fact check", "verify"])

    sufficiency = "unknown"
    if distinct_domains > 0 or official or finance:
        sufficiency = "sufficient"
        if finance_query:
            if distinct_domains < args.min_finance_domains or (args.require_official_source and not (finance or official)):
                sufficiency = "limited"
            elif not finance:
                sufficiency = "limited"
        elif needs_breadth:
            if distinct_domains < args.min_distinct_domains and not official:
                sufficiency = "limited"
        elif distinct_domains < 2 and not official:
            sufficiency = "limited"

    return {
        "distinct_domains": distinct_domains,
        "official_source_present": official,
        "finance_priority_present": finance,
        "evidence_sufficiency": sufficiency,
        "notes": notes,
    }


def extract_context_evidence(payload: Dict[str, Any]) -> Dict[str, Any]:
    user_message = sanitize_text(payload.get("user_message") or payload.get("request_summary") or "")
    prior_context = sanitize_text(payload.get("prior_context") or payload.get("chat_history_summary") or "")
    continuity_preserved = bool(payload.get("continuity_preserved", True))
    notes = [sanitize_text(note) for note in (payload.get("context_notes") or [])]
    short_followup = len(re.findall(r"[A-Za-z0-9']+", user_message)) <= 6 or any(re.search(p, user_message, re.IGNORECASE) for p in FOLLOWUP_PATTERNS)
    if short_followup and not prior_context:
        continuity_preserved = False
        notes.append("Short follow-up detected without preserved prior context summary.")
    return {
        "short_followup": short_followup,
        "continuity_preserved": continuity_preserved,
        "notes": notes,
    }


def infer_truth_guard_status(payload: Dict[str, Any], final_answer: str) -> str:
    explicit = payload.get("truthfulness_guard_status")
    if isinstance(explicit, str) and explicit:
        return explicit
    lowered = final_answer.lower()
    if "can't confirm that" in lowered or "cannot confirm that" in lowered or "not yet verified" in lowered:
        return "blocked_false_success"
    return "not_triggered"


def classify(payload: Dict[str, Any], args: argparse.Namespace) -> Tuple[str, str, str, float, List[str]]:
    if args.hallucination_class != "auto":
        return forced_classification(args.hallucination_class)

    user_message = sanitize_text(payload.get("user_message") or payload.get("request_summary") or "")
    final_answer = sanitize_text(payload.get("final_answer") or payload.get("assistant_response") or "")
    trigger_evidence: List[str] = []

    tool_calls, tool_results, verification_present, tool_notes = count_successful_tool_results(payload)
    search_evidence = extract_search_evidence(payload, args)
    context_evidence = extract_context_evidence(payload)
    truth_guard_status = infer_truth_guard_status(payload, final_answer)

    if truth_guard_status == "blocked_false_success" and tool_results == 0:
        if re.search(r"\b(?:move|put|place|create|open|rename)\b", user_message, re.IGNORECASE):
            trigger_evidence.append("Truthfulness guard blocked an unverified action claim.")
            if re.search(r"\b(?:folder|file|desktop|directory)\b", user_message, re.IGNORECASE):
                trigger_evidence.append("User request appears operational and tool-backed.")
            if tool_calls == 0:
                trigger_evidence.append("No tool call was emitted before the guard message.")
                return "deterministic_executor_gap", "medium", "gap_detected", 0.86, trigger_evidence + tool_notes
            return "truth_guard_blocked_false_success", "info", "guard_success", 0.91, trigger_evidence + tool_notes

    if final_answer and any(re.search(pattern, final_answer, re.IGNORECASE) for pattern in STRONG_CONFIDENCE_PATTERNS):
        if tool_results == 0 and any(re.search(pattern, user_message, re.IGNORECASE) for pattern in FILESYSTEM_PATTERNS):
            trigger_evidence.append("Strong completion language was used without successful tool proof.")
            return "action_hallucination", "high", "finding", 0.94, trigger_evidence + tool_notes
        if search_evidence["evidence_sufficiency"] == "limited":
            trigger_evidence.append("Strong certainty language was used even though search evidence was limited.")
            return "confidence_miscalibration", "medium", "finding", 0.88, trigger_evidence + search_evidence["notes"]

    if search_evidence["evidence_sufficiency"] == "limited":
        trigger_evidence.append("Search evidence did not meet the configured corroboration threshold.")
        return "evidence_hallucination", "high", "finding", 0.9, trigger_evidence + search_evidence["notes"]

    if context_evidence["short_followup"] and not context_evidence["continuity_preserved"]:
        trigger_evidence.append("Short follow-up lost prior-turn continuity.")
        return "context_drop_hallucination", "medium", "finding", 0.85, trigger_evidence + context_evidence["notes"]

    return "no_finding", "info", "no_finding", 0.7, ["No high-confidence hallucination or adjacent gap was detected from the provided evidence."]


def forced_classification(kind: str) -> Tuple[str, str, str, float, List[str]]:
    mapping = {
        "action": ("action_hallucination", "high", "finding", 0.95),
        "evidence": ("evidence_hallucination", "high", "finding", 0.95),
        "context": ("context_drop_hallucination", "medium", "finding", 0.95),
        "confidence": ("confidence_miscalibration", "medium", "finding", 0.95),
    }
    klass, severity, verdict, confidence = mapping[kind]
    return klass, severity, verdict, confidence, [f"Classification was forced via --hallucination-class {kind}."]


def build_root_cause(klass: str) -> str:
    mapping = {
        "action_hallucination": "no-proof completion wording",
        "evidence_hallucination": "evidence insufficiency",
        "context_drop_hallucination": "context continuity failure",
        "confidence_miscalibration": "confidence wording bug",
        "truth_guard_blocked_false_success": "truthfulness guard success",
        "deterministic_executor_gap": "executor gap",
        "no_finding": "no confirmed hallucination finding",
    }
    return mapping.get(klass, "unknown")


def build_portability_notes() -> List[str]:
    return [
        "Reports should stay sanitized and must not include raw host-specific paths.",
        "Use optional project profiles for repository-specific guidance instead of hardcoding project assumptions into the generic workflow.",
        "Structured outputs are local artifacts and should remain privacy-safe before mirroring or sharing."
    ]


def build_pulse_events(report: Dict[str, Any]) -> List[Dict[str, Any]]:
    payload = {
        "hallucination_class": report["hallucination_class"],
        "severity": report["severity"],
        "root_cause": report["root_cause"],
        "owner_skills": report["recommended_owner_skills"],
        "regression_required": bool(report["recommended_tests"]),
        "evidence_sufficiency": report["search_evidence"]["evidence_sufficiency"],
        "truth_guard_status": report["truthfulness_guard_status"],
    }
    events = [{"event_type": "hallucination.audit.completed", "payload": payload}]
    if report["verdict"] in {"finding", "gap_detected"}:
        events.append({"event_type": "hallucination.remediation.recommended", "payload": payload})
    if report["recommended_tests"]:
        events.append({"event_type": "hallucination.regression.required", "payload": payload})
    if report["hallucination_class"] == "truth_guard_blocked_false_success":
        events.append({"event_type": "hallucination.truth_guard.confirmed", "payload": payload})
    if report["hallucination_class"] == "deterministic_executor_gap":
        events.append({"event_type": "hallucination.executor_gap.confirmed", "payload": payload})
    if report["severity"] in {"high", "critical"} and report["verdict"] in {"finding", "gap_detected"}:
        events.append({"event_type": "hallucination.audit.blocking", "payload": payload})
    return events


def build_report(payload: Dict[str, Any], args: argparse.Namespace) -> Dict[str, Any]:
    final_answer = sanitize_text(payload.get("final_answer") or payload.get("assistant_response") or "")
    request_summary = sanitize_text(payload.get("request_summary") or payload.get("user_message") or "(no request summary provided)")
    tool_calls, tool_results, verification_present, tool_notes = count_successful_tool_results(payload)
    search_evidence = extract_search_evidence(payload, args)
    context_evidence = extract_context_evidence(payload)
    truthfulness_guard_status = infer_truth_guard_status(payload, final_answer)
    klass, severity, verdict, confidence, trigger_evidence = classify(payload, args)
    report = {
        "request_summary": request_summary,
        "hallucination_class": klass,
        "severity": severity,
        "verdict": verdict,
        "confidence": confidence,
        "trigger_evidence": trigger_evidence,
        "tool_evidence": {
            "tool_calls": tool_calls,
            "tool_results": tool_results,
            "verification_present": verification_present,
            "notes": tool_notes,
        },
        "search_evidence": search_evidence,
        "context_evidence": context_evidence,
        "truthfulness_guard_status": truthfulness_guard_status,
        "root_cause": build_root_cause(klass),
        "recommended_owner_skills": OWNER_MAP.get(klass, []),
        "recommended_code_changes": CODE_CHANGE_MAP.get(klass, []),
        "recommended_tests": TEST_MAP.get(klass, []),
        "portability_notes": build_portability_notes(),
    }
    if args.emit_pulse_events:
        report["pulse_events"] = build_pulse_events(report)
    return report


def render_markdown(report: Dict[str, Any], args: argparse.Namespace) -> str:
    lines = [
        "# Hallucination Audit Report",
        "",
        f"- Mode: `{args.mode}`",
        f"- Project profile: `{args.project_profile}`",
        f"- Hallucination class: `{report['hallucination_class']}`",
        f"- Severity: `{report['severity']}`",
        f"- Verdict: `{report['verdict']}`",
        f"- Confidence: `{report['confidence']:.2f}`",
        "",
        "## Request Summary",
        report["request_summary"],
        "",
        "## Trigger Evidence",
    ]
    lines.extend([f"- {item}" for item in report["trigger_evidence"]] or ["- None"])
    lines.extend([
        "",
        "## Tool Evidence",
        f"- Tool calls: {report['tool_evidence']['tool_calls']}",
        f"- Successful tool results: {report['tool_evidence']['tool_results']}",
        f"- Explicit verification present: {'yes' if report['tool_evidence']['verification_present'] else 'no'}",
    ])
    lines.extend([f"- {item}" for item in report["tool_evidence"].get("notes", [])])
    lines.extend([
        "",
        "## Search Evidence",
        f"- Distinct domains: {report['search_evidence']['distinct_domains']}",
        f"- Official source present: {'yes' if report['search_evidence']['official_source_present'] else 'no'}",
        f"- Finance-priority source present: {'yes' if report['search_evidence']['finance_priority_present'] else 'no'}",
        f"- Evidence sufficiency: {report['search_evidence']['evidence_sufficiency']}",
    ])
    lines.extend([f"- {item}" for item in report['search_evidence'].get('notes', [])])
    lines.extend([
        "",
        "## Context Evidence",
        f"- Short follow-up: {'yes' if report['context_evidence']['short_followup'] else 'no'}",
        f"- Continuity preserved: {'yes' if report['context_evidence']['continuity_preserved'] else 'no'}",
    ])
    lines.extend([f"- {item}" for item in report['context_evidence'].get('notes', [])])
    lines.extend([
        "",
        "## Root Cause",
        f"- Truthfulness guard status: `{report['truthfulness_guard_status']}`",
        f"- Root cause: `{report['root_cause']}`",
        "",
        "## Recommended Owner Skills",
    ])
    lines.extend([f"- `{item}`" for item in report['recommended_owner_skills']] or ["- None"])
    lines.extend([
        "",
        "## Recommended Code Changes",
    ])
    lines.extend([f"- {item}" for item in report['recommended_code_changes']] or ["- None"])
    lines.extend([
        "",
        "## Recommended Tests",
    ])
    lines.extend([f"- {item}" for item in report['recommended_tests']] or ["- None"])
    lines.extend([
        "",
        "## Portability Notes",
    ])
    lines.extend([f"- {item}" for item in report['portability_notes']] or ["- None"])
    if report.get("pulse_events"):
        lines.extend([
            "",
            "## Pulse Events",
        ])
        for event in report["pulse_events"]:
            lines.append(f"- `{event['event_type']}`")
    return "\n".join(lines).strip() + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Structured hallucination auditor and remediation planner.")
    parser.add_argument("--input", required=True, help="Path to the sanitized evidence JSON input.")
    parser.add_argument("--out-md", required=True, help="Path to write the Markdown report.")
    parser.add_argument("--out-json", required=True, help="Path to write the JSON report.")
    parser.add_argument("--mode", choices=["audit", "triage", "regression-plan"], default="audit")
    parser.add_argument("--hallucination-class", choices=["auto", "action", "evidence", "context", "confidence"], default="auto")
    parser.add_argument("--strictness", choices=["high", "balanced", "broad"], default="high")
    parser.add_argument("--require-official-source", action="store_true")
    parser.add_argument("--min-distinct-domains", type=int, default=3)
    parser.add_argument("--min-finance-domains", type=int, default=2)
    parser.add_argument("--emit-pulse-events", action="store_true")
    parser.add_argument("--project-profile", choices=["generic", "pfemacos"], default="generic")
    return parser.parse_args()


def ensure_parent(path: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)


def main() -> int:
    args = parse_args()
    payload = load_input(args.input)
    report = build_report(payload, args)
    markdown = render_markdown(report, args)

    ensure_parent(args.out_md)
    ensure_parent(args.out_json)
    with open(args.out_md, "w", encoding="utf-8") as f:
        f.write(markdown)
    with open(args.out_json, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=True)
        f.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
