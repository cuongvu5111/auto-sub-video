"""
Module trích xuất âm thanh từ tệp video.
Chuyển đổi âm thanh sang định dạng chuẩn WAV 16kHz mono phục vụ mô hình Whisper.
"""

import sys
import subprocess
import shutil
from pathlib import Path
from typing import Optional
from config import Config

# Cờ ẩn cửa sổ console phụ trên Windows khi chạy FFmpeg
SUBPROCESS_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0


class AudioExtractionError(Exception):
    """Lỗi xảy ra trong quá trình trích xuất âm thanh."""
    pass


def find_ffmpeg() -> str:
    """
    Xác định đường dẫn khả dụng của lệnh ffmpeg trên hệ thống.
    Ưu tiên:
    1. Binary nội bộ trong thư mục bin/ffmpeg.exe của dự án
    2. ffmpeg có sẵn trong biến môi trường PATH hệ thống
    3. imageio-ffmpeg nếu có cài đặt
    """
    # 1. Kiểm tra thư mục bin nội bộ của dự án (hỗ trợ cả exe đóng gói và thư mục dự án)
    for candidate_dir in [Config.BIN_DIR, getattr(Config, "INTERNAL_DIR", Config.BASE_DIR) / "bin"]:
        local_ffmpeg = candidate_dir / "ffmpeg.exe"
        if local_ffmpeg.exists():
            return str(local_ffmpeg)

    # 2. Kiểm tra trong biến môi trường PATH
    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg:
        return system_ffmpeg

    # 3. Thử tìm qua imageio_ffmpeg
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        pass

    raise AudioExtractionError(
        "Không tìm thấy công cụ FFmpeg trên hệ thống!\n"
        "Vui lòng cài đặt bằng lệnh: winget install Gyan.FFmpeg\n"
        "Hoặc tải ffmpeg.exe đặt vào thư mục bin/ của dự án."
    )


def extract_audio(
    video_path: Path | str,
    output_wav_path: Optional[Path | str] = None,
    sample_rate: int = 16000
) -> Path:
    """
    Trích xuất âm thanh từ video sang định dạng WAV 16kHz Mono.

    Args:
        video_path: Đường dẫn tệp video nguồn.
        output_wav_path: Đường dẫn lưu file âm thanh WAV (tự sinh nếu không truyền).
        sample_rate: Tần số lấy mẫu (mặc định 16000Hz - chuẩn tối ưu của Whisper).

    Returns:
        Path: Đường dẫn tuyệt đối đến tệp audio WAV đã trích xuất.
    """
    video_file = Path(video_path).resolve()
    if not video_file.exists():
        raise FileNotFoundError(f"Không tìm thấy tệp video nguồn: {video_path}")

    # Đặt tên file audio đích nếu chưa chỉ định
    if output_wav_path:
        target_wav = Path(output_wav_path).resolve()
    else:
        target_wav = Config.TEMP_DIR / f"{video_file.stem}_audio.wav"

    target_wav.parent.mkdir(parents=True, exist_ok=True)

    ffmpeg_bin = find_ffmpeg()

    # Lệnh trích xuất: -vn (bỏ hình), -acodec pcm_s16le (WAV chuẩn), -ar (tần số 16kHz), -ac 1 (kênh mono)
    cmd = [
        ffmpeg_bin,
        "-y",                       # Ghi đè nếu file đích đã tồn tại
        "-i", str(video_file),      # Tệp video đầu vào
        "-vn",                      # Không lấy luồng hình ảnh
        "-acodec", "pcm_s16le",     # Bộ mã hóa âm thanh PCM 16-bit
        "-ar", str(sample_rate),    # Tần số 16000 Hz
        "-ac", "1",                 # Mono (1 kênh)
        str(target_wav)             # Tệp âm thanh đầu ra
    ]

    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
            creationflags=SUBPROCESS_NO_WINDOW
        )
        if not target_wav.exists() or target_wav.stat().st_size == 0:
            raise AudioExtractionError("Tệp âm thanh sinh ra bị rỗng hoặc không tồn tại.")
        return target_wav

    except subprocess.CalledProcessError as e:
        error_msg = e.stderr[-500:] if e.stderr else str(e)
        raise AudioExtractionError(f"Lỗi khi trích xuất âm thanh bằng FFmpeg: {error_msg}") from e
