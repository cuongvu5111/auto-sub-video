"""Runtime checks for the frozen Windows distribution."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from typing import Optional

from config import Config
from core.audio_extractor import find_ffmpeg
from core.audio_mixer import generate_ass_file, render_final_video
from core.media_probe import probe_media
from core.process import run_process


def _assert_writable(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(prefix="runtime_check_", dir=directory, delete=True):
        pass


def run_runtime_self_check(
    input_video: str | Path,
    expected_llm_model: Optional[str] = None,
) -> dict:
    """Verify frozen config, PyAV, FFmpeg, subtitle rendering, and writable app paths."""
    if not getattr(sys, "frozen", False):
        raise RuntimeError("Runtime self-check must be run from the frozen application.")

    input_info = probe_media(input_video)
    ffmpeg_path = Path(find_ffmpeg()).resolve()
    version = run_process(
        [str(ffmpeg_path), "-version"], timeout=15.0, check=True, capture_stdout=True
    )
    version_line = version.stdout.splitlines()[0] if version.stdout else "FFmpeg available"
    _assert_writable(Config.TEMP_DIR)
    _assert_writable(Config.OUTPUT_DIR)

    if expected_llm_model is not None and Config.LLM_MODEL != expected_llm_model:
        raise RuntimeError("The .env model setting was not loaded from the application directory.")

    with tempfile.TemporaryDirectory(prefix="runtime_render_check_", dir=Config.TEMP_DIR) as tmp:
        work_dir = Path(tmp)
        source_fixture = work_dir / "subtitle_fixture.mp4"
        ass_path = work_dir / "subtitle_fixture.ass"
        output_fixture = work_dir / "subtitle_rendered.mp4"
        run_process(
            [
                str(ffmpeg_path), "-y", "-v", "error",
                "-f", "lavfi", "-i", "color=c=black:s=320x240:r=25:d=1",
                "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:duration=1",
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
                str(source_fixture),
            ],
            timeout=30.0,
            check=True,
        )
        generate_ass_file(
            [{"index": 0, "start": 0.0, "end": 0.9, "translated_text": "Frozen Subtitle Font Check"}],
            ass_path,
            font_name="Arial",
            font_size=32,
            total_duration=1.0,
        )
        render_final_video(
            source_fixture,
            None,
            output_fixture,
            ass_subtitle_path=ass_path,
            encoder="libx264",
        )
        rendered_info = probe_media(output_fixture)

        import av

        bright_pixels = 0
        with av.open(str(output_fixture)) as container:
            video_stream = next(stream for stream in container.streams if stream.type == "video")
            for frame in container.decode(video_stream):
                timestamp = float(frame.pts * frame.time_base) if frame.pts is not None else 0.0
                if 0.2 <= timestamp <= 0.8:
                    pixels = frame.to_ndarray(format="rgb24")
                    bright_pixels = max(bright_pixels, int((pixels.max(axis=2) >= 220).sum()))
                    if bright_pixels:
                        break
        if bright_pixels < 10:
            raise RuntimeError("Subtitle render completed but no visible subtitle pixels were detected.")

    return {
        "status": "passed",
        "frozen": True,
        "config_base_dir": str(Config.BASE_DIR),
        "env_model_match": expected_llm_model is None or Config.LLM_MODEL == expected_llm_model,
        "ffmpeg_path": str(ffmpeg_path),
        "ffmpeg_version": version_line,
        "input_video_codec": input_info.video_codec,
        "input_video_duration_seconds": input_info.duration,
        "input_audio_present": input_info.has_audio,
        "pyav_probe": "passed",
        "subtitle_render": "passed",
        "subtitle_bright_pixels": bright_pixels,
        "rendered_fixture_video_codec": rendered_info.video_codec,
        "rendered_fixture_audio_present": rendered_info.has_audio,
        "writable_temp_and_output_dirs": True,
    }
