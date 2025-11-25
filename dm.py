#!/usr/bin/python3
# dm.py

import argparse
import json
import os

from openai import OpenAI

from managers import (
    SessionManager,
    NPCManager,
    PlayerCharacterManager,
    DEFAULT_MODULE_PATH,
    extract_module_from_pdf,
    load_module_text,
)

client = OpenAI()

# ANSI Colors
GREEN = "\033[92m"
YELLOW = "\033[93m"
RESET = "\033[0m"


def build_system_prompt(module_text: str, npc_mgr: NPCManager, pc_mgr: PlayerCharacterManager, session) -> str:
    """
    System-level instructions for the model.
    Starts with 'DM:' as requested.
    Enforces 1-2 paragraph responses unless 'detailed' is requested.
    Enforces 1-2 sentances responses if 'short' is requested.
    """
    return f"""DM: You are an AI Dungeon Master running a fantasy adventure.

REQUIREMENTS:
- Limit descriptions to **1-2 paragraphs maximum** unless the player explicitly requests a "detailed" description.
- Limit descriptions to **1-2 sentances maximum** if the player explicitly requests a "short" description.
- Use vivid but concise sensory detail (sight, sound, smell, mood).
- Use appearance, personality, and backstory for both PCs and NPCs.
- Never describe player actions; only describe the world and NPC reactions.
- Maintain continuity based on the story log.

MODULE TEXT (Reference Only):
{module_text[:30000]}

NPC RECORDS:
{npc_mgr.get_all_npc_descriptions()}

PLAYER CHARACTER RECORDS:
{pc_mgr.get_all_pc_descriptions()}

STORY LOG:
{json.dumps(session.session["story_log"], indent=2)}
"""


def generate_dm_response(
    session: SessionManager,
    npc_mgr: NPCManager,
    pc_mgr: PlayerCharacterManager,
    user_input: str,
    module_text: str,
) -> str:
    # Add user message to session history
    session.add_message("user", user_input)

    system_prompt = build_system_prompt(module_text, npc_mgr, pc_mgr, session)

    messages = [{"role": "system", "content": system_prompt}] + session.session["messages"]

    response = client.chat.completions.create(
        model="gpt-4.1",
        messages=messages,
        max_tokens=600,
    )

    reply = response.choices[0].message.content
    session.add_message("assistant", reply)
    session.add_story_event(reply)

    return reply


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AI Dungeon Master assistant")

    parser.add_argument(
        "-s",
        "--session",
        help="Session name or JSON file path (default: sessions/default.json)",
        default=None,
    )
    parser.add_argument(
        "-m",
        "--module",
        help=f"Module text file path (default: {DEFAULT_MODULE_PATH})",
        default=None,
    )

    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--clear-session",
        action="store_true",
        help="Clear the session data file and exit",
    )
    group.add_argument(
        "--extract-module",
        metavar="PDF_PATH",
        help="Extract module text from PDF and save to module text file, then exit",
    )

    return parser.parse_args()


def resolve_session_path(session_arg: str | None) -> str:
    if not session_arg:
        return "sessions/default.json"
    # If it looks like a JSON file, use as-is; otherwise treat as a name
    if session_arg.endswith(".json"):
        return session_arg
    return os.path.join("sessions", f"{session_arg}.json")


def resolve_module_path(module_arg: str | None) -> str:
    return module_arg or DEFAULT_MODULE_PATH


def clear_session_file(session_path: str) -> None:
    os.makedirs(os.path.dirname(session_path), exist_ok=True)
    if os.path.exists(session_path):
        os.remove(session_path)
        print(f"Cleared session data at: {session_path}")
    else:
        print(f"No session file found at: {session_path} (nothing to clear)")


def run_extract_module(pdf_path: str, module_path: str) -> None:
    output = extract_module_from_pdf(pdf_path, module_path)
    print(f"Extracted module text to: {output}")


def run_chat(session_path: str, module_path: str) -> None:
    # Ensure sessions directory exists
    os.makedirs(os.path.dirname(session_path), exist_ok=True)

    # Check module file
    if not os.path.exists(module_path):
        print(f"Module text file not found: {module_path}")
        print("Use --extract-module path/to/module.pdf (and optionally --module path/to/output.txt)")
        return

    session = SessionManager(session_path)
    npc_mgr = NPCManager()
    pc_mgr = PlayerCharacterManager()

    module_text = load_module_text(module_path)

    print("=== AI Dungeon Master ===")
    print(f"Session file: {session_path}")
    print(f"Module file:  {module_path}")
    print("Type 'exit' to quit.\n")

    while True:
        try:
            user_input = input(GREEN + "You: " + RESET)
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            break

        if user_input.strip().lower() in ("exit", "quit"):
            print("Goodbye!")
            break

        reply = generate_dm_response(session, npc_mgr, pc_mgr, user_input, module_text)
        print("\nAssistant: " + YELLOW + reply + RESET + "\n")


def main() -> None:
    args = parse_args()

    session_path = resolve_session_path(args.session)
    module_path = resolve_module_path(args.module)

    # Mode: clear session
    if args.clear_session:
        clear_session_file(session_path)
        return

    # Mode: extract module from PDF
    if args.extract_module:
        run_extract_module(args.extract_module, module_path)
        return

    # Default mode: chat
    run_chat(session_path, module_path)


if __name__ == "__main__":
    main()

