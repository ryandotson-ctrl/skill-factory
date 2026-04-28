# Release Hygiene Contracts

Use these contracts for deterministic git hygiene and release-lane decisions.

## HygieneFindingV1
- `category`
- `severity`
- `evidence`
- `blocking_reason`
- `recommended_fix`

## ReleaseReadinessV1
- `repo_mode`: local or shared
- `working_tree_state`
- `remote_parity`
- `ci_parity_status`
- `artifacts_or_leaks`
- `go_no_go`

## Decision Ladder
1. block on secrets or runtime residue
2. block on missing release-parity checks for shared branches
3. warn on stale remotes or hygiene debt
4. permit only when the repo state is explainable and reversible
