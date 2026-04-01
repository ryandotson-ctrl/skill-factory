# Contracts

## StorageCleanupPlanV1

```json
{
  "schema": "StorageCleanupPlanV1",
  "generated_at": "2026-03-05T01:00:00Z",
  "workspace": "/abs/path",
  "keep_models": ["mlx-community/Qwen2.5-7B-Instruct-4bit"],
  "scan_roots": ["/abs/path/.venv", "..."],
  "summary": {
    "total_candidates": 12,
    "reclaimable_bytes_by_tier": {
      "safe_now": 123456,
      "conditional": 987654321,
      "keep": 54321
    }
  },
  "candidates": [
    {
      "path": "/abs/path/to/dir",
      "kind": "hf_repo|workspace_venv|workspace_artifacts|mlxmodels_repo|models_repo",
      "tier": "safe_now|conditional|keep",
      "size_bytes": 123456,
      "size_gb": 0.115,
      "model_id": "mlx-community/Qwen2.5-7B-Instruct-4bit",
      "link_target": "/optional/symlink/target",
      "reason": "why this was classified"
    }
  ]
}
```

Candidate `kind` may also be:
- `mlx_hidden_repo`
- `symlink_alias`

For `symlink_alias` candidates:
- `size_bytes` should remain `0`
- `tier` should remain `keep`
- `link_target` should identify the destination path when known

## StorageCleanupApplyResultV1

```json
{
  "schema": "StorageCleanupApplyResultV1",
  "applied_at": "2026-03-05T01:05:00Z",
  "plan_path": "/abs/path/plan.json",
  "tiers_requested": ["safe_now"],
  "deleted": [
    {
      "path": "/abs/path/removed",
      "size_bytes": 123456,
      "tier": "safe_now",
      "status": "deleted"
    }
  ],
  "skipped": [
    {
      "path": "/abs/path/kept",
      "tier": "keep",
      "status": "skipped_not_in_tiers"
    }
  ],
  "errors": [],
  "reclaimed_bytes": 123456
}
```

## ColdStorageManifestV1

```json
{
  "manifest_version": "ColdStorageManifestV1",
  "generated_at": "ISO-8601",
  "entries": [
    {
      "name": "string",
      "strategy": "copy_back|path_preserved_symlink",
      "size_kb": 123456,
      "live_path": "/path/original",
      "cold_path": "/path/archive",
      "alias_paths": ["/optional/alias/path"],
      "notes": "string"
    }
  ]
}
```

## ColdStorageVerificationResultV1

```json
{
  "schema": "ColdStorageVerificationResultV1",
  "manifest_version": "ColdStorageManifestV1",
  "entries": [
    {
      "name": "string",
      "strategy": "copy_back|path_preserved_symlink",
      "live_exists": true,
      "cold_exists": true,
      "live_is_symlink": false,
      "live_target": "/path/archive",
      "points_to_cold": true,
      "alias_checks": [
        {
          "path": "/optional/alias/path",
          "exists": true,
          "is_symlink": true,
          "target": "/some/path"
        }
      ]
    }
  ]
}
```
