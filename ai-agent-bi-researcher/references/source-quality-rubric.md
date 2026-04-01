# Source Quality Rubric

Use this rubric to assign evidence quality before making recommendations.

## Tier Definitions
1. Tier 1 (Highest): Official documentation, release notes, standards, canonical repositories.
2. Tier 2: Maintainer-authored technical posts, project issue trackers, verified benchmark repos.
3. Tier 3: Peer-reviewed papers and reputable conference artifacts.
4. Tier 4: Reputable analyst and engineering blogs with clear citations.
5. Tier 5 (Signal only): Social posts, forum threads, and unverified commentary.

## Evidence Grades
- Grade A: At least two Tier 1 or Tier 2 sources agree, with current dates.
- Grade B: One Tier 1 or Tier 2 source plus one independent Tier 3 or Tier 4 source.
- Grade C: Tier 3 or Tier 4 only, limited corroboration.
- Grade D: Tier 5 only or conflicting evidence.

## Claim Labels
- `[FACT]`: Directly supported by cited sources.
- `[INFERENCE]`: Reasoned from multiple facts.
- `[ASSUMPTION]`: Needed to proceed when required inputs are missing.

## Freshness Rules
- Add absolute dates (YYYY-MM-DD) to all decision-critical claims.
- If the latest verified source is older than 90 days, mark as `stale`.
- If sources disagree, label the claim `conflicted` and explain both sides.
