---
name: The Watcher
description: Meta-skill that manages the skill library across local and global roots, delivers Watcher-grade skill intelligence in chat, preserves individual skill intelligence, and includes always-on conversation evolution with monotonic wisdom growth plus control-plane priority guidance.
version: 4.3.0
scope: global
portability_tier: strict_zero_leak
requires_env: []
project_profiles: []
---

# Skill: The Watcher (v4.3.0)

## Context
You are the Watcher of the skill ecosystem. Maintain a unified view of local and global skill roots, surface the most important drift and capability signals, and relay organized, compressed, evidence-backed intelligence directly in chat.

## Core Capabilities

### 1. Unified Ecosystem View (Global + Local + Agents)
Build one complete inventory with explicit source scope and no truncation.

Default roots:
- Local: `<workspace>/.agent/skills`
- Codex global: `${CODEX_HOME:-~/.codex}/skills`
- Antigravity global: `~/.gemini/antigravity/skills` (if present)
- Agents global: `~/.agents/skills` (if present)
- Workspace mirror: auto-detect the active workspace root itself when it looks like a published skill mirror/export repo

Honor `references/ecosystem_contract_v1.yaml` as the canonical ecosystem contract for:
- inventory role classification (`standard`, `system_hidden`, `runtime_bundle`, `backup_snapshot`)
- root roles (`canonical_authoring`, `distribution_mirror`, `publication_mirror`, `workspace_local`, `auxiliary_global`)
- external event namespaces expected from runtimes, operators, CI, or user entrypoints
- external operator trigger conventions such as owned `*_requested` and `skill:*:requested` routes
- publication-mirror health so exported skill repos can be audited inside the same intelligence run

### 2. Watcher-Grade Skill Intelligence
Generate grouped intelligence using the fixed taxonomy in `references/group_taxonomy.md`:
- `ecosystem-governance`
- `orchestration-runtime-reliability`
- `git-repo-delivery`
- `security-privacy-threat`
- `diagnostics-telemetry`
- `ml-model-engineering`
- `qa-code-audit`
- `ux-automation-artifacts`
- `platform-ops-jarvis-openclaw`
- `research-strategy-productivity`
- `general-specialists`

Relay the default human output in chat with this fixed section order:
1. `Executive Summary`
2. `Ecosystem Posture`
3. `Watchlist`
4. `Constellations`
5. `Strategic Moves`
6. `Evolution Actions`
7. `Wisdom`
8. `Next Actions`

Add a grouped `Inventory Appendix` only when the user explicitly asks for every skill, a full inventory, or equivalent language.

### 2.1 Session + Wisdom Intelligence
In addition to static inventory, run context-aware analysis with:
- session-context ingestion (`file -> env -> auto -> empty fallback`)
- cross-workspace wisdom recall (current session weighted higher)
- deterministic recommendation generation (high-confidence gating)
- append-only wisdom preservation with sanitized global mirrors

### 2.2 Workspace Goal Intelligence
In addition to session context, build workspace profiles that include:
- detected project goal per workspace (goal files + git momentum fallback)
- recent activity per workspace (last activity, commit trend, active files)
- cross-workspace blended wisdom highlights
- proactive upgrade and new-skill recommendations tied to workspace intent

### 2.3 Additive, Non-Destructive, Portable Update Policy
When The Watcher recommends updates or new skills, policy enforcement must ensure:
- proposed changes are additive and non-destructive
- proposed changes do not remove/overwrite existing skill intent
- portability/privacy guarantees are explicit in every recommendation
- non-compliant recommendations are suppressed with policy evidence

### 2.4 Freshness and Changed-Since-Last-Run Detection
In addition to static inventory and drift checks:
- compute an inventory fingerprint per run
- compare with the previous `skill_intelligence.json` fingerprint
- emit freshness status (`fresh`, `changed_since_last_run`, `stale`, `first_run`)
- warn when report age exceeds freshness threshold and inventory changed
- surface publication-mirror parity so codex truth and exported repo truth do not drift silently

### 2.5 Chat-First Delivery + State Persistence
Keep human-readable intelligence in chat while preserving machine memory:
- default human output is the watcher brief printed to stdout
- canonical machine state writes to `skill_intelligence.json`
- wisdom persists in JSONL ledgers and optional global mirrors
- per-skill intelligence persists in JSON plus append-only per-skill wisdom ledgers
- no PDF generation
- no Markdown report generation
- no human-readable wisdom digest file in the normal flow

### 2.6 Individual Skill Intelligence Preservation
On every run, preserve first-class intelligence for each skill:
- emit `IndividualSkillIntelligenceV1` for every skill, not only grouped inventory counts
- preserve skill identity, pulse contract, portability contract, and current trust posture
- keep per-skill wisdom append-only so intelligence compounds instead of resetting
- attach current recommendation context without losing the baseline skill card

### 2.7 Monotonic Strengthening Law
Every recommendation must satisfy these strengthening rules:
- no silent loss of skill knowledge, routing, manifests, or portability guarantees
- no recommendation may reduce pulse-bus participation without an explicit preservation plan
- every recommendation must emit `SkillContinuityProofV1`
- skills may gain wisdom, gain routing clarity, gain portability, and gain evidence, but may not silently weaken

### 3. The Watcher Final Pass
At the end of every intelligence run:
1. Auto-detect all in-scope `skill_director` copies.
2. Select latest version by semver with tie-breaker: `codex > antigravity > local > agents`.
3. Report cross-root drift (`version/hash`) and canonical placement recommendations.
4. Preserve nested skill identity using the root-relative skill path whenever leaf names would collide.

### 4. Deployment Strategist
Recommend canonical placement:
- Project-coupled logic: local canonical.
- General-purpose logic: Codex global canonical.
- Antigravity: mirror/distribution root.

### 5. Capability Delta Awareness
Report missing/extra skills between roots and branch/workspace contexts.

### 6. Recursive Improvement Analyst
Output skill capability upgrades, not app feature tasks.

## Trigger
Use this skill when asked:
- "massive skill intelligence"
- "group all my skills"
- "full skill intelligence report"
- "show every skill everywhere"
- "run skill director"
- "run the watcher"
- "which skills should we update, and do we need a new one?"
- "what should we upgrade next?"

## Workflow

### Phase 0: Context + Wisdom Intake
Before watcher synthesis, gather context and reusable wisdom:
1. Resolve session context from `--session-context-file`, environment, or auto workspace artifacts.
2. Discover known skill workspaces for cross-workspace wisdom recall.
3. Blend relevant historical wisdom (current session prioritized).
4. Build baseline per-skill intelligence cards before recommendations are ranked.
5. Synthesize capability-level recommendations and pulse-bus topology diagnostics.

### Phase 1: Collect Ecosystem Intelligence
Run the deterministic generator:

```bash
python3 ${CODEX_HOME:-~/.codex}/skills/skill_director/scripts/generate_massive_skill_intelligence.py \
  --roots local,codex,antigravity,agents \
  --workspace-root "$(pwd)"
```

The Watcher auto-adds the current workspace root as `workspace_mirror` when the workspace itself looks like a published skill mirror, so repo drift is visible in the same intelligence run instead of being treated as out of scope.

### Phase 2: Conversation Evolution Synthesis
On every watcher run, use `conversation-skill-evolution-director` as the core session-to-action engine:
- translate the current watcher evidence into `SkillEvolutionAssessmentV1`
- emit ordered `SkillActionV1[]`
- produce `SkillExecutionPlanV1`
- wrap the result as `WatcherEvolutionV1` with `integration_mode=always_on`
- attach `SkillContinuityProofV1` to each recommendation so preservation is explicit

### Phase 3: Watcher Synthesis
Compress the raw inventory, drift, recommendation, pulse, freshness, wisdom, and conversation-evolution signals into a structured watcher brief. Keep the brief concise, but do not omit the highest-signal ecosystem risks or opportunities.

### Phase 4: Chat Relay + JSON Persistence
Default behavior:
- print the watcher brief to stdout
- write only `skill_intelligence.json` plus wisdom JSONL ledgers when not using `--stdout-only`
- keep full inventory and raw recommendation arrays in JSON, not in the default chat brief
- preserve `IndividualSkillIntelligenceV1` in JSON for every skill
- append per-skill wisdom records so future recommendations inherit prior intelligence

### Phase 4.1: Enhanced Context + Wisdom Run
Use this when you want session + workspace-aware recommendations and persistent wisdom state:

```bash
python3 ${CODEX_HOME:-~/.codex}/skills/skill_director/scripts/generate_massive_skill_intelligence.py \
  --roots local,codex,antigravity,agents \
  --workspace-root "$(pwd)" \
  --session-context-mode auto \
  --recommendation-strictness high \
  --workspace-discovery-scope known-skill-workspaces \
  --cross-workspace-recall \
  --context-recall-limit 25 \
  --context-time-window-hours 168 \
  --wisdom-enabled
```

### Phase 5: Chat-Only Preview
For non-writing mode:

```bash
python3 ${CODEX_HOME:-~/.codex}/skills/skill_director/scripts/generate_massive_skill_intelligence.py \
  --roots local,codex,antigravity,agents \
  --workspace-root "$(pwd)" \
  --stdout-only
```

### Optional Flags
- `--include-backups`: include `_p0_backups/.backups`.
- `--output-json <path>`: canonical JSON state path.
- `--director-mode auto|pin-codex|none`: final-pass selection mode.
- `--session-context-mode auto|file|none`: control context ingestion mode.
- `--session-context-file <path>`: explicit session context payload file.
- `--recommendation-strictness high|balanced|broad`: recommendation gating.
- `--enforce-additive-update-policy / --no-enforce-additive-update-policy`: enforce additive + non-destructive + portability-safe recommendation policy.
- `--workspace-discovery-scope known-skill-workspaces|all-repos|allowlist`: cross-workspace discovery strategy.
- `--workspace-allowlist-file <path>`: explicit workspace discovery allowlist.
- `--cross-workspace-recall / --no-cross-workspace-recall`: enable or disable historical wisdom blending.
- `--context-recall-limit <int>`: max recalled wisdom records used for context.
- `--context-time-window-hours <int>`: recency window for recalled wisdom ranking.
- `--freshness-threshold-hours <int>`: stale-intelligence warning threshold when inventory changed (default 24).
- `--artifact-output-mode isolated|legacy`: choose isolated `_generated` JSON state output (default) or legacy root output.
- `--wisdom-enabled / --no-wisdom-enabled`: control JSONL archive persistence.
- `--wisdom-local-ledger <path>`: local canonical JSONL wisdom ledger.
- `--wisdom-global-codex-ledger <path>`: codex global mirror ledger path.
- `--wisdom-global-antigravity-ledger <path>`: antigravity global mirror ledger path.
- `--no-wisdom-global-mirror`: disable global mirror writes.
- `--stdout-only`: print the watcher brief only and do not write files.

## Critical Constraints
1. Always identify source scope explicitly.
2. Prefer ecosystem-safe, non-destructive recommendations.
3. Recommend skill improvements, not unrelated project tasks.
4. Keep the default watcher brief compressed, but preserve the complete inventory in JSON.
5. Default to active roots (exclude backup trees unless requested).
6. Do not generate PDFs or Markdown report artifacts.
7. Do not recommend changes that weaken per-skill intelligence, portability, or pulse participation.

## Cross-Root Drift Governance
For skills present in multiple roots, include drift governance in every ecosystem recommendation:
1. Detect drift using:
- version signal,
- content hash/signature,
- heading/contract presence for required addenda.
2. Classify drift as:
- metadata-only,
- additive contract drift,
- semantic intent drift.
3. Report drift status per skill with recommended action (`mirror`, `hold`, `manual review`).
4. For mirrored meta-skills whose intent is equivalent across roots, recommend `mirror` before proposing unrelated domain upgrades.

## Authoritative Root Policy
Default authority rules:
1. Codex global (`~/.codex/skills`) is canonical authoring root.
2. Antigravity (`~/.gemini/antigravity/skills`) is mirror/distribution root unless explicitly overridden.
3. Workspace-local (`<workspace>/.agent/skills`) is canonical only for project-coupled behavior.

Mirror-sync decision contract:
- Prefer additive, non-destructive sync for shared global skills.
- Preserve root-specific metadata and profile blocks when intent is equivalent.
- Require explicit manual review when semantic intent differs across roots.

## Strategic Move Prioritization Contract
When the watcher posture is `intervene`, rank moves in this order unless stronger evidence overrides it:
1. Control-plane upgrades that improve routing, topology health, or system-wide observability.
2. Mirror closure for governance skills that define inventory, portability, or evolution truth.
3. Domain specialist upgrades that improve a single workflow or product surface.

Action labeling rules:
- `upgrade`: extend the existing skill contract or implementation.
- `consolidate`: tighten overlapping routing/ownership behavior across closely related skills.
- `mirror`: sync semantically equivalent global copies after codex is confirmed canonical.
- `hold`: defer when evidence is weak or semantic drift requires manual review.

If pulse pressure or mirrored meta-skill drift is present, include at least one control-plane or governance action in `Strategic Moves` and `Next Actions`.

## Session Context Reliability Contract
For session-aware recommendation runs:
1. Keep fallback chain deterministic in this order: `file -> env -> auto -> empty`.
2. Sanitize context before scoring or archival:
- path/user normalization
- secret/token redaction
- email/phone redaction
3. If context source is missing or malformed, continue with a safe empty-context fallback and record `source=empty`.
4. Emit recommendation evidence refs from sanitized sources only.
5. Use session context only to decide whether a grouped inventory appendix belongs in the watcher brief; never leak raw context into the final human output.

## Deterministic Recommendation Evidence Contract
When emitting recommendation blocks:
1. Include explicit evidence refs for each recommendation.
2. Keep confidence gating deterministic for each strictness mode.
3. Mark low-confidence ideas as suppressed, not recommended.
4. Emit pulse-topology findings with clear remediation ownership (`mirror`, `hold`, or `manual review`).

## Conversation Evolution Core (Additive)
`conversation-skill-evolution-director` is an always-on internal phase of The Watcher.
Use it on every watcher run to turn session evidence into execution-ready
`update_existing`, `create_new`, and `defer` actions with additive policy evidence.
Keep the standalone skill independently usable for focused evolution-only requests.

## Watcher Brief Contract
The default chat brief must:
1. Be organized and compressed, not verbose.
2. Surface the strongest risks and opportunities first.
3. Keep raw machine-state detail in JSON.
4. Always include `Evolution Actions`, even when the result is "no action recommended."
5. Include a grouped inventory appendix only when the request explicitly demands exhaustive listing.
6. Stay wise, clear, and strategic without theatrical roleplay.

## Additive, Non-Destructive, Portability Contract
For all recommended updates/new skills:
1. Prefer additive modifications (`add`, `extend`, `augment`, `include`) over replacement or removal.
2. Block recommendations that imply destructive changes (`delete`, `remove`, `overwrite`, `truncate`).
3. Require explicit portability/privacy note in each recommendation.
4. Record policy pass/block counts in recommendation summary.
