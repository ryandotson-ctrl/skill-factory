#!/usr/bin/env python3
from __future__ import annotations

import argparse
import pathlib
import re


def slugify(value: str) -> str:
    lowered = value.strip().lower()
    lowered = re.sub(r"[^a-z0-9]+", "-", lowered)
    lowered = re.sub(r"-{2,}", "-", lowered).strip("-")
    return lowered or "apple-app"


def detect_container(project_dir: pathlib.Path, app_name: str) -> str:
    workspaces = sorted(project_dir.glob("*.xcworkspace"))
    if workspaces:
        return workspaces[0].name
    projects = sorted(project_dir.glob("*.xcodeproj"))
    if projects:
        return projects[0].name
    return f"{app_name}.xcodeproj"


def build_profile_text(project_dir: pathlib.Path, app_name: str, bundle_id: str, platform: str, generator_command: str) -> str:
    container = detect_container(project_dir, app_name)
    project_yml = project_dir / "project.yml"
    source_block = f"""version_source:
  path: project.yml
  target: {app_name}
  key: MARKETING_VERSION
build_number_source:
  path: project.yml
  target: {app_name}
  key: CURRENT_PROJECT_VERSION"""
    if not project_yml.exists():
      source_block = """version_source:
  path: [TODO]
  key: [TODO]
build_number_source:
  path: [TODO]
  key: [TODO]"""

    archive_folder = {
        "ios": "iOS",
        "ipados": "iPadOS",
        "macos": "macOS",
        "visionos": "visionOS",
        "watchos": "watchOS",
    }.get(platform, platform)

    generator_line = f'generator_command: "{generator_command}"\n' if generator_command else ""
    return f"""platform: {platform}
project_root: ..
xcode_project_or_workspace: {container}
scheme: {app_name}
bundle_id: {bundle_id}
apple_team_id: TEAMID_PLACEHOLDER
{source_block}
archive_path: build/TestFlight/{archive_folder}/{app_name}.xcarchive
default_testflight_group: Internal
asc_app_name: {app_name}
sku: {slugify(app_name)}-{platform}
{generator_line}"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Write a release profile skeleton for Apple release operator.")
    parser.add_argument("--project-dir", required=True)
    parser.add_argument("--app-name", required=True)
    parser.add_argument("--bundle-id", required=True)
    parser.add_argument("--platform", required=True)
    parser.add_argument("--generator-command", default="")
    parser.add_argument("--output", default="release/apple_release_profile.yaml")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    project_dir = pathlib.Path(args.project_dir).resolve()
    output_path = project_dir / args.output
    payload = build_profile_text(project_dir, args.app_name, args.bundle_id, args.platform, args.generator_command)

    if args.dry_run:
        print(f"[dry-run] Would write Apple release profile to {output_path}")
        print(payload)
        return

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(payload, encoding="utf-8")
    print(f"Wrote Apple release profile to {output_path}")


if __name__ == "__main__":
    main()
