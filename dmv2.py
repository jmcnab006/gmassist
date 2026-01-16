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

SYSTEM_PROMPT_FILE="system.prompt"
DEVELOPER_PROMPT_FILE="developer.prompt"
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

EXECUTION RULES
- ALWAYS add the AREA or LOC as a **BOLD HEADER** when entered
- ALWAYS respect defined area connections
- Trigger NARRATIVE_THREADS and CONSEQUENCES silently and automatically
- Track all world-state changes in the STORY LOG

IMMERSION
- Never reference mechanics, flags, timelines, or module structure
- Never explain why something happens—only show that it does
- Avoid exposition unless delivered naturally by an NPC

ROLEPLAY
- Portray NPCs with distinct voices, emotions, and intent
- Let NPC reactions drive scenes instead of narration dumps

GOAL
Deliver immersive, concise storytelling while:
- Faithfully executing MODULE DATA
- Maintaining strict continuity
- Supporting branching timelines and fail-forward outcomes
- Handing off combat cleanly to the human DM

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
        default="session.json",
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

