# Tech Auditor Source Priority

## Source Order
1. Official project docs, release notes, changelogs, maintainers.
2. Official package registries (npm, PyPI, crates.io, RubyGems, Maven Central).
3. Foundation/vendor release channels (Node.js, Python.org, OpenJDK, Go, Rust, Apple Swift/Xcode channels).
4. Trusted ecosystem summaries (only when primary source is unavailable).

## Evidence Labels
- `high` + `[FACT]`: primary source with explicit release/version evidence.
- `medium` + `[INFERENCE]`: corroborated inference from multiple reliable sources.
- `low` + `[ASSUMPTION]`: incomplete/conflicting evidence; recommendation needs confirmation.

## Recency Rules
1. Use absolute dates in freshness-critical claims.
2. If source freshness is unknown, mark status as `unknown`.
3. Do not claim "latest" without a source citation.
