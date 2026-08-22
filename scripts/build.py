"""Build Glitch.exe.

    python scripts/build.py

Validates the assets first, because a broken manifest is much easier to fix
here than inside a packaged executable.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(command: list[str]) -> int:
    print("$", " ".join(command))
    return subprocess.call(command, cwd=ROOT)


def main() -> int:
    if run([sys.executable, "scripts/validate_assets.py"]) != 0:
        print("Asset validation failed; not building.")
        return 1

    if run([sys.executable, "-m", "pytest", "-q"]) != 0:
        print("Tests failed; not building.")
        return 1

    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("PyInstaller is not installed. Run: pip install pyinstaller")
        return 1

    code = run([sys.executable, "-m", "PyInstaller", "--noconfirm", "glitch.spec"])
    if code == 0:
        print(f"\nBuilt {ROOT / 'dist' / 'Glitch.exe'}")
    return code


if __name__ == "__main__":
    sys.exit(main())
