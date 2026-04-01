#!/usr/bin/env python3
"""Deterministic regression gate for skill evolution changes."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple


PORTABILITY_PATTERNS = [
    re.compile(r"/Users/[A-Za-z0-9][A-Za-z0-9._-]{1,}"),
    re.compile(r"/home/[A-Za-z0-9][A-Za-z0-9._-]{1,}"),
    re.compile(r"[A-Za-z]:\\\\Users\\\\[A-Za-z0-9][A-Za-z0-9._-]{1,}"),
]

SKILL_ROOT_PATTERNS = [
    (".agent/skills", "workspace_local"),
    ("global-skills/codex", "workspace_global"),
    (".codex/skills", "codex_global"),
]

TEXT_EXTENSIONS = {".md", ".txt", ".json", ".yaml", ".yml", ".py", ".toml"}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_status_line(line: str) -> Optional[Tuple[str, str]]:
    if len(line) < 4:
        return None
    status = line[:2]
    path_text = line[3:].strip()
    if not path_text:
        return None
    if " -> " in path_text:
        path_text = path_text.split(" -> ", 1)[1].strip()
    return status, path_text


def run_git_status(workspace_root: Path) -> List[Tuple[str, str]]:
    cmd = ["git", "-C", str(workspace_root), "status", "--short", "--untracked-files=all"]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        return []
    out: List[Tuple[str, str]] = []
    for line in proc.stdout.splitlines():
        parsed = parse_status_line(line.rstrip("\n"))
        if parsed is not None:
            out.append(parsed)
    return out


def run_git_numstat(workspace_root: Path, paths: Sequence[str]) -> Tuple[int, int]:
    if not paths:
        return 0, 0
    cmd = ["git", "-C", str(workspace_root), "diff", "--numstat", "--", *paths]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        return 0, 0

    added = 0
    deleted = 0
    for line in proc.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        try:
            a = int(parts[0]) if parts[0].isdigit() else 0
            d = int(parts[1]) if parts[1].isdigit() else 0
        except Exception:
            a, d = 0, 0
        added += a
        deleted += d
    return added, deleted


def normalize_rel_path(path_text: str) -> str:
    return path_text.strip().replace("\\", "/")


def detect_skill_ref(path_text: str) -> Optional[Tuple[str, str, str]]:
    rel = normalize_rel_path(path_text)
    for prefix, root_tag in SKILL_ROOT_PATTERNS:
        marker = f"{prefix}/"
        idx = rel.find(marker)
        if idx == -1:
            continue
        tail = rel[idx + len(marker) :]
        parts = [p for p in tail.split("/") if p]
        if not parts:
            return None
        skill_id = parts[0]
        return root_tag, skill_id, rel
    return None


def load_input_changed_files(path: Path) -> List[Tuple[str, str]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return []
    entries = payload.get("changed_files", [])
    if not isinstance(entries, list):
        return []
    out: List[Tuple[str, str]] = []
    for item in entries:
        if isinstance(item, str):
            out.append(("M ", item))
            continue
        if isinstance(item, dict):
            status = str(item.get("status", "M "))[:2].ljust(2)
            p = str(item.get("path", "")).strip()
            if p:
                out.append((status, p))
    return out


def read_text_if_supported(path: Path) -> str:
    if path.suffix.lower() not in TEXT_EXTENSIONS:
        return ""
    if not path.exists() or not path.is_file():
        return ""
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def check_portability_leaks(workspace_root: Path, changed_skill_paths: Sequence[str]) -> Dict[str, Any]:
    findings: List[str] = []
    for rel in changed_skill_paths:
        abs_path = (workspace_root / rel).resolve()
        text = read_text_if_supported(abs_path)
        if not text:
            continue
        for pattern in PORTABILITY_PATTERNS:
            if pattern.search(text):
                findings.append(rel)
                break
    return {
        "id": "portability_leak_scan",
        "severity": "blocker",
        "passed": len(findings) == 0,
        "summary": "No host-specific user path leaks detected in changed skill files.",
        "details": findings,
    }


def check_manifest_parity(workspace_root: Path, skill_ids: Sequence[str], skill_roots: Dict[str, List[str]]) -> Dict[str, Any]:
    missing: List[str] = []
    invalid: List[str] = []

    for skill_id in skill_ids:
        roots = skill_roots.get(skill_id, [])
        for root_prefix in roots:
            skill_dir = (workspace_root / root_prefix / skill_id).resolve()
            m1 = skill_dir / "manifest.json"
            m2 = skill_dir / "manifest.v2.json"
            if m1.exists() ^ m2.exists():
                missing.append(f"{root_prefix}/{skill_id}")
            for manifest in (m1, m2):
                if not manifest.exists():
                    continue
                try:
                    json.loads(manifest.read_text(encoding="utf-8"))
                except Exception:
                    invalid.append(str(manifest.relative_to(workspace_root)))

    details: List[str] = []
    for item in missing:
        details.append(f"missing_manifest_pair:{item}")
    for item in invalid:
        details.append(f"invalid_json:{item}")

    return {
        "id": "manifest_parity_and_validity",
        "severity": "blocker",
        "passed": len(details) == 0,
        "summary": "Changed skills have coherent manifest pairs and valid JSON.",
        "details": details,
    }


def check_additive_bias(lines_added: int, lines_deleted: int) -> Dict[str, Any]:
    passed = lines_added >= lines_deleted
    return {
        "id": "additive_bias",
        "severity": "warning",
        "passed": passed,
        "summary": "Skill changes are additive-biased by line delta.",
        "details": [f"lines_added={lines_added}", f"lines_deleted={lines_deleted}"],
    }


def build_result(
    workspace_root: Path,
    skill_ids: Sequence[str],
    checks: Sequence[Dict[str, Any]],
    changed_file_count: int,
    lines_added: int,
    lines_deleted: int,
) -> Dict[str, Any]:
    has_blocker = any((not c.get("passed")) and c.get("severity") == "blocker" for c in checks)
    has_warning = any((not c.get("passed")) and c.get("severity") == "warning" for c in checks)

    status = "pass"
    if has_blocker:
        status = "blocker"
    elif has_warning:
        status = "warning"

    recommendation = (
        "Block merge until blocker checks pass."
        if status == "blocker"
        else "Proceed with caution; review warnings before merge."
        if status == "warning"
        else "Gate passed. Skill changes satisfy current regression policy."
    )

    return {
        "generated_at": now_iso(),
        "status": status,
        "workspace_root": str(workspace_root),
        "changed_skill_ids": sorted(skill_ids),
        "checks": list(checks),
        "totals": {
            "changed_files": int(changed_file_count),
            "lines_added": int(lines_added),
            "lines_deleted": int(lines_deleted),
        },
        "recommendation": recommendation,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run skill evolution regression gate.")
    parser.add_argument("--workspace-root", default=".", help="Workspace root (default: cwd).")
    parser.add_argument("--input", help="Optional JSON input with changed_files.")
    parser.add_argument("--output", required=True, help="Output JSON path.")
    args = parser.parse_args()

    workspace_root = Path(args.workspace_root).expanduser().resolve()
    changed_rows = load_input_changed_files(Path(args.input)) if args.input else run_git_status(workspace_root)

    skill_paths: List[str] = []
    skill_ids: set[str] = set()
    skill_roots: Dict[str, set[str]] = {}
    for _status, path_text in changed_rows:
        ref = detect_skill_ref(path_text)
        if ref is None:
            continue
        root_tag, skill_id, rel = ref
        _ = root_tag  # root tag currently used only for diagnostics via root prefix.
        skill_paths.append(rel)
        skill_ids.add(skill_id)

        rel_parts = rel.split("/")
        if len(rel_parts) >= 3:
            root_prefix = "/".join(rel_parts[:2]) if rel_parts[0] != ".codex" else "/".join(rel_parts[:2])
        else:
            root_prefix = "/".join(rel_parts[:2])
        skill_roots.setdefault(skill_id, set()).add(root_prefix)

    changed_skill_paths = sorted(set(skill_paths))
    flattened_skill_roots = {k: sorted(v) for k, v in skill_roots.items()}

    lines_added, lines_deleted = run_git_numstat(workspace_root, changed_skill_paths)
    scope_check = {
        "id": "skill_change_scope",
        "severity": "warning",
        "passed": len(changed_skill_paths) > 0,
        "summary": "At least one changed file belongs to a skill directory.",
        "details": changed_skill_paths[:50],
    }
    portability_check = check_portability_leaks(workspace_root, changed_skill_paths)
    manifest_check = check_manifest_parity(
        workspace_root=workspace_root,
        skill_ids=sorted(skill_ids),
        skill_roots=flattened_skill_roots,
    )
    additive_check = check_additive_bias(lines_added, lines_deleted)

    result = build_result(
        workspace_root=workspace_root,
        skill_ids=sorted(skill_ids),
        checks=[scope_check, portability_check, manifest_check, additive_check],
        changed_file_count=len(changed_skill_paths),
        lines_added=lines_added,
        lines_deleted=lines_deleted,
    )

    output_path = Path(args.output).expanduser()
    if not output_path.is_absolute():
        output_path = (workspace_root / output_path).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
