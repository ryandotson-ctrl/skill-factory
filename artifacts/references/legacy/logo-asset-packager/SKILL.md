---
name: logo-asset-packager
description: Converts a supplied logo or brand image into faithful production assets without redesign by default, including background separation, vector-master handoff, monochrome variants, and Apple-ready app icon exports.
---

# Logo Asset Packager

Turns a user-supplied logo, icon, or brand image into reusable production assets while preserving the original mark unless the user explicitly asks for a new interpretation.

## When to use
- The user provides a logo or brand image and wants it cleaned up, upscaled, isolated, vectorized, or packaged.
- The task includes transparent exports, monochrome variants, App Store icons, Xcode asset catalogs, or brand handoff files.
- The user says things like "keep exactly this image," "same logo," "do not redesign it," or "make this App Store ready."

## Default stance
- The supplied asset is the source of truth.
- Preservation beats reinvention.
- Do not redraw, restyle, or "improve" the mark unless the user explicitly asks for reinterpretation.
- Do not claim something is fully vector if parts are still raster-derived or approximated.

If the user explicitly wants a new visual direction, concept exploration, or generative edits, hand off the creative portion to `$imagegen`. Do not use generative image edits as the default path for exact-source preservation because drift is likely.

## Decision ladder
Choose the lightest operation that satisfies the request:

1. `preserve`
   Use the original art directly, with only export-safe framing or padding changes.
2. `extract`
   Separate the mark from its background and clean edges without changing composition.
3. `restore`
   Upscale, denoise, or rebalance contrast while preserving geometry and lighting intent.
4. `vectorize`
   Rebuild the supplied geometry as vector shapes as faithfully as possible.
5. `hybrid`
   Use a vector master for the stable geometry and preserve raster effects only where exact reproduction requires it.
6. `redesign`
   Only when the user explicitly asks for a new interpretation.

## Workflow
### 1. Intake and invariants
- Locate the actual source file in the workspace when available. Do not rely on a chat thumbnail if exact preservation matters.
- Record the invariants before editing: silhouette, perspective, spacing, line weights, internal gaps, glow/core treatment, color family, and background behavior.
- Separate asset goals:
  - brand-mark reuse
  - app/store icon packaging
  - marketing exports
  - vector source of truth

### 2. Classify the source
- Decide whether the job is primarily preserve, extract, restore, vectorize, or hybrid.
- If the source is low-resolution or JPEG-compressed, preserve the original geometry first and be explicit about any limits in perfect extraction.
- If the user asks for "real vector," rebuild curves faithfully and note whether visual effects remain vector-safe or require a hybrid fallback.

### 3. Build source-of-truth masters
- Create one canonical transparent brand-mark master.
- Create one square opaque icon master for app icon use.
- Create monochrome variants only if they remain truthful to the supplied mark.
- Create a vector master when feasible:
  - prefer SVG for editable source
  - keep naming explicit if it is hybrid or approximate

### 4. Export production assets
- Transparent mark: high-resolution PNG with clean alpha.
- Monochrome variants: light, dark, or silver only when requested or obviously useful.
- App icon master: opaque square canvas, centered, padded safely, no pre-rounded corners.
- Apple exports: generate the PNG sizes needed by `AppIcon` asset catalogs for iPhone, iPad, macOS, and visionOS targets in the active repo.
- visionOS: when layered treatment is requested, split background, reactor/body, and core into separate source layers.

### 5. Truth rules for Apple packaging
- Apple app icons are packaged as raster assets in Xcode asset catalogs even when the source master is vector.
- Keep the vector master as source of truth, then export the required PNG sizes from it.
- Do not introduce transparency in the app icon canvas unless the target format explicitly supports it.
- Do not round corners manually; let the platform mask them.

### 6. QA before handoff
Always perform and report:
- Source fidelity check: compare the new master against the supplied image side by side, and prefer overlay checks when tooling allows.
- Small-size legibility check at representative sizes such as 16, 29, 40, 60, 128, 512, and 1024.
- Transparency check: confirm the standalone brand mark has real alpha.
- Opaque icon check: confirm app icon masters remain fully opaque.
- Packaging check: confirm target asset catalog names match the project contract, typically `AppIcon`.

### 7. Handoff
Deliver:
- paths to the canonical source masters
- paths to transparent and monochrome exports
- the vector source path
- the Apple asset catalog paths
- a short truth note describing what is exact, what is approximated, and any unverified runtime previews

## Guardrails
- Never claim an extraction is perfect if JPEG artifacts or glow spill remain.
- Never drift from the original geometry just to make the mark feel more modern or polished.
- Never substitute a fresh illustration when the user asked to preserve the supplied image.
- Never confuse brand-source assets with platform packaging outputs.
- Never skip small-size review; logos that work at 2048 can fail at 16.

## Minimal outputs
For most requests, the useful minimum is:
- one transparent brand-mark master
- one opaque square icon master
- one vector source master or an explicit note that only a hybrid approximation is possible
- one Apple-ready `AppIcon` export set if the repo contains Apple targets
