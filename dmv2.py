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
            "combat_active": False,
            "combatants": []
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
def load_module_text(path):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            console.print(f"[bold green]Module {path} loaded successfully.[/bold green]")
            return f.read()

    console.print("[yellow]No module found. Running without loaded adventure.[/yellow]")
    return ""


# -------------------------------
# DM Response Generator
# -------------------------------
def generate_dm_response(session, npc_mgr, pc_mgr, user_input, module_text):

    session.add_message("user", user_input)

    # UPDATED REQUIREMENTS BLOCK
    system_prompt = f"""
You are an AI Dungeon Master running a Dungeons & Dragons adventure. 
	- Use MODULE DATA to narrate scenes, roleplay NPCs, manage exploration, and maintain story continuity.
	- Limit default area descriptions to 1–2 paragraphs. If a player requests a brief/“breif” description, provide 1–2 sentences. If they request a detailed description, provide 3–5 paragraphs. 
	- ALWAYS Use vivid sensory imagery but remain concise. 
	- NEVER describe player actions
	- ONLY describe the world’s reaction to them. 
	- NEVER reveal NPC names, area names, secrets, hidden items, or trap mechanics UNLESS they are discovered in-world. 
	- NEVER narrate anything the characters would not naturally perceive.
	- ALWAYS Use desc.short and desc.long from each AREA block to describe locations. 
	- ONLY mention items, encounters, and visible features the characters can directly observe. 
	- ALWAYS Roleplay NPCs using the motivations, dialogue hooks, personality notes, secrets, and known information. 
	- NPCs should ONLY reveal information they actually know. 
	- Items should ONLY be revealed when visible or discovered. 
	- EVENTs should trigger when player actions match their conditions. 
	- TRIGGERs such as traps or magical effects must activate immediately when their requirements are met.
	- NEVER reveal TRIGGERs or EVENTs or their mechanics before they occur. 
	- Monsters may be described atmospherically but their stats are not used unless requested.
	- ALWAYS Use connections between areas when players move.
	- Be creative when AREAs lack cohesive interconnectivity.
	- COMBAT is not resolved here. 
	- Your ONLY job during COMBAT is to determine when it begins.
	- COMBAT begins when appropriate TRIGGERs or EVENTs occur such as an ambush, trap activation, hostile action, or event.
	- Announce that combat begins and identify the creatures involved. Provide only a brief cinematic setup. Do not run initiative, attacks, damage, or combat rounds.
	- ALWAYS maintain complete continuity using the story log. 
	- Track discovered clues, opened passages, solved puzzles, triggered events, and changing NPC states. 
	- If unsure whether players know something, assume they do not. 
	- Stay consistent with prior descriptions and MODULE DATA provide additional detail for vivid imagery.
	- Speak in-character for NPCs using their tone, hooks, and motivations, be creative. 
	- Avoid information dumps unless the NPC would naturally give them. 
	- NEVER reveal MODULE DATA content directly or break immersion with meta commentary.
	- ALWAYS react logically to player actions. 
	- ALWAYS move the story forward using the adventure’s tone and themes.
	- Your goal is to provide immersive, concise narration and roleplay while faithfully using the MODULE DATA, maintaining continuity, and triggering—but never resolving—combat.
    - If the players do nothing TRY and MOVE the story along maintaining the story theme and tone.
    - ALWAYS Roleplay NPC dialogue, decision-making, and reactions to the party’s choices in detail.
    - NEVER Roleplay PC dialogue or decision-making. 
    - If statistics or stats are asked for, provide statistics blocks as appropriate for the adventure or OGL


MODULE DATA:
{module_text}

PLAYER CHARACTER RECORDS:
{pc_mgr.get_all_pc_descriptions()}

STORY LOG:
{json.dumps(session.session["story_log"], indent=2)}

    """
    messages = [{"role": "system", "content": system_prompt}] + session.session["messages"]

    response = client.chat.completions.create(
        #model="gpt-4.1",
        model="gpt-4.1-mini",
        messages=messages,
        max_tokens=600
    )

    reply = response.choices[0].message.content
    session.add_message("assistant", reply)
    session.add_story_event(reply)

    return reply

def process_dm_command(cmd, session, npc_mgr, pc_mgr, module_text):

    # Command: /combat
    if cmd == "/combat":
        session.session["combat_active"] = True
        session.session["combatants"] = []  # reset last combatants
        session.save()

        # Ask AI to generate combatants based on scene/NPCs
        prompt = """
A combat encounter has been manually triggered by the Dungeon Master.

Please:
1. Generate a combatant list.
2. Provide brief stat blocks for each combatant.
3. Only reveal names for NPCs the players know.
4. Use descriptions for unknown enemies (e.g., "Armored Guard", "Young Bandit").
5. Use alignment-based willingness to fight.
"""

        reply = generate_dm_response(
            session,
            npc_mgr,
            pc_mgr,
            prompt,
            module_text
        )

        # Store combatants from the last assistant output (extraction optional)
        session.session["combatants"].append(reply)
        session.save()
        return True

    # Command: /statblocks
    if cmd == "/statblocks":
        if not session.session["combat_active"]:
            console.print("[red]Combat is not active.[/red]")
            return True

        prompt = f"""
The Dungeon Master requests stat blocks for active combatants.
Use the previously generated combatant list:

{session.session["combatants"]}

Provide:
- A clear list
- A concise stat block for each combatant
"""

        reply = generate_dm_response(
            session, npc_mgr, pc_mgr, prompt, module_text
        )
        return True

    # Unknown command
    return False

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

    return parser.parse_args()

# -------------------------------
# MAIN APPLICATION
# -------------------------------
def main():
    args = parse_args()
    console.print("[bold cyan]=== AI Dungeon Master ===[/bold cyan]")
    console.print("Type 'exit' to quit.\n")

    #os.makedirs("sessions", exist_ok=True)

    session = SessionManager(args.session)
    npcs = NPCManager()
    pcs = PlayerCharacterManager(args.pcstore)

    module_text = load_module_text(args.module)

    console.print("\n[bold green]DM is ready. Begin your adventure.[/bold green]\n")

    while True:
        user_input = input(GREEN + "You: " + RESET)

        # Exit
        if user_input.lower() in ("exit", "quit"):
            console.print("[red]Goodbye![/red]")
            break

        # Slash command (DM-only)
        if user_input.startswith("/"):
            handled = process_dm_command(
                user_input, session, npcs, pcs, module_text
            )
            if handled:
                continue

        # Normal player input → AI response
        reply = generate_dm_response(session, npcs, pcs, user_input, module_text)

        md = Markdown(reply)
        console.print(Panel(md, border_style="yellow"))

if __name__ == "__main__":
    main()

