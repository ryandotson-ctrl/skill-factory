# Performance Anti-Pattern Catalog

## Core Questions
- What unit of user behavior becomes backend or compute work?
- What multiplies cost as traffic grows?
- What bound exists on concurrency, retries, and payload size?
- What signal will confirm success or overload?

## Anti-Patterns
- Per-keystroke work
  - symptom: spikes during typing or polling
  - typical guard: debounce, coalescing, caching
- N+1 access
  - symptom: cost rises with list size
  - typical guard: batching, prefetch, join, bulk load
- Retry storm
  - symptom: failures amplify traffic
  - typical guard: jitter, cap, circuit breaker, backoff
- Cache stampede
  - symptom: thundering herd on misses or expiry
  - typical guard: request coalescing, staggered TTL, background refresh
- Unbounded concurrency
  - symptom: queue growth, saturation, OOM, timeout cascades
  - typical guard: semaphore, pool cap, backpressure, admission control
- Blocking in async paths
  - symptom: latency cliffs, event-loop stalls
  - typical guard: move work off the hot path, isolate blocking work

## Observability Minimums
- One signal for latency or throughput
- One signal for saturation or queue pressure
- One signal for error or fallback rate
- One signal that proves the chosen guard actually engaged
