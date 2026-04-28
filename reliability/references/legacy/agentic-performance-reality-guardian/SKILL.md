---
name: agentic-performance-reality-guardian
description: Portable performance and scale-risk guard for agentic changes. Use when a change can amplify work across users, requests, keystrokes, records, retries, streams, jobs, caches, or queues and needs load-shape analysis, guardrails, and observability before ship.
---

# Agentic Performance Reality Guardian

Expose the gap between "works in testing" and "survives real load."

Read `references/performance-anti-patterns.md` when checking load shape, guards, or observability.

## Workflow
1. Emit `PerformanceRealityV1` with:
   - `load_shape`
   - `amplifiers`
   - `guards`
   - `observability`
2. Model the workload:
   - what one user action expands into
   - what happens at 10x and 100x
   - where retries, fanout, or polling multiply cost
3. Check for portable anti-patterns:
   - per-keystroke or per-item queries
   - N+1 access patterns
   - missing debounce, batching, caching, or rate limits
   - cache stampede or retry storm risk
   - unbounded concurrency or queue growth
   - blocking work in async or request paths
   - large payload or serialization amplification
4. Propose guards that match the risk: debounce, batching, coalescing, backpressure, bounded concurrency, caching, TTL policy, circuit breaking, or admission control.
5. Require observability that can confirm the fix under load, not just in happy-path tests.

## Coordination
- Use `$async-hygiene-monitor` when latency risk may come from event-loop blocking or improper async structure.
- Use `$thread-safety-auditor` when concurrency, shared state, or race risk is present.
- Hand off to `$agentic-production-readiness-gate` once guards and observability are explicit.

## Non-Negotiable Rules
- Do not accept "tests passed with tiny load" as sufficient performance evidence.
- Do not discuss caching without invalidation and TTL discipline.
- Do not approve scale-sensitive changes without at least one clear guard and one clear signal.
