# Target Behavior

## Diagnose

Prints:
- project or workspace selection
- scheme defaults
- platform
- destination
- detected toolchain commands

## Build And Test

Rules:
- warnings are treated as errors
- strict concurrency stays enabled
- result bundles and logs are captured under `build/logs/<agent>`
- simulator-backed platforms resolve a current destination dynamically

## Run

- `macos`: launches the built app bundle directly
- `ios` and `ipados`: installs and launches on a resolved simulator
- `visionos` and `watchos`: build and test remain first-class; simulator run is best-effort and may still require local tuning

## Agent Verify

`agent-verify` is the preferred local proof target for Apple repos that install this harness.
It must run build then test with the same isolated cache and DerivedData contract.
