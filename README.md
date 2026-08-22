# Glitch

A lightweight Windows desktop pet with an optional AI brain. Glitch lives on
the desktop, roams around, reacts to you, and — when an OpenAI key is
configured — talks back through a speech bubble.

The pet engine never depends on the AI layer. With no network and no API key,
Glitch still walks, idles, sits, sleeps, reacts and can be dragged around; the
AI only adds conversation on top.

## Requirements

- Python 3.10+
- Windows 10/11 (the window handling targets Windows; other platforms are untested)

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

Glitch appears on the primary monitor with a system tray icon.

## Using Glitch

| Action | Result |
| --- | --- |
| Left click | A reaction, chosen to match its mood |
| Click repeatedly | Annoyance, then a less friendly reaction |
| Drag | Pick Glitch up; it falls and lands when released |
| Double click | Opens the chat prompt |
| Right click | The tray menu |
| Tray icon | Chat, pause movement, wake up, always-on-top, click-through, settings, hide, exit |

Left alone, Glitch makes its own decisions every few seconds — wandering,
sitting, looking around, playing, yawning — weighted by how energetic, curious,
annoyed or sleepy it currently is. After long enough without attention it
falls asleep, and wakes when you click it.

### Talking to Glitch

Add an OpenAI API key in **Settings → AI**. It is stored in the Windows
Credential Manager, never in the config file, database or logs.

Replies stream into the speech bubble as they arrive, and the model also picks
an emotion and an action, which drive the animation Glitch plays afterwards.
If a request fails — no key, no network, a timeout, a rate limit — Glitch says
so and carries on; nothing blocks the GUI.

Memory is explicit. Say *"remember that I prefer dark themes"* and the fact is
stored and included in later conversations; *"forget everything"* clears it.

## Layout

```text
main.py                 entry point
core/application.py     wires subsystems together, owns the runtime tick
core/pet/               state machine, physics, behaviour, interaction
core/animation/         manifest registry, sprite decoding, frame playback
core/ai/                brain, conversation, memory, emotion, prompts
core/events/            internal publish/subscribe bus
core/screen/            virtual desktop geometry, multi-monitor support
core/persistence/       config, SQLite storage, credential storage
ui/                     pet window, chat bubble, settings, tray, autostart
assets/animations/      one directory per clip: sheet PNG + Aseprite JSON
scripts/                asset validation and build tooling
```

Four layers, with one rule holding them apart: **the pet engine must never
depend on the AI engine to keep working.**

## Animations

Every animation is declared in `assets/animations/animations.json`, which maps
a logical name (`idle`, `walk`, `think`, `happy`, …) onto a clip directory plus
playback metadata: fps, looping, priority, interruptibility and an optional
follow-on clip. Sprite sheets are Aseprite-style — a single-row PNG strip with
a sidecar JSON describing each frame.

Nothing in the code refers to an asset path directly. Add a clip directory, add
a manifest entry, and it is playable. Sheets are decoded straight to display
size, so the 2048px source frames never sit in memory at full resolution, and
clips load lazily the first time they are needed.

Validate after any change:

```bash
python scripts/validate_assets.py
```

## Tests

```bash
python -m pytest
```

The suite covers the state machine, physics, configuration, animation
playback, screen geometry, behaviour weighting, emotion, memory, the database
and the full AI streaming path against a fake client. It runs offscreen and
needs no display.

## Building an executable

```bash
pip install pyinstaller
python scripts/build.py
```

This validates the assets, runs the tests, then produces `dist/Glitch.exe`
with the animations bundled. User data is never packaged — config, database
and credentials are created on first launch.

## Data locations

- Config: `%APPDATA%\GlitchPet\Glitch\config.json`
- Database: `%APPDATA%\GlitchPet\Glitch\glitch.db`
- Logs: `%LOCALAPPDATA%\GlitchPet\Glitch\Logs\`
- API key: Windows Credential Manager

## Sounds

None ship with Glitch. Drop WAV files named `click`, `drag`, `drop`, `sleep`,
`wake`, `talk` or `react` into `assets/sounds/` and enable sound effects in
Settings → Behaviour; cues with no file stay silent.
