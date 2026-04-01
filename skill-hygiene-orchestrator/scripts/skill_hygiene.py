#!/usr/bin/env python3
"""
Skill Hygiene Orchestrator

Goals:
- Detect duplicates across Codex global skills, Antigravity global skills, and workspace-local skills.
- Keep the newest (semver first, then newest payload file mtime).
- Back up older copies before replacing or archiving.
- Deduplicate within a root when two directories collide by normalized name (e.g., '_' vs '-').

Default behavior is dry-run (report only).
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional


SEMVER_RE = re.compile(r"v?(\d+)\.(\d+)\.(\d+)(?:[-+].*)?$")

# Ignore runtime artifacts that should not drive version decisions.
IGNORE_FILES = {
    ".DS_Store",
    "catalog_output.md",
}
IGNORE_DIRS = {
    "__pycache__",
    ".pytest_cache",
}


def normalize(s: str) -> str:
    s = s.strip().lower().replace("_", "-")
    s = re.sub(r"[^a-z0-9-]+", "-", s)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return s


def semver_key(v: Optional[str]) -> Optional[tuple[int, int, int]]:
    if not v:
        return None
    m = SEMVER_RE.match(v.strip())
    if not m:
        return None
    return tuple(int(x) for x in m.groups())


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def parse_meta(skill_md: Path) -> tuple[str, Optional[str]]:
    """
    Tolerant parser for SKILL.md frontmatter-like headers.
    Returns (name, version).
    """
    content = read_text(skill_md)

    # YAML frontmatter delimited by --- ... ---
    block = None
    if content.startswith("---\n"):
        end = content.find("\n---", 4)
        if end != -1:
            block = content[4:end]

    meta: dict[str, str] = {}
    if block is not None:
        lines = block.splitlines()
    else:
        # Fallback: parse initial header-style "key: value" lines.
        lines = content.splitlines()[:30]

    for line in lines:
        line = line.strip()
        if not line:
            # Stop at first blank line when not in formal frontmatter.
            if block is None:
                break
            continue
        if line.startswith("#") or ":" not in line:
            continue
        k, v = line.split(":", 1)
        k = k.strip()
        v = v.strip()
        if v.startswith(("\"", "'")) and v.endswith(("\"", "'")) and len(v) >= 2:
            v = v[1:-1]
        meta[k] = v

    name = meta.get("name") or skill_md.parent.name
    version = meta.get("version")
    return name, version


def iter_payload_files(skill_dir: Path) -> Iterable[Path]:
    # Root files.
    for rel in ("SKILL.md", "manifest.json", "manifest.v2.json"):
        p = skill_dir / rel
        if p.is_file():
            yield p

    # Conventional payload dirs.
    for sub in ("scripts", "references", "assets", "agents"):
        d = skill_dir / sub
        if not d.is_dir():
            continue
        for p in d.rglob("*"):
            if p.is_dir():
                continue
            if p.name in IGNORE_FILES:
                continue
            if p.suffix in {".pyc", ".pyo"}:
                continue
            if any(part in IGNORE_DIRS for part in p.parts):
                continue
            yield p


def payload_hash(skill_dir: Path) -> str:
    h = hashlib.sha256()
    for p in sorted(iter_payload_files(skill_dir)):
        rel = p.relative_to(skill_dir)
        h.update(str(rel).encode("utf-8"))
        h.update(b"\0")
        h.update(p.read_bytes())
        h.update(b"\0")
    return h.hexdigest()


def payload_mtime(skill_dir: Path) -> float:
    latest = 0.0
    for p in iter_payload_files(skill_dir):
        try:
            latest = max(latest, p.stat().st_mtime)
        except FileNotFoundError:
            continue
    return latest


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(64 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def files_differ(src: Path, dst: Path) -> bool:
    if not dst.exists() or not dst.is_file():
        return True
    try:
        if src.stat().st_size != dst.stat().st_size:
            return True
    except FileNotFoundError:
        return True
    return file_sha256(src) != file_sha256(dst)


@dataclass(frozen=True)
class SkillInst:
    root: str
    dir_name: str
    path: Path
    name: str
    version: Optional[str]
    semver: Optional[tuple[int, int, int]]
    payload_hash: str
    payload_mtime: float


def scan_root(root: Path, root_id: str) -> list[SkillInst]:
    out: list[SkillInst] = []
    if not root.exists():
        return out
    for d in sorted(root.iterdir(), key=lambda p: p.name.lower()):
        if not d.is_dir():
            continue
        md = d / "SKILL.md"
        if not md.is_file():
            continue
        name, version = parse_meta(md)
        sv = semver_key(version)
        out.append(
            SkillInst(
                root=root_id,
                dir_name=d.name,
                path=d,
                name=name,
                version=version,
                semver=sv,
                payload_hash=payload_hash(d),
                payload_mtime=payload_mtime(d),
            )
        )
    return out


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def backup_and_replace_dir(src_dir: Path, dst_dir: Path, backup_base: Path, *, dry_run: bool) -> None:
    """
    Replace dst_dir with src_dir (full directory copy), backing up dst_dir first.
    """
    backup_target = backup_base / dst_dir.name
    if dry_run:
        print(f"DRY-RUN: backup {dst_dir} -> {backup_target}")
        print(f"DRY-RUN: replace {dst_dir} with copy of {src_dir}")
        return

    ensure_dir(backup_base)
    if backup_target.exists():
        raise RuntimeError(f"Backup target already exists: {backup_target}")

    if dst_dir.exists():
        shutil.move(str(dst_dir), str(backup_target))

    shutil.copytree(
        src_dir,
        dst_dir,
        symlinks=True,
        ignore=shutil.ignore_patterns(*IGNORE_FILES, "*.pyc", "*.pyo"),
    )


def backup_and_sync_payload(src_dir: Path, dst_dir: Path, backup_base: Path, *, dry_run: bool) -> None:
    """
    Targeted sync strategy:
    - only sync managed payload files from src -> dst
    - back up dst files that would be overwritten
    - preserve non-managed files in dst to avoid unintended drift
    """
    src_files = {p.relative_to(src_dir): p for p in iter_payload_files(src_dir)}
    dst_files: dict[Path, Path] = {}
    if dst_dir.exists():
        dst_files = {p.relative_to(dst_dir): p for p in iter_payload_files(dst_dir)}

    to_overwrite: list[Path] = []
    to_create: list[Path] = []
    for rel, src_file in src_files.items():
        dst_file = dst_dir / rel
        if dst_file.exists():
            if files_differ(src_file, dst_file):
                to_overwrite.append(rel)
        else:
            to_create.append(rel)

    if dry_run:
        print(
            f"DRY-RUN: targeted sync {src_dir} -> {dst_dir} "
            f"(overwrite={len(to_overwrite)}, create={len(to_create)}, preserve_non_managed=true)"
        )
        return

    backup_target = backup_base / dst_dir.name / "targeted_payload_backup"
    if to_overwrite:
        ensure_dir(backup_target)
    for rel in to_overwrite:
        src = dst_dir / rel
        dst = backup_target / rel
        ensure_dir(dst.parent)
        shutil.copy2(src, dst)

    for rel, src_file in src_files.items():
        dst_file = dst_dir / rel
        ensure_dir(dst_file.parent)
        shutil.copy2(src_file, dst_file)


def backup_and_archive_dir(dst_dir: Path, backup_base: Path, *, dry_run: bool) -> None:
    backup_target = backup_base / dst_dir.name
    if dry_run:
        print(f"DRY-RUN: archive {dst_dir} -> {backup_target}")
        return
    ensure_dir(backup_base)
    if backup_target.exists():
        raise RuntimeError(f"Backup target already exists: {backup_target}")
    shutil.move(str(dst_dir), str(backup_target))


def pick_winner(insts: list[SkillInst]) -> SkillInst:
    """
    Pick most recent:
    - Highest semver when 2+ instances provide semver
    - Else newest payload mtime
    - Tie-breaker prefers codex_global, then workspace_local, then antigravity_global
    """
    root_rank = {"codex_global": 0, "workspace_local": 1, "antigravity_global": 2}

    semvers = [i.semver for i in insts if i.semver is not None]
    use_semver = len(semvers) >= 2
    max_semver = max(semvers) if use_semver else None

    candidates = insts
    if use_semver and max_semver is not None:
        candidates = [i for i in insts if i.semver == max_semver]

    def key(i: SkillInst):
        # Prefer freshest payload, then root preference as a tiebreak.
        return (i.payload_mtime, -root_rank.get(i.root, 99))

    return max(candidates, key=key)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Audit and de-duplicate/sync skill libraries.")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply changes (default is dry-run report only).",
    )
    parser.add_argument(
        "--roots",
        default="codex,antigravity,local",
        help="Comma-separated roots to operate on: codex,antigravity,local (default: codex,antigravity,local).",
    )
    parser.add_argument(
        "--workspace-root",
        default=os.getcwd(),
        help="Workspace root used to locate .agent/skills for local (default: cwd).",
    )
    parser.add_argument(
        "--sync-strategy",
        choices=["targeted", "replace_dir"],
        default="targeted",
        help=(
            "Sync behavior for divergent cross-root skills. "
            "'targeted' backs up and updates only managed payload files (default). "
            "'replace_dir' uses full-directory replacement (legacy behavior)."
        ),
    )
    args = parser.parse_args(argv)

    selected_roots = {r.strip().lower() for r in args.roots.split(",") if r.strip()}
    dry_run = not args.apply

    codex_root = (Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))) / "skills").expanduser().resolve()
    antigravity_root = (Path.home() / ".gemini" / "antigravity" / "skills").expanduser().resolve()
    workspace_root = Path(args.workspace_root).expanduser().resolve()
    local_root = (workspace_root / ".agent" / "skills").resolve()

    roots: dict[str, Path] = {}
    if "codex" in selected_roots:
        roots["codex_global"] = codex_root
    if "antigravity" in selected_roots:
        roots["antigravity_global"] = antigravity_root
    if "local" in selected_roots and local_root.exists():
        roots["workspace_local"] = local_root

    print("Roots:")
    for k, p in roots.items():
        print(f"- {k}: {p}")
    if "local" in selected_roots and not local_root.exists():
        print(f"- workspace_local: (not found at {local_root})")

    # Inventory.
    all_skills: list[SkillInst] = []
    for rid, root in roots.items():
        all_skills.extend(scan_root(root, rid))

    counts: dict[str, int] = {rid: sum(1 for s in all_skills if s.root == rid) for rid in roots.keys()}
    print("\nCounts:", counts)
    print(f"Sync strategy: {args.sync_strategy}")

    # Deduplicate within each root by normalized name collisions.
    print("\nIn-root duplicates (normalized name collisions):")
    any_in_root_dups = False
    archived_paths: set[Path] = set()

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")

    for rid, root in roots.items():
        by_norm: dict[str, list[SkillInst]] = {}
        for s in (x for x in all_skills if x.root == rid):
            by_norm.setdefault(normalize(s.name), []).append(s)

        collisions = {k: v for k, v in by_norm.items() if len(v) > 1}
        if not collisions:
            continue

        any_in_root_dups = True
        print(f"\n- {rid}: {len(collisions)} collisions")
        backup_base = _backup_base_for_root(rid, root, timestamp) / "archived_duplicates"

        for key, insts in sorted(collisions.items()):
            winner = pick_winner(insts)
            losers = [i for i in insts if i.path != winner.path]
            print(f"  - {key}: keep {winner.dir_name} (root={winner.root}, version={winner.version})")
            for loser in losers:
                print(f"    - archive {loser.dir_name}")
                archived_paths.add(loser.path)
                backup_and_archive_dir(loser.path, backup_base, dry_run=dry_run)

    if not any_in_root_dups:
        print("- none")

    # Exclude archived duplicates from cross-root comparisons (even in dry-run, to avoid
    # planning sync steps for directories we intend to archive).
    effective_skills = [s for s in all_skills if s.path not in archived_paths]

    # Cross-root sync by normalized directory name.
    by_key: dict[str, list[SkillInst]] = {}
    for s in effective_skills:
        by_key.setdefault(normalize(s.dir_name), []).append(s)

    sync_groups = {k: v for k, v in by_key.items() if len({i.root for i in v}) > 1}

    print("\nCross-root divergent skills (payload differs):")
    divergent_groups: list[tuple[str, list[SkillInst]]] = []
    for k, insts in sync_groups.items():
        if len({i.payload_hash for i in insts}) > 1:
            divergent_groups.append((k, insts))

    if not divergent_groups:
        print("- none")
        return 0

    for k, insts in sorted(divergent_groups, key=lambda t: t[0]):
        winner = pick_winner(insts)
        losers = [i for i in insts if i.path != winner.path and i.payload_hash != winner.payload_hash]
        print(f"\n- {k}: keep {winner.root}/{winner.dir_name} (version={winner.version}, mtime={int(winner.payload_mtime)})")
        for loser in losers:
            print(f"  - sync {loser.root}/{loser.dir_name} <- {winner.root}/{winner.dir_name}")
            backup_base = _backup_base_for_root(loser.root, roots[loser.root], timestamp) / "replaced_versions"
            if args.sync_strategy == "replace_dir":
                backup_and_replace_dir(winner.path, loser.path, backup_base, dry_run=dry_run)
            else:
                backup_and_sync_payload(winner.path, loser.path, backup_base, dry_run=dry_run)

    # Non-zero exit helps automation detect that apply is needed.
    return 1 if dry_run else 0


def _backup_base_for_root(root_id: str, root_path: Path, timestamp: str) -> Path:
    if root_id == "codex_global":
        # ~/.codex/skill_backups/...
        return root_path.parent / "skill_backups" / "skill-hygiene-orchestrator" / timestamp / root_id
    if root_id == "antigravity_global":
        # ~/.gemini/antigravity/skill_backups/...
        return root_path.parent / "skill_backups" / "skill-hygiene-orchestrator" / timestamp / root_id
    if root_id == "workspace_local":
        # <repo>/.agent/skills/.backups/...
        return root_path / ".backups" / "skill-hygiene-orchestrator" / timestamp / root_id
    # Fallback: next to root.
    return root_path / ".backups" / "skill-hygiene-orchestrator" / timestamp / root_id


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
