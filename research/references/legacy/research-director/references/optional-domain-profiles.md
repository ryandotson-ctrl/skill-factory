# Optional Domain Profiles

Load these profiles only when the user request is actually domain-specific. The default `research-director` path should remain general.

## Apple / MLX / Local Inference On Mac

Use this profile when the task is specifically about Apple Silicon local inference, MLX, Metal-backed runtime behavior, or model-performance work on Mac.

### Objective Lock
- Local inference performance on Mac remains the primary KPI.
- Preserve quality gates, memory constraints, and user-visible stability.
- Prefer local rehearsal evidence before recommending invasive runtime changes.

### Primary Sources
- MLX docs and releases
- Apple platform and Metal documentation
- Maintainer docs for model and runtime libraries used in the stack

### Decision Rules
- Treat regressions in latency, quality, or stability as first-class blockers.
- Verify hardware-acceleration paths for silent no-op conditions.
- Cross-check docs against package or release truth before upgrade calls.
- Separate upstream model-family claims from converted runtime or package-lane claims; both can be true at the same time.
- Treat official model cards and runtime maintainer docs as stronger evidence than community or competitor posts; use X or forum posts as signal only.
- When compatibility claims are high impact and local verification is feasible, run the smallest credible local smoke test before concluding that a model or runtime lane is blocked.

## Quantum / Hybrid Compute

Use this profile when the task involves IBM Quantum, Google Quantum / Cirq, Qiskit, PennyLane, or any paid or time-limited hybrid-compute path.

### Objective Lock
- Quantum or hybrid execution is optional leverage, not the default answer.
- Paid or limited-minute execution must be justified by local rehearsal evidence.
- Recommendations must include budget and fallback paths.

### Primary Sources
- IBM Quantum platform docs and runtime guides
- Google Quantum AI / Cirq docs
- PennyLane and Qiskit maintainer docs
- Official provider pricing, plans, limits, and release notes

### Decision Rules
- Do not recommend paid hardware submission without explicit preflight evidence.
- Record backend identity and entitlement constraints in every decision-ready output.
- Escalate when documentation and live plan limits disagree.

## Local-First Assistant Migration

Use this profile when the active project is a local-first assistant migrating between runtime layers, such as Python-to-Swift ownership changes or adapter retirement.

### Objective Lock
- Preserve user-visible behavior while retiring legacy surfaces.
- Freeze contracts before replacing subsystem owners.
- Prefer client-surface truth over implementation nostalgia.

### Focus Areas
- supported client surface
- migration contracts and parity gates
- adapter retirement sequencing
- launch, lifecycle, and trust-recovery implications

### Decision Rules
- Retire legacy surfaces completely once unsupported.
- Keep user-facing capabilities in scope even when ownership moves between languages.
- Require parity evidence before cutting over a subsystem owner.
