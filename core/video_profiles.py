"""Validated output geometry profiles for social-video exports."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional


@dataclass(frozen=True)
class VideoExportProfile:
    name: str
    width: Optional[int] = None
    height: Optional[int] = None
    fit_mode: str = "crop"

    @property
    def transforms_video(self) -> bool:
        return self.width is not None and self.height is not None


def resolve_video_export_profile(value: Optional[Mapping[str, Any]]) -> VideoExportProfile:
    """Resolve user-facing profile data and reject unsafe or ambiguous geometry."""
    if not value or str(value.get("name", "original")).strip().lower() == "original":
        return VideoExportProfile("original")

    name = str(value.get("name", "")).strip().lower()
    if name not in {"tiktok_9_16", "portrait_9_16"}:
        raise ValueError(f"Unsupported video export profile: {name or '(empty)'}")

    try:
        width = int(value.get("width", 1080))
        height = int(value.get("height", 1920))
    except (TypeError, ValueError) as exc:
        raise ValueError("Export profile dimensions must be integers.") from exc
    if width < 180 or height < 320 or width > 4320 or height > 7680:
        raise ValueError("Export profile dimensions must be within 180x320 and 4320x7680.")
    if width % 2 or height % 2:
        raise ValueError("Export profile dimensions must be even for H.264 encoding.")
    if abs((width / height) - (9 / 16)) > 0.002:
        raise ValueError("TikTok portrait profile dimensions must use a 9:16 aspect ratio.")

    fit_mode = str(value.get("fit_mode", "crop")).strip().lower()
    if fit_mode not in {"crop", "contain"}:
        raise ValueError("Portrait fit mode must be 'crop' or 'contain'.")
    return VideoExportProfile(name, width, height, fit_mode)


def ass_play_resolution(width: int, height: int, reference_height: int = 1280) -> tuple[int, int]:
    """Return an aspect-matched ASS canvas with a stable reference height."""
    if width <= 0 or height <= 0 or reference_height <= 0:
        raise ValueError("Video dimensions and ASS reference height must be positive.")
    if height >= width:
        return max(1, round(reference_height * width / height)), reference_height
    return reference_height, max(1, round(reference_height * height / width))
