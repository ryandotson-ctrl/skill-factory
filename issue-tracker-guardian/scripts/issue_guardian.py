#!/usr/bin/env python3
"""
Issue Tracker Guardian 2.0
Portable autonomous issue lifecycle manager.
"""

from __future__ import annotations

import argparse
import dataclasses
import difflib
import fnmatch
import hashlib
import json
import os
import re
import subprocess
import sys
import textwrap
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    yaml = None


DEFAULT_STATE_REL = ".issue-guardian/state.json"
DEFAULT_CONFIG_REL = ".issue-guardian/config.yaml"
DEFAULT_ISSUES_MD = "issues.md"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def as_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def safe_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return default


def normalize_title(value: str) -> str:
    cleaned = re.sub(r"\s+", " ", (value or "").strip().lower())
    return re.sub(r"[^a-z0-9 ]", "", cleaned)


def short_line(value: str, max_len: int = 90) -> str:
    line = re.sub(r"\s+", " ", (value or "").strip())
    if len(line) <= max_len:
        return line
    return line[: max_len - 3].rstrip() + "..."


def sha1_text(value: str) -> str:
    return hashlib.sha1((value or "").encode("utf-8")).hexdigest()


def command_exists(cmd: str) -> bool:
    return subprocess.run(["bash", "-lc", f"command -v {cmd}"], capture_output=True).returncode == 0


def run_cmd(cmd: str, cwd: Path, timeout: int = 120) -> Dict[str, Any]:
    started = now_iso()
    proc = subprocess.run(
        ["bash", "-lc", cmd],
        cwd=str(cwd),
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    return {
        "cmd": cmd,
        "started_at": started,
        "finished_at": now_iso(),
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
    }


def load_yaml_or_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        try:
            data = json.loads(text)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}
    if yaml is not None:
        try:
            data = yaml.safe_load(text)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}
    # Fallback without PyYAML: only allow JSON-compatible content.
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def infer_repo_from_git(workspace_root: Path) -> Optional[str]:
    remote = run_cmd("git remote get-url origin", workspace_root)
    if remote["returncode"] != 0:
        return None
    url = (remote.get("stdout") or "").strip()
    if not url:
        return None

    # git@github.com:owner/repo.git
    m = re.search(r"github\.com[:/](?P<owner>[^/]+)/(?P<repo>[^/]+?)(?:\.git)?$", url)
    if m:
        return f"{m.group('owner')}/{m.group('repo')}"
    return None


def parse_guardian_meta(body: str) -> Dict[str, str]:
    meta: Dict[str, str] = {}
    for key, value in re.findall(r"<!--\s*issue_guardian:([a-z_]+)=([^>]+?)\s*-->", body or "", flags=re.IGNORECASE):
        meta[key.strip().lower()] = value.strip()
    return meta


def ensure_state(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {
            "schema_version": "2.0.0",
            "updated_at": now_iso(),
            "issues": [],
            "actions": [],
            "classification_history": [],
        }
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        data = {}
    if not isinstance(data, dict):
        data = {}
    data.setdefault("schema_version", "2.0.0")
    data.setdefault("updated_at", now_iso())
    data.setdefault("issues", [])
    data.setdefault("actions", [])
    data.setdefault("classification_history", [])
    return data


def save_state(path: Path, state: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    state["updated_at"] = now_iso()
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def issues_markdown_rows(issues: List[Dict[str, Any]]) -> str:
    lines = [
        "| ID | State | Type | Severity | Title | Updated | Link |",
        "|---|---|---|---|---|---|---|",
    ]
    for it in issues:
        lines.append(
            "| {id} | {state} | {typ} | {sev} | {title} | {updated} | {url} |".format(
                id=it.get("id", ""),
                state=it.get("state", ""),
                typ=it.get("type", ""),
                sev=it.get("severity", ""),
                title=str(it.get("title", "")).replace("|", "\\|"),
                updated=it.get("updated_at", ""),
                url=it.get("url", ""),
            )
        )
    return "\n".join(lines) + "\n"


def load_taxonomy(skill_root: Path, workspace_root: Path) -> Dict[str, Any]:
    defaults = load_yaml_or_json(skill_root / "references" / "issue_taxonomy.yaml")
    config = load_yaml_or_json(workspace_root / DEFAULT_CONFIG_REL)
    cfg_rules = config.get("classification_rules") if isinstance(config, dict) else None
    if cfg_rules:
        merged = deep_merge(defaults, {"classification_rules": cfg_rules})
    else:
        merged = defaults
    if isinstance(config, dict) and config.get("duplicate_policy"):
        merged = deep_merge(merged, {"duplicate_policy": config.get("duplicate_policy")})
    return merged


def load_policy(skill_root: Path, workspace_root: Path) -> Dict[str, Any]:
    defaults = load_yaml_or_json(skill_root / "references" / "lifecycle_policy.yaml")
    config = load_yaml_or_json(workspace_root / DEFAULT_CONFIG_REL)
    if isinstance(config, dict):
        keys = ["monitoring", "creation_policy", "update_policy", "reopen_policy", "closure_policy", "verification_map", "signal_files"]
        overlay = {k: config.get(k) for k in keys if config.get(k) is not None}
        return deep_merge(defaults, overlay)
    return defaults


def classify_text(text: str, taxonomy: Dict[str, Any]) -> Dict[str, Any]:
    lowered = (text or "").lower()
    best: Optional[Dict[str, Any]] = None
    best_hits = 0

    for rule in taxonomy.get("classification_rules", []) or []:
        patterns = rule.get("match_any", []) or []
        hits = 0
        for p in patterns:
            if str(p).lower() in lowered:
                hits += 1
        if hits > best_hits:
            best_hits = hits
            best = rule

    defaults = taxonomy.get("defaults", {}) or {}
    if best is None:
        typ = defaults.get("type", "question")
        sev = defaults.get("severity", "low")
        comp = defaults.get("component", "general")
        labels = defaults.get("labels", ["triage"])
        confidence = 0.45 if lowered.strip() else 0.0
        rule_id = "default"
    else:
        typ = best.get("type", "question")
        sev = best.get("severity", "low")
        comp = best.get("component", "general")
        labels = best.get("labels", ["triage"])
        confidence = min(0.98, 0.45 + (0.16 * best_hits))
        rule_id = best.get("id", "rule")

    return {
        "type": typ,
        "severity": sev,
        "component": comp,
        "labels": labels,
        "confidence": round(confidence, 3),
        "rule_id": rule_id,
    }


def build_fingerprint(title: str, issue_type: str, component: str, evidence: List[str]) -> str:
    ev = "\n".join(short_line(e, 120).lower() for e in (evidence or [])[:3])
    raw = f"{normalize_title(title)}|{issue_type.lower()}|{component.lower()}|{ev}"
    return sha1_text(raw)


def split_candidate_texts(signals: List[Dict[str, Any]]) -> List[Tuple[str, str, List[str]]]:
    out: List[Tuple[str, str, List[str]]] = []
    for sig in signals:
        src = sig.get("source", "unknown")
        text = sig.get("text", "")
        if not text:
            continue
        lower = text.lower()
        if src in {"logs", "tests"}:
            lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
            hits = [ln for ln in lines if any(k in ln.lower() for k in ("error", "failed", "exception", "traceback", "panic", "oom"))]
            if hits:
                for ln in hits[:3]:
                    out.append((src, ln, [ln]))
                continue
        if src == "user":
            out.append((src, text, sig.get("evidence", []) or []))
            continue
        if src == "git":
            # Git is primarily resolution evidence, not creation evidence.
            # Only promote git into a candidate when an explicit incident marker exists.
            explicit_issue_markers = (
                "new bug:",
                "bug report:",
                "incident:",
                "regression detected:",
                "error report:",
            )
            if any(marker in lower for marker in explicit_issue_markers):
                out.append((src, text, []))
            continue
        out.append((src, text, sig.get("evidence", []) or []))
    return out


def _candidate_text_blob(candidate: Dict[str, Any]) -> str:
    parts = [
        str(candidate.get("title", "") or ""),
        str(candidate.get("summary", "") or ""),
    ]
    for ev in candidate.get("evidence", []) or []:
        if isinstance(ev, str):
            parts.append(ev)
    return "\n".join(parts).strip().lower()


def is_progress_update_candidate(candidate: Dict[str, Any], policy: Dict[str, Any]) -> bool:
    text = _candidate_text_blob(candidate)
    if not text:
        return True

    creation = policy.get("creation_policy", {}) or {}
    patterns = creation.get("non_issue_update_patterns", []) or []
    default_patterns = [
        "work in progress",
        "wip",
        "fix applied",
        "patched",
        "implemented fix",
        "validation passed",
        "tests passed",
        "build succeeded",
        "build complete",
        "progress update",
        "status update",
        "git status:",
        "recent commits:",
        "changed files:",
    ]
    merged_patterns = [str(p).strip().lower() for p in (patterns or default_patterns) if str(p).strip()]
    return any(token in text for token in merged_patterns)


def derive_title(issue_type: str, text: str) -> str:
    head = short_line(text, 78)
    prefix = {
        "bug": "[Bug] ",
        "enhancement": "[Enhancement] ",
        "chore": "[Chore] ",
        "question": "[Question] ",
    }.get(issue_type, "[Issue] ")
    return prefix + head


def candidate_from_text(
    source: str,
    text: str,
    evidence: List[str],
    taxonomy: Dict[str, Any],
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    cls = classify_text(text, taxonomy)
    title = derive_title(cls["type"], text)
    candidate_evidence = list(evidence or [])
    if text and text not in candidate_evidence:
        candidate_evidence.insert(0, text)
    fp = build_fingerprint(title, cls["type"], cls["component"], candidate_evidence)
    labels = list(cls["labels"] or [])
    component = cls["component"]

    cfg = config or {}
    label_map = cfg.get("label_map", {}) if isinstance(cfg, dict) else {}
    if isinstance(label_map, dict):
        for extra in label_map.get(cls["type"], []) or []:
            if isinstance(extra, str) and extra.strip():
                labels.append(extra.strip())

    path_ownership = cfg.get("path_ownership", {}) if isinstance(cfg, dict) else {}
    evidence_paths: List[str] = []
    for ev in candidate_evidence:
        if isinstance(ev, str) and ev.startswith("file:"):
            evidence_paths.append(ev[5:])

    if isinstance(path_ownership, dict):
        for path in evidence_paths:
            for pattern, data in path_ownership.items():
                try:
                    matched = fnmatch.fnmatch(path, str(pattern))
                except Exception:
                    matched = False
                if not matched:
                    continue
                if isinstance(data, str) and data.strip():
                    component = data.strip()
                elif isinstance(data, dict):
                    if data.get("component"):
                        component = str(data.get("component")).strip()
                    for extra in data.get("labels", []) or []:
                        if isinstance(extra, str) and extra.strip():
                            labels.append(extra.strip())

    labels = sorted(set(labels))

    return {
        "source": source,
        "title": title,
        "summary": short_line(text, 220),
        "type": cls["type"],
        "severity": cls["severity"],
        "component": component,
        "confidence": cls["confidence"],
        "rule_id": cls["rule_id"],
        "labels": labels,
        "repro": "",
        "expected": "",
        "actual": "",
        "evidence": candidate_evidence[:12],
        "fingerprint": fp,
    }


def collect_signal_files(workspace_root: Path, names: List[str], window_hours: int) -> List[Path]:
    now_ts = datetime.now(timezone.utc).timestamp()
    max_age = max(1, window_hours) * 3600
    out: List[Path] = []
    for rel in names:
        p = (workspace_root / rel).resolve()
        if not p.exists() or not p.is_file():
            continue
        try:
            age = now_ts - p.stat().st_mtime
        except Exception:
            continue
        if age <= max_age:
            out.append(p)
    return out


def collect_signals(args: argparse.Namespace, policy: Dict[str, Any], workspace_root: Path) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    sources = args.input_source or ["user", "tests", "logs", "git", "issues"]
    window_hours = safe_int(args.periodic_window_hours, 24)

    out: List[Dict[str, Any]] = []
    meta: Dict[str, Any] = {"source_counts": {}, "files_read": []}

    if "user" in sources:
        body_parts = [args.message or "", args.title or "", args.body or ""]
        text = "\n".join([p.strip() for p in body_parts if p and p.strip()]).strip()
        ev = args.evidence or []
        if text or ev:
            out.append({"source": "user", "text": text or "User-provided issue signal", "evidence": ev})

    sig_files = policy.get("signal_files", {}) or {}
    for src in ("tests", "logs"):
        if src not in sources:
            continue
        rels = sig_files.get(src, []) or []
        for p in collect_signal_files(workspace_root, rels, window_hours):
            try:
                text = p.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            out.append({"source": src, "text": text[:50000], "evidence": [f"file:{p}"]})
            meta["files_read"].append(str(p))

    for p in args.signal_file or []:
        fp = (workspace_root / p).resolve() if not os.path.isabs(p) else Path(p)
        if fp.exists() and fp.is_file():
            try:
                text = fp.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                text = ""
            out.append({"source": "logs", "text": text[:50000], "evidence": [f"file:{fp}"]})
            meta["files_read"].append(str(fp))

    if "git" in sources:
        status = run_cmd("git status --porcelain", workspace_root)
        log = run_cmd("git log --pretty='%H %s' -n 25", workspace_root)
        diff_names = run_cmd("git diff --name-only HEAD~20..HEAD", workspace_root)
        git_text = []
        if status["returncode"] == 0:
            git_text.append("git status:\n" + (status.get("stdout") or ""))
        if log["returncode"] == 0:
            git_text.append("recent commits:\n" + (log.get("stdout") or ""))
        if diff_names["returncode"] == 0:
            git_text.append("changed files:\n" + (diff_names.get("stdout") or ""))
        merged = "\n\n".join([g for g in git_text if g.strip()]).strip()
        if merged:
            out.append({"source": "git", "text": merged, "evidence": []})

    for src in sources:
        meta["source_counts"][src] = len([s for s in out if s.get("source") == src])

    return out, meta


def dedupe_candidates(candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen: set[str] = set()
    out: List[Dict[str, Any]] = []
    for c in candidates:
        fp = c.get("fingerprint")
        if not fp or fp in seen:
            continue

        merged = False
        c_norm = normalize_title(c.get("title", ""))
        for existing in out:
            e_norm = normalize_title(existing.get("title", ""))
            score = difflib.SequenceMatcher(None, c_norm, e_norm).ratio()
            if score >= 0.88:
                merged = True
                old_ev = existing.get("evidence", []) or []
                new_ev = c.get("evidence", []) or []
                existing["evidence"] = list(dict.fromkeys(old_ev + new_ev))[:12]
                if float(c.get("confidence", 0.0)) > float(existing.get("confidence", 0.0)):
                    existing["confidence"] = c.get("confidence")
                    existing["type"] = c.get("type")
                    existing["severity"] = c.get("severity")
                    existing["component"] = c.get("component")
                    existing["labels"] = c.get("labels", [])
                break

        if merged:
            seen.add(fp)
            continue

        seen.add(fp)
        out.append(c)
    return out


def match_existing_issue(
    candidate: Dict[str, Any],
    open_issues: List[Dict[str, Any]],
    closed_issues: List[Dict[str, Any]],
    threshold: float,
) -> Tuple[Optional[Dict[str, Any]], Optional[str], Optional[str]]:
    c_fp = (candidate.get("fingerprint") or "").strip().lower()
    c_title = candidate.get("title") or ""
    c_norm = normalize_title(c_title)

    # Exact open fingerprint/title match first.
    for issue in open_issues:
        i_fp = (issue.get("fingerprint") or "").strip().lower()
        if c_fp and i_fp and c_fp == i_fp:
            return issue, "duplicate_open", "fingerprint"
        if normalize_title(issue.get("title", "")) == c_norm:
            return issue, "duplicate_open", "title_exact"

    # Fuzzy open title match.
    best_issue = None
    best_score = 0.0
    for issue in open_issues:
        score = difflib.SequenceMatcher(None, c_norm, normalize_title(issue.get("title", ""))).ratio()
        if score > best_score:
            best_issue = issue
            best_score = score
    if best_issue and best_score >= threshold:
        return best_issue, "duplicate_open", f"title_fuzzy:{best_score:.2f}"

    # Closed issue -> possible regression reopen.
    for issue in closed_issues:
        i_fp = (issue.get("fingerprint") or "").strip().lower()
        if c_fp and i_fp and c_fp == i_fp:
            return issue, "reopen_candidate", "fingerprint"

    return None, None, None


def issue_body_from_candidate(candidate: Dict[str, Any]) -> str:
    ev_lines = "\n".join(f"- {short_line(e, 400)}" for e in (candidate.get("evidence") or [])[:12])
    return textwrap.dedent(
        f"""
        ## Summary
        {candidate.get('summary', '')}

        ## Expected
        {candidate.get('expected', 'TBD') or 'TBD'}

        ## Actual
        {candidate.get('actual', 'TBD') or 'TBD'}

        ## Reproduction
        {candidate.get('repro', 'TBD') or 'TBD'}

        ## Evidence
        {ev_lines or '- No evidence provided.'}

        ## Classification
        - Type: {candidate.get('type', 'question')}
        - Severity: {candidate.get('severity', 'low')}
        - Component: {candidate.get('component', 'general')}
        - Confidence: {candidate.get('confidence', 0.0)}

        <!-- issue_guardian:fingerprint={candidate.get('fingerprint','')} -->
        <!-- issue_guardian:type={candidate.get('type','question')} -->
        <!-- issue_guardian:severity={candidate.get('severity','low')} -->
        <!-- issue_guardian:component={candidate.get('component','general')} -->
        """
    ).strip() + "\n"


def lifecycle_comment(action: str, candidate: Dict[str, Any], reason: str, checks: Optional[List[Dict[str, Any]]] = None) -> str:
    lines = [
        "Issue Guardian Update",
        f"- Action: {action}",
        f"- Confidence: {candidate.get('confidence', 0.0)}",
        f"- Fingerprint: `{candidate.get('fingerprint', '')}`",
    ]
    if candidate.get("evidence"):
        lines.append("- Evidence added:")
        for e in (candidate.get("evidence") or [])[:6]:
            lines.append(f"  - {short_line(e, 220)}")
    if checks:
        lines.append("- Verification:")
        for c in checks:
            lines.append(f"  - {c.get('cmd')}: {'pass' if c.get('returncode') == 0 else 'fail'}")
    lines.append(f"- Reason: {reason}")
    return "\n".join(lines)


class BaseTracker:
    def list_issues(self) -> List[Dict[str, Any]]:  # pragma: no cover - interface
        raise NotImplementedError

    def create_issue(self, candidate: Dict[str, Any], dry_run: bool) -> Dict[str, Any]:  # pragma: no cover
        raise NotImplementedError

    def comment_issue(self, issue: Dict[str, Any], comment: str, dry_run: bool) -> None:  # pragma: no cover
        raise NotImplementedError

    def add_labels(self, issue: Dict[str, Any], labels: List[str], dry_run: bool) -> None:  # pragma: no cover
        raise NotImplementedError

    def close_issue(self, issue: Dict[str, Any], comment: str, dry_run: bool) -> None:  # pragma: no cover
        raise NotImplementedError

    def reopen_issue(self, issue: Dict[str, Any], comment: str, dry_run: bool) -> None:  # pragma: no cover
        raise NotImplementedError


class GitHubTracker(BaseTracker):
    def __init__(self, workspace_root: Path, repo: str, max_issues: int):
        self.workspace_root = workspace_root
        self.repo = repo
        self.max_issues = max(1, max_issues)
        self._label_cache: Optional[set[str]] = None

    def _run(self, cmd: str) -> Dict[str, Any]:
        return run_cmd(cmd, self.workspace_root)

    @staticmethod
    def _is_missing_label_error(stderr: str) -> bool:
        text = (stderr or "").lower()
        return ("label" in text and "not found" in text) or ("could not add label" in text)

    @staticmethod
    def _label_color(name: str) -> str:
        lowered = (name or "").strip().lower()
        if lowered == "bug":
            return "d73a4a"
        if lowered == "enhancement":
            return "a2eeef"
        if lowered == "chore":
            return "c5def5"
        if lowered == "question":
            return "d876e3"
        if lowered.startswith("priority:"):
            return "b60205"
        if lowered.startswith("area:"):
            return "0e8a16"
        return "ededed"

    @staticmethod
    def _label_description(name: str) -> str:
        lowered = (name or "").strip().lower()
        if lowered.startswith("area:"):
            return f"Component area label: {name}"
        if lowered.startswith("priority:"):
            return f"Priority label: {name}"
        return f"Managed by issue-tracker-guardian ({name})"

    def _load_labels(self, force: bool = False) -> set[str]:
        if self._label_cache is not None and not force:
            return set(self._label_cache)
        cmd = f"gh label list --repo {self.repo} --limit 1000 --json name"
        res = self._run(cmd)
        if res["returncode"] != 0:
            if self._label_cache is not None:
                return set(self._label_cache)
            self._label_cache = set()
            return set()
        payload = json.loads(res.get("stdout") or "[]")
        names = {
            str(it.get("name", "")).strip()
            for it in payload
            if isinstance(it, dict) and str(it.get("name", "")).strip()
        }
        self._label_cache = names
        return set(names)

    def _ensure_labels(self, labels: List[str]) -> List[str]:
        requested = [str(x).strip() for x in labels if str(x).strip()]
        if not requested:
            return []

        known = self._load_labels()
        for label in requested:
            if label in known:
                continue
            cmd = (
                f"gh label create {json.dumps(label)} --repo {self.repo} "
                f"--color {self._label_color(label)} "
                f"--description {json.dumps(self._label_description(label))}"
            )
            res = self._run(cmd)
            if res["returncode"] == 0:
                known.add(label)
                continue
            stderr_lower = (res.get("stderr") or "").lower()
            if "already exists" in stderr_lower:
                known.add(label)
                continue
            # Permission/policy constraints can block label creation on some repos.
            # Keep lifecycle execution non-fatal and proceed with labels that exist.
            continue

        self._label_cache = known
        return [x for x in requested if x in known]

    def list_issues(self) -> List[Dict[str, Any]]:
        cmd = (
            f"gh issue list --repo {self.repo} --state all --limit {self.max_issues} "
            "--json number,title,body,state,labels,updatedAt,url"
        )
        res = self._run(cmd)
        if res["returncode"] != 0:
            raise RuntimeError(f"Failed to list GitHub issues: {res.get('stderr','').strip()}")
        payload = json.loads(res.get("stdout") or "[]")
        out: List[Dict[str, Any]] = []
        for it in payload:
            body = it.get("body") or ""
            meta = parse_guardian_meta(body)
            out.append(
                {
                    "id": str(it.get("number")),
                    "number": int(it.get("number")),
                    "title": it.get("title") or "",
                    "body": body,
                    "state": str(it.get("state") or "").lower(),
                    "labels": [x.get("name") for x in (it.get("labels") or []) if x.get("name")],
                    "updated_at": it.get("updatedAt") or "",
                    "url": it.get("url") or "",
                    "fingerprint": meta.get("fingerprint", ""),
                    "type": meta.get("type", ""),
                    "severity": meta.get("severity", ""),
                    "component": meta.get("component", ""),
                }
            )
        return out

    def create_issue(self, candidate: Dict[str, Any], dry_run: bool) -> Dict[str, Any]:
        if dry_run:
            return {
                "id": "DRY-RUN",
                "number": -1,
                "title": candidate.get("title", ""),
                "state": "open",
                "labels": candidate.get("labels", []),
                "url": "",
                "fingerprint": candidate.get("fingerprint", ""),
            }
        body_path = self.workspace_root / ".issue-guardian" / f"tmp-create-{uuid.uuid4().hex}.md"
        body_path.parent.mkdir(parents=True, exist_ok=True)
        body_path.write_text(issue_body_from_candidate(candidate), encoding="utf-8")
        labels = self._ensure_labels([l for l in candidate.get("labels", []) if l])
        label_args = " ".join([f"--label {json.dumps(lbl)}" for lbl in labels])
        cmd = f"gh issue create --repo {self.repo} --title {json.dumps(candidate.get('title',''))} --body-file {json.dumps(str(body_path))} {label_args}".strip()
        res = self._run(cmd)
        if res["returncode"] != 0 and self._is_missing_label_error(res.get("stderr", "")):
            # Rare edge case where label cache drifted between ensure/create.
            # Retry without labels instead of failing the lifecycle run.
            cmd_retry = f"gh issue create --repo {self.repo} --title {json.dumps(candidate.get('title',''))} --body-file {json.dumps(str(body_path))}"
            res = self._run(cmd_retry)
            if res["returncode"] == 0:
                labels = []
        try:
            body_path.unlink(missing_ok=True)
        except Exception:
            pass
        if res["returncode"] != 0:
            raise RuntimeError(f"Failed to create GitHub issue: {res.get('stderr','').strip()}")
        url = (res.get("stdout") or "").strip().splitlines()[-1].strip()
        num_match = re.search(r"/(\d+)$", url)
        number = int(num_match.group(1)) if num_match else -1
        return {
            "id": str(number),
            "number": number,
            "title": candidate.get("title", ""),
            "state": "open",
            "labels": labels,
            "url": url,
            "fingerprint": candidate.get("fingerprint", ""),
            "type": candidate.get("type", ""),
            "severity": candidate.get("severity", ""),
            "component": candidate.get("component", ""),
        }

    def comment_issue(self, issue: Dict[str, Any], comment: str, dry_run: bool) -> None:
        if dry_run:
            return
        cmd = f"gh issue comment {issue.get('number')} --repo {self.repo} --body {json.dumps(comment)}"
        res = self._run(cmd)
        if res["returncode"] != 0:
            raise RuntimeError(f"Failed to comment issue #{issue.get('number')}: {res.get('stderr','').strip()}")

    def add_labels(self, issue: Dict[str, Any], labels: List[str], dry_run: bool) -> None:
        labels = self._ensure_labels([x for x in labels if x])
        if not labels or dry_run:
            return
        joined = ",".join(labels)
        cmd = f"gh issue edit {issue.get('number')} --repo {self.repo} --add-label {json.dumps(joined)}"
        res = self._run(cmd)
        if res["returncode"] != 0:
            # Label taxonomies vary heavily across repos; non-fatal by design.
            return

    def close_issue(self, issue: Dict[str, Any], comment: str, dry_run: bool) -> None:
        if dry_run:
            return
        cmd = f"gh issue close {issue.get('number')} --repo {self.repo} --comment {json.dumps(comment)}"
        res = self._run(cmd)
        if res["returncode"] != 0:
            raise RuntimeError(f"Failed to close issue #{issue.get('number')}: {res.get('stderr','').strip()}")

    def reopen_issue(self, issue: Dict[str, Any], comment: str, dry_run: bool) -> None:
        if dry_run:
            return
        cmd = f"gh issue reopen {issue.get('number')} --repo {self.repo}"
        res = self._run(cmd)
        if res["returncode"] != 0:
            raise RuntimeError(f"Failed to reopen issue #{issue.get('number')}: {res.get('stderr','').strip()}")
        self.comment_issue(issue, comment, dry_run=False)


class LocalTracker(BaseTracker):
    def __init__(self, workspace_root: Path, state_path: Path, issues_md_path: Path):
        self.workspace_root = workspace_root
        self.state_path = state_path
        self.issues_md_path = issues_md_path
        self.state = ensure_state(state_path)

    def _save(self) -> None:
        save_state(self.state_path, self.state)
        rows = issues_markdown_rows(self.state.get("issues", []))
        self.issues_md_path.write_text(rows, encoding="utf-8")

    def list_issues(self) -> List[Dict[str, Any]]:
        return list(self.state.get("issues", []))

    def _next_id(self) -> int:
        nums = []
        for it in self.state.get("issues", []):
            try:
                nums.append(int(it.get("id")))
            except Exception:
                continue
        return (max(nums) + 1) if nums else 1

    def create_issue(self, candidate: Dict[str, Any], dry_run: bool) -> Dict[str, Any]:
        issue = {
            "id": str(self._next_id()),
            "title": candidate.get("title", ""),
            "body": issue_body_from_candidate(candidate),
            "state": "open",
            "labels": candidate.get("labels", []),
            "updated_at": now_iso(),
            "created_at": now_iso(),
            "url": "",
            "fingerprint": candidate.get("fingerprint", ""),
            "type": candidate.get("type", ""),
            "severity": candidate.get("severity", ""),
            "component": candidate.get("component", ""),
            "comments": [],
        }
        if not dry_run:
            self.state.setdefault("issues", []).append(issue)
            self._save()
        return issue

    def comment_issue(self, issue: Dict[str, Any], comment: str, dry_run: bool) -> None:
        if dry_run:
            return
        for it in self.state.get("issues", []):
            if str(it.get("id")) == str(issue.get("id")):
                it.setdefault("comments", []).append({"at": now_iso(), "body": comment})
                it["updated_at"] = now_iso()
                break
        self._save()

    def add_labels(self, issue: Dict[str, Any], labels: List[str], dry_run: bool) -> None:
        if dry_run:
            return
        labels = [l for l in labels if l]
        if not labels:
            return
        for it in self.state.get("issues", []):
            if str(it.get("id")) == str(issue.get("id")):
                merged = sorted(set((it.get("labels") or []) + labels))
                it["labels"] = merged
                it["updated_at"] = now_iso()
                break
        self._save()

    def close_issue(self, issue: Dict[str, Any], comment: str, dry_run: bool) -> None:
        if dry_run:
            return
        for it in self.state.get("issues", []):
            if str(it.get("id")) == str(issue.get("id")):
                it["state"] = "closed"
                it.setdefault("comments", []).append({"at": now_iso(), "body": comment})
                it["updated_at"] = now_iso()
                break
        self._save()

    def reopen_issue(self, issue: Dict[str, Any], comment: str, dry_run: bool) -> None:
        if dry_run:
            return
        for it in self.state.get("issues", []):
            if str(it.get("id")) == str(issue.get("id")):
                it["state"] = "open"
                it.setdefault("comments", []).append({"at": now_iso(), "body": comment})
                it["updated_at"] = now_iso()
                break
        self._save()


def choose_tracker(args: argparse.Namespace, workspace_root: Path, state_path: Path) -> Tuple[str, BaseTracker, Dict[str, Any]]:
    tracker = (args.tracker or "auto").lower()
    info: Dict[str, Any] = {"tracker_requested": tracker}

    repo = args.repo or infer_repo_from_git(workspace_root)
    info["repo"] = repo

    gh_ready = command_exists("gh")
    gh_auth_ok = False
    if gh_ready:
        auth = run_cmd("gh auth status", workspace_root)
        gh_auth_ok = auth["returncode"] == 0
        info["gh_auth_status_returncode"] = auth["returncode"]

    if tracker == "github":
        if not gh_ready or not gh_auth_ok or not repo:
            raise RuntimeError("Tracker github requested, but gh auth/repo inference is unavailable.")
        return "github", GitHubTracker(workspace_root, repo, safe_int(args.max_issues, 200)), info

    if tracker == "local":
        issues_md = workspace_root / DEFAULT_ISSUES_MD
        return "local", LocalTracker(workspace_root, state_path, issues_md), info

    # auto
    if gh_ready and gh_auth_ok and repo:
        return "github", GitHubTracker(workspace_root, repo, safe_int(args.max_issues, 200)), info
    issues_md = workspace_root / DEFAULT_ISSUES_MD
    return "local", LocalTracker(workspace_root, state_path, issues_md), info


def extract_commit_refs_for_issue(issue: Dict[str, Any], git_signal_text: str) -> List[str]:
    issue_id = str(issue.get("id") or issue.get("number") or "")
    if not issue_id:
        return []
    refs: List[str] = []
    patterns = [
        rf"\b(?:fix|fixes|fixed|close|closes|closed|resolve|resolves|resolved)\s+#?{re.escape(issue_id)}\b",
    ]
    for line in (git_signal_text or "").splitlines():
        lowered = line.lower()
        if any(re.search(p, lowered) for p in patterns):
            refs.append(short_line(line, 220))
    return refs


def run_verification(issue: Dict[str, Any], policy: Dict[str, Any], workspace_root: Path) -> Tuple[bool, List[Dict[str, Any]], str]:
    closure = policy.get("closure_policy", {}) or {}
    verify_map = policy.get("verification_map", {}) or {}
    issue_type = (issue.get("type") or "").lower() or "question"
    entry = verify_map.get(issue_type, {}) or {}
    commands = entry.get("commands", []) or []

    if not commands:
        if as_bool(closure.get("allow_close_without_tests"), False):
            return True, [], "no_checks_configured_but_allowed"
        return False, [], "no_verification_checks_configured"

    checks: List[Dict[str, Any]] = []
    all_pass = True
    for cmd in commands:
        result = run_cmd(str(cmd), workspace_root, timeout=safe_int(policy.get("verification_timeout_sec"), 600))
        checks.append(result)
        if result.get("returncode") != 0:
            all_pass = False
    return all_pass, checks, "checks_passed" if all_pass else "checks_failed"


def has_conflicting_signals(issue: Dict[str, Any], signal_texts: List[str], policy: Dict[str, Any]) -> bool:
    closure = policy.get("closure_policy", {}) or {}
    keywords = [str(k).lower() for k in (closure.get("conflict_keywords") or [])]
    if not keywords:
        keywords = ["failed", "error", "exception", "crash"]

    title_terms = [t for t in normalize_title(issue.get("title", "")).split(" ") if len(t) >= 4][:5]
    for raw in signal_texts:
        lower = (raw or "").lower()
        if not any(k in lower for k in keywords):
            continue
        if not title_terms or any(t in lower for t in title_terms):
            return True
    return False


def render_markdown_report(report: Dict[str, Any]) -> str:
    lines: List[str] = []
    lines.append("# Issue Guardian Report")
    lines.append("")
    lines.append(f"- Timestamp: {report.get('timestamp')}")
    lines.append(f"- Mode: `{report.get('mode')}`")
    lines.append(f"- Tracker: `{report.get('tracker')}`")
    lines.append(f"- Dry run: `{report.get('dry_run')}`")
    lines.append(f"- Strict: `{report.get('strict')}`")
    lines.append("")

    summary = report.get("summary", {})
    lines.append("## Summary")
    lines.append("")
    for key in ["issues_open", "issues_closed", "candidates", "opened", "updated", "duplicates", "reopened", "closed", "blocked"]:
        lines.append(f"- {key.replace('_', ' ').title()}: `{summary.get(key, 0)}`")
    lines.append("")

    if report.get("actions"):
        lines.append("## Actions")
        lines.append("")
        for a in report["actions"]:
            lines.append(f"- `{a.get('action')}` issue=`{a.get('issue_id','-')}` reason=`{a.get('reason','')}`")
        lines.append("")

    if report.get("blocked_reasons"):
        lines.append("## Blocked Reasons")
        lines.append("")
        for b in report["blocked_reasons"]:
            lines.append(f"- {b}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def write_report(report: Dict[str, Any], report_json: str, report_md: str) -> None:
    if report_json:
        p = Path(report_json).expanduser()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if report_md:
        p = Path(report_md).expanduser()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(render_markdown_report(report), encoding="utf-8")


def maybe_append_bus_events(bus_path: Optional[str], events: List[Dict[str, Any]], dry_run: bool) -> None:
    if not bus_path or not events or dry_run:
        return
    p = Path(bus_path).expanduser()
    if not p.exists():
        return
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(doc, dict):
            return
        doc.setdefault("events", [])
        for evt in events:
            doc["events"].append(evt)
        doc["updated_at"] = now_iso()
        p.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    except Exception:
        return


def make_event(event_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": str(uuid.uuid4()),
        "type": event_type,
        "time": now_iso(),
        "created_at": now_iso(),
        "source": {"skill_id": "issue-tracker-guardian"},
        "severity": "info",
        "status": "new",
        "payload": payload,
        "tags": ["issues", "guardian"],
    }


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Issue Tracker Guardian 2.0")
    p.add_argument("--mode", choices=["scan", "ingest", "reconcile", "close", "report"], required=True)
    p.add_argument("--repo", default="")
    p.add_argument("--workspace-root", default=".")
    p.add_argument("--tracker", choices=["github", "local", "auto"], default="auto")
    p.add_argument("--input-source", action="append", default=[])
    p.add_argument("--state-file", default=DEFAULT_STATE_REL)
    p.add_argument("--report-json", default="")
    p.add_argument("--report-md", default="")
    p.add_argument("--dry-run", default="false")
    p.add_argument("--strict", default="true")
    p.add_argument("--close-enabled", default="true")
    p.add_argument("--periodic-window-hours", default="24")
    p.add_argument("--message", default="")
    p.add_argument("--title", default="")
    p.add_argument("--body", default="")
    p.add_argument("--evidence", action="append", default=[])
    p.add_argument("--signal-file", action="append", default=[])
    p.add_argument("--bus-path", default="")
    p.add_argument("--max-issues", default="200")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    dry_run = as_bool(args.dry_run, False)
    strict = as_bool(args.strict, True)
    close_enabled = as_bool(args.close_enabled, True)

    skill_root = Path(__file__).resolve().parents[1]
    workspace_root = Path(args.workspace_root).expanduser().resolve()
    state_path = Path(args.state_file).expanduser()
    if not state_path.is_absolute():
        state_path = workspace_root / state_path

    taxonomy = load_taxonomy(skill_root, workspace_root)
    policy = load_policy(skill_root, workspace_root)
    config = load_yaml_or_json(workspace_root / DEFAULT_CONFIG_REL)

    report: Dict[str, Any] = {
        "timestamp": now_iso(),
        "mode": args.mode,
        "dry_run": dry_run,
        "strict": strict,
        "close_enabled": close_enabled,
        "workspace_root": str(workspace_root),
        "state_file": str(state_path),
        "tracker": "",
        "tracker_info": {},
        "actions": [],
        "blocked_reasons": [],
        "events": [],
        "summary": {
            "issues_open": 0,
            "issues_closed": 0,
            "candidates": 0,
            "opened": 0,
            "updated": 0,
            "duplicates": 0,
            "reopened": 0,
            "closed": 0,
            "blocked": 0,
        },
    }

    try:
        tracker_name, tracker, tracker_info = choose_tracker(args, workspace_root, state_path)
        report["tracker"] = tracker_name
        report["tracker_info"] = tracker_info

        all_issues = tracker.list_issues()
        open_issues = [i for i in all_issues if str(i.get("state", "")).lower() == "open"]
        closed_issues = [i for i in all_issues if str(i.get("state", "")).lower() == "closed"]
        report["summary"]["issues_open"] = len(open_issues)
        report["summary"]["issues_closed"] = len(closed_issues)

        signals, signal_meta = collect_signals(args, policy, workspace_root)
        report["signal_meta"] = signal_meta

        candidates: List[Dict[str, Any]] = []
        if args.mode in {"scan", "ingest", "reconcile"}:
            for src, text, ev in split_candidate_texts(signals):
                if not text.strip() and not ev:
                    continue
                c = candidate_from_text(src, text, ev, taxonomy, config=config)
                # ingest mode should prioritize explicit user title/body if provided
                if args.mode == "ingest" and (args.title or args.body):
                    if args.title:
                        c["title"] = short_line(args.title, 90)
                    if args.body:
                        c["summary"] = short_line(args.body, 220)
                candidates.append(c)
            candidates = dedupe_candidates(candidates)
            report["summary"]["candidates"] = len(candidates)

        threshold = float((taxonomy.get("duplicate_policy", {}) or {}).get("fuzzy_title_threshold", 0.86))
        creation_policy = policy.get("creation_policy", {}) or {}
        min_conf = float((creation_policy or {}).get("min_confidence", 0.55))
        min_evidence = safe_int((creation_policy or {}).get("require_min_evidence_items", 1), 1)
        blocked_sources = {
            str(src).strip().lower()
            for src in ((creation_policy or {}).get("blocked_create_sources", ["git"]) or [])
            if str(src).strip()
        }
        max_new_issues_per_run = safe_int((creation_policy or {}).get("max_new_issues_per_run", 3), 3)
        opened_this_run = 0
        reopen_min_conf = float((policy.get("reopen_policy", {}) or {}).get("min_confidence", 0.6))

        if args.mode in {"ingest", "reconcile"}:
            for c in candidates:
                source = str(c.get("source", "")).strip().lower()
                if source in blocked_sources:
                    report["summary"]["blocked"] += 1
                    reason = f"candidate_blocked: source `{source}` is creation-blocked"
                    report["blocked_reasons"].append(reason)
                    report["actions"].append({"action": "blocked", "issue_id": "", "reason": reason})
                    report["events"].append(make_event("issue:action_blocked", {"reason": reason, "fingerprint": c.get("fingerprint")}))
                    continue

                if is_progress_update_candidate(c, policy):
                    report["summary"]["blocked"] += 1
                    reason = f"candidate_blocked: non-issue progress/update signal for `{c.get('title')}`"
                    report["blocked_reasons"].append(reason)
                    report["actions"].append({"action": "blocked", "issue_id": "", "reason": reason})
                    report["events"].append(make_event("issue:action_blocked", {"reason": reason, "fingerprint": c.get("fingerprint")}))
                    continue

                match, relation, reason = match_existing_issue(c, open_issues, closed_issues, threshold)

                if relation == "duplicate_open" and match is not None:
                    comment = lifecycle_comment("duplicate", c, reason or "matched existing open issue")
                    tracker.comment_issue(match, comment, dry_run=dry_run)
                    tracker.add_labels(match, c.get("labels", []), dry_run=dry_run)
                    report["summary"]["duplicates"] += 1
                    report["summary"]["updated"] += 1
                    report["actions"].append({"action": "duplicate_update", "issue_id": match.get("id"), "reason": reason})
                    report["events"].append(make_event("issue:duplicate_detected", {"issue_id": match.get("id"), "reason": reason, "fingerprint": c.get("fingerprint")}))
                    continue

                if relation == "reopen_candidate" and match is not None:
                    if c.get("source") == "git":
                        report["summary"]["blocked"] += 1
                        reason_git = f"reopen_blocked:{match.get('id')}:git_only_signal"
                        report["blocked_reasons"].append(reason_git)
                        report["actions"].append({"action": "blocked_reopen", "issue_id": match.get("id"), "reason": reason_git})
                        report["events"].append(make_event("issue:action_blocked", {"issue_id": match.get("id"), "reason": "git-only signal not sufficient to reopen"}))
                        continue
                    if c.get("confidence", 0.0) >= reopen_min_conf and as_bool((policy.get("reopen_policy", {}) or {}).get("enabled"), True):
                        comment = lifecycle_comment("reopened", c, reason or "closed issue fingerprint resurfaced")
                        tracker.reopen_issue(match, comment, dry_run=dry_run)
                        tracker.add_labels(match, c.get("labels", []), dry_run=dry_run)
                        report["summary"]["reopened"] += 1
                        report["actions"].append({"action": "reopen", "issue_id": match.get("id"), "reason": reason})
                        report["events"].append(make_event("issue:updated", {"issue_id": match.get("id"), "action": "reopened"}))
                        continue

                if c.get("confidence", 0.0) < min_conf or len(c.get("evidence", [])) < min_evidence:
                    report["summary"]["blocked"] += 1
                    block_reason = f"candidate_blocked: confidence/evidence below threshold for `{c.get('title')}`"
                    report["blocked_reasons"].append(block_reason)
                    report["actions"].append({"action": "blocked", "issue_id": "", "reason": block_reason})
                    report["events"].append(make_event("issue:action_blocked", {"reason": block_reason, "fingerprint": c.get("fingerprint")}))
                    continue

                if opened_this_run >= max_new_issues_per_run:
                    report["summary"]["blocked"] += 1
                    block_reason = f"candidate_blocked: run open-limit reached ({max_new_issues_per_run})"
                    report["blocked_reasons"].append(block_reason)
                    report["actions"].append({"action": "blocked", "issue_id": "", "reason": block_reason})
                    report["events"].append(make_event("issue:action_blocked", {"reason": block_reason, "fingerprint": c.get("fingerprint")}))
                    continue

                created = tracker.create_issue(c, dry_run=dry_run)
                report["summary"]["opened"] += 1
                opened_this_run += 1
                report["actions"].append({"action": "opened", "issue_id": created.get("id"), "reason": "new candidate"})
                report["events"].append(make_event("issue:opened", {"issue_id": created.get("id"), "fingerprint": c.get("fingerprint")}))

        if args.mode in {"close", "reconcile"} and close_enabled:
            # Refresh issue list after potential create/reopen operations.
            all_issues = tracker.list_issues()
            open_issues = [i for i in all_issues if str(i.get("state", "")).lower() == "open"]
            signal_texts = [s.get("text", "") for s in signals]
            git_text = "\n\n".join(s.get("text", "") for s in signals if s.get("source") == "git")

            for issue in open_issues:
                refs = extract_commit_refs_for_issue(issue, git_text)
                if refs:
                    report["events"].append(make_event("issue:resolution_candidate", {"issue_id": issue.get("id"), "refs": refs[:3]}))

                closure = policy.get("closure_policy", {}) or {}
                if as_bool(closure.get("require_linked_fix"), True) and not refs:
                    report["summary"]["blocked"] += 1
                    reason = f"close_blocked:{issue.get('id')}:missing_linked_fix"
                    report["blocked_reasons"].append(reason)
                    report["actions"].append({"action": "blocked_close", "issue_id": issue.get("id"), "reason": reason})
                    report["events"].append(make_event("issue:action_blocked", {"issue_id": issue.get("id"), "reason": "missing linked fix"}))
                    continue

                checks_passed, checks, checks_reason = run_verification(issue, policy, workspace_root)
                if as_bool(closure.get("require_verification_checks"), True) and not checks_passed:
                    report["summary"]["blocked"] += 1
                    reason = f"close_blocked:{issue.get('id')}:{checks_reason}"
                    report["blocked_reasons"].append(reason)
                    report["actions"].append({"action": "blocked_close", "issue_id": issue.get("id"), "reason": reason})
                    report["events"].append(make_event("issue:action_blocked", {"issue_id": issue.get("id"), "reason": checks_reason}))
                    continue

                conflicting = has_conflicting_signals(issue, signal_texts, policy)
                if conflicting:
                    report["summary"]["blocked"] += 1
                    reason = f"close_blocked:{issue.get('id')}:conflicting_fresh_signals"
                    report["blocked_reasons"].append(reason)
                    report["actions"].append({"action": "blocked_close", "issue_id": issue.get("id"), "reason": reason})
                    report["events"].append(make_event("issue:action_blocked", {"issue_id": issue.get("id"), "reason": "conflicting fresh signals"}))
                    continue

                required_fields = [str(x).strip().lower() for x in (closure.get("required_evidence_fields") or []) if str(x).strip()]
                if required_fields:
                    field_values = {
                        "linked_fix": bool(refs),
                        "verification_checks": bool(checks_passed),
                        "no_conflicts": not conflicting,
                    }
                    missing = [f for f in required_fields if not field_values.get(f, False)]
                    if missing:
                        report["summary"]["blocked"] += 1
                        reason = f"close_blocked:{issue.get('id')}:missing_required_fields:{','.join(missing)}"
                        report["blocked_reasons"].append(reason)
                        report["actions"].append({"action": "blocked_close", "issue_id": issue.get("id"), "reason": reason})
                        report["events"].append(make_event("issue:action_blocked", {"issue_id": issue.get("id"), "reason": reason}))
                        continue

                candidate_stub = {
                    "confidence": 1.0,
                    "fingerprint": issue.get("fingerprint", ""),
                    "evidence": refs,
                }
                comment = lifecycle_comment("closed", candidate_stub, "closure gate passed", checks=checks)
                tracker.close_issue(issue, comment, dry_run=dry_run)
                report["summary"]["closed"] += 1
                report["actions"].append({"action": "closed", "issue_id": issue.get("id"), "reason": "closure gate passed"})
                report["events"].append(make_event("issue:closed", {"issue_id": issue.get("id"), "reason": "closure gate passed"}))

        if args.mode == "scan":
            # Read-only analysis mode: no tracker mutation.
            report["actions"].append({"action": "scan_complete", "issue_id": "", "reason": "analysis only"})

        if args.mode == "report":
            report["actions"].append({"action": "report_generated", "issue_id": "", "reason": "state snapshot"})

        maybe_append_bus_events(args.bus_path or "", report.get("events", []), dry_run=dry_run)
        write_report(report, args.report_json, args.report_md)
        print(json.dumps({"ok": True, "mode": args.mode, "tracker": report["tracker"], "summary": report["summary"]}))

        if strict and report["summary"].get("blocked", 0) > 0:
            return 2
        return 0

    except Exception as exc:  # noqa: BLE001
        report["error"] = str(exc)
        write_report(report, args.report_json, args.report_md)
        print(json.dumps({"ok": False, "error": str(exc)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
