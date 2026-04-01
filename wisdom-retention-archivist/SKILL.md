---
name: wisdom-retention-archivist
description: Maintains append-only sanitized wisdom ledgers and retrieval scoring for cross-workspace recommendation systems. Use when archiving postmortems or recommendations, generating wisdom digests, or ranking prior lessons for deterministic context recall.
version: 1.0.0
scope: global
portability_tier: strict_zero_leak
requires_env: []
project_profiles: []
---

# Wisdom Retention Archivist

## Mission
Preserve reusable operational wisdom without leaking private context, and make recall deterministic for recommendation engines.

## Core Capabilities
1. Append-only wisdom archival with sanitization and dedupe.
2. Deterministic digest generation for human review.
3. Query-aware recall scoring for recommendation pipelines.

## Trigger
Use this skill when you need to:
- archive recommendation outcomes or postmortem lessons
- update wisdom digests from JSONL ledgers
- rank prior wisdom entries for session-aware recommendation generation

## Workflow
1. Append sanitized wisdom entry:
```bash
python3 scripts/wisdom_archiver.py append \
  --ledger <ledger.jsonl> \
  --entry-json <entry.json>
```
2. Refresh digest:
```bash
python3 scripts/wisdom_archiver.py digest \
  --ledger <ledger.jsonl> \
  --digest <WISDOM_DIGEST.md>
```
3. Score recall candidates:
```bash
python3 scripts/wisdom_archiver.py score \
  --ledger <ledger.jsonl> \
  --query "context terms" \
  --limit 10
```

## Non-Negotiable Rules
1. Keep ledgers append-only.
2. Sanitize path/user/secret/PII fields before archival.
3. Never store raw private transcript dumps in wisdom entries.
4. Prefer deterministic scoring and stable output ordering.

## Event Contract
- Inputs: `skill_recommendation_emitted`, `postmortem_generated`
- Outputs: `wisdom_entry_archived`, `wisdom_digest_updated`
