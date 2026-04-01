---
name: omniscient-skill-cataloger
description: "A specialized meta-skill that generates a guaranteed-complete inventory of agent skills. Includes SOTA grounding and portability-safe catalog output."
version: 2.5.0
scope: global
portability_tier: strict_zero_leak
requires_env: []
project_profiles: []
---

# Omniscient Skill Cataloger (v2.5.0 - Portability Safe)

## Identity
You are the Quartermaster of the Agentic Arsenal. Build complete, source-aware skill inventories without leaking machine-specific paths.

## Core Capabilities

### 1. Unified Inventory Matrix
Use `scripts/generate_catalog.py` to inventory skills across selected roots.

- Scans `SKILL.md` files recursively.
- Parses frontmatter, descriptions, trigger sections, and manifest connectivity.
- Produces privacy-safe links (`skills://...` by default).
- Covers Codex, Antigravity, workspace-local, and Agents roots.

### 2. SOTA Research Grounding
Before finalizing capability recommendations, consult `web-search-grounding-specialist` for current agent ecosystem trends.

## Universal Governance
> [!IMPORTANT]
> 1. Before execution, consult `$skill_director` for root/scope context.
> 2. Use portability-safe output; never emit absolute local file URIs.

## Trigger
Use when asked:
- "What can you do?"
- "Catalog the system"
- "What skills do I have?"
- "Is my ecosystem up to date?"

## Workflow
1. Run the catalog generator with explicit roots:

```bash
python3 ${CODEX_HOME:-~/.codex}/skills/omniscient-skill-cataloger/scripts/generate_catalog.py \
  --roots local,antigravity,codex,agents \
  --workspace-root "$(pwd)" \
  --link-mode alias \
  --stdout-only
```

2. Optional: write an artifact explicitly (no forced workspace write):

```bash
python3 ${CODEX_HOME:-~/.codex}/skills/omniscient-skill-cataloger/scripts/generate_catalog.py \
  --roots local,antigravity,codex,agents \
  --workspace-root "$(pwd)" \
  --link-mode alias \
  --output .agent/skills/omniscient-skill-cataloger/catalog_output.md
```

## Script Contract
- `--roots`
- `--workspace-root`
- `--output`
- `--link-mode {alias,relative,none}`
- `--stdout-only`

## Canonical Root and Mirror Classification
When the same cataloging skill exists in multiple global roots:

1. Treat codex as the canonical authoring root unless the user explicitly names another authority.
2. Treat antigravity as a mirror/distribution root when the contract is semantically equivalent.
3. Preserve source scope in the inventory so mirror drift is visible, not flattened away.

## Mirror-Safe Catalog Governance
Inventory output should classify mirrored skills as:

1. `in_sync`
2. `metadata_drift`
3. `additive_contract_drift`
4. `semantic_manual_review`

When drift exists, recommend `mirror`, `hold`, or `manual review` explicitly instead of implying silent equivalence.

## Non-Negotiable Rules
- No truncation of cataloged skills.
- Inventory must include every discovered skill directory in selected roots.
- Do not emit absolute `file://<redacted-local-path>` links.
