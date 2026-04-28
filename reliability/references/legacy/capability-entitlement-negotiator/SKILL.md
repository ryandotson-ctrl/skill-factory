---
name: capability-entitlement-negotiator
description: Portable pre-launch capability and entitlement negotiator that classifies
  execution mode and fallback options before runtime work starts.
metadata:
  version: 1.3.0
  short-description: Portable capability and entitlement negotiation
  portability_tier: strict_zero_leak
  scope: global
  requires_env: []
  project_profiles: []
---

# Capability Entitlement Negotiator

## Use When
- A workflow depends on external credentials or provider entitlements.
- You need deterministic `full|limited|disabled` mode selection before launch.
- You want explicit fallback modes instead of implicit failure.

## Providers
- `simulator_only`
- `ibm_runtime`
- `ibm_catalog`
- `google_engine`
- `generic` (fallback adapter)

## Inputs
- `request.json` with:
- `provider`
- `credentials` (`token_present`, `token_valid`, optional provider-specific fields)
- `provider_config` (adapter facts such as `runtime_available`, `catalog_entitlement`, `approved_access`)
- `required_features`
- `features` (optional overrides)
- `fallback_modes`
- `local_route_prereqs` (optional local prerequisites such as draft-model env presence)

## Outputs
- `capability_matrix.json`
- `execution_mode.json`

## Contracts
- `ExecutionModeV1` includes `provenance[]`.
- Capability matrix includes `provenance_signature` for immutable evidence hashing.
- Execution mode output should include explicit reason codes for downgraded local routes.
- Capability matrix should include `effective_state_proof[]` with `requested` vs `effective_available`.

## Workflow
1. Normalize credentials and provider adapter signals.
2. Normalize local route prerequisites when provided.
3. Build capability matrix with required/available/source provenance.
4. Build requested-vs-effective proof rows and local prerequisite failure mapping.
5. Compute deterministic execution mode.
6. Emit portable JSON artifacts with schema tags and signature.

## Additive Contract Notes (NEW v1.1)
For local inference routes with optional accelerators:
- missing prerequisites must downgrade mode to `limited` with explicit fallback path
- silent enable-without-effect states must be reported as capability mismatches

## Additive Contract Notes (NEW v1.2)
For feature-level launch safety:
- capability output must include `effective_state_proof[]` with:
  - `feature`
  - `requested`
  - `provider_available`
  - `effective_available`
  - `reason_code`
  - `missing_local_prereqs[]`
- execution mode output should include:
  - `reason_code`
  - `downgrade_codes[]`
  - `local_route_prereq_failures[]`

## Additive Contract Notes (NEW v1.3)
For runtime provenance and cooldown-safe governance:
- capability output should include `runtime_provenance` with:
  - `mock_runtime_runs`
  - `real_runtime_runs`
  - `evidence_mode` (`none|mock_only|real_runtime|mixed`)
  - `cooldown_safe` (bool)
- execution mode output should include:
  - `cooldown_safe` (bool)
  - downgrade code `mock_runtime_cooldown_policy_violation` when mock evidence is misclassified as cooldown-consuming

## Run
```bash
python3 scripts/negotiate.py --request request.json --out-dir out
```

## Validation
```bash
python3 scripts/negotiate.py --self-test
```

## References
- `references/contracts-v1.md`
