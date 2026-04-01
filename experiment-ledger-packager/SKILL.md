---
name: experiment-ledger-packager
description: Portable run-ledger packager that normalizes events into immutable records and emits reproducible replay manifests.
metadata:
  version: 1.4.0
  short-description: Immutable run ledgers and replay manifest packaging
  portability_tier: strict_zero_leak
  scope: global
---

# Experiment Ledger Packager

## Use When
- You need auditable run records with stable hashes.
- You must hand off experiments across teams/tools.
- Replayability and reproducibility are requirements.

## Inputs
- `events.jsonl` (raw events)

## Outputs
- `run_record.jsonl`
- `decision_context.json`
- `replay_manifest.json`

## Features
- Hash-chained ledger entries (`prev_hash`, `entry_hash`).
- Replay signature bundle for immutable handoff contracts.
- Policy and parser provenance fields for deterministic replay:
  - `parser_version`
  - `objective_policy_version`
  - `route_mode`
  - `draft_model_present`
  - `baseline_anchor_type` (`initial|calibrated`)
  - `drift_guard_applied` (bool)
  - `calibration_id` (optional)

## Additive Contract Notes (NEW v1.1)
`replay_manifest.json` should include stable references to:
- decision artifact
- leaderboard artifact
- test summary artifact (if present)

## Additive Contract Notes (NEW v1.2)
`decision_context.json` should include:
- `drift_guard` summary (`enabled`, `calibration_count`, `decode_drift_pct`)
- `rechecked_candidate_key`
- `enforced_baseline_fallback`

## Additive Contract Notes (NEW v1.3)
`run_record.jsonl` entries should include governance fields when available:
- `policy_mode`
- `frontier_class`
- `launch_recommendation`
- `reentry_go`
- `contract_go`

`decision_context.json` and `replay_manifest.json` should include:
- `governance.policy_modes[]`
- `governance.frontier_classes[]`
- `governance.latest_launch_recommendation`
- `governance.latest_reentry_go`
- `governance.latest_contract_go`

## Additive Contract Notes (NEW v1.4)
For autonomous research systems with accepted runs that may stall, package terminal-state integrity explicitly.

`run_record.jsonl` should include when available:
- `artifact_type`
- `schema_version`
- `producer_version`
- `run_terminal_state` (`completed|failed|blocked|abandoned`)
- `crash_signature`
- `lane_health`
- `quarantine_reason`

`decision_context.json` should include:
- `terminal_state_reconciled` (bool)
- `stale_acceptance_window_seconds`
- `latest_reconciled_run_ids[]`

`replay_manifest.json` should include:
- `artifact_envelope_required` (bool)
- `required_schema_versions[]`
- `terminal_state_contract_version`

## Replay Integrity Rules (NEW v1.4)
- A replay package is incomplete if an accepted run lacks a terminal state.
- `abandoned` is a valid terminal state only when accompanied by reconciliation evidence.
- Hash-chained entries must preserve both original event order and the later reconciliation event.
- Readers should fail loudly on incompatible schema versions rather than silently dropping fields.

## Run
```bash
python3 scripts/package_ledger.py --events events.jsonl --out-dir out
```

## Validation
```bash
python3 scripts/package_ledger.py --self-test
```

## References
- `references/contracts-v1.md`
