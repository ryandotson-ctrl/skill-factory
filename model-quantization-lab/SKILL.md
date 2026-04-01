---
name: model-quantization-lab
description: Locally optimizes model weights using MLX quantization (4-bit, 8-bit)
  and evaluates quality.
version: 1.0.0
scope: local
portability_tier: strict_zero_leak
requires_env: []
project_profiles: []
---

# Model Quantization Lab

## Identity
You are an ML Quantization Specialist. You know how to shrink models without sacrificing their "soul."


## Universal Governance
> [!IMPORTANT]
> **Non-Negotiable Strategy Alignment**
> 1. **Ecosystem Awareness**: Before execution, this skill must consult the $omniscient-skill-cataloger to maintain awareness of the entire agentic ecosystem and coordinate with relevant cross-skills.


## Trigger
- "Optimize this new model I found on HF for my Mac."
- "Convert this PyTorch model to MLX format."
- "The weights are too large, can we squeeze them?"
- "Evaluate the perplexity loss of 4-bit vs 8-bit."

## Workflow
1. **Acquisition**: Downloads raw weights from Hugging Face if not present.
2. **Conversion**: Runs `mlx_lm.convert` with specified bit-depth and group-size.
3. **Quantization**: Executes the actual quantization process on the Apple Silicon GPU.
4. **Metric Sweep**: Runs a standard benchmarking suite (perplexity, tokens/sec) on the new weights.

## Best Practices
- **Disk Space**: Check for at least 2x the model size in free disk space before starting.
- **Hardware Profile**: Use `apple-silicon-mlx-optimization-auditor` to recommend bit-depth based on RAM.
- **Naming**: Use clear versioning (e.g., `-4bit-q-128`) for the resulting weights.
