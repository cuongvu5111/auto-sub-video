"""
Module lồng tiếng AI (Text-to-Speech) và đồng bộ thời lượng âm thanh.
Sử dụng edge-tts tạo giọng đọc tiếng Việt truyền cảm và FFmpeg atempo để nén/giãn tốc độ.
"""

import sys
import os
import re
import asyncio
import subprocess
from pathlib import Path
from typing import Optional, Callable, List, Dict, Any
from config import Config
from core.audio_extractor import find_ffmpeg

# Cấu hình encoding UTF-8 nếu chạy trên Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except AttributeError:
        pass


class TTSError(Exception):
    """Lỗi xảy ra trong quá trình tạo giọng đọc hoặc đồng bộ thời lượng."""
    pass


def get_audio_duration(file_path: Path | str) -> float:
    """
    Đo thời lượng chính xác của tệp âm thanh (tính bằng giây) qua FFmpeg.
    """
    file_obj = Path(file_path).resolve()
    if not file_obj.exists():
        raise FileNotFoundError(f"Không tìm thấy file để đo thời lượng: {file_path}")

    ffmpeg_bin = find_ffmpeg()
    cmd = [ffmpeg_bin, "-i", str(file_obj)]

    # FFmpeg in thông tin media ra stderr
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    match = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", result.stderr)
    if match:
        hours = float(match.group(1))
        minutes = float(match.group(2))
        seconds = float(match.group(3))
        return hours * 3600 + minutes * 60 + seconds

    raise TTSError(f"Không thể xác định thời lượng của tệp: {file_path}")


async def synthesize_speech_async(text: str, output_file: Path, voice: str) -> Path:
    """
    Hàm bất đồng bộ gọi Microsoft Edge TTS tạo giọng đọc tiếng Việt.
    """
    try:
        import edge_tts
    except ImportError:
        raise TTSError("Thư viện edge-tts chưa được cài đặt. Vui lòng chạy: pip install edge-tts")

    output_file.parent.mkdir(parents=True, exist_ok=True)
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(str(output_file))
    return output_file


def adjust_audio_speed(
    input_audio: Path,
    output_audio: Path,
    target_duration: float,
    min_speed: float = 0.85,
    max_speed: float = 1.30
) -> Path:
    """
    Căn chỉnh tốc độ của tệp âm thanh bằng filter atempo của FFmpeg để khớp target_duration.

    Args:
        input_audio: Đường dẫn file âm thanh gốc.
        output_audio: Đường dẫn file âm thanh sau khi chỉnh tốc độ.
        target_duration: Thời lượng mong muốn (giây).
        min_speed: Giới hạn làm chậm tối đa (tránh giọng bị rề rà).
        max_speed: Giới hạn tăng tốc tối đa (tránh giọng bị như chipmunk).

    Returns:
        Path: Đường dẫn file audio đã qua căn chỉnh tốc độ.
    """
    input_file = Path(input_audio).resolve()
    output_file = Path(output_audio).resolve()
    output_file.parent.mkdir(parents=True, exist_ok=True)

    current_duration = get_audio_duration(input_file)
    if current_duration <= 0 or target_duration <= 0:
        # Nếu thời lượng quá ngắn hoặc lỗi, copy nguyên file
        import shutil
        shutil.copy2(input_file, output_file)
        return output_file

    # Tính toán tốc độ cần điều chỉnh
    raw_factor = current_duration / target_duration
    # Kẹp giá trị trong dải an toàn để giữ nguyên độ tự nhiên của giọng đọc
    speed_factor = max(min_speed, min(max_speed, raw_factor))

    # Nếu tốc độ chênh lệch rất nhỏ (dưới 3%), giữ nguyên file không cần re-encode
    if abs(speed_factor - 1.0) < 0.03:
        import shutil
        shutil.copy2(input_file, output_file)
        return output_file

    ffmpeg_bin = find_ffmpeg()
    # atempo chỉ thay đổi tốc độ (tempo), giữ nguyên cao độ (pitch) của giọng người
    cmd = [
        ffmpeg_bin,
        "-y",
        "-i", str(input_file),
        "-filter:a", f"atempo={speed_factor:.3f}",
        "-vn",
        str(output_file)
    ]

    try:
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        return output_file
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr[-300:] if e.stderr else str(e)
        raise TTSError(f"Lỗi khi căn chỉnh tốc độ âm thanh với atempo: {error_msg}") from e


def process_dubbing_segments(
    segments: List[Dict[str, Any]],
    voice: Optional[str] = None,
    output_dir: Optional[Path] = None,
    progress_callback: Optional[Callable[[str, float], None]] = None
) -> List[Dict[str, Any]]:
    """
    Xử lý hàng loạt toàn bộ danh sách câu thoại:
    1. Sinh file audio tiếng Việt cho từng câu bằng edge-tts.
    2. Căn chỉnh tốc độ khớp với mốc thời gian (start - end) của video gốc.

    Args:
        segments: Danh sách phân đoạn đã có translated_text.
        voice: Giọng đọc (mặc định lấy từ Config.DEFAULT_VOICE).
        output_dir: Thư mục lưu các file audio thành phẩm.
        progress_callback: Hàm nhận (thông điệp, phần trăm tiến độ).

    Returns:
        List[Dict[str, Any]]: Danh sách phân đoạn được bổ sung "dubbed_audio_path" và "dubbed_duration".
    """
    if not segments:
        return []

    target_voice = voice or Config.DEFAULT_VOICE
    target_dir = output_dir or (Config.TEMP_DIR / "dubbing_segments")
    target_dir.mkdir(parents=True, exist_ok=True)

    total_segments = len(segments)
    enriched_segments = []

    for idx, seg in enumerate(segments):
        text = seg.get("translated_text", "").strip() or seg.get("text", "").strip()
        start = seg.get("start", 0.0)
        end = seg.get("end", 0.0)
        target_duration = max(0.5, end - start)

        seg_index = seg.get("index", idx)
        raw_mp3 = target_dir / f"raw_seg_{seg_index}.mp3"
        synced_mp3 = target_dir / f"synced_seg_{seg_index}.mp3"

        if progress_callback:
            percent = (idx / total_segments) * 100.0
            progress_callback(f"Đang sinh giọng đọc câu {idx + 1}/{total_segments}: {text[:30]}...", percent)

        try:
            # 1. Sinh âm thanh bằng edge-tts
            asyncio.run(synthesize_speech_async(text, raw_mp3, target_voice))

            # 2. Căn chỉnh tốc độ khớp thời lượng mục tiêu
            adjust_audio_speed(raw_mp3, synced_mp3, target_duration)

            # 3. Đo lại thời lượng thực tế của file âm thanh sau khi đồng bộ
            actual_duration = get_audio_duration(synced_mp3)

            seg_copy = dict(seg)
            seg_copy["dubbed_audio_path"] = str(synced_mp3)
            seg_copy["dubbed_duration"] = actual_duration
            enriched_segments.append(seg_copy)

        except Exception as e:
            raise TTSError(f"Lỗi khi xử lý lồng tiếng câu #{seg_index} ('{text}'): {str(e)}") from e

    if progress_callback:
        progress_callback(f"Lồng tiếng hoàn tất toàn bộ {total_segments} câu thoại.", 100.0)

    return enriched_segments
