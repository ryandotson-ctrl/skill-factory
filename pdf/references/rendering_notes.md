# Portable PDF Rendering Notes

## Goals
1. Clean typography
2. Reliable table pagination
3. No black square glyph artifacts
4. No horizontal overflow

## Font strategy
1. Default mode: core fonts (`Helvetica` family), ASCII-safe text normalization.
2. Unicode mode: register TTF fonts explicitly and preserve wider character sets.

## Overflow strategy
1. Use page-aware widths (`doc.width`).
2. Use ratio-based column definitions in specs.
3. Wrap long cells and split long tokens when needed.
4. Re-render and inspect pages visually before final delivery.

## Cross-viewer validation
Always test in at least one native viewer (macOS Preview, Acrobat, or browser PDF viewer). Glyph behavior can differ by renderer.
