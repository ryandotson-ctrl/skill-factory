#!/usr/bin/env python3
"""Portable eval flywheel with threshold, regression, and gradient gates."""

from __future__ import annotations

import argparse
import json
import math
import statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover
    yaml = None


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        item = json.loads(line)
        if isinstance(item, dict):
            rows.append(item)
    return rows


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


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(row, sort_keys=True, separators=(",", ":")) for row in rows]
    path.write_text("\n".join(lines) + ("\n" if lines else ""))


def _write_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if yaml is not None:
        path.write_text(yaml.safe_dump(payload, sort_keys=True))
        return
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _confidence_interval(samples: list[float], z: float = 1.96) -> tuple[float, float]:
    if not samples:
        return (0.0, 0.0)
    mean = float(statistics.mean(samples))
    if len(samples) < 2:
        return (mean, 0.0)
    stdev = float(statistics.stdev(samples))
    return (mean, z * (stdev / math.sqrt(len(samples))))


def _classify_frontier(
    *,
    speed_gain_pct: float | None,
    quality_drop_pct: float | None,
    near_miss_floor_pct: float,
    speed_gate_min_pct: float,
    quality_gate_max_drop_pct: float,
) -> str:
    if speed_gain_pct is None or quality_drop_pct is None:
        return "unknown_frontier"
    if quality_drop_pct > quality_gate_max_drop_pct:
        return "quality_risk_frontier"
    if speed_gain_pct >= speed_gate_min_pct:
        return "success_frontier"
    if near_miss_floor_pct <= speed_gain_pct < speed_gate_min_pct:
        return "near_miss_frontier"
    return "below_frontier"


def evaluate(
    dataset_rows: list[dict[str, Any]],
    grader_spec: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    normalized_spec = {
        "schema": "GraderSpecV1",
        "grader_id": str(grader_spec.get("grader_id", "default-grader")),
        "threshold": float(grader_spec.get("threshold", 0.0) or 0.0),
        "max_regression_drop": float(grader_spec.get("max_regression_drop", 0.0) or 0.0),
        "gradient_abs_tol": float(grader_spec.get("gradient_abs_tol", 0.0) or 0.0),
        "gradient_rel_tol": float(grader_spec.get("gradient_rel_tol", 0.0) or 0.0),
        "confidence_z": float(grader_spec.get("confidence_z", 1.96) or 1.96),
        "near_miss_floor_pct": float(grader_spec.get("near_miss_floor_pct", 8.0) or 8.0),
        "speed_gate_min_gain_pct": float(grader_spec.get("speed_gate_min_gain_pct", 10.0) or 10.0),
        "quality_gate_max_drop_pct": float(grader_spec.get("quality_gate_max_drop_pct", 2.0) or 2.0),
        "generated_at": _utc_now(),
    }

    normalized_rows: list[dict[str, Any]] = []
    stochastic_means: list[float] = []

    for index, row in enumerate(dataset_rows):
        dataset_id = str(row.get("dataset_id", f"row-{index:06d}"))
        score = float(row.get("score", row.get("actual_score", 0.0)) or 0.0)
        baseline_score = float(row.get("baseline_score", score) or score)
        threshold = float(row.get("threshold", normalized_spec["threshold"]) or normalized_spec["threshold"])
        regression_delta = score - baseline_score

        gradient_abs_err = float(row.get("gradient_abs_err", 0.0) or 0.0)
        gradient_rel_err_raw = row.get("gradient_rel_err")
        gradient_rel_err = None if gradient_rel_err_raw is None else float(gradient_rel_err_raw or 0.0)
        gradient_abs_tol = float(row.get("gradient_abs_tol", normalized_spec["gradient_abs_tol"]) or normalized_spec["gradient_abs_tol"])
        gradient_rel_tol = float(row.get("gradient_rel_tol", normalized_spec["gradient_rel_tol"]) or normalized_spec["gradient_rel_tol"])

        gradient_present = any(key in row for key in ("gradient_abs_err", "gradient_rel_err"))
        gradient_pass = True
        if gradient_present:
            abs_ok = gradient_abs_err <= gradient_abs_tol
            rel_ok = (
                gradient_rel_err is not None
                and gradient_rel_tol > 0
                and gradient_rel_err <= gradient_rel_tol
            )
            gradient_pass = abs_ok or rel_ok

        stochastic_samples = row.get("stochastic_samples", [])
        row_stochastic_mean = None
        row_stochastic_ci = None
        if isinstance(stochastic_samples, list) and stochastic_samples:
            sample_values = [float(value) for value in stochastic_samples]
            row_stochastic_mean, row_stochastic_ci = _confidence_interval(sample_values, normalized_spec["confidence_z"])
            stochastic_means.append(row_stochastic_mean)

        speed_gain_raw = row.get("speed_gain_pct")
        quality_drop_raw = row.get("quality_drop_pct")
        speed_gain_pct = None if speed_gain_raw is None else float(speed_gain_raw or 0.0)
        quality_drop_pct = None if quality_drop_raw is None else float(quality_drop_raw or 0.0)
        frontier_class = _classify_frontier(
            speed_gain_pct=speed_gain_pct,
            quality_drop_pct=quality_drop_pct,
            near_miss_floor_pct=normalized_spec["near_miss_floor_pct"],
            speed_gate_min_pct=normalized_spec["speed_gate_min_gain_pct"],
            quality_gate_max_drop_pct=normalized_spec["quality_gate_max_drop_pct"],
        )

        score_pass = score >= threshold
        regression_pass = regression_delta >= -normalized_spec["max_regression_drop"]
        passes = score_pass and regression_pass and gradient_pass

        normalized_rows.append(
            {
                "schema": "EvalResultV1",
                "dataset_id": dataset_id,
                "grader_id": normalized_spec["grader_id"],
                "score": score,
                "threshold": threshold,
                "regression_delta": regression_delta,
                "pass": passes,
                "score_pass": score_pass,
                "regression_pass": regression_pass,
                "gradient_pass": gradient_pass,
                "gradient_abs_err": gradient_abs_err,
                "gradient_rel_err": gradient_rel_err,
                "gradient_abs_tol": gradient_abs_tol,
                "gradient_rel_tol": gradient_rel_tol,
                "speed_gain_pct": speed_gain_pct,
                "quality_drop_pct": quality_drop_pct,
                "frontier_class": frontier_class,
                "stochastic_mean": row_stochastic_mean,
                "stochastic_ci_half_width": row_stochastic_ci,
            }
        )

    count = len(normalized_rows)
    avg_score = sum(row["score"] for row in normalized_rows) / count if count else 0.0
    pass_count = sum(1 for row in normalized_rows if row["pass"])
    regression_failures = sum(
        1
        for row in normalized_rows
        if row["regression_delta"] < -normalized_spec["max_regression_drop"]
    )
    gradient_failures = sum(1 for row in normalized_rows if not row["gradient_pass"])

    stochastic_mean, stochastic_ci = _confidence_interval(stochastic_means, normalized_spec["confidence_z"])
    frontier_counts: dict[str, int] = {}
    for row in normalized_rows:
        key = str(row.get("frontier_class", "unknown_frontier"))
        frontier_counts[key] = frontier_counts.get(key, 0) + 1
    dominant_frontier_class = "unknown_frontier"
    if frontier_counts:
        dominant_frontier_class = sorted(frontier_counts.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
    frontier_sequence = [str(row.get("frontier_class", "unknown_frontier")) for row in normalized_rows]

    summary = {
        "schema": "EvalSummaryV1",
        "generated_at": _utc_now(),
        "grader_id": normalized_spec["grader_id"],
        "count": count,
        "avg_score": avg_score,
        "pass_count": pass_count,
        "pass_rate": (pass_count / count) if count else 0.0,
        "regression_failures": regression_failures,
        "gradient_failures": gradient_failures,
        "stochastic_mean": stochastic_mean,
        "stochastic_ci_half_width": stochastic_ci,
        "frontier_diagnostics": {
            "near_miss_floor_pct": normalized_spec["near_miss_floor_pct"],
            "speed_gate_min_gain_pct": normalized_spec["speed_gate_min_gain_pct"],
            "quality_gate_max_drop_pct": normalized_spec["quality_gate_max_drop_pct"],
            "counts": frontier_counts,
            "dominant_frontier_class": dominant_frontier_class,
            "first_frontier_class": frontier_sequence[0] if frontier_sequence else "unknown_frontier",
            "last_frontier_class": frontier_sequence[-1] if frontier_sequence else "unknown_frontier",
        },
        "overall_pass": pass_count == count,
    }

    return normalized_rows, normalized_spec, summary


def _run_self_test() -> None:
    dataset = [
        {
            "dataset_id": "d1",
            "score": 0.79,
            "baseline_score": 0.85,
            "threshold": 0.8,
            "gradient_abs_err": 0.03,
            "gradient_abs_tol": 0.01,
            "speed_gain_pct": 8.7,
            "quality_drop_pct": 1.0,
            "stochastic_samples": [0.74, 0.75, 0.76],
        },
        {
            "dataset_id": "d2",
            "score": 0.92,
            "baseline_score": 0.91,
            "threshold": 0.8,
            "gradient_abs_err": 0.001,
            "gradient_abs_tol": 0.01,
            "speed_gain_pct": 10.2,
            "quality_drop_pct": 0.4,
            "stochastic_samples": [0.91, 0.92, 0.93],
        },
    ]
    spec = {
        "grader_id": "g1",
        "threshold": 0.8,
        "max_regression_drop": 0.02,
        "gradient_abs_tol": 0.01,
    }
    rows, normalized_spec, summary = evaluate(dataset, spec)
    assert normalized_spec["grader_id"] == "g1"
    assert any(row["dataset_id"] == "d1" and row["gradient_pass"] is False for row in rows)
    assert any(row["dataset_id"] == "d1" and row["frontier_class"] == "near_miss_frontier" for row in rows)
    assert any(row["dataset_id"] == "d2" and row["frontier_class"] == "success_frontier" for row in rows)
    assert summary["overall_pass"] is False
    assert summary["gradient_failures"] >= 1
    assert summary["frontier_diagnostics"]["counts"]["success_frontier"] >= 1


def main() -> None:
    parser = argparse.ArgumentParser(description="Run portable eval flywheel")
    parser.add_argument("--dataset", type=Path, help="Path to dataset JSONL")
    parser.add_argument("--grader-spec", type=Path, help="Path to grader spec YAML/JSON")
    parser.add_argument("--out-dir", type=Path, default=Path("."), help="Output directory")
    parser.add_argument("--self-test", action="store_true", help="Run built-in tests")
    args = parser.parse_args()

    if args.self_test:
        _run_self_test()
        print("self-test passed")
        return

    if not args.dataset:
        raise SystemExit("--dataset is required unless --self-test is used")

    dataset_rows = _read_jsonl(args.dataset)
    grader_spec = _read_yaml_or_json(args.grader_spec) if args.grader_spec else {}

    normalized_rows, normalized_spec, summary = evaluate(dataset_rows, grader_spec)

    _write_jsonl(args.out_dir / "eval_dataset.jsonl", normalized_rows)
    _write_yaml(args.out_dir / "grader_spec.yaml", normalized_spec)
    _write_json(args.out_dir / "eval_summary.json", summary)
    print(str(args.out_dir.resolve()))


if __name__ == "__main__":
    main()
