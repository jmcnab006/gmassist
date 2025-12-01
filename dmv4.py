#!/usr/bin/python3
import json
import os
import re
from openai import OpenAI
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

try:
    import readline  # noqa
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
            "combatants": [],
            # Combat state
            "initiative": {
                "players": {},
                "npcs": {}
            },
            "turn_order": [],
            "current_turn_index": 0,
            "pending_npc_resolution": None,  # NPC action waiting on hit/miss/save/fail
            "npc_hp": {},  # NPC/monster HP tracking
        }
        if os.path.exists(file_path):
            self.load()
        else:
            self.save()
        self._ensure_combat_fields()

    def _ensure_combat_fields(self):
        self.session.setdefault("combat_active", False)
        self.session.setdefault("combatants", [])
        self.session.setdefault("initiative", {"players": {}, "npcs": {}})
        self.session.setdefault("turn_order", [])
        self.session.setdefault("current_turn_index", 0)
        self.session.setdefault("pending_npc_resolution", None)
        self.session.setdefault("npc_hp", {})

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
    path = "data/module/module.txt"
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

COMBAT RULES AND TRIGGERS:
- You must automatically initiate combat when:
    - The players attack or clearly threaten violence.
    - An NPC attempts to harm or restrain the players.
    - A story event logically escalates to combat.
- Announce combat with a brief description such as:
    **"Combat has begun! Roll Initiative."**

COMBATANT LIST AND STAT BLOCKS:
- When combat begins, generate a combatant list and ONLY include stat blocks for NPCs or monsters (never PCs).
- Provide a brief D&D 5e–style stat summary for each NPC/monster combatant:
    - Name (if known or introduced)
    - Creature type
    - AC
    - Hit Points
    - Speed
    - Attacks (include +to hit and damage)
    - Key abilities
    - Special traits
- For NPCs/monsters the players have NOT been introduced to:
    - DO NOT reveal names; use descriptions like “Bandit Leader”, “Armored Guard”, “Young Red Dragon”.
- Always separate combatant summaries into a list.

ALIGNMENT-BASED WILLINGNESS TO FIGHT:
- NPC decision to fight or flee must factor alignment plus:
    - NPC personality traits
    - Goals and motivations
    - Fear, morale, or injuries
    - Overwhelming player force (may cause surrender)

DURING COMBAT:
- Describe combat in **1–2 paragraphs per turn** unless the player requests detailed narration.
- Do not play the players’ actions; only respond to them.
- You may state exact damage values, but do not reveal total enemy HP numerically.
- Use descriptive cues like “bloodied” or “barely holding on” instead of exact HP totals.

END OF COMBAT:
- Clearly indicate when combat ends.
- Provide outcomes, loot (if any), NPC reactions, and narrative transitions.

MODULE TEXT (optional, truncated):
{module_text[:50000]}

NPC RECORDS:
{npc_mgr.get_all_npc_descriptions()}

PLAYER CHARACTER RECORDS:
{pc_mgr.get_all_pc_descriptions()}

STORY LOG:
{json.dumps(session.session["story_log"], indent=2)}
"""

    messages = [{"role": "system", "content": system_prompt}] + session.session["messages"]

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=messages,
        max_tokens=600,
    )

    reply = response.choices[0].message.content
    session.add_message("assistant", reply)
    session.add_story_event(reply)

    return reply


# -------------------------------
# Initiative + HP Helpers
# -------------------------------
def collect_player_initiatives(pc_mgr):
    initiatives = {}
    if not pc_mgr.pcs:
        console.print("[yellow]No player characters found in pc_store.json.[/yellow]")
        return initiatives

    console.print("\n[bold cyan]Enter initiative for each player character.[/bold cyan]")
    for name in pc_mgr.pcs.keys():
        while True:
            raw = input(f"Initiative for {name} (leave blank to skip): ").strip()
            if raw == "":
                break
            try:
                initiatives[name] = int(raw)
                break
            except ValueError:
                console.print("[red]Please enter a valid integer or leave blank to skip.[/red]")

    return initiatives


def get_npc_initiatives_from_ai(session, npc_mgr, pc_mgr, module_text):
    combatant_text = "\n\n".join(map(str, session.session.get("combatants", [])))

    prompt = f"""
Combat has begun.

Based on the following combatant descriptions and stat blocks (NPCs/monsters only), 
assign a single D&D 5e initiative value (d20 + appropriate modifier) to EACH NPC or monster combatant.

Do NOT include player characters in this list.

Combatant information:
{combatant_text}

Return ONLY a valid JSON object mapping combatant names/descriptions to integer initiative values.
Example:
{{
  "Goblin": 14,
  "Bandit Captain": 19
}}
"""

    reply = generate_dm_response(session, npc_mgr, pc_mgr, prompt, module_text)

    start = reply.find("{")
    end = reply.rfind("}")
    if start == -1 or end == -1 or end <= start:
        console.print("[red]Could not parse NPC initiative JSON from AI response.[/red]")
        return {}

    json_text = reply[start:end + 1]
    try:
        data = json.loads(json_text)
    except json.JSONDecodeError:
        console.print("[red]Failed to decode NPC initiative JSON from AI response.[/red]")
        return {}

    npc_inits = {}
    for name, val in data.items():
        try:
            npc_inits[name] = int(val)
        except (TypeError, ValueError):
            continue

    return npc_inits


def get_npc_hp_from_ai(session, npc_mgr, pc_mgr, module_text):
    """
    Ask the AI to extract NPC/monster HP from the stat blocks
    into a JSON mapping: { "Name": hp_int, ... }.
    """
    combatant_text = "\n\n".join(map(str, session.session.get("combatants", [])))

    prompt = f"""
From the following NPC/monster combatant descriptions and stat blocks, extract each NPC or monster's name
and its current hit points (use its maximum hit points) as a JSON object.

Combatant information:
{combatant_text}

Return ONLY a valid JSON object mapping names to integer HP values.
Example:
{{
  "Goblin": 7,
  "Bandit Captain": 65,
  "Young Red Dragon": 133
}}
"""

    reply = generate_dm_response(session, npc_mgr, pc_mgr, prompt, module_text)

    start = reply.find("{")
    end = reply.rfind("}")
    if start == -1 or end == -1 or end <= start:
        console.print("[red]Could not parse NPC HP JSON from AI response.[/red]")
        return {}

    json_text = reply[start:end + 1]
    try:
        data = json.loads(json_text)
    except json.JSONDecodeError:
        console.print("[red]Failed to decode NPC HP JSON from AI response.[/red]")
        return {}

    npc_hp = {}
    for name, val in data.items():
        try:
            npc_hp[name] = int(val)
        except (TypeError, ValueError):
            continue

    return npc_hp


def build_initiative_order(player_inits, npc_inits):
    order = []
    for name, init_val in player_inits.items():
        order.append({"name": name, "type": "pc", "initiative": init_val})
    for name, init_val in npc_inits.items():
        order.append({"name": name, "type": "npc", "initiative": init_val})

    order.sort(key=lambda x: x["initiative"], reverse=True)
    return order


def advance_turn(session):
    turn_order = session.session.get("turn_order", [])
    if not turn_order:
        return
    idx = session.session.get("current_turn_index", 0)
    idx = (idx + 1) % len(turn_order)
    session.session["current_turn_index"] = idx
    session.save()


def get_current_turn_entry(session):
    """
    Return the current turn entry, skipping dead NPCs.
    Adjusts current_turn_index if needed.
    """
    turn_order = session.session.get("turn_order", [])
    if not turn_order:
        return None

    npc_hp = session.session.get("npc_hp", {})
    n = len(turn_order)
    idx = session.session.get("current_turn_index", 0) % n

    for _ in range(n):
        entry = turn_order[idx]
        if entry["type"] == "npc":
            hp = npc_hp.get(entry["name"])
            if hp is not None and hp <= 0:
                # Skip dead NPC
                idx = (idx + 1) % n
                continue
        # Found a valid entry (PC or alive/unknown NPC)
        session.session["current_turn_index"] = idx
        session.save()
        return entry

    return None


def end_combat(session):
    """
    Reset combat-related state.
    """
    session.session["combat_active"] = False
    session.session["initiative"] = {"players": {}, "npcs": {}}
    session.session["turn_order"] = []
    session.session["current_turn_index"] = 0
    session.session["pending_npc_resolution"] = None
    session.session["npc_hp"] = {}
    session.save()
    console.print("[bold green]All enemies are defeated or combat has ended.[/bold green]")


def parse_and_apply_pc_damage(session, reply_text):
    """
    Parse AI narration for PC turns and subtract damage from NPC HP.

    We assume that when a hostile NPC/monster takes damage, the AI uses:
      "<Exact NPC Name> takes <number> ... damage (XdY+Z)."
    """
    npc_hp = session.session.get("npc_hp", {})
    if not npc_hp:
        return

    # Map normalized names to actual names
    norm_to_name = {name.lower(): name for name in npc_hp.keys()}

    # Regex: capture "<Name> takes 7 ... damage"
    pattern = re.compile(r"([A-Z][A-Za-z0-9' _-]+?) takes (\d+) [^\.]* damage", re.IGNORECASE)

    changed = False

    for m in pattern.finditer(reply_text):
        raw_name = m.group(1).strip()
        dmg_str = m.group(2)
        try:
            dmg = int(dmg_str)
        except ValueError:
            continue

        key = raw_name.lower()
        if key not in norm_to_name:
            continue

        actual_name = norm_to_name[key]
        old_hp = npc_hp.get(actual_name)
        if old_hp is None:
            continue

        new_hp = max(0, old_hp - dmg)
        npc_hp[actual_name] = new_hp
        changed = True

        console.print(f"[red]{actual_name} takes {dmg} damage and is now at {new_hp} HP.[/red]")
        if new_hp <= 0:
            console.print(f"[bold red]{actual_name} is defeated![/bold red]")

    if changed:
        session.session["npc_hp"] = npc_hp
        session.save()

        # If all NPCs that we know about are at 0 or below, auto-end combat
        if npc_hp and all(hp <= 0 for hp in npc_hp.values()):
            end_combat(session)


# -------------------------------
# Combat Turn Handlers
# -------------------------------
def resolve_pc_turn(session, npc_mgr, pc_mgr, module_text, pc_name, action_text):
    """
    Resolve a single PC's turn based on the player's natural-language description.
    Also parses resulting narration to apply damage to NPC HP.
    """
    prompt = f"""
It is {pc_name}'s turn in combat.

The player describes {pc_name}'s entire turn with the following actions 
(movement, action, bonus action, free actions, etc.):

\"\"\"{action_text}\"\"\"

Interpret and resolve these declared actions using D&D 5e–style logic.
- Do NOT invent additional actions beyond what was described.
- You may clarify implied details (such as which weapon is used) if obvious or previously established.
- You MAY fully resolve attacks, saving throws, and damage against NPCs/monsters, because you know their AC and HP.
- When a hostile NPC or monster takes damage, you MUST state it in this exact pattern, using the exact combatant name:
  "<Exact NPC Name> takes <number> <damage type> damage (XdY+Z)."
  Examples:
    "Goblin takes 7 slashing damage (1d6+4)."
    "Young Red Dragon takes 13 fire damage (3d6+1)."
- Do NOT use generic phrases like "the goblin" if there is a specific named combatant; use its exact name from its stat block.
- Keep narration concise in 1–2 short paragraphs.
"""
    reply = generate_dm_response(session, npc_mgr, pc_mgr, prompt, module_text)
    md = Markdown(reply)
    console.print(Panel(md, border_style="yellow"))

    # After narration, parse for NPC damage and update HP
    parse_and_apply_pc_damage(session, reply)


def declare_npc_action(session, npc_mgr, pc_mgr, module_text, npc_name):
    """
    Have the AI declare an NPC/monster's action, rolls, and DCs,
    but NOT resolve the outcome.
    """
    prompt = f"""
It is now {npc_name}'s turn in combat.

Declare exactly ONE action for {npc_name} this turn.

Requirements:
- Choose appropriate target(s) among the player characters by NAME only (e.g. "John Doe", "Dirk Daring").
- Briefly describe what {npc_name} attempts to do.

If the action is a weapon or spell attack that uses an attack roll:
- Roll a d20 and add an appropriate attack modifier.
- Show the attack roll in EXACTLY this format:
  "rolls a 16 (12 + 4)"
  where:
    - 16 is the total,
    - 12 is the d20 roll,
    - 4 is the modifier.
- Do NOT decide whether it hits or misses.
- Do NOT show the damage dice yet.
- Instead, say something like:
  "If it hits: slashing damage."
  or
  "If it hits: fire damage."

If the action calls for saving throws (for example, an area spell):
- Name ALL affected characters by name (e.g. "John Doe and Dirk Daring").
- State the saving throw type and DC, e.g.:
  "Roll Dexterity saving throws, DC 13."
- Briefly state what happens on a failed save and what happens on a successful save.
- Do NOT roll damage yet, and do NOT show damage dice yet.

General constraints:
- Do NOT narrate the outcome (no hits, no misses, no damage actually taken, no conditions applied).
- Do NOT start another turn or declare additional actions.
- End your response after describing the attempted action, its target(s),
  the attack roll and/or saving throw DC, and the conditional effects.
"""
    reply = generate_dm_response(session, npc_mgr, pc_mgr, prompt, module_text)
    session.session["pending_npc_resolution"] = {
        "npc_name": npc_name,
        "declaration": reply,
    }
    session.save()

    md = Markdown(reply)
    console.print(Panel(md, border_style="yellow"))


def resolve_npc_outcome(session, npc_mgr, pc_mgr, module_text, resolution_text):
    """
    Resolve the outcome of a previously-declared NPC action based on
    DM/player feedback (hit/miss/save/fail per target).
    (We do NOT track PC HP here, only narration.)
    """
    pending = session.session.get("pending_npc_resolution")
    if not pending:
        console.print("[red]No NPC action is awaiting resolution.[/red]")
        return

    npc_name = pending["npc_name"]
    declaration = pending["declaration"]

    prompt = f"""
Earlier in this combat round, {npc_name} declared the following action:

\"\"\"{declaration}\"\"\"

The Dungeon Master and/or players now report the actual results of the attack rolls
and/or saving throws with the following description:

\"\"\"{resolution_text}\"\"\"

Using ONLY the declared action and this outcome description:

- Apply hits, misses, successful saves, and failed saves according to the DM/players' text.
- If damage is dealt to a player character, just narrate it; do NOT track player HP.
- Include the damage DICE expression in parentheses after the damage, e.g.:
  "John Doe takes 7 slashing damage (1d8+2)."
- If some targets succeed and others fail on a save, apply full or half damage appropriately
  (or no damage if that is normal for the effect).
- You may apply conditions (stunned, prone, paralyzed, frightened, etc.)
  only when consistent with the declared effect and the DM's reported outcome.
- Keep narration succinct (1–2 short paragraphs).
- Do NOT start a new turn, declare new actions, or roll new attack rolls.
  You are ONLY resolving the consequences of the previously declared action.
"""
    reply = generate_dm_response(session, npc_mgr, pc_mgr, prompt, module_text)

    session.session["pending_npc_resolution"] = None
    session.save()

    md = Markdown(reply)
    console.print(Panel(md, border_style="yellow"))


# -------------------------------
# DM Command Processor
# -------------------------------
def process_dm_command(cmd, session, npc_mgr, pc_mgr, module_text):
    # Command: /combat
    if cmd == "/combat":
        session.session["combat_active"] = True
        session.session["combatants"] = []
        session.session["initiative"] = {"players": {}, "npcs": {}}
        session.session["turn_order"] = []
        session.session["current_turn_index"] = 0
        session.session["pending_npc_resolution"] = None
        session.session["npc_hp"] = {}
        session.save()

        prompt = """
A combat encounter has been manually triggered by the Dungeon Master.

Please:
1. Generate a combatant list.
2. Provide brief stat blocks for each NPC/monster combatant only (no player character stat blocks).
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

        session.session["combatants"].append(reply)
        session.save()

        # NPC HP extraction
        npc_hp = get_npc_hp_from_ai(session, npc_mgr, pc_mgr, module_text)
        if npc_hp:
            session.session["npc_hp"] = npc_hp
            session.save()
            console.print("[bold green]NPC HP initialized for combatants.[/bold green]")
        else:
            console.print("[yellow]NPC HP could not be fully parsed; HP tracking may be incomplete.[/yellow]")

        # Player initiatives
        player_inits = collect_player_initiatives(pc_mgr)
        session.session["initiative"]["players"] = player_inits
        session.save()

        # NPC initiatives
        npc_inits = get_npc_initiatives_from_ai(session, npc_mgr, pc_mgr, module_text)
        session.session["initiative"]["npcs"] = npc_inits

        # Combined order
        turn_order = build_initiative_order(player_inits, npc_inits)
        session.session["turn_order"] = turn_order
        session.session["current_turn_index"] = 0
        session.save()

        if turn_order:
            console.print("\n[bold magenta]Initiative order:[/bold magenta]")
            for idx, entry in enumerate(turn_order, start=1):
                console.print(
                    f"{idx}. {entry['name']} "
                    f"({'PC' if entry['type'] == 'pc' else 'NPC'}) "
                    f"- {entry['initiative']}"
                )
            console.print("")
        else:
            console.print(
                "[yellow]No initiatives recorded. "
                "You may need to rerun /combat or enter data manually.[/yellow]"
            )

        return True

    # Command: /statblocks
    if cmd == "/statblocks":
        if not session.session.get("combat_active"):
            console.print("[red]Combat is not active.[/red]")
            return True

        prompt = f"""
The Dungeon Master requests stat blocks for active combatants.

Use the previously generated combatant list:

{session.session.get("combatants", [])}

Provide:
- A clear list
- A concise stat block for each NPC/monster combatant
"""
        reply = generate_dm_response(
            session, npc_mgr, pc_mgr, prompt, module_text
        )
        md = Markdown(reply)
        console.print(Panel(md, border_style="yellow"))
        return True

    # Command: /hp
    if cmd == "/hp":
        npc_hp = session.session.get("npc_hp", {})
        if not npc_hp:
            console.print("[yellow]No NPC HP is currently tracked.[/yellow]")
            return True

        console.print("[bold magenta]NPC Hit Points:[/bold magenta]")
        for name, hp in npc_hp.items():
            status = f"{hp} HP" if hp > 0 else "dead"
            console.print(f"- {name}: {status}")
        return True

    # Command: /next
    if cmd == "/next":
        if not session.session.get("combat_active"):
            console.print("[yellow]/next has no effect because combat is not active.[/yellow]")
            return True
        session.session["pending_npc_resolution"] = None
        session.save()
        advance_turn(session)
        console.print("[bold cyan]Turn advanced by DM.[/bold cyan]")
        return True

    # Command: /endcombat
    if cmd == "/endcombat":
        if not session.session.get("combat_active"):
            console.print("[yellow]Combat is already inactive.[/yellow]")
            return True
        end_combat(session)
        return True

    return False


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

    last_announced_turn_index = None

    while True:
        # If there is a pending NPC action awaiting resolution,
        # we treat the next input as the DM/players' outcome description.
        if session.session.get("pending_npc_resolution"):
            prompt_label = (
                "Resolve NPC action result (i.e 'that hits' or 'misses'): "
            )
            user_input = input(GREEN + prompt_label + RESET)

            if user_input.lower() in ("exit", "quit"):
                console.print("[red]Goodbye![/red]")
                break

            if user_input.startswith("/"):
                handled = process_dm_command(
                    user_input, session, npcs, pcs, module_text
                )
                if handled:
                    continue

            # Normal text: resolve NPC outcome
            resolve_npc_outcome(session, npcs, pcs, module_text, user_input)
            advance_turn(session)
            last_announced_turn_index = None
            continue

        prompt_label = "You: "

        # If combat is active and we have an initiative order,
        # handle NPC declarations and PC prompts.
        if session.session.get("combat_active") and session.session.get("turn_order"):
            current_entry = get_current_turn_entry(session)
            if current_entry is None:
                prompt_label = "You: "
            else:
                if last_announced_turn_index != session.session["current_turn_index"]:
                    console.print(
                        f"\n[bold magenta]-- {current_entry['name']}'s turn "
                        f"({'PC' if current_entry['type'] == 'pc' else 'NPC'}) --[/bold magenta]"
                    )
                    last_announced_turn_index = session.session["current_turn_index"]

                if current_entry["type"] == "npc":
                    # Declare NPC action and then wait for DM resolution on next loop iteration.
                    declare_npc_action(session, npcs, pcs, module_text, current_entry["name"])
                    continue
                else:
                    # It's a PC's turn; prompt for that character's actions
                    prompt_label = f"{current_entry['name']}'s action: "
        else:
            last_announced_turn_index = None
            prompt_label = "You: "

        # Get user input (non-pending NPC case)
        user_input = input(GREEN + prompt_label + RESET)

        # Exit
        if user_input.lower() in ("exit", "quit"):
            console.print("[red]Goodbye![/red]")
            break

        # Slash commands
        if user_input.startswith("/"):
            handled = process_dm_command(
                user_input, session, npcs, pcs, module_text
            )
            if handled:
                if user_input == "/next":
                    last_announced_turn_index = None
                continue

        # If combat is active and it's a PC's turn, treat input as that PC's turn description
        if session.session.get("combat_active") and session.session.get("turn_order"):
            current_entry = get_current_turn_entry(session)
            if current_entry and current_entry["type"] == "pc":
                pc_name = current_entry["name"]
                resolve_pc_turn(session, npcs, pcs, module_text, pc_name, user_input)
                # After possible kills, combat may have ended
                if session.session.get("combat_active"):
                    advance_turn(session)
                    last_announced_turn_index = None
                continue

        # Otherwise, normal non-combat input → AI response
        reply = generate_dm_response(session, npcs, pcs, user_input, module_text)
        md = Markdown(reply)
        console.print(Panel(md, border_style="yellow"))


if __name__ == "__main__":
    main()

