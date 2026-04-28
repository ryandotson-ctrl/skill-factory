---
name: target-compatibility-gate
description: Portable compatibility gate that compares artifact requirements to target
  capabilities and emits automatic transform plans.
metadata:
  version: 1.3.0
  short-description: Artifact-to-target compatibility and auto-fix planning
  portability_tier: strict_zero_leak
  scope: global
  requires_env: []
  project_profiles:
  - PFEMacOS
---

# Target Compatibility Gate

## Use When
- A target backend may reject artifact instructions, formats, or precision.
- You need compatibility proof before paid/irreversible execution.
- You want deterministic transform actions (transpile/convert/downcast).

## Inputs
- `request.json` with:
- `target`
- `artifact`
- `required_capabilities[]`
- `target_capabilities`
- `route_pair` (optional base+draft route compatibility descriptor)

## Outputs
- `compatibility_report.json`
- `artifact_transform_plan.json`

## Circuit-Level Features
- Basis-gate compatibility checks.
- Qubit budget checks.
- Observable support checks.
- Shot requirement checks.

## MLX Runtime Features (NEW v1.2)
- KV-cache quantization compatibility probe for model/runtime pairs.
- Known incompatibility classification for fail-closed routing:
  - `rotating_kv_quantization_not_implemented`
- Auto-fix transform actions:
  - `disable_kv_quantization`
  - `restrict_search_space_kv_bits_null`

## Provider And Eligibility Features (NEW v1.3)
- Distinguish these compatibility layers explicitly:
  - `upstream_supported`
  - `sdk_or_runtime_supported`
  - `device_eligible`
  - `feature_enabled`
  - `artifact_ready`
  - `launched_runtime_ready`
- Emit readiness states instead of collapsing them into one verdict:
  - `unsupported`
  - `supported_but_disabled`
  - `supported_but_not_ready`
  - `ready`
- For local AI/runtime products, treat provider lanes as separate targets. Example:
  - local backend / MLX lane
  - optional Apple on-device lane
  - helper/finalizer lane
- If a feature is supported by platform docs but not ready in the launched artifact, the launched-artifact truth wins for user-visible compatibility.

## Route-Level Features (NEW v1.1)
- Base-model + draft-model pair compatibility checks.
- Deterministic transform plans for route mismatches:
  - `disable_draft`
  - `swap_draft_model`
  - `enforce_deterministic_decode`

## Run
```bash
python3 scripts/check_compatibility.py --request request.json --out-dir out
```

## Validation
```bash
python3 scripts/check_compatibility.py --self-test
```

## References
- `references/contracts-v1.md`

## Physical And Topology Compatibility (NEW v1.2.1)
- Compatibility is not only software, format, or precision.
- When outcomes depend on the physical world, compare artifact intent to deployment topology as well:
  - sensor placement
  - radio path observability
  - room geometry and likely coupling strength
  - network mode constraints (client-associated Wi-Fi vs monitor/CSI paths)
  - contention with the target's primary workload
- Emit one of:
  - `strong_observable_path`
  - `weak_observable_path`
  - `unknown_observable_path`
- If observability is weak or unknown, the transform plan must recommend the least disruptive correction first:
  - recalibration
  - repositioning
  - shorter validation path
  - secondary sensor only if simpler remedies fail

## Honest Downgrade And Capability Disclosure
- If the target can technically run the stack but cannot reliably express the intended signal, do not report `compatible` without qualification.
- Preferred output is a qualified verdict such as:
  - `compatible_with_limits`
  - `compatible_but_low_confidence`
  - `requires_repositioning`
- Never upgrade claims beyond the measurable path.
- Preserve an explicit distinction between:
  - `installable`
  - `operational`
  - `observably useful`

## PFEMacOS Compatibility Matrix Doctrine (NEW v1.3)
When the active workspace is PFEMacOS or another local-first macOS app:
1. compare:
   - source declaration truth
   - generated project/build-setting truth
   - active runtime environment truth
   - launched-artifact truth
2. for optional Apple Intelligence or Foundation Models lanes, keep these states distinct:
   - platform unsupported
   - supported but not eligible on this device
   - eligible but disabled
   - eligible but model/provider not ready
   - ready
3. for model/runtime compatibility, keep these truths distinct:
   - architecture family supported upstream
   - converted package contract compatible
   - installed runtime loader supports the package
   - actual launched environment can load and use it
4. never recommend a destructive UX label such as `Not Runnable` unless incompatibility is explicitly proven at the correct layer.
