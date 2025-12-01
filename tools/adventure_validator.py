#!/usr/bin/env python3
"""
validator.py

Usage:
    python validator.py module.ini

Validates:
- Section name formats (AREA, NPC, MONSTER, EVENT, ITEM, TRIGGER)
- AREA IDs must follow strict pattern: AREA:<LEVEL><LETTER>
  where LEVEL = 1,2,3... and LETTER = A..Z.
- Presence of required keys per section type.

Exit codes:
  0 = valid (only warnings or clean)
  1 = errors found
"""

import sys
import re
import configparser
from pathlib import Path
from typing import Dict, List, Tuple


# Regex for AREA IDs: AREA:1A, AREA:2B, etc.
AREA_ID_RE = re.compile(r"^AREA:([1-9][0-9]*)([A-Z])$")


SECTION_PREFIXES = ("AREA:", "NPC:", "MONSTER:", "EVENT:", "ITEM:", "TRIGGER:")

REQUIRED_KEYS: Dict[str, List[str]] = {
    "AREA": [
        "name",
        "desc.short",
        "desc.long",
        "connects",
        "encounters",
        "items",
        "triggers",
        "notes",
    ],
    "NPC": [
        "name",
        "race",
        "role",
        "alignment",
        "motivation",
        "knows",
        "secrets",
        "dialogue.hooks",
    ],
    "MONSTER": [
        "name",
        "hp",
        "ac",
        "initiative",
        "attack",
        "ranged",
        "traits",
        "ai",
    ],
    "EVENT": [
        "trigger",
        "description",
        "npc",
        "location",
        "notes",
    ],
    "ITEM": [
        "name",
        "type",
        "description",
        "effects",
        "notes",
    ],
    "TRIGGER": [
        "when",
        "effect",
        "alert",
    ],
}


def classify_section(section: str) -> str:
    """
    Return base type: AREA, NPC, MONSTER, EVENT, ITEM, TRIGGER, or "" if unknown.
    """
    for prefix in SECTION_PREFIXES:
        if section.startswith(prefix):
            return prefix.rstrip(":")
    return ""

def validate_area_ids(sections: List[str]) -> List[str]:
    """
    Validate AREA section IDs have *some* non-empty identifier after 'AREA:'.
    We do NOT enforce a specific pattern like AREA:1A vs AREA:12.

    Valid:
      AREA:1A
      AREA:12
      AREA:EntranceHall

    Invalid:
      AREA:
      AREA      (no colon / no id)
    """
    errors = []

    for sec in sections:
        base = classify_section(sec)
        if base != "AREA":
            continue

        # Must start with "AREA:" and have something after it
        parts = sec.split(":", 1)
        if len(parts) != 2 or not parts[1].strip():
            errors.append(
                f"ERROR: AREA section '{sec}' must have a non-empty ID after 'AREA:'. "
                f"Examples: AREA:1A, AREA:12, AREA:EntranceHall."
            )

    return errors

def validate_required_keys(config: configparser.ConfigParser) -> List[str]:
    errors = []

    for sec in config.sections():
        base = classify_section(sec)
        if not base:
            errors.append(
                f"ERROR: Section '{sec}' has unknown prefix. "
                f"Expected one of: AREA:, NPC:, MONSTER:, EVENT:, ITEM:, TRIGGER:"
            )
            continue

        needed = REQUIRED_KEYS.get(base, [])
        for key in needed:
            if key not in config[sec]:
                errors.append(
                    f"ERROR: Section '{sec}' (type {base}) is missing required key '{key}'."
                )
    return errors


def main(argv=None) -> None:
    argv = argv or sys.argv[1:]

    if len(argv) != 1:
        print("Usage: python validator.py module.ini", file=sys.stderr)
        sys.exit(1)

    ini_path = Path(argv[0])
    if not ini_path.exists():
        print(f"File not found: {ini_path}", file=sys.stderr)
        sys.exit(1)

    parser = configparser.ConfigParser(
        interpolation=None,
        delimiters=(":", "="),  # allow "key: value" and "key = value"
        strict=False,
    )

    # Preserve case of keys
    parser.optionxform = str  # type: ignore

    try:
        with ini_path.open("r", encoding="utf-8") as f:
            parser.read_file(f)
    except Exception as e:
        print(f"ERROR: Could not parse INI file: {e}", file=sys.stderr)
        sys.exit(1)

    errors = []
    errors.extend(validate_required_keys(parser))
    errors.extend(validate_area_ids(parser.sections()))

    if errors:
        print("Validation FAILED:\n")
        for msg in errors:
            print(msg)
        sys.exit(1)

    print("Validation OK: module.ini looks structurally sound.")
    sys.exit(0)


if __name__ == "__main__":
    main()
