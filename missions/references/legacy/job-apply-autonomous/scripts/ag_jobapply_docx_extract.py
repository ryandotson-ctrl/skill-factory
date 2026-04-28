#!/usr/bin/env python3
import argparse
from docx import Document

def extract_docx(in_path: str) -> str:
    doc = Document(in_path)
    parts = []
    for p in doc.paragraphs:
        t = (p.text or "").strip()
        if t:
            parts.append(t)
    return "\n".join(parts) + "\n"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="in_path", required=True)
    ap.add_argument("--out", dest="out_path", required=True)
    args = ap.parse_args()

    text = extract_docx(args.in_path)
    with open(args.out_path, "w", encoding="utf-8") as f:
        f.write(text)

if __name__ == "__main__":
    main()
