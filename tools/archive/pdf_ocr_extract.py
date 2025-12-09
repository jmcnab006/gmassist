#!/usr/bin/env python3
"""
D&D / DDEX PDF CLEAN TEXT EXTRACTOR v5
--------------------------------------

Designed for print-layout D&D PDFs (Adventurers League / DDEX / etc.)
that have:
- Two-column layouts
- Decorative images / sidebars / backgrounds
- Weird glyphs / ligatures
- Invisible / junk text layers

This script:
- Renders the PDF pages to IMAGES (uses OCR only; no PDF text extraction)
- Blanks ALL images (so OCR only sees letter glyphs, not art)
- Deskews pages
- Crops headers / footers
- Detects 1 or 2 columns
- OCRs each column with EasyOCR
- Rebuilds lines -> paragraphs
- Drops AL/WotC header/footer boilerplate
- Uses a garbage-line filter to drop junk like:
  "2 9 E 3 1 1 Q L 2 8 1 1 8 3 2 1 1..."

Outputs clean, readable text (Markdown-ish).

Usage:
    python3 ddex_clean_extract_v5.py input.pdf output.txt
"""

import argparse
import io
import re
from dataclasses import dataclass
from typing import List, Optional

import fitz              # PyMuPDF
import numpy as np
import cv2
from PIL import Image
import easyocr


# -------------------------
# Global Settings
# -------------------------

DPI = 350     # 300–400 is good for printed serif fonts
TOP_CROP = 0.06
BOTTOM_CROP = 0.09
MIN_CONF = 0.45

FOOTER_KEYWORDS = [
    "not for resale",
    "permission granted to print",
    "wizards of the coast",
    "hasbro",
    "adventurers league",
    "dungeons & dragons",
    "po box",
]


@dataclass
class TextBox:
    text: str
    cx: float   # normalized center-x (0–1)
    cy: float   # normalized center-y (0–1)
    conf: float


# -------------------------
# Image Helpers
# -------------------------

def pil_to_np(pil_img: Image.Image) -> np.ndarray:
    """Convert a PIL Image to an RGB NumPy array."""
    return np.array(pil_img.convert("RGB"))


def deskew(img: np.ndarray) -> np.ndarray:
    """Deskew image using OpenCV angle detection."""
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    _, th = cv2.threshold(
        blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
    )
    th_inv = cv2.bitwise_not(th)
    pts = cv2.findNonZero(th_inv)

    if pts is None or len(pts) < 50:
        return img

    rect = cv2.minAreaRect(pts)
    angle = rect[-1]

    if angle < -45:
        angle = -(90 + angle)
    else:
        angle = -angle

    if abs(angle) < 0.5:
        return img

    h, w = img.shape[:2]
    M = cv2.getRotationMatrix2D((w // 2, h // 2), angle, 1.0)
    rot = cv2.warpAffine(
        img, M, (w, h),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_REPLICATE
    )
    return rot


def crop_margins(img: np.ndarray) -> np.ndarray:
    """Crop top and bottom to remove headers/footers."""
    h, w = img.shape[:2]
    top = int(h * TOP_CROP)
    bottom = int(h * (1 - BOTTOM_CROP))
    if bottom <= top + 10:
        return img
    return img[top:bottom, :]


def remove_images_from_page(page: fitz.Page, np_img: np.ndarray) -> np.ndarray:
    """
    Blank out all image blocks on the rendered raster.
    Uses PDF text dict to find image block bounding boxes.
    Option A: remove ALL images.
    """
    data = page.get_text("dict")
    h, w = np_img.shape[:2]
    scale = DPI / 72.0  # points (1/72 in) -> pixels at desired DPI

    for block in data.get("blocks", []):
        if block.get("type", 0) != 1:  # 1 = image block
            continue
        x0, y0, x1, y1 = block.get("bbox", [0, 0, 0, 0])

        px0 = int(x0 * scale)
        py0 = int(y0 * scale)
        px1 = int(x1 * scale)
        py1 = int(y1 * scale)

        # clamp to image bounds
        px0 = max(0, min(w - 1, px0))
        py0 = max(0, min(h - 1, py0))
        px1 = max(0, min(w, px1))
        py1 = max(0, min(h, py1))

        # paint white over the image region
        np_img[py0:py1, px0:px1] = 255

    return np_img


# -------------------------
# Column Detection
# -------------------------

def detect_column_split(gray: np.ndarray) -> Optional[int]:
    """Detect two-column layout using vertical projection."""
    h, w = gray.shape
    proj = np.sum(gray < 230, axis=0).astype(float)

    # Narrow pages usually single-column
    if w < 900:
        return None

    left = int(w * 0.35)
    right = int(w * 0.65)
    mid_band = proj[left:right]
    if mid_band.size == 0:
        return None

    valley_local = int(np.argmin(mid_band))
    valley_x = left + valley_local

    valley_val = proj[valley_x]
    left_peak = np.max(proj[:valley_x]) if valley_x > 0 else 0
    right_peak = np.max(proj[valley_x:]) if valley_x < w - 1 else 0

    if left_peak < 80 or right_peak < 80:
        return None

    # distinct valley between two dense regions
    if valley_val < 0.35 * min(left_peak, right_peak):
        return valley_x

    return None


def split_columns(img: np.ndarray) -> List[np.ndarray]:
    """Split image into 1 or 2 column sub-images."""
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    split_x = detect_column_split(gray)
    if split_x is None:
        return [img]

    gutter = 12
    left = img[:, :max(split_x - gutter, 1)]
    right = img[:, min(split_x + gutter, img.shape[1]):]
    return [left, right]


# -------------------------
# OCR
# -------------------------

def get_ocr_reader():
    """Initialize EasyOCR reader once for reuse."""
    return easyocr.Reader(['en'], gpu=False)


def ocr_column(reader, col_img: np.ndarray) -> List[TextBox]:
    """Run OCR on a column and return TextBox entries."""
    results = reader.readtext(
        col_img,
        detail=1,
        paragraph=False
    )

    h, w = col_img.shape[:2]
    boxes: List[TextBox] = []

    for res in results:
        if len(res) != 3:
            continue
        bbox, text, conf = res
        if not text or not text.strip():
            continue
        if conf < MIN_CONF:
            continue

        xs = [p[0] for p in bbox]
        ys = [p[1] for p in bbox]
        cx = (min(xs) + max(xs)) / 2.0 / w
        cy = (min(ys) + max(ys)) / 2.0 / h

        boxes.append(TextBox(text.strip(), cx, cy, conf))

    return boxes


def sort_into_lines(boxes: List[TextBox]) -> List[str]:
    """Sort OCR boxes into lines, top-to-bottom, left-to-right."""
    if not boxes:
        return []

    boxes = sorted(boxes, key=lambda b: (b.cy, b.cx))
    lines: List[List[TextBox]] = []
    current: List[TextBox] = []
    current_y = boxes[0].cy

    Y_TOL = 0.013  # tuned

    for b in boxes:
        if abs(b.cy - current_y) <= Y_TOL:
            current.append(b)
        else:
            if current:
                current = sorted(current, key=lambda tb: tb.cx)
                lines.append(current)
            current = [b]
            current_y = b.cy

    if current:
        current = sorted(current, key=lambda tb: tb.cx)
        lines.append(current)

    text_lines: List[str] = []
    for line_boxes in lines:
        parts = [tb.text for tb in line_boxes]
        joined = " ".join(parts)
        joined = re.sub(r"\s{2,}", " ", joined).strip()
        if joined:
            text_lines.append(joined)

    return text_lines


# -------------------------
# Garbage Line Filter
# -------------------------

def is_garbage_line(line: str) -> bool:
    """Detect if a line is OCR garbage rather than real text."""
    s = line.strip()
    if not s:
        return False

    # Too many non-alphanumeric characters
    non_alnum = sum(1 for c in s if not c.isalnum())
    if non_alnum / len(s) > 0.35:
        return True

    # Extremely low vowel content -> unlikely to be English
    vowels = sum(1 for c in s.lower() if c in "aeiouy")
    letters = sum(1 for c in s if c.isalpha())
    if letters > 12 and vowels / max(letters, 1) < 0.10:
        return True

    # Too many uppercase letters
    upper = sum(1 for c in s if c.isupper())
    if upper > 15 and upper / max(len(s), 1) > 0.50:
        return True

    # Too few recognizable words in long line
    words = s.split()
    real_words = sum(
        1 for w in words if len(w) > 2 and re.search(r"[aeiou]", w.lower())
    )
    if len(s) > 50 and real_words < 3:
        return True

    # Long sequences of single-letter tokens
    if re.search(r"(?:\b[A-Z0-9]\b[\s,]*){6,}", s):
        return True

    return False


def remove_garbage(lines: List[str]) -> List[str]:
    """Apply garbage-line filter."""
    clean: List[str] = []
    for ln in lines:
        if is_garbage_line(ln):
            continue
        clean.append(ln)
    return clean


# -------------------------
# Cleanup + Paragraphs
# -------------------------

def remove_headers(lines: List[str]) -> List[str]:
    """Drop AL/WotC boilerplate and page numbers."""
    out: List[str] = []
    for ln in lines:
        s = ln.strip()
        low = s.lower()
        if not s:
            out.append(ln)
            continue
        if any(k in low for k in FOOTER_KEYWORDS):
            continue
        if re.fullmatch(r"\d+", s):
            continue
        out.append(ln)
    return out


def merge_paragraphs(lines: List[str]) -> List[str]:
    """Merge line list into paragraphs; fix hyphens and simple run-ons."""
    paras: List[str] = []
    buf = ""

    for ln in lines:
        ln = ln.rstrip()
        # blank line = paragraph break
        if not ln.strip():
            if buf:
                paras.append(buf.strip())
                buf = ""
            continue

        # hyphenated word broken across lines
        if buf.endswith("-"):
            buf = buf[:-1] + ln.lstrip()
            continue

        # sentence boundary logic
        if re.search(r'[.!?]"?$', buf):
            paras.append(buf.strip())
            buf = ln.lstrip()
        else:
            if buf:
                buf += " " + ln.lstrip()
            else:
                buf = ln.lstrip()

    if buf:
        paras.append(buf.strip())

    cleaned: List[str] = []
    for p in paras:
        # Insert space between lower+Upper if missing
        p = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", p)
        p = re.sub(r"\s{2,}", " ", p)
        cleaned.append(p.strip())

    return cleaned


def format_headings(paragraphs: List[str]) -> List[str]:
    """Lightweight heading detection for Markdown-ish output."""
    out: List[str] = []
    for p in paragraphs:
        s = p.strip()
        if not s:
            out.append(s)
            continue

        # Heuristic: AL headings or all-caps short lines
        if (len(s.split()) <= 6 and s.upper() == s) or s.lower().startswith("mission "):
            out.append("## " + s)
        else:
            out.append(s)
    return out


# -------------------------
# Page Processing
# -------------------------

def process_page(reader, page: fitz.Page) -> str:
    """
    Render a page to an image, remove images, OCR text,
    and return clean text for that page.
    """

    # Render to raster at desired DPI (includes all visible content)
    pix = page.get_pixmap(dpi=DPI, alpha=False)
    pil_img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
    np_img = pil_to_np(pil_img)

    # Remove images (option A: remove ALL images we can detect)
    np_img = remove_images_from_page(page, np_img)

    # Preprocess: deskew and crop
    np_img = deskew(np_img)
    np_img = crop_margins(np_img)

    # Split into columns and OCR each
    column_imgs = split_columns(np_img)
    boxes: List[TextBox] = []
    for col in column_imgs:
        boxes.extend(ocr_column(reader, col))

    # Lines → remove headers → remove garbage
    lines = sort_into_lines(boxes)
    lines = remove_headers(lines)
    lines = remove_garbage(lines)

    # Paragraphs + headings
    paras = merge_paragraphs(lines)
    paras = format_headings(paras)

    return "\n\n".join(paras).strip()


# -------------------------
# Whole-PDF Extraction
# -------------------------

def extract_pdf(pdf_path: str) -> str:
    reader = get_ocr_reader()
    doc = fitz.open(pdf_path)
    pages_text: List[str] = []

    for i, page in enumerate(doc):
        print(f"[+] Processing page {i+1}/{len(doc)}")
        page_txt = process_page(reader, page)
        if page_txt:
            pages_text.append(page_txt)

    full = "\n\n".join(pages_text)
    full = re.sub(r"\s{2,}", " ", full)
    full = re.sub(r"\n\s*\n\s*\n+", "\n\n", full)
    return full.strip()


# -------------------------
# CLI
# -------------------------

def main():
    parser = argparse.ArgumentParser(
        description="D&D / DDEX PDF → clean text extractor v5 (image-based, EasyOCR, no images, garbage-line filter)."
    )
    parser.add_argument("pdf_file", help="Input PDF file")
    parser.add_argument("output_file", help="Output text file")
    args = parser.parse_args()

    text = extract_pdf(args.pdf_file)

    with open(args.output_file, "w", encoding="utf-8") as f:
        f.write(text + "\n")

    print(f"[✓] Extraction complete → {args.output_file}")


if __name__ == "__main__":
    main()

