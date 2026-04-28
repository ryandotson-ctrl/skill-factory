#!/usr/bin/env python3
"""Dynamic, session-aware storage guardian engine."""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
from collections import deque
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence


DELETE_NOW = "delete_now"
OFFLOAD_MANIFEST = "offload_manifest"
REVIEW_FIRST = "review_first"
PROTECT = "protect"

HOT = "hot"
WARM = "warm"
COLD = "cold"

ACTION_ORDER = {
    DELETE_NOW: 0,
    OFFLOAD_MANIFEST: 1,
    REVIEW_FIRST: 2,
    PROTECT: 3,
}

TEMPERATURE_ORDER = {HOT: 0, WARM: 1, COLD: 2}

SAFE_NOW_DIR_NAMES = {
    "node_modules": "build_artifact",
    ".next": "build_artifact",
    "dist": "build_artifact",
    "build": "build_artifact",
    ".venv": "dev_env",
    "venv": "dev_env",
    "__pycache__": "dev_env",
    ".pytest_cache": "dev_env",
}

APPLE_CONTAINER_PROTECT = {
    ("Library", "Containers", "com.apple.podcasts"): (
        "apple_managed",
        "Apple-managed Podcasts store",
    ),
    ("Library", "Containers", "com.apple.MobileSMS"): (
        "apple_managed",
        "Apple-managed Messages store",
    ),
    ("Library", "Group Containers", "group.com.apple.VoiceMemos.shared"): (
        "apple_managed",
        "Apple-managed Voice Memos store",
    ),
}

REGISTRY_V2_SCHEMA = "StorageGuardianRegistryV2"
PLAN_V2_SCHEMA = "StorageGuardianPlanV2"
APPLY_V2_SCHEMA = "StorageGuardianApplyResultV2"
OFFLOAD_MARKER = "OFFLOADED_TO_EXTERNAL_SSD.md"
DIRECTORY_STUB_INDEX = "index.json"
LEGACY_SESSION_TSV = "session_archives.tsv"
LEGACY_WORKTREE_TSV = "worktree_offloads.tsv"
DEFAULT_EXTERNAL_RESERVE_GB = 25
DEFAULT_EXTERNAL_ROOT = Path("/Volumes/e/ Home/Archive/ssd-guardian-portable")
DEFAULT_REGISTRY_PATH = Path(
    "~/Library/Application Support/ssd-guardian-portable/offload-registry.json"
).expanduser()
PATH_FIELD_NAMES = {
    "cwd",
    "workdir",
    "path",
    "file",
    "source_path",
    "external_root",
    "registry_path",
    "rollout_path",
}
PATCH_PATH_RE = re.compile(r"^\*\*\* (?:Update|Add|Delete) File: (/.+)$", re.MULTILINE)
PATCH_MOVE_RE = re.compile(r"^\*\*\* Move to: (/.+)$", re.MULTILINE)
MARKDOWN_ABS_PATH_RE = re.compile(r"\((/(?:Users|Volumes)/[^)\n]+)\)")
QUOTED_ABS_PATH_RE = re.compile(r"""['"](/(?:Users|Volumes)/[^'"\n]+)['"]""")
SIMPLE_ABS_PATH_RE = re.compile(r"(?<![A-Za-z0-9])(/(?:Users|Volumes)/[^\s'\"`()<>]+)")


@dataclass(frozen=True)
class ThreadRecord:
    id: str
    cwd: Path | None
    rollout_path: Path | None
    updated_at: datetime
    archived: bool
    git_sha: str | None
    git_branch: str | None
    title: str


@dataclass(frozen=True)
class Workspace:
    name: str
    root: Path
    last_signal_at: datetime
    activity: str


@dataclass(frozen=True)
class WorktreeRecord:
    container: Path
    identifier: str
    repo_path: Path | None
    repo_name: str | None
    last_signal_at: datetime
    clean: bool | None
    git_branch: str | None
    git_sha: str | None
    is_symlink: bool
    symlink_target: Path | None


@dataclass(frozen=True)
class CandidateV2:
    path: Path
    display_path: str
    size_bytes: int
    category: str
    source_type: str
    temperature: str
    importance_score: int
    action: str
    workspace: str | None
    thread_ids: list[str]
    last_signal_at: str
    recovery_cost: str
    reason: str
    offload_pressure_score: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "path": self.display_path,
            "size_bytes": self.size_bytes,
            "category": self.category,
            "source_type": self.source_type,
            "temperature": self.temperature,
            "importance_score": self.importance_score,
            "action": self.action,
            "workspace": self.workspace,
            "thread_ids": self.thread_ids,
            "last_signal_at": self.last_signal_at,
            "recovery_cost": self.recovery_cost,
            "reason": self.reason,
        }
        if self.offload_pressure_score:
            payload["offload_pressure_score"] = self.offload_pressure_score
        if self.metadata:
            payload["metadata"] = self.metadata
        return payload


@dataclass(frozen=True)
class WorkspaceProfile:
    name: str
    root_display: str
    activity: str
    last_signal_at: str
    protected_bytes: int
    delete_now_bytes: int
    offload_manifest_bytes: int
    review_first_bytes: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "root": self.root_display,
            "activity": self.activity,
            "last_signal_at": self.last_signal_at,
            "protected_bytes": self.protected_bytes,
            "delete_now_bytes": self.delete_now_bytes,
            "offload_manifest_bytes": self.offload_manifest_bytes,
            "review_first_bytes": self.review_first_bytes,
        }


@dataclass(frozen=True)
class SessionProfile:
    day: str
    size_bytes: int
    temperature: str
    action: str
    thread_ids: list[str]
    offloaded: bool
    last_signal_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "day": self.day,
            "size_bytes": self.size_bytes,
            "temperature": self.temperature,
            "action": self.action,
            "thread_ids": self.thread_ids,
            "offloaded": self.offloaded,
            "last_signal_at": self.last_signal_at,
        }


@dataclass(frozen=True)
class ContextSnapshot:
    cwd: str
    detected_thread_id: str | None
    hot_thread_ids: list[str]
    hot_session_days: list[str]
    hot_workspace_roots: list[str]
    hot_worktree_paths: list[str]
    conversation_workspace_roots: list[str]
    conversation_goal_workspace_roots: list[str]
    conversation_goal_worktree_paths: list[str]
    conversation_paths: list[str]
    keep_models: list[str]
    external_volumes: list[dict[str, Any]]
    time_windows: dict[str, int]

    def to_dict(self) -> dict[str, Any]:
        return {
            "cwd": self.cwd,
            "detected_thread_id": self.detected_thread_id,
            "hot_thread_ids": self.hot_thread_ids,
            "hot_session_days": self.hot_session_days,
            "hot_workspace_roots": self.hot_workspace_roots,
            "hot_worktree_paths": self.hot_worktree_paths,
            "conversation_workspace_roots": self.conversation_workspace_roots,
            "conversation_goal_workspace_roots": self.conversation_goal_workspace_roots,
            "conversation_goal_worktree_paths": self.conversation_goal_worktree_paths,
            "conversation_paths": self.conversation_paths,
            "keep_models": self.keep_models,
            "external_volumes": self.external_volumes,
            "time_windows": self.time_windows,
        }


def safe_stat(path: Path) -> os.stat_result | None:
    try:
        return path.stat()
    except OSError:
        return None


def on_disk_size(path_stat: os.stat_result) -> int:
    blocks = getattr(path_stat, "st_blocks", 0)
    if blocks:
        return int(blocks) * 512
    return int(path_stat.st_size)


def du_measure(path: Path) -> int | None:
    try:
        result = subprocess.run(
            ["du", "-sk", str(path)],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0 or not result.stdout.strip():
        return None
    try:
        kibibytes = int(result.stdout.split()[0])
    except (ValueError, IndexError):
        return None
    return kibibytes * 1024


def human_bytes(size_bytes: int) -> str:
    value = float(size_bytes)
    units = ["B", "KiB", "MiB", "GiB", "TiB"]
    for unit in units:
        if value < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{size_bytes} B"


def isoformat(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_datetime(value: str | int | float | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value), tz=timezone.utc)
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def home_relative(path: Path, home: Path) -> str:
    absolute = path.expanduser()
    try:
        relative = absolute.relative_to(home)
        if not relative.parts:
            return "$HOME"
        return "$HOME/" + relative.as_posix()
    except ValueError:
        resolved = absolute.resolve()
        try:
            relative = resolved.relative_to(home)
            if not relative.parts:
                return "$HOME"
            return "$HOME/" + relative.as_posix()
        except ValueError:
            return resolved.as_posix()


def display_path_is_home_relative(display_path: str) -> bool:
    return display_path == "$HOME" or display_path.startswith("$HOME/")


def is_git_archive_like_path(path: Path) -> bool:
    lower = path.name.lower()
    if lower.endswith(".bundle"):
        try:
            return path.is_file()
        except OSError:
            return False
    if lower in {"git-archives", "git_home_backup"}:
        return True
    return "git" in lower and ("archive" in lower or "backup" in lower or "bundle" in lower)


def relative_parts(path: Path, home: Path) -> list[str]:
    try:
        return list(path.resolve().relative_to(home).parts)
    except ValueError:
        return list(path.parts)


def normalize_goal_text(text: str) -> str:
    normalized = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", text)
    normalized = re.sub(r"(?<=[A-Z])(?=[A-Z][a-z])", " ", normalized)
    normalized = re.sub(r"(?<=[A-Za-z])(?=[0-9])", " ", normalized)
    normalized = re.sub(r"(?<=[0-9])(?=[A-Za-z])", " ", normalized)
    normalized = re.sub(r"[^A-Za-z0-9]+", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip().lower()
    return normalized


def alias_is_specific(alias: str) -> bool:
    tokens = [token for token in alias.split() if token]
    if len(tokens) >= 2:
        return sum(1 for token in tokens if len(token) >= 2) >= 2
    return len(alias) >= 10


def alias_candidates_from_name(name: str) -> set[str]:
    alias = normalize_goal_text(name)
    if not alias or not alias_is_specific(alias):
        return set()
    aliases = {alias}
    if " workspace" in alias:
        aliases.add(alias.replace(" workspace", "").strip())
    if " project" in alias:
        aliases.add(alias.replace(" project", "").strip())
    return {item for item in aliases if item and alias_is_specific(item)}


def default_roots(home: Path) -> list[Path]:
    return [
        home / "Documents",
        home / "Library",
        home / ".cache",
        home / ".npm",
        home / ".codex",
        home / "Pictures",
        home / "Movies",
        home / "Models",
        home / "Desktop",
        home / "Downloads",
    ]


def git_last_commit(repo: Path) -> datetime | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), "log", "-1", "--format=%cI"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    text = result.stdout.strip()
    if result.returncode != 0 or not text:
        return None
    return parse_datetime(text)


def git_branch(repo: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), "branch", "--show-current"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    branch = result.stdout.strip()
    return branch or None


def git_sha(repo: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "HEAD"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    sha = result.stdout.strip()
    return sha or None


def git_is_clean(repo: Path) -> bool | None:
    git_dir = repo / ".git"
    if not git_dir.exists():
        return None
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), "status", "--porcelain"],
            check=False,
            capture_output=True,
            text=True,
            timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    return not result.stdout.strip()


def classify_activity(last_signal: datetime, now: datetime, hot_days: int, warm_days: int) -> str:
    if last_signal >= now - timedelta(days=hot_days):
        return "active"
    if last_signal >= now - timedelta(days=warm_days):
        return "warm"
    return "cold"


def discover_keep_models(workspace: Path | None) -> set[str]:
    import re

    model_id_re = re.compile(r"([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)")
    include_file_re = re.compile(r"\.(ya?ml|json|jsonl|env|toml|ini|txt|md)$", re.IGNORECASE)
    model_hint_re = re.compile(r"(model|draft|hf)", re.IGNORECASE)
    bad_owner_tokens = {
        "Users",
        "users",
        "Documents",
        "configs",
        "artifacts",
        "src",
        "tests",
        "prompts",
        "hardware",
        "software",
    }
    bad_repo_suffixes = (".yaml", ".yml", ".json", ".jsonl", ".py", ".md", ".txt", ".toml", ".ini")

    def plausible(value: str) -> bool:
        if value.count("/") != 1:
            return False
        owner, repo = value.split("/", 1)
        if not owner or not repo:
            return False
        if owner in bad_owner_tokens or len(repo) < 3 or repo.endswith(bad_repo_suffixes):
            return False
        return True

    keep: set[str] = set()
    if workspace is None or not workspace.exists():
        return keep
    roots = [workspace / "configs", workspace / "src", workspace / ".env", workspace / ".env.example"]
    for root in roots:
        if not root.exists():
            continue
        if root.is_file():
            files = [root]
        else:
            files = [
                p
                for p in root.rglob("*")
                if p.is_file() and include_file_re.search(p.name) and ".venv" not in p.as_posix()
            ]
        for file_path in files:
            try:
                text = file_path.read_text(errors="ignore")
            except OSError:
                continue
            for line in text.splitlines():
                if not model_hint_re.search(line):
                    continue
                for match in model_id_re.findall(line):
                    if plausible(match):
                        keep.add(match)
    return keep


def directory_stub_paths(path: Path) -> tuple[Path, Path]:
    return path / OFFLOAD_MARKER, path / DIRECTORY_STUB_INDEX


def sibling_stub_paths(source: Path) -> tuple[Path, Path]:
    return (
        source.parent / f"{source.name}.OFFLOADED.md",
        source.parent / f"{source.name}.offloaded.json",
    )


def is_directory_stub(path: Path) -> bool:
    marker, index = directory_stub_paths(path)
    return path.is_dir() and marker.exists() and index.exists()


def is_session_day_path(path: Path, home: Path) -> bool:
    parts = relative_parts(path, home)
    return len(parts) == 5 and parts[:2] == [".codex", "sessions"]


def parse_session_day(path: Path, home: Path) -> str:
    parts = relative_parts(path, home)
    return "-".join(parts[2:5])


def normalize_absolute_path(raw: str) -> Path | None:
    candidate = raw.strip().strip("`")
    while candidate and candidate[-1] in ",.;:)]}":
        candidate = candidate[:-1]
    if not candidate.startswith("/"):
        return None
    if any(char in candidate for char in "*?[]{}"):
        return None
    try:
        return Path(candidate).expanduser()
    except (OSError, ValueError):
        return None


def extract_paths_from_text(text: str, known_roots: Sequence[Path]) -> set[Path]:
    discovered: set[Path] = set()
    for root in known_roots:
        root_text = str(root)
        if root_text and root_text in text:
            discovered.add(root)
    for pattern in (PATCH_PATH_RE, PATCH_MOVE_RE, MARKDOWN_ABS_PATH_RE, QUOTED_ABS_PATH_RE, SIMPLE_ABS_PATH_RE):
        for match in pattern.findall(text):
            value = match if isinstance(match, str) else match[0]
            candidate = normalize_absolute_path(value)
            if candidate is not None:
                discovered.add(candidate)
    return discovered


def extract_paths_from_jsonish(value: Any, known_roots: Sequence[Path]) -> set[Path]:
    discovered: set[Path] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            if isinstance(item, str) and key in PATH_FIELD_NAMES:
                candidate = normalize_absolute_path(item)
                if candidate is not None:
                    discovered.add(candidate)
            discovered.update(extract_paths_from_jsonish(item, known_roots))
        return discovered
    if isinstance(value, list):
        for item in value:
            discovered.update(extract_paths_from_jsonish(item, known_roots))
        return discovered
    if isinstance(value, str):
        discovered.update(extract_paths_from_text(value, known_roots))
    return discovered


def extract_user_text_fragments(value: Any) -> list[str]:
    fragments: list[str] = []
    if isinstance(value, dict):
        if value.get("type") == "input_text" and isinstance(value.get("text"), str):
            fragments.append(str(value["text"]))
        for item in value.values():
            fragments.extend(extract_user_text_fragments(item))
        return fragments
    if isinstance(value, list):
        for item in value:
            fragments.extend(extract_user_text_fragments(item))
    return fragments


def rollout_semantic_paths(rollout_path: Path, known_roots: Sequence[Path]) -> set[Path]:
    if not rollout_path.exists():
        return set()
    discovered: set[Path] = set()
    try:
        handle = rollout_path.open(errors="ignore")
    except OSError:
        return discovered
    with handle:
        for line in handle:
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            event_type = event.get("type")
            payload = event.get("payload")
            if event_type == "session_meta":
                discovered.update(extract_paths_from_jsonish({"cwd": payload.get("cwd"), "rollout_path": str(rollout_path)}, known_roots))
                continue
            if event_type == "turn_context":
                discovered.update(extract_paths_from_jsonish({"cwd": payload.get("cwd")}, known_roots))
                continue
            if event_type != "response_item" or not isinstance(payload, dict):
                continue
            payload_type = payload.get("type")
            if payload_type == "function_call":
                arguments = payload.get("arguments", "")
                try:
                    parsed_arguments = json.loads(arguments) if isinstance(arguments, str) else arguments
                except json.JSONDecodeError:
                    parsed_arguments = None
                if parsed_arguments is not None:
                    discovered.update(extract_paths_from_jsonish(parsed_arguments, known_roots))
                continue
            if payload_type == "custom_tool_call":
                discovered.update(extract_paths_from_text(str(payload.get("input", "")), known_roots))
                continue
    return discovered


def rollout_user_text(rollout_path: Path) -> list[str]:
    if not rollout_path.exists():
        return []
    fragments: list[str] = []
    try:
        handle = rollout_path.open(errors="ignore")
    except OSError:
        return fragments
    with handle:
        for line in handle:
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get("type") != "response_item":
                continue
            payload = event.get("payload")
            if not isinstance(payload, dict):
                continue
            if payload.get("type") == "message" and payload.get("role") == "user":
                fragments.extend(extract_user_text_fragments(payload.get("content", [])))
    return fragments


def has_live_lock_or_pid(path: Path) -> bool:
    probe_paths: list[Path] = []
    if path.is_file():
        probe_paths = [path]
    elif path.is_dir():
        try:
            probe_paths = list(path.glob("*.pid")) + list(path.glob("*.lock")) + list(path.glob("pid")) + list(path.glob("lock"))
            probe_paths += list(path.glob("*/*.pid")) + list(path.glob("*/*.lock"))
        except OSError:
            return False
    for candidate in probe_paths:
        if candidate.name.endswith(".lock") or candidate.name == "lock":
            return True
        try:
            pid_value = int(candidate.read_text(errors="ignore").strip())
        except (OSError, ValueError):
            continue
        try:
            os.kill(pid_value, 0)
        except OSError:
            continue
        return True
    return False


def remove_path(path: Path) -> None:
    if not path.exists() and not path.is_symlink():
        return
    if path.is_symlink() or path.is_file():
        path.unlink()
        return
    shutil.rmtree(path)


def load_threads(state_db: Path) -> dict[str, ThreadRecord]:
    if not state_db.exists():
        return {}
    threads: dict[str, ThreadRecord] = {}
    try:
        connection = sqlite3.connect(state_db)
    except sqlite3.Error:
        return {}
    with connection:
        cursor = connection.cursor()
        try:
            cursor.execute(
                """
                SELECT id, rollout_path, updated_at, cwd, archived, git_sha, git_branch, title
                FROM threads
                """
            )
        except sqlite3.Error:
            return {}
        for row in cursor.fetchall():
            updated_at = parse_datetime(row[2])
            if updated_at is None:
                continue
            cwd = Path(row[3]).expanduser().resolve() if row[3] else None
            rollout_path = Path(row[1]).expanduser().resolve() if row[1] else None
            threads[str(row[0])] = ThreadRecord(
                id=str(row[0]),
                cwd=cwd,
                rollout_path=rollout_path,
                updated_at=updated_at,
                archived=bool(row[4]),
                git_sha=row[5],
                git_branch=row[6],
                title=row[7] or "",
            )
    connection.close()
    return threads


def load_thread_edges(state_db: Path) -> dict[str, set[str]]:
    if not state_db.exists():
        return {}
    edges: dict[str, set[str]] = {}
    try:
        connection = sqlite3.connect(state_db)
    except sqlite3.Error:
        return {}
    with connection:
        cursor = connection.cursor()
        try:
            cursor.execute("SELECT parent_thread_id, child_thread_id FROM thread_spawn_edges")
        except sqlite3.Error:
            return {}
        for parent_id, child_id in cursor.fetchall():
            if not parent_id or not child_id:
                continue
            edges.setdefault(str(parent_id), set()).add(str(child_id))
            edges.setdefault(str(child_id), set()).add(str(parent_id))
    connection.close()
    return edges


def load_thread_semantic_paths(
    *,
    thread_ids: Iterable[str],
    threads: dict[str, ThreadRecord],
    known_roots: Sequence[Path],
) -> dict[str, set[Path]]:
    semantic_paths: dict[str, set[Path]] = {}
    for thread_id in thread_ids:
        record = threads.get(thread_id)
        if record is None:
            continue
        discovered: set[Path] = set()
        if record.cwd is not None:
            discovered.add(record.cwd)
        if record.rollout_path is not None:
            discovered.add(record.rollout_path.parent)
            discovered.update(rollout_semantic_paths(record.rollout_path, known_roots))
        if record.title:
            discovered.update(extract_paths_from_text(record.title, known_roots))
        semantic_paths[thread_id] = {path.resolve() if path.exists() else path for path in discovered}
    return semantic_paths


def build_goal_alias_maps(
    workspaces: Sequence[Workspace],
    worktrees: Sequence[WorktreeRecord],
) -> tuple[dict[str, set[Path]], dict[str, set[Path]]]:
    workspace_aliases: dict[str, set[Path]] = {}
    for workspace in workspaces:
        for alias in alias_candidates_from_name(workspace.name):
            workspace_aliases.setdefault(alias, set()).add(workspace.root)
    worktree_aliases: dict[str, set[Path]] = {}
    for worktree in worktrees:
        if worktree.repo_path is None:
            continue
        for alias in alias_candidates_from_name(worktree.repo_name or worktree.repo_path.name):
            worktree_aliases.setdefault(alias, set()).add(worktree.repo_path)
    return workspace_aliases, worktree_aliases


def infer_goal_paths_from_text(
    texts: Sequence[str],
    workspace_aliases: dict[str, set[Path]],
    worktree_aliases: dict[str, set[Path]],
) -> tuple[set[Path], set[Path]]:
    workspace_paths: set[Path] = set()
    worktree_paths: set[Path] = set()
    aliases = sorted(set(workspace_aliases) | set(worktree_aliases), key=len, reverse=True)
    for text in texts:
        normalized = f" {normalize_goal_text(text)} "
        if not normalized.strip():
            continue
        for alias in aliases:
            if f" {alias} " not in normalized:
                continue
            workspace_paths.update(workspace_aliases.get(alias, set()))
            worktree_paths.update(worktree_aliases.get(alias, set()))
    return workspace_paths, worktree_paths


def load_thread_goal_references(
    *,
    thread_ids: Iterable[str],
    threads: dict[str, ThreadRecord],
    workspaces: Sequence[Workspace],
    worktrees: Sequence[WorktreeRecord],
) -> tuple[dict[str, set[Path]], dict[str, set[Path]]]:
    workspace_aliases, worktree_aliases = build_goal_alias_maps(workspaces, worktrees)
    thread_workspace_goals: dict[str, set[Path]] = {}
    thread_worktree_goals: dict[str, set[Path]] = {}
    for thread_id in thread_ids:
        record = threads.get(thread_id)
        if record is None:
            continue
        texts: list[str] = []
        if record.title:
            texts.append(record.title)
        if record.rollout_path is not None:
            texts.extend(rollout_user_text(record.rollout_path))
        workspace_paths, worktree_paths = infer_goal_paths_from_text(texts, workspace_aliases, worktree_aliases)
        thread_workspace_goals[thread_id] = {path.resolve() if path.exists() else path for path in workspace_paths}
        thread_worktree_goals[thread_id] = {path.resolve() if path.exists() else path for path in worktree_paths}
    return thread_workspace_goals, thread_worktree_goals


def discover_workspaces(home: Path, now: datetime, hot_days: int, warm_days: int) -> list[Workspace]:
    documents_root = home / "Documents"
    if not documents_root.exists():
        return []
    discovered: list[Path] = []
    for current_root, dirnames, _ in os.walk(documents_root, topdown=True, followlinks=False):
        current = Path(current_root)
        depth = len(current.relative_to(documents_root).parts)
        if depth > 3:
            dirnames[:] = []
            continue
        if ".git" in dirnames:
            discovered.append(current)
            dirnames[:] = []
            continue
    discovered.sort(key=lambda path: len(path.parts))
    top_level: list[Path] = []
    for repo in discovered:
        if any(is_relative_to(repo, existing) for existing in top_level):
            continue
        top_level.append(repo)
    workspaces: list[Workspace] = []
    for repo in top_level:
        git_signal = git_last_commit(repo)
        repo_signal = datetime.fromtimestamp(repo.stat().st_mtime, tz=timezone.utc)
        last_signal = max(git_signal, repo_signal) if git_signal else repo_signal
        workspaces.append(
            Workspace(
                name=repo.name,
                root=repo,
                last_signal_at=last_signal,
                activity=classify_activity(last_signal, now, hot_days, warm_days),
            )
        )
    return sorted(workspaces, key=lambda item: item.root.as_posix().lower())


def discover_worktrees(home: Path, now: datetime, hot_days: int, warm_days: int) -> list[WorktreeRecord]:
    root = home / ".codex" / "worktrees"
    if not root.exists():
        return []
    worktrees: list[WorktreeRecord] = []
    for container in sorted(root.iterdir()):
        if not container.is_dir():
            continue
        try:
            children = [child for child in container.iterdir() if child.name != ".DS_Store"]
        except OSError:
            children = []
        repo_candidates = [child for child in children if child.is_dir() or child.is_symlink()]
        repo_path = repo_candidates[0] if len(repo_candidates) == 1 else None
        repo_name = repo_path.name if repo_path else None
        symlink_target: Path | None = None
        is_symlink = bool(repo_path and repo_path.is_symlink())
        if repo_path and repo_path.is_symlink():
            try:
                symlink_target = Path(os.readlink(repo_path))
                if not symlink_target.is_absolute():
                    symlink_target = (repo_path.parent / symlink_target).resolve()
            except OSError:
                symlink_target = None
        signal_sources: list[datetime] = [
            datetime.fromtimestamp(container.stat().st_mtime, tz=timezone.utc)
        ]
        clean: bool | None = None
        branch: str | None = None
        sha: str | None = None
        if repo_path and repo_path.exists():
            signal_sources.append(datetime.fromtimestamp(repo_path.stat().st_mtime, tz=timezone.utc))
            git_signal = git_last_commit(repo_path)
            if git_signal is not None:
                signal_sources.append(git_signal)
            clean = git_is_clean(repo_path)
            branch = git_branch(repo_path)
            sha = git_sha(repo_path)
        worktrees.append(
            WorktreeRecord(
                container=container,
                identifier=container.name,
                repo_path=repo_path,
                repo_name=repo_name,
                last_signal_at=max(signal_sources),
                clean=clean,
                git_branch=branch,
                git_sha=sha,
                is_symlink=is_symlink,
                symlink_target=symlink_target,
            )
        )
    return worktrees


def choose_active_thread(
    threads: dict[str, ThreadRecord],
    cwd: Path,
    thread_id: str | None,
) -> str | None:
    if thread_id and thread_id in threads:
        return thread_id
    ranked: list[tuple[int, datetime, str]] = []
    for record in threads.values():
        if record.archived or record.cwd is None:
            continue
        score = 0
        if record.cwd == cwd:
            score = 3
        elif is_relative_to(cwd, record.cwd):
            score = 2
        elif is_relative_to(record.cwd, cwd):
            score = 1
        if score:
            ranked.append((score, record.updated_at, record.id))
    if not ranked:
        return None
    ranked.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return ranked[0][2]


def thread_family_ids(
    active_thread_id: str | None,
    edges: dict[str, set[str]],
    threads: dict[str, ThreadRecord],
    now: datetime,
    warm_days: int,
) -> set[str]:
    if active_thread_id is None:
        return set()
    family: set[str] = set()
    queue: deque[str] = deque([active_thread_id])
    warm_cutoff = now - timedelta(days=warm_days)
    while queue:
        thread_id = queue.popleft()
        if thread_id in family:
            continue
        record = threads.get(thread_id)
        if record is None:
            continue
        if record.updated_at < warm_cutoff and thread_id != active_thread_id:
            continue
        family.add(thread_id)
        for neighbor in edges.get(thread_id, set()):
            if neighbor not in family:
                queue.append(neighbor)
    return family


def registry_source_type(entry: dict[str, Any]) -> str:
    source_path = Path(str(entry.get("source_path", "/")))
    if ".codex" in source_path.parts and "sessions" in source_path.parts:
        return "session_day"
    category = str(entry.get("category", ""))
    if category == "git_archive":
        return "git_archive"
    if "worktree" in category or "worktree" in str(entry.get("legacy_mode", "")):
        return "worktree"
    return "path"


def build_registry_state(
    registry: dict[str, Any],
    legacy_imports: list[dict[str, Any]],
) -> dict[str, Any]:
    entries = registry.get("entries", [])
    legacy_entries = [entry for entry in entries if entry.get("provenance") != "native_guardian"]
    return {
        "schema": registry.get("schema"),
        "entry_count": len(entries),
        "legacy_entry_count": len(legacy_entries),
        "legacy_import_count": len(legacy_imports),
        "external_root": registry.get("external_root"),
        "updated_at": registry.get("updated_at"),
    }


def upgrade_registry(registry: dict[str, Any], external_root: Path) -> dict[str, Any]:
    if registry.get("schema") == REGISTRY_V2_SCHEMA:
        registry.setdefault("entries", [])
        registry.setdefault("legacy_imports", [])
        return registry
    if registry.get("schema") == "ssd_guardian_offload_registry_v1":
        upgraded_entries = []
        for entry in registry.get("entries", []):
            upgraded_entries.append(
                {
                    "id": f"entry-{abs(hash((entry.get('source_path'), entry.get('external_path'))))}",
                    "source_path": entry.get("source_path"),
                    "external_path": entry.get("external_path"),
                    "mode": entry.get("mode", "manifest_only"),
                    "source_type": registry_source_type(entry),
                    "workspace": entry.get("workspace"),
                    "thread_ids": [],
                    "session_days": [],
                    "provenance": "ssd_guardian_v1",
                    "status": entry.get("status", "offloaded"),
                    "moved_at": entry.get("moved_at"),
                    "restore_command": entry.get("restore_command"),
                    "temperature_at_move": None,
                    "legacy_mode": entry.get("stub_mode"),
                    "category": entry.get("category"),
                    "description": entry.get("description"),
                    "size_bytes": entry.get("size_bytes"),
                }
            )
        return {
            "schema": REGISTRY_V2_SCHEMA,
            "updated_at": registry.get("updated_at"),
            "attached_volume": registry.get("attached_volume", "e"),
            "external_root": registry.get("external_root", str(external_root)),
            "entries": upgraded_entries,
            "legacy_imports": [],
        }
    return {
        "schema": REGISTRY_V2_SCHEMA,
        "updated_at": isoformat(now_utc()),
        "attached_volume": "e",
        "external_root": str(external_root),
        "entries": [],
        "legacy_imports": [],
    }


def load_registry(registry_path: Path, external_root: Path) -> dict[str, Any]:
    if registry_path.exists():
        try:
            payload = json.loads(registry_path.read_text())
        except json.JSONDecodeError:
            payload = {}
    else:
        payload = {}
    return upgrade_registry(payload, external_root)


def save_registry(registry: dict[str, Any], registry_path: Path, external_root: Path | None) -> Path:
    registry["updated_at"] = isoformat(now_utc())
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(json.dumps(registry, indent=2) + "\n")
    if external_root is not None:
        registry_dir = external_root / "registry"
        registry_dir.mkdir(parents=True, exist_ok=True)
        current_path = registry_dir / "offload-registry-current.json"
        current_path.write_text(json.dumps(registry, indent=2) + "\n")
        snapshot = registry_dir / f"offload-registry-{now_utc().strftime('%Y%m%dT%H%M%SZ')}.json"
        snapshot.write_text(json.dumps(registry, indent=2) + "\n")
        return snapshot
    return registry_path


def find_registry_entry(registry: dict[str, Any], source_path: str) -> dict[str, Any] | None:
    for entry in registry.get("entries", []):
        if entry.get("source_path") == source_path:
            return entry
    return None


def ensure_external_layout(external_root: Path) -> dict[str, Path]:
    layout = {
        "root": external_root,
        "registry_dir": external_root / "registry",
        "cold_codex_sessions_dir": external_root / "cold" / "codex" / "sessions",
        "cold_codex_worktrees_dir": external_root / "cold" / "codex" / "worktrees",
        "cold_user_data_dir": external_root / "cold" / "user-data",
        "cold_workspace_dir": external_root / "cold" / "workspaces",
        "logs_dir": external_root / "logs",
    }
    for path in layout.values():
        path.mkdir(parents=True, exist_ok=True)
    return layout


def volume_summary(path: Path) -> dict[str, Any]:
    usage = shutil.disk_usage(path)
    return {
        "mount": str(path),
        "total_bytes": usage.total,
        "used_bytes": usage.used,
        "available_bytes": usage.free,
    }


def registry_entry_id(source_path: Path, external_path: str) -> str:
    token = f"{source_path}|{external_path}"
    return f"entry-{abs(hash(token))}"


def build_registry_entry(
    *,
    home: Path,
    source_path: Path,
    external_path: Path,
    source_type: str,
    category: str,
    workspace: str | None,
    thread_ids: list[str],
    session_days: list[str],
    temperature_at_move: str,
    mode: str = "manifest_only",
    provenance: str = "native_guardian",
    status: str = "offloaded",
    legacy_mode: str | None = None,
    description: str | None = None,
    size_bytes: int | None = None,
) -> dict[str, Any]:
    restore_command = (
        f"python3 {Path(__file__).parent / 'storage_hygiene.py'} restore "
        f"--source-path {source_path} --confirm RESTORE"
    )
    return {
        "id": registry_entry_id(source_path, str(external_path)),
        "source_path": str(source_path),
        "source_display_path": home_relative(source_path, home),
        "external_path": str(external_path),
        "mode": mode,
        "source_type": source_type,
        "workspace": workspace,
        "thread_ids": thread_ids,
        "session_days": session_days,
        "provenance": provenance,
        "status": status,
        "moved_at": isoformat(now_utc()),
        "restore_command": restore_command,
        "temperature_at_move": temperature_at_move,
        "legacy_mode": legacy_mode,
        "category": category,
        "description": description or category,
        "size_bytes": size_bytes,
    }


def upsert_registry_entry(registry: dict[str, Any], entry: dict[str, Any]) -> None:
    for index, existing in enumerate(registry.get("entries", [])):
        if existing.get("source_path") == entry.get("source_path"):
            registry["entries"][index] = entry
            break
    else:
        registry.setdefault("entries", []).append(entry)


def stub_markdown(entry: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Offloaded To External SSD",
            "",
            f"- Source: `{entry['source_path']}`",
            f"- External: `{entry['external_path']}`",
            f"- Source Type: `{entry['source_type']}`",
            f"- Category: `{entry['category']}`",
            f"- Moved At: `{entry['moved_at']}`",
            f"- Restore: `{entry['restore_command']}`",
            "",
            "Attach the external SSD and run the restore command to materialize this item locally.",
            "",
        ]
    )


def write_directory_stub(path: Path, entry: dict[str, Any]) -> None:
    path.mkdir(parents=True, exist_ok=True)
    marker, index = directory_stub_paths(path)
    marker.write_text(stub_markdown(entry))
    index.write_text(json.dumps(entry, indent=2) + "\n")


def write_sibling_stub(path: Path, entry: dict[str, Any]) -> None:
    markdown_path, json_path = sibling_stub_paths(path)
    markdown_path.write_text(stub_markdown(entry))
    json_path.write_text(json.dumps(entry, indent=2) + "\n")


def remove_sibling_stub(path: Path) -> None:
    for stub_path in sibling_stub_paths(path):
        if stub_path.exists():
            remove_path(stub_path)


def import_legacy_archives(
    *,
    home: Path,
    external_root: Path,
    registry: dict[str, Any],
) -> list[dict[str, Any]]:
    volume_mount = external_root
    while volume_mount.parent != Path("/Volumes") and volume_mount.parent != volume_mount:
        volume_mount = volume_mount.parent
    if volume_mount.parent != Path("/Volumes"):
        parents = external_root.parents
        volume_mount = parents[2] if len(parents) >= 3 else external_root.parent

    discovered: list[dict[str, Any]] = []
    already_imported = {item.get("root") for item in registry.get("legacy_imports", [])}
    for candidate in sorted(volume_mount.iterdir()):
        if not candidate.is_dir():
            continue
        manifests_dir = candidate / "manifests"
        breadcrumbs_dir = candidate / "breadcrumbs"
        session_manifest = manifests_dir / LEGACY_SESSION_TSV
        worktree_manifest = manifests_dir / LEGACY_WORKTREE_TSV
        breadcrumb_matches = list(breadcrumbs_dir.glob("*breadcrumb*.md")) if breadcrumbs_dir.exists() else []
        if not (
            session_manifest.exists()
            or worktree_manifest.exists()
            or breadcrumb_matches
        ):
            continue
        if str(candidate) in already_imported:
            continue
        import_record = {
            "root": str(candidate),
            "imported_at": isoformat(now_utc()),
            "provenance": "legacy_manifest",
        }
        if session_manifest.exists():
            with session_manifest.open(newline="") as handle:
                reader = csv.DictReader(handle, delimiter="\t")
                for row in reader:
                    source = Path(row["source"]).expanduser()
                    archive = Path(row["archive"]).expanduser()
                    if find_registry_entry(registry, str(source)):
                        continue
                    entry = build_registry_entry(
                        home=home,
                        source_path=source,
                        external_path=archive,
                        source_type="session_day",
                        category="app_support",
                        workspace=None,
                        thread_ids=[],
                        session_days=[parse_session_day(source, home)] if is_session_day_path(source, home) else [],
                        temperature_at_move=COLD,
                        mode="legacy_tar_archive",
                        provenance=str(candidate),
                        status=row.get("status", "offloaded"),
                        legacy_mode="tar_placeholder",
                        description="Imported legacy Codex session archive",
                        size_bytes=int(row.get("archive_kib", "0") or "0") * 1024,
                    )
                    upsert_registry_entry(registry, entry)
        if worktree_manifest.exists():
            with worktree_manifest.open(newline="") as handle:
                reader = csv.DictReader(handle, delimiter="\t")
                for row in reader:
                    source = Path(row["source"]).expanduser()
                    destination = Path(row["destination"]).expanduser()
                    if find_registry_entry(registry, str(source)):
                        continue
                    legacy_mode = "live_symlink" if source.is_symlink() else "copied_external"
                    entry = build_registry_entry(
                        home=home,
                        source_path=source,
                        external_path=destination,
                        source_type="worktree",
                        category="codex_worktree",
                        workspace=Path(row.get("repo_name") or "").name or None,
                        thread_ids=[],
                        session_days=[],
                        temperature_at_move=COLD,
                        mode="legacy_live_symlink" if source.is_symlink() else "manifest_only",
                        provenance=str(candidate),
                        status=row.get("status", "offloaded"),
                        legacy_mode=legacy_mode,
                        description="Imported legacy Codex worktree archive",
                        size_bytes=int(row.get("raw_kib", "0") or "0") * 1024,
                    )
                    upsert_registry_entry(registry, entry)
        registry.setdefault("legacy_imports", []).append(import_record)
        discovered.append(import_record)
    return discovered


class StorageGuardian:
    def __init__(
        self,
        *,
        home: Path,
        cwd: Path | None = None,
        roots: Iterable[Path] | None = None,
        external_root: Path | None = None,
        include_external: bool = False,
        registry_path: Path | None = None,
        cache_policy: str = "review_first",
        hot_days: int = 14,
        warm_days: int = 45,
        now: datetime | None = None,
        thread_id: str | None = None,
        import_legacy: bool = False,
    ) -> None:
        self.home = home.expanduser().resolve()
        self.cwd = (cwd or Path.cwd()).expanduser().resolve()
        self.roots = self._normalize_roots(roots or default_roots(self.home))
        self.external_root = external_root.expanduser().resolve() if external_root else None
        self.include_external = include_external
        self.registry_path = (registry_path or DEFAULT_REGISTRY_PATH).expanduser().resolve()
        self.cache_policy = cache_policy
        self.hot_days = hot_days
        self.warm_days = warm_days
        self.now = now or now_utc()
        self.thread_override = thread_id
        self.size_cache: dict[Path, int] = {}
        self.candidates: dict[Path, CandidateV2] = {}
        self.session_profiles: dict[Path, SessionProfile] = {}
        self.workspaces = discover_workspaces(self.home, self.now, hot_days, warm_days)
        self.workspace_lookup = sorted(self.workspaces, key=lambda item: len(item.root.parts), reverse=True)
        self.threads = load_threads(self.home / ".codex" / "state_5.sqlite")
        self.thread_edges = load_thread_edges(self.home / ".codex" / "state_5.sqlite")
        self.worktrees = discover_worktrees(self.home, self.now, hot_days, warm_days)
        self.thread_semantic_paths: dict[str, set[Path]] = {}
        self.thread_goal_workspace_roots: dict[str, set[Path]] = {}
        self.thread_goal_worktree_paths: dict[str, set[Path]] = {}
        self.registry = load_registry(self.registry_path, self.external_root or DEFAULT_EXTERNAL_ROOT)
        self.legacy_imports: list[dict[str, Any]] = []
        if import_legacy and self.external_root and self.external_root.exists():
            self.legacy_imports = import_legacy_archives(
                home=self.home,
                external_root=self.external_root,
                registry=self.registry,
            )
        self.context = self._build_context()

    def _normalize_roots(self, roots: Iterable[Path]) -> list[Path]:
        normalized: list[Path] = []
        seen: set[Path] = set()
        for root in roots:
            candidate = root.expanduser().resolve()
            if not candidate.exists():
                continue
            if candidate in seen:
                continue
            seen.add(candidate)
            normalized.append(candidate)
        return normalized

    def _workspace_for_path(self, path: Path) -> Workspace | None:
        for workspace in self.workspace_lookup:
            if is_relative_to(path, workspace.root):
                return workspace
        return None

    def _path_matches_semantic_reference(self, path: Path, reference: Path) -> bool:
        return path == reference or is_relative_to(path, reference) or is_relative_to(reference, path)

    def _has_semantic_reference(self, path: Path, thread_ids: Sequence[str] | None = None) -> bool:
        ids = thread_ids or self.context.hot_thread_ids
        for thread_id in ids:
            for reference in self.thread_semantic_paths.get(thread_id, set()):
                if self._path_matches_semantic_reference(path, reference):
                    return True
        return False

    def _has_goal_reference(self, path: Path, thread_ids: Sequence[str] | None = None) -> bool:
        ids = thread_ids or self.context.hot_thread_ids
        for thread_id in ids:
            for reference in self.thread_goal_workspace_roots.get(thread_id, set()):
                if self._path_matches_semantic_reference(path, reference):
                    return True
            for reference in self.thread_goal_worktree_paths.get(thread_id, set()):
                if self._path_matches_semantic_reference(path, reference):
                    return True
        return False

    def _threads_for_path(self, path: Path) -> list[str]:
        thread_ids: list[str] = []
        session_day = parse_session_day(path, self.home) if is_session_day_path(path, self.home) else None
        for thread_id in self.context.hot_thread_ids:
            record = self.threads.get(thread_id)
            if record is None:
                continue
            if session_day and record.rollout_path and parse_session_day(record.rollout_path.parent, self.home) == session_day:
                thread_ids.append(thread_id)
                continue
            if record.cwd is None:
                if self._has_semantic_reference(path, [thread_id]) or self._has_goal_reference(path, [thread_id]):
                    thread_ids.append(thread_id)
                continue
            if record.cwd == path or is_relative_to(record.cwd, path) or is_relative_to(path, record.cwd):
                thread_ids.append(thread_id)
                continue
            if self._has_semantic_reference(path, [thread_id]) or self._has_goal_reference(path, [thread_id]):
                thread_ids.append(thread_id)
        return sorted(set(thread_ids))

    def _build_context(self) -> ContextSnapshot:
        active_thread_id = choose_active_thread(self.threads, self.cwd, self.thread_override)
        family_ids = thread_family_ids(
            active_thread_id,
            self.thread_edges,
            self.threads,
            self.now,
            self.warm_days,
        )
        hot_cutoff = self.now - timedelta(days=self.hot_days)
        hot_thread_ids = set(family_ids)
        for record in self.threads.values():
            if record.archived or record.updated_at < hot_cutoff:
                continue
            if record.cwd and (record.cwd == self.cwd or is_relative_to(self.cwd, record.cwd) or is_relative_to(record.cwd, self.cwd)):
                hot_thread_ids.add(record.id)
        semantic_thread_ids = set(family_ids) | set(hot_thread_ids)
        known_roots: list[Path] = [self.cwd]
        known_roots.extend(workspace.root for workspace in self.workspaces)
        known_roots.extend(worktree.repo_path for worktree in self.worktrees if worktree.repo_path is not None)
        self.thread_semantic_paths = load_thread_semantic_paths(
            thread_ids=semantic_thread_ids,
            threads=self.threads,
            known_roots=sorted({path.resolve() if path.exists() else path for path in known_roots}, key=lambda item: len(str(item)), reverse=True),
        )
        for thread_id, references in list(self.thread_semantic_paths.items()):
            self.thread_semantic_paths[thread_id] = {
                path for path in references if path != self.home and str(path) != str(self.home)
            }
        self.thread_goal_workspace_roots, self.thread_goal_worktree_paths = load_thread_goal_references(
            thread_ids=semantic_thread_ids,
            threads=self.threads,
            workspaces=self.workspaces,
            worktrees=self.worktrees,
        )
        hot_session_days: set[str] = set()
        hot_workspace_roots: set[str] = set()
        hot_worktree_paths: set[str] = set()
        conversation_workspace_roots: set[str] = set()
        conversation_goal_workspace_roots: set[str] = set()
        conversation_goal_worktree_paths: set[str] = set()
        conversation_paths: set[str] = set()
        for thread_id in hot_thread_ids:
            record = self.threads.get(thread_id)
            if record is None:
                continue
            if record.rollout_path:
                hot_session_days.add(home_relative(record.rollout_path.parent, self.home))
            if record.cwd:
                workspace = self._workspace_for_path(record.cwd)
                if workspace:
                    hot_workspace_roots.add(home_relative(workspace.root, self.home))
                else:
                    hot_workspace_roots.add(home_relative(record.cwd, self.home))
                for worktree in self.worktrees:
                    if worktree.repo_path and (
                        record.cwd == worktree.repo_path
                        or is_relative_to(record.cwd, worktree.repo_path)
                        or is_relative_to(worktree.repo_path, record.cwd)
                    ):
                        hot_worktree_paths.add(home_relative(worktree.repo_path, self.home))
        for thread_id in semantic_thread_ids:
            for semantic_path in self.thread_semantic_paths.get(thread_id, set()):
                conversation_paths.add(home_relative(semantic_path, self.home))
                workspace = self._workspace_for_path(semantic_path)
                if workspace:
                    display = home_relative(workspace.root, self.home)
                    conversation_workspace_roots.add(display)
                    hot_workspace_roots.add(display)
                for worktree in self.worktrees:
                    if worktree.repo_path and self._path_matches_semantic_reference(semantic_path, worktree.repo_path):
                        hot_worktree_paths.add(home_relative(worktree.repo_path, self.home))
            for workspace_root in self.thread_goal_workspace_roots.get(thread_id, set()):
                display = home_relative(workspace_root, self.home)
                conversation_goal_workspace_roots.add(display)
                hot_workspace_roots.add(display)
            for worktree_path in self.thread_goal_worktree_paths.get(thread_id, set()):
                display = home_relative(worktree_path, self.home)
                conversation_goal_worktree_paths.add(display)
                hot_worktree_paths.add(display)
        current_workspace = self._workspace_for_path(self.cwd)
        keep_models = sorted(discover_keep_models(current_workspace.root if current_workspace else self.cwd))
        external_volumes: list[dict[str, Any]] = []
        if self.external_root and self.external_root.exists():
            external_volumes.append(volume_summary(self.external_root))
        return ContextSnapshot(
            cwd=home_relative(self.cwd, self.home),
            detected_thread_id=active_thread_id,
            hot_thread_ids=sorted(hot_thread_ids),
            hot_session_days=sorted(hot_session_days),
            hot_workspace_roots=sorted(hot_workspace_roots),
            hot_worktree_paths=sorted(hot_worktree_paths),
            conversation_workspace_roots=sorted(conversation_workspace_roots),
            conversation_goal_workspace_roots=sorted(conversation_goal_workspace_roots),
            conversation_goal_worktree_paths=sorted(conversation_goal_worktree_paths),
            conversation_paths=sorted(conversation_paths)[:100],
            keep_models=keep_models,
            external_volumes=external_volumes,
            time_windows={"hot_days": self.hot_days, "warm_days": self.warm_days},
        )

    def _measure_path(self, path: Path, root_dev: int | None = None) -> int:
        resolved = path.resolve()
        cached = self.size_cache.get(resolved)
        if cached is not None:
            return cached
        path_stat = safe_stat(resolved)
        if path_stat is None:
            return 0
        if not resolved.is_dir():
            size = on_disk_size(path_stat)
            self.size_cache[resolved] = size
            return size
        if root_dev is None:
            root_dev = path_stat.st_dev
        total = 0
        had_errors = False
        stack = [resolved]
        while stack:
            current = stack.pop()
            try:
                with os.scandir(current) as entries:
                    for entry in entries:
                        try:
                            entry_stat = entry.stat(follow_symlinks=False)
                        except OSError:
                            had_errors = True
                            continue
                        if entry_stat.st_dev != root_dev:
                            continue
                        total += on_disk_size(entry_stat)
                        if entry.is_dir(follow_symlinks=False):
                            stack.append(Path(entry.path))
            except OSError:
                had_errors = True
        if had_errors:
            du_size = du_measure(resolved)
            if du_size is not None:
                total = du_size
        self.size_cache[resolved] = total
        return total

    def _signal_for_path(self, path: Path, workspace: Workspace | None) -> datetime:
        signals = [datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)]
        if workspace and is_relative_to(path, workspace.root):
            signals.append(workspace.last_signal_at)
        for thread_id in self._threads_for_path(path):
            record = self.threads.get(thread_id)
            if record is not None:
                signals.append(record.updated_at)
        return max(signals)

    def _temperature_for(
        self,
        *,
        path: Path,
        workspace: Workspace | None,
        last_signal: datetime,
        thread_ids: list[str],
        matched_keep_model: bool,
        has_live_guard: bool,
        semantic_ref_match: bool,
    ) -> tuple[str, int]:
        score = 0
        if path == self.cwd or is_relative_to(self.cwd, path):
            score += 100
        if workspace and home_relative(workspace.root, self.home) in self.context.hot_workspace_roots:
            score += 70
        if thread_ids:
            score += 65
        if semantic_ref_match:
            score += 60
        if matched_keep_model:
            score += 55
        if has_live_guard:
            score += 55
        if last_signal >= self.now - timedelta(days=self.hot_days):
            score += 45
        elif last_signal >= self.now - timedelta(days=self.warm_days):
            score += 20

        if score >= 100 or last_signal >= self.now - timedelta(days=self.hot_days):
            return HOT, min(score, 100)
        if score >= 35 or last_signal >= self.now - timedelta(days=self.warm_days):
            return WARM, min(score, 100)
        return COLD, min(score, 100)

    def _action_for(
        self,
        *,
        path: Path,
        category: str,
        source_type: str,
        temperature: str,
        workspace: Workspace | None,
        matched_keep_model: bool,
        has_live_guard: bool,
        metadata: dict[str, Any],
    ) -> tuple[str, str]:
        if category in {"apple_managed", "user_media"}:
            return PROTECT, "Apple-managed or personal data"
        if matched_keep_model:
            return PROTECT, "Referenced by active workspace model configuration"
        if has_live_guard:
            return PROTECT, "Live lock or PID guard detected"

        if source_type == "session_day":
            if temperature == HOT:
                return PROTECT, "Active or recent Codex session day"
            if temperature == WARM:
                return REVIEW_FIRST, "Recent session day; review before offload"
            return OFFLOAD_MANIFEST, "Cold session day eligible for manifest-only offload"

        if source_type == "worktree":
            if metadata.get("empty_container"):
                return DELETE_NOW, "Empty or orphaned worktree container"
            if metadata.get("legacy_live_symlink"):
                if temperature == HOT:
                    return PROTECT, "Legacy live symlink worktree still appears active"
                if temperature == WARM:
                    return REVIEW_FIRST, "Legacy live symlink worktree is recent; review before migration"
                return OFFLOAD_MANIFEST, "Cold legacy worktree can be migrated away from live symlink mode"
            if temperature == HOT:
                return PROTECT, "Active worktree tied to recent session or workspace activity"
            if temperature == WARM:
                return REVIEW_FIRST, "Recent worktree; review before offload"
            if metadata.get("clean_repo"):
                return OFFLOAD_MANIFEST, "Cold clean worktree eligible for manifest-only offload"
            return REVIEW_FIRST, "Cold worktree is not clean; review before offload"

        if category in {"cache", "build_artifact", "dev_env"}:
            if temperature == HOT:
                return REVIEW_FIRST, "Rebuildable artifact is still warm or active"
            return DELETE_NOW, "Rebuildable cache or development artifact"

        if category == "model_cache":
            if self.cache_policy == "cache_first" and temperature == COLD:
                return DELETE_NOW, "Cold model cache under cache-first policy"
            if temperature == HOT:
                return PROTECT, "Model cache is still hot or referenced"
            return REVIEW_FIRST, "Model cache has redownload cost"

        if category in {"training_artifact", "model_asset"}:
            if temperature == HOT:
                return PROTECT, "Training or model asset is still active"
            return REVIEW_FIRST, "Training or model asset requires manual review"

        if category in {"git_history", "duplicate_candidate", "external_archive", "external_quarantine"}:
            return REVIEW_FIRST, "Large or archival data requires review"

        if workspace and workspace.activity == "active":
            return PROTECT, "Inside an active workspace and not clearly rebuildable"
        if temperature == HOT:
            return PROTECT, "Hot path without a safe automatic action"
        return REVIEW_FIRST, "Needs manual review"

    def _record_candidate(
        self,
        *,
        path: Path,
        category: str,
        source_type: str,
        recovery_cost: str,
        reason: str,
        metadata: dict[str, Any] | None = None,
        root_dev: int | None = None,
    ) -> None:
        resolved = path.resolve() if path.exists() or path.is_symlink() else path
        display_path = home_relative(path, self.home)
        existing = self.candidates.get(resolved)
        if existing is not None:
            existing_is_home = display_path_is_home_relative(existing.display_path)
            new_is_home = display_path_is_home_relative(display_path)
            if new_is_home and not existing_is_home:
                del self.candidates[resolved]
            else:
                return
        if path.exists():
            root_dev = root_dev if root_dev is not None else path.stat().st_dev
            size_bytes = self._measure_path(path, root_dev)
        else:
            size_bytes = 0
        workspace = self._workspace_for_path(path)
        thread_ids = self._threads_for_path(path)
        matched_keep_model = path.name in {model.split("/", 1)[1] for model in self.context.keep_models}
        has_live_guard = has_live_lock_or_pid(path)
        semantic_ref_match = self._has_semantic_reference(path, thread_ids or self.context.hot_thread_ids)
        last_signal = self._signal_for_path(path, workspace) if path.exists() else self.now
        temp, score = self._temperature_for(
            path=path,
            workspace=workspace,
            last_signal=last_signal,
            thread_ids=thread_ids,
            matched_keep_model=matched_keep_model,
            has_live_guard=has_live_guard,
            semantic_ref_match=semantic_ref_match,
        )
        action, action_reason = self._action_for(
            path=path,
            category=category,
            source_type=source_type,
            temperature=temp,
            workspace=workspace,
            matched_keep_model=matched_keep_model,
            has_live_guard=has_live_guard,
            metadata=metadata or {},
        )
        self.candidates[resolved] = CandidateV2(
            path=resolved,
            display_path=display_path,
            size_bytes=size_bytes,
            category=category,
            source_type=source_type,
            temperature=temp,
            importance_score=score,
            action=action,
            workspace=workspace.name if workspace else None,
            thread_ids=thread_ids,
            last_signal_at=isoformat(last_signal),
            recovery_cost=recovery_cost,
            reason=f"{reason}; {action_reason}",
            metadata=metadata or {},
        )

    def _scan_codex_root(self, root: Path) -> None:
        sessions_root = root / "sessions"
        if sessions_root.exists():
            for year_dir in sorted(sessions_root.iterdir()):
                if not year_dir.is_dir():
                    continue
                for month_dir in sorted(year_dir.iterdir()):
                    if not month_dir.is_dir():
                        continue
                    for day_dir in sorted(month_dir.iterdir()):
                        if not day_dir.is_dir():
                            continue
                        if is_directory_stub(day_dir) or (day_dir / "OFFLOADED_TO_EXTERNAL_SSD.txt").exists():
                            size_bytes = self._measure_path(day_dir, day_dir.stat().st_dev) if day_dir.exists() else 0
                            thread_ids = self._threads_for_path(day_dir)
                            last_signal = datetime.fromtimestamp(day_dir.stat().st_mtime, tz=timezone.utc)
                            temp, score = self._temperature_for(
                                path=day_dir,
                                workspace=None,
                                last_signal=last_signal,
                                thread_ids=thread_ids,
                                matched_keep_model=False,
                                has_live_guard=False,
                                semantic_ref_match=self._has_semantic_reference(day_dir, thread_ids)
                                or self._has_goal_reference(day_dir, thread_ids),
                            )
                            action = PROTECT if temp == HOT else REVIEW_FIRST
                            self.session_profiles[day_dir.resolve()] = SessionProfile(
                                day=parse_session_day(day_dir, self.home),
                                size_bytes=size_bytes,
                                temperature=temp,
                                action=action,
                                thread_ids=thread_ids,
                                offloaded=True,
                                last_signal_at=isoformat(last_signal),
                            )
                            continue
                        self._record_candidate(
                            path=day_dir,
                            category="app_support",
                            source_type="session_day",
                            recovery_cost="medium",
                            reason="Codex session day",
                            root_dev=day_dir.stat().st_dev,
                        )
                        candidate = self.candidates[day_dir.resolve()]
                        self.session_profiles[day_dir.resolve()] = SessionProfile(
                            day=parse_session_day(day_dir, self.home),
                            size_bytes=candidate.size_bytes,
                            temperature=candidate.temperature,
                            action=candidate.action,
                            thread_ids=candidate.thread_ids,
                            offloaded=False,
                            last_signal_at=candidate.last_signal_at,
                        )

        archived_sessions = root / "archived_sessions"
        if archived_sessions.exists():
            self._record_candidate(
                path=archived_sessions,
                category="app_support",
                source_type="path",
                recovery_cost="medium",
                reason="Archived Codex sessions directory",
                root_dev=archived_sessions.stat().st_dev,
            )

        worktrees_root = root / "worktrees"
        if worktrees_root.exists():
            for worktree in self.worktrees:
                if worktree.repo_path is None:
                    self._record_candidate(
                        path=worktree.container,
                        category="dev_env",
                        source_type="worktree",
                        recovery_cost="low",
                        reason="Worktree container without a repo payload",
                        metadata={"empty_container": True, "worktree_id": worktree.identifier},
                        root_dev=worktree.container.stat().st_dev,
                    )
                    continue
                metadata = {
                    "worktree_id": worktree.identifier,
                    "repo_name": worktree.repo_name,
                    "clean_repo": bool(worktree.clean),
                    "legacy_live_symlink": worktree.is_symlink,
                }
                if worktree.is_symlink:
                    metadata["symlink_target"] = str(worktree.symlink_target) if worktree.symlink_target else None
                self._record_candidate(
                    path=worktree.repo_path,
                    category="codex_worktree" if not worktree.is_symlink else "external_archive",
                    source_type="worktree",
                    recovery_cost="high",
                    reason="Codex worktree payload",
                    metadata=metadata,
                    root_dev=worktree.repo_path.stat().st_dev if worktree.repo_path.exists() else None,
                )

    def _classify_standard_path(
        self,
        path: Path,
        *,
        is_root: bool,
    ) -> tuple[str, str, str, str] | None:
        parts = relative_parts(path, self.home)
        name = path.name
        lower_name = name.lower()

        if name.endswith(".photoslibrary"):
            return ("user_media", "path", "high", "Photo library package")
        if name.endswith(".fcpbundle"):
            return ("user_media", "path", "high", "Final Cut library bundle")
        if lower_name == "apple_health_export":
            return ("user_media", "path", "high", "Personal health export")

        apple_key = tuple(parts[:3])
        if apple_key in APPLE_CONTAINER_PROTECT:
            category, reason = APPLE_CONTAINER_PROTECT[apple_key]
            return (category, "path", "high", reason)

        if parts[:3] == ["Library", "Application Support", "Caches"] and len(parts) == 4:
            return ("cache", "cache", "low", "Application Support cache")

        if parts[:2] == ["Library", "Caches"] and len(parts) == 3:
            if lower_name == "models":
                return ("model_cache", "cache", "medium", "Library model cache")
            return ("cache", "cache", "low", "Library cache")

        if parts[:1] == [".cache"] and len(parts) == 2:
            if lower_name == "huggingface":
                return ("model_cache", "cache", "high", "Hugging Face model cache")
            return ("cache", "cache", "low", "User cache")

        if parts[:2] == [".npm", "_cacache"]:
            return ("cache", "cache", "low", "npm package cache")

        if parts[:4] == ["Library", "Developer", "Xcode", "DerivedData"]:
            return ("build_artifact", "path", "low", "Xcode DerivedData")

        if (
            len(parts) >= 5
            and parts[:3] == ["Library", "Developer", "Xcode"]
            and parts[3].endswith("DeviceSupport")
        ):
            return ("simulator", "path", "medium", "Xcode device support runtime files")

        if parts[:3] == ["Library", "Developer", "CoreSimulator"]:
            return ("simulator", "path", "medium", "Simulator runtime and device data")

        if is_root and parts == ["Models"]:
            return ("model_asset", "path", "high", "Local model store")

        if lower_name in SAFE_NOW_DIR_NAMES:
            return (SAFE_NOW_DIR_NAMES[lower_name], "path", "low", "Rebuildable development artifact")

        if lower_name.startswith("venv") and lower_name != "vendor":
            return ("dev_env", "path", "low", "Rebuildable Python environment")

        if lower_name == ".git":
            path_stat = safe_stat(path)
            if path_stat is None:
                return None
            size_bytes = self._measure_path(path, path_stat.st_dev)
            if size_bytes >= 1024**3:
                return ("git_history", "path", "high", "Large git history store")
            return None

        if is_git_archive_like_path(path):
            return ("external_archive", "path", "medium", "Git archive or backup payload")

        if "copy" in lower_name:
            path_stat = safe_stat(path)
            if path_stat is None:
                return None
            size_bytes = self._measure_path(path, path_stat.st_dev)
            if size_bytes >= 512 * 1024 * 1024:
                return ("duplicate_candidate", "path", "low", "Name suggests a duplicate or copied folder")

        if lower_name in {"models", "artifacts", "adapters"}:
            if lower_name == "models":
                return ("model_asset", "path", "high", "Large local model directory")
            return ("training_artifact", "path", "high", "Generated training or experiment output")

        return None

    def _scan_standard_root(self, root: Path) -> None:
        root_stat = safe_stat(root)
        if root_stat is None:
            return
        root_dev = root_stat.st_dev
        root_spec = self._classify_standard_path(root, is_root=True)
        if root_spec is not None:
            category, source_type, recovery_cost, reason = root_spec
            self._record_candidate(
                path=root,
                category=category,
                source_type=source_type,
                recovery_cost=recovery_cost,
                reason=reason,
                root_dev=root_dev,
            )
            return
        for dirpath, dirnames, filenames in os.walk(root, topdown=True, followlinks=False):
            current = Path(dirpath)
            kept_dirs: list[str] = []
            for dirname in list(dirnames):
                child = current / dirname
                child_stat = safe_stat(child)
                if child_stat is None or child_stat.st_dev != root_dev:
                    continue
                spec = self._classify_standard_path(child, is_root=False)
                if spec is not None:
                    category, source_type, recovery_cost, reason = spec
                    self._record_candidate(
                        path=child,
                        category=category,
                        source_type=source_type,
                        recovery_cost=recovery_cost,
                        reason=reason,
                        root_dev=root_dev,
                    )
                    continue
                kept_dirs.append(dirname)
            dirnames[:] = kept_dirs
            for filename in filenames:
                child = current / filename
                child_stat = safe_stat(child)
                if child_stat is None or child_stat.st_dev != root_dev:
                    continue
                spec = self._classify_standard_path(child, is_root=False)
                if spec is None:
                    continue
                category, source_type, recovery_cost, reason = spec
                self._record_candidate(
                    path=child,
                    category=category,
                    source_type=source_type,
                    recovery_cost=recovery_cost,
                    reason=reason,
                    root_dev=root_dev,
                )

    def _scan_external_root(self, root: Path) -> None:
        if not root.exists():
            return
        for child in sorted(root.iterdir()):
            if child.name == "registry":
                continue
            if child.name == "quarantine":
                self._record_candidate(
                    path=child,
                    category="external_quarantine",
                    source_type="external_path",
                    recovery_cost="low",
                    reason="External quarantine holding area",
                    root_dev=child.stat().st_dev,
                )
                continue
            self._record_candidate(
                path=child,
                category="external_archive",
                source_type="external_path",
                recovery_cost="medium",
                reason="External cold storage or archive root",
                root_dev=child.stat().st_dev,
            )
        legacy_roots = [Path(item["root"]) for item in self.registry.get("legacy_imports", [])]
        for legacy_root in legacy_roots:
            if not legacy_root.exists():
                continue
            self._record_candidate(
                path=legacy_root,
                category="external_archive",
                source_type="external_path",
                recovery_cost="medium",
                reason="Imported legacy external archive root",
                root_dev=legacy_root.stat().st_dev,
            )

    def _archive_pressure_score(self, candidate: CandidateV2) -> int:
        if candidate.temperature != COLD:
            return 0
        score = 0
        if candidate.source_type == "session_day":
            score += 70
        elif candidate.category == "external_archive" and is_git_archive_like_path(candidate.path):
            score += 60
        else:
            return 0

        size_bytes = candidate.size_bytes
        if size_bytes >= 50 * 1024**3:
            score += 30
        elif size_bytes >= 10 * 1024**3:
            score += 25
        elif size_bytes >= 1024**3:
            score += 18
        elif size_bytes >= 100 * 1024**2:
            score += 10
        return min(score, 100)

    def _apply_archive_pressure_pass(self) -> None:
        for resolved, candidate in list(self.candidates.items()):
            pressure = self._archive_pressure_score(candidate)
            if pressure <= 0:
                continue
            metadata = dict(candidate.metadata)
            metadata["archive_pressure_score"] = pressure
            reason = candidate.reason
            action = candidate.action
            if candidate.source_type == "session_day":
                action = OFFLOAD_MANIFEST
                reason = candidate.reason + "; Archive pressure pass: cold session day prioritized for offload"
            elif candidate.category == "external_archive" and is_git_archive_like_path(candidate.path):
                if display_path_is_home_relative(candidate.display_path):
                    action = OFFLOAD_MANIFEST
                    reason = candidate.reason + "; Archive pressure pass: cold git archive prioritized for offload"
                else:
                    reason = candidate.reason + "; Archive pressure pass: cold external git archive prioritized for prune review"
            self.candidates[resolved] = replace(
                candidate,
                action=action,
                reason=reason,
                offload_pressure_score=pressure,
                metadata=metadata,
            )

    def scan(self) -> dict[str, Any]:
        for root in self.roots:
            if root == self.home / ".codex":
                self._scan_codex_root(root)
            else:
                self._scan_standard_root(root)
        if self.include_external and self.external_root and self.external_root.exists():
            self._scan_external_root(self.external_root)

        self._apply_archive_pressure_pass()

        candidates = sorted(
            self.candidates.values(),
            key=lambda candidate: (
                ACTION_ORDER[candidate.action],
                -candidate.offload_pressure_score,
                TEMPERATURE_ORDER[candidate.temperature],
                -candidate.size_bytes,
                candidate.display_path.lower(),
            ),
        )
        workspace_profiles = self._build_workspace_profiles(candidates)
        session_profiles = [profile.to_dict() for profile in sorted(self.session_profiles.values(), key=lambda item: item.day)]
        volume_summaries = [volume_summary(Path("/System/Volumes/Data"))]
        if self.external_root and self.external_root.exists():
            volume_summaries.append(volume_summary(self.external_root))
        summary_by_action = {
            DELETE_NOW + "_bytes": sum(item.size_bytes for item in candidates if item.action == DELETE_NOW),
            OFFLOAD_MANIFEST + "_bytes": sum(item.size_bytes for item in candidates if item.action == OFFLOAD_MANIFEST),
            REVIEW_FIRST + "_bytes": sum(item.size_bytes for item in candidates if item.action == REVIEW_FIRST),
            PROTECT + "_bytes": sum(item.size_bytes for item in candidates if item.action == PROTECT),
        }
        return {
            "schema": PLAN_V2_SCHEMA,
            "generated_at": isoformat(self.now),
            "execution_context": self.context.to_dict(),
            "volume_summaries": volume_summaries,
            "workspace_profiles": [profile.to_dict() for profile in workspace_profiles],
            "session_profiles": session_profiles,
            "candidates": [candidate.to_dict() for candidate in candidates],
            "summary_by_action": summary_by_action,
            "registry_state": build_registry_state(self.registry, self.legacy_imports),
            "legacy_imports": self.legacy_imports,
            "settings": {
                "hot_days": self.hot_days,
                "warm_days": self.warm_days,
                "cache_policy": self.cache_policy,
                "cwd": str(self.cwd),
                "roots": [str(root) for root in self.roots],
                "external_root": str(self.external_root) if self.external_root else None,
                "include_external": self.include_external,
                "thread_id": self.thread_override,
                "registry_path": str(self.registry_path),
            },
        }

    def _build_workspace_profiles(self, candidates: Sequence[CandidateV2]) -> list[WorkspaceProfile]:
        candidate_totals: dict[str, dict[str, int]] = {}
        for candidate in candidates:
            if candidate.workspace is None:
                continue
            bucket = candidate_totals.setdefault(
                candidate.workspace,
                {DELETE_NOW: 0, OFFLOAD_MANIFEST: 0, REVIEW_FIRST: 0, PROTECT: 0},
            )
            bucket[candidate.action] += candidate.size_bytes
        profiles: list[WorkspaceProfile] = []
        for workspace in self.workspaces:
            total_size = self._measure_path(workspace.root, workspace.root.stat().st_dev)
            totals = candidate_totals.get(
                workspace.name,
                {DELETE_NOW: 0, OFFLOAD_MANIFEST: 0, REVIEW_FIRST: 0, PROTECT: 0},
            )
            protected_bytes = max(
                0,
                total_size - totals[DELETE_NOW] - totals[OFFLOAD_MANIFEST] - totals[REVIEW_FIRST],
            )
            profiles.append(
                WorkspaceProfile(
                    name=workspace.name,
                    root_display=home_relative(workspace.root, self.home),
                    activity=workspace.activity,
                    last_signal_at=isoformat(workspace.last_signal_at),
                    protected_bytes=protected_bytes,
                    delete_now_bytes=totals[DELETE_NOW],
                    offload_manifest_bytes=totals[OFFLOAD_MANIFEST],
                    review_first_bytes=totals[REVIEW_FIRST],
                )
            )
        return profiles


def markdown_report(report: dict[str, Any]) -> str:
    lines = [
        "# Storage Guardian Report",
        "",
        f"Generated: {report['generated_at']}",
        "",
        "## Execution Context",
        "",
        f"- CWD: `{report['execution_context']['cwd']}`",
        f"- Detected Thread: `{report['execution_context']['detected_thread_id'] or 'none'}`",
        f"- Hot Days: `{report['execution_context']['time_windows']['hot_days']}`",
        f"- Warm Days: `{report['execution_context']['time_windows']['warm_days']}`",
        "",
        "## Volume Summaries",
        "",
    ]
    for volume in report["volume_summaries"]:
        lines.append(
            f"- `{volume['mount']}`: used `{human_bytes(int(volume['used_bytes']))}`, free `{human_bytes(int(volume['available_bytes']))}`"
        )
    lines.extend(["", "## Workspace Profiles", ""])
    if report["workspace_profiles"]:
        lines.append("| Workspace | Root | Activity | Last Signal | Protected | Delete Now | Offload | Review |")
        lines.append("| --- | --- | --- | --- | ---: | ---: | ---: | ---: |")
        for profile in report["workspace_profiles"]:
            lines.append(
                "| {name} | `{root}` | {activity} | {last_signal_at} | {protected} | {delete_now} | {offload} | {review} |".format(
                    name=profile["name"],
                    root=profile["root"],
                    activity=profile["activity"],
                    last_signal_at=profile["last_signal_at"],
                    protected=human_bytes(int(profile["protected_bytes"])),
                    delete_now=human_bytes(int(profile["delete_now_bytes"])),
                    offload=human_bytes(int(profile["offload_manifest_bytes"])),
                    review=human_bytes(int(profile["review_first_bytes"])),
                )
            )
    else:
        lines.append("No workspaces detected.")
    lines.extend(["", "## Session Profiles", ""])
    if report["session_profiles"]:
        lines.append("| Day | Size | Temperature | Action | Offloaded | Threads |")
        lines.append("| --- | ---: | --- | --- | --- | --- |")
        for profile in report["session_profiles"]:
            lines.append(
                "| {day} | {size} | {temperature} | {action} | {offloaded} | {threads} |".format(
                    day=profile["day"],
                    size=human_bytes(int(profile["size_bytes"])),
                    temperature=profile["temperature"],
                    action=profile["action"],
                    offloaded="yes" if profile["offloaded"] else "no",
                    threads=", ".join(profile["thread_ids"]) or "-",
                )
            )
    else:
        lines.append("No session profiles detected.")
    for action, title in [
        (DELETE_NOW, "Delete Now"),
        (OFFLOAD_MANIFEST, "Offload Manifest"),
        (REVIEW_FIRST, "Review First"),
        (PROTECT, "Protect"),
    ]:
        lines.extend(["", f"## {title}", ""])
        action_candidates = [item for item in report["candidates"] if item["action"] == action]
        if not action_candidates:
            lines.append("No entries in this section.")
            continue
        lines.append("| Path | Size | Temp | Category | Workspace | Threads | Reason |")
        lines.append("| --- | ---: | --- | --- | --- | --- | --- |")
        for candidate in action_candidates:
            lines.append(
                "| `{path}` | {size} | {temperature} | {category} | {workspace} | {threads} | {reason} |".format(
                    path=candidate["path"],
                    size=human_bytes(int(candidate["size_bytes"])),
                    temperature=candidate["temperature"],
                    category=candidate["category"],
                    workspace=candidate["workspace"] or "-",
                    threads=", ".join(candidate["thread_ids"]) or "-",
                    reason=candidate["reason"],
                )
            )
    lines.extend(["", "## Summary By Action", ""])
    for action in [DELETE_NOW, OFFLOAD_MANIFEST, REVIEW_FIRST, PROTECT]:
        lines.append(f"- `{action}`: `{human_bytes(int(report['summary_by_action'][action + '_bytes']))}`")
    return "\n".join(lines) + "\n"


def cleanup_script(report: dict[str, Any]) -> str:
    lines = [
        "#!/usr/bin/env bash",
        "set -eu",
        "",
        "# Generated by storage_guardian_engine.py.",
        "# Review before running. This script deletes only delete_now entries.",
        "",
    ]
    for candidate in report["candidates"]:
        if candidate["action"] != DELETE_NOW:
            continue
        lines.append(f'rm -rf "{candidate["path"]}"')
    lines.append("")
    return "\n".join(lines)


def audit_with_options(
    *,
    home: Path,
    cwd: Path,
    json_out: Path,
    md_out: Path | None,
    cleanup_script_out: Path | None,
    roots: Iterable[Path] | None,
    external_root: Path | None,
    include_external: bool,
    registry_path: Path,
    cache_policy: str,
    hot_days: int,
    warm_days: int,
    thread_id: str | None,
    import_legacy: bool,
    now: datetime | None = None,
) -> tuple[dict[str, Any], StorageGuardian]:
    guardian = StorageGuardian(
        home=home,
        cwd=cwd,
        roots=roots,
        external_root=external_root,
        include_external=include_external,
        registry_path=registry_path,
        cache_policy=cache_policy,
        hot_days=hot_days,
        warm_days=warm_days,
        now=now,
        thread_id=thread_id,
        import_legacy=import_legacy,
    )
    report = guardian.scan()
    json_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(report, indent=2) + "\n")
    if md_out is not None:
        md_out.parent.mkdir(parents=True, exist_ok=True)
        md_out.write_text(markdown_report(report))
    if cleanup_script_out is not None:
        cleanup_script_out.parent.mkdir(parents=True, exist_ok=True)
        cleanup_script_out.write_text(cleanup_script(report))
    if import_legacy:
        save_registry(guardian.registry, registry_path, external_root if include_external else None)
    return report, guardian


def candidate_path(path_text: str, home: Path) -> Path:
    if path_text == "$HOME":
        return home
    if path_text.startswith("$HOME/"):
        return home / path_text.removeprefix("$HOME/")
    return Path(path_text).expanduser()


def external_headroom_ok(external_root: Path, incoming_bytes: int) -> bool:
    usage = shutil.disk_usage(external_root)
    reserve = DEFAULT_EXTERNAL_RESERVE_GB * 1024**3
    return usage.free - incoming_bytes >= reserve


def planned_external_relative(candidate: dict[str, Any], path: Path, home: Path) -> str:
    parts = relative_parts(path, home)
    if is_session_day_path(path, home):
        return "cold/codex/sessions/" + "/".join(parts[2:5])
    metadata = candidate.get("metadata", {})
    if candidate.get("source_type") == "worktree":
        repo_name = metadata.get("repo_name") or path.name
        worktree_id = metadata.get("worktree_id") or path.parent.name
        return f"cold/codex/worktrees/{worktree_id}/{repo_name}"
    workspace = candidate.get("workspace")
    if workspace:
        return f"cold/workspaces/{workspace}/{path.name}"
    return f"cold/user-data/{path.name}"


def offload_candidate(
    candidate: dict[str, Any],
    *,
    home: Path,
    external_root: Path,
    registry: dict[str, Any],
) -> dict[str, Any]:
    path = candidate_path(str(candidate["path"]), home)
    if candidate.get("metadata", {}).get("legacy_live_symlink") and path.is_symlink():
        target = Path(os.readlink(path))
        if not target.is_absolute():
            target = (path.parent / target).resolve()
        remove_path(path)
        entry = build_registry_entry(
            home=home,
            source_path=path,
            external_path=target,
            source_type="worktree",
            category=str(candidate["category"]),
            workspace=candidate.get("workspace"),
            thread_ids=list(candidate.get("thread_ids", [])),
            session_days=[],
            temperature_at_move=str(candidate["temperature"]),
            mode="manifest_only",
            provenance="native_guardian",
            status="offloaded",
            legacy_mode="migrated_from_live_symlink",
            description="Migrated legacy live symlink worktree to manifest stub",
            size_bytes=int(candidate.get("size_bytes", 0)),
        )
        write_directory_stub(path, entry)
        upsert_registry_entry(registry, entry)
        return {
            "path": str(path),
            "status": "migrated_stub",
            "external_path": str(target),
        }

    if not path.exists():
        return {"path": str(path), "status": "skipped_missing"}
    external_path = external_root / planned_external_relative(candidate, path, home)
    if external_path.exists():
        return {"path": str(path), "status": "skipped_external_exists", "external_path": str(external_path)}
    size_bytes = du_measure(path) or 0
    if not external_headroom_ok(external_root, size_bytes):
        return {"path": str(path), "status": "blocked_external_headroom", "external_path": str(external_path)}
    external_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(path), str(external_path))
    entry = build_registry_entry(
        home=home,
        source_path=path,
        external_path=external_path,
        source_type=str(candidate["source_type"]),
        category=str(candidate["category"]),
        workspace=candidate.get("workspace"),
        thread_ids=list(candidate.get("thread_ids", [])),
        session_days=[parse_session_day(path, home)] if is_session_day_path(path, home) else [],
        temperature_at_move=str(candidate["temperature"]),
        size_bytes=int(candidate.get("size_bytes", 0)),
    )
    if path.suffix in {".xcarchive", ".fcpbundle"}:
        write_sibling_stub(path, entry)
    else:
        write_directory_stub(path, entry)
    upsert_registry_entry(registry, entry)
    return {
        "path": str(path),
        "status": "offloaded",
        "external_path": str(external_path),
        "size_bytes": int(candidate.get("size_bytes", 0)),
    }


def restore_entry(entry: dict[str, Any]) -> dict[str, Any]:
    source = Path(str(entry["source_path"]))
    external = Path(str(entry["external_path"]))
    if not external.exists():
        return {"path": str(source), "status": "missing_external"}

    if entry.get("mode") == "legacy_tar_archive":
        return {"path": str(source), "status": "unsupported_legacy_tar_restore"}

    if source.exists() and not source.is_symlink():
        if is_directory_stub(source):
            remove_path(source)
        else:
            sibling_md, sibling_json = sibling_stub_paths(source)
            if sibling_md.exists() or sibling_json.exists():
                remove_sibling_stub(source)
            else:
                return {"path": str(source), "status": "refused_existing_mismatch"}

    if source.is_symlink():
        source.unlink()

    source.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(external), str(source))

    if not source.exists():
        return {"path": str(source), "status": "restore_failed"}
    return {"path": str(source), "status": "restored"}


def apply_plan(plan: dict[str, Any], *, requested_actions: list[str], confirm: str) -> tuple[int, dict[str, Any]]:
    if confirm != "APPLY":
        return 2, {"error": "Pass --confirm APPLY to execute."}
    if plan.get("schema") != PLAN_V2_SCHEMA:
        return 2, {"error": "Unsupported plan schema."}

    settings = plan["settings"]
    home = Path.home().expanduser().resolve()
    cwd = Path(settings["cwd"]).expanduser().resolve()
    external_root = Path(settings["external_root"]).expanduser().resolve() if settings.get("external_root") else None
    registry_path = Path(settings["registry_path"]).expanduser().resolve()

    fresh_report, guardian = audit_with_options(
        home=home,
        cwd=cwd,
        json_out=Path("/tmp/storage_guardian_apply_revalidation.json"),
        md_out=None,
        cleanup_script_out=None,
        roots=[Path(item) for item in settings["roots"]],
        external_root=external_root,
        include_external=bool(settings["include_external"]),
        registry_path=registry_path,
        cache_policy=settings["cache_policy"],
        hot_days=int(settings["hot_days"]),
        warm_days=int(settings["warm_days"]),
        thread_id=settings.get("thread_id"),
        import_legacy=False,
    )
    fresh_candidates = {item["path"]: item for item in fresh_report["candidates"]}

    deleted: list[dict[str, Any]] = []
    offloaded: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    for candidate in plan["candidates"]:
        path_text = str(candidate["path"])
        planned_action = str(candidate["action"])
        if planned_action not in requested_actions:
            skipped.append({"path": path_text, "status": "skipped_not_requested"})
            continue
        fresh = fresh_candidates.get(path_text)
        if fresh is None:
            skipped.append({"path": path_text, "status": "skipped_missing_or_reclassified"})
            continue
        if fresh["action"] != planned_action:
            skipped.append(
                {
                    "path": path_text,
                    "status": "skipped_revalidated_action_changed",
                    "planned_action": planned_action,
                    "fresh_action": fresh["action"],
                }
            )
            continue
        try:
            if planned_action == DELETE_NOW:
                remove_path(candidate_path(path_text, home))
                deleted.append({"path": path_text, "status": "deleted", "size_bytes": int(candidate["size_bytes"])})
            elif planned_action == OFFLOAD_MANIFEST:
                if external_root is None:
                    skipped.append({"path": path_text, "status": "skipped_no_external_root"})
                    continue
                result = offload_candidate(fresh, home=home, external_root=external_root, registry=guardian.registry)
                if result["status"] in {"offloaded", "migrated_stub"}:
                    offloaded.append(result)
                else:
                    skipped.append(result)
            else:
                skipped.append({"path": path_text, "status": "skipped_non_mutating_action"})
        except Exception as exc:  # noqa: BLE001
            errors.append({"path": path_text, "status": "error", "error": str(exc)})

    if external_root is not None:
        save_registry(guardian.registry, registry_path, external_root if settings["include_external"] else None)

    result = {
        "schema": APPLY_V2_SCHEMA,
        "applied_at": isoformat(now_utc()),
        "actions_requested": requested_actions,
        "deleted": deleted,
        "offloaded": offloaded,
        "skipped": skipped,
        "errors": errors,
    }
    return (0 if not errors else 1), result


def run_audit(args: argparse.Namespace) -> int:
    home = Path.home().expanduser().resolve()
    cwd = Path(args.workspace).expanduser().resolve() if args.workspace else Path.cwd().resolve()
    json_out = Path(args.json_out or args.output).expanduser().resolve()
    md_out = Path(args.md_out).expanduser().resolve() if args.md_out else None
    cleanup_out = Path(args.cleanup_script_out).expanduser().resolve() if args.cleanup_script_out else None
    external_root = Path(args.external_root).expanduser().resolve() if args.external_root else None
    roots = [Path(item).expanduser().resolve() for item in args.roots] if args.roots else default_roots(home)
    report, guardian = audit_with_options(
        home=home,
        cwd=cwd,
        json_out=json_out,
        md_out=md_out,
        cleanup_script_out=cleanup_out,
        roots=roots,
        external_root=external_root,
        include_external=args.include_external,
        registry_path=Path(args.registry_path).expanduser().resolve(),
        cache_policy=args.cache_policy,
        hot_days=args.hot_days,
        warm_days=args.warm_days,
        thread_id=args.thread_id,
        import_legacy=args.import_legacy,
    )
    if args.import_legacy and external_root is not None:
        save_registry(guardian.registry, Path(args.registry_path).expanduser().resolve(), external_root if args.include_external else None)
    print(f"Wrote storage guardian report: {json_out}")
    if md_out:
        print(f"Wrote markdown report: {md_out}")
    if cleanup_out:
        print(f"Wrote cleanup script: {cleanup_out}")
    print("Summary by action:")
    for action in [DELETE_NOW, OFFLOAD_MANIFEST, REVIEW_FIRST, PROTECT]:
        print(f"  {action}: {human_bytes(int(report['summary_by_action'][action + '_bytes']))}")
    return 0


def run_apply(args: argparse.Namespace) -> int:
    plan_path = Path(args.plan).expanduser().resolve()
    if not plan_path.exists():
        print(f"Plan not found: {plan_path}", file=sys.stderr)
        return 2
    plan = json.loads(plan_path.read_text())
    actions = [item.strip() for item in args.actions.split(",") if item.strip()]
    code, result = apply_plan(plan, requested_actions=actions, confirm=args.confirm)
    output_path = Path(args.output).expanduser().resolve() if args.output else plan_path.with_name(plan_path.stem + ".apply_result.json")
    output_path.write_text(json.dumps(result, indent=2) + "\n")
    print(f"Apply result written: {output_path}")
    return code


def run_restore(args: argparse.Namespace) -> int:
    registry_path = Path(args.registry_path).expanduser().resolve()
    external_root = Path(args.external_root).expanduser().resolve() if args.external_root else DEFAULT_EXTERNAL_ROOT
    registry = load_registry(registry_path, external_root)
    if args.confirm != "RESTORE":
        print("Pass --confirm RESTORE to execute.", file=sys.stderr)
        return 2
    entry = find_registry_entry(registry, str(Path(args.source_path).expanduser().resolve()))
    if entry is None:
        print(f"Registry entry not found for {args.source_path}", file=sys.stderr)
        return 2
    result = restore_entry(entry)
    if result["status"] != "restored":
        print(json.dumps(result, indent=2), file=sys.stderr)
        return 1
    save_registry(registry, registry_path, external_root)
    print(json.dumps(result, indent=2))
    return 0


def run_import_legacy(args: argparse.Namespace) -> int:
    home = Path.home().expanduser().resolve()
    external_root = Path(args.external_root).expanduser().resolve()
    registry_path = Path(args.registry_path).expanduser().resolve()
    registry = load_registry(registry_path, external_root)
    imports = import_legacy_archives(home=home, external_root=external_root, registry=registry)
    save_registry(registry, registry_path, external_root)
    print(json.dumps({"imported": imports, "entry_count": len(registry["entries"])}, indent=2))
    return 0


def run_offload_path(args: argparse.Namespace) -> int:
    if args.confirm != "OFFLOAD_PATH":
        print("Pass --confirm OFFLOAD_PATH to execute.", file=sys.stderr)
        return 2
    home = Path.home().expanduser().resolve()
    external_root = Path(args.external_root).expanduser().resolve()
    registry_path = Path(args.registry_path).expanduser().resolve()
    ensure_external_layout(external_root)
    registry = load_registry(registry_path, external_root)
    source = Path(args.source_path).expanduser().resolve()
    if not source.exists():
        print(f"Missing source path: {source}", file=sys.stderr)
        return 2
    relative = args.external_relative.strip("/")
    candidate = {
        "path": home_relative(source, home),
        "category": args.category,
        "source_type": "path",
        "temperature": COLD,
        "workspace": args.workspace,
        "thread_ids": [],
        "size_bytes": du_measure(source) or 0,
        "metadata": {},
    }
    external_path = external_root / relative
    external_path.parent.mkdir(parents=True, exist_ok=True)
    if external_path.exists():
        print(f"Destination already exists: {external_path}", file=sys.stderr)
        return 2
    shutil.move(str(source), str(external_path))
    entry = build_registry_entry(
        home=home,
        source_path=source,
        external_path=external_path,
        source_type="path",
        category=args.category,
        workspace=args.workspace,
        thread_ids=[],
        session_days=[],
        temperature_at_move=COLD,
        size_bytes=int(candidate["size_bytes"]),
        description=args.description,
    )
    if args.stub_mode == "sibling_notice":
        write_sibling_stub(source, entry)
    else:
        write_directory_stub(source, entry)
    upsert_registry_entry(registry, entry)
    save_registry(registry, registry_path, external_root)
    print(json.dumps({"status": "offloaded", "source_path": str(source), "external_path": str(external_path)}, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Dynamic, session-aware storage guardian")
    sub = parser.add_subparsers(dest="command", required=True)

    audit = sub.add_parser("audit", help="Generate a StorageGuardianPlanV2 report.")
    audit.add_argument("--workspace", default=os.getcwd(), help="Workspace root / current cwd for context.")
    audit.add_argument("--output", default="", help="Compatibility alias for --json-out.")
    audit.add_argument("--json-out", default="", help="Path for JSON report output.")
    audit.add_argument("--md-out", default="", help="Optional markdown report path.")
    audit.add_argument("--cleanup-script-out", default="", help="Optional delete-now cleanup script path.")
    audit.add_argument("--thread-id", default=None, help="Optional explicit thread id override.")
    audit.add_argument("--hot-days", type=int, default=14, help="Hot retention window in days.")
    audit.add_argument("--warm-days", type=int, default=45, help="Warm retention window in days.")
    audit.add_argument("--external-root", default=str(DEFAULT_EXTERNAL_ROOT), help="External SSD guardian root.")
    audit.add_argument("--include-external", action="store_true", help="Include external SSD volume and archive scan.")
    audit.add_argument("--import-legacy", action="store_true", help="Import compatible legacy cold-storage manifests into the registry.")
    audit.add_argument("--registry-path", default=str(DEFAULT_REGISTRY_PATH), help="Registry path.")
    audit.add_argument("--cache-policy", default="review_first", choices=("review_first", "cache_first"))
    audit.add_argument("--roots", nargs="*", help="Optional explicit roots to scan.")

    apply = sub.add_parser("apply", help="Apply delete_now and/or offload_manifest actions with revalidation.")
    apply.add_argument("--plan", required=True, help="Path to StorageGuardianPlanV2 JSON.")
    apply.add_argument("--actions", default=DELETE_NOW, help="Comma-separated actions to execute.")
    apply.add_argument("--confirm", default="", help="Must be APPLY to execute.")
    apply.add_argument("--output", default="", help="Optional path for apply result JSON.")

    restore = sub.add_parser("restore", help="Restore a manifest-only offloaded entry from the registry.")
    restore.add_argument("--source-path", required=True, help="Original source path.")
    restore.add_argument("--registry-path", default=str(DEFAULT_REGISTRY_PATH), help="Registry path.")
    restore.add_argument("--external-root", default=str(DEFAULT_EXTERNAL_ROOT), help="External SSD guardian root.")
    restore.add_argument("--confirm", default="", help="Must be RESTORE to execute.")

    import_legacy_parser = sub.add_parser("import-legacy", help="Import compatible legacy cold-storage trees into RegistryV2.")
    import_legacy_parser.add_argument("--registry-path", default=str(DEFAULT_REGISTRY_PATH), help="Registry path.")
    import_legacy_parser.add_argument("--external-root", default=str(DEFAULT_EXTERNAL_ROOT), help="External SSD guardian root.")

    offload_path = sub.add_parser("offload-path", help="Compatibility helper to offload a specific path with a local stub.")
    offload_path.add_argument("--external-root", default=str(DEFAULT_EXTERNAL_ROOT), help="External SSD guardian root.")
    offload_path.add_argument("--registry-path", default=str(DEFAULT_REGISTRY_PATH), help="Registry path.")
    offload_path.add_argument("--source-path", required=True, help="Absolute path to offload.")
    offload_path.add_argument("--external-relative", required=True, help="Destination relative to external root.")
    offload_path.add_argument("--category", required=True, help="Category recorded in registry.")
    offload_path.add_argument("--description", required=True, help="Human-readable description.")
    offload_path.add_argument("--workspace", default=None, help="Optional workspace name.")
    offload_path.add_argument("--stub-mode", default="directory", choices=("directory", "sibling_notice"))
    offload_path.add_argument("--confirm", default="", help="Must be OFFLOAD_PATH to execute.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "audit":
        if not args.json_out and not args.output:
            parser.error("audit requires --json-out or --output")
        return run_audit(args)
    if args.command == "apply":
        return run_apply(args)
    if args.command == "restore":
        return run_restore(args)
    if args.command == "import-legacy":
        return run_import_legacy(args)
    if args.command == "offload-path":
        return run_offload_path(args)
    parser.error(f"Unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
