#!/usr/bin/python3
import json
import os
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


# -------------------------------
# NPC Manager
# -------------------------------
class NPCManager:
    def __init__(self, npc_file="npc_store.json"):
        self.npc_file = npc_file
        self.npcs = {}
        if os.path.exists(npc_file):
            self.load()

    def load(self):
        with open(self.npc_file, "r", encoding="utf-8") as f:
            self.npcs = json.load(f)

    def save(self):
        with open(self.npc_file, "w", encoding="utf-8") as f:
            json.dump(self.npcs, f, indent=2)

    def get_all_npc_descriptions(self):
        desc = []
        for name, data in self.npcs.items():
            desc.append(f"NPC: {name}\n{json.dumps(data, indent=2)}")
        return "\n\n".join(desc)

    def ensure_npc(self, name):
        if name not in self.npcs:
            self.npcs[name] = {
                "name": name,
                "appearance": "",
                "personality": "",
                "goals": "",
                "knowledge": "",
                "relationship_to_party": ""
            }
            self.save()

    def update_npc(self, name, field, value):
        self.ensure_npc(name)
        self.npcs[name][field] = value
        self.save()


# -------------------------------
# Player Character Manager
# -------------------------------
class PlayerCharacterManager:
    def __init__(self, pc_file="pc_store.json"):
        self.pc_file = pc_file
        self.pcs = {}
        if os.path.exists(pc_file):
            self.load()

    def load(self):
        with open(self.pc_file, "r", encoding="utf-8") as f:
            self.pcs = json.load(f)

    def save(self):
        with open(self.pc_file, "w", encoding="utf-8") as f:
            json.dump(self.pcs, f, indent=2)

    def ensure_pc(self, name):
        if name not in self.pcs:
            self.pcs[name] = {
                "name": name,
                "race": "",
                "class": "",
                "appearance": "",
                "personality": "",
                "backstory": "",
                "notes": ""
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
            "active_npcs": []
        }
        if os.path.exists(file_path):
            self.load()

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
def load_module_text():
    path = "data/module_text.txt"
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            console.print("[bold green]Module loaded successfully.[/bold green]")
            return f.read()

    console.print("[yellow]No module found. Running without module_text.[/yellow]")
    return ""


# -------------------------------
# DM Response Generator
# -------------------------------
def generate_dm_response(session, npc_mgr, pc_mgr, user_input, module_text):

    session.add_message("user", user_input)

    # UPDATED REQUIREMENTS BLOCK
    system_prompt = f"""
You are an AI Dungeon Master.

REQUIREMENTS:
- Limit descriptions to **1–2 paragraphs maximum** unless the player asks for a "detailed" description.
- Limit descriptions to **1–2 sentences maximum** when the player asks for a "brief" or "breif" description.
- Use vivid sensory details but remain concise.
- Use appearance, personality, and backstory for PCs and NPCs.
- NEVER describe player actions—only the world's reaction.
    - Maintain full continuity using the story log.
- If module text is available, integrate it naturally.
- Do not narrate information the players would not know by sight or previously provided information.
- Players do not know NPC names unless introduced.
- NPC character names are only known after an introduction by the NPC or another NPC.

MODULE TEXT (optional):
{module_text[:30000]}

NPC RECORDS:
{npc_mgr.get_all_npc_descriptions()}

PLAYER CHARACTER RECORDS:
{pc_mgr.get_all_pc_descriptions()}

STORY LOG:
{json.dumps(session.session["story_log"], indent=2)}
"""

    messages = [{"role": "system", "content": system_prompt}] + session.session["messages"]

    response = client.chat.completions.create(
        model="gpt-4.1",
        messages=messages,
        max_tokens=600
    )

    reply = response.choices[0].message.content
    session.add_message("assistant", reply)
    session.add_story_event(reply)

    return reply


# -------------------------------
# MAIN APPLICATION
# -------------------------------
def main():
    console.print("[bold cyan]=== AI Dungeon Master ===[/bold cyan]")
    console.print("Type 'exit' to quit.\n")

    session_path = "sessions/default.json"

    os.makedirs("sessions", exist_ok=True)

    session = SessionManager(session_path)
    npcs = NPCManager()
    pcs = PlayerCharacterManager()

    module_text = load_module_text()

    console.print("\n[bold green]DM is ready. Begin your adventure.[/bold green]\n")

    while True:
        user_input = input(GREEN + "You: " + RESET)
        if user_input.lower() in ("exit", "quit"):
            console.print("[red]Goodbye![/red]")
            break

        reply = generate_dm_response(session, npcs, pcs, user_input, module_text)

        # Render the DM response with full Markdown support
        md = Markdown(reply)
        console.print(Panel(md, border_style="yellow"))


if __name__ == "__main__":
    main()

