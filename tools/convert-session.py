#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
from datetime import datetime

DEFAULT_MODEL = "gpt-4.1-mini"


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save_json(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, indent=2), encoding="utf-8")


def convert(old):
    new = {
        "model": old.get("model", DEFAULT_MODEL),
        "summary": old.get("summary", ""),
        "log": [],
        "settings": {
            "max_recent_log_entries": 12,
            "compression_trigger_entries": 20
        },
        "legacy": {
            "active_npcs": old.get("active_npcs", []),
            "combat_active": old.get("combat_active", False),
            "combatants": old.get("combatants", [])
        }
    }

    messages = old.get("messages", [])

    for i in range(0, len(messages), 2):
        user_msg = messages[i] if i < len(messages) else {}
        assistant_msg = messages[i + 1] if i + 1 < len(messages) else {}

        if user_msg.get("role") != "user":
            continue

        prompt = user_msg.get("content", "").strip()

        # Skip empty prompts from old sessions
        if not prompt:
            continue

        response = ""
        if assistant_msg.get("role") == "assistant":
            response = assistant_msg.get("content", "").strip()

        new["log"].append({
            "time": datetime.now().isoformat(timespec="seconds"),
            "prompt": prompt,
            "response": response
        })

    if old.get("story_log") and not new["summary"]:
        new["summary"] = "\n".join(old["story_log"][-10:])

    return new


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("old_session")
    parser.add_argument("new_session")
    args = parser.parse_args()

    old = load_json(args.old_session)
    new = convert(old)

    save_json(args.new_session, new)

    print(f"Converted {args.old_session}")
    print(f"Saved     {args.new_session}")
    print(f"Log entries: {len(new['log'])}")


if __name__ == "__main__":
    main()