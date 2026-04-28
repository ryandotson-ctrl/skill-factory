#!/usr/bin/env python3
"""Portable cold-storage manifest inspector and restore helper."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


def load_manifest(path: Path) -> dict:
    return json.loads(path.read_text())


def run_rsync(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["rsync", "-a", f"{source}/", f"{destination}/"], check=True)


def verify_entry(entry: dict) -> dict:
    live = Path(entry["live_path"])
    cold = Path(entry["cold_path"])
    live_exists = live.exists() or live.is_symlink()
    cold_exists = cold.exists()
    live_is_symlink = live.is_symlink()
    live_target = os.readlink(live) if live_is_symlink else None
    alias_checks = []
    for alias in entry.get("alias_paths", []):
        alias_path = Path(alias)
        alias_checks.append(
            {
                "path": alias,
                "exists": alias_path.exists() or alias_path.is_symlink(),
                "is_symlink": alias_path.is_symlink(),
                "target": os.readlink(alias_path) if alias_path.is_symlink() else None,
            }
        )
    return {
        "name": entry["name"],
        "strategy": entry["strategy"],
        "live_exists": live_exists,
        "cold_exists": cold_exists,
        "live_is_symlink": live_is_symlink,
        "live_target": live_target,
        "points_to_cold": live_is_symlink and live_target == entry["cold_path"],
        "alias_checks": alias_checks,
    }


def list_entries(manifest: dict) -> int:
    for entry in manifest["entries"]:
        status = verify_entry(entry)
        print(
            f"{entry['name']}: strategy={entry['strategy']} "
            f"live_exists={status['live_exists']} cold_exists={status['cold_exists']}"
        )
        print(f"  live: {entry['live_path']}")
        print(f"  cold: {entry['cold_path']}")
    return 0


def verify_entries(manifest: dict, as_json: bool) -> int:
    payload = {
        "schema": "ColdStorageVerificationResultV1",
        "manifest_version": manifest["manifest_version"],
        "entries": [verify_entry(entry) for entry in manifest["entries"]],
    }
    if as_json:
        print(json.dumps(payload, indent=2))
    else:
        for entry in payload["entries"]:
            print(
                f"{entry['name']}: live_exists={entry['live_exists']} "
                f"cold_exists={entry['cold_exists']} points_to_cold={entry['points_to_cold']}"
            )
    return 0


def materialize_entry(entry: dict) -> int:
    cold = Path(entry["cold_path"])
    live = Path(entry["live_path"])
    if not cold.exists():
        raise FileNotFoundError(f"Cold path is missing: {cold}")

    if entry["strategy"] == "path_preserved_symlink" and live.is_symlink():
        live.unlink()
        run_rsync(cold, live)
        return 0

    if entry["strategy"] == "copy_back":
        if live.is_symlink():
            live.unlink()
        if live.exists():
            raise FileExistsError(f"Live path already exists and is not a symlink: {live}")
        run_rsync(cold, live)
        return 0

    if live.exists() and not live.is_symlink():
        return 0

    raise RuntimeError(
        f"Don't know how to materialize entry '{entry['name']}' with strategy {entry['strategy']}"
    )


def relink_entry(entry: dict) -> int:
    cold = Path(entry["cold_path"])
    live = Path(entry["live_path"])
    if not cold.exists():
        raise FileNotFoundError(f"Cold path is missing: {cold}")
    if live.is_symlink():
        live.unlink()
    elif live.exists():
        raise FileExistsError(f"Live path already exists and is not a symlink: {live}")
    live.parent.mkdir(parents=True, exist_ok=True)
    live.symlink_to(cold)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage cold-stored model directories.")
    parser.add_argument("--manifest", required=True, help="Path to ColdStorageManifestV1 JSON.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("list", help="List manifest entries.")

    verify = subparsers.add_parser("verify", help="Verify manifest entries.")
    verify.add_argument("--json", action="store_true", help="Emit JSON.")

    restore = subparsers.add_parser(
        "materialize-local",
        help="Copy an entry back onto the internal drive as a real directory.",
    )
    restore.add_argument("name", help="Entry name from the manifest.")

    relink = subparsers.add_parser(
        "relink-cold",
        help="Recreate a symlink from the live path back to the cold-storage path.",
    )
    relink.add_argument("name", help="Entry name from the manifest.")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    manifest = load_manifest(Path(args.manifest))
    entries = {entry["name"]: entry for entry in manifest["entries"]}

    if args.command == "list":
        return list_entries(manifest)
    if args.command == "verify":
        return verify_entries(manifest, as_json=args.json)
    if args.command == "materialize-local":
        return materialize_entry(entries[args.name])
    if args.command == "relink-cold":
        return relink_entry(entries[args.name])
    parser.error(f"Unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # pragma: no cover
        print(f"error: {exc}", file=sys.stderr)
        raise
