#!/usr/bin/env python3
"""
Lifecycle Orphan Process Guardian

Portable lifecycle regression checker:
- Static checks (optional): verify required hook/cleanup patterns in source files.
- Runtime checks (optional): launch -> shutdown -> verify no residual matched processes.
- Apply mode: best-effort cleanup of residual process trees.
"""

from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import json
import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


DEFAULT_WARMUP_SEC = 4.0
DEFAULT_SHUTDOWN_WAIT_SEC = 8.0
DEFAULT_GRACE_KILL_SEC = 1.5


@dataclasses.dataclass
class ProcInfo:
    pid: int
    ppid: int
    command: str
    matched_by: list[str]


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rule_applies_to_target(rule: dict[str, Any], target_path: Path, workspace_root: Path) -> bool:
    targets = rule.get("targets") or []
    target_pattern = str(rule.get("target_pattern", "")).strip()

    target_abs = target_path.resolve().as_posix()
    try:
        target_rel = target_path.resolve().relative_to(workspace_root).as_posix()
    except ValueError:
        target_rel = ""

    if targets:
        for raw in targets:
            candidate = str(raw).strip()
            if not candidate:
                continue
            candidate_path = Path(candidate).expanduser()
            if candidate_path.is_absolute():
                if target_abs == candidate_path.resolve().as_posix():
                    return True
                continue
            normalized = candidate.replace("\\", "/").lstrip("./")
            if target_rel and target_rel == normalized:
                return True
            if target_abs.endswith(f"/{normalized}") or target_abs.endswith(normalized):
                return True
        return False

    if target_pattern:
        try:
            return re.search(target_pattern, target_rel or target_abs) is not None
        except re.error:
            return False

    return True


def shell_run(cmd: str, cwd: Path | None, timeout: float | None = None) -> dict[str, Any]:
    start = time.time()
    proc = subprocess.run(
        cmd,
        shell=True,
        cwd=str(cwd) if cwd else None,
        text=True,
        capture_output=True,
        timeout=timeout,
    )
    return {
        "cmd": cmd,
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "duration_sec": round(time.time() - start, 3),
    }


def list_processes(patterns: list[str]) -> dict[int, ProcInfo]:
    compiled = [re.compile(p) for p in patterns]
    me = os.getpid()
    out = subprocess.run(
        ["ps", "-axo", "pid=,ppid=,command="],
        text=True,
        capture_output=True,
        check=False,
    )
    rows = out.stdout.splitlines()
    parsed_rows: list[tuple[int, int, str]] = []
    ppid_map: dict[int, int] = {}
    for row in rows:
        row = row.strip()
        if not row:
            continue
        parts = row.split(None, 2)
        if len(parts) < 3:
            continue
        try:
            pid = int(parts[0])
            ppid = int(parts[1])
        except ValueError:
            continue
        cmd = parts[2]
        parsed_rows.append((pid, ppid, cmd))
        ppid_map[pid] = ppid

    # Avoid matching this checker and its shell ancestry (regex can appear in CLI args).
    excluded_pids: set[int] = set()
    cursor = me
    for _ in range(64):
        if cursor in excluded_pids:
            break
        excluded_pids.add(cursor)
        parent = ppid_map.get(cursor)
        if not parent or parent <= 1:
            break
        cursor = parent

    found: dict[int, ProcInfo] = {}
    for pid, ppid, cmd in parsed_rows:
        if pid in excluded_pids:
            continue
        hits = [pat.pattern for pat in compiled if pat.search(cmd)]
        if hits:
            found[pid] = ProcInfo(pid=pid, ppid=ppid, command=cmd, matched_by=hits)
    return found


def expand_tree(seed_pids: set[int], process_map: dict[int, ProcInfo]) -> set[int]:
    expanded = set(seed_pids)
    changed = True
    while changed:
        changed = False
        for pid, info in process_map.items():
            if info.ppid in expanded and pid not in expanded:
                expanded.add(pid)
                changed = True
    return expanded


def kill_pids(pids: set[int], sig: int) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for pid in sorted(pids, reverse=True):
        try:
            os.kill(pid, sig)
            results.append({"pid": pid, "signal": sig, "ok": True, "error": None})
        except ProcessLookupError:
            results.append({"pid": pid, "signal": sig, "ok": True, "error": "not_running"})
        except Exception as exc:  # noqa: BLE001
            results.append({"pid": pid, "signal": sig, "ok": False, "error": str(exc)})
    return results


def render_md(report: dict[str, Any]) -> str:
    static = report.get("static_checks", {})
    runtime = report.get("runtime_checks", {})
    lines: list[str] = []
    lines.append("# Lifecycle Orphan Process Guardian Report")
    lines.append("")
    lines.append(f"- Timestamp: {report.get('timestamp')}")
    lines.append(f"- Mode: `{report.get('mode')}`")
    lines.append(f"- Passed: `{report.get('passed')}`")
    lines.append("")
    lines.append("## Static Checks")
    lines.append("")
    lines.append(f"- Enabled: `{static.get('enabled', False)}`")
    lines.append(f"- Passed: `{static.get('passed', True)}`")
    if static.get("findings"):
        lines.append("- Findings:")
        for item in static["findings"]:
            lines.append(f"  - `{item['id']}` in `{item['target']}`: expected >= {item['required']}, found {item['found']}")
    lines.append("")
    lines.append("## Runtime Checks")
    lines.append("")
    lines.append(f"- Enabled: `{runtime.get('enabled', False)}`")
    lines.append(f"- Passed: `{runtime.get('passed', True)}`")
    if runtime.get("baseline_count") is not None:
        lines.append(f"- Baseline matches: `{runtime.get('baseline_count')}`")
    if runtime.get("during_count") is not None:
        lines.append(f"- During-run matches: `{runtime.get('during_count')}`")
    if runtime.get("residual_count") is not None:
        lines.append(f"- Residual matches after shutdown: `{runtime.get('residual_count')}`")
    if runtime.get("residual"):
        lines.append("- Residual processes:")
        for p in runtime["residual"]:
            lines.append(f"  - `{p['pid']}` ppid=`{p['ppid']}` `{p['command']}`")
    if runtime.get("cleanup_actions"):
        lines.append("- Cleanup actions:")
        for action in runtime["cleanup_actions"]:
            sig = action.get("signal")
            sig_name = "SIGTERM" if sig == int(signal.SIGTERM) else "SIGKILL" if sig == int(signal.SIGKILL) else str(sig)
            lines.append(f"  - pid `{action['pid']}` -> `{sig_name}` ok=`{action['ok']}` error=`{action['error']}`")
    lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def load_profile(root: Path, profile_name: str | None) -> dict[str, Any]:
    if not profile_name:
        return {}
    profiles_path = root / "references" / "profiles.json"
    if not profiles_path.exists():
        raise FileNotFoundError(f"profiles.json not found: {profiles_path}")
    data = json.loads(profiles_path.read_text())
    profiles = data.get("profiles", {})
    if profile_name not in profiles:
        raise KeyError(f"Unknown profile '{profile_name}'. Available: {', '.join(sorted(profiles.keys()))}")
    return profiles[profile_name]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit and remediate orphan process lifecycle regressions.")
    parser.add_argument("--mode", choices=["audit", "apply"], default="audit")
    parser.add_argument("--workspace-root", default=".", help="Root used to resolve relative static target paths.")
    parser.add_argument("--profile", default="", help="Optional profile name from references/profiles.json.")
    parser.add_argument("--launch-cmd", default="", help="Command used to start the target app/service.")
    parser.add_argument("--shutdown-cmd", default="", help="Command used to gracefully stop the target app/service.")
    parser.add_argument("--process-match", action="append", default=[], help="Regex pattern to identify target processes (repeatable).")
    parser.add_argument("--static-target", action="append", default=[], help="Source file path for static checks (repeatable).")
    parser.add_argument("--required-pattern", action="append", default=[], help="Regex required in each static target (repeatable).")
    parser.add_argument("--warmup-sec", type=float, default=DEFAULT_WARMUP_SEC)
    parser.add_argument("--shutdown-wait-sec", type=float, default=DEFAULT_SHUTDOWN_WAIT_SEC)
    parser.add_argument("--grace-kill-sec", type=float, default=DEFAULT_GRACE_KILL_SEC)
    parser.add_argument("--strict", type=str, default="true", help="true|false. If true, non-passing checks return code 2.")
    parser.add_argument("--report-json", default="", help="Optional output path for JSON report.")
    parser.add_argument("--report-md", default="", help="Optional output path for Markdown report.")
    parser.add_argument("--skip-static", action="store_true", help="Disable static code checks.")
    parser.add_argument("--skip-runtime", action="store_true", help="Disable runtime launch/shutdown process checks.")
    return parser.parse_args()


def as_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def main() -> int:
    args = parse_args()
    skill_root = Path(__file__).resolve().parents[1]
    workspace_root = Path(args.workspace_root).expanduser().resolve()

    profile: dict[str, Any] = {}
    try:
        profile = load_profile(skill_root, args.profile or None)
    except Exception as exc:  # noqa: BLE001
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1

    launch_cmd = args.launch_cmd or profile.get("launch_cmd", "")
    shutdown_cmd = args.shutdown_cmd or profile.get("shutdown_cmd", "")

    process_patterns = list(args.process_match)
    process_patterns.extend(profile.get("process_match", []))
    process_patterns = [p for p in process_patterns if p]

    static_targets = list(args.static_target)
    static_targets.extend(profile.get("static_targets", []))
    static_targets = [t for t in static_targets if t]

    required_patterns = list(args.required_pattern)
    required_patterns.extend(profile.get("required_patterns_plain", []))

    profile_required = profile.get("required_patterns", [])

    report: dict[str, Any] = {
        "timestamp": utc_now(),
        "mode": args.mode,
        "profile": args.profile or None,
        "config": {
            "workspace_root": str(workspace_root),
            "launch_cmd": launch_cmd,
            "shutdown_cmd": shutdown_cmd,
            "process_match": process_patterns,
            "static_targets": static_targets,
            "required_patterns_plain": required_patterns,
            "warmup_sec": args.warmup_sec,
            "shutdown_wait_sec": args.shutdown_wait_sec,
            "grace_kill_sec": args.grace_kill_sec,
            "strict": as_bool(args.strict),
            "skip_static": args.skip_static,
            "skip_runtime": args.skip_runtime,
        },
    }

    static_findings: list[dict[str, Any]] = []
    static_enabled = (not args.skip_static) and bool(static_targets and (required_patterns or profile_required))
    if static_enabled:
        plain_compiled = [re.compile(p) for p in required_patterns]
        for target in static_targets:
            tpath = Path(target)
            if not tpath.is_absolute():
                tpath = workspace_root / tpath
            if not tpath.exists():
                static_findings.append(
                    {"id": "target_missing", "target": str(tpath), "required": 1, "found": 0, "pattern": "<file exists>"}
                )
                continue
            text = tpath.read_text(errors="ignore")

            for regex in plain_compiled:
                hits = len(regex.findall(text))
                if hits < 1:
                    static_findings.append(
                        {"id": "required_pattern_missing", "target": str(tpath), "required": 1, "found": hits, "pattern": regex.pattern}
                    )

            for item in profile_required:
                rid = item.get("id", "profile_rule")
                patt = item.get("pattern", "")
                required = int(item.get("count_at_least", 1))
                if not rule_applies_to_target(item, tpath, workspace_root):
                    continue
                if not patt:
                    continue
                hits = len(re.findall(patt, text, flags=re.MULTILINE))
                if hits < required:
                    static_findings.append(
                        {
                            "id": rid,
                            "target": str(tpath),
                            "required": required,
                            "found": hits,
                            "pattern": patt,
                            "description": item.get("description", ""),
                        }
                    )

    static_passed = len(static_findings) == 0
    report["static_checks"] = {
        "enabled": static_enabled,
        "passed": static_passed,
        "findings": static_findings,
    }

    runtime_enabled = (not args.skip_runtime) and bool(launch_cmd and shutdown_cmd and process_patterns)
    runtime: dict[str, Any] = {
        "enabled": runtime_enabled,
        "passed": True,
        "baseline_count": None,
        "during_count": None,
        "residual_count": None,
        "baseline": [],
        "during": [],
        "residual": [],
        "cleanup_actions": [],
        "launch_result": None,
        "shutdown_result": None,
    }

    if runtime_enabled:
        baseline = list_processes(process_patterns)
        runtime["baseline_count"] = len(baseline)
        runtime["baseline"] = [dataclasses.asdict(v) for v in baseline.values()]

        launch_proc = subprocess.Popen(
            launch_cmd,
            shell=True,
            cwd=str(workspace_root),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        runtime["launch_result"] = {"pid": launch_proc.pid, "cmd": launch_cmd}

        time.sleep(max(0.0, args.warmup_sec))
        during = list_processes(process_patterns)
        runtime["during_count"] = len(during)
        runtime["during"] = [dataclasses.asdict(v) for v in during.values()]

        shutdown_result = shell_run(shutdown_cmd, workspace_root)
        runtime["shutdown_result"] = shutdown_result

        deadline = time.time() + max(0.0, args.shutdown_wait_sec)
        residual: dict[int, ProcInfo] = {}
        while time.time() < deadline:
            current = list_processes(process_patterns)
            residual = {pid: info for pid, info in current.items() if pid not in baseline}
            if not residual:
                break
            time.sleep(0.3)

        if residual and args.mode == "apply":
            all_current = list_processes(process_patterns)
            residual_pids = set(residual.keys())
            tree = expand_tree(residual_pids, all_current)
            runtime["cleanup_actions"].extend(kill_pids(tree, int(signal.SIGTERM)))
            time.sleep(max(0.0, args.grace_kill_sec))

            current_after_term = list_processes(process_patterns)
            still = {pid: info for pid, info in current_after_term.items() if pid not in baseline}
            if still:
                still_tree = expand_tree(set(still.keys()), current_after_term)
                runtime["cleanup_actions"].extend(kill_pids(still_tree, int(signal.SIGKILL)))
                time.sleep(0.3)

            final_current = list_processes(process_patterns)
            residual = {pid: info for pid, info in final_current.items() if pid not in baseline}

        runtime["residual_count"] = len(residual)
        runtime["residual"] = [dataclasses.asdict(v) for v in residual.values()]
        runtime["passed"] = len(residual) == 0 and int(runtime["shutdown_result"]["returncode"]) == 0

    report["runtime_checks"] = runtime

    passed = static_passed and (runtime["passed"] if runtime_enabled else True)
    report["passed"] = passed

    if args.report_json:
        out_json = Path(args.report_json).expanduser()
        out_json.parent.mkdir(parents=True, exist_ok=True)
        out_json.write_text(json.dumps(report, indent=2))
    if args.report_md:
        out_md = Path(args.report_md).expanduser()
        out_md.parent.mkdir(parents=True, exist_ok=True)
        out_md.write_text(render_md(report))

    print(json.dumps({"passed": report["passed"], "mode": args.mode, "profile": report["profile"]}))

    if as_bool(args.strict) and not report["passed"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
