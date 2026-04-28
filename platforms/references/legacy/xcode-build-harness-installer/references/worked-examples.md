# Worked Examples

## Example 1: Fresh install
- request: add Apple CLI verification to an existing repo
- action: install the toolkit
- expected outcome: `make diagnose`, `make build`, `make test`, and `make agent-verify` are available

## Example 2: Upgrade existing harness
- request: refresh the toolkit without replacing app code
- action: run upgrade mode
- expected outcome: toolkit files update in place and preserve project source

## Example 3: Dry run
- request: show me what would be installed
- action: run `dry-run`
- expected outcome: no writes, clear install plan, and target-behavior summary
