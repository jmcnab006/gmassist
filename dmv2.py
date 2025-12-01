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
                "background": "",
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
def load_module_text():
    path = "data/module.ini"
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
- Players do not know names of locations unless they are told by NPCs.

COMBAT RULES AND TRIGGERS:
- You must automatically initiate combat when:
    - The players attack or clearly threaten violence.
    - An NPC attempts to harm or restrain the players.
    - A story event logically escalates to combat.
- Announce combat with a brief description such as:
    **"Combat has begun! Roll Initiative."**

COMBATANT LIST AND STAT BLOCKS:
- When combat begins, generate a combatant list only include stat blocks for NPC's.
- Provide a brief D&D 5e–style stat summary for each NPC combatant:
    - Name (if known or introduced)
    - Creature type
    - AC
    - Hit Points
    - Speed
    - Attacks. Include +tohit and damage.
    - Key Abilities 
    - Special Traits
- For NPCs the players have NOT been introduced to:
    - DO NOT reveal names; use descriptions like “Bandit Leader”, “Armored Guard”, “Young Red Dragon”.
- Always separate combatant summaries into a list.
- Also weigh:
    - NPC personality traits
    - Goals and motivations
    - Fear, morale, or injuries
    - Overwhelming player force (may cause surrender)

DURING COMBAT:
- Describe combat in **1–2 paragraphs per turn** unless the player requests detailed narration.
- Do not play the players’ actions; only respond to them.
- Do not reveal enemy HP numerically unless appropriate; use descriptions like “bloodied”, “barely holding on”, “unharmed”.

END OF COMBAT:
- Clearly indicate when combat ends.
- Provide outcomes, loot (if any), NPC reactions, and narrative transitions.

MODULE TEXT:
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

# -------------------------------
# MAIN APPLICATION
# -------------------------------
def main():
    console.print("[bold cyan]=== AI Dungeon Master ===[/bold cyan]")
    console.print("Type 'exit' to quit.\n")

    session_path = "session.json"

    #os.makedirs("sessions", exist_ok=True)

    session = SessionManager(session_path)
    npcs = NPCManager()
    pcs = PlayerCharacterManager()

    module_text = load_module_text()

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

