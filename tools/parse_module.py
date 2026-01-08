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
import yaml
import sys
from openai import OpenAI

# -----------------------------
# CONFIG
# -----------------------------

MODEL = "gpt-4.1"
OUTPUT_FILE = "module.json"
#SYSTEM_PROMPT="prompts/parse_module/parse_module_ds.prompt"
SYSTEM_PROMPT="prompts/parse_module/parse_module_yaml.prompt"

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

with open(SYSTEM_PROMPT, 'r') as file:
    SYSTEM_INSTRUCTIONS = file.read()

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


# Validate YAML
try:
    module_data = yaml.safe_load(output_text)
except yaml.YAMLError as e:
    print("[!] Failed to parse YAML output")
    print(e)
    print(output_text)
    sys.exit(1)

# Validate JSON
#try:
#    module_data = json.loads(output_text)
#except json.JSONDecodeError as e:
#    print("[!] Failed to parse JSON output")
#    print(e)
#    print(output_text)
#    sys.exit(1)

# -----------------------------
# WRITE OUTPUT
# -----------------------------

#with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
#    json.dump(module_data, f, indent=2, ensure_ascii=False)

with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    yaml.dump(module_data, f, sort_keys=False, allow_unicode=True)

print(f"[+] Conversion complete: {OUTPUT_FILE}")
