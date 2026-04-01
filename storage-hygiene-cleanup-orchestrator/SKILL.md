---
name: storage-hygiene-cleanup-orchestrator
description: Audit and reclaim disk space safely across project artifacts, virtual environments, and model caches (Hugging Face, MLXModels, local model folders). Use when SSD usage spikes, large model experiments leave residue, or the user asks what can be safely deleted. Supports dry-run cleanup plans, cold-storage manifests, reversible restore workflows, and symlink-aware model audits while preserving active model allowlists.
metadata:
  version: 1.3.0
  portability_tier: strict_zero_leak
  scope: global
---

# Storage Hygiene Cleanup Orchestrator

Run guarded storage cleanup in two phases: plan first, apply second.

## Quick Start

1. Audit and generate a cleanup plan JSON:
```bash
python3 scripts/storage_hygiene.py audit \
  --workspace "$PWD" \
  --output "$PWD/artifacts/storage_cleanup_plan.json"
```

2. Review tiered candidates in the plan:
- `safe_now`: low-risk deletions (e.g., stale artifacts, tiny placeholder cache dirs)
- `conditional`: reclaimable but may impact future runs (e.g., old model caches, `.venv`)
- `keep`: currently referenced or explicitly protected

3. Apply only reviewed tiers:
```bash
python3 scripts/storage_hygiene.py apply \
  --plan "$PWD/artifacts/storage_cleanup_plan.json" \
  --tiers safe_now \
  --confirm DELETE
```

4. Optional safety filter by candidate kind:
```bash
python3 scripts/storage_hygiene.py apply \
  --plan "$PWD/artifacts/storage_cleanup_plan.json" \
  --tiers conditional \
  --kinds hf_repo,mlxmodels_repo,models_repo \
  --confirm DELETE
```

## Workflow

1. Discover active model allowlist from workspace files.
2. Scan common high-usage roots:
- `<workspace>/.venv`
- `<workspace>/artifacts`
- `~/.cache/huggingface/hub`
- `~/MLXModels`
- `~/Models`
- `~/.mlx_models`
3. Classify each candidate by tier and reason.
4. Produce machine-readable plan (`StorageCleanupPlanV1`).
5. Apply only explicit tiers from the plan with hard confirmation.

## Archive Mode (NEW v1.1)

Use archive mode when the user wants to reclaim space without losing access to large but currently inactive assets.

Preferred sequence:
1. Audit first and separate candidates into:
- `delete_now`
- `archive_now`
- `keep_local`
2. Validate the target archive volume:
- mounted
- writable
- enough free space for payload plus 10 percent headroom
3. Prefer preserving working paths with symlink-back mode after a verified copy.
4. Re-measure source and destination sizes before removing the local copy.
5. Re-measure system free space after the move and report actual reclaimed bytes.

Archive mode is especially appropriate for:
- old experiment runs with preserved metadata but low active reuse
- large training output folders
- bundled release assets not needed for current iteration
- stale build products the user wants kept off-machine rather than deleted

## Git LFS Reclaim (NEW v1.1)

If a repository is unexpectedly huge, inspect `.git/lfs` before touching workspace files.

Use this sequence:
```bash
git -C <repo> lfs prune --dry-run
git -C <repo> lfs prune
git -C <repo> count-objects -vH
```

Rules:
- treat `lfs prune --dry-run` as mandatory before pruning
- explain that pruned LFS objects may need to be re-downloaded for older refs
- never combine LFS pruning with destructive workspace cleanup in one opaque step

## Symlink-Back Safety Pattern (NEW v1.1)

When offloading to external storage, prefer:
1. copy source to archive target
2. verify destination exists and size is plausible
3. remove local source
4. create symlink from original path to archived path

Do not use symlink-back mode for:
- actively mutating database directories
- lock directories
- ephemeral temp directories
- paths the user explicitly wants fully removed

## Cold Storage Manifest + Restore (NEW v1.2)

Use a manifest whenever you offload anything that may need to come back later.

Why:
- archive copies are only truly safe when they are reversible
- symlink-preserved paths should be explicitly tracked
- cold-only archives should be materializable with one command

Preferred sequence:
1. archive/offload the reviewed paths
2. write a `ColdStorageManifestV1` JSON alongside the workspace artifacts
3. verify the manifest immediately
4. use the helper script for restore or relink operations instead of ad hoc shell

Helper commands:
```bash
python3 scripts/cold_storage_manifest.py list \
  --manifest <workspace>/artifacts/cold_storage_manifest.json
```

```bash
python3 scripts/cold_storage_manifest.py verify \
  --manifest <workspace>/artifacts/cold_storage_manifest.json \
  --json
```

```bash
python3 scripts/cold_storage_manifest.py materialize-local \
  --manifest <workspace>/artifacts/cold_storage_manifest.json \
  <entry-name>
```

```bash
python3 scripts/cold_storage_manifest.py relink-cold \
  --manifest <workspace>/artifacts/cold_storage_manifest.json \
  <entry-name>
```

Use `materialize-local` when the local directory should exist as real bytes again.
Use `relink-cold` when you want the original path to point back to the archived location.

## Symlink Alias Awareness (NEW v1.3)

Some local model registries use symlink aliases that point into other workspaces.

Rules:
- discover `~/.mlx_models` during audit
- classify symlink entries as `symlink_alias`
- report their link targets for operator awareness
- never count them as reclaimable payload bytes
- never delete them during `apply`, even if a caller over-selects tiers

This prevents false reclaim estimates and avoids breaking apps that depend on alias paths.

## Safety Rules

- Never delete outside paths explicitly listed in the generated plan.
- Never apply without `--confirm DELETE`.
- Default apply tier should be `safe_now` only.
- Treat `conditional` as opt-in and review each item.
- Preserve models discovered from active configs and `.env` unless manually overridden.
- Preserve currently active research bases and known keep lists even during archive mode.
- Keep delete actions and archive actions in separate reviewed groups.
- Never offload a path with a live process lock or active PID file without explicit liveness verification.

## Useful Options

- Add model keep overrides:
```bash
python3 scripts/storage_hygiene.py audit --workspace "$PWD" \
  --keep-model mlx-community/Qwen2.5-7B-Instruct-4bit \
  --keep-model mlx-community/Qwen2.5-0.5B-Instruct-4bit
```

- Tighten report focus to bigger wins:
```bash
python3 scripts/storage_hygiene.py audit --workspace "$PWD" --min-size-gb 0.5
```

- Apply both low-risk and reviewed conditional candidates:
```bash
python3 scripts/storage_hygiene.py apply \
  --plan "$PWD/artifacts/storage_cleanup_plan.json" \
  --tiers safe_now,conditional \
  --kinds hf_repo,mlxmodels_repo,models_repo \
  --confirm DELETE
```

- Recommended manual archive checklist when no native offload script exists:
```bash
df -h <archive-volume>
du -sh <source>
rsync -a <source>/ <archive-dest>/
du -sh <archive-dest>
rm -rf <source>
ln -s <archive-dest> <source>
df -h /
```

## Contract Reference

Use `references/contracts.md` for plan and apply result schemas.
