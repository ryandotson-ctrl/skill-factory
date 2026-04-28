# Core Skill Topology

The radical consolidation target is 12 active core skills with legacy skills preserved as source archives and future compatibility aliases.

Core skills:
- watcher
- engineering
- reliability
- security
- research
- knowledge-data
- ml
- automation
- artifacts
- ux
- platforms
- missions

Migration posture:
- The 12 core skills are the preferred lean routing surface.
- Existing legacy skill folders remain in place until the compatibility-stub phase is explicitly applied.
- Verbatim legacy copies live under `<core>/references/legacy/<legacy-id>/` with checksums.
- The Watcher remains responsible for per-skill intelligence, Pulse Bus topology, portability, and migration receipts.
- `skill_director` remains the stable Watcher implementation root until all call sites migrate safely to `watcher`.
