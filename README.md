# Skill Factory

This repository is the portable source mirror of the current Codex skill ecosystem from `~/.codex/skills`.

It includes the broader skill control plane as well as the specialist skills themselves:
- standard global skills
- hidden system skills under `.system/`
- runtime bundle skills under `codex-primary-runtime/`
- manifests, references, scripts, assets, and `agents/openai.yaml` metadata
- Pulse Bus routing contracts and ecosystem-governance files

Current ecosystem snapshot:
- `114` unique skills
- `114` Pulse Bus active skills
- publication mirror health: aligned with Codex across `110` shared exported skills
- current ecosystem intelligence is managed by `The Watcher` (`skill_director`)

This mirror intentionally excludes local runtime residue so the GitHub copy stays portable and reusable:
- generated reports
- wisdom ledgers
- transient `_generated` state
- Python cache files
- local backup directories

In short: this repo is the source-of-truth GitHub mirror for the latest portable skill ecosystem, not a dump of machine-local state.
