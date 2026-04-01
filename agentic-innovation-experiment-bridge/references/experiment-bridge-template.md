# Experiment Bridge Template

## Template
```text
ExperimentBridgeV1
- hypothesis:
- blast_radius:
- eval_plan:
- promotion_criteria:
```

## Bounding Rules
- Define the smallest slice that can falsify the idea.
- Keep user-facing impact limited until evidence is strong.
- State what existing path remains as the fallback.

## Eval Prompts
- What metric or behavior should improve?
- What baseline are we protecting?
- What would count as a regression even if the demo looks good?
- How long should the experiment run before promotion or rejection?

## Promotion Rules
- Promote only when the eval is repeatable.
- Promote only when rollback is clear.
- Promote only when readiness work is named, even if not yet completed.
