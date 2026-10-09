"""
Kiểm thử cho Phase 2: Module Downloader & Audio Extractor.
"""

import sys
import subprocess
import tempfile
from pathlib import Path

# Cấu hình encoding UTF-8 cho console Windows để in tiếng Việt mượt mà
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

# Thêm thư mục gốc vào sys.path để import core
root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir))

from core.downloader import is_url, download_video
from core.audio_extractor import find_ffmpeg, extract_audio
from core.media_probe import MediaProbeError, probe_media, validate_video_input


def test_is_url():
    """Kiểm tra hàm nhận diện URL."""
    assert is_url("https://www.tiktok.com/@user/video/123") is True
    assert is_url("http://example.com/video.mp4") is True
    assert is_url("D:/videos/my_video.mp4") is False
    assert is_url("C:\\test\\clip.mp4") is False
    print("✓ test_is_url: PASSED")


def test_local_video_handling():
    """Kiểm tra xử lý video cục bộ nếu tệp không tồn tại sẽ báo lỗi đúng."""
    try:
        download_video("non_existent_file.mp4")
        assert False, "Cần ném ngoại lệ FileNotFoundError"
    except FileNotFoundError:
        print("✓ test_local_video_handling: PASSED")


def test_yt_dlp_availability():
    """Kiểm tra thư viện yt-dlp đã được cài đặt và sẵn sàng hoạt động."""
    try:
        import yt_dlp
    except ImportError:
        print("⚠ SKIPPED test_yt_dlp_availability: install project requirements to enable downloads")
        return
    assert hasattr(yt_dlp, "YoutubeDL")
    print(f"✓ test_yt_dlp_availability: PASSED (Phiên bản: {yt_dlp.version.__version__})")


def test_media_probe_detects_short_audio_and_video_only_input():
    """Metadata inspection must distinguish video duration from a shorter audio stream."""
    ffmpeg = find_ffmpeg()
    creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    with tempfile.TemporaryDirectory(prefix="media_probe_", dir=str(root_dir / "temp")) as tmp:
        temp_dir = Path(tmp)
        short_audio_video = temp_dir / "short_audio.mp4"
        subprocess.run(
            [
                ffmpeg, "-y", "-f", "lavfi", "-i", "color=c=black:s=64x64:r=25:d=1.2",
                "-f", "lavfi", "-i", "sine=frequency=1000:duration=0.4",
                "-map", "0:v:0", "-map", "1:a:0", "-c:v", "libx264", "-c:a", "aac",
                str(short_audio_video)
            ],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True, creationflags=creationflags
        )
        info = probe_media(short_audio_video)
        assert info.has_video and info.has_audio
        assert info.duration >= 1.0
        assert info.audio_duration is not None and info.audio_duration < info.duration

        silent_video = temp_dir / "silent.mp4"
        subprocess.run(
            [ffmpeg, "-y", "-f", "lavfi", "-i", "color=c=black:s=64x64:r=25:d=1", "-an", "-c:v", "libx264", str(silent_video)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True, creationflags=creationflags
        )
        try:
            validate_video_input(silent_video, require_audio=True)
            raise AssertionError("Expected an actionable no-audio validation error")
        except MediaProbeError as exc:
            assert "No audio stream" in str(exc)

    print("✓ test_media_probe_detects_short_audio_and_video_only_input: PASSED")


if __name__ == "__main__":
    print("=== CHẠY KIỂM THỬ PHASE 2 ===")
    test_is_url()
    test_local_video_handling()
    test_yt_dlp_availability()
    test_media_probe_detects_short_audio_and_video_only_input()
    print("=== TẤT CẢ TEST ĐƠN VỊ ĐÃ VƯỢT QUA ===")
