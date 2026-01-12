#!/usr/bin/env python3
"""
dmv3.py — AI Dungeon Master (Session-Authoritative, JSON Module Driven)

Behavior:
- session.json is the single source of truth
- -m / --module replaces session.module
- -c / --characters replaces session.characters.pcs
- Schema drift in module JSON is normalized safely
- World state, flags, consequences persist across runs
"""

import argparse
import json
import os
from datetime import datetime, UTC
from typing import Any, Dict

from openai import OpenAI
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

try:
    import readline  # noqa
except ImportError:
    pass

# =========================
# GLOBALS
# =========================
client = OpenAI()
console = Console()

GREEN = "\033[92m"
RESET = "\033[0m"

SYSTEM_PROMPT_FILE = "system.prompt"
DEVELOPER_PROMPT_FILE = "developer.prompt"


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def read_text(path: str) -> str:
    if not os.path.exists(path):
        return ""
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


SYSTEM_PROMPT = read_text(SYSTEM_PROMPT_FILE)
DEVELOPER_PROMPT = read_text(DEVELOPER_PROMPT_FILE)

# =========================
# SESSION STATE
# =========================
class SessionState:
    def __init__(self, path="session.json"):
        self.path = path
        self.data = self._default()

        if os.path.exists(self.path):
            self.load()
            self.migrate()
        else:
            self.save()

        console.print(f"[bold green]Session:[/bold green] {self.path}\n")

    def _default(self) -> Dict[str, Any]:
        return {
            "meta": {
                "created": utc_now(),
                "last_updated": None,
                "schema_version": 3,
            },
            "module": None,
            "characters": {
                "pcs": {},
                "source": None,
                "last_loaded_at": None,
            },
            "world": {},
            "global_flags": {},
            "timelines": {},
            "messages": [],
            "story_log": [],
        }

    def migrate(self):
        self.data.setdefault("characters", {"pcs": {}})
        self.data.setdefault("world", {})
        self.data.setdefault("global_flags", {})
        self.data.setdefault("timelines", {})
        self.data.setdefault("messages", [])
        self.data.setdefault("story_log", [])
        self.save()

    def load(self):
        with open(self.path, "r", encoding="utf-8") as f:
            self.data = json.load(f)

    def save(self):
        self.data["meta"]["last_updated"] = utc_now()
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)

    def add_message(self, role, content):
        self.data["messages"].append({"role": role, "content": content})
        self.save()

    def add_story_event(self, text):
        self.data["story_log"].append(text)
        self.save()

# =========================
# CHARACTER MANAGER
# =========================
class CharacterManager:
    def __init__(self, session: SessionState):
        self.session = session

    @property
    def pcs(self):
        return self.session.data["characters"]["pcs"]

    def get_all_pc_descriptions(self) -> str:
        return "\n\n".join(
            f"Player Character: {name}\n{json.dumps(data, indent=2, ensure_ascii=False)}"
            for name, data in self.pcs.items()
        )

# =========================
# MODULE NORMALIZATION
# =========================
def ensure_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def normalize_module(module: Dict[str, Any]) -> Dict[str, Any]:
    for thread in module.get("threads", {}).values():
        pk = thread.get("player_knowledge", {})
        thread["player_knowledge"] = {
            "known_to_players": ensure_list(pk.get("known_to_players")),
            "truth_hidden": ensure_list(pk.get("truth_hidden")),
        }

    for area in module.get("areas", {}).values():
        sc = area.get("skill_challenges", [])
        normalized = []
        for entry in sc:
            if isinstance(entry, str):
                normalized.append({
                    "id": None,
                    "goal": entry,
                    "checks": [],
                    "dm_notes": "Imported as descriptive placeholder"
                })
            else:
                normalized.append(entry)
        area["skill_challenges"] = normalized

    for var in module.get("world_state", {}).get("variables", {}).values():
        if var.get("type") == "int":
            var["type"] = "number"

    return module

# =========================
# LOADERS
# =========================
def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_module(session: SessionState, path: str):
    module_data = load_json(path)
    module_data = normalize_module(module_data)

    meta = module_data.get("module", {})
    session.data["module"] = {
        "id": meta.get("id"),
        "title": meta.get("title"),
        "data": module_data,
        "source": path,
        "loaded_at": utc_now(),
    }
    session.save()

    console.print(f"[bold green]Module loaded:[/bold green] {meta.get('title')}")


def load_characters(session: SessionState, path: str):
    pcs = load_json(path)
    session.data["characters"]["pcs"] = pcs
    session.data["characters"]["source"] = path
    session.data["characters"]["last_loaded_at"] = utc_now()
    session.save()

    console.print(f"[bold green]Characters loaded:[/bold green] {path}")

# =========================
# AI DUNGEON MASTER
# =========================
class AIDungeonMaster:
    def __init__(self, session: SessionState, pcs: CharacterManager):
        self.session = session
        self.pcs = pcs

    def _require_module(self):
        if not self.session.data.get("module"):
            raise RuntimeError("No module loaded. Use -m module.json")
        return self.session.data["module"]["data"]

    def build_prompt(self, module):
        return f"""
You are the AI Dungeon Master, responsible ONLY for narrative, world continuity,
NPC portrayal, and consequence progression.

RULES
- NEVER explain mechanics, dice, flags, or structure
- NEVER invent locations, NPCs, or connections
- Respect module JSON as authoritative truth
- Track consequences silently via story progression
- Hand combat narration to the human DM

MODULE DATA (JSON):
{json.dumps(module, indent=2, ensure_ascii=False)}

PLAYER CHARACTERS:
{self.pcs.get_all_pc_descriptions()}

STORY LOG:
{json.dumps(self.session.data["story_log"], indent=2, ensure_ascii=False)}
"""

    def handle_input(self, user_input: str) -> str:
        module = self._require_module()

        self.session.add_message("user", user_input)

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "system", "content": DEVELOPER_PROMPT},
            {"role": "assistant", "content": self.build_prompt(module)},
        ] + self.session.data["messages"]

        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=messages,
            max_tokens=600
        )

        reply = response.choices[0].message.content

        self.session.add_message("assistant", reply)
        self.session.add_story_event(reply)

        return reply

# =========================
# CLI
# =========================
def parse_args():
    p = argparse.ArgumentParser("AI Dungeon Master v3")
    p.add_argument("-s", "--session", default="session.json")
    p.add_argument("-m", "--module")
    p.add_argument("-c", "--characters")
    return p.parse_args()

# =========================
# MAIN
# =========================
def main():
    args = parse_args()

    console.print("[bold cyan]=== AI Dungeon Master v3 ===[/bold cyan]\n")

    session = SessionState(args.session)

    if args.module:
        load_module(session, args.module)

    if args.characters:
        load_characters(session, args.characters)

    pcs = CharacterManager(session)
    dm = AIDungeonMaster(session, pcs)

    mod = session.data.get("module")
    if mod:
        console.print(f"[bold green]Active Module:[/bold green] {mod['title']}")
    else:
        console.print("[yellow]No module loaded yet.[/yellow]")

    console.print("\n[bold green]DM ready. Begin your adventure.[/bold green]\n")

    while True:
        user_input = input(GREEN + "You: " + RESET).strip()

        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit"):
            console.print("[red]Goodbye![/red]")
            break

        try:
            reply = dm.handle_input(user_input)
            console.print(Panel(Markdown(reply), border_style="yellow"))
        except Exception as e:
            console.print(f"[red]Error:[/red] {e}")

if __name__ == "__main__":
    main()
