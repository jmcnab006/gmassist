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
OPENAI_MODEL = "gpt-4.1"

# Rough character limit per chunk (safe for most models)
CHUNK_SIZE = 12000

# Seconds between calls to avoid rate limits
SLEEP_BETWEEN_CALLS = 1.0

# Output file name
OUTPUT_FILE = "module_output.txt"
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
You are a universal TTRPG adventure module parser.

Your job is to take ANY raw adventure PDF text (from any game system)
and convert it into a structured, system-prompt-friendly module file
for use by an automated DM engine.

You MUST extract:
- adventure background / opening history
- setting information
- themes, tone, and atmosphere
- world lore and legends
- factions, key NPCs, motivations
- story arcs and quest structure
- important items and relics
- all areas/rooms/locations
- all creatures, traps, hazards
- environmental effects
- mechanical triggers
- world-state elements
- any internal logic or special rules

Your output MUST be in “Format C” DM-automation style, using ONLY
the following kinds of blocks (add as many instances of each as needed):

[ADVENTURE_META]
title: ...
setting: ...
themes: ...
tone: ...
background.summary: ...
story.overview: ...
recommended_level: ...
hooks: ...

[AREA:<ID>]
name: ...
desc.short: ...
desc.long: ...
connects: <comma-separated list of other AREA IDs or names>
encounters: <summary of creatures / NPCs / hazards here>
items: <important items or loot>
triggers: <mechanical conditions, e.g., combat triggers, traps, events>
notes: <special rules, secrets, or DM notes>

[NPC:<NAME>]
role: ...
motivation: ...
secrets: ...
relationships: ...
desc: ...

[CREATURE:<NAME>]
ac: ...
hp: ...
speed: ...
attack: ...
special: ...
trigger: <when combat or appearance should be triggered>

[TRAP:<NAME>]
trigger: ...
effect: ...
disarm: ...
location: <AREA ID or description>

[ITEM:<NAME>]
type: ...
properties: ...
plot_relevance: ...
location: <AREA or NPC that holds it>

[STATE]
# describe persistent world or module-level state variables here
# example:
# cult_appeased: bool
# villain_alive: bool
# ritual_completed: bool

# --- DESCRIPTION RULES ---
Descriptions MUST:
- capture the atmosphere, tone, and mood of the adventure
- retain meaningful flavor text and evocative details
- include sensory details (sound, light, smell, tension) when helpful
- be creative when needed, but consistent with the story
- avoid filler or rambling
- stay concise but evocative

desc.short = 1–2 line ultra-condensed summary of the location
desc.long  = 4–10 lines, atmospheric, story-aware, with key details

# --- IMPORTANCE RULES ---
NEVER discard:
- lore
- background
- history
- motivations
- plot hooks
- worldbuilding
- tone

You MAY condense:
- repeated text
- long mechanical tables
- statblocks (into compact mechanical summaries)

If a section describes the story, themes, or history, it MUST be preserved
in some form.

# --- OUTPUT RULES ---
- Output ONLY the structured module content, no commentary
- Keep the block format rigidly consistent and parseable
- Never output plain unstructured paragraphs; everything must be in blocks
- Never invent plot-critical facts; stay faithful to the text
- You may enhance descriptions slightly to maintain or improve atmosphere
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

