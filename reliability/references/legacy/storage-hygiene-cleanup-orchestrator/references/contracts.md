# Contracts

## StorageGuardianPlanV2

```json
{
  "schema": "StorageGuardianPlanV2",
  "generated_at": "ISO-8601",
  "execution_context": {
    "cwd": "$HOME-relative path",
    "detected_thread_id": "string|null",
    "hot_thread_ids": ["string"],
    "hot_session_days": ["$HOME/.codex/sessions/YYYY/MM/DD"],
    "hot_workspace_roots": ["$HOME/Documents/Repo"],
    "hot_worktree_paths": ["$HOME/.codex/worktrees/id/Repo"],
    "keep_models": ["owner/repo"],
    "external_volumes": [{"mount": "string", "total_bytes": 0, "used_bytes": 0, "available_bytes": 0}],
    "time_windows": {"hot_days": 14, "warm_days": 45}
  },
  "volume_summaries": [
    {"mount": "string", "total_bytes": 0, "used_bytes": 0, "available_bytes": 0}
  ],
  "workspace_profiles": [
    {
      "name": "string",
      "root": "$HOME/Documents/Repo",
      "activity": "active|warm|cold",
      "last_signal_at": "ISO-8601",
      "protected_bytes": 0,
      "delete_now_bytes": 0,
      "offload_manifest_bytes": 0,
      "review_first_bytes": 0
    }
  ],
  "session_profiles": [
    {
      "day": "YYYY-MM-DD",
      "size_bytes": 0,
      "temperature": "hot|warm|cold",
      "action": "delete_now|offload_manifest|review_first|protect",
      "thread_ids": ["string"],
      "offloaded": false,
      "last_signal_at": "ISO-8601"
    }
  ],
  "candidates": [
    {
      "path": "$HOME-relative path",
      "size_bytes": 0,
      "category": "string",
      "source_type": "string",
      "temperature": "hot|warm|cold",
      "importance_score": 0,
      "action": "delete_now|offload_manifest|review_first|protect",
      "workspace": "string|null",
      "thread_ids": ["string"],
      "last_signal_at": "ISO-8601",
      "recovery_cost": "low|medium|high",
      "reason": "string",
      "metadata": {}
    }
  ],
  "summary_by_action": {
    "delete_now_bytes": 0,
    "offload_manifest_bytes": 0,
    "review_first_bytes": 0,
    "protect_bytes": 0
  },
  "registry_state": {
    "schema": "StorageGuardianRegistryV2",
    "entry_count": 0,
    "legacy_entry_count": 0,
    "legacy_import_count": 0,
    "external_root": "string|null",
    "updated_at": "ISO-8601"
  },
  "legacy_imports": [{"root": "string", "imported_at": "ISO-8601", "provenance": "string"}],
  "settings": {
    "hot_days": 14,
    "warm_days": 45,
    "cache_policy": "review_first|cache_first",
    "cwd": "/abs/path",
    "roots": ["/abs/path"],
    "external_root": "/abs/path|null",
    "include_external": true,
    "thread_id": "string|null",
    "registry_path": "/abs/path"
  }
}
```

## StorageGuardianApplyResultV2

```json
{
  "schema": "StorageGuardianApplyResultV2",
  "applied_at": "ISO-8601",
  "actions_requested": ["delete_now", "offload_manifest"],
  "deleted": [{"path": "$HOME-relative path", "status": "deleted", "size_bytes": 0}],
  "offloaded": [{"path": "/abs/path", "status": "offloaded", "external_path": "/abs/path"}],
  "skipped": [{"path": "/abs/path", "status": "string"}],
  "errors": [{"path": "/abs/path", "status": "error", "error": "message"}]
}
```

## StorageGuardianRegistryV2

```json
{
  "schema": "StorageGuardianRegistryV2",
  "updated_at": "ISO-8601",
  "attached_volume": "e",
  "external_root": "/abs/path",
  "entries": [
    {
      "id": "string",
      "source_path": "/abs/path",
      "external_path": "/abs/path",
      "mode": "manifest_only|legacy_tar_archive|legacy_live_symlink|archive_only",
      "source_type": "path|session_day|worktree|git_archive",
      "workspace": "string|null",
      "thread_ids": ["string"],
      "session_days": ["YYYY-MM-DD"],
      "provenance": "native_guardian|legacy-root-path|ssd_guardian_v1",
      "status": "offloaded|archived|review",
      "moved_at": "ISO-8601",
      "restore_command": "string",
      "temperature_at_move": "hot|warm|cold|null",
      "legacy_mode": "string|null",
      "category": "string",
      "description": "string",
      "size_bytes": 0
    }
  ],
  "legacy_imports": [{"root": "string", "imported_at": "ISO-8601", "provenance": "string"}]
}
```
