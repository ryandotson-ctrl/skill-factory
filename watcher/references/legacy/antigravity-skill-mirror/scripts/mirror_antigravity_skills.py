#!/usr/bin/env python3
"""
Audit and sync Antigravity skills into Codex with canonical-root awareness.

Defaults:
- Antigravity global: ~/.gemini/antigravity/skills
- Codex global:       ~/.codex/skills (or $CODEX_HOME/skills)
- Local (informational): <workspace>/.agent/skills if present
- Workspace mirror (informational): <workspace> when it looks like a published skill mirror
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path


SKIP_PARTS = {
    "_p0_backups",
    ".backups",
    ".skill-backups",
    "__pycache__",
    ".pytest_cache",
    ".agent",
    ".git",
    "wisdom",
    "reports",
    "_generated",
}
SKIP_FILES = {".DS_Store"}


def _default_codex_root() -> Path:
    codex_home = os.environ.get("CODEX_HOME")
    if codex_home:
        return (Path(codex_home).expanduser() / "skills").resolve()
    return (Path.home() / ".codex" / "skills").resolve()


def _looks_like_workspace_mirror_root(workspace_root: Path) -> bool:
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


def _iter_skill_dirs(root: Path) -> list[str]:
    if not root.exists() or not root.is_dir():
        return []
    skills: set[str] = set()
    for skill_md in root.rglob("SKILL.md"):
        if any(part in SKIP_PARTS for part in skill_md.parts):
            continue
        try:
            rel = skill_md.parent.relative_to(root).as_posix()
        except Exception:
            continue
        if rel:
            skills.add(rel)
    return sorted(skills, key=lambda s: s.lower())


def _skill_tree_hash(root: Path, relative_skill_path: str) -> str:
    skill_root = root / relative_skill_path
    digest = hashlib.sha256()
    for file_path in sorted(skill_root.rglob("*")):
        if not file_path.is_file():
            continue
        if any(part in SKIP_PARTS for part in file_path.parts):
            continue
        if file_path.name in SKIP_FILES:
            continue
        rel = file_path.relative_to(skill_root).as_posix()
        digest.update(rel.encode("utf-8"))
        digest.update(b"\0")
        digest.update(file_path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _shared_drift(left_root: Path, right_root: Path, shared: list[str]) -> list[str]:
    drifted: list[str] = []
    for relative_skill_path in shared:
        if _skill_tree_hash(left_root, relative_skill_path) != _skill_tree_hash(right_root, relative_skill_path):
            drifted.append(relative_skill_path)
    return sorted(drifted, key=lambda s: s.lower())


def _print_list(title: str, items: list[str], *, max_items: int | None = None) -> None:
    print(f"\n{title} ({len(items)})")
    if not items:
        return
    show = items if max_items is None else items[:max_items]
    for item in show:
        print(f"- {item}")
    if max_items is not None and len(items) > max_items:
        print(f"- ... ({len(items) - max_items} more)")


def _write_json_if_requested(report: dict[str, object], path_text: str) -> None:
    if not path_text:
        return
    output_path = Path(path_text).expanduser()
    if not output_path.is_absolute():
        output_path = (Path.cwd() / output_path).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


def _render_text_report(report: dict[str, object]) -> None:
    counts = report["counts"]
    print("Antigravity root:", report["antigravity_root"])
    print("Codex root:", report["codex_root"])
    print("Workspace root:", report["workspace_root"])
    print("Local skills root:", report["local_root"])
    print("Workspace mirror root:", report["workspace_mirror_root"])
    print("\nPolicy")
    print("- Codex is treated as canonical authoring root.")
    print("- Antigravity is treated as distribution mirror.")
    print("- Shared drift is advisory unless --overwrite-existing is used explicitly.")
    print("\nCounts")
    for key, value in counts.items():
        print(f"- {key}: {value}")
    _print_list("Copy candidates (antigravity_global - codex_global)", report["copy_candidates"])
    _print_list("Shared codex/antigravity drift (manual review unless overwrite)", report["shared_drift"])
    _print_list("Workspace mirror drift vs codex", report["workspace_mirror_drift"])
    _print_list("Antigravity minus Codex (union)", report["union_missing"], max_items=50)
    _print_list("Codex minus Antigravity (union)", report["union_extra"], max_items=50)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="mirror_antigravity_skills.py",
        description="Audit and sync Antigravity global skills into Codex global skills.",
    )
    parser.add_argument(
        "--antigravity-root",
        default=str(Path.home() / ".gemini" / "antigravity" / "skills"),
        help="Antigravity global skills directory.",
    )
    parser.add_argument(
        "--codex-root",
        default=str(_default_codex_root()),
        help="Codex global skills directory (defaults to ~/.codex/skills or $CODEX_HOME/skills).",
    )
    parser.add_argument(
        "--workspace-root",
        default=os.getcwd(),
        help="Workspace root used to detect local skills at .agent/skills and optional publication mirror.",
    )
    parser.add_argument(
        "--workspace-mirror-root",
        default="",
        help="Optional explicit workspace mirror root. Defaults to auto-detect from --workspace-root.",
    )
    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Report output format.",
    )
    parser.add_argument(
        "--report-json",
        default="",
        help="Optional JSON report path.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Copy Antigravity-only skills into Codex.",
    )
    parser.add_argument(
        "--overwrite-existing",
        action="store_true",
        help="If set with --apply, back up and replace Codex skills with Antigravity copies when shared drift exists.",
    )
    args = parser.parse_args(argv)

    ag_root = Path(args.antigravity_root).expanduser().resolve()
    codex_root = Path(args.codex_root).expanduser().resolve()
    workspace_root = Path(args.workspace_root).expanduser().resolve()
    local_root = workspace_root / ".agent" / "skills"

    if args.workspace_mirror_root:
        workspace_mirror_root = Path(args.workspace_mirror_root).expanduser().resolve()
    elif _looks_like_workspace_mirror_root(workspace_root):
        workspace_mirror_root = workspace_root
    else:
        workspace_mirror_root = None

    ag_global = set(_iter_skill_dirs(ag_root))
    codex_global = set(_iter_skill_dirs(codex_root))
    local = set(_iter_skill_dirs(local_root)) if local_root.exists() else set()
    workspace_mirror = set(_iter_skill_dirs(workspace_mirror_root)) if workspace_mirror_root else set()

    antigravity_union = ag_global | local
    codex_union = codex_global | local

    copy_candidates = sorted(ag_global - codex_global, key=lambda s: s.lower())
    shared_global = sorted(ag_global & codex_global, key=lambda s: s.lower())
    shared_drift = _shared_drift(ag_root, codex_root, shared_global) if shared_global else []
    workspace_shared = sorted(codex_global & workspace_mirror, key=lambda s: s.lower())
    workspace_mirror_drift = (
        _shared_drift(codex_root, workspace_mirror_root, workspace_shared)
        if workspace_mirror_root and workspace_shared
        else []
    )
    union_missing = sorted(antigravity_union - codex_union, key=lambda s: s.lower())
    union_extra = sorted(codex_union - antigravity_union, key=lambda s: s.lower())

    report: dict[str, object] = {
        "policy": {
            "canonical_root": "codex",
            "mirror_root": "antigravity",
            "publication_root": "workspace_mirror" if workspace_mirror_root else "none",
            "shared_drift_handling": "manual_review_unless_overwrite_existing",
        },
        "antigravity_root": str(ag_root),
        "codex_root": str(codex_root),
        "workspace_root": str(workspace_root),
        "local_root": str(local_root) if local_root.exists() else "(not found)",
        "workspace_mirror_root": str(workspace_mirror_root) if workspace_mirror_root else "(not detected)",
        "counts": {
            "antigravity_global": len(ag_global),
            "codex_global": len(codex_global),
            "local": len(local),
            "workspace_mirror": len(workspace_mirror),
            "shared_codex_antigravity": len(shared_global),
            "shared_codex_workspace_mirror": len(workspace_shared),
        },
        "copy_candidates": copy_candidates,
        "shared_drift": shared_drift,
        "workspace_mirror_drift": workspace_mirror_drift,
        "union_missing": union_missing,
        "union_extra": union_extra,
    }

    if args.format == "json":
        print(json.dumps(report, indent=2))
    else:
        _render_text_report(report)
    _write_json_if_requested(report, args.report_json)

    if not args.apply:
        action_needed = bool(copy_candidates or shared_drift or workspace_mirror_drift)
        return 1 if action_needed else 0

    if not ag_root.exists():
        print(f"\nERROR: antigravity root does not exist: {ag_root}")
        return 2

    codex_root.mkdir(parents=True, exist_ok=True)

    backup_base: Path | None = None
    if args.overwrite_existing:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        codex_home = codex_root.parent
        backup_base = codex_home / "skill_backups" / "antigravity-skill-mirror" / timestamp
        backup_base.mkdir(parents=True, exist_ok=True)
        print("\nBackups:", backup_base)

    copied: list[str] = []
    overwritten: list[str] = []
    skipped: list[str] = []

    targets = copy_candidates + (shared_drift if args.overwrite_existing else [])
    for relative_skill_path in sorted(set(targets), key=lambda s: s.lower()):
        src = ag_root / relative_skill_path
        dst = codex_root / relative_skill_path

        if not src.is_dir():
            print(f"\nWARN: missing source skill dir (skipping): {src}")
            continue

        if dst.exists():
            if not args.overwrite_existing:
                skipped.append(relative_skill_path)
                continue

            assert backup_base is not None
            backup_dst = backup_base / relative_skill_path
            backup_dst.parent.mkdir(parents=True, exist_ok=True)
            if backup_dst.exists():
                print(f"\nERROR: backup destination already exists: {backup_dst}")
                return 2

            shutil.move(str(dst), str(backup_dst))
            overwritten.append(relative_skill_path)

        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(
            src,
            dst,
            symlinks=True,
            ignore=shutil.ignore_patterns(".DS_Store"),
        )
        copied.append(relative_skill_path)

    _print_list("Copied", copied)
    _print_list("Overwritten (backed up then replaced)", overwritten)
    _print_list("Skipped (already present)", skipped)

    codex_global_after = set(_iter_skill_dirs(codex_root))
    still_missing = sorted(ag_global - codex_global_after, key=lambda s: s.lower())
    shared_after = sorted(ag_global & codex_global_after, key=lambda s: s.lower())
    still_drift = _shared_drift(ag_root, codex_root, shared_after) if shared_after else []

    _print_list("Still missing after apply", still_missing)
    _print_list("Shared drift after apply", still_drift)

    return 0 if not still_missing and not still_drift else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
