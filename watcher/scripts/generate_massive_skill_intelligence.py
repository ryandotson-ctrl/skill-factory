#!/usr/bin/env python3
"""Generate Watcher-grade, source-aware skill intelligence for The Watcher."""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover - dependency may be absent in minimal envs
    yaml = None


CACHE_SKIP = {"__pycache__", ".pytest_cache"}
BACKUP_SKIP = {"_p0_backups", ".backups", ".skill-backups"}
ARCHIVE_SKIP_SEQUENCES = (("references", "legacy"),)
SOURCE_PRIORITY = {"codex": 0, "antigravity": 1, "workspace_mirror": 2, "local": 3, "agents": 4}
DIRECTOR_PRIORITY = {"codex": 0, "antigravity": 1, "workspace_mirror": 2, "local": 3, "agents": 4}
SEMVER_PATTERN = re.compile(r"^\s*(\d+)\.(\d+)\.(\d+)")
EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
PHONE_PATTERN = re.compile(r"\b(?:\+?\d[\d\-\s().]{7,}\d)\b")
SECRET_PATTERN = re.compile(
    r"(?i)\b(api[_-]?key|access[_-]?token|secret|password|passwd|bearer)\b\s*[:=]\s*([^\s,;]+)"
)
EVENT_NAME_PATTERN = re.compile(r"^[a-z0-9:._*\-]+$")
ADDITIVE_CHANGE_PATTERN = re.compile(
    r"\b(add|append|augment|extend|expand|include|introduce|enrich|emit|surface|strengthen|improve)\b",
    re.IGNORECASE,
)
DESTRUCTIVE_CHANGE_PATTERN = re.compile(
    r"\b(delete|remove|drop|erase|overwrite|truncate|hard\s*reset|reset\s+--hard|replace\s+entire|rewrite\s+from\s+scratch)\b",
    re.IGNORECASE,
)
PORTABILITY_PATTERN = re.compile(
    r"\b(portable|path-agnostic|host-agnostic|workspace-agnostic|privacy|sanitized|redacted|no private paths|avoid private paths)\b",
    re.IGNORECASE,
)

LEGACY_OUTPUT_JSON = ".agent/skills/watcher/skill_intelligence.json"
ISOLATED_OUTPUT_JSON = ".agent/skills/watcher/_generated/skill_intelligence.json"

STOP_WORDS = {
    "the",
    "and",
    "with",
    "that",
    "this",
    "from",
    "have",
    "your",
    "into",
    "for",
    "are",
    "was",
    "were",
    "will",
    "would",
    "about",
    "after",
    "before",
    "over",
    "under",
    "when",
    "where",
    "what",
    "which",
    "while",
    "should",
    "could",
    "must",
    "also",
    "just",
    "then",
    "than",
    "them",
    "they",
    "their",
    "there",
    "been",
    "being",
    "using",
    "used",
    "across",
    "local",
    "global",
    "skill",
    "skills",
    "session",
    "workspace",
}

AUTO_CONTEXT_FILES = [
    "README.md",
    "docs/README.md",
    "docs/RUNLOG.md",
    "artifacts/training/RunLog.md",
    "docs/ROADMAP.md",
    ".agent/context/session_context.json",
    ".agent/context/session_context.md",
    ".agent/ecosystem_state.json",
    "issues.md",
]

WORKSPACE_GOAL_FILES = [
    ".agent/context/session_context.json",
    ".agent/context/session_context.md",
    ".agent/workspace_goal.md",
    ".agent/WORKSPACE_GOAL.md",
    "GOALS.md",
    "ROADMAP.md",
    "README.md",
    "docs/README.md",
    "issues.md",
]

WORKSPACE_SCAN_SKIP_DIRS = {
    ".git",
    ".idea",
    ".vscode",
    "node_modules",
    ".next",
    "dist",
    "build",
    "target",
    "vendor",
    "__pycache__",
    ".pytest_cache",
    ".venv",
    "venv",
    "venv_312",
    ".mypy_cache",
    ".ruff_cache",
    ".cache",
}

WORKSPACE_SCAN_SKIP_FILES = {
    ".DS_Store",
}

SESSION_CONTEXT_FALLBACK_CHAIN = ("file", "env", "auto", "empty")
ECOSYSTEM_CONTRACT_PATH = Path(__file__).resolve().parent.parent / "references" / "ecosystem_contract_v1.yaml"
FALLBACK_ECOSYSTEM_CONTRACT: Dict[str, Any] = {
    "inventory_roles": {
        "standard": {"path_prefixes": []},
        "system_hidden": {"path_prefixes": [".system/"]},
        "runtime_bundle": {"path_prefixes": ["codex-primary-runtime/"]},
        "backup_snapshot": {"path_prefixes": [".skill-backups/", "_p0_backups/", ".backups/"]},
    },
    "root_roles": {
        "codex": "canonical_authoring",
        "antigravity": "distribution_mirror",
        "workspace_mirror": "publication_mirror",
        "local": "workspace_local",
        "agents": "auxiliary_global",
    },
    "external_event_registry": {
        "runtime_patterns": [
            "backend_ipc_error_detected",
            "backend_transport_changed",
            "filesystem_action_gap_detected",
            "grounding_gap_detected",
            "ipc_auth_failure_detected",
            "run.completed",
            "run.error",
            "run.failed",
            "run.search.query",
            "run.tool.result",
            "run:finished",
            "truthfulness_guard_triggered",
            "web_evidence_thin_detected",
        ],
        "operator_patterns": [
            "apple:build_harness_install_requested",
            "apple:project_adoption_requested",
            "apple:project_bootstrap_requested",
            "apple:release_requested",
            "artifact:ready_for_target_check",
            "bundle.integrity.failed",
            "capability:negotiation_requested",
            "code_change",
            "compatibility:check_requested",
            "contract_parity_report_emitted",
            "eval:run_requested",
            "experiment:package_requested",
            "git.push.requested",
            "git:push_complete",
            "git_hygiene_check_requested",
            "issue:ingest_requested",
            "issue:reconcile_requested",
            "issue:scan_requested",
            "launch:preflight_requested",
            "launch:window_check_requested",
            "log:anomaly_detected",
            "mlx_objective_training_request",
            "partner.sync.requested",
            "portability.violation.detected",
            "postmortem_generated",
            "qa:test_failed",
            "release.preflight.completed",
            "release_bundle_preflight_requested",
            "release_gate_check_requested",
            "research:competitive_intel_requested",
            "research:scan_requested",
            "roadmap:review_requested",
            "run:high_cost_launch_requested",
            "skill.mirror.changed",
            "skill_director_context_ingest_requested",
            "skill_evolution_requested",
            "skills_portability_audit_requested",
            "smart_launch_success",
            "stability_gate_check",
            "system.log_error",
            "system:startup",
            "tech:freshness_audit_requested",
            "tech:inventory_requested",
            "ux:audit_requested",
            "ux:brief_requested",
            "ux:handoff_requested",
            "ux:system_requested",
            "workspace:dependency_freshness_requested",
        ],
        "operator_conventions": [
            {"kind": "skill_request_namespace", "prefix": "skill:", "suffix": ":requested"},
            {"kind": "owned_route_suffix", "suffix": ":requested", "route_modes": ["owned", "alias"]},
            {"kind": "owned_route_suffix", "suffix": "_requested", "route_modes": ["owned", "alias"]},
        ],
    },
    "shared_event_registry": {
        "output_events": [
            {
                "event_type": "skill_evolution_assessment_emitted",
                "ownership_mode": "intentional_shared",
                "allowed_producers": ["conversation-skill-evolution-director", "skill_director"],
                "allowed_roles": ["specialist_primary", "watcher_embedded_evolution_aggregate"],
            },
            {
                "event_type": "skill_evolution_actions_emitted",
                "ownership_mode": "intentional_shared",
                "allowed_producers": ["conversation-skill-evolution-director", "skill_director"],
                "allowed_roles": ["specialist_primary", "watcher_embedded_evolution_aggregate"],
            },
            {
                "event_type": "skill_evolution_plan_emitted",
                "ownership_mode": "intentional_shared",
                "allowed_producers": ["conversation-skill-evolution-director", "proactive-skill-evolution-planner"],
                "allowed_roles": ["specialist_primary", "planner_primary"],
            },
            {
                "event_type": "skill_recommendation_emitted",
                "ownership_mode": "intentional_shared",
                "allowed_producers": [
                    "cross-workspace-goal-intelligence",
                    "proactive-skill-evolution-planner",
                    "skill_director",
                ],
                "allowed_roles": ["watcher_aggregate", "workspace_signal_source", "planner_signal"],
            },
            {
                "event_type": "skill_activity:imagegen",
                "ownership_mode": "intentional_shared",
                "allowed_producers": [".system/imagegen", "imagegen"],
                "allowed_roles": ["primary_skill", "system_fallback"],
            },
            {
                "event_type": "skill_activity:openai-docs",
                "ownership_mode": "intentional_shared",
                "allowed_producers": [".system/openai-docs", "openai-docs"],
                "allowed_roles": ["primary_skill", "system_fallback"],
            },
        ]
    },
}


@lru_cache(maxsize=1)
def load_ecosystem_contract() -> Dict[str, Any]:
    if yaml is None or not ECOSYSTEM_CONTRACT_PATH.exists():
        return FALLBACK_ECOSYSTEM_CONTRACT
    try:
        loaded = yaml.safe_load(ECOSYSTEM_CONTRACT_PATH.read_text(encoding="utf-8"))
    except Exception:
        return FALLBACK_ECOSYSTEM_CONTRACT
    if not isinstance(loaded, dict):
        return FALLBACK_ECOSYSTEM_CONTRACT
    return loaded


def external_runtime_trigger_patterns() -> set[str]:
    registry = load_ecosystem_contract().get("external_event_registry", {})
    values = registry.get("runtime_patterns", []) if isinstance(registry, dict) else []
    return {str(item).strip() for item in values if str(item).strip()}


def external_operator_trigger_patterns() -> set[str]:
    registry = load_ecosystem_contract().get("external_event_registry", {})
    values = registry.get("operator_patterns", []) if isinstance(registry, dict) else []
    return {str(item).strip() for item in values if str(item).strip()}


def external_operator_conventions() -> List[Dict[str, Any]]:
    registry = load_ecosystem_contract().get("external_event_registry", {})
    values = registry.get("operator_conventions", []) if isinstance(registry, dict) else []
    return [item for item in values if isinstance(item, dict)]


def shared_output_event_contracts() -> Dict[str, Dict[str, Any]]:
    registry = load_ecosystem_contract().get("shared_event_registry", {})
    values = registry.get("output_events", []) if isinstance(registry, dict) else []
    out: Dict[str, Dict[str, Any]] = {}
    if not isinstance(values, list):
        return out
    for entry in values:
        if not isinstance(entry, dict):
            continue
        event_type = str(entry.get("event_type") or "").strip()
        if not event_type:
            continue
        out[event_type] = entry
    return out


def classify_inventory_role(relative_skill_path: str) -> str:
    contract = load_ecosystem_contract()
    inventory_roles = contract.get("inventory_roles", {})
    if isinstance(inventory_roles, dict):
        for role_name, role_config in inventory_roles.items():
            if not isinstance(role_config, dict):
                continue
            prefixes = role_config.get("path_prefixes", [])
            if not isinstance(prefixes, list):
                continue
            for prefix in prefixes:
                if str(prefix).strip() and relative_skill_path.startswith(str(prefix).strip()):
                    return str(role_name)
    return "standard"


def classify_root_role(source: str) -> str:
    root_roles = load_ecosystem_contract().get("root_roles", {})
    if isinstance(root_roles, dict):
        mapped = root_roles.get(source)
        if mapped:
            return str(mapped)
    return "unknown"


def inventory_key_for_path(relative_skill_path: str) -> str:
    normalized = relative_skill_path.strip().replace("\\", "/")
    return normalized or relative_skill_path


def leaf_skill_id(relative_skill_path: str) -> str:
    return Path(relative_skill_path).name


def is_external_runtime_trigger_pattern(pattern: str) -> bool:
    return pattern in external_runtime_trigger_patterns()


def is_external_operator_trigger_pattern(pattern: str, route_entries: Optional[Sequence[Mapping[str, Any]]] = None) -> bool:
    if pattern in external_operator_trigger_patterns():
        return True
    normalized = pattern.strip()
    if not normalized:
        return False
    for convention in external_operator_conventions():
        kind = str(convention.get("kind", "")).strip()
        prefix = str(convention.get("prefix", "")).strip()
        suffix = str(convention.get("suffix", "")).strip()
        route_modes = {
            str(item).strip().lower()
            for item in convention.get("route_modes", [])
            if str(item).strip()
        }
        if kind == "skill_request_namespace":
            if normalized.startswith(prefix) and normalized.endswith(suffix):
                return True
            continue
        if kind == "owned_route_suffix" and suffix and normalized.endswith(suffix):
            if not route_modes or not route_entries:
                return True
            seen_modes = {str(entry.get("route_mode") or "owned").strip().lower() for entry in route_entries}
            return seen_modes <= route_modes
    return False

GROUP_DEFS: List[Dict[str, str]] = [
    {
        "group_id": "ecosystem-governance",
        "title": "Ecosystem Governance",
        "group_purpose": "Oversees skill lifecycle, inventory integrity, portability, and dispatch governance.",
        "what_you_get": "Clear skill visibility, controlled drift, better skill hygiene, and safer cross-root decisions.",
    },
    {
        "group_id": "orchestration-runtime-reliability",
        "title": "Orchestration, Runtime, and Reliability",
        "group_purpose": "Coordinates event routing, runtime control, fallback behavior, and availability guardrails.",
        "what_you_get": "More stable execution, predictable orchestration paths, and fewer runtime incidents.",
    },
    {
        "group_id": "git-repo-delivery",
        "title": "Git, Repo, and Delivery",
        "group_purpose": "Manages repository health, release hygiene, topology alignment, and promotion decisions.",
        "what_you_get": "Cleaner delivery flows, reduced merge risk, and better shared-environment confidence.",
    },
    {
        "group_id": "security-privacy-threat",
        "title": "Security, Privacy, and Threat",
        "group_purpose": "Audits security posture, enforces hardening patterns, and mitigates privacy leakage.",
        "what_you_get": "Stronger defensive baselines, fewer risky misconfigurations, and clearer threat coverage.",
    },
    {
        "group_id": "diagnostics-telemetry",
        "title": "Diagnostics and Telemetry",
        "group_purpose": "Investigates anomalies, validates semantics, and tracks system behavior through evidence.",
        "what_you_get": "Faster root-cause analysis, better observability fidelity, and clearer operational signals.",
    },
    {
        "group_id": "ml-model-engineering",
        "title": "ML and Model Engineering",
        "group_purpose": "Optimizes model training, inference, quantization, retrieval quality, and hardware alignment.",
        "what_you_get": "Improved model performance, better reliability on-device, and sharper quality control loops.",
    },
    {
        "group_id": "qa-code-audit",
        "title": "QA and Code Audit",
        "group_purpose": "Expands test coverage and performs quality audits for correctness and regression resistance.",
        "what_you_get": "Higher confidence releases, stronger regression prevention, and clearer code risk visibility.",
    },
    {
        "group_id": "ux-automation-artifacts",
        "title": "UX, Automation, and Artifacts",
        "group_purpose": "Supports UI quality, browser automation, and artifact-heavy workflows like screenshots and document rendering.",
        "what_you_get": "Faster interface validation, richer output artifacts, and smoother human-facing workflows.",
    },
    {
        "group_id": "platform-ops-jarvis-openclaw",
        "title": "Platform Ops: Jarvis and OpenClaw",
        "group_purpose": "Runs and hardens Jarvis/OpenClaw operations under constrained system conditions.",
        "what_you_get": "Operational continuity, budget-safe behavior, and safer upgrades for edge deployments.",
    },
    {
        "group_id": "research-strategy-productivity",
        "title": "Research, Strategy, and Productivity",
        "group_purpose": "Delivers market intelligence, strategy scaffolding, and productivity acceleration.",
        "what_you_get": "Better planning inputs, faster research synthesis, and improved execution throughput.",
    },
    {
        "group_id": "general-specialists",
        "title": "General Specialists",
        "group_purpose": "Catches domain-specific capabilities that do not cleanly map to the fixed taxonomy.",
        "what_you_get": "No skill left uncategorized and reliable fallback coverage for unique capabilities.",
    },
]

GROUP_BY_ID = {item["group_id"]: item for item in GROUP_DEFS}

GROUP_OVERRIDE: Dict[str, str] = {
    "skill_director": "ecosystem-governance",
    "skill-hygiene-orchestrator": "ecosystem-governance",
    "skill-portability-guardian": "ecosystem-governance",
    "skill-creator": "ecosystem-governance",
    "skill-installer": "ecosystem-governance",
    "omniscient-skill-cataloger": "ecosystem-governance",
    "find-skills": "research-strategy-productivity",
    "openai-docs": "research-strategy-productivity",
    "atlas": "ux-automation-artifacts",
    "playwright": "ux-automation-artifacts",
    "pdf": "ux-automation-artifacts",
    "screenshot": "ux-automation-artifacts",
    "tech_auditor": "research-strategy-productivity",
    "project-manager-maestro": "research-strategy-productivity",
    "job-apply-autonomous": "research-strategy-productivity",
    "orchestration-sentinel": "orchestration-runtime-reliability",
    "orchestration-sentinel-v2": "orchestration-runtime-reliability",
    "orchestration_sentinel": "orchestration-runtime-reliability",
    "jarvis-mini-runtime-operator": "platform-ops-jarvis-openclaw",
    "jarvis-mini-antigravity-routing": "platform-ops-jarvis-openclaw",
    "jarvis-mini-openclaw-release-guardian": "platform-ops-jarvis-openclaw",
    "jarvis-mini-ears-guardrails": "platform-ops-jarvis-openclaw",
    "jarvis-mini-token-discipline": "platform-ops-jarvis-openclaw",
    "pi3b-openclaw-tuning-specialist": "platform-ops-jarvis-openclaw",
    "security-best-practices": "security-privacy-threat",
    "security-threat-model": "security-privacy-threat",
    "security_appsec_worldclass_auditor": "security-privacy-threat",
    "private-pii-scrub-master": "security-privacy-threat",
    "local-network-hardener": "security-privacy-threat",
    "macos_end_to_end_security_audit": "security-privacy-threat",
    "qa-automation-engineer": "qa-code-audit",
    "principal_code_auditor_worldclass": "qa-code-audit",
}

GROUP_RULES: List[Tuple[str, Sequence[str]]] = [
    (
        "ecosystem-governance",
        (
            "skill director",
            "skill_director",
            "skill-",
            "catalog",
            "portability",
            "hygiene",
            "installer",
            "creator",
            "capability delta",
            "deployment strategist",
        ),
    ),
    (
        "orchestration-runtime-reliability",
        (
            "orchestration",
            "sentinel",
            "runtime",
            "launch",
            "fallback",
            "scheduler",
            "uptime",
            "lifecycle",
            "stream",
            "stability",
            "entitlement",
            "router",
        ),
    ),
    (
        "git-repo-delivery",
        (
            "git",
            "repository",
            "repo_",
            "repo-",
            "release",
            "bootstrap",
            "sync",
            "harmonization",
            "branch",
        ),
    ),
    (
        "security-privacy-threat",
        (
            "security",
            "threat",
            "privacy",
            "hardener",
            "pii",
            "abuse",
            "vulnerability",
            "appsec",
        ),
    ),
    (
        "diagnostics-telemetry",
        (
            "telemetry",
            "log",
            "anomaly",
            "checksum",
            "ledger",
            "diagnostic",
            "observer",
            "semconv",
            "trace",
            "detective",
        ),
    ),
    (
        "ml-model-engineering",
        (
            "mlx",
            "model",
            "inference",
            "quantization",
            "tensor",
            "compiler",
            "rag",
            "lora",
            "neural",
        ),
    ),
    (
        "qa-code-audit",
        (
            "qa",
            "test",
            "validator",
            "audit",
            "correctness",
            "regression",
        ),
    ),
    (
        "ux-automation-artifacts",
        (
            "ui",
            "ux",
            "playwright",
            "screenshot",
            "pdf",
            "atlas",
            "artifact",
            "frontend",
        ),
    ),
    (
        "platform-ops-jarvis-openclaw",
        (
            "jarvis",
            "openclaw",
            "pi3b",
            "raspberry",
            "token discipline",
        ),
    ),
    (
        "research-strategy-productivity",
        (
            "research",
            "strategy",
            "project manager",
            "tech auditor",
            "find-skills",
            "openai docs",
            "job apply",
            "productivity",
        ),
    ),
]


@dataclass(frozen=True)
class RootSpec:
    key: str
    path: Path


def parse_args() -> argparse.Namespace:
    codex_home_default = Path(
        os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))
    ).expanduser()
    parser = argparse.ArgumentParser(
        description="Generate Watcher-grade skill intelligence for The Watcher."
    )
    parser.add_argument(
        "--roots",
        default="local,codex,antigravity,agents",
        help="Comma-separated roots: local,codex,antigravity,agents or explicit paths.",
    )
    parser.add_argument(
        "--workspace-root",
        default=os.getcwd(),
        help="Workspace root used to resolve local skills and relative output paths.",
    )
    parser.add_argument(
        "--include-backups",
        action="store_true",
        help="Include backup directories (_p0_backups/.backups).",
    )
    parser.add_argument(
        "--output-json",
        default=ISOLATED_OUTPUT_JSON,
        help="JSON state output path.",
    )
    parser.add_argument(
        "--artifact-output-mode",
        choices=["isolated", "legacy"],
        default="isolated",
        help=(
            "Where the default JSON state artifact is written. "
            "'isolated' writes to .agent/skills/watcher/_generated (default). "
            "'legacy' writes to .agent/skills/watcher."
        ),
    )
    parser.add_argument(
        "--director-mode",
        choices=["auto", "pin-codex", "none"],
        default="auto",
        help="Final pass selection mode for skill_director copy.",
    )
    parser.add_argument(
        "--session-context-mode",
        choices=["auto", "file", "none"],
        default="auto",
        help="Session context intake mode.",
    )
    parser.add_argument(
        "--session-context-file",
        default="",
        help="Optional path to a JSON/TXT session context file.",
    )
    parser.add_argument(
        "--recommendation-strictness",
        choices=["high", "balanced", "broad"],
        default="high",
        help="Strictness level for recommendation emission.",
    )
    parser.add_argument(
        "--enforce-additive-update-policy",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Require recommended skill updates/new skills to be additive, non-destructive, and portability-safe.",
    )
    parser.add_argument(
        "--workspace-discovery-scope",
        choices=["known-skill-workspaces", "all-repos", "allowlist"],
        default="known-skill-workspaces",
        help="Scope used for cross-workspace wisdom discovery.",
    )
    parser.add_argument(
        "--workspace-allowlist-file",
        default="",
        help="Optional file with one workspace path per line (used by allowlist scope).",
    )
    parser.add_argument(
        "--cross-workspace-recall",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Enable cross-workspace wisdom recall (enabled by default).",
    )
    parser.add_argument(
        "--context-recall-limit",
        type=int,
        default=25,
        help="Maximum number of recalled wisdom records to blend into context.",
    )
    parser.add_argument(
        "--context-time-window-hours",
        type=int,
        default=168,
        help="Recency window for context and wisdom relevance.",
    )
    parser.add_argument(
        "--freshness-threshold-hours",
        type=int,
        default=24,
        help="Report age threshold used for stale-intelligence warnings when inventory has changed.",
    )
    parser.add_argument(
        "--wisdom-enabled",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Enable wisdom archive writes to JSONL ledgers (enabled by default).",
    )
    parser.add_argument(
        "--wisdom-local-ledger",
        default=".agent/skills/watcher/wisdom/session_wisdom.jsonl",
        help="Local canonical wisdom ledger path.",
    )
    parser.add_argument(
        "--wisdom-global-codex-ledger",
        default=str(codex_home_default / "skills" / "watcher" / "wisdom" / "global_wisdom.jsonl"),
        help="Global codex wisdom mirror ledger path.",
    )
    parser.add_argument(
        "--wisdom-global-antigravity-ledger",
        default=str(Path.home() / ".gemini" / "antigravity" / "skills" / "watcher" / "wisdom" / "global_wisdom.jsonl"),
        help="Global antigravity wisdom mirror ledger path.",
    )
    parser.add_argument(
        "--no-wisdom-global-mirror",
        action="store_true",
        help="Disable global wisdom mirror writes.",
    )
    parser.add_argument(
        "--stdout-only",
        action="store_true",
        help="Print the watcher intelligence brief only and do not write files.",
    )
    return parser.parse_args()


def apply_artifact_output_mode(args: argparse.Namespace) -> None:
    if args.artifact_output_mode != "legacy":
        return
    if args.output_json == ISOLATED_OUTPUT_JSON:
        args.output_json = LEGACY_OUTPUT_JSON


def looks_like_workspace_mirror_root(workspace_root: Path) -> bool:
    if not workspace_root.exists() or not workspace_root.is_dir():
        return False
    sentinel_paths = [
        workspace_root / "skill_director" / "SKILL.md",
        workspace_root / ".system" / "skill-creator" / "SKILL.md",
    ]
    if not any(path.exists() for path in sentinel_paths):
        return False

    exported_skill_count = 0
    for child in workspace_root.iterdir():
        if child.name in {".agent", ".git", "__pycache__"}:
            continue
        if not child.is_dir():
            continue
        if (child / "SKILL.md").exists():
            exported_skill_count += 1
            continue
        if child.name in {".system", "codex-primary-runtime"}:
            exported_skill_count += sum(1 for nested in child.iterdir() if (nested / "SKILL.md").exists())
    return exported_skill_count >= 10


def default_roots(workspace_root: Path) -> Dict[str, Path]:
    codex_home = Path(
        os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))
    ).expanduser()
    roots = {
        "local": (workspace_root / ".agent" / "skills").resolve(),
        "codex": (codex_home / "skills").resolve(),
        "antigravity": (Path.home() / ".gemini" / "antigravity" / "skills").resolve(),
        "agents": (Path.home() / ".agents" / "skills").resolve(),
    }
    if looks_like_workspace_mirror_root(workspace_root):
        roots["workspace_mirror"] = workspace_root.resolve()
    return roots


def resolve_roots(roots_arg: str, workspace_root: Path) -> List[RootSpec]:
    defaults = default_roots(workspace_root)
    specs: List[RootSpec] = []
    for token in [item.strip() for item in roots_arg.split(",") if item.strip()]:
        if token in defaults:
            specs.append(RootSpec(token, defaults[token]))
            continue
        candidate = Path(token).expanduser()
        if not candidate.is_absolute():
            candidate = (workspace_root / candidate).resolve()
        specs.append(RootSpec(f"path{len(specs) + 1}", candidate))

    dedup: Dict[Path, RootSpec] = {}
    for spec in specs:
        dedup[spec.path] = spec
    if "workspace_mirror" in defaults and defaults["workspace_mirror"] not in dedup:
        dedup[defaults["workspace_mirror"]] = RootSpec("workspace_mirror", defaults["workspace_mirror"])
    return list(dedup.values())


def skip_parts(include_backups: bool) -> set[str]:
    skip = set(CACHE_SKIP)
    if not include_backups:
        skip.update(BACKUP_SKIP)
    return skip


def is_archived_skill_reference_path(path: Path) -> bool:
    parts = tuple(path.parts)
    for sequence in ARCHIVE_SKIP_SEQUENCES:
        width = len(sequence)
        if width == 0:
            continue
        for index in range(0, max(0, len(parts) - width + 1)):
            if parts[index : index + width] == sequence:
                return True
    return False


def is_backup_path(path: Path) -> bool:
    return any(part in BACKUP_SKIP for part in path.parts)


def parse_frontmatter(content: str) -> Dict[str, Any]:
    match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    if not match or yaml is None:
        return {}
    try:
        parsed = yaml.safe_load(match.group(1))
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def extract_trigger(content: str) -> str:
    match = re.search(r"##\s+(?:When to use|Trigger|Activation)", content, re.IGNORECASE)
    if not match:
        return "See SKILL.md"
    start = match.end()
    snippet = content[start : start + 500].split("\n##", 1)[0]
    return compact_sentence(strip_markdown(snippet), limit=220)


def strip_markdown(text: str) -> str:
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"[*_>#-]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def first_sentence(text: str) -> str:
    normalized = strip_markdown(text)
    if not normalized:
        return ""
    match = re.search(r"(.+?[.!?])(?:\s|$)", normalized)
    if match:
        return match.group(1).strip()
    return normalized.split("\n", 1)[0].strip()


def compact_sentence(text: str, limit: int = 180) -> str:
    cleaned = re.sub(r"\s+", " ", text).strip()
    if not cleaned:
        return ""
    sentence = first_sentence(cleaned) or cleaned
    sentence = re.sub(r"\s+", " ", sentence).strip()
    if len(sentence) > limit:
        return sentence[: limit - 3].rstrip() + "..."
    return sentence


def extract_body_after_frontmatter(content: str) -> str:
    match = re.match(r"^---\n.*?\n---\n?", content, re.DOTALL)
    if not match:
        return content
    return content[match.end() :]


def parse_manifest(skill_dir: Path) -> Dict[str, Any]:
    for name in ("manifest.v2.json", "manifest.json"):
        path = skill_dir / name
        if path.exists():
            try:
                parsed = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(parsed, dict):
                    return parsed
            except Exception:
                continue
    return {}


def frontmatter_field(frontmatter: Dict[str, Any], key: str, default: Any = "") -> Any:
    if key in frontmatter:
        return frontmatter.get(key, default)
    metadata = frontmatter.get("metadata", {})
    if isinstance(metadata, dict):
        return metadata.get(key, default)
    return default


def manifest_input_patterns(manifest: Dict[str, Any]) -> List[str]:
    inputs = manifest.get("inputs", [])
    if not isinstance(inputs, list):
        return []
    patterns: List[str] = []
    for item in inputs:
        if not isinstance(item, dict):
            continue
        pattern = str(item.get("pattern") or item.get("event_type") or "").strip()
        if pattern:
            patterns.append(pattern)
    return sorted(set(patterns))


def manifest_output_events(manifest: Dict[str, Any]) -> List[str]:
    outputs = manifest.get("outputs", [])
    if not isinstance(outputs, list):
        return []
    events: List[str] = []
    for item in outputs:
        if not isinstance(item, dict):
            continue
        event_type = str(item.get("event_type") or "").strip()
        if event_type:
            events.append(event_type)
    return sorted(set(events))


def manifest_contract_posture(*, manifest_present: bool, inputs_count: int, outputs_count: int) -> str:
    if not manifest_present:
        return "missing"
    if inputs_count > 0 and outputs_count > 0:
        return "full"
    if inputs_count > 0 or outputs_count > 0:
        return "partial"
    return "quiet"


def summarize_skill_copy_drift(copies: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    versions = sorted(
        {
            str(copy.get("version", "")).strip()
            for copy in copies
            if str(copy.get("version", "")).strip()
        }
    )
    content_hashes = sorted(
        {
            str(copy.get("content_hash", "")).strip()
            for copy in copies
            if str(copy.get("content_hash", "")).strip()
        }
    )
    portability_tiers = sorted(
        {
            str(copy.get("portability_tier", "")).strip()
            for copy in copies
            if str(copy.get("portability_tier", "")).strip()
        }
    )
    drift_types: List[str] = []
    if len(versions) > 1:
        drift_types.append("version")
    if len(content_hashes) > 1:
        drift_types.append("content")
    if len(portability_tiers) > 1:
        drift_types.append("portability_contract")
    return {
        "status": "aligned" if not drift_types else "drift",
        "drift_types": drift_types or ["none"],
        "versions": versions,
        "hash_count": len(content_hashes),
        "portability_tiers": portability_tiers,
    }


def parse_skill_file(skill_md: Path, root: RootSpec) -> Dict[str, Any]:
    content = skill_md.read_text(encoding="utf-8", errors="replace")
    frontmatter = parse_frontmatter(content)
    body = extract_body_after_frontmatter(content)
    relative_skill_path = skill_md.parent.relative_to(root.path).as_posix()
    skill_id = inventory_key_for_path(relative_skill_path)
    inventory_role = classify_inventory_role(relative_skill_path)

    summary = compact_sentence(str(frontmatter.get("description", "")))
    if not summary:
        summary = compact_sentence(first_sentence(body))
    if not summary:
        summary = "No description provided."

    manifest = parse_manifest(skill_md.parent)
    inputs = manifest.get("inputs", [])
    outputs = manifest.get("outputs", [])
    if not isinstance(inputs, list):
        inputs = []
    if not isinstance(outputs, list):
        outputs = []

    version = str(frontmatter_field(frontmatter, "version", "") or "").strip()
    scope = str(frontmatter_field(frontmatter, "scope", "") or "").strip()
    portability_tier = str(frontmatter_field(frontmatter, "portability_tier", "") or "").strip()
    requires_env_raw = frontmatter_field(frontmatter, "requires_env", [])
    project_profiles_raw = frontmatter_field(frontmatter, "project_profiles", [])
    requires_env = (
        [str(item).strip() for item in requires_env_raw if str(item).strip()]
        if isinstance(requires_env_raw, list)
        else []
    )
    project_profiles = (
        [str(item).strip() for item in project_profiles_raw if str(item).strip()]
        if isinstance(project_profiles_raw, list)
        else []
    )
    input_patterns = manifest_input_patterns(manifest)
    output_events = manifest_output_events(manifest)
    manifest_present = bool(manifest)

    return {
        "skill_id": skill_id,
        "leaf_skill_id": leaf_skill_id(relative_skill_path),
        "relative_skill_path": relative_skill_path,
        "inventory_role": inventory_role,
        "root_role": classify_root_role(root.key),
        "name": str(frontmatter.get("name", leaf_skill_id(relative_skill_path))),
        "summary": summary,
        "trigger": extract_trigger(content),
        "source": root.key,
        "path": skill_md.resolve(),
        "manifest": manifest,
        "version": version,
        "scope": scope,
        "portability_tier": portability_tier,
        "requires_env": requires_env,
        "project_profiles": project_profiles,
        "content_hash": hashlib.sha256(content.encode("utf-8")).hexdigest(),
        "inputs_count": len(inputs),
        "outputs_count": len(outputs),
        "input_patterns": input_patterns,
        "output_events": output_events,
        "manifest_contract_posture": manifest_contract_posture(
            manifest_present=manifest_present,
            inputs_count=len(inputs),
            outputs_count=len(outputs),
        ),
        "pulse_bus_active": bool(inputs or outputs),
    }


def iter_skill_files(root: RootSpec, include_backups: bool) -> Iterable[Path]:
    if not root.path.exists():
        return
    skip = skip_parts(include_backups)
    for path in root.path.rglob("SKILL.md"):
        if any(part in skip for part in path.parts):
            continue
        if is_archived_skill_reference_path(path):
            continue
        yield path


def sort_key_for_source(source: str) -> Tuple[int, str]:
    return (SOURCE_PRIORITY.get(source, 99), source)


def pick_primary(copies: List[Dict[str, Any]]) -> Dict[str, Any]:
    def manifest_rank(item: Dict[str, Any]) -> int:
        posture = str(item.get("manifest_contract_posture", "") or "").strip().lower()
        if posture == "full":
            return 0
        if posture in {"partial", "quiet"}:
            return 1
        return 2

    def semver_rank(raw: Any) -> Tuple[int, int, int]:
        parsed = parse_semver(str(raw or "").strip())
        return parsed or (0, 0, 0)

    return sorted(
        copies,
        key=lambda item: (
            SOURCE_PRIORITY.get(item["source"], 99),
            1 if is_backup_path(Path(str(item["path"]))) else 0,
            manifest_rank(item),
            tuple(-value for value in semver_rank(item.get("version"))),
            item["name"].lower(),
            str(item["path"]),
        ),
    )[0]


def classify_group(entry: Dict[str, Any]) -> str:
    skill_id = str(entry["skill_id"])
    if skill_id in GROUP_OVERRIDE:
        return GROUP_OVERRIDE[skill_id]

    corpus = " ".join(
        [
            skill_id,
            str(entry.get("name", "")),
            str(entry.get("summary", "")),
            str(entry.get("trigger", "")),
        ]
    ).lower()

    for group_id, keywords in GROUP_RULES:
        if any(keyword in corpus for keyword in keywords):
            return group_id
    return "general-specialists"


def parse_semver(raw: str) -> Optional[Tuple[int, int, int]]:
    if not raw:
        return None
    match = SEMVER_PATTERN.match(raw.strip())
    if not match:
        return None
    return (int(match.group(1)), int(match.group(2)), int(match.group(3)))


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(65536)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso_timestamp(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        return None


def sanitize_text(text: str, workspace_root: Path) -> str:
    out = str(text or "")
    try:
        workspace_text = str(workspace_root.resolve())
        out = out.replace(workspace_text, "<workspace>")
    except Exception:
        pass
    home_text = str(Path.home())
    out = out.replace(home_text, "<home>")
    out = re.sub(r"/Users/[^/\s]+", "/Users/<user>", out)
    out = EMAIL_PATTERN.sub("<redacted_email>", out)
    out = PHONE_PATTERN.sub("<redacted_phone>", out)
    out = SECRET_PATTERN.sub(lambda m: f"{m.group(1)}=<redacted_secret>", out)
    out = re.sub(r"\b(?:sk|rk|pk)_[A-Za-z0-9]{8,}\b", "<redacted_token>", out)
    out = re.sub(r"(?<![A-Za-z0-9])/(?:tmp|private|var|opt|etc|Volumes|Applications)/[^\s,;]+", "<redacted_path>", out)
    out = re.sub(r"(?<![A-Za-z0-9])/(?:[A-Za-z0-9._-]+/){2,}[A-Za-z0-9._-]+", "<redacted_path>", out)
    out = re.sub(r"\b[a-z0-9._-]{3,}\.local\b", "<host>", out, flags=re.IGNORECASE)
    out = re.sub(r"\b[a-z0-9._-]*macbook[a-z0-9._-]*\b", "<host>", out, flags=re.IGNORECASE)
    out = re.sub(r"\b[a-z0-9._-]*-ctrl\b", "<host>", out, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", out).strip()


def sanitize_obj(value: Any, workspace_root: Path) -> Any:
    if isinstance(value, dict):
        return {sanitize_text(str(k), workspace_root): sanitize_obj(v, workspace_root) for k, v in value.items()}
    if isinstance(value, list):
        return [sanitize_obj(item, workspace_root) for item in value]
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return sanitize_text(str(value), workspace_root)


def normalize_context_text(text: str, *, max_chars: int = 24000) -> str:
    """Normalize and bound context text used for recommendation scoring."""
    raw = str(text or "")
    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    deduped: List[str] = []
    seen: set[str] = set()
    for line in lines:
        key = re.sub(r"\s+", " ", line).lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(line)
    joined = "\n".join(deduped).strip()
    if len(joined) > max_chars:
        joined = joined[:max_chars]
    return joined


def tokenize_terms(text: str) -> List[str]:
    tokens = re.findall(r"[a-z0-9][a-z0-9_\-:.]{2,}", text.lower())
    seen: set[str] = set()
    out: List[str] = []
    for token in tokens:
        normalized = token.strip("._:-")
        if len(normalized) < 3 or normalized in STOP_WORDS:
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        out.append(normalized)
    return out


def overlap_score(a_terms: Sequence[str], b_terms: Sequence[str]) -> float:
    if not a_terms or not b_terms:
        return 0.0
    a_set = set(a_terms)
    b_set = set(b_terms)
    intersection = len(a_set.intersection(b_set))
    union = len(a_set.union(b_set))
    if union == 0:
        return 0.0
    return float(intersection) / float(union)


def read_small_text(path: Path, limit: int = 12000) -> str:
    try:
        data = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""
    if len(data) > limit:
        data = data[:limit]
    return data


def safe_relative_path(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except Exception:
        return str(path)


def run_git_command(workspace_root: Path, args: Sequence[str], timeout_seconds: int = 5) -> Tuple[int, str, str]:
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=str(workspace_root),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except Exception as exc:
        return 1, "", str(exc)
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


def _first_context_line(blob: str) -> str:
    lines = [line.strip() for line in blob.splitlines() if line.strip()]
    for raw in lines:
        line = raw.lstrip("#*- ").strip()
        lowered = line.lower()
        if len(line) < 20:
            continue
        if lowered.startswith(("generated", "timestamp", "entries shown", "ledger", "workspace root")):
            continue
        return compact_sentence(line, limit=220)
    return compact_sentence(blob, limit=220)


def infer_workspace_goal(workspace_root: Path) -> Dict[str, Any]:
    for rel in WORKSPACE_GOAL_FILES:
        candidate = (workspace_root / rel).resolve()
        if not candidate.exists() or not candidate.is_file():
            continue
        blob = read_small_text(candidate, limit=18000)
        if not blob:
            continue

        summary = ""
        if candidate.suffix.lower() in {".json"}:
            try:
                parsed = json.loads(blob)
            except Exception:
                parsed = None
            if isinstance(parsed, dict):
                parts: List[str] = []
                for key in [
                    "goal",
                    "goals",
                    "objective",
                    "objectives",
                    "current_goal",
                    "project_goal",
                    "mission",
                    "summary",
                    "focus",
                    "next_steps",
                ]:
                    value = parsed.get(key)
                    if isinstance(value, str) and value.strip():
                        parts.append(value.strip())
                    elif isinstance(value, list):
                        for item in value[:3]:
                            if isinstance(item, str) and item.strip():
                                parts.append(item.strip())
                summary = compact_sentence(" ".join(parts), limit=220)

        if not summary:
            summary = _first_context_line(blob)

        if summary:
            return {
                "goal_summary": summary,
                "goal_source": f"file:{rel}",
                "goal_confidence": 0.9,
            }

    return {
        "goal_summary": "",
        "goal_source": "none",
        "goal_confidence": 0.0,
    }


def collect_git_activity(workspace_root: Path) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "has_git": False,
        "branch": "",
        "dirty_file_count": 0,
        "recent_commits": [],
        "last_commit_utc": "",
    }
    if not ((workspace_root / ".git").exists() or (workspace_root / ".git").is_file()):
        return out

    out["has_git"] = True
    rc, branch, _ = run_git_command(workspace_root, ["rev-parse", "--abbrev-ref", "HEAD"])
    if rc == 0:
        out["branch"] = branch

    rc, status, _ = run_git_command(workspace_root, ["status", "--porcelain"])
    if rc == 0 and status:
        out["dirty_file_count"] = len([line for line in status.splitlines() if line.strip()])

    rc, log_out, _ = run_git_command(
        workspace_root,
        ["log", "--date=iso-strict", "--pretty=format:%ad%x1f%s", "-n", "8"],
    )
    commits: List[Dict[str, Any]] = []
    if rc == 0 and log_out:
        for line in log_out.splitlines():
            parts = line.split("\x1f", 1)
            if len(parts) != 2:
                continue
            ts = parse_iso_timestamp(parts[0])
            ts_text = ts.strftime("%Y-%m-%dT%H:%M:%SZ") if ts else ""
            message = compact_sentence(parts[1], limit=140)
            commits.append(
                {
                    "timestamp_utc": ts_text,
                    "message": message,
                }
            )

    out["recent_commits"] = commits
    if commits:
        out["last_commit_utc"] = commits[0].get("timestamp_utc", "")
    return out


def collect_workspace_file_activity(
    workspace_root: Path,
    *,
    recency_window_hours: int,
    max_files: int = 4000,
) -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    cutoff_seconds = max(1, recency_window_hours) * 3600.0
    scanned = 0
    changed_recently = 0
    newest_epoch = 0.0
    newest_path = ""
    recent_files: List[Tuple[float, str]] = []
    stop_scan = False

    for base, dirs, files in os.walk(workspace_root):
        if stop_scan:
            break
        dirs[:] = [d for d in dirs if d not in WORKSPACE_SCAN_SKIP_DIRS]
        for name in files:
            if name in WORKSPACE_SCAN_SKIP_FILES:
                continue
            scanned += 1
            if scanned > max_files:
                stop_scan = True
                break

            path = Path(base) / name
            try:
                stat = path.stat()
            except Exception:
                continue
            mtime = float(stat.st_mtime)
            if mtime > newest_epoch:
                newest_epoch = mtime
                newest_path = safe_relative_path(path, workspace_root)

            age_seconds = now.timestamp() - mtime
            if age_seconds <= cutoff_seconds:
                changed_recently += 1
                recent_files.append((mtime, safe_relative_path(path, workspace_root)))

    recent_files.sort(key=lambda item: item[0], reverse=True)
    top_recent = [item[1] for item in recent_files[:8]]
    last_activity_utc = ""
    hours_since_last_activity = 99999.0
    if newest_epoch > 0.0:
        latest_dt = datetime.fromtimestamp(newest_epoch, tz=timezone.utc)
        last_activity_utc = latest_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        hours_since_last_activity = max(
            0.0, (now - latest_dt).total_seconds() / 3600.0
        )

    return {
        "files_scanned": scanned,
        "files_changed_within_window": changed_recently,
        "last_activity_utc": last_activity_utc,
        "hours_since_last_activity": round(hours_since_last_activity, 2),
        "last_activity_path": newest_path,
        "recent_files": top_recent,
    }


def build_workspace_intelligence(
    *,
    workspaces: List[Path],
    workspace_root: Path,
    recency_window_hours: int,
) -> Dict[str, Any]:
    profiles: List[Dict[str, Any]] = []
    now = datetime.now(timezone.utc)

    for ws in workspaces:
        goal = infer_workspace_goal(ws)
        git_activity = collect_git_activity(ws)
        file_activity = collect_workspace_file_activity(
            ws,
            recency_window_hours=recency_window_hours,
        )

        goal_summary = goal.get("goal_summary", "")
        goal_source = goal.get("goal_source", "none")
        goal_confidence = float(goal.get("goal_confidence", 0.0) or 0.0)

        if not goal_summary and git_activity.get("recent_commits"):
            first_commit = git_activity["recent_commits"][0]
            goal_summary = compact_sentence(
                f"Current momentum appears to center on: {first_commit.get('message', '')}",
                limit=220,
            )
            goal_source = "git:last_commit"
            goal_confidence = 0.55

        commit_messages = [
            compact_sentence(item.get("message", ""), limit=120)
            for item in git_activity.get("recent_commits", [])
            if isinstance(item, dict)
        ]
        commit_messages = [msg for msg in commit_messages if msg]

        recent_summary_parts: List[str] = []
        if goal_summary:
            recent_summary_parts.append(goal_summary)
        if commit_messages:
            recent_summary_parts.append(commit_messages[0])
        if file_activity.get("last_activity_path"):
            recent_summary_parts.append(
                f"Recent file activity near {file_activity.get('last_activity_path')}."
            )
        recent_action_summary = compact_sentence(" ".join(recent_summary_parts), limit=220)

        signal_terms = tokenize_terms(
            " ".join(
                [
                    goal_summary,
                    " ".join(commit_messages[:4]),
                    " ".join(file_activity.get("recent_files", [])[:6]),
                    recent_action_summary,
                ]
            )
        )

        latest_ts: Optional[datetime] = None
        ts_candidates = [
            parse_iso_timestamp(file_activity.get("last_activity_utc")),
            parse_iso_timestamp(git_activity.get("last_commit_utc")),
        ]
        for ts in ts_candidates:
            if ts is None:
                continue
            if latest_ts is None or ts > latest_ts:
                latest_ts = ts

        hours_since_latest = 99999.0
        if latest_ts is not None:
            hours_since_latest = max(0.0, (now - latest_ts).total_seconds() / 3600.0)

        profile = {
            "workspace_path": str(ws.resolve()),
            "workspace_name": ws.name,
            "is_current": ws.resolve() == workspace_root.resolve(),
            "goal_summary": goal_summary or "No explicit goal discovered.",
            "goal_source": goal_source,
            "goal_confidence": round(goal_confidence, 2),
            "recent_action_summary": recent_action_summary or "No recent activity summary available.",
            "has_git": bool(git_activity.get("has_git", False)),
            "branch": str(git_activity.get("branch", "")),
            "dirty_file_count": int(git_activity.get("dirty_file_count", 0) or 0),
            "last_commit_utc": str(git_activity.get("last_commit_utc", "")),
            "recent_commit_messages": commit_messages[:6],
            "recent_activity_files": list(file_activity.get("recent_files", [])),
            "files_changed_within_window": int(file_activity.get("files_changed_within_window", 0) or 0),
            "hours_since_last_activity": round(hours_since_latest, 2),
            "last_activity_utc": (
                latest_ts.strftime("%Y-%m-%dT%H:%M:%SZ") if latest_ts else ""
            ),
            "signal_terms": signal_terms[:40],
            "wisdom_records_blended": 0,
            "wisdom_highlights": [],
        }
        profiles.append(profile)

    profiles.sort(
        key=lambda item: (
            not item.get("is_current", False),
            float(item.get("hours_since_last_activity", 99999.0)),
            item.get("workspace_name", ""),
        )
    )
    summary = {
        "workspace_count": len(profiles),
        "current_workspace": str(workspace_root.resolve()),
        "workspaces_with_goals": sum(
            1
            for item in profiles
            if item.get("goal_summary") and item.get("goal_source") != "none"
        ),
        "active_within_window": sum(
            1 for item in profiles if float(item.get("hours_since_last_activity", 99999.0)) <= recency_window_hours
        ),
    }
    return {
        "summary": summary,
        "workspace_profiles": profiles,
    }


def enrich_workspace_intelligence_with_wisdom(
    *,
    workspace_intelligence: Dict[str, Any],
    recalled_wisdom: List[Dict[str, Any]],
) -> Dict[str, Any]:
    profiles = workspace_intelligence.get("workspace_profiles", [])
    if not isinstance(profiles, list) or not profiles:
        return workspace_intelligence

    by_path: Dict[str, Dict[str, Any]] = {}
    for profile in profiles:
        if isinstance(profile, dict):
            by_path[str(profile.get("workspace_path", ""))] = profile

    for record in recalled_wisdom:
        source_workspace = str(record.get("_source_workspace", ""))
        if source_workspace not in by_path:
            continue
        profile = by_path[source_workspace]
        profile["wisdom_records_blended"] = int(profile.get("wisdom_records_blended", 0) or 0) + 1
        summary = compact_sentence(str(record.get("summary", "")), limit=140)
        if summary:
            highlights = profile.get("wisdom_highlights", [])
            if isinstance(highlights, list) and summary not in highlights:
                highlights.append(summary)
                profile["wisdom_highlights"] = highlights[:5]

    for profile in by_path.values():
        highlights = profile.get("wisdom_highlights", [])
        if isinstance(highlights, list) and highlights:
            merged = tokenize_terms(
                " ".join([profile.get("goal_summary", ""), " ".join(highlights)])
            )
            profile["signal_terms"] = merged[:40]

    workspace_intelligence["workspace_profiles"] = profiles
    summary = workspace_intelligence.get("summary", {})
    if isinstance(summary, dict):
        summary["workspaces_with_wisdom"] = sum(
            1 for p in profiles if int(p.get("wisdom_records_blended", 0) or 0) > 0
        )
    workspace_intelligence["summary"] = summary
    return workspace_intelligence


def load_session_context(
    *,
    mode: str,
    context_file: str,
    workspace_root: Path,
) -> Dict[str, Any]:
    source = "empty"
    raw_context: Dict[str, Any] = {"text": "", "artifacts": []}

    if mode == "none":
        return {
            "mode": mode,
            "source": source,
            "summary": "Session context disabled.",
            "signals": [],
            "artifacts": [],
            "text": "",
            "term_set": [],
        }

    if context_file:
        context_path = resolve_output_path(context_file, workspace_root)
        if context_path.exists():
            source = f"file:{context_path}"
            if context_path.suffix.lower() in {".json", ".jsonl"}:
                try:
                    parsed = json.loads(context_path.read_text(encoding="utf-8", errors="replace"))
                except Exception:
                    parsed = context_path.read_text(encoding="utf-8", errors="replace")
                raw_context = {"content": parsed, "artifacts": [str(context_path)]}
            else:
                raw_context = {
                    "text": context_path.read_text(encoding="utf-8", errors="replace"),
                    "artifacts": [str(context_path)],
                }
    elif os.environ.get("SKILL_DIRECTOR_SESSION_CONTEXT_JSON"):
        source = "env:SKILL_DIRECTOR_SESSION_CONTEXT_JSON"
        env_text = os.environ.get("SKILL_DIRECTOR_SESSION_CONTEXT_JSON", "")
        try:
            parsed_env = json.loads(env_text)
        except Exception:
            parsed_env = env_text
        raw_context = {"content": parsed_env, "artifacts": []}

    if source == "empty" and mode == "auto":
        collected: List[Dict[str, Any]] = []
        combined_text_parts: List[str] = []
        for rel in AUTO_CONTEXT_FILES:
            path = (workspace_root / rel).resolve()
            if not path.exists() or not path.is_file():
                continue
            blob = read_small_text(path)
            if not blob:
                continue
            collected.append({"path": str(path), "chars": len(blob)})
            combined_text_parts.append(f"[{path.name}] {blob}")
        source = "auto:workspace_artifacts" if collected else "empty"
        raw_context = {"text": "\n\n".join(combined_text_parts), "artifacts": collected}

    sanitized = sanitize_obj(raw_context, workspace_root)
    base_text = ""
    if isinstance(sanitized, dict):
        if "text" in sanitized and isinstance(sanitized["text"], str):
            base_text = sanitized["text"]
        else:
            base_text = json.dumps(sanitized, ensure_ascii=True, sort_keys=True)
    else:
        base_text = str(sanitized)
    base_text = normalize_context_text(base_text)

    terms = tokenize_terms(base_text)
    summary = compact_sentence(base_text, limit=220) if base_text else "No session context found."
    artifacts = []
    if isinstance(sanitized, dict):
        raw_artifacts = sanitized.get("artifacts", [])
        if isinstance(raw_artifacts, list):
            artifacts = raw_artifacts

    return {
        "mode": mode,
        "source": source,
        "fallback_chain": list(SESSION_CONTEXT_FALLBACK_CHAIN),
        "summary": summary,
        "signals": terms[:30],
        "artifacts": artifacts,
        "text": base_text,
        "term_set": terms,
    }


def gather_director_candidates(
    roots: List[RootSpec], include_backups: bool
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    skip = skip_parts(include_backups)
    for root in roots:
        if not root.path.exists():
            continue
        candidates = list(root.path.rglob("watcher/SKILL.md"))
        for skill_md in candidates:
            if any(part in skip for part in skill_md.parts):
                continue
            content = skill_md.read_text(encoding="utf-8", errors="replace")
            frontmatter = parse_frontmatter(content)
            version_raw = str(frontmatter.get("version", "")).strip()
            out.append(
                {
                    "source": root.key,
                    "path": str(skill_md.resolve()),
                    "version": version_raw or "unknown",
                    "semver": parse_semver(version_raw),
                    "sha256": file_sha256(skill_md),
                }
            )
    out.sort(
        key=lambda item: (
            DIRECTOR_PRIORITY.get(item["source"], 99),
            item["path"],
        )
    )
    return out


def choose_director_candidate(
    candidates: List[Dict[str, Any]], director_mode: str
) -> Optional[Dict[str, Any]]:
    if not candidates or director_mode == "none":
        return None

    if director_mode == "pin-codex":
        codex = [item for item in candidates if item["source"] == "codex"]
        if codex:
            codex.sort(
                key=lambda item: (
                    item["semver"] is None,
                    tuple(-(x) for x in item["semver"]) if item["semver"] else (0, 0, 0),
                    item["path"],
                )
            )
            return codex[0]

    sortable = []
    for item in candidates:
        semver = item["semver"] or (-1, -1, -1)
        sortable.append(
            (
                semver,
                -DIRECTOR_PRIORITY.get(item["source"], 99),
                item["version"],
                item["path"],
                item,
            )
        )
    sortable.sort(reverse=True)
    return sortable[0][4]


def summarize_drift(candidates: List[Dict[str, Any]]) -> Dict[str, Any]:
    versions = sorted({item["version"] for item in candidates})
    hashes = sorted({item["sha256"] for item in candidates})
    drift_types: List[str] = []
    if len(versions) > 1:
        drift_types.append("version_drift")
    if len(hashes) > 1:
        drift_types.append("hash_drift")
    if not drift_types:
        drift_types.append("none")
    return {
        "version_drift": len(versions) > 1,
        "hash_drift": len(hashes) > 1,
        "drift_types": drift_types,
        "versions": versions,
        "hash_count": len(hashes),
    }


def canonical_recommendations(
    selected: Optional[Dict[str, Any]], drift: Dict[str, Any]
) -> List[str]:
    recommendations = [
        "Use codex root as canonical authoring root for The Watcher.",
        "Mirror to antigravity after compatibility checks and intent validation.",
    ]
    if selected is not None and selected.get("source") != "codex":
        recommendations.append(
            "Selected latest The Watcher copy is not in codex root; review promotion path to codex."
        )
    if drift.get("version_drift"):
        recommendations.append(
            "Version drift detected across roots; perform manual review before mirror actions."
        )
    if drift.get("hash_drift") and not drift.get("version_drift"):
        recommendations.append(
            "Hash drift with same versions detected; treat as semantic drift and review diff."
        )
    return recommendations


def collect_inventory(
    roots: List[RootSpec], include_backups: bool
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    discovered: List[Dict[str, Any]] = []
    root_stats: List[Dict[str, Any]] = []

    for root in roots:
        root_info = {
            "key": root.key,
            "path": str(root.path),
            "status": "missing",
            "skill_copies": 0,
        }
        if not root.path.exists():
            root_stats.append(root_info)
            continue

        root_info["status"] = "present"
        for skill_md in iter_skill_files(root, include_backups):
            discovered.append(parse_skill_file(skill_md, root))
            root_info["skill_copies"] += 1
        root_stats.append(root_info)

    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for entry in discovered:
        grouped.setdefault(entry["skill_id"], []).append(entry)

    aggregated: List[Dict[str, Any]] = []
    for _, copies in grouped.items():
        primary = pick_primary(copies)
        sources = sorted({copy["source"] for copy in copies}, key=sort_key_for_source)
        drift = summarize_skill_copy_drift(copies)
        input_patterns = sorted(
            {
                pattern
                for copy in copies
                for pattern in copy.get("input_patterns", [])
                if str(pattern).strip()
            }
        )
        output_events = sorted(
            {
                event_type
                for copy in copies
                for event_type in copy.get("output_events", [])
                if str(event_type).strip()
            }
        )
        requires_env = sorted(
            {
                env_name
                for copy in copies
                for env_name in copy.get("requires_env", [])
                if str(env_name).strip()
            }
        )
        project_profiles = sorted(
            {
                profile
                for copy in copies
                for profile in copy.get("project_profiles", [])
                if str(profile).strip()
            }
        )
        copy_details = [
            {
                "source": copy["source"],
                "root_role": str(copy.get("root_role", "") or ""),
                "path": str(copy["path"]),
                "relative_skill_path": str(copy.get("relative_skill_path", "") or ""),
                "version": str(copy.get("version", "") or ""),
                "scope": str(copy.get("scope", "") or ""),
                "portability_tier": str(copy.get("portability_tier", "") or ""),
                "manifest_present": bool(copy.get("manifest")),
                "manifest_contract_posture": str(copy.get("manifest_contract_posture", "") or ""),
                "inputs_count": int(copy.get("inputs_count", 0) or 0),
                "outputs_count": int(copy.get("outputs_count", 0) or 0),
                "input_patterns": [str(item) for item in copy.get("input_patterns", [])[:12]],
                "output_events": [str(item) for item in copy.get("output_events", [])[:12]],
                "pulse_bus_active": bool(copy.get("pulse_bus_active", False)),
                "content_hash": str(copy.get("content_hash", "") or ""),
            }
            for copy in sorted(copies, key=lambda item: sort_key_for_source(str(item.get("source", ""))))
        ]
        entry = {
            "skill_id": primary["skill_id"],
            "leaf_skill_id": str(primary.get("leaf_skill_id", "") or ""),
            "relative_skill_path": str(primary.get("relative_skill_path", "") or ""),
            "inventory_role": str(primary.get("inventory_role", "") or "standard"),
            "name": primary["name"],
            "summary": primary["summary"],
            "trigger": primary["trigger"],
            "primary_source": primary["source"],
            "primary_root_role": str(primary.get("root_role", "") or ""),
            "primary_path": str(primary["path"]),
            "sources": sources,
            "source_roles": sorted(
                {
                    str(copy.get("root_role", "")).strip()
                    for copy in copies
                    if str(copy.get("root_role", "")).strip()
                }
            ),
            "copy_count": len(copies),
            "inputs_count": max(copy["inputs_count"] for copy in copies),
            "outputs_count": max(copy["outputs_count"] for copy in copies),
            "pulse_bus_active": any(copy["pulse_bus_active"] for copy in copies),
            "manifest_present": any(bool(copy["manifest"]) for copy in copies),
            "version_signals": drift["versions"],
            "scope_signals": sorted(
                {
                    str(copy.get("scope", "")).strip()
                    for copy in copies
                    if str(copy.get("scope", "")).strip()
                }
            ),
            "portability_tiers": drift["portability_tiers"],
            "requires_env": requires_env,
            "project_profiles": project_profiles,
            "content_hash_count": int(drift["hash_count"]),
            "drift_status": drift["status"],
            "drift_types": drift["drift_types"],
            "input_patterns": input_patterns[:20],
            "output_events": output_events[:20],
            "manifest_contract_posture": manifest_contract_posture(
                manifest_present=any(bool(copy.get("manifest")) for copy in copies),
                inputs_count=max(copy["inputs_count"] for copy in copies),
                outputs_count=max(copy["outputs_count"] for copy in copies),
            ),
            "copy_details": copy_details,
        }
        entry["group_id"] = classify_group(entry)
        aggregated.append(entry)

    aggregated.sort(key=lambda item: (item["name"].lower(), item["skill_id"].lower()))
    return aggregated, root_stats


def build_group_payload(skills: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    by_group: Dict[str, List[Dict[str, Any]]] = {item["group_id"]: [] for item in GROUP_DEFS}
    for skill in skills:
        by_group.setdefault(skill["group_id"], []).append(skill)

    output: List[Dict[str, Any]] = []
    for group in GROUP_DEFS:
        members = by_group.get(group["group_id"], [])
        members.sort(key=lambda item: (item["name"].lower(), item["skill_id"]))
        payload = {
            "group_id": group["group_id"],
            "title": group["title"],
            "group_purpose": group["group_purpose"],
            "what_you_get": group["what_you_get"],
            "skill_count": len(members),
            "skills": [member["skill_id"] for member in members],
        }
        output.append(payload)
    return output


def inventory_counts(skills: List[Dict[str, Any]], root_stats: List[Dict[str, Any]]) -> Dict[str, Any]:
    total_copies = sum(int(root["skill_copies"]) for root in root_stats)
    shared = sum(1 for item in skills if len(item["sources"]) > 1)
    source_sets = [set(item["sources"]) for item in skills]
    inventory_roles = [str(item.get("inventory_role", "") or "standard") for item in skills]
    return {
        "unique_skills": len(skills),
        "total_skill_copies": total_copies,
        "shared_skills": shared,
        "single_source_skills": len(skills) - shared,
        "local_only": sum(1 for sources in source_sets if sources == {"local"}),
        "codex_only": sum(1 for sources in source_sets if sources == {"codex"}),
        "antigravity_only": sum(1 for sources in source_sets if sources == {"antigravity"}),
        "workspace_mirror_only": sum(1 for sources in source_sets if sources == {"workspace_mirror"}),
        "agents_only": sum(1 for sources in source_sets if sources == {"agents"}),
        "pulse_bus_active_skills": sum(1 for item in skills if item["pulse_bus_active"]),
        "skills_without_manifest_count": sum(1 for item in skills if not item.get("manifest_present", False)),
        "skills_without_pulse_participation_count": sum(1 for item in skills if not item.get("pulse_bus_active", False)),
        "portable_claimed_skills": sum(1 for item in skills if item.get("portability_tiers")),
        "standard_inventory_skills": sum(1 for role in inventory_roles if role == "standard"),
        "system_hidden_skills": sum(1 for role in inventory_roles if role == "system_hidden"),
        "runtime_bundle_skills": sum(1 for role in inventory_roles if role == "runtime_bundle"),
        "backup_snapshot_skills": sum(1 for role in inventory_roles if role == "backup_snapshot"),
        "mirrored_skill_count": sum(1 for item in skills if "distribution_mirror" in item.get("source_roles", [])),
    }


def build_root_parity_summary(skills: List[Dict[str, Any]]) -> Dict[str, Any]:
    def summarize_pair(left: str, right: str) -> Dict[str, Any]:
        shared = [
            item
            for item in skills
            if left in set(item.get("sources", [])) and right in set(item.get("sources", []))
        ]
        drift = [
            str(item.get("skill_id", ""))
            for item in shared
            if str(item.get("drift_status", "aligned") or "aligned") != "aligned"
        ]
        return {
            "shared": len(shared),
            "drift": len(drift),
            "examples": drift[:12],
        }

    return {
        "codex_vs_antigravity": summarize_pair("codex", "antigravity"),
        "codex_vs_workspace_mirror": summarize_pair("codex", "workspace_mirror"),
    }


def build_inventory_fingerprint(skills: List[Dict[str, Any]]) -> str:
    normalized = [
        {
            "skill_id": item.get("skill_id", ""),
            "name": item.get("name", ""),
            "group_id": item.get("group_id", ""),
            "primary_source": item.get("primary_source", ""),
            "sources": sorted(item.get("sources", [])),
            "copy_count": int(item.get("copy_count", 0) or 0),
            "inputs_count": int(item.get("inputs_count", 0) or 0),
            "outputs_count": int(item.get("outputs_count", 0) or 0),
            "pulse_bus_active": bool(item.get("pulse_bus_active", False)),
            "manifest_present": bool(item.get("manifest_present", False)),
            "drift_status": str(item.get("drift_status", "") or ""),
            "portability_tiers": sorted(item.get("portability_tiers", []) or []),
        }
        for item in sorted(skills, key=lambda row: str(row.get("skill_id", "")))
    ]
    raw = json.dumps(normalized, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def load_previous_report_snapshot(path: Path) -> Dict[str, Any]:
    snapshot = {
        "path": str(path),
        "exists": False,
        "generated_at_utc": "",
        "inventory_fingerprint": "",
        "read_error": "",
    }
    if not path.exists():
        return snapshot
    snapshot["exists"] = True
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        snapshot["read_error"] = str(exc)
        return snapshot

    if not isinstance(payload, dict):
        snapshot["read_error"] = "invalid_json_shape"
        return snapshot

    metadata = payload.get("metadata", {})
    if isinstance(metadata, dict):
        snapshot["generated_at_utc"] = str(metadata.get("generated_at_utc", "") or "")
        snapshot["inventory_fingerprint"] = str(metadata.get("inventory_fingerprint", "") or "")

    if not snapshot["inventory_fingerprint"]:
        skills = payload.get("skills", [])
        if isinstance(skills, list):
            safe_skills = [item for item in skills if isinstance(item, dict)]
            if safe_skills:
                snapshot["inventory_fingerprint"] = build_inventory_fingerprint(safe_skills)
    return snapshot


def load_previous_report_payload(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def build_freshness_audit(
    *,
    now_utc: datetime,
    current_generated_at_utc: str,
    current_inventory_fingerprint: str,
    previous_snapshot: Dict[str, Any],
    threshold_hours: int,
) -> Dict[str, Any]:
    audit = {
        "status": "first_run",
        "changed_since_last_run": False,
        "stale_intelligence_detected": False,
        "freshness_threshold_hours": int(max(1, threshold_hours)),
        "current_generated_at_utc": current_generated_at_utc,
        "current_inventory_fingerprint": current_inventory_fingerprint,
        "previous_generated_at_utc": str(previous_snapshot.get("generated_at_utc", "") or ""),
        "previous_inventory_fingerprint": str(previous_snapshot.get("inventory_fingerprint", "") or ""),
        "previous_report_age_hours": None,
        "warnings": [],
    }

    if previous_snapshot.get("read_error"):
        audit["status"] = "previous_report_unreadable"
        audit["warnings"].append(
            f"Previous report could not be parsed: {previous_snapshot.get('read_error')}"
        )
        return audit

    prev_generated = parse_iso_timestamp(audit["previous_generated_at_utc"])
    if prev_generated is not None:
        age_hours = max(0.0, (now_utc - prev_generated).total_seconds() / 3600.0)
        audit["previous_report_age_hours"] = round(age_hours, 2)

    prev_fp = audit["previous_inventory_fingerprint"]
    if prev_fp:
        changed = prev_fp != current_inventory_fingerprint
        audit["changed_since_last_run"] = changed
        if changed:
            audit["warnings"].append("Skill inventory changed since the previous report.")

    if not audit["previous_generated_at_utc"]:
        audit["status"] = "first_run"
        return audit

    if audit["changed_since_last_run"]:
        stale = (
            audit["previous_report_age_hours"] is not None
            and float(audit["previous_report_age_hours"]) >= float(audit["freshness_threshold_hours"])
        )
        audit["stale_intelligence_detected"] = bool(stale)
        if stale:
            audit["status"] = "stale"
            audit["warnings"].append(
                "Previous report is older than freshness threshold and inventory changed."
            )
        else:
            audit["status"] = "changed_since_last_run"
        return audit

    audit["status"] = "fresh"
    return audit


def discover_workspace_candidates(
    *,
    scope: str,
    workspace_root: Path,
    roots: List[RootSpec],
    allowlist_file: str,
) -> List[Path]:
    candidates: set[Path] = {workspace_root.resolve()}

    def add_if_workspace(path: Path) -> None:
        marker = path / ".agent" / "skills"
        if marker.exists() and marker.is_dir():
            candidates.add(path.resolve())

    if scope == "allowlist" and allowlist_file:
        allow_path = resolve_output_path(allowlist_file, workspace_root)
        if allow_path.exists():
            for raw in allow_path.read_text(encoding="utf-8", errors="replace").splitlines():
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                candidate = Path(line).expanduser()
                if not candidate.is_absolute():
                    candidate = (workspace_root / candidate).resolve()
                add_if_workspace(candidate)
    elif scope == "all-repos":
        home = Path.home()
        discovered = 0
        for git_dir in home.rglob(".git"):
            repo = git_dir.parent
            add_if_workspace(repo)
            discovered += 1
            if discovered >= 200:
                break
    else:
        # known-skill-workspaces default: current workspace family + Documents.
        anchors = {
            workspace_root,
            workspace_root.parent,
            Path.home() / "Documents",
        }
        max_markers = 160
        marker_count = 0
        for anchor in sorted(anchors, key=lambda item: str(item)):
            if not anchor.exists() or not anchor.is_dir():
                continue
            for marker in anchor.rglob(".agent/skills"):
                if marker.is_dir():
                    workspace = marker.parent.parent
                    add_if_workspace(workspace)
                    marker_count += 1
                if marker_count >= max_markers:
                    break
            if marker_count >= max_markers:
                break

    # Always include the roots currently scanned by this report.
    for root in roots:
        if root.key in {"local"}:
            local_workspace = root.path.parent.parent
            add_if_workspace(local_workspace)

    return sorted(candidates)


def read_jsonl_records(path: Path) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    records: List[Dict[str, Any]] = []
    if not path.exists():
        return records, None
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    parsed = json.loads(line)
                except Exception:
                    continue
                if isinstance(parsed, dict):
                    records.append(parsed)
    except Exception as exc:
        return [], str(exc)
    return records, None


def as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def evaluate_additive_portability_policy(
    *,
    reason: str,
    suggested_changes: Sequence[str],
    portability_note: str,
) -> Dict[str, Any]:
    combined = " ".join([reason, *[str(item) for item in suggested_changes]]).strip()
    portability_text = str(portability_note or "").strip()
    violations: List[str] = []

    if not ADDITIVE_CHANGE_PATTERN.search(combined):
        violations.append("missing_additive_language")
    if DESTRUCTIVE_CHANGE_PATTERN.search(combined):
        violations.append("contains_destructive_language")
    if not PORTABILITY_PATTERN.search(portability_text):
        violations.append("missing_portability_safety_note")

    return {
        "policy_id": "additive_non_destructive_portable_v1",
        "is_compliant": len(violations) == 0,
        "violations": violations,
    }


def collect_cross_workspace_wisdom(
    *,
    workspace_root: Path,
    workspaces: List[Path],
    roots: List[RootSpec],
    wisdom_local_ledger: Path,
    wisdom_global_codex_ledger: Path,
    wisdom_global_antigravity_ledger: Path,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    sources: List[Dict[str, Any]] = []
    records: List[Dict[str, Any]] = []

    candidate_paths: List[Tuple[Path, str, str]] = []
    for ws in workspaces:
        candidate_paths.append(
            (ws / ".agent" / "skills" / "watcher" / "wisdom" / "session_wisdom.jsonl", str(ws), "workspace_session_wisdom")
        )
        candidate_paths.append(
            (ws / ".agent" / "skills" / "watcher" / "skill_intelligence.json", str(ws), "workspace_skill_intelligence")
        )
        candidate_paths.append(
            (
                ws / ".agent" / "skills" / "watcher" / "_generated" / "skill_intelligence.json",
                str(ws),
                "workspace_skill_intelligence_generated",
            )
        )

    candidate_paths.extend(
        [
            (wisdom_local_ledger, str(workspace_root), "explicit_local_ledger"),
            (wisdom_global_codex_ledger, "codex_global", "explicit_codex_global"),
            (wisdom_global_antigravity_ledger, "antigravity_global", "explicit_antigravity_global"),
        ]
    )

    seen_source_keys: set[Tuple[str, str]] = set()
    for root in roots:
        if root.key in {"codex", "antigravity"}:
            candidate_paths.append((root.path / "skill_director" / "wisdom" / "global_wisdom.jsonl", root.key, "root_global_wisdom"))

    for path, workspace_tag, source_kind in candidate_paths:
        canonical = path.expanduser().resolve()
        source_key = (str(canonical), source_kind)
        if source_key in seen_source_keys:
            continue
        seen_source_keys.add(source_key)

        source_info: Dict[str, Any] = {
            "path": str(canonical),
            "workspace": workspace_tag,
            "source_kind": source_kind,
            "status": "missing",
            "records_loaded": 0,
            "sha256": "",
        }
        if not canonical.exists() or not canonical.is_file():
            sources.append(source_info)
            continue

        source_info["sha256"] = file_sha256(canonical)
        source_info["status"] = "loaded"

        loaded: List[Dict[str, Any]] = []
        if canonical.suffix.lower() == ".jsonl":
            parsed, err = read_jsonl_records(canonical)
            if err:
                source_info["status"] = f"error:{err}"
            loaded = parsed
        else:
            try:
                parsed_json = json.loads(canonical.read_text(encoding="utf-8", errors="replace"))
            except Exception as exc:
                source_info["status"] = f"error:{exc}"
                parsed_json = {}

            if isinstance(parsed_json, dict):
                md = parsed_json.get("metadata", {}) if isinstance(parsed_json.get("metadata", {}), dict) else {}
                recommendation_block = parsed_json.get("capability_recommendations", {})
                loaded = [
                    {
                        "timestamp_utc": md.get("generated_at_utc", ""),
                        "summary": f"Skill intelligence snapshot from {workspace_tag}",
                        "recommendation_counts": {
                            "updates": len(recommendation_block.get("recommended_updates", []))
                            if isinstance(recommendation_block, dict)
                            else 0,
                            "new_skills": len(recommendation_block.get("recommended_new_skills", []))
                            if isinstance(recommendation_block, dict)
                            else 0,
                        },
                        "source_type": "skill_intelligence_json",
                    }
                ]

        source_info["records_loaded"] = len(loaded)
        for item in loaded:
            sanitized = sanitize_obj(item, workspace_root)
            if isinstance(sanitized, dict):
                sanitized["_source_path"] = str(canonical)
                sanitized["_source_workspace"] = workspace_tag
                sanitized["_source_kind"] = source_kind
                records.append(sanitized)
        sources.append(source_info)

    # De-duplicate by path + sha (prefer first loaded source entry)
    deduped_sources: List[Dict[str, Any]] = []
    seen_hash_keys: set[Tuple[str, str]] = set()
    for source in sources:
        hash_key = (source.get("path", ""), source.get("sha256", ""))
        if hash_key in seen_hash_keys:
            continue
        seen_hash_keys.add(hash_key)
        deduped_sources.append(source)

    return deduped_sources, records


def rank_recalled_wisdom(
    *,
    records: List[Dict[str, Any]],
    session_terms: List[str],
    workspace_root: Path,
    limit: int,
    recency_window_hours: int,
) -> List[Dict[str, Any]]:
    if not records:
        return []

    now = datetime.now(timezone.utc)
    window = max(1, recency_window_hours)
    ranked: List[Dict[str, Any]] = []
    for record in records:
        text_blob = sanitize_text(
            " ".join(
                [
                    str(record.get("summary", "")),
                    str(record.get("challenges", "")),
                    str(record.get("mitigations", "")),
                    str(record.get("decisions", "")),
                    str(record.get("lessons_learned", "")),
                ]
            ),
            workspace_root,
        )
        terms = tokenize_terms(text_blob)
        semantic = overlap_score(session_terms, terms)

        ts = parse_iso_timestamp(record.get("timestamp_utc") or record.get("generated_at_utc") or record.get("timestamp"))
        recency = 0.0
        if ts is not None:
            delta = max(0.0, (now - ts).total_seconds() / 3600.0)
            recency = max(0.0, 1.0 - (delta / float(window)))

        confidence = max(0.0, min(1.0, as_float(record.get("confidence", 0.6), default=0.6)))
        source_kind = str(record.get("_source_kind", ""))
        source_quality = 0.85
        if "explicit_local_ledger" in source_kind:
            source_quality = 1.0
        elif "workspace_session_wisdom" in source_kind:
            source_quality = 0.95
        elif "skill_intelligence_json" in source_kind or "workspace_skill_intelligence" in source_kind:
            source_quality = 0.72

        workspace_weight = 1.0
        if str(record.get("_source_workspace", "")) == str(workspace_root):
            workspace_weight = 1.2

        score = (0.45 * semantic + 0.25 * recency + 0.2 * confidence + 0.1 * source_quality) * workspace_weight
        ranked_item = dict(record)
        ranked_item["relevance_score"] = round(score, 4)
        ranked_item["semantic_overlap"] = round(semantic, 4)
        ranked_item["recency_score"] = round(recency, 4)
        ranked_item["source_quality"] = round(source_quality, 4)
        ranked.append(ranked_item)

    ranked.sort(key=lambda item: item.get("relevance_score", 0.0), reverse=True)
    return ranked[: max(1, limit)]


def build_session_intelligence(
    *,
    session_context: Dict[str, Any],
    recalled_wisdom: List[Dict[str, Any]],
    workspace_intelligence: Dict[str, Any],
) -> Dict[str, Any]:
    cross_signals: List[str] = []
    for record in recalled_wisdom:
        cross_signals.extend(tokenize_terms(str(record.get("summary", ""))))

    workspace_profiles = workspace_intelligence.get("workspace_profiles", [])
    workspace_signals: List[str] = []
    workspace_goal_snapshots: List[str] = []
    if isinstance(workspace_profiles, list):
        for profile in workspace_profiles:
            if not isinstance(profile, dict):
                continue
            terms = profile.get("signal_terms", [])
            if isinstance(terms, list):
                workspace_signals.extend([str(item) for item in terms[:20]])
            goal = compact_sentence(str(profile.get("goal_summary", "")), limit=120)
            workspace_name = str(profile.get("workspace_name", "workspace"))
            if goal and goal != "No explicit goal discovered.":
                workspace_goal_snapshots.append(f"{workspace_name}: {goal}")

    combined_terms = list(
        dict.fromkeys(
            (session_context.get("term_set", []) or [])
            + cross_signals
            + workspace_signals
        )
    )

    return {
        "mode": session_context.get("mode", "auto"),
        "source": session_context.get("source", "empty"),
        "fallback_chain": session_context.get("fallback_chain", list(SESSION_CONTEXT_FALLBACK_CHAIN)),
        "summary": session_context.get("summary", "No context."),
        "signals": combined_terms[:40],
        "session_only_signals": session_context.get("signals", []),
        "artifacts": session_context.get("artifacts", []),
        "cross_workspace_records_used": len(recalled_wisdom),
        "cross_workspace_blend_mode": "current_session_first",
        "context_text_excerpt": compact_sentence(str(session_context.get("text", "")), limit=300),
        "workspace_profiles_used": len(workspace_profiles) if isinstance(workspace_profiles, list) else 0,
        "workspace_goal_snapshots": workspace_goal_snapshots[:10],
    }


def recommendation_target_skill(item: Dict[str, Any]) -> str:
    return str(item.get("skill_id", "") or item.get("proposed_skill_id", "") or "").strip()


def recommendation_action(item: Dict[str, Any]) -> str:
    if str(item.get("type", "") or "") == "new_skill" or item.get("proposed_skill_id"):
        return "create_new"
    return "update_existing"


def build_individual_skill_intelligence(
    *,
    skills: List[Dict[str, Any]],
    recalled_wisdom: List[Dict[str, Any]],
    previous_payload: Dict[str, Any],
    capability_recommendations: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    previous_cards_raw = previous_payload.get("individual_skill_intelligence", [])
    previous_cards = (
        [item for item in previous_cards_raw if isinstance(item, dict)]
        if isinstance(previous_cards_raw, list)
        else []
    )
    previous_index = {
        str(item.get("skill_id", "") or "").strip(): item
        for item in previous_cards
        if str(item.get("skill_id", "") or "").strip()
    }

    recommendation_index: Dict[str, Dict[str, Any]] = {}
    if isinstance(capability_recommendations, dict):
        for bucket in ("recommended_updates", "recommended_new_skills"):
            raw_items = capability_recommendations.get(bucket, [])
            if not isinstance(raw_items, list):
                continue
            for item in raw_items:
                if not isinstance(item, dict):
                    continue
                target = recommendation_target_skill(item)
                if target:
                    recommendation_index[target] = item

    entries: List[Dict[str, Any]] = []
    for skill in skills:
        skill_id = str(skill.get("skill_id", "") or "").strip()
        if not skill_id:
            continue
        skill_terms = tokenize_terms(
            " ".join(
                [
                    skill_id,
                    str(skill.get("name", "")),
                    str(skill.get("summary", "")),
                    str(skill.get("trigger", "")),
                    str(skill.get("group_id", "")),
                ]
            )
        )

        wisdom_hits: List[Dict[str, Any]] = []
        for record in recalled_wisdom:
            text_blob = " ".join(
                [
                    str(record.get("summary", "")),
                    str(record.get("session_summary", "")),
                    str(record.get("challenges", "")),
                    str(record.get("mitigations", "")),
                    str(record.get("decisions", "")),
                ]
            )
            overlap = overlap_score(skill_terms, tokenize_terms(text_blob))
            if overlap <= 0.0:
                continue
            source = str(record.get("_source_kind", "") or record.get("_source_workspace", "") or "wisdom")
            wisdom_hits.append(
                {
                    "summary": compact_sentence(text_blob, limit=150),
                    "source": compact_sentence(source, limit=60),
                    "relevance": round(overlap, 3),
                }
            )
        wisdom_hits.sort(key=lambda item: float(item.get("relevance", 0.0)), reverse=True)
        wisdom_hits = wisdom_hits[:3]

        previous_card = previous_index.get(skill_id, {})
        previous_wisdom_count = 0
        if isinstance(previous_card.get("knowledge_state"), dict):
            previous_wisdom_count = int(
                previous_card.get("knowledge_state", {}).get("current_wisdom_signals", 0) or 0
            )
        elif isinstance(previous_card.get("wisdom_signals"), list):
            previous_wisdom_count = len(previous_card.get("wisdom_signals", []))
        current_wisdom_count = len(wisdom_hits)
        monotonic_state = "growing" if current_wisdom_count > previous_wisdom_count else "stable"

        portability_tiers = [str(item) for item in skill.get("portability_tiers", []) or [] if str(item).strip()]
        portability_posture = "unspecified"
        if "strict_zero_leak" in portability_tiers:
            portability_posture = "strict_zero_leak"
        elif portability_tiers:
            portability_posture = "declared"

        pulse_status = "missing"
        if bool(skill.get("pulse_bus_active", False)) and bool(skill.get("manifest_present", False)):
            pulse_status = "active"
        elif bool(skill.get("manifest_present", False)):
            pulse_status = "quiet"

        trust_posture = "strong"
        if pulse_status == "missing" or not bool(skill.get("manifest_present", False)):
            trust_posture = "repair"
        elif str(skill.get("drift_status", "aligned") or "aligned") != "aligned":
            trust_posture = "watch"
        elif portability_posture == "unspecified":
            trust_posture = "watch"

        recommendation = recommendation_index.get(skill_id, {})
        continuity = recommendation.get("continuity_proof", {}) if isinstance(recommendation, dict) else {}

        entry = {
            "schema": "IndividualSkillIntelligenceV1",
            "skill_id": skill_id,
            "leaf_skill_id": str(skill.get("leaf_skill_id", "") or ""),
            "relative_skill_path": str(skill.get("relative_skill_path", "") or ""),
            "name": str(skill.get("name", "")),
            "group_id": str(skill.get("group_id", "")),
            "inventory_role": str(skill.get("inventory_role", "") or "standard"),
            "intelligence_summary": compact_sentence(
                " ".join(
                    part
                    for part in [
                        f"{skill.get('name', skill_id)} is a {skill.get('group_id', 'general')} skill.",
                        f"Inventory role is {skill.get('inventory_role', 'standard')}.",
                        f"Primary source is {skill.get('primary_source', 'unknown')}.",
                        f"Pulse posture is {pulse_status}.",
                        f"Portability posture is {portability_posture}.",
                    ]
                    if part
                ),
                limit=220,
            ),
            "roots": {
                "primary_source": str(skill.get("primary_source", "")),
                "primary_root_role": str(skill.get("primary_root_role", "") or ""),
                "sources": [str(item) for item in skill.get("sources", [])],
                "source_roles": [str(item) for item in skill.get("source_roles", [])],
                "copy_count": int(skill.get("copy_count", 0) or 0),
                "drift_status": str(skill.get("drift_status", "") or ""),
                "drift_types": [str(item) for item in skill.get("drift_types", [])[:4]],
                "version_signals": [str(item) for item in skill.get("version_signals", [])[:4]],
            },
            "pulse_contract": {
                "manifest_present": bool(skill.get("manifest_present", False)),
                "participation_status": pulse_status,
                "manifest_contract_posture": str(skill.get("manifest_contract_posture", "") or ""),
                "inputs_count": int(skill.get("inputs_count", 0) or 0),
                "outputs_count": int(skill.get("outputs_count", 0) or 0),
                "input_patterns": [str(item) for item in skill.get("input_patterns", [])[:12]],
                "output_events": [str(item) for item in skill.get("output_events", [])[:12]],
            },
            "portability_contract": {
                "scopes": [str(item) for item in skill.get("scope_signals", [])[:4]],
                "tiers": portability_tiers[:4],
                "requires_env": [str(item) for item in skill.get("requires_env", [])[:12]],
                "project_profiles": [str(item) for item in skill.get("project_profiles", [])[:8]],
                "portability_posture": portability_posture,
            },
            "knowledge_state": {
                "previous_snapshot_present": bool(previous_card),
                "previous_wisdom_signals": previous_wisdom_count,
                "current_wisdom_signals": current_wisdom_count,
                "monotonic_state": monotonic_state,
            },
            "wisdom_signals": wisdom_hits,
            "trust_posture": trust_posture,
            "continuity_anchor": {
                "skill_id": skill_id,
                "relative_skill_path": str(skill.get("relative_skill_path", "") or ""),
                "primary_path": str(skill.get("primary_path", "")),
                "summary": str(skill.get("summary", "")),
                "input_patterns": [str(item) for item in skill.get("input_patterns", [])[:8]],
                "output_events": [str(item) for item in skill.get("output_events", [])[:8]],
            },
            "preservation_requirements": [
                "Preserve stable skill identity and summary context.",
                "Preserve or strengthen manifest participation and pulse-bus visibility.",
                "Do not weaken declared portability or privacy guarantees.",
                "Append wisdom; never discard prior skill intelligence.",
            ],
            "current_recommendation": (
                {
                    "action": recommendation_action(recommendation),
                    "reason": compact_sentence(str(recommendation.get("reason", "")), limit=150),
                    "confidence": round(float(recommendation.get("confidence", 0.0) or 0.0), 3),
                    "continuity_verdict": str(continuity.get("verdict", "") or ""),
                }
                if recommendation
                else None
            ),
        }
        entries.append(entry)

    entries.sort(key=lambda item: str(item.get("skill_id", "")))
    return entries


def derive_strengthening_delta(
    *,
    recommendation: Dict[str, Any],
    baseline: Optional[Dict[str, Any]],
    action_kind: str,
) -> List[str]:
    deltas: List[str] = []
    if action_kind == "create_new":
        deltas.append("adds capability without replacing existing skills")
    else:
        deltas.append("extends the existing skill instead of replacing it")

    proposed_io = recommendation.get("proposed_manifest_io", {})
    if isinstance(proposed_io, dict) and (
        proposed_io.get("inputs") or proposed_io.get("outputs")
    ):
        deltas.append("strengthens manifest and pulse-bus contract clarity")

    portability_note = str(recommendation.get("portability_privacy_notes", "") or "")
    if PORTABILITY_PATTERN.search(portability_note):
        deltas.append("preserves portability and privacy guarantees")

    combined_text = " ".join(
        [str(recommendation.get("reason", ""))]
        + [str(item) for item in recommendation.get("suggested_changes", [])]
    ).lower()
    if "wisdom" in combined_text or "evidence" in combined_text:
        deltas.append("grows reusable wisdom and evidence discipline")

    if baseline and baseline.get("pulse_contract", {}).get("participation_status") == "active":
        deltas.append("protects existing pulse-bus participation")

    ordered: List[str] = []
    for item in deltas:
        if item not in ordered:
            ordered.append(item)
    return ordered[:4]


def build_skill_continuity_proof(
    *,
    recommendation: Dict[str, Any],
    skill_intelligence_index: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    action_kind = recommendation_action(recommendation)
    target_skill = recommendation_target_skill(recommendation) or "unknown"
    baseline = skill_intelligence_index.get(target_skill)
    policy_check = recommendation.get("change_policy", {}) if isinstance(recommendation, dict) else {}
    portability_note = str(recommendation.get("portability_privacy_notes", "") or "")
    proposed_manifest_io = recommendation.get("proposed_manifest_io", {})
    proposed_inputs = proposed_manifest_io.get("inputs", []) if isinstance(proposed_manifest_io, dict) else []
    proposed_outputs = proposed_manifest_io.get("outputs", []) if isinstance(proposed_manifest_io, dict) else []

    identity_preserved = bool(baseline) if action_kind == "update_existing" else not bool(baseline)
    knowledge_preserved = bool(policy_check.get("is_compliant", False))
    portability_preserved = bool(PORTABILITY_PATTERN.search(portability_note))
    if action_kind == "create_new":
        pulse_preserved = bool(proposed_inputs or proposed_outputs)
    else:
        baseline_pulse = baseline.get("pulse_contract", {}) if isinstance(baseline, dict) else {}
        pulse_preserved = str(baseline_pulse.get("participation_status", "missing")) != "missing"

    wisdom_growth_enforced = True
    checks = {
        "identity_preserved": identity_preserved,
        "knowledge_preserved": knowledge_preserved,
        "portability_preserved": portability_preserved,
        "pulse_participation_preserved": pulse_preserved,
        "wisdom_growth_enforced": wisdom_growth_enforced,
    }

    verdict = "pass"
    if not identity_preserved or not knowledge_preserved:
        verdict = "block"
    elif not portability_preserved or not pulse_preserved:
        verdict = "warn"

    strengthening_delta = derive_strengthening_delta(
        recommendation=recommendation,
        baseline=baseline,
        action_kind=action_kind,
    )

    summary_parts = []
    if verdict == "pass":
        summary_parts.append("Preserves identity, portability, pulse participation, and append-only wisdom growth.")
    elif verdict == "warn":
        summary_parts.append("Continuity is mostly preserved, but one or more strengthening signals need follow-through.")
    else:
        summary_parts.append("Continuity is blocked because the proposal would weaken identity or additive knowledge guarantees.")
    if strengthening_delta:
        summary_parts.append(f"Strengthens: {', '.join(strengthening_delta)}.")

    return {
        "schema": "SkillContinuityProofV1",
        "target_skill": target_skill,
        "action": action_kind,
        "baseline_present": bool(baseline),
        "baseline_trust_posture": str(baseline.get("trust_posture", "") or "") if isinstance(baseline, dict) else "",
        "checks": checks,
        "verdict": verdict,
        "strengthening_delta": strengthening_delta,
        "summary": compact_sentence(" ".join(summary_parts), limit=220),
    }


def attach_continuity_proofs(
    *,
    recommendations: List[Dict[str, Any]],
    skill_intelligence_index: Dict[str, Dict[str, Any]],
    enforce_additive_update_policy: bool,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, int]]:
    approved: List[Dict[str, Any]] = []
    suppressed: List[Dict[str, Any]] = []
    summary = {"passed": 0, "warned": 0, "blocked": 0}
    for recommendation in recommendations:
        proof = build_skill_continuity_proof(
            recommendation=recommendation,
            skill_intelligence_index=skill_intelligence_index,
        )
        recommendation["continuity_proof"] = proof
        verdict = str(proof.get("verdict", "warn") or "warn")
        if verdict == "block":
            summary["blocked"] += 1
            if enforce_additive_update_policy:
                recommendation["suppression_reason"] = "continuity_blocked"
                suppressed.append(recommendation)
                continue
        elif verdict == "warn":
            summary["warned"] += 1
        else:
            summary["passed"] += 1
        approved.append(recommendation)
    return approved, suppressed, summary


def build_pulse_bus_topology_audit(skills: List[Dict[str, Any]]) -> Dict[str, Any]:
    event_producers: Dict[str, List[str]] = {}
    event_producer_roles: Dict[str, Dict[str, str]] = {}
    input_patterns: Dict[str, List[str]] = {}
    input_route_meta: Dict[str, List[Dict[str, Any]]] = {}
    wildcard_listeners: List[Dict[str, Any]] = []
    guarded_wildcards: List[Dict[str, Any]] = []
    malformed_names: List[Dict[str, Any]] = []

    for skill in skills:
        manifest = parse_manifest(Path(skill["primary_path"]).parent)
        if not manifest:
            for copy in skill.get("copy_details", []):
                if not isinstance(copy, dict) or not copy.get("manifest_present"):
                    continue
                candidate_manifest = parse_manifest(Path(str(copy.get("path", ""))).parent)
                if candidate_manifest:
                    manifest = candidate_manifest
                    break
        inputs = manifest.get("inputs", [])
        outputs = manifest.get("outputs", [])
        if not isinstance(inputs, list):
            inputs = []
        if not isinstance(outputs, list):
            outputs = []

        for inp in inputs:
            if not isinstance(inp, dict):
                continue
            pattern = str(inp.get("pattern") or inp.get("event_type") or "").strip()
            if not pattern:
                continue

            route_mode = str(inp.get("route_mode") or "owned").strip().lower()
            route_priority_raw = inp.get("route_priority", 50)
            try:
                route_priority = int(route_priority_raw)
            except Exception:
                route_priority = 50

            exclude_patterns_raw = inp.get("exclude_patterns", [])
            exclude_patterns: List[str] = []
            if isinstance(exclude_patterns_raw, list):
                exclude_patterns = [str(item).strip() for item in exclude_patterns_raw if str(item).strip()]

            skill_id = skill["skill_id"]
            input_patterns.setdefault(pattern, []).append(skill_id)
            input_route_meta.setdefault(pattern, []).append(
                {
                    "skill_id": skill_id,
                    "route_mode": route_mode,
                    "route_priority": route_priority,
                    "exclude_patterns": exclude_patterns,
                }
            )

            if pattern == "*" or pattern.startswith("*"):
                if exclude_patterns or route_mode in {"broadcast", "observer"}:
                    guarded_wildcards.append(
                        {
                            "skill_id": skill_id,
                            "pattern": pattern,
                            "severity": "low",
                            "reason": "Wildcard listener is constrained by route_mode/exclude_patterns.",
                        }
                    )
                else:
                    wildcard_listeners.append(
                        {
                            "skill_id": skill_id,
                            "pattern": pattern,
                            "severity": "medium",
                            "reason": "Over-broad wildcard listener may cause noisy dispatch.",
                        }
                    )

            if not EVENT_NAME_PATTERN.match(pattern):
                malformed_names.append({"kind": "input_pattern", "skill_id": skill_id, "name": pattern})
            for excluded in exclude_patterns:
                if not EVENT_NAME_PATTERN.match(excluded):
                    malformed_names.append(
                        {"kind": "input_exclude_pattern", "skill_id": skill_id, "name": excluded}
                    )

        for out in outputs:
            if not isinstance(out, dict):
                continue
            event_type = str(out.get("event_type") or "").strip()
            if not event_type:
                continue
            event_producers.setdefault(event_type, []).append(skill["skill_id"])
            producer_role = str(out.get("event_producer_role") or out.get("event_producer_class") or "").strip()
            if producer_role:
                event_producer_roles.setdefault(event_type, {})[skill["skill_id"]] = producer_role
            if not EVENT_NAME_PATTERN.match(event_type):
                malformed_names.append({"kind": "output_event", "skill_id": skill["skill_id"], "name": event_type})

    orphan_emitters: List[Dict[str, Any]] = []
    for event_type, producers in sorted(event_producers.items()):
        matched = any(fnmatch.fnmatch(event_type, pattern) for pattern in input_patterns)
        if not matched:
            orphan_emitters.append(
                {
                    "event_type": event_type,
                    "producers": sorted(set(producers)),
                    "severity": "low" if event_type.endswith("_activity") else "medium",
                }
            )

    orphan_listeners: List[Dict[str, Any]] = []
    external_listener_patterns: List[Dict[str, Any]] = []
    external_runtime_patterns: List[Dict[str, Any]] = []
    external_operator_patterns: List[Dict[str, Any]] = []
    produced_events = list(event_producers.keys())
    for pattern, listeners in sorted(input_patterns.items()):
        if pattern == "*":
            continue
        matched = any(fnmatch.fnmatch(evt, pattern) for evt in produced_events)
        if not matched:
            route_entries = input_route_meta.get(pattern, [])
            listener_entry = {
                "pattern": pattern,
                "listeners": sorted(set(listeners)),
                "severity": "low",
            }
            if is_external_runtime_trigger_pattern(pattern):
                listener_entry["reason"] = "Pattern is expected to be emitted by runtime, app, or backend event sources."
                listener_entry["external_kind"] = "runtime"
                external_listener_patterns.append(listener_entry)
                external_runtime_patterns.append(listener_entry)
                continue
            if is_external_operator_trigger_pattern(pattern, route_entries):
                listener_entry["reason"] = "Pattern is expected to be emitted by external orchestrators, operators, CI, or user entrypoints."
                listener_entry["external_kind"] = "operator"
                external_listener_patterns.append(listener_entry)
                external_operator_patterns.append(listener_entry)
                continue
            orphan_listeners.append(
                {
                    "pattern": pattern,
                    "listeners": sorted(set(listeners)),
                    "severity": "medium",
                }
            )

    duplicate_routes: List[Dict[str, Any]] = []
    for pattern, listeners in sorted(input_patterns.items()):
        unique = sorted(set(listeners))
        if len(unique) <= 1 or pattern == "*":
            continue
        route_entries = input_route_meta.get(pattern, [])
        if any(entry.get("route_mode") == "broadcast" for entry in route_entries):
            continue
        ranked = sorted(
            route_entries,
            key=lambda item: (int(item.get("route_priority", 0)), str(item.get("skill_id", ""))),
            reverse=True,
        )
        if len(ranked) >= 2 and int(ranked[0].get("route_priority", 0)) > int(ranked[1].get("route_priority", 0)):
            continue
        duplicate_routes.append(
            {
                "pattern": pattern,
                "listener_count": len(unique),
                "listeners": unique,
                "severity": "medium",
                "route_priorities": {
                    str(item.get("skill_id", "")): int(item.get("route_priority", 0)) for item in route_entries
                },
            }
        )

    intentional_shared_outputs: List[Dict[str, Any]] = []
    ambiguous_shared_outputs: List[Dict[str, Any]] = []
    shared_contracts = shared_output_event_contracts()
    for event_type, producers in sorted(event_producers.items()):
        unique = sorted(set(producers))
        if len(unique) <= 1:
            continue
        contract = shared_contracts.get(event_type)
        producer_roles = event_producer_roles.get(event_type, {})
        roles = {producer: producer_roles.get(producer, "") for producer in unique}
        if contract:
            allowed_producers = {
                str(item).strip() for item in contract.get("allowed_producers", []) if str(item).strip()
            }
            allowed_roles = {str(item).strip() for item in contract.get("allowed_roles", []) if str(item).strip()}
            role_values = {value for value in roles.values() if value}
            if set(unique).issubset(allowed_producers) and (not allowed_roles or role_values.issubset(allowed_roles)):
                intentional_shared_outputs.append(
                    {
                        "event_type": event_type,
                        "producers": unique,
                        "producer_roles": roles,
                        "ownership_mode": str(contract.get("ownership_mode") or "intentional_shared"),
                        "severity": "info",
                    }
                )
                continue
        ambiguous_shared_outputs.append(
            {
                "event_type": event_type,
                "producers": unique,
                "producer_roles": roles,
                "severity": "medium",
            }
        )

    suggestions: List[str] = []
    if orphan_emitters:
        suggestions.append("Add downstream listeners or deprecate unconsumed emitted events.")
    if orphan_listeners:
        suggestions.append("Review listener patterns that never match any emitted event.")
    if wildcard_listeners:
        suggestions.append("Constrain wildcard listeners with more specific patterns and conditions.")
    if duplicate_routes:
        suggestions.append("Introduce route ownership or priority to avoid duplicate dispatch triggers.")
    if ambiguous_shared_outputs:
        suggestions.append("Clarify shared output event ownership with explicit producer roles or shared-event contracts.")
    if guarded_wildcards:
        suggestions.append("Guarded wildcard listeners are present; keep exclude patterns reviewed as event taxonomy evolves.")
    if malformed_names:
        suggestions.append("Normalize event names to lowercase portable pattern-safe tokens.")
    if not suggestions:
        suggestions.append("Pulse bus topology is healthy; maintain current contract discipline.")

    return {
        "summary": {
            "producer_events": len(event_producers),
            "listener_patterns": len(input_patterns),
            "orphan_emitters": len(orphan_emitters),
            "orphan_listeners": len(orphan_listeners),
            "external_listener_patterns": len(external_listener_patterns),
            "external_runtime_patterns": len(external_runtime_patterns),
            "external_operator_patterns": len(external_operator_patterns),
            "wildcard_overreach_listeners": len(wildcard_listeners),
            "duplicate_routes": len(duplicate_routes),
            "intentional_shared_output_events": len(intentional_shared_outputs),
            "ambiguous_shared_output_events": len(ambiguous_shared_outputs),
            "naming_inconsistencies": len(malformed_names),
        },
        "orphan_emitters": orphan_emitters,
        "orphan_listeners": orphan_listeners,
        "external_listener_patterns": external_listener_patterns,
        "external_runtime_patterns": external_runtime_patterns,
        "external_operator_patterns": external_operator_patterns,
        "wildcard_overreach_listeners": wildcard_listeners,
        "guarded_wildcard_listeners": guarded_wildcards,
        "duplicate_or_overlapping_routes": duplicate_routes,
        "intentional_shared_output_events": intentional_shared_outputs,
        "ambiguous_shared_output_events": ambiguous_shared_outputs,
        "naming_inconsistencies": malformed_names,
        "suggested_manifest_contract_improvements": suggestions,
    }


def build_capability_recommendations(
    *,
    skills: List[Dict[str, Any]],
    individual_skill_intelligence: List[Dict[str, Any]],
    session_intelligence: Dict[str, Any],
    workspace_intelligence: Dict[str, Any],
    recalled_wisdom: List[Dict[str, Any]],
    pulse_audit: Dict[str, Any],
    strictness: str,
    enforce_additive_update_policy: bool,
    workspace_root: Path,
) -> Dict[str, Any]:
    skill_ids = {item["skill_id"] for item in skills}
    skill_index = {item["skill_id"]: item for item in skills}
    skill_intelligence_index = {
        str(item.get("skill_id", "") or "").strip(): item
        for item in individual_skill_intelligence
        if str(item.get("skill_id", "") or "").strip()
    }
    skill_content_cache: Dict[str, str] = {}
    manifest_cache: Dict[str, Dict[str, Any]] = {}
    signal_blob = " ".join(session_intelligence.get("signals", []))
    signal_terms = set(tokenize_terms(signal_blob))
    evidence_refs_base = [
        f"session:{session_intelligence.get('source', 'unknown')}",
    ]

    if recalled_wisdom:
        top = recalled_wisdom[0]
        top_source = sanitize_text(str(top.get("_source_path", "unknown")), workspace_root)
        evidence_refs_base.append(f"wisdom:{top_source}")

    def skill_content(skill_id: str) -> str:
        if skill_id in skill_content_cache:
            return skill_content_cache[skill_id]
        entry = skill_index.get(skill_id)
        if not entry:
            skill_content_cache[skill_id] = ""
            return ""
        path = Path(str(entry.get("primary_path", "")))
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            text = ""
        skill_content_cache[skill_id] = text
        return text

    def skill_manifest(skill_id: str) -> Dict[str, Any]:
        if skill_id in manifest_cache:
            return manifest_cache[skill_id]
        entry = skill_index.get(skill_id)
        if not entry:
            manifest_cache[skill_id] = {}
            return {}
        path = Path(str(entry.get("primary_path", "")))
        manifest = parse_manifest(path.parent) if path.parent else {}
        manifest_cache[skill_id] = manifest
        return manifest

    def skill_sources(skill_id: str) -> List[str]:
        entry = skill_index.get(skill_id)
        if not entry:
            return []
        raw = entry.get("sources", [])
        if not isinstance(raw, list):
            return []
        return [str(item) for item in raw if str(item).strip()]

    def has_markers(skill_id: str, markers: Sequence[str]) -> bool:
        if not markers:
            return False
        content = skill_content(skill_id)
        if not content:
            return False
        return all(marker in content for marker in markers)

    def manifest_contract_satisfied(skill_id: str, contract: Dict[str, Any]) -> bool:
        if not contract:
            return False
        manifest = skill_manifest(skill_id)
        if not manifest:
            return False
        inputs = manifest.get("inputs", []) if isinstance(manifest.get("inputs", []), list) else []
        outputs = manifest.get("outputs", []) if isinstance(manifest.get("outputs", []), list) else []
        input_patterns = {str(inp.get("pattern") or inp.get("event_type") or "").strip() for inp in inputs if isinstance(inp, dict)}
        output_events = {str(out.get("event_type") or "").strip() for out in outputs if isinstance(out, dict)}
        required_inputs = set(contract.get("inputs", []) or [])
        required_outputs = set(contract.get("outputs", []) or [])
        return required_inputs.issubset(input_patterns) and required_outputs.issubset(output_events)

    def gate_recommendation(confidence: float, evidence_refs: List[str]) -> bool:
        min_refs = 2 if strictness in {"high", "balanced"} else 1
        if len(evidence_refs) < min_refs:
            return False
        if strictness == "high":
            return confidence >= 0.75 and len(evidence_refs) >= 2
        if strictness == "balanced":
            return confidence >= 0.6
        return confidence >= 0.45

    update_candidates: List[Dict[str, Any]] = []
    suppressed: List[Dict[str, Any]] = []
    policy_summary = {
        "policy_id": "additive_non_destructive_portable_v1",
        "enforced": bool(enforce_additive_update_policy),
        "passed": 0,
        "blocked": 0,
    }

    def maybe_add_update(
        *,
        skill_id: str,
        reason: str,
        keywords: Sequence[str],
        suggested_changes: Sequence[str],
        proposed_manifest_io: Dict[str, Any],
        portability_note: str,
        completion_markers: Sequence[str] = (),
        require_manifest_contract: bool = False,
        operating_move: str = "upgrade",
        confidence_floor: float = 0.58,
    ) -> None:
        if skill_id not in skill_ids:
            return
        if has_markers(skill_id, completion_markers):
            if not require_manifest_contract or manifest_contract_satisfied(skill_id, proposed_manifest_io):
                return
        keyword_hits = sorted(set(signal_terms.intersection(set(keywords))))
        evidence_refs = list(evidence_refs_base)
        if keyword_hits:
            evidence_refs.append(f"keywords:{','.join(keyword_hits)}")
        skill_card = skill_intelligence_index.get(skill_id, {})
        if skill_card:
            evidence_refs.append(
                f"skill_intelligence:{skill_card.get('trust_posture', 'watch')}"
            )

        context_bonus = 0.0
        mirrored_sources = skill_sources(skill_id)
        if len(mirrored_sources) >= 2:
            evidence_refs.append(f"roots:{','.join(mirrored_sources[:3])}")
            context_bonus += 0.05

        cross_ws_count = int(session_intelligence.get("cross_workspace_records_used", 0) or 0)
        if cross_ws_count >= 5:
            evidence_refs.append("context:cross_workspace_records>=5")
            context_bonus += 0.06

        pulse_summary = pulse_audit.get("summary", {})
        topology_nonzero = (
            int(pulse_summary.get("orphan_listeners", 0) or 0)
            + int(pulse_summary.get("duplicate_routes", 0) or 0)
            + int(pulse_summary.get("wildcard_overreach_listeners", 0) or 0)
        )
        if skill_id in {"skill_director", "orchestration-sentinel-v2"} and topology_nonzero > 0:
            evidence_refs.append("pulse_audit:topology_findings")
            context_bonus += 0.08

        confidence = min(
            0.97,
            confidence_floor + 0.09 * len(keyword_hits) + 0.04 * len(evidence_refs) + context_bonus,
        )
        rec = {
            "type": "update",
            "skill_id": skill_id,
            "operating_move": operating_move,
            "confidence": round(confidence, 3),
            "reason": reason,
            "evidence_refs": evidence_refs,
            "suggested_changes": list(suggested_changes),
            "proposed_manifest_io": proposed_manifest_io,
            "portability_privacy_notes": portability_note,
        }
        policy_check = evaluate_additive_portability_policy(
            reason=reason,
            suggested_changes=suggested_changes,
            portability_note=portability_note,
        )
        rec["change_policy"] = policy_check
        if enforce_additive_update_policy and not policy_check["is_compliant"]:
            rec["suppression_reason"] = "policy_non_compliant"
            suppressed.append(rec)
            policy_summary["blocked"] += 1
            return
        if gate_recommendation(confidence, evidence_refs):
            update_candidates.append(rec)
            policy_summary["passed"] += 1
        else:
            suppressed.append(rec)

    maybe_add_update(
        skill_id="watcher",
        reason="Session/context awareness and cross-workspace recall surfaced as primary need.",
        keywords=("session", "context", "wisdom", "archive", "cross-workspace", "recommendations"),
        suggested_changes=(
            "Strengthen context ingestion fallback chain and sanitization.",
            "Keep recommendation rationale evidence-backed and deterministic.",
            "Prioritize control-plane and mirror interventions before workspace-fit moves when posture is intervene.",
            "Classify strategic moves as upgrade, consolidate, mirror, or hold with deterministic ranking.",
        ),
        proposed_manifest_io={
            "inputs": ["stability_gate_check", "skill_director_context_ingest_requested"],
            "outputs": ["skill_director_activity", "skill_recommendation_emitted"],
        },
        portability_note="Use portable placeholders for path/user identity in archived context.",
        completion_markers=(
            "## Session Context Reliability Contract",
            "## Deterministic Recommendation Evidence Contract",
            "## Strategic Move Prioritization Contract",
        ),
        require_manifest_contract=True,
        operating_move="upgrade",
        confidence_floor=0.72,
    )
    maybe_add_update(
        skill_id="model-ux-orchestrator",
        reason="Truthful UX and action confirmation themes remain high-signal requirements.",
        keywords=("truthful", "verify", "claimed", "success", "filesystem", "tool"),
        suggested_changes=(
            "Expand no-proof claim blocking patterns.",
            "Require tool-confirmed status in user-visible completion prose.",
        ),
        proposed_manifest_io={
            "inputs": ["dispatch_completed", "dispatch_failed", "tool_result_received"],
            "outputs": ["ux_truthfulness_guardrail_applied"],
        },
        portability_note="Keep verification logic model-agnostic and path-agnostic.",
        completion_markers=(
            "## No-Proof Claim Blocklist",
            "## Tool-Confirmed Completion Contract",
        ),
    )
    maybe_add_update(
        skill_id="web-search-grounding-specialist",
        reason="Fact-check follow-ups and grounding quality are persistent contextual signals.",
        keywords=("fact", "check", "grounding", "search", "query", "contextual"),
        suggested_changes=(
            "Prioritize contextual follow-up expansion before generic query fallback.",
            "Emit diagnostics traces for normalized query quality arbitration.",
        ),
        proposed_manifest_io={
            "inputs": ["search_requested", "grounding_validation_requested"],
            "outputs": ["grounding_quality_reported"],
        },
        portability_note="Do not persist raw private queries; archive only sanitized query summaries.",
        completion_markers=(
            "## Contextual Follow-Up Expansion Contract",
            "## Query Quality Arbitration Diagnostics",
        ),
    )
    maybe_add_update(
        skill_id="orchestration-sentinel-v2",
        reason="Pulse bus topology findings indicate opportunities for tighter dispatch governance.",
        keywords=("pulse", "event", "manifest", "dispatch", "orphan", "duplicate"),
        suggested_changes=(
            "Add route lint pass for orphaned producers/listeners.",
            "Publish deterministic dispatch health summary event.",
            "Document consolidation bias so v2 owns manifest.v2 routing decisions.",
        ),
        proposed_manifest_io={
            "inputs": ["stability_gate_check", "dispatch_requested"],
            "outputs": ["dispatch_health_report_emitted"],
        },
        portability_note="Topology metrics should use skill IDs/events only, with no host paths.",
        completion_markers=(
            "### Route Ownership and Priority Contract",
            "### Route Lint and Health Emission",
            "### Topology Remediation Ladder",
        ),
        operating_move="consolidate",
        confidence_floor=0.76,
    )
    maybe_add_update(
        skill_id="skill-portability-guardian",
        reason="Mirrored governance skills need codex-canonical ownership and deterministic mirror closure guidance.",
        keywords=("portability", "mirror", "canonical", "drift", "sanitize"),
        suggested_changes=(
            "Declare codex as the canonical authoring root and antigravity as the distribution mirror.",
            "Classify mirrored skill decisions as mirror, hold, or manual review without destructive rewrites.",
            "Emit mirror-closure guidance that preserves sidecar metadata and profile-specific blocks.",
        ),
        proposed_manifest_io={
            "inputs": ["skills_portability_audit_requested"],
            "outputs": ["skill_portability_guardian_completed", "skill_portability_guardian_failed"],
        },
        portability_note="Keep mirror governance path-agnostic and preserve root-specific metadata when intent is equivalent.",
        completion_markers=(
            "## Canonical Root and Mirror Governance",
            "## Mirror Closure Decision Contract",
        ),
        operating_move="mirror",
        confidence_floor=0.74,
    )
    maybe_add_update(
        skill_id="omniscient-skill-cataloger",
        reason="Inventory truth is a mirrored governance concern and should explicitly honor codex-canonical ownership.",
        keywords=("catalog", "inventory", "scope", "mirror", "canonical"),
        suggested_changes=(
            "Document codex as authoritative inventory root when mirrored copies are semantically equivalent.",
            "Classify mirror-safe catalog output separately from manual-review drift.",
        ),
        proposed_manifest_io={
            "inputs": ["stability_gate_check"],
            "outputs": ["omniscient_skill_cataloger_activity"],
        },
        portability_note="Keep catalog output portable and source-aware without embedding local file URIs.",
        completion_markers=(
            "## Canonical Root and Mirror Classification",
            "## Mirror-Safe Catalog Governance",
        ),
        operating_move="mirror",
        confidence_floor=0.72,
    )
    maybe_add_update(
        skill_id="proactive-skill-evolution-planner",
        reason="Evolution planning should prioritize control-plane and mirror closure work before lower-leverage domain upgrades.",
        keywords=("evolution", "planner", "upgrade", "mirror", "canonical"),
        suggested_changes=(
            "Bias intervention plans toward control-plane and mirrored governance fixes when ecosystem posture is intervene.",
            "Declare codex as canonical for mirrored planning contracts and treat antigravity as distribution.",
        ),
        proposed_manifest_io={
            "inputs": ["skill_director_activity", "postmortem_generated", "skill_evolution_requested"],
            "outputs": ["skill_evolution_plan_emitted", "skill_recommendation_emitted", "skill_evolution_scorecard_emitted"],
        },
        portability_note="Use sanitized evidence refs and preserve mirror-safe contracts across roots.",
        completion_markers=(
            "## Canonical Root and Mirror Scope",
            "## Intervention-First Planning Contract",
        ),
        operating_move="mirror",
        confidence_floor=0.72,
    )
    maybe_add_update(
        skill_id="ai-agent-bi-researcher",
        reason="Current project intent favors evidence-graded market intelligence that maps directly to implementation lanes and companion skills.",
        keywords=("strategy", "research", "roadmap", "market", "agent", "adopt"),
        suggested_changes=(
            "Add decision lanes that separate adopt-now, prototype-next, and monitor-only recommendations.",
            "Map recommendations to companion skills so research output lands on executable implementation paths.",
            "Keep the default human relay compressed and chat-friendly while preserving evidence detail.",
        ),
        proposed_manifest_io={
            "inputs": ["research:scan_requested", "roadmap:review_requested", "research:competitive_intel_requested"],
            "outputs": ["research:trend_report_ready", "research:action_candidates_emitted", "ai_agent_bi_researcher_activity"],
        },
        portability_note="Ground outputs in sources and companion-skill names, not workspace-private paths or brands.",
        completion_markers=(
            "## Decision Lanes Contract",
            "## Companion Skill Fit",
        ),
        operating_move="upgrade",
        confidence_floor=0.71,
    )
    maybe_add_update(
        skill_id="repository-harmonization-specialist",
        reason="Cross-workspace structure work needs stronger intake, rollback, and runtime-boundary contracts before moving repositories around.",
        keywords=("harmonize", "monorepo", "shared", "runtime", "cutover", "rollback"),
        suggested_changes=(
            "Add workspace-family intake that distinguishes app roots, shared libraries, and runtime-owned state.",
            "Require explicit cutover and rollback plans before structural migration.",
            "Strengthen post-move verification for launch contracts and mutable-state boundaries.",
        ),
        proposed_manifest_io={},
        portability_note="Keep harmonization guidance repository-agnostic and avoid hardcoded local layouts or ports.",
        completion_markers=(
            "## Workspace Family Intake",
            "## Cutover and Rollback Contract",
        ),
        operating_move="upgrade",
        confidence_floor=0.69,
    )

    new_skill_candidates: List[Dict[str, Any]] = []

    if not any("wisdom" in skill_id for skill_id in skill_ids):
        evidence_refs = list(evidence_refs_base)
        evidence_refs.append("gap:no_skill_contains_wisdom")
        confidence = 0.82 if gate_recommendation(0.82, evidence_refs) else 0.67
        proposal = {
            "type": "new_skill",
            "proposed_skill_id": "wisdom-retention-archivist",
            "confidence": round(confidence, 3),
            "reason": "No dedicated skill currently governs reusable cross-workspace wisdom lifecycle.",
            "evidence_refs": evidence_refs,
            "suggested_changes": [
                "Maintain append-only normalized wisdom ledgers and summaries.",
                "Provide retrieval scoring APIs for contextual recommendation engines.",
            ],
            "proposed_manifest_io": {
                "inputs": ["skill_recommendation_emitted", "postmortem_generated"],
                "outputs": ["wisdom_entry_archived", "wisdom_digest_updated"],
            },
            "portability_privacy_notes": "Archive sanitized lessons, not raw private transcripts.",
        }
        policy_check = evaluate_additive_portability_policy(
            reason=proposal["reason"],
            suggested_changes=proposal["suggested_changes"],
            portability_note=proposal["portability_privacy_notes"],
        )
        proposal["change_policy"] = policy_check
        if enforce_additive_update_policy and not policy_check["is_compliant"]:
            proposal["suppression_reason"] = "policy_non_compliant"
            suppressed.append(proposal)
            policy_summary["blocked"] += 1
        elif gate_recommendation(confidence, evidence_refs):
            new_skill_candidates.append(proposal)
            policy_summary["passed"] += 1
        else:
            suppressed.append(proposal)

    if as_float(pulse_audit.get("summary", {}).get("orphan_emitters", 0), 0.0) >= 8:
        evidence_refs = list(evidence_refs_base)
        evidence_refs.append("pulse_audit:orphan_emitters>=8")
        confidence = 0.79
        proposal = {
            "type": "new_skill",
            "proposed_skill_id": "pulse-contract-linter",
            "confidence": round(confidence, 3),
            "reason": "Pulse topology indicates high orphan event volume requiring dedicated contract linting.",
            "evidence_refs": evidence_refs,
            "suggested_changes": [
                "Continuously lint manifest inputs/outputs and event naming.",
                "Open remediation recommendations per skill contract owner.",
            ],
            "proposed_manifest_io": {
                "inputs": ["stability_gate_check", "manifest_updated"],
                "outputs": ["pulse_contract_findings_emitted"],
            },
            "portability_privacy_notes": "Analyze manifests and event contracts only; avoid workspace-private payload data.",
        }
        policy_check = evaluate_additive_portability_policy(
            reason=proposal["reason"],
            suggested_changes=proposal["suggested_changes"],
            portability_note=proposal["portability_privacy_notes"],
        )
        proposal["change_policy"] = policy_check
        if enforce_additive_update_policy and not policy_check["is_compliant"]:
            proposal["suppression_reason"] = "policy_non_compliant"
            suppressed.append(proposal)
            policy_summary["blocked"] += 1
        elif gate_recommendation(confidence, evidence_refs):
            new_skill_candidates.append(proposal)
            policy_summary["passed"] += 1
        else:
            suppressed.append(proposal)

    def manifest_io_excerpt(manifest: Dict[str, Any]) -> Dict[str, Any]:
        inputs: List[str] = []
        outputs: List[str] = []
        raw_inputs = manifest.get("inputs", [])
        raw_outputs = manifest.get("outputs", [])
        if isinstance(raw_inputs, list):
            for item in raw_inputs:
                if not isinstance(item, dict):
                    continue
                pattern = str(item.get("pattern") or item.get("event_type") or "").strip()
                if pattern:
                    inputs.append(pattern)
        if isinstance(raw_outputs, list):
            for item in raw_outputs:
                if not isinstance(item, dict):
                    continue
                event_type = str(item.get("event_type") or "").strip()
                if event_type:
                    outputs.append(event_type)
        return {
            "inputs": sorted(set(inputs))[:6],
            "outputs": sorted(set(outputs))[:6],
        }

    workspace_profiles_raw = workspace_intelligence.get("workspace_profiles", [])
    workspace_profiles: List[Dict[str, Any]] = []
    if isinstance(workspace_profiles_raw, list):
        workspace_profiles = [
            item for item in workspace_profiles_raw if isinstance(item, dict)
        ]

    skill_terms_map: Dict[str, List[str]] = {}
    for item in skills:
        skill_id = str(item.get("skill_id", ""))
        corpus = " ".join(
            [
                skill_id,
                str(item.get("name", "")),
                str(item.get("summary", "")),
                str(item.get("trigger", "")),
                str(item.get("group_id", "")),
            ]
        )
        skill_terms_map[skill_id] = tokenize_terms(corpus)

    used_update_skill_ids = {
        str(rec.get("skill_id", "")) for rec in update_candidates if isinstance(rec, dict)
    }
    for profile in workspace_profiles:
        demand_terms = profile.get("signal_terms", [])
        if not isinstance(demand_terms, list):
            continue
        demand_terms = [str(term) for term in demand_terms if str(term).strip()][:30]
        if not demand_terms:
            continue

        workspace_name = str(profile.get("workspace_name", "workspace"))
        goal_summary = compact_sentence(str(profile.get("goal_summary", "")), limit=120)
        hours_since = as_float(profile.get("hours_since_last_activity", 99999.0), 99999.0)

        workspace_weight = 1.0
        if bool(profile.get("is_current", False)):
            workspace_weight += 0.25
        if hours_since <= 48:
            workspace_weight += 0.15

        scored: List[Tuple[float, float, str]] = []
        for skill in skills:
            skill_id = str(skill.get("skill_id", ""))
            skill_terms = skill_terms_map.get(skill_id, [])
            if not skill_terms:
                continue
            overlap = overlap_score(demand_terms, skill_terms)
            if overlap <= 0.0:
                continue
            scored.append((overlap * workspace_weight, overlap, skill_id))

        scored.sort(key=lambda item: item[0], reverse=True)
        for weighted_overlap, overlap, skill_id in scored[:3]:
            if skill_id in used_update_skill_ids:
                continue
            entry = skill_index.get(skill_id)
            if not entry:
                continue
            existing_text = skill_content(skill_id).lower()
            if (
                "workspace goal alignment" in existing_text
                or "workspace goal ingestion" in existing_text
                or "goal-aligned bootstrap plan" in existing_text
            ):
                continue

            matched_terms = sorted(
                set(demand_terms).intersection(set(skill_terms_map.get(skill_id, [])))
            )[:6]
            evidence_refs = list(evidence_refs_base)
            evidence_refs.append(f"workspace:{workspace_name}")
            evidence_refs.append(f"workspace_goal:{goal_summary or 'n/a'}")
            if matched_terms:
                evidence_refs.append(f"overlap_terms:{','.join(matched_terms)}")
            if bool(profile.get("is_current", False)):
                evidence_refs.append("workspace:current")
            if hours_since <= 48:
                evidence_refs.append("workspace:active_within_48h")

            confidence = min(
                0.95,
                0.6
                + (0.42 * overlap)
                + (0.08 if bool(profile.get("is_current", False)) else 0.0)
                + (0.05 if hours_since <= 48 else 0.0),
            )
            manifest_excerpt = manifest_io_excerpt(skill_manifest(skill_id))
            rec = {
                "type": "update",
                "skill_id": skill_id,
                "confidence": round(confidence, 3),
                "reason": (
                    f"Workspace '{workspace_name}' goal and recent activity indicate "
                    f"this skill should adapt to current project intent."
                ),
                "evidence_refs": evidence_refs,
                "suggested_changes": [
                    f"Add a 'Workspace Goal Alignment' section for {workspace_name}.",
                    f"Include trigger examples that reference: {', '.join(matched_terms[:4]) or 'current workspace signals'}.",
                    "Add proactive guidance for near-term tasks observed in recent activity.",
                ],
                "proposed_manifest_io": manifest_excerpt,
                "portability_privacy_notes": "Preserve workspace-agnostic language and avoid embedding private paths.",
            }
            policy_check = evaluate_additive_portability_policy(
                reason=rec["reason"],
                suggested_changes=rec["suggested_changes"],
                portability_note=rec["portability_privacy_notes"],
            )
            rec["change_policy"] = policy_check
            if enforce_additive_update_policy and not policy_check["is_compliant"]:
                rec["suppression_reason"] = "policy_non_compliant"
                suppressed.append(rec)
                policy_summary["blocked"] += 1
            elif gate_recommendation(confidence, evidence_refs):
                update_candidates.append(rec)
                used_update_skill_ids.add(skill_id)
                policy_summary["passed"] += 1
            else:
                suppressed.append(rec)

    all_skill_terms: set[str] = set()
    for terms in skill_terms_map.values():
        all_skill_terms.update(terms)

    uncovered_terms: List[str] = []
    for profile in workspace_profiles:
        demand_terms = profile.get("signal_terms", [])
        if not isinstance(demand_terms, list):
            continue
        for term in demand_terms:
            token = str(term).strip().lower()
            if len(token) < 4:
                continue
            if token in all_skill_terms:
                continue
            if token in uncovered_terms:
                continue
            uncovered_terms.append(token)
            if len(uncovered_terms) >= 12:
                break
        if len(uncovered_terms) >= 12:
            break

    if len(workspace_profiles) >= 2 and "cross-workspace-goal-intelligence" not in skill_ids:
        evidence_refs = list(evidence_refs_base)
        evidence_refs.append(f"workspaces:{len(workspace_profiles)}")
        evidence_refs.append(
            f"cross_workspace_records:{int(session_intelligence.get('cross_workspace_records_used', 0) or 0)}"
        )
        confidence = 0.84 if len(uncovered_terms) >= 2 else 0.78
        proposal = {
            "type": "new_skill",
            "proposed_skill_id": "cross-workspace-goal-intelligence",
            "confidence": round(confidence, 3),
            "reason": "Multiple active workspaces require unified goal memory and intent routing across projects.",
            "evidence_refs": evidence_refs,
            "suggested_changes": [
                "Track per-workspace goals, momentum, and confidence over time.",
                "Expose a deterministic query surface for 'current focus per workspace'.",
                "Emit proactive upgrade prompts when workspace goals diverge from available skills.",
            ],
            "proposed_manifest_io": {
                "inputs": ["skill_director_context_ingest_requested", "stability_gate_check"],
                "outputs": ["workspace_goal_intelligence_emitted", "skill_recommendation_emitted"],
            },
            "portability_privacy_notes": "Persist sanitized summaries and avoid private path leakage in cross-workspace memory.",
        }
        policy_check = evaluate_additive_portability_policy(
            reason=proposal["reason"],
            suggested_changes=proposal["suggested_changes"],
            portability_note=proposal["portability_privacy_notes"],
        )
        proposal["change_policy"] = policy_check
        if enforce_additive_update_policy and not policy_check["is_compliant"]:
            proposal["suppression_reason"] = "policy_non_compliant"
            suppressed.append(proposal)
            policy_summary["blocked"] += 1
        elif gate_recommendation(confidence, evidence_refs):
            new_skill_candidates.append(proposal)
            policy_summary["passed"] += 1
        else:
            suppressed.append(proposal)

    if uncovered_terms and "proactive-skill-evolution-planner" not in skill_ids:
        evidence_refs = list(evidence_refs_base)
        evidence_refs.append(f"uncovered_terms:{','.join(uncovered_terms[:5])}")
        confidence = min(0.9, 0.72 + (0.02 * min(6, len(uncovered_terms))))
        proposal = {
            "type": "new_skill",
            "proposed_skill_id": "proactive-skill-evolution-planner",
            "confidence": round(confidence, 3),
            "reason": "Emerging workspace goals include repeated terms not strongly covered by existing skill contracts.",
            "evidence_refs": evidence_refs,
            "suggested_changes": [
                "Continuously detect gaps between workspace goals and current skill coverage.",
                "Auto-propose upgrade diffs with explicit evidence and confidence thresholds.",
                "Surface a weekly roadmap for skill upgrades and net-new skill opportunities.",
            ],
            "proposed_manifest_io": {
                "inputs": ["skill_director_activity", "postmortem_generated"],
                "outputs": ["skill_evolution_plan_emitted", "skill_recommendation_emitted"],
            },
            "portability_privacy_notes": "Store only sanitized, aggregated intent signals across workspaces.",
        }
        policy_check = evaluate_additive_portability_policy(
            reason=proposal["reason"],
            suggested_changes=proposal["suggested_changes"],
            portability_note=proposal["portability_privacy_notes"],
        )
        proposal["change_policy"] = policy_check
        if enforce_additive_update_policy and not policy_check["is_compliant"]:
            proposal["suppression_reason"] = "policy_non_compliant"
            suppressed.append(proposal)
            policy_summary["blocked"] += 1
        elif gate_recommendation(confidence, evidence_refs):
            new_skill_candidates.append(proposal)
            policy_summary["passed"] += 1
        else:
            suppressed.append(proposal)

    update_candidates, continuity_suppressed_updates, continuity_update_summary = attach_continuity_proofs(
        recommendations=update_candidates,
        skill_intelligence_index=skill_intelligence_index,
        enforce_additive_update_policy=bool(enforce_additive_update_policy),
    )
    new_skill_candidates, continuity_suppressed_new, continuity_new_summary = attach_continuity_proofs(
        recommendations=new_skill_candidates,
        skill_intelligence_index=skill_intelligence_index,
        enforce_additive_update_policy=bool(enforce_additive_update_policy),
    )
    suppressed.extend(continuity_suppressed_updates)
    suppressed.extend(continuity_suppressed_new)

    summary = {
        "strictness": strictness,
        "recommended_updates": len(update_candidates),
        "recommended_new_skills": len(new_skill_candidates),
        "suppressed": len(suppressed),
        "workspace_profiles_considered": len(workspace_profiles),
        "policy_enforced": bool(enforce_additive_update_policy),
        "policy_passed": int(policy_summary["passed"]),
        "policy_blocked": int(policy_summary["blocked"]),
        "continuity_proofs_emitted": len(update_candidates) + len(new_skill_candidates),
        "continuity_passed": int(continuity_update_summary["passed"] + continuity_new_summary["passed"]),
        "continuity_warned": int(continuity_update_summary["warned"] + continuity_new_summary["warned"]),
        "continuity_blocked": int(continuity_update_summary["blocked"] + continuity_new_summary["blocked"]),
        "skill_cards_considered": len(individual_skill_intelligence),
    }

    return {
        "strictness": strictness,
        "summary": summary,
        "update_policy": policy_summary,
        "continuity_summary": summary,
        "recommended_updates": update_candidates,
        "recommended_new_skills": new_skill_candidates,
        "suppressed_recommendations": suppressed,
    }


def evolution_priority(index: int) -> str:
    if index <= 0:
        return "P0"
    if index <= 2:
        return "P1"
    return "P2"


def evolution_risk(
    *,
    action: str,
    operating_move: str,
    target_skill: str,
) -> str:
    if action == "defer":
        return "low"
    if operating_move == "consolidate":
        return "high"
    if target_skill in {"skill_director", "orchestration-sentinel-v2", "orchestration-sentinel"}:
        return "medium"
    if action == "create_new":
        return "medium"
    if operating_move == "mirror":
        return "low"
    return "low"


def evolution_validation_gate(action: Dict[str, Any]) -> str:
    action_kind = str(action.get("action", "update_existing") or "update_existing")
    target_skill = str(action.get("target_skill", "") or "skill")
    if action_kind == "create_new":
        return (
            f"Validate skill structure, manifest parity, and inventory visibility for `{target_skill}`."
        )
    if action_kind == "defer":
        return "Re-run The Watcher after stronger evidence or topology changes arrive."
    operating_move = str(action.get("operating_move", "upgrade") or "upgrade")
    if operating_move == "mirror":
        return f"Validate mirrored intent/hash alignment and rerun The Watcher drift check for `{target_skill}`."
    if operating_move == "consolidate":
        return f"Validate manifest routing ownership and pulse topology health for `{target_skill}`."
    return f"Validate additive contract changes, manifest parity, and chat/JSON continuity for `{target_skill}`."


def build_watcher_evolution(
    *,
    metadata: Dict[str, Any],
    session_intelligence: Dict[str, Any],
    workspace_root: Path,
    freshness_audit: Dict[str, Any],
    director_final_pass: Dict[str, Any],
    capability_recommendations: Dict[str, Any],
    pulse_bus_topology_audit: Dict[str, Any],
    watcher_intelligence: Dict[str, Any],
) -> Dict[str, Any]:
    recommended_updates = capability_recommendations.get("recommended_updates", [])
    recommended_new_skills = capability_recommendations.get("recommended_new_skills", [])
    suppressed_recommendations = capability_recommendations.get("suppressed_recommendations", [])
    pulse_summary = pulse_bus_topology_audit.get("summary", {})
    drift = director_final_pass.get("drift_summary", {})

    recommendation_index: Dict[str, Dict[str, Any]] = {}
    for item in recommended_updates:
        if not isinstance(item, dict):
            continue
        target = str(item.get("skill_id", "") or "").strip()
        if target:
            recommendation_index[target] = item
    for item in recommended_new_skills:
        if not isinstance(item, dict):
            continue
        target = str(item.get("proposed_skill_id", "") or "").strip()
        if target:
            recommendation_index[target] = item

    actions: List[Dict[str, Any]] = []
    strategic_moves = watcher_intelligence.get("strategic_moves", []) or []
    if isinstance(strategic_moves, list):
        for index, move in enumerate(strategic_moves):
            if not isinstance(move, dict):
                continue
            target_skill = str(move.get("target", "") or "").strip()
            if not target_skill:
                continue
            recommendation = recommendation_index.get(target_skill, {})
            action_kind = "update_existing"
            if str(move.get("action", "update") or "update") == "create":
                action_kind = "create_new"
            operating_move = str(
                move.get("operating_move", "create" if action_kind == "create_new" else "upgrade")
                or ("create" if action_kind == "create_new" else "upgrade")
            )
            suggested_changes = recommendation.get("suggested_changes", [])
            additive_scope = compact_sentence(
                " ".join(str(item) for item in suggested_changes if str(item).strip()),
                limit=200,
            )
            if not additive_scope:
                additive_scope = compact_sentence(str(move.get("reason", "")), limit=200)
            portability_note = compact_sentence(
                str(
                    recommendation.get("portability_privacy_notes", "")
                    or move.get("portability_note", "")
                    or "Keep the change additive, portable, and privacy-safe."
                ),
                limit=160,
            )
            continuity_proof = recommendation.get("continuity_proof", {}) if isinstance(recommendation, dict) else {}
            actions.append(
                {
                    "action": action_kind,
                    "target_skill": target_skill,
                    "priority": evolution_priority(index),
                    "rationale": compact_sentence(str(move.get("reason", "")), limit=180),
                    "evidence_refs": [str(ref) for ref in move.get("evidence_refs", [])[:4]],
                    "additive_scope": additive_scope,
                    "portability_note": portability_note,
                    "risk": evolution_risk(
                        action=action_kind,
                        operating_move=operating_move,
                        target_skill=target_skill,
                    ),
                    "confidence": round(float(move.get("confidence", 0.0) or 0.0), 3),
                    "operating_move": operating_move,
                    "continuity_verdict": str(continuity_proof.get("verdict", "") or ""),
                    "continuity_summary": compact_sentence(
                        str(continuity_proof.get("summary", "") or ""),
                        limit=170,
                    ),
                    "strengthening_delta": continuity_proof.get("strengthening_delta", [])[:4]
                    if isinstance(continuity_proof, dict)
                    else [],
                }
            )

    if isinstance(suppressed_recommendations, list):
        for item in suppressed_recommendations[:2]:
            if not isinstance(item, dict):
                continue
            target_skill = str(
                item.get("skill_id", "") or item.get("proposed_skill_id", "") or "unknown"
            ).strip()
            if not target_skill:
                continue
            suppression_reason = str(item.get("suppression_reason", "") or "insufficient_evidence")
            portability_note = compact_sentence(
                str(
                    item.get("portability_privacy_notes", "")
                    or "Collect more evidence before changing this skill."
                ),
                limit=160,
            )
            actions.append(
                {
                    "action": "defer",
                    "target_skill": target_skill,
                    "priority": "P2",
                    "rationale": compact_sentence(
                        f"{suppression_reason}: {item.get('reason', '')}",
                        limit=180,
                    ),
                    "evidence_refs": [str(ref) for ref in item.get("evidence_refs", [])[:4]],
                    "additive_scope": "Defer until stronger additive scope or policy-compliant evidence is available.",
                    "portability_note": portability_note,
                    "risk": evolution_risk(
                        action="defer",
                        operating_move=str(item.get("operating_move", "hold") or "hold"),
                        target_skill=target_skill,
                    ),
                    "confidence": round(float(item.get("confidence", 0.0) or 0.0), 3),
                    "operating_move": str(item.get("operating_move", "hold") or "hold"),
                    "continuity_verdict": str(
                        (item.get("continuity_proof", {}) or {}).get("verdict", "")
                    ),
                    "continuity_summary": compact_sentence(
                        str((item.get("continuity_proof", {}) or {}).get("summary", "") or ""),
                        limit=170,
                    ),
                    "strengthening_delta": ((item.get("continuity_proof", {}) or {}).get("strengthening_delta", [])[:4]),
                }
            )

    executable_actions = [item for item in actions if item.get("action") != "defer"]
    confidence_values = [
        float(item.get("confidence", 0.0) or 0.0)
        for item in executable_actions
        if float(item.get("confidence", 0.0) or 0.0) > 0.0
    ]
    recommendation_confidence = round(
        sum(confidence_values) / len(confidence_values),
        3,
    ) if confidence_values else 0.0

    pulse_pressure = (
        int(pulse_summary.get("orphan_emitters", 0) or 0)
        + int(pulse_summary.get("orphan_listeners", 0) or 0)
        + int(pulse_summary.get("duplicate_routes", 0) or 0)
        + int(pulse_summary.get("wildcard_overreach_listeners", 0) or 0)
        + int(pulse_summary.get("naming_inconsistencies", 0) or 0)
    )
    workspace_scope = workspace_root.name or "workspace"
    objective_summary = compact_sentence(
        " ".join(
            part
            for part in [
                str(session_intelligence.get("summary", "") or ""),
                f"Evolution actions proposed: {len(executable_actions)}."
                if executable_actions
                else "No high-confidence additive evolution action is currently required.",
            ]
            if part
        ),
        limit=220,
    )
    assessment_evidence_refs = [
        f"session:{session_intelligence.get('source', 'empty')}",
        f"freshness:{freshness_audit.get('status', 'unknown')}",
        f"pulse_pressure:{pulse_pressure}",
        f"workspace_profiles:{int(session_intelligence.get('workspace_profiles_used', 0) or 0)}",
    ]
    if drift.get("version_drift", False) or drift.get("hash_drift", False):
        assessment_evidence_refs.append(
            f"director_drift:{','.join(drift.get('drift_types', ['unknown']))}"
        )

    suppressed_ideas: List[Dict[str, Any]] = []
    if isinstance(suppressed_recommendations, list):
        for item in suppressed_recommendations[:3]:
            if not isinstance(item, dict):
                continue
            target_skill = str(
                item.get("skill_id", "") or item.get("proposed_skill_id", "") or "unknown"
            ).strip()
            if not target_skill:
                continue
            suppressed_ideas.append(
                {
                    "idea": target_skill,
                    "reason": compact_sentence(
                        f"{item.get('suppression_reason', 'suppressed')}: {item.get('reason', '')}",
                        limit=140,
                    ),
                }
            )

    assessment = {
        "schema": "SkillEvolutionAssessmentV1",
        "generated_at": str(metadata.get("generated_at_utc", "") or ""),
        "workspace_scope": workspace_scope,
        "objective_summary": objective_summary or "No evolution objective summary available.",
        "evidence_refs": assessment_evidence_refs,
        "recommendation_confidence": recommendation_confidence,
        "suppressed_ideas": suppressed_ideas,
    }

    steps: List[Dict[str, Any]] = []
    if executable_actions:
        for order, action in enumerate(executable_actions[:5], start=1):
            steps.append(
                {
                    "order": order,
                    "action_id": f"{action.get('action', 'update_existing')}:{action.get('target_skill', 'skill')}",
                    "implementation_note": compact_sentence(
                        str(action.get("additive_scope", "") or action.get("rationale", "")),
                        limit=180,
                    ),
                    "validation_gate": evolution_validation_gate(action),
                }
            )
    else:
        steps.append(
            {
                "order": 1,
                "action_id": "defer:watcher_recheck",
                "implementation_note": "Preserve current skill contracts and wait for stronger evidence before changing the ecosystem.",
                "validation_gate": "Next Watcher run still emits Evolution Actions without regressing existing chat or JSON output.",
            }
        )

    execution_plan = {
        "schema": "SkillExecutionPlanV1",
        "steps": steps,
        "rollback_note": (
            "Rollback by removing only the additive evolution sections or events introduced for this pass; "
            "preserve stable skill IDs, existing Watcher fields, and standalone skill behavior."
        ),
    }

    compact_summary = compact_sentence(
        (
            "Conversation evolution is always on through conversation-skill-evolution-director, "
            + (
                f"with {len(executable_actions)} execution-ready action(s) recommended"
                if executable_actions
                else "with no execution-ready action recommended right now"
            )
            + (
                f" and {len(suppressed_ideas)} suppressed idea(s) held for stronger evidence or policy-safe scope."
                if suppressed_ideas
                else "."
            )
            + (
                f" {capability_recommendations.get('summary', {}).get('continuity_proofs_emitted', 0)} continuity proof(s) preserve skill intelligence."
                if capability_recommendations.get("summary", {}).get("continuity_proofs_emitted", 0)
                else ""
            )
        ),
        limit=220,
    )

    compact_actions = [
        {
            "action": str(item.get("action", "")),
            "target_skill": str(item.get("target_skill", "")),
            "priority": str(item.get("priority", "")),
            "rationale": compact_sentence(str(item.get("rationale", "")), limit=150),
            "risk": str(item.get("risk", "")),
            "confidence": round(float(item.get("confidence", 0.0) or 0.0), 3),
            "portability_note": compact_sentence(str(item.get("portability_note", "")), limit=120),
            "continuity_verdict": str(item.get("continuity_verdict", "") or ""),
            "continuity_summary": compact_sentence(str(item.get("continuity_summary", "") or ""), limit=130),
            "strengthening_delta": [str(part) for part in item.get("strengthening_delta", [])[:3]],
        }
        for item in actions[:5]
    ]

    return {
        "schema": "WatcherEvolutionV1",
        "integration_mode": "always_on",
        "source_skill": "conversation-skill-evolution-director",
        "assessment": assessment,
        "actions": actions,
        "has_execution_ready_actions": bool(executable_actions),
        "execution_plan": execution_plan,
        "compact_summary": compact_summary,
        "chat_actions": compact_actions,
    }


def build_wisdom_entry(
    *,
    workspace_root: Path,
    metadata: Dict[str, Any],
    session_intelligence: Dict[str, Any],
    recommendations: Dict[str, Any],
    pulse_audit: Dict[str, Any],
    trace_refs: List[str],
) -> Dict[str, Any]:
    timestamp = now_utc_iso()
    base = {
        "timestamp_utc": timestamp,
        "workspace_root": str(workspace_root),
        "session_summary": session_intelligence.get("summary", ""),
        "solved_problem_signals": session_intelligence.get("signals", [])[:12],
        "challenges": [
            f"orphan_emitters={pulse_audit.get('summary', {}).get('orphan_emitters', 0)}",
            f"orphan_listeners={pulse_audit.get('summary', {}).get('orphan_listeners', 0)}",
            f"duplicate_routes={pulse_audit.get('summary', {}).get('duplicate_routes', 0)}",
        ],
        "mitigations": [item.get("reason", "") for item in recommendations.get("recommended_updates", [])[:4]],
        "decisions": [
            "current_session_prioritized",
            "cross_workspace_wisdom_blended",
            f"strictness={recommendations.get('strictness', 'high')}",
            "per_skill_intelligence_preserved",
            f"continuity_proofs={recommendations.get('summary', {}).get('continuity_proofs_emitted', 0)}",
        ],
        "recommendations_accepted_or_pending": {
            "updates": len(recommendations.get("recommended_updates", [])),
            "new_skills": len(recommendations.get("recommended_new_skills", [])),
        },
        "pulse_bus_findings": pulse_audit.get("summary", {}),
        "trace_refs": trace_refs,
        "confidence": round(
            as_float(
                (
                    sum(as_float(item.get("confidence", 0.0), 0.0) for item in recommendations.get("recommended_updates", []))
                    + sum(as_float(item.get("confidence", 0.0), 0.0) for item in recommendations.get("recommended_new_skills", []))
                )
                / max(
                    1,
                    len(recommendations.get("recommended_updates", []))
                    + len(recommendations.get("recommended_new_skills", [])),
                ),
                0.7,
            ),
            3,
        ),
        "report_version": metadata.get("report_version", "4.0.0"),
    }
    identity = f"{base['timestamp_utc']}|{base['workspace_root']}|{base['session_summary']}"
    base["entry_id"] = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:16]
    return base


def append_jsonl_entry(path: Path, entry: Dict[str, Any]) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    entry_id = str(entry.get("entry_id", ""))
    if path.exists() and entry_id:
        try:
            with path.open("r", encoding="utf-8", errors="replace") as handle:
                for line in handle:
                    if f'"entry_id": "{entry_id}"' in line:
                        return False
        except Exception:
            pass
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=True))
        handle.write("\n")
    return True


def persist_wisdom(
    *,
    workspace_root: Path,
    enabled: bool,
    stdout_only: bool,
    global_mirror_disabled: bool,
    local_ledger: Path,
    codex_ledger: Path,
    antigravity_ledger: Path,
    wisdom_entry: Dict[str, Any],
) -> Dict[str, Any]:
    status: Dict[str, Any] = {
        "enabled": enabled,
        "entry_id": wisdom_entry.get("entry_id", ""),
        "local_ledger": {"path": str(local_ledger), "status": "skipped"},
        "human_digest": {"surface": "chat", "status": "disabled_in_v3"},
        "global_mirror": {"enabled": not global_mirror_disabled, "targets": []},
    }
    if not enabled:
        status["reason"] = "wisdom_disabled"
        return status
    if stdout_only:
        status["reason"] = "stdout_only_no_writes"
        return status

    clean_entry = sanitize_obj(wisdom_entry, workspace_root)
    if not isinstance(clean_entry, dict):
        status["reason"] = "invalid_wisdom_entry"
        return status

    try:
        written = append_jsonl_entry(local_ledger, clean_entry)
        status["local_ledger"]["status"] = "appended" if written else "duplicate_skipped"
    except Exception as exc:
        status["local_ledger"]["status"] = f"error:{exc}"

    if global_mirror_disabled:
        status["global_mirror"]["reason"] = "disabled_by_flag"
        return status

    mirror_entry = dict(clean_entry)
    mirror_entry["workspace_root"] = "<workspace>"
    mirror_entry["trace_refs"] = ["<sanitized_trace_refs>"]

    for target_name, target_path in [("codex", codex_ledger), ("antigravity", antigravity_ledger)]:
        target = {"target": target_name, "path": str(target_path), "status": "skipped"}
        skill_root = target_path.parent.parent
        if target_name == "antigravity" and not skill_root.exists():
            target["status"] = "missing_root_skipped"
            status["global_mirror"]["targets"].append(target)
            continue
        try:
            written = append_jsonl_entry(target_path, mirror_entry)
            target["status"] = "appended" if written else "duplicate_skipped"
        except Exception as exc:
            target["status"] = f"error:{exc}"
        status["global_mirror"]["targets"].append(target)

    return status


def build_per_skill_wisdom_entries(
    *,
    metadata: Dict[str, Any],
    individual_skill_intelligence: List[Dict[str, Any]],
    capability_recommendations: Dict[str, Any],
) -> List[Dict[str, Any]]:
    recommendation_index: Dict[str, Dict[str, Any]] = {}
    for bucket in ("recommended_updates", "recommended_new_skills"):
        items = capability_recommendations.get(bucket, [])
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            target = recommendation_target_skill(item)
            if target:
                recommendation_index[target] = item

    entries: List[Dict[str, Any]] = []
    timestamp = str(metadata.get("generated_at_utc", "") or now_utc_iso())
    inventory_fingerprint = str(metadata.get("inventory_fingerprint", "") or "")
    for card in individual_skill_intelligence:
        if not isinstance(card, dict):
            continue
        skill_id = str(card.get("skill_id", "") or "").strip()
        if not skill_id:
            continue
        recommendation = recommendation_index.get(skill_id, {})
        continuity = recommendation.get("continuity_proof", {}) if isinstance(recommendation, dict) else {}
        payload = {
            "timestamp_utc": timestamp,
            "skill_id": skill_id,
            "skill_name": str(card.get("name", "") or skill_id),
            "group_id": str(card.get("group_id", "") or ""),
            "intelligence_summary": str(card.get("intelligence_summary", "") or ""),
            "trust_posture": str(card.get("trust_posture", "") or ""),
            "roots": card.get("roots", {}),
            "pulse_contract": card.get("pulse_contract", {}),
            "portability_contract": card.get("portability_contract", {}),
            "knowledge_state": card.get("knowledge_state", {}),
            "wisdom_signals": card.get("wisdom_signals", [])[:3],
            "current_recommendation": {
                "action": recommendation_action(recommendation) if recommendation else "none",
                "reason": compact_sentence(str(recommendation.get("reason", "")), limit=140) if recommendation else "",
                "confidence": round(float(recommendation.get("confidence", 0.0) or 0.0), 3) if recommendation else 0.0,
            },
            "continuity_verdict": str(continuity.get("verdict", "") or "none"),
            "strengthening_delta": continuity.get("strengthening_delta", [])[:4] if isinstance(continuity, dict) else [],
            "report_version": str(metadata.get("report_version", "") or ""),
        }
        identity = f"{timestamp}|{skill_id}|{inventory_fingerprint}"
        payload["entry_id"] = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:20]
        entries.append(payload)
    return entries


def persist_per_skill_wisdom(
    *,
    workspace_root: Path,
    enabled: bool,
    stdout_only: bool,
    global_mirror_disabled: bool,
    local_ledger: Path,
    codex_ledger: Path,
    antigravity_ledger: Path,
    entries: List[Dict[str, Any]],
) -> Dict[str, Any]:
    local_path = local_ledger.parent / "skill_wisdom.jsonl"
    codex_path = codex_ledger.parent / "skill_wisdom.jsonl"
    antigravity_path = antigravity_ledger.parent / "skill_wisdom.jsonl"
    status: Dict[str, Any] = {
        "enabled": enabled,
        "entry_count": len(entries),
        "local_ledger": {"path": str(local_path), "status": "skipped", "appended": 0, "duplicates": 0},
        "global_mirror": {"enabled": not global_mirror_disabled, "targets": []},
    }
    if not enabled:
        status["reason"] = "wisdom_disabled"
        return status
    if stdout_only:
        status["reason"] = "stdout_only_no_writes"
        return status
    if not entries:
        status["reason"] = "no_entries"
        return status

    clean_entries: List[Dict[str, Any]] = []
    for item in entries:
        clean_item = sanitize_obj(item, workspace_root)
        if isinstance(clean_item, dict):
            clean_entries.append(clean_item)

    appended = 0
    duplicates = 0
    for entry in clean_entries:
        try:
            written = append_jsonl_entry(local_path, entry)
        except Exception as exc:
            status["local_ledger"]["status"] = f"error:{exc}"
            break
        if written:
            appended += 1
        else:
            duplicates += 1
    else:
        status["local_ledger"]["status"] = "appended" if appended else "duplicate_skipped"
    status["local_ledger"]["appended"] = appended
    status["local_ledger"]["duplicates"] = duplicates

    if global_mirror_disabled:
        status["global_mirror"]["reason"] = "disabled_by_flag"
        return status

    for target_name, target_path in [("codex", codex_path), ("antigravity", antigravity_path)]:
        target = {"target": target_name, "path": str(target_path), "status": "skipped", "appended": 0, "duplicates": 0}
        skill_root = target_path.parent.parent
        if target_name == "antigravity" and not skill_root.exists():
            target["status"] = "missing_root_skipped"
            status["global_mirror"]["targets"].append(target)
            continue
        try:
            target_appended = 0
            target_duplicates = 0
            for entry in clean_entries:
                written = append_jsonl_entry(target_path, entry)
                if written:
                    target_appended += 1
                else:
                    target_duplicates += 1
            target["status"] = "appended" if target_appended else "duplicate_skipped"
            target["appended"] = target_appended
            target["duplicates"] = target_duplicates
        except Exception as exc:
            target["status"] = f"error:{exc}"
        status["global_mirror"]["targets"].append(target)

    return status


def inventory_appendix_requested(
    session_context: Dict[str, Any],
    session_intelligence: Dict[str, Any],
) -> bool:
    phrases = (
        "show every skill",
        "every skill everywhere",
        "full inventory",
        "full skill intelligence",
        "full skill intelligence report",
        "group all my skills",
        "complete skill index",
    )
    haystacks = [
        str(session_context.get("text", "") or "").lower(),
        str(session_context.get("summary", "") or "").lower(),
        str(session_intelligence.get("summary", "") or "").lower(),
        " ".join(str(item) for item in session_intelligence.get("session_only_signals", [])).lower(),
    ]
    return any(phrase in haystack for haystack in haystacks for phrase in phrases)


def build_watcher_intelligence(
    *,
    metadata: Dict[str, Any],
    freshness_audit: Dict[str, Any],
    counts: Dict[str, Any],
    groups: List[Dict[str, Any]],
    skills: List[Dict[str, Any]],
    individual_skill_intelligence: List[Dict[str, Any]],
    director_final_pass: Dict[str, Any],
    session_context: Dict[str, Any],
    session_intelligence: Dict[str, Any],
    workspace_intelligence: Dict[str, Any],
    recalled_wisdom: List[Dict[str, Any]],
    capability_recommendations: Dict[str, Any],
    pulse_bus_topology_audit: Dict[str, Any],
) -> Dict[str, Any]:
    pulse_summary = pulse_bus_topology_audit.get("summary", {})
    policy = capability_recommendations.get("update_policy", {})
    drift = director_final_pass.get("drift_summary", {})
    warnings = [str(item) for item in freshness_audit.get("warnings", []) if str(item).strip()]
    pulse_pressure = (
        int(pulse_summary.get("orphan_emitters", 0) or 0)
        + int(pulse_summary.get("orphan_listeners", 0) or 0)
        + int(pulse_summary.get("duplicate_routes", 0) or 0)
        + int(pulse_summary.get("wildcard_overreach_listeners", 0) or 0)
        + int(pulse_summary.get("naming_inconsistencies", 0) or 0)
    )
    recommended_updates = capability_recommendations.get("recommended_updates", [])
    recommended_new_skills = capability_recommendations.get("recommended_new_skills", [])
    total_moves = len(recommended_updates) + len(recommended_new_skills)
    blocked_moves = int(policy.get("blocked", 0) or 0)
    continuity_summary = capability_recommendations.get("continuity_summary", {})
    skill_cards = len(individual_skill_intelligence)
    root_parity_summary = build_root_parity_summary(skills)
    publication_parity = root_parity_summary.get("codex_vs_workspace_mirror", {})

    posture = "stable"
    if (
        bool(freshness_audit.get("stale_intelligence_detected", False))
        or pulse_pressure >= 8
        or blocked_moves > 0
    ):
        posture = "intervene"
    elif (
        bool(freshness_audit.get("changed_since_last_run", False))
        or bool(drift.get("version_drift", False))
        or bool(drift.get("hash_drift", False))
        or pulse_pressure > 0
        or total_moves > 0
    ):
        posture = "watch"

    posture_reason = compact_sentence(
        " ".join(
            part
            for part in [
                f"Freshness is {freshness_audit.get('status', 'unknown')}.",
                f"Pulse pressure totals {pulse_pressure}.",
                (
                    f"Director drift types: {', '.join(drift.get('drift_types', []))}."
                    if drift.get("version_drift") or drift.get("hash_drift")
                    else ""
                ),
                f"Active strategic moves: {total_moves}.",
            ]
            if part
        ),
        limit=220,
    )

    severity_rank = {"low": 1, "medium": 2, "high": 3}
    watchlist_candidates: List[Dict[str, Any]] = []
    if warnings or freshness_audit.get("changed_since_last_run", False):
        watchlist_candidates.append(
            {
                "title": "Freshness drift",
                "severity": "high" if freshness_audit.get("stale_intelligence_detected", False) else "medium",
                "reason": compact_sentence(
                    " ".join(warnings)
                    or "Inventory changed since the last watcher run and should be re-evaluated against the latest state.",
                    limit=180,
                ),
                "evidence_refs": [
                    f"freshness:{freshness_audit.get('status', 'unknown')}",
                    f"changed_since_last_run:{freshness_audit.get('changed_since_last_run', False)}",
                ],
            }
        )
    if pulse_pressure > 0:
        watchlist_candidates.append(
            {
                "title": "Pulse topology pressure",
                "severity": "high" if pulse_pressure >= 8 else "medium",
                "reason": compact_sentence(
                    f"Pulse bus findings show {pulse_summary.get('orphan_emitters', 0)} orphan emitters, "
                    f"{pulse_summary.get('orphan_listeners', 0)} orphan listeners, "
                    f"and {pulse_summary.get('duplicate_routes', 0)} duplicate routes.",
                    limit=180,
                ),
                "evidence_refs": [
                    f"pulse:orphan_emitters={pulse_summary.get('orphan_emitters', 0)}",
                    f"pulse:orphan_listeners={pulse_summary.get('orphan_listeners', 0)}",
                    f"pulse:duplicate_routes={pulse_summary.get('duplicate_routes', 0)}",
                ],
            }
        )
    if drift.get("version_drift", False) or drift.get("hash_drift", False):
        watchlist_candidates.append(
            {
                "title": "Cross-root director drift",
                "severity": "medium",
                "reason": compact_sentence(
                    f"The Watcher copies diverge across roots with drift types: {', '.join(drift.get('drift_types', ['unknown']))}.",
                    limit=180,
                ),
                "evidence_refs": [
                    f"director:version_drift={drift.get('version_drift', False)}",
                    f"director:hash_drift={drift.get('hash_drift', False)}",
                ],
            }
        )
    if blocked_moves > 0:
        watchlist_candidates.append(
            {
                "title": "Policy-blocked moves",
                "severity": "medium",
                "reason": compact_sentence(
                    f"{blocked_moves} recommendation candidates were blocked by the additive and portability policy.",
                    limit=180,
                ),
                "evidence_refs": [f"policy:blocked={blocked_moves}"],
            }
        )
    if total_moves > 0:
        watchlist_candidates.append(
            {
                "title": "Upgrade pressure",
                "severity": "low",
                "reason": compact_sentence(
                    f"The watcher sees {len(recommended_updates)} upgrade candidates and {len(recommended_new_skills)} net-new opportunities worth tracking.",
                    limit=180,
                ),
                "evidence_refs": [
                    f"recommendations:updates={len(recommended_updates)}",
                    f"recommendations:new_skills={len(recommended_new_skills)}",
                ],
            }
        )
    if int(publication_parity.get("drift", 0) or 0) > 0:
        watchlist_candidates.append(
            {
                "title": "Publication mirror drift",
                "severity": "medium",
                "reason": compact_sentence(
                    f"Codex and the active workspace mirror diverge on {publication_parity.get('drift', 0)} shared skill copies.",
                    limit=180,
                ),
                "evidence_refs": [
                    f"publication_mirror:shared={publication_parity.get('shared', 0)}",
                    f"publication_mirror:drift={publication_parity.get('drift', 0)}",
                ],
            }
        )

    watchlist = sorted(
        watchlist_candidates,
        key=lambda item: (-severity_rank.get(str(item.get("severity", "low")), 1), str(item.get("title", ""))),
    )[:3]

    groups_by_id = {item.get("group_id", ""): item for item in groups}
    constellation_briefs: List[Dict[str, Any]] = []
    for group in sorted(groups, key=lambda item: (-int(item.get("skill_count", 0) or 0), str(item.get("title", ""))))[:5]:
        members = [item for item in skills if item.get("group_id") == group.get("group_id")]
        standouts = [
            str(member.get("name", ""))
            for member in sorted(
                members,
                key=lambda entry: (
                    0 if entry.get("pulse_bus_active") else 1,
                    str(entry.get("name", "")).lower(),
                ),
            )[:3]
        ]
        gist = compact_sentence(
            " ".join(
                part
                for part in [
                    str(group.get("group_purpose", "")),
                    str(group.get("what_you_get", "")),
                    (
                        f"Standouts: {', '.join(standouts)}."
                        if standouts
                        else ""
                    ),
                ]
                if part
            ),
            limit=200,
        )
        constellation_briefs.append(
            {
                "group_id": group.get("group_id", ""),
                "title": group.get("title", ""),
                "skill_count": int(group.get("skill_count", 0) or 0),
                "gist": gist,
                "standouts": standouts,
            }
        )

    strategic_moves: List[Dict[str, Any]] = []
    for item in recommended_updates:
        strategic_moves.append(
            {
                "action": "update",
                "target": str(item.get("skill_id", "")),
                "operating_move": str(item.get("operating_move", "upgrade") or "upgrade"),
                "confidence": float(item.get("confidence", 0.0) or 0.0),
                "reason": compact_sentence(str(item.get("reason", "")), limit=180),
                "evidence_refs": [str(ref) for ref in item.get("evidence_refs", [])[:3]],
                "portability_note": compact_sentence(str(item.get("portability_privacy_notes", "")), limit=140),
                "continuity_verdict": str((item.get("continuity_proof", {}) or {}).get("verdict", "") or ""),
                "continuity_summary": compact_sentence(
                    str((item.get("continuity_proof", {}) or {}).get("summary", "") or ""),
                    limit=150,
                ),
                "strengthening_delta": ((item.get("continuity_proof", {}) or {}).get("strengthening_delta", [])[:3]),
            }
        )
    for item in recommended_new_skills:
        strategic_moves.append(
            {
                "action": "create",
                "target": str(item.get("proposed_skill_id", "")),
                "operating_move": "create",
                "confidence": float(item.get("confidence", 0.0) or 0.0),
                "reason": compact_sentence(str(item.get("reason", "")), limit=180),
                "evidence_refs": [str(ref) for ref in item.get("evidence_refs", [])[:3]],
                "portability_note": compact_sentence(str(item.get("portability_privacy_notes", "")), limit=140),
                "continuity_verdict": str((item.get("continuity_proof", {}) or {}).get("verdict", "") or ""),
                "continuity_summary": compact_sentence(
                    str((item.get("continuity_proof", {}) or {}).get("summary", "") or ""),
                    limit=150,
                ),
                "strengthening_delta": ((item.get("continuity_proof", {}) or {}).get("strengthening_delta", [])[:3]),
            }
        )

    control_plane_targets = {
        "watcher",
        "orchestration-sentinel-v2",
        "orchestration-sentinel",
        "issue-tracker-guardian",
        "skill-portability-guardian",
        "omniscient-skill-cataloger",
        "proactive-skill-evolution-planner",
    }
    orchestration_targets = {
        "orchestration-sentinel-v2",
        "orchestration-sentinel",
        "issue-tracker-guardian",
    }
    mirrored_governance_targets = {
        "skill_director",
        "skill-portability-guardian",
        "omniscient-skill-cataloger",
        "proactive-skill-evolution-planner",
    }
    move_weight = {"consolidate": 18, "mirror": 16, "upgrade": 12, "create": 8}

    def move_priority(item: Dict[str, Any]) -> Tuple[int, float, str]:
        target = str(item.get("target", "") or "")
        operating_move = str(item.get("operating_move", item.get("action", "update")) or "upgrade")
        confidence = float(item.get("confidence", 0.0) or 0.0)
        score = move_weight.get(operating_move, 10)
        if posture == "intervene" and target in control_plane_targets:
            score += 40
        if pulse_pressure > 0 and target in orchestration_targets:
            score += 24
        if (drift.get("version_drift", False) or drift.get("hash_drift", False)) and target in mirrored_governance_targets:
            score += 20
        if target == "watcher":
            score += 14
        return (score, confidence, target)

    strategic_moves.sort(
        key=lambda item: (
            -move_priority(item)[0],
            -move_priority(item)[1],
            move_priority(item)[2],
        )
    )
    strategic_moves = strategic_moves[:5]

    wisdom_highlights: List[Dict[str, Any]] = []
    for record in recalled_wisdom[:5]:
        summary = compact_sentence(
            str(record.get("summary", "") or record.get("session_summary", "")),
            limit=160,
        )
        if not summary:
            continue
        wisdom_highlights.append(
            {
                "summary": summary,
                "source": compact_sentence(
                    str(record.get("_source_kind", "") or record.get("_source_workspace", "") or "wisdom"),
                    limit=80,
                ),
            }
        )
    if not wisdom_highlights:
        for snapshot in session_intelligence.get("workspace_goal_snapshots", [])[:5]:
            wisdom_highlights.append({"summary": compact_sentence(str(snapshot), limit=160), "source": "workspace_goal"})

    next_actions: List[Dict[str, Any]] = []
    if strategic_moves:
        top_move = strategic_moves[0]
        move_label = str(top_move.get("operating_move", top_move.get("action", "update")) or "update").replace("_", " ").title()
        next_actions.append(
            {
                "action": f"{move_label} `{top_move.get('target', '')}` first.",
                "why": compact_sentence(str(top_move.get("reason", "")), limit=140),
            }
        )
    if pulse_pressure > 0:
        next_actions.append(
            {
                "action": "Review pulse topology findings and assign an owner.",
                "why": compact_sentence(
                    f"Current pulse pressure is {pulse_pressure} and can distort downstream skill routing quality.",
                    limit=140,
                ),
            }
        )
    if freshness_audit.get("changed_since_last_run", False):
        next_actions.append(
            {
                "action": "Refresh watcher state after root changes settle.",
                "why": compact_sentence(
                    "The inventory changed since the last run, so the current posture should be rechecked against the freshest JSON state.",
                    limit=140,
                ),
            }
        )
    if int(publication_parity.get("drift", 0) or 0) > 0:
        next_actions.append(
            {
                "action": "Close publication mirror drift after codex changes.",
                "why": compact_sentence(
                    f"The active workspace mirror is drifted on {publication_parity.get('drift', 0)} shared skills and should be resynchronized before release or export.",
                    limit=140,
                ),
            }
        )
    if not next_actions:
        next_actions.append(
            {
                "action": "Maintain the current watcher cadence.",
                "why": "No urgent ecosystem intervention is visible in the current signal set.",
            }
        )
    next_actions = next_actions[:3]

    inventory_appendix: List[Dict[str, Any]] = []
    if inventory_appendix_requested(session_context, session_intelligence):
        for group_id, group in groups_by_id.items():
            members = [
                {
                    "skill_id": str(skill.get("skill_id", "")),
                    "inventory_role": str(skill.get("inventory_role", "") or "standard"),
                    "name": str(skill.get("name", "")),
                    "summary": compact_sentence(str(skill.get("summary", "")), limit=140),
                    "sources": [str(source) for source in skill.get("sources", [])],
                    "pulse_bus_active": bool(skill.get("pulse_bus_active", False)),
                }
                for skill in sorted(
                    [item for item in skills if item.get("group_id") == group_id],
                    key=lambda item: str(item.get("name", "")).lower(),
                )
            ]
            inventory_appendix.append(
                {
                    "group_id": group_id,
                    "title": str(group.get("title", "")),
                    "skill_count": len(members),
                    "skills": members,
                }
            )

    executive_summary = compact_sentence(
        " ".join(
            part
            for part in [
                f"The Watcher sees {counts.get('unique_skills', 0)} unique skills across {len([g for g in groups if int(g.get('skill_count', 0) or 0) > 0])} active constellations.",
                (
                    f"Inventory roles: {counts.get('standard_inventory_skills', 0)} standard, "
                    f"{counts.get('system_hidden_skills', 0)} hidden system, "
                    f"{counts.get('runtime_bundle_skills', 0)} runtime bundle."
                ),
                f"Ecosystem posture is {posture}.",
                f"Per-skill intelligence is preserved for {skill_cards} skills with {continuity_summary.get('continuity_proofs_emitted', 0)} continuity proof(s).",
                (
                    f"Freshness status is {freshness_audit.get('status', 'unknown')}."
                    if freshness_audit.get("status")
                    else ""
                ),
                (
                    f"The strongest current move count is {total_moves}."
                    if total_moves
                    else "No high-confidence strategic move is currently forcing change."
                ),
            ]
            if part
        ),
        limit=260,
    )

    preservation_summary = {
        "skill_cards_preserved": skill_cards,
        "continuity_proofs_emitted": int(continuity_summary.get("continuity_proofs_emitted", 0) or 0),
        "continuity_passed": int(continuity_summary.get("continuity_passed", 0) or 0),
        "continuity_warned": int(continuity_summary.get("continuity_warned", 0) or 0),
        "continuity_blocked": int(continuity_summary.get("continuity_blocked", 0) or 0),
        "pulse_bus_active_skills": int(counts.get("pulse_bus_active_skills", 0) or 0),
        "skills_without_manifest_count": int(counts.get("skills_without_manifest_count", 0) or 0),
        "skills_without_pulse_participation_count": int(
            counts.get("skills_without_pulse_participation_count", 0) or 0
        ),
        "standard_inventory_skills": int(counts.get("standard_inventory_skills", 0) or 0),
        "system_hidden_skills": int(counts.get("system_hidden_skills", 0) or 0),
        "runtime_bundle_skills": int(counts.get("runtime_bundle_skills", 0) or 0),
        "monotonic_wisdom_mode": "append_only_per_skill_and_global",
    }

    return {
        "schema": "WatcherIntelligenceV1",
        "executive_summary": executive_summary,
        "ecosystem_posture": posture,
        "ecosystem_posture_reason": posture_reason,
        "preservation_summary": preservation_summary,
        "watchlist": watchlist,
        "constellation_briefs": constellation_briefs,
        "strategic_moves": strategic_moves,
        "wisdom_highlights": wisdom_highlights[:5],
        "next_actions": next_actions,
        "inventory_appendix": inventory_appendix or None,
        "root_parity_summary": root_parity_summary,
        "publication_mirror_health": {
            "present": int(publication_parity.get("shared", 0) or 0) > 0,
            "shared": int(publication_parity.get("shared", 0) or 0),
            "drift": int(publication_parity.get("drift", 0) or 0),
            "status": "aligned" if int(publication_parity.get("drift", 0) or 0) == 0 else "drift",
            "examples": publication_parity.get("examples", [])[:6],
        },
    }


def render_chat_intelligence(
    *,
    metadata: Dict[str, Any],
    watcher_intelligence: Dict[str, Any],
) -> str:
    lines: List[str] = []
    lines.append("# The Watcher Intelligence")
    lines.append("")
    lines.append("## Executive Summary")
    lines.append(watcher_intelligence.get("executive_summary", "No executive summary available."))
    lines.append("")

    lines.append("## Ecosystem Posture")
    lines.append(f"- Status: `{watcher_intelligence.get('ecosystem_posture', 'unknown')}`")
    posture_reason = str(watcher_intelligence.get("ecosystem_posture_reason", "") or "")
    if posture_reason:
        lines.append(f"- Reading: {posture_reason}")
    preservation_summary = watcher_intelligence.get("preservation_summary", {}) or {}
    if preservation_summary:
        lines.append(
            f"- Preservation: `{preservation_summary.get('skill_cards_preserved', 0)}` skill cards, "
            f"`{preservation_summary.get('continuity_proofs_emitted', 0)}` continuity proofs, "
            f"`{preservation_summary.get('pulse_bus_active_skills', 0)}` pulse-active skills, "
            f"`{preservation_summary.get('monotonic_wisdom_mode', 'append_only')}`."
        )
        lines.append(
            f"- Inventory roles: `{preservation_summary.get('standard_inventory_skills', 0)}` standard, "
            f"`{preservation_summary.get('system_hidden_skills', 0)}` hidden system, "
            f"`{preservation_summary.get('runtime_bundle_skills', 0)}` runtime bundle."
        )
    publication_mirror = watcher_intelligence.get("publication_mirror_health", {}) or {}
    if publication_mirror.get("present", False):
        lines.append(
            f"- Publication mirror: `{publication_mirror.get('status', 'unknown')}` "
            f"across `{publication_mirror.get('shared', 0)}` shared skills with `{publication_mirror.get('drift', 0)}` drifted."
        )
    lines.append(f"- Generated (UTC): `{metadata.get('generated_at_utc', '')}`")
    lines.append("")

    lines.append("## Watchlist")
    watchlist = watcher_intelligence.get("watchlist", []) or []
    if not watchlist:
        lines.append("- None.")
    else:
        for item in watchlist:
            evidence = ", ".join(str(ref) for ref in item.get("evidence_refs", [])[:3])
            tail = f" Evidence: {evidence}." if evidence else ""
            lines.append(
                f"- `{item.get('severity', 'low')}` {item.get('title', '')}: {item.get('reason', '')}{tail}"
            )
    lines.append("")

    lines.append("## Constellations")
    constellations = watcher_intelligence.get("constellation_briefs", []) or []
    if not constellations:
        lines.append("- None.")
    else:
        for item in constellations:
            standouts = ", ".join(str(name) for name in item.get("standouts", [])[:3])
            tail = f" Standouts: {standouts}." if standouts else ""
            lines.append(
                f"- `{item.get('group_id', '')}` ({item.get('skill_count', 0)} skills): {item.get('gist', '')}{tail}"
            )
    lines.append("")

    lines.append("## Strategic Moves")
    strategic_moves = watcher_intelligence.get("strategic_moves", []) or []
    if not strategic_moves:
        lines.append("- None.")
    else:
        for move in strategic_moves:
            label = str(move.get("operating_move", move.get("action", "update")) or "update").replace("_", " ").title()
            evidence = ", ".join(str(ref) for ref in move.get("evidence_refs", [])[:3])
            portability = str(move.get("portability_note", "") or "")
            lines.append(
                f"- {label} `{move.get('target', '')}` ({move.get('confidence', 0):.3f}): {move.get('reason', '')}"
            )
            if evidence:
                lines.append(f"  Evidence: {evidence}.")
            if portability:
                lines.append(f"  Portability: {portability}.")
            continuity_summary = str(move.get("continuity_summary", "") or "")
            if continuity_summary:
                lines.append(f"  Continuity: {continuity_summary}")
            strengthening = ", ".join(str(item) for item in move.get("strengthening_delta", [])[:3])
            if strengthening:
                lines.append(f"  Strengthens: {strengthening}.")
    lines.append("")

    lines.append("## Evolution Actions")
    evolution_actions = watcher_intelligence.get("evolution_actions", {}) or {}
    evolution_summary = str(evolution_actions.get("summary", "") or "")
    evolution_source = str(evolution_actions.get("source_skill", "") or "")
    integration_mode = str(evolution_actions.get("integration_mode", "") or "")
    has_execution_ready_actions = bool(
        evolution_actions.get("has_execution_ready_actions", False)
    )
    assessment_confidence = evolution_actions.get("assessment_confidence")
    if evolution_source or integration_mode:
        engine = evolution_source
        if integration_mode:
            engine = f"{engine} ({integration_mode})" if engine else integration_mode
        lines.append(f"- Engine: `{engine}`")
    if evolution_summary:
        lines.append(f"- Summary: {evolution_summary}")
    if assessment_confidence is not None:
        try:
            lines.append(f"- Assessment Confidence: `{float(assessment_confidence):.3f}`")
        except Exception:
            pass
    if not has_execution_ready_actions:
        lines.append("- No execution-ready action is recommended right now.")
    compact_actions = evolution_actions.get("actions", []) or []
    if not compact_actions:
        lines.append("- No action recommended.")
    else:
        for item in compact_actions:
            lines.append(
                f"- `{item.get('priority', 'P2')}` `{item.get('action', 'defer')}` `{item.get('target_skill', '')}` "
                f"({item.get('confidence', 0):.3f}, risk={item.get('risk', 'low')}): {item.get('rationale', '')}"
            )
            portability = str(item.get("portability_note", "") or "")
            if portability:
                lines.append(f"  Portability: {portability.rstrip('.')}.")
            continuity_summary = str(item.get("continuity_summary", "") or "")
            if continuity_summary:
                lines.append(f"  Continuity: {continuity_summary}")
            strengthening = ", ".join(str(part) for part in item.get("strengthening_delta", [])[:3])
            if strengthening:
                lines.append(f"  Strengthens: {strengthening}.")
    lines.append("")

    lines.append("## Wisdom")
    wisdom_highlights = watcher_intelligence.get("wisdom_highlights", []) or []
    if not wisdom_highlights:
        lines.append("- No blended wisdom highlights were strong enough to surface.")
    else:
        for item in wisdom_highlights:
            source = str(item.get("source", "") or "")
            prefix = f"`{source}` " if source else ""
            lines.append(f"- {prefix}{item.get('summary', '')}")
    lines.append("")

    lines.append("## Next Actions")
    next_actions = watcher_intelligence.get("next_actions", []) or []
    if not next_actions:
        lines.append("- None.")
    else:
        for item in next_actions:
            lines.append(f"- {item.get('action', '')} {item.get('why', '')}".strip())

    inventory_appendix = watcher_intelligence.get("inventory_appendix")
    if inventory_appendix:
        lines.append("")
        lines.append("## Inventory Appendix")
        for group in inventory_appendix:
            lines.append("")
            lines.append(f"### {group.get('title', '')} (`{group.get('group_id', '')}`)")
            for skill in group.get("skills", []):
                pulse = "pulse" if skill.get("pulse_bus_active") else "quiet"
                sources = ", ".join(str(source) for source in skill.get("sources", []))
                lines.append(
                    f"- `{skill.get('skill_id', '')}` [{pulse}, {skill.get('inventory_role', 'standard')}] ({sources}): {skill.get('summary', '')}"
                )

    return "\n".join(lines)


def resolve_output_path(path_text: str, workspace_root: Path) -> Path:
    path = Path(path_text).expanduser()
    if not path.is_absolute():
        path = (workspace_root / path).resolve()
    return path


def main() -> int:
    args = parse_args()
    apply_artifact_output_mode(args)
    workspace_root = Path(args.workspace_root).expanduser().resolve()
    roots = resolve_roots(args.roots, workspace_root)

    skills, root_stats = collect_inventory(roots, args.include_backups)
    groups = build_group_payload(skills)
    counts = inventory_counts(skills, root_stats)

    candidates = gather_director_candidates(roots, args.include_backups)
    selected = choose_director_candidate(candidates, args.director_mode)
    drift = summarize_drift(candidates) if candidates else {
        "version_drift": False,
        "hash_drift": False,
        "drift_types": ["none"],
        "versions": [],
        "hash_count": 0,
    }
    final_pass = {
        "mode": args.director_mode,
        "selected": selected,
        "candidates": candidates,
        "drift_summary": drift,
        "recommendations": canonical_recommendations(selected, drift),
    }

    session_context = load_session_context(
        mode=args.session_context_mode,
        context_file=args.session_context_file,
        workspace_root=workspace_root,
    )

    workspace_candidates = discover_workspace_candidates(
        scope=args.workspace_discovery_scope,
        workspace_root=workspace_root,
        roots=roots,
        allowlist_file=args.workspace_allowlist_file,
    )
    workspace_intelligence = build_workspace_intelligence(
        workspaces=workspace_candidates,
        workspace_root=workspace_root,
        recency_window_hours=max(1, args.context_time_window_hours),
    )

    wisdom_local_ledger = resolve_output_path(args.wisdom_local_ledger, workspace_root)
    wisdom_global_codex_ledger = resolve_output_path(args.wisdom_global_codex_ledger, workspace_root)
    wisdom_global_antigravity_ledger = resolve_output_path(
        args.wisdom_global_antigravity_ledger, workspace_root
    )

    cross_workspace_wisdom_sources: List[Dict[str, Any]] = []
    recalled_wisdom: List[Dict[str, Any]] = []
    if args.cross_workspace_recall:
        sources, raw_wisdom_records = collect_cross_workspace_wisdom(
            workspace_root=workspace_root,
            workspaces=workspace_candidates,
            roots=roots,
            wisdom_local_ledger=wisdom_local_ledger,
            wisdom_global_codex_ledger=wisdom_global_codex_ledger,
            wisdom_global_antigravity_ledger=wisdom_global_antigravity_ledger,
        )
        cross_workspace_wisdom_sources = sources
        recalled_wisdom = rank_recalled_wisdom(
            records=raw_wisdom_records,
            session_terms=session_context.get("term_set", []),
            workspace_root=workspace_root,
            limit=max(1, args.context_recall_limit),
            recency_window_hours=max(1, args.context_time_window_hours),
        )
    workspace_intelligence = enrich_workspace_intelligence_with_wisdom(
        workspace_intelligence=workspace_intelligence,
        recalled_wisdom=recalled_wisdom,
    )

    session_intelligence = build_session_intelligence(
        session_context=session_context,
        recalled_wisdom=recalled_wisdom,
        workspace_intelligence=workspace_intelligence,
    )
    output_json_path = resolve_output_path(args.output_json, workspace_root)
    previous_snapshot = load_previous_report_snapshot(output_json_path)
    previous_payload = load_previous_report_payload(output_json_path)
    individual_skill_intelligence = build_individual_skill_intelligence(
        skills=skills,
        recalled_wisdom=recalled_wisdom,
        previous_payload=previous_payload,
    )
    pulse_bus_topology_audit = build_pulse_bus_topology_audit(skills)
    capability_recommendations = build_capability_recommendations(
        skills=skills,
        individual_skill_intelligence=individual_skill_intelligence,
        session_intelligence=session_intelligence,
        workspace_intelligence=workspace_intelligence,
        recalled_wisdom=recalled_wisdom,
        pulse_audit=pulse_bus_topology_audit,
        strictness=args.recommendation_strictness,
        enforce_additive_update_policy=bool(args.enforce_additive_update_policy),
        workspace_root=workspace_root,
    )
    individual_skill_intelligence = build_individual_skill_intelligence(
        skills=skills,
        recalled_wisdom=recalled_wisdom,
        previous_payload=previous_payload,
        capability_recommendations=capability_recommendations,
    )
    current_generated_at_utc = now_utc_iso()
    current_inventory_fingerprint = build_inventory_fingerprint(skills)
    freshness_audit = build_freshness_audit(
        now_utc=datetime.now(timezone.utc),
        current_generated_at_utc=current_generated_at_utc,
        current_inventory_fingerprint=current_inventory_fingerprint,
        previous_snapshot=previous_snapshot,
        threshold_hours=max(1, int(args.freshness_threshold_hours)),
    )

    metadata = {
        "report_version": "4.1.0",
        "generated_at_utc": current_generated_at_utc,
        "workspace_root": str(workspace_root),
        "roots_arg": args.roots,
        "include_backups": bool(args.include_backups),
        "artifact_output_mode": args.artifact_output_mode,
        "director_mode": args.director_mode,
        "session_context_mode": args.session_context_mode,
        "recommendation_strictness": args.recommendation_strictness,
        "enforce_additive_update_policy": bool(args.enforce_additive_update_policy),
        "workspace_discovery_scope": args.workspace_discovery_scope,
        "cross_workspace_recall": bool(args.cross_workspace_recall),
        "context_recall_limit": int(args.context_recall_limit),
        "context_time_window_hours": int(args.context_time_window_hours),
        "wisdom_enabled": bool(args.wisdom_enabled),
        "freshness_threshold_hours": int(max(1, args.freshness_threshold_hours)),
        "inventory_fingerprint": current_inventory_fingerprint,
        "ecosystem_contract_path": str(ECOSYSTEM_CONTRACT_PATH),
        "freshness_status": freshness_audit.get("status", "unknown"),
        "changed_since_last_run": bool(freshness_audit.get("changed_since_last_run", False)),
        "stale_intelligence_detected": bool(freshness_audit.get("stale_intelligence_detected", False)),
        "previous_report_generated_at_utc": str(freshness_audit.get("previous_generated_at_utc", "") or ""),
        "previous_report_age_hours": freshness_audit.get("previous_report_age_hours"),
        "output_json_path": str(resolve_output_path(args.output_json, workspace_root)),
        "human_output_mode": "chat",
        "skill_intelligence_preservation_mode": "monotonic_append_only_v1",
    }

    prospective_trace_refs = [
        str(resolve_output_path(args.output_json, workspace_root)),
    ]

    wisdom_entry = build_wisdom_entry(
        workspace_root=workspace_root,
        metadata=metadata,
        session_intelligence=session_intelligence,
        recommendations=capability_recommendations,
        pulse_audit=pulse_bus_topology_audit,
        trace_refs=prospective_trace_refs,
    )
    wisdom_archive = persist_wisdom(
        workspace_root=workspace_root,
        enabled=bool(args.wisdom_enabled),
        stdout_only=bool(args.stdout_only),
        global_mirror_disabled=bool(args.no_wisdom_global_mirror),
        local_ledger=wisdom_local_ledger,
        codex_ledger=wisdom_global_codex_ledger,
        antigravity_ledger=wisdom_global_antigravity_ledger,
        wisdom_entry=wisdom_entry,
    )
    per_skill_wisdom_entries = build_per_skill_wisdom_entries(
        metadata=metadata,
        individual_skill_intelligence=individual_skill_intelligence,
        capability_recommendations=capability_recommendations,
    )
    per_skill_wisdom_archive = persist_per_skill_wisdom(
        workspace_root=workspace_root,
        enabled=bool(args.wisdom_enabled),
        stdout_only=bool(args.stdout_only),
        global_mirror_disabled=bool(args.no_wisdom_global_mirror),
        local_ledger=wisdom_local_ledger,
        codex_ledger=wisdom_global_codex_ledger,
        antigravity_ledger=wisdom_global_antigravity_ledger,
        entries=per_skill_wisdom_entries,
    )

    watcher_intelligence = build_watcher_intelligence(
        metadata=metadata,
        freshness_audit=freshness_audit,
        counts=counts,
        groups=groups,
        skills=skills,
        individual_skill_intelligence=individual_skill_intelligence,
        director_final_pass=final_pass,
        session_context=session_context,
        session_intelligence=session_intelligence,
        workspace_intelligence=workspace_intelligence,
        recalled_wisdom=recalled_wisdom,
        capability_recommendations=capability_recommendations,
        pulse_bus_topology_audit=pulse_bus_topology_audit,
    )
    watcher_evolution = build_watcher_evolution(
        metadata=metadata,
        session_intelligence=session_intelligence,
        workspace_root=workspace_root,
        freshness_audit=freshness_audit,
        director_final_pass=final_pass,
        capability_recommendations=capability_recommendations,
        pulse_bus_topology_audit=pulse_bus_topology_audit,
        watcher_intelligence=watcher_intelligence,
    )
    watcher_intelligence["evolution_actions"] = {
        "summary": watcher_evolution.get("compact_summary", ""),
        "assessment_confidence": watcher_evolution.get("assessment", {}).get(
            "recommendation_confidence", 0.0
        ),
        "source_skill": watcher_evolution.get("source_skill", ""),
        "integration_mode": watcher_evolution.get("integration_mode", ""),
        "has_execution_ready_actions": watcher_evolution.get(
            "has_execution_ready_actions", False
        ),
        "actions": watcher_evolution.get("chat_actions", []),
        "suppressed_ideas": watcher_evolution.get("assessment", {}).get(
            "suppressed_ideas", []
        )[:3],
    }

    inventory_summary = {
        "unique_skills": int(counts.get("unique_skills", 0) or 0),
        "copies": int(counts.get("total_skill_copies", 0) or 0),
        "pulse_active_skills": int(counts.get("pulse_bus_active_skills", 0) or 0),
        "skills_without_manifest_count": int(counts.get("skills_without_manifest_count", 0) or 0),
        "skills_without_pulse_participation_count": int(
            counts.get("skills_without_pulse_participation_count", 0) or 0
        ),
        "roles": {
            "standard": int(counts.get("standard_inventory_skills", 0) or 0),
            "system_hidden": int(counts.get("system_hidden_skills", 0) or 0),
            "runtime_bundle": int(counts.get("runtime_bundle_skills", 0) or 0),
            "backup_snapshot": int(counts.get("backup_snapshot_skills", 0) or 0),
        },
    }
    freshness_summary = dict(freshness_audit)
    freshness_summary["state"] = str(freshness_audit.get("status", "unknown") or "unknown")

    payload = {
        "metadata": metadata,
        "freshness": freshness_summary,
        "freshness_audit": freshness_audit,
        "inventory_summary": inventory_summary,
        "roots": root_stats,
        "inventory_roots": root_stats,
        "inventory_counts": counts,
        "groups": groups,
        "skills": skills,
        "individual_skill_intelligence": individual_skill_intelligence,
        "director_final_pass": final_pass,
        "workspace_intelligence": workspace_intelligence,
        "session_intelligence": session_intelligence,
        "capability_recommendations": capability_recommendations,
        "pulse_bus_topology_audit": pulse_bus_topology_audit,
        "wisdom_archive": wisdom_archive,
        "per_skill_wisdom_archive": per_skill_wisdom_archive,
        "cross_workspace_wisdom_sources": cross_workspace_wisdom_sources,
        "watcher_evolution": watcher_evolution,
        "watcher_intelligence": watcher_intelligence,
    }

    chat_intelligence = render_chat_intelligence(
        metadata=metadata,
        watcher_intelligence=watcher_intelligence,
    )

    print(chat_intelligence)

    if not args.stdout_only:
        json_path = resolve_output_path(args.output_json, workspace_root)
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"JSON written to: {json_path}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
