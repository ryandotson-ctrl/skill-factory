---
name: mlx-quantum-autodiff-bridge
description: Build and validate MLX custom-function quantum bridges that keep MLX as the top-level autodiff engine while routing quantum execution to external runtimes.
metadata:
  version: 1.1.0
  short-description: MLX custom VJP bridge for quantum backends
  portability_tier: strict_zero_leak
  scope: global
---

# MLX Quantum Autodiff Bridge

## Workspace Goal Alignment
When the active goal is hybrid quantum-classical autotune for local MLX inference:
1. Keep MLX as the training and autodiff owner.
2. Use quantum as an optional accelerator, never a blocker for local optimization delivery.
3. Require simulator-first evidence and strict budget gates before paid hardware usage.
4. Prioritize measurable local inference gains with quality-safe decisions.

## Use When
- You need MLX-only training with external quantum execution.
- You must implement `mx.custom_function` + custom VJP for a quantum block.
- You want deterministic bridge validation before hardware usage.
- You need strict simulator-first routing with optional IBM/Cirq hardware validation.

## Trigger Examples (MLX + Quantum)
- "Keep MLX autodiff in control while using PennyLane/Qiskit execution."
- "Prove VJP correctness before we spend limited quantum minutes."
- "Run simulator-first, then allow hardware only after launch guards pass."
- "Use quantum as reranker support while local inference optimization remains primary."

## Inputs
- Python file path containing bridge implementation.

## Outputs
- `bridge_validation.json`
- `bridge_route_report.json` (optional)

## Workflow
1. Validate presence of MLX custom-function boundary.
2. Validate explicit `mx.eval` materialization at boundary.
3. Validate custom VJP registration and return arity.
4. Validate controlled NumPy/Python conversion only at boundary.
5. Validate simulator-first route defaults and deterministic settings.
6. Validate budget guard hooks for hardware paths.
7. Emit fail-closed diagnostics for missing credentials/entitlements.

## Proactive Near-Term Guidance
For active local-inference optimization programs:
1. Fix invalid candidate generation and candidate-count mismatches before hardware spend.
2. Rehearse with budget-safe settings (`quantum_budget: 1`) and capture deterministic artifacts.
3. Keep strict go/no-go thresholds and document evidence in run ledgers.
4. If config tuning gains plateau, pivot to model-level shortlist benchmarking and keep quantum optional.

## Run
```bash
python3 scripts/validate_bridge.py --file bridge.py --out bridge_validation.json
```

## Validation
```bash
python3 scripts/validate_bridge.py --self-test
```

## References
- `references/contracts-v1.md`
