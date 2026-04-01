# Apple Release Profile Schema

Use one profile per shipped target, usually at `release/apple_release_profile.yaml`.

## Required Fields

```yaml
platform: ios
project_root: ..
xcode_project_or_workspace: PFEAppleApps.xcodeproj
scheme: PFEPhone
bundle_id: com.example.phone
apple_team_id: ABC1234567
version_source:
  path: project.yml
  target: PFEPhone
  key: MARKETING_VERSION
build_number_source:
  path: project.yml
  target: PFEPhone
  key: CURRENT_PROJECT_VERSION
archive_path: build/TestFlight/PFEPhone.xcarchive
default_testflight_group: Internal
asc_app_name: Example App
sku: example-app-ios
```

## Optional Fields

```yaml
generator_command: xcodegen generate
test_command: cd Packages/AppCore && DEVELOPER_DIR=${DEVELOPER_DIR:-/Applications/Xcode.app/Contents/Developer} xcodebuild test -scheme AppCore -destination 'platform=iOS Simulator,name=iPhone 17 Pro'
archive_destination: generic/platform=iOS
simulator_destination: platform=iOS Simulator,name=iPhone 17 Pro
export_path: build/TestFlight/export
known_proven_archive_command: ./scripts/release_phone_testflight.sh archive
known_proven_upload_command: ./scripts/release_phone_testflight.sh upload
```

## Source Rules

- Resolve `project_root` relative to the profile file.
- Resolve all other relative paths from `project_root`.
- `version_source` and `build_number_source` may point into YAML or JSON files. Prefer target-scoped keys when the file contains multiple Apple targets.
- Keep real bundle IDs, SKUs, schemes, and team IDs in the project-local profile, not in the reusable skill.

## Platform Values

Supported `platform` values:

- `ios`
- `ipados`
- `macos`
- `visionos`
- `watchos`

The script will use a default archive destination for each platform unless `archive_destination` overrides it.
