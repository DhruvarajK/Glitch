<div align="center">
  <img src="assets/icons/glitch.ico" width="128" height="128" alt="Glitch Desktop Pet Logo" />
  <h1>Glitch</h1>
  <p><strong>A modular, production-grade Windows desktop pet featuring autonomous physics, zero-token local intent processing, and decoupled LLM intelligence.</strong></p>

  <p>
    <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python Version" /></a>
    <a href="https://doc.qt.io/qtforpython-6/"><img src="https://img.shields.io/badge/GUI-PySide6%20%2F%20Qt%206-41CD52?style=flat-square&logo=qt&logoColor=white" alt="PySide6 / Qt 6" /></a>
    <a href="https://platform.openai.com/"><img src="https://img.shields.io/badge/LLM-OpenAI%20API-412991?style=flat-square&logo=openai&logoColor=white" alt="OpenAI API" /></a>
    <a href="https://www.sqlite.org/"><img src="https://img.shields.io/badge/Storage-SQLite%20%26%20Keyring-003B57?style=flat-square&logo=sqlite&logoColor=white" alt="SQLite & Keyring" /></a>
    <a href="https://docs.pytest.org/"><img src="https://img.shields.io/badge/Tests-Pytest-0A9EDC?style=flat-square&logo=pytest&logoColor=white" alt="Pytest" /></a>
    <a href="https://pyinstaller.org/"><img src="https://img.shields.io/badge/Packaging-PyInstaller-2C2D72?style=flat-square&logo=python&logoColor=white" alt="PyInstaller" /></a>
    <img src="https://img.shields.io/badge/Platform-Windows%2010%20%7C%2011-0078D6?style=flat-square&logo=windows&logoColor=white" alt="Windows Platform" />
  </p>
</div>

---

## Table of Contents

- [Overview](#overview)
- [Architectural Principles](#architectural-principles)
- [System Architecture](#system-architecture)
- [Core Subsystems](#core-subsystems)
  - [Autonomous Pet Engine & Physics](#autonomous-pet-engine--physics)
  - [Local Intent & Command Engine](#local-intent--command-engine)
  - [Proactive Context Awareness](#proactive-context-awareness)
  - [Decoupled LLM Brain & Dialogue Pipeline](#decoupled-llm-brain--dialogue-pipeline)
- [Interaction Model](#interaction-model)
- [Offline Commands & Intent Matrix](#offline-commands--intent-matrix)
- [Security, Privacy & Budget Controls](#security-privacy--budget-controls)
- [Codebase Layout](#codebase-layout)
- [Installation & Setup](#installation--setup)
- [Animation & Asset Pipeline](#animation--asset-pipeline)
- [Testing & Quality Assurance](#testing--quality-assurance)
- [Packaging & Distribution](#packaging--distribution)
- [Data Locations](#data-locations)
- [Audio Pipeline](#audio-pipeline)

---

## Overview

Glitch is a lightweight, fully autonomous desktop companion engineered for Windows 10 and 11. It roams the desktop, reacts to user input and active workloads, manages productivity reminders, and provides natural conversational interactions when connected to an LLM provider.

Unlike conventional chatbot wrappers, Glitch is designed from the ground up as a native desktop entity. The simulation engine runs entirely locally and independently of external cloud services: without an internet connection or an API key, Glitch maintains its complete behavior tree, physics simulation, animation system, and local tool execution.

---

## Architectural Principles

1. **Strict Engine Decoupling**: The core pet simulation (state machine, physics, animation decoding, desktop geometry) never depends on the AI subsystem. Network latency, API downtimes, or missing credentials will never block GUI rendering or physics updates.
2. **Zero-Token Local Routing**: Common productivity requests (reminders, whitelisted application launching, productivity tracking, fact storage) are parsed and executed entirely offline with zero API calls.
3. **Zero-Trust Security & Privacy**: Sensitive credentials are stored in Windows Credential Manager rather than plaintext configuration files. Process monitoring records only aggregate duration and broad categories without recording window titles or keystrokes unless explicitly enabled.
4. **Strict Cost & Frequency Rationing**: Conversational and proactive triggers are governed by configurable cooldowns, quiet periods, and hard daily token/request ceilings.
5. **High-DPI & Multi-Monitor Native**: Window geometry and coordinate transformations accommodate multi-monitor configurations, virtual desktop bounds, and per-monitor display scaling.

---

## System Architecture

```text
+-----------------------------------------------------------------------+
|                              Qt GUI Thread                            |
|  +--------------------+  +--------------------+  +-----------------+  |
|  |     Pet Window     |  |    Speech Bubble   |  |   Tray & Settings| |
|  |  (Frameless/Alpha) |  |   (Markdown / UI)  |  |     Management  |  |
|  +---------+----------+  +---------+----------+  +--------+--------+  |
+------------|-----------------------|----------------------|-----------+
             |                       |                      |
             v                       v                      v
+-----------------------------------------------------------------------+
|                       Application Event Bus (Pub/Sub)                 |
+------+---------------+---------------+----------------+---------------+
       |               |               |                |
       v               v               v                v
+--------------+ +--------------+ +--------------+ +--------------------+
|  Pet Engine  | | Animation    | | Context      | | Local Tool         |
|  & Physics   | | Decoders     | | Sensors      | | Engine             |
|  (30 Hz FSM) | | (Aseprite)   | | (psutil/Win) | | (SQLite/Scheduler) |
+--------------+ +--------------+ +--------------+ +--------------------+
                                                            |
                                                            | Unhandled
                                                            v Intents
                                                   +--------------------+
                                                   | Async AI Worker    |
                                                   | (OpenAI / Keyring) |
                                                   +--------------------+
```

---

## Core Subsystems

### Autonomous Pet Engine & Physics

- **State Machine**: Driven at a constant 30 Hz tick (`PHYSICS_HZ`). Transitions dynamically between states including `IDLE`, `WALK`, `SIT`, `SLEEP`, `FALL`, `DRAG`, `REACT`, and `THINK`.
- **Personality & Mood Vector**: Evaluates an internal mood state (energy, curiosity, annoyance, sleepiness) to weight Markovian state decisions every few seconds.
- **Physics Integration**: Simulates gravity, boundary collisions, drag acceleration, and floor-detection across primary and secondary display geometries.
- **Window Platforms**: Open application windows are treated as one-way platforms. Glitch lands on a window's top edge, walks along it, rides it as it is moved, and falls back to the desktop once it walks off the end or the window closes, minimises or is covered. Enumeration is confined to `core/screen/desktop_windows.py`; the selection rules are pure geometry in `core/screen/platforms.py`. Disable via **Settings -> Behaviour -> Walk on windows**.

### Local Intent & Command Engine

- **Pattern-Matching Dispatcher**: Intercepts chat inputs locally before invoking remote API calls.
- **Persistent Reminders**: Stored in SQLite (`glitch.db`). Survives process restarts; reminders that mature while Glitch is closed are immediately delivered upon subsequent startup.
- **Application Launcher**: Whitelist-enforced direct executable dispatching. Prevents arbitrary shell command execution.
- **Activity Tracker**: Locally tallies time spent across development, communication, gaming, and media categories.

### Proactive Context Awareness

- **Environmental Sensors**: Monitors active process metadata, system idle time via Windows user input hooks, battery states, and temporal thresholds (such as late-night hours).
- **Proactive Rationing Engine**:
  - Minimum quiet interval between unprompted remarks (10 minutes default).
  - Individual trigger cooldowns to eliminate repetitive remarks.
  - Hard daily limits on proactive observations (6 remarks default).
  - Absolute suppression during fullscreen applications, video playback, active gaming, or sleep mode.

### Decoupled LLM Brain & Dialogue Pipeline

- **Async Streaming Execution**: Responses stream into the UI character-by-character on background worker threads without dropping frame rates.
- **Structured Schema Decoding**: The model outputs dynamic emotional states (19 distinct classifications) and physical actions (9 animations) alongside response text, instantly queuing corresponding animations.
- **Bounded Context Window**: Keeps conversation history within a rolling 12-message window and constrains token output to minimize latency and expenditure.
- **Explicit Long-Term Memory**: Stores user preferences and persistent facts into SQLite on demand (`remember that...` / `forget everything`).

---

## Interaction Model

| Input Action | Result |
| :--- | :--- |
| **Left Click** | Triggers an immediate reactive animation matching the pet's current mood. |
| **Repeated Left Click** | Increments the internal annoyance vector, prompting frustrated animations and dialogue. |
| **Left Click + Drag** | Transitions to `DRAG` state; upon release, simulates gravitational acceleration until landing. |
| **Double Click** | Focuses and opens the conversational chat prompt. |
| **Right Click** | Context menu access for quick settings and state management. |
| **System Tray Icon** | Full control center: Chat, Pause Roaming, Wake/Sleep, Always-on-Top toggle, Click-Through mode, Settings, Hide, and Graceful Exit. |

---

## Offline Commands & Intent Matrix

The following commands are parsed locally via regex and rule engines. They incur **zero token cost** and function completely offline:

| Utterance Pattern | Execution Target | System Behavior |
| :--- | :--- | :--- |
| `"remind me in 20 minutes to stretch"` | Reminder Scheduler | Schedules a background event; persists across restarts in SQLite. |
| `"remind me to rest in half an hour"` | Natural Language Parser | Resolves relative natural language time offsets into exact timestamps. |
| `"open notepad"` | Whitelist Launcher | Validates against approved application registry and starts the process. |
| `"what am I doing?"` / `"how long have I been coding?"` | Activity Monitor | Summarizes aggregate local time tracked for the given category today. |
| `"shut up for an hour"` | Rationing Engine | Temporarily mutes proactive remarks while keeping conversational chat active. |
| `"you can talk again"` | Rationing Engine | Resets proactive silence timer and restores standard observation triggers. |
| `"remember that I use vim"` | Memory Manager | Writes key fact into SQLite storage for injection into future context windows. |
| `"forget everything"` | Memory Manager | Clears all persistent user facts from SQLite storage. |

---

## Security, Privacy & Budget Controls

### Credential Isolation
- API keys are never written to `config.json`, database tables, or application log files.
- Keys are securely dispatched to and retrieved from the **Windows Credential Manager** via the `keyring` library (`KEYRING_SERVICE = "GlitchDesktopPet"`).

### Whitelisted Execution Architecture
- The application launcher operates exclusively on an explicit whitelist defined in `Settings -> Actions`.
- Process execution uses direct system path resolution (`subprocess.Popen`) without invoking shell interpreters (`shell=False`), preventing command injection.

### Privacy-Preserving Telemetry
- By default, awareness monitoring evaluates only process executables and category classifications (e.g., `code_editor`, `browser`).
- Window title inspection is disabled by default and requires explicit user consent via Settings.

### Budget & Rate Limits
- **Daily Request Caps**: Enforces a strict ceiling on total API requests per calendar day (Default: 60).
- **Daily Token Caps**: Enforces a maximum total token consumption per calendar day (Default: 120,000).
- **Token Truncation**: Output generations are constrained to 220 completion tokens per prompt.

---

## Codebase Layout

```text
Glitch/
├── assets/
│   ├── animations/          # Sprite sheets (PNG) and Aseprite frame definitions (JSON)
│   │   └── animations.json  # Central animation manifest and playback registry
│   ├── icons/               # Application and system tray icons (glitch.ico, glitch.png)
│   └── sounds/              # Optional WAV sound effects
├── core/
│   ├── ai/                  # LLM integration, conversation buffer, prompts, emotion parsing
│   ├── animation/           # Manifest registry, frame decoders, sprite scaling
│   ├── awareness/           # Process monitors, system idle hooks, proactive triggers
│   ├── events/              # Publish/subscribe application event bus
│   ├── persistence/         # Configuration manager, SQLite schema, credential storage
│   ├── pet/                 # State machine, physics engine, mood vectors, behavior tree
│   ├── screen/              # Virtual desktop geometry, multi-monitor boundary calculations
│   ├── tools/               # Local intent parsers, reminders, application launcher
│   ├── utils/               # Constants, logging, filesystem path resolution
│   └── application.py       # Central orchestrator and subsystem lifecycle manager
├── ui/
│   ├── widgets/             # Reusable UI controls and styled components
│   ├── autostart.py         # Windows Startup Registry integration
│   ├── chat_bubble.py       # Frameless speech bubble with markdown rendering
│   ├── pet_window.py        # Frameless alpha-channel pet rendering surface
│   ├── settings_window.py   # Multi-tab configuration and budget interface
│   ├── theme.py             # Global typography, palettes, and styling tokens
│   └── tray.py              # System tray integration and context menus
├── scripts/
│   ├── build.py             # PyInstaller automated packaging script
│   └── validate_assets.py   # Asset integrity, frame dimension, and manifest linter
├── tests/                   # Automated pytest suite covering core subsystems
├── glitch.spec              # PyInstaller build specification
├── main.py                  # Application entry point
├── pytest.ini               # Pytest configuration
└── requirements.txt         # Production and development dependencies
```

---

## Installation & Setup

### Prerequisites

- **Operating System**: Windows 10 or Windows 11 (64-bit)
- **Python Runtime**: Python 3.10 or higher

### Development Setup

1. **Clone the Repository**:
   ```bash
   git clone https://github.com/DhruvarajK/Glitch.git
   cd Glitch
   ```

2. **Initialize Virtual Environment**:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   ```

3. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Launch Application**:
   ```bash
   python main.py
   ```

5. **Configure Credentials (Optional)**:
   - Right-click the system tray icon and open **Settings**.
   - Navigate to the **AI** tab and input your OpenAI API Key.
   - The key is securely committed to the Windows Credential Manager.

---

## Animation & Asset Pipeline

All pet visuals utilize single-row sprite sheets exported from Aseprite accompanied by frame metadata JSON files.

- **Manifest Declaration**: Registered inside `assets/animations/animations.json`. Each entry defines frame rate, loop policies, interruptibility, playback priorities, and optional chained animations.
- **Lazy Runtime Loading**: Sprite sheets are decoded on-demand and scaled directly to the target logical resolution (`BASE_PET_HEIGHT = 190`), ensuring minimal resident memory footprint.
- **Asset Integrity Verification**: Run the asset validation linter before committing new animations:
  ```bash
  python scripts/validate_assets.py
  ```

---

## Testing & Quality Assurance

The test suite runs headlessly without requiring an active graphical display, making it fully compatible with automated CI pipelines.

```bash
python -m pytest
```

### Test Coverage Breakdown

- `test_state_machine.py`: State transition rules, timeout fallbacks, and priority overrides.
- `test_physics.py`: Gravitational acceleration, delta calculations, and collision boundaries.
- `test_animation.py`: Manifest parsing, frame sequence math, and sprite cache decoders.
- `test_behaviour.py`: Mood vector calculus and Markovian transition weighting.
- `test_brain.py` & `test_ai.py`: Asynchronous streaming, structured output decoding, and mock LLM pipelines.
- `test_memory.py`: SQLite conversation persistence and memory recall routines.
- `test_awareness.py`: Process categorizers, sensor filters, and rationing window calculations.
- `test_tools.py`: Regex pattern matching, NL reminder resolution, and process whitelisting.

---

## Packaging & Distribution

Glitch includes an automated build pipeline utilizing PyInstaller to produce a self-contained executable.

```bash
pip install pyinstaller
python scripts/build.py
```

The build script executes asset verification and the full test suite before invoking `glitch.spec`. The resulting artifact is generated at:

```text
dist/Glitch.exe
```

*Note: User-specific configuration files (`config.json`), local databases (`glitch.db`), and system logs are never bundled into the binary; they are initialized in user-space upon first execution.*

---

## Data Locations

Glitch adheres to standard Windows directory layouts:

| Storage Type | Filesystem Path | Description |
| :--- | :--- | :--- |
| **Configuration** | `%APPDATA%\GlitchPet\Glitch\config.json` | Application preferences, whitelist registry, awareness flags. |
| **Database** | `%APPDATA%\GlitchPet\Glitch\glitch.db` | SQLite tables for persistent reminders, memory facts, activity metrics. |
| **System Logs** | `%LOCALAPPDATA%\GlitchPet\Glitch\Logs\` | Rolling debug and application event logs. |
| **API Credentials** | Windows Credential Manager | Encrypted storage under target identifier `GlitchDesktopPet`. |

---

## Audio Pipeline

Sound effects in Glitch are fully event-driven and optional. 

To enable audio cues:
1. Place standard `.wav` audio files into `assets/sounds/` adhering to the naming convention:
   - `click.wav`, `drag.wav`, `drop.wav`, `sleep.wav`, `wake.wav`, `talk.wav`, `react.wav`
2. Enable sound playback in **Settings -> Behaviour**. Unassigned sound events fail silently without performance impact.
