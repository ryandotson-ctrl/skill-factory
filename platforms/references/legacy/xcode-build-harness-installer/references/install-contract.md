# Install Contract

## Primary Flags

- `--project-dir PATH`
- `--app-name NAME`
- `--platform ios|ipados|macos|visionos|watchos`
- `--sim-name NAME`
- `--namespace NAME`
- `--mode install|upgrade`
- `--dry-run`

## Install Outputs

- `Makefile` or `Makefile.<namespace>`
- `scripts/` or `scripts/<namespace>/`
- no hidden global state
- all build artifacts isolated under `build/`

## Isolation Layout

- `build/DerivedData/<agent>`
- `build/logs/<agent>`
- `build/cache/<agent>`
- `build/tmp/<agent>`
- `build/home/<agent>`

## Dry Run Expectations

Dry runs must print:
- target makefile path
- target scripts directory
- platform and simulator defaults
- whether install or upgrade would be used
