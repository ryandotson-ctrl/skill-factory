#!/usr/bin/env python3
"""Skill portability and privacy hardener.

Audits and applies deterministic portability fixes across skill roots while creating
backups and verifiable reports.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

try:
    import yaml
except Exception:  # pragma: no cover - fallback handled at runtime
    yaml = None


REQUIRED_CONTRACT_FIELDS = ("scope", "portability_tier", "requires_env", "project_profiles")
TRIGGER_FRONTMATTER_FIELDS = ("name", "description")
ECOSYSTEM_CONTRACT_PATH = (
    Path(__file__).resolve().parents[2] / "skill_director" / "references" / "ecosystem_contract_v1.yaml"
)
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
}


@dataclass(frozen=True)
class Rule:
    rule_id: str
    description: str
    regex: str
    replacement: str
    file_globs: Tuple[str, ...]


@dataclass(frozen=True)
class StrictPattern:
    pattern_id: str
    description: str
    regex: str


@dataclass
class RootSpec:
    key: str
    path: Path
    exists: bool


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


def classify_root_role(root_key: str) -> str:
    root_roles = load_ecosystem_contract().get("root_roles", {})
    if isinstance(root_roles, dict):
        mapped = root_roles.get(root_key)
        if mapped:
            return str(mapped)
    return "unknown"


def backup_skip_parts_from_contract() -> set[str]:
    inventory_roles = load_ecosystem_contract().get("inventory_roles", {})
    if not isinstance(inventory_roles, dict):
        return {".skill-backups", "_p0_backups", ".backups"}
    backup_role = inventory_roles.get("backup_snapshot", {})
    if not isinstance(backup_role, dict):
        return {".skill-backups", "_p0_backups", ".backups"}
    prefixes = backup_role.get("path_prefixes", [])
    parts = {".skill-backups", "_p0_backups", ".backups"}
    if isinstance(prefixes, list):
        for prefix in prefixes:
            text = str(prefix).strip().strip("/")
            if text and "/" not in text:
                parts.add(text)
    return parts


def parse_frontmatter(text: str) -> Tuple[Optional[Dict[str, Any]], Optional[str], str]:
    m = re.match(r"^---\n(.*?)\n---\n?", text, re.DOTALL)
    if not m:
        return None, None, text
    if yaml is None:
        return None, None, text
    raw = m.group(1)
    body = text[m.end():]
    try:
        data = yaml.safe_load(raw)
    except Exception:
        return None, raw, body
    if not isinstance(data, dict):
        return None, raw, body
    return data, raw, body


def sidecar_interface_path(skill_md_path: Path) -> Path:
    return skill_md_path.parent / "agents" / "openai.yaml"


def is_sidecar_frontmatter_compatible(
    skill_md_path: Optional[Path],
    meta: Optional[Dict[str, Any]],
) -> bool:
    if skill_md_path is None or skill_md_path.name != "SKILL.md" or meta is None:
        return False
    if not sidecar_interface_path(skill_md_path).exists():
        return False

    observed_keys = set(str(key) for key in meta.keys())
    required_keys = set(TRIGGER_FRONTMATTER_FIELDS)
    return required_keys.issubset(observed_keys) and observed_keys.issubset(required_keys)


def build_compatibility_advisory(
    skill_md_path: Optional[Path],
    meta: Optional[Dict[str, Any]],
    portable_file: str,
) -> Optional[Dict[str, Any]]:
    if not is_sidecar_frontmatter_compatible(skill_md_path, meta):
        return None
    return {
        "file": portable_file,
        "mode": "sidecar_interface_frontmatter",
        "validator_expectation": list(REQUIRED_CONTRACT_FIELDS),
        "observed_keys": [str(key) for key in meta.keys()],
        "sidecar_file": sidecar_interface_path(skill_md_path).relative_to(skill_md_path.parent).as_posix(),
        "recommended_remediation": "Treat as compatible when trigger-only frontmatter is paired with agents/openai.yaml; keep strict leak scanning active.",
    }


def metadata_block(meta: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not isinstance(meta, dict):
        return {}
    metadata = meta.get("metadata")
    return metadata if isinstance(metadata, dict) else {}


def portability_contract_field_present(meta: Optional[Dict[str, Any]], field: str) -> bool:
    if not isinstance(meta, dict):
        return False
    if field in meta:
        return True
    return field in metadata_block(meta)


def assess_contract_missing(
    meta: Optional[Dict[str, Any]],
    skill_md_path: Optional[Path] = None,
) -> List[str]:
    if is_sidecar_frontmatter_compatible(skill_md_path, meta):
        return []
    if not meta:
        return list(REQUIRED_CONTRACT_FIELDS)
    missing: List[str] = []
    for field in REQUIRED_CONTRACT_FIELDS:
        if not portability_contract_field_present(meta, field):
            missing.append(field)
    return missing


def ensure_portability_contract(
    text: str,
    root_key: str,
    skill_md_path: Optional[Path] = None,
) -> Tuple[str, Optional[Dict[str, Any]]]:
    meta, _, body = parse_frontmatter(text)
    if meta is None:
        return text, None
    if is_sidecar_frontmatter_compatible(skill_md_path, meta):
        return text, None

    changed: List[str] = []
    default_scope = "local" if root_key == "local" else "global"
    project_coupled = bool(re.search(r"PFEMacOS|ProjectFreeEnergy|project-free-energy", body, re.IGNORECASE))
    metadata_target = meta.get("metadata")
    use_metadata_target = isinstance(metadata_target, dict)
    contract_target: Dict[str, Any]
    if use_metadata_target:
        contract_target = metadata_target
    else:
        contract_target = meta

    if "scope" not in contract_target:
        contract_target["scope"] = default_scope
        changed.append("scope")
    if "portability_tier" not in contract_target:
        contract_target["portability_tier"] = "strict_zero_leak"
        changed.append("portability_tier")
    if "requires_env" not in contract_target:
        contract_target["requires_env"] = []
        changed.append("requires_env")
    elif not isinstance(contract_target["requires_env"], list):
        contract_target["requires_env"] = [str(contract_target["requires_env"])] if contract_target["requires_env"] else []
        changed.append("requires_env")
    if "project_profiles" not in contract_target:
        contract_target["project_profiles"] = ["PFEMacOS"] if project_coupled else []
        changed.append("project_profiles")
    elif not isinstance(contract_target["project_profiles"], list):
        contract_target["project_profiles"] = [str(contract_target["project_profiles"])] if contract_target["project_profiles"] else []
        changed.append("project_profiles")

    if not changed:
        return text, None

    if use_metadata_target:
        meta["metadata"] = contract_target
    dumped = yaml.safe_dump(meta, sort_keys=False, default_flow_style=False, allow_unicode=False).strip()
    new_text = f"---\n{dumped}\n---\n\n{body.lstrip(chr(10))}"
    evidence = {
        "rule_id": "ensure_portability_contract_v1",
        "description": "Add/normalize portability frontmatter contract fields.",
        "before_matches": len(changed),
        "replacements": len(changed),
        "after_matches": 0,
        "changed_fields": changed,
    }
    return new_text, evidence


def build_scope_map(
    root_specs: List[RootSpec],
    skip_parts: set[str],
    exclude_globs: Tuple[str, ...],
) -> Dict[str, Any]:
    by_skill: Dict[str, Dict[str, Any]] = {}

    for root in root_specs:
        if not root.exists:
            continue
        for skill_md in root.path.rglob("SKILL.md"):
            if should_skip_path(skill_md, skip_parts):
                continue
            if is_excluded_file(root, skill_md, exclude_globs):
                continue
            text = read_text(skill_md) or ""
            relative_skill_path = skill_md.parent.relative_to(root.path).as_posix()
            sid = relative_skill_path
            rec = by_skill.setdefault(
                sid,
                {
                    "skill_id": sid,
                    "leaf_skill_id": skill_md.parent.name,
                    "roots": set(),
                    "root_roles": set(),
                    "project_coupled": False,
                    "inventory_role": classify_inventory_role(relative_skill_path),
                },
            )
            rec["roots"].add(root.key)
            rec["root_roles"].add(classify_root_role(root.key))
            if re.search(r"PFEMacOS|ProjectFreeEnergy|project-free-energy", text, re.IGNORECASE):
                rec["project_coupled"] = True

    entries: List[Dict[str, Any]] = []
    for sid, rec in sorted(by_skill.items()):
        roots = sorted(rec["roots"])
        if roots == ["local"]:
            scope = "local_only"
            canonical = "local"
        elif "local" not in roots:
            scope = "global_only"
            if "codex" in roots:
                canonical = "codex"
            elif "antigravity" in roots:
                canonical = "antigravity"
            else:
                canonical = roots[0]
        else:
            scope = "shared"
            canonical = "local" if rec["project_coupled"] else "codex"
        entries.append(
            {
                "skill_id": sid,
                "leaf_skill_id": rec["leaf_skill_id"],
                "roots": roots,
                "root_roles": sorted(rec["root_roles"]),
                "scope": scope,
                "canonical": canonical,
                "project_coupled": bool(rec["project_coupled"]),
                "inventory_role": rec["inventory_role"],
            }
        )

    return {"generated_at": datetime.now().isoformat(timespec="seconds"), "entries": entries}


def parse_bool(value: str) -> bool:
    v = (value or "").strip().lower()
    if v in {"1", "true", "yes", "y", "on"}:
        return True
    if v in {"0", "false", "no", "n", "off"}:
        return False
    raise argparse.ArgumentTypeError(f"Invalid boolean value: {value}")


def default_codex_skills_root() -> Path:
    codex_home = os.environ.get("CODEX_HOME")
    if codex_home:
        return (Path(codex_home).expanduser() / "skills").resolve()
    return (Path.home() / ".codex" / "skills").resolve()


def resolve_roots(roots_csv: str, workspace_root: Path) -> List[RootSpec]:
    selected = [r.strip().lower() for r in roots_csv.split(",") if r.strip()]
    out: List[RootSpec] = []

    mapping = {
        "codex": default_codex_skills_root(),
        "antigravity": (Path.home() / ".gemini" / "antigravity" / "skills").resolve(),
        "agents": (Path.home() / ".agents" / "skills").resolve(),
        "local": (workspace_root / ".agent" / "skills").resolve(),
    }

    for key in ["codex", "antigravity", "agents", "local"]:
        if key not in selected:
            continue
        p = mapping[key]
        out.append(RootSpec(key=key, path=p, exists=p.exists()))
    return out


def load_rules(rules_path: Path) -> Dict[str, Any]:
    content = rules_path.read_text(encoding="utf-8")
    if yaml is None:
        raise RuntimeError("PyYAML is required to parse portability_rules.yaml")
    data = yaml.safe_load(content)
    if not isinstance(data, dict):
        raise ValueError("Rules file must parse to a mapping")
    return data


def matches_glob(path: Path, globs: Iterable[str]) -> bool:
    name = path.name
    rel = str(path).replace("\\", "/")
    for g in globs:
        if fnmatch.fnmatch(name, g) or fnmatch.fnmatch(rel, g):
            return True
    return False


def is_excluded_file(root: RootSpec, path: Path, exclude_globs: Iterable[str]) -> bool:
    rel = path.relative_to(root.path).as_posix()
    for g in exclude_globs:
        if fnmatch.fnmatch(rel, g) or fnmatch.fnmatch(path.name, g):
            return True
    return False


def is_allowed_file(path: Path, allow_exts: set[str], allow_names: set[str]) -> bool:
    if path.name in allow_names:
        return True
    if path.suffix.lower() in allow_exts:
        return True
    if path.name == "SKILL.md":
        return True
    return False


ARCHIVE_SKIP_SEQUENCES = (("references", "legacy"),)


def is_archived_reference_path(path: Path) -> bool:
    parts = tuple(path.parts)
    for sequence in ARCHIVE_SKIP_SEQUENCES:
        width = len(sequence)
        if width == 0:
            continue
        for index in range(0, max(0, len(parts) - width + 1)):
            if parts[index : index + width] == sequence:
                return True
    return False


def should_skip_path(path: Path, skip_parts: set[str]) -> bool:
    return any(part in skip_parts for part in path.parts) or is_archived_reference_path(path)


def iter_target_files(
    root: RootSpec,
    allow_exts: set[str],
    allow_names: set[str],
    skip_parts: set[str],
    exclude_globs: Tuple[str, ...],
) -> Iterable[Path]:
    if not root.exists:
        return
    for p in root.path.rglob("*"):
        if not p.is_file():
            continue
        if should_skip_path(p, skip_parts):
            continue
        if is_excluded_file(root, p, exclude_globs):
            continue
        if not is_allowed_file(p, allow_exts, allow_names):
            continue
        yield p


def compile_rules(data: Dict[str, Any]) -> Tuple[List[Rule], List[StrictPattern]]:
    rules: List[Rule] = []
    for raw in data.get("autofix_rules", []):
        rules.append(
            Rule(
                rule_id=str(raw["id"]),
                description=str(raw.get("description", "")),
                regex=str(raw["regex"]),
                replacement=str(raw.get("replacement", "")),
                file_globs=tuple(raw.get("file_globs", ["*"])),
            )
        )

    strict_patterns: List[StrictPattern] = []
    for raw in data.get("strict_violation_patterns", []):
        strict_patterns.append(
            StrictPattern(
                pattern_id=str(raw["id"]),
                description=str(raw.get("description", "")),
                regex=str(raw["regex"]),
            )
        )
    return rules, strict_patterns


def backup_base_for_root(root: RootSpec, timestamp: str) -> Path:
    if root.key == "codex":
        # ~/.codex/skill_backups/.../files
        return root.path.parent / "skill_backups" / "skill-portability-guardian" / timestamp / "files"
    if root.key == "antigravity":
        # ~/.gemini/antigravity/skill_backups/.../files
        return root.path.parent / "skill_backups" / "skill-portability-guardian" / timestamp / "files"
    if root.key == "agents":
        return root.path.parent / "skill_backups" / "skill-portability-guardian" / timestamp / "files"
    # local
    return root.path / ".backups" / "skill-portability-guardian" / timestamp / "files"


def read_text(path: Path) -> Optional[str]:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return None


def apply_rules_to_text(text: str, path: Path, rules: List[Rule]) -> Tuple[str, List[Dict[str, Any]]]:
    current = text
    per_rule: List[Dict[str, Any]] = []

    for rule in rules:
        if not matches_glob(path, rule.file_globs):
            continue

        before_count = len(re.findall(rule.regex, current, flags=re.MULTILINE))
        if before_count == 0:
            continue

        updated, replaced = re.subn(rule.regex, rule.replacement, current, flags=re.MULTILINE)
        after_count = len(re.findall(rule.regex, updated, flags=re.MULTILINE))

        per_rule.append(
            {
                "rule_id": rule.rule_id,
                "description": rule.description,
                "before_matches": before_count,
                "replacements": replaced,
                "after_matches": after_count,
            }
        )
        current = updated

    return current, per_rule


def scan_strict(text: str, strict_patterns: List[StrictPattern]) -> List[Dict[str, Any]]:
    hits: List[Dict[str, Any]] = []
    for pat in strict_patterns:
        count = len(re.findall(pat.regex, text, flags=re.MULTILINE))
        if count > 0:
            hits.append(
                {
                    "pattern_id": pat.pattern_id,
                    "description": pat.description,
                    "matches": count,
                }
            )
    return hits


def write_backup_if_needed(root: RootSpec, file_path: Path, backup_base: Path) -> Path:
    rel = file_path.relative_to(root.path)
    backup_path = backup_base / rel
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    if not backup_path.exists():
        shutil.copy2(file_path, backup_path)
    return backup_path


def resolve_report_path(arg_value: Optional[str], default_path: Path) -> Path:
    if not arg_value:
        return default_path
    p = Path(arg_value).expanduser()
    if p.is_absolute():
        return p
    return (Path.cwd() / p).resolve()


def to_portable_rel(path: Path, root_specs: List[RootSpec]) -> str:
    for r in root_specs:
        if r.exists and str(path).startswith(str(r.path)):
            rel = path.relative_to(r.path)
            return f"{r.key}:{rel.as_posix()}"
    return path.as_posix()


def render_markdown_report(report: Dict[str, Any]) -> str:
    lines: List[str] = []
    lines.append("# Skill Portability Guardian Report")
    lines.append("")
    lines.append(f"- Generated: {report['generated_at']}")
    lines.append(f"- Mode: {report['mode']}")
    lines.append(f"- Strict zero leak: {report['strict_zero_leak']}")
    lines.append("")

    lines.append("## Root Status")
    for root in report["roots"]:
        lines.append(f"- {root['key']}: {'present' if root['exists'] else 'missing'}")
    lines.append("")

    summary = report["summary"]
    lines.append("## Summary")
    lines.append(f"- Files scanned: {summary['files_scanned']}")
    lines.append(f"- Files changed: {summary['files_changed']}")
    lines.append(f"- Backups written: {summary['backups_written']}")
    lines.append(f"- Rule hits (pre): {summary['rule_hits_pre']}")
    lines.append(f"- Rule hits (post): {summary['rule_hits_post']}")
    if "rule_hits_proposed_post" in summary:
        lines.append(f"- Rule hits (proposed post): {summary['rule_hits_proposed_post']}")
    lines.append(f"- Strict violations (post): {summary['strict_violations_post']}")
    lines.append(f"- Contract missing fields (pre): {summary['contract_missing_fields_pre']}")
    lines.append(f"- Contract missing fields (post): {summary['contract_missing_fields_post']}")
    lines.append(f"- Contract files updated: {summary['contract_files_updated']}")
    if "contract_files_proposed" in summary:
        lines.append(f"- Contract files proposed: {summary['contract_files_proposed']}")
    lines.append(f"- Compatibility advisories: {summary['compatibility_advisories']}")
    lines.append("")
    lines.append("## Artifacts")
    scope_map_path = str(report.get("scope_map_path", "") or "")
    if scope_map_path:
        lines.append(f"- Scope map: `{scope_map_path}`")
    else:
        lines.append("- Scope map: embedded in snapshot output")
    lines.append("")

    lines.append("## Changed Files")
    if not report["changed_files"]:
        lines.append("- None")
    else:
        for changed in report["changed_files"]:
            lines.append(f"- `{changed['file']}`")
            for ev in changed["evidence"]:
                lines.append(
                    f"  - `{ev['rule_id']}`: before={ev['before_matches']}, replacements={ev['replacements']}, after={ev['after_matches']}"
                )
    lines.append("")

    lines.append("## Compatibility Advisories")
    if not report["compatibility_advisories"]:
        lines.append("- None")
    else:
        for advisory in report["compatibility_advisories"]:
            lines.append(f"- `{advisory['file']}`")
            lines.append(f"  - mode: `{advisory['mode']}`")
            lines.append(f"  - sidecar: `{advisory['sidecar_file']}`")
            lines.append(f"  - observed keys: `{', '.join(advisory['observed_keys'])}`")
            lines.append(f"  - remediation: {advisory['recommended_remediation']}")
    lines.append("")

    lines.append("## Residual Strict Violations")
    if not report["strict_residuals"]:
        lines.append("- None")
    else:
        for res in report["strict_residuals"]:
            lines.append(f"- `{res['file']}`")
            for hit in res["hits"]:
                lines.append(f"  - `{hit['pattern_id']}`: matches={hit['matches']}")
    lines.append("")

    return "\n".join(lines)


def main(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(description="Audit and harden skills for portability/privacy safety.")
    parser.add_argument("--mode", choices=["audit", "apply", "snapshot"], default="apply")
    parser.add_argument("--roots", default="codex,antigravity,agents,local")
    parser.add_argument("--workspace-root", default=os.getcwd())
    parser.add_argument("--strict-zero-leak", type=parse_bool, default=True)
    parser.add_argument("--report-json", default="")
    parser.add_argument("--report-md", default="")
    parser.add_argument(
        "--write-report-artifacts",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Write JSON/Markdown audit artifacts for read-only runs. Apply mode always writes artifacts.",
    )
    parser.add_argument(
        "--rules",
        default=str(Path(__file__).resolve().parent.parent / "references" / "portability_rules.yaml"),
        help="Path to portability rules YAML.",
    )
    args = parser.parse_args(argv)

    workspace_root = Path(args.workspace_root).expanduser().resolve()
    root_specs = resolve_roots(args.roots, workspace_root)

    rules_data = load_rules(Path(args.rules).expanduser().resolve())
    allow_exts = {str(x).strip().lower() for x in rules_data.get("allowlist_extensions", [])}
    allow_names = {str(x).strip() for x in rules_data.get("allowlist_filenames", [])}
    skip_parts = {str(x).strip() for x in rules_data.get("skip_path_parts", [])}
    skip_parts.update(backup_skip_parts_from_contract())
    exclude_globs = tuple(str(x).strip() for x in rules_data.get("exclude_file_globs", []))
    rules, strict_patterns = compile_rules(rules_data)

    now = datetime.now().strftime("%Y%m%d-%H%M%S")
    default_json = Path(__file__).resolve().parent.parent / "reports" / f"portability-report-{now}.json"
    default_md = Path(__file__).resolve().parent.parent / "reports" / f"portability-report-{now}.md"
    report_json_path = resolve_report_path(args.report_json, default_json)
    report_md_path = resolve_report_path(args.report_md, default_md)
    snapshot_mode = args.mode == "snapshot"
    write_report_artifacts = bool(args.mode == "apply" or args.write_report_artifacts or args.report_json or args.report_md)

    files_scanned = 0
    files_changed = 0
    backups_written = 0
    rule_hits_pre = 0
    rule_hits_post = 0
    rule_hits_proposed_post = 0
    strict_violations_post = 0
    contract_missing_fields_pre = 0
    contract_missing_fields_post = 0
    contract_files_updated = 0
    contract_files_proposed = 0
    compatibility_advisories: List[Dict[str, Any]] = []

    changed_files: List[Dict[str, Any]] = []

    backup_cache: set[Path] = set()
    compatibility_seen: set[str] = set()

    for root in root_specs:
        if not root.exists:
            continue

        backup_base = backup_base_for_root(root, now)

        for file_path in iter_target_files(root, allow_exts, allow_names, skip_parts, exclude_globs):
            text = read_text(file_path)
            if text is None:
                continue

            files_scanned += 1

            updated_text, evidence = apply_rules_to_text(text, file_path, rules)
            if file_path.name == "SKILL.md":
                meta, _, _ = parse_frontmatter(text)
                portable_file = to_portable_rel(file_path, root_specs)
                advisory = build_compatibility_advisory(file_path, meta, portable_file)
                if advisory and portable_file not in compatibility_seen:
                    compatibility_seen.add(portable_file)
                    compatibility_advisories.append(advisory)
                contract_missing_fields_pre += len(assess_contract_missing(meta, file_path))
                contract_text, contract_ev = ensure_portability_contract(updated_text, root.key, file_path)
                updated_text = contract_text
                if contract_ev:
                    evidence.append(contract_ev)
                    contract_files_proposed += 1

            rule_evidence = [
                ev for ev in evidence if str(ev.get("rule_id", "")) != "ensure_portability_contract_v1"
            ]
            if rule_evidence:
                rule_hits_pre += sum(int(ev["before_matches"]) for ev in rule_evidence)
                rule_hits_proposed_post += sum(int(ev["after_matches"]) for ev in rule_evidence)

            if args.mode == "apply" and updated_text != text:
                backup_path = write_backup_if_needed(root, file_path, backup_base)
                if backup_path not in backup_cache:
                    backup_cache.add(backup_path)
                    backups_written += 1

                file_path.write_text(updated_text, encoding="utf-8")
                files_changed += 1
                if any(str(ev.get("rule_id", "")) == "ensure_portability_contract_v1" for ev in evidence):
                    contract_files_updated += 1

                changed_files.append(
                    {
                        "file": to_portable_rel(file_path, root_specs),
                        "backup": f"{root.key}-backup:{file_path.relative_to(root.path).as_posix()}",
                        "evidence": evidence,
                    }
                )

    # Post-scan strict violations
    strict_residuals: List[Dict[str, Any]] = []
    for root in root_specs:
        if not root.exists:
            continue
        for file_path in iter_target_files(root, allow_exts, allow_names, skip_parts, exclude_globs):
            text = read_text(file_path)
            if text is None:
                continue
            if file_path.name == "SKILL.md":
                meta, _, _ = parse_frontmatter(text)
                contract_missing_fields_post += len(assess_contract_missing(meta, file_path))
            hits = scan_strict(text, strict_patterns)
            if hits:
                strict_violations_post += sum(int(h["matches"]) for h in hits)
                strict_residuals.append({"file": to_portable_rel(file_path, root_specs), "hits": hits})
            post_text, post_evidence = apply_rules_to_text(text, file_path, rules)
            if post_evidence:
                rule_hits_post += sum(int(ev["before_matches"]) for ev in post_evidence)

    scope_map = build_scope_map(root_specs, skip_parts, exclude_globs)
    scope_map_rel = ""
    if write_report_artifacts and not snapshot_mode:
        scope_map_path = Path(__file__).resolve().parent.parent / "reports" / f"scope-map-{now}.json"
        scope_map_path.parent.mkdir(parents=True, exist_ok=True)
        scope_map_path.write_text(json.dumps(scope_map, indent=2), encoding="utf-8")
        scope_map_rel = f"skill-portability-guardian/{scope_map_path.relative_to(Path(__file__).resolve().parent.parent).as_posix()}"

    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "mode": args.mode,
        "strict_zero_leak": bool(args.strict_zero_leak),
        "roots": [{"key": r.key, "exists": r.exists} for r in root_specs],
        "summary": {
            "files_scanned": files_scanned,
            "files_changed": files_changed,
            "backups_written": backups_written,
            "rule_hits_pre": rule_hits_pre,
            "rule_hits_post": rule_hits_post,
            "rule_hits_proposed_post": rule_hits_proposed_post,
            "strict_violations_post": strict_violations_post,
            "contract_missing_fields_pre": contract_missing_fields_pre,
            "contract_missing_fields_post": contract_missing_fields_post,
            "contract_files_updated": contract_files_updated,
            "contract_files_proposed": contract_files_proposed,
            "compatibility_advisories": len(compatibility_advisories),
        },
        "changed_files": changed_files,
        "compatibility_advisories": compatibility_advisories,
        "strict_residuals": strict_residuals,
        "scope_map_path": scope_map_rel,
        "scope_map": scope_map if snapshot_mode else None,
    }

    if write_report_artifacts and not snapshot_mode:
        report_json_path.parent.mkdir(parents=True, exist_ok=True)
        report_md_path.parent.mkdir(parents=True, exist_ok=True)
        report_json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        report_md_path.write_text(render_markdown_report(report), encoding="utf-8")
        print(f"Report JSON: {report_json_path}")
        print(f"Report MD: {report_md_path}")
    print(json.dumps(report["summary"], indent=2))
    if snapshot_mode:
        print(json.dumps(report, indent=2))

    if args.strict_zero_leak and strict_violations_post > 0:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
