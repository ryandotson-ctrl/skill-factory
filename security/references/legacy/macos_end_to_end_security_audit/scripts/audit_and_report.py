#!/usr/bin/env python3
"""Apple-level, read-only macOS security + privacy audit.

Goals
- Non-destructive: no deletes, no unloads, no settings changes.
- Privacy-first defaults: prints a redacted console summary by default and writes no files.
- Additive outputs are opt-in: PDF and history snapshot only when explicitly requested.
- High signal: persistence + background items, network surface, trust signals, privacy controls.
- Privacy-aware: default redaction avoids leaking sensitive endpoints/paths.

This script intentionally avoids non-standard Python deps.
"""

from __future__ import annotations

import argparse
import errno
import json
import os
import plistlib
import re
import shutil
import sqlite3
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


# --------------------------
# Config + findings
# --------------------------


@dataclass(frozen=True)
class AuditConfig:
    depth: str  # standard|deep
    privacy: str  # strict|balanced|forensics
    format: str  # text|json
    generate_pdf: bool
    output_dir: Path
    output_pdf: Optional[Path]
    keep_history: bool
    diff_last: bool
    max_rows: int
    recent_apps_days: int
    recent_apps_max: int
    tcc_recent_log_minutes: Optional[int]


@dataclass(frozen=True)
class CommandResult:
    rc: int
    out: str
    kind: str = "ok"  # ok|blocked|timeout|error
    duration_ms: int = 0


@dataclass(frozen=True)
class Finding:
    severity: str  # CRITICAL|HIGH|MEDIUM|LOW|INFO
    title: str
    pillar: str
    evidence: str


SEV_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "INFO": 4}

# Default destinations are private (not Desktop) to avoid clutter and reduce leakage risk.
DEFAULT_REPORTS_DIR = Path.home() / "Library/Application Support/macos_end_to_end_security_audit/reports"
DEFAULT_HISTORY_DIR = Path.home() / "Library/Application Support/macos_end_to_end_security_audit/history"


def list_history_snapshots(hist_dir: Path = DEFAULT_HISTORY_DIR) -> List[Path]:
    try:
        if not hist_dir.exists():
            return []
        snaps = [p for p in hist_dir.glob("snapshot_*.json") if p.is_file()]
        return sorted(snaps, key=lambda p: p.stat().st_mtime)
    except Exception:
        return []


def read_json_file(p: Path) -> Optional[dict]:
    try:
        return json.loads(p.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return None


def diff_snapshots(prev: dict, curr: dict) -> dict:
    """Compute a small, high-signal delta between two sanitized snapshots."""
    out: dict = {}

    prev_inv = prev.get("inventory") or {}
    curr_inv = curr.get("inventory") or {}

    def _set(v: object) -> set[str]:
        if not isinstance(v, list):
            return set()
        return {str(x) for x in v if str(x)}

    prev_listeners = _set(prev_inv.get("listeners_ports"))
    curr_listeners = _set(curr_inv.get("listeners_ports"))
    new_listeners = sorted(curr_listeners - prev_listeners)
    gone_listeners = sorted(prev_listeners - curr_listeners)
    if new_listeners or gone_listeners:
        out["listeners_ports"] = {"new": new_listeners, "removed": gone_listeners}

    prev_persist = _set(prev_inv.get("persistence_execs"))
    curr_persist = _set(curr_inv.get("persistence_execs"))
    new_persist = sorted(curr_persist - prev_persist)
    gone_persist = sorted(prev_persist - curr_persist)
    if new_persist or gone_persist:
        out["persistence_execs"] = {"new": new_persist[:50], "removed": gone_persist[:50], "truncated": (len(new_persist) > 50 or len(gone_persist) > 50)}

    prev_flagged = _set(prev_inv.get("recent_apps_flagged"))
    curr_flagged = _set(curr_inv.get("recent_apps_flagged"))
    new_flagged = sorted(curr_flagged - prev_flagged)
    gone_flagged = sorted(prev_flagged - curr_flagged)
    if new_flagged or gone_flagged:
        out["recent_apps_flagged"] = {"new": new_flagged[:30], "removed": gone_flagged[:30], "truncated": (len(new_flagged) > 30 or len(gone_flagged) > 30)}

    prev_posture = prev.get("posture") or {}
    curr_posture = curr.get("posture") or {}
    posture_changes: dict = {}
    if isinstance(prev_posture, dict) and isinstance(curr_posture, dict):
        keys = sorted(set(prev_posture.keys()) | set(curr_posture.keys()))
        for k in keys:
            if prev_posture.get(k) != curr_posture.get(k):
                posture_changes[k] = {"from": prev_posture.get(k), "to": curr_posture.get(k)}
    if posture_changes:
        out["posture_changes"] = posture_changes

    # Trust/proxy/profile signals are particularly important; surface separately.
    for k in ["Proxy configured", "Custom trust settings", "MDM enrolled", "Profiles present"]:
        if isinstance(prev_posture, dict) and isinstance(curr_posture, dict):
            if prev_posture.get(k) != curr_posture.get(k):
                out.setdefault("high_signal_posture", {})[k] = {"from": prev_posture.get(k), "to": curr_posture.get(k)}

    return out


@dataclass(frozen=True)
class AuditResult:
    generated: str
    user: str
    os: str
    kernel: str
    posture: Dict[str, str]
    counts: Dict[str, int]
    findings: List[Finding]
    unknowns: List[str]
    top_processes: List[List[str]]
    snapshot: dict
    # Internal: raw/parsed data used for PDF generation and richer console context.
    data: dict


# --------------------------
# Command runner (allowlisted)
# --------------------------


class CommandRunner:
    def __init__(self):
        self.allowed = {
            "plutil",
            "uname",
            "sw_vers",
            "whoami",
            "id",
            "uptime",
            "date",
            "csrutil",
            "spctl",
            "fdesetup",
            "profiles",
            "systemextensionsctl",
            "kmutil",
            "scutil",
            "lsof",
            "launchctl",
            "brew",
            "sfltool",
            "security",
            "sharing",
            "ps",
            "crontab",
            "codesign",
            "defaults",
            "log",
        }
        self.allowed_paths = {
            "/usr/libexec/ApplicationFirewall/socketfilterfw",
        }

    def run(self, cmd: Sequence[str], timeout_s: int = 20) -> CommandResult:
        if not cmd:
            return CommandResult(999, "(empty command)\n", kind="error", duration_ms=0)
        exe = cmd[0]
        base = os.path.basename(exe)
        if exe not in self.allowed_paths and base not in self.allowed and exe not in self.allowed:
            return CommandResult(999, f"(blocked: command not allowlisted: {exe})\n", kind="blocked", duration_ms=0)

        t0 = time.monotonic()
        try:
            p = subprocess.run(
                list(cmd),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=timeout_s,
                check=False,
            )
            dt = int((time.monotonic() - t0) * 1000)
            return CommandResult(p.returncode, p.stdout or "", kind="ok", duration_ms=dt)
        except subprocess.TimeoutExpired as e:
            dt = int((time.monotonic() - t0) * 1000)
            out = ""
            # subprocess.TimeoutExpired may carry partial output in .stdout/.output.
            partial = getattr(e, "stdout", None) or getattr(e, "output", None)
            if isinstance(partial, bytes):
                out = partial.decode("utf-8", errors="replace")
            elif isinstance(partial, str):
                out = partial
            msg = f"(timeout after {timeout_s}s: {cmd!r})\n"
            return CommandResult(124, msg + (out or ""), kind="timeout", duration_ms=dt)
        except Exception as e:
            dt = int((time.monotonic() - t0) * 1000)
            return CommandResult(999, f"(failed to run {cmd!r}: {e})\n", kind="error", duration_ms=dt)


def run_with_retry(runner: CommandRunner, cmd: Sequence[str], timeouts_s: Sequence[int]) -> CommandResult:
    """Run a command with a small timeout ladder.

    Only retries on timeouts. This prevents "hangy" commands from producing misleading
    empty/zero results in downstream parsers.
    """
    last: Optional[CommandResult] = None
    for t in timeouts_s:
        res = runner.run(cmd, timeout_s=int(t))
        last = res
        if res.kind != "timeout":
            return res
    return last or CommandResult(999, "(failed to run)\n", kind="error", duration_ms=0)


def btm_enabled_count_from_result(btm_res: CommandResult, btm_items: List[BackgroundItem]) -> int:
    """BTM is frequently blocked/timeout on some systems; never report a misleading 0."""
    return len(btm_items) if (btm_res.kind == "ok" and btm_res.rc == 0) else -1


# --------------------------
# Redaction + sanitization
# --------------------------


_REDACT_PATTERNS: List[Tuple[re.Pattern[str], str]] = [
    # Specific env tokens
    (re.compile(r"(CLAWDBOT_GATEWAY_TOKEN\s*=>\s*)\"[^\"]+\""), r"\1\"[REDACTED]\""),
    (re.compile(r"(CLAWDBOT_GATEWAY_TOKEN=)[^\s]+"), r"\1[REDACTED]"),
    # Common API token shapes
    (re.compile(r"\b(sk-[A-Za-z0-9]{20,})\b"), "[REDACTED]"),
    (re.compile(r"\b(ghp_[A-Za-z0-9]{20,})\b"), "[REDACTED]"),
    (re.compile(r"\b(xox[baprs]-[A-Za-z0-9-]{10,})\b"), "[REDACTED]"),
    (re.compile(r"\b(AKI[0-9A-Z]{16})\b"), "[REDACTED]"),
    # Long hex-ish blobs (often tokens)
    (re.compile(r"\b([0-9a-f]{32,64})\b", re.IGNORECASE), "[REDACTED_HEX]"),
]


def normalize_ascii(s: str) -> str:
    # PDF content stream is encoded as ASCII in this script.
    # Replace common punctuation first, then replace any remaining non-ASCII.
    if not s:
        return ""
    s = s.replace("\u2019", "'").replace("\u2018", "'")
    s = s.replace("\u201c", '"').replace("\u201d", '"')
    s = s.replace("\u2013", "-").replace("\u2014", "-")
    s = s.replace("\u2026", "...")
    return s.encode("ascii", "replace").decode("ascii")


def redact_tokens(s: str) -> str:
    out = s
    for pat, repl in _REDACT_PATTERNS:
        out = pat.sub(repl, out)
    return out


def redact_paths(s: str, home: Path) -> str:
    # Redact user home paths to ~
    try:
        return s.replace(str(home), "~")
    except Exception:
        return s


def redact_remote_endpoint(ep: str) -> str:
    # Redact host/IP but keep port if present
    if not ep:
        return ep
    if ":" in ep:
        left, right = ep.rsplit(":", 1)
        if right.isdigit():
            return f"[REDACTED_REMOTE]:{right}"
    return "[REDACTED_REMOTE]"


# --------------------------
# Parsers
# --------------------------


@dataclass(frozen=True)
class Listener:
    process: str
    pid: str
    user: str
    proto: str
    listen: str


def parse_lsof_listen(lsof_out: str) -> List[Listener]:
    lines = [ln.rstrip("\n") for ln in lsof_out.splitlines() if ln.strip()]
    if not lines:
        return []

    # Expect header + rows; be tolerant.
    listeners: List[Listener] = []
    for ln in lines[1:]:
        parts = ln.split()
        if len(parts) < 9:
            continue
        proc, pid, user = parts[0], parts[1], parts[2]
        # lsof places protocol in the NODE column; match the whole line so we work across variants.
        m = re.search(r"\b(TCP|UDP)\s+([^\s]+)\s+\(LISTEN\)", ln)
        if not m:
            # Best-effort parse even if LISTEN marker is absent.
            m = re.search(r"\b(TCP|UDP)\s+([^\s]+)", ln)
            if not m:
                continue
        proto, ep = m.group(1), m.group(2)
        listeners.append(Listener(process=proc, pid=pid, user=user, proto=proto, listen=ep))
    return listeners


@dataclass(frozen=True)
class Connection:
    process: str
    pid: str
    user: str
    proto: str
    local: str
    remote: str
    state: str


def parse_lsof_established(lsof_out: str) -> List[Connection]:
    lines = [ln.rstrip("\n") for ln in lsof_out.splitlines() if ln.strip()]
    if not lines:
        return []

    conns: List[Connection] = []
    for ln in lines[1:]:
        parts = ln.split()
        if len(parts) < 9:
            continue
        proc, pid, user = parts[0], parts[1], parts[2]
        # lsof places protocol in the NODE column; match the whole line so we work across variants.
        m = re.search(r"\b(TCP)\s+([^\s]+)->([^\s]+)\s+\(([^)]+)\)", ln)
        if not m:
            continue
        proto, local, remote, state = m.group(1), m.group(2), m.group(3), m.group(4)
        conns.append(Connection(process=proc, pid=pid, user=user, proto=proto, local=local, remote=remote, state=state))
    return conns


@dataclass(frozen=True)
class LaunchItem:
    path: str
    label: str
    kind: str
    loaded: bool
    keepalive: Optional[bool]
    runatload: Optional[bool]
    startinterval: Optional[int]
    exec_path: Optional[str]
    arguments: List[str]
    stdout: Optional[str]
    stderr: Optional[str]


def plist_to_json(path: Path, runner: CommandRunner) -> Optional[dict]:
    # plutil output can be huge; keep timeout small.
    res = runner.run(["plutil", "-convert", "json", "-o", "-", str(path)], timeout_s=10)
    if res.rc != 0:
        return None
    try:
        return json.loads(res.out)
    except Exception:
        return None


def parse_launch_item(path: Path, d: dict, loaded_labels: set[str]) -> LaunchItem:
    label = str(d.get("Label") or path.stem)
    keepalive = d.get("KeepAlive")
    runatload = d.get("RunAtLoad")
    startinterval = d.get("StartInterval")

    program = d.get("Program")
    args = d.get("ProgramArguments") or []
    if program and not args:
        args = [program]

    exec_path = None
    if args and isinstance(args, list) and isinstance(args[0], str):
        exec_path = args[0]
    elif isinstance(program, str):
        exec_path = program

    stdout = d.get("StandardOutPath")
    stderr = d.get("StandardErrorPath")

    kind = "unknown"
    s = str(path)
    if "/Library/LaunchDaemons/" in s:
        kind = "LaunchDaemon"
    elif "/Library/LaunchAgents/" in s:
        kind = "LaunchAgent (system)"
    elif "/Users/" in s and "/Library/LaunchAgents/" in s:
        kind = "LaunchAgent (user)"

    return LaunchItem(
        path=str(path),
        label=label,
        kind=kind,
        loaded=label in loaded_labels,
        keepalive=keepalive if isinstance(keepalive, bool) else None,
        runatload=runatload if isinstance(runatload, bool) else None,
        startinterval=int(startinterval) if isinstance(startinterval, int) else None,
        exec_path=str(exec_path) if isinstance(exec_path, str) else None,
        arguments=[str(a) for a in args if isinstance(a, str)],
        stdout=str(stdout) if isinstance(stdout, str) else None,
        stderr=str(stderr) if isinstance(stderr, str) else None,
    )


@dataclass(frozen=True)
class LaunchctlStatus:
    label: str
    state: str
    runs: Optional[int]
    last_exit: Optional[str]


def parse_launchctl_print(text: str) -> LaunchctlStatus:
    label = "(unknown)"
    m = re.search(r"^(gui/\d+/[^\s]+)", text.strip(), re.M)
    if m:
        label = m.group(1)

    state = "(unknown)"
    m = re.search(r"\n\s*state\s*=\s*([^\n]+)", text)
    if m:
        state = m.group(1).strip()

    runs = None
    m = re.search(r"\n\s*runs\s*=\s*(\d+)", text)
    if m:
        try:
            runs = int(m.group(1))
        except Exception:
            runs = None

    last_exit = None
    m = re.search(r"\n\s*last exit code\s*=\s*([^\n]+)", text)
    if m:
        last_exit = m.group(1).strip()

    return LaunchctlStatus(label=label, state=state, runs=runs, last_exit=last_exit)


@dataclass(frozen=True)
class BackgroundItem:
    scope: str  # UID 501 / UID 0
    identifier: str
    name: str
    team_id: str
    disposition: str
    allowed: Optional[bool]
    exec_path: str
    url: str


def _btm_allowed_from_disposition(disposition: str) -> Optional[bool]:
    s = (disposition or "").lower()
    # Check "disallowed" first since it contains "allowed" as a substring.
    if "disallowed" in s:
        return False
    if "allowed" in s:
        return True
    return None


def parse_sfltool_dumpbtm(text: str) -> List[BackgroundItem]:
    items: List[BackgroundItem] = []
    scope = "(unknown)"

    cur: Dict[str, str] = {}

    def flush():
        nonlocal cur
        if not cur:
            return
        disp = cur.get("Disposition", "")
        if "enabled" not in disp:
            cur = {}
            return
        items.append(
            BackgroundItem(
                scope=scope,
                identifier=cur.get("Identifier", ""),
                name=cur.get("Name", ""),
                team_id=cur.get("Team Identifier", ""),
                disposition=disp,
                allowed=_btm_allowed_from_disposition(disp),
                exec_path=cur.get("Executable Path", ""),
                url=cur.get("URL", ""),
            )
        )
        cur = {}

    for raw in text.splitlines():
        line = raw.rstrip("\n")
        m = re.search(r"^\s*Records for UID\s+([^:]+)\s*:\s*(.*)$", line)
        if m:
            flush()
            scope = f"UID {m.group(1).strip()}"
            continue

        if re.match(r"^\s*#\d+:\s*$", line):
            flush()
            cur = {}
            continue

        m = re.match(r"^\s*([A-Za-z][A-Za-z ]+):\s*(.*)$", line)
        if m:
            key = m.group(1).strip()
            val = m.group(2).strip()
            # Normalize (null)
            if val == "(null)":
                val = ""
            cur[key] = val

    flush()
    # Filter out empties
    return [it for it in items if it.identifier or it.exec_path or it.name]


@dataclass(frozen=True)
class SharePoint:
    name: str
    path: str
    protocol: str
    guest_access: Optional[bool]
    read_only: Optional[bool]


def parse_sharing_list(text: str) -> List[SharePoint]:
    shares: List[SharePoint] = []

    cur_name = ""
    cur_path = ""
    cur_proto = ""
    cur_guest: Optional[bool] = None
    cur_ro: Optional[bool] = None

    def flush():
        nonlocal cur_name, cur_path, cur_proto, cur_guest, cur_ro
        if cur_name or cur_path:
            shares.append(
                SharePoint(
                    name=cur_name,
                    path=cur_path,
                    protocol=cur_proto or "smb",
                    guest_access=cur_guest,
                    read_only=cur_ro,
                )
            )
        cur_name = ""
        cur_path = ""
        cur_proto = ""
        cur_guest = None
        cur_ro = None

    in_proto = False
    for raw in text.splitlines():
        line = raw.rstrip("\n")
        s = line.strip()
        if not s:
            continue
        # Important: top-level "name:"/"path:" have no leading whitespace; nested protocol blocks do.
        if line.lower().startswith("name:"):
            # New share
            if cur_name or cur_path:
                flush()
            cur_name = s.split(":", 1)[1].strip()
            in_proto = False
            continue
        if line.lower().startswith("path:"):
            cur_path = s.split(":", 1)[1].strip()
            continue
        m = re.match(r"^(smb|afp|ftp|webdav):", line.lstrip(), flags=re.IGNORECASE)
        if m:
            cur_proto = m.group(1).lower()
            in_proto = True
            continue
        if line.lstrip().startswith("}"):
            in_proto = False
            continue
        if in_proto:
            # Examples: guest access: 1, read-only: 0
            if line.lstrip().lower().startswith("guest access:"):
                v = line.split(":", 1)[1].strip()
                cur_guest = v == "1"
            if line.lstrip().lower().startswith("read-only:"):
                v = line.split(":", 1)[1].strip()
                cur_ro = v == "1"

    flush()
    return shares


# --------------------------
# Signing / Gatekeeper checks
# --------------------------


@dataclass(frozen=True)
class SigningAssessment:
    path: str
    assessed_path: str
    codesign_rc: int
    codesign_summary: str
    spctl_rc: int
    spctl_summary: str
    spctl_category: str


def normalize_assess_target(exec_path: str) -> str:
    """Prefer assessing the containing bundle rather than an inner binary.

    spctl/codesign checks on the inner binary of an .app frequently produce low-signal
    "does not seem to be an app" rejections; assessing the bundle root is higher signal.
    """
    p = exec_path or ""

    m = re.search(r"^(.+?\.app)(/|$)", p, flags=re.IGNORECASE)
    if m:
        return m.group(1)

    m = re.search(r"^(.+?\.(?:appex|xpc))(/|$)", p, flags=re.IGNORECASE)
    if m:
        return m.group(1)

    return p


def summarize_codesign_display(out: str) -> str:
    # codesign -dv writes to stderr but we capture combined.
    lines = [ln.strip() for ln in (out or "").splitlines() if ln.strip()]
    team = ""
    auth: List[str] = []
    signature = ""
    for ln in lines:
        if ln.startswith("Signature="):
            signature = ln.split("=", 1)[1].strip()
        if ln.startswith("TeamIdentifier="):
            team = ln.split("=", 1)[1].strip()
        if ln.startswith("Authority="):
            auth.append(ln.split("=", 1)[1].strip())
        if "code object is not signed" in ln.lower():
            return "unsigned"

    if signature.lower() == "adhoc":
        return "adhoc"
    # Heuristic: ad-hoc signatures often have no authority chain and TeamIdentifier=not set.
    if (team.lower() == "not set" or not team) and not auth and lines:
        # Avoid incorrectly calling empty output "adhoc".
        if any(k in (out or "").lower() for k in ["teamidentifier=", "signature="]):
            return "adhoc"

    if team:
        return f"TeamID={team}" + (f"; Auth={auth[0]}" if auth else "")
    if auth:
        return f"Auth={auth[0]}"
    return (lines[-1] if lines else "")[:200]


def summarize_spctl_assess(out: str, path_hint: str = "") -> str:
    lines = [ln.strip() for ln in (out or "").splitlines() if ln.strip()]
    hint = (path_hint or "").lower()
    # Common: "<path>: accepted" / "<path>: rejected"
    for ln in lines:
        ll = ln.lower()
        if hint and ll.startswith(hint) and ("accepted" in ll or "rejected" in ll):
            return ln[:200]
    for ln in lines:
        ll = ln.lower()
        if "accepted" in ll or "rejected" in ll or "source=" in ll:
            return ln[:200]
    return (lines[-1] if lines else "")[:200]


def classify_spctl_summary(summary: str) -> str:
    s = (summary or "").lower()
    if "accepted" in s:
        if "notarized" in s:
            return "accepted_notarized"
        if "developer id" in s:
            return "accepted_dev_id"
        return "accepted_other"
    if "does not seem to be an app" in s or "not an app" in s:
        return "rejected_not_app"
    if "no resources but signature indicates they must be present" in s or "resources missing" in s:
        return "rejected_resources_missing"
    if "rejected" in s:
        return "rejected_other"
    return "unknown"


def _spctl_assess_cmd(target_path: str) -> List[str]:
    p = (target_path or "").lower()
    if p.endswith(".app") or p.endswith(".appex") or p.endswith(".xpc"):
        return ["spctl", "--assess", "--verbose=4", target_path]
    return ["spctl", "--assess", "-vv", "--type", "execute", target_path]


def assess_signing(exec_path: str, runner: CommandRunner) -> SigningAssessment:
    target = normalize_assess_target(exec_path)
    cs = runner.run(["codesign", "-dv", "--verbose=4", target], timeout_s=20)
    sp = runner.run(_spctl_assess_cmd(target), timeout_s=20)

    cs_sum = summarize_codesign_display(cs.out)
    sp_sum = summarize_spctl_assess(sp.out, path_hint=target)
    sp_cat = classify_spctl_summary(sp_sum)

    return SigningAssessment(
        path=exec_path,
        assessed_path=target,
        codesign_rc=cs.rc,
        codesign_summary=cs_sum,
        spctl_rc=sp.rc,
        spctl_summary=sp_sum,
        spctl_category=sp_cat,
    )


def classify_exec_path(p: str, home: Path) -> str:
    if not p:
        return "unknown"
    if p.startswith("/System/") or p.startswith("/usr/") and not p.startswith("/usr/local/"):
        return "system"
    if p.startswith("/Applications/"):
        return "applications"
    if p.startswith("/Library/"):
        return "library"
    if p.startswith(str(home) + "/"):
        return "user"
    if p.startswith("/opt/homebrew/") or p.startswith("/usr/local/"):
        return "homebrew"
    return "other"


# --------------------------
# PDF generator (no deps)
# --------------------------


def pdf_escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


@dataclass
class PDFObject:
    obj_id: int
    data: bytes


class PDFBuilder:
    def __init__(self, pagesize: Tuple[int, int] = (612, 792)):
        self.pagesize = pagesize
        self.objects: List[PDFObject] = []
        self.next_id = 1
        self.page_objs: List[int] = []

        # Fonts
        self.font_regular = self._add_obj(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
        self.font_bold = self._add_obj(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>")
        self.font_mono = self._add_obj(b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>")

    def _add_obj(self, data: bytes) -> int:
        oid = self.next_id
        self.next_id += 1
        self.objects.append(PDFObject(oid, data))
        return oid

    def add_page(self, content_stream: bytes) -> None:
        stream = b"<< /Length " + str(len(content_stream)).encode("ascii") + b" >>\nstream\n" + content_stream + b"\nendstream"
        content_id = self._add_obj(stream)

        w, h = self.pagesize
        page_dict = (
            f"<< /Type /Page /Parent 0 0 R /MediaBox [0 0 {w} {h}] "
            f"/Resources << /Font << /F1 {self.font_regular} 0 R /F2 {self.font_bold} 0 R /F3 {self.font_mono} 0 R >> >> "
            f"/Contents {content_id} 0 R >>"
        ).encode("ascii")
        page_id = self._add_obj(page_dict)
        self.page_objs.append(page_id)

    def build(self) -> bytes:
        kids = " ".join([f"{pid} 0 R" for pid in self.page_objs]).encode("ascii")
        pages_id = self._add_obj(b"<< /Type /Pages /Kids [" + kids + b"] /Count " + str(len(self.page_objs)).encode("ascii") + b" >>")

        fixed: List[PDFObject] = []
        for obj in self.objects:
            if obj.obj_id in self.page_objs:
                fixed.append(PDFObject(obj.obj_id, obj.data.replace(b"/Parent 0 0 R", f"/Parent {pages_id} 0 R".encode("ascii"))))
            else:
                fixed.append(obj)
        self.objects = fixed

        catalog_id = self._add_obj(f"<< /Type /Catalog /Pages {pages_id} 0 R >>".encode("ascii"))

        header = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"
        body = bytearray()
        offsets = {0: 0}

        for obj in sorted(self.objects, key=lambda o: o.obj_id):
            offsets[obj.obj_id] = len(header) + len(body)
            body += f"{obj.obj_id} 0 obj\n".encode("ascii")
            body += obj.data
            body += b"\nendobj\n"

        xref_start = len(header) + len(body)
        max_id = max([o.obj_id for o in self.objects] + [0])

        xref = bytearray()
        xref += f"xref\n0 {max_id + 1}\n".encode("ascii")
        xref += b"0000000000 65535 f \n"
        for i in range(1, max_id + 1):
            off = offsets.get(i)
            if off is None:
                xref += b"0000000000 00000 f \n"
            else:
                xref += f"{off:010d} 00000 n \n".encode("ascii")

        trailer = (
            b"trailer\n"
            + f"<< /Size {max_id + 1} /Root {catalog_id} 0 R >>\n".encode("ascii")
            + b"startxref\n"
            + str(xref_start).encode("ascii")
            + b"\n%%EOF\n"
        )

        return header + bytes(body) + bytes(xref) + trailer


class PDFLayout:
    def __init__(self, builder: PDFBuilder, report_title: str, generated: str, margin: int = 54):
        self.b = builder
        self.margin = margin
        self.w, self.h = builder.pagesize
        self.report_title = report_title
        self.generated = generated

        # Leave room for header/footer
        self.top_pad = 36
        self.bottom_pad = 30

        self.pages: List[bytearray] = []
        self.cur: bytearray = bytearray()
        self.page_num = 0

        self.leading = 14
        self.y = 0
        self._new_page()

    def _new_page(self):
        if self.cur:
            self._commit_page()
        self.page_num += 1
        self.cur = bytearray()

        # Header
        header_y = self.h - 26
        self._text(self.margin, header_y, self.report_title, font="F2", size=11)
        self._text(self.margin, header_y - 12, f"Generated: {self.generated}", font="F1", size=9)
        self._line(self.margin, header_y - 18, self.w - self.margin, header_y - 18, width=0.6)

        self.y = self.h - self.margin - self.top_pad

    def _commit_page(self):
        # Footer (page num)
        footer_y = 18
        self._line(self.margin, footer_y + 10, self.w - self.margin, footer_y + 10, width=0.6)
        self._text(self.margin, footer_y, "Treat this report as sensitive.", font="F1", size=9)
        self._text(self.w - self.margin - 80, footer_y, f"Page {self.page_num}", font="F1", size=9)

        self.pages.append(self.cur)

    def finish(self):
        if self.cur and (not self.pages or self.cur is not self.pages[-1]):
            self._commit_page()
        for p in self.pages:
            self.b.add_page(bytes(p))

    def _ensure_space(self, needed: int):
        if self.y - needed < self.margin + self.bottom_pad:
            self._new_page()

    def _text(self, x: float, y: float, text: str, font: str = "F1", size: int = 11):
        t = normalize_ascii(text)
        t = pdf_escape(t)
        self.cur += f"BT /{font} {size} Tf {x:.1f} {y:.1f} Td ({t}) Tj ET\n".encode("ascii")

    def _line(self, x1: float, y1: float, x2: float, y2: float, width: float = 1.0):
        self.cur += f"{width:.2f} w {x1:.1f} {y1:.1f} m {x2:.1f} {y2:.1f} l S\n".encode("ascii")

    def _rect_fill(self, x: float, y: float, w: float, h: float, gray: float):
        self.cur += f"{gray:.3f} g {x:.1f} {y:.1f} {w:.1f} {h:.1f} re f 0 g\n".encode("ascii")

    def heading(self, text: str, level: int = 1):
        size = 18 if level == 1 else 14 if level == 2 else 12
        lead = size + 6
        self._ensure_space(lead)
        self._text(self.margin, self.y, text, font="F2", size=size)
        self.y -= lead

    def paragraph(self, text: str, size: int = 11):
        maxw = self.w - 2 * self.margin
        lines = wrap_text(normalize_ascii(text), maxw, size)
        self._ensure_space(len(lines) * self.leading + 6)
        for ln in lines:
            self._text(self.margin, self.y, ln, font="F1", size=size)
            self.y -= self.leading
        self.y -= 6

    def mono_block(self, text: str, max_lines: int = 6):
        # Small monospaced block for short raw snippets
        lines = [normalize_ascii(ln) for ln in text.splitlines() if ln.strip()][:max_lines]
        if not lines:
            return
        h = len(lines) * 11 + 10
        self._ensure_space(h)
        self._rect_fill(self.margin, self.y - h + 4, self.w - 2 * self.margin, h, gray=0.96)
        yy = self.y - 12
        for ln in lines:
            self._text(self.margin + 6, yy, ln[:110], font="F3", size=9)
            yy -= 11
        self.y -= h + 6

    def table(self, headers: List[str], rows: List[List[str]], col_widths: Optional[List[float]] = None):
        if not rows:
            return
        ncol = len(headers)
        totalw = self.w - 2 * self.margin
        if not col_widths:
            col_widths = [totalw / ncol] * ncol

        header_h = 18
        self._ensure_space(header_h + 8)
        y_top = self.y
        self._rect_fill(self.margin, y_top - header_h + 4, totalw, header_h, gray=0.92)
        x = self.margin
        for i, htxt in enumerate(headers):
            self._text(x + 4, y_top - 12, htxt, font="F2", size=11)
            x += col_widths[i]
        self.y -= header_h

        for r in rows:
            cell_lines: List[List[str]] = []
            max_lines = 1
            for i, cell in enumerate(r):
                cellw = col_widths[i] - 8
                lines = wrap_text(normalize_ascii(cell), cellw, 10)
                cell_lines.append(lines)
                max_lines = max(max_lines, len(lines))

            row_h = max_lines * 12 + 6
            self._ensure_space(row_h + 4)

            y0 = self.y
            # outer rect
            self._line(self.margin, y0 + 2, self.margin + totalw, y0 + 2, width=0.6)
            self._line(self.margin, y0 - row_h + 2, self.margin + totalw, y0 - row_h + 2, width=0.6)
            self._line(self.margin, y0 + 2, self.margin, y0 - row_h + 2, width=0.6)
            self._line(self.margin + totalw, y0 + 2, self.margin + totalw, y0 - row_h + 2, width=0.6)

            # verticals
            x = self.margin
            for i in range(ncol - 1):
                x += col_widths[i]
                self._line(x, y0 + 2, x, y0 - row_h + 2, width=0.6)

            # cell text
            x = self.margin
            for i in range(ncol):
                y_text = y0 - 12
                for ln in cell_lines[i]:
                    self._text(x + 4, y_text, ln, font="F1", size=10)
                    y_text -= 12
                x += col_widths[i]

            self.y -= row_h

        self.y -= 10


def approx_text_width(text: str, font_size: int) -> float:
    return len(text) * font_size * 0.52


def wrap_text(text: str, max_width: float, font_size: int) -> List[str]:
    text = " ".join((text or "").split())
    if not text:
        return [""]
    words = text.split(" ")
    lines: List[str] = []
    cur = ""
    for w in words:
        cand = w if not cur else f"{cur} {w}"
        if approx_text_width(cand, font_size) <= max_width:
            cur = cand
        else:
            if cur:
                lines.append(cur)
            if approx_text_width(w, font_size) <= max_width:
                cur = w
            else:
                chunk = ""
                for ch in w:
                    cand2 = chunk + ch
                    if approx_text_width(cand2, font_size) <= max_width:
                        chunk = cand2
                    else:
                        if chunk:
                            lines.append(chunk)
                        chunk = ch
                cur = chunk
    if cur:
        lines.append(cur)
    return lines


# --------------------------
# Collectors
# --------------------------


def list_launch_plists() -> List[Path]:
    home = Path.home()
    dirs = [home / "Library/LaunchAgents", Path("/Library/LaunchAgents"), Path("/Library/LaunchDaemons")]
    out: List[Path] = []
    for d in dirs:
        try:
            if d.exists():
                out.extend(sorted(d.glob("*.plist")))
        except Exception:
            pass
    return out


def collect_loaded_launchctl_labels(runner: CommandRunner) -> set[str]:
    res = runner.run(["launchctl", "list"], timeout_s=15)
    labels: set[str] = set()
    for ln in res.out.splitlines()[1:]:
        parts = ln.split()
        if len(parts) >= 3:
            labels.add(parts[2])
    return labels


def collect_processes(runner: CommandRunner, cfg: AuditConfig) -> List[List[str]]:
    res = runner.run(["ps", "-axo", "pid,ppid,user,%cpu,%mem,etime,command", "-r"], timeout_s=15)
    lines = [ln.rstrip("\n") for ln in res.out.splitlines() if ln.strip()]
    if len(lines) <= 1:
        return []
    rows: List[List[str]] = []
    for ln in lines[1 : 1 + cfg.max_rows]:
        # pid ppid user cpu mem etime command...
        m = re.match(r"^\s*(\d+)\s+(\d+)\s+(\S+)\s+([0-9.]+)\s+([0-9.]+)\s+(\S+)\s+(.*)$", ln)
        if not m:
            continue
        pid, ppid, user, cpu, mem, etime, cmd = m.group(1), m.group(2), m.group(3), m.group(4), m.group(5), m.group(6), m.group(7)
        rows.append([pid, user, cpu, mem, etime, cmd])
    return rows


@dataclass(frozen=True)
class RecentApp:
    name: str
    path: str
    bundle_id: str
    version: str
    modified: str  # local timestamp string
    signature: str  # notarized|dev_id|adhoc|unsigned|unknown
    codesign_summary: str
    codesign_kind: str  # ok|timeout|blocked|error
    codesign_verify_rc: int
    codesign_verify_summary: str
    codesign_verify_kind: str  # ok|timeout|blocked|error
    spctl_rc: int
    spctl_summary: str
    spctl_category: str
    spctl_kind: str  # ok|timeout|blocked|error
    quarantine_present: Optional[bool]
    provenance_present: Optional[bool]


def _iter_app_bundles(base: Path, max_depth: int = 2) -> Iterable[Path]:
    """Yield .app bundles under base without descending into bundles themselves."""
    if not base.exists() or not base.is_dir():
        return []
    seen: set[str] = set()
    stack: List[Tuple[Path, int]] = [(base, 0)]
    out: List[Path] = []
    while stack:
        d, depth = stack.pop()
        try:
            with os.scandir(str(d)) as it:
                for ent in it:
                    if not ent.is_dir(follow_symlinks=False):
                        continue
                    p = Path(ent.path)
                    name = p.name
                    if name.lower().endswith(".app"):
                        key = str(p)
                        if key not in seen:
                            seen.add(key)
                            out.append(p)
                        continue
                    if depth < max_depth and not name.startswith(".") and name not in {"Contents"}:
                        stack.append((p, depth + 1))
        except (FileNotFoundError, PermissionError, NotADirectoryError):
            continue
        except Exception:
            continue
    return out


def _read_info_plist(app_path: Path) -> dict:
    ip = app_path / "Contents" / "Info.plist"
    if not ip.exists():
        return {}
    try:
        return plistlib.loads(ip.read_bytes())
    except Exception:
        try:
            return plistlib.load(ip.open("rb"))
        except Exception:
            return {}


def _xattr_present(p: Path, attr: str) -> Optional[bool]:
    try:
        os.getxattr(str(p), attr)
        return True
    except OSError as e:
        if e.errno in {getattr(errno, "ENOATTR", 93), getattr(errno, "ENODATA", 61), errno.ENOENT}:
            return False
        if e.errno in {errno.EPERM, errno.EACCES}:
            return None
        return False
    except Exception:
        return None


def _signature_type(codesign_summary: str, spctl_category: str) -> str:
    if codesign_summary == "unsigned":
        return "unsigned"
    if codesign_summary == "adhoc":
        return "adhoc"
    if spctl_category == "accepted_notarized":
        return "notarized"
    if spctl_category == "accepted_dev_id":
        return "dev_id"
    if spctl_category.startswith("accepted_"):
        return "accepted"
    return "unknown"


def collect_recent_apps(days: int, max_apps: int, runner: CommandRunner) -> List[RecentApp]:
    """Scan /Applications and ~/Applications for recently modified .app bundles and assess trust signals."""
    home = Path.home()
    bases = [Path("/Applications"), home / "Applications"]
    cutoff = time.time() - (max(0, int(days)) * 86400)

    candidates: List[Tuple[float, Path]] = []
    for base in bases:
        for app in _iter_app_bundles(base, max_depth=2):
            try:
                st = app.stat()
            except Exception:
                continue
            if st.st_mtime < cutoff:
                continue
            candidates.append((st.st_mtime, app))

    candidates.sort(key=lambda t: t[0], reverse=True)
    selected = candidates[: max(0, int(max_apps))]

    out: List[RecentApp] = []
    for mtime, app in selected:
        info = _read_info_plist(app)
        bundle_id = str(info.get("CFBundleIdentifier") or "")
        version = str(info.get("CFBundleShortVersionString") or info.get("CFBundleVersion") or "")
        name = str(info.get("CFBundleDisplayName") or info.get("CFBundleName") or app.stem)
        modified = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")

        # Signing + Gatekeeper assessments
        cs = runner.run(["codesign", "-dv", "--verbose=4", str(app)], timeout_s=20)
        cs_sum = summarize_codesign_display(cs.out) if cs.kind == "ok" else f"unknown ({cs.kind})"

        cv = runner.run(["codesign", "--verify", "--deep", "--strict", "--verbose=2", str(app)], timeout_s=20)
        if cv.kind != "ok":
            cv_sum = f"unknown ({cv.kind})"
        elif cv.rc == 0:
            cv_sum = "ok"
        else:
            cv_sum = (cv.out.strip().splitlines()[-1] if cv.out.strip().splitlines() else cv.out.strip())[:200]

        sp = runner.run(_spctl_assess_cmd(str(app)), timeout_s=20)
        if sp.kind != "ok":
            sp_sum = f"unknown ({sp.kind})"
            sp_cat = "unknown"
        else:
            sp_sum = summarize_spctl_assess(sp.out, path_hint=str(app))
            sp_cat = classify_spctl_summary(sp_sum)

        sig = _signature_type(cs_sum, sp_cat)

        q = _xattr_present(app, "com.apple.quarantine")
        prov = _xattr_present(app, "com.apple.provenance")

        out.append(
            RecentApp(
                name=name,
                path=str(app),
                bundle_id=bundle_id,
                version=version,
                modified=modified,
                signature=sig,
                codesign_summary=cs_sum,
                codesign_kind=cs.kind,
                codesign_verify_rc=cv.rc,
                codesign_verify_summary=cv_sum[:200],
                codesign_verify_kind=cv.kind,
                spctl_rc=sp.rc,
                spctl_summary=sp_sum[:200],
                spctl_category=sp_cat,
                spctl_kind=sp.kind,
                quarantine_present=q,
                provenance_present=prov,
            )
        )

    return out


def collect_extensions() -> List[List[str]]:
    # Chromium-based extensions inventory
    def read_json(p: Path) -> Optional[dict]:
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return None

    home = Path.home()
    bases = [
        ("Chrome", home / "Library/Application Support/Google/Chrome"),
        ("Brave", home / "Library/Application Support/BraveSoftware/Brave-Browser"),
        ("Edge", home / "Library/Application Support/Microsoft Edge"),
    ]

    rows: List[List[str]] = []
    for browser, base in bases:
        if not base.exists():
            continue
        for profile in sorted([p for p in base.iterdir() if p.is_dir() and (p.name == "Default" or p.name.startswith("Profile") or p.name == "Guest Profile")], key=lambda x: x.name):
            ext_dir = profile / "Extensions"
            if not ext_dir.exists():
                continue
            for ext_id_dir in sorted([d for d in ext_dir.iterdir() if d.is_dir() and re.fullmatch(r"[a-p]{32}", d.name)]):
                ver_dirs = sorted([v for v in ext_id_dir.iterdir() if v.is_dir()], key=lambda x: x.name)
                if not ver_dirs:
                    continue
                manifest_path = ver_dirs[-1] / "manifest.json"
                m = read_json(manifest_path)
                if not m:
                    continue

                name = m.get("name", "")
                if isinstance(name, str) and name.startswith("__MSG_") and name.endswith("__"):
                    key = name[len("__MSG_") : -len("__")]
                    for loc in ["en", "en_US", "en-GB", "en_GB"]:
                        msg_path = ver_dirs[-1] / "_locales" / loc / "messages.json"
                        mm = read_json(msg_path) if msg_path.exists() else None
                        if isinstance(mm, dict) and isinstance(mm.get(key), dict) and "message" in mm[key]:
                            name = mm[key]["message"]
                            break

                version = str(m.get("version", ""))
                perms = m.get("permissions", [])
                hosts = m.get("host_permissions", [])
                update_url = "yes" if m.get("update_url") else "no"
                pcount = len(perms) if isinstance(perms, list) else 0
                hcount = len(hosts) if isinstance(hosts, list) else 0
                rows.append([f"{browser}/{profile.name}", ext_id_dir.name, str(name), f"v{version}; perms={pcount}; hosts={hcount}; update_url={update_url}"])

    return rows


def collect_external_extensions_artifacts() -> List[List[str]]:
    # External/forced extensions are often represented as JSON in External Extensions directories.
    home = Path.home()
    dirs = [
        Path("/Library/Application Support/Google/Chrome/External Extensions"),
        home / "Library/Application Support/Google/Chrome/External Extensions",
        Path("/Library/Application Support/BraveSoftware/Brave-Browser/External Extensions"),
        home / "Library/Application Support/BraveSoftware/Brave-Browser/External Extensions",
        Path("/Library/Application Support/Microsoft Edge/External Extensions"),
        home / "Library/Application Support/Microsoft Edge/External Extensions",
    ]

    rows: List[List[str]] = []
    for d in dirs:
        if not d.exists() or not d.is_dir():
            continue
        for f in sorted(d.glob("*.json")):
            try:
                content = f.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            # Try to parse typical schema: { "external_update_url": ..., "external_crx": ... }
            try:
                j = json.loads(content)
            except Exception:
                j = None
            if isinstance(j, dict):
                keys = ",".join(sorted(j.keys()))
                rows.append([str(d), f.name, keys[:80], str(j.get("external_update_url") or j.get("external_crx") or "")[:120]])
            else:
                rows.append([str(d), f.name, "(unparsed)", content.strip().splitlines()[0][:120] if content.strip() else ""])
    return rows


def collect_native_messaging_hosts() -> List[List[str]]:
    home = Path.home()
    dirs = [
        home / "Library/Application Support/Google/Chrome/NativeMessagingHosts",
        home / "Library/Application Support/BraveSoftware/Brave-Browser/NativeMessagingHosts",
        home / "Library/Application Support/Microsoft Edge/NativeMessagingHosts",
    ]
    rows: List[List[str]] = []
    for d in dirs:
        if not d.exists() or not d.is_dir():
            continue
        for f in sorted(d.glob("*.json")):
            try:
                j = json.loads(f.read_text(encoding="utf-8"))
            except Exception:
                continue
            rows.append([str(d), f.name, str(j.get("name", ""))[:80], str(j.get("path", ""))[:120]])
    return rows


def read_plist_defaults(path: str, runner: CommandRunner) -> CommandResult:
    # defaults can read plists; read-only.
    return runner.run(["defaults", "read", path], timeout_s=10)


def check_lockdown_mode(runner: CommandRunner) -> str:
    # Best-effort: key may not exist when disabled.
    res = runner.run(["defaults", "read", "-g", "LDMGlobalEnabled"], timeout_s=5)
    if res.rc == 0:
        v = res.out.strip().splitlines()[-1].strip()
        if v in {"1", "true", "YES"}:
            return "ON"
        if v in {"0", "false", "NO"}:
            return "OFF"
        return f"unknown ({v})"
    # If key doesn't exist, treat as OFF (common)
    if "does not exist" in res.out:
        return "OFF (key missing)"
    return "unknown (permission blocked or unavailable)"


def tcc_best_effort() -> Tuple[str, List[List[str]]]:
    # Best-effort read of per-user TCC.db.
    home = Path.home()
    db = home / "Library/Application Support/com.apple.TCC/TCC.db"
    if not db.exists():
        return "unavailable", []

    services = [
        "kTCCServiceAccessibility",
        "kTCCServiceInputMonitoring",
        "kTCCServiceScreenCapture",
        "kTCCServiceSystemPolicyAllFiles",
        "kTCCServiceAppleEvents",
        "kTCCServiceMicrophone",
        "kTCCServiceCamera",
        "kTCCServiceListenEvent",
    ]

    try:
        con = sqlite3.connect(str(db))
        cur = con.cursor()
        q = (
            "SELECT service, client, auth_value, last_modified "
            "FROM access WHERE service IN (%s) AND auth_value=2 ORDER BY service, last_modified DESC" % (
                ",".join(["?"] * len(services))
            )
        )
        cur.execute(q, services)
        rows = []
        for service, client, auth_value, last_modified in cur.fetchall():
            rows.append([str(service), str(client), str(auth_value), str(last_modified)])
        con.close()
        return "ok", rows
    except Exception as e:
        # Common: permission denied / authorization denied
        return f"blocked ({e.__class__.__name__})", []


# --------------------------
# Findings engine
# --------------------------


def _truthy_setting(val: str) -> Optional[bool]:
    v = (val or "").strip().strip(";").strip().lower()
    if v in {"1", "true", "yes", "on"}:
        return True
    if v in {"0", "false", "no", "off"}:
        return False
    return None


def _contains_any(haystack: str, needles: Sequence[str]) -> bool:
    hs = haystack.lower()
    return any(n.lower() in hs for n in needles)


def findings_from_posture(
    sip_out: str,
    gatekeeper_out: str,
    filevault_out: str,
    fw_state_out: str,
    su_keys: Dict[str, str],
) -> List[Finding]:
    out: List[Finding] = []

    sip = sip_out.lower()
    if "disabled" in sip:
        out.append(Finding("CRITICAL", "System Integrity Protection (SIP) disabled", "OS Integrity", sip_out.strip()[:200]))
    elif "enabled" not in sip and sip_out.strip():
        out.append(Finding("INFO", "System Integrity Protection (SIP) unknown", "OS Integrity", sip_out.strip()[:200]))

    gk = gatekeeper_out.lower()
    if "disabled" in gk:
        out.append(Finding("HIGH", "Gatekeeper assessments disabled", "OS Integrity", gatekeeper_out.strip()[:200]))
    elif "enabled" not in gk and gatekeeper_out.strip():
        out.append(Finding("INFO", "Gatekeeper status unknown", "OS Integrity", gatekeeper_out.strip()[:200]))

    fv = filevault_out.lower()
    if "off" in fv and "filevault" in fv:
        out.append(Finding("HIGH", "FileVault appears OFF", "OS Integrity", filevault_out.strip()[:200]))
    elif "on" not in fv and filevault_out.strip():
        out.append(Finding("INFO", "FileVault status unknown", "OS Integrity", filevault_out.strip()[:200]))

    fw = fw_state_out.lower()
    if "disabled" in fw:
        out.append(Finding("MEDIUM", "Firewall appears disabled", "Network", fw_state_out.strip()[:200]))
    elif "enabled" not in fw and fw_state_out.strip():
        out.append(Finding("INFO", "Firewall status unknown", "Network", fw_state_out.strip()[:200]))

    # Updates (best-effort): only flag when we can confidently read values.
    # Keys are from /Library/Preferences/com.apple.SoftwareUpdate via defaults read.
    if su_keys:
        disabled = []
        for k in ["ConfigDataInstall", "CriticalUpdateInstall", "InstallSecurityResponse"]:
            v = su_keys.get(k)
            tv = _truthy_setting(str(v)) if v is not None else None
            if tv is False:
                disabled.append(k)
        if disabled:
            out.append(Finding("MEDIUM", "Background security updates appear disabled", "Updates", "Disabled: " + ", ".join(disabled)))

    return out

def findings_from_proxy(proxy_out: str) -> List[Finding]:
    flags = ["HTTPEnable", "HTTPSEnable", "SOCKSEnable", "ProxyAutoConfigEnable"]
    enabled = []
    for f in flags:
        if re.search(rf"\b{re.escape(f)}\s*:\s*1\b", proxy_out):
            enabled.append(f)
    if enabled:
        return [Finding("HIGH", "System proxy configured", "Network", f"Enabled: {', '.join(enabled)}")]
    return []


def findings_from_vpn(nc_list_out: str, enroll_out: str, prof_list_out: str) -> List[Finding]:
    vpn = _summarize_vpn_connected(nc_list_out)
    if vpn != "YES":
        return []
    mdm = _summarize_mdm_enrollment(enroll_out)
    prof = _summarize_profiles_present(prof_list_out)
    # This is not inherently bad (consumer VPNs are common); treat as a "verify expected" nudge.
    if mdm == "NO" and prof == "NO":
        # Capture the first connected line as a clue.
        line = ""
        for ln in (nc_list_out or "").splitlines():
            if "connected" in ln.lower():
                line = ln.strip()
                break
        return [Finding("MEDIUM", "VPN connection detected (verify expected)", "Network", (line or "VPN appears connected")[:200])]
    return []


def _parse_hosts_nondefault(hosts_text: str) -> List[str]:
    out: List[str] = []
    for raw in (hosts_text or "").splitlines():
        s = raw.strip()
        if not s or s.startswith("#"):
            continue
        if s.startswith("("):
            # E.g. "(failed to read /etc/hosts: ...)"
            continue
        # Remove inline comments.
        s = s.split("#", 1)[0].strip()
        parts = s.split()
        if len(parts) < 2:
            continue
        ip = parts[0]
        names = parts[1:]

        # Ignore common defaults.
        if ip in {"127.0.0.1", "::1"}:
            if all(n in {"localhost", "ip6-localhost", "ip6-loopback"} for n in names):
                continue
        if ip == "255.255.255.255" and all(n == "broadcasthost" for n in names):
            continue
        if ip.startswith("fe80::1%lo0") and "localhost" in names:
            continue

        out.append(s)
    return out


def findings_from_hosts(hosts_text: str) -> List[Finding]:
    nondefault = _parse_hosts_nondefault(hosts_text)
    if nondefault:
        # Keep evidence minimal to avoid leaking internal hostnames in strict mode.
        return [Finding("MEDIUM", "Non-default /etc/hosts mappings present", "Network", f"entries={len(nondefault)}")]
    return []


def _parse_systemextensionsctl_list(sys_ext_out: str) -> List[str]:
    # Returns likely extension rows; best-effort and tolerant of format changes.
    out: List[str] = []
    for raw in (sys_ext_out or "").splitlines():
        ln = raw.strip()
        if not ln:
            continue
        low = ln.lower()
        if "com.apple." in low:
            continue
        if low.startswith("enabled") or low.startswith("----") or low.endswith("extension(s)"):
            continue
        # Heuristic: rows usually include a TeamID-like token and a bundle id.
        if re.search(r"\b[A-Z0-9]{10}\b", ln) and re.search(r"\b[a-z0-9_.-]+\.[a-z0-9_.-]+\b", ln, flags=re.IGNORECASE):
            out.append(ln[:240])
    return out


def findings_from_system_extensions(sys_ext_out: str) -> List[Finding]:
    rows = _parse_systemextensionsctl_list(sys_ext_out)
    if not rows:
        return []
    low = " ".join(rows).lower()
    sev = "MEDIUM"
    if any(k in low for k in ["endpoint", "endpointsecurity", "network", "filter", "vpn", "firewall", "packet", "proxy"]):
        sev = "HIGH"
    return [Finding(sev, "Third-party system extension(s) present (verify expected)", "OS Integrity", rows[0])]


def findings_from_listeners(listeners: List[Listener]) -> List[Finding]:
    sensitive = {"22", "5900", "3283", "445"}
    out: List[Finding] = []
    for l in listeners:
        # l.listen example: *:5000 or [::1]:22
        port = ""
        if ":" in l.listen:
            port = l.listen.rsplit(":", 1)[1]
        if port in sensitive:
            out.append(Finding("HIGH", f"Listener on sensitive port {port}", "Network", f"{l.process} (pid {l.pid}) listening on {l.listen}"))
    return out


def findings_from_shares(shares: List[SharePoint], listeners: List[Listener]) -> List[Finding]:
    out: List[Finding] = []
    smb_listening = any((l.listen.endswith(":445") or l.listen.endswith(":548")) for l in listeners)
    for s in shares:
        if s.guest_access is True and (s.read_only is False or s.read_only is None):
            sev = "HIGH" if smb_listening else "MEDIUM"
            out.append(Finding(sev, "Guest-writable share point configured", "Sharing", f"{s.name} -> {s.path} (guest=1, read-only=0); smb_listener={'yes' if smb_listening else 'no'}"))
    return out


def findings_from_profiles(prof_list_out: str, enroll_out: str) -> List[Finding]:
    out: List[Finding] = []
    if "MDM enrollment: Yes" in enroll_out or "Enrolled via DEP: Yes" in enroll_out:
        out.append(Finding("HIGH", "Device enrolled in MDM/DEP", "MDM/Profiles", enroll_out.strip().splitlines()[0][:200]))
    if "There are no configuration profiles" not in prof_list_out:
        # Could be benign (VPN, etc), but high signal.
        out.append(Finding("MEDIUM", "Configuration profiles present", "MDM/Profiles", "profiles list indicates installed profiles"))
    return out


def findings_from_trust(trust_out: str) -> List[Finding]:
    if "No Trust Settings were found" in trust_out:
        return []
    if trust_out.strip():
        return [Finding("MEDIUM", "Custom trust settings present", "Trust", "security dump-trust-settings returned data")]
    return []


def findings_from_kexts(non_apple_kext_lines: List[str]) -> List[Finding]:
    if non_apple_kext_lines:
        return [Finding("HIGH", "Non-Apple kernel extension(s) loaded", "OS Integrity", non_apple_kext_lines[0][:200])]
    return []


def findings_from_btm(items: List[BackgroundItem]) -> List[Finding]:
    out: List[Finding] = []
    for it in items:
        if it.allowed is False:
            out.append(
                Finding(
                    "MEDIUM",
                    "Enabled background item is disallowed (unusual state)",
                    "Persistence",
                    f"{it.identifier or it.name} ({it.exec_path})",
                )
            )
        if it.identifier and "Unknown Developer" in (it.name or ""):
            out.append(Finding("MEDIUM", "Enabled background item from unknown developer", "Persistence", f"{it.identifier} ({it.exec_path})"))
    return out


def findings_from_launchd_status(statuses: List[LaunchctlStatus]) -> List[Finding]:
    out: List[Finding] = []
    for s in statuses:
        if s.runs is None or s.runs < 50:
            continue
        if not s.last_exit:
            continue
        if "never exited" in s.last_exit.lower():
            continue
        label = s.label.split("/", 2)[-1] if "/" in s.label else s.label
        out.append(
            Finding(
                "MEDIUM",
                "launchd service repeatedly respawning",
                "Persistence",
                f"{label}: runs={s.runs}; last_exit={s.last_exit}",
            )
        )
    return out


def findings_from_suspicious_persistence_paths(paths: List[str], home: Path) -> List[Finding]:
    out: List[Finding] = []
    suspicious_markers = ["/Downloads/", "/Desktop/", "/tmp/", "/var/folders/"]
    for p in paths:
        if not p or not p.startswith("/"):
            continue
        if any(m in p for m in suspicious_markers):
            cls = classify_exec_path(p, home)
            out.append(Finding("HIGH", "Persistence executable in high-risk location", "Persistence", f"{p} ({cls})"))
    return out


def _is_staging_or_dropper_path(p: str, home: Path) -> bool:
    if not p:
        return False
    if p.startswith("/Volumes/") or p.startswith("/tmp/") or p.startswith("/private/var/folders/"):
        return True
    # Common download/staging dirs under the user's home.
    if p.startswith(str(home / "Downloads") + "/") or p.startswith(str(home / "Desktop") + "/"):
        return True
    if "/var/folders/" in p or "/tmp/" in p:
        return True
    return False


def findings_from_signing(assessments: List[SigningAssessment], home: Path) -> List[Finding]:
    out: List[Finding] = []
    for a in assessments:
        assess_path = a.assessed_path or a.path
        cls = classify_exec_path(assess_path, home)
        staging = _is_staging_or_dropper_path(a.path, home) or _is_staging_or_dropper_path(assess_path, home)
        sp_cat = a.spctl_category or classify_spctl_summary(a.spctl_summary)

        # Baseline severity: keep signal high, but reduce panic for common dev tooling.
        if staging:
            sev = "HIGH"
        elif cls in {"applications", "library"}:
            sev = "MEDIUM"
        elif cls == "user":
            sev = "MEDIUM"
        elif cls == "homebrew":
            sev = "LOW"
        else:
            sev = "LOW"

        # Escalate for ad-hoc/unsigned in high-trust install locations.
        if a.codesign_summary in {"unsigned", "adhoc"} and cls in {"applications", "library"}:
            sev = "HIGH"
        if sp_cat == "rejected_resources_missing":
            sev = "HIGH"

        ev_path = assess_path if assess_path == a.path else f"{assess_path} (from {a.path})"

        if a.codesign_summary == "unsigned":
            out.append(Finding(sev, "Unsigned code used by persistence/background item", "Signing", f"{ev_path} ({cls})"))
        elif a.codesign_summary == "adhoc":
            out.append(Finding(sev, "Ad-hoc signed code used by persistence/background item", "Signing", f"{ev_path} ({cls})"))

        if a.spctl_rc != 0:
            # For CLI tooling, spctl frequently returns a low-signal "does not seem to be an app".
            if sp_cat == "rejected_not_app" and cls in {"homebrew"} and not staging:
                continue
            sev2 = sev
            if sp_cat == "rejected_not_app" and cls in {"homebrew", "user"} and not staging:
                sev2 = "INFO"
            title = "Gatekeeper assessment failed for persistence/background item"
            if sp_cat == "rejected_resources_missing":
                title = "Gatekeeper assessment indicates missing bundle resources"
            out.append(Finding(sev2, title, "Signing", f"{ev_path} ({cls}): {a.spctl_summary}"))
    return out


def findings_from_recent_apps(recent_apps: List[RecentApp], home: Path) -> List[Finding]:
    out: List[Finding] = []
    home_apps = str(home / "Applications") + "/"
    for app in recent_apps:
        p = app.path or ""
        in_system_apps = p.startswith("/System/Applications/")
        in_apps = p.startswith("/Applications/") or p.startswith(home_apps)
        if in_system_apps:
            continue

        if app.spctl_kind == "ok" and app.spctl_rc != 0:
            sev = "HIGH" if p.startswith("/Applications/") else "MEDIUM"
            title = "Recently modified app failed Gatekeeper assessment"
            if app.spctl_category == "rejected_resources_missing":
                title = "Recently modified app appears tampered/mispackaged (missing resources)"
                sev = "HIGH"
            out.append(
                Finding(
                    sev,
                    title,
                    "Untrusted Installs",
                    f"{app.name} ({app.bundle_id or 'no_bundle_id'}): {app.spctl_summary}",
                )
            )

        # Ad-hoc/unsigned apps installed into /Applications are high-signal.
        if app.signature in {"unsigned", "adhoc"} and p.startswith("/Applications/"):
            out.append(
                Finding(
                    "HIGH",
                    "Recently modified app is unsigned/ad-hoc in /Applications",
                    "Untrusted Installs",
                    f"{app.name} ({app.bundle_id or 'no_bundle_id'}): signature={app.signature}; codesign={app.codesign_summary}",
                )
            )

        # Quarantine removed + untrusted is a "closed beta / quarantine bypass" signal.
        if app.spctl_kind == "ok" and app.spctl_rc != 0 and app.quarantine_present is False and in_apps:
            out.append(
                Finding(
                    "HIGH",
                    "Recently modified app appears untrusted with quarantine attribute absent",
                    "Untrusted Installs",
                    f"{app.name} ({app.bundle_id or 'no_bundle_id'}): {app.spctl_summary}; quarantine=absent",
                )
            )

        # codesign --verify failures can surface missing/invalid sealed resources.
        if app.codesign_verify_kind == "ok" and app.codesign_verify_rc != 0:
            v = (app.codesign_verify_summary or "").lower()
            if "sealed resource" in v or ("resource" in v and "missing" in v):
                out.append(
                    Finding(
                        "HIGH",
                        "App bundle verification reports missing/invalid resources",
                        "Untrusted Installs",
                        f"{app.name} ({app.bundle_id or 'no_bundle_id'}): {app.codesign_verify_summary}",
                    )
                )

    return out


def findings_from_process_staging(proc_rows: List[List[str]], home: Path) -> List[Finding]:
    out: List[Finding] = []
    seen: set[str] = set()
    dl = str(home / "Downloads") + "/"
    desk = str(home / "Desktop") + "/"

    for row in proc_rows:
        if len(row) < 6:
            continue
        pid, user, cpu, mem, etime, cmd = row[:6]
        s = (cmd or "").lstrip()
        if not s.startswith("/"):
            continue

        title = ""
        if s.startswith("/Volumes/"):
            title = "Process running from mounted volume (/Volumes)"
        elif s.startswith("/tmp/") or s.startswith("/private/var/folders/"):
            title = "Process running from temporary/staging directory"
        elif s.startswith(dl) or s.startswith(desk):
            title = "Process running from Downloads/Desktop"

        if not title:
            continue

        # Avoid spamming duplicates; key by the probable executable prefix.
        exec_hint = s.split(" ", 1)[0]
        key = f"{title}|{exec_hint}"
        if key in seen:
            continue
        seen.add(key)
        out.append(Finding("HIGH", title, "Processes", f"pid={pid} user={user} cmd={s[:220]}"))

    return out


# --------------------------
# Main report
# --------------------------


def _looks_permission_blocked(out: str) -> bool:
    return _contains_any(
        out or "",
        [
            "operation not permitted",
            "not permitted",
            "permission denied",
            "not authorized",
            "authorization denied",
        ],
    )


def _summarize_profiles_present(prof_list_out: str) -> str:
    if not prof_list_out.strip():
        return "UNKNOWN"
    if "There are no configuration profiles" in prof_list_out:
        return "NO"
    return "YES/UNKNOWN"


def _summarize_mdm_enrollment(enroll_out: str) -> str:
    s = enroll_out.lower()
    if "mdm enrollment: yes" in s or "enrolled via dep: yes" in s:
        return "YES"
    if "mdm enrollment: no" in s or "enrolled via dep: no" in s:
        return "NO"
    return "UNKNOWN"


def _summarize_trust_custom(trust_user_out: str, trust_admin_out: str) -> str:
    if "No Trust Settings were found" in trust_user_out and "No Trust Settings were found" in trust_admin_out:
        return "NO"
    if (trust_user_out + trust_admin_out).strip():
        return "YES/UNKNOWN"
    return "UNKNOWN"


def _summarize_proxy_configured(proxy_out: str) -> str:
    return "YES" if findings_from_proxy(proxy_out) else "NO"


def _summarize_vpn_connected(nc_list_out: str) -> str:
    s = (nc_list_out or "").strip()
    if not s:
        return "UNKNOWN"
    if re.search(r"\(connected\)", s, flags=re.IGNORECASE):
        return "YES"
    # If we can see any explicit disconnected entries, that's a decent signal it's not connected.
    if re.search(r"\(disconnected\)", s, flags=re.IGNORECASE):
        return "NO"
    # Some versions omit parentheses; be conservative.
    if "connected" in s.lower():
        return "YES/UNKNOWN"
    return "UNKNOWN"


def _summarize_sip(sip_out: str) -> str:
    s = sip_out.lower()
    if "disabled" in s:
        return "DISABLED"
    if "enabled" in s:
        return "ENABLED"
    return "UNKNOWN"


def _summarize_gatekeeper(gk_out: str) -> str:
    s = gk_out.lower()
    if "disabled" in s:
        return "DISABLED"
    if "enabled" in s:
        return "ENABLED"
    return "UNKNOWN"


def _summarize_filevault(fv_out: str) -> str:
    s = fv_out.lower()
    if "filevault is off" in s or re.search(r"\bfilevault\b.*\boff\b", s):
        return "OFF"
    if "filevault is on" in s or re.search(r"\bfilevault\b.*\bon\b", s):
        return "ON"
    return "UNKNOWN"


def _summarize_firewall_state(fw_state_out: str) -> str:
    s = fw_state_out.lower()
    if "enabled" in s:
        return "ENABLED"
    if "disabled" in s:
        return "DISABLED"
    return "UNKNOWN"


def _summarize_updates(su_keys: Dict[str, str], su_rc: int) -> str:
    if su_rc != 0 and not su_keys:
        return "UNKNOWN/BLOCKED"
    if not su_keys:
        return "UNKNOWN"
    parts = []
    for k in ["ConfigDataInstall", "CriticalUpdateInstall", "InstallSecurityResponse", "AutomaticDownload", "AutomaticallyInstallMacOSUpdates"]:
        if k in su_keys:
            parts.append(f"{k}={su_keys[k]}")
    return ", ".join(parts)[:220] if parts else "OK/UNKNOWN"


def run_audit(cfg: AuditConfig) -> AuditResult:
    runner = CommandRunner()
    home = Path.home()
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M")

    now = runner.run(["date"]).out.strip()
    uname = runner.run(["uname", "-a"]).out.strip()
    sw_vers = runner.run(["sw_vers"]).out.strip().replace("\t", " ")
    user = runner.run(["whoami"]).out.strip()
    uptime = runner.run(["uptime"]).out.strip()

    # Security posture
    sip = runner.run(["csrutil", "status"]).out.strip()
    gatekeeper = runner.run(["spctl", "--status"]).out.strip()
    filevault = runner.run(["fdesetup", "status"]).out.strip()

    fw_state = runner.run(["/usr/libexec/ApplicationFirewall/socketfilterfw", "--getglobalstate"]).out.strip()
    fw_stealth = runner.run(["/usr/libexec/ApplicationFirewall/socketfilterfw", "--getstealthmode"]).out.strip()
    fw_blockall = runner.run(["/usr/libexec/ApplicationFirewall/socketfilterfw", "--getblockall"]).out.strip()

    # Profiles
    enroll = runner.run(["profiles", "status", "-type", "enrollment"], timeout_s=20).out
    prof_list = runner.run(["profiles", "list"], timeout_s=20).out

    # Extensions / kexts
    sys_ext_res = run_with_retry(runner, ["systemextensionsctl", "list"], [20, 40])
    sys_ext = sys_ext_res.out
    km_res = run_with_retry(runner, ["kmutil", "showloaded"], [25, 45])
    km = km_res.out
    non_apple_kext_lines: List[str] = []
    if km_res.kind == "ok" and km_res.rc == 0:
        non_apple_kext_lines = [
            ln
            for ln in km.splitlines()
            if ln.strip() and "com.apple." not in ln and not ln.startswith("Index") and "No variant" not in ln
        ]

    # Lockdown mode (best effort)
    lockdown = check_lockdown_mode(runner)

    # Updates posture (best-effort): read com.apple.SoftwareUpdate
    su = read_plist_defaults("/Library/Preferences/com.apple.SoftwareUpdate", runner)
    su_keys = {}
    if su.rc == 0:
        for k in ["AutomaticDownload", "ConfigDataInstall", "CriticalUpdateInstall", "AutomaticallyInstallMacOSUpdates", "InstallSecurityResponse"]:
            m = re.search(rf"\b{k}\s*=\s*([^;]+);", su.out)
            if m:
                su_keys[k] = m.group(1).strip()

    # Network
    proxy = runner.run(["scutil", "--proxy"], timeout_s=15).out
    dns = runner.run(["scutil", "--dns"], timeout_s=20).out
    nc_list = runner.run(["scutil", "--nc", "list"], timeout_s=20).out

    # /etc/hosts
    hosts_text = ""
    try:
        hosts_text = (Path("/etc/hosts").read_text(encoding="utf-8", errors="replace") or "")
    except Exception as e:
        hosts_text = f"(failed to read /etc/hosts: {e})\n"

    # Listeners
    l_listen = runner.run(["lsof", "-nP", "-iTCP", "-sTCP:LISTEN"], timeout_s=20)
    listeners = parse_lsof_listen(l_listen.out)

    # Established (sample)
    l_est = runner.run(["lsof", "-nP", "-iTCP", "-sTCP:ESTABLISHED"], timeout_s=20)
    established = parse_lsof_established(l_est.out)

    # UDP sample (raw)
    l_udp = runner.run(["lsof", "-nP", "-iUDP"], timeout_s=20).out

    # Processes
    proc_rows = collect_processes(runner, cfg)

    # Recent app installs / untrusted installs (Skippy-class detection)
    recent_apps = collect_recent_apps(cfg.recent_apps_days, cfg.recent_apps_max, runner)

    # Persistence: launch plists + loaded labels
    loaded_labels = collect_loaded_launchctl_labels(runner)
    launch_items: List[LaunchItem] = []
    for p in list_launch_plists():
        d = plist_to_json(p, runner)
        if isinstance(d, dict):
            launch_items.append(parse_launch_item(p, d, loaded_labels))

    # launchctl details (user launchagents only; deep mode expands)
    uid = os.getuid()
    launch_status: List[LaunchctlStatus] = []
    candidates = [it for it in launch_items if it.kind == "LaunchAgent (user)" and not it.label.startswith("com.apple.")]
    if cfg.depth == "deep":
        candidates = [it for it in launch_items if it.kind.startswith("LaunchAgent") and not it.label.startswith("com.apple.")]
    for it in candidates[: (80 if cfg.depth == "deep" else 25)]:
        out = runner.run(["launchctl", "print", f"gui/{uid}/{it.label}"], timeout_s=10).out
        if "Could not find service" in out:
            continue
        launch_status.append(parse_launchctl_print(out))

    # Background items (BTM)
    btm_res = run_with_retry(runner, ["sfltool", "dumpbtm"], [15, 60])
    btm_items: List[BackgroundItem] = []
    if btm_res.kind == "ok" and btm_res.rc == 0:
        btm_items = parse_sfltool_dumpbtm(btm_res.out)

    # Cron
    cron = runner.run(["crontab", "-l"], timeout_s=10)

    # Trust settings
    trust_user = runner.run(["security", "dump-trust-settings"], timeout_s=20).out
    trust_admin = runner.run(["security", "dump-trust-settings", "-d"], timeout_s=20).out

    # Shares
    shares_raw = runner.run(["sharing", "-l"], timeout_s=20).out
    shares = parse_sharing_list(shares_raw)

    # Brew services
    brew_services = ""
    if shutil.which("brew"):
        brew_services = runner.run(["brew", "services", "list"], timeout_s=20).out

    # Browser surfaces
    ext_rows = collect_extensions()
    ext_external = collect_external_extensions_artifacts()
    native_hosts = collect_native_messaging_hosts()

    # TCC best-effort
    tcc_status, tcc_rows = tcc_best_effort()
    tcc_log_sample: List[str] = []
    tcc_log_res: Optional[CommandResult] = None
    if tcc_status != "ok" and cfg.tcc_recent_log_minutes and int(cfg.tcc_recent_log_minutes) > 0:
        mins = max(1, int(cfg.tcc_recent_log_minutes))
        # Unified logging sample (not comprehensive). Useful when TCC.db is blocked.
        tcc_log_res = runner.run(
            [
                "log",
                "show",
                "--style",
                "syslog",
                "--last",
                f"{mins}m",
                "--predicate",
                'subsystem == "com.apple.TCC"',
            ],
            timeout_s=30,
        )
        if tcc_log_res.kind == "ok" and tcc_log_res.out.strip():
            lines = [ln.rstrip("\n") for ln in tcc_log_res.out.splitlines() if ln.strip()]
            # Keep it small and recent.
            tcc_log_sample = lines[-min(len(lines), 80) :]

    # Signing assessments: persistence + enabled background items executables
    exec_paths: List[str] = []
    for it in launch_items:
        if it.label.startswith("com.apple."):
            continue
        if it.exec_path and it.exec_path.startswith("/"):
            exec_paths.append(it.exec_path)
    for it in btm_items:
        if it.exec_path and it.exec_path.startswith("/"):
            exec_paths.append(it.exec_path)

    # De-dupe and only assess existing files
    uniq_exec: List[str] = []
    seen = set()
    for p in exec_paths:
        if p in seen:
            continue
        seen.add(p)
        if Path(p).exists():
            uniq_exec.append(p)

    max_assess = 60 if cfg.depth == "deep" else 25
    assessments: List[SigningAssessment] = []
    for p in uniq_exec[:max_assess]:
        assessments.append(assess_signing(p, runner))

    # Findings
    findings: List[Finding] = []
    findings += findings_from_posture(sip, gatekeeper, filevault, fw_state, su_keys)
    findings += findings_from_recent_apps(recent_apps, home)
    findings += findings_from_process_staging(proc_rows, home)
    findings += findings_from_proxy(proxy)
    findings += findings_from_vpn(nc_list, enroll, prof_list)
    findings += findings_from_hosts(hosts_text)
    findings += findings_from_listeners(listeners)
    findings += findings_from_shares(shares, listeners)
    findings += findings_from_profiles(prof_list, enroll)
    findings += findings_from_trust(trust_user + "\n" + trust_admin)
    if sys_ext_res.kind == "ok" and sys_ext_res.rc == 0:
        findings += findings_from_system_extensions(sys_ext)
    findings += findings_from_kexts(non_apple_kext_lines)
    findings += findings_from_btm(btm_items)
    findings += findings_from_launchd_status(launch_status)
    findings += findings_from_suspicious_persistence_paths(uniq_exec, home)
    findings += findings_from_signing(assessments, home)

    findings_sorted = sorted(findings, key=lambda f: (SEV_ORDER.get(f.severity, 99), f.title))

    # Privacy redaction for console/PDF outputs
    def R_console(s: str) -> str:
        s = redact_tokens(s)
        if cfg.privacy == "strict":
            s = redact_paths(s, home)
        return s

    # History snapshots are always stored strictly sanitized (tokens + home path redaction).
    def R_snapshot(s: str) -> str:
        s = redact_tokens(s)
        s = redact_paths(s, home)
        return s

    # Unknowns / blocked checks (best-effort signals)
    unknowns: List[str] = []
    if su.rc != 0 and not su_keys:
        unknowns.append("Updates settings: unknown (permission blocked or unavailable).")
    if _looks_permission_blocked(l_listen.out):
        unknowns.append("Network listeners: permission blocked; results may be incomplete.")
    if _looks_permission_blocked(l_est.out):
        unknowns.append("Established connections: permission blocked; results may be incomplete.")
    if tcc_status != "ok":
        unknowns.append(f"Privacy permissions (TCC): automatic inspection {tcc_status}.")
    if sys_ext_res.kind != "ok" or sys_ext_res.rc != 0:
        reason = sys_ext_res.kind if sys_ext_res.kind != "ok" else "error"
        unknowns.append(f"System extensions: unknown ({reason}).")
    if km_res.kind != "ok" or km_res.rc != 0:
        reason = km_res.kind if km_res.kind != "ok" else "error"
        unknowns.append(f"Kernel extension inventory: unknown ({reason}).")
    if btm_res.kind != "ok" or btm_res.rc != 0:
        reason = btm_res.kind if btm_res.kind != "ok" else "error"
        unknowns.append(f"Background items (BTM): unknown ({reason}).")

    # High-signal posture summary (for console)
    profiles_present = _summarize_profiles_present(prof_list)
    mdm_enrolled = _summarize_mdm_enrollment(enroll)
    proxy_configured = _summarize_proxy_configured(proxy)
    trust_custom = _summarize_trust_custom(trust_user, trust_admin)

    posture = {
        "SIP": _summarize_sip(sip),
        "Gatekeeper": _summarize_gatekeeper(gatekeeper),
        "FileVault": _summarize_filevault(filevault),
        "Lockdown Mode": lockdown,
        "Firewall": _summarize_firewall_state(fw_state),
        "Updates": _summarize_updates(su_keys, su.rc),
        "MDM enrolled": mdm_enrolled,
        "Profiles present": profiles_present,
        "Proxy configured": proxy_configured,
        "VPN connected": _summarize_vpn_connected(nc_list),
        "Custom trust settings": trust_custom,
    }

    btm_enabled_count = btm_enabled_count_from_result(btm_res, btm_items)
    recent_apps_scanned = len(recent_apps)
    recent_apps_flagged = len([a for a in recent_apps if (a.spctl_kind == "ok" and a.spctl_rc != 0) or a.signature in {"unsigned", "adhoc"}])

    counts = {
        "listeners": len(listeners),
        "established": len(established),
        "launch_items": len(launch_items),
        "launch_non_apple": len([it for it in launch_items if not it.label.startswith("com.apple.")]),
        "btm_enabled": btm_enabled_count,
        "extensions": len(ext_rows),
        "shares": len(shares),
        "recent_apps_scanned": recent_apps_scanned,
        "recent_apps_flagged": recent_apps_flagged,
    }

    top_processes: List[List[str]] = []
    for pid, user2, cpu, mem, etime, cmd in proc_rows[: min(len(proc_rows), 5)]:
        cmd_out = cmd[:160]
        if cfg.privacy == "strict":
            cmd_out = redact_paths(cmd_out, home)
        top_processes.append([pid, user2, cpu, mem, etime, cmd_out])

    # Build sanitized snapshot for history/diffing
    listeners_ports: set[str] = set()
    for l in listeners:
        port = ""
        if ":" in (l.listen or ""):
            port = l.listen.rsplit(":", 1)[1]
        if port.isdigit():
            listeners_ports.add(f"{l.proto.lower()}:{port}")

    sys_ext_third_party: List[str] = []
    if sys_ext_res.kind == "ok" and sys_ext_res.rc == 0:
        sys_ext_third_party = _parse_systemextensionsctl_list(sys_ext)[:100]

    hosts_nondefault_count = len(_parse_hosts_nondefault(hosts_text))

    persistence_execs = sorted({R_snapshot(p) for p in uniq_exec if p})[:300]

    recent_apps_payload: List[dict] = []
    recent_apps_flagged_keys: List[str] = []
    for a in recent_apps:
        flagged = (a.spctl_kind == "ok" and a.spctl_rc != 0) or (a.signature in {"unsigned", "adhoc"})
        key = f"{a.bundle_id or ''}|{R_snapshot(a.path)}"
        if flagged:
            recent_apps_flagged_keys.append(key)
        recent_apps_payload.append(
            {
                "name": a.name,
                "path": R_snapshot(a.path),
                "bundle_id": a.bundle_id,
                "version": a.version,
                "modified": a.modified,
                "signature": a.signature,
                "spctl_kind": a.spctl_kind,
                "spctl_rc": a.spctl_rc,
                "spctl_category": a.spctl_category,
                "quarantine_present": a.quarantine_present,
            }
        )

    snapshot = {
        "schema_version": 2,
        "generated": now,
        "user": user,
        "os": " ".join(sw_vers.splitlines()),
        "privacy": cfg.privacy,
        "depth": cfg.depth,
        "posture": posture,
        "unknowns": unknowns,
        "findings": [
            {"severity": f.severity, "pillar": f.pillar, "title": f.title, "evidence": R_snapshot(f.evidence)}
            for f in findings_sorted
        ],
        "counts": {
            "listeners": len(listeners),
            "established": len(established),
            "launch_items": len(launch_items),
            "btm_enabled": btm_enabled_count,
            "extensions": len(ext_rows),
            "recent_apps_scanned": recent_apps_scanned,
            "recent_apps_flagged": recent_apps_flagged,
        },
        "inventory": {
            "listeners_ports": sorted(listeners_ports),
            "persistence_execs": persistence_execs,
            "recent_apps_flagged": sorted(set(recent_apps_flagged_keys)),
            "system_extensions_third_party": sys_ext_third_party,
            "hosts_nondefault_count": hosts_nondefault_count,
        },
        "recent_apps": recent_apps_payload,
        "tcc": {
            "status": tcc_status,
            "rows": min(len(tcc_rows), cfg.max_rows),
            "log_sample_lines": len(tcc_log_sample),
            "log_sample_kind": (tcc_log_res.kind if tcc_log_res else ""),
        },
        "trust": {"custom": "No Trust Settings were found" not in (trust_user + trust_admin)},
    }

    # Optional diff (read-only): compare this run to the most recent prior snapshot.
    diff_last: Optional[dict] = None
    prev_snapshot_path: Optional[Path] = None
    if cfg.diff_last:
        snaps = list_history_snapshots(DEFAULT_HISTORY_DIR)
        if snaps:
            prev_snapshot_path = snaps[-1]
            prev = read_json_file(prev_snapshot_path) or {}
            diff_last = diff_snapshots(prev, snapshot)
        else:
            diff_last = {"error": "no_previous_snapshot"}
        snapshot["diff_last"] = diff_last
        snapshot["diff_last_source"] = str(prev_snapshot_path) if prev_snapshot_path else ""

    hist_path: Optional[Path] = None
    if cfg.keep_history:
        hist_dir = DEFAULT_HISTORY_DIR
        hist_dir.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(hist_dir, 0o700)
        except Exception:
            pass
        hist_path = hist_dir / f"snapshot_{stamp}.json"
        hist_path.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
        try:
            os.chmod(hist_path, 0o600)
        except Exception:
            pass
        snapshot["history_path"] = str(hist_path)

    data = {
        "stamp": stamp,
        "home": str(home),
        "now": now,
        "uname": uname,
        "sw_vers": sw_vers,
        "user": user,
        "uptime": uptime,
        "sip": sip,
        "gatekeeper": gatekeeper,
        "filevault": filevault,
        "fw_state": fw_state,
        "fw_stealth": fw_stealth,
        "fw_blockall": fw_blockall,
        "su_rc": su.rc,
        "su_keys": su_keys,
        "enroll": enroll,
        "prof_list": prof_list,
        "sys_ext": sys_ext,
        "sys_ext_kind": sys_ext_res.kind,
        "sys_ext_rc": sys_ext_res.rc,
        "non_apple_kext_lines": non_apple_kext_lines,
        "km_kind": km_res.kind,
        "km_rc": km_res.rc,
        "lockdown": lockdown,
        "proxy": proxy,
        "dns": dns,
        "nc_list": nc_list,
        "hosts_text": hosts_text,
        "listeners": listeners,
        "established": established,
        "proc_rows": proc_rows,
        "launch_items": launch_items,
        "launch_status": launch_status,
        "uid": os.getuid(),
        "btm_items": btm_items,
        "btm_kind": btm_res.kind,
        "btm_rc": btm_res.rc,
        "recent_apps": recent_apps,
        "cron": cron,
        "trust_user": trust_user,
        "trust_admin": trust_admin,
        "shares": shares,
        "brew_services": brew_services,
        "ext_rows": ext_rows,
        "ext_external": ext_external,
        "native_hosts": native_hosts,
        "tcc_status": tcc_status,
        "tcc_rows": tcc_rows,
        "tcc_log_sample": tcc_log_sample,
        "tcc_log_kind": (tcc_log_res.kind if tcc_log_res else ""),
        "assessments": assessments,
        "hist_path": str(hist_path) if hist_path else "",
        "diff_last": snapshot.get("diff_last"),
        "diff_last_source": snapshot.get("diff_last_source", ""),
    }

    return AuditResult(
        generated=now,
        user=user,
        os=" ".join(sw_vers.splitlines()),
        kernel=uname,
        posture=posture,
        counts=counts,
        findings=findings_sorted,
        unknowns=unknowns,
        top_processes=top_processes,
        snapshot=snapshot,
        data=data,
    )


def _console_sev_counts(findings: List[Finding]) -> Dict[str, int]:
    counts = {k: 0 for k in ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]}
    for f in findings:
        if f.severity in counts:
            counts[f.severity] += 1
    return counts


def _next_steps_for_finding(f: Finding) -> List[str]:
    t = (f.title or "").lower()

    if "system integrity protection" in t and "disabled" in t:
        return [
            "System Settings -> Privacy & Security: verify SIP is not intentionally disabled (most users should keep it enabled).",
            "If you recently installed low-level dev tools that asked to disable SIP, re-evaluate that tradeoff before leaving it off long-term.",
            "If SIP was disabled unexpectedly, treat this as high risk and investigate persistence items and trust settings first.",
        ]
    if "gatekeeper" in t and "disabled" in t:
        return [
            "System Settings -> Privacy & Security: confirm Gatekeeper behavior matches your expectations.",
            "Avoid running unsigned/unnotarized binaries; review recent downloads and persistence items.",
        ]
    if "filevault" in t and "off" in t:
        return [
            "System Settings -> Privacy & Security -> FileVault: consider enabling (protects data at rest).",
        ]
    if "system proxy configured" in t:
        return [
            "System Settings -> Network -> (active service) -> Details -> Proxies: verify proxies are OFF unless intentionally set.",
            "System Settings -> Network -> VPN & Filters: look for unexpected VPNs/filters.",
            "If unexpected, identify the installing app/profile (MDM/Profiles section) before changing anything.",
        ]
    if "custom trust settings" in t:
        return [
            "Review any user-installed root certificates (custom trust anchors are a MITM signal).",
            "If you did not intentionally install enterprise/VPN certs, investigate profiles/MDM and recent installers first.",
        ]
    if "device enrolled in mdm" in t or "configuration profiles present" in t:
        return [
            "System Settings -> General -> VPN & Device Management: review installed profiles and MDM enrollment.",
            "Confirm every profile is expected (work/school VPN, security tooling). Unexpected profiles warrant investigation.",
        ]
    if "listener on sensitive port" in t:
        return [
            "Confirm you expect remote access services (SSH, Screen Sharing, SMB). If not, identify the owning process and its origin.",
            "System Settings -> General -> Sharing: confirm only intended sharing services are enabled.",
        ]
    if "guest-writable share point" in t:
        return [
            "System Settings -> General -> Sharing: review File Sharing and guest access settings.",
            "Avoid guest + writeable shares unless absolutely required.",
        ]
    if "kernel extension" in t or "system extensions" in t:
        return [
            "Non-Apple extensions have deep access; confirm each vendor is expected (VPN/AV/endpoint tooling).",
            "If unexpected, identify the installing app before making changes.",
        ]
    if "persistence executable" in t or "launchd service repeatedly" in t:
        return [
            "Review LaunchAgents/Daemons and Background Items; confirm each non-Apple item is expected.",
            "If an item points to Downloads/Desktop/tmp paths, treat it as suspicious and investigate the app origin first.",
        ]
    if "unsigned executable" in t or "gatekeeper assessment failed" in t:
        return [
            "For each flagged executable: confirm you recognize the owning app/service (LaunchAgent/Daemon or Background Item).",
            "Developer tooling (Homebrew, Python venvs, Node) can legitimately fail spctl/Gatekeeper checks. Treat these as 'review required' unless combined with suspicious paths (Downloads/tmp) or an unknown app.",
            "If you do not recognize it, prioritize disabling the persistence item via UI first (non-destructive), then investigate the binary origin and signatures.",
        ]

    return ["Review this finding in context and verify it matches an expected app or configuration change."]


def render_console(cfg: AuditConfig, result: AuditResult) -> None:
    # Keep console output privacy-safe by honoring cfg.privacy (strict by default).
    home = Path.home()

    def R(s: str) -> str:
        s = redact_tokens(s)
        if cfg.privacy == "strict":
            s = redact_paths(s, home)
        return s

    def C(n: object, default: str = "0") -> str:
        try:
            v = int(n)  # type: ignore[arg-type]
            return "unknown" if v < 0 else str(v)
        except Exception:
            return default

    if cfg.diff_last:
        diff = result.data.get("diff_last")
        src = str(result.data.get("diff_last_source") or "")
        if isinstance(diff, dict):
            if diff.get("error"):
                print("Changes since last snapshot")
                print(f"- {diff.get('error')}")
                if diff.get("error") == "no_previous_snapshot":
                    print(f"- Tip: run once with --history to create a baseline snapshot in {DEFAULT_HISTORY_DIR}")
                print("")
            elif diff:
                print("Changes since last snapshot")
                if src:
                    print(f"- Source: {R(src)}")
                if "listeners_ports" in diff:
                    d = diff["listeners_ports"]
                    print(f"- Listener ports: +{len(d.get('new', []))} / -{len(d.get('removed', []))}")
                    if d.get("new"):
                        print(f"  New: {', '.join([str(x) for x in d.get('new', [])[:8]])}" + (" ..." if len(d.get("new", [])) > 8 else ""))
                    if d.get("removed"):
                        print(f"  Removed: {', '.join([str(x) for x in d.get('removed', [])[:8]])}" + (" ..." if len(d.get("removed", [])) > 8 else ""))
                if "persistence_execs" in diff:
                    d = diff["persistence_execs"]
                    print(f"- Persistence executables: +{len(d.get('new', []))} / -{len(d.get('removed', []))}")
                    if d.get("new"):
                        print(f"  New: {', '.join([R(str(x)) for x in d.get('new', [])[:4]])}" + (" ..." if len(d.get("new", [])) > 4 else ""))
                    if d.get("removed"):
                        print(f"  Removed: {', '.join([R(str(x)) for x in d.get('removed', [])[:4]])}" + (" ..." if len(d.get("removed", [])) > 4 else ""))
                if "recent_apps_flagged" in diff:
                    d = diff["recent_apps_flagged"]
                    print(f"- Recent apps flagged: +{len(d.get('new', []))} / -{len(d.get('removed', []))}")
                    if d.get("new"):
                        print(f"  New: {', '.join([R(str(x)) for x in d.get('new', [])[:4]])}" + (" ..." if len(d.get("new", [])) > 4 else ""))
                    if d.get("removed"):
                        print(f"  Removed: {', '.join([R(str(x)) for x in d.get('removed', [])[:4]])}" + (" ..." if len(d.get("removed", [])) > 4 else ""))
                if "high_signal_posture" in diff:
                    print("- High-signal posture changes:")
                    for k, v in diff["high_signal_posture"].items():
                        print(f"  - {k}: {v.get('from')} -> {v.get('to')}")
                print("")

    print("macOS Security + Privacy Audit (read-only)")
    print(f"Generated: {R(result.generated)}")
    print(f"Mode: privacy={cfg.privacy} depth={cfg.depth}")
    print("")

    print("Security posture quick check")
    for k in ["SIP", "Gatekeeper", "FileVault", "Lockdown Mode", "Firewall", "Updates", "MDM enrolled", "Profiles present", "Proxy configured", "VPN connected", "Custom trust settings"]:
        print(f"- {k}: {R(str(result.posture.get(k, 'UNKNOWN')))}")
    print("")

    print("Inventory (best-effort)")
    print(
        f"- listeners={C(result.counts.get('listeners', 0))}; established_tcp_sample={C(result.counts.get('established', 0))}; "
        f"launch_items={C(result.counts.get('launch_items', 0))} (non_apple={C(result.counts.get('launch_non_apple', 0))}); "
        f"btm_enabled={C(result.counts.get('btm_enabled', 0))}; extensions={C(result.counts.get('extensions', 0))}; "
        f"shares={C(result.counts.get('shares', 0))}; "
        f"recent_apps_scanned={C(result.counts.get('recent_apps_scanned', 0))} (flagged={C(result.counts.get('recent_apps_flagged', 0))})"
    )
    print("")

    recent_apps = result.data.get("recent_apps") or []
    if recent_apps:
        print(f"Recent app installs/modifications (last {cfg.recent_apps_days} days, max {cfg.recent_apps_max}; redacted)")
        print("MODIFIED\tAPP\tBUNDLE_ID\tSIG\tSPCTL\tQUAR\tNOTE")
        for app in recent_apps[:10]:
            q = "unknown" if app.quarantine_present is None else ("yes" if app.quarantine_present else "no")
            sp = "unknown" if app.spctl_kind != "ok" else ("ok" if app.spctl_rc == 0 else "fail")
            note = ""
            if app.spctl_category == "rejected_resources_missing":
                note = "resources_missing"
            elif app.signature in {"unsigned", "adhoc"}:
                note = app.signature
            bid = app.bundle_id or "(none)"
            print(f"{app.modified}\t{R(app.name)[:28]}\t{R(bid)[:28]}\t{app.signature}\t{sp}\t{q}\t{note}")
        if len(recent_apps) > 10:
            print(f"(Truncated: showing 10 of {len(recent_apps)} recent apps.)")
        print("")

    if result.top_processes:
        print("Top processes (by CPU at capture, truncated)")
        print("PID\tUSER\t%CPU\t%MEM\tELAPSED\tCOMMAND")
        for pid, user2, cpu, mem, etime, cmd in result.top_processes:
            print(f"{pid}\t{user2}\t{cpu}\t{mem}\t{etime}\t{R(cmd)}")
        print("")

    sev_counts = _console_sev_counts(result.findings)
    print("Findings summary")
    print("CRITICAL={CRITICAL} HIGH={HIGH} MEDIUM={MEDIUM} LOW={LOW} INFO={INFO}".format(**sev_counts))

    if result.findings:
        print("")
        print("Top findings (redacted)")
        for i, f in enumerate(result.findings[:10], start=1):
            ev = R(f.evidence)[:240]
            print(f"{i}. [{f.severity}] {f.pillar}: {f.title} ({ev})")
    else:
        print("- No high-signal findings detected by automated checks.")

    print("")
    print("Actionable next steps (non-destructive)")
    action_findings = [f for f in result.findings if f.severity in {"CRITICAL", "HIGH"}]
    if not action_findings:
        action_findings = [f for f in result.findings if f.severity in {"MEDIUM"}]

    # De-duplicate by (pillar,title) to keep output tight.
    seen = set()
    uniq: List[Finding] = []
    for f in action_findings:
        key = (f.pillar, f.title)
        if key in seen:
            continue
        seen.add(key)
        uniq.append(f)

    if uniq:
        for f in uniq[:6]:
            print(f"- [{f.severity}] {f.pillar}: {f.title}")
            ev = R(f.evidence)[:220]
            if ev:
                print(f"  Evidence: {ev}")
            steps = _next_steps_for_finding(f)
            for j, step in enumerate(steps[:3], start=1):
                print(f"  {j}. {step}")
    else:
        print("- No findings to triage. If you still suspect keyloggers/sleeper agents: focus on Privacy permissions + persistence items + trust/proxy signals below.")

    print("")
    print("Manual privacy/keylogger checklist (recommended even if findings are clean)")
    manual = [
        "System Settings -> Privacy & Security -> Input Monitoring",
        "System Settings -> Privacy & Security -> Accessibility",
        "System Settings -> Privacy & Security -> Screen Recording",
        "System Settings -> Privacy & Security -> Full Disk Access",
        "System Settings -> Privacy & Security -> Automation (Apple Events)",
        "System Settings -> Privacy & Security -> Microphone",
        "System Settings -> Privacy & Security -> Camera",
    ]
    for m in manual:
        print(f"- {m}: only expected apps should be enabled")

    if result.unknowns:
        print("")
        print("Unknown / permission-blocked areas")
        for u in result.unknowns:
            print(f"- {u}")
        print("Tip: Re-run with the same settings after granting Full Disk Access to your terminal if you want more complete TCC signals (optional).")

        tcc_log_sample = result.data.get("tcc_log_sample") or []
        if tcc_log_sample:
            mins = cfg.tcc_recent_log_minutes or 0
            print("")
            print(f"Recent TCC log sample (last {mins} minutes; best-effort, redacted)")
            for ln in tcc_log_sample[-20:]:
                print(f"- {R(str(ln))[:240]}")


def render_pdf(cfg: AuditConfig, result: AuditResult) -> Path:
    home = Path.home()
    data = result.data
    stamp = data.get("stamp") or datetime.now().strftime("%Y-%m-%d_%H%M")

    # Resolve output path (private by default).
    if cfg.output_pdf:
        out_pdf = cfg.output_pdf.expanduser().resolve()
        out_pdf.parent.mkdir(parents=True, exist_ok=True)
    else:
        out_dir = cfg.output_dir.expanduser().resolve()
        out_dir.mkdir(parents=True, exist_ok=True)
        # If using default private dir, lock permissions down.
        if out_dir == DEFAULT_REPORTS_DIR.expanduser().resolve():
            try:
                os.chmod(out_dir, 0o700)
            except Exception:
                pass
        out_pdf = out_dir / f"security_audit_report_{stamp}.pdf"

    # Privacy redaction applied to outputs included in the PDF
    def R(s: str) -> str:
        s = redact_tokens(s)
        if cfg.privacy == "strict":
            s = redact_paths(s, home)
        return s

    findings_sorted: List[Finding] = result.findings

    b = PDFBuilder()
    l = PDFLayout(b, report_title="macOS Security + Privacy Audit", generated=str(data.get("now", result.generated)))

    l.heading("macOS End-to-End Security + Privacy Audit", level=1)
    l.paragraph("Non-destructive audit. This report is privacy-aware and redacts obvious secrets. Treat it as sensitive.")

    # Findings summary early
    l.heading("Findings Summary", level=2)
    if findings_sorted:
        rows = []
        for f in findings_sorted[: min(len(findings_sorted), 30)]:
            rows.append([f.severity, f.pillar, f.title, R(f.evidence)])
        l.table(["Severity", "Pillar", "Finding", "Evidence"], rows, col_widths=[70, 90, 170, 612 - 2 * 54 - 70 - 90 - 170])
        if len(findings_sorted) > 30:
            l.paragraph(f"(Truncated in PDF: showing 30 of {len(findings_sorted)} findings.)")
    else:
        l.paragraph("No high-signal findings detected by automated checks. Continue with manual verification sections for maximum confidence.")

    l.paragraph("Severity legend: CRITICAL/HIGH require immediate review; MEDIUM review soon; LOW/INFO are context.", size=10)

    l.heading("System Overview", level=2)
    l.table(
        ["Field", "Value"],
        [
            ["Generated", R(str(data.get("now", "")))],
            ["User", R(str(data.get("user", "")))],
            ["Uptime", R(str(data.get("uptime", "")))],
            ["OS", R(" ".join(str(data.get("sw_vers", "")).splitlines()))],
            ["Kernel", R(str(data.get("uname", "")))],
            ["Privacy mode", cfg.privacy],
            ["Depth", cfg.depth],
        ],
        col_widths=[150, 612 - 2 * 54 - 150],
    )

    l.heading("OS Integrity & Platform Protections", level=2)
    l.table(
        ["Control", "Status"],
        [
            ["SIP", R(str(data.get("sip", ""))) or "(unknown)"],
            ["Gatekeeper", R(str(data.get("gatekeeper", ""))) or "(unknown)"],
            ["FileVault", R(str(data.get("filevault", ""))) or "(unknown)"],
            ["Lockdown Mode (best-effort)", R(str(data.get("lockdown", "")))],
        ],
        col_widths=[210, 612 - 2 * 54 - 210],
    )

    l.heading("Firewall", level=2)
    l.table(
        ["Setting", "Value"],
        [
            ["Global State", R(str(data.get("fw_state", "")))],
            ["Stealth Mode", R(str(data.get("fw_stealth", "")))],
            ["Block All", R(str(data.get("fw_blockall", "")))],
        ],
        col_widths=[150, 612 - 2 * 54 - 150],
    )

    l.heading("Updates (Best-Effort)", level=2)
    su_keys = data.get("su_keys") or {}
    if su_keys:
        l.table(["Key", "Value"], [[k, str(v)] for k, v in sorted(su_keys.items())], col_widths=[230, 612 - 2 * 54 - 230])
    else:
        l.paragraph("Could not read /Library/Preferences/com.apple.SoftwareUpdate (permission blocked or unavailable).")

    l.heading("MDM / Configuration Profiles", level=2)
    enroll = str(data.get("enroll", ""))
    prof_list = str(data.get("prof_list", ""))
    l.paragraph("Enrollment status:")
    l.mono_block(R(enroll), max_lines=6)
    if "There are no configuration profiles" in prof_list:
        l.paragraph("Installed configuration profiles: none detected.")
    else:
        l.paragraph("Installed configuration profiles: present or unknown (review recommended).")

    l.heading("Kernel/System Extensions", level=2)
    sys_ext = str(data.get("sys_ext", ""))
    non_apple_kext_lines = data.get("non_apple_kext_lines") or []
    if "0 extension(s)" in sys_ext:
        l.paragraph("System Extensions: none detected.")
    else:
        l.paragraph("System Extensions: present (review recommended).")
        l.mono_block(R(sys_ext), max_lines=6)

    if non_apple_kext_lines:
        l.paragraph("Non-Apple kernel extensions appear loaded (review required):")
        l.mono_block("\n".join(non_apple_kext_lines[:6]), max_lines=6)
    else:
        l.paragraph("Non-Apple kernel extensions: none detected by kmutil.")

    l.heading("Processes / Compute (Top)", level=2)
    proc_rows = data.get("proc_rows") or []
    if proc_rows:
        rows = []
        for pid, user2, cpu, mem, etime, cmd in proc_rows[: cfg.max_rows]:
            cmd_out = cmd
            if cfg.privacy == "strict":
                cmd_out = redact_paths(cmd_out, home)
            rows.append([pid, user2, cpu, mem, etime, cmd_out[:120]])
        l.table(["PID", "User", "%CPU", "%MEM", "Elapsed", "Command"], rows, col_widths=[45, 50, 45, 45, 70, 612 - 2 * 54 - 45 - 50 - 45 - 45 - 70])
    else:
        l.paragraph("Process list unavailable.")

    l.heading("Network Surface", level=2)
    listeners = data.get("listeners") or []
    if listeners:
        l.table(
            ["Process", "PID", "Proto", "Listen"],
            [[R(x.process), x.pid, x.proto, R(x.listen)] for x in listeners[: cfg.max_rows]],
            col_widths=[150, 55, 55, 612 - 2 * 54 - 150 - 55 - 55],
        )
    else:
        l.paragraph("No listening TCP sockets found at time of capture.")

    l.heading("Established Connections (Sample)", level=2)
    established = data.get("established") or []
    if established:
        rows = []
        for c in established[: cfg.max_rows]:
            remote = c.remote
            if cfg.privacy == "strict":
                remote = redact_remote_endpoint(remote)
            rows.append([R(c.process), c.pid, R(c.local), R(remote), c.state])
        l.table(["Process", "PID", "Local", "Remote", "State"], rows, col_widths=[150, 55, 150, 150, 612 - 2 * 54 - 150 - 55 - 150 - 150])
    else:
        l.paragraph("No established TCP connections found (or permission blocked).")

    l.heading("Proxy / DNS / Hosts", level=2)
    proxy = str(data.get("proxy", ""))
    dns = str(data.get("dns", ""))
    hosts_text = str(data.get("hosts_text", ""))
    proxy_clean = " ".join([ln.strip() for ln in proxy.splitlines() if ln.strip()])
    l.paragraph(f"Proxy (summary): {R(proxy_clean)[:260] or '(none)'}", size=10)

    # DNS resolver #1 summary
    dns_lines = [ln.rstrip("\n") for ln in dns.splitlines()]
    resolver1 = []
    in_r1 = False
    for ln in dns_lines:
        if ln.startswith("resolver #1"):
            in_r1 = True
            continue
        if in_r1 and ln.startswith("resolver #"):
            break
        if in_r1 and ln.strip():
            resolver1.append(ln.strip())
        if len(resolver1) >= 12:
            break
    if resolver1:
        l.mono_block("\n".join(resolver1), max_lines=12)

    # hosts file (first lines)
    hosts_preview = "\n".join(hosts_text.splitlines()[:12])
    l.paragraph("/etc/hosts (first lines):", size=10)
    l.mono_block(hosts_preview, max_lines=12)

    l.heading("VPN / Network Connections", level=2)
    nc_list = str(data.get("nc_list", ""))
    if nc_list.strip():
        l.mono_block(R(nc_list), max_lines=10)
    else:
        l.paragraph("No VPN services listed (or command unavailable).")

    l.heading("Persistence (LaunchAgents/Daemons)", level=2)
    launch_items = data.get("launch_items") or []
    uid = int(data.get("uid", os.getuid()))
    interesting = [it for it in launch_items if not it.label.startswith("com.apple.")]
    interesting = sorted(interesting, key=lambda x: x.path)

    rows = []
    for it in interesting[: min(len(interesting), cfg.max_rows)]:
        exe = it.exec_path or ""
        exe_out = exe
        if cfg.privacy == "strict":
            exe_out = redact_paths(exe_out, home)
        rows.append([
            it.label,
            it.kind,
            "yes" if it.loaded else "no",
            "yes" if it.keepalive else "no" if it.keepalive is False else "",
            str(it.startinterval or ""),
            exe_out[:60],
        ])

    if rows:
        l.table(["Label", "Kind", "Loaded", "KeepAlive", "Interval", "Exec"], rows, col_widths=[175, 95, 50, 60, 55, 612 - 2 * 54 - 175 - 95 - 50 - 60 - 55])
    else:
        l.paragraph("No LaunchAgents/Daemons found (unexpected).")

    launch_status = data.get("launch_status") or []
    if launch_status:
        l.heading("launchd Status (Selected)", level=3)
        l.table(
            ["Service", "State", "Runs", "Last Exit"],
            [[x.label.replace(f"gui/{uid}/", ""), x.state, str(x.runs or ""), str(x.last_exit or "")] for x in launch_status[: cfg.max_rows]],
            col_widths=[210, 140, 55, 612 - 2 * 54 - 210 - 140 - 55],
        )

    l.heading("Background Items / Login Items (BTM)", level=2)
    btm_items = data.get("btm_items") or []
    btm_kind = str(data.get("btm_kind") or "")
    btm_rc = int(data.get("btm_rc") or 0)
    if btm_items:
        rows = []
        for it in btm_items[: min(len(btm_items), cfg.max_rows)]:
            rows.append([
                it.scope,
                it.identifier,
                it.team_id,
                redact_paths(it.exec_path, home) if cfg.privacy == "strict" else it.exec_path,
            ])
        l.table(["Scope", "Identifier", "TeamID", "Exec"], rows, col_widths=[70, 200, 80, 612 - 2 * 54 - 70 - 200 - 80])
    else:
        if btm_kind and (btm_kind != "ok" or btm_rc != 0):
            l.paragraph(f"Background Items check unavailable: kind={btm_kind} rc={btm_rc}.")
        else:
            l.paragraph("No enabled Background Items detected.")

    l.heading("Cron / Scheduled Tasks", level=2)
    cron = data.get("cron")
    if cron and getattr(cron, "rc", 1) == 0:
        l.paragraph("User crontab present.")
        l.mono_block(R(getattr(cron, "out", "")), max_lines=10)
    else:
        out = getattr(cron, "out", "") if cron else ""
        if "no crontab" in (out or "").lower():
            l.paragraph("No user crontab present.")
        else:
            l.paragraph(f"crontab check blocked/unavailable: {R(out)[:140]}")

    l.heading("Trust & MITM Signals", level=2)
    trust_user = str(data.get("trust_user", ""))
    trust_admin = str(data.get("trust_admin", ""))
    if "No Trust Settings were found" in trust_user and "No Trust Settings were found" in trust_admin:
        l.paragraph("No custom trust settings detected.")
    else:
        l.paragraph("Custom trust settings may be present (review required).")
        l.mono_block(R(trust_user), max_lines=8)

    l.heading("Sharing / Local Data Exposure", level=2)
    shares = data.get("shares") or []
    if shares:
        rows = []
        for s in shares[: cfg.max_rows]:
            rows.append([
                s.protocol,
                s.name,
                redact_paths(s.path, home) if cfg.privacy == "strict" else s.path,
                "yes" if s.guest_access else "no" if s.guest_access is False else "",
                "yes" if s.read_only else "no" if s.read_only is False else "",
            ])
        l.table(["Proto", "Name", "Path", "Guest", "Read-only"], rows, col_widths=[45, 170, 180, 55, 612 - 2 * 54 - 45 - 170 - 180 - 55])
        l.paragraph("Note: share points can exist even when SMB is not actively listening.", size=10)
    else:
        l.paragraph("No share points detected (or permission blocked).")

    brew_services = str(data.get("brew_services", ""))
    if brew_services.strip():
        l.heading("Homebrew Services", level=2)
        rows = []
        for ln in brew_services.splitlines()[1:]:
            cols = ln.split()
            if len(cols) >= 2:
                rows.append([cols[0], cols[1]])
        if rows:
            l.table(["Service", "Status"], rows[: cfg.max_rows], col_widths=[220, 612 - 2 * 54 - 220])

    l.heading("Browser Attack Surface", level=2)
    ext_rows = data.get("ext_rows") or []
    if ext_rows:
        risky_keywords = ["Downloader", "Video Downloader", "Wallet", "MetaMask", "Yoroi", "Eternl", "Nami", "Nautilus"]
        rows = []
        for scope, ext_id, name, summary in ext_rows[: min(len(ext_rows), cfg.max_rows)]:
            risk = "review"
            if any(k.lower() in str(name).lower() for k in risky_keywords):
                risk = "high"
            rows.append([scope, str(name), risk, str(summary)])
        l.table(["Browser/Profile", "Extension", "Risk", "Summary"], rows, col_widths=[120, 190, 55, 612 - 2 * 54 - 120 - 190 - 55])
    else:
        l.paragraph("No Chromium-based extension directories detected.")

    ext_external = data.get("ext_external") or []
    if ext_external:
        l.heading("External/Forced Extension Artifacts", level=3)
        l.table(["Dir", "File", "Keys", "URL/Path"], ext_external[: cfg.max_rows], col_widths=[140, 120, 100, 612 - 2 * 54 - 140 - 120 - 100])

    native_hosts = data.get("native_hosts") or []
    if native_hosts:
        l.heading("Native Messaging Hosts", level=3)
        l.table(["Dir", "File", "Name", "Path"], native_hosts[: cfg.max_rows], col_widths=[160, 110, 140, 612 - 2 * 54 - 160 - 110 - 140])

    l.heading("Privacy Permissions (Best-Effort)", level=2)
    tcc_status = str(data.get("tcc_status", ""))
    tcc_rows = data.get("tcc_rows") or []
    if tcc_status == "ok":
        if tcc_rows:
            l.paragraph("TCC grants detected for selected high-risk services (auth_value=2).")
            l.table(["Service", "Client", "Auth", "LastModified"], tcc_rows[: cfg.max_rows], col_widths=[170, 220, 45, 612 - 2 * 54 - 170 - 220 - 45])
        else:
            l.paragraph("No allowed grants detected for selected services (or none recorded).")
    else:
        l.paragraph(f"Automatic TCC inspection blocked/unavailable: {tcc_status}.")
        l.paragraph("Manual check: System Settings -> Privacy & Security -> Input Monitoring / Accessibility / Screen Recording / Full Disk Access / Automation / Microphone / Camera.")

    l.heading("Signing / Gatekeeper Checks (Persistence/Background Items)", level=2)
    assessments = data.get("assessments") or []
    if assessments:
        rows = []
        for a in assessments[: cfg.max_rows]:
            path_out = getattr(a, "assessed_path", "") or a.path
            if cfg.privacy == "strict":
                path_out = redact_paths(path_out, home)
            cat = getattr(a, "spctl_category", "") or ""
            rows.append([path_out, a.codesign_summary, cat, a.spctl_summary])
        l.table(["Path", "codesign", "spctl category", "spctl detail"], rows, col_widths=[220, 120, 95, 612 - 2 * 54 - 220 - 120 - 95])
        if cfg.depth != "deep":
            l.paragraph("Tip: run with --depth deep to assess more executables.", size=10)
    else:
        l.paragraph("No signing assessments performed (no persistence/background executables found or permission blocked).")

    l.heading("Limitations / Next Steps", level=2)
    l.paragraph(
        "This audit is intentionally non-destructive. Some checks are blocked by macOS privacy protections without additional permissions. "
        "For maximum confidence, complete the manual Privacy & Security review and verify that only expected apps have Input Monitoring/Accessibility/Screen Recording/Full Disk Access/Automation grants."
    )

    l.finish()
    pdf_bytes = b.build()
    out_pdf.write_bytes(pdf_bytes)
    try:
        os.chmod(out_pdf, 0o600)
    except Exception:
        pass
    return out_pdf


def parse_args(argv: List[str]) -> AuditConfig:
    p = argparse.ArgumentParser(description="Read-only macOS security + privacy audit -> console summary (PDF optional)")
    p.add_argument("--format", choices=["text", "json"], default="text", help="Output format (default: text)")
    p.add_argument("--diff-last", action="store_true", help="Show changes since last history snapshot (read-only; no writes)")
    p.add_argument("--pdf", action="store_true", help="Generate a PDF report (opt-in)")
    p.add_argument("--output-pdf", default="", help="Write PDF to an explicit file path (implies --pdf)")
    p.add_argument(
        "--output-dir",
        default=str(DEFAULT_REPORTS_DIR),
        help="Where to write the PDF when --pdf is set (default: private reports folder)",
    )
    p.add_argument("--depth", choices=["standard", "deep"], default="standard")
    p.add_argument("--privacy", choices=["strict", "balanced", "forensics"], default="strict")
    p.add_argument("--max-rows", type=int, default=60)
    p.add_argument("--recent-apps-days", type=int, default=None, help="Scan for recently modified .app bundles within N days (default: 14 standard / 60 deep)")
    p.add_argument("--recent-apps-max", type=int, default=None, help="Max number of recent apps to assess (default: 20 standard / 60 deep)")
    p.add_argument("--tcc-recent-log-minutes", type=int, default=None, help="If TCC DB is blocked, optionally sample recent TCC logs from unified logging (minutes)")

    # history defaults off (privacy-first)
    g = p.add_mutually_exclusive_group()
    g.add_argument("--history", dest="history", action="store_true", help="Write sanitized JSON snapshot for diffing (off by default)")
    g.add_argument("--no-history", dest="history", action="store_false", help="Do not write history snapshot (default)")
    p.set_defaults(history=False)

    a = p.parse_args(argv)
    if a.recent_apps_days is None:
        recent_apps_days = 60 if a.depth == "deep" else 14
    else:
        recent_apps_days = max(0, int(a.recent_apps_days))

    if a.recent_apps_max is None:
        recent_apps_max = 60 if a.depth == "deep" else 20
    else:
        recent_apps_max = max(0, int(a.recent_apps_max))

    output_pdf = Path(a.output_pdf).expanduser() if a.output_pdf else None
    generate_pdf = bool(a.pdf) or bool(output_pdf)
    return AuditConfig(
        depth=a.depth,
        privacy=a.privacy,
        format=a.format,
        generate_pdf=generate_pdf,
        output_dir=Path(a.output_dir).expanduser(),
        output_pdf=output_pdf,
        keep_history=bool(a.history),
        diff_last=bool(a.diff_last),
        max_rows=max(10, int(a.max_rows)),
        recent_apps_days=recent_apps_days,
        recent_apps_max=recent_apps_max,
        tcc_recent_log_minutes=(int(a.tcc_recent_log_minutes) if a.tcc_recent_log_minutes is not None else None),
    )


def main(argv: List[str]) -> int:
    cfg = parse_args(argv)
    result = run_audit(cfg)
    if cfg.format == "json":
        obj = dict(result.snapshot)
        if cfg.generate_pdf:
            out_pdf = render_pdf(cfg, result)
            obj["pdf_path"] = str(out_pdf)
        # Ensure the JSON always has history path when present.
        hist_path = result.data.get("hist_path") or obj.get("history_path") or ""
        if hist_path:
            obj["history_path"] = str(hist_path)
        print(json.dumps(obj, indent=2))
        return 0

    render_console(cfg, result)

    if cfg.generate_pdf:
        out_pdf = render_pdf(cfg, result)
        print("")
        print(f"PDF written to: {out_pdf}")
    if cfg.keep_history:
        hist_path = result.data.get("hist_path") or ""
        if hist_path:
            print(f"History snapshot written to: {hist_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
