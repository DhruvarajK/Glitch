"""Decodes Aseprite-style sprite sheets into display-sized frames.

The source sheets are very large (2048x2048 per frame). Frames are decoded
straight to their on-screen size with QImageReader.setScaledSize so the full
resolution sheet never has to exist in memory.
"""
from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import QImage, QImageReader, QPixmap, QTransform

from core.animation.animation_data import LoadedClip
from core.utils.logger import get_logger

log = get_logger("sprites")


class SpriteLoadError(RuntimeError):
    pass


def _read_metadata(json_path: Path) -> tuple[list[dict], list[float]]:
    data = json.loads(json_path.read_text(encoding="utf-8"))
    frames = data.get("frames")
    if isinstance(frames, dict):  # hash form; order by declaration
        frames = list(frames.values())
    if not frames:
        raise SpriteLoadError(f"{json_path.name} contains no frames")
    rects = [f["frame"] for f in frames]
    durations = [max(float(f.get("duration", 83)), 1.0) / 1000.0 for f in frames]
    return rects, durations


def _is_uniform_row(rects: list[dict]) -> bool:
    """True when frames are equal-sized and laid out left-to-right in one row."""
    w, h = rects[0]["w"], rects[0]["h"]
    return all(
        r["w"] == w and r["h"] == h and r["y"] == 0 and r["x"] == i * w
        for i, r in enumerate(rects)
    )


def load_clip(
    clip_dir: Path, name: str, target_height: int, mirrored: bool = False
) -> LoadedClip:
    """Load `name`'s sheet from `clip_dir`, scaled so each frame is target_height tall."""
    sheets = sorted(clip_dir.glob("*.png"))
    metas = sorted(clip_dir.glob("*.json"))
    if not sheets or not metas:
        raise SpriteLoadError(f"No sprite sheet/metadata pair in {clip_dir}")

    rects, durations = _read_metadata(metas[0])
    frame_w, frame_h = rects[0]["w"], rects[0]["h"]
    target_height = max(8, int(target_height))
    target_width = max(8, round(frame_w * target_height / frame_h))

    reader = QImageReader(str(sheets[0]))
    reader.setAutoTransform(True)

    if _is_uniform_row(rects):
        # Fast path: let the decoder downscale the whole strip on the way in.
        reader.setScaledSize(QSize(target_width * len(rects), target_height))
        sheet = reader.read()
        if sheet.isNull():
            raise SpriteLoadError(f"Could not decode {sheets[0].name}: {reader.errorString()}")
        images = [
            sheet.copy(QRect(i * target_width, 0, target_width, target_height))
            for i in range(len(rects))
        ]
    else:
        sheet = reader.read()
        if sheet.isNull():
            raise SpriteLoadError(f"Could not decode {sheets[0].name}: {reader.errorString()}")
        images = []
        for rect in rects:
            crop = sheet.copy(QRect(rect["x"], rect["y"], rect["w"], rect["h"]))
            images.append(
                crop.scaled(
                    target_width,
                    target_height,
                    Qt.IgnoreAspectRatio,
                    Qt.SmoothTransformation,
                )
            )

    frames = [QPixmap.fromImage(img) for img in images]
    flipped: list[QPixmap] = []
    if mirrored:
        transform = QTransform().scale(-1, 1)
        flipped = [p.transformed(transform, Qt.SmoothTransformation) for p in frames]

    log.debug("Loaded clip %s: %d frames at %dx%d", name, len(frames), target_width, target_height)
    return LoadedClip(
        name=name,
        frames=frames,
        durations=durations,
        width=target_width,
        height=target_height,
        flipped=flipped,
    )


def probe_clip(clip_dir: Path) -> dict:
    """Cheap metadata-only inspection, used by the asset validator."""
    sheets = sorted(clip_dir.glob("*.png"))
    metas = sorted(clip_dir.glob("*.json"))
    if not sheets or not metas:
        raise SpriteLoadError(f"No sprite sheet/metadata pair in {clip_dir}")
    rects, durations = _read_metadata(metas[0])
    reader = QImageReader(str(sheets[0]))
    size = reader.size()
    return {
        "sheet": sheets[0],
        "metadata": metas[0],
        "frames": len(rects),
        "frame_size": (rects[0]["w"], rects[0]["h"]),
        "sheet_size": (size.width(), size.height()),
        "durations": durations,
        "uniform_row": _is_uniform_row(rects),
        "rects": rects,
    }
