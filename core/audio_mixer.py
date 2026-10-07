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
    margin_v: int = 40,                  # Khoảng cách từ đáy video (pixel)
    alignment: int = 2,                  # Căn chỉnh vị trí (2: Dưới, 5: Giữa, 8: Trên)
    box_padding: Optional[int] = None,   # Khoảng đệm hộp (nếu có sẽ áp dụng vào outline_width)
    total_duration: Optional[float] = None, # Tổng thời lượng video (giây)
    text_watermark: Optional[Dict[str, Any]] = None # Cấu hình chèn text watermark
) -> Path:
    """
    Sinh file phụ đề định dạng ASS (Advanced SubStation Alpha) với kiểu chữ nổi bật cho TikTok.
    Hỗ trợ:
    - BorderStyle 3 (hộp nền bao quanh chữ) hoặc BorderStyle 1 (viền bóng truyền thống).
    - Tùy chỉnh vị trí alignment (2: Dưới, 5: Giữa, 8: Trên) và margin_v để che phụ đề cũ.
    - Chèn Text Watermark (dòng chữ bản quyền giữa video hoặc toàn video).
    """
    output_ass_path = Path(output_ass_path).resolve()
    output_ass_path.parent.mkdir(parents=True, exist_ok=True)

    if box_padding is not None and box_padding >= 0:
        outline_width = box_padding

    ass_primary = hex_to_ass_color(primary_color, default="&H00000000")
    ass_outline = hex_to_ass_color(outline_color, default="&H00FFFFFF")
    ass_back = hex_to_ass_color(back_color, default="&H00FFFFFF")

    styles_section = f"""[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: TikTokStyle,{font_name},{font_size},{ass_primary},&H000000FF,{ass_outline},{ass_back},-1,0,0,0,100,100,0,0,{border_style},{outline_width},{shadow_width},{alignment},20,20,{margin_v},1
"""

    # Thêm style riêng cho Text Watermark nếu được kích hoạt
    has_text_wm = bool(text_watermark and text_watermark.get("enabled", False) and text_watermark.get("text", "").strip())
    if has_text_wm:
        wm_pos = str(text_watermark.get("position", "center")).lower()
        if "top" in wm_pos:
            wm_align = 8
            wm_margin_v = 45
        elif "bottom" in wm_pos:
            wm_align = 2
            wm_margin_v = 45
        else:
            wm_align = 5
            wm_margin_v = 0

        wm_font_size = int(text_watermark.get("font_size", 22))
        styles_section += f"Style: WatermarkStyle,Arial,{wm_font_size},&H00FFFFFF,&H000000FF,&H00000000,&H60000000,-1,0,0,0,100,100,0,0,3,5,0,{wm_align},30,30,{wm_margin_v},1\n"

    header = f"""[Script Info]
Title: AutoSub TikTok Dubbing
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes
YCbCr Matrix: None
PlayResX: 720
PlayResY: 1280

{styles_section}
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = [header]

    # 1. Thêm các dòng phụ đề thoại (Layer 0)
    for seg in segments:
        text = seg.get("translated_text", "").strip() or seg.get("text", "").strip()
        if not text:
            continue
        start_ts = format_ass_timestamp(seg.get("start", 0.0))
        end_ts = format_ass_timestamp(seg.get("end", 0.0))
        lines.append(f"Dialogue: 0,{start_ts},{end_ts},TikTokStyle,,0,0,0,,{text}\n")

    # 2. Thêm dòng Text Watermark nếu có (Layer 1)
    if has_text_wm:
        wm_text = text_watermark.get("text", "").strip()
        timing_mode = text_watermark.get("timing_mode", "mid_video")
        max_seg_end = max((seg.get("end", 0.0) for seg in segments), default=0.0)
        dur = total_duration if (total_duration and total_duration > 0) else max(max_seg_end, 10.0)

        if timing_mode == "full":
            wm_start = 0.0
            wm_end = dur
        else:
            # Mặc định: Hiển thị 6 giây ở mốc giữa video
            wm_len = float(text_watermark.get("duration", 6.0))
            mid = dur / 2.0
            wm_start = max(0.0, mid - (wm_len / 2.0))
            wm_end = min(dur, wm_start + wm_len)

        start_ts = format_ass_timestamp(wm_start)
        end_ts = format_ass_timestamp(wm_end)
        lines.append(f"Dialogue: 1,{start_ts},{end_ts},WatermarkStyle,,0,0,0,,{wm_text}\n")

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
    watermark_options: Optional[Dict[str, Any]] = None,
    progress_callback: Optional[Callable[[str, float], None]] = None
) -> Path:
    """
    Đóng gói video hoàn thiện bằng FFmpeg:
    - Thay thế track âm thanh gốc bằng track âm thanh đã hòa âm.
    - Nung phụ đề .ass trực tiếp vào khung hình (nếu có yêu cầu).
    - Chèn Logo Watermark (vị trí tùy biến, độ mờ Opacity, tự động co tỉ lệ).
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

    has_sub = bool(ass_subtitle_path and Path(ass_subtitle_path).exists())

    # Kiểm tra cấu hình Logo Watermark
    has_logo = False
    logo_path = None
    if watermark_options and watermark_options.get("logo_enabled", False):
        candidate_path = watermark_options.get("logo_path")
        if candidate_path and Path(candidate_path).exists():
            has_logo = True
            logo_path = Path(candidate_path).resolve()

    if has_sub or has_logo:
        # Trường hợp cần xử lý hình ảnh qua filter_complex và mã hóa lại libx264
        cmd = [
            ffmpeg_bin,
            "-y",
            "-i", str(orig_video),
            "-i", str(mixed_audio)
        ]

        filter_chains = []
        curr_v = "0:v"

        if has_logo:
            cmd.extend(["-i", str(logo_path)])
            # logo stream là luồng video thứ 3 (index 2:v)
            opacity = float(watermark_options.get("logo_opacity", 0.8))
            opacity = max(0.05, min(1.0, opacity))
            max_w = int(watermark_options.get("logo_max_width", 160))
            max_w = max(40, min(800, max_w))

            pos_key = str(watermark_options.get("logo_position", "top-right")).lower().replace(" ", "-")
            pos_expr_map = {
                "top-right": "main_w-overlay_w-24:24",
                "top-left": "24:24",
                "bottom-right": "main_w-overlay_w-24:main_h-overlay_h-24",
                "bottom-left": "24:main_h-overlay_h-24",
                "center": "(main_w-overlay_w)/2:(main_h-overlay_h)/2"
            }
            pos_expr = pos_expr_map.get(pos_key, "main_w-overlay_w-24:24")

            filter_chains.append(f"[2:v]scale={max_w}:-1,format=rgba,colorchannelmixer=aa={opacity:.2f}[logo]")
            filter_chains.append(f"[{curr_v}][logo]overlay={pos_expr}[v_logo]")
            curr_v = "v_logo"

        if has_sub:
            ass_path_str = str(Path(ass_subtitle_path).resolve()).replace("\\", "/")
            # Trên Windows, ký tự : trong ổ đĩa (D:/) cần escape thành D\:/ trong filter ass
            ass_path_str = ass_path_str.replace(":", "\\:")
            filter_chains.append(f"[{curr_v}]ass='{ass_path_str}'[v]")
            curr_v = "v"
        else:
            if curr_v != "v":
                # Đổi tên nhãn cuối cùng từ [v_logo] thành [v]
                last_filter = filter_chains.pop()
                last_filter = last_filter.replace(f"[{curr_v}]", "[v]")
                filter_chains.append(last_filter)
                curr_v = "v"

        filter_complex_str = ";".join(filter_chains)
        cmd.extend([
            "-filter_complex", filter_complex_str,
            "-map", "[v]",
            "-map", "1:a",
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "22",
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest",
            str(out_video)
        ])
    else:
        # Trường hợp không có phụ đề lẫn logo: copy thẳng luồng video để xuất cực nhanh
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
