# Known Failure Modes

This catalog documents past failures with web search grounding to help diagnose recurring issues.

---

## WS-001: Dispatcher Returns String Instead of Dict

**Symptom**: `'str' object has no attribute 'get'` error

**Root Cause**: DispatcherEngine sometimes returns a plain string like `"search"` instead of `{"intent": "search", ...}`

**Fix Applied**: Type coercion in `mlx_engine.py`:
```python
if isinstance(result, str):
    result = {"intent": result.lower().strip(), "query": original_message}
```

**Status**: ✅ Fixed (2026-01-24)

---

## WS-002: DuckDuckGo Rate Limited

**Symptom**: Searches fail silently or return empty results

**Root Cause**: Too many requests to DDG HTML endpoint

**Fix Applied**: Exponential backoff + Bing fallback in `web_search.py`

**Status**: ✅ Fixed

---

## WS-003: Search Results Ignored by Model

**Symptom**: Model answers from training data despite search results in context

**Root Cause**: 
- Results not prominent enough in prompt
- Model overconfident in training data

**Fix Applied**: Added prominent `[Search Results]` header and "DO NOT fabricate" instruction

**Status**: 🟡 Improved, still monitoring

---

## WS-004: Wrong Intent Detected

**Symptom**: "Who is the president?" routed to chat instead of search

**Root Cause**: Dispatcher model trained on different patterns

**Fix Applied**: Keyword override in main.py that bypasses dispatcher for known patterns

**Status**: ✅ Fixed

---

## WS-005: SSE Progress Resets to 0%

**Symptom**: Download progress bar resets during model downloads

**Root Cause**: Keepalive packets sent with `percent: 0`

**Fix Applied**: Changed keepalives to SSE comments (`: keepalive\n\n`)

**Status**: ✅ Fixed (2026-01-24)

---

## WS-006: TrackingTqdm Missing Methods

**Symptom**: `'TrackingTqdm' object has no attribute 'set_lock'`

**Root Cause**: huggingface_hub expects full tqdm interface

**Fix Applied**: Added `set_lock`, `get_lock`, `__enter__`, `__exit__` methods

**Status**: ✅ Fixed (2026-01-24)
