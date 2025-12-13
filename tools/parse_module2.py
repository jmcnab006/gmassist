#!/usr/bin/env python3

"""
pdf_to_dm_module.py

Uploads a D&D 5e adventure PDF to OpenAI,
parses and analyzes its contents,
and converts it into a structured JSON data model
suitable for a Dungeon Master Assistant.

This script ONLY performs conversion.
No gameplay, narration, or combat logic.
"""

import json
import sys
from openai import OpenAI

# -----------------------------
# CONFIG
# -----------------------------

MODEL = "gpt-4.1-mini"
OUTPUT_FILE = "module.json"

# -----------------------------
# VALIDATION
# -----------------------------

if len(sys.argv) < 2:
    print("Usage: python pdf_to_dm_module.py <adventure.pdf> [output.json]")
    sys.exit(1)

PDF_PATH = sys.argv[1]
if len(sys.argv) > 2:
    OUTPUT_FILE = sys.argv[2]

# -----------------------------
# OPENAI CLIENT
# -----------------------------

client = OpenAI()

# -----------------------------
# UPLOAD PDF
# -----------------------------

print("[*] Uploading PDF...")

with open(PDF_PATH, "rb") as f:
    uploaded_file = client.files.create(
        file=f,
        purpose="assistants"
    )

print(f"[+] Uploaded file id: {uploaded_file.id}")

# -----------------------------
# SYSTEM INSTRUCTIONS
# -----------------------------

SYSTEM_INSTRUCTIONS = """
You are a data extraction and conversion engine.

Your task:
- Analyze a Dungeons & Dragons 5th Edition adventure PDF
- Extract ALL adventure content
- Structure the content extracted
- Convert it into a strict JSON data model
- Do NOT add new lore, encounters, or content
- Do NOT narrate or summarize creatively
- Preserve original intent and mechanics
- Preserve original plot and subplots

The output will be consumed by another AI model acting as a Dungeon Master assistant.

Follow these rules strictly:

GENERAL
- Output VALID JSON ONLY
- No markdown
- No commentary
- No trailing text
- Use null if information is missing
- Use arrays for multiple entries
- Use objects keyed by IDs where applicable

IDENTIFIERS
- Areas: AREA:1, AREA:2A, AREA:3B, etc.
- Rooms: ROOM:1A, ROOM:1B, etc.
- NPCs: NPC:<Name>
- Monsters: MON:<Name>
- Quests: QUEST:<ID>
- Items: ITEM:<Name>

DATA MODEL
You MUST use this top-level structure:

{
  "metadata": {
    "title": "",
    "source": "",
    "edition": "5e",
    "recommended_level": "",
    "setting": "",
    "themes": []
  },
  "adventure": {
    "summary": "",
    "background": ""
  },
  "hooks": [
    {
      "id": "",
      "description": ""
    }
  ],
  "quests": [
    {
      "id": "",
      "name": "",
      "type": "main|side|optional",
      "description": "",
      "objectives": [],
      "rewards": []
    }
  ],
  "areas": {
    "AREA:ID": {
      "name": "",
      "description": "",
      "rooms": ["ROOM:ID"],
      "notes": ""
    }
  },
  "rooms": {
    "ROOM:ID": {
      "area": "AREA:ID",
      "name": "",
      "description": "",
      "features": [],
      "exits": [],
      "encounters": [],
      "items": [],
      "triggers": []
    }
  },
  "npcs": {
    "NPC:Name": {
      "role": "",
      "description": "",
      "personality": "",
      "goals": "",
      "location": ""
    }
  },
  "monsters": {
    "MON:Name": {
      "type": "",
      "description": "",
      "location": "",
      "tactics": ""
    }
  },
  "items": {
    "ITEM:Name": {
      "type": "",
      "description": "",
      "location": ""
    }
  },
  "events": [
    {
      "id": "",
      "description": "",
      "location": "",
      "outcome": ""
    }
  ],
  "triggers": [
    {
      "id": "",
      "condition": "",
      "effect": "",
      "location": ""
    }
  ],
  "traps": [
    {
      "id": "",
      "trigger": "",
      "effect": "",
      "disarm": "",
      "location": ""
    }
  ]
}

IMPORTANT
- Extract traps, triggers, and scripted events explicitly
- Keep descriptions concise but complete
- Preserve adventure flow and dependencies
"""

# -----------------------------
# PARSE REQUEST
# -----------------------------

print("[*] Parsing PDF into structured DM module...")

response = client.responses.create(
    model=MODEL,
    input=[
        {
            "role": "system",
            "content": SYSTEM_INSTRUCTIONS
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "input_file",
                    "file_id": uploaded_file.id
                }
            ]
        }
    ]
)

# -----------------------------
# EXTRACT OUTPUT
# -----------------------------

output_text = response.output_text.strip()

# Validate JSON
try:
    module_data = json.loads(output_text)
except json.JSONDecodeError as e:
    print("[!] Failed to parse JSON output")
    print(e)
    print(output_text)
    sys.exit(1)

# -----------------------------
# WRITE OUTPUT
# -----------------------------

with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(module_data, f, indent=2, ensure_ascii=False)

print(f"[+] Conversion complete: {OUTPUT_FILE}")
