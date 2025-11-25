# managers/session_manager.py

import json
import os


class SessionManager:
    def __init__(self, file_path: str = "sessions/default.json"):
        self.file_path = file_path
        self.session = {
            "messages": [],
            "story_log": [],
            "active_npcs": [],
        }
        if os.path.exists(file_path):
            self.load()

    def load(self) -> None:
        with open(self.file_path, "r", encoding="utf-8") as f:
            self.session = json.load(f)

    def save(self) -> None:
        os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump(self.session, f, indent=2)

    def add_message(self, role: str, content: str) -> None:
        self.session["messages"].append({"role": role, "content": content})
        self.save()

    def add_story_event(self, text: str) -> None:
        self.session["story_log"].append(text)
        self.save()

