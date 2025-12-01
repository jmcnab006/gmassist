import os
from pypdf import PdfReader
import openai
import textwrap
import time

# ----------------------------------------
# CONFIGURATION
# ----------------------------------------

OPENAI_MODEL = "gpt-4.1-mini"   # your preferred model
#CHUNK_SIZE = 12000              # tokens worth of text per chunk for safety
CHUNK_SIZE = 50000              # tokens worth of text per chunk for safety
SLEEP_BETWEEN_CALLS = 1         # avoid rate-limits
OUTPUT_FILE = "module_output.txt"

# Choose your output format:
#FORMAT_STYLE = "C"              # A, B, or C
DESCRIPTION_STYLE = "long"    # "short", "medium", or "long"

# ----------------------------------------
# OPENAI CLIENT
# ----------------------------------------

client = openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# ----------------------------------------
# PDF TEXT EXTRACTION
# ----------------------------------------
def extract_pdf_text(pdf_path):
    reader = PdfReader(pdf_path)

    print(f"[+] Extracting text from: {pdf_path}")
    output_text = ""
    for page in reader.pages:
        try:
            output_text += page.extract_text() + "\n"
        except:
            pass

    print(f"[+] Extracted {len(output_text)} characters from PDF")
    return output_text

# ----------------------------------------
# CHUNKING FUNCTION
# ----------------------------------------

def chunk_text(text, max_chars):
    print("[+] Splitting text into API-safe chunks...")
    chunks = []
    current = []

    for line in text.split("\n"):
        if sum(len(c) for c in current) + len(line) >= max_chars:
            chunks.append("\n".join(current))
            current = []
        current.append(line)

    if current:
        chunks.append("\n".join(current))

    print(f"[+] Created {len(chunks)} chunks")
    return chunks


# ----------------------------------------
# AI CALL FOR PARSING CHUNKS
# ----------------------------------------

def parse_chunk(chunk_text, chunk_index, total_chunks):
    print(f"[+] Parsing chunk {chunk_index+1}/{total_chunks}")

    system_prompt = f"""
You are an AI module-parser for Dungeons & Dragons adventures.
You convert raw PDF text into a structured DM-automation-friendly module file.

Description detail: {DESCRIPTION_STYLE}

You MUST output ONLY the parsed module with NO commentary.
If you see repeated text or headers, remove duplicates.

Identify the following:
    - structural rules
    - npcs
    - areas 
    - rooms 
    - creatures
    - traps
    - items
    - environmental hazards


Produce HIGHLY structured content organized by type:

[AREA:<ID>]
name: <unique clean name>
description: ...
connects: <comma list of area <ID> >
items: ...
encounters: ...
triggers: ...
notes: < special notes regarding area >

[CREATURE:<NAME>]
ac: ...
hp: ...
speed: ...
attack: ...
special: ...
trigger: ...

[ITEM:<NAME>]
type: ...
properties: ...
plot_relevance: ...
location: <ID> <location in area>

[TRAP:<NAME>]
trigger: ...
effect: ...
disarm: ...
location: <ID> <location in area>

ONLY output structured module content — NO filler, NO abstractions.
"""

    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": chunk_text}
        ]
    )

    return response.choices[0].message.content


# ----------------------------------------
# MAIN PROCESS
# ----------------------------------------

def generate_module(pdf_path):

    raw_text = extract_pdf_text(pdf_path)
    chunks = chunk_text(raw_text, CHUNK_SIZE)

    all_outputs = []

    for i, chunk in enumerate(chunks):
        parsed = parse_chunk(chunk, i, len(chunks))
        all_outputs.append(parsed)
        time.sleep(SLEEP_BETWEEN_CALLS)

    full_text = "\n\n".join(all_outputs)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(full_text)

    print(f"[+] FINISHED! Module written to: {OUTPUT_FILE}")


# ----------------------------------------
# RUN SCRIPT (EXAMPLE)
# ----------------------------------------

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python parse_module.py <pdf_file>")
        exit()

    pdf_path = sys.argv[1]
    generate_module(pdf_path)

