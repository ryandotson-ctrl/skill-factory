#!/usr/bin/env python3
"""Append-only wisdom archival, digest generation, and retrieval scoring."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
PHONE_PATTERN = re.compile(r"\b(?:\+?\d[\d\-\s().]{7,}\d)\b")
SECRET_PATTERN = re.compile(
    r"(?i)\b(api[_-]?key|access[_-]?token|secret|password|passwd|bearer)\b\s*[:=]\s*([^\s,;]+)"
)

STOP_WORDS = {
    "the",
    "and",
    "for",
    "that",
    "this",
    "with",
    "from",
    "have",
    "will",
    "would",
    "could",
    "should",
    "your",
    "into",
    "about",
    "when",
    "where",
    "what",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_iso(text: str) -> Optional[datetime]:
    value = str(text or "").strip()
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        return None


def sanitize_text(text: str, workspace_root: Path) -> str:
    out = str(text or "")
    try:
        out = out.replace(str(workspace_root.resolve()), "<workspace>")
    except Exception:
        pass
    out = out.replace(str(Path.home()), "<home>")
    out = re.sub(r"/Users/[^/\s]+", "/Users/<user>", out)
    out = EMAIL_PATTERN.sub("<redacted_email>", out)
    out = PHONE_PATTERN.sub("<redacted_phone>", out)
    out = SECRET_PATTERN.sub(lambda m: f"{m.group(1)}=<redacted_secret>", out)
    out = re.sub(r"\b(?:sk|rk|pk)_[A-Za-z0-9]{8,}\b", "<redacted_token>", out)
    out = re.sub(r"\s+", " ", out).strip()
    return out


def sanitize_obj(value: Any, workspace_root: Path) -> Any:
    if isinstance(value, dict):
        return {sanitize_text(str(k), workspace_root): sanitize_obj(v, workspace_root) for k, v in value.items()}
    if isinstance(value, list):
        return [sanitize_obj(item, workspace_root) for item in value]
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return sanitize_text(str(value), workspace_root)


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def fingerprint_entry(entry: Dict[str, Any]) -> str:
    body = dict(entry)
    body.pop("entry_id", None)
    body.pop("created_at", None)
    digest = hashlib.sha256(canonical_json(body).encode("utf-8")).hexdigest()
    return digest


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    entries: List[Dict[str, Any]] = []
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            parsed = json.loads(raw)
        except Exception:
            continue
        if isinstance(parsed, dict):
            entries.append(parsed)
    return entries


def append_entry(ledger: Path, entry_payload: Dict[str, Any], workspace_root: Path, dedupe: bool) -> Dict[str, Any]:
    ensure_parent(ledger)
    sanitized = sanitize_obj(entry_payload, workspace_root)
    if not isinstance(sanitized, dict):
        sanitized = {"summary": str(sanitized)}

    sanitized.setdefault("created_at", now_iso())
    fingerprint = fingerprint_entry(sanitized)
    sanitized["_fingerprint"] = fingerprint
    sanitized.setdefault("entry_id", fingerprint[:16])

    existing = load_jsonl(ledger)
    if dedupe:
        for item in existing:
            if item.get("_fingerprint") == fingerprint:
                return {
                    "status": "duplicate_skipped",
                    "entry_id": item.get("entry_id", ""),
                    "fingerprint": fingerprint,
                    "ledger": str(ledger),
                }

    with ledger.open("a", encoding="utf-8") as handle:
        handle.write(canonical_json(sanitized))
        handle.write("\n")

    return {
        "status": "appended",
        "entry_id": sanitized.get("entry_id", ""),
        "fingerprint": fingerprint,
        "ledger": str(ledger),
    }


def compact(text: str, limit: int = 160) -> str:
    clean = re.sub(r"\s+", " ", str(text or "")).strip()
    if len(clean) <= limit:
        return clean
    return clean[: limit - 3].rstrip() + "..."


def build_digest(ledger: Path, digest_path: Path, limit: int = 25) -> Dict[str, Any]:
    entries = load_jsonl(ledger)
    selected = list(reversed(entries[-max(1, limit) :]))
    ensure_parent(digest_path)

    lines = ["# Wisdom Digest", ""]
    if not selected:
        lines.append("_No entries found._")
    else:
        for entry in selected:
            created = str(entry.get("created_at", ""))
            summary = compact(str(entry.get("summary", "")) or canonical_json(entry), limit=220)
            entry_id = str(entry.get("entry_id", ""))
            lines.append(f"- `{created}` `{entry_id}` {summary}")

    digest_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {
        "status": "written",
        "digest": str(digest_path),
        "entries": len(selected),
    }


def tokenize(text: str) -> List[str]:
    tokens = re.findall(r"[a-z0-9][a-z0-9_\-:.]{2,}", str(text or "").lower())
    out: List[str] = []
    seen: set[str] = set()
    for token in tokens:
        norm = token.strip("._:-")
        if len(norm) < 3 or norm in STOP_WORDS or norm in seen:
            continue
        seen.add(norm)
        out.append(norm)
    return out


def score_entries(
    ledger: Path,
    query: str,
    *,
    limit: int = 10,
    recency_window_hours: int = 168,
) -> Dict[str, Any]:
    entries = load_jsonl(ledger)
    query_terms = set(tokenize(query))
    now = datetime.now(timezone.utc)
    window = max(1, recency_window_hours)
    scored: List[Dict[str, Any]] = []

    for entry in entries:
        blob = canonical_json(entry)
        terms = set(tokenize(blob))
        overlap = 0.0
        if query_terms and terms:
            overlap = len(query_terms.intersection(terms)) / float(len(query_terms.union(terms)))

        created = parse_iso(str(entry.get("created_at", "")))
        recency = 0.0
        if created is not None:
            age_hours = max(0.0, (now - created).total_seconds() / 3600.0)
            recency = max(0.0, 1.0 - (age_hours / float(window)))

        confidence = float(entry.get("confidence", 0.0) or 0.0)
        score = round(0.6 * overlap + 0.25 * recency + 0.15 * confidence, 6)

        scored.append(
            {
                "entry_id": entry.get("entry_id", ""),
                "created_at": entry.get("created_at", ""),
                "summary": compact(str(entry.get("summary", "")) or blob, limit=180),
                "score": score,
                "overlap": round(overlap, 6),
                "recency": round(recency, 6),
            }
        )

    scored.sort(key=lambda item: item.get("score", 0.0), reverse=True)
    return {"status": "ok", "query": query, "results": scored[: max(1, limit)]}


def load_entry_from_args(args: argparse.Namespace) -> Dict[str, Any]:
    if args.entry_json:
        raw = Path(args.entry_json).read_text(encoding="utf-8", errors="replace")
    elif args.entry_inline:
        raw = args.entry_inline
    else:
        raw = "{}"
    parsed = json.loads(raw)
    if isinstance(parsed, dict):
        return parsed
    return {"summary": str(parsed)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Wisdom archival and scoring utility.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    append_p = sub.add_parser("append", help="Append sanitized wisdom entry to JSONL ledger.")
    append_p.add_argument("--ledger", required=True)
    append_p.add_argument("--entry-json", default="")
    append_p.add_argument("--entry-inline", default="")
    append_p.add_argument("--workspace-root", default=str(Path.cwd()))
    append_p.add_argument("--no-dedupe", action="store_true")

    digest_p = sub.add_parser("digest", help="Build markdown digest from ledger.")
    digest_p.add_argument("--ledger", required=True)
    digest_p.add_argument("--digest", required=True)
    digest_p.add_argument("--limit", type=int, default=25)

    score_p = sub.add_parser("score", help="Score ledger entries for a query.")
    score_p.add_argument("--ledger", required=True)
    score_p.add_argument("--query", required=True)
    score_p.add_argument("--limit", type=int, default=10)
    score_p.add_argument("--recency-window-hours", type=int, default=168)

    args = parser.parse_args()

    if args.cmd == "append":
        payload = load_entry_from_args(args)
        result = append_entry(
            ledger=Path(args.ledger),
            entry_payload=payload,
            workspace_root=Path(args.workspace_root),
            dedupe=not bool(args.no_dedupe),
        )
        print(json.dumps(result, ensure_ascii=True, sort_keys=True))
        return

    if args.cmd == "digest":
        result = build_digest(
            ledger=Path(args.ledger),
            digest_path=Path(args.digest),
            limit=max(1, int(args.limit)),
        )
        print(json.dumps(result, ensure_ascii=True, sort_keys=True))
        return

    result = score_entries(
        ledger=Path(args.ledger),
        query=str(args.query),
        limit=max(1, int(args.limit)),
        recency_window_hours=max(1, int(args.recency_window_hours)),
    )
    print(json.dumps(result, ensure_ascii=True, sort_keys=True))


if __name__ == "__main__":
    main()
