# Worked Examples

## Example 1: Action hallucination
- symptom: assistant claims a file move succeeded with no tool result
- classification: `action_hallucination`
- primary owner lane: `model-ux-orchestrator` plus `qa-automation-engineer`

## Example 2: Truth guard success
- symptom: assistant says it cannot confirm a filesystem action because no proof exists
- classification: `truth_guard_blocked_false_success`
- follow-up: inspect executor or routing gap before calling it hallucination

## Example 3: Context drop on fact-check
- symptom: user says "fact check that" and the prior claim subject is lost
- classification: `context_drop_hallucination`
- owner lane: `web-search-grounding-specialist`
