# Skill Portability Contract v1

## Required Frontmatter Fields

Every active `SKILL.md` should include:

- `scope`: `local` or `global`
- `portability_tier`: `strict_zero_leak` (or stricter internal policy)
- `requires_env`: list of required env keys
- `project_profiles`: list of optional project profile names

## Cross-Skill Reference Contract

- Do not use path-bound references like `@[.agent/skills/<name>]`.
- Use skill-id references like `$<skill-id>`.

## Privacy Output Contract

- Do not emit absolute local `file://<redacted-local-path> links in catalogs/reports.
- Use `skills://<scope>/<skill-id>` or relative links.

## Root and Canonical Policy

- Local-only skills: canonical in `<workspace>/.agent/skills`.
- Global-only skills: canonical in `${CODEX_HOME:-~/.codex}/skills`.
- Shared skills:
  - project-coupled -> local canonical
  - general-purpose -> codex canonical
- Antigravity is a mirror/distribution root.

## Backup and Safety Policy

- Backup before any mutation.
- Exclude `_p0_backups` and `.backups` from active rewrite scope.
- Do not run destructive cleanup on archived roots unless explicitly requested.
