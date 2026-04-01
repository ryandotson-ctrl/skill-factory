---
name: research-director
description: End-to-end primary-source research director for any project. Use when you need the latest verified platform, dependency, standards, architecture, or product intelligence plus a decision-ready plan tied to the active project's north star.
metadata:
  version: 2.2.1
  scope: global
  portability_tier: strict_zero_leak
  requires_env: []
  project_profiles:
    - optional-domain-profiles
---

# Research Director

## Overview
Use this skill to run rigorous, recency-verified research and convert it into actionable decisions, experiments, migration plans, or launch recommendations for any project.

## Project North Star Lock
When the active workspace has a declared objective:
1. Restate the primary KPI or decision target before researching.
2. Restate the hard constraints that recommendations must preserve:
   - latency or throughput
   - quality or correctness
   - budget or entitlement
   - privacy, security, or compliance
   - staffing or schedule
3. Every recommendation must map back to that objective and those constraints.
4. If the request is domain-specific, load the matching optional profile from `references/optional-domain-profiles.md`.

## PFEMacOS Wisdom Lock
When the active workspace is Project Free Energy:
1. Treat PFEMacOS app truth, backend runtime truth, launched-artifact truth, and source truth as separate layers.
2. Treat the registry wisdom ledger as a first-class source of anti-regression guidance.
3. If the task touches subagent architecture, model-routing, MCP, reasoning UX, or tool orchestration, favor additive updates over replacement unless a hard blocker exists.
4. Record audit findings as `wisdom_inputs`, `known_regressions`, `forbidden_reintroductions`, and `artifact_truth_required` rather than burying them in prose.
5. When runtime or model-routing claims are in scope, prefer local smoke and launched-artifact evidence over source-only confidence.
6. Treat repo dependency pins, the live backend virtual environment, and the launched app's effective runtime as separate evidence sources that must be reconciled before declaring compatibility.
7. For model-family compatibility claims, distinguish:
   - upstream architecture support
   - converted package contract
   - installed runtime loader support
   - actual local loadability in the active environment
8. If the product is recommending or installing local models, verify that the same environment the app will launch can actually load them.
9. For PFEMacOS search and agent-runtime work, treat MCP mode, provider fallback order, and live route ownership as first-class research surfaces, not implementation details.
10. For latest-Xcode and latest-macOS work, treat deployment target preservation, App Intents metadata extraction, optional Apple Intelligence eligibility, and launched-artifact archive truth as separate evidence lines.

## When To Use
Trigger this skill when the user asks for any of the following:
- latest or most up-to-date vendor, platform, standards, or dependency guidance
- architecture, feasibility, or roadmap decisions
- migration, retirement, or cutover planning
- experiment backlog design, prioritization, or go/no-go criteria
- pre-launch checks before costly, risky, or time-limited execution
- periodic program reassessment after major run outcomes or incidents

## Trigger Examples
- "Use the latest docs to tell me whether we should migrate this subsystem."
- "What changed in this stack recently, and what should we do about it?"
- "Research the safest way to retire this legacy surface without breaking users."
- "Build a decision-ready experiment backlog from the latest evidence."

## Non-Negotiable Rules
1. Primary-source first: prioritize official docs, release notes, API references, and standards.
2. Recency discipline: verify date/version for every high-impact claim and include absolute dates.
3. Evidence separation: label facts, inferences, and assumptions explicitly.
4. Project north star lock: every recommendation must map to the active objective and constraints.
5. Cost awareness: do not recommend paid or high-risk execution without preflight evidence that lower-cost alternatives were exhausted for that stage.
6. Zero silent drift: if sources conflict, report the conflict and propose a bounded decision policy.
7. Version-truth discipline: for installable dependencies, cross-check documentation claims against package registries and record absolute release timestamps.
8. Silent no-op discipline: for optional acceleration or feature flags, verify both requested state and effective state.
9. Architecture-vs-deployment discipline: distinguish upstream family or platform claims from converted package, runtime, or deployment-lane claims.
10. High-impact tie-breaker: when sources conflict on a compatibility or feasibility claim and local verification is possible, run the smallest credible smoke test before concluding.
11. Wisdom retention: when a past incident or audit already identified a failure mode, carry that lesson forward as explicit anti-regression guidance.
12. Runtime-drift discipline: if repo pins and the live launched environment disagree, do not trust either one alone; measure both and resolve the mismatch explicitly.
13. Product-eligibility discipline: if the app is presenting a model, route, or tool as usable, verify that the launched runtime agrees before recommending it to users.
14. Latest-platform modernization discipline: if the product adopts a newest-SDK feature, verify both conditional availability and real archive/build evidence before calling it integrated.

## Source Strategy
Use `references/official-source-registry.md` as the starting registry.
Load `references/optional-domain-profiles.md` only when the request actually requires domain-specific guidance.

Required order of preference:
1. Vendor official docs and release notes
2. Project-maintainer docs and canonical repositories
3. Standards bodies/specifications
4. Package registries and release feeds
5. Security advisories when relevant
6. Reputable secondary analysis only as supplemental context

Registry cross-check requirements for dependency-sensitive decisions:
1. Pull latest package or release timestamps from the relevant registry or official release feed.
2. Compare docs claims vs registry truth before making upgrade or compatibility calls.
3. Record doc-vs-registry mismatches explicitly as conflicts with bounded actions.

## Workflow

### Phase 1: Mission Lock
1. Restate the current objective and hard gates.
2. Restate budget and schedule constraints.
3. Identify the decision class:
   - architecture
   - platform capability
   - dependency or tooling
   - migration or cutover
   - experiment design
   - launch readiness
4. Load an optional domain profile only if the request genuinely needs one.

### Phase 2: Evidence Sweep
1. Perform a fresh web sweep with recency checks.
2. Capture source metadata per claim:
   - URL
   - publisher
   - published or updated date
   - version number or release tag (if available)
3. Build an evidence matrix across the actual decision surface:
   - platform and runtime constraints
   - dependency and version state
   - standards or protocol requirements
   - rollout, pricing, or entitlement constraints
4. When package conversions, wrappers, or alternate runtimes are involved, split the matrix into:
   - upstream architecture truth
   - converted/runtime contract truth
   - locally verified execution truth

### Phase 2.4: Local Runtime Drift Audit
When the active workspace is a local-first runtime such as PFEMacOS:
1. Read repo pins from the authoritative dependency files.
2. Read the versions from the live environment that the launched app or backend actually uses.
3. Detect drift across:
   - source pins
   - active virtual environment
   - launched app runtime
   - bundled runtime if present
4. For model-runtime disputes, run the smallest credible local loader smoke test in the exact live environment.
5. Treat "current runtime can load the installed artifact" as the decisive tie-breaker for user-visible compatibility.

### Phase 2.6: Latest-SDK Modernization Audit
When the task touches a new Xcode or OS release line:
1. verify the installed toolchain version locally
2. verify official platform support and release notes
3. compare deployment target before and after modernization work
4. check whether newest-platform features are optional or mandatory in the current design
5. require archive or launched-artifact evidence for claims about App Intents, on-device AI, or latest-SDK integration
6. record any silent drift between source-level adoption and launched-artifact behavior

### Phase 2.5: MCP and Agent Runtime Surface Audit
When the task touches tool use, browser automation, search, or orchestration:
1. Verify whether MCP is `off`, `shadow`, or `live` in the active runtime.
2. Record which provider or broker path is actually serving the current request class.
3. Distinguish:
   - declared broker architecture
   - code-path ownership
   - live runtime ownership
4. If route duplication or a bypass exists, treat it as a stop-ship architecture conflict for product-truth claims.

### Phase 2.3: Audit Wisdom Ingestion
1. Read the active workspace's wisdom ledger before finalizing recommendations.
2. Separate the current question from known regressions and forbidden reintroductions.
3. If the repo already has a documented failure mode, treat it as a hard constraint, not as background color.
4. For PFEMacOS, never collapse backend runtime health, launched artifact health, and source-level success into one verdict.

### Phase 2.1: Silent No-Op Detection
1. For every optional acceleration or feature flag, verify "enabled" and "effective" separately.
2. Add explicit checks for common silent no-op conditions:
   - missing optional env or config prerequisites
   - fallback paths that preserve execution but disable the intended benefit
3. Require one evidence line per feature:
   - requested state
   - effective state
   - proof artifact reference

### Phase 2.2: Registry Reconciliation
1. Build a dependency truth table for active stack components:
   - installed version
   - latest observed version
   - latest upload or release timestamp
2. Compare documentation claims to registry truth.
3. Classify mismatches:
   - doc lag
   - package lag
   - incompatibility conflict
4. Emit a bounded action:
   - keep pinned
   - upgrade and smoke test
   - block the path

### Phase 3: Consistency and Feasibility Analysis
1. Validate compatibility intersections (SDK versions, provider access modes, runtime assumptions).
2. Flag blockers and classify each blocker:
   - hard blocker
   - soft blocker
   - monitor-only
3. Quantify uncertainty and failure risk in plain language.

### Phase 3.1: Architecture vs Deployment Contract Reconciliation
1. For model, runtime, or packaging disputes, state whether each claim describes:
   - the upstream family or architecture
   - the converted package or repository contract
   - the actual runnable lane in the target environment
2. If community or competitor posts disagree with official cards, treat those posts as signal only until canonical docs or a local smoke test confirm the claim.
3. If official upstream docs and converted runtime docs both appear correct but describe different layers, say so explicitly instead of forcing a single verdict.
4. When the claim directly affects product eligibility, use the smallest credible local smoke test as the tie-breaker and record the outcome as a separate evidence line.

### Phase 3.2: PFEMacOS Compatibility Tie-Breaker
For PFEMacOS runtime or model-store disputes, use this decision order:
1. launched-artifact local smoke in the active environment
2. live backend runtime versions and loader support
3. repo dependency pins
4. upstream documentation and package registry claims

Never let step 4 override steps 1 or 2 for user-visible compatibility labels.

### Phase 4: Experiment Director
Produce a prioritized experiment or decision backlog where each item has:
1. Hypothesis or decision statement
2. Expected impact on the active north star
3. Preconditions
4. Exact success and failure metrics
5. Runtime and cost budget
6. Safety stop conditions
7. Next-best fallback

### Phase 4.1: Near-Miss Recovery Protocol
When outcomes land in a near-miss band:
1. Run scorer or evaluator integrity validation before increasing budget.
2. Run parser or boundary validation if quality shifts are unexplained.
3. Re-run the strongest frontier with deterministic settings and confirmation replicates.
4. Only then escalate to new spend or a more invasive option.

### Phase 4.2: Drift and Order-Bias Guard
When a frontier gain appears large but later confirmation regresses:
1. Require interleaved baseline calibrations during candidate search.
2. Require drift-aware recheck of the top candidate against the latest calibrated baseline.
3. Require isolated A/B confirmation before promotion.
4. If recheck or A/B fails gate, force the baseline recommendation and mark the uplift as non-reproducible.

### Phase 4.3: Backend Selection Stability
When hardware routing or provider selection is part of the decision:
1. Distinguish discovery from pinned execution.
2. Record backend or provider identity in every relevant artifact.
3. If evidence was collected on a different backend than intended production backend, require pinned confirmation before promotion.

### Phase 5: Launch Governance
Before any paid, irreversible, or high-risk launch, require:
1. checklist-complete preflight
2. explicit budget guard pass
3. deterministic rehearsal evidence
4. rollback path and recommendation if gates fail

## Periodic Consult Cadence
Consult this skill automatically at these checkpoints:
1. Before each new optimization sprint design
2. Immediately after each completed long run
3. Before any high-cost or externally constrained launch
4. Weekly during active development
5. Any time a blocker or entitlement error appears
6. Immediately after dependency upgrades or lockfile refreshes

## Output Contracts
Prefer writing concise artifacts under `artifacts/research/`:
1. `latest_snapshot.md`
2. `source_registry.json`
3. `compatibility_matrix.json`
4. `experiment_backlog.json`
5. `governance_brief.md`
6. `runtime_drift_matrix.json`
7. `eligibility_tie_breakers.json`

Each artifact must include `generated_at` (ISO-8601), `scope`, and `assumptions`.

## Quality Bar
A research pass is complete only if:
1. every critical recommendation cites primary sources
2. all decision-critical facts are date and version stamped
3. proposed experiments have measurable gates and stop rules
4. recommendations are explicitly tied to the active north star
5. high-cost recommendations include budget rationale
6. near-miss recommendations include a scoring-integrity and silent-no-op check step
7. drift and order-bias guard is explicitly evaluated for high-variance runs
8. dependency truth table and doc-vs-registry conflict status are included for decision-critical components
9. architecture-vs-deployment disagreements are resolved or explicitly labeled with a bounded tie-break policy
10. audit wisdom is preserved in an explicit, reusable form that later sessions can inherit without re-deriving it
11. live runtime drift has been checked whenever user-visible compatibility or installability is part of the decision
12. MCP or route ownership has been checked whenever the task involves tools, search, browser automation, or orchestration

## Escalation Policy
Escalate before execution when:
1. source evidence is contradictory for a critical decision
2. entitlement state is unknown but could trigger paid usage or irreversible work
3. expected gain is below target gate after uncertainty adjustment
4. dependency documentation conflicts could change runtime behavior

Use a short decision fork with options and consequences.

## Collaboration Notes
When available and relevant, pair this skill with:
- `tech_auditor`
- `capability-entitlement-negotiator`
- `launch-window-budget-guard`
- `target-compatibility-gate`
- `eval-flywheel-orchestrator`
- `ml-compiler-inference-optimizer`
- `web-search-grounding-specialist`
- `rag-architect-specialist`
- `log-detective-sre`
- `uptime-reliability-sentinel`

The Research Director proposes and validates strategy; execution skills implement and measure.

## Optional Domain Profiles
Specialized profiles live in `references/optional-domain-profiles.md`.
Only load them when the request is actually domain-specific, such as:
- Apple / MLX / local inference on Mac
- quantum or hybrid compute
- project-specific migration guidance for a local-first assistant stack
