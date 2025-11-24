import json
import os
from pypdf import PdfReader
from openai import OpenAI

client = OpenAI()

# ANSI Colors
GREEN = "\033[92m"
YELLOW = "\033[93m"
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
        """Minimal narrative PC fields."""
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
# Module Reader
# -------------------------------
def load_pdf_text(pdf_path, output_path="data/module_text.txt"):
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

    return text


def auto_load_module_text():
    path = "data/module_text.txt"
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    # Needs PDF
    pdf_path = input("Enter path to module PDF: ").strip()
    return load_pdf_text(pdf_path)


# -------------------------------
# ChatGPT Response Generator
# -------------------------------
def generate_dm_response(session, npc_mgr, pc_mgr, user_input, module_text):

    session.add_message("user", user_input)

    # Key instruction: 1–2 paragraphs unless DM asks for "detailed"
    system_prompt = f"""
You are an AI Dungeon Master running a fantasy adventure.

REQUIREMENTS:
- Limit descriptions to **1 paragraphs maximum** unless the player explicitly requests a "detailed" description.
- Limit descriptions to **1-2 sentances maximum** if the player explicitly requests a "short" description.
- Use vivid sensory details, but remain concise.
- Use appearance/personality/backstory for PCs and NPCs.
- Never describe player actions; only world and NPC reactions.
- Maintain story continuity based on the story log.

MODULE TEXT (Reference Only):
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
        model="gpt-5-nano",
        #model="gpt-4.1",
        messages=messages,
        #max_tokens=600
        #max_completion_tokens=600
    )

    reply = response.choices[0].message.content
    session.add_message("assistant", reply)
    session.add_story_event(reply)

    return reply


# -------------------------------
# MAIN APPLICATION LOOP
# -------------------------------
def main():
    print("=== AI Dungeon Master ===")
    print("Type 'exit' to quit.\n")

    # Default session file
    session_name = input("Enter session name (ENTER for default): ").strip()
    if session_name == "":
        session_path = "sessions/default.json"
    else:
        session_path = f"sessions/{session_name}.json"

    os.makedirs("sessions", exist_ok=True)

    session = SessionManager(session_path)
    npcs = NPCManager()
    pcs = PlayerCharacterManager()

    # Auto-load module
    module_text = auto_load_module_text()

    print("\nDM is ready. Begin your adventure.\n")

    while True:
        user_input = input(GREEN + "You: " + RESET)
        if user_input.lower() in ("exit", "quit"):
            print("Goodbye!")
            break

        reply = generate_dm_response(session, npcs, pcs, user_input, module_text)
        print(YELLOW + "\nDM: " + RESET + reply + "\n")


if __name__ == "__main__":
    main()

