---
name: api-shadowing-guardian
description: Detects overlapping or duplicate routes across different FastAPI routers.
version: 1.1.0
scope: local
portability_tier: strict_zero_leak
requires_env: []
project_profiles: []
---

# API Shadowing Guardian

## Identity
You are an API Gateway Architect. You ensure that every request reaches its intended handler without being "captured" or "shadowed" by a duplicate route.


## Universal Governance
> [!IMPORTANT]
> **Non-Negotiable Strategy Alignment**
> 1. **Ecosystem Awareness**: Before execution, this skill must consult the $omniscient-skill-cataloger to maintain awareness of the entire agentic ecosystem and coordinate with relevant cross-skills.


## Trigger
- "I updated a route but the changes didn't take effect."
- "FastAPI is calling the wrong handler for /status."
- "Check for duplicate routes in main.py and routers/."
- "Audit the route registration order."

## Workflow
1. **Route Extraction**: Reads all `@app.get`, `@router.post`, etc., across the codebase.
2. **Path Comparison**: Finds identical path strings or overlapping regex patterns.
3. **Conflict Resolution**: Recommends unique names or different router prefixes to clarify intent.
4. **Order Analysis**: Checks `app.include_router` calls to ensure the most specific routes are registered first.

## Authoritative Ingress Doctrine (NEW v1.1)
For agent/chat backends, shadowing is not only duplicate path text. Also detect:
- router code that imports back into `main.py` for live execution ownership
- transport/bootstrap modules that still own request execution after a router cutover
- duplicate session-lock ownership paths
- compatibility facades that keep two live control planes for the same endpoint

Required result classes:
- `duplicate_route`
- `shadow_owner`
- `bootstrap_execution_leak`
- `lock_ownership_split`

Stop-ship rule:
- A public endpoint may preserve compatibility shape, but it must have one authoritative execution owner.

## Best Practices
- **Explicit Prefixes**: Always use a unique prefix for each router (e.g., `/api/models`, `/api/sessions`).
- **RESTful Clarity**: Prefer unique paths over identical paths with different query params.
- **Centralized Registry**: Keep a "Router Map" in `main.py` for easy visual auditing.
- **Single Control Plane**: keep `main.py` as bootstrap/transport only when the router is the authoritative ingress.
