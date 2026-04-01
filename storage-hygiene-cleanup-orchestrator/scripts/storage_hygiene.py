#!/usr/bin/env python3
"""Guarded storage audit and cleanup for model-heavy workflows."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

MODEL_ID_RE = re.compile(r"([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)")
INCLUDE_FILE_RE = re.compile(r"\.(ya?ml|json|jsonl|env|toml|ini|txt|md)$", re.IGNORECASE)
MODEL_HINT_RE = re.compile(r"(model|draft|hf)", re.IGNORECASE)
BAD_OWNER_TOKENS = {
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
BAD_REPO_SUFFIXES = (".yaml", ".yml", ".json", ".jsonl", ".py", ".md", ".txt", ".toml", ".ini")


@dataclass
class Candidate:
    path: str
    kind: str
    tier: str
    size_bytes: int
    size_gb: float
    reason: str
    model_id: Optional[str] = None
    link_target: Optional[str] = None

    def to_dict(self) -> Dict[str, object]:
        return {
            "path": self.path,
            "kind": self.kind,
            "tier": self.tier,
            "size_bytes": self.size_bytes,
            "size_gb": round(self.size_gb, 3),
            "model_id": self.model_id,
            "link_target": self.link_target,
            "reason": self.reason,
        }


def now_utc_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def parse_tiers(raw: str) -> List[str]:
    tiers = [x.strip() for x in raw.split(",") if x.strip()]
    valid = {"safe_now", "conditional", "keep"}
    bad = [t for t in tiers if t not in valid]
    if bad:
        raise ValueError(f"Invalid tiers: {bad}. Valid: {sorted(valid)}")
    return tiers


def parse_kinds(raw: str) -> Optional[Set[str]]:
    if not raw.strip():
        return None
    kinds = {x.strip() for x in raw.split(",") if x.strip()}
    valid = {
        "hf_repo",
        "workspace_venv",
        "workspace_artifacts",
        "mlxmodels_repo",
        "models_repo",
        "mlx_hidden_repo",
        "symlink_alias",
    }
    bad = sorted(kinds - valid)
    if bad:
        raise ValueError(f"Invalid kinds: {bad}. Valid: {sorted(valid)}")
    return kinds


def shell_size_bytes(path: Path) -> int:
    try:
        out = subprocess.check_output(["du", "-sk", str(path)], stderr=subprocess.DEVNULL, text=True)
        kb = int(out.split()[0])
        return kb * 1024
    except Exception:
        total = 0
        if path.is_file():
            return path.stat().st_size
        for root, _, files in os.walk(path, followlinks=False):
            for file_name in files:
                try:
                    total += (Path(root) / file_name).stat().st_size
                except OSError:
                    pass
        return total


def to_gb(size_bytes: int) -> float:
    return size_bytes / (1024 ** 3)


def discover_keep_models(workspace: Optional[Path]) -> Set[str]:
    keep: Set[str] = set()
    if workspace is None or not workspace.exists():
        return keep

    roots = [workspace / "configs", workspace / "src", workspace / ".env", workspace / ".env.example"]

    for root in roots:
        if not root.exists():
            continue
        files: Iterable[Path]
        if root.is_file():
            files = [root]
        else:
            files = [
                p
                for p in root.rglob("*")
                if p.is_file() and INCLUDE_FILE_RE.search(p.name) and ".venv" not in p.as_posix()
            ]

        for file_path in files:
            try:
                text = file_path.read_text(errors="ignore")
            except OSError:
                continue
            for line in text.splitlines():
                if not MODEL_HINT_RE.search(line):
                    continue
                for match in MODEL_ID_RE.findall(line):
                    if is_plausible_model_id(match):
                        keep.add(match)
    return keep


def is_plausible_model_id(value: str) -> bool:
    if value.count("/") != 1:
        return False
    owner, repo = value.split("/", 1)
    if not owner or not repo:
        return False
    if owner in BAD_OWNER_TOKENS:
        return False
    if len(repo) < 3:
        return False
    if repo.endswith(BAD_REPO_SUFFIXES):
        return False
    return True


def hf_dirname_to_model_id(dirname: str) -> Optional[str]:
    if not dirname.startswith("models--"):
        return None
    payload = dirname[len("models--") :]
    parts = payload.split("--")
    if len(parts) < 2:
        return None
    owner = parts[0]
    repo = "--".join(parts[1:])
    return f"{owner}/{repo}"


def model_id_to_hf_dirname(model_id: str) -> str:
    owner, repo = model_id.split("/", 1)
    return f"models--{owner}--{repo}"


def basename_in_keep(path: Path, keep_models: Set[str]) -> Optional[str]:
    base = path.name
    for model_id in keep_models:
        if base == model_id.split("/", 1)[1]:
            return model_id
    return None


def classify_hf_repo(path: Path, keep_models: Set[str], tiny_threshold_bytes: int) -> Candidate:
    model_id = hf_dirname_to_model_id(path.name)
    size_bytes = shell_size_bytes(path)
    size_gb = to_gb(size_bytes)

    if model_id and model_id in keep_models:
        tier = "keep"
        reason = "Referenced by workspace config/env allowlist"
    elif size_bytes <= tiny_threshold_bytes:
        tier = "safe_now"
        reason = "Tiny placeholder cache entry"
    else:
        tier = "conditional"
        reason = "Not referenced by active workspace allowlist"

    return Candidate(
        path=str(path),
        kind="hf_repo",
        tier=tier,
        size_bytes=size_bytes,
        size_gb=size_gb,
        reason=reason,
        model_id=model_id,
    )


def classify_generic_dir(path: Path, kind: str, keep_models: Set[str], safe_artifacts: bool) -> Candidate:
    size_bytes = shell_size_bytes(path)
    size_gb = to_gb(size_bytes)

    matched = basename_in_keep(path, keep_models)
    if matched:
        return Candidate(
            path=str(path),
            kind=kind,
            tier="keep",
            size_bytes=size_bytes,
            size_gb=size_gb,
            reason="Directory name matches active keep-model",
            model_id=matched,
        )

    if kind == "workspace_artifacts":
        tier = "safe_now" if safe_artifacts else "conditional"
        reason = "Generated run artifacts; safe_now only when explicitly enabled"
    elif kind == "workspace_venv":
        tier = "conditional"
        reason = "Rebuildable virtual environment"
    else:
        tier = "conditional"
        reason = "Not matched to active keep-model"

    return Candidate(
        path=str(path),
        kind=kind,
        tier=tier,
        size_bytes=size_bytes,
        size_gb=size_gb,
        reason=reason,
        model_id=None,
    )


def classify_symlink_alias(path: Path, keep_models: Set[str]) -> Candidate:
    matched = basename_in_keep(path, keep_models)
    try:
        target = os.readlink(path)
    except OSError:
        target = None
    reason = (
        "Symlink alias to another model directory; deleting it frees negligible space "
        "and may break dependent apps"
    )
    return Candidate(
        path=str(path),
        kind="symlink_alias",
        tier="keep",
        size_bytes=0,
        size_gb=0.0,
        reason=reason,
        model_id=matched,
        link_target=target,
    )


def iter_mlx_model_dirs(root: Path) -> List[Path]:
    """
    Enumerate model directories in ~/MLXModels without descending into nested
    internal cache folders.
    """
    out: List[Path] = []
    for child in sorted(root.iterdir()):
        if not child.is_dir():
            continue
        subdirs = [p for p in sorted(child.iterdir()) if p.is_dir()]
        if subdirs:
            out.extend(subdirs)
        else:
            out.append(child)
    return out


def collect_candidates(
    workspace: Optional[Path],
    keep_models: Set[str],
    min_size_gb: float,
    include_workspace_artifacts_as_safe_now: bool,
) -> Tuple[List[Candidate], List[str]]:
    candidates: List[Candidate] = []
    scan_roots: List[str] = []
    min_bytes = int(min_size_gb * (1024 ** 3))

    hf_root = Path.home() / ".cache" / "huggingface" / "hub"
    if hf_root.exists():
        scan_roots.append(str(hf_root))
        for repo_dir in sorted(hf_root.glob("models--*")):
            if not repo_dir.is_dir():
                continue
            c = classify_hf_repo(repo_dir, keep_models, tiny_threshold_bytes=2 * 1024 * 1024)
            if c.size_bytes >= min_bytes:
                candidates.append(c)

    mlx_models_root = Path.home() / "MLXModels"
    if mlx_models_root.exists():
        scan_roots.append(str(mlx_models_root))
        for p in iter_mlx_model_dirs(mlx_models_root):
            c = classify_generic_dir(
                p,
                "mlxmodels_repo",
                keep_models,
                include_workspace_artifacts_as_safe_now,
            )
            if c.size_bytes >= min_bytes:
                candidates.append(c)

    models_root = Path.home() / "Models"
    if models_root.exists():
        scan_roots.append(str(models_root))
        for p in sorted(models_root.iterdir()):
            if p.is_dir():
                c = classify_generic_dir(
                    p,
                    "models_repo",
                    keep_models,
                    include_workspace_artifacts_as_safe_now,
                )
                if c.size_bytes >= min_bytes:
                    candidates.append(c)

    hidden_mlx_root = Path.home() / ".mlx_models"
    if hidden_mlx_root.exists():
        scan_roots.append(str(hidden_mlx_root))
        for p in sorted(hidden_mlx_root.iterdir()):
            if p.is_symlink():
                candidates.append(classify_symlink_alias(p, keep_models))
                continue
            if p.is_dir():
                c = classify_generic_dir(
                    p,
                    "mlx_hidden_repo",
                    keep_models,
                    include_workspace_artifacts_as_safe_now,
                )
                if c.size_bytes >= min_bytes:
                    candidates.append(c)

    if workspace and workspace.exists():
        venv = workspace / ".venv"
        if venv.exists():
            scan_roots.append(str(venv))
            c = classify_generic_dir(
                venv,
                "workspace_venv",
                keep_models,
                include_workspace_artifacts_as_safe_now,
            )
            if c.size_bytes >= min_bytes:
                candidates.append(c)

        artifacts = workspace / "artifacts"
        if artifacts.exists():
            scan_roots.append(str(artifacts))
            c = classify_generic_dir(
                artifacts,
                "workspace_artifacts",
                keep_models,
                include_workspace_artifacts_as_safe_now,
            )
            if c.size_bytes >= min_bytes:
                candidates.append(c)

    # Deduplicate path collisions, keeping the largest record.
    dedup: Dict[str, Candidate] = {}
    for c in candidates:
        prev = dedup.get(c.path)
        if prev is None or c.size_bytes > prev.size_bytes:
            dedup[c.path] = c
    return sorted(dedup.values(), key=lambda x: x.size_bytes, reverse=True), scan_roots


def summarize(candidates: Sequence[Candidate]) -> Dict[str, int]:
    totals = {"safe_now": 0, "conditional": 0, "keep": 0}
    for c in candidates:
        totals[c.tier] += c.size_bytes
    return totals


def write_json(path: Path, payload: Dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n")


def human_gb(num_bytes: int) -> str:
    return f"{to_gb(num_bytes):.2f} GB"


def run_audit(args: argparse.Namespace) -> int:
    workspace = Path(args.workspace).expanduser().resolve() if args.workspace else None

    keep_models = discover_keep_models(workspace)
    keep_models.update(args.keep_model)

    candidates, scan_roots = collect_candidates(
        workspace=workspace,
        keep_models=keep_models,
        min_size_gb=args.min_size_gb,
        include_workspace_artifacts_as_safe_now=args.artifacts_safe_now,
    )

    plan = {
        "schema": "StorageCleanupPlanV1",
        "generated_at": now_utc_iso(),
        "workspace": str(workspace) if workspace else None,
        "keep_models": sorted(keep_models),
        "scan_roots": scan_roots,
        "summary": {
            "total_candidates": len(candidates),
            "reclaimable_bytes_by_tier": summarize(candidates),
        },
        "candidates": [c.to_dict() for c in candidates],
    }

    out_path = Path(args.output).expanduser().resolve()
    write_json(out_path, plan)

    totals = plan["summary"]["reclaimable_bytes_by_tier"]
    print(f"Wrote cleanup plan: {out_path}")
    print("Reclaimable by tier:")
    print(f"  safe_now:    {human_gb(int(totals['safe_now']))}")
    print(f"  conditional: {human_gb(int(totals['conditional']))}")
    print(f"  keep:        {human_gb(int(totals['keep']))}")

    print("\nTop candidates:")
    for c in candidates[: args.top]:
        print(f"  [{c.tier:11}] {c.size_gb:7.2f} GB  {c.path}")

    return 0


def remove_path(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)
    else:
        raise FileNotFoundError(str(path))


def run_apply(args: argparse.Namespace) -> int:
    if args.confirm != "DELETE":
        print("Refusing apply. Pass --confirm DELETE to proceed.", file=sys.stderr)
        return 2

    tiers = parse_tiers(args.tiers)
    kinds_filter = parse_kinds(args.kinds)
    plan_path = Path(args.plan).expanduser().resolve()
    if not plan_path.exists():
        print(f"Plan not found: {plan_path}", file=sys.stderr)
        return 2

    plan = json.loads(plan_path.read_text())
    if plan.get("schema") != "StorageCleanupPlanV1":
        print("Unsupported plan schema.", file=sys.stderr)
        return 2

    deleted: List[Dict[str, object]] = []
    skipped: List[Dict[str, object]] = []
    errors: List[Dict[str, object]] = []
    reclaimed_bytes = 0

    for item in plan.get("candidates", []):
        path = Path(item["path"])
        tier = item.get("tier", "")
        size_bytes = int(item.get("size_bytes", 0))
        kind = item.get("kind", "")

        if tier not in tiers:
            skipped.append({"path": str(path), "tier": tier, "status": "skipped_not_in_tiers"})
            continue
        if kinds_filter is not None and kind not in kinds_filter:
            skipped.append({"path": str(path), "tier": tier, "status": "skipped_not_in_kinds"})
            continue
        if kind == "symlink_alias":
            skipped.append({"path": str(path), "tier": tier, "status": "skipped_symlink_alias_protected"})
            continue

        if not path.exists():
            skipped.append({"path": str(path), "tier": tier, "status": "skipped_missing"})
            continue

        try:
            remove_path(path)
            reclaimed_bytes += size_bytes
            deleted.append(
                {
                    "path": str(path),
                    "size_bytes": size_bytes,
                    "tier": tier,
                    "status": "deleted",
                }
            )
        except Exception as exc:  # noqa: BLE001
            errors.append({"path": str(path), "tier": tier, "status": "error", "error": str(exc)})

    result = {
        "schema": "StorageCleanupApplyResultV1",
        "applied_at": now_utc_iso(),
        "plan_path": str(plan_path),
        "tiers_requested": tiers,
        "deleted": deleted,
        "skipped": skipped,
        "errors": errors,
        "reclaimed_bytes": reclaimed_bytes,
    }

    if args.output:
        out = Path(args.output).expanduser().resolve()
    else:
        out = plan_path.with_name(plan_path.stem + ".apply_result.json")
    write_json(out, result)

    print(f"Apply result written: {out}")
    print(f"Deleted: {len(deleted)} entries")
    print(f"Skipped: {len(skipped)} entries")
    print(f"Errors:  {len(errors)} entries")
    print(f"Reclaimed: {human_gb(reclaimed_bytes)}")

    return 0 if not errors else 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Guarded storage audit and cleanup")
    sub = p.add_subparsers(dest="cmd", required=True)

    audit = sub.add_parser("audit", help="Generate a cleanup plan (no deletion)")
    audit.add_argument("--workspace", default=os.getcwd(), help="Workspace root for model discovery")
    audit.add_argument("--output", required=True, help="Path for StorageCleanupPlanV1 JSON")
    audit.add_argument("--keep-model", action="append", default=[], help="Explicit model ID to keep")
    audit.add_argument("--min-size-gb", type=float, default=0.0, help="Ignore entries smaller than this size")
    audit.add_argument("--top", type=int, default=25, help="Print top N largest candidates")
    audit.add_argument(
        "--artifacts-safe-now",
        action="store_true",
        help="Classify workspace artifacts as safe_now (default is conditional)",
    )

    apply = sub.add_parser("apply", help="Apply deletion from a generated plan")
    apply.add_argument("--plan", required=True, help="Path to StorageCleanupPlanV1 JSON")
    apply.add_argument("--tiers", default="safe_now", help="Comma-separated tiers to delete")
    apply.add_argument(
        "--kinds",
        default="",
        help="Optional comma-separated kind filter "
        "(hf_repo,workspace_venv,workspace_artifacts,mlxmodels_repo,models_repo,mlx_hidden_repo,symlink_alias)",
    )
    apply.add_argument("--confirm", default="", help="Must be exactly DELETE")
    apply.add_argument("--output", default="", help="Optional path for apply result JSON")

    return p


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.cmd == "audit":
        return run_audit(args)
    if args.cmd == "apply":
        return run_apply(args)
    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
