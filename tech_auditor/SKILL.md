---
name: tech_auditor
description: Portable technology freshness auditor for any repository. Defaults to active-runtime-first analysis with optional cross-workspace expansion and evidence-tagged reporting.
version: 1.4.0
scope: global
portability_tier: strict_zero_leak
requires_env: []
project_profiles: []
---

# Tech Auditor

## Purpose
Produce a decision-ready freshness audit that reflects what is active now, while still preserving legacy context in a separate appendix.

## Workspace Goal Alignment
When the active workspace is a shared local-AI platform repository such as `ProjectFreeEnergy_Shared`, bias the audit toward:
1. The real user-facing runtime surfaces first (for example macOS app plus local backend), not retired or speculative surfaces.
2. Freshness and risk around the currently shipped model/runtime/toolchain path.
3. Repository-level drift that can distort delivery, such as stale mirrors, retired client surfaces, or CI/toolchain mismatches.

## Default Behavior (v1.3)
1. `mode: active-runtime-first`
2. Cross-workspace: opt-in only (`--extra-workspace`)
3. Ambiguity recency fallback: `45` days
4. Legacy surfaces are reported separately (appendix), not mixed into primary findings

## Audit Coverage
1. Runtime/toolchain inventory (Swift/Xcode + Apple generator and verification CLIs + Python/Node + CLI package managers).
2. Dependency manifests and lockfiles from auditable (non-generated) paths.
3. Active surface map (`active_surfaces[]`, `legacy_surfaces[]`) with rationale.
4. MLX family freshness rows (`mlx`, `mlx-lm`, `mlx-vlm`, `mlx-embeddings`).
5. Evidence-tagged freshness claims with source and absolute date.

## Core Workflow

### Phase 0: Intake
1. Determine scope: current workspace only vs explicit cross-workspace set.
2. Select mode:
   - `active-runtime-first` (default)
   - `all-manifests` (full inventory mode)

### Phase 1: Active Surface Resolution
1. Build runtime-entrypoint signal graph (app boot paths, launch commands, service entrypoints).
2. Map manifests to candidate surfaces.
3. Apply 45-day git recency fallback only when runtime graph is ambiguous.
4. Emit deterministic classifications with `surface_reason`.

### Phase 2: Inventory Discovery
1. Collect runtime/tool versions (including Apple-native tooling such as `xcodebuild`, `xcodegen`, and optional helpers like `xcbeautify`).
2. Parse dependency manifests from auditable paths.
3. Exclude generated/vendor trees by default (`.next`, `.build`, `.swiftpm`, `DerivedData`, `site-packages`, `venv*`, `.venv*`, `node_modules`, caches).

### Phase 3: Freshness Verification
1. Verify latest versions from primary sources.
2. Promote MLX package freshness into first-class output rows.
3. Tag every recommendation with:
   - claim tag: `[FACT]`, `[INFERENCE]`, `[ASSUMPTION]`
   - evidence quality: `high`, `medium`, `low`
   - source + absolute date

### Phase 4: Report Generation
Use `references/report-template.md` with active-only primary sections and required legacy appendix.

## Trigger Examples
- "Audit this repository for stale runtimes, frameworks, and dependency surfaces."
- "What technology in this repository is drifting or needs upgrades first?"
- "Give me a freshness report for the active PFE app/backend stack, not the retired surfaces."

## CLI Contract (v1.4)
Use `scripts/build_inventory.py` with:
- `--mode active-runtime-first|all-manifests` (default `active-runtime-first`)
- `--active-window-days 45` (default `45`)
- `--include-legacy-appendix` (default `true`)
- `--extra-workspace <path>` (repeatable, opt-in)
- `--output <path>`

## Event Contract (v1.4)
Input events:
- `tech:inventory_requested`
- `tech:freshness_audit_requested`
- `workspace:dependency_freshness_requested`

Output events:
- `tech:inventory_emitted`
- `tech:freshness_report_ready`
- `tech:active_surface_map_emitted`
- `tech_auditor_activity` (legacy compatibility)

## Constraints
1. Report-only: never auto-run mutating update commands.
2. Do not require `git pull`; audit local state unless explicitly asked to sync.
3. Never claim “latest” without source evidence.
4. Keep defaults portable and workspace-agnostic.

## Proactive Guidance
When recent activity suggests imminent release or hardening work:
1. Highlight runtime-critical drift before broad inventory noise.
2. Call out CI-parity risks separately from user-surface risks.
3. Treat retired or legacy repository surfaces as appendix material unless they still affect delivery.
4. Prefer recommendations that reduce ambiguity for the next engineering move, not just maximize update count.

## Universal Governance
Before execution, consult `$omniscient-skill-cataloger` for ecosystem awareness and companion skill routing.
