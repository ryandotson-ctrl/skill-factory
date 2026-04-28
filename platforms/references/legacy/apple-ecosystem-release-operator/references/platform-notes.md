# Platform Notes

## Shared Defaults

- Use one release profile per shipped target.
- Keep internal TestFlight work separate from external beta or App Store release work.
- Regenerate the project first when generator-backed files are the source of truth.

## Archive Destination Defaults

- `ios` and `ipados`: `generic/platform=iOS`
- `visionos`: `generic/platform=visionOS`
- `macos`: `generic/platform=macOS`
- `watchos`: `generic/platform=watchOS`

Override `archive_destination` in the release profile if the target requires a different Xcode destination.

## Common Friction Points

- Generator-backed projects drift when `project.yml` changes but the `.xcodeproj` is stale.
- Internal testers are not attachable until they accept the App Store Connect invite and become eligible.
- A successful upload is not the same as a build being ready to test.
- Local development signing may still allow archive creation while final distribution upload remains blocked.

## Portability Rules

- Keep skill instructions path-agnostic.
- Store project specifics only in the profile.
- When a project needs extra steps, prefer `generator_command` or `test_command` overrides over hardcoding project names into the skill.
