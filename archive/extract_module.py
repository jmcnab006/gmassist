#!/usr/bin/python3
import os
import sys
from pypdf import PdfReader

def extract_pdf_to_text(pdf_path, output_path="data/module.txt"):
    reader = PdfReader(pdf_path)
    text = ""

    for page in reader.pages:
        try:
            text += page.extract_text() + "\n"
        except:
            pass

    os.makedirs("data", exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(text)

    print(f"Module saved to: {output_path}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python extract_module.py <module.pdf>")
        sys.exit(1)

    extract_pdf_to_text(sys.argv[1])
