# Mode Contracts

## Supported Modes

### `new_project`
- scaffolds a generator-backed Apple app template
- may run the configured generator command
- may install the Xcode build harness
- may install local task templates
- may install onboarding fragments
- may write a release-profile skeleton

### `adopt_existing`
- does not regenerate app sources
- installs optional tooling only
- can refresh onboarding fragments and release profiles

## Primary Flags

- `--project-mode new|adopt`
- `--name`
- `--bundle-id`
- `--platform ios|ipados|macos|visionos|watchos`
- `--ui swiftui|uikit|appkit`
- `--output`
- `--generator-command "<cmd>"`
- `--profile generic|pfe`
- `--with-build-harness | --skip-build-harness`
- `--with-task-templates | --skip-task-templates`
- `--with-onboarding | --skip-onboarding`
- `--with-release-profile | --skip-release-profile`
- `--git-init auto|never`
- `--git-commit prompt|always|never`
- `--dry-run`
- `--no-prompt`

## Platform And UI Matrix

- `ios`: `swiftui`, `uikit`
- `ipados`: `swiftui`, `uikit`
- `macos`: `swiftui`, `appkit`
- `visionos`: `swiftui`
- `watchos`: `swiftui`

## Output Expectations

`BootstrapReceiptV1`
- `mode`
- `platform`
- `ui`
- `project_root`
- `generator_command`
- `build_harness_installed`
- `task_templates_installed`
- `onboarding_installed`
- `release_profile_written`
- `git_action`
- `next_commands[]`

## Dry-Run Behavior

Dry runs must:
- print every intended action
- never mutate the target project
- keep generator and git commands visible
- show optional support installs separately from scaffolding
