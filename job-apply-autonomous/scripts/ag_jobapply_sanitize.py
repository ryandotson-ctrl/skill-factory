#!/usr/bin/env python3
import argparse, sys
from docx import Document

EM_DASH = "\u2014"
EN_DASH = "\u2013"

def sanitize_docx(path: str) -> int:
    doc = Document(path)
    changed = 0
    for p in doc.paragraphs:
        if EM_DASH in p.text or EN_DASH in p.text:
            p.text = p.text.replace(EM_DASH, ", ").replace(EN_DASH, "-")
            changed += 1
    if changed:
        doc.save(path)
    return changed

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", required=True)
    args = ap.parse_args()
    n = sanitize_docx(args.path)
    print(f"sanitized_paragraphs={n}")

if __name__ == "__main__":
    main()
