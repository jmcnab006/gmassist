import fitz # PyMuPDF

def extract_text_with_pymupdf(pdf_path):
    try:
        doc = fitz.open(pdf_path)
        text = ""
        for page_num in range(doc.page_count):
            page = doc.load_page(page_num)
            text += page.get_text()
        return text
    except Exception as e:
        print(f"Error extracting text with PyMuPDF: {e}")
        return None

# Example usage
pdf_file = "/home/jmcnab/Downloads/DDEX11_Defiance_in_Phlan.pdf"
extracted_text = extract_text_with_pymupdf(pdf_file)
if extracted_text:
    print(extracted_text)
