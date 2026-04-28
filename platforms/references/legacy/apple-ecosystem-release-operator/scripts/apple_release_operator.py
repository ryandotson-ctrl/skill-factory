#!/usr/bin/env python3
import argparse
import datetime as dt
import json
import os
import pathlib
import plistlib
import re
import shutil
import subprocess
import sys
import tempfile

try:
    import yaml
except ImportError as exc:  # pragma: no cover
    yaml = None
    YAML_IMPORT_ERROR = exc
else:
    YAML_IMPORT_ERROR = None


DEFAULT_DEVELOPER_DIR = "/Applications/Xcode.app/Contents/Developer"
DEFAULT_EXPORT_PATH = "build/TestFlight/export"


def die(message: str) -> None:
    print(f"[apple-release] ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def log(message: str) -> None:
    print(f"[apple-release] {message}")


def need_cmd(name: str) -> None:
    if shutil.which(name) is None:
        die(f"Missing required command: {name}")


def run(command, *, cwd=None, env=None, capture=False, check=True):
    rendered = command if isinstance(command, str) else " ".join(str(part) for part in command)
    log(f"Running: {rendered}")
    return subprocess.run(
        command,
        cwd=cwd,
        env=env,
        shell=isinstance(command, str),
        text=True,
        capture_output=capture,
        check=check,
    )


def load_yaml(path: pathlib.Path):
    if yaml is None:
        die(f"PyYAML is required to read {path}: {YAML_IMPORT_ERROR}")
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def load_profile(profile_path: pathlib.Path) -> dict:
    profile = load_yaml(profile_path)
    if not isinstance(profile, dict):
        die(f"Profile is not a mapping: {profile_path}")
    return profile


def profile_project_root(profile_path: pathlib.Path, profile: dict) -> pathlib.Path:
    return (profile_path.parent / profile["project_root"]).resolve()


def resolve_project_path(project_root: pathlib.Path, value: str) -> pathlib.Path:
    return (project_root / value).resolve()


def platform_default_archive_destination(platform_name: str) -> str:
    normalized = platform_name.lower()
    defaults = {
        "ios": "generic/platform=iOS",
        "ipados": "generic/platform=iOS",
        "visionos": "generic/platform=visionOS",
        "macos": "generic/platform=macOS",
        "watchos": "generic/platform=watchOS",
    }
    if normalized not in defaults:
        die(f"Unsupported platform '{platform_name}'")
    return defaults[normalized]


def xcode_container_flag(project_path: pathlib.Path):
    suffix = project_path.suffix.lower()
    if suffix == ".xcworkspace":
        return "-workspace", str(project_path)
    return "-project", str(project_path)


def extract_source_value(project_root: pathlib.Path, source_spec: dict) -> str:
    if "value" in source_spec:
        return str(source_spec["value"])

    source_path = resolve_project_path(project_root, source_spec["path"])
    document = load_yaml(source_path)
    key = source_spec["key"]
    target = source_spec.get("target")
    template = source_spec.get("template")

    if target:
        value = (
            document.get("targets", {})
            .get(target, {})
            .get("settings", {})
            .get("base", {})
            .get(key)
        )
        if value is not None:
            return str(value)

    if template:
        value = (
            document.get("targetTemplates", {})
            .get(template, {})
            .get("settings", {})
            .get("base", {})
            .get(key)
        )
        if value is not None:
            return str(value)

    if isinstance(document, dict):
        for candidate_key, candidate_value in walk_items(document):
            if candidate_key == key:
                return str(candidate_value)

    die(f"Could not resolve key '{key}' from {source_path}")


def walk_items(value):
    if isinstance(value, dict):
        for key, item in value.items():
            yield key, item
            yield from walk_items(item)
    elif isinstance(value, list):
        for item in value:
            yield from walk_items(item)


def collect_build_settings(project_path: pathlib.Path, scheme: str, developer_dir: str) -> dict:
    flag, location = xcode_container_flag(project_path)
    env = os.environ.copy()
    env["DEVELOPER_DIR"] = developer_dir
    result = run(
        [
            "xcodebuild",
            flag,
            location,
            "-scheme",
            scheme,
            "-showBuildSettings",
        ],
        env=env,
        capture=True,
    )
    values = {}
    for line in result.stdout.splitlines():
        match = re.match(r"\s*([A-Z0-9_]+)\s*=\s*(.+)\s*$", line)
        if not match:
            continue
        key, value = match.groups()
        if key in {
            "PRODUCT_BUNDLE_IDENTIFIER",
            "DEVELOPMENT_TEAM",
            "MARKETING_VERSION",
            "CURRENT_PROJECT_VERSION",
        }:
            values[key] = value
    return values


def release_identity_status() -> str:
    if shutil.which("security") is None:
        return "security-command-missing"
    result = subprocess.run(
        ["security", "find-identity", "-v", "-p", "codesigning"],
        text=True,
        capture_output=True,
        check=False,
    )
    if re.search(r"Apple Distribution|iOS Distribution|Mac App Distribution", result.stdout):
        return "distribution-identity-present"
    return "distribution-identity-not-found"


def ensure_local_tools(profile: dict) -> None:
    for command in ("xcodebuild", "plutil", "xcrun"):
        need_cmd(command)
    if profile.get("generator_command"):
        need_cmd(profile["generator_command"].split()[0])


def discover_local_build_harness(project_root: pathlib.Path) -> dict:
    candidates = []
    for path in sorted(project_root.glob("Makefile*"), key=lambda item: (item.name != "Makefile", item.name)):
        if not path.is_file():
            continue
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if "agent-verify" not in content:
            continue
        namespace = path.name.split(".", 1)[1] if "." in path.name else ""
        verify_target = f"{namespace}-agent-verify" if namespace else "agent-verify"
        diagnose_target = f"{namespace}-diagnose" if namespace else "diagnose"
        if path.name == "Makefile":
            base_command = "make"
        else:
            base_command = f"make -f {path.name}"
        candidates.append(
            {
                "makefile": path.name,
                "namespace": namespace,
                "verify_target": verify_target,
                "diagnose_target": diagnose_target,
                "preferred_verify_command": f"{base_command} {verify_target}",
                "preferred_diagnose_command": f"{base_command} {diagnose_target}",
            }
        )
    if not candidates:
        return {"installed": False, "candidates": []}
    return {
        "installed": True,
        "preferred": candidates[0],
        "candidates": candidates,
    }


def build_context(profile_path: pathlib.Path, profile: dict, developer_dir: str) -> dict:
    project_root = profile_project_root(profile_path, profile)
    project_path = resolve_project_path(project_root, profile["xcode_project_or_workspace"])
    archive_path = resolve_project_path(project_root, profile["archive_path"])
    export_path = resolve_project_path(project_root, profile.get("export_path", DEFAULT_EXPORT_PATH))
    version = extract_source_value(project_root, profile["version_source"])
    build_number = extract_source_value(project_root, profile["build_number_source"])
    archive_destination = profile.get(
        "archive_destination",
        platform_default_archive_destination(profile["platform"]),
    )
    return {
        "profile_path": str(profile_path),
        "project_root": project_root,
        "project_path": project_path,
        "archive_path": archive_path,
        "export_path": export_path,
        "version": version,
        "build_number": build_number,
        "archive_destination": archive_destination,
        "developer_dir": developer_dir,
    }


def preflight(profile_path: pathlib.Path, developer_dir: str) -> dict:
    profile = load_profile(profile_path)
    ensure_local_tools(profile)
    context = build_context(profile_path, profile, developer_dir)
    settings = collect_build_settings(context["project_path"], profile["scheme"], developer_dir)
    local_build_harness = discover_local_build_harness(context["project_root"])
    mismatches = []

    expected_pairs = {
        "PRODUCT_BUNDLE_IDENTIFIER": profile["bundle_id"],
        "DEVELOPMENT_TEAM": profile["apple_team_id"],
        "MARKETING_VERSION": context["version"],
        "CURRENT_PROJECT_VERSION": context["build_number"],
    }
    for key, expected_value in expected_pairs.items():
        actual_value = settings.get(key)
        if actual_value != expected_value:
            mismatches.append({"field": key, "expected": expected_value, "actual": actual_value})

    receipt = {
        "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
        "platform": profile["platform"],
        "scheme": profile["scheme"],
        "bundle_id": profile["bundle_id"],
        "apple_team_id": profile["apple_team_id"],
        "version": context["version"],
        "build_number": context["build_number"],
        "project_path": str(context["project_path"]),
        "archive_path": str(context["archive_path"]),
        "default_testflight_group": profile["default_testflight_group"],
        "asc_app_name": profile["asc_app_name"],
        "sku": profile["sku"],
        "build_settings": settings,
        "distribution_identity": release_identity_status(),
        "local_build_harness": local_build_harness,
        "mismatches": mismatches,
        "status": "ok" if not mismatches else "mismatch",
    }
    return receipt


def maybe_run_generator(profile: dict, project_root: pathlib.Path) -> None:
    command = profile.get("generator_command")
    if command:
        run(command, cwd=project_root)


def maybe_run_tests(profile: dict, project_root: pathlib.Path, developer_dir: str, skip_tests: bool) -> dict:
    harness = discover_local_build_harness(project_root)
    command = profile.get("local_proof_command")
    source = "profile_local_proof_command" if command else ""
    if harness.get("installed"):
        command = harness["preferred"]["preferred_verify_command"]
        source = "xcode_build_harness"
    elif profile.get("test_command"):
        command = profile["test_command"]
        source = "profile_test_command"
    if skip_tests or not command:
        return {
            "proof_command": "",
            "proof_source": "skipped" if skip_tests else "none",
            "local_build_harness": harness,
        }
    env = os.environ.copy()
    env["DEVELOPER_DIR"] = developer_dir
    run(command, cwd=project_root, env=env)
    return {
        "proof_command": command,
        "proof_source": source,
        "local_build_harness": harness,
    }


def archive(profile_path: pathlib.Path, developer_dir: str, skip_tests: bool) -> dict:
    profile = load_profile(profile_path)
    ensure_local_tools(profile)
    context = build_context(profile_path, profile, developer_dir)
    maybe_run_generator(profile, context["project_root"])
    proof = maybe_run_tests(profile, context["project_root"], developer_dir, skip_tests)
    flag, location = xcode_container_flag(context["project_path"])
    env = os.environ.copy()
    env["DEVELOPER_DIR"] = developer_dir
    context["archive_path"].parent.mkdir(parents=True, exist_ok=True)
    run(
        [
            "xcodebuild",
            flag,
            location,
            "-scheme",
            profile["scheme"],
            "-configuration",
            "Release",
            "-destination",
            context["archive_destination"],
            "-archivePath",
            str(context["archive_path"]),
            "-allowProvisioningUpdates",
            "archive",
        ],
        cwd=context["project_root"],
        env=env,
    )
    return {
        "status": "archived",
        "archive_path": str(context["archive_path"]),
        "scheme": profile["scheme"],
        "platform": profile["platform"],
        "proof_command": proof["proof_command"],
        "proof_source": proof["proof_source"],
        "local_build_harness": proof["local_build_harness"],
    }


def write_export_options_plist(path: pathlib.Path, team_id: str, internal_only: bool) -> None:
    payload = {
        "method": "app-store-connect",
        "destination": "upload",
        "signingStyle": "automatic",
        "teamID": team_id,
        "uploadSymbols": True,
        "manageAppVersionAndBuildNumber": False,
    }
    if internal_only:
        payload["testFlightInternalTestingOnly"] = True
    with path.open("wb") as handle:
        plistlib.dump(payload, handle)


def upload(profile_path: pathlib.Path, developer_dir: str, internal_only: bool) -> dict:
    profile = load_profile(profile_path)
    ensure_local_tools(profile)
    context = build_context(profile_path, profile, developer_dir)
    if not context["archive_path"].exists():
        die(f"Archive not found at {context['archive_path']}")
    export_options = pathlib.Path(tempfile.mkstemp(prefix=f"{profile['scheme']}.", suffix=".plist")[1])
    write_export_options_plist(export_options, profile["apple_team_id"], internal_only)
    flag, location = xcode_container_flag(context["project_path"])
    env = os.environ.copy()
    env["DEVELOPER_DIR"] = developer_dir
    run(
        [
            "xcodebuild",
            "-exportArchive",
            "-archivePath",
            str(context["archive_path"]),
            "-exportPath",
            str(context["export_path"]),
            "-exportOptionsPlist",
            str(export_options),
            "-allowProvisioningUpdates",
        ],
        cwd=context["project_root"],
        env=env,
    )
    return {
        "status": "uploaded",
        "archive_path": str(context["archive_path"]),
        "export_path": str(context["export_path"]),
        "scheme": profile["scheme"],
        "internal_only": internal_only,
    }


def portal_sync(profile_path: pathlib.Path) -> dict:
    profile = load_profile(profile_path)
    return {
        "status": "checkpoint",
        "bundle_id": profile["bundle_id"],
        "asc_app_name": profile["asc_app_name"],
        "default_testflight_group": profile["default_testflight_group"],
        "safe_portal_actions": [
            "verify Bundle ID exists",
            "verify App Store Connect app record exists",
            "verify internal TestFlight group exists",
            "fill internal What to Test",
        ],
        "human_checkpoints": [
            "confirm authenticated Apple session before browser automation",
            "stop if portal work would expand beyond internal TestFlight scope",
        ],
    }


def invite_internal(profile_path: pathlib.Path, email: str, accepted: bool) -> dict:
    profile = load_profile(profile_path)
    return {
        "status": "eligible" if accepted else "awaiting_asc_acceptance",
        "email": email,
        "default_testflight_group": profile["default_testflight_group"],
        "bundle_id": profile["bundle_id"],
        "next_action": (
            f"Attach {email} to the {profile['default_testflight_group']} group."
            if accepted
            else f"Wait for {email} to accept the App Store Connect invite, then add them to {profile['default_testflight_group']}."
        ),
    }


def capture_evidence(profile_path: pathlib.Path, developer_dir: str, output_path: pathlib.Path, blockers, tester_statuses) -> dict:
    profile = load_profile(profile_path)
    context = build_context(profile_path, profile, developer_dir)
    settings = collect_build_settings(context["project_path"], profile["scheme"], developer_dir)
    local_build_harness = discover_local_build_harness(context["project_root"])
    evidence = {
        "captured_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "platform": profile["platform"],
        "scheme": profile["scheme"],
        "bundle_id": profile["bundle_id"],
        "asc_app_name": profile["asc_app_name"],
        "sku": profile["sku"],
        "apple_team_id": profile["apple_team_id"],
        "version": context["version"],
        "build_number": context["build_number"],
        "archive_path": str(context["archive_path"]),
        "default_testflight_group": profile["default_testflight_group"],
        "known_proven_archive_command": profile.get("known_proven_archive_command"),
        "known_proven_upload_command": profile.get("known_proven_upload_command"),
        "local_build_harness": local_build_harness,
        "build_settings": settings,
        "blockers": blockers,
        "tester_statuses": tester_statuses,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(evidence, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return evidence


def print_receipt(payload: dict) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def main():
    parser = argparse.ArgumentParser(description="Profile-driven Apple release operator")
    parser.add_argument("--developer-dir", default=os.environ.get("DEVELOPER_DIR", DEFAULT_DEVELOPER_DIR))
    subparsers = parser.add_subparsers(dest="command", required=True)

    for name in ("preflight", "portal-sync"):
        command = subparsers.add_parser(name)
        command.add_argument("--profile", required=True)

    archive_parser = subparsers.add_parser("archive")
    archive_parser.add_argument("--profile", required=True)
    archive_parser.add_argument("--skip-tests", action="store_true")

    upload_parser = subparsers.add_parser("upload")
    upload_parser.add_argument("--profile", required=True)
    upload_parser.add_argument("--internal-only", action="store_true")

    invite_parser = subparsers.add_parser("invite-internal")
    invite_parser.add_argument("--profile", required=True)
    invite_parser.add_argument("--email", required=True)
    invite_parser.add_argument("--accepted", action="store_true")

    evidence_parser = subparsers.add_parser("capture-evidence")
    evidence_parser.add_argument("--profile", required=True)
    evidence_parser.add_argument("--output", required=True)
    evidence_parser.add_argument("--blocker", action="append", default=[])
    evidence_parser.add_argument("--tester-status", action="append", default=[])

    args = parser.parse_args()
    developer_dir = args.developer_dir

    if args.command == "preflight":
        print_receipt(preflight(pathlib.Path(args.profile).resolve(), developer_dir))
    elif args.command == "archive":
        print_receipt(archive(pathlib.Path(args.profile).resolve(), developer_dir, args.skip_tests))
    elif args.command == "upload":
        print_receipt(upload(pathlib.Path(args.profile).resolve(), developer_dir, args.internal_only))
    elif args.command == "portal-sync":
        print_receipt(portal_sync(pathlib.Path(args.profile).resolve()))
    elif args.command == "invite-internal":
        print_receipt(invite_internal(pathlib.Path(args.profile).resolve(), args.email, args.accepted))
    elif args.command == "capture-evidence":
        tester_statuses = []
        for item in args.tester_status:
            if "=" in item:
                email, status = item.split("=", 1)
                tester_statuses.append({"email": email, "status": status})
            else:
                tester_statuses.append({"email": item, "status": "unknown"})
        print_receipt(
            capture_evidence(
                pathlib.Path(args.profile).resolve(),
                developer_dir,
                pathlib.Path(args.output).resolve(),
                args.blocker,
                tester_statuses,
            )
        )


if __name__ == "__main__":
    main()
