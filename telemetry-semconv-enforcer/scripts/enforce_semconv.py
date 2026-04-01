#!/usr/bin/env python3
"""Telemetry semantic convention conformance checker."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover
    yaml = None

KEY_PATTERN = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z0-9_]+)+$")


DEFAULT_RESOURCE_ATTRS = ["service.name", "service.version"]
DEFAULT_TRACE_ATTRS = [
    "trace.id",
    "span.id",
    "span.kind",
    "quantum.provider",
    "quantum.backend",
]
DEFAULT_METRIC_ATTRS = ["metric.name", "metric.unit", "quantum.shots"]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_yaml_or_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    text = path.read_text().strip()
    if not text:
        return {}

    if path.suffix.lower() == ".json":
        value = json.loads(text)
        return value if isinstance(value, dict) else {}

    if yaml is not None:
        value = yaml.safe_load(text)
        return value if isinstance(value, dict) else {}

    value = json.loads(text)
    return value if isinstance(value, dict) else {}


def _read_samples(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []

    text = path.read_text().strip()
    if not text:
        return []

    if path.suffix.lower() == ".json":
        payload = json.loads(text)
        if isinstance(payload, dict):
            return [payload]
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        return []

    rows: list[dict[str, Any]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        item = json.loads(line)
        if isinstance(item, dict):
            rows.append(item)
    return rows


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _write_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if yaml is not None:
        path.write_text(yaml.safe_dump(payload, sort_keys=True))
        return
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _required_profile(profile: dict[str, Any]) -> dict[str, Any]:
    quantum_required = bool(profile.get("quantum_required", True))

    resource_attrs = list(profile.get("resource_attrs", DEFAULT_RESOURCE_ATTRS))
    trace_attrs = list(profile.get("trace_attrs", DEFAULT_TRACE_ATTRS if quantum_required else ["trace.id", "span.id", "span.kind"]))
    metric_attrs = list(profile.get("metric_attrs", DEFAULT_METRIC_ATTRS if quantum_required else ["metric.name", "metric.unit"]))

    return {
        "schema": "TelemetryProfileV1",
        "resource_attrs": resource_attrs,
        "trace_attrs": trace_attrs,
        "metric_attrs": metric_attrs,
        "key_pattern": str(profile.get("key_pattern", KEY_PATTERN.pattern)),
        "quantum_required": quantum_required,
        "redact_job_ids": bool(profile.get("redact_job_ids", True)),
        "generated_at": _utc_now(),
    }


def _job_id_is_redacted(value: Any) -> bool:
    text = str(value)
    if text.startswith("redacted:"):
        return True
    if text.startswith("hash:"):
        return True
    if text in {"***", "<redacted>", "[redacted]"}:
        return True
    return False


def evaluate(profile: dict[str, Any], samples: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any]]:
    normalized_profile = _required_profile(profile)
    required_resource = [str(x) for x in normalized_profile["resource_attrs"]]
    required_trace = [str(x) for x in normalized_profile["trace_attrs"]]
    required_metric = [str(x) for x in normalized_profile["metric_attrs"]]
    pattern = re.compile(normalized_profile["key_pattern"])

    violations: list[str] = []
    raw_job_id_count = 0

    for index, sample in enumerate(samples):
        resource_attrs = sample.get("resource_attrs", {})
        trace_attrs = sample.get("trace_attrs", {})
        metric_attrs = sample.get("metric_attrs", {})

        if not isinstance(resource_attrs, dict):
            resource_attrs = {}
        if not isinstance(trace_attrs, dict):
            trace_attrs = {}
        if not isinstance(metric_attrs, dict):
            metric_attrs = {}

        for key in required_resource:
            if key not in resource_attrs:
                violations.append(f"sample[{index}] missing resource_attr: {key}")
        for key in required_trace:
            if key not in trace_attrs:
                violations.append(f"sample[{index}] missing trace_attr: {key}")
        for key in required_metric:
            if key not in metric_attrs:
                violations.append(f"sample[{index}] missing metric_attr: {key}")

        for space_name, attrs in (
            ("resource", resource_attrs),
            ("trace", trace_attrs),
            ("metric", metric_attrs),
        ):
            for key in attrs.keys():
                if not pattern.match(str(key)):
                    violations.append(f"sample[{index}] invalid {space_name} key format: {key}")

        if normalized_profile["redact_job_ids"]:
            if "quantum.job_id" in trace_attrs and not _job_id_is_redacted(trace_attrs.get("quantum.job_id")):
                raw_job_id_count += 1
                violations.append(f"sample[{index}] raw quantum.job_id must be redacted")

    conformance = {
        "schema": "TelemetryConformanceV1",
        "resource_attrs": required_resource,
        "trace_attrs": required_trace,
        "metric_attrs": required_metric,
        "violations": violations,
        "pass": len(violations) == 0,
        "checked_at": _utc_now(),
        "sample_count": len(samples),
        "redaction_policy": {
            "quantum_job_id_redaction_required": bool(normalized_profile["redact_job_ids"]),
            "raw_job_id_violations": raw_job_id_count,
        },
    }

    return normalized_profile, conformance


def _run_self_test() -> None:
    profile = {
        "resource_attrs": ["service.name", "service.version"],
        "trace_attrs": ["trace.id", "span.id", "quantum.provider", "quantum.backend"],
        "metric_attrs": ["metric.name", "metric.unit", "quantum.shots"],
        "redact_job_ids": True,
    }
    samples = [
        {
            "resource_attrs": {"service.name": "demo", "service.version": "1.0"},
            "trace_attrs": {
                "trace.id": "t-1",
                "span.id": "s-1",
                "quantum.provider": "ibm",
                "quantum.backend": "ibm_torino",
                "quantum.job_id": "raw_job_123",
            },
            "metric_attrs": {"metric.name": "latency", "metric.unit": "ms", "quantum.shots": 512},
        }
    ]
    _, report = evaluate(profile, samples)
    assert report["pass"] is False
    assert any("raw quantum.job_id" in v for v in report["violations"])


def main() -> None:
    parser = argparse.ArgumentParser(description="Enforce telemetry semantic conventions")
    parser.add_argument("--profile", type=Path, help="Path to telemetry profile YAML/JSON")
    parser.add_argument("--samples", type=Path, help="Path to telemetry samples JSON/JSONL")
    parser.add_argument("--out-dir", type=Path, default=Path("."), help="Output directory")
    parser.add_argument("--self-test", action="store_true", help="Run built-in tests")
    args = parser.parse_args()

    if args.self_test:
        _run_self_test()
        print("self-test passed")
        return

    if not args.samples:
        raise SystemExit("--samples is required unless --self-test is used")

    profile_input = _read_yaml_or_json(args.profile) if args.profile else {}
    samples = _read_samples(args.samples)

    normalized_profile, conformance = evaluate(profile_input, samples)
    _write_yaml(args.out_dir / "telemetry_profile.yaml", normalized_profile)
    _write_json(args.out_dir / "telemetry_conformance.json", conformance)
    print(str(args.out_dir.resolve()))


if __name__ == "__main__":
    main()
