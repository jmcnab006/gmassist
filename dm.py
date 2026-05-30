#!/usr/bin/env python3
import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from openai import OpenAI


DEFAULT_MODEL = "gpt-4.1-mini"

client = OpenAI()
COMMANDS: dict[str, dict[str, Any]] = {}


@dataclass
class CommandResult:
    continue_running: bool = True
    save_session: bool = False


def command(name: str, help_text: str = ""):
    def wrapper(func: Callable):
        COMMANDS[name] = {
            "func": func,
            "help": help_text,
        }
        return func
    return wrapper


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def load_text(path: str) -> str:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Missing text file: {path}")
    return p.read_text(encoding="utf-8")


def load_json(path: str, default: Any) -> Any:
    p = Path(path)
    if not p.exists():
        return default
    return json.loads(p.read_text(encoding="utf-8"))


def save_json(path: str, data: Any) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2), encoding="utf-8")


def default_session() -> dict[str, Any]:
    return {
        "model": DEFAULT_MODEL,
        "summary": "",
        "log": [],
        "settings": {
            "max_recent_log_entries": 12,
            "compression_trigger_entries": 20,
        },
    }


def normalize_session(session: dict[str, Any]) -> dict[str, Any]:
    session.setdefault("model", DEFAULT_MODEL)
    session.setdefault("summary", "")
    session.setdefault("log", [])
    session.setdefault("settings", {})

    session["settings"].setdefault("max_recent_log_entries", 12)
    session["settings"].setdefault("compression_trigger_entries", 20)

    return session


def save_session(state: dict[str, Any]) -> None:
    save_json(state["session_file"], state["session"])
    state["dirty"] = False


def shutdown(state: dict[str, Any]) -> None:
    if state.get("dirty"):
        print("\nSaving session...")
        save_session(state)
        print("Session saved.")
    else:
        print("\nNo session changes to save.")

    print("Goodbye.")


def reload_external_files(state: dict[str, Any]) -> None:
    state["module"] = load_json(state["module_file"], {})
    state["characters"] = load_json(state["characters_file"], {})
    state["system_prompt"] = load_text(state["system_prompt_file"])
    state["developer_prompt"] = load_text(state["developer_prompt_file"])


def build_context(
    session: dict[str, Any],
    module: dict[str, Any],
    characters: dict[str, Any],
    user_input: str,
) -> str:
    recent_count = session["settings"]["max_recent_log_entries"]
    recent_log = session.get("log", [])[-recent_count:]

    return f"""
SESSION SUMMARY:
{session.get("summary", "")}

MODULE:
{json.dumps(module, indent=2)}

CHARACTERS:
{json.dumps(characters, indent=2)}

RECENT SESSION LOG:
{json.dumps(recent_log, indent=2)}

CURRENT INPUT:
{user_input}
""".strip()


def ask_model(
    model: str,
    system_prompt: str,
    developer_prompt: str,
    context: str,
) -> str:
    if not context.strip():
        return ""

    response = client.responses.create(
        model=model,
        instructions=f"{system_prompt}\n\n{developer_prompt}",
        input=context,
    )

    return response.output_text.strip()


def compress_session_log(state: dict[str, Any], force: bool = False) -> bool:
    session = state["session"]
    log = session.get("log", [])

    trigger = session["settings"]["compression_trigger_entries"]
    keep_recent = session["settings"]["max_recent_log_entries"]

    if not force and len(log) < trigger:
        return False

    if len(log) <= keep_recent:
        return False

    old_entries = log[:-keep_recent]
    recent_entries = log[-keep_recent:]

    compression_prompt = f"""
Condense these tabletop RPG session log entries into a compact persistent campaign summary.

Preserve only information known to the characters or established through play.

Preserve:
- discovered facts
- NPC names
- NPC attitudes that are observable or known
- locations visited
- player decisions
- unresolved hooks
- consequences
- items found
- threats revealed
- current scene state

Do not include hidden information unless it was revealed to the characters.
Do not infer motives.
Do not add new facts.

Existing Summary:
{session.get("summary", "")}

Entries to Condense:
{json.dumps(old_entries, indent=2)}
""".strip()

    summary = ask_model(
        session.get("model", DEFAULT_MODEL),
        state["system_prompt"],
        state["developer_prompt"],
        compression_prompt,
    )

    if not summary:
        return False

    session["summary"] = summary
    session["log"] = recent_entries
    state["dirty"] = True
    return True


@command("/help", "Show available commands")
def cmd_help(state: dict[str, Any], arg: str) -> CommandResult:
    print("\nCommands:")
    for name, data in sorted(COMMANDS.items()):
        print(f"  {name:<12} {data['help']}")

    print(f"  {'/quit':<12} Exit and save if needed")
    print(f"  {'/exit':<12} Exit and save if needed")
    print()
    return CommandResult()


@command("/save", "Save the current session")
def cmd_save(state: dict[str, Any], arg: str) -> CommandResult:
    save_session(state)
    print("Session saved.")
    return CommandResult()


@command("/reload", "Reload prompts, module, and characters from disk")
def cmd_reload(state: dict[str, Any], arg: str) -> CommandResult:
    reload_external_files(state)
    print("Prompts, module, and characters reloaded.")
    return CommandResult()


@command("/status", "Show current session status")
def cmd_status(state: dict[str, Any], arg: str) -> CommandResult:
    session = state["session"]

    print("\nStatus:")
    print(f"  Session file:      {state['session_file']}")
    print(f"  Module file:       {state['module_file']}")
    print(f"  Characters file:   {state['characters_file']}")
    print(f"  System prompt:     {state['system_prompt_file']}")
    print(f"  Developer prompt:  {state['developer_prompt_file']}")
    print(f"  Model:             {session.get('model', DEFAULT_MODEL)}")
    print(f"  Log entries:       {len(session.get('log', []))}")
    print(f"  Summary chars:     {len(session.get('summary', ''))}")
    print(f"  Dirty:             {state.get('dirty', False)}")
    print()

    return CommandResult()


@command("/model", "Show or set the model")
def cmd_model(state: dict[str, Any], arg: str) -> CommandResult:
    arg = arg.strip()

    if not arg:
        print(f"Current model: {state['session'].get('model', DEFAULT_MODEL)}")
        return CommandResult()

    state["session"]["model"] = arg
    state["dirty"] = True
    print(f"Model set to: {arg}")

    return CommandResult(save_session=True)


@command("/compress", "Compress old session log entries")
def cmd_compress(state: dict[str, Any], arg: str) -> CommandResult:
    changed = compress_session_log(state, force=True)

    if changed:
        print("Session log compressed.")
        return CommandResult(save_session=True)

    print("Nothing to compress.")
    return CommandResult()


@command("/nolog", "Ask outside-game/storyteller question without saving")
def cmd_nolog(state: dict[str, Any], arg: str) -> CommandResult:
    arg = arg.strip()

    if not arg:
        return CommandResult()

    context = build_context(
        state["session"],
        state["module"],
        state["characters"],
        arg,
    )

    response = ask_model(
        state["session"].get("model", DEFAULT_MODEL),
        state["system_prompt"],
        state["developer_prompt"],
        context,
    )

    if response:
        print(f"\n{response}\n")

    return CommandResult()


@command("/log", "Send game input and save prompt/response")
def cmd_log(state: dict[str, Any], arg: str) -> CommandResult:
    arg = arg.strip()

    if not arg:
        return CommandResult()

    prompt_context = build_context(
        state["session"],
        state["module"],
        state["characters"],
        arg,
    )

    response = ask_model(
        state["session"].get("model", DEFAULT_MODEL),
        state["system_prompt"],
        state["developer_prompt"],
        prompt_context,
    )

    if response:
        print(f"\n{response}\n")

    state["session"]["log"].append({
        "time": now(),
        "prompt": arg,
        "response": response,
    })

    state["dirty"] = True

    compressed = compress_session_log(state, force=False)

    return CommandResult(save_session=True or compressed)


def handle_command(state: dict[str, Any], line: str) -> CommandResult:
    line = line.strip()

    if not line:
        return CommandResult()

    parts = line.split(maxsplit=1)
    cmd = parts[0].lower()
    arg = parts[1] if len(parts) > 1 else ""

    if cmd in {"/quit", "/exit"}:
        shutdown(state)
        return CommandResult(continue_running=False)

    entry = COMMANDS.get(cmd)

    if not entry:
        print(f"Unknown command: {cmd}")
        print("Type /help")
        return CommandResult()

    return entry["func"](state, arg)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Persistent tabletop RPG narrator and NPC dialogue assistant."
    )

    parser.add_argument(
        "-s",
        "--session",
        required=True,
        help="Path to session JSON file",
    )

    parser.add_argument(
        "-m",
        "--module",
        required=True,
        help="Path to adventure/module JSON file",
    )

    parser.add_argument(
        "-c",
        "--characters",
        required=True,
        help="Path to character JSON file",
    )

    parser.add_argument(
        "--system-prompt",
        default="prompts/system.txt",
        help="Path to system prompt text file",
    )

    parser.add_argument(
        "--developer-prompt",
        default="prompts/developer.txt",
        help="Path to developer prompt text file",
    )

    parser.add_argument(
        "--model",
        default=None,
        help="Override model and save it to the session",
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()

    session = normalize_session(load_json(args.session, default_session()))

    if args.model:
        session["model"] = args.model

    state = {
        "session_file": args.session,
        "module_file": args.module,
        "characters_file": args.characters,
        "system_prompt_file": args.system_prompt,
        "developer_prompt_file": args.developer_prompt,
        "session": session,
        "module": {},
        "characters": {},
        "system_prompt": "",
        "developer_prompt": "",
        "dirty": True,
    }

    try:
        reload_external_files(state)
        save_session(state)

        print("DM Assistant loaded.")
        print(f"Session:     {args.session}")
        print(f"Module:      {args.module}")
        print(f"Characters:  {args.characters}")
        print(f"Model:       {state['session']['model']}")
        print()
        print("Use /log for game input.")
        print("Use /nolog for outside-game help.")
        print("Use /help for commands.")
        print()

        while True:
            line = input("> ")

            if not line.strip():
                continue

            if line.strip().startswith("/"):
                result = handle_command(state, line)
            else:
                result = cmd_log(state, line)

            if result.save_session:
                save_session(state)

            if not result.continue_running:
                break

    except KeyboardInterrupt:
        shutdown(state)
        return 0

    except EOFError:
        shutdown(state)
        return 0

    except Exception as exc:
        print(f"\nError: {exc}", file=sys.stderr)

        if state.get("dirty"):
            try:
                print("Attempting to save session before exit...")
                save_session(state)
                print("Session saved.")
            except Exception as save_exc:
                print(f"Failed to save session: {save_exc}", file=sys.stderr)

        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())