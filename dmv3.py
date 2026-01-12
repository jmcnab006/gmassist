#!/usr/bin/env python3
"""
dmv3.py — AI Dungeon Master v3.1
State-authoritative, JSON-module driven campaign engine
"""

import argparse
import json
import os
from datetime import datetime, UTC
from typing import Dict, Any

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
# SESSION (PERSISTENCE ONLY)
# =========================
class SessionState:
    def __init__(self, path="session.json"):
        self.path = path
        self.data = self._default()

        if os.path.exists(self.path):
            self.load()
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
                "npcs": {},
                "source": None,
                "last_loaded_at": None,
            },
            "global_flags": {},
            "timelines": {},
            "messages": [],
            "story_log": [],
        }

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

    def get_characters(self) -> str:
        return "\n\n".join(
            f"Player Character: {name}\n{json.dumps(data, indent=2, ensure_ascii=False)}"
            for name, data in self.pcs.items()
        )

# =========================
# NORMALIZATION HELPERS
# =========================
def ensure_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]

# =========================
# AI DUNGEON MASTER (AUTHORITATIVE)
# =========================
class AIDungeonMaster:
    def __init__(self, session: SessionState, pcs: CharacterManager):
        self.session = session
        self.pcs = pcs

        if not session.data.get("module"):
            raise RuntimeError("No module loaded. Use -m module.json")

        # Static module data
        self.module = session.data["module"]["data"]

        # Runtime mutable state
        self.threads = self.module.get("threads", {})
        self.world_state = self.module.get("world_state", {})
        self.consequences = self.module.get("consequences", {})
        self.flags = session.data.setdefault("global_flags", {})
        self.timelines = session.data.setdefault("timelines", {})

        self._normalize_runtime()
        self._dirty = False

    # -------------------------
    # NORMALIZATION
    # -------------------------
    def _normalize_runtime(self):
        for t in self.threads.values():
            pk = t.get("player_knowledge", {})
            t["player_knowledge"] = {
                "known_to_players": ensure_list(pk.get("known_to_players")),
                "truth_hidden": ensure_list(pk.get("truth_hidden")),
            }

        for area in self.module.get("areas", {}).values():
            sc = area.get("skill_challenges", [])
            normalized = []
            for entry in sc:
                if isinstance(entry, str):
                    normalized.append({
                        "id": None,
                        "goal": entry,
                        "checks": [],
                        "dm_notes": "Imported placeholder"
                    })
                else:
                    normalized.append(entry)
            area["skill_challenges"] = normalized

        for var in self.world_state.get("variables", {}).values():
            if var.get("type") == "int":
                var["type"] = "number"

    # -------------------------
    # FLAG API
    # -------------------------
    def set_flag(self, flag: str, value=True):
        self.flags[flag] = value
        self._dirty = True

    def has_flag(self, flag: str) -> bool:
        return bool(self.flags.get(flag))

    # -------------------------
    # THREAD API
    # -------------------------
    def set_thread_status(self, thread_id: str, status: str):
        if thread_id in self.threads:
            self.threads[thread_id]["status"] = status
            self._dirty = True

    # -------------------------
    # WORLD STATE API
    # -------------------------
    def update_world_var(self, var_id: str, delta: int):
        var = self.world_state.get("variables", {}).get(var_id)
        if not var:
            return
        var["value"] = max(var["min"], min(var["max"], var["value"] + delta))
        self._dirty = True

    # -------------------------
    # TIMERS / CONSEQUENCES
    # -------------------------
    def tick_timers(self, reason="manual"):
        for timer in self.world_state.get("timers", {}).values():
            if timer.get("ticks_when") == reason:
                timer["value"] -= 1
                self._dirty = True
                if timer["value"] <= 0:
                    for cid in timer.get("on_expire", []):
                        self.activate_consequence(cid)

    def activate_consequence(self, cons_id: str):
        cons = self.consequences.get(cons_id)
        if not cons or cons["status"] == "resolved":
            return
        cons["status"] = "ongoing"
        self._dirty = True

    # -------------------------
    # PERSISTENCE
    # -------------------------
    def commit(self):
        if not self._dirty:
            return

        self.session.data["global_flags"] = self.flags
        self.session.data["timelines"] = self.timelines

        self.session.data["module"]["data"]["threads"] = self.threads
        self.session.data["module"]["data"]["world_state"] = self.world_state
        self.session.data["module"]["data"]["consequences"] = self.consequences

        self.session.save()
        self._dirty = False

    # -------------------------
    # PROMPT
    # -------------------------
    def build_prompt(self) -> str:
        active_threads = {
            k: v for k, v in self.threads.items()
            if v.get("status") != "resolved"
        }

        return f"""
You are the AI Dungeon Master.
You manage narrative, NPCs, and consequences.
You do NOT explain mechanics or system structure.

MODULE METADATA:
{json.dumps(self.module.get("module"), indent=2)}

ACTIVE THREADS:
{json.dumps(active_threads, indent=2)}

WORLD STATE:
{json.dumps(self.world_state, indent=2)}

GLOBAL FLAGS:
{json.dumps(self.flags, indent=2)}

PLAYER CHARACTERS:
{self.pcs.get_characters()}

RECENT STORY:
{json.dumps(self.session.data["story_log"][-15:], indent=2)}
"""

    # -------------------------
    # TURN HANDLER
    # -------------------------
    def handle_input(self, user_input: str) -> str:
        self.session.add_message("user", user_input)

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "system", "content": DEVELOPER_PROMPT},
            {"role": "assistant", "content": self.build_prompt()},
        ] + self.session.data["messages"]

        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=messages,
            max_tokens=600
        )

        reply = response.choices[0].message.content

        self.session.add_message("assistant", reply)
        self.session.add_story_event(reply)

        self.commit()
        return reply

# =========================
# LOADERS
# =========================
def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_module(session: SessionState, path: str):
    module = load_json(path)
    session.data["module"] = {
        "id": module["module"]["id"],
        "title": module["module"]["title"],
        "data": module,
        "source": path,
        "loaded_at": utc_now(),
    }
    session.save()
    console.print(f"[bold green]Module loaded:[/bold green] {module['module']['title']}")


def load_characters(session: SessionState, path: str):
    pcs = load_json(path)
    session.data["characters"]["pcs"] = pcs
    session.data["characters"]["source"] = path
    session.data["characters"]["last_loaded_at"] = utc_now()
    session.save()
    console.print(f"[bold green]Characters loaded:[/bold green] {path}")

# =========================
# CLI
# =========================
def parse_args():
    p = argparse.ArgumentParser("AI Dungeon Master v3.1")
    p.add_argument("-s", "--session", default="session.json")
    p.add_argument("-m", "--module")
    p.add_argument("-c", "--characters")
    return p.parse_args()

# =========================
# MAIN
# =========================
def main():
    args = parse_args()
    console.print("[bold cyan]=== AI Dungeon Master v3.1 ===[/bold cyan]\n")

    session = SessionState(args.session)

    if args.module:
        load_module(session, args.module)
    if args.characters:
        load_characters(session, args.characters)

    pcs = CharacterManager(session)
    dm = AIDungeonMaster(session, pcs)

    console.print(f"[bold green]Active Module:[/bold green] {session.data['module']['title']}")
    console.print("\n[bold green]DM ready. Begin your adventure.[/bold green]\n")

    while True:
        user_input = input(GREEN + "You: " + RESET).strip()
        if user_input.lower() in ("exit", "quit"):
            console.print("[red]Goodbye![/red]")
            break

        reply = dm.handle_input(user_input)
        console.print(Panel(Markdown(reply), border_style="yellow"))

if __name__ == "__main__":
    main()
