#!/usr/bin/env python3
"""
Mirror Antigravity global skills into Codex global skills.

Defaults:
- Antigravity global: ~/.gemini/antigravity/skills
- Codex global:       ~/.codex/skills (or $CODEX_HOME/skills)
- Local (report only): <workspace>/.agent/skills if present
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path


def _list_skill_dirs(root: Path) -> list[str]:
    """Immediate child directories that contain a SKILL.md."""
    if not root.exists() or not root.is_dir():
        return []
    out: list[str] = []
    for p in root.iterdir():
        if p.is_dir() and (p / "SKILL.md").is_file():
            out.append(p.name)
    return sorted(out, key=lambda s: s.lower())


def _default_codex_root() -> Path:
    codex_home = os.environ.get("CODEX_HOME")
    if codex_home:
        return (Path(codex_home).expanduser() / "skills").resolve()
    return (Path.home() / ".codex" / "skills").resolve()


def _print_list(title: str, items: list[str], *, max_items: int | None = None) -> None:
    print(f"\n{title} ({len(items)})")
    if not items:
        return
    show = items if max_items is None else items[:max_items]
    for s in show:
        print(f"- {s}")
    if max_items is not None and len(items) > max_items:
        print(f"- ... ({len(items) - max_items} more)")


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
        help="Workspace root used to detect local skills at .agent/skills (report-only).",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Copy Antigravity global skills into Codex global skills.",
    )
    parser.add_argument(
        "--overwrite-existing",
        action="store_true",
        help="If set with --apply, backup and replace existing Codex skills to match Antigravity.",
    )
    args = parser.parse_args(argv)

    ag_root = Path(args.antigravity_root).expanduser().resolve()
    codex_root = Path(args.codex_root).expanduser().resolve()
    workspace_root = Path(args.workspace_root).expanduser().resolve()
    local_root = workspace_root / ".agent" / "skills"

    ag_global = set(_list_skill_dirs(ag_root))
    codex_global = set(_list_skill_dirs(codex_root))
    local = set(_list_skill_dirs(local_root)) if local_root.exists() else set()

    antigravity_union = ag_global | local
    codex_union = codex_global | local

    copy_candidates = sorted(ag_global - codex_global, key=lambda s: s.lower())
    union_missing = sorted(antigravity_union - codex_union, key=lambda s: s.lower())
    union_extra = sorted(codex_union - antigravity_union, key=lambda s: s.lower())

    print("Antigravity root:", ag_root)
    print("Codex root:", codex_root)
    print("Workspace root:", workspace_root)
    print("Local skills root:", local_root if local_root.exists() else "(not found)")

    print("\nCounts")
    print("- antigravity_global:", len(ag_global))
    print("- codex_global:", len(codex_global))
    print("- local:", len(local))
    print("- antigravity_union:", len(antigravity_union))
    print("- codex_union:", len(codex_union))

    _print_list("Copy candidates (antigravity_global - codex_global)", copy_candidates)
    _print_list("Antigravity minus Codex (union)", union_missing)
    _print_list("Codex minus Antigravity (union)", union_extra)

    if not args.apply:
        # Non-zero exit helps automation detect "action needed".
        return 1 if union_missing else 0

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

    # In overwrite mode we mirror ALL Antigravity global skills. Otherwise copy only missing.
    targets = sorted(ag_global, key=lambda s: s.lower()) if args.overwrite_existing else copy_candidates

    for skill in targets:
        src = ag_root / skill
        dst = codex_root / skill

        if not src.is_dir():
            print(f"\nWARN: missing source skill dir (skipping): {src}")
            continue

        if dst.exists():
            if not args.overwrite_existing:
                skipped.append(skill)
                continue

            assert backup_base is not None
            backup_dst = backup_base / skill
            if backup_dst.exists():
                # Extremely unlikely unless the same skill name appears twice.
                print(f"\nERROR: backup destination already exists: {backup_dst}")
                return 2

            shutil.move(str(dst), str(backup_dst))
            overwritten.append(skill)

        shutil.copytree(
            src,
            dst,
            symlinks=True,
            ignore=shutil.ignore_patterns(".DS_Store"),
        )
        copied.append(skill)

    _print_list("Copied", copied)
    _print_list("Overwritten (backed up then replaced)", overwritten)
    _print_list("Skipped (already present)", skipped)

    # Recompute union missing after apply.
    codex_global_after = set(_list_skill_dirs(codex_root))
    codex_union_after = codex_global_after | local
    still_missing = sorted(antigravity_union - codex_union_after, key=lambda s: s.lower())
    _print_list("Still missing after apply (union)", still_missing)

    return 0 if not still_missing else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

