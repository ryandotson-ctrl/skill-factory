#!/usr/bin/env python3
"""Render a portable PDF from a JSON specification."""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Sequence


def _ascii_safe(text: Any) -> str:
    raw = str(text or "")
    table = str.maketrans(
        {
            "\u2018": "'",
            "\u2019": "'",
            "\u201c": '"',
            "\u201d": '"',
            "\u2013": "-",
            "\u2014": "-",
            "\u2212": "-",
            "\u2022": "-",
            "\u00a0": " ",
            "\u2007": " ",
            "\u202f": " ",
            "\u200b": "",
            "\u200c": "",
            "\u200d": "",
            "\ufeff": "",
        }
    )
    raw = raw.translate(table)
    raw = unicodedata.normalize("NFKD", raw)

    out: List[str] = []
    for ch in raw:
        code = ord(ch)
        if ch in ("\n", "\r", "\t"):
            out.append(" ")
            continue
        if code < 32:
            continue
        if unicodedata.combining(ch):
            continue
        out.append(ch if code <= 126 else " ")
    return re.sub(r"\s+", " ", "".join(out)).strip()


def _normalize_ratios(ratios: Sequence[float], columns: int) -> List[float]:
    if columns <= 0:
        return []
    values: List[float] = []
    for value in list(ratios or [])[:columns]:
        try:
            values.append(max(0.0, float(value)))
        except Exception:
            values.append(0.0)
    while len(values) < columns:
        values.append(1.0)
    total = sum(values)
    if total <= 0:
        return [1.0 / columns] * columns
    return [value / total for value in values]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render a portable PDF from JSON spec")
    parser.add_argument("--spec", required=True, help="Input JSON spec path")
    parser.add_argument("--output", required=True, help="Output PDF path")
    parser.add_argument("--font-regular", default="", help="Optional TTF regular font path")
    parser.add_argument("--font-bold", default="", help="Optional TTF bold font path")
    parser.add_argument(
        "--text-mode",
        choices=["ascii-safe", "unicode"],
        default="ascii-safe",
        help="ascii-safe avoids tofu glyphs with core fonts; unicode requires valid TTF fonts",
    )
    return parser.parse_args()


def render_pdf(spec: Dict[str, Any], output_path: Path, font_regular: str, font_bold: str, text_mode: str) -> None:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, letter, landscape, portrait
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.utils import simpleSplit
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import LongTable, Paragraph, SimpleDocTemplate, Spacer

    meta = spec.get("meta") if isinstance(spec.get("meta"), dict) else {}
    theme = spec.get("theme") if isinstance(spec.get("theme"), dict) else {}
    sections = spec.get("sections") if isinstance(spec.get("sections"), list) else []

    page_size_name = str(meta.get("page_size") or "letter").lower()
    orientation = str(meta.get("orientation") or "landscape").lower()
    base_size = A4 if page_size_name == "a4" else letter
    page_size = landscape(base_size) if orientation == "landscape" else portrait(base_size)

    use_unicode_fonts = bool(font_regular and font_bold and text_mode == "unicode")
    font_name = "Helvetica"
    font_name_bold = "Helvetica-Bold"
    if use_unicode_fonts:
        pdfmetrics.registerFont(TTFont("PortableRegular", str(Path(font_regular).expanduser())))
        pdfmetrics.registerFont(TTFont("PortableBold", str(Path(font_bold).expanduser())))
        font_name = "PortableRegular"
        font_name_bold = "PortableBold"

    def norm(text: Any) -> str:
        return str(text or "").strip() if use_unicode_fonts else _ascii_safe(text)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=page_size,
        leftMargin=28,
        rightMargin=28,
        topMargin=36,
        bottomMargin=28,
        title=norm(meta.get("title") or "Portable PDF"),
        author=norm(meta.get("author") or "PDF Skill"),
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "TitleStyle",
        parent=styles["Title"],
        fontName=font_name_bold,
        fontSize=20,
        leading=24,
        textColor=colors.HexColor(str(theme.get("text_color") or "#0F172A")),
        spaceAfter=6,
    )
    subtitle_style = ParagraphStyle(
        "SubtitleStyle",
        parent=styles["Normal"],
        fontName=font_name,
        fontSize=9.2,
        leading=12,
        textColor=colors.HexColor("#334155"),
        spaceAfter=10,
    )
    section_style = ParagraphStyle(
        "SectionStyle",
        parent=styles["Heading2"],
        fontName=font_name_bold,
        fontSize=12.5,
        leading=15,
        textColor=colors.HexColor(str(theme.get("text_color") or "#0F172A")),
        spaceBefore=10,
        spaceAfter=4,
    )
    body_style = ParagraphStyle(
        "BodyStyle",
        parent=styles["Normal"],
        fontName=font_name,
        fontSize=9,
        leading=11.6,
        textColor=colors.HexColor(str(theme.get("text_color") or "#0F172A")),
    )
    cell_style = ParagraphStyle(
        "CellStyle",
        parent=styles["Normal"],
        fontName=font_name,
        fontSize=8.0,
        leading=10.2,
        textColor=colors.HexColor(str(theme.get("text_color") or "#0F172A")),
        wordWrap="CJK",
        splitLongWords=1,
    )
    cell_header_style = ParagraphStyle(
        "CellHeaderStyle",
        parent=cell_style,
        fontName=font_name_bold,
        textColor=colors.white,
        alignment=1,
    )

    def para(value: Any, style: ParagraphStyle) -> Paragraph:
        safe = norm(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        return Paragraph(safe, style)

    story: List[Any] = []
    story.append(para(meta.get("title") or "Portable PDF Report", title_style))
    subtitle = meta.get("subtitle")
    if subtitle:
        story.append(para(subtitle, subtitle_style))

    for section in sections:
        if not isinstance(section, dict):
            continue
        heading = section.get("heading")
        if heading:
            story.append(para(heading, section_style))

        paragraphs = section.get("paragraphs")
        if isinstance(paragraphs, list):
            for text in paragraphs:
                story.append(para(text, body_style))
                story.append(Spacer(1, 3))

        table = section.get("table")
        if isinstance(table, dict):
            headers = table.get("headers") if isinstance(table.get("headers"), list) else []
            rows = table.get("rows") if isinstance(table.get("rows"), list) else []
            if headers:
                column_count = len(headers)
                ratios = _normalize_ratios(table.get("column_widths_ratio") or [], column_count)
                col_widths = [doc.width * ratio for ratio in ratios]
                data: List[List[Any]] = [[para(header, cell_header_style) for header in headers]]
                for row in rows:
                    if isinstance(row, list):
                        padded = row[:column_count] + ([""] * max(0, column_count - len(row)))
                    else:
                        padded = [str(row)] + ([""] * max(0, column_count - 1))
                    data.append([para(cell, cell_style) for cell in padded])

                long_table = LongTable(data, colWidths=col_widths, repeatRows=1, splitByRow=1)
                long_table.setStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(str(theme.get("primary_color") or "#0B3A6E"))),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                        ("FONTNAME", (0, 0), (-1, 0), font_name_bold),
                        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#CBD5E1")),
                        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor(str(theme.get("stripe_color") or "#F8FAFC"))]),
                        ("LEFTPADDING", (0, 0), (-1, -1), 4),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                        ("TOPPADDING", (0, 0), (-1, -1), 4),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ]
                )
                story.append(Spacer(1, 2))
                story.append(long_table)
                story.append(Spacer(1, 8))

    def draw_footer(canvas: Any, document: Any) -> None:
        canvas.saveState()
        canvas.setFont(font_name, 8)
        canvas.setFillColor(colors.HexColor("#64748B"))
        left_text = norm(meta.get("title") or "Portable PDF Report")
        # Keep footer bounded to avoid overflow.
        max_chars = 80
        if len(left_text) > max_chars:
            left_text = left_text[: max_chars - 3] + "..."
        canvas.drawString(document.leftMargin, 13, left_text)
        canvas.drawRightString(document.pagesize[0] - document.rightMargin, 13, f"Page {canvas.getPageNumber()}")
        canvas.restoreState()

    doc.build(story, onFirstPage=draw_footer, onLaterPages=draw_footer)


def main() -> int:
    args = parse_args()
    spec_path = Path(args.spec).expanduser()
    out_path = Path(args.output).expanduser()
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    render_pdf(spec, out_path, args.font_regular, args.font_bold, args.text_mode)
    print(f"Rendered PDF: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
