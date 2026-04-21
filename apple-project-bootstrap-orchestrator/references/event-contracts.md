# Event Contracts

## Owned Ingress

### `skill:apple-project-bootstrap-orchestrator:requested`
- purpose: direct request to bootstrap or adopt an Apple project
- minimum payload:
  - `project_mode`
  - `project_root` optional
  - `platform` optional
  - `ui` optional

### `apple:project_bootstrap_requested`
- purpose: scaffold a new generator-backed Apple app and optional support tooling
- minimum payload:
  - `project_mode: new`
  - `platform`
  - `ui`

### `apple:project_adoption_requested`
- purpose: adopt an existing Apple repo without regenerating app sources
- minimum payload:
  - `project_mode: adopt`
  - `project_root`

### `apple:project_support_install_requested`
- purpose: install harness, onboarding, task templates, or release profile support into an existing repo
- minimum payload:
  - `project_root`
  - `support_targets[]`

## Emitted Outputs

### `apple:project_bootstrap_receipt`
- producer role: `bootstrap_receipt`
- payload summary:
  - `mode`
  - `platform`
  - `ui`
  - `project_root`
  - `profile`
  - `installed_support[]`
  - `next_commands[]`

### `apple:project_adoption_receipt`
- producer role: `adoption_receipt`
- payload summary:
  - `mode`
  - `project_root`
  - `installed_support[]`
  - `skipped_actions[]`
  - `next_commands[]`

### `apple:project_support_install_receipt`
- producer role: `support_install_receipt`
- payload summary:
  - `project_root`
  - `support_targets[]`
  - `next_commands[]`

### `apple_project_bootstrap_orchestrator_activity`
- producer role: `bootstrap_activity`
- purpose: lightweight routing and status signal for broader Apple project setup activity
