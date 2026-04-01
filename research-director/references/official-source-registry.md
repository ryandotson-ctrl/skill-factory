# Official Source Registry

Use this registry to start every research sweep. Prefer these sources before secondary commentary.

## Core Source Classes

### Vendor Docs and Release Notes
- Official product docs
- Official release notes and changelogs
- Official API references
- Official migration guides

### Project-Maintainer Sources
- Canonical repository README and docs
- Maintainer-authored upgrade notes
- GitHub releases or tags for the official project

### Package and Release Registries
- PyPI for Python packages
- npm for JavaScript and TypeScript packages
- GitHub releases for source-of-truth release timestamps
- Language-specific registries when they are the canonical release surface

### Standards and Specifications
- IETF RFCs
- W3C / WHATWG specs
- OpenTelemetry specifications
- POSIX or platform vendor specifications when relevant

### Security and Stability Sources
- GitHub Security Advisories
- NVD or vendor advisories
- Vendor status pages when outage or reliability claims matter

## Research Hygiene
For each major claim, capture:
- source URL
- title
- publisher
- published or updated date
- version or release tag (if provided)
- why it matters to the active project goal

## Default Query Families
Use these query families in every sweep:
1. latest release and migration guidance for the relevant stack
2. compatibility notes and breaking changes
3. official limits, pricing, or entitlement changes
4. registry truth for the exact dependencies under discussion
5. security or reliability advisories that change the decision

## Optional Domain Packs
If the task is domain-specific, load the matching pack from `optional-domain-profiles.md` instead of hard-coding niche sources into the default path.
