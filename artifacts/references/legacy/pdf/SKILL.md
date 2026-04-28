---
name: "pdf"
description: "Use when tasks involve reading, creating, or reviewing PDF files where rendering and layout matter; prefer visual checks by rendering pages (Poppler) and use Python tools such as `reportlab`, `pdfplumber`, and `pypdf` for generation and extraction."
---


# PDF Skill

## When to use
- Read or review PDF content where layout and visuals matter.
- Create PDFs programmatically with reliable formatting.
- Validate final rendering before delivery.

## Workflow
1. Prefer visual review: render PDF pages to PNGs and inspect them.
   - Use `pdftoppm` if available.
   - If unavailable, install Poppler or ask the user to review the output locally.
2. Use `reportlab` to generate PDFs when creating new documents.
3. Use `pdfplumber` (or `pypdf`) for text extraction and quick checks; do not rely on it for layout fidelity.
4. After each meaningful update, re-render pages and verify alignment, spacing, and legibility.
5. For wide analytical reports, fall back from dense tables to wrapped key-value blocks when a table would exceed the available content width.
6. Keep at least one rendered thumbnail from the latest PDF revision as visual evidence that overflow, clipping, and page-break defects were checked.

## Temp and output conventions
- Use `tmp/pdfs/` for intermediate files; delete when done.
- Write final artifacts under `output/pdf/` when working in this repo.
- Keep filenames stable and descriptive.

## Dependencies (install if missing)
Prefer `uv` for dependency management.

Python packages:
```
uv pip install reportlab pdfplumber pypdf
```
If `uv` is unavailable:
```
python3 -m pip install reportlab pdfplumber pypdf
```
System tools (for rendering):
```
# macOS (Homebrew)
brew install poppler

# Ubuntu/Debian
sudo apt-get install -y poppler-utils
```

If installation isn't possible in this environment, tell the user which dependency is missing and how to install it locally.

## Environment
No required environment variables.

## Rendering command
```
pdftoppm -png $INPUT_PDF $OUTPUT_PREFIX
```

## Quality expectations
- Maintain polished visual design: consistent typography, spacing, margins, and section hierarchy.
- Avoid rendering issues: clipped text, overlapping elements, broken tables, black squares, or unreadable glyphs.
- Charts, tables, and images must be sharp, aligned, and clearly labeled.
- Use ASCII hyphens only. Avoid U+2011 (non-breaking hyphen) and other Unicode dashes.
- Citations and references must be human-readable; never leave tool tokens or placeholder strings.

## Final checks
- Do not deliver until the latest PNG inspection shows zero visual or formatting defects.
- Confirm headers/footers, page numbering, and section transitions look polished.
- Keep intermediate files organized or remove them after final approval.

## Portable execution profile (additive)
Use parameterized roots instead of project-specific paths.

Recommended defaults:
- Temp root: `<workspace_root>/artifacts/pdf/tmp`
- Output root: `<workspace_root>/artifacts/pdf/out`
- Spec root: `<workspace_root>/artifacts/pdf/specs`

Do not hardcode usernames, home folders, or machine-specific absolute paths in reusable scripts.

## Unicode and font safety (critical)
When using ReportLab core fonts (`Helvetica`, `Times`, `Courier`), unsupported Unicode can render as black squares in macOS Preview.

Rules:
1. Do not inject zero-width break characters (`U+200B`, `U+200C`, `U+200D`) into PDF text.
2. Normalize punctuation to safe equivalents when using core fonts:
   - smart quotes -> `'` or `"`
   - em/en dash -> `-`
   - bullet glyphs -> `-`
3. If full Unicode typography is required, register a Unicode TTF family explicitly.
4. Keep an ASCII-safe fallback mode for portability.

## Table layout rules (no overflow)
1. Use `LongTable` with `repeatRows=1` for multi-page tables.
2. Compute column widths from page content width (ratios summing to 1.0).
3. Enable wrapping and long-token splitting (`wordWrap`, `splitLongWords`).
4. Keep table text size conservative (typically `8-10pt`).
5. Keep cell padding tight and consistent.
6. Validate no clipped text or horizontal spill in rendered PNG page checks.
7. If the content still does not fit after width budgeting, convert the section from a table to stacked key-value cards instead of shrinking into illegibility.

## Generic PDF generation contract
For reusable generation, use a JSON spec with:
- document metadata (title, page size, orientation)
- ordered sections
- each section containing paragraphs and/or tables
- table headers, rows, and column width ratios

Use the bundled template:
- `references/pdf_spec_template.json`

Use the bundled renderer:
- `scripts/render_portable_pdf.py`
