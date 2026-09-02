# PyInstaller build spec for Glitch.
#
#   pyinstaller glitch.spec
#
# Produces dist/Glitch.exe with the assets bundled. User data (config.json,
# glitch.db, the API key) is never packaged: it is created in the user's
# application-data directory on first launch.
from pathlib import Path

ROOT = Path(SPECPATH)

block_cipher = None

a = Analysis(
    ["main.py"],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        (str(ROOT / "assets" / "animations"), "assets/animations"),
        (str(ROOT / "assets" / "icons"), "assets/icons"),
        (str(ROOT / "assets" / "sounds"), "assets/sounds"),
    ],
    hiddenimports=[
        # QSoundEffect is imported lazily so the cues keep working headless.
        "PySide6.QtMultimedia",
        # keyring resolves its Windows backend at runtime.
        "keyring.backends.Windows",
        # The awareness sensors import these lazily.
        "win32api",
        "win32con",
        "win32gui",
        "win32process",
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "PySide6.QtWebEngineCore",
        "PySide6.QtWebEngineWidgets",
        "PySide6.Qt3DCore",
        "PySide6.QtCharts",
        "PySide6.QtDataVisualization",
        "PySide6.QtQuick",
        "PySide6.QtQml",
    ],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="Glitch",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=False,  # no console window for a tray application
    icon=str(ROOT / "assets" / "icons" / "glitch.ico")
    if (ROOT / "assets" / "icons" / "glitch.ico").exists()
    else None,
)
