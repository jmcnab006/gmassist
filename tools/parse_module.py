#!/usr/bin/python3
import os
import sys
import argparse
import pathlib
import time
from openai import OpenAI

# ----------------------------------------
# CONFIGURATION
# ----------------------------------------

# Model to use
OPENAI_MODEL = "gpt-4.1-mini"
#OPENAI_MODEL = "gpt-4.1"

# Rough character limit per chunk (safe for most models)
CHUNK_SIZE = 50000

# Seconds between calls to avoid rate limits
SLEEP_BETWEEN_CALLS = 1.0

# Output file name
#OUTPUT_FILE = "module.ini"
#DEBUG_OUTPUT_FILE = "module_output.debug"

PROMPT_PATH = "prompts/deepseek.prompt"

# ----------------------------------------
# OPENAI CLIENT
# ----------------------------------------

# Make sure OPENAI_API_KEY is set in your environment
# export OPENAI_API_KEY="your-key-here"
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))


def extract_pdf_to_text(pdf_path, output_path="module.raw"):
    reader = PdfReader(pdf_path)
    text = ""

    for page in reader.pages:
        try:
            text += page.extract_text() + "\n"
        except:
            pass

    os.makedirs("data", exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(text)

    print(f"Module saved to: {output_path}")

def parse_module(file_path: str ) -> str:
    # Upload a PDF we will reference in the variables
    file = client.files.create(
        file=open(file_path, "rb"),
        purpose="user_data",
    )

    print(f"[+] uploading file {file_path} ...")
    response = client.responses.create(
        model="gpt-5",
        reasoning={"effort": "low"},
        input=[
            {
                "role": "system",
                "content": "You are a Roleplaying Dungeon Master PDF Extractor. Read the ."
            },
            {
                "role": "user",
                "content": "Read the adventure module and convert it into a data structure that is easily read by gpt4.1-mini so that the model can assist a live DM running the adventure"
            }
           "id": "pmpt_abc123",
            "variables": {
                "topic": "Adventure Module",
                "reference_pdf": {
                    "type": "input_file",
                    "file_id": file.id,
                },
            },

        ],
        prompt={
            "id": "pmpt_abc123",
            "variables": {
                "topic": "Adventure Module",
                "reference_pdf": {
                    "type": "input_file",
                    "file_id": file.id,
                },
            },
        },
    )
    print(response.output_text)

def parse_args():
    parser = argparse.ArgumentParser(
        description="Extract structured module data from a PDF."
    )
    
    parser.add_argument(
        "infile",
        help="Path to the input adventure PDF file."
    )

    parser.add_argument(
        "outfile",
        nargs="?",
        default="module.raw",
        help="Path to write the extracted module.ini file."
    )

    return parser.parse_args()

if __name__ == "__main__":

    args = parse_args()
    try:
        parse_module(args.infile)

    except Exception as e:
        print(f"[ERROR] something didnt work: {e}")
