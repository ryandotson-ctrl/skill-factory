---
name: apple-ecosystem-release-operator
description: Portable Apple platform release operator for iOS, iPadOS, macOS, visionOS,
  and watchOS projects. Use when preparing Xcode targets for internal TestFlight or
  Apple distribution, defining a release profile, validating signing and archive readiness,
  capturing release evidence, or automating safe App Store Connect follow-through
  with explicit human checkpoints.
metadata:
  version: 1.4.0
  scope: global
  portability_tier: strict_zero_leak
  requires_env: []
  project_profiles:
  - PFEMacOS
---

# Apple Ecosystem Release Operator

## Overview

Use this skill to turn Apple release work into a repeatable, profile-driven flow across iPhone, iPad, Mac, Vision Pro, and Apple Watch apps.

Prefer deterministic local automation for project truth, build, archive, upload, and evidence capture. Use authenticated browser automation only for safe App Store Connect tasks that cannot be completed locally.

## When To Use This Skill

Activate when the user asks to:

- ship an Apple app to TestFlight
- prepare an iOS, iPadOS, macOS, visionOS, or watchOS build for internal testing
- verify signing, bundle ID, app record, or archive readiness
- diagnose why App Store Connect still shows a placeholder icon or stale app metadata
- attach an App Store version to the correct processed build in App Store Connect
- explain why a processed build is visible in TestFlight but disabled for App Store attachment
- create a reusable Apple release workflow for a project
- capture release intelligence from a successful Apple release path
- invite internal testers or verify why they are still ineligible

## Release Profile Contract

This skill expects a project-local release profile, usually at `release/apple_release_profile.yaml`.

Required fields:

- `platform`
- `project_root`
- `xcode_project_or_workspace`
- `scheme`
- `bundle_id`
- `apple_team_id`
- `version_source`
- `build_number_source`
- `archive_path`
- `default_testflight_group`
- `asc_app_name`
- `sku`

Optional fields:

- `generator_command`
- `local_proof_command`
- `test_command`
- `archive_destination`
- `simulator_destination`
- `export_path`
- `known_proven_archive_command`
- `known_proven_upload_command`
- `xcode_baseline`
- `swift_compiler_baseline`
- `swift_language_mode`
- `deployment_target`
- `latest_platform_surfaces`
- `optional_provider_lanes`

Read [references/profile-schema.md](references/profile-schema.md) before creating or updating a profile.

## Workflow

### 1. Ground The Project Truth

Run the skill script first:

```bash
python3 "$CODEX_HOME/skills/apple-ecosystem-release-operator/scripts/apple_release_operator.py" \
  preflight \
  --profile release/apple_release_profile.yaml
```

Confirm:

- the profile points at the correct project or workspace
- the scheme resolves
- the configured bundle ID and team match `xcodebuild -showBuildSettings`
- the configured Xcode baseline and active local Xcode version are aligned when the profile declares one
- the configured deployment target did not silently rise during generator or project regeneration
- version and build sources still resolve truthfully
- generator-backed projects have already regenerated the concrete Xcode project before any build-number or signing assertions that read generated artifacts
- when a local Apple build harness is installed, prefer its `make agent-verify` or namespaced equivalent as the first local proof command unless the profile overrides it explicitly
- release evidence captures the exact source state being shipped, including commit SHA and any guarded dirty-file summary

### 2. Build And Archive

If the project uses `xcodegen` or another generator, keep that command in the profile and let the script run it.

Use:

```bash
python3 "$CODEX_HOME/skills/apple-ecosystem-release-operator/scripts/apple_release_operator.py" \
  archive \
  --profile release/apple_release_profile.yaml
```

This step is responsible for:

- generator regeneration when configured
- optional shared test execution when configured
- preferring installed local harness verification commands as the first proof lane when they are available
- release archive creation with the platform-appropriate destination
- bundled/runtime preflight checks when the shipped app contains an embedded backend or helper runtime
- latest-platform capability checks when the app conditionally adopts new OS surfaces such as App Intents metadata, optional on-device model lanes, or new scene behavior
- refusing to silently ship from a mixed source-of-truth state unless the operator was explicitly told to override the guard

### 3. Upload

Use:

```bash
python3 "$CODEX_HOME/skills/apple-ecosystem-release-operator/scripts/apple_release_operator.py" \
  upload \
  --profile release/apple_release_profile.yaml \
  --internal-only
```

If upload fails, classify the failure before making claims:

- missing Bundle ID
- missing App Store Connect app record
- upload auth failure
- signing identity or provisioning gap
- upload succeeded but build is still processing
- upload partially advanced: App Store Connect or Content Delivery created a build record, but the local exporter/uploader hung or stalled afterward

### 4. Portal Sync And Tester Follow-Through

For Bundle ID, App Store Connect app record, internal groups, and tester attachment:

- use local script receipts first:

```bash
python3 "$CODEX_HOME/skills/apple-ecosystem-release-operator/scripts/apple_release_operator.py" \
  portal-sync \
  --profile release/apple_release_profile.yaml
```

- then, if the user has a live Apple session and wants the action performed, use browser automation to execute the safe steps and confirm the final state

Use browser automation only for safe operational tasks such as:

- verifying Bundle ID existence
- verifying App Store Connect app record existence
- creating or checking an internal TestFlight group
- verifying whether a tester is eligible yet
- attaching an eligible internal tester to the configured group
- filling TestFlight internal `What to Test`
- attaching a processed, App Store eligible build to an App Store version when the user explicitly asks

Do not silently automate identity-sensitive or irreversible account changes without a clear user request.

### 5. Capture Evidence

After a successful or blocked run, capture a sanitized receipt:

```bash
python3 "$CODEX_HOME/skills/apple-ecosystem-release-operator/scripts/apple_release_operator.py" \
  capture-evidence \
  --profile release/apple_release_profile.yaml \
  --output release/internal_testflight_evidence.json \
  --blocker "internal tester invite not yet accepted"
```

The evidence artifact should record:

- platform
- scheme
- bundle ID
- App Store Connect app name
- SKU
- resolved version and build
- active Xcode version and SDK line if relevant to the release
- deployment target and language-mode truth when those are part of the release contract
- archive path
- default internal TestFlight group
- proven commands if known
- current blocker state

## Portal Guardrails

- Keep portal work internal-TestFlight scoped unless the user explicitly asks for external beta or App Store release prep.
- Prefer neutral state language when a tester is invited but not yet eligible.
- Never claim an internal tester is added until the portal shows them as selectable or attached.
- Treat browser session state as ephemeral. Reconfirm current page state with a fresh snapshot before acting.
- Treat `build record exists` and `build is installable` as different truths.
- If local upload tooling hangs after Apple created the build record, report that exact split state and stop the stuck exporter rather than leaving an orphan release process running.

Read [references/portal-state-machine.md](references/portal-state-machine.md) when the portal state is unclear.

## App Store Connect Triage

When App Store Connect and TestFlight disagree, separate build truth from portal presentation before suggesting icon or asset changes.

### Icon mismatch triage

If the app icon is correct in TestFlight or on-device but the `Apps` overview still shows the placeholder icon:

1. open the app record and check whether the header icon is also stale
2. open the App Store version `Distribution` page and verify whether a build is attached
3. if no build is attached, treat that as the primary blocker before blaming the icon asset
4. if a build is attached and TestFlight already shows the real icon, describe the remaining issue as likely App Store Connect lag or presentation inconsistency

### Build attachment truth

Before claiming a build is unavailable, verify all of the following:

- `processingState` is complete or otherwise valid enough for selection
- the App Store version page actually has a chosen build saved
- the picker row is enabled, not merely visible
- the build belongs to the correct platform and app record

When the user explicitly asks you to attach the build, it is safe to use browser automation for:

- opening `Distribution`
- selecting the intended build
- saving the version
- confirming the save persisted after reload

### Disabled build picker diagnosis

If App Store Connect shows completed builds in TestFlight but disables every row in `Add Build`, inspect eligibility before escalating:

- compare build audience or release eligibility, not just processing completion
- check whether the build is effectively internal-test only versus App Store eligible
- compare candidate builds across platforms when iOS works but macOS does not
- inspect current page data or authenticated network responses when the UI does not explain the reason

Do not describe this as an icon problem once the build is proven to be internal-only or otherwise not App Store attachable.

## User-Visible Flow Verification Rule (NEW v1.3)
- For app-facing changes, package tests are necessary but insufficient release evidence.
- Require a real app-target build before claiming an Apple app fix is complete.
- When the changed behavior is user-visible, prefer one of:
  1. live flow verification from the actual app surface
  2. launched-artifact fixture/runtime verification that exercises the same flow
- Treat this as a blocker when:
  - SwiftPM passes
  - but the real Xcode target fails
  - or the packaged/launched artifact contradicts the claimed fix

## Actor-Isolation And Platform-Availability Guard (NEW v1.3)
- Apple-target release validation must catch issues that SwiftPM may miss, including:
  - actor-isolated default initializer misuse
  - platform-availability API regressions
  - target-specific build behavior that differs from package-only compilation
- When a fix introduces dependency injection or UI lifecycle changes, require app-target compilation evidence, not only package-level evidence.

## Frontmost Target Proof Rule (NEW v1.4)
- Live verification screenshots, videos, or manual receipts are only valid when they prove the intended app was frontmost and actually exercised.
- Acceptable proof includes at least one of:
  1. a screenshot or recording clearly showing the target app and the claimed flow
  2. a launched-artifact fixture run tied to the built app bundle
  3. a deterministic automation receipt that names the target bundle and action
- Do not count a generic desktop screenshot, unrelated browser window, or stale foreground app as live product verification.
- If target ownership cannot be proven, classify the evidence as `unverified_live_surface`, not as a product pass or fail.

## Unsigned Debug vs Signed Distribution Truth (NEW v1.4)
- Keep these release truths separate:
  1. unsigned Debug build truth
  2. signed Debug build truth
  3. signed Release or archive truth
  4. distribution or TestFlight truth
- Warnings about hardened runtime, deep signature checks, or signing posture on an unsigned verification build should not be mislabeled as product regressions.
- Conversely, unsigned Debug success does not prove signed archive readiness.
- Require the operator to state exactly which artifact class was verified before declaring release readiness.

## Cross-Platform Notes

The core workflow stays the same across Apple platforms, but archive destinations and target defaults vary.

Read [references/platform-notes.md](references/platform-notes.md) before adapting a profile for macOS, visionOS, iPadOS, or watchOS.

## PFEMacOS Latest-Platform Doctrine (NEW v1.1)
- For PFEMacOS modernization work, treat these as separate release truths:
  - SDK/toolchain support
  - deployment target support
  - launched-artifact behavior
  - optional provider-lane eligibility
  - App Intents metadata registration
- Xcode 26.x or later adoption must not silently raise the deployment target. The operator should explicitly compare:
  - declared deployment target in the release profile
  - generated project/build settings
  - archive metadata
- Optional Apple Intelligence or Foundation Models integration must remain an additive lane. It must never be treated as proof that the primary MLX/backend lane can be removed.
- If the app claims App Shortcuts or App Intents support, archive evidence should include whether `Metadata.appintents` was produced.
- If the app claims macOS-latest conditional UX adoption, release evidence should separate:
  - source-level availability guards
  - successful build/archive against the latest SDK
  - launched-artifact verification when feasible

## Embedded Backend And Attachment-Truth Release Doctrine (NEW v1.2)
When a shipped Apple app includes an embedded backend or document-analysis claims:
- require launched-artifact backend integrity checks, not only archive success
- verify protected chat-route readiness from the built artifact
- for attachment-first assistant claims, prefer one real uploaded-document smoke over source-only assertions

Minimum release evidence when document intelligence is in scope:
1. `xcodebuild` or archive success
2. launched-artifact backend integrity success
3. protected chat readiness success
4. one attachment-grounded turn proving the app can retrieve or verify uploaded document text, or an explicit note that this live proof was not performed

## Latest-SDK Verification Checklist (NEW v1.1)
When the project is adopting a new Xcode or macOS SDK line:
1. verify the active Xcode version locally
2. verify the deployment target remained unchanged unless explicitly approved
3. run project-target build on the active machine
4. run archive smoke, not only Debug build
5. capture whether App Intents metadata extraction succeeded if intents are present
6. capture whether optional provider lanes are:
   - unsupported
   - supported but disabled
   - supported but not ready
   - ready
7. avoid compressing those states into one generic `available` verdict

## Outputs

This skill should leave behind:

- a reusable project release profile
- a truthful evidence artifact for the current release state
- a clear distinction between completed automation, human checkpoints, and blocked states

## Release Source-State Doctrine (NEW)
- Release automation should capture:
  - commit SHA
  - active branch
  - source-of-truth ref
  - guarded dirty-file summary
  - guarded diff summary versus source-of-truth
- Default behavior should fail closed when guarded release files differ from the intended source-of-truth, unless the operator explicitly overrides that protection.

## Hung Export / Upload Classification
When `xcodebuild -exportArchive` or equivalent upload tooling appears stuck:
1. inspect the current `.xcdistributionlogs`
2. determine whether Apple already issued a build record or build ID
3. determine whether logs are still moving
4. if local export is stalled with no progress, terminate the stuck local exporter and report the split truth:
   - archive succeeded
   - Apple build record created or not
   - upload fully completed or not
   - portal installability still blocked or not

Never compress that situation into a generic `upload failed` or `upload succeeded` claim.

## CI Verification Build Doctrine (NEW)
- Hosted Apple CI runners should not be expected to have project-specific development certificates installed.
- If the CI job's purpose is verification rather than distributable artifact signing, prefer an unsigned build configuration for Xcode target validation.
- Typical verification-build overrides include:
  - `CODE_SIGNING_ALLOWED=NO`
  - `CODE_SIGNING_REQUIRED=NO`
  - `CODE_SIGN_IDENTITY=""`
- Keep this separate from archive or release signing flows:
  - CI verification build proves structural/build correctness
  - archive/export/upload steps still require the real signing posture needed for TestFlight or App Store delivery
- If CI is failing only because the hosted runner lacks a signing identity, classify that as a verification-configuration issue, not a product-code regression.

## Source-of-Truth Branch Doctrine (NEW)
- Release and GitHub follow-through should capture whether the validated release commit lives on:
  - a dedicated feature/release branch
  - `main`
  - both
- When the user asks for a dedicated branch, verify the active branch before committing or pushing.
- If a validated release commit lands on `main` unexpectedly but truthfully, report that exact state and then reconcile branch pointers instead of pretending the branch-only flow happened cleanly.
