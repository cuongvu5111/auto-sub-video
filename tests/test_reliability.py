"""Offline regression tests for pipeline reliability and SRT flows."""

import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir))
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except AttributeError:
        pass


def test_job_workspace_isolation_and_safe_cleanup():
    from core.job_workspace import cleanup_job_workspace, create_job_workspace

    first = create_job_workspace()
    second = create_job_workspace()
    try:
        assert first != second
        assert first.parent == second.parent
        (first / "artifact.tmp").write_text("first", encoding="utf-8")
        cleanup_job_workspace(first)
        assert not first.exists()
        assert second.exists()
        try:
            cleanup_job_workspace(root_dir)
            raise AssertionError("Cleanup accepted a path outside the jobs directory")
        except ValueError:
            pass
    finally:
        if first.exists():
            cleanup_job_workspace(first)
        if second.exists():
            cleanup_job_workspace(second)
    print("✓ test_job_workspace_isolation_and_safe_cleanup: PASSED")


def test_downloads_with_same_video_id_use_separate_job_paths():
    from types import ModuleType
    from core.downloader import download_video

    class FakeYoutubeDL:
        def __init__(self, options):
            self.options = options
            self.filename = None

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def extract_info(self, _url, download=True):
            self.filename = self.options["outtmpl"].replace("%(id)s", "same-id").replace("%(ext)s", "mp4")
            Path(self.filename).write_bytes(b"fixture-video")
            return {"id": "same-id", "ext": "mp4"}

        def prepare_filename(self, _info):
            return self.filename

    fake_yt_dlp = ModuleType("yt_dlp")
    fake_yt_dlp.YoutubeDL = FakeYoutubeDL
    with tempfile.TemporaryDirectory(prefix="same_id_", dir=str(root_dir / "temp")) as tmp:
        parent = Path(tmp)
        with patch.dict(sys.modules, {"yt_dlp": fake_yt_dlp}):
            first = download_video("https://example.test/video", output_dir=parent / "job-a")
            second = download_video("https://example.test/video", output_dir=parent / "job-b")
        assert first != second
        assert first.name == second.name == "same-id.mp4"
        assert first.read_bytes() == second.read_bytes() == b"fixture-video"
    print("✓ test_downloads_with_same_video_id_use_separate_job_paths: PASSED")


def test_download_url_hook_preserves_cancellation():
    from types import ModuleType
    from core.downloader import download_video

    class FakeYoutubeDL:
        def __init__(self, options):
            self.options = options

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def extract_info(self, _url, download=True):
            self.options["progress_hooks"][0]({"status": "downloading"})

    fake_yt_dlp = ModuleType("yt_dlp")
    fake_yt_dlp.YoutubeDL = FakeYoutubeDL
    with tempfile.TemporaryDirectory(prefix="download_cancel_", dir=str(root_dir / "temp")) as tmp:
        with patch.dict(sys.modules, {"yt_dlp": fake_yt_dlp}):
            try:
                download_video(
                    "https://example.test/video",
                    output_dir=Path(tmp),
                    cancel_check=lambda: True,
                )
                raise AssertionError("Expected URL download cancellation")
            except InterruptedError:
                pass
    print("✓ test_download_url_hook_preserves_cancellation: PASSED")


def test_llm_cancellation_happens_before_provider_request():
    import openai
    from unittest.mock import MagicMock
    from core.translator import translate_segments

    client = MagicMock()
    with patch.object(openai, "OpenAI", return_value=client):
        try:
            translate_segments(
                [{"index": 0, "start": 0.0, "end": 1.0, "text": "Hello"}],
                cancel_check=lambda: True,
            )
            raise AssertionError("Expected LLM translation cancellation")
        except InterruptedError:
            pass
    client.chat.completions.create.assert_not_called()
    print("✓ test_llm_cancellation_happens_before_provider_request: PASSED")


def test_tts_and_audio_mix_cancel_before_work():
    from core.tts_engine import process_dubbing_segments
    from core.audio_mixer import create_mixed_audio_track, render_final_video
    from unittest.mock import AsyncMock, patch

    with patch("core.tts_engine.synthesize_speech_async", new=AsyncMock()) as synthesize:
        try:
            process_dubbing_segments(
                [{"index": 0, "start": 0.0, "end": 1.0, "translated_text": "Hello"}],
                output_dir=root_dir / "temp" / "cancelled_tts",
                cancel_check=lambda: True,
            )
            raise AssertionError("Expected TTS cancellation")
        except InterruptedError:
            pass
        synthesize.assert_not_awaited()

    try:
        create_mixed_audio_track(
            None,
            [],
            root_dir / "temp" / "cancelled_mix.wav",
            total_duration=1.0,
            cancel_check=lambda: True,
        )
        raise AssertionError("Expected audio-mix cancellation")
    except InterruptedError:
        pass
    assert not (root_dir / "temp" / "cancelled_mix.wav").exists()

    source_video = root_dir / "output" / "video_test.mp4"
    if source_video.is_file():
        with tempfile.TemporaryDirectory(prefix="render_cancel_", dir=str(root_dir / "temp")) as tmp:
            destination = Path(tmp) / "cancelled.mp4"
            try:
                render_final_video(
                    source_video,
                    None,
                    destination,
                    encoder="libx264",
                    cancel_check=lambda: True,
                )
                raise AssertionError("Expected video-render cancellation")
            except InterruptedError:
                pass
            assert not destination.exists()
            assert not list(Path(tmp).glob("*.partial.mp4"))
    print("✓ test_tts_and_audio_mix_cancel_before_work: PASSED")


def test_packager_removes_host_icu_dlls_that_conflict_with_qt():
    from build_exe import remove_conflicting_icu_binaries

    with tempfile.TemporaryDirectory(prefix="package_icu_", dir=str(root_dir / "temp")) as tmp:
        package = Path(tmp)
        internal = package / "_internal"
        internal.mkdir()
        (package / "icuuc.dll").write_bytes(b"host ICU")
        (internal / "icudt78.dll").write_bytes(b"host ICU data")
        (internal / "ffmpeg.exe").write_bytes(b"application binary")

        removed = remove_conflicting_icu_binaries(package)
        assert set(removed) == {"icuuc.dll", "icudt78.dll"}
        assert not (package / "icuuc.dll").exists()
        assert not (internal / "icudt78.dll").exists()
        assert (internal / "ffmpeg.exe").exists()
    print("✓ test_packager_removes_host_icu_dlls_that_conflict_with_qt: PASSED")


def test_external_process_stops_on_cancellation():
    from core.process import run_process

    started = time.monotonic()
    try:
        run_process(
            [sys.executable, "-c", "import time; time.sleep(20)"],
            timeout=30,
            cancel_check=lambda: time.monotonic() - started >= 0.25,
        )
        raise AssertionError("Expected cancellation")
    except InterruptedError:
        assert time.monotonic() - started < 5
    print("✓ test_external_process_stops_on_cancellation: PASSED")


def test_hardware_capabilities_are_cached_and_can_be_refreshed():
    from types import SimpleNamespace
    from config import Config

    previous_cache = Config._HARDWARE_CAPABILITIES
    previous_bin_dir = Config.BIN_DIR
    try:
        with tempfile.TemporaryDirectory(prefix="hardware_probe_", dir=str(root_dir / "temp")) as tmp:
            Config.BIN_DIR = Path(tmp)
            (Config.BIN_DIR / "ffmpeg.exe").write_bytes(b"fake ffmpeg")
            Config._HARDWARE_CAPABILITIES = None

            with patch("config.subprocess.run", return_value=SimpleNamespace(returncode=1)) as probe:
                first = Config.detect_hardware_capabilities()
                second = Config.detect_hardware_capabilities()
                assert probe.call_count == 1
                assert first == second

                first["has_nvenc"] = not first["has_nvenc"]
                assert Config.detect_hardware_capabilities() == second

                Config.detect_hardware_capabilities(refresh=True)
                assert probe.call_count == 2
    finally:
        Config.BIN_DIR = previous_bin_dir
        Config._HARDWARE_CAPABILITIES = previous_cache

    print("✓ test_hardware_capabilities_are_cached_and_can_be_refreshed: PASSED")


def test_srt_parser_handles_utf8_and_rejects_invalid_timing():
    from core.subtitles import SubtitleFileError, parse_srt

    with tempfile.TemporaryDirectory(prefix="srt_parse_", dir=str(root_dir / "temp")) as tmp:
        valid = Path(tmp) / "valid.srt"
        valid.write_text(
            "1\n00:00:00,500 --> 00:00:02,000\nXin chào\nmọi người\n\n"
            "2\n00:00:02.000 --> 00:00:03.250\nTạm biệt\n",
            encoding="utf-8",
        )
        entries = parse_srt(valid)
        assert len(entries) == 2
        assert entries[0]["start"] == 0.5 and entries[0]["end"] == 2.0
        assert entries[0]["text"] == "Xin chào mọi người"
        assert entries[1]["end"] == 3.25

        invalid = Path(tmp) / "invalid.srt"
        invalid.write_text("1\n00:00:02,000 --> 00:00:01,000\nWrong\n", encoding="utf-8")
        try:
            parse_srt(invalid)
            raise AssertionError("Expected invalid SRT timing to be rejected")
        except SubtitleFileError as exc:
            assert "ends before it starts" in str(exc)

        out_of_order = Path(tmp) / "out_of_order.srt"
        out_of_order.write_text(
            "1\n00:00:02,000 --> 00:00:03,000\nLater\n\n"
            "2\n00:00:01,000 --> 00:00:01,500\nEarlier\n",
            encoding="utf-8",
        )
        try:
            parse_srt(out_of_order)
            raise AssertionError("Expected out-of-order SRT entries to be rejected")
        except SubtitleFileError as exc:
            assert "chronological order" in str(exc)

        invalid_clock = Path(tmp) / "invalid_clock.srt"
        invalid_clock.write_text(
            "1\n00:61:00,000 --> 00:61:01,000\nBad clock\n",
            encoding="utf-8",
        )
        try:
            parse_srt(invalid_clock)
            raise AssertionError("Expected invalid minute fields to be rejected")
        except SubtitleFileError as exc:
            assert "out-of-range timestamp fields" in str(exc)
    print("✓ test_srt_parser_handles_utf8_and_rejects_invalid_timing: PASSED")


def test_segment_timeline_is_clamped_and_dubbing_delay_tracks_captions():
    from pipeline import _normalize_segments, _shift_subtitle_segments

    warnings = []
    normalized = _normalize_segments(
        [
            {"index": 0, "start": 0.2, "end": 2.5, "text": "Translated"},
            {"index": 1, "start": 2.1, "end": 2.8, "text": "Beyond video"},
        ],
        2.0,
        warning_callback=lambda message, percent: warnings.append(message),
    )
    assert len(normalized) == 1 and normalized[0]["end"] == 2.0
    assert "clipped 1, removed 1" in warnings[0]

    shifted = _shift_subtitle_segments(
        [
            {"index": 0, "start": 0.2, "end": 1.2, "translation_status": "translated"},
            {"index": 1, "start": 0.2, "end": 1.2, "translation_status": "source_fallback"},
            {"index": 2, "start": 0.2, "end": 1.2, "translation_status": "translated", "tts_status": "failed_silence_fallback"},
        ],
        0.5,
        2.0,
    )
    assert shifted[0]["start"] == 0.7 and shifted[0]["end"] == 1.7
    assert shifted[1]["start"] == 0.2 and shifted[1]["end"] == 1.2
    assert shifted[2]["start"] == 0.2 and shifted[2]["end"] == 1.2
    print("✓ test_segment_timeline_is_clamped_and_dubbing_delay_tracks_captions: PASSED")


def test_pipeline_uses_attached_srt_without_whisper():
    from core.media_probe import MediaInfo
    import pipeline

    with tempfile.TemporaryDirectory(prefix="srt_pipeline_", dir=str(root_dir / "temp")) as tmp:
        folder = Path(tmp)
        video = folder / "source.mp4"
        srt = folder / "source.srt"
        video.write_bytes(b"fixture")
        srt.write_text("1\n00:00:00,000 --> 00:00:01,000\nHello\n", encoding="utf-8")
        media_info = MediaInfo(
            path=video, duration=1.0, audio_duration=None, has_video=True, has_audio=False,
            width=64, height=64, frame_rate=25.0, video_codec="h264", audio_codec=None,
            container_format="mov,mp4,m4a,3gp,3g2,mj2",
        )

        def translated(segments, **kwargs):
            return [{**segment, "translated_text": "Xin chào", "translation_status": "translated"} for segment in segments]

        output = folder / "output"
        output.mkdir()
        progress_messages = []
        with patch.object(pipeline, "download_video", return_value=video), \
             patch.object(pipeline, "validate_video_input", return_value=media_info), \
             patch.object(pipeline, "translate_segments", side_effect=translated), \
             patch.object(pipeline, "transcribe_audio", side_effect=AssertionError("Whisper should be skipped")), \
             patch.object(pipeline, "extract_audio", side_effect=AssertionError("Audio extraction should be skipped")), \
             patch.object(pipeline, "render_final_video", return_value=output / "result.mp4") as render:
            result = pipeline._run_pipeline(
                source=str(video),
                subtitle_path=srt,
                prefer_attached_subtitle=True,
                translate_srt_only=True,
                enable_dubbing=False,
                export_profile={"name": "tiktok_9_16", "width": 360, "height": 640, "fit_mode": "crop"},
                progress_callback=lambda message, percent: progress_messages.append(message),
                workspace_dir=folder / "work",
                output_dir=output,
            )
        assert result.name == "result.mp4"
        assert render.call_args.kwargs["ass_subtitle_path"] == folder / "work" / "subtitles.ass"
        assert render.call_args.kwargs["export_profile"]["name"] == "tiktok_9_16"
        ass_text = (folder / "work" / "subtitles.ass").read_text(encoding="utf-8")
        assert "PlayResX: 720" in ass_text and "PlayResY: 1280" in ass_text
        completion = next(message for message in progress_messages if message.startswith("Pipeline completed!"))
        assert "Stage timings:" in completion
        assert "SRT parsing=" in completion and "LLM translation=" in completion
        assert "video rendering=" in completion
    print("✓ test_pipeline_uses_attached_srt_without_whisper: PASSED")


def test_short_landscape_srt_clip_exports_portrait_without_audio():
    """Exercise a real short no-audio SRT pipeline through portrait rendering."""
    import subprocess
    from core.audio_extractor import find_ffmpeg
    from core.media_probe import probe_media
    import pipeline

    with tempfile.TemporaryDirectory(prefix="short_tiktok_srt_", dir=str(root_dir / "temp")) as tmp:
        folder = Path(tmp)
        video = folder / "short_landscape.mp4"
        srt = folder / "short.srt"
        output = folder / "output"
        output.mkdir()
        ffmpeg_bin = find_ffmpeg()
        creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        subprocess.run(
            [ffmpeg_bin, "-y", "-f", "lavfi", "-i", "color=c=navy:s=320x180:r=24:d=1.2",
             "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(video)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True, creationflags=creationflags,
        )
        srt.write_text("1\n00:00:00,100 --> 00:00:01,100\nHello short clip\n", encoding="utf-8")

        def translated(segments, **_kwargs):
            return [{**item, "translated_text": "Xin chào video ngắn", "translation_status": "translated"} for item in segments]

        progress_messages = []
        with patch.object(pipeline, "translate_segments", side_effect=translated):
            result = pipeline.run_pipeline(
                source=str(video),
                subtitle_path=srt,
                prefer_attached_subtitle=True,
                translate_srt_only=True,
                enable_dubbing=False,
                export_profile={"name": "tiktok_9_16", "width": 360, "height": 640, "fit_mode": "crop"},
                encoder="libx264",
                output_dir=output,
                progress_callback=lambda message, _percent: progress_messages.append(message),
            )
        info = probe_media(result)
        assert (info.width, info.height) == (360, 640)
        assert not info.has_audio
        assert abs(info.duration - 1.2) <= 0.15
        assert any("upscale source pixels" in message for message in progress_messages)
    print("✓ test_short_landscape_srt_clip_exports_portrait_without_audio: PASSED")


def test_pipeline_job_returns_typed_terminal_statuses():
    import pipeline
    from core.job_result import JobStatus

    output = root_dir / "output" / "typed_status_fixture.mp4"
    forwarded = []

    def completed(source, progress_callback=None, **kwargs):
        progress_callback("Pipeline completed", 100.0)
        return output

    with patch.object(pipeline, "run_pipeline", side_effect=completed):
        result = pipeline.run_pipeline_job("source.mp4", progress_callback=lambda m, p: forwarded.append(m))
    assert result.status == JobStatus.COMPLETED
    assert result.output_path == output
    assert result.warnings == () and result.error is None
    assert forwarded == ["Pipeline completed"]

    def completed_with_warning(source, progress_callback=None, **kwargs):
        progress_callback("⚠ Source fallback used", 95.0)
        return output

    with patch.object(pipeline, "run_pipeline", side_effect=completed_with_warning):
        result = pipeline.run_pipeline_job("source.mp4")
    assert result.status == JobStatus.COMPLETED_WITH_WARNINGS
    assert len(result.warnings) == 1

    with patch.object(pipeline, "run_pipeline", side_effect=RuntimeError("render failed")):
        result = pipeline.run_pipeline_job("source.mp4")
    assert result.status == JobStatus.FAILED and result.error == "render failed"

    with patch.object(pipeline, "run_pipeline", side_effect=InterruptedError("cancelled")):
        result = pipeline.run_pipeline_job("source.mp4")
    assert result.status == JobStatus.CANCELLED and result.error == "cancelled"
    print("✓ test_pipeline_job_returns_typed_terminal_statuses: PASSED")


def test_transcription_honors_cancellation_between_segments():
    from types import SimpleNamespace
    from core.transcriber import transcribe_audio

    with tempfile.TemporaryDirectory(prefix="transcribe_cancel_", dir=str(root_dir / "temp")) as tmp:
        audio = Path(tmp) / "audio.wav"
        audio.write_bytes(b"fixture")
        state = {"cancelled": False}

        class FakeModel:
            def transcribe(self, *args, **kwargs):
                return iter([
                    SimpleNamespace(start=0.0, end=0.5, text=" first", words=[]),
                    SimpleNamespace(start=0.5, end=1.0, text=" second", words=[]),
                ]), SimpleNamespace(language="en")

        def progress(message, percent):
            if message.startswith("Đã nhận diện:"):
                state["cancelled"] = True

        with patch("core.transcriber.get_whisper_model", return_value=FakeModel()):
            try:
                transcribe_audio(
                    audio,
                    progress_callback=progress,
                    cancel_check=lambda: state["cancelled"],
                )
                raise AssertionError("Expected transcription to stop after cancellation")
            except InterruptedError:
                pass
    print("✓ test_transcription_honors_cancellation_between_segments: PASSED")


def test_benchmark_parser_extracts_stage_and_recovery_metrics():
    from tools.benchmark_pipeline import PeakRssSampler, _parse_progress

    metrics = _parse_progress([
        "Nhận diện hoàn tất: 75 câu thoại.",
        "⚠️ LLM could not return a valid response for 8 dialogues; retrying as smaller batches.",
        "⚠️ 2 dialogue(s) kept in the source language because translation did not return a valid result.",
        "Translation completed: 75 dialogues ready for dubbing.",
        "Pipeline completed! Stage timings: media preflight=0.20s, LLM translation=566.53s, video rendering=49.80s",
    ])
    assert metrics["transcribed_segments"] == 75
    assert metrics["translated_segments"] == 75
    assert metrics["translation_fallback_segments"] == 2
    assert metrics["adaptive_translation_splits"] == 1
    assert metrics["stage_timings_seconds"] == {
        "media preflight": 0.20,
        "LLM translation": 566.53,
        "video rendering": 49.80,
    }
    with PeakRssSampler(interval_seconds=0.01) as sampler:
        time.sleep(0.03)
    assert sampler.peak_bytes > 0
    assert sampler.source == "Windows WorkingSetSize" if sys.platform == "win32" else sampler.source != "unavailable"
    print("✓ test_benchmark_parser_extracts_stage_and_recovery_metrics: PASSED")


if __name__ == "__main__":
    test_job_workspace_isolation_and_safe_cleanup()
    test_downloads_with_same_video_id_use_separate_job_paths()
    test_download_url_hook_preserves_cancellation()
    test_llm_cancellation_happens_before_provider_request()
    test_tts_and_audio_mix_cancel_before_work()
    test_packager_removes_host_icu_dlls_that_conflict_with_qt()
    test_external_process_stops_on_cancellation()
    test_hardware_capabilities_are_cached_and_can_be_refreshed()
    test_srt_parser_handles_utf8_and_rejects_invalid_timing()
    test_segment_timeline_is_clamped_and_dubbing_delay_tracks_captions()
    test_pipeline_uses_attached_srt_without_whisper()
    test_short_landscape_srt_clip_exports_portrait_without_audio()
    test_pipeline_job_returns_typed_terminal_statuses()
    test_transcription_honors_cancellation_between_segments()
    test_benchmark_parser_extracts_stage_and_recovery_metrics()
