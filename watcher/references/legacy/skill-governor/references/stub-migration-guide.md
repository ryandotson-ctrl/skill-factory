# Stub Migration Guide

This phase does not convert old skills into stubs. It installs the new core skills first and keeps the old skills intact.

Future stub phase:
1. For each legacy skill, copy detailed SOP content into the owning core skill reference tree.
2. Replace the legacy `SKILL.md` body with a short compatibility redirect.
3. Preserve the legacy `name`, `description`, `manifest.json`, `manifest.v2.json`, and trigger aliases.
4. Add a reference pointer to the owning core skill.
5. Run The Watcher, Cataloger, Portability Guardian snapshot, and regression gate.
6. Keep compatibility stubs for at least one release cycle before any archival.

Required stub text:
```md
# <legacy-skill>

This legacy skill is preserved as a compatibility entrypoint.

Use `<core-skill>` for the lean routing surface.

Load migrated references from `<core-skill>/references/` when deeper historical behavior is needed.
```
