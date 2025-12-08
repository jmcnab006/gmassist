#!/usr/bin/env python3
import fitz
import easyocr
from PIL import Image
import numpy as np
import io
import argparse
import re


def clean(text):
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n\s*\n+', '\n\n', text)
    return text.strip()


def extract(pdf_path):
    reader = easyocr.Reader(['en'], gpu=False)
    doc = fitz.open(pdf_path)
    pages = []

    for page in doc:
        pix = page.get_pixmap(dpi=300)
        img_bytes = pix.tobytes("png")

        pil_img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
        np_img = np.array(pil_img)

        results = reader.readtext(
            np_img,
            detail=0,
            paragraph=True
        )

        page_text = "\n".join(results)
        pages.append(page_text)

    return "\n\n".join(pages)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf_file")
    parser.add_argument("output")
    args = parser.parse_args()

    print("[+] Running EasyOCR (no Tesseract needed) …")
    raw = extract(args.pdf_file)
    cleaned = clean(raw)

    with open(args.output, "w", encoding="utf-8") as f:
        f.write(cleaned)

    print(f"[✓] Done: {args.output}")


if __name__ == "__main__":
    main()

