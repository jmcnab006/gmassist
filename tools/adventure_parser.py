#!/usr/bin/python3
import os
import time
from typing import List
from openai import OpenAI

# ----------------------------------------
# CONFIGURATION
# ----------------------------------------

# Model to use
OPENAI_MODEL = "gpt-4.1-mini"
#OPENAI_MODEL = "gpt-4.1"

# Rough character limit per chunk (safe for most models)
CHUNK_SIZE = 50000

# Seconds between calls to avoid rate limits
SLEEP_BETWEEN_CALLS = 1.0

# Output file name
OUTPUT_FILE = "module.ini"
DEBUG_OUTPUT_FILE = "module_output.debug"

PROMPT_PATH = "prompts/deepseek.prompt"

# ----------------------------------------
# OPENAI CLIENT
# ----------------------------------------

# Make sure OPENAI_API_KEY is set in your environment
# export OPENAI_API_KEY="your-key-here"
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))


# ----------------------------------------
# PDF TEXT EXTRACTION
# ----------------------------------------

def extract_pdf_text(pdf_path: str) -> str:
    print(f"[+] Extracting PDF text via pdfminer.six: {pdf_path}")

    try:
        text = pdfminer_extract_text(pdf_path)
    except Exception as e:
        print(f"[ERROR] pdfminer failed: {e}")
        text = ""

    print(f"[+] Extracted {len(text)} characters")
    return text

# ----------------------------------------
# CHUNKING FUNCTION
# ----------------------------------------

def chunk_text(text: str, max_chars: int) -> List[str]:
    """
    Splits a large text into chunks of roughly max_chars characters,
    preserving line boundaries as much as possible.
    """
    print("[+] Splitting text into chunks...")
    chunks: List[str] = []
    current_lines: List[str] = []
    current_len = 0

    for line in text.split("\n"):
        line_len = len(line) + 1  # +1 for newline
        if current_len + line_len > max_chars and current_lines:
            chunks.append("\n".join(current_lines))
            current_lines = [line]
            current_len = line_len
        else:
            current_lines.append(line)
            current_len += line_len

    if current_lines:
        chunks.append("\n".join(current_lines))

    print(f"[+] Created {len(chunks)} chunk(s)")
    return chunks


# ----------------------------------------
# UNIVERSAL ADVENTURE PARSER SYSTEM PROMPT
# ----------------------------------------

with open(PROMPT_PATH, "r") as file:
    UNIVERSAL_SYSTEM_PROMPT = file.read()


# ----------------------------------------
# AI CALL FOR PARSING CHUNKS
# ----------------------------------------

def parse_chunk(chunk_text: str, chunk_index: int, total_chunks: int) -> str:
    """
    Sends a chunk of raw PDF text to the OpenAI model and receives
    structured module output.
    """
    print(f"[+] Parsing chunk {chunk_index + 1}/{total_chunks}...")

    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": UNIVERSAL_SYSTEM_PROMPT},
            {"role": "user", "content": chunk_text},
        ],
        temperature=0.4,  # low-temp for structure, but not 0 to allow some creativity
    )

    content = response.choices[0].message.content
    print(f"    - Received {len(content)} characters of structured output")
    return content


# ----------------------------------------
# MAIN PROCESS
# ----------------------------------------

def generate_module(pdf_path: str, output_path: str = OUTPUT_FILE):
    """
    Full pipeline:
    1. Extract text from PDF
    2. Chunk it
    3. Parse each chunk via OpenAI
    4. Combine into a single structured module file
    """
    with open(pdf_path, "r") as file:
        raw_text = file.read()
    #raw_text = extract_pdf_text(pdf_path)
#    with open(DEBUG_OUTPUT_FILE, "w", encoding="utf-8") as f:
#        f.write(raw_text)

    chunks = chunk_text(raw_text, CHUNK_SIZE)

    all_outputs: List[str] = []

    for i, chunk in enumerate(chunks):
        structured = parse_chunk(chunk, i, len(chunks))
        all_outputs.append(structured)
        time.sleep(SLEEP_BETWEEN_CALLS)

    # Combine all structured blocks
    full_text = "\n\n".join(all_outputs)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(full_text)

    print(f"[+] DONE! Structured module written to: {output_path}")


# ----------------------------------------
# CLI ENTRYPOINT
# ----------------------------------------

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python adventure_parser.py <adventure.pdf> [output.txt]")
        raise SystemExit(1)

    raw_file = sys.argv[1]
    #pdf_file = sys.argv[1]
    if len(sys.argv) >= 3:
        out_file = sys.argv[2]
    else:
        out_file = OUTPUT_FILE

    generate_module(raw_file, out_file)
