"""Application-wide constants and filesystem locations."""
from __future__ import annotations

import sys
from pathlib import Path

from platformdirs import user_data_dir, user_log_dir

APP_NAME = "Glitch"
APP_ORG = "GlitchPet"
APP_VERSION = "0.1.0"

def _root_dir() -> Path:
    """Where the bundled assets live.

    In a PyInstaller build the data files are unpacked next to the bootloader
    rather than beside this module, so the frozen case is resolved separately.
    """
    bundle = getattr(sys, "_MEIPASS", None)
    if bundle is not None:
        return Path(bundle)
    return Path(__file__).resolve().parents[2]


ROOT_DIR = _root_dir()
ASSETS_DIR = ROOT_DIR / "assets"
ANIMATIONS_DIR = ASSETS_DIR / "animations"
ICONS_DIR = ASSETS_DIR / "icons"
SOUNDS_DIR = ASSETS_DIR / "sounds"
ANIMATION_MANIFEST = ANIMATIONS_DIR / "animations.json"

# User-writable locations. Never bundled into the executable.
DATA_DIR = Path(user_data_dir(APP_NAME, APP_ORG, roaming=True))
LOG_DIR = Path(user_log_dir(APP_NAME, APP_ORG))
CONFIG_PATH = DATA_DIR / "config.json"
DATABASE_PATH = DATA_DIR / "glitch.db"

# Secure credential storage.
KEYRING_SERVICE = "GlitchDesktopPet"
KEYRING_USERNAME = "openai_api_key"

# Runtime frequencies (Hz).
PHYSICS_HZ = 30
ANIMATION_HZ = 60  # ticker resolution; each clip advances at its own fps

# Base on-screen height of the pet at scale 1.0, in logical pixels.
BASE_PET_HEIGHT = 190
