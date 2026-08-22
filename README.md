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
an emotion (19 of them) and an action (9), which drive the animation Glitch
plays afterwards.
If a request fails — no key, no network, a timeout, a rate limit — Glitch says
so and carries on; nothing blocks the GUI.

Memory is explicit. Say *"remember that I prefer dark themes"* and the fact is
stored and included in later conversations; *"forget everything"* clears it.

### Telling Glitch to do things

Glitch does more than talk. These are recognised and carried out **locally,
with no API request at all** - they work with no key and no network:

| Say | It does |
| --- | --- |
| "remind me in 20 minutes to stretch" | Schedules it; survives a restart |
| "remind me to rest in half an hour" | Same, in plain English |
| "open notepad" | Launches an approved app |
| "what am I doing?" / "how long have I been coding?" | Reports the day from its own records |
| "shut up for an hour" | Mutes unprompted remarks; chat still works |
| "you can talk again" | Unmutes |
| "remember that ..." | Stores a fact |

Anything not recognised is ordinary conversation and goes to the brain as
before, so a phrasing that misses costs nothing but a normal reply.

Reminders live in the database. One that came due while Glitch was closed is
delivered on the next launch rather than lost.

**Opening apps is whitelisted.** Notepad, calculator and paint work out of the
box; anything else has to be added in **Settings -> Actions**. A name from a
chat message is only ever used as a key into that list, never as a command, and
the program is started directly rather than through a shell.

### Keeping the cost down

The AI is the only part that costs anything, so most of Glitch avoids it:

- Every instruction above is handled locally - zero tokens.
- Unprompted remarks use written-in lines by default; AI-written ones are
  off until you turn them on in **Settings -> Awareness**.
- Replies are capped at 220 output tokens, which is more than a speech bubble
  needs, and only the last 12 messages of context are sent.
- **Daily ceilings** in **Settings -> AI**: 60 requests and 120,000 tokens by
  default. On reaching either, Glitch says so and stops making requests until
  tomorrow. Set either to zero for no limit.
- The AI tab shows what has been spent today and in total.

Time spent per kind of app is tracked locally so "how long have I been coding"
is answerable without asking a model. Only the category and a running total of
seconds are stored - never an app name or a window title.

### Noticing things on its own

Glitch watches the machine around it and occasionally speaks first. It notices
apps starting, which kind of app is in front, long unbroken stretches of work,
you leaving and coming back, a nearly empty battery, and the small hours of the
morning.

Most reactions are local: a canned line and a matching clip, free and instant,
working with no API key. Turn on **Settings → Awareness → Write these lines
with AI** and the *situation* — never a window title — is handed to the model,
which writes the line instead.

Being unprompted is rationed, because a pet that talks whenever it can is
unbearable by lunchtime:

- a quiet period between remarks (10 minutes by default)
- a per-trigger cooldown, so the same observation cannot repeat
- a daily ceiling (6 by default); set it to 0 to keep Glitch silent while it
  still reacts with a face
- silence entirely while it is asleep or hidden, while you are typing to it,
  while it is already talking, and behind any fullscreen window
- no remarks at all when a call, a game or a video player is in front

**What it looks at:** the names of running processes, which one has focus, how
long since your last keypress, and the battery. Window titles are read only if
you turn them on, and that toggle asks first. Nothing is sent anywhere unless
you enable AI replies, and then only the category — "the user just opened a
code editor" — never the app name or the title.

Turn the whole thing off with **Settings → Awareness → Notice what I'm doing**.

## Layout

```text
main.py                 entry point
core/application.py     wires subsystems together, owns the runtime tick
core/pet/               state machine, physics, behaviour, interaction
core/animation/         manifest registry, sprite decoding, frame playback
core/ai/                brain, conversation, memory, emotion, prompts
core/awareness/         sensors, app categories, triggers and rationing
core/tools/             local instructions: reminders, launching, activity
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
playback, screen geometry, behaviour weighting, emotion, memory, the database,
awareness detection and rationing, local instruction parsing, reminders, the
whitelisted launcher, the cost ceilings, and the full AI streaming path against
a fake client. It runs offscreen and
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
