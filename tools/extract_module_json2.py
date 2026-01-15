#!/usr/bin/env python3
"""
extract_module_json.py

Multi-pass PDF parser for D&D 5e adventures.
Uses gpt-4.1 safely by extracting module components separately.
JSON ONLY. Fail-fast per component.
"""

import json
import sys
import os
from openai import OpenAI

# -----------------------------
# CONFIG
# -----------------------------

MODEL = "gpt-4.1-mini"
DEFAULT_OUTPUT = "module.json"

PROMPT_DIR = "prompts/parse_module"

EXTRACTION_PASSES = {
    "module": {
        "prompt": "module.prompt",
        "keys": ["module"]
    },
    "locations": {
        "prompt": "locations.prompt",
        "keys": ["locations", "areas"]
    },
    "npcs": {
        "prompt": "npcs.prompt",
        "keys": ["npcs", "factions"]
    },
    "items": {
        "prompt": "items.prompt",
        "keys": ["items", "encounter_pool"]
    },
    "plot": {
        "prompt": "plot.prompt",
        "keys": ["threads", "plot_branches", "consequences", "world_state"]
    },
    "xref": {
        "prompt": "xref.prompt",
        "keys": ["xref_index"]
    }
}

# -----------------------------
# CLI
# -----------------------------

if len(sys.argv) < 2:
    print("Usage: python extract_module_json.py <adventure.pdf> [output.json]")
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
# UPLOAD PDF (ONCE)
# -----------------------------

print("[*] Uploading PDF...")

with open(PDF_PATH, "rb") as f:
    uploaded = client.files.create(
        file=f,
        purpose="assistants"
    )

FILE_ID = uploaded.id
print(f"[+] File uploaded: {FILE_ID}")

# -----------------------------
# RUN EXTRACTION PASSES
# -----------------------------

final_module = {}

for name, cfg in EXTRACTION_PASSES.items():
    prompt_path = os.path.join(PROMPT_DIR, cfg["prompt"])

    if not os.path.exists(prompt_path):
        print(f"[!] Missing prompt: {prompt_path}")
        sys.exit(1)

    with open(prompt_path, "r", encoding="utf-8") as f:
        system_prompt = f.read()

    print(f"[*] Extracting {name}...")

    response = client.responses.create(
        model=MODEL,
        input=[
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": [
                    {"type": "input_file", "file_id": FILE_ID}
                ]
            }
        ]
    )

    raw = response.output_text.strip()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"[!] Invalid JSON in pass '{name}'")
        print(e)
        print(raw)
        sys.exit(1)

    for key in cfg["keys"]:
        if key not in data:
            print(f"[!] Missing key '{key}' in pass '{name}'")
            sys.exit(1)
        final_module[key] = data[key]

    print(f"[+] {name} extracted")

# -----------------------------
# FINAL VALIDATION
# -----------------------------

required = {
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

missing = required - set(final_module.keys())
if missing:
    print("[!] FINAL MODULE MISSING KEYS:", ", ".join(missing))
    sys.exit(1)

# -----------------------------
# WRITE OUTPUT
# -----------------------------

out_dir = os.path.dirname(OUTPUT_FILE)
if out_dir:
    os.makedirs(out_dir, exist_ok=True)

with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(final_module, f, indent=2, ensure_ascii=False)

print(f"[+] Module extraction complete: {OUTPUT_FILE}")
