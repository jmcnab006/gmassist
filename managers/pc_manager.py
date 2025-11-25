# managers/pc_manager.py

import json
import os


class PlayerCharacterManager:
    def __init__(self, pc_file: str = "pc_store.json"):
        self.pc_file = pc_file
        self.pcs = {}
        if os.path.exists(pc_file):
            self.load()

    def load(self) -> None:
        with open(self.pc_file, "r", encoding="utf-8") as f:
            self.pcs = json.load(f)

    def save(self) -> None:
        with open(self.pc_file, "w", encoding="utf-8") as f:
            json.dump(self.pcs, f, indent=2)

    def ensure_pc(self, name: str) -> None:
        """Minimal narrative PC fields, including appearance."""
        if name not in self.pcs:
            self.pcs[name] = {
                "name": name,
                "race": "",
                "class": "",
                "appearance": "",
                "personality": "",
                "backstory": "",
                "notes": "",
            }
            self.save()

    def update_pc(self, name: str, field: str, value) -> None:
        self.ensure_pc(name)
        self.pcs[name][field] = value
        self.save()

    def get_all_pc_descriptions(self) -> str:
        desc = []
        for name, data in self.pcs.items():
            desc.append(f"Player Character: {name}\n{json.dumps(data, indent=2)}")
        return "\n\n".join(desc)

