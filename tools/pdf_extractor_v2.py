#!/usr/bin/env python3
"""
PDF Text Extractor with multiple processing options
"""

import argparse
import sys
import re
from pathlib import Path

# Try to import PDF libraries
try:
    import pdfplumber
    HAS_PDFPLUMBER = True
except ImportError:
    HAS_PDFPLUMBER = False

try:
    from pypdf import PdfReader
    HAS_PYPDF = True
except ImportError:
    HAS_PYPDF = False

if not HAS_PDFPLUMBER and not HAS_PYPDF:
    print("Error: No PDF library found. Install one of:")
    print("  pip install pdfplumber")
    print("  pip install pypdf")
    sys.exit(1)


def extract_pdf_text(pdf_path):
    """Extract text from PDF file."""
    # Try pdfplumber first (better for complex layouts)
    if HAS_PDFPLUMBER:
        try:
            text = ""
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n\n"
            return text
        except Exception as e:
            print(f"pdfplumber error: {e}", file=sys.stderr)
            if not HAS_PYPDF:
                sys.exit(1)
    
    # Fallback to pypdf
    if HAS_PYPDF:
        try:
            reader = PdfReader(pdf_path)
            text = ""
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n\n"
            return text
        except Exception as e:
            print(f"Error reading PDF: {e}", file=sys.stderr)
            sys.exit(1)


def remove_non_printable(text):
    """Remove non-printable characters while keeping newlines and tabs."""
    cleaned = []
    for char in text:
        code = ord(char)
        # Keep printable ASCII (32-126), newline (10), tab (9)
        # Also keep common unicode characters (128+)
        if (32 <= code <= 126) or char in '\n\t' or code >= 128:
            cleaned.append(char)
        # Replace other control characters with space
        elif code < 32 and char not in '\n\t':
            cleaned.append(' ')
    return ''.join(cleaned)


def fix_broken_words(text):
    """Attempt to fix words that were broken during extraction."""
    # Fix pattern: "T he" -> "The", "c ult" -> "cult"
    text = re.sub(r'\b([A-Za-z])\s+([a-z]{2,})\b', r'\1\2', text)
    
    # Fix pattern: "wo rd" -> "word" (but only for short combinations)
    text = re.sub(r'\b([a-z]{2,})\s+([a-z]{2,})\b', 
                  lambda m: m.group(1) + m.group(2) if len(m.group(1) + m.group(2)) < 15 else m.group(0), 
                  text)
    
    return text


def clean_text(text):
    """Basic cleaning - remove non-printable chars and excessive whitespace."""
    # Remove non-printable characters
    text = remove_non_printable(text)
    
    # Normalize line breaks (handle Windows/Mac/Unix)
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    
    # Remove multiple spaces and tabs on same line
    text = re.sub(r'[ \t]+', ' ', text)
    
    # Remove spaces at start/end of lines
    lines = [line.strip() for line in text.split('\n')]
    
    # Remove empty lines
    lines = [line for line in lines if line]
    
    # Join with single newlines
    return '\n'.join(lines)


def format_text(text):
    """Format text with better structure and paragraph breaks."""
    # Remove non-printable characters first
    text = remove_non_printable(text)
    
    # Normalize line breaks
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    
    # Fix broken words
    text = fix_broken_words(text)
    
    # Remove multiple spaces and tabs
    text = re.sub(r'[ \t]+', ' ', text)
    
    # Split into lines and process
    lines = text.split('\n')
    formatted = []
    buffer = []
    
    for line in lines:
        line = line.strip()
        
        # Skip empty lines
        if not line:
            continue
        
        # Skip very short lines (likely extraction artifacts)
        if len(line) < 3:
            continue
        
        # Check if this looks like a header
        is_header = (
            len(line) < 80 and
            (line.isupper() or 
             re.match(r'^[A-Z][A-Za-z\s]+$', line) or
             line.endswith(':'))
        )
        
        # Check if this is a list item
        is_list = (
            re.match(r'^[\•\-\*]\s', line) or
            re.match(r'^\d+[\.\)]\s', line)
        )
        
        if is_header:
            # Flush buffer
            if buffer:
                formatted.append(' '.join(buffer))
                formatted.append('')
                buffer = []
            # Add header with spacing
            formatted.append(line)
            formatted.append('')
        elif is_list:
            # Flush buffer
            if buffer:
                formatted.append(' '.join(buffer))
                formatted.append('')
                buffer = []
            # Add list item
            formatted.append(line)
        else:
            # Add to buffer
            buffer.append(line)
            
            # End paragraph if line ends with sentence-ending punctuation
            if re.search(r'[.!?]$', line):
                formatted.append(' '.join(buffer))
                formatted.append('')
                buffer = []
    
    # Flush remaining buffer
    if buffer:
        formatted.append(' '.join(buffer))
    
    # Join lines
    result = '\n'.join(formatted)
    
    # Final cleanup: reduce multiple blank lines to double newline max
    result = re.sub(r'\n{3,}', '\n\n', result)
    
    # Remove any remaining multiple spaces
    result = re.sub(r'[ \t]+', ' ', result)
    
    return result.strip()


def main():
    parser = argparse.ArgumentParser(
        description='Extract and process text from PDF files',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s document.pdf -r                    # Raw extract to module.ini
  %(prog)s document.pdf -f                    # Formatted extract to module.ini
  %(prog)s document.pdf -r --stdout           # Print raw to console
  %(prog)s document.pdf -f -o output.txt      # Save formatted to custom file

Installation:
  pip install pdfplumber    # Recommended for best results
  pip install pypdf         # Alternative
        """
    )
    
    parser.add_argument(
        'input_file',
        help='Input PDF file path'
    )
    
    # Mode flags (mutually exclusive)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        '-r', '--raw',
        action='store_true',
        help='Raw extraction (minimal processing)'
    )
    mode.add_argument(
        '-f', '--formatted',
        action='store_true',
        help='Formatted extraction (cleaned and structured)'
    )
    
    parser.add_argument(
        '-o', '--output',
        default='module.ini',
        help='Output file (default: module.ini)'
    )
    
    parser.add_argument(
        '--stdout',
        action='store_true',
        help='Print to stdout instead of file'
    )
    
    args = parser.parse_args()
    
    # Default to raw if nothing specified
    if not args.raw and not args.formatted:
        args.raw = True
    
    # Validate input file
    input_path = Path(args.input_file)
    if not input_path.exists():
        print(f"Error: File not found: {args.input_file}", file=sys.stderr)
        sys.exit(1)
    
    # Extract text
    print(f"Extracting text from {args.input_file}...", file=sys.stderr)
    text = extract_pdf_text(args.input_file)
    
    if not text.strip():
        print("Error: No text extracted from PDF", file=sys.stderr)
        sys.exit(1)
    
    # Process based on mode
    if args.formatted:
        print("Formatting text...", file=sys.stderr)
        result = format_text(text)
    else:  # raw
        print("Cleaning text...", file=sys.stderr)
        result = clean_text(text)
    
    # Output
    if args.stdout:
        print("\n--- OUTPUT ---")
        print(result)
    else:
        try:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(result)
            print(f"✓ Output written to {args.output}", file=sys.stderr)
        except Exception as e:
            print(f"Error writing file: {e}", file=sys.stderr)
            sys.exit(1)


if __name__ == '__main__':
    main()
