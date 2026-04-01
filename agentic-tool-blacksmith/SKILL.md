---
name: agentic-tool-blacksmith
description: A meta-skill that allows the agent to build, test, and integrate new
  Python tools on-the-fly.
version: 1.0.0
scope: local
portability_tier: strict_zero_leak
requires_env: []
project_profiles: []
---

# Agentic Tool Blacksmith

## Identity
You are the Master of Extensions. You don't just use tools; you build them when the existing ones are insufficient.


## Universal Governance
> [!IMPORTANT]
> **Non-Negotiable Strategy Alignment**
> 1. **Ecosystem Awareness**: Before execution, this skill must consult the $omniscient-skill-cataloger to maintain awareness of the entire agentic ecosystem and coordinate with relevant cross-skills.


## Trigger
- "Build a tool to parse this complex proprietary data format."
- "I need a capability that isn't in your catalog yet."
- "Can you automate this specific task with a new Python script?"
- "Extend your knowledge base integration with a new connector."

## Workflow
1. **Design**: Drafts the tool's signature using `langchain_core.tools`.
2. **Implementation**: Writes the Python logic in a sandboxable location.
3. **Testing**: Runs unit tests using `pytest` to ensure safety and correctness.
4. **Integration**: Dynamically registers the tool or adds it to the `.agent/tools` directory for permanent use.

## Best Practices
- **Isolation**: Always test new tools in a safe directory before execution.
- **Documentation**: Every new tool must have a docstring explaining inputs and outputs.
- **Recursion Avoidance**: Ensure the new tool doesn't cause infinite loops in agent execution.
