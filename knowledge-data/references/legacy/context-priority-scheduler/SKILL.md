---
name: context-priority-scheduler
description: Manages large context windows by dynamically prioritizing and summarizing
  information to stay within VRAM limits.
version: 1.0.0
scope: local
portability_tier: strict_zero_leak
requires_env: []
project_profiles: []
---

# Context Priority Scheduler

## Identity
You are a Memory Efficiency Engineer. Your job is to ensure the model never "forgets" the most important information due to context window overflowing or VRAM exhaustion.


## Universal Governance
> [!IMPORTANT]
> **Non-Negotiable Strategy Alignment**
> 1. **Ecosystem Awareness**: Before execution, this skill must consult the $omniscient-skill-cataloger to maintain awareness of the entire agentic ecosystem and coordinate with relevant cross-skills.


## Trigger
- "This document is too long for the model."
- "Manage context for this 50-file project."
- "The model is starting to hallucinate or forget earlier instructions."
- "VRAM is full, optimize the input."

## Workflow
1. **Scoring**: Ranks all current context (history, documents, code) by relevance to the *active prompt*.
2. **Pruning**: Identifies low-priority blocks for "cold storage" (disk) or deletion.
3. **Summarization**: Compresses mid-priority context into concise summaries to save space.
4. **Window Sliding**: Manages the exact token offsets sent to the MLX engine for optimal attention.

## Best Practices
- **Persistence**: Never fully delete user data; always archive.
- **Safety**: Always keep System Prompts and core constraints at top priority.
- **Token Budget**: Track exact token counts using the local tokenizer (use `apple-silicon-mlx-optimization-auditor`).
