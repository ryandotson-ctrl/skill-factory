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

TEXT_EXTENSIONS = {".md", ".txt", ".json", ".yaml", ".yml", ".py", ".toml"}
NESTED_SKILL_PREFIXES = {".system", "codex-primary-runtime"}
SKIP_TOP_LEVEL_PREFIXES = {".agent", ".git"}
BACKUP_PREFIXES = {".skill-backups", "_p0_backups", ".backups"}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_status_line(line: str) -> Optional[Tuple[str, str]]:
    if len(line) < 4:
        return None
    status = line[:2]
    path_text = line[3:].strip()
    if not path_text:
        return None
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
            status, path_text = parsed
            if " -> " in path_text and status.strip().startswith("R"):
                old_path, new_path = [item.strip() for item in path_text.split(" -> ", 1)]
                if old_path:
                    out.append((status, old_path))
                if new_path:
                    out.append((status, new_path))
                continue
            out.append(parsed)
    return out


def run_git_numstat(workspace_root: Path, status_rows: Sequence[Tuple[str, str]], paths: Sequence[str]) -> Tuple[int, int]:
    if not paths:
        return 0, 0
    tracked_paths = [
        normalize_rel_path(path_text)
        for status, path_text in status_rows
        if not status.startswith("??")
    ]
    tracked_paths = sorted(set(path for path in tracked_paths if path in set(paths)))

    cmd = ["git", "-C", str(workspace_root), "diff", "--numstat", "HEAD", "--", *tracked_paths]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)

    added = 0
    deleted = 0
    for line in proc.stdout.splitlines() if proc.returncode == 0 else []:
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
    untracked_paths = [
        normalize_rel_path(path_text)
        for status, path_text in status_rows
        if status.startswith("??") and normalize_rel_path(path_text) in set(paths)
    ]
    for rel in sorted(set(untracked_paths)):
        text = read_text_if_supported((workspace_root / rel).resolve())
        if text:
            added += len(text.splitlines())
    return added, deleted


def normalize_rel_path(path_text: str) -> str:
    return path_text.strip().replace("\\", "/")


def candidate_skill_id_from_parts(parts: Sequence[str]) -> Optional[str]:
    if not parts:
        return None
    if any(part in BACKUP_PREFIXES for part in parts):
        return None
    if parts[0] in SKIP_TOP_LEVEL_PREFIXES:
        return None
    if parts[0] in NESTED_SKILL_PREFIXES:
        if len(parts) < 2:
            return None
        return Path(parts[0], parts[1]).as_posix()
    return parts[0]


def detect_skill_ref(
    workspace_root: Path,
    path_text: str,
    *,
    status: str = "M ",
) -> Optional[Tuple[str, str]]:
    rel = normalize_rel_path(path_text)
    rel_path = Path(rel)
    if rel_path.is_absolute():
        try:
            rel_path = rel_path.relative_to(workspace_root)
            rel = rel_path.as_posix()
        except Exception:
            return None

    parts = rel_path.parts
    for depth in range(len(parts), 0, -1):
        candidate = Path(*parts[:depth])
        if (workspace_root / candidate / "SKILL.md").exists():
            return candidate.as_posix(), rel

    candidate_skill_id = candidate_skill_id_from_parts(parts)
    if not candidate_skill_id:
        return None

    candidate_path = workspace_root / candidate_skill_id
    candidate_exists = (candidate_path / "SKILL.md").exists()
    deletion_like = status.startswith("D") or status.strip().startswith("R")
    expected_depth = 2 if parts and parts[0] in NESTED_SKILL_PREFIXES else 1
    touches_skillish_file = rel_path.name in {"SKILL.md", "manifest.json", "manifest.v2.json"}
    touches_skill_subtree = len(parts) > expected_depth

    if candidate_exists or deletion_like or touches_skillish_file or touches_skill_subtree:
        return candidate_skill_id, rel
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


def check_manifest_parity(workspace_root: Path, skill_ids: Sequence[str]) -> Dict[str, Any]:
    missing: List[str] = []
    invalid: List[str] = []

    for skill_id in skill_ids:
        skill_dir = (workspace_root / skill_id).resolve()
        m1 = skill_dir / "manifest.json"
        m2 = skill_dir / "manifest.v2.json"
        if m1.exists() ^ m2.exists():
            missing.append(skill_id)
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
        "stats": {
            "changed_files": int(changed_file_count),
            "lines_added": int(lines_added),
            "lines_deleted": int(lines_deleted),
        },
        "blocker_checks": [dict(check) for check in checks if str(check.get("severity", "")) == "blocker"],
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

    changed_skill_files: List[str] = []
    changed_skill_dirs: set[str] = set()
    for status, path_text in changed_rows:
        ref = detect_skill_ref(workspace_root, path_text, status=status)
        if ref is None:
            continue
        skill_id, rel = ref
        changed_skill_files.append(rel)
        changed_skill_dirs.add(skill_id)

    changed_skill_paths = sorted(set(changed_skill_files))
    changed_skill_ids = sorted(changed_skill_dirs)

    lines_added, lines_deleted = run_git_numstat(workspace_root, changed_rows, changed_skill_paths)
    scope_check = {
        "id": "skill_change_scope",
        "severity": "warning",
        "passed": len(changed_skill_ids) > 0,
        "summary": "At least one changed file belongs to a skill directory.",
        "details": changed_skill_ids[:50],
    }
    portability_check = check_portability_leaks(workspace_root, changed_skill_paths)
    manifest_check = check_manifest_parity(
        workspace_root=workspace_root,
        skill_ids=changed_skill_ids,
    )
    additive_check = check_additive_bias(lines_added, lines_deleted)

    result = build_result(
        workspace_root=workspace_root,
        skill_ids=changed_skill_ids,
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
