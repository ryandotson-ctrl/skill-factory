---
name: runtime-context-launcher
description: Detects PFEMacOSApp runtime context and launches the backend using BackendController-compatible
  dev or bundled mode.
version: 2.6.0
scope: local
portability_tier: strict_zero_leak
requires_env: []
project_profiles:
- PFEMacOS
---

# Runtime Context Launcher

## Profile Modes

- Default Profile (Generic): apply this skill in any repository using root discovery and environment-driven paths.
- Project Profile: PFEMacOS (Optional): enable PFEMacOS-specific behavior only when that project context is active.


## Identity
You are the launch pilot for Project Free Energy. Your job is to pick the correct backend runtime mode and verify liveness without relying on legacy `supervise.sh` assumptions.

## Current Runtime Truth
- PFEMacOSApp launches backend through `BackendController`.
- Launch modes:
  - `dev`: repo-backed runtime (`venv_312`, `backend.main:app`) with optional `--reload`.
  - `bundled`: app-embedded `backend_runtime` with env-driven writable state.
- IPC transport is dual-stack:
  - Primary: Unix Domain Socket (UDS).
  - Fallback: loopback HTTP (`127.0.0.1:<port>`) for one-release compatibility.
- Endpoint publication contract:
  - `<Application Support>/Project Free Energy/backend_endpoint.json`
  - fields: `transport`, `socket_path`, `loopback_port`, `session_token`, `pid`, `started_at`, `version`.
- Non-public backend routes require `X-PFE-Session` token when `PFE_SESSION_TOKEN` is set.
- Backend reuse requires ownership proof, not just liveness. A healthy loopback listener without a current endpoint manifest must be treated as unowned or stale until reclaimed.
- Ownership is bundle-scoped. The current macOS app must not reuse a backend that was launched for a sibling iPhone, iPadOS, or visionOS app bundle in the same workspace.
- Actual launch proof requires all of: current manifest, live PID, reachable published transport, valid protected-route auth, and matching bundle/runtime identity for the app that is launching now.
- Chat-ready launch proof is stricter than process-ready launch proof. The app must not trust a launched backend until it has either:
  - a current endpoint manifest, or
  - an in-memory bootstrap endpoint bound to the current launch context,
  and a post-launch chat-capable readiness check succeeds for the current bundle/runtime identity.

## Trigger
- "Run the app"
- "Start backend"
- "Backend is offline"
- "Use bundled runtime"
- "UDS socket failed"
- "Backend transport fallback"

## Workflow
1. Resolve launch mode in this order:
   - `PFE_BACKEND_MODE` (`dev` or `bundled`) when set.
   - Dev when repo root is available.
   - Bundled when `Contents/Resources/backend_runtime/python/bin/python` exists.
2. Build runtime-specific environment:
   - Dev: honor `PFE_BACKEND_RELOAD` (`false/0/off` disables reload).
   - Bundled: set `PFE_DATA_DIR`, `DB_PATH`, `CHROMA_DB_PATH`, `FEATURE_FLAGS_PATH`, `PYTHONPATH`, `PYTHONUNBUFFERED=1`, `PFE_ALLOW_DEFAULT_USER_FALLBACK=0`.
3. Launch transport in this order:
   - UDS first with `PFE_IPC_MODE=uds`, `PFE_SOCKET_PATH=<short tmp socket>`, `PFE_SESSION_TOKEN=<random>`.
   - If UDS startup/health fails, fallback to loopback with `PFE_IPC_MODE=loopback`.
4. Publish endpoint manifest atomically after process launch.
5. Health check `/health` until ready using the active transport.
6. Validate protected-route auth contract:
   - request without `X-PFE-Session` -> `401`.
   - request with `X-PFE-Session` -> success.
7. Validate chat-capable readiness before trusting the backend for interactive use:
   - protected model/catalog routes succeed for the current launch context
   - `/mlx/chat` preflight or equivalent chat-acceptance probe succeeds for the current runtime contract
   - if the manifest is not yet written, hold an in-memory bootstrap endpoint and session identity for the current app until endpoint publication converges
   - do not elevate the backend from `starting` to `ready` when launch/auth are healthy but chat acceptance is still unknown or failing
8. Reuse gate:
   - Reuse an existing backend only when all are true:
     - endpoint manifest is present and decodes cleanly
     - health check succeeds
     - protected-route auth contract succeeds
     - chat-capable readiness succeeds or a current in-memory bootstrap endpoint proves the same backend is still converging for this launch
     - manifest PID is alive and serving the published transport
     - manifest bundle/runtime identity matches the current launch context
   - If the manifest is missing, treat the backend as unowned even if `/health` is `200`.
   - Reclaim ownership by terminating stale loopback or UDS fallbacks and launching a fresh manifest-backed backend.
   - Treat a backend from a sibling app bundle as unowned even if its APIs respond correctly.
   - Treat sibling Apple-platform builds in the same workspace as foreign runtime owners. They may share code, but they must not share backend identity, socket paths, loopback ports, or endpoint manifests.
9. Report mode, transport, endpoint manifest path, bootstrap-endpoint status, reuse or reclaim decision, and health/chat-readiness result.

## Workspace Goal Alignment (ProjectFreeEnergy_Shared)
- Prefer UDS-first launch diagnostics and short-socket-path safeguards to avoid `AF_UNIX path too long`.
- Treat backend flapping as recoverable until retry budget is exhausted.
- Keep release mode bundled-only and avoid host-specific assumptions in runbooks.
- Treat stale loopback listeners without endpoint publication as a stop-ship ownership defect, not a harmless fallback.
- Keep backend runtime roots, manifests, socket paths, and loopback allocations bundle-scoped so PFEMacOSApp cannot share ownership with iPhone, iPadOS, or visionOS companions.
- Require live runtime proof after reclaim: the launched backend must publish identity that matches the current app bundle before the UI may treat startup as complete.
- Treat sibling Apple-platform builds in the same workspace as foreign runtime owners even when they share repository code. Shared code is allowed; shared backend identity is not.
- Require a chat-ready handshake after startup. A backend that can answer `/health` but cannot yet accept real chat requests is still in startup convergence, not production readiness.

## Verification Checklist
- `/health` returns 200.
- UDS path remains below platform limits and startup avoids `AF_UNIX path too long`.
- Endpoint manifest is present and decodes with expected fields.
- If the manifest is absent during bootstrap, the in-memory bootstrap endpoint matches the launched backend and is replaced by the manifest once publication converges.
- A missing manifest prevents backend reuse even when health endpoints respond.
- Protected-route success without a manifest is insufficient ownership proof.
- Current launch context and published backend identity agree before reuse.
- A sibling bundle's backend is rejected even if health endpoints answer.
- Chat-capable readiness succeeds before the backend is surfaced as ready for user turns.
- In bundled mode, `PFE_DATA_DIR` resolves to user-writable Application Support.
- In dev mode, reload behavior matches `PFE_BACKEND_RELOAD`.
- Protected routes enforce `X-PFE-Session` when session token mode is active.

## Runtime Integrity Gate (NEW v2.6)
- Startup truth requires more than health and auth. When the project exposes a runtime-integrity contract, verify:
  - build artifact identity
  - backend manifest hash
  - dependency manifest or lockfile hash
  - Python runtime identity
  - protected chat-route readiness
- If integrity data is missing or mismatched, classify it explicitly as:
  - `artifact_mismatch`
  - `runtime_drift`
  - `dependency_drift`
  - `backend_unverified`
- For release-facing checks, launched-artifact smoke outranks dev-only process health.

## Non-Negotiable Constraints
- Do not use `supervise.sh` as the default launcher for PFEMacOSApp.
- Do not assume a frontend process on `:3001` is required for app health.
- Never write persistent state inside app bundle resources.
- Never require fixed-port assumptions when UDS is available.
- Never attach PFEMacOSApp to a healthy-but-unowned loopback backend when endpoint publication is missing.
- Never mark runtime ready from `/health` alone when runtime-integrity or chat-readiness proof is still missing.
