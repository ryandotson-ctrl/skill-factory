#!/usr/bin/env python3
"""Generate a portable MLX objective contract file."""

from __future__ import annotations

import argparse
from pathlib import Path


DEFAULT_TEMPLATE = """# Portable objective contract for MLX fine-tuning pipelines
# Copy and fill values before execution.

objective:
  name: "{objective_name}"
  summary: "{summary}"
  execute_mode: "{execute_mode}"  # plan_only | execute
  source_prompt_ref: "<optional-user-prompt-snippet>"

constraints:
  local_only: true
  allow_public_web_research: true
  allow_login_or_accounts: false
  no_data_exfiltration: true
  strict_sanitization: true
  sandbox_test_writes: true

paths:
  repo_root: "<repo_root>"
  artifact_root: "<artifact_root>"
  model_store_root: "<model_store_root>"
  sandbox_root: "<sandbox_root>"

model:
  base_model: "{base_model}"
  target_model_id: "{target_model_id}"
  training_method: "{training_method}"   # lora | qlora

deliverables:
  research_notes: true
  run_log: true
  manifest: true
  tool_schema: true
  supervised_datasets: true
  distillation_datasets: true
  training_runner: true
  adapters_and_fused_model: true
  evaluation_report: true
  integration_runbook: true

quality_gates:
  tool_name_accuracy_min: 0.95
  args_json_and_schema_min: 0.95
  false_positive_tool_call_max: 0.05
  claimed_success_without_proof_max: 0.01
  permission_guidance_min: 0.98
  integration_streaming_required: true

retries:
  max_attempts: 5
  backoff_seconds: [5, 15, 30, 60, 90]

integration:
  discovery_method: "local_model_store_scan"
  rollback_required: true
  retrain_instructions_required: true
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate MLX objective contract YAML")
    parser.add_argument("--output", required=True, help="Output YAML path")
    parser.add_argument("--objective-name", default="custom-orchestrator-training")
    parser.add_argument(
        "--summary",
        default="Train an objective-specific orchestrator with local MLX tooling.",
    )
    parser.add_argument("--execute-mode", choices=["plan_only", "execute"], default="plan_only")
    parser.add_argument("--base-model", default="mlx-community/Llama-3.1-8B-Instruct-4bit")
    parser.add_argument("--target-model-id", default="custom_orchestrator_4bit")
    parser.add_argument("--training-method", choices=["lora", "qlora"], default="lora")
    args = parser.parse_args()

    out_path = Path(args.output).expanduser()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = DEFAULT_TEMPLATE.format(
        objective_name=args.objective_name,
        summary=args.summary,
        execute_mode=args.execute_mode,
        base_model=args.base_model,
        target_model_id=args.target_model_id,
        training_method=args.training_method,
    )
    out_path.write_text(payload, encoding="utf-8")
    print(f"Wrote objective contract: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
