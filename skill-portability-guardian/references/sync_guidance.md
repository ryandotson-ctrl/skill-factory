# Sync Guidance

## Canonical Policy

- Canonical source for this skill: `${CODEX_HOME:-~/.codex}/skills/skill-portability-guardian`
- Antigravity and workspace-local copies are mirrors.

## Recommended Sync Steps

1. Audit current state (no changes):

```bash
python3 ${CODEX_HOME:-~/.codex}/skills/skill-portability-guardian/scripts/skill_portability_guardian.py \
  --mode audit \
  --roots codex,antigravity,local \
  --workspace-root "$(pwd)" \
  --strict-zero-leak true
```

2. Mirror the canonical skill to Antigravity when needed:

```bash
mkdir -p ~/.gemini/antigravity/skills
rsync -a --delete \
  ${CODEX_HOME:-~/.codex}/skills/skill-portability-guardian/ \
  ~/.gemini/antigravity/skills/skill-portability-guardian/
```

3. Optional: copy into project-local skills for project-embedded usage:

```bash
mkdir -p .agent/skills
rsync -a --delete \
  ${CODEX_HOME:-~/.codex}/skills/skill-portability-guardian/ \
  .agent/skills/skill-portability-guardian/
```

4. Re-run strict apply validation after any mirror operation:

```bash
python3 ${CODEX_HOME:-~/.codex}/skills/skill-portability-guardian/scripts/skill_portability_guardian.py \
  --mode apply \
  --roots codex,antigravity,local \
  --workspace-root "$(pwd)" \
  --strict-zero-leak true
```

## Safety Notes

- Backups are created automatically before any file rewrite.
- `_p0_backups` and `.backups` trees are never mutated.
- Missing roots are skipped without failing the run.
