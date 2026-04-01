---
name: telemetry-semconv-enforcer
description: Portable telemetry semantic convention enforcer that validates required attributes and reports precise conformance violations.
metadata:
  version: 1.2.0
  short-description: Telemetry semantic convention conformance enforcement
  portability_tier: strict_zero_leak
  scope: global
---

# Telemetry Semconv Enforcer

## Use When
- Trace/log/metric data needs consistent semantic naming.
- You need conformance evidence before release.
- Telemetry contracts must be interoperable across systems.

## Inputs
- optional `profile.yaml`
- `samples.json` or `samples.jsonl`

## Outputs
- `telemetry_profile.yaml`
- `telemetry_conformance.json`

## Features
- Quantum semantic keys (`quantum.provider`, `quantum.backend`, `quantum.shots`).
- Redaction enforcement for `quantum.job_id` values.
- Exact missing-key and key-format violations.
- Inference tuning semantic keys:
  - `inference.objective.metric_coverage`
  - `inference.objective.weight_policy`
  - `inference.route.speculative_enabled`
  - `inference.route.draft_model_hash`
  - `inference.parser.version`

## Additive Contract Notes (NEW v1.1)
For privacy portability:
- prefer hashed identifiers for model-route identifiers in telemetry
- keep raw provider job identifiers redacted by default

## GenAI Turn Lifecycle Semconv (NEW v1.2)
For agentic assistant traces, enforce additive semantic coverage for:
- turn identity:
  - `gen_ai.trace_id`
  - `gen_ai.turn_id`
  - `gen_ai.session_id`
  - `gen_ai.run_id`
- route and provider truth:
  - `gen_ai.route_intent`
  - `gen_ai.provider_lane`
  - `gen_ai.selected_model`
  - `gen_ai.task_model`
  - `gen_ai.visible_answer_model`
  - `gen_ai.helper_model` when present
- tool lifecycle:
  - `gen_ai.tool.name`
  - `gen_ai.tool.call_id`
  - `gen_ai.tool.risk_level`
  - `gen_ai.tool.requires_approval`
  - `gen_ai.tool.schema_valid`
- retrieval and grounding:
  - `gen_ai.retrieval.source`
  - `gen_ai.retrieval.page_number`
  - `gen_ai.retrieval.chunk_id`
  - `gen_ai.retrieval.semantic_score`
  - `gen_ai.retrieval.rerank_score`
  - `gen_ai.grounding.low_confidence_reason`
- degradation and answer provenance:
  - `gen_ai.degradation.code`
  - `gen_ai.answer.provenance`

Rules:
- OTLP export may be optional, but local trace persistence is not.
- Missing optional exporter transport must not be treated as missing trace evidence if the local ledger is complete.

## Run
```bash
python3 scripts/enforce_semconv.py --profile profile.yaml --samples samples.json --out-dir out
```

## Validation
```bash
python3 scripts/enforce_semconv.py --self-test
```

## References
- `references/contracts-v1.md`
