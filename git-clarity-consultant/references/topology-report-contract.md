# Topology Report Contract

Use this contract when reporting repository clarity findings.

## RepoTopologyBriefV1
- `workspace_intent`: shared partner repo, delivery pressure, or local-only
- `active_remotes`: origin, shared, and any notable gaps
- `branch_topology`: short summary plus optional mermaid graph
- `drift_summary`: ahead/behind state and branches at risk
- `partner_activity`: recent activity grouped by collaborator
- `conflict_zones`: files or areas with overlapping ownership
- `near_term_guidance`: the next 2-4 low-risk checks or actions

## Severity Ladder
- `monitor`: informational drift or stale branches
- `attention`: shared-branch divergence, partner overlap, or unclear ownership
- `blocking`: push-risk, unreviewed partner overlap, or release-lane drift

## Output Rules
- Keep the report consultative.
- Prefer branch-level and remote-level facts over generic git advice.
- If partner context is inferred rather than confirmed, say so explicitly.
