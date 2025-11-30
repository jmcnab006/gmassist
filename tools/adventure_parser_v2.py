import os
import time
import fitz  # PyMuPDF for image extraction
from typing import List

from openai import OpenAI
from pdfminer.high_level import extract_text as pdfminer_extract_text

# ----------------------------------------
# CONFIGURATION
# ----------------------------------------

OPENAI_MODEL = "gpt-4.1-mini"
VISION_MODEL = "gpt-4.1-mini"   # same family supports vision + OCR

CHUNK_SIZE = 12000
SLEEP_BETWEEN_CALLS = 1.0

OUTPUT_FILE = "module_output.txt"

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))


# ----------------------------------------
# UNIVERSAL SYSTEM PROMPT (INCLUDING MAPPING + OCR)
# ----------------------------------------

UNIVERSAL_SYSTEM_PROMPT = """
You are a universal TTRPG adventure module parser.

Your job is to convert ANY adventure PDF text and map images into a 
structured Format C module for use by an automated AI Dungeon Master.

You MUST extract:
- adventure meta (background, tone, hooks, themes)
- story beats
- all areas / rooms
- hallways
- stairs
- NPCs
- creatures
- items
- traps
- world state
- map labels from OCR
- map geometry (dimensions, doors, hallways, stairs)
- floor relationships
- door directions
- coordinate inference where possible
- square size from map legends
- secret door rules
- adjacency graphs

You MUST output ONLY well-formed Format C blocks:

[ADVENTURE_META] ...
[STORY_BEAT:<ID>] ...
[AREA:<ID>] ...
[HALLWAY:<ID>] ...
[STAIRS:<ID>] ...
[NPC:<NAME>] ...
[CREATURE:<NAME>] ...
[TRAP:<NAME>] ...
[ITEM:<NAME>] ...
[STATE] ...
[MAP_LABELS:<MAP_ID>] ...
[NARRATION_GUIDE] ...
[MAP_WARNINGS] ...

# --- MAP ACCURACY RULES ---

1. Floors:
Every AREA, HALLWAY, and STAIRS must include:
floor: <floor name>

2. Square size:
Extract from map legend or OCR:
map.square_size: <N ft>

3. Room dimensions:
dimensions: <WxL ft> or irregular: <describe shape>
Infer using grid squares when shown.

4. Doors:
doors:
  - direction: north/south/east/west
    type: standard/double/arched/secret/trapdoor
    leads_to: <AREA or HALLWAY>

5. Hallways:
Create [HALLWAY:<ID>] blocks for any unlabelled connectors.

6. Stairs:
[STAIRS:<ID>]
floor_A: ...
floor_B: ...
connects_A: ...
connects_B: ...
orientation: north/south/east/west

7. Secret doors:
Only include if explicitly labeled in text OR shown on map.

8. Coordinates:
geometry:
  estimated_center: (x,y) or unknown
  doors:
    - location: (x,y)
      direction: <dir>

9. OCR text labels MUST be included in [MAP_LABELS] block.

# --- STORY & DESCRIPTION RULES ---
desc.short: 1–2 lines
desc.long: 4–10 lines, atmospheric, sensory

# --- CONTINUITY ---
Extract all transitional narrative into STORY_BEAT blocks.

# --- OUTPUT RULES ---
- Only structured blocks
- No commentary
- No plain prose outside block format
- Never contradict the adventure
"""


# ----------------------------------------
# PDF TEXT EXTRACTION (pdfminer)
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
# PDF IMAGE EXTRACTION (maps)
# ----------------------------------------

def extract_images(pdf_path: str) -> List[str]:
    print("[+] Extracting images (likely maps)...")
    doc = fitz.open(pdf_path)
    image_paths = []
    for page_number, page in enumerate(doc):
        images = page.get_images(full=True)
        for img_index, img in enumerate(images):
            xref = img[0]
            extracted = doc.extract_image(xref)
            img_bytes = extracted["image"]
            filename = f"map_{page_number}_{img_index}.png"
            with open(filename, "wb") as f:
                f.write(img_bytes)
            image_paths.append(filename)
            print(f"    [+] Saved image: {filename}")
    return image_paths


# ----------------------------------------
# TEXT CHUNKING
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

    print(f"[+] Created {len(chunks)} text chunks")
    return chunks


# ----------------------------------------
# GPT UNIT: PARSE TEXT CHUNK
# ----------------------------------------

def parse_text_chunk(chunk: str, idx: int, total: int) -> str:
    print(f"[+] Parsing text chunk {idx+1}/{total}")

    result = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": UNIVERSAL_SYSTEM_PROMPT},
            {"role": "user", "content": chunk}
        ],
        temperature=0.3,
    )
    return result.choices[0].message.content


# ----------------------------------------
# GPT VISION: MAP GEOMETRY EXTRACTION
# ----------------------------------------

def parse_map_geometry(image_path: str) -> str:
    print(f"[+] Parsing map geometry from {image_path}")

    with open(image_path, "rb") as f:
        img_bytes = f.read()

    result = client.chat.completions.create(
        model=VISION_MODEL,
        messages=[
            {"role": "system", "content": UNIVERSAL_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_image",
                        "image_url": f"data:image/png;base64,{img_bytes.hex()}"
                    },
                    {
                        "type": "input_text",
                        "text": "Extract map geometry, floors, dimensions, doors, hallways, stairs, coordinates."
                    }
                ]
            }
        ],
        temperature=0.2,
    )

    return result.choices[0].message.content


# ----------------------------------------
# GPT VISION: OCR LABEL EXTRACTION
# ----------------------------------------

def extract_ocr_from_map_image(image_path: str) -> str:
    print(f"[+] Performing OCR on map: {image_path}")

    with open(image_path, "rb") as f:
        img_bytes = f.read()

    result = client.chat.completions.create(
        model=VISION_MODEL,
        messages=[
            {
                "role": "system",
                "content": """
Extract ALL readable text labels from the map image.
Return only:

[MAP_LABELS:<MAP_FILE>]
text:
  - "<label>"
  - "<label>"
  - ...
"""
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_image",
                        "image_url": f"data:image/png;base64,{img_bytes.hex()}"
                    },
                    {
                        "type": "input_text",
                        "text": "Extract every text label, room number, floor name, legend, arrow, and map annotation."
                    }
                ]
            }
        ],
        temperature=0.0,
    )

    return result.choices[0].message.content


# ----------------------------------------
# GRAPH CONSISTENCY CHECK
# ----------------------------------------

def graph_consistency_check(full_structured_text: str) -> str:
    print("[+] Running graph-consistency check...")

    check_prompt = """
You are a graph auditor for a TTRPG module.

Check the content for:
- unpaired doors
- orphan hallways
- unreachable rooms
- stairs without matching endpoints
- duplicate area IDs
- cycles that contradict map geometry
- missing floor metadata
- impossible room adjacencies

Respond ONLY as:

[MAP_WARNINGS]
- warning 1
- warning 2
...
or:

[MAP_WARNINGS]
- none
"""

    result = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": check_prompt},
            {"role": "user", "content": full_structured_text}
        ],
        temperature=0.0,
    )

    return result.choices[0].message.content


# ----------------------------------------
# MAIN MODULE GENERATOR
# ----------------------------------------

def generate_module(pdf_path: str, output_path: str = OUTPUT_FILE):

    # Step 1: Extract text
    text = extract_pdf_text(pdf_path)
    chunks = chunk_text(text, CHUNK_SIZE)

    # Step 2: Extract map images
#    images = extract_images(pdf_path)

    outputs = []

    # Step 3: Parse text chunks
    for i, c in enumerate(chunks):
        outputs.append(parse_text_chunk(c, i, len(chunks)))
        time.sleep(SLEEP_BETWEEN_CALLS)

    # Step 4: Parse map geometry + OCR for each map
    #for img in images:
    #    outputs.append(parse_map_geometry(img))
    #    time.sleep(SLEEP_BETWEEN_CALLS)
#
#        outputs.append(extract_ocr_from_map_image(img))
#        time.sleep(SLEEP_BETWEEN_CALLS)

    # Step 5: Combine structured content
    combined = "\n\n".join(outputs)

    # Step 6: Graph Consistency Pass
    warnings = graph_consistency_check(combined)
    combined += "\n\n" + warnings

    # Step 7: Save
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(combined)

    print(f"[+] DONE: Module written to {output_path}")


# ----------------------------------------
# CLI ENTRY
# ----------------------------------------

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python adventure_parser.py <file.pdf> [output]")
        exit(1)

    pdf_file = sys.argv[1]
    out_file = sys.argv[2] if len(sys.argv) > 2 else OUTPUT_FILE

    generate_module(pdf_file, out_file)

