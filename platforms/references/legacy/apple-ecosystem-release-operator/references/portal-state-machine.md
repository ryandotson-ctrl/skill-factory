# Portal State Machine

Use these states when reasoning about App Store Connect and internal TestFlight.

## Bundle And App Record

- `missing_bundle_id`: Apple Developer identifier does not exist yet.
- `bundle_id_ready`: Bundle ID exists and matches the profile.
- `missing_app_record`: App Store Connect app record does not exist yet for the bundle.
- `app_record_ready`: App Store Connect app record exists.

## Build Lifecycle

- `archive_missing`: No release archive available yet.
- `uploaded_processing`: Upload finished, App Store Connect is still processing the build.
- `ready_to_submit`: Build is visible and ready for internal submission metadata or group attachment.
- `ready_to_test`: Internal group is attached and the build is installable for eligible testers.

## Internal Tester Lifecycle

- `user_not_invited`: No App Store Connect invite exists.
- `invited_unaccepted`: Invite was sent but the user has not accepted yet, so they are not eligible as an internal tester.
- `eligible_unattached`: User accepted the invite and is selectable, but is not yet attached to the internal group.
- `attached`: User is attached to the internal group.

## Safe Automation Boundary

Safe browser automation:

- verify existence of Bundle ID, app record, build, and group
- create or confirm internal group
- fill internal `What to Test`
- attach eligible testers

Human checkpoint required:

- ambiguous identity or role changes
- unclear provider or team selection
- actions that would expand scope beyond internal TestFlight
