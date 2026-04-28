#!/usr/bin/env python3
import argparse, json, re, os
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, ListItem, ListFlowable
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER

EM_DASH = "\u2014"
EN_DASH = "\u2013"

def sanitize_text(s: str) -> str:
    if not s: return ""
    s = str(s).replace(EM_DASH, ", ").replace(EN_DASH, "-")
    return re.sub(r"\s+", " ", s).strip()

def build_pdf(profile: dict, posting_text: str | None, out_path: str):
    doc = SimpleDocTemplate(out_path, pagesize=LETTER,
                             rightMargin=72, leftMargin=72,
                             topMargin=72, bottomMargin=72)
    
    styles = getSampleStyleSheet()
    
    # Custom Styles
    styles.add(ParagraphStyle(name='Name', parent=styles['Heading1'], fontSize=18, alignment=TA_CENTER, spaceAfter=6))
    styles.add(ParagraphStyle(name='Contact', parent=styles['Normal'], alignment=TA_CENTER, spaceAfter=20))
    styles.add(ParagraphStyle(name='SectionHeader', parent=styles['Heading2'], fontSize=12, spaceBefore=12, spaceAfter=6, borderPadding=2, borderSides='B'))
    styles.add(ParagraphStyle(name='RoleHeader', parent=styles['Normal'], fontSize=11, fontWeight='bold', spaceBefore=6))
    styles.add(ParagraphStyle(name='CustomBullet', parent=styles['Normal'], leftIndent=20, firstLineIndent=-10, spaceBefore=3))

    elements = []

    name = profile.get("name","")
    contact = profile.get("contact","")
    summary = profile.get("summary","")
    skills = profile.get("skills", [])
    experience = profile.get("experience", [])
    education = profile.get("education", [])

    # Skills reordering if posting text is provided
    if posting_text and isinstance(skills, list):
        pt = posting_text.lower()
        def score(skill):
            s = str(skill).lower()
            return 1 if s in pt else 0
        skills = sorted(skills, key=score, reverse=True)

    # Header
    if name:
        elements.append(Paragraph(f"<b>{sanitize_text(name)}</b>", styles['Name']))
    if contact:
        elements.append(Paragraph(sanitize_text(contact), styles['Contact']))

    # Summary
    if summary:
        elements.append(Paragraph("SUMMARY", styles['SectionHeader']))
        elements.append(Paragraph(sanitize_text(summary), styles['Normal']))
        elements.append(Spacer(1, 0.1 * inch))

    # Skills
    if skills:
        elements.append(Paragraph("SKILLS", styles['SectionHeader']))
        skill_text = ", ".join([sanitize_text(s) for s in skills])
        elements.append(Paragraph(skill_text, styles['Normal']))
        elements.append(Spacer(1, 0.1 * inch))

    # Experience
    if experience:
        elements.append(Paragraph("EXPERIENCE", styles['SectionHeader']))
        for role in experience:
            title = role.get("title","")
            company = role.get("company","")
            dates = role.get("dates","")
            header = " | ".join([x for x in [title, company, dates] if x])
            if header:
                elements.append(Paragraph(f"<b>{sanitize_text(header)}</b>", styles['RoleHeader']))
            
            bullets = role.get("bullets", [])
            for b in bullets:
                elements.append(Paragraph(f"• {sanitize_text(b)}", styles['CustomBullet']))
            elements.append(Spacer(1, 0.05 * inch))

    # Education
    if education:
        elements.append(Paragraph("EDUCATION", styles['SectionHeader']))
        for e in education:
            elements.append(Paragraph(sanitize_text(e), styles['Normal']))

    doc.build(elements)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--posting", required=False)
    args = ap.parse_args()

    profile = json.load(open(args.profile, "r", encoding="utf-8"))
    posting_text = None
    if args.posting:
        posting_text = open(args.posting, "r", encoding="utf-8").read()

    # Ensure output directory exists
    out_dir = os.path.dirname(args.out)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    build_pdf(profile, posting_text, args.out)
    print(f"pdf_created={args.out}")

if __name__ == "__main__":
    main()
