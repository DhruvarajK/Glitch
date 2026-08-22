# Glitch AI Desktop Pet — Complete Updated Implementation Plan

## 1. Project Goal

Build **Glitch**, a lightweight, production-quality Windows desktop pet that:

- Lives directly on the user's desktop.
- Moves and roams autonomously across the screen.
- Can walk, idle, sit, sleep, react, think, talk, and be dragged.
- Remains above normal application windows when configured.
- Uses pre-rendered sprite-sheet animations.
- Responds intelligently using OpenAI's API.
- Displays AI responses through a dynamic speech bubble.
- Maintains local conversation and personality state.
- Supports multiple monitors and Windows display scaling.
- Uses minimal CPU/RAM while running continuously in the background.
- Provides a system-tray-based configuration interface.
- Can eventually support voice, sounds, memory, notifications, and richer desktop interaction without rewriting the core architecture.

The application should be designed as a **local autonomous desktop creature with an AI brain**, rather than as an AI chatbot wrapped inside a desktop window.

---

# 2. Recommended Technology Stack

### Core

- **Python 3.11+**
- **PySide6**
- **OpenAI Python SDK**
- **SQLite**
- **asyncio**
- **Pillow** for sprite processing where required

### Optional

- `keyring` for secure API-key storage.
- `platformdirs` for Windows-standard application data/config paths.
- `python-dotenv` for development-only environment variables.
- `pytest` for automated tests.
- `pydantic` for structured configuration and AI response models.

### Why PySide6

PySide6 provides the Windows desktop primitives needed by Glitch:

- Frameless windows
- Transparent windows
- Always-on-top windows
- Mouse interaction
- Window movement
- System tray integration
- Timers
- Screen information
- DPI-aware geometry

The GUI thread remains responsible for rendering and interaction, while the AI/network layer stays asynchronous and isolated.

---

# 3. High-Level Architecture

```text
                         ┌───────────────────────┐
                         │      Glitch App        │
                         └───────────┬───────────┘
                                     │
                ┌────────────────────┼────────────────────┐
                │                    │                    │
                ▼                    ▼                    ▼
        Pet Runtime              UI Layer            System Tray
                │                    │
        ┌───────┼────────┐           │
        │       │        │           │
        ▼       ▼        ▼           ▼
     Behavior State   Physics    Chat Bubble
     Engine   Machine Controller
        │       │        │
        └───────┼────────┘
                │
                ▼
        Animation Controller
                │
                ▼
          Sprite Registry
                │
                ▼
             Assets

                         AI Layer
                            │
                ┌───────────┼───────────┐
                ▼           ▼           ▼
             Brain     Conversation   Emotion
                │
                ▼
           OpenAI SDK
                │
                ▼
             OpenAI API

                  Persistence Layer
                            │
                   ┌────────┴────────┐
                   ▼                 ▼
               config.json       glitch.db
                   │                 │
                   ▼                 ▼
             Preferences       Conversations
                               Memories
                               Usage
```

---

# 4. Core Design Principle

The application must function normally without an internet connection.

### Without OpenAI

Glitch should still:

- Walk
- Stop
- Idle
- Blink
- Sit
- Sleep
- Wake
- React to clicks
- React to dragging
- Wander around
- Recover from screen boundaries
- Use local animations
- Display local UI

### With OpenAI

Glitch additionally gains:

- Natural conversation
- Contextual responses
- Emotion selection
- Personality
- Memory
- Dynamic reactions
- Talking behavior

OpenAI should therefore be an **optional intelligence layer**, not a dependency of the pet runtime.

---

# 5. Project Structure

```text
glitch/
│
├── main.py
├── requirements.txt
├── README.md
├── .gitignore
│
├── core/
│   ├── application.py
│   │
│   ├── pet/
│   │   ├── controller.py
│   │   ├── state.py
│   │   ├── state_machine.py
│   │   ├── behavior.py
│   │   ├── physics.py
│   │   └── interaction.py
│   │
│   ├── animation/
│   │   ├── controller.py
│   │   ├── sprite_loader.py
│   │   ├── registry.py
│   │   └── animation_data.py
│   │
│   ├── ai/
│   │   ├── brain.py
│   │   ├── conversation.py
│   │   ├── emotion.py
│   │   ├── prompts.py
│   │   └── models.py
│   │
│   ├── events/
│   │   ├── bus.py
│   │   └── events.py
│   │
│   ├── screen/
│   │   ├── manager.py
│   │   └── geometry.py
│   │
│   ├── persistence/
│   │   ├── database.py
│   │   ├── models.py
│   │   └── config.py
│   │
│   └── utils/
│       ├── logger.py
│       ├── timers.py
│       └── constants.py
│
├── ui/
│   ├── pet_window.py
│   ├── chat_bubble.py
│   ├── settings_window.py
│   ├── tray.py
│   └── widgets/
│
├── assets/
│   ├── animations/
│   │   ├── idle/
│   │   ├── walking/
│   │   ├── thinking/
│   │   ├── talking/
│   │   ├── sleeping/
│   │   └── reactions/
│   │
│   ├── sounds/
│   └── icons/
│
├── data/
│   ├── config.json
│   └── glitch.db
│
├── tests/
│   ├── test_animation.py
│   ├── test_state_machine.py
│   ├── test_physics.py
│   ├── test_config.py
│   └── test_ai.py
│
└── scripts/
    └── validate_assets.py
```

---

# 6. Application Bootstrap

## `main.py`

Responsibilities:

1. Create the Qt application.
2. Configure application metadata.
3. Initialize logging.
4. Initialize configuration.
5. Initialize persistence.
6. Initialize event bus.
7. Initialize screen manager.
8. Initialize animation registry.
9. Initialize pet controller.
10. Initialize AI brain.
11. Initialize system tray.
12. Create the pet window.
13. Start the runtime.

Startup sequence:

```text
main.py
   ↓
QApplication
   ↓
ConfigManager
   ↓
Database
   ↓
EventBus
   ↓
ScreenManager
   ↓
AnimationRegistry
   ↓
AI Brain
   ↓
PetController
   ↓
PetWindow
   ↓
TrayController
   ↓
Application starts
```

---

# 7. Pet Window

## `ui/pet_window.py`

The pet window should be:

- Frameless
- Transparent
- Borderless
- Configurable as always-on-top
- Sized to the current sprite
- Mouse-aware
- Able to move independently of standard windows

It should **not** contain the pet's behavioral logic.

Its responsibilities are strictly:

```text
Rendering
Mouse events
Window flags
Position
Visibility
Chat bubble attachment
```

### Window configuration

Use:

- `Qt.FramelessWindowHint`
- `Qt.WA_TranslucentBackground`
- `Qt.WindowStaysOnTopHint` when enabled

The actual sprite should be rendered inside the transparent window.

---

# 8. Pet Controller

## `core/pet/controller.py`

This is the primary orchestrator for Glitch's physical behavior.

Responsibilities:

- Current position
- Current velocity
- Current state
- Current animation
- Movement
- Behavior decisions
- Physics updates
- Interaction responses
- Event handling

It coordinates:

```text
PetStateMachine
BehaviorController
PhysicsController
AnimationController
InteractionController
```

It should not know implementation details of OpenAI.

---

# 9. State Machine

## `core/pet/state_machine.py`

Define explicit states:

```python
IDLE
WALKING
RUNNING
LOOKING
SITTING
THINKING
TALKING
HAPPY
SAD
ANGRY
CONFUSED
SLEEPING
WAKING
DRAGGED
DROPPED
```

### State priorities

```text
DRAGGED       100
THINKING       80
REACTION       70
TALKING        60
SLEEPING       50
WALKING        20
IDLE           10
```

Higher-priority states override lower-priority behavior where appropriate.

Example:

```text
WALKING
   ↓
Mouse press
   ↓
DRAGGED
   ↓
Mouse release
   ↓
DROPPED
   ↓
IDLE/WALKING
```

AI:

```text
IDLE
   ↓
User asks question
   ↓
THINKING
   ↓
AI response
   ↓
EMOTION
   ↓
TALKING / HAPPY / CONFUSED
   ↓
IDLE
```

---

# 10. Behavior Controller

## `core/pet/behavior.py`

This controls autonomous behavior.

It should periodically make decisions without involving an LLM.

Example behavior probabilities:

```text
Blink               25%
Look around         10%
Walk                 8%
Sit                  5%
Stretch              3%
Playful reaction     2%
Yawn                 2%
Sleep transition     1%
Remain idle         44%
```

These values should be configurable.

Behavior should also depend on internal state.

Example:

```text
high energy
→ walking becomes more likely

high sleepiness
→ sitting/sleeping becomes more likely

high curiosity
→ looking/wandering becomes more likely
```

---

# 11. Emotional System

## `core/ai/emotion.py`

Maintain local emotional variables:

```python
EmotionState:
    happiness
    energy
    curiosity
    annoyance
    sleepiness
    affection
```

Values should generally stay in:

```text
0.0 → 1.0
```

Example:

```text
User clicks Glitch gently
→ happiness + 0.05

User drags Glitch
→ annoyance + 0.10

Long inactivity
→ sleepiness + 0.03

Interesting AI interaction
→ curiosity + 0.05
```

AI responses can modify emotions but should do so through validated structured data.

---

# 12. Physics System

## `core/pet/physics.py`

Implement lightweight desktop physics.

### Required

- Horizontal movement
- Vertical position
- Gravity
- Floor collision
- Screen-edge collision
- Basic acceleration
- Friction
- Drop behavior

Internal representation:

```python
position
velocity
acceleration
```

Example:

```text
gravity = 1200 px/s²
walk_speed = configurable
fall_speed = capped
```

Values should be tuned empirically instead of hardcoded permanently.

---

# 13. Coordinate System

## `core/screen/manager.py`

The application must support:

- Multiple monitors
- Different monitor resolutions
- Negative screen coordinates
- Mixed DPI
- Monitor changes during runtime
- Taskbar-aware available geometry where appropriate

Represent the desktop as a virtual coordinate space.

```text
Monitor A
x = 0
y = 0

Monitor B
x = 1920
y = 0
```

Do not assume the primary monitor is the only screen.

---

# 14. Animation System

## `core/animation/controller.py`

The animation system handles rendering only.

Responsibilities:

- Load animations
- Select animation
- Advance frames
- Loop or stop
- Notify completion
- Control FPS
- Cache sprite frames

It should not decide *why* the animation plays.

---

# 15. Sprite Sheet Format

Use one sprite sheet per animation whenever practical.

Example:

```text
assets/
└── animations/
    └── reactions/
        └── amazed.png
```

Sprite sheet:

```text
┌────┬────┬────┬────┬────┬────┬────┬────┐
│ F1 │ F2 │ F3 │ F4 │ F5 │ F6 │ F7 │ F8 │
└────┴────┴────┴────┴────┴────┴────┴────┘
```

This is preferable to maintaining hundreds of separate files.

---

# 16. Animation Registry

## `core/animation/registry.py`

Use metadata rather than hardcoded asset paths.

Example:

```json
{
  "idle": {
    "file": "idle/default.png",
    "frames": 8,
    "fps": 8,
    "loop": true
  },
  "walking": {
    "file": "walking/walk.png",
    "frames": 10,
    "fps": 12,
    "loop": true
  },
  "amazed": {
    "file": "reactions/amazed.png",
    "frames": 8,
    "fps": 12,
    "loop": false
  }
}
```

The exact metadata schema should remain centralized.

---

# 17. Animation Priority and Interruptions

Implement animation priorities.

Example:

```text
IDLE animation
    ↓
WALK animation
    ↓
HAPPY reaction overrides WALK
    ↓
reaction finishes
    ↓
WALK resumes
```

Some animations must be interruptible:

```text
idle
walking
```

Some should normally complete:

```text
amazed
celebrate
wake
```

Some have absolute priority:

```text
dragged
```

---

# 18. AI Brain

## `core/ai/brain.py`

The AI brain should provide a clean API:

```python
await brain.respond(
    message=user_message,
    context=conversation_context
)
```

Internally:

```text
User message
     ↓
Conversation manager
     ↓
Prompt builder
     ↓
OpenAI client
     ↓
Structured AI response
     ↓
Emotion parser
     ↓
Pet event
```

---

# 19. Structured AI Response

Do not rely on free-form parsing such as:

```text
"Happy response 😊"
```

Prefer structured output:

```json
{
  "message": "Haha, that's actually funny.",
  "emotion": "amused",
  "intensity": 0.7,
  "action": "talk"
}
```

Possible emotions:

```text
neutral
happy
amused
sad
angry
confused
surprised
sleepy
excited
curious
```

Possible actions:

```text
talk
idle
laugh
look
celebrate
sleep
```

The application should validate the response before using it.

---

# 20. AI Prompt Architecture

Use multiple prompt layers.

```text
System Prompt
   +
Glitch Personality
   +
Current Emotional State
   +
Conversation Context
   +
Current Environment
   +
User Message
```

Example environmental information:

```text
Current state: WALKING
Energy: 0.72
Happiness: 0.83
Time of day: evening
User interaction: clicked
```

Avoid sending unnecessary internal information.

---

# 21. Conversation Manager

## `core/ai/conversation.py`

Responsibilities:

- Maintain recent messages
- Limit context length
- Persist conversations
- Load previous conversation
- Trim old messages
- Optionally summarize old context

Example:

```text
Recent context
    20 messages

Older context
    ↓
summary

Long-term memory
    ↓
separate database entries
```

Do not continuously send the entire database to the model.

---

# 22. AI Streaming

Use streaming for user-facing responses.

Sequence:

```text
User message
     ↓
THINKING
     ↓
OpenAI streaming
     ↓
First token
     ↓
Speech bubble appears
     ↓
Text progressively updates
     ↓
TALKING
     ↓
Final response
     ↓
Reaction
     ↓
IDLE
```

This makes the pet feel much more responsive.

---

# 23. AI Failure Handling

The pet must gracefully handle:

```text
No API key
Network unavailable
Timeout
Rate limit
Server error
Invalid response
Cancelled request
```

Example:

```text
Thinking
   ↓
Timeout
   ↓
CONFUSED
   ↓
"I'm having trouble reaching my brain right now."
```

The application must never freeze because the AI request failed.

---

# 24. AI Worker Architecture

Never execute a blocking network operation on the Qt GUI thread.

Recommended architecture:

```text
Qt Main Thread
    │
    ├── Pet rendering
    ├── Animation
    ├── Input
    └── UI
          │
          ▼
     Async AI Layer
          │
          ▼
      OpenAI API
```

AI jobs should support:

- cancellation
- timeout
- response callbacks/events
- request IDs

If a newer request replaces an older request, the old request should be safely cancelled or ignored.

---

# 25. Chat Bubble

## `ui/chat_bubble.py`

The chat bubble should:

- Track the pet's screen position.
- Appear above or beside Glitch.
- Automatically resize.
- Support multiple lines.
- Support streaming text.
- Automatically disappear after inactivity.
- Reposition if it would leave the screen.
- Never prevent normal pet interaction.

Example:

```text
           ┌─────────────────────────┐
           │ Hey! What are you doing?│
           └────────────┬────────────┘
                        ↓
                      Glitch
```

For long discussions, allow opening the full chat UI.

---

# 26. User Interaction System

## `core/pet/interaction.py`

Support:

### Left click

Possible behavior:

```text
click
→ reaction
→ happiness increase
```

### Drag

```text
mouse down
→ DRAGGED

mouse move
→ pet follows cursor

mouse release
→ physics/drop
```

### Double click

Possible:

```text
open chat
```

### Right click

Potential contextual menu:

```text
Chat
Pause
Sleep
Settings
Hide
Exit
```

---

# 27. Click-Through Mode

Add a configurable mode where Glitch does not intercept mouse events.

UI:

```text
☑ Always on Top
☐ Click Through
```

When enabled:

```text
Glitch visible
     ↓
Mouse events pass through
     ↓
Applications underneath remain interactive
```

Provide a tray shortcut to toggle it quickly.

---

# 28. System Tray

## `ui/tray.py`

Tray menu:

```text
Glitch
──────────────
Chat
Pause Movement
Wake Up
──────────────
Always on Top     ✓
Click Through
Start with Windows
──────────────
Settings
──────────────
Hide Glitch
Exit
```

Tray should remain usable even when Glitch is hidden.

---

# 29. Settings Window

## `ui/settings_window.py`

Sections:

### General

```text
Pet Size
Movement Speed
Start with Windows
Always on Top
Click Through
```

### AI

```text
API Key
Model
Temperature/configuration if supported
Conversation memory
```

### Behavior

```text
Autonomous movement
Reaction frequency
Sleep behavior
Idle behavior
```

### Appearance

```text
Scale
Animation speed
```

### Advanced

```text
Logging
Debug mode
Reset configuration
Clear memory
```

---

# 30. API Key Storage

Do not store the API key directly in:

```text
config.json
```

Use Windows secure credential storage through an appropriate credential library.

Keep only non-sensitive preferences in:

```text
config.json
```

Example:

```json
{
  "pet_scale": 1.0,
  "movement_speed": 80,
  "always_on_top": true,
  "click_through": false,
  "start_with_windows": true
}
```

The API key lives separately in secure storage.

---

# 31. Configuration Manager

## `core/persistence/config.py`

Responsibilities:

- Load configuration
- Apply defaults
- Validate values
- Save configuration
- Handle malformed configuration
- Perform migrations

Use a versioned config structure:

```json
{
  "version": 1
}
```

Future versions can migrate automatically.

---

# 32. SQLite Persistence

Use SQLite for data that grows.

### Tables

```text
conversations
messages
memories
emotion_state
usage
```

Potential structure:

```text
messages
----------------
id
conversation_id
role
content
created_at
```

```text
memories
----------------
id
category
content
importance
created_at
updated_at
```

Do not store every transient pet position in SQLite.

---

# 33. Event Bus

## `core/events/bus.py`

Create an internal event system.

Examples:

```text
USER_CLICKED
USER_DOUBLE_CLICKED
USER_DRAG_STARTED
USER_DRAGGED
USER_DRAG_ENDED

AI_REQUEST_STARTED
AI_TOKEN_RECEIVED
AI_RESPONSE_RECEIVED
AI_REQUEST_FAILED

PET_STATE_CHANGED
ANIMATION_STARTED
ANIMATION_FINISHED

SCREEN_CONFIGURATION_CHANGED

PET_WENT_TO_SLEEP
PET_WOKE_UP
```

Components subscribe instead of directly depending on one another.

---

# 34. Performance Architecture

Target:

```text
Idle CPU: very low
Animation CPU: low
Memory: modest
No persistent GPU-heavy rendering
No continuous API activity
```

Important rules:

### Do

- Cache loaded sprites.
- Load assets once.
- Avoid unnecessary repaint calls.
- Pause expensive processing when hidden.
- Use event-driven AI.
- Use low-frequency behavioral decisions.
- Avoid unnecessary database writes.

### Don't

- Poll OpenAI.
- Run 60 AI/physics loops per second.
- Reopen image files every frame.
- Continuously rebuild widgets.
- Continuously write pet coordinates to disk.

---

# 35. Runtime Frequencies

Recommended starting targets:

```text
Rendering             Qt managed
Physics               ~30 Hz
Movement              ~30 Hz
Animation             8–24 FPS depending on asset
Behavior decisions    every 1–5 seconds
Emotion update        event driven
AI                    event driven
Database persistence  event driven / batched
```

Tune these after profiling.

---

# 36. Asset Pipeline

Use a consistent directory format:

```text
assets/
└── animations/
    ├── idle/
    │   ├── default.png
    │   └── blink.png
    │
    ├── walking/
    │   ├── left.png
    │   └── right.png
    │
    ├── thinking/
    │   └── thinking.png
    │
    ├── talking/
    │   └── talking.png
    │
    ├── sleeping/
    │   ├── sleep.png
    │   └── wake.png
    │
    └── reactions/
        ├── happy.png
        ├── amazed.png
        ├── sad.png
        ├── angry.png
        ├── confused.png
        └── surprised.png
```

Each animation should have metadata specifying:

```text
sprite sheet
frame count
frame dimensions
FPS
looping
priority
interruptibility
```

---

# 37. Sprite Validation Tool

Create:

```text
scripts/validate_assets.py
```

It should detect:

- Missing files
- Incorrect image dimensions
- Invalid frame counts
- Wrong frame sizes
- Unsupported formats
- Metadata mismatches

This prevents broken animations from reaching the runtime.

---

# 38. Desktop Roaming

Glitch should choose destinations using screen geometry rather than random raw coordinates.

Example:

```text
Current position
      ↓
Select valid destination
      ↓
Choose left/right direction
      ↓
Walk
      ↓
Decelerate
      ↓
Idle
      ↓
Choose next action
```

Possible destinations:

```text
left edge
right edge
screen center
random point
favorite location
monitor boundary
```

---

# 39. Monitor Switching

Later-stage feature:

```text
Glitch reaches monitor edge
        ↓
Check adjacent monitor
        ↓
If available:
    transition
Else:
    turn around
```

Do not implement complicated monitor traversal in the first MVP, but design `ScreenManager` so it can support it.

---

# 40. Sleeping System

Glitch should have a lightweight autonomous sleep cycle.

Example:

```text
Long inactivity
      ↓
Yawn
      ↓
Sit
      ↓
Sleep
```

User interaction:

```text
click
     ↓
wake
     ↓
stretch
     ↓
idle
```

Sleep should not disable AI or system-tray functionality.

---

# 41. Personality System

Create a configurable personality object:

```text
Name: Glitch

Traits:
    playful
    curious
    sarcastic
    friendly
    energetic

Tone:
    casual
    concise

Response style:
    short
    expressive
```

The AI prompt should derive personality behavior from this configuration.

Eventually support selectable personalities:

```text
Glitch Default
Cute
Sarcastic
Professional
Chaotic
Calm
```

---

# 42. Memory Architecture

Do not make every conversation message permanent memory.

Separate:

```text
Conversation history
```

from:

```text
Long-term memories
```

Example memory:

```text
User likes dark themes.
User is working on Glitch.
User prefers concise responses.
```

The memory system can later use an AI-based consolidation step.

For the first version, keep memory simple and explicit.

---

# 43. Usage Tracking

Track basic AI usage locally:

```text
timestamp
model
input tokens
output tokens
request duration
success/failure
```

This enables:

- Cost estimation
- Debugging
- Usage display
- Future model switching

Do not log sensitive prompts unnecessarily.

---

# 44. Logging

Create structured application logging.

Levels:

```text
DEBUG
INFO
WARNING
ERROR
CRITICAL
```

Example:

```text
[INFO] Glitch started
[INFO] Loaded 27 animations
[INFO] Screen configuration detected
[DEBUG] State changed WALKING → THINKING
[INFO] AI request started
[DEBUG] AI response completed
```

Debug logging should be disabled or reduced by default.

---

# 45. Error Boundaries

The application should isolate failure domains.

For example:

```text
AI fails
→ Pet continues running

Animation file fails
→ fallback animation

Database fails
→ runtime continues with temporary state

Settings file corrupt
→ defaults restored

Tray fails
→ pet remains running
```

No individual subsystem should be capable of killing the whole pet.

---

# 46. Application Lifecycle

Startup:

```text
Initialize
   ↓
Load configuration
   ↓
Load assets
   ↓
Detect monitors
   ↓
Start pet
   ↓
Start tray
   ↓
Start autonomous behavior
```

Shutdown:

```text
Stop AI requests
   ↓
Save state
   ↓
Save configuration
   ↓
Close DB
   ↓
Destroy tray
   ↓
Close Qt
```

---

# 47. MVP Scope

The first implementation should **not** attempt everything.

### Phase 1 — Desktop Pet Foundation

Implement:

```text
Transparent window
Sprite rendering
Idle animation
Walking animation
Mouse dragging
Screen boundaries
System tray
Configuration
```

### Phase 2 — Behavior

Implement:

```text
State machine
Physics
Autonomous movement
Idle decisions
Sleeping
Reactions
Emotion state
```

### Phase 3 — AI

Implement:

```text
OpenAI integration
Thinking state
Talking state
Streaming responses
Speech bubble
Conversation history
Secure API-key storage
```

### Phase 4 — Advanced

Implement:

```text
Long-term memory
Multiple monitors
Click-through
Sounds
Notifications
Personality presets
Usage tracking
Advanced behavior
```

---

# 48. Recommended Implementation Order

The safest implementation sequence is:

```text
1. Project bootstrap
2. Configuration
3. Screen manager
4. Transparent PetWindow
5. Sprite loader
6. Animation controller
7. Idle animation
8. Walking movement
9. State machine
10. Physics
11. Drag interaction
12. Behavior engine
13. System tray
14. Settings UI
15. Event bus
16. AI brain
17. Conversation manager
18. Streaming chat
19. Chat bubble
20. Emotion system
21. SQLite persistence
22. Memory
23. Multi-monitor support
24. Click-through
25. Performance profiling
26. Packaging
```

This order ensures that Glitch becomes a functioning desktop pet before AI complexity is introduced.

---

# 49. Testing Strategy

## Unit tests

Test:

```text
State transitions
Physics calculations
Screen boundaries
Animation frame selection
Configuration loading
Configuration migration
AI response parsing
Emotion calculation
Database operations
```

## Integration tests

Test:

```text
Pet + animation
Pet + state machine
AI + conversation manager
AI + event bus
Tray + configuration
Screen manager + pet movement
```

## Manual tests

Verify:

```text
Start application
Drag pet
Release pet
Walk across screen
Reach screen edge
Open tray
Open settings
Change scale
Change movement speed
Enable/disable always-on-top
Enable click-through
Send AI message
Observe thinking animation
Observe streamed response
Observe talking animation
Disconnect internet
Recover gracefully
Close application
Restart application
```

---

# 50. Performance Testing

Measure:

```text
CPU usage while idle
CPU while walking
RAM at startup
RAM after 1 hour
Animation CPU
AI request latency
Database growth
Startup time
Shutdown time
```

Test for memory leaks by leaving Glitch running for several hours.

The application should be capable of behaving like a background utility rather than a foreground application consuming significant resources.

---

# 51. Packaging

For Windows distribution, package the application as a standalone executable.

Recommended initial route:

```text
PyInstaller
```

Build:

```text
Glitch.exe
```

Include:

```text
Python runtime
PySide6
assets
configuration defaults
required libraries
```

Do not package user-specific:

```text
config.json
glitch.db
API credentials
```

inside the executable.

Those should be created in the appropriate user application-data directory on first launch.

---

# 52. First-Launch Experience

On first launch:

```text
Glitch starts
   ↓
Default animation loaded
   ↓
Welcome reaction
   ↓
Tray icon appears
   ↓
Optional onboarding/settings panel
```

Possible onboarding:

```text
Meet Glitch.

Your new desktop companion.

[Configure AI]
[Skip for now]
```

AI should remain optional.

---

# 53. Security Requirements

Never:

```text
Hardcode API keys
Log API keys
Write API keys to normal logs
Send unnecessary user data
Store sensitive information without purpose
```

AI requests should only include the context necessary for the response.

---

# 54. Future-Proof Features

The architecture should leave extension points for:

```text
Voice input
Text-to-speech
Sound effects
Windows notifications
Calendar awareness
Application awareness
Desktop events
Local LLM support
Multiple AI providers
Custom pets
Custom sprite packs
Pet marketplace
Multiple pets
Plugin system
```

However, these should not be part of MVP.

---

# 55. Final Component Responsibility Map

```text
Application
    │
    ├── ConfigManager
    ├── Database
    ├── EventBus
    ├── ScreenManager
    ├── AnimationRegistry
    ├── AI Brain
    └── PetController

PetController
    │
    ├── StateMachine
    ├── BehaviorController
    ├── PhysicsController
    └── InteractionController

AnimationController
    │
    └── SpriteLoader

AI Brain
    │
    ├── ConversationManager
    ├── PromptBuilder
    └── EmotionProcessor

UI
    │
    ├── PetWindow
    ├── ChatBubble
    ├── SettingsWindow
    └── Tray
```

---

# 56. Core Runtime Loop

Conceptually:

```text
┌───────────────────────────────┐
│          Glitch Runtime       │
└───────────────┬───────────────┘
                │
                ▼
        Receive Events
                │
                ▼
        Update State Machine
                │
                ▼
        Update Behavior
                │
                ▼
          Update Physics
                │
                ▼
       Select/Update Animation
                │
                ▼
            Render
                │
                └───────────────┐
                                │
                                ▼
                         Wait for next
                           update/event
```

AI runs independently:

```text
User Message
     ↓
AI Brain
     ↓
OpenAI
     ↓
Structured Response
     ↓
EventBus
     ↓
Glitch State / Emotion
     ↓
Animation + Speech Bubble
```

---

# 57. Definition of Done for Version 1

Version 1 should be considered complete when:

```text
[ ] Glitch launches as a transparent desktop pet
[ ] Glitch renders sprite-sheet animations correctly
[ ] Glitch can idle and walk
[ ] Glitch can move within screen boundaries
[ ] Glitch can be dragged
[ ] Glitch has basic gravity/drop behavior
[ ] Glitch has autonomous behavior
[ ] Glitch can sleep/wake
[ ] Glitch supports reactions
[ ] Glitch has a state machine
[ ] Glitch uses an event bus
[ ] Glitch has a system tray
[ ] Glitch has a settings window
[ ] Settings persist between launches
[ ] API credentials are stored securely
[ ] OpenAI calls are asynchronous
[ ] AI requests never freeze the GUI
[ ] Thinking state works
[ ] Streaming response works
[ ] Talking animation works
[ ] Speech bubble follows Glitch
[ ] Conversation history persists
[ ] AI failures are handled gracefully
[ ] Multi-monitor architecture is supported
[ ] Click-through mode exists
[ ] Application survives long-running sessions
[ ] Basic automated tests pass
[ ] Windows executable can be generated
```

# 58. Recommended Initial Dependencies

```text
PySide6
openai
keyring
platformdirs
pydantic
Pillow
pytest
```

`python-dotenv` can be included for development environments but should not be required for production credential storage.

---

# 59. Final Architecture Recommendation

The final architecture should be centered around four independent layers:

```text
                ┌───────────────────┐
                │       UI          │
                │ Pet / Chat / Tray │
                └─────────┬─────────┘
                          │
                ┌─────────▼─────────┐
                │    PET ENGINE     │
                │                  │
                │ State             │
                │ Behavior          │
                │ Physics           │
                │ Interaction       │
                └─────────┬─────────┘
                          │
                ┌─────────▼─────────┐
                │ ANIMATION ENGINE  │
                │ Sprite Registry   │
                │ Frame Playback    │
                └───────────────────┘

                          ▲
                          │
                ┌─────────┴─────────┐
                │     AI ENGINE     │
                │ Brain             │
                │ Conversation      │
                │ Emotion           │
                │ Memory            │
                └─────────┬─────────┘
                          │
                          ▼
                     OpenAI API
```

The most important architectural rule is:

**The Pet Engine must never depend on the AI Engine to remain functional.**

That gives Glitch the characteristics of a real desktop creature: it continues existing, moving, reacting, sleeping, and behaving even when there is no network connection, while the AI adds intelligence whenever it is available.

The result is a much stronger foundation for the eventual Glitch experience than a simple `PetWindow + Animation + OpenAI` implementation.