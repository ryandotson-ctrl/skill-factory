---
name: xcode-build-harness-installer
description: Install or upgrade a portable Apple CLI build harness for generator-backed or existing Xcode projects. Use when a repo needs isolated DerivedData, logs, cache, and temp paths under build/, reproducible make targets like diagnose, build, test, run, and agent-verify, or a safe project-local install flow for iOS, iPadOS, macOS, visionOS, and watchOS work.
---

# Xcode Build Harness Installer

## Overview

Use this skill to install a reusable Apple CLI build kit into a project without inventing repo-specific shell flows from scratch.

The harness preserves the strongest parts of older Xcode makefile toolkits:
- isolated `build/DerivedData`, logs, cache, and temp roots
- strict `make` targets for diagnose, build, test, run, and `agent-verify`
- `xcbuild.sh` result-bundle and log capture
- scoped `atomic_commit.sh`
- optional namespacing so multiple harnesses can coexist in one repo

## When To Use

Activate when the user asks to:
- add Apple CLI build tooling to a repo
- upgrade an existing Apple makefile harness
- isolate per-agent build artifacts
- make Apple app verification reproducible from the terminal
- give an Apple repo a stable `make diagnose` or `make agent-verify` path

## Install Contract

Primary command:

```bash
python3 "$CODEX_HOME/skills/xcode-build-harness-installer/scripts/install.sh" \
  --project-dir /path/to/project \
  --app-name ExampleApp \
  --platform ios
```

Supported platforms:
- `ios`
- `ipados`
- `macos`
- `visionos`
- `watchos`

Read `references/install-contract.md` for flags and `references/target-behavior.md` for the target contract.

## Behavior

- `install`: fail rather than overwrite existing harness files
- `upgrade`: replace the harness files intentionally
- `dry-run`: print exactly what would be installed
- namespacing: optional `Makefile.<namespace>` and `scripts/<namespace>/`
- environment-driven agent identity: prefer environment values over hard-coded labels
- `xcbeautify` is optional, never required

## Target Contract

Installed targets:
- `make diagnose`
- `make build`
- `make test`
- `make run`
- `make build-and-run`
- `make build-and-run-background`
- `make clean`
- `make agent-verify`

Simulator run support is strongest for iOS and iPadOS. visionOS and watchOS installs still get build and test discipline, and run behavior remains best-effort rather than guaranteed.

## Resources

- `references/install-contract.md`
- `references/target-behavior.md`
- `scripts/install.sh`
- `scripts/render_template.py`
- `assets/toolkit/`
