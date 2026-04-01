#!/usr/bin/env python3
"""Capability and entitlement negotiation for portable launch planning."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text())
    if not isinstance(data, dict):
        raise ValueError("request JSON must be an object")
    return data


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _stable_hash(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _normalize_features(raw_features: Any, source: str) -> dict[str, dict[str, Any]]:
    features: dict[str, dict[str, Any]] = {}
    if isinstance(raw_features, dict):
        for name, value in raw_features.items():
            available = bool(value) if not isinstance(value, dict) else bool(value.get("available"))
            detail = "" if not isinstance(value, dict) else str(value.get("detail", ""))
            features[str(name)] = {
                "available": available,
                "detail": detail,
                "source": source,
            }
        return features

    if isinstance(raw_features, list):
        for item in raw_features:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name", "")).strip()
            if not name:
                continue
            features[name] = {
                "available": bool(item.get("available", False)),
                "detail": str(item.get("detail", "")),
                "source": source,
            }
    return features


def _normalize_local_route_prereqs(raw_prereqs: Any) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []

    def _normalize_one(name: str, value: Any) -> dict[str, Any]:
        if isinstance(value, dict):
            present = bool(value.get("present", value.get("available", False)))
            required = bool(value.get("required", True))
            detail = str(value.get("detail", ""))
            required_for_raw = value.get("required_for", value.get("required_features", value.get("applies_to", [])))
        else:
            present = bool(value)
            required = True
            detail = ""
            required_for_raw = []

        required_for: list[str] = []
        if isinstance(required_for_raw, list):
            required_for = [str(item) for item in required_for_raw if str(item)]
        elif isinstance(required_for_raw, str) and required_for_raw.strip():
            required_for = [required_for_raw.strip()]

        return {
            "name": name,
            "required": required,
            "present": present,
            "required_for": required_for,
            "detail": detail,
            "source": "request",
        }

    if isinstance(raw_prereqs, dict):
        for raw_name, raw_value in raw_prereqs.items():
            name = str(raw_name).strip()
            if not name:
                continue
            normalized.append(_normalize_one(name, raw_value))
        return normalized

    if isinstance(raw_prereqs, list):
        for item in raw_prereqs:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name", "")).strip()
            if not name:
                continue
            normalized.append(_normalize_one(name, item))

    return normalized


def _normalize_runtime_provenance(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raw = {}

    mock_runtime_runs = int(raw.get("mock_runtime_runs", 0) or 0)
    real_runtime_runs = int(raw.get("real_runtime_runs", 0) or 0)
    mock_runtime_detected = bool(raw.get("mock_runtime_detected", mock_runtime_runs > 0))
    real_runtime_detected = bool(raw.get("real_runtime_detected", real_runtime_runs > 0))
    mock_counts_toward_cooldown = bool(raw.get("mock_counts_toward_cooldown", False))

    if real_runtime_detected and mock_runtime_detected:
        evidence_mode = "mixed"
    elif real_runtime_detected:
        evidence_mode = "real_runtime"
    elif mock_runtime_detected:
        evidence_mode = "mock_only"
    else:
        evidence_mode = "none"

    cooldown_safe = not (mock_runtime_detected and mock_counts_toward_cooldown)
    return {
        "mock_runtime_runs": max(0, mock_runtime_runs),
        "real_runtime_runs": max(0, real_runtime_runs),
        "mock_runtime_detected": mock_runtime_detected,
        "real_runtime_detected": real_runtime_detected,
        "mock_counts_toward_cooldown": mock_counts_toward_cooldown,
        "evidence_mode": evidence_mode,
        "cooldown_safe": cooldown_safe,
    }


def _build_effective_state_proof(
    *,
    requested_features: set[str],
    required_features: set[str],
    features: dict[str, dict[str, Any]],
    local_prereqs: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str], dict[str, list[str]]]:
    missing_by_feature: dict[str, list[str]] = {}
    missing_required_prereqs: list[str] = []

    for prereq in local_prereqs:
        if not bool(prereq.get("required", True)):
            continue
        if bool(prereq.get("present", False)):
            continue

        prereq_name = str(prereq.get("name", "unnamed_prereq"))
        required_for = [str(item) for item in prereq.get("required_for", []) if str(item)]
        if not required_for:
            required_for = sorted(required_features)

        if required_for:
            for feature in required_for:
                missing_by_feature.setdefault(feature, []).append(prereq_name)
        else:
            missing_required_prereqs.append(prereq_name)

    proof_rows: list[dict[str, Any]] = []
    features_to_prove = sorted(set(features.keys()) | requested_features | required_features)
    for feature in features_to_prove:
        info = features.get(feature, {"available": False})
        provider_available = bool(info.get("available", False))
        missing_local = sorted(set(missing_by_feature.get(feature, [])))
        effective_available = provider_available and not missing_local

        if missing_local:
            reason_code = "missing_local_prerequisite"
        elif provider_available:
            reason_code = "available"
        else:
            reason_code = "provider_or_entitlement_unavailable"

        proof_rows.append(
            {
                "feature": feature,
                "requested": feature in requested_features,
                "provider_available": provider_available,
                "effective_available": effective_available,
                "missing_local_prereqs": missing_local,
                "reason_code": reason_code,
            }
        )

    return proof_rows, sorted(set(missing_required_prereqs)), missing_by_feature


def _provider_features(provider: str, request: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    credentials = request.get("credentials", {})
    cfg = request.get("provider_config", {})

    token_present = bool(credentials.get("token_present", False))
    token_valid = bool(credentials.get("token_valid", False))

    provenance: list[dict[str, Any]] = [
        {
            "name": "token_present",
            "passed": token_present,
            "detail": "Credential token present",
        },
        {
            "name": "token_valid",
            "passed": token_valid,
            "detail": "Credential token validated",
        },
    ]

    if provider == "simulator_only":
        features = {
            "sim": {
                "available": True,
                "detail": "Local simulator always available",
                "source": "adapter",
            }
        }
        provenance.append(
            {
                "name": "simulator_local",
                "passed": True,
                "detail": "No remote entitlement required",
            }
        )
        return features, provenance

    if provider == "ibm_runtime":
        runtime_available = bool(cfg.get("runtime_available", False))
        instance_present = bool(credentials.get("instance_present", False))
        runtime_ok = token_valid and runtime_available and instance_present
        features = {
            "runtime_sampler": {
                "available": runtime_ok,
                "detail": "IBM Runtime sampler availability",
                "source": "adapter",
            }
        }
        provenance.extend(
            [
                {
                    "name": "runtime_available",
                    "passed": runtime_available,
                    "detail": "qiskit-ibm-runtime available",
                },
                {
                    "name": "instance_present",
                    "passed": instance_present,
                    "detail": "IBM instance present",
                },
            ]
        )
        return features, provenance

    if provider == "ibm_catalog":
        runtime_available = bool(cfg.get("runtime_available", False))
        catalog_available = bool(cfg.get("catalog_available", False))
        catalog_entitlement = bool(cfg.get("catalog_entitlement", False))
        runtime_ok = token_valid and runtime_available
        catalog_ok = token_valid and catalog_available and catalog_entitlement
        features = {
            "runtime_sampler": {
                "available": runtime_ok,
                "detail": "IBM Runtime fallback path",
                "source": "adapter",
            },
            "catalog_solver": {
                "available": catalog_ok,
                "detail": "IBM catalog solver entitlement",
                "source": "adapter",
            },
        }
        provenance.extend(
            [
                {
                    "name": "runtime_available",
                    "passed": runtime_available,
                    "detail": "qiskit-ibm-runtime available",
                },
                {
                    "name": "catalog_available",
                    "passed": catalog_available,
                    "detail": "qiskit-ibm-catalog available",
                },
                {
                    "name": "catalog_entitlement",
                    "passed": catalog_entitlement,
                    "detail": "Catalog entitlement present",
                },
            ]
        )
        return features, provenance

    if provider == "google_engine":
        approved_access = bool(cfg.get("approved_access", False))
        project_present = bool(cfg.get("project_present", False))
        qpu_ok = token_valid and approved_access and project_present
        features = {
            "cirq_simulator": {
                "available": True,
                "detail": "Cirq simulator path",
                "source": "adapter",
            },
            "google_qpu": {
                "available": qpu_ok,
                "detail": "Google engine QPU entitlement",
                "source": "adapter",
            },
        }
        provenance.extend(
            [
                {
                    "name": "approved_access",
                    "passed": approved_access,
                    "detail": "Google access approved",
                },
                {
                    "name": "project_present",
                    "passed": project_present,
                    "detail": "Google project configured",
                },
            ]
        )
        return features, provenance

    # Generic adapter fallback
    features = {
        "generic_mode": {
            "available": token_valid,
            "detail": "Generic provider fallback",
            "source": "adapter",
        }
    }
    provenance.append(
        {
            "name": "generic_adapter",
            "passed": True,
            "detail": "Generic adapter selected",
        }
    )
    return features, provenance


def negotiate(request: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    provider = str(request.get("provider", "unknown"))
    required = [str(x) for x in request.get("required_features", []) if str(x)]
    required_features = set(required)
    requested_features = set(required)
    requested_features.update(str(x) for x in request.get("requested_features", []) if str(x))
    fallback_modes = [str(x) for x in request.get("fallback_modes", ["limited"]) if str(x)]
    local_route_prereqs = _normalize_local_route_prereqs(request.get("local_route_prereqs", []))

    credentials = request.get("credentials", {})
    token_present = bool(credentials.get("token_present", False))
    token_valid = bool(credentials.get("token_valid", False))
    runtime_provenance = _normalize_runtime_provenance(request.get("runtime_provenance", {}))

    adapter_features, provenance = _provider_features(provider, request)
    provenance.append(
        {
            "name": "runtime_provenance_cooldown_safe",
            "passed": bool(runtime_provenance["cooldown_safe"]),
            "detail": (
                f"evidence_mode={runtime_provenance['evidence_mode']} "
                f"mock_counts_toward_cooldown={runtime_provenance['mock_counts_toward_cooldown']}"
            ),
        }
    )
    user_features = _normalize_features(request.get("features", {}), source="request")

    features: dict[str, dict[str, Any]] = {}
    features.update(adapter_features)
    features.update(user_features)

    effective_state_proof, missing_required_prereqs, _ = _build_effective_state_proof(
        requested_features=requested_features,
        required_features=required_features,
        features=features,
        local_prereqs=local_route_prereqs,
    )

    matrix_rows: list[dict[str, Any]] = []
    for name in sorted(set(list(features.keys()) + required)):
        info = features.get(name, {"available": False, "detail": "not declared", "source": "derived"})
        matrix_rows.append(
            {
                "feature": name,
                "required": name in required,
                "available": bool(info.get("available", False)),
                "detail": str(info.get("detail", "")),
                "source": str(info.get("source", "derived")),
            }
        )

    required_proof_rows = [row for row in effective_state_proof if row["feature"] in required_features]
    required_effective_available = all(row["effective_available"] for row in required_proof_rows)
    local_route_prereq_failures = sorted(
        {
            prereq
            for row in required_proof_rows
            for prereq in row.get("missing_local_prereqs", [])
            if str(prereq)
        }
        | {str(item) for item in missing_required_prereqs if str(item)}
    )
    missing_provider_required = any(
        (not row["provider_available"]) for row in required_proof_rows
    )
    downgrade_codes: list[str] = []

    if not token_present and provider != "simulator_only":
        mode = "disabled"
        reason = "Missing credentials: token not present"
        reason_code = "missing_credentials"
        resolved_fallback = []
        downgrade_codes = ["missing_credentials"]
    elif not token_valid and provider not in {"simulator_only"}:
        mode = "disabled"
        reason = "Invalid credentials: token could not be verified"
        reason_code = "invalid_credentials"
        resolved_fallback = []
        downgrade_codes = ["invalid_credentials"]
    elif required_effective_available:
        mode = "full"
        reason = "All required features are effectively available"
        reason_code = "all_required_effective_available"
        resolved_fallback = fallback_modes
    elif fallback_modes:
        mode = "limited"
        reason = "Required features missing; fallback mode available"
        if local_route_prereq_failures and not missing_provider_required:
            reason_code = "missing_local_route_prerequisites"
        else:
            reason_code = "required_features_unavailable_fallback_available"
        resolved_fallback = fallback_modes
        downgrade_codes = ["required_features_unavailable"]
        if local_route_prereq_failures:
            downgrade_codes.append("missing_local_route_prerequisites")
        if missing_provider_required:
            downgrade_codes.append("provider_or_entitlement_unavailable")
    else:
        mode = "disabled"
        reason = "Required features missing and no viable fallback"
        if local_route_prereq_failures and not missing_provider_required:
            reason_code = "missing_local_route_prerequisites"
        else:
            reason_code = "required_features_unavailable_no_fallback"
        resolved_fallback = []
        downgrade_codes = ["required_features_unavailable", "no_viable_fallback"]
        if local_route_prereq_failures:
            downgrade_codes.append("missing_local_route_prerequisites")
        if missing_provider_required:
            downgrade_codes.append("provider_or_entitlement_unavailable")

    if local_route_prereq_failures and mode != "full" and "missing_local_route_prerequisites" not in downgrade_codes:
        downgrade_codes.append("missing_local_route_prerequisites")
    if mode != "full" and missing_provider_required and "provider_or_entitlement_unavailable" not in downgrade_codes:
        downgrade_codes.append("provider_or_entitlement_unavailable")

    if not runtime_provenance["cooldown_safe"]:
        downgrade_codes.append("mock_runtime_cooldown_policy_violation")
        if mode == "full":
            if fallback_modes:
                mode = "limited"
                resolved_fallback = fallback_modes
            else:
                mode = "disabled"
                resolved_fallback = []
            reason = "Mock-runtime provenance cannot be counted as cooldown-consuming evidence"
            reason_code = "mock_runtime_cooldown_policy_violation"

    downgrade_codes = sorted(set(downgrade_codes))

    signature_payload = {
        "provider": provider,
        "credentials": {"token_present": token_present, "token_valid": token_valid},
        "rows": matrix_rows,
        "local_route_prereqs": local_route_prereqs,
        "effective_state_proof": effective_state_proof,
        "runtime_provenance": runtime_provenance,
        "provenance": provenance,
    }

    capability_matrix = {
        "schema": "CapabilityMatrixV1",
        "provider": provider,
        "checked_at": _utc_now(),
        "credentials": {
            "token_present": token_present,
            "token_valid": token_valid,
        },
        "rows": matrix_rows,
        "local_route_prereqs": local_route_prereqs,
        "effective_state_proof": effective_state_proof,
        "runtime_provenance": runtime_provenance,
        "provenance": provenance,
        "provenance_signature": _stable_hash(signature_payload),
    }

    execution_mode = {
        "schema": "ExecutionModeV1",
        "mode": mode,
        "reason": reason,
        "reason_code": reason_code,
        "downgrade_codes": downgrade_codes,
        "local_route_prereq_failures": local_route_prereq_failures,
        "fallback_modes": resolved_fallback,
        "provider": provider,
        "runtime_provenance": runtime_provenance,
        "cooldown_safe": bool(runtime_provenance["cooldown_safe"]),
        "checked_at": _utc_now(),
        "provenance": provenance,
    }

    return capability_matrix, execution_mode


def _run_self_test() -> None:
    missing_creds_request = {
        "provider": "ibm_runtime",
        "credentials": {"token_present": False, "token_valid": False, "instance_present": False},
        "required_features": ["runtime_sampler"],
        "provider_config": {"runtime_available": True},
        "fallback_modes": ["sim"],
    }
    _, mode_missing = negotiate(missing_creds_request)
    assert mode_missing["mode"] == "disabled"
    assert mode_missing["reason_code"] == "missing_credentials"
    assert "missing_credentials" in mode_missing["downgrade_codes"]

    partial_request = {
        "provider": "ibm_catalog",
        "credentials": {"token_present": True, "token_valid": True, "instance_present": True},
        "required_features": ["catalog_solver"],
        "provider_config": {
            "runtime_available": True,
            "catalog_available": True,
            "catalog_entitlement": False,
        },
        "fallback_modes": ["runtime_sampler"],
    }
    matrix, mode_partial = negotiate(partial_request)
    assert mode_partial["mode"] == "limited"
    assert "runtime_sampler" in mode_partial["fallback_modes"]
    assert any(row["feature"] == "catalog_solver" and not row["available"] for row in matrix["rows"])
    assert any(
        row["feature"] == "catalog_solver"
        and row["provider_available"] is False
        and row["effective_available"] is False
        for row in matrix["effective_state_proof"]
    )
    assert isinstance(matrix.get("provenance_signature"), str)

    simulator_request = {
        "provider": "simulator_only",
        "credentials": {"token_present": False, "token_valid": False},
        "required_features": ["sim"],
        "fallback_modes": [],
        "local_route_prereqs": [
            {"name": "sim_binary", "required": True, "present": True, "required_for": ["sim"]},
        ],
    }
    _, simulator_mode = negotiate(simulator_request)
    assert simulator_mode["mode"] == "full"

    local_prereq_missing_request = {
        "provider": "ibm_runtime",
        "credentials": {"token_present": True, "token_valid": True, "instance_present": True},
        "required_features": ["runtime_sampler"],
        "provider_config": {"runtime_available": True},
        "fallback_modes": ["sim"],
        "local_route_prereqs": [
            {
                "name": "draft_model_env",
                "required": True,
                "present": False,
                "required_for": ["runtime_sampler"],
            }
        ],
    }
    matrix_local, mode_local = negotiate(local_prereq_missing_request)
    assert mode_local["mode"] == "limited"
    assert mode_local["reason_code"] == "missing_local_route_prerequisites"
    assert "draft_model_env" in mode_local["local_route_prereq_failures"]
    assert "missing_local_route_prerequisites" in mode_local["downgrade_codes"]
    assert any(
        row["feature"] == "runtime_sampler"
        and row["provider_available"] is True
        and row["effective_available"] is False
        for row in matrix_local["effective_state_proof"]
    )

    mock_cooldown_violation_request = {
        "provider": "ibm_runtime",
        "credentials": {"token_present": True, "token_valid": True, "instance_present": True},
        "required_features": ["runtime_sampler"],
        "provider_config": {"runtime_available": True},
        "fallback_modes": ["sim"],
        "runtime_provenance": {
            "mock_runtime_detected": True,
            "mock_counts_toward_cooldown": True,
            "real_runtime_detected": False,
        },
    }
    matrix_violation, mode_violation = negotiate(mock_cooldown_violation_request)
    assert mode_violation["mode"] == "limited"
    assert mode_violation["reason_code"] == "mock_runtime_cooldown_policy_violation"
    assert mode_violation["cooldown_safe"] is False
    assert "mock_runtime_cooldown_policy_violation" in mode_violation["downgrade_codes"]
    assert matrix_violation["runtime_provenance"]["evidence_mode"] == "mock_only"


def main() -> None:
    parser = argparse.ArgumentParser(description="Negotiate capability and entitlement state")
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
    capability_matrix, execution_mode = negotiate(request)

    _write_json(args.out_dir / "capability_matrix.json", capability_matrix)
    _write_json(args.out_dir / "execution_mode.json", execution_mode)
    print(str(args.out_dir.resolve()))


if __name__ == "__main__":
    main()
