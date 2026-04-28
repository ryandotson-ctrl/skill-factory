# Stub Migration Guide

This phase prepares compatibility stubs but does not replace mature legacy `SKILL.md` files yet. The behavior switch should happen only after the 12-core layer, legacy archives, manifests, and Pulse Bus aliases validate cleanly.

Future stub phase:
1. Confirm the legacy folder was copied to `<core-skill>/references/legacy/<legacy-skill>/`.
2. Confirm `source-checksum.json` exists for the copied legacy folder.
3. Replace the legacy `SKILL.md` body with a short compatibility redirect.
4. Preserve the legacy `name`, `description`, `manifest.json`, `manifest.v2.json`, and trigger aliases.
5. Add alias manifest inputs with `route_mode: "alias"` and `target_skill: "<core-skill>"`.
6. Run The Watcher, Portability Guardian snapshot, manifest parsing, and regression gate.
7. Keep compatibility stubs for at least one release cycle before archival.

Required stub text:
```md
---
name: <legacy-skill-name>
description: Compatibility entrypoint for legacy <legacy-skill-name>; routes to <core-skill-name> while preserving historical references.
---

# <legacy-skill-name>

Purpose: Preserve the old trigger while routing work to <core-skill-name>.

Capabilities:
- route legacy invocations to <core-skill-name>
- preserve old trigger aliases
- keep old manifests and event contracts stable
- point to migrated references
- avoid duplicate active behavior

Pulse Bus awareness: <core-skill-name>, watcher.

Vibe: compatibility-only, quiet, and non-authoritative.

Load relevant reference files from /references/ only when the situation requires deeper knowledge.

Legacy details were migrated to:
`/<core-skill-name>/references/legacy/<legacy-skill-name>/`
```
