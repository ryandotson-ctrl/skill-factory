#!/usr/bin/env python3
"""Build a deterministic technology inventory with active-surface classification."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

try:
    import tomllib  # Python 3.11+
except Exception:  # pragma: no cover
    tomllib = None


MANIFEST_FILES = {
    "Package.swift",
    "package.json",
    "requirements.txt",
    "requirements-dev.txt",
    "requirements.in",
    "pyproject.toml",
    "poetry.lock",
    "Pipfile",
    "Pipfile.lock",
    "go.mod",
    "Cargo.toml",
    "Gemfile",
    "Gemfile.lock",
    "pom.xml",
    "build.gradle",
}

SKIP_DIR_EXACT = {
    ".git",
    ".hg",
    ".svn",
    ".next",
    ".build",
    ".swiftpm",
    "deriveddata",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    "dist",
    "build",
    ".cache",
    "site-packages",
}

SKIP_DIR_PREFIX = {
    "venv",
    ".venv",
}

TEXT_SCAN_EXTENSIONS = {
    ".md",
    ".txt",
    ".swift",
    ".py",
    ".sh",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
}

KNOWN_FRAMEWORKS = {
    "react",
    "next",
    "vue",
    "nuxt",
    "svelte",
    "angular",
    "django",
    "fastapi",
    "flask",
    "rails",
    "nestjs",
    "express",
    "spring-boot",
    "tailwindcss",
    "laravel",
}

MLX_PACKAGES = {
    "mlx",
    "mlx-lm",
    "mlx-vlm",
    "mlx-embeddings",
}

VERSION_COMMANDS: List[Tuple[str, List[str]]] = [
    ("swift", ["swift", "--version"]),
    ("xcodebuild", ["xcodebuild", "-version"]),
    ("xcodegen", ["xcodegen", "--version"]),
    ("xcbeautify", ["xcbeautify", "--version"]),
    ("xcrun", ["xcrun", "--version"]),
    ("clang", ["clang", "--version"]),
    ("node", ["node", "-v"]),
    ("npm", ["npm", "-v"]),
    ("pnpm", ["pnpm", "-v"]),
    ("yarn", ["yarn", "-v"]),
    ("python3", ["python3", "--version"]),
    ("pip", ["pip", "--version"]),
    ("uv", ["uv", "--version"]),
    ("poetry", ["poetry", "--version"]),
    ("go", ["go", "version"]),
    ("rustc", ["rustc", "--version"]),
    ("cargo", ["cargo", "--version"]),
    ("java", ["java", "-version"]),
    ("ruby", ["ruby", "--version"]),
    ("gem", ["gem", "--version"]),
    ("brew", ["brew", "--version"]),
    ("gh", ["gh", "--version"]),
    ("docker", ["docker", "--version"]),
    ("codex", ["codex", "--version"]),
]

SEMVER_PATTERN = re.compile(r"(\d+)\.(\d+)\.(\d+)")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def is_skipped_dir(name: str) -> bool:
    lowered = name.strip().lower()
    if lowered in SKIP_DIR_EXACT:
        return True
    if any(lowered.startswith(prefix) for prefix in SKIP_DIR_PREFIX):
        return True
    return False


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build technology inventory for tech auditor.")
    parser.add_argument("--workspace-root", default=".", help="Primary workspace root.")
    parser.add_argument(
        "--extra-workspace",
        action="append",
        default=[],
        help="Additional workspace root(s) for cross-workspace inventory.",
    )
    parser.add_argument(
        "--mode",
        choices=["active-runtime-first", "all-manifests"],
        default="active-runtime-first",
        help="Surface selection mode.",
    )
    parser.add_argument(
        "--active-window-days",
        type=int,
        default=45,
        help="Recency window in days used when runtime signals are ambiguous.",
    )
    parser.add_argument(
        "--include-legacy-appendix",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Include legacy/non-primary surfaces in output.",
    )
    parser.add_argument("--output", required=True, help="Output JSON path.")
    return parser.parse_args()


def run_version(cmd: List[str]) -> Dict[str, Any]:
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10, check=False)
    except Exception:
        return {"available": False, "version": "", "raw": ""}

    raw = (proc.stdout or proc.stderr or "").strip()
    line = raw.splitlines()[0].strip() if raw else ""
    return {"available": proc.returncode == 0, "version": line, "raw": raw}


def scan_global_tools() -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for component, cmd in VERSION_COMMANDS:
        row = run_version(cmd)
        out.append(
            {
                "component": component,
                "command": " ".join(cmd),
                "available": bool(row["available"]),
                "version": str(row["version"]),
            }
        )
    return out


def unique_paths(paths: Iterable[Path]) -> List[Path]:
    seen: Set[str] = set()
    out: List[Path] = []
    for path in paths:
        canonical = str(path.resolve())
        if canonical in seen:
            continue
        seen.add(canonical)
        out.append(path.resolve())
    return out


def iter_manifest_files(workspace_root: Path) -> Iterable[Path]:
    for dirpath, dirnames, filenames in os.walk(workspace_root):
        dirnames[:] = [d for d in dirnames if not is_skipped_dir(d)]
        current = Path(dirpath)
        for filename in filenames:
            if filename not in MANIFEST_FILES:
                continue
            yield current / filename


def normalize_dep_name(value: str) -> str:
    name = value.strip().lower()
    if not name:
        return ""
    name = re.split(r"[<>=!~ ;\[]", name, maxsplit=1)[0].strip()
    return name


def parse_requirements(path: Path, dep_map: Dict[str, Dict[str, Any]], source_prefix: str, surface_id: str) -> None:
    for raw in read_text(path).splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith(("-", "--")):
            continue
        name = normalize_dep_name(line)
        if not name:
            continue
        add_dep(dep_map, name, line, f"{source_prefix}:{path.name}", surface_id)


def parse_package_json(path: Path, dep_map: Dict[str, Dict[str, Any]], source_prefix: str, surface_id: str) -> None:
    try:
        payload = json.loads(read_text(path))
    except Exception:
        return
    if not isinstance(payload, dict):
        return

    for field in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
        table = payload.get(field, {})
        if not isinstance(table, dict):
            continue
        for dep_name, dep_version in table.items():
            name = normalize_dep_name(str(dep_name))
            if not name:
                continue
            add_dep(dep_map, name, str(dep_version), f"{source_prefix}:{path.name}:{field}", surface_id)


def parse_pyproject(path: Path, dep_map: Dict[str, Dict[str, Any]], source_prefix: str, surface_id: str) -> None:
    if tomllib is None:
        return
    try:
        payload = tomllib.loads(read_text(path))
    except Exception:
        return
    if not isinstance(payload, dict):
        return

    project = payload.get("project", {})
    if isinstance(project, dict):
        deps = project.get("dependencies", [])
        if isinstance(deps, list):
            for item in deps:
                hint = str(item).strip()
                name = normalize_dep_name(hint)
                if name:
                    add_dep(dep_map, name, hint, f"{source_prefix}:pyproject:project.dependencies", surface_id)

    tool = payload.get("tool", {})
    if isinstance(tool, dict):
        poetry = tool.get("poetry", {})
        if isinstance(poetry, dict):
            deps = poetry.get("dependencies", {})
            if isinstance(deps, dict):
                for dep_name, dep_version in deps.items():
                    if str(dep_name).lower() == "python":
                        continue
                    name = normalize_dep_name(str(dep_name))
                    if name:
                        add_dep(
                            dep_map,
                            name,
                            str(dep_version),
                            f"{source_prefix}:pyproject:tool.poetry.dependencies",
                            surface_id,
                        )


def parse_go_mod(path: Path, dep_map: Dict[str, Dict[str, Any]], source_prefix: str, surface_id: str) -> None:
    for raw in read_text(path).splitlines():
        line = raw.strip()
        if not line or line.startswith("//"):
            continue
        if line.startswith("require "):
            parts = line.split()
            if len(parts) >= 3:
                name = normalize_dep_name(parts[1])
                if name:
                    add_dep(dep_map, name, parts[2], f"{source_prefix}:go.mod", surface_id)


def parse_cargo_toml(path: Path, dep_map: Dict[str, Dict[str, Any]], source_prefix: str, surface_id: str) -> None:
    if tomllib is None:
        return
    try:
        payload = tomllib.loads(read_text(path))
    except Exception:
        return
    if not isinstance(payload, dict):
        return

    for section in ("dependencies", "dev-dependencies", "build-dependencies"):
        table = payload.get(section, {})
        if not isinstance(table, dict):
            continue
        for dep_name, dep_version in table.items():
            name = normalize_dep_name(str(dep_name))
            if not name:
                continue
            hint = str(dep_version) if isinstance(dep_version, str) else ""
            add_dep(dep_map, name, hint, f"{source_prefix}:Cargo.toml:{section}", surface_id)


def parse_gemfile(path: Path, dep_map: Dict[str, Dict[str, Any]], source_prefix: str, surface_id: str) -> None:
    pattern = re.compile(r'^\s*gem\s+["\']([^"\']+)["\']\s*(?:,\s*["\']([^"\']+)["\'])?')
    for raw in read_text(path).splitlines():
        match = pattern.search(raw)
        if not match:
            continue
        name = normalize_dep_name(match.group(1))
        if not name:
            continue
        hint = match.group(2) or ""
        add_dep(dep_map, name, hint, f"{source_prefix}:Gemfile", surface_id)


def parse_manifest(path: Path, dep_map: Dict[str, Dict[str, Any]], source_prefix: str, surface_id: str) -> None:
    filename = path.name
    if filename == "package.json":
        parse_package_json(path, dep_map, source_prefix, surface_id)
    elif filename.startswith("requirements"):
        parse_requirements(path, dep_map, source_prefix, surface_id)
    elif filename == "pyproject.toml":
        parse_pyproject(path, dep_map, source_prefix, surface_id)
    elif filename == "go.mod":
        parse_go_mod(path, dep_map, source_prefix, surface_id)
    elif filename == "Cargo.toml":
        parse_cargo_toml(path, dep_map, source_prefix, surface_id)
    elif filename == "Gemfile":
        parse_gemfile(path, dep_map, source_prefix, surface_id)


def add_dep(dep_map: Dict[str, Dict[str, Any]], name: str, version_hint: str, source: str, surface_id: str) -> None:
    row = dep_map.setdefault(
        name,
        {
            "name": name,
            "version_hint": "",
            "sources": set(),
            "surface_ids": set(),
        },
    )
    if version_hint and not row["version_hint"]:
        row["version_hint"] = version_hint.strip()
    row["sources"].add(source)
    row["surface_ids"].add(surface_id)


def derive_surface_root(manifest: Path, workspace_root: Path) -> Path:
    rel = manifest.relative_to(workspace_root)
    parts = list(rel.parts)

    anchored = {"backend", "frontend", "mhon-app", "pfe-macos"}
    for idx, part in enumerate(parts):
        if part in anchored:
            return workspace_root.joinpath(*parts[: idx + 1])

    if manifest.name == "Package.swift":
        return manifest.parent

    if manifest.name.startswith("requirements"):
        return manifest.parent

    if manifest.name == "pyproject.toml":
        parent = manifest.parent
        backend_main = parent / "backend" / "main.py"
        if backend_main.is_file():
            return parent / "backend"

    return manifest.parent


def detect_surface_kind(surface_root: Path) -> str:
    if (surface_root / "Package.swift").is_file() or list(surface_root.glob("*.xcodeproj")):
        return "swift_macos"
    if (surface_root / "backend" / "main.py").is_file() or (surface_root / "main.py").is_file():
        return "python_backend"
    if (surface_root / "package.json").is_file():
        return "web_app"
    if (surface_root / "pyproject.toml").is_file() or (surface_root / "requirements.txt").is_file():
        return "python_project"
    return "general"


def runtime_signal_for_surface(surface_root: Path, kind: str) -> Tuple[int, List[str]]:
    score = 0
    signals: List[str] = []

    if kind == "swift_macos":
        if (surface_root / "Package.swift").is_file():
            score += 3
            signals.append("swift_package_manifest")
        if list(surface_root.glob("*.xcodeproj")):
            score += 2
            signals.append("xcode_project")
        if (surface_root / "Sources").is_dir():
            score += 1
            signals.append("swift_sources")

    if kind in {"python_backend", "python_project"}:
        if (surface_root / "backend" / "main.py").is_file() or (surface_root / "main.py").is_file():
            score += 3
            signals.append("python_entrypoint")
        if (surface_root / "requirements.txt").is_file() or (surface_root / "pyproject.toml").is_file():
            score += 1
            signals.append("python_dependency_manifest")

    if kind == "web_app":
        pkg = surface_root / "package.json"
        if pkg.is_file():
            score += 1
            signals.append("node_package_manifest")
            try:
                payload = json.loads(read_text(pkg))
            except Exception:
                payload = {}
            scripts = payload.get("scripts", {}) if isinstance(payload, dict) else {}
            if isinstance(scripts, dict):
                if "dev" in scripts or "start" in scripts:
                    score += 1
                    signals.append("web_runtime_script")
        if (surface_root / "app").is_dir() or (surface_root / "src").is_dir():
            score += 1
            signals.append("web_source_tree")

    return score, sorted(set(signals))


def git_last_commit_epoch(workspace_root: Path, target_path: Path) -> Optional[int]:
    rel = str(target_path.relative_to(workspace_root))
    cmd = ["git", "-C", str(workspace_root), "log", "-1", "--format=%ct", "--", rel]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        return None
    raw = proc.stdout.strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def scan_text_files(root: Path) -> Iterable[Path]:
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not is_skipped_dir(d)]
        base = Path(dirpath)
        for filename in filenames:
            path = base / filename
            if path.suffix.lower() not in TEXT_SCAN_EXTENSIONS:
                continue
            try:
                if path.stat().st_size > 1_000_000:
                    continue
            except OSError:
                continue
            yield path


def build_surface_reference_graph(workspace_root: Path, surfaces: Dict[str, Dict[str, Any]]) -> Dict[str, Set[str]]:
    graph: Dict[str, Set[str]] = {surface_id: set() for surface_id in surfaces.keys()}
    rel_map = {surface_id: str(info["root"].relative_to(workspace_root)).replace("\\", "/") for surface_id, info in surfaces.items()}

    for surface_id, info in surfaces.items():
        root = info["root"]
        for text_file in scan_text_files(root):
            text = read_text(text_file)
            if not text:
                continue
            for other_id, other_rel in rel_map.items():
                if other_id == surface_id:
                    continue
                if other_rel and other_rel in text:
                    graph[surface_id].add(other_id)

    return graph


def classify_surfaces(
    *,
    workspace_root: Path,
    surfaces: Dict[str, Dict[str, Any]],
    mode: str,
    active_window_days: int,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    now_dt = datetime.now(timezone.utc)
    graph = build_surface_reference_graph(workspace_root, surfaces)

    items: List[Dict[str, Any]] = []
    for surface_id, info in surfaces.items():
        last_commit_epoch = git_last_commit_epoch(workspace_root, info["root"])
        last_commit_utc = None
        days_since = None
        if last_commit_epoch is not None:
            commit_dt = datetime.fromtimestamp(last_commit_epoch, tz=timezone.utc)
            last_commit_utc = commit_dt.isoformat().replace("+00:00", "Z")
            days_since = (now_dt - commit_dt).days

        runtime_score = int(info.get("runtime_score", 0))
        outbound_refs = sorted(graph.get(surface_id, set()))
        launch_ref_score = len(outbound_refs)

        item = {
            "surface_id": surface_id,
            "root": str(info["root"]),
            "kind": info.get("kind", "general"),
            "runtime_score": runtime_score,
            "runtime_signals": info.get("runtime_signals", []),
            "launch_ref_score": launch_ref_score,
            "outbound_surface_refs": outbound_refs,
            "manifest_files": sorted(info.get("manifest_files", [])),
            "last_commit_utc": last_commit_utc,
            "days_since_last_commit": days_since,
            "classification": "legacy",
            "surface_reason": "not_selected",
        }
        items.append(item)

    if mode == "all-manifests":
        for item in items:
            item["classification"] = "active"
            item["surface_reason"] = "all_manifests_mode"
        return sorted(items, key=lambda x: x["surface_id"]), []

    active_ids: Set[str] = set()

    # Stage 1: runtime-entrypoint seeds (high-confidence executables).
    for item in items:
        days = item["days_since_last_commit"]
        recent_enough = days is None or days <= active_window_days
        if item["runtime_score"] >= 4 and recent_enough:
            active_ids.add(item["surface_id"])
            item["surface_reason"] = "runtime_entrypoint_seed"

    # Stage 2: include direct dependencies in runtime graph from active seeds.
    if active_ids:
        for seed in list(active_ids):
            for linked in graph.get(seed, set()):
                linked_item = next((i for i in items if i["surface_id"] == linked), None)
                if linked_item is None:
                    continue
                if linked_item["runtime_score"] >= 2:
                    active_ids.add(linked)
                    if linked_item["surface_reason"] == "not_selected":
                        linked_item["surface_reason"] = f"referenced_by:{seed}"

    # Stage 3: recency fallback if still ambiguous/no active seed.
    if not active_ids and items:
        candidates = sorted(
            items,
            key=lambda i: (
                -i["runtime_score"],
                i["days_since_last_commit"] if i["days_since_last_commit"] is not None else 10**9,
                i["surface_id"],
            ),
        )
        chosen = candidates[0]
        active_ids.add(chosen["surface_id"])
        chosen["surface_reason"] = "fallback_primary_no_runtime_seed"

    active: List[Dict[str, Any]] = []
    legacy: List[Dict[str, Any]] = []
    for item in items:
        if item["surface_id"] in active_ids:
            item["classification"] = "active"
            active.append(item)
        else:
            days = item["days_since_last_commit"]
            if days is not None and days > active_window_days:
                item["surface_reason"] = f"legacy_no_recent_activity_gt_{active_window_days}d"
            elif item["surface_reason"] == "not_selected":
                item["surface_reason"] = "legacy_not_on_active_entrypoint_path"
            legacy.append(item)

    active = sorted(active, key=lambda x: x["surface_id"])
    legacy = sorted(legacy, key=lambda x: x["surface_id"])
    return active, legacy


def infer_frameworks(dep_names: Iterable[str]) -> List[str]:
    found: Set[str] = set()
    for dep in dep_names:
        key = dep.lower()
        for framework in KNOWN_FRAMEWORKS:
            if framework == key or key.startswith(f"{framework}-") or framework in key:
                found.add(framework)
    return sorted(found)


def surface_id_from_root(workspace_root: Path, root: Path) -> str:
    rel = str(root.relative_to(workspace_root)).replace("\\", "/")
    return rel if rel else "."


def pypi_latest_version(package: str) -> Dict[str, Any]:
    url = f"https://pypi.org/pypi/{package}/json"
    req = urllib.request.Request(url, headers={"User-Agent": "tech-auditor/1.3"})
    try:
        with urllib.request.urlopen(req, timeout=12) as response:
            payload = json.loads(response.read().decode("utf-8", "replace"))
        latest = str(payload.get("info", {}).get("version", "")).strip()
        return {
            "latest": latest,
            "source": url,
            "source_date": now_iso(),
            "evidence_quality": "high",
            "claim_tag": "[FACT]",
        }
    except urllib.error.HTTPError as exc:
        return {
            "latest": "",
            "source": url,
            "source_date": now_iso(),
            "evidence_quality": "low",
            "claim_tag": "[ASSUMPTION]",
            "error": f"http_error:{exc.code}",
        }
    except Exception as exc:  # pragma: no cover
        return {
            "latest": "",
            "source": url,
            "source_date": now_iso(),
            "evidence_quality": "low",
            "claim_tag": "[ASSUMPTION]",
            "error": str(exc),
        }


def extract_semver(text: str) -> str:
    match = SEMVER_PATTERN.search(text or "")
    if not match:
        return ""
    return ".".join(match.groups())


def classify_freshness(local_hint: str, latest: str) -> str:
    local = extract_semver(local_hint)
    remote = extract_semver(latest)
    if not local or not remote:
        return "unknown"
    a = tuple(int(v) for v in local.split("."))
    b = tuple(int(v) for v in remote.split("."))
    if a == b:
        return "fresh"
    if a[0] < b[0]:
        return "critical"
    return "stale"


def collect_mlx_freshness(dep_map: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    names = sorted([name for name in dep_map.keys() if name in MLX_PACKAGES or name.startswith("mlx-")])
    for name in names:
        dep = dep_map[name]
        latest = pypi_latest_version(name)
        status = classify_freshness(dep.get("version_hint", ""), latest.get("latest", ""))
        rows.append(
            {
                "component": name,
                "local_version_hint": dep.get("version_hint", ""),
                "latest": latest.get("latest", ""),
                "status": status,
                "source": latest.get("source", ""),
                "source_date": latest.get("source_date", ""),
                "evidence_quality": latest.get("evidence_quality", "low"),
                "claim_tag": latest.get("claim_tag", "[ASSUMPTION]"),
                "error": latest.get("error", ""),
            }
        )
    return rows


def scan_workspace(
    *,
    workspace_root: Path,
    mode: str,
    active_window_days: int,
    include_legacy_appendix: bool,
) -> Dict[str, Any]:
    manifest_paths = sorted(iter_manifest_files(workspace_root), key=lambda p: str(p))

    surfaces: Dict[str, Dict[str, Any]] = {}
    for manifest in manifest_paths:
        surface_root = derive_surface_root(manifest, workspace_root)
        surface_id = surface_id_from_root(workspace_root, surface_root)
        item = surfaces.setdefault(
            surface_id,
            {
                "root": surface_root,
                "kind": detect_surface_kind(surface_root),
                "manifest_files": [],
            },
        )
        rel_manifest = str(manifest.relative_to(workspace_root)).replace("\\", "/")
        item["manifest_files"].append(rel_manifest)

    for surface in surfaces.values():
        runtime_score, runtime_signals = runtime_signal_for_surface(surface["root"], surface["kind"])
        surface["runtime_score"] = runtime_score
        surface["runtime_signals"] = runtime_signals

    active_surfaces, legacy_surfaces = classify_surfaces(
        workspace_root=workspace_root,
        surfaces=surfaces,
        mode=mode,
        active_window_days=active_window_days,
    )
    active_ids = {row["surface_id"] for row in active_surfaces}

    dep_map: Dict[str, Dict[str, Any]] = {}
    surface_manifests: Dict[str, List[str]] = {surface_id: [] for surface_id in surfaces.keys()}

    for manifest in manifest_paths:
        surface_root = derive_surface_root(manifest, workspace_root)
        surface_id = surface_id_from_root(workspace_root, surface_root)
        rel_manifest = str(manifest.relative_to(workspace_root)).replace("\\", "/")
        surface_manifests.setdefault(surface_id, []).append(rel_manifest)
        parse_manifest(manifest, dep_map, source_prefix=surface_id, surface_id=surface_id)

    dependencies: List[Dict[str, Any]] = []
    active_dependencies: List[Dict[str, Any]] = []
    for name in sorted(dep_map.keys()):
        row = dep_map[name]
        item = {
            "name": row["name"],
            "version_hint": row["version_hint"],
            "sources": sorted(row["sources"]),
            "surface_ids": sorted(row["surface_ids"]),
            "is_active_surface_dependency": any(surface_id in active_ids for surface_id in row["surface_ids"]),
        }
        dependencies.append(item)
        if item["is_active_surface_dependency"]:
            active_dependencies.append(item)

    frameworks_all = infer_frameworks([item["name"] for item in dependencies])
    frameworks_active = infer_frameworks([item["name"] for item in active_dependencies])

    def summarize_surfaces(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for row in rows:
            sid = row["surface_id"]
            out.append(
                {
                    **row,
                    "manifest_files": sorted(surface_manifests.get(sid, row.get("manifest_files", []))),
                }
            )
        return out

    active_out = summarize_surfaces(active_surfaces)
    legacy_out = summarize_surfaces(legacy_surfaces)

    mlx_freshness = collect_mlx_freshness(dep_map)

    payload = {
        "root": str(workspace_root),
        "mode": mode,
        "active_window_days": active_window_days,
        "include_legacy_appendix": include_legacy_appendix,
        "surface_count": len(surfaces),
        "active_surfaces": active_out,
        "legacy_surfaces": legacy_out if include_legacy_appendix else [],
        "frameworks": frameworks_all,
        "active_frameworks": frameworks_active,
        "dependency_count": len(dependencies),
        "active_dependency_count": len(active_dependencies),
        "manifest_files": sorted(str(path.relative_to(workspace_root)).replace("\\", "/") for path in manifest_paths),
        "dependencies": dependencies,
        "active_dependencies": active_dependencies,
        "mlx_freshness": mlx_freshness,
    }
    return payload


def main() -> None:
    args = parse_args()

    primary = Path(args.workspace_root).expanduser().resolve()
    extras = [Path(item).expanduser().resolve() for item in args.extra_workspace]
    workspaces = [path for path in unique_paths([primary, *extras]) if path.exists() and path.is_dir()]

    workspace_payloads = [
        scan_workspace(
            workspace_root=root,
            mode=args.mode,
            active_window_days=max(1, int(args.active_window_days)),
            include_legacy_appendix=bool(args.include_legacy_appendix),
        )
        for root in workspaces
    ]

    active_surfaces_all: List[Dict[str, Any]] = []
    legacy_surfaces_all: List[Dict[str, Any]] = []
    for ws in workspace_payloads:
        for row in ws.get("active_surfaces", []):
            active_surfaces_all.append({"workspace_root": ws["root"], **row})
        for row in ws.get("legacy_surfaces", []):
            legacy_surfaces_all.append({"workspace_root": ws["root"], **row})

    payload = {
        "generated_at": now_iso(),
        "version": "1.3.0",
        "mode": args.mode,
        "active_window_days": max(1, int(args.active_window_days)),
        "include_legacy_appendix": bool(args.include_legacy_appendix),
        "workspace_count": len(workspaces),
        "global_tools": scan_global_tools(),
        "active_surfaces": active_surfaces_all,
        "legacy_surfaces": legacy_surfaces_all if args.include_legacy_appendix else [],
        "workspaces": workspace_payloads,
    }

    output_path = Path(args.output).expanduser()
    if not output_path.is_absolute():
        output_path = (primary / output_path).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
