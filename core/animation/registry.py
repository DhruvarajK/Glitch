"""Central catalogue of animations, backed by the JSON manifest.

The registry owns metadata for every animation and lazily decodes sprite
sheets at the current display size, caching the result. A missing or broken
clip degrades to the fallback animation instead of crashing the runtime.
"""
from __future__ import annotations

import json
from pathlib import Path

from core.animation.animation_data import AnimationSpec, LoadedClip
from core.animation.sprite_loader import SpriteLoadError, load_clip
from core.utils.constants import ANIMATION_MANIFEST, ANIMATIONS_DIR
from core.utils.logger import get_logger

log = get_logger("animations")


class AnimationRegistry:
    """Metadata lookup plus a size-aware sprite cache."""

    def __init__(
        self,
        manifest_path: Path | None = None,
        animations_dir: Path | None = None,
        target_height: int = 190,
    ) -> None:
        self.manifest_path = Path(manifest_path or ANIMATION_MANIFEST)
        self.animations_dir = Path(animations_dir or ANIMATIONS_DIR)
        self._target_height = max(8, int(target_height))
        self._specs: dict[str, AnimationSpec] = {}
        self._mirrored_clips: set[str] = set()
        self._cache: dict[str, LoadedClip] = {}
        self._broken: set[str] = set()
        self.fallback = "idle"
        self._load_manifest()

    # -------------------------------------------------------------- manifest
    def _load_manifest(self) -> None:
        try:
            data = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Animation manifest unreadable: {exc}") from exc

        self.fallback = data.get("fallback", "idle")
        self._mirrored_clips = set(data.get("mirrored_clips", []))

        for name, entry in data.get("animations", {}).items():
            self._specs[name] = AnimationSpec(
                name=name,
                clip=entry["clip"],
                fps=entry.get("fps"),
                loop=bool(entry.get("loop", True)),
                priority=int(entry.get("priority", 10)),
                interruptible=bool(entry.get("interruptible", entry.get("loop", True))),
                next_animation=entry.get("next"),
            )
        log.info("Registered %d animations from manifest", len(self._specs))

    # ---------------------------------------------------------------- specs
    def has(self, name: str) -> bool:
        return name in self._specs

    def spec(self, name: str) -> AnimationSpec:
        spec = self._specs.get(name)
        if spec is None:
            log.warning("Unknown animation %r; falling back to %r", name, self.fallback)
            spec = self._specs[self.fallback]
        return spec

    def names(self) -> list[str]:
        return sorted(self._specs)

    def clip_names(self) -> list[str]:
        return sorted({spec.clip for spec in self._specs.values()})

    # --------------------------------------------------------------- sprites
    @property
    def target_height(self) -> int:
        return self._target_height

    def set_target_height(self, height: int) -> None:
        """Change the display size; invalidates every decoded clip."""
        height = max(8, int(height))
        if height == self._target_height:
            return
        self._target_height = height
        self._cache.clear()
        self._broken.clear()
        log.info("Sprite target height set to %dpx; cache cleared", height)

    def clip(self, clip_name: str) -> LoadedClip:
        """Return decoded frames for a clip, loading it on first use."""
        cached = self._cache.get(clip_name)
        if cached is not None:
            return cached
        if clip_name in self._broken:
            return self._fallback_clip(clip_name)

        clip_dir = self.animations_dir / clip_name
        try:
            loaded = load_clip(
                clip_dir,
                clip_name,
                self._target_height,
                mirrored=clip_name in self._mirrored_clips,
            )
        except (SpriteLoadError, OSError, KeyError, ValueError) as exc:
            log.error("Failed to load clip %r: %s", clip_name, exc)
            self._broken.add(clip_name)
            return self._fallback_clip(clip_name)

        self._cache[clip_name] = loaded
        return loaded

    def _fallback_clip(self, failed: str) -> LoadedClip:
        fallback_clip = self.spec(self.fallback).clip
        if failed == fallback_clip:
            raise RuntimeError("Fallback animation is unavailable; cannot render")
        return self.clip(fallback_clip)

    def clip_for(self, animation: str) -> LoadedClip:
        return self.clip(self.spec(animation).clip)

    def preload(self, animations: list[str]) -> None:
        for name in animations:
            try:
                self.clip_for(name)
            except RuntimeError:
                raise
            except Exception:
                log.exception("Preload failed for %r", name)

    def clear_cache(self) -> None:
        self._cache.clear()
