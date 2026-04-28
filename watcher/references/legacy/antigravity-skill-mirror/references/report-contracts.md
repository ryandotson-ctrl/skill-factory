# Report Contracts

## `MirrorReportV1`

Use this for dry-run and audit summaries.

Required fields:
- `policy.canonical_root`
- `policy.mirror_root`
- `policy.publication_root`
- `codex_root`
- `antigravity_root`
- `workspace_root`
- `counts.*`
- `copy_candidates[]`
- `shared_drift[]`
- `workspace_mirror_drift[]`
- `union_missing[]`
- `union_extra[]`

Interpretation rules:
- `shared_drift` means codex and antigravity differ on a mirrored skill and should be treated as manual review unless overwrite is explicit.
- `workspace_mirror_drift` means the published mirror is behind or diverged from codex canonical truth.
- `union_extra` is informational and may include codex-only skills that are not mirror failures.

## `MirrorApplyReceiptV1`

Use this after `--apply`.

Required fields:
- `applied_copy_candidates[]`
- `overwrite_existing`
- `backup_root` when overwrite is true
- `shared_drift_remaining[]`
- `workspace_mirror_drift_remaining[]`
- `next_manual_reviews[]`

Interpretation rules:
- additive sync without overwrite should only reduce `copy_candidates`
- shared drift may remain intentionally when semantic review is still required

## `MirrorAlignmentV1`

Use this when the mirror state is verified as clean enough for release or publication.

Required fields:
- `shared_drift_count`
- `workspace_mirror_drift_count`
- `aligned`
- `checked_at`

Alignment rule:
- `aligned=true` only when both `shared_drift_count` and `workspace_mirror_drift_count` are zero
