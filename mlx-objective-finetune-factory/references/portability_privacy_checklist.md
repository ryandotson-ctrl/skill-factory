# Portability + Privacy Checklist

Use this checklist before sharing artifacts or skills.

## Redaction
1. Replace user home paths:
- `/Users/<name>` -> `/Users/<user>`
- `/home/<name>` -> `/home/<user>`
2. Remove or redact:
- API keys, tokens, secrets, passwords
- emails and phone numbers
- local hostnames and unique machine IDs
3. Truncate private content payloads while preserving structure.

## Portability
1. Use placeholders or env vars, not machine-specific paths.
2. Parameterize:
- repo root
- artifact root
- model store root
- sandbox root
3. Keep project-specific behavior in optional profile blocks.

## Truthfulness
1. Never claim filesystem success without same-run tool evidence.
2. Require post-action verification for create/move/delete flows.
3. If intent is ambiguous ("clean up"), ask for explicit action.

## Evaluation
1. Gate on objective metrics before declaring success.
2. Record retries and failures with timestamps in run log.
3. Include reproducible commands for retrain + reinstall.
