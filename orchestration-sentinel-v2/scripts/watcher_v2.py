#!/usr/bin/env python3
import argparse
import fnmatch
import json
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ECOSYSTEM_STATE_PATH = Path(".agent/ecosystem_state.json")
SKILLS_ROOT = Path(".agent/skills")
WATCHER_ID = "orchestration-sentinel-v2"
IGNORED_EVENT_TYPES = {
    "dispatch_requested",
    "dispatch_locked",
    "dispatch_started",
    "dispatch_completed",
    "dispatch_failed",
    "dispatch_health_report_emitted",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_iso(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def ensure_state_shape(state: Dict[str, Any]) -> Dict[str, Any]:
    state.setdefault("schema_version", "1.0.0")
    state.setdefault("bus_id", "local-ai-platform")
    state.setdefault("updated_at", now_iso())
    state.setdefault("events", [])
    state.setdefault("cursors", {})
    state.setdefault("state", {})
    return state


def load_state(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return ensure_state_shape({})
    with open(path, "r", encoding="utf-8") as f:
        return ensure_state_shape(json.load(f))


def save_state(path: Path, state: Dict[str, Any]) -> None:
    state["updated_at"] = now_iso()
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
        f.write("\n")
    os.replace(tmp_path, path)


def load_manifests(skills_root: Path) -> List[Dict[str, Any]]:
    manifests: List[Dict[str, Any]] = []
    if not skills_root.exists():
        return manifests

    for path in skills_root.glob("*/manifest.v2.json"):
        try:
            with open(path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
            manifest["_skill_id"] = path.parent.name
            manifests.append(manifest)
        except Exception as exc:
            print(f"Error loading {path}: {exc}")
    return manifests


def match_pattern(pattern: str, event_type: str) -> bool:
    if pattern == "*":
        return True
    return fnmatch.fnmatch(event_type, pattern)


def handler_excludes_event(handler: Dict[str, Any], event_type: str) -> bool:
    raw = handler.get("exclude_patterns", [])
    if not isinstance(raw, list):
        return False
    for item in raw:
        pattern = str(item).strip()
        if not pattern:
            continue
        if fnmatch.fnmatch(event_type, pattern):
            return True
    return False


def parse_route_priority(handler: Dict[str, Any]) -> int:
    raw = handler.get("route_priority", 50)
    try:
        return int(raw)
    except (TypeError, ValueError):
        return 50


def select_route_candidates(candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Select dispatch targets by route contract (broadcast vs owned with priority)."""
    by_pattern: Dict[str, List[Dict[str, Any]]] = {}
    for item in candidates:
        by_pattern.setdefault(str(item.get("pattern", "")), []).append(item)

    selected: List[Dict[str, Any]] = []
    for _, entries in by_pattern.items():
        broadcast = [entry for entry in entries if entry.get("route_mode") == "broadcast"]
        if broadcast:
            selected.extend(broadcast)
            continue

        owned = [entry for entry in entries if entry.get("route_mode") != "observer"]
        if not owned:
            continue
        top_priority = max(int(entry.get("route_priority", 0)) for entry in owned)
        selected.extend([entry for entry in owned if int(entry.get("route_priority", 0)) == top_priority])
    return selected


def summarize_manifest_routes(manifests: List[Dict[str, Any]]) -> Dict[str, int]:
    summary = {
        "manifests": 0,
        "inputs": 0,
        "owned_inputs": 0,
        "broadcast_inputs": 0,
        "observer_inputs": 0,
        "wildcard_inputs": 0,
    }
    for manifest in manifests:
        summary["manifests"] += 1
        inputs = manifest.get("inputs", []) or []
        if not isinstance(inputs, list):
            continue
        for handler in inputs:
            if not isinstance(handler, dict):
                continue
            summary["inputs"] += 1
            route_mode = str(handler.get("route_mode") or "owned").strip().lower()
            if route_mode == "broadcast":
                summary["broadcast_inputs"] += 1
            elif route_mode == "observer":
                summary["observer_inputs"] += 1
            else:
                summary["owned_inputs"] += 1
            pattern = str(handler.get("pattern") or handler.get("event_type") or "").strip()
            if pattern == "*":
                summary["wildcard_inputs"] += 1
    return summary


def build_dispatch_health_event(
    *,
    scanned_events: int,
    dispatch_count: int,
    locked_count: int,
    route_summary: Dict[str, int],
    dedupe_key: str,
) -> Dict[str, Any]:
    return {
        "id": str(uuid.uuid4()),
        "type": "dispatch_health_report_emitted",
        "time": now_iso(),
        "created_at": now_iso(),
        "source": {"skill_id": WATCHER_ID},
        "severity": "info",
        "status": "new",
        "dedupe_key": dedupe_key,
        "payload": {
            "scanned_events": scanned_events,
            "dispatch_queued": dispatch_count,
            "dispatch_locked": locked_count,
            "route_summary": route_summary,
        },
        "tags": ["dispatch", "orchestration", "v2", "health"],
    }


def last_dispatch_time(events: List[Dict[str, Any]], skill_id: str, input_id: str) -> Optional[datetime]:
    for event in reversed(events):
        if event.get("type") != "dispatch_requested":
            continue
        payload = event.get("payload", {})
        if payload.get("target_skill_id") != skill_id:
            continue
        if payload.get("target_input_id") != input_id:
            continue
        return parse_iso(event.get("time") or event.get("created_at"))
    return None


def build_dispatch_event(event: Dict[str, Any], skill_id: str, input_id: str, pattern: str, dedupe_key: str) -> Dict[str, Any]:
    event_id = event.get("id")
    correlation_id = event.get("correlation_id") or event_id
    return {
        "id": str(uuid.uuid4()),
        "type": "dispatch_requested",
        "time": now_iso(),
        "created_at": now_iso(),
        "source": {"skill_id": WATCHER_ID},
        "severity": "info",
        "status": "new",
        "dedupe_key": dedupe_key,
        "correlation_id": correlation_id,
        "parent_id": event_id,
        "payload": {
            "trigger_event_id": event_id,
            "target_skill_id": skill_id,
            "target_input_id": input_id,
            "reason": f"Matched pattern {pattern}",
        },
        "tags": ["dispatch", "orchestration", "v2"],
    }


def build_locked_event(event: Dict[str, Any], skill_id: str, input_id: str, reason: str, dedupe_key: str) -> Dict[str, Any]:
    event_id = event.get("id")
    correlation_id = event.get("correlation_id") or event_id
    return {
        "id": str(uuid.uuid4()),
        "type": "dispatch_locked",
        "time": now_iso(),
        "created_at": now_iso(),
        "source": {"skill_id": WATCHER_ID},
        "severity": "warning",
        "status": "new",
        "dedupe_key": dedupe_key,
        "correlation_id": correlation_id,
        "parent_id": event_id,
        "payload": {
            "trigger_event_id": event_id,
            "target_skill_id": skill_id,
            "target_input_id": input_id,
            "reason": reason,
        },
        "tags": ["dispatch", "orchestration", "v2", "locked"],
    }


def should_lock_dispatch(event: Dict[str, Any], skill_id: str, event_type: str) -> Tuple[bool, str]:
    """
    Guardrails for mutation-heavy issue lifecycle dispatches.
    - issue ingest requires concrete message + evidence/confidence
    - issue close requires linked fix evidence
    """
    if skill_id != "issue-tracker-guardian":
        return False, ""

    payload = event.get("payload", {}) if isinstance(event.get("payload"), dict) else {}
    if payload.get("bypass_guardrails") is True:
        return False, ""

    evt = (event_type or "").strip().lower()
    if evt == "issue:ingest_requested":
        has_message = bool(str(payload.get("message", "")).strip())
        has_evidence = bool(payload.get("evidence")) or bool(payload.get("confidence"))
        if not has_message or not has_evidence:
            return True, "missing required ingest evidence (message + evidence/confidence)"

    if evt == "issue:close_requested":
        has_link = bool(payload.get("linked_fix")) or bool(payload.get("commit")) or bool(payload.get("pr"))
        if not has_link:
            return True, "missing linked fix evidence for close request"

    return False, ""


def process_events(state: Dict[str, Any], manifests: List[Dict[str, Any]]) -> Tuple[bool, int, int, int]:
    events: List[Dict[str, Any]] = state.get("events", [])
    original_len = len(events)

    cursor = state.get("cursors", {}).get(WATCHER_ID, {})
    last_index = cursor.get("last_event_index", -1)
    if not isinstance(last_index, int) or last_index >= original_len:
        last_index = -1

    dedupe_keys = {event.get("dedupe_key") for event in events if event.get("dedupe_key")}
    pending_dispatches: List[Dict[str, Any]] = []
    pending_locks: List[Dict[str, Any]] = []
    now = datetime.now(timezone.utc)
    route_summary = summarize_manifest_routes(manifests)

    print(f"Scanning {original_len} events against {len(manifests)} v2 manifests...")
    scanned_events = max(0, original_len - (last_index + 1))

    for event in events[last_index + 1 : original_len]:
        event_type = event.get("type")
        event_id = event.get("id")
        if not event_type or not event_id:
            continue
        if event_type in IGNORED_EVENT_TYPES:
            continue

        matched_candidates: List[Dict[str, Any]] = []
        for manifest in manifests:
            skill_id = manifest.get("_skill_id")
            if not skill_id or skill_id == WATCHER_ID:
                continue

            dispatch_cfg = manifest.get("dispatch", {})
            cooldown_default = dispatch_cfg.get("cooldown", 0)
            try:
                cooldown_default = int(cooldown_default)
            except (TypeError, ValueError):
                cooldown_default = 0

            handlers = manifest.get("inputs", []) or []
            for handler in handlers:
                pattern = handler.get("pattern") or handler.get("event_type")
                if not isinstance(pattern, str):
                    continue
                if not match_pattern(pattern, event_type):
                    continue
                if handler_excludes_event(handler, event_type):
                    continue

                input_id = handler.get("id")
                if not input_id:
                    safe_pattern = pattern.replace("*", "any").replace(".", "_").replace(":", "_")
                    input_id = f"legacy_{safe_pattern}"

                cooldown = handler.get("cooldown")
                if cooldown is None:
                    cooldown = handler.get("cooldown_seconds", cooldown_default)
                try:
                    cooldown = int(cooldown)
                except (TypeError, ValueError):
                    cooldown = cooldown_default

                matched_candidates.append(
                    {
                        "skill_id": skill_id,
                        "input_id": input_id,
                        "pattern": pattern,
                        "cooldown": cooldown,
                        "route_mode": str(handler.get("route_mode") or "owned").strip().lower(),
                        "route_priority": parse_route_priority(handler),
                    }
                )

        for candidate in select_route_candidates(matched_candidates):
            skill_id = str(candidate.get("skill_id"))
            input_id = str(candidate.get("input_id"))
            pattern = str(candidate.get("pattern"))
            cooldown = int(candidate.get("cooldown", 0))

            last_time = last_dispatch_time(events + pending_dispatches, skill_id, input_id)
            if cooldown > 0 and last_time is not None:
                if (now - last_time).total_seconds() < cooldown:
                    continue

            dedupe_key = f"dispatch:{event_id}:{skill_id}:{input_id}"
            if dedupe_key in dedupe_keys:
                continue

            lock, reason = should_lock_dispatch(event, skill_id, event_type)
            if lock:
                lock_key = f"dispatch_locked:{event_id}:{skill_id}:{input_id}:{reason}"
                if lock_key in dedupe_keys:
                    continue
                lock_event = build_locked_event(event, skill_id, input_id, reason, lock_key)
                pending_locks.append(lock_event)
                dedupe_keys.add(lock_key)
                print(f"  -> LOCKED: {skill_id} ({input_id}) reason={reason}")
                continue

            dispatch_event = build_dispatch_event(event, skill_id, input_id, pattern, dedupe_key)
            pending_dispatches.append(dispatch_event)
            dedupe_keys.add(dedupe_key)
            print(f"  -> QUEUED: dispatch_requested -> {skill_id} ({input_id})")

    changed = False
    if pending_dispatches:
        state["events"].extend(pending_dispatches)
        changed = True
    if pending_locks:
        state["events"].extend(pending_locks)
        changed = True
    health_dedupe = f"dispatch_health:{last_index}:{original_len}:{len(pending_dispatches)}:{len(pending_locks)}"
    if health_dedupe not in dedupe_keys:
        health_event = build_dispatch_health_event(
            scanned_events=scanned_events,
            dispatch_count=len(pending_dispatches),
            locked_count=len(pending_locks),
            route_summary=route_summary,
            dedupe_key=health_dedupe,
        )
        state["events"].append(health_event)
        changed = True
        dedupe_keys.add(health_dedupe)

    next_cursor = {
        "last_event_index": original_len - 1,
        "last_event_id": events[original_len - 1].get("id") if original_len > 0 else None,
        "updated_at": now_iso(),
    }
    if cursor != next_cursor:
        state.setdefault("cursors", {})[WATCHER_ID] = next_cursor
        changed = True

    return changed, len(pending_dispatches), len(pending_locks), scanned_events


def run_once(bus_path: Path, skills_root: Path) -> None:
    state = load_state(bus_path)
    manifests = load_manifests(skills_root)
    changed, dispatch_count, lock_count, scanned_count = process_events(state, manifests)
    if changed:
        save_state(bus_path, state)
    if dispatch_count == 0:
        print(f"No new dispatches needed (scanned={scanned_count}, locked={lock_count}).")
    else:
        print(
            f"Committed {dispatch_count} dispatch events to the bus "
            f"(scanned={scanned_count}, locked={lock_count})."
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Pulse Bus v2 watcher")
    parser.add_argument("--bus", default=str(ECOSYSTEM_STATE_PATH))
    parser.add_argument("--skills-root", default=str(SKILLS_ROOT))
    parser.add_argument("--poll-interval", type=float, default=1.5)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()

    bus_path = Path(args.bus)
    skills_root = Path(args.skills_root)

    if args.once:
        run_once(bus_path, skills_root)
        return

    last_mtime: Optional[float] = None
    while True:
        try:
            mtime = bus_path.stat().st_mtime
        except FileNotFoundError:
            mtime = None

        if mtime != last_mtime:
            run_once(bus_path, skills_root)
            try:
                last_mtime = bus_path.stat().st_mtime
            except FileNotFoundError:
                last_mtime = None

        time.sleep(args.poll_interval)


if __name__ == "__main__":
    main()
