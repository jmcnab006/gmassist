#!/usr/bin/env python3
"""
parse_adventure.py

Uploads a D&D 5e adventure PDF to OpenAI,
parses and analyzes its contents,
and converts it into a STRICT JSON module
for use with dmv3.py.

JSON ONLY. No INI. No YAML.
Fail-fast on invalid output.
"""

import json
import sys
import os
from openai import OpenAI

# -----------------------------
# CONFIG
# -----------------------------

#MODEL = "gpt-4.1"
MODEL = "gpt-4.1-mini"
DEFAULT_OUTPUT = "module.json"

SYSTEM_PROMPT_PATH = "prompts/parse_module/parse_module_json.prompt"

# -----------------------------
# CLI
# -----------------------------

if len(sys.argv) < 2:
    print("Usage: python parse_adventure.py <adventure.pdf> [output.json]")
    sys.exit(1)

PDF_PATH = sys.argv[1]
OUTPUT_FILE = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_OUTPUT

if not os.path.exists(PDF_PATH):
    print(f"[!] PDF not found: {PDF_PATH}")
    sys.exit(1)

# -----------------------------
# OPENAI CLIENT
# -----------------------------

client = OpenAI()

# -----------------------------
# LOAD SYSTEM PROMPT
# -----------------------------

if not os.path.exists(SYSTEM_PROMPT_PATH):
    print(f"[!] System prompt not found: {SYSTEM_PROMPT_PATH}")
    sys.exit(1)

with open(SYSTEM_PROMPT_PATH, "r", encoding="utf-8") as f:
    SYSTEM_PROMPT = f.read()

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
# PARSE REQUEST
# -----------------------------

print("[*] Parsing PDF into structured JSON module...")

response = client.responses.create(
    model=MODEL,
    input=[
        {
            "role": "system",
            "content": SYSTEM_PROMPT
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

output_text = response.output_text.strip()

# -----------------------------
# VALIDATE JSON
# -----------------------------

try:
    module_data = json.loads(output_text)
except json.JSONDecodeError as e:
    print("[!] MODEL OUTPUT IS NOT VALID JSON")
    print("---- ERROR ----")
    print(e)
    print("---- RAW OUTPUT ----")
    print(output_text)
    sys.exit(1)

# -----------------------------
# BASIC SCHEMA VALIDATION
# -----------------------------

REQUIRED_TOP_LEVEL_KEYS = {
    "module",
    "threads",
    "locations",
    "areas",
    "items",
    "npcs",
    "factions",
    "consequences",
    "world_state",
    "encounter_pool",
    "plot_branches",
    "xref_index"
}

missing = REQUIRED_TOP_LEVEL_KEYS - set(module_data.keys())
if missing:
    print("[!] JSON MODULE IS MISSING REQUIRED KEYS")
    print("Missing:", ", ".join(missing))
    sys.exit(1)

if not isinstance(module_data["module"], dict):
    print("[!] 'module' must be an object")
    sys.exit(1)

for key in ("id", "title", "starting_area"):
    if key not in module_data["module"]:
        print(f"[!] module.{key} is required")
        sys.exit(1)

# -----------------------------
# WRITE OUTPUT
# -----------------------------
out_dir = os.path.dirname(OUTPUT_FILE)
if out_dir:
    os.makedirs(out_dir, exist_ok=True)

with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(module_data, f, indent=2, ensure_ascii=False)

print(f"[+] Conversion complete: {OUTPUT_FILE}")

