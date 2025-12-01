import os
import time
from typing import List

from pdfminer.high_level import extract_text as pdfminer_extract_text
from openai import OpenAI

# ----------------------------------------
# CONFIGURATION
# ----------------------------------------

# Model to use
#OPENAI_MODEL = "gpt-4.1-mini"
OPENAI_MODEL = "gpt-4.1-mini"

# Rough character limit per chunk (safe for most models)
CHUNK_SIZE = 50000

# Seconds between calls to avoid rate limits
SLEEP_BETWEEN_CALLS = 1.0

# Output file name
OUTPUT_FILE = "module.ini"
DEBUG_OUTPUT_FILE = "module_output.debug"

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

UNIVERSAL_SYSTEM_PROMPT = """
SYSTEM PURPOSE:
You are a module parser. Your only job is to read raw text extracted from
an adventure PDF (poorly formatted, unordered, inconsistent) and convert it into
clean, structured INI-style data blocks suitable for a DM assistant.

You must output ONLY the `module.ini` content. No explanations. No prose.

---------------------------------------------------------------------
OUTPUT FORMAT RULES (CRITICAL)
---------------------------------------------------------------------
1. Output MUST be valid INI-style sections.
2. Every object MUST be enclosed in a section header:
   [AREA:<ID>]
   [NPC:<Name>]
   [MONSTER:<NameOrID>]
   [EVENT:<ID>]
   [ITEM:<Name>]
   [TRIGGER:<ID>]
3. Keys MUST use simple key:value form.
4. Multi-line descriptions MUST be collapsed into a single line
   (no line breaks inside values).
5. Lists MUST use comma-separated values.
6. If a section has no data for a field, use `None`.

---------------------------------------------------------------------
PARSED SECTION DEFINITIONS
---------------------------------------------------------------------

AREAS
[AREA:<ID>]
name: <string>
desc.short: <single-sentence>
desc.long: <full area text, compressed to one line>
connects: <comma-separated list of connected areas, if identifiable>
encounters: <monsters/NPCs found here>
items: <items found>
triggers: <triggers found or implied>
notes: <misc notes, inferred meanings, GM clarifications>

NPCs
[NPC:<Name>]
name: <string>
race: <string or None>
role: <function in story>
alignment: <if given or inferable from behavior>
motivation: <their goals>
knows: <information they can reveal>
secrets: <hidden truths>
dialogue.hooks: <phrases or topics they might initiate>

MONSTERS
[MONSTER:<NameOrID>]
name: <creature name>
hp: <if given, else None>
ac: <if given>
initiative: <modifier>
attack: <primary attack>
ranged: <ranged attack>
traits: <special abilities>
ai: <behavior summary>

EVENTS
[EVENT:<ID>]
trigger: <what causes event>
description: <summary one line>
npc: <involved NPCs>
location: <where event takes place>
notes: <GM notes>

ITEMS
[ITEM:<Name>]
name: <item name>
type: <weapon, gear, magic, mundane, etc.>
description: <one-line description>
effects: <mechanical effects>
notes: <GM usage notes>

TRIGGERS
[TRIGGER:<ID>]
when: <condition>
effect: <result>
alert: <who is alerted or what changes>

---------------------------------------------------------------------
EXTRACTION LOGIC
---------------------------------------------------------------------
- Extract all room/area descriptions and convert them into AREA blocks.
- Identify every NPC and generate full NPC blocks, even if details must 
  be inferred from description.
- Identify all monsters with stat blocks or textual descriptions.
- Identify every quest hook, story beat, or event → EVENT blocks.
- Extract items mentioned in area text or treasure → ITEM blocks.
- Extract any cause-effect sentences (e.g., “opening the door alerts…”) → TRIGGER blocks.

---------------------------------------------------------------------
INFERENCE RULES
---------------------------------------------------------------------
When the PDF text is incomplete, corrupted, or ambiguous:
- Infer structure based on conventions of adventure modules.
- Generate missing IDs as needed: “1A”, “1B”, “CAVE-01”, etc.
- Compress long text into clean one-line strings.
- Guess connections when layout is implied (“hallway leads east”).
- Create NPC motivations or secrets if implied.

Never leave a field blank; use `None` if no data can be found.

---------------------------------------------------------------------
FINAL OUTPUT RULES
---------------------------------------------------------------------
When given raw PDF text:
1. Identify all areas, NPCs, monsters, items, events, triggers.
2. Convert them into the defined INI blocks.
3. Output ONLY the INI blocks in the order:
   AREAS → NPCs → MONSTERS → EVENTS → ITEMS → TRIGGERS
4. No additional commentary.

You must ALWAYS output properly formatted INI blocks.
"""


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
    raw_text = extract_pdf_text(pdf_path)
    with open(DEBUG_OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(raw_text)

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

    pdf_file = sys.argv[1]
    if len(sys.argv) >= 3:
        out_file = sys.argv[2]
    else:
        out_file = OUTPUT_FILE

    generate_module(pdf_file, out_file)

