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
            console.print(f"[bold green]PCs: {self.pc_file} [/bold green]\n")

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
    module_prompt = """
MODULE DATA:
{module_text}

PLAYER CHARACTER RECORDS:
{pc_mgr.get_all_pc_descriptions()}

STORY LOG:
{json.dumps(session.session["story_log"], indent=2)}
"""
    system_prompt = f"""
You are an AI Dungeon Master running a Dungeons & Dragons adventure. 
    - Use MODULE DATA to:
        - narrate scenes
        - roleplay NPCs
        - navigate through the adventure
        - and maintain story continuity
	- LIMIT descriptions to 1–2 paragraphs.
    - LIMIT descriptions to 1-2 sentances if a request includes "brief"/“breif”.
    - LIMIT descriptions to 3-4 paragraphs if a request includes "detail"/"details"/"detailed". 
	- Use sensory imagery but remain concise.
	- ALWAYS Roleplay NPCs.
	- NEVER describe player actions.
	- NEVER reveal NPC names, area names, secrets, hidden items, or trap mechanics UNLESS they are discovered. 
	- NEVER narrate anything the characters would not naturally perceive.
	- Describe ONLY the world’s reaction to player actions. 
	- Describe ONLY items, encounters, features the characters can observe.
        - example: A character does not know that a box contains a cat, until they open the box.
        - example: A character does not know a room contains a winch unless the characters enter the room. 
        - example: A character does not know the purpose of an item until they study it.
        - exmaple: A character does not know the contents of a book until they read it.
	- NPCs ONLY reveal information they actually know.
	- Items are described ONLY when visible or revealed. 
	- EVENTs should trigger when player actions match their conditions, be creative. 
	- TRIGGERs such as traps or magical effects must activate immediately when their requirements are met.
	- NEVER reveal TRIGGERs or EVENTs or their mechanics before they occur. 
	- Monsters may be described atmospherically but their stats are not used unless requested.
	- ALWAYS Use connections between areas when players move.
    - ALWAYS add the ROOM or AREA ID as a BOLD HEADER when characters move into an area.
	- Be creative when AREAs lack cohesive interconnectivity.
	- Maintain complete continuity using the story log. 
	- Track discovered clues, opened passages, solved puzzles, triggered events, and changing NPC states. 
	- If unsure whether players know something, assume they do not. 
	- Speak in-character for NPCs using their personality, goals, and motivations.
	- Avoid information dumps unless the NPC would naturally give them. 
	- NEVER reveal MODULE DATA content directly or break immersion with meta commentary.
	- ALWAYS react logically to player actions. 
	- Your goal is to provide immersive, concise narration and roleplay while faithfully using the MODULE DATA, maintaining continuity, and triggering—but never resolving—combat.
    - ALWAYS Roleplay NPC dialogue, decision-making, and reactions to the party’s choices in detail.
    - NEVER Roleplay PC dialogue or decision-making. 
    - If statistics or stats are asked for, provide statistics blocks as appropriate for the adventure or OGL
    - ONLY provide information the characters can immediately observe.
    - Players have no intuitive knowledge of the adventure. They are "blind" to the plot. treat them as such.
    - When skill checks are required provide the Difficulty Class (DC). 
    - If a player or character rolls a Skill check determine its success by the Difficulty Class (DC).

COMBAT LOGIC:
- COMBAT means that the party or character is being attacked or is attacking another. This includes but is not limited to:
    - NPCs
    - Monsters
    - Items
    - Objects
    - Players (not encouraged)
- COMBAT occurs immediately if:
    - The story requires it.
    - Adventure text indicates the party is attacked.
    - The party or character attacks an NPC or Monster. 
    - An NPC or Monster attacks the party or character.
- COMBAT RESOLUTION:
    - Announce in bold text that "COMBAT BEGINS!" when COMBAT occurs.
    - Provide a stats block for the monsters involved.
    - Do not run initiative, attacks, damage, or combat rounds.
    - When asked for targets monsters attack determine appropriate targets. when in doubt, guess.
    

MODULE DATA:
{module_text}

PLAYER CHARACTER RECORDS:
{pc_mgr.get_all_pc_descriptions()}

STORY LOG:
{json.dumps(session.session["story_log"], indent=2)}

    """
    messages = [{"role": "system", "content": module_prompt}] + session.session["messages"]

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

