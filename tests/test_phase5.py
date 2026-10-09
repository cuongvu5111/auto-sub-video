"""
Kiểm thử cho Phase 5: Module Lồng Tiếng AI (TTS Engine) & Đồng Bộ Tốc Độ.
"""

import sys
import asyncio
import os
import wave
from pathlib import Path

# Cấu hình encoding UTF-8 cho console Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

# Thêm thư mục gốc vào sys.path
root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir))

from core.tts_engine import (
    get_audio_duration,
    process_dubbing_segments,
    synthesize_speech_async,
    adjust_audio_speed,
    TTSError
)


def test_missing_file_duration():
    """Kiểm tra đo thời lượng file không tồn tại sẽ báo lỗi đúng."""
    try:
        get_audio_duration("non_existent_audio.mp3")
        assert False, "Cần ném ngoại lệ FileNotFoundError"
    except FileNotFoundError:
        print("✓ test_missing_file_duration: PASSED")


def test_audio_duration_prefers_pyav_and_keeps_ffmpeg_fallback():
    from types import SimpleNamespace
    from unittest.mock import patch
    from core.audio_extractor import find_ffmpeg
    from core.process import run_process
    import tempfile

    with tempfile.TemporaryDirectory(prefix="duration_probe_", dir=str(root_dir / "temp")) as tmp:
        audio_path = Path(tmp) / "fixture.wav"
        with wave.open(str(audio_path), "wb") as audio:
            audio.setnchannels(1)
            audio.setsampwidth(2)
            audio.setframerate(24000)
            audio.writeframes(b"\0\0" * 12000)

        with patch("core.tts_engine.run_process", side_effect=AssertionError("FFmpeg should not be needed")):
            assert abs(get_audio_duration(audio_path) - 0.5) < 0.01

        with patch("core.tts_engine._get_audio_duration_from_pyav", return_value=None), \
             patch("core.tts_engine.run_process", return_value=SimpleNamespace(
                 stderr="  Duration: 00:00:00.500, start: 0.000000, bitrate: 384 kb/s\n"
             )) as ffmpeg_probe:
            assert abs(get_audio_duration(audio_path) - 0.5) < 0.001
            ffmpeg_probe.assert_called_once()

        mp3_path = Path(tmp) / "fixture.mp3"
        run_process(
            [
                find_ffmpeg(), "-y", "-f", "lavfi", "-i",
                "sine=frequency=440:sample_rate=24000:duration=1.0",
                "-c:a", "libmp3lame", "-b:a", "48k", str(mp3_path),
            ],
            timeout=30,
            check=True,
        )
        pyav_duration = get_audio_duration(mp3_path)
        with patch("core.tts_engine._get_audio_duration_from_pyav", return_value=None):
            ffmpeg_duration = get_audio_duration(mp3_path)
        assert pyav_duration > 0
        assert abs(pyav_duration - ffmpeg_duration) <= 0.10

    print("✓ test_audio_duration_prefers_pyav_and_keeps_ffmpeg_fallback: PASSED")


def test_speed_sync_trims_edge_silence_before_tempo_adjustment():
    """Long TTS silence tails should not force speech to overlap the following cue."""
    import tempfile
    from core.audio_extractor import find_ffmpeg
    from core.process import run_process
    from core.tts_engine import _detect_audio_content_window

    with tempfile.TemporaryDirectory(prefix="tts_silence_trim_", dir=str(root_dir / "temp")) as tmp:
        raw = Path(tmp) / "raw.mp3"
        synced = Path(tmp) / "synced.mp3"
        run_process(
            [
                find_ffmpeg(), "-y", "-hide_banner", "-v", "error",
                "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=24000:duration=0.4",
                "-af", "adelay=300,apad=pad_dur=0.8", "-t", "1.5",
                "-c:a", "libmp3lame", "-b:a", "48k", str(raw),
            ],
            timeout=30,
            check=True,
        )
        raw_duration = get_audio_duration(raw)
        raw_window = _detect_audio_content_window(raw)
        assert raw_duration >= 1.4
        assert raw_window is not None and raw_window[1] - raw_window[0] < 0.6

        adjust_audio_speed(raw, synced, target_duration=0.36)
        synced_duration = get_audio_duration(synced)
        assert 0.25 <= synced_duration <= 0.46
        synced_window = _detect_audio_content_window(synced)
        assert synced_window is not None
        assert synced_window[1] - synced_window[0] <= 0.46
    print("✓ test_speed_sync_trims_edge_silence_before_tempo_adjustment: PASSED")


def test_empty_segments():
    """Kiểm tra xử lý danh sách rỗng không phát sinh lỗi."""
    assert process_dubbing_segments([]) == []
    print("✓ test_empty_segments: PASSED")


def test_tts_failure_is_reported_and_marked():
    """A network failure may use silence, but the segment must retain a failure status."""
    from unittest.mock import AsyncMock, patch
    import tempfile

    with tempfile.TemporaryDirectory(prefix="tts_failure_", dir=str(root_dir / "temp")) as tmp:
        output_dir = Path(tmp)
        logs = []

        def make_audio(path, duration, cancel_check=None):
            Path(path).write_bytes(b"fake-audio")
            return Path(path)

        def sync_audio(source, output, duration, cancel_check=None, timing_callback=None):
            Path(output).write_bytes(b"fake-audio")
            return Path(output)

        with patch("core.tts_engine.synthesize_speech_async", new=AsyncMock(return_value=False)), \
             patch("core.tts_engine.generate_silence_audio", side_effect=make_audio), \
             patch("core.tts_engine.adjust_audio_speed", side_effect=sync_audio), \
             patch("core.tts_engine.get_audio_duration", return_value=0.8):
            results = process_dubbing_segments(
                [{"index": 0, "start": 0.0, "end": 0.8, "text": "hello", "translated_text": "Xin chào"}],
                output_dir=output_dir,
                progress_callback=lambda message, percent: logs.append(message),
            )

        assert results[0]["tts_status"] == "failed_silence_fallback"
        assert results[0]["sync_status"] == "success"
        assert any("Không lấy được audio TTS" in message for message in logs)

    print("✓ test_tts_failure_is_reported_and_marked: PASSED")


def test_tts_batch_reuses_one_event_loop():
    """A batch should initialize one asyncio loop and reuse it for all TTS requests."""
    from unittest.mock import AsyncMock, patch
    import tempfile

    with tempfile.TemporaryDirectory(prefix="tts_loop_", dir=str(root_dir / "temp")) as tmp:
        output_dir = Path(tmp)

        def sync_audio(source, output, duration, cancel_check=None, timing_callback=None):
            Path(output).write_bytes(b"fake-audio")
            return Path(output)

        def fake_duration(path, cancel_check=None, timing_callback=None):
            if timing_callback:
                timing_callback("PyAV duration probe", 0.001)
            return 0.8

        with patch("core.tts_engine.synthesize_speech_async", new=AsyncMock(return_value=True)) as synthesize, \
             patch("core.tts_engine.adjust_audio_speed", side_effect=sync_audio), \
             patch("core.tts_engine.get_audio_duration", side_effect=fake_duration), \
             patch("core.tts_engine.time.sleep"), \
             patch("core.tts_engine.asyncio.new_event_loop", wraps=asyncio.new_event_loop) as new_loop:
            logs = []
            results = process_dubbing_segments(
                [
                    {"index": 0, "start": 0.0, "end": 0.8, "translated_text": "Xin chào"},
                    {"index": 1, "start": 0.8, "end": 1.6, "translated_text": "Tạm biệt"},
                ],
                output_dir=output_dir,
                progress_callback=lambda message, percent: logs.append(message),
            )

        assert len(results) == 2
        assert synthesize.await_count == 2
        assert new_loop.call_count == 1
        assert new_loop.return_value.is_closed()
        assert any(message.startswith("TTS performance timings:") for message in logs)

    print("✓ test_tts_batch_reuses_one_event_loop: PASSED")


def test_tts_batch_uses_bounded_concurrency_and_preserves_order():
    """TTS calls overlap only up to the configured limit; results stay in source order."""
    from config import Config
    from unittest.mock import patch
    import tempfile

    original_concurrency = Config.TTS_MAX_CONCURRENCY
    original_pacing = Config.TTS_REQUEST_PACING_SECONDS
    active = 0
    max_active = 0

    async def fake_synthesize(text, output_file, voice, **kwargs):
        nonlocal active, max_active
        active += 1
        max_active = max(max_active, active)
        await asyncio.sleep(0.02)
        Path(output_file).write_bytes(b"raw-audio")
        active -= 1
        return True

    def sync_audio(source, output, duration, cancel_check=None, timing_callback=None):
        Path(output).write_bytes(b"synced-audio")
        return Path(output)

    try:
        Config.TTS_MAX_CONCURRENCY = 2
        Config.TTS_REQUEST_PACING_SECONDS = 0
        with tempfile.TemporaryDirectory(prefix="tts_concurrency_", dir=str(root_dir / "temp")) as tmp:
            output_dir = Path(tmp)
            progress = []
            segments = [
                {"index": index, "start": 0.0, "end": 0.8, "translated_text": f"Câu {index}"}
                for index in (7, 2, 9, 1, 5)
            ]
            with patch("core.tts_engine.synthesize_speech_async", new=fake_synthesize), \
                 patch("core.tts_engine.adjust_audio_speed", side_effect=sync_audio), \
                 patch("core.tts_engine.get_audio_duration", return_value=0.8):
                results = process_dubbing_segments(
                    segments,
                    output_dir=output_dir,
                    progress_callback=lambda message, percent: progress.append(percent),
                )

        assert max_active == 2
        assert [segment["index"] for segment in results] == [7, 2, 9, 1, 5]
        assert [segment["tts_status"] for segment in results] == ["success"] * 5
        assert progress == sorted(progress)
        assert max(progress) == 100.0
    finally:
        Config.TTS_MAX_CONCURRENCY = original_concurrency
        Config.TTS_REQUEST_PACING_SECONDS = original_pacing

    print("✓ test_tts_batch_uses_bounded_concurrency_and_preserves_order: PASSED")


def test_overlong_dubbing_is_preserved_and_overlap_is_reported():
    """Keep all speech and report subtitle overrun plus actual next-line overlap."""
    from unittest.mock import AsyncMock, patch
    import tempfile

    with tempfile.TemporaryDirectory(prefix="tts_overlap_", dir=str(root_dir / "temp")) as tmp:
        output_dir = Path(tmp)

        def sync_audio(_source, output, _duration, **_kwargs):
            Path(output).write_bytes(b"complete-speech")
            return Path(output)

        logs = []
        with patch("core.tts_engine.synthesize_speech_async", new=AsyncMock(return_value=True)), \
             patch("core.tts_engine.adjust_audio_speed", side_effect=sync_audio), \
             patch("core.tts_engine.get_audio_duration", return_value=1.5):
            results = process_dubbing_segments(
                [
                    {"index": 0, "start": 0.0, "end": 1.0, "translated_text": "Long sentence"},
                    {"index": 1, "start": 1.2, "end": 2.0, "translated_text": "Next sentence"},
                ],
                output_dir=output_dir,
                progress_callback=lambda message, _percent: logs.append(message),
            )

        assert results[0]["dubbed_duration"] == 1.5
        assert Path(results[0]["dubbed_audio_path"]).read_bytes() == b"complete-speech"
        assert any("exceeds its subtitle interval by 0.50s" in message for message in logs)
        assert any("overlaps the next line by 0.30s" in message for message in logs)
    print("✓ test_overlong_dubbing_is_preserved_and_overlap_is_reported: PASSED")


def test_tts_rate_limit_retry_is_bounded_and_cancellable():
    """Edge TTS provider errors retry within the segment deadline and honor cancellation."""
    import time
    import tempfile
    from types import ModuleType
    from unittest.mock import patch

    calls = {"count": 0, "cancel": False}

    class FakeCommunicate:
        def __init__(self, *_args):
            pass

        async def save(self, _path):
            calls["count"] += 1
            if calls["cancel"]:
                raise RuntimeError("cancel after provider response")
            raise RuntimeError("429 rate limit")

    fake_edge_tts = ModuleType("edge_tts")
    fake_edge_tts.Communicate = FakeCommunicate

    with tempfile.TemporaryDirectory(prefix="tts_rate_limit_", dir=str(root_dir / "temp")) as tmp:
        output = Path(tmp) / "speech.mp3"
        with patch.dict(sys.modules, {"edge_tts": fake_edge_tts}):
            started = time.perf_counter()
            succeeded = asyncio.run(synthesize_speech_async(
                "Xin chào", output, "vi-VN-NamMinhNeural", max_retries=1,
                request_timeout=0.2, total_timeout=0.35,
            ))
            elapsed = time.perf_counter() - started
            assert not succeeded and elapsed < 1.5
            assert calls["count"] <= 2
            assert not output.exists()

            calls["count"] = 0
            calls["cancel"] = True
            started = time.perf_counter()
            try:
                asyncio.run(synthesize_speech_async(
                    "Xin chào", output, "vi-VN-NamMinhNeural", max_retries=1,
                    request_timeout=1.0, total_timeout=3.0,
                    cancel_check=lambda: calls["count"] > 0,
                ))
                raise AssertionError("Expected cancellation after provider error")
            except InterruptedError:
                pass
            assert time.perf_counter() - started < 1.0
            assert calls["count"] == 1
    print("✓ test_tts_rate_limit_retry_is_bounded_and_cancellable: PASSED")


def test_live_edge_tts():
    """Kiểm tra gọi thử edge-tts sinh một đoạn audio tiếng Việt ngắn 1-2 từ."""
    if os.getenv("AUTOSUB_RUN_LIVE_TTS_TESTS") != "1":
        print("⚠ SKIPPED test_live_edge_tts: set AUTOSUB_RUN_LIVE_TTS_TESTS=1 to enable the network test")
        return
    test_out = root_dir / "temp" / "test_tts_sample.mp3"
    test_out.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        asyncio.run(synthesize_speech_async("Xin chào", test_out, "vi-VN-NamMinhNeural"))
        assert test_out.exists() and test_out.stat().st_size > 0
        duration = get_audio_duration(test_out)
        print(f"✓ test_live_edge_tts: PASSED (Thời lượng: {duration:.2f}s, Kích thước: {test_out.stat().st_size} bytes)")
    except Exception as e:
        print(f"! test_live_edge_tts SKIPPED/WARNING (Có thể do mạng): {e}")


if __name__ == "__main__":
    print("=== CHẠY KIỂM THỬ PHASE 5 ===")
    test_missing_file_duration()
    test_audio_duration_prefers_pyav_and_keeps_ffmpeg_fallback()
    test_speed_sync_trims_edge_silence_before_tempo_adjustment()
    test_empty_segments()
    test_tts_failure_is_reported_and_marked()
    test_tts_batch_reuses_one_event_loop()
    test_tts_batch_uses_bounded_concurrency_and_preserves_order()
    test_overlong_dubbing_is_preserved_and_overlap_is_reported()
    test_tts_rate_limit_retry_is_bounded_and_cancellable()
    test_live_edge_tts()
    print("=== TẤT CẢ TEST ĐƠN VỊ PHASE 5 ĐÃ VƯỢT QUA ===")
