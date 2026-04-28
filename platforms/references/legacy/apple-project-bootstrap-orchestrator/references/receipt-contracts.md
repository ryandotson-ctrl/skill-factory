# Receipt Contracts

## `BootstrapReceiptV1`

Use this after a `new_project` or full bootstrap run.

Required fields:
- `mode`
- `platform`
- `ui`
- `project_root`
- `profile`
- `generator_command`
- `build_harness_installed`
- `task_templates_installed`
- `onboarding_installed`
- `release_profile_written`
- `git_action`
- `next_commands[]`

## `SupportInstallReceiptV1`

Use this after `adopt_existing` when the flow primarily installs support tooling instead of generating sources.

Required fields:
- `mode`
- `project_root`
- `profile`
- `build_harness_installed`
- `task_templates_installed`
- `onboarding_installed`
- `release_profile_written`
- `skipped_actions[]`
- `next_commands[]`

## `DoctorReportV1`

Use this before bootstrap or adoption when environment readiness matters.

Required fields:
- `project_mode`
- `xcodebuild_available`
- `xcodegen_available`
- `jq_available`
- `xcbeautify_available`
- `warnings[]`

Interpretation rules:
- missing `xcbeautify` is advisory, not a blocker
- missing `xcodebuild`, `xcodegen`, or `jq` should be treated as action-blocking for the affected mode
