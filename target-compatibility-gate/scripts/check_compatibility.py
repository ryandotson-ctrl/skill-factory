#!/usr/bin/env python3
"""Target compatibility checker with deterministic auto-fix plan."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        raise ValueError("request JSON must be an object")
    return payload


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _missing_capabilities(required: list[str], target_caps: dict[str, Any]) -> list[str]:
    instructions = {str(x) for x in target_caps.get("instructions", [])}
    formats = {str(x) for x in target_caps.get("formats", [])}
    precisions = {str(x) for x in target_caps.get("precisions", [])}
    generic_caps = {str(x) for x in target_caps.get("capabilities", [])}

    missing: list[str] = []
    for cap in required:
        if cap.startswith("instruction:"):
            op = cap.split(":", 1)[1]
            if op not in instructions:
                missing.append(cap)
        elif cap.startswith("format:"):
            fmt = cap.split(":", 1)[1]
            if fmt not in formats:
                missing.append(cap)
        elif cap.startswith("precision:"):
            prec = cap.split(":", 1)[1]
            if prec not in precisions:
                missing.append(cap)
        elif cap not in generic_caps:
            missing.append(cap)
    return missing


def _auto_fix_for(missing_cap: str, target_caps: dict[str, Any], artifact: dict[str, Any]) -> str | None:
    formats = {str(x) for x in target_caps.get("formats", [])}
    precisions = {str(x) for x in target_caps.get("precisions", [])}

    if missing_cap.startswith("instruction:"):
        return "transpile_to_target_basis"

    if missing_cap.startswith("format:"):
        missing_format = missing_cap.split(":", 1)[1]
        if formats:
            to_format = sorted(formats)[0]
            return f"convert_format:{missing_format}->{to_format}"
        return None

    if missing_cap.startswith("precision:"):
        missing_precision = missing_cap.split(":", 1)[1]
        if precisions:
            to_precision = sorted(precisions)[0]
            return f"convert_precision:{missing_precision}->{to_precision}"
        return None

    if missing_cap == "qubit_budget":
        return "partition_or_reduce_qubits"

    if missing_cap == "basis_gate_compatibility":
        return "basis_translate_with_transpiler"

    if missing_cap == "observable_support":
        return "observable_rewrite_or_postprocess"

    if missing_cap == "shot_requirement":
        return "set_shots_within_target_limits"

    if missing_cap.startswith("capability:"):
        return "switch_execution_mode_or_provider"

    if artifact:
        return "apply_adapter_transform"
    return None


def _check_circuit_constraints(
    artifact: dict[str, Any],
    target_caps: dict[str, Any],
    required: list[str],
) -> list[str]:
    missing: list[str] = []

    qubits = int(artifact.get("qubits", 0) or 0)
    max_qubits = int(target_caps.get("max_qubits", 0) or 0)
    if max_qubits > 0 and qubits > max_qubits and "qubit_budget" not in required:
        missing.append("qubit_budget")

    artifact_basis = {str(x) for x in artifact.get("basis_gates", [])}
    target_basis = {str(x) for x in target_caps.get("basis_gates", [])}
    if artifact_basis and target_basis and not artifact_basis.issubset(target_basis):
        missing.append("basis_gate_compatibility")

    artifact_obs = {str(x) for x in artifact.get("observables", [])}
    target_obs = {str(x) for x in target_caps.get("observables", [])}
    if artifact_obs and target_obs and not artifact_obs.issubset(target_obs):
        missing.append("observable_support")

    if bool(artifact.get("requires_shots", False)):
        supports_shots = bool(target_caps.get("supports_shots", True))
        if not supports_shots:
            missing.append("shot_requirement")
        else:
            requested_shots = int(artifact.get("shots", 0) or 0)
            min_shots = int(target_caps.get("min_shots", 0) or 0)
            max_shots = int(target_caps.get("max_shots", 0) or 0)
            if min_shots and requested_shots and requested_shots < min_shots:
                missing.append("shot_requirement")
            if max_shots and requested_shots and requested_shots > max_shots:
                missing.append("shot_requirement")

    return missing


def evaluate(request: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    target = str(request.get("target", "unknown_target"))
    artifact = request.get("artifact", {})
    target_caps = request.get("target_capabilities", {})

    required = [str(x) for x in request.get("required_capabilities", []) if str(x)]

    missing = _missing_capabilities(required, target_caps)

    if isinstance(artifact, dict) and isinstance(target_caps, dict):
        circuit_missing = _check_circuit_constraints(artifact, target_caps, required)
        for item in circuit_missing:
            if item not in missing:
                missing.append(item)

    auto_fixes: list[str] = []
    for cap in missing:
        action = _auto_fix_for(cap, target_caps, artifact if isinstance(artifact, dict) else {})
        if action and action not in auto_fixes:
            auto_fixes.append(action)

    compatibility = {
        "schema": "CompatibilityV1",
        "target": target,
        "artifact": str(artifact.get("type", "unknown_artifact")) if isinstance(artifact, dict) else "unknown_artifact",
        "required_capabilities": required,
        "missing_capabilities": sorted(missing),
        "auto_fixes": auto_fixes,
        "checked_at": _utc_now(),
    }

    unresolved = [cap for cap in sorted(missing) if _auto_fix_for(cap, target_caps, artifact if isinstance(artifact, dict) else {}) is None]
    compatible_after_fixes = len(unresolved) == 0

    transform_plan = {
        "schema": "ArtifactTransformPlanV1",
        "target": target,
        "compatible_now": len(missing) == 0,
        "compatible_after_fixes": compatible_after_fixes,
        "steps": [
            {
                "step": index + 1,
                "action": action,
                "reason": "auto-generated from missing capability",
                "blocking": False,
            }
            for index, action in enumerate(auto_fixes)
        ],
        "unresolved": unresolved,
        "checked_at": _utc_now(),
    }

    return compatibility, transform_plan


def _run_self_test() -> None:
    request = {
        "target": "example-target",
        "artifact": {
            "type": "quantum_circuit",
            "qubits": 20,
            "basis_gates": ["rz", "sx", "cz"],
            "observables": ["Z", "Y"],
            "requires_shots": True,
            "shots": 10000,
        },
        "required_capabilities": ["instruction:ry", "format:qasm3", "precision:fp32"],
        "target_capabilities": {
            "instructions": ["rz", "x", "measure"],
            "formats": ["qasm2"],
            "precisions": ["fp16"],
            "max_qubits": 16,
            "basis_gates": ["rz", "sx", "x"],
            "observables": ["Z"],
            "supports_shots": True,
            "max_shots": 4096,
        },
    }

    report, plan = evaluate(request)
    missing = set(report["missing_capabilities"])
    assert "instruction:ry" in missing
    assert "format:qasm3" in missing
    assert "precision:fp32" in missing
    assert "qubit_budget" in missing
    assert "basis_gate_compatibility" in missing
    assert "observable_support" in missing
    assert "shot_requirement" in missing
    actions = {step["action"] for step in plan["steps"]}
    assert "transpile_to_target_basis" in actions
    assert "basis_translate_with_transpiler" in actions


def main() -> None:
    parser = argparse.ArgumentParser(description="Check compatibility and propose transform plan")
    parser.add_argument("--request", type=Path, help="Path to request JSON")
    parser.add_argument("--out-dir", type=Path, default=Path("."), help="Output directory")
    parser.add_argument("--self-test", action="store_true", help="Run built-in tests")
    args = parser.parse_args()

    if args.self_test:
        _run_self_test()
        print("self-test passed")
        return

    if not args.request:
        raise SystemExit("--request is required unless --self-test is used")

    request = _read_json(args.request)
    compatibility, transform_plan = evaluate(request)

    _write_json(args.out_dir / "compatibility_report.json", compatibility)
    _write_json(args.out_dir / "artifact_transform_plan.json", transform_plan)
    print(str(args.out_dir.resolve()))


if __name__ == "__main__":
    main()
