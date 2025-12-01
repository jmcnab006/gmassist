import os
import sys
import time
from typing import List
from pdfminer.high_level import extract_text as pdfminer_extract_text
from openai import OpenAI

# ----------------------------------------
# CONFIG
# ----------------------------------------

OPENAI_MODEL = "gpt-4.1-mini"
CHUNK_SIZE = 12000
SLEEP_BETWEEN_CALLS = 1.0
OUTPUT_FILE = "parsed_areas.txt"

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# ----------------------------------------
# SYSTEM PROMPT — FINAL SCHEMA
# ----------------------------------------

SYSTEM_PROMPT = """
You are a TTRPG adventure parser. Convert RAW MODULE TEXT into structured AREA blocks.

Output ONLY blocks in the EXACT following format:

[AREA:<ID>]
name: <string>
description: <string>
connects: <comma-separated list or None>
encounters: <comma-separated list or None>
items: <comma-separated list or None>
triggers: <string or None>
notes: <string or None>

Rules:
- Each AREA block must represent a distinct room, location, or map-labeled space.
- <ID> should reflect any numbering used in the text if possible (e.g., “1A”, “3”, “K2”). If none exists, create a stable descriptive ID.
- description must be a detailed paragraph (3–8 sentences), preserving original atmosphere.
- connects: list ONLY areas explicitly or strongly implied to connect; otherwise None.
- encounters: creatures or NPCs physically present; otherwise None.
- items: only meaningful objects or treasure; otherwise None.
- triggers: traps, skill checks, or conditional events; or None.
- notes: DM guidance, secrets, or special rules; or None.
- Do NOT invent areas or encounters.
- Do NOT output commentary.
- If this chunk contains no area content, output nothing.
"""

# ----------------------------------------
# PDF TEXT
# ----------------------------------------

def extract_pdf_text(pdf_path: str) -> str:
    print(f"[+] Extracting text with pdfminer: {pdf_path}")
    return pdfminer_extract_text(pdf_path)

# ----------------------------------------
# CHUNKING
# ----------------------------------------

def chunk_text(text: str, max_chars: int) -> List[str]:
    lines = text.split("\n")
    chunks = []
    buf = []
    length = 0
    for line in lines:
        if length + len(line) + 1 > max_chars:
            chunks.append("\n".join(buf))
            buf = [line]
            length = len(line)
        else:
            buf.append(line)
            length += len(line) + 1
    if buf:
        chunks.append("\n".join(buf))
    print(f"[+] Created {len(chunks)} chunk(s)")
    return chunks

# ----------------------------------------
# GPT PARSE
# ----------------------------------------

def parse_chunk(chunk: str, idx: int, total: int) -> str:
    print(f"[+] Parsing chunk {idx+1}/{total}")
    resp = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": chunk}
        ],
        temperature=0.2,
    )
    return resp.choices[0].message.content.strip()

# ----------------------------------------
# MAIN
# ----------------------------------------

def generate(pdf_path: str, output_path: str = OUTPUT_FILE):

    text = extract_pdf_text(pdf_path)
    chunks = chunk_text(text, CHUNK_SIZE)

    blocks = []

    for i, chunk in enumerate(chunks):
        out = parse_chunk(chunk, i, len(chunks)).strip()
        if out:
            blocks.append(out)
        time.sleep(SLEEP_BETWEEN_CALLS)

    full_output = "\n\n".join(blocks)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(full_output)

    print(f"[+] Done. Wrote AREA blocks to {output_path}")

# ----------------------------------------
# CLI ENTRY
# ----------------------------------------

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python adventure_parser_v5.py <adventure.pdf> [output.txt]")
        exit(1)

    pdf = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) >= 3 else OUTPUT_FILE

    generate(pdf, out)

