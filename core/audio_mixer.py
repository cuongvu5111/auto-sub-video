"""
Module hòa âm (Audio Mixer) và đóng gói video hoàn thiện (FFmpeg).
Thực hiện kỹ thuật Audio Ducking (giảm âm lượng tiếng gốc làm nền, đè tiếng lồng tiếng Việt)
và nung phụ đề .ass tùy chọn vào khung hình video.
"""

import sys
import os
import subprocess
from pathlib import Path
from typing import Optional, Callable, List, Dict, Any, Union
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


def hex_to_ass_color(color_str: str, default: str = "&H00FFFFFF") -> str:
    """
    Chuyển đổi mã màu hex (ví dụ #000000 hoặc #FFFFFF) sang mã màu chuẩn ASS (&HAABBGGRR).
    Nếu đã là định dạng ASS (&H...) thì giữ nguyên.
    """
    if not color_str:
        return default
    color_str = color_str.strip()
    if color_str.startswith("&H") or color_str.startswith("&h"):
        return color_str

    if color_str.startswith("#"):
        color_str = color_str[1:]

    if len(color_str) == 3:
        color_str = "".join(c * 2 for c in color_str)

    if len(color_str) == 6 or len(color_str) == 8:
        r = color_str[0:2].upper()
        g = color_str[2:4].upper()
        b = color_str[4:6].upper()
        # Định dạng chuẩn ASS là &HAABBGGRR (Alpha=00 là đặc hoàn toàn)
        return f"&H00{b}{g}{r}"

    return default


def generate_ass_file(
    segments: List[Dict[str, Any]],
    output_ass_path: Path,
    font_name: str = "Arial",
    font_size: int = 24,
    primary_color: str = "&H00000000",   # Màu chữ (mặc định đen cho dạng TikTok badge)
    outline_color: str = "&H00FFFFFF",   # Màu viền / viền hộp (mặc định trắng)
    back_color: str = "&H00FFFFFF",      # Màu nền hộp (khi border_style=3)
    border_style: int = 3,               # 3: Hộp nền (Box/Badge), 1: Viền đổ bóng (Outline)
    outline_width: int = 6,              # Khoảng đệm hộp khi border_style=3, hoặc độ dày viền khi border_style=1
    shadow_width: int = 0,               # Độ đổ bóng
    margin_v: int = 40                   # Khoảng cách từ đáy video (pixel)
) -> Path:
    """
    Sinh file phụ đề định dạng ASS (Advanced SubStation Alpha) với kiểu chữ nổi bật cho TikTok.
    Hỗ trợ BorderStyle 3 (hộp nền chữ nhật bao quanh chữ) hoặc BorderStyle 1 (viền bóng truyền thống).
    """
    output_ass_path = Path(output_ass_path).resolve()
    output_ass_path.parent.mkdir(parents=True, exist_ok=True)

    ass_primary = hex_to_ass_color(primary_color, default="&H00000000")
    ass_outline = hex_to_ass_color(outline_color, default="&H00FFFFFF")
    ass_back = hex_to_ass_color(back_color, default="&H00FFFFFF")

    header = f"""[Script Info]
Title: AutoSub TikTok Dubbing
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes
YCbCr Matrix: None

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: TikTokStyle,{font_name},{font_size},{ass_primary},&H000000FF,{ass_outline},{ass_back},-1,0,0,0,100,100,0,0,{border_style},{outline_width},{shadow_width},2,20,20,{margin_v},1

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


def _init_pydub():
    """Cấu hình pydub dùng ffmpeg portable và fallback mediainfo bằng PyAV nếu thiếu ffprobe."""
    try:
        import pydub
        import pydub.audio_segment
        import pydub.utils
    except ImportError:
        return

    # 1. Cấu hình ffmpeg converter
    ffmpeg_bin = find_ffmpeg()
    pydub.AudioSegment.converter = str(ffmpeg_bin)

    # 2. Đảm bảo bin/ nằm trong PATH
    bin_dir = str(Config.BIN_DIR.resolve())
    if bin_dir not in os.environ.get("PATH", ""):
        os.environ["PATH"] = bin_dir + os.pathsep + os.environ.get("PATH", "")

    # 3. Fallback đọc thông tin media bằng PyAV nếu hệ thống chưa cài ffprobe độc lập
    def _av_mediainfo(filepath, read_ahead_limit=-1):
        try:
            import av
            with av.open(str(filepath)) as container:
                streams = []
                for s in container.streams.audio:
                    ctx = s.codec_context
                    fmt_name = ctx.format.name if ctx.format else "s16"
                    bits = ctx.format.bits if (ctx.format and hasattr(ctx.format, "bits") and ctx.format.bits > 0) else 16
                    streams.append({
                        "codec_type": "audio",
                        "codec_name": ctx.name,
                        "sample_fmt": fmt_name,
                        "bits_per_sample": bits,
                        "channels": ctx.channels,
                        "sample_rate": str(ctx.sample_rate),
                        "index": s.index
                    })
                duration_sec = float(container.duration / av.time_base) if container.duration else 0.0
                return {
                    "streams": streams,
                    "format": {
                        "duration": str(duration_sec),
                        "size": str(os.path.getsize(filepath)) if os.path.exists(filepath) else "0"
                    }
                }
        except Exception:
            return None

    pydub.utils.mediainfo_json = _av_mediainfo
    pydub.audio_segment.mediainfo_json = _av_mediainfo


def _load_audio_file(file_path: Union[str, Path]):
    """
    Nạp tệp âm thanh an toàn qua pydub:
    - Nhận diện định dạng phổ biến (.wav, .mp3) để nạp thẳng không cần qua ffprobe.
    - Tự động gọi fallback qua PyAV cho các định dạng khác.
    """
    from pydub import AudioSegment
    p = Path(file_path).resolve()
    ext = p.suffix.lower()
    if ext == ".wav":
        return AudioSegment.from_file(str(p), format="wav", codec="pcm_s16le")
    elif ext == ".mp3":
        return AudioSegment.from_file(str(p), format="mp3", codec="mp3")
    else:
        return AudioSegment.from_file(str(p))


# Tự động cấu hình pydub ngay khi nạp module
_init_pydub()


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

    _init_pydub()

    orig_path = Path(original_audio_path).resolve()
    out_path = Path(output_audio_path).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if not orig_path.exists():
        raise FileNotFoundError(f"Không tìm thấy file audio gốc: {original_audio_path}")

    # 1. Nạp audio gốc và giảm âm lượng
    orig_audio = _load_audio_file(orig_path)
    
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
        seg_audio = _load_audio_file(dubbed_file)

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
