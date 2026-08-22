"""Validate the animation manifest against the sprite sheets on disk.

Run before shipping or after adding animations:

    python scripts/validate_assets.py

Exits non-zero when any animation would fail to load at runtime.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QGuiApplication  # noqa: E402

from core.animation.sprite_loader import SpriteLoadError, probe_clip  # noqa: E402
from core.utils.constants import ANIMATION_MANIFEST, ANIMATIONS_DIR  # noqa: E402

SUPPORTED_SUFFIXES = {".png"}


def validate() -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    try:
        manifest = json.loads(ANIMATION_MANIFEST.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"manifest: unreadable ({exc})"], []

    animations = manifest.get("animations", {})
    if not animations:
        return ["manifest: no animations declared"], []

    fallback = manifest.get("fallback", "idle")
    if fallback not in animations:
        errors.append(f"manifest: fallback {fallback!r} is not a declared animation")

    referenced = {entry["clip"] for entry in animations.values() if "clip" in entry}

    for name, entry in sorted(animations.items()):
        clip = entry.get("clip")
        if not clip:
            errors.append(f"{name}: no clip declared")
            continue
        clip_dir = ANIMATIONS_DIR / clip
        if not clip_dir.is_dir():
            errors.append(f"{name}: clip directory missing ({clip_dir})")
            continue
        try:
            info = probe_clip(clip_dir)
        except (SpriteLoadError, OSError, KeyError, ValueError) as exc:
            errors.append(f"{name}: {exc}")
            continue

        if info["sheet"].suffix.lower() not in SUPPORTED_SUFFIXES:
            errors.append(f"{name}: unsupported sheet format {info['sheet'].suffix}")
        if info["frames"] < 1:
            errors.append(f"{name}: zero frames")

        sheet_w, sheet_h = info["sheet_size"]
        if sheet_w <= 0 or sheet_h <= 0:
            errors.append(f"{name}: sheet {info['sheet'].name} has no readable size")
        else:
            for index, rect in enumerate(info["rects"]):
                if rect["x"] + rect["w"] > sheet_w or rect["y"] + rect["h"] > sheet_h:
                    errors.append(
                        f"{name}: frame {index} ({rect}) falls outside "
                        f"the {sheet_w}x{sheet_h} sheet"
                    )
                    break

        if not info["uniform_row"]:
            warnings.append(
                f"{name}: frames are not a uniform single row; "
                "loading will use the slower scaling path"
            )

        fps = entry.get("fps")
        if fps is not None and (not isinstance(fps, (int, float)) or fps <= 0):
            errors.append(f"{name}: invalid fps {fps!r}")
        follow_up = entry.get("next")
        if follow_up and follow_up not in animations:
            errors.append(f"{name}: next animation {follow_up!r} is not declared")

    for clip_dir in sorted(p for p in ANIMATIONS_DIR.iterdir() if p.is_dir()):
        if clip_dir.name not in referenced:
            warnings.append(f"{clip_dir.name}: clip on disk is not used by any animation")

    return errors, warnings


def main() -> int:
    QGuiApplication([])  # QImageReader needs a Qt application instance
    errors, warnings = validate()

    for warning in warnings:
        print(f"WARN  {warning}")
    for error in errors:
        print(f"ERROR {error}")

    if errors:
        print(f"\n{len(errors)} error(s), {len(warnings)} warning(s)")
        return 1
    print(f"\nAll animations valid ({len(warnings)} warning(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main())
