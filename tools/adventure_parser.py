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
a TTRPG adventure (messy, from PDF, with bad line breaks) and convert it into
clean, structured INI-style data blocks suitable for a DM assistant.

You MUST output ONLY the module.ini content. No explanations. No prose.

---------------------------------------------------------------------
GLOBAL OUTPUT RULES (CRITICAL)
---------------------------------------------------------------------
- Output MUST be valid INI-style sections.
- Every object MUST be in a section header, one of:
  [ADVENTURE]
  [AREA:<ID>]
  [NPC:<Name>]
  [MONSTER:<NameOrID>]
  [EVENT:<ID>]
  [ITEM:<Name>]
  [TRIGGER:<ID>]

- Keys MUST use simple `key: value` form.
- All values MUST be on a single line (no embedded newlines).
- Lists MUST use comma-separated values.
- If you cannot find data for a field, use `None`.
- Do NOT include any text outside INI sections.

---------------------------------------------------------------------
STRICT ID & INDEXING RULES
---------------------------------------------------------------------
AREAS:
- AREA IDs MUST follow: AREA:<LEVEL> or AREA:<LEVEL><LETTER> or AREA:<UNIQUE_STRING>
  - LEVEL is a positive integer: 1, 2, 3, ...
  - LETTER is a single uppercase letter: A, B, C, ...
  - UNIQUE_STRING is an word describing the area in upper case letters. (e.g. [AREA:OUTSIDE], [AREA:BASEMENT])
  - AREAs with the same LEVEL but different LETTERs are sub-areas.
  Examples: [AREA:1A], [AREA:1B], [AREA:1], [AREA:2B], [AREA:13], [AREA:OUTSIDE]. [AREA:1B] and [AREA:1A] are both part of [AREA:1]	
- Within a single level, letters should increment alphabetically based
  on natural reading order of the module. 
- If the original text does not give a clear ID, invent one following
  this pattern and be consistent.

MONSTERS:
- MONSTER IDs should be `MONSTER:<BaseName><Index>` when there are
  multiple of the same type in different places, e.g. Skeleton1, Skeleton2.

EVENTS & TRIGGERS:
- EVENT and TRIGGER IDs should be concise and stable, e.g. EVENT:1,
  EVENT:2, TRIGGER:1A, TRIGGER:GateScream. Avoid spaces.

NPCs & ITEMS:
- NPC and ITEM IDs may be human-readable names, e.g. [NPC:Runara],
  [ITEM:DragonStatue].

---------------------------------------------------------------------
SECTION DEFINITIONS
---------------------------------------------------------------------
ADVENTURE
[ADVENTURE]
title: <string>
setting: <description of the adventure area>
themes: ...
tone: ...
background: <detailed adventure background>
overview: <detailed summary of the adventure>
flow: <detailed long form description of the flow of events>
hooks: <description on how the adventurers get started>
plot: <long form description of the plot and flow of the adventure>


AREAS
[AREA:<ID>]
name: <string>
desc.short: <single short sentence>
desc.long: <full area description, compressed to one line>
connects: <comma-separated list of AREA IDs or named locations, or None>
encounters: <comma-separated list of MONSTER or NPC IDs, or None>
items: <comma-separated list of ITEM IDs, or None>
triggers: <TRIGGER IDs or descriptive text, or None>
notes: <GM-only notes, or None>

NPCs
[NPC:<Name>]
name: <string>
race: <string or None>
role: <their function in the story>
alignment: <if given or easily inferred, else None>
motivation: <their goals>
knows: <information they can reveal>
secrets: <hidden truths>
dialogue.hooks: <one-line prompts or topics to start conversation>

MONSTERS
[MONSTER:<NameOrID>]
name: <creature name>
hp: <integer or None>
ac: <integer or None>
initiative: <modifier like +2 or None>
attack: <primary melee attack description or None>
ranged: <ranged attack description or None>
traits: <special abilities or defenses or None>
ai: <brief behavior summary, e.g. "Focus weakest target", or None>

EVENTS
[EVENT:<ID>]
trigger: <what causes the event>
description: <one-line summary of the event>
npc: <comma-separated list of involved NPC IDs or None>
location: <AREA ID or named location>
notes: <GM notes>

ITEMS
[ITEM:<Name>]
name: <item name>
type: <weapon, gear, magic, mundane, etc.>
description: <one-line description>
effects: <mechanical effects, or None>
notes: <GM usage notes, or None>

TRIGGERS
[TRIGGER:<ID>]
when: <condition or cause>
effect: <resulting effect>
alert: <who is alerted / what changes, or None>

---------------------------------------------------------------------
EXTRACTION LOGIC
---------------------------------------------------------------------
When you receive raw module text:
- Idenfity the ADVENTURE overview, summary, plot hooks, background, tone and themes.
- Identify each distinct AREA (room, location, numbered keyed area).
- Identify any infered AREAs from text (world, outside, forest, garden).
- Build an AREA block for each.
- Extract NPCs described with personality, role, dialogue, or relationships.
- Extract MONSTER stat blocks and monsters described in encounters.
- Extract EVENTS for major beats, quest hooks, or scripted scenes.
- Extract ITEMs for notable treasure, quest items, magic items, special props.
- Extract TRIGGERs for mechanical cause-effect (e.g., "opening the door
- Extract TRIGGERs for NPC interactions that move the story along.
- Extract ADVENTURE adventure background / opening history.
- Extract ADVENTURE setting information.
- Extract ADVENTURE themes, tone, and atmosphere.
- Extract ADVENTURE world lore and legends.
- Extract ADVENTURE factions, key NPCs, motivations.
- Extract ADVENTURE story arcs and quest structure.
- Extract ADVENTURE important items and relics.
- Extract ADVENTURE environmental effects.
- Extract any internal logic or special rules.
- Create any additional ADVENTURE keys to provide information about the adventure.

---------------------------------------------------------------------
INFERENCE RULES
---------------------------------------------------------------------
- When the raw text is incomplete, infer reasonable defaults based on
  typical TTRPG adventures.
- If room numbers or IDs are unclear, assign AREA IDs in reading order:
  AREA:1A, AREA:1B, AREA:1C, then AREA:2A, 2B, etc.
- Compress multi-paragraph descriptions into a single long string in
  desc.long, preserving key details.
- Never leave a key undefined; if no data, use `None`.

---------------------------------------------------------------------
FINAL OUTPUT RULES
---------------------------------------------------------------------
- Output ONLY INI blocks.
- No markdown, no backticks, no commentary.
- Recommended order:
  1. ADVENTURE section
  1. All AREA sections
  2. All NPC sections
  3. All MONSTER sections
  4. All EVENT sections
  5. All ITEM sections
  6. All TRIGGER sections
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

