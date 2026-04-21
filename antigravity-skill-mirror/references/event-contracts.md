# Event Contracts

## Owned Ingress

### `skill:antigravity-skill-mirror:requested`
- purpose: direct request to audit or sync codex and antigravity mirror state
- minimum payload:
  - `workspace_root` optional
  - `apply` optional boolean
  - `overwrite_existing` optional boolean

### `skills:antigravity_mirror_requested`
- purpose: ecosystem-level alias for mirror checks or sync work
- minimum payload:
  - `workspace_root` optional
  - `scope` optional: `audit | sync | publish_check`

## Emitted Outputs

### `skills:mirror_report_ready`
- producer role: `mirror_audit`
- payload summary:
  - `counts`
  - `copy_candidates`
  - `shared_drift`
  - `workspace_mirror_drift`
  - `aligned`

### `skills:workspace_mirror_drift_detected`
- producer role: `publication_drift`
- emit when:
  - `workspace_mirror_drift` is non-empty
- payload summary:
  - `workspace_root`
  - `drifted_skills[]`
  - `shared_codex_workspace_mirror`

### `skills:mirror_alignment_verified`
- producer role: `mirror_alignment`
- emit when:
  - codex vs antigravity drift is empty
  - codex vs workspace mirror drift is empty when a workspace mirror is active
- payload summary:
  - `aligned: true`
  - `shared_codex_antigravity`
  - `shared_codex_workspace_mirror`

### `skills:mirror_sync_applied`
- producer role: `mirror_apply`
- payload summary:
  - `applied_copy_candidates`
  - `overwrite_existing`
  - `backup_root`
  - `shared_drift_remaining`
  - `workspace_mirror_drift_remaining`

### `skill_activity:antigravity-skill-mirror`
- producer role: `mirror_status`
- purpose: lightweight status signal for routing and operator awareness
