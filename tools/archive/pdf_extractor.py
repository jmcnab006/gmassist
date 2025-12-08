#!/usr/bin/env python3
"""
PDF Text Extractor with multiple processing options
"""

import argparse
import sys
from pathlib import Path

# You'll need: pip install PyPDF2
try:
    from pdfminer.high_level import extract_text as pdfminer_extract_text
except ImportError:
    print("Please install pdfminer: pip install pdfminer")
    sys.exit(1)

def extract_pdf_text(pdf_path: str) -> str:
    print(f"[+] Extracting PDF text : {pdf_path}")

    try:
        text = pdfminer_extract_text(pdf_path)
    except Exception as e:
        print(f"Error reading PDF: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"[+] Extracted {len(text)} characters")
    return text


def process_raw(text):
    """Return text as-is (raw extraction)."""
    return text


def process_reformat(text):
    """Clean and reformat the text for better structure."""
    import re
    
    # Split into lines
    lines = text.split('\n')
    result_lines = []
    current_paragraph = []
    
    for line in lines:
        stripped = line.strip()
        
        # Skip empty lines
        if not stripped:
            if current_paragraph:
                result_lines.append(' '.join(current_paragraph))
                current_paragraph = []
            continue
        
        # Detect headers (short lines, often all caps or title case)
        is_header = (
            len(stripped) < 50 and 
            (stripped.isupper() or 
             stripped[0].isupper() and not stripped.endswith('.'))
        )
        
        # Detect list items (starts with bullet, number, or dash)
        is_list_item = re.match(r'^[\u2022\u2023\u25E6\u2043\u2219\-\*]\s+', stripped) or \
                       re.match(r'^\d+[\.\)]\s+', stripped) or \
                       stripped.startswith('• ')
        
        # Handle headers
        if is_header:
            if current_paragraph:
                result_lines.append(' '.join(current_paragraph))
                current_paragraph = []
            result_lines.append('')  # Blank line before header
            result_lines.append(stripped)
            result_lines.append('')  # Blank line after header
            continue
        
        # Handle list items
        if is_list_item:
            if current_paragraph:
                result_lines.append(' '.join(current_paragraph))
                current_paragraph = []
            result_lines.append(stripped)
            continue
        
        # Check if line ends a sentence
        ends_sentence = stripped.endswith(('.', '!', '?', ':', '"'))
        
        # Add to current paragraph
        current_paragraph.append(stripped)
        
        # If it ends a sentence and next line might be a new paragraph, flush
        if ends_sentence and len(current_paragraph) > 1:
            result_lines.append(' '.join(current_paragraph))
            result_lines.append('')  # Paragraph break
            current_paragraph = []
    
    # Don't forget the last paragraph
    if current_paragraph:
        result_lines.append(' '.join(current_paragraph))
    
    # Clean up: remove multiple consecutive blank lines
    cleaned = []
    prev_blank = False
    for line in result_lines:
        if not line:
            if not prev_blank:
                cleaned.append(line)
            prev_blank = True
        else:
            cleaned.append(line)
            prev_blank = False
    
    return '\n'.join(cleaned).strip()


def main():
    parser = argparse.ArgumentParser(
        description="Extract and process text from PDF files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s input.pdf -r                                  # Raw extract to module.ini
  %(prog)s input.pdf --raw --stdout                      # Raw extract to console
  %(prog)s input.pdf -f -o output.txt                    # Formatted extract to custom file
  %(prog)s input.pdf --formatted                         # Formatted extract to module.ini
        """
    )
    
    # Required argument
    parser.add_argument(
        'input_file',
        type=str,
        help='Input PDF file path'
    )
    
    # Processing mode flags
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        '-r', '--raw',
        action='store_true',
        help='Raw extraction (simple text extraction)'
    )
    
    mode_group.add_argument(
        '-f', '--formatted',
        action='store_true',
        help='Formatted extraction (clean and structure the text)'
    )
    
    # Output file (optional)
    parser.add_argument(
        '--output', '-o',
        type=str,
        default='output.txt',
        help='Output file path (default: module.ini)'
    )
    
    parser.add_argument(
        '--stdout',
        action='store_true',
        help='Print output to stdout instead of file'
    )
    
    args = parser.parse_args()
    
    # Default to raw if no mode specified
    if not args.raw and not args.formatted:
        args.raw = True
    
    # Validate input file
    input_path = Path(args.input_file)
    if not input_path.exists():
        print(f"Error: File not found: {args.input_file}", file=sys.stderr)
        sys.exit(1)
    
    if not input_path.suffix.lower() == '.pdf':
        print(f"Warning: File doesn't have .pdf extension: {args.input_file}", file=sys.stderr)
    
    # Extract text from PDF
    print(f"Extracting text from {args.input_file}...", file=sys.stderr)
    raw_text = extract_pdf_text(args.input_file)
    
    # Process based on flags
    if args.formatted:
        print("Processing in 'formatted' mode...", file=sys.stderr)
        result = process_reformat(raw_text)
    else:  # args.raw or default
        print("Processing in 'raw' mode...", file=sys.stderr)
        result = process_raw(raw_text)
    
    # Output result
    if args.stdout:
        print("\n--- OUTPUT ---")
        print(result)
    else:
        try:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(result)
            print(f"Output written to {args.output}", file=sys.stderr)
        except Exception as e:
            print(f"Error writing output file: {e}", file=sys.stderr)
            sys.exit(1)


if __name__ == '__main__':
    main()
