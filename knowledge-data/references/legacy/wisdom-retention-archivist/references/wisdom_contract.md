# Wisdom Contract

## Required Entry Fields
- `summary`: concise lesson or recommendation outcome
- `created_at`: UTC timestamp (auto-filled if missing)
- `entry_id`: stable identifier (auto-filled if missing)

## Optional Fields
- `confidence`: numeric confidence for ranking
- `evidence_refs`: list of normalized evidence references
- `tags`: list of portable tags
- `mitigations`: list of follow-up actions

## Sanitization Rules
1. Replace host/user paths with placeholders.
2. Redact tokens, API keys, emails, and phone numbers.
3. Avoid storing full private transcripts.
4. Keep entries deterministic and JSON-serializable.

## Retrieval Scoring
Score combines:
- query overlap
- recency within configurable window
- optional entry confidence

Use stable ordering by score descending.
