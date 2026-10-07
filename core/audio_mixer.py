"""
Module hòa âm (Audio Mixer) và đóng gói video hoàn thiện (FFmpeg).
Thực hiện kỹ thuật Audio Ducking (giảm âm lượng tiếng gốc làm nền, đè tiếng lồng tiếng Việt)
và nung phụ đề .ass tùy chọn vào khung hình video.
"""

import sys
import os
import subprocess
from pathlib import Path
from typing import Optional, Callable, List, Dict, Any
from config import Config
from core.audio_extractor import find_ffmpeg
from core.tts_engine import get_audio_duration

# Cấu hình encoding UTF-8 nếu chạy trên Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except AttributeError:
        pass


class AudioMixerError(Exception):
    """Lỗi xảy ra trong quá trình hòa âm hoặc render video."""
    pass


def format_ass_timestamp(seconds: float) -> str:
    """
    Chuyển đổi số giây thành định dạng thời gian chuẩn ASS (H:MM:SS.cs).
    Ví dụ: 75.25 -> 0:01:15.25
    """
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    centis = int(round((seconds - int(seconds)) * 100))
    if centis >= 100:
        centis = 99
    return f"{hrs}:{mins:02d}:{secs:02d}.{centis:02d}"


def generate_ass_file(
    segments: List[Dict[str, Any]],
    output_ass_path: Path,
    font_name: str = "Arial",
    font_size: int = 20,
    primary_color: str = "&H00FFFFFF",  # Màu trắng
    outline_color: str = "&H00000000",  # Viền đen
    outline_width: int = 3
) -> Path:
    """
    Sinh file phụ đề định dạng ASS (Advanced SubStation Alpha) với kiểu chữ nổi bật cho TikTok.
    """
    output_ass_path = Path(output_ass_path).resolve()
    output_ass_path.parent.mkdir(parents=True, exist_ok=True)

    header = f"""[Script Info]
Title: AutoSub TikTok Dubbing
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes
YCbCr Matrix: None

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: TikTokStyle,{font_name},{font_size},{primary_color},&H000000FF,{outline_color},&H80000000,-1,0,0,0,100,100,0,0,1,{outline_width},1,2,20,20,35,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = [header]
    for seg in segments:
        text = seg.get("translated_text", "").strip() or seg.get("text", "").strip()
        if not text:
            continue
        start_ts = format_ass_timestamp(seg.get("start", 0.0))
        end_ts = format_ass_timestamp(seg.get("end", 0.0))
        lines.append(f"Dialogue: 0,{start_ts},{end_ts},TikTokStyle,,0,0,0,,{text}\n")

    with open(output_ass_path, "w", encoding="utf-8") as f:
        f.writelines(lines)

    return output_ass_path


def create_mixed_audio_track(
    original_audio_path: Path,
    segments: List[Dict[str, Any]],
    output_audio_path: Path,
    ducking_volume: float = 0.10,
    total_duration: Optional[float] = None
) -> Path:
    """
    Hòa trộn âm thanh lồng tiếng vào âm thanh gốc (Kỹ thuật Audio Ducking):
    1. Giảm âm lượng âm thanh gốc xuống ducking_volume (ví dụ 10% để giữ nhạc nền/tiếng cười).
    2. Đặt các file thoại tiếng Việt vào đúng mốc start (ms) trên timeline.
    3. Trộn 2 track thành một file âm thanh hoàn thiện.
    """
    try:
        from pydub import AudioSegment
    except ImportError:
        raise AudioMixerError("Thư viện pydub chưa được cài đặt. Vui lòng chạy: pip install pydub")

    orig_path = Path(original_audio_path).resolve()
    out_path = Path(output_audio_path).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if not orig_path.exists():
        raise FileNotFoundError(f"Không tìm thấy file audio gốc: {original_audio_path}")

    # 1. Nạp audio gốc và giảm âm lượng
    orig_audio = AudioSegment.from_file(str(orig_path))
    
    # Tính toán mức giảm dB dựa trên tỷ lệ volume (0.10 ~ -20dB)
    import math
    if ducking_volume > 0:
        db_change = 20 * math.log10(max(0.01, ducking_volume))
        background_track = orig_audio + db_change
    else:
        # Nếu ducking_volume = 0 thì tắt hẳn tiếng gốc (tạo đoạn im lặng)
        background_track = AudioSegment.silent(duration=len(orig_audio))

    # 2. Tạo track lồng tiếng mới (bắt đầu bằng đoạn im lặng bằng độ dài video)
    final_length = len(orig_audio)
    if total_duration:
        final_length = max(final_length, int(total_duration * 1000))
    speech_track = AudioSegment.silent(duration=final_length)

    # 3. Chèn từng đoạn thoại lồng tiếng vào đúng mốc thời gian start
    for seg in segments:
        dubbed_file = seg.get("dubbed_audio_path")
        if not dubbed_file or not Path(dubbed_file).exists():
            continue

        start_ms = int(seg.get("start", 0.0) * 1000)
        seg_audio = AudioSegment.from_file(dubbed_file)

        # Chèn âm thanh lồng tiếng vào đúng vị trí start_ms
        speech_track = speech_track.overlay(seg_audio, position=start_ms)

    # 4. Hòa âm: Đè track lồng tiếng (100% âm lượng) lên track nền (10% âm lượng)
    mixed_audio = background_track.overlay(speech_track)

    # Xuất ra file âm thanh đích (AAC hoặc MP3)
    mixed_audio.export(str(out_path), format="mp3", bitrate="192k")
    return out_path


def render_final_video(
    original_video_path: Path,
    mixed_audio_path: Path,
    output_video_path: Path,
    ass_subtitle_path: Optional[Path] = None,
    progress_callback: Optional[Callable[[str, float], None]] = None
) -> Path:
    """
    Đóng gói video hoàn thiện bằng FFmpeg:
    - Thay thế track âm thanh gốc bằng track âm thanh đã hòa âm.
    - Nung phụ đề .ass trực tiếp vào khung hình (nếu có yêu cầu).
    """
    orig_video = Path(original_video_path).resolve()
    mixed_audio = Path(mixed_audio_path).resolve()
    out_video = Path(output_video_path).resolve()
    out_video.parent.mkdir(parents=True, exist_ok=True)

    if not orig_video.exists():
        raise FileNotFoundError(f"Không tìm thấy video gốc: {original_video_path}")
    if not mixed_audio.exists():
        raise FileNotFoundError(f"Không tìm thấy file audio đã hòa âm: {mixed_audio_path}")

    ffmpeg_bin = find_ffmpeg()

    if progress_callback:
        progress_callback("Đang tiến hành ghép âm thanh và xuất video thành phẩm...", 70.0)

    # Trường hợp 1: Có nung phụ đề vào hình
    if ass_subtitle_path and Path(ass_subtitle_path).exists():
        ass_path_str = str(Path(ass_subtitle_path).resolve()).replace("\\", "/")
        # Trên Windows, ký tự : trong ổ đĩa (D:/) cần escape thành D\:/ trong filter ass
        ass_path_str = ass_path_str.replace(":", "\\:")

        cmd = [
            ffmpeg_bin,
            "-y",
            "-i", str(orig_video),
            "-i", str(mixed_audio),
            "-filter_complex", f"[0:v]ass='{ass_path_str}'[v]",
            "-map", "[v]",
            "-map", "1:a",
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "22",
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest",
            str(out_video)
        ]
    else:
        # Trường hợp 2: Không nung phụ đề (copy thẳng luồng video để xuất cực nhanh)
        cmd = [
            ffmpeg_bin,
            "-y",
            "-i", str(orig_video),
            "-i", str(mixed_audio),
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest",
            str(out_video)
        ]

    try:
        process = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )
        if not out_video.exists() or out_video.stat().st_size == 0:
            raise AudioMixerError("Tệp video xuất ra bị rỗng hoặc không tồn tại.")

        if progress_callback:
            progress_callback(f"Xuất video hoàn tất: {out_video.name}", 100.0)

        return out_video

    except subprocess.CalledProcessError as e:
        error_msg = e.stderr[-400:] if e.stderr else str(e)
        raise AudioMixerError(f"Lỗi khi render video bằng FFmpeg: {error_msg}") from e
