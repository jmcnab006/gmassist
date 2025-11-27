Here is a clean, professional **README.md** tailored for your updated `dm.py` DM Assistant system.

You can drop this directly into your project root.

---

# 📘 **AI Dungeon Master — README**

This project provides an **AI-powered Dungeon Master** for running tabletop RPG adventures with dynamic storytelling, NPC interaction, combat triggers, and stat block generation.
It uses the **new OpenAI Python SDK** (2024+), Markdown rendering via **Rich**, and supports **DM-only slash commands** like `/combat` and `/statblocks`.

---

## 🚀 Features

* **AI Dungeon Master narration**
* **Rich Markdown** output for immersive scenes
* **NPC Manager** (appearance, personality, goals, etc.)
* **Player Character Manager** (appearance, personality, backstory)
* **Session persistence** using `sessions/default.json`
* **Automatic module loading** from `data/module_text.txt`
* **DM-only commands**

  * `/combat` — forcibly trigger combat and generate stat blocks
  * `/statblocks` — show stat blocks based on the current encounter
* **Combat logic**

  * Automatic combat narration when violence escalates
  * Alignment-based willingness to fight
  * Stat blocks for all combatants
* **Arrow-key navigation** in input via `readline`

---

## 📦 Requirements

Install dependencies:

```bash
pip install openai rich pypdf
```

(Optional) For arrow-key input editing on Windows:

```bash
pip install pyreadline3
```

---

## 🔑 Environment Variable

Make sure the **OpenAI API key** is set before running:

### Linux / macOS

```bash
export OPENAI_API_KEY="your_api_key_here"
```

### Windows (PowerShell)

```powershell
setx OPENAI_API_KEY "your_api_key_here"
```

### Windows (cmd)

```cmd
set OPENAI_API_KEY=your_api_key_here
```

---

## 📁 Directory Structure

```
project/
  dm.py
  extract_module.py
  npc_store.json
  pc_store.json
  sessions/
      default.json
  data/
      module_text.txt  (optional — autoloaded)
  README.md
```

---

## 📄 Loading a Module

If you want the DM to reference a campaign or adventure module:

1. Place your module PDF anywhere
2. Run:

```bash
python extract_module.py module.pdf
```

This creates:

```
data/module_text.txt
```

`dm.py` will automatically detect and load it on startup.

If no module exists, the DM still works normally.

---

## ▶️ Running the Dungeon Master

Start the AI DM:

```bash
python dm.py
```

You will see:

```
=== AI Dungeon Master ===
DM is ready. Begin your adventure.
```

Enter your actions or dialogue as if speaking to the DM.

---

## 🎮 Gameplay Controls

### 🧙 Player Input

Just type:

```
We travel north toward the ruined monastery.
```

The AI DM responds with vivid, concise narration.

---

## ⚔️ DM-Only Slash Commands

These commands **begin with `/`** and **do not enter the story log**.

### Start Combat

```
/combat
```

Triggers combat immediately and generates stat blocks.

### Show Stat Blocks

```
/statblocks
```

Reprints stat blocks from the current encounter.

---

## 🧠 Notes About NPC Names & Player Knowledge

* NPC names are **not revealed** until introduced.
* Unknown enemies use descriptions like "Armored Guard" or "Young Bandit".
* Combat stats never break character knowledge.

---

## 🧱 Session Storage

All story logs, NPC interactions, and DM/AI conversation history are saved to:

```
sessions/default.json
```

The session loads automatically each time `dm.py` runs.

---

## 🛠 Troubleshooting

### API Key Not Found

If you see:

```
openai.AuthenticationError: No API key provided
```

Make sure `OPENAI_API_KEY` is exported in your shell environment.

### Arrow keys don’t work

Install:

```
pip install pyreadline3
```

Or make sure you're running Python in a standard terminal (not VSCode debug console).

---

## 📝 License

You may freely modify or extend this project for personal or gaming use.

---

If you want a *fancier* README with images, badges, examples, or command reference tables, I can enhance it anytime.

