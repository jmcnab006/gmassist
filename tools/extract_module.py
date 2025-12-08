#!/usr/bin/python3
import os
import sys
from pypdf import PdfReader
from pdfminer.high_level import extract_text as pdfminer_extract_text
from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
from pdfminer.converter import TextConverter
from pdfminer.layout import LAParams
from pdfminer.pdfpage import PDFPage
from io import StringIO

OUTPUT_FILE = "module.raw"

def convert_pdf_text(path: str) -> str:
    rsrcmgr = PDFResourceManager()
    retstr = StringIO()
    codec = 'utf-8'
    laparams = LAParams()
    device = TextConverter(rsrcmgr, retstr, codec=codec, laparams=laparams)
    fp = open(path, 'rb')
    interpreter = PDFPageInterpreter(rsrcmgr, device)
    password = ""
    maxpages = 0
    caching = True
    pagenos=set()

    for page in PDFPage.get_pages(fp, pagenos, maxpages=maxpages, password=password,caching=caching, check_extractable=True):
        interpreter.process_page(page)

    text = retstr.getvalue()

    fp.close()
    device.close()
    retstr.close()
    return text

def extract_pdf_text(pdf_path: str) -> str:
    print(f"[+] Extracting PDF text via pdfminer.six: {pdf_path}")

    try:
        text = pdfminer_extract_text(pdf_path)
    except Exception as e:
        print(f"[ERROR] pdfminer failed: {e}")
        text = ""

    print(f"[+] Extracted {len(text)} characters")
    return text


def extract_pdf_to_text(pdf_path, output_path="module.raw"):
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
	
    raw_text = ""
    try:
        raw_text = convert_pdf_text(sys.argv[1])
        raw_text = raw_text.replace("\n","")

    except Exception as e:
        print(f"[ERROR] pdfminer failed: {e}")

    print(f"[+] Extracted {len(raw_text)} characters")
	
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(raw_text)

    print(f"Data saved to: {OUTPUT_FILE}")
