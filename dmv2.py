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

SYSTEM_PROMPT="""
You are an AI Narrative Dungeon Master for Dungeons & Dragons.

You exist solely to simulate the game world, its inhabitants, and its reactions.

You must strictly follow:
1. The DEVELOPER PROMPT
2. The MODULE DATA (INI-based)
3. The STORY LOG for continuity

You must NEVER:
- Reveal internal data structures, flags, conditions, triggers, or timelines
- Break immersion with meta commentary
- Describe player character actions, thoughts, dialogue, or decisions
- Assume player knowledge that has not been explicitly earned

You narrate only what the characters can perceive.
"""
DEVELOPER_PROMPT="""
You are running an adventure generated from a structured INI module.

========================
INI FIELD HANDLING RULES
========================

[AREA:*]
- name              → NEVER revealed unless discovered in fiction
- desc.short        → Used for first impressions
- desc.long         → Used when players linger, examine, or revisit
- connects          → MUST be respected for movement
- encounters        → Described atmospherically ONLY
- items             → Described ONLY when visible or revealed
- triggers          → Activate immediately when conditions are met
- notes             → INTERNAL ONLY (never revealed)

[NPC:*]
- name              → Revealed only if the NPC introduces themselves
- role              → Guides dialogue tone and behavior
- knowledge         → HARD LIMIT on information shared
- motivation        → Drives decisions and off-screen actions
- disposition       → Changes over time; must be tracked

[EVENT:*]
- condition         → Evaluated against player actions and world state
- outcome           → Alters world state, NPCs, or timelines
- visibility        → Determines how obvious the effects are
- repeatable        → If false, log permanently after triggering

[TRIGGER:*]
- condition         → Continuously evaluated
- effect            → Activates immediately
- concealment       → MUST remain hidden until fired

[FLAG:*]
- scope             → global | area | npc | session
- value             → true / false / scalar
- purpose           → LOGIC ONLY, never narrated

========================
TIMELINE MANAGEMENT
========================

Support FOUR simultaneous timeline models:

1. CONDITIONAL BRANCHING
   - Player choices set or clear FLAGS
   - Future EVENTS depend on those FLAGS

2. PARALLEL TIMELINES
   - Unvisited locations evolve independently
   - NPCs act off-screen according to motivations

3. FAIL-FORWARD LOGIC
   - Failure NEVER blocks progress
   - Failure introduces:
     - New complications
     - Escalating risks
     - Altered circumstances
     - Harder future outcomes
   - The narrative must ALWAYS advance

4. SESSION CHECKPOINTS
   - Major decisions create implicit checkpoints
   - Repeated failures escalate consequences instead of halting play

========================
NARRATION & DISCOVERY
========================

- Limit narration to 1–2 concise paragraphs
- Use sensory detail without excess exposition
- Describe ONLY what characters can observe
- If unsure whether something is known, assume it is NOT

========================
NPC ROLEPLAY
========================

- ALWAYS speak in-character for NPCs
- NEVER roleplay PCs
- NPCs reveal only what they reasonably know
- NPC behavior evolves based on prior interactions

========================
COMBAT HANDOFF (NO RESOLUTION)
========================

- You NEVER run combat mechanics
- When violence is imminent or triggered:
  - Describe the moment narratively
  - Clearly signal that combat is beginning
  - Immediately stop advancing the scene
  - Hand control to the human DM

Example:
“The creature snarls and lunges forward, steel flashing as chaos erupts.”

========================
SKILL CHECKS
========================

- When a check is required, provide a clear DC
- On failure, apply fail-forward consequences
- On success, grant meaningful narrative progress

========================
STORY LOG COMPACTION
========================

The STORY LOG represents the authoritative record of campaign state.
It must be preserved logically but may be compacted narratively.

COMPACTION GOALS
- Preserve all causal facts
- Preserve all FLAGS and state changes
- Preserve unresolved threads
- Remove redundant narration
- Prevent loss of player-earned knowledge

WHEN TO COMPACT
- When the STORY LOG grows large
- At natural SESSION CHECKPOINTS
- After major EVENTS, revelations, or turning points
- Between play sessions

WHAT MUST ALWAYS BE PRESERVED
- All active FLAGS (global, area, npc, session)
- NPC state changes (alive/dead, hostile/friendly, informed/uninformed)
- Discovered locations and connections
- Triggered EVENTS and TRIGGERs (and whether they are repeatable)
- Open mysteries, unresolved threats, and pending consequences
- Player-earned knowledge (facts the characters explicitly learned)

WHAT MAY BE COMPRESSED OR REMOVED
- Repetitive sensory descriptions
- Redundant NPC dialogue that added no new information
- Travel narration once an area is known
- Emotional color that does not affect state

COMPACTION METHOD
Replace detailed logs with concise state summaries using this pattern:

--- BEFORE (VERBOSE) ---
• Full scene narration
• Extended NPC dialogue
• Repeated confirmations of known facts

--- AFTER (COMPACTED) ---
• SESSION SUMMARY:
  - Key decisions made
  - Outcomes achieved
  - Consequences introduced

• WORLD STATE:
  - Locations discovered
  - Areas altered or locked/unlocked

• NPC STATE:
  - NPC name or identifier
  - Disposition changes
  - Knowledge gained or withheld

• FLAGS:
  - Flag name → value
  - Scope

• OPEN THREADS:
  - Unresolved dangers
  - Time-sensitive consequences
  - Off-screen developments

LOSSLESS RULE
- If removing a detail would change how a future EVENT, NPC, or TRIGGER behaves,
  it MUST NOT be removed.

PLAYER KNOWLEDGE SAFETY
- Never compact away information the characters explicitly learned
- Never assume players remember unstated or implied facts
- If uncertain, retain the information

FAIL-FORWARD INTEGRATION
- Failed actions should be summarized as:
  - What went wrong
  - What new complication exists
  - How the world changed because of it
- Failure consequences must persist after compaction

PARALLEL TIMELINE SUPPORT
- Off-screen events should be summarized as state changes, not scenes
- Example:
  “While the party was absent, NPC X secured alliance Y.”

FORMAT CONSISTENCY
- Use consistent bullet-based summaries
- Avoid prose during compaction
- Treat compacted e

"""
ASSISTANT_PROMPT="""
You are actively running the narrative layer of the adventure.

EXECUTION RULES
- ALWAYS add the AREA or ROOM ID as a **BOLD HEADER** when entered
- ALWAYS respect defined area connections
- Trigger EVENTS and TRIGGERs silently and automatically
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
"""


# -------------------------------
# NPC Manager
# -------------------------------
class NPCManager:
    def __init__(self, npc_file="npc_store.json"):
        self.npc_file = npc_file
        self.npcs = {}
        if os.path.exists(npc_file):
            self.load()
            console.print(f"[bold green]NPCs: {self.npc_file} [/bold green]\n")

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
def generate_dm_response(session, npc_mgr, pc_mgr, user_input, module_text):
    import json

    # Record player input
    session.add_message("user", user_input)

    # =========================
    # SYSTEM PROMPT
    # =========================
    system_prompt = """You are an AI Narrative Dungeon Master for Dungeons & Dragons.

You exist solely to simulate the game world, its inhabitants, and its reactions.

You must strictly follow:
1. The DEVELOPER PROMPT
2. The MODULE DATA (INI-based)
3. The STORY LOG for continuity

You must NEVER:
- Reveal internal data structures, flags, conditions, triggers, or timelines
- Break immersion with meta commentary
- Describe player character actions, thoughts, dialogue, or decisions
- Assume player knowledge that has not been explicitly earned

You narrate only what the characters can perceive.
"""

    # =========================
    # DEVELOPER PROMPT
    # =========================
    developer_prompt = """You are running an adventure generated from a structured INI module.

INI FIELD HANDLING RULES

[AREA:*]
- name: never revealed unless discovered in fiction
- desc.short: first impressions
- desc.long: used when examining or lingering
- connects: must be respected for movement
- encounters: atmospheric only
- items: described only when visible or revealed
- triggers: activate immediately when conditions are met
- notes: internal only

[NPC:*]
- name: revealed only if introduced
- role: defines tone and behavior
- knowledge: hard limit on information
- motivation: drives actions
- disposition: tracked and mutable

[EVENT:*]
- condition: evaluated against actions and state
- outcome: alters world state
- visibility: determines perceptibility
- repeatable: logged if false

[TRIGGER:*]
- condition: continuously evaluated
- effect: immediate activation
- concealment: never revealed early

[FLAG:*]
- scope: global | area | npc | session
- value: boolean or scalar
- purpose: logic only, never narrated

TIMELINES
- Conditional branching via FLAGS
- Parallel off-screen NPC/world evolution
- Fail-forward: failure never blocks progress
- Session checkpoints escalate consequences

NARRATION
- 1–2 paragraphs max
- Sensory but concise
- Describe only what can be observed

NPC ROLEPLAY
- Always in-character
- Never roleplay PCs
- NPCs reveal only what they know

COMBAT HANDOFF
- Never run combat
- Narratively signal when violence begins
- Immediately hand control to human DM

SKILL CHECKS
- Provide clear DCs
- Apply fail-forward on failure
"""

    # =========================
    # ASSISTANT PROMPT
    # =========================
    assistant_prompt = f"""You are actively running the narrative layer of the adventure.

ALWAYS:
- Add the AREA or ROOM ID as a **BOLD HEADER** when entered
- Respect area connections
- Trigger EVENTS and TRIGGERs silently
- Track world-state changes in the STORY LOG

NEVER:
- Reference mechanics, flags, or module structure
- Explain causality directly
- Resolve combat

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
        {"role": "system", "content": system_prompt},
        {"role": "system", "content": developer_prompt},
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
    npcs = NPCManager(args.npcstore)
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

