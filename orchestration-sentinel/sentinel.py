import json
import uuid
import time
import subprocess
from pathlib import Path
from typing import Dict, List, Any, Optional

BUS_PATH = Path(".agent/ecosystem_state.json")
SKILLS_ROOT = Path(".agent/skills")

def load_json(path: Path) -> Dict[str, Any]:
    if not path.exists(): return {}
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}

def write_json(path: Path, data: Dict[str, Any]):
    # Atomic write to avoid corruption
    tmp_path = path.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(data, indent=2))
    tmp_path.replace(path)

class OrchestrationSentinel:
    def __init__(self):
        self.manifest_cache = {}
        self.load_manifests()

    def load_manifests(self):
        """Scans all skills for manifest.json"""
        for skill_dir in SKILLS_ROOT.iterdir():
            manifest_path = skill_dir / "manifest.json"
            if manifest_path.exists():
                manifest = load_json(manifest_path)
                if "skill_id" in manifest:
                    self.manifest_cache[manifest["skill_id"]] = manifest

    def match_listeners(self, event: Dict[str, Any]) -> List[str]:
        """Finds skills that want to handle this event"""
        listeners = []
        for skill_id, manifest in self.manifest_cache.items():
            for inp in manifest.get("inputs", []):
                # Simple wildcard matching
                pattern = inp["event_type"].replace("*", "")
                if pattern in event["type"]:
                    listeners.append(skill_id)
        return list(set(listeners))

    def dispatch(self, handlers: List[str], event: Dict[str, Any]):
        """Triggers downstream skills"""
        for skill_id in handlers:
            print(f"🔥 Sentinel: Triggering {skill_id} for event {event['type']}")
            
            # Record dispatch request to bus
            dispatch_event = {
                "id": str(uuid.uuid4()),
                "time": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                "source": {"skill_id": "orchestration_sentinel"},
                "type": "dispatch_requested",
                "severity": "info",
                "status": "new",
                "payload": {
                    "target_skill": skill_id,
                    "trigger_event_id": event["id"]
                }
            }
            # Append atomic logic here (reading bus, appending, writing)
            # For simplicity in this scaffold, we just print
            print(json.dumps(dispatch_event, indent=2))

    def watch(self):
        print("👁️ Orchestration Sentinel watching Pulse Bus...")
        last_mtime = 0
        while True:
            try:
                if BUS_PATH.stat().st_mtime != last_mtime:
                    last_mtime = BUS_PATH.stat().st_mtime
                    bus = load_json(BUS_PATH)
                    events = bus.get("events", [])
                    
                    # Simple cursor logic: process all new events
                    # In production, use 'cursors' object in bus
                    for event in events[-5:]: # Check last 5
                        handlers = self.match_listeners(event)
                        if handlers:
                            self.dispatch(handlers, event)
            except FileNotFoundError:
                pass
            time.sleep(1)

if __name__ == "__main__":
    sentinel = OrchestrationSentinel()
    sentinel.watch()
