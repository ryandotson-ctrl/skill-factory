---
name: mlx-objective-finetune-factory
description: Objective-driven local MLX fine-tuning and self-distillation pipeline builder for reusable model training. Use when the user wants to fine-tune a model from a written objective/prompt with strict privacy, sanitization, evaluation gates, and portable integration instructions (no host-specific path leakage).
---

# MLX Objective Fine-Tune Factory

## Purpose
Turn a user objective into a complete, local-first MLX training pipeline that is reproducible, gated, and shareable.

This skill is the "full pipeline" version of MLX fine-tuning:
- research -> schema export -> trace extraction -> sanitization -> distillation -> training -> fusion -> evaluation -> integration

## Trigger Phrases
- "Fine-tune a model from this objective prompt"
- "Build a portable MLX training pipeline"
- "Train an orchestrator model like we did before"
- "Set up end-to-end LoRA/QLoRA with hard quality gates"
- "Create retrainable local model workflow with MLX"

## Required Coordination
Before running major steps:
1. Use `$tech_auditor` (freshness check for MLX + mlx-lm).
2. Use `$private-pii-scrub-master` (dataset sanitization checks).
3. Use `$qa-automation-engineer` (gate and regression tests).
4. Use `$skill-portability-guardian` before publishing skill outputs.

## Input Contract
Use `references/objective_contract.template.yaml` as the canonical objective format.

If user gives a long prompt:
1. Parse it into objective contract fields.
2. Confirm assumptions.
3. Do not execute if the user explicitly says "reference only."

## Workflow
1. Normalize objective into contract:
- base model and target model id
- local-only/security constraints
- deliverables
- quality gates
- integration target

2. Run freshness research:
- gather latest MLX/mlx-lm official docs and release notes
- record links + timestamps in a research note

3. Export canonical tool schema:
- generate function-calling compatible schema
- validate uniqueness and JSON-schema shape

4. Build supervised datasets from local traces:
- extract sessions/runs/tool-calls/results
- sanitize paths, users, secrets, contacts, large private content
- split deterministic train/valid/test
- add negative samples (no-tool, permission-blocked, ambiguity)

5. Build web-informed self-distillation data:
- discover scenario patterns from public web sources only
- generate with local teacher model only
- keep only schema-valid, policy-safe samples

6. Train with MLX (LoRA/QLoRA):
- use conservative first-pass settings
- keep exact commands in a runnable command log
- maintain retry/backoff logs for transient failures

7. Fuse model and run smoke tests:
- verify tool-call JSON/schema
- verify truthful UX (no unproven success claims)
- verify permission guidance behavior

8. Evaluate hard gates:
- tool correctness
- false positive tool-calls
- permission compliance
- claimed success without proof
- block completion if any gate fails

9. Integrate and document:
- install/discover model in target app
- provide retrain + reinstall instructions
- provide report + manifest + checksums

## Non-Negotiable Rules
1. Keep all training and data processing local.
2. Use public web sources only; no sign-ins.
3. Never leak direct user paths or host identifiers in shareable artifacts.
4. Never claim task success without same-run evidence.
5. Use sandboxed test folders for filesystem validations.

## Portability Rules
1. Replace machine-specific paths with placeholders:
- `<repo_root>`
- `<artifact_root>`
- `<model_store_root>`
- `<workspace_root>`

2. Keep project-specific behavior in optional profile blocks.
3. Parameterize all paths via environment variables or objective contract values.
4. Publish only sanitized manifests/reports/datasets.

## Deliverable Minimum
The skill output should always include:
1. `RESEARCH_NOTES.md` with links and access timestamps
2. `RunLog.md` with attempt/retry ledger
3. `MANIFEST.json` with source/version/license/checksum metadata
4. tool schema export
5. supervised + distillation datasets
6. training command runner
7. fused model artifact location
8. evaluation report with gate pass/fail
9. integration runbook

## Helper Script
Generate a portable objective contract file:

```bash
python3 scripts/generate_objective_contract.py --output ./objective_contract.yaml
```

## Knowledge Freshness Gate (OpenClaw/Tessie/Tesla)
Before each distill/train/eval/promotion cycle, require fresh documentation coverage for these families:
- `openclaw`
- `tessie`
- `tesla`

Default freshness SLA is `72h`.

Minimum manifest requirements for each ingested source:
- `source_url`
- `fetched_at_utc`
- `last_modified` (when available)
- `sha256`
- `parser_version`
- `doc_family` (`openclaw|tessie|tesla`)

Hard gate:
- Block training and promotion when required families are stale, missing, or unreachable unless an explicit manual override is recorded in the run evidence.

## Promotion Gate: Provenance and Groundedness
Promotion must be blocked unless evaluation artifacts prove grounded behavior in protected domains.

Required evidence fields in eval/promotion outputs:
- `run_id`
- `model_id`
- `adapter_id` (if applicable)
- `dataset_version`
- `regression_suite_version`
- `doc_manifest_hash`
- `grounded_claim_rate`
- `ungrounded_claim_count`
- `tool_call_schema_validity`
- `pass_fail_by_gate`
- `fetched_at_utc` for supporting docs

Gate requirements:
- No ungrounded operational claims in protected domains.
- Coverage and freshness checks pass for all required doc families.
- Tool-call schema and policy gates pass before promotion.

## Model Routing Contract (Primary/Fallback/Safety)
Training outputs must declare and validate a deterministic routing profile:
- `primary_model`
- `fallback_model`
- `safety_fallback_model`

Routing validation requirements:
1. Verify primary path handles representative Jarvis tasks.
2. Verify fallback activation triggers only on declared failure criteria.
3. Verify safety fallback remains available and policy-compliant.
4. Record a route test matrix artifact with pass/fail evidence for all three paths.
