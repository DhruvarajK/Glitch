# Glitch

A lightweight Windows desktop pet with an optional AI brain. Glitch lives on
the desktop, roams around, reacts to you, and — when an OpenAI key is
configured — talks back.

The pet engine never depends on the AI layer: with no network and no API key,
Glitch still walks, idles, sleeps, reacts and can be dragged around.

## Requirements

- Python 3.10+
- Windows 10/11 (the window handling targets Windows; other platforms are untested)

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Run

```bash
python main.py
```

Glitch appears on the primary monitor with a system tray icon.

- **Left click** — a reaction
- **Drag** — pick Glitch up and drop it anywhere
- **Right click** — the tray menu
- **Tray icon** — always-on-top, click-through, hide/show, exit

## Layout

```text
main.py                 entry point
core/application.py     wires subsystems together, owns the runtime tick
core/pet/               position, state, physics, behaviour, interaction
core/animation/         manifest registry, sprite decoding, frame playback
core/ai/                brain, conversation, emotion, prompts
core/events/            internal publish/subscribe bus
core/screen/            virtual desktop geometry, multi-monitor support
core/persistence/       configuration and SQLite storage
ui/                     pet window, chat bubble, settings, tray
assets/animations/      one directory per clip: sheet PNG + Aseprite JSON
scripts/                asset validation tooling
```

## Animations

Every animation is declared in `assets/animations/animations.json`, which maps
a logical name (`idle`, `walk`, `think`, `happy`, …) onto a clip directory plus
playback metadata (fps, looping, priority, interruptibility). Sprite sheets are
Aseprite-style: a single-row PNG strip with a sidecar JSON describing frames.

Nothing in the code refers to an asset path directly — add a clip directory,
add a manifest entry, and it is playable.

Validate assets after any change:

```bash
python scripts/validate_assets.py
```

## Data locations

User data lives outside the source tree and is never bundled:

- Config: `%APPDATA%\GlitchPet\Glitch\config.json`
- Database: `%APPDATA%\GlitchPet\Glitch\glitch.db`
- Logs: `%LOCALAPPDATA%\GlitchPet\Glitch\Logs\`
- API key: Windows Credential Manager (never in config or logs)
