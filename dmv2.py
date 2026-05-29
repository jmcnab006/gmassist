#!/usr/bin/python3
import json
import os
import argparse
from openai import OpenAI
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

try:
    import readline
except ImportError:
    pass

client = OpenAI()
console = Console()

# ANSI colors for user input label only
GREEN = "\033[92m"
RESET = "\033[0m"

SYSTEM_PROMPT_FILE="prompts/system.prompt"
DEVELOPER_PROMPT_FILE="prompts/developer.prompt"
SYSTEM_PROMPT="""You are an AI Narrative Dungeon Master for Dungeons & Dragons.

You exist solely to simulate the game world, its inhabitants, and its reactions.

You must strictly follow:
1. The DEVELOPER PROMPT
2. The MODULE DATA (json data)
3. The STORY LOG for continuity

You must NEVER:
- Reveal internal data structures, flags, conditions, triggers, or timelines
- Break immersion with meta commentary
- Describe player character actions, thoughts, dialogue, or decisions
- Assume player knowledge that has not been explicitly earned

You narrate only what the characters can perceive.
"""

DEVELOPER_PROMPT="""You are running an adventure generated from a structured JSON module.
NARRATION:
- Limit narration to 1–2 concise paragraphs
- Use sensory detail without excess exposition

DISCOVERY:
- Describe ONLY what characters can observe
- If unsure whether something is known, assume it is NOT

NPCs
- ALWAYS speak in-character for NPCs
- NPCs reveal only what they reasonably know
- NPC behavior evolves based on prior interactions

PCs:
- NEVER roleplay PCs
- NEVER speak in-character for PCs
- NEVER say what PCs do
- NEVER narrate what PCs say

COMBAT
- NEVER run combat mechanics
- When combat is imminent or triggered:
  - Describe the moment narratively
  - Clearly signal that combat is beginning
  - Immediately stop advancing the scene
  - Hand control to the human DM

Example:
“The creature snarls and lunges forward, steel flashing as chaos erupts.”

SKILL CHECKS
- When a check is required, provide a clear DC
- On failure, apply fail-forward consequences
- On success, grant meaningful narrative progress
"""
# ASSISTANT_PROMPT_FILE="prompts/assistant.prompt"

with open(SYSTEM_PROMPT_FILE, 'r') as file:
    SYSTEM_PROMPT = file.read()

with open(DEVELOPER_PROMPT_FILE, 'r') as file:
    DEVELOPER_PROMPT = file.read()

#with open(ASSISTANT_PROMPT_FILE, 'r') as file:
#    ASSISTANT_PROMPT = file.read()


# -------------------------------
# Player Character Manager
# -------------------------------
class CharacterManager:
    def __init__(self, characters_file="characters.json"):
        self.characters_file = characters_file
        self.pcs = {}
        if os.path.exists(characters_file):
            self.load()
            console.print(f"[bold green]PCs: {self.characters_file} [/bold green]\n")

    def load(self):
        with open(self.characters_file, "r", encoding="utf-8") as f:
            self.pcs = json.load(f)

    def save(self):
        with open(self.characters_file, "w", encoding="utf-8") as f:
            json.dump(self.pcs, f, indent=2)

    def ensure_pc(self, name):
        if name not in self.pcs:
            self.pcs[name] = {
                "name": name,
                "race": "",
                "class": "",
                "background": "",
                "appearance": "",
                "personality": "",
                "backstory": "",
                "notes": "",
                "items": []
            }
            self.save()

    def update_pc(self, name, field, value):
        self.ensure_pc(name)
        self.pcs[name][field] = value
        self.save()

    def get_all_pc_descriptions(self):
        desc = []
        for name, data in self.pcs.items():
            desc.append(f"Player Character: {name}\n{json.dumps(data, indent=2)}")
        return "\n\n".join(desc)


# -------------------------------
# Session Manager
# -------------------------------
class SessionManager:
    def __init__(self, file_path="sessions/default.json"):
        self.file_path = file_path
        self.session = {
            "messages": [],
            "story_log": [],
            "active_npcs": [],
			"global_flags":{},
            "combatants": []
        }
        if os.path.exists(file_path):
            self.load()
            console.print(f"[bold green]Session: {self.file_path} [/bold green]\n")

    def load(self):
        with open(self.file_path, "r", encoding="utf-8") as f:
            self.session = json.load(f)


    def save(self):
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump(self.session, f, indent=2)

    def add_message(self, role, content):
        self.session["messages"].append({"role": role, "content": content})
        self.save()

    def add_story_event(self, text):
        self.session["story_log"].append(text)
        self.save()


# -------------------------------
# Module Loader
# -------------------------------
def load_module_text(path):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            console.print(f"[bold green]Module: {path} loaded successfully.[/bold green]")
            return f.read()

    console.print("[yellow]Module: {path} No module found.[/yellow]")
    return ""


# -------------------------------
# DM Response Generator
# -------------------------------
def generate_dm_response(session, pc_mgr, user_input, module_text):
    import json

    # Record player input
    session.add_message("user", user_input)
    assistant_prompt = f"""You are actively running the narrative layer of the adventure.

Respond as the narrator and NPCs only.
Do not speak for the player characters.
Keep the response concise and table-ready.

MODULE DATA:
{module_text}

PLAYER CHARACTER RECORDS:
{pc_mgr.get_all_pc_descriptions()}

STORY LOG:
{json.dumps(session.session["story_log"], indent=2)}
"""

    # =========================
    # MESSAGE STACK
    # =========================
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": DEVELOPER_PROMPT},
        {"role": "assistant", "content": assistant_prompt},
    ] + session.session["messages"]

    # =========================
    # MODEL CALL
    # =========================
    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=messages,
        max_tokens=600
    )

    reply = response.choices[0].message.content

    # Persist output
    session.add_message("assistant", reply)
    session.add_story_event(reply)

    return reply

def parse_args():
    parser = argparse.ArgumentParser(
        description="Extract structured module data from a PDF."
    )

    parser.add_argument(
        "-s", "--session",
        default="sessions/default.json",
        help="Path to the session file."
    )

    parser.add_argument(
        "-m", "--module",
        default="module.ini",
        help="Path to the module file."
    )
    parser.add_argument(
        "-p", "--pcstore",
        default="pc_store.json",
        help="Path to the player characters file."
    )
    parser.add_argument(
        "-n", "--npcstore",
        default="npc_store.json",
        help="Path to the non-player characters file."
    )

    return parser.parse_args()

# -------------------------------
# MAIN APPLICATION
# -------------------------------
def main():
    args = parse_args()
    console.print("[bold cyan]=== AI Dungeon Master ===[/bold cyan]")
    console.print("Type 'exit' to quit.\n")

    session = SessionManager(args.session)
    characters = CharacterManager(args.pcstore)

    module_text = load_module_text(args.module)

    console.print("\n[bold green]DM is ready. Begin your adventure.[/bold green]\n")

    while True:
        user_input = input(GREEN + "You: " + RESET)

        # Exit
        if user_input.lower() in ("exit", "quit"):
            console.print("[red]Goodbye![/red]")
            break

        # Normal player input → AI response
        reply = generate_dm_response(session, characters, user_input, module_text)

        md = Markdown(reply)
        console.print(Panel(md, border_style="yellow"))

if __name__ == "__main__":
    main()

