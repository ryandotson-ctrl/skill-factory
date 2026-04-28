# Skill Factory

This repository is the portable source mirror of the current Codex skill ecosystem from `~/.codex/skills`.

It includes the broader skill control plane as well as the specialist skills themselves:
- 12 lean core consolidation targets
- existing legacy skill directories preserved in place
- verbatim legacy archives under each core skill's `references/legacy/` tree
- hidden system skills under `.system/`
- runtime bundle skills under `codex-primary-runtime/`
- manifests, references, scripts, assets, and `agents/openai.yaml` metadata
- Pulse Bus routing contracts and ecosystem-governance files

Current ecosystem snapshot:
- `12` target core skills for the lean routing surface
- `124` top-level exported skill directories with `SKILL.md` in this mirror
- `7` hidden/system or runtime bundle skill directories preserved in this mirror
- `136` unique skills observed by The Watcher across Codex, Antigravity, Agents, and this mirror after the 12-core preservation pass
- `130` Pulse Bus active skills observed by The Watcher before mature legacy stubbing
- publication mirror health: aligned with Codex across `128` shared exported skills
- current ecosystem intelligence is managed by `The Watcher` (`skill_director`) while the new `watcher` core provides the future lean entrypoint

Migration status:
- The 12-core layer is installed additively.
- Legacy wisdom is copied verbatim into core `references/legacy/` folders with checksums.
- Compatibility stubs are prepared but not applied to mature legacy skills yet.
- No legacy skill directory has been deleted.

This mirror intentionally excludes local runtime residue so the GitHub copy stays portable and reusable:
- generated reports
- wisdom ledgers
- transient `_generated` state
- Python cache files
- local backup directories

In short: this repo is the source-of-truth GitHub mirror for the latest portable skill ecosystem, with a 12-core consolidation layer and preserved legacy wisdom.
