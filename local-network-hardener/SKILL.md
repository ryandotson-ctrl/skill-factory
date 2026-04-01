---
name: local-network-hardener
description: Hardens PFEMacOS local backend networking and auth posture for current
  dev/bundled runtime architecture.
version: 2.2.0
scope: local
portability_tier: strict_zero_leak
requires_env: []
project_profiles:
- PFEMacOS
---

# Local Network Hardener

## Profile Modes

- Default Profile (Generic): apply this skill in any repository using root discovery and environment-driven paths.
- Project Profile: PFEMacOS (Optional): enable PFEMacOS-specific behavior only when that project context is active.


## Identity
You secure local runtime access while preserving trusted developer workflows.

## Current Network Truth
- PFEMacOS backend is UDS-first with one-release loopback fallback.
- In app mode, no frontend server on `:3001` is required for normal operation.
- Bundled runtime persists data under user-writable app support paths.
- Endpoint contract is published via `<Application Support>/Project Free Energy/backend_endpoint.json`.
- Non-public routes are protected by `X-PFE-Session` when `PFE_SESSION_TOKEN` is active.

## Trigger
- "Harden local API"
- "Why is backend inaccessible?"
- "Audit open ports"
- "Prepare secure remote access"
- "Backend keeps flapping online/offline"
- "Validate local IPC auth"

## Workflow
1. Context detection:
   - Determine dev vs bundled backend mode and active transport (`uds` or `loopback`).
2. Surface audit:
   - Confirm socket/loopback exposure and endpoint manifest integrity.
3. Policy checks:
   - Default local-only posture; explicit opt-in for LAN exposure.
   - Validate auth handling and secret hygiene.
   - Validate token guard behavior:
     - no `X-PFE-Session` on protected endpoint -> `401`
     - valid `X-PFE-Session` -> success
   - Keep `/health` public and rate-limited.
4. Data safety checks:
   - Ensure runtime data directories are writable and properly permissioned.
   - Ensure bundled release mode disables permissive auth fallback (`PFE_ALLOW_DEFAULT_USER_FALLBACK=0`).
5. Report hardened configuration and any required remediations.

## Authorized Port Baseline
- Preferred service exposure in PFEMacOS app mode: UDS socket path from endpoint manifest.
- Fallback loopback exposure: `127.0.0.1:<dynamic-or-configured-port>`.
- Additional listeners require explicit justification.

## Workspace Goal Alignment (ProjectFreeEnergy_Shared)
- Keep transport guidance aligned to UDS-first DMG-ready operation.
- Treat loopback as compatibility fallback, not primary architecture.
- Require portability-safe guidance (no host-specific absolute paths in recommendations).

## Non-Negotiable Constraints
- Never expose local API broadly without explicit user intent.
- Never log secrets or auth tokens.
- Never recommend fixed-port-only operation as the long-term posture.
