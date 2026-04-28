# Skill Factory

This repository is the portable source mirror of the current Codex skill ecosystem from `~/.codex/skills`.

It includes the broader skill control plane as well as the specialist skills themselves:
- 12 active lean core skills
- no top-level legacy skill directories in the active Codex, Antigravity, or Agents app roots
- verbatim legacy archives under each core skill's `references/legacy/` tree
- hidden system skills under `.system/`
- manifests, references, scripts, assets, and `agents/openai.yaml` metadata
- Pulse Bus routing contracts and ecosystem-governance files

Current ecosystem snapshot:
- `12` active core skills in the Codex app root
- `12` active core skills in the Antigravity app root
- `0` active legacy skills in the Agents app root
- `5` hidden system support skills preserved under `.system/`
- `128` legacy skill archives preserved under core `references/legacy/` folders
- `145` total `SKILL.md` files in this mirror, including archived legacy references
- current ecosystem intelligence is managed by the active `watcher` core

Migration status:
- The 12-core layer is now the only app-visible exported skill surface.
- Legacy wisdom is copied verbatim into core `references/legacy/` folders with checksums.
- Legacy top-level skills were removed from active app roots so models do not invoke them directly.
- Hidden `.system` skills remain available as support tooling, not domain routers.

This mirror intentionally excludes local runtime residue so the GitHub copy stays portable and reusable:
- generated reports
- wisdom ledgers
- transient `_generated` state
- Python cache files
- local backup directories

In short: this repo is the source-of-truth GitHub mirror for the latest portable skill ecosystem, with a 12-core active routing surface and preserved legacy wisdom kept out of the active Codex app path.
