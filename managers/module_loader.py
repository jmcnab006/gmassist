# managers/module_loader.py

import os
from pypdf import PdfReader

DEFAULT_MODULE_PATH = "data/module_text.txt"


def extract_module_from_pdf(pdf_path: str, output_path: str = DEFAULT_MODULE_PATH) -> str:
    """Extract text from a PDF module and save it to a text file."""
    reader = PdfReader(pdf_path)
    text = ""
    for page in reader.pages:
        try:
            extracted = page.extract_text()
            if extracted:
                text += extracted + "\n"
        except Exception:
            # Ignore pages that can't be parsed cleanly
            pass

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(text)

    return output_path


def load_module_text(path: str = DEFAULT_MODULE_PATH) -> str:
    """Load module text from a file."""
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

