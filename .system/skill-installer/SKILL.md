---
name: skill-installer
description: Install Codex skills into $CODEX_HOME/skills from a curated list or a
  GitHub repo path. Use when a user asks to list installable skills, install a curated
  skill, or install a skill from another repo (including private repos).
metadata:
  version: 1.1.0
  short-description: Install curated skills from openai/skills or other repos
  scope: global
  portability_tier: strict_zero_leak
  requires_env: []
  project_profiles: []
---

# Skill Installer

Helps install skills. By default these are from https://github.com/openai/skills/tree/main/skills/.curated, but users can also provide other locations.

Use the helper scripts based on the task:
- List curated skills when the user asks what is available, or if the user uses this skill without specifying what to do.
- List skills from any repo path when the user wants a non-curated source inventory.
- Install from the curated list when the user provides a skill name.
- Install from another repo when the user provides a GitHub repo/path (including private repos).

Install skills with the helper scripts.

## Communication

When listing curated skills, output approximately as follows, depending on the context of the user's request:
"""
Skills from {repo}:
1. skill-1
2. skill-2 (already installed)
3. ...
Which ones would you like installed?
"""

After installing a skill, tell the user: "Restart Codex to pick up new skills."

Also surface the post-install health summary:
- validator result (when `quick_validate.py` is available)
- manifest presence (`manifest.json`, `manifest.v2.json`)
- interface sidecar presence (`agents/openai.yaml`)
- whether the installed skill is likely `full`, `partial`, or `manual-only` from a Pulse Bus perspective

## Scripts

All of these scripts use network, so when running in the sandbox, request escalation when running them.

- `scripts/list-curated-skills.py` (prints curated list with installed annotations)
- `scripts/list-curated-skills.py --format json`
- `scripts/list-skills.py --path skills/.system` (lists any repo path, not just `.curated`)
- `scripts/install-skill-from-github.py --repo <owner>/<repo> --path <path/to/skill> [<path/to/skill> ...]`
- `scripts/install-skill-from-github.py --url https://github.com/<owner>/<repo>/tree/<ref>/<path>`

## Behavior and Options

- Defaults to direct download for public GitHub repos.
- If download fails with auth/permission errors, falls back to git sparse checkout.
- Aborts if the destination skill directory already exists.
- Installs into `$CODEX_HOME/skills/<skill-name>` (defaults to `~/.codex/skills`).
- Multiple `--path` values install multiple skills in one run, each named from the path basename unless `--name` is supplied.
- Options: `--ref <ref>` (default `main`), `--dest <path>`, `--method auto|download|git`.

## Notes

- Curated listing is fetched from `https://github.com/openai/skills/tree/main/skills/.curated` via the GitHub API. If it is unavailable, explain the error and exit.
- Private GitHub repos can be accessed via existing git credentials or optional `GITHUB_TOKEN`/`GH_TOKEN` for download.
- Git fallback tries HTTPS first, then SSH.
- The skills at https://github.com/openai/skills/tree/main/skills/.system are preinstalled, so no need to help users install those. If they ask, just explain this. If they insist, you can download and overwrite.
- Installed annotations come from `$CODEX_HOME/skills`.
- Installation should stay additive and non-destructive. If a fetched skill lacks manifest or interface metadata, install it but clearly say that Pulse Bus or UI participation may be partial until the skill is upgraded.
