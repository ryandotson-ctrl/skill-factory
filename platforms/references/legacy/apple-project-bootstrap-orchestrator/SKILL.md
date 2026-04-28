---
name: apple-project-bootstrap-orchestrator
description: Portable Apple app scaffolding and adoption orchestrator for iOS, iPadOS, macOS, visionOS, and watchOS projects. Use when creating a new generator-backed Apple app, adopting an existing Xcode repo, installing an isolated build harness, writing an Apple release-profile skeleton, or laying down optional local task and onboarding templates without destructive regeneration.
---

# Apple Project Bootstrap Orchestrator

## Overview

Use this skill to create or adopt Apple app projects in a way that fits the rest of the Codex ecosystem.

This is the modern successor to older one-shot app creator flows:
- scaffold new Apple app projects with generator-backed templates
- adopt existing Apple repos non-destructively
- install the shared Xcode CLI harness through `$xcode-build-harness-installer`
- optionally install lightweight local task templates
- optionally write a release profile skeleton for `$apple-ecosystem-release-operator`
- optionally add onboarding fragments that point the repo at The Watcher and the core Apple verification lane

## When To Use

Activate when the user asks to:
- scaffold a new iOS, iPadOS, macOS, visionOS, or watchOS app
- bootstrap a clean Apple companion app
- adopt an existing Xcode project into the Codex skill ecosystem
- install Apple build tooling into a repo without regenerating app sources
- create or refresh a release profile skeleton for an Apple project
- set up project-local AGENTS or task helpers for an Apple repo

## Modes

Select one mode before acting:
- `new_project`: scaffold a generator-backed app template, then optionally install support tooling
- `adopt_existing`: do not regenerate app sources; only install optional tooling and bootstrap artifacts

Read `references/mode-contracts.md` for flags, receipts, and the platform or UI compatibility matrix.
Use `references/receipt-contracts.md` for the canonical bootstrap and support-install receipts, and `references/event-contracts.md` for Pulse Bus routing semantics.

## Supported Platforms And UI

Supported platforms:
- `ios`
- `ipados`
- `macos`
- `visionos`
- `watchos`

Supported UI frameworks:
- `swiftui` for all supported platforms
- `uikit` for `ios` and `ipados`
- `appkit` for `macos`

Xcode project generation is `xcodegen` first, but the workflow keeps `generator_command` explicit so future generators can fit without changing the skill contract.

## Workflow

### 1. Doctor And Mode Lock
Run the doctor check first:

```bash
python3 "$CODEX_HOME/skills/apple-project-bootstrap-orchestrator/scripts/doctor.sh" --project-mode new
```

### 2. Bootstrap Or Adoption
Use the orchestrator entrypoint:

```bash
python3 "$CODEX_HOME/skills/apple-project-bootstrap-orchestrator/scripts/init.sh" --project-mode new
```

Key behaviors:
- build harness installation is enabled by default
- task templates are optional and remain project-local
- git onboarding is optional and skipped when the repo is already dirty
- adopt mode never regenerates app sources

### 3. Optional Project Support
When requested, the bootstrap flow may also:
- install the shared Apple build harness
- install local task templates from `assets/simple-tasks`
- write onboarding fragments from `assets/onboarding`
- generate `release/apple_release_profile.yaml`

### 4. Final Receipt
The final response should include:
- selected mode
- platform and UI
- generated or adopted project root
- optional tooling that was installed
- exact next commands
- any skipped actions and why

Treat that final response as `BootstrapReceiptV1` for `new_project` work and `SupportInstallReceiptV1` for support-only adoption passes.

## Project Free Energy Profile

Use the optional `pfe` profile when the project is a PFE companion surface.

PFE defaults:
- keep `adopt_existing` as the safe posture for the main PFEMacOS repo
- install the Apple build harness by default
- install onboarding fragments that point to The Watcher, QA, runtime, and release skills
- generate a release profile skeleton by default
- keep PFE-specific consults and checks profile-gated so the base skill stays general

Read `references/pfe-profile.md` before using the PFE profile.

## Resources

- `references/mode-contracts.md`
- `references/receipt-contracts.md`
- `references/event-contracts.md`
- `references/pfe-profile.md`
- `references/worked-examples.md`
- `scripts/init.sh`
- `scripts/scaffold_app.sh`
- `scripts/install_task_templates.sh`
- `scripts/install_onboarding_fragment.sh`
- `scripts/write_release_profile.py`
- `assets/xcodegen/`
- `assets/simple-tasks/`
- `assets/onboarding/`

## Pulse Bus Contract

Ingress:
- `skill:apple-project-bootstrap-orchestrator:requested`
- `apple:project_bootstrap_requested`
- `apple:project_adoption_requested`
- `apple:project_support_install_requested`

Primary outputs:
- `apple:project_bootstrap_receipt`
- `apple:project_adoption_receipt`
- `apple:project_support_install_receipt`
- `apple_project_bootstrap_orchestrator_activity`

Use the receipt and event contracts so downstream skills can distinguish full scaffolds from non-destructive adoption and support-only installation passes.
