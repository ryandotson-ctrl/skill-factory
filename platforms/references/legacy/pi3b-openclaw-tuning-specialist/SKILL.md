---
name: pi3b-openclaw-tuning-specialist
description: Stabilize and tune OpenClaw on Raspberry Pi 3 Model B (1 GB) under severe
  RAM, CPU, and microSD limits. Use when diagnosing memory pressure, OOM kills, slowdowns,
  rate-limit cascades, or reliability issues on a Pi 3B, or when producing runbooks,
  memory budgets, systemd/cgroup caps, zram/swap plans, and acceptance tests for OpenClaw
  on low-memory hardware.
scope: global
portability_tier: strict_zero_leak
requires_env: []
project_profiles: []
---

# Raspberry Pi 3B OpenClaw Tuning Specialist

## Overview

Force OpenClaw to run reliably on a Pi 3B (1 GB) by measuring first, bounding memory, isolating services, and validating stability with explicit tests.

## Scope Gate

Proceed only if the workload is OpenClaw (or its gateway/agent stack) on a Pi 3B-class device with tight memory. If not, decline and ask for the correct target environment.

## Required Inputs (request only if missing)

A) Hardware and OS facts
1. `uname -m`
2. `cat /etc/os-release`
3. `free -h`
4. `vcgencmd get_mem gpu` (if available)

B) Workload facts
1. Command used to start the service
2. Config files relevant to the workload
3. `journalctl -u <service> -n 200`
4. `journalctl -k -n 200`

C) Storage facts
1. microSD size and filesystem
2. `df -h`
3. `lsblk -f`

Use this minimal bundle when speed matters:

```bash
uname -m
cat /etc/os-release
free -h
vcgencmd get_mem gpu || true
ps -eo pid,comm,rss,vsz,pmem,pcpu --sort=-rss | head -n 20
journalctl -u openclaw -n 200 --no-pager
journalctl -k -n 200 --no-pager
df -h
lsblk -f
```

## Non-Negotiables

1. Do not guess. Every claim must be backed by measurements, logs, or a cited reference.
2. Do not take destructive actions without explicit approval.
3. Make every change reversible and provide rollback steps.
4. Produce a memory budget table with headroom targets.
5. Finish with a stability test and pass/fail criteria.

## Workflow (follow in order)

1. Classify the regime.
   - Fits natively.
   - Fits only with bounds.
   - Does not fit, must split (Pi runs gateway only).

2. Measure with low overhead tools.
   - `free -h`, `vmstat 1`, `top` or `htop`
   - `/proc/meminfo`
   - `ps -eo pid,comm,rss,vsz,pmem,pcpu --sort=-rss | head`
   - `journalctl -u <service> -n 200`
   - `journalctl -k -n 200`
   - `pmap -x <pid> | tail -n 30` (if needed)

3. Bound memory growth at the process level.
   - For Node/V8: set `NODE_OPTIONS="--max-old-space-size=<MiB>"`.
   - Reduce concurrency and batch sizes before touching OS-level tuning.

4. Enforce service ceilings (systemd/cgroups v2).
   - Use `MemoryHigh` and `MemoryMax` with restart policy.
   - Provide override and rollback snippets.

5. OS survival engineering.
   - Add zram or swap only after measurement.
   - Tune swappiness based on observed swap storms, not by default.
   - Reduce microSD writes (logs, caches, temp).

6. Algorithmic redesign when required.
   - Streaming transforms.
   - Chunking with bounded buffers and backpressure.
   - Bounded caches by bytes, not item counts.

7. Split architecture if needed.
   - Pi: gateway, routing, lightweight schedulers.
   - Worker: heavy parsing, embeddings, browser automation.
   - Define failure behavior when worker is offline.

8. Token budget discipline (TPM guard).
   - Read `${OPENCLAW_HOME:-~/.openclaw}/state/token_governor.json` for rolling 60s usage and capacity.
   - Gate heavy actions if headroom is low.
   - Prefer smaller contexts and earlier compaction to avoid TPM spikes.

9. Validate stability.
   - 6h, 24h, 72h targets.
   - No OOM kills, no unbounded RSS growth, swap stays under ceiling.

## Current Baseline (Jarvis Mini, Feb 2026)

Treat these as the expected “known good” defaults unless evidence suggests otherwise:

- Pi service: `openclaw.service` (systemd)
- Gateway bind: `127.0.0.1:18789`
- Model stack (primary + fallbacks):
- Primary `macmlx/local` (Mac MLX via reverse SSH tunnel to Pi loopback)
- Fallbacks `google/gemini-3-flash-preview`, then `openai/gpt-5-mini`
- Concurrency: `maxConcurrent=1`
- Output cap: `maxTokens=640`
- Throttle: `OPENCLAW_MIN_LLM_INTERVAL_MS=20000`
- Node heap: `NODE_OPTIONS=--max-old-space-size=768`
- cgroups: `MemoryHigh=780M`, `MemoryMax=900M`
- Steel CDP URL: store as `STEEL_CDP_URL` in `${OPENCLAW_HOME:-~/.openclaw}/.env` and reference it from config as `${STEEL_CDP_URL}` (do not hardcode secrets in `openclaw.json`)

## Storm Control (Scheduling Consolidation)

Prefer systemd timers over many OpenClaw cron jobs:

- Health tick (no LLM): `jarvis-auto-doctor.timer` every `15m`
- Autonomy tick (safe scripts): `jarvis-autonomy-tick.timer` every `4h`

Implementation notes:

- Use `flock` lockfiles in `/tmp` to prevent overlap.
- Ensure `PATH` is set in the units (Pi services often run with minimal env).
- Avoid aggressive cache flushing. Dropping page cache every tick can hurt latency and microSD wear. Prefer guarded drops only when memory is low, and at most every few hours.
  - Knobs (if implemented in your workspace scripts): `JARVIS_DROP_CACHES_UNDER_MB`, `JARVIS_MIN_DROP_CACHES_INTERVAL_SECS`

## Web Search 429 Cooldown (Brave)

Goal: when Brave returns `429`, stop repeated retries for a fixed window.

- Cooldown file (on Pi workspace): `memory/limits/web_search_cooldown.json`
- Behavior: if cooldown is active, `web_search` should return an empty result with a “cooldown until …” payload (not throw), so the agent continues without web search.

If OpenClaw is updated and the patch is lost, re-apply by locating the Brave web search tool in the installed OpenClaw dist bundle and re-implement:

- Pre-flight cooldown check.
- On `res.status == 429`, write cooldown file and return a non-throwing result.

## CLI Timeout Defaults (Avoid --timeout 60000)

On a Pi 3B, “default 10s/30s” timeouts are often too tight. If the operator keeps adding `--timeout 60000`, raise defaults (and keep backups).

Key places to look in the installed OpenClaw dist bundle:

- Gateway status/health CLI defaults
- Gateway RPC defaults (used by `openclaw browser` and other gateway calls)

## Security Notes (Keep Autonomy Safe)

1. Keep OpenClaw updated past known security advisories.
   - If you are pinned to an older OpenClaw, explicitly review recent advisories before enabling remote access.
2. Treat skill installation as supply-chain risk.
   - Prefer local, auditable skills in the Pi workspace.
   - Run skill audits periodically and disable any network-delivered "auto install" behavior unless you have tight allowlists.

## Secure Mac Offload (No Host File Access)

Use when the Pi must stay “gateway-only” and heavier network work is pushed to a Mac, while guaranteeing the worker cannot read host files:

- Create a Lima VM with no mounts (`limactl create ... --mount-none`)
- On Pi, add a forced-command SSH key entry that can only run a bridge (no shell)
- Queue contract (Pi): `memory/offload_queue.json`
- Results (Pi): `memory/offload_results/<task_id>.json`

Security proof checklist:

- Inside the VM: `mount` shows no `/Users/<you>` mounts
- `/Users/<you>` does not exist inside the VM
- SSH key cannot run arbitrary commands on the Pi (forced-command only)

## Secure Mac Inference Offload (MLX/Metal, No Host File Access)

Use when you want local inference throughput without exposing the Mac host filesystem.

Architecture:

- Mac runs `mlx-openai-server` on `127.0.0.1:9020` (OpenAI-compatible API)
- Mac opens an outbound reverse tunnel to the Pi:
  - Pi listens on `127.0.0.1:9030`
  - Pi forwards to Mac `127.0.0.1:9020`
- Pi OpenClaw calls the Mac model at `http://127.0.0.1:9030/v1`

Mac hardening:

- Use `sandbox-exec` (seatbelt) to deny file read/write under `/Users/<you>/**`
  - Allow only a runtime directory (e.g. `/Users/<you>/.jarvismini_runtime/**`)
- Redirect `HOME`, `HF_HOME`, `TMPDIR` into that runtime directory.

Pi hardening:

- The tunnel key in `~/.ssh/authorized_keys` must be restricted:
  - forced command that prevents shells (sleep-forever is fine)
  - `permitlisten="127.0.0.1:9030"`
  - `no-pty,no-agent-forwarding,no-X11-forwarding`

Acceptance probes:

- On Mac: `curl -sSf http://127.0.0.1:9020/v1/models`
- On Pi: `curl -sSf http://127.0.0.1:9030/v1/models`
- On Mac (sandboxed): reading `/Users/<you>/.ssh/*` must fail.

Failure behavior (required):

- If the Mac is asleep/off or the tunnel is down, OpenClaw must fall back to cloud models.
- Keep provider timeouts low enough that fallback happens quickly (avoid “hang then reply” UX).

## Deliverables (in this order)

1. Constraint Map
2. Memory Budget and Headroom Model
3. Forcing Plan (A to D)
4. RunLog with Attempt Log
5. Acceptance Tests

## Output Templates

Constraint Map (table):

| Limit | Value | Evidence |
|---|---|---|
| RAM | | |
| Swap | | |
| zram | | |
| CPU | | |
| Storage | | |
| Network | | |

Memory Budget (table):

| Component | MiB | Notes |
|---|---|---|
| Kernel | | |
| Userspace baseline | | |
| Page cache | | |
| OpenClaw RSS | | |
| Swap in use | | |
| Headroom target | | |

TPM Guard (summary):

- Capacity: 
- Rolling 60s: 
- Headroom: 
- Guard threshold: 
- Actions taken: 

## References

- Use `references/reference-pack.md` for upstream URLs.
- Use `references/proven-fixes.md` for candidate fixes. Validate against measurements before applying.
