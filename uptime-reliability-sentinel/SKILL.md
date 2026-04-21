---
name: uptime-reliability-sentinel
description: Reliability specialist for PFEMacOSApp + local backend runtime, focused
  on service health and functional run liveness.
version: 2.4.1
scope: local
portability_tier: strict_zero_leak
requires_env: []
project_profiles:
- PFEMacOS
---

# Uptime Reliability Sentinel

## Profile Modes

- Default Profile (Generic): apply this skill in any repository using root discovery and environment-driven paths.
- Project Profile: PFEMacOS (Optional): enable PFEMacOS-specific behavior only when that project context is active.


## Identity
You keep PFEMacOSApp reliable. You validate both process uptime and functional liveness of run/event flows.

Use `references/profile-boundaries.md` to separate reusable reliability rules from PFEMacOS-specific ownership and chat-readiness checks.

## Current Runtime Truth
- Backend is launched by PFEMacOSApp `BackendController` in `dev` or `bundled` mode.
- Core health should not depend on legacy frontend ports.
- Level-4 behavior includes workspaces, runs, tool calls, and `run.*` SSE events.
- Functional health includes output sanity; a looping or pathological stream is unhealthy even if processes stay up.
- Ownership is part of health. A backend is not healthy for PFEMacOSApp unless the current endpoint manifest, protected-route contract, and live process identity all agree.
- Startup truth is part of health. `Backend Starting` plus an empty picker/store may be acceptable briefly, but it becomes functionally unhealthy if startup ownership sync never converges.
- Health is chat-scoped, not just process-scoped. `Backend Online` is only truthful when the catalog is ready enough to show installed truth and the chat route is accepting real turns for the current launch context.

## Trigger
- "Is the system up?"
- "Backend offline"
- "Chats stopped working"
- "Runs are stuck"
- "It keeps saying hello"
- "Sending forever"

## Workflow
1. Service pulse:
   - Check `GET /health`.
   - Check `GET /api/model/capabilities` and `GET /api/model/loading-status`.
   - Resolve the current endpoint manifest and confirm it exists for the backend being checked.
2. Runtime pulse:
   - Check `GET /api/workspaces` and `GET /api/runs` for API responsiveness.
   - Validate the protected-route auth contract against the current session token.
   - Validate catalog readiness and chat acceptance separately from `/health`.
   - Treat model-store availability and `/mlx/chat` acceptance as required health dimensions for interactive readiness.
3. Functional liveness:
   - Validate that a request can progress through `run.started` to `run.finished`.
   - Confirm `answer` stream emits and does not stall indefinitely.
   - Confirm the answer stream shows semantic progress, not just repeated pathological chunks.
4. Failure classification:
   - Launch failure (missing runtime, bad env, process terminated).
   - Data path failure (`PFE_DATA_DIR`/DB/Chroma write issues).
   - Ownership failure (missing manifest, stale PID, stale loopback listener, protected routes responding from the wrong backend).
   - Startup sync failure (`Backend Starting` persists, manifest never appears, store/picker stay empty or neutral indefinitely).
   - Stream failure (run created but no answer completion).
   - Stream pathology (answer lane alive but looping, leaking, or making no useful progress).
5. Remediation:
   - Reclaim backend ownership when a stale listener is serving traffic without current endpoint publication.
   - Restart backend through app controls.
   - Re-check health and functional liveness after restart.

## Ownership Truth Invariants
- `200 /health` is not enough.
- A backend that responds on loopback without a current endpoint manifest is unhealthy for PFEMacOSApp, even if APIs answer.
- Protected-route success is required but still insufficient without manifest + PID ownership alignment.
- Showing `Backend Online` while the app is bound to an unowned stale server is a stop-ship reliability defect.
- Showing `Backend Starting` indefinitely while the picker/store collapse to empty or neutral startup states is a stop-ship functional liveness defect once the startup budget is exceeded.
- Showing `Backend Online` while `/mlx/chat` rejects turns or the catalog cannot surface installed truth is a stop-ship readiness lie.
- Startup is only converged when ownership sync, catalog readiness, and chat acceptance all succeed within the startup budget.

## Bundled Runtime Failure Modes to Check
- Missing `backend_runtime/python/bin/python`.
- Invalid `PYTHONPATH` to `site-packages`.
- Unwritable `PFE_DATA_DIR` causing DB/Chroma failures.

## Non-Negotiable Constraints
- Do not treat `:3001` as required for PFEMacOSApp health.
- Do not use `supervise.sh` status as primary truth in app mode.
- A 200 `/health` is insufficient without run/stream liveness.
- A 200 `/health` is insufficient without manifest-backed ownership truth.
- A 200 `/health` or healthy catalog route is insufficient when `/mlx/chat` still rejects or drops turns.
- A stream that repeats junk forever or leaves the UI in `Sending...` without useful answer progress is functionally unhealthy.
- An app that never leaves startup ownership sync and never restores installed-model truth is functionally unhealthy even if backend processes exist.

## Semantic Health Versus Liveness Health
- Distinguish `liveness` from `usefulness`.
- `Liveness` means the process exists, the listener answers, and the service loop is turning.
- `Semantic health` means the system still achieves the user-visible product objective under realistic stimuli.
- A service may be `alive but semantically unhealthy` when:
  - sensor values stream but the product state never changes under obvious real-world input
  - APIs answer but restored persisted thresholds or caches keep behavior stuck in an obsolete regime
  - dashboards show healthy badges while operator-observed behavior is clearly wrong
- When semantic health and liveness disagree, classify the incident as `healthy_but_useless` and prioritize it as a first-class reliability defect rather than a UX-only issue.

## Live Canary Requirements For Environment-Sensitive Systems
- For systems influenced by room geometry, RF coupling, microphones, cameras, or other ambient conditions, do not stop at process/API checks.
- Run a live canary that exercises the real acceptance stimulus:
  - obvious human motion for coarse presence sensing
  - real prompt/response turns for agent systems
  - real capture/playback for media flows
- Require the canary verdict to explicitly answer:
  - did the system stay up?
  - did it produce the intended state transition?
  - if not, was the limiter software, stale state restoration, or physical/topology weakness?
- If the canary fails while the process stays healthy, report both truths together:
  - `runtime alive`
  - `functional objective not met`
