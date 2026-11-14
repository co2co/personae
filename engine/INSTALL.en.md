<p align="center">
  <a href="INSTALL.md">简体中文</a> | <b>English</b>
</p>

# Personae (working title) — Installation Guide

This guide is for **users who received the distribution package**: the `engine/` directory alone is enough to run it, and no Python project experience is required. Everything can be done graphically (double-click the `.bat` files); the command line is a fallback.

> UI labels below are quoted in English, which is what a non-Chinese system shows. On a Chinese system the same panels appear in Chinese. The interface language can be overridden under System Settings → Interface Language.

---

## 1. Requirements

- OS: Windows 10 / 11 (macOS and Linux work too; see the cross-platform notes in sections 3 and 4)
- Python: **3.10 or newer** (3.12 recommended; from [python.org](https://www.python.org) or the Microsoft Store)
- Network: needed once to install dependencies, and whenever you call a cloud model

---

## 2. Download and Extract

1. Get the package `personae-vX.Y.zip`.
2. Extract it anywhere (a path without non-ASCII characters or spaces is safest). You get an `engine/` directory.

> **Extraction tool**: use **Windows Explorer's "Extract All"** or **7-Zip**. Do not use old-style tools such as `unzip` inside Git Bash — they may garble non-ASCII file names. (Garbled names only affect how files are displayed, not whether the engine runs; use one of the two tools above to avoid confusion.)

---

## 3. Install Dependencies (once)

Go into `engine/` and double-click **`install.bat`**. It will:

1. detect Python (preferring `py -3`, falling back to `python`);
2. create a virtual environment at `engine/venv`;
3. pip-install what `requirements.txt` lists (Flask, requests).

The script's own messages are in Chinese; wait until it reports success. If it fails, install manually:

```bat
cd engine
python -m venv venv
venv\Scripts\pip install -r requirements.txt
```

**macOS / Linux (cross-platform):**

```bash
cd engine
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---

## 4. Start the Engine

Either method works:

- **Graphical**: double-click `engine/run.bat` (default port **5051**).
- **Command line**:

  ```bat
  cd engine
  python app.py                 # defaults to http://127.0.0.1:5000
  ```

  To use another port, set the environment variable before starting:

  ```bat
  set PORT=8080
  python app.py
  ```

When the terminal prints `Running on http://127.0.0.1:5051`, it is up.
(`run.bat` also releases the port if something is holding it; with a manual `python app.py` you change the port yourself.)

---

## 5. Open and Use

Browse to the address (default `http://127.0.0.1:5051`, or `http://127.0.0.1:5000` when started manually).

The top bar has four panels:

- **Character Library**: create / edit / delete character cards, or **Import JSON** from an external file (unrecognized fields are preserved).
- **Worldbook**: edit worldbook entries; the "worldbook manual" link opens the full guide (`/docs/worldbook`).
- **Sessions**: list / resume / abandon dramas in progress.
- **System Settings**: model and generation parameters, plus the writer persona.

Close the terminal window or press `Ctrl+C` to stop the server.

---

## 6. Configure a Model (System Settings)

The engine calls models through an **OpenAI-compatible API**. In **System Settings** fill in:

- `base_url`: endpoint URL (defaults to a local inference server, e.g. llama.cpp's `http://127.0.0.1:1234/v1`; any OpenAI-compatible service works)
- `model`: model name (local: whatever your backend reports, such as the gguf file name; cloud: the name the provider gives)
- `api_key`: your key

Save and it takes effect immediately — **no restart needed**.

> You can start the engine, browse the UI, and edit content without a key; only "start simulation" fails when it calls the model.

### Writer Persona

Under **System Settings → Writer Persona** you rewrite this writer's name and self-description: they decide
**which tone, technique and taste** the prose comes out in, not what may be written. Leave the self-description
blank to keep the factory writer — the writer is always present and cannot be switched off. Saving takes effect
immediately, **no restart needed**. The text lives in the `writer` field of `engine/data/config.json`; it is
personal creative content and never ships in the release package.

---

## 7. Where Your Content Lives

All data is local files under `engine/`, with no database:

- `data/characters/*.json` — character cards (**the file name is the character's display name**; add your own)
- `data/worlds/*.json` — worldbooks (add your own)
- `data/config.json` — system configuration (ships with an empty connection)

**The package ships no drama at all** — you get an empty library, and you fill `data/characters/` and `data/worlds/` yourself. Create a drama in the Drama Library, or use Generate from Script to distil an existing script into character cards and a worldbook. To see what a complete, distillable script looks like, open `/static/script-example.txt` in the browser (a bundled sample text, not playable data).
(Session records live in `data/sessions/` and state in `data/state.json` — those are not packaged either.)

---

## 8. Troubleshooting

- **Port already in use**: `run.bat` kills the holding process automatically; with a manual start, change the `PORT` environment variable.
- **Python not found**: add Python 3.10+ to PATH, or install the Microsoft Store build.
- **Dependency install slow or failing**: check your network or proxy; configure a pip mirror.
- **Browser cannot open the page**: verify the address and port, and that the firewall is not blocking the loopback interface.
- **`/docs/worldbook` returns 500**: `static/worldbook-guide.html` is missing or renamed; re-extract the package.

---

## 9. Upgrading

Take the new package and **overwrite** the old `engine/` directory.
If you have accumulated cards / worldbooks / sessions, back up `engine/data/` first; when overwriting, keep your `data/` and update only the code and frontend.

---

For fuller mechanics see `/docs/worldbook` in the browser (worldbook); for the engine layout and per-file responsibilities see [`README.md`](README.md); the version is in the `VERSION` file.
