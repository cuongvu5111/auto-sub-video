"""Read source media metadata and validate streams before pipeline work starts."""

from dataclasses import dataclass
import math
from pathlib import Path
from typing import Optional


class MediaProbeError(Exception):
    """Raised when an input file cannot be inspected or is not usable video."""


@dataclass(frozen=True)
class MediaInfo:
    path: Path
    duration: float
    audio_duration: Optional[float]
    has_video: bool
    has_audio: bool
    width: Optional[int]
    height: Optional[int]
    frame_rate: Optional[float]
    video_codec: Optional[str]
    audio_codec: Optional[str]
    container_format: Optional[str]


def _stream_duration(stream) -> Optional[float]:
    try:
        if stream.duration is not None and stream.time_base is not None:
            duration = float(stream.duration * stream.time_base)
            if duration > 0:
                return duration
    except (AttributeError, TypeError, ValueError, ZeroDivisionError):
        pass

    try:
        if stream.frames and stream.average_rate:
            duration = float(stream.frames / stream.average_rate)
            if duration > 0:
                return duration
    except (AttributeError, TypeError, ValueError, ZeroDivisionError):
        pass
    return None


def probe_media(media_path: str | Path) -> MediaInfo:
    """Inspect a video with PyAV, which is already a project dependency."""
    path = Path(media_path).expanduser().resolve()
    if not path.is_file():
        raise MediaProbeError(f"Video file does not exist: {path}")

    try:
        import av
    except ImportError as exc:
        raise MediaProbeError("PyAV is required to inspect media. Reinstall project dependencies.") from exc

    try:
        with av.open(str(path)) as container:
            video = next((stream for stream in container.streams if stream.type == "video"), None)
            audio = next((stream for stream in container.streams if stream.type == "audio"), None)
            if video is None:
                raise MediaProbeError(f"No video stream was found in: {path.name}")

            duration = _stream_duration(video)
            if duration is None and container.duration is not None:
                duration = float(container.duration / av.time_base)
            if duration is None or not math.isfinite(duration) or duration <= 0:
                raise MediaProbeError(f"Could not determine a positive video duration for: {path.name}")

            try:
                frame_rate = float(video.average_rate) if video.average_rate else None
            except (TypeError, ValueError, ZeroDivisionError):
                frame_rate = None

            try:
                container_format = container.format.name if container.format else None
            except AttributeError:
                container_format = None

            return MediaInfo(
                path=path,
                duration=duration,
                audio_duration=_stream_duration(audio) if audio else None,
                has_video=True,
                has_audio=audio is not None,
                width=getattr(video, "width", None),
                height=getattr(video, "height", None),
                frame_rate=frame_rate,
                video_codec=getattr(video.codec_context, "name", None),
                audio_codec=getattr(audio.codec_context, "name", None) if audio else None,
                container_format=container_format,
            )
    except MediaProbeError:
        raise
    except Exception as exc:
        raise MediaProbeError(f"Could not read video metadata for {path.name}: {exc}") from exc


def validate_video_input(media_path: str | Path, *, require_audio: bool = True) -> MediaInfo:
    """Validate that an input has a video stream and any required audio stream."""
    info = probe_media(media_path)
    if require_audio and not info.has_audio:
        raise MediaProbeError(
            f"No audio stream was found in {info.path.name}. Speech transcription requires audio; "
            "attach a timed SRT file or select a video with audio."
        )
    return info
