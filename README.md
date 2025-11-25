# AI Dungeon Master Assistant

A modular Python-based AI Dungeon Master that runs tabletop RPG adventures, tracks characters, loads module content, and maintains persistent campaign sessions.

This tool uses the OpenAI ChatGPT API to generate dynamic, narrative-driven DM responses while preserving world continuity across sessions.

---

## Features

### AI Dungeon Master

* Generates immersive, concise (1–2 paragraph) fantasy scene descriptions
* Roleplays NPCs using stored appearance, personality, goals, and knowledge
* Integrates player character backstories and traits into the narrative
* Maintains a full story log for continuity

### Module Loader

* Extracts text from a PDF module via command line (`--extract-module`)
* Automatically loads `data/module_text.txt` if available
* Supports custom module file paths via command line options

### Session Management

* Persistent session files stored as JSON
* Persists messages, story logs, and active NPCs
* Command-line option to clear a session (`--clear-session`)
* Default session auto-selected if none is specified

### Modular Codebase

Managers are split into separate files for clean maintenance:

* `managers/session_manager.py`
* `managers/npc_manager.py`
* `managers/pc_manager.py`
* `managers/module_loader.py`

### Colored Terminal Output

* Green for player input prompt
* Yellow for assistant (AI DM) responses

---

## Requirements

* Python 3.10+

* Python packages:

  ```bash
  pip install openai pypdf
  ```

* Environment variable:

  ```bash
  export OPENAI_API_KEY="your_api_key_here"
  ```

---

## Command Line Usage

### Start the AI DM (default session and default module)

```bash
python dm.py
```

Defaults:

* Session: `sessions/default.json`
* Module: `data/module_text.txt`

---

## Command Line Options

### Use a custom session or module text file

```bash
python dm.py --session mycampaign --module data/stormwreck.txt
```

* `--session` can be a name (stored under `sessions/`) or a direct JSON file path
* `--module` is a path to a text file containing module content

### Clear a session

Clear the default session:

```bash
python dm.py --clear-session
```

Clear a named session:

```bash
python dm.py --session mycampaign --clear-session
```

### Extract module text from a PDF

Extract from a PDF into the default module text file:

```bash
python dm.py --extract-module /path/to/module.pdf
```

By default this writes to:

* `data/module_text.txt`

You can override the output path by specifying `--module`:

```bash
python dm.py --extract-module /path/to/module.pdf --module data/custom_module.txt
```

---

## Session Structure

Each session JSON file contains:

```json
{
  "messages": [],
  "story_log": [],
  "active_npcs": []
}
```

The assistant uses this data to maintain story continuity across turns.

---

## NPC Manager

NPCs include:

* Appearance
* Personality
* Goals
* Knowledge
* Relationship to the party

NPC data is stored in:

* `npc_store.json`

---

## Player Character Manager

PCs include:

* Race
* Class
* Appearance
* Personality
* Backstory
* Notes

PC data is stored in:

* `pc_store.json`

These fields are used for narrative integration only; no stats, hit points, or mechanics are tracked.

---

## Example Interaction

```text
You: We enter the ruined lighthouse.
Assistant: The wooden door groans open as a salty wind cuts through the interior, carrying the scent of old rope and damp stone. Faint light filters through broken slats above, painting the circular chamber in pale, uneven bands as the sea crashes somewhere below.
```

Assistant responses are automatically labeled and colorized in the terminal.

---

## Folder Structure

A typical project layout:

```text
dm_assistant/
├── dm.py
├── managers/
│   ├── __init__.py
│   ├── session_manager.py
│   ├── npc_manager.py
│   ├── pc_manager.py
│   └── module_loader.py
├── data/
│   └── module_text.txt
└── sessions/
    └── default.json
```

---

## Optional Future Enhancements

You may extend this tool with:

* In-chat commands (`/addpc`, `/addnpc`, `/listpcs`, `/listnpcs`)
* Quest tracking
* Dice rolling mechanics
* Turn-based combat helpers
* Character or NPC portraits (via image generation tools)
* Procedural map or scene creation
* Web-based interface (Flask or FastAPI)
* Embedding-based memory for large or multiple modules

---

## License

MIT (or your preferred license).

