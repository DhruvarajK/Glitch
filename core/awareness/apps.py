"""Process names to the handful of categories Glitch actually reacts to.

Only the executable name is ever consulted. An unknown process maps to None
and is ignored, which keeps the pet quiet about everything it does not
recognise rather than guessing.
"""
from __future__ import annotations

APP_CATEGORIES: dict[str, str] = {
    # Editors and IDEs
    "code.exe": "coding",
    "code - insiders.exe": "coding",
    "cursor.exe": "coding",
    "devenv.exe": "coding",
    "pycharm64.exe": "coding",
    "idea64.exe": "coding",
    "webstorm64.exe": "coding",
    "rider64.exe": "coding",
    "clion64.exe": "coding",
    "goland64.exe": "coding",
    "sublime_text.exe": "coding",
    "atom.exe": "coding",
    "zed.exe": "coding",
    # Terminals
    "windowsterminal.exe": "terminal",
    "wt.exe": "terminal",
    "powershell.exe": "terminal",
    "pwsh.exe": "terminal",
    "cmd.exe": "terminal",
    "alacritty.exe": "terminal",
    "mintty.exe": "terminal",
    "git-bash.exe": "terminal",
    "conemu64.exe": "terminal",
    "wezterm-gui.exe": "terminal",
    # Browsers
    "chrome.exe": "browser",
    "msedge.exe": "browser",
    "firefox.exe": "browser",
    "brave.exe": "browser",
    "opera.exe": "browser",
    "arc.exe": "browser",
    "vivaldi.exe": "browser",
    # Music
    "spotify.exe": "music",
    "itunes.exe": "music",
    "musicbee.exe": "music",
    "foobar2000.exe": "music",
    "aimp.exe": "music",
    "deezer.exe": "music",
    # Games and launchers
    "steam.exe": "gaming",
    "epicgameslauncher.exe": "gaming",
    "battle.net.exe": "gaming",
    "riotclientservices.exe": "gaming",
    "goggalaxy.exe": "gaming",
    "eadesktop.exe": "gaming",
    "ubisoftconnect.exe": "gaming",
    # Calls
    "zoom.exe": "meeting",
    "teams.exe": "meeting",
    "ms-teams.exe": "meeting",
    "webex.exe": "meeting",
    "gotomeeting.exe": "meeting",
    # Chat
    "discord.exe": "chat",
    "slack.exe": "chat",
    "telegram.exe": "chat",
    "whatsapp.exe": "chat",
    "signal.exe": "chat",
    # Design and media production
    "photoshop.exe": "design",
    "illustrator.exe": "design",
    "figma.exe": "design",
    "blender.exe": "design",
    "afterfx.exe": "design",
    "adobe premiere pro.exe": "design",
    "resolve.exe": "design",
    "gimp-2.10.exe": "design",
    "krita.exe": "design",
    # Writing and notes
    "winword.exe": "writing",
    "notion.exe": "writing",
    "obsidian.exe": "writing",
    "notepad.exe": "writing",
    "notepad++.exe": "writing",
    "typora.exe": "writing",
    # Documents and spreadsheets
    "excel.exe": "office",
    "powerpnt.exe": "office",
    "onenote.exe": "office",
    "acrobat.exe": "office",
    "acrord32.exe": "office",
    # Video
    "vlc.exe": "video",
    "mpc-hc64.exe": "video",
    "potplayermini64.exe": "video",
    "netflix.exe": "video",
    "obs64.exe": "video",
}

# How a category is described to the model and in canned lines.
CATEGORY_LABELS: dict[str, str] = {
    "coding": "a code editor",
    "terminal": "a terminal",
    "browser": "a web browser",
    "music": "a music player",
    "gaming": "a game launcher",
    "meeting": "a video call app",
    "chat": "a chat app",
    "design": "a design or video editing app",
    "writing": "a writing app",
    "office": "a document or spreadsheet app",
    "video": "a video player",
}

# Categories where an unprompted interruption would be genuinely unwelcome.
QUIET_CATEGORIES = frozenset({"meeting", "gaming", "video"})


def categorise(process: str | None) -> str | None:
    """The category for an executable name, or None when unrecognised."""
    if not process:
        return None
    return APP_CATEGORIES.get(process.strip().lower())


def label_for(category: str | None) -> str:
    return CATEGORY_LABELS.get(category or "", "an app")


def is_quiet(category: str | None) -> bool:
    """True when the foreground app means Glitch should keep to itself."""
    return category in QUIET_CATEGORIES
