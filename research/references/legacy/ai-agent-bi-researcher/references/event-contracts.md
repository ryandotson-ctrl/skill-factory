# Event Contracts (v1.3)

This file defines the event-level contract for `ai-agent-bi-researcher`.

## Dispatch Configuration
- `mode`: `hybrid`
- `cooldown`: `900` seconds

## Input Events
1. `research:scan_requested`
2. `roadmap:review_requested`
3. `research:competitive_intel_requested`

## Output Events
1. `research:trend_report_ready`
2. `research:action_candidates_emitted`
3. `ai_agent_bi_researcher_activity` (legacy compatibility output)

## Payload Guidance
- Every output should include:
  - `generated_at` (absolute timestamp)
  - `evidence_window` (oldest/newest source dates)
  - `top_actions` (ordered list)
  - `decision_lanes`
  - `companion_skill_fit`
  - `confidence_summary`

## Compatibility Window
- Emit `ai_agent_bi_researcher_activity` through the v1.3 cycle.
- Prepare consumers to shift to `research:*` outputs for the next major revision.
