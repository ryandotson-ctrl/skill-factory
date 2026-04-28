#!/usr/bin/env python3
"""Validate MLX custom-function quantum bridge implementation contracts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


REQUIRED_PATTERNS = {
    "mlx_custom_function": "@mx.custom_function",
    "custom_vjp": ".vjp",
    "eval_barrier": "mx.eval(",
    "numpy_boundary": "np.asarray(",
}


def validate_source(text: str) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    missing: list[str] = []

    for name, pattern in REQUIRED_PATTERNS.items():
        passed = pattern in text
        checks.append(
            {
                "name": name,
                "passed": passed,
                "detail": f"pattern='{pattern}'",
            }
        )
        if not passed:
            missing.append(name)

    payload = {
        "schema": "BridgeValidationV1",
        "pass": len(missing) == 0,
        "checks": checks,
        "missing": missing,
    }
    return payload


def _run_self_test() -> None:
    text = """
import mlx.core as mx
import numpy as np

@mx.custom_function
def qop(a, b):
    mx.eval(a, b)
    x = np.asarray(a)
    return mx.array(x)

@qop.vjp
def qop_vjp(primals, cotangent, output):
    return cotangent, cotangent
"""
    report = validate_source(text)
    assert report["pass"] is True


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate MLX quantum bridge contracts")
    parser.add_argument("--file", type=Path, help="Python file to validate")
    parser.add_argument("--out", type=Path, default=Path("bridge_validation.json"), help="Output JSON path")
    parser.add_argument("--self-test", action="store_true", help="Run built-in tests")
    args = parser.parse_args()

    if args.self_test:
        _run_self_test()
        print("self-test passed")
        return

    if not args.file:
        raise SystemExit("--file is required unless --self-test is used")

    text = args.file.read_text()
    report = validate_source(text)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(str(args.out.resolve()))


if __name__ == "__main__":
    main()
