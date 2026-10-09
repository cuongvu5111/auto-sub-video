"""
Module hòa âm (Audio Mixer) và đóng gói video hoàn thiện (FFmpeg).
Thực hiện kỹ thuật Audio Ducking (giảm âm lượng tiếng gốc làm nền, đè tiếng lồng tiếng Việt)
và nung phụ đề .ass tùy chọn vào khung hình video.
"""

import sys
import os
import subprocess
import math
import uuid
import wave
from pathlib import Path
from typing import Optional, Callable, List, Dict, Any, Union
from config import Config
from core.audio_extractor import find_ffmpeg
from core.tts_engine import get_audio_duration
from core.media_probe import probe_media, MediaProbeError
from core.process import run_process
from core.video_profiles import resolve_video_export_profile

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


def _validate_full_media_decode(media_path: Path, cancel_check=None) -> None:
    """Decode all streams so portrait exports are not published with truncated/corrupt packets."""
    try:
        import av
        video_frames = 0
        audio_frames = 0
        with av.open(str(media_path)) as container:
            expect_audio = bool(container.streams.audio)
            for packet in container.demux():
                if cancel_check and cancel_check():
                    raise InterruptedError("Video validation was cancelled before output publishing.")
                for _frame in packet.decode():
                    if packet.stream.type == "video":
                        video_frames += 1
                    elif packet.stream.type == "audio":
                        audio_frames += 1
        if video_frames <= 0:
            raise AudioMixerError("Rendered portrait video contains no decodable video frames.")
        if expect_audio and audio_frames <= 0:
            raise AudioMixerError("Rendered portrait video contains no decodable audio frames.")
    except InterruptedError:
        raise
    except AudioMixerError:
        raise
    except Exception as exc:
        raise AudioMixerError(f"Rendered portrait video failed full-stream decode validation: {exc}") from exc


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
    text_watermark: Optional[Dict[str, Any]] = None, # Cấu hình chèn text watermark
    play_res_x: int = 720,
    play_res_y: int = 1280,
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
PlayResX: {int(play_res_x)}
PlayResY: {int(play_res_y)}

{styles_section}
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = [header]

    # 1. Thêm các dòng phụ đề thoại (Layer 0)
    for seg in segments:
        text = _sanitize_ass_text(seg.get("translated_text", "").strip() or seg.get("text", "").strip())
        if not text:
            continue
        start_ts = format_ass_timestamp(seg.get("start", 0.0))
        end_ts = format_ass_timestamp(seg.get("end", 0.0))
        lines.append(f"Dialogue: 0,{start_ts},{end_ts},TikTokStyle,,0,0,0,,{text}\n")

    # 2. Thêm dòng Text Watermark nếu có (Layer 1)
    if has_text_wm:
        wm_text = _sanitize_ass_text(text_watermark.get("text", "").strip())
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

    # 4. Ngăn chặn pydub mở cửa sổ console phụ trên Windows khi gọi subprocess ffmpeg
    if sys.platform == "win32":
        class _SilentPopen(subprocess.Popen):
            """Class kế thừa chuẩn từ subprocess.Popen, tự động chèn CREATE_NO_WINDOW trên Windows."""
            def __init__(self, *args, **kwargs):
                kwargs.setdefault("creationflags", subprocess.CREATE_NO_WINDOW)
                super().__init__(*args, **kwargs)

        if hasattr(pydub.utils, "Popen"):
            pydub.utils.Popen = _SilentPopen


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
    original_audio_path: Optional[Path],
    segments: List[Dict[str, Any]],
    output_audio_path: Path,
    ducking_volume: float = 0.10,
    total_duration: Optional[float] = None,
    delay_offset: float = 0.0,
    cancel_check: Optional[Callable[[], bool]] = None,
) -> Path:
    """
    Hòa trộn âm thanh lồng tiếng vào âm thanh gốc (Kỹ thuật Audio Ducking):
    1. Giảm âm lượng âm thanh gốc xuống ducking_volume (ví dụ 10% để giữ nhạc nền/tiếng cười).
    2. Đặt các file thoại tiếng Việt vào đúng mốc start (ms) trên timeline.
    3. Trộn 2 track thành một file âm thanh hoàn thiện.
    """
    if cancel_check and cancel_check():
        raise InterruptedError("The audio mix was cancelled by the user.")
    try:
        from pydub import AudioSegment
    except ImportError:
        raise AudioMixerError("Thư viện pydub chưa được cài đặt. Vui lòng chạy: pip install pydub")

    _init_pydub()

    orig_path = Path(original_audio_path).resolve() if original_audio_path else None
    out_path = Path(output_audio_path).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if not math.isfinite(float(ducking_volume)) or not 0.0 <= float(ducking_volume) <= 1.0:
        raise AudioMixerError("Ducking volume must be a finite value between 0 and 1.")
    if not math.isfinite(float(delay_offset)):
        raise AudioMixerError("Audio delay must be a finite number.")
    if total_duration is not None and (not math.isfinite(float(total_duration)) or float(total_duration) <= 0):
        raise AudioMixerError("Video duration must be a finite positive number.")

    # Load the source once, but allocate working mix tracks one chunk at a time.
    if orig_path is not None:
        if not orig_path.exists():
            raise FileNotFoundError(f"Không tìm thấy file audio gốc: {original_audio_path}")
        orig_audio = _load_audio_file(orig_path)
    elif total_duration is not None and total_duration > 0:
        orig_audio = AudioSegment.silent(duration=int(round(total_duration * 1000)), frame_rate=24000)
        orig_audio = orig_audio.set_channels(1).set_sample_width(2)
    else:
        raise FileNotFoundError(f"Không tìm thấy file audio gốc: {original_audio_path}")

    final_length = len(orig_audio)
    if total_duration is not None:
        final_length = int(round(float(total_duration) * 1000))
        if len(orig_audio) > final_length:
            orig_audio = orig_audio[:final_length]
        elif len(orig_audio) < final_length:
            silence = AudioSegment.silent(duration=final_length - len(orig_audio), frame_rate=orig_audio.frame_rate)
            silence = silence.set_channels(orig_audio.channels).set_sample_width(orig_audio.sample_width)
            orig_audio += silence

    mix_frame_rate = max(orig_audio.frame_rate, 24000)
    mix_channels = orig_audio.channels
    mix_sample_width = max(orig_audio.sample_width, 2)
    mix_segments = []
    for seg in segments:
        if cancel_check and cancel_check():
            raise InterruptedError("The audio mix was cancelled by the user.")
        dubbed_file = seg.get("dubbed_audio_path")
        if not dubbed_file or not Path(dubbed_file).exists():
            continue

        source_fallback = (
            seg.get("tts_status") == "translation_fallback_source_audio"
            or seg.get("sync_status") == "failed_silence_fallback"
            or seg.get("tts_status") == "failed_silence_fallback"
        )
        try:
            start_seconds = float(seg.get("start", 0.0))
            if not math.isfinite(start_seconds) or start_seconds < 0:
                raise ValueError
        except (TypeError, ValueError):
            raise AudioMixerError(f"Invalid start timestamp in dubbed segment {seg.get('index', '?')}.")

        if source_fallback:
            try:
                source_end = float(seg.get("end", start_seconds + (seg.get("dubbed_duration") or 0.0)))
                if not math.isfinite(source_end):
                    raise ValueError
                source_length_ms = max(0, int(round((source_end - start_seconds) * 1000)))
            except (TypeError, ValueError):
                try:
                    source_length_ms = int(round(float(seg.get("dubbed_duration") or 0.0) * 1000))
                except (TypeError, ValueError):
                    source_length_ms = 0
            start_ms = int(round(start_seconds * 1000))
            source_length_ms = min(source_length_ms, max(0, final_length - start_ms))
            if source_length_ms > 0:
                mix_segments.append({
                    "source_fallback": True,
                    "start_ms": start_ms,
                    "duration_ms": source_length_ms,
                })
            continue

        shifted_start = start_seconds + float(delay_offset)
        if not math.isfinite(shifted_start):
            raise AudioMixerError(f"Invalid shifted timestamp in dubbed segment {seg.get('index', '?')}.")
        start_ms = max(0, int(round(shifted_start * 1000)))
        if start_ms >= final_length:
            continue
        mix_segments.append({
            "source_fallback": False,
            "path": Path(dubbed_file).resolve(),
            "start_ms": start_ms,
            "trim_ms": max(0, int(round(-shifted_start * 1000))),
            "duration_ms": None,
        })

    temp_wav = out_path.with_name(f".{out_path.stem}.{uuid.uuid4().hex}.tmp.wav")
    temp_encoded = out_path.with_name(f".{out_path.stem}.{uuid.uuid4().hex}.tmp{out_path.suffix}")
    chunk_size_ms = 10_000
    db_change = 20 * math.log10(max(0.01, float(ducking_volume))) if ducking_volume > 0 else None

    try:
        with wave.open(str(temp_wav), "wb") as rendered:
            rendered.setnchannels(mix_channels)
            rendered.setsampwidth(mix_sample_width)
            rendered.setframerate(mix_frame_rate)

            for chunk_start in range(0, final_length, chunk_size_ms):
                if cancel_check and cancel_check():
                    raise InterruptedError("The audio mix was cancelled by the user.")

                chunk_end = min(final_length, chunk_start + chunk_size_ms)
                source_chunk = orig_audio[chunk_start:chunk_end]
                source_chunk = source_chunk.set_frame_rate(mix_frame_rate)
                source_chunk = source_chunk.set_channels(mix_channels).set_sample_width(mix_sample_width)
                chunk_length = len(source_chunk)
                if db_change is not None:
                    background_track = source_chunk + db_change
                else:
                    background_track = AudioSegment.silent(
                        duration=chunk_length,
                        frame_rate=mix_frame_rate,
                    ).set_channels(mix_channels).set_sample_width(mix_sample_width)

                speech_track = AudioSegment.silent(
                    duration=chunk_length,
                    frame_rate=mix_frame_rate,
                ).set_channels(mix_channels).set_sample_width(mix_sample_width)

                for mix_segment in mix_segments:
                    if cancel_check and cancel_check():
                        raise InterruptedError("The audio mix was cancelled by the user.")

                    segment_start = mix_segment["start_ms"]
                    if segment_start >= chunk_end:
                        continue

                    if mix_segment["source_fallback"]:
                        segment_end = min(final_length, segment_start + mix_segment["duration_ms"])
                        if segment_end <= chunk_start:
                            continue
                        overlap_start = max(chunk_start, segment_start)
                        overlap_end = min(chunk_end, segment_end)
                        source_segment = orig_audio[overlap_start:overlap_end]
                        source_segment = source_segment.set_frame_rate(mix_frame_rate)
                        source_segment = source_segment.set_channels(mix_channels).set_sample_width(mix_sample_width)
                        if len(source_segment):
                            speech_track = speech_track.overlay(
                                source_segment,
                                position=overlap_start - chunk_start,
                            )
                        continue

                    segment_duration = mix_segment["duration_ms"]
                    if segment_duration is not None and segment_start + segment_duration <= chunk_start:
                        continue

                    segment_audio = _load_audio_file(mix_segment["path"])
                    trim_ms = mix_segment["trim_ms"]
                    if trim_ms:
                        segment_audio = segment_audio[trim_ms:]
                    segment_audio = segment_audio.set_frame_rate(mix_frame_rate)
                    segment_audio = segment_audio.set_channels(mix_channels).set_sample_width(mix_sample_width)
                    if segment_start + len(segment_audio) > final_length:
                        segment_audio = segment_audio[:final_length - segment_start]
                    mix_segment["duration_ms"] = len(segment_audio)

                    segment_end = segment_start + len(segment_audio)
                    if segment_end <= chunk_start:
                        continue
                    overlap_start = max(chunk_start, segment_start)
                    overlap_end = min(chunk_end, segment_end)
                    segment_piece = segment_audio[
                        overlap_start - segment_start:overlap_end - segment_start
                    ]
                    if len(segment_piece):
                        speech_track = speech_track.overlay(
                            segment_piece,
                            position=overlap_start - chunk_start,
                        )

                if cancel_check and cancel_check():
                    raise InterruptedError("The audio mix was cancelled by the user.")
                mixed_chunk = background_track.overlay(speech_track)
                rendered.writeframesraw(mixed_chunk.raw_data)

        if out_path.suffix.lower() == ".wav":
            os.replace(temp_wav, out_path)
        else:
            cmd = [find_ffmpeg(), "-y", "-i", str(temp_wav), "-vn"]
            if out_path.suffix.lower() == ".mp3":
                cmd.extend(["-b:a", "192k"])
            cmd.append(str(temp_encoded))
            run_process(
                cmd,
                timeout=Config.FFMPEG_TIMEOUT,
                cancel_check=cancel_check,
                check=True,
            )
            if not temp_encoded.exists() or temp_encoded.stat().st_size <= 0:
                raise AudioMixerError("FFmpeg did not produce a valid mixed audio file.")
            os.replace(temp_encoded, out_path)
    except InterruptedError:
        raise
    except subprocess.CalledProcessError as exc:
        error_msg = exc.stderr[-300:] if exc.stderr else str(exc)
        raise AudioMixerError(f"Failed to encode the mixed audio: {error_msg}") from exc
    except TimeoutError as exc:
        raise AudioMixerError(str(exc)) from exc
    finally:
        temp_wav.unlink(missing_ok=True)
        temp_encoded.unlink(missing_ok=True)

    return out_path


def _reserve_output_path(requested_path: Path) -> Path:
    """Reserve a unique output name without replacing an existing result."""
    base = requested_path
    counter = 1
    while True:
        candidate = base if counter == 1 else base.with_name(f"{base.stem}_{counter}{base.suffix}")
        try:
            descriptor = os.open(str(candidate), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o666)
            os.close(descriptor)
            return candidate
        except FileExistsError:
            counter += 1


def _sanitize_ass_text(value: Any) -> str:
    """Prevent newlines and override syntax from escaping an ASS dialogue field."""
    text = str(value or "").replace("\r\n", " ").replace("\r", " ").replace("\n", " ")
    return text.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")


def render_final_video(
    original_video_path: Path,
    mixed_audio_path: Optional[Path],
    output_video_path: Path,
    ass_subtitle_path: Optional[Path] = None,
    watermark_options: Optional[Dict[str, Any]] = None,
    encoder: Optional[str] = None,
    progress_callback: Optional[Callable[[str, float], None]] = None,
    cancel_check: Optional[Callable[[], bool]] = None,
    export_profile: Optional[Dict[str, Any]] = None,
) -> Path:
    """
    Đóng gói video hoàn thiện bằng FFmpeg:
    - Nếu có mixed_audio_path: Thay thế track âm thanh gốc bằng track âm thanh đã hòa âm (có lồng tiếng).
    - Nếu mixed_audio_path là None: Giữ nguyên 100% âm thanh gốc của video.
    - Nung phụ đề .ass trực tiếp vào khung hình (nếu có yêu cầu).
    - Chèn Logo Watermark (vị trí tùy biến, độ mờ Opacity, tự động co tỉ lệ).
    - Tự động dùng bộ mã hóa phần cứng h264_nvenc nếu có GPU NVIDIA, tự động fallback về libx264 nếu lỗi.
    """
    orig_video = Path(original_video_path).resolve()
    out_video = Path(output_video_path).resolve()
    out_video.parent.mkdir(parents=True, exist_ok=True)
    render_temp = out_video.with_name(f"{out_video.stem}.{uuid.uuid4().hex}.partial{out_video.suffix}")

    if not orig_video.exists():
        raise FileNotFoundError(f"Không tìm thấy video gốc: {original_video_path}")

    has_mixed_audio = False
    mixed_audio = None
    if mixed_audio_path:
        candidate_audio = Path(mixed_audio_path).resolve()
        if candidate_audio.exists():
            mixed_audio = candidate_audio
            has_mixed_audio = True
        else:
            raise FileNotFoundError(f"Không tìm thấy file audio đã hòa âm: {mixed_audio_path}")

    ffmpeg_bin = find_ffmpeg()

    if progress_callback:
        action_msg = "Đang tiến hành ghép âm thanh và xuất video thành phẩm..." if has_mixed_audio else "Đang nung phụ đề và xuất video (giữ âm thanh gốc)..."
        progress_callback(action_msg, 70.0)

    has_sub = bool(ass_subtitle_path and Path(ass_subtitle_path).exists())
    profile = resolve_video_export_profile(export_profile)
    has_profile_transform = profile.transforms_video

    # Kiểm tra cấu hình Logo Watermark
    has_logo = False
    logo_path = None
    if watermark_options:
        candidate_path = watermark_options.get("logo_path")
        logo_flag = watermark_options.get("logo_enabled")
        is_enabled = logo_flag if logo_flag is not None else bool(candidate_path)
        if is_enabled and candidate_path and Path(candidate_path).exists():
            has_logo = True
            logo_path = Path(candidate_path).resolve()

    # Xác định bộ mã hóa video phù hợp
    hw = Config.detect_hardware_capabilities()
    enc_lower = (encoder or "").lower()
    if not encoder or enc_lower.startswith("auto"):
        target_encoder = "h264_nvenc" if hw["has_nvenc"] else "libx264"
    elif "nvenc" in enc_lower:
        target_encoder = "h264_nvenc"
    elif "copy" in enc_lower and not (has_sub or has_logo or has_profile_transform):
        target_encoder = "copy"
    else:
        target_encoder = "libx264"

    if has_sub or has_logo or has_profile_transform:
        # Trường hợp cần xử lý hình ảnh qua filter_complex
        cmd = [
            ffmpeg_bin,
            "-y",
            "-i", str(orig_video)
        ]
        if has_mixed_audio:
            cmd.extend(["-i", str(mixed_audio)])

        filter_chains = []
        curr_v = "0:v"

        if has_profile_transform:
            target_w = profile.width
            target_h = profile.height
            if profile.fit_mode == "crop":
                filter_chains.append(
                    f"[0:v]scale={target_w}:{target_h}:force_original_aspect_ratio=increase,"
                    f"crop={target_w}:{target_h},setsar=1[v_profile]"
                )
            else:
                filter_chains.append(
                    f"[0:v]scale={target_w}:{target_h}:force_original_aspect_ratio=decrease,"
                    f"pad={target_w}:{target_h}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1[v_profile]"
                )
            curr_v = "v_profile"

        if has_logo:
            cmd.extend(["-i", str(logo_path)])
            # Xác định index của luồng logo
            # Nếu có mixed_audio (input 1) -> logo là index 2:v
            # Nếu không có mixed_audio -> logo là index 1:v
            logo_input_idx = 2 if has_mixed_audio else 1
            opacity = float(watermark_options.get("logo_opacity", 0.8))
            opacity = max(0.05, min(1.0, opacity))
            max_w = int(watermark_options.get("logo_max_width", 160))
            max_w = max(10, min(1920, max_w))

            pos_key = str(watermark_options.get("logo_position", "top-right")).lower().replace(" ", "-")
            pos_expr_map = {
                "top-right": "main_w-overlay_w-24:24",
                "top-left": "24:24",
                "bottom-right": "main_w-overlay_w-24:main_h-overlay_h-24",
                "bottom-left": "24:main_h-overlay_h-24",
                "center": "(main_w-overlay_w)/2:(main_h-overlay_h)/2"
            }
            pos_expr = pos_expr_map.get(pos_key, "main_w-overlay_w-24:24")

            filter_chains.append(f"[{logo_input_idx}:v]scale={max_w}:-1,format=rgba,colorchannelmixer=aa={opacity:.2f}[logo]")
            filter_chains.append(f"[{curr_v}][logo]overlay={pos_expr}[v_logo]")
            curr_v = "v_logo"

        if has_sub:
            ass_path_str = str(Path(ass_subtitle_path).resolve()).replace("\\", "/")
            # Cú pháp filter của FFmpeg cần escape dấu hai chấm ổ đĩa và dấu nháy.
            ass_path_str = ass_path_str.replace(":", "\\:").replace("'", "\\'")
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

        if target_encoder == "h264_nvenc":
            video_codec_args = ["-c:v", "h264_nvenc", "-preset", "p4", "-cq", "22"]
        else:
            video_codec_args = ["-c:v", "libx264", "-preset", "fast", "-crf", "22"]

        if has_mixed_audio:
            audio_map_args = ["-map", "1:a", "-c:a", "aac", "-b:a", "192k", "-shortest"]
        else:
            # Giữ nguyên âm thanh gốc: map từ 0:a?
            audio_map_args = ["-map", "0:a?", "-c:a", "aac", "-b:a", "192k"]

        cmd.extend([
            "-filter_complex", filter_complex_str,
            "-map", "[v]",
            *audio_map_args,
            *video_codec_args,
            str(render_temp)
        ])
    else:
        # Trường hợp không có phụ đề lẫn logo
        if has_mixed_audio:
            if target_encoder == "copy":
                no_filter_video_args = ["-c:v", "copy"]
            elif target_encoder == "h264_nvenc":
                no_filter_video_args = ["-c:v", "h264_nvenc", "-preset", "p4", "-cq", "22"]
            else:
                no_filter_video_args = ["-c:v", "libx264", "-preset", "fast", "-crf", "22"]
            cmd = [
                ffmpeg_bin,
                "-y",
                "-i", str(orig_video),
                "-i", str(mixed_audio),
                "-map", "0:v:0",
                "-map", "1:a:0",
                *no_filter_video_args,
                "-c:a", "aac",
                "-b:a", "192k",
                "-shortest",
                str(render_temp)
            ]
        else:
            if target_encoder == "copy":
                no_filter_video_args = ["-c:v", "copy", "-c:a", "copy"]
            elif target_encoder == "h264_nvenc":
                no_filter_video_args = ["-c:v", "h264_nvenc", "-preset", "p4", "-cq", "22", "-c:a", "aac", "-b:a", "192k"]
            else:
                no_filter_video_args = ["-c:v", "libx264", "-preset", "fast", "-crf", "22", "-c:a", "aac", "-b:a", "192k"]
            cmd = [
                ffmpeg_bin,
                "-y",
                "-i", str(orig_video),
                "-map", "0:v:0",
                "-map", "0:a?",
                *no_filter_video_args,
                str(render_temp)
            ]

    def run_ffmpeg_cancellable(exec_cmd):
        return run_process(
            exec_cmd,
            timeout=Config.FFMPEG_TIMEOUT,
            cancel_check=cancel_check,
            check=True,
        )

    def validate_and_publish() -> Path:
        if cancel_check and cancel_check():
            raise InterruptedError("The video render was cancelled before publishing the output.")
        if not render_temp.exists() or render_temp.stat().st_size == 0:
            raise AudioMixerError("FFmpeg did not create a non-empty temporary video.")
        try:
            source_info = probe_media(orig_video)
            output_info = probe_media(render_temp)
        except MediaProbeError as exc:
            raise AudioMixerError(f"Could not validate rendered video: {exc}") from exc

        expected_audio = has_mixed_audio or source_info.has_audio
        if expected_audio and not output_info.has_audio:
            raise AudioMixerError("Rendered video is missing its required audio stream.")
        if has_profile_transform and (output_info.width, output_info.height) != (profile.width, profile.height):
            raise AudioMixerError(
                f"Rendered dimensions {output_info.width}x{output_info.height} do not match requested "
                f"profile {profile.width}x{profile.height}."
            )
        if has_profile_transform and output_info.video_codec != "h264":
            raise AudioMixerError(
                f"Portrait export must use H.264 video; received {output_info.video_codec or 'unknown'}."
            )
        if has_profile_transform and output_info.has_audio and output_info.audio_codec != "aac":
            raise AudioMixerError(
                f"Portrait export must use AAC audio when audio is present; received "
                f"{output_info.audio_codec or 'unknown'}."
            )
        if has_profile_transform:
            _validate_full_media_decode(render_temp, cancel_check=cancel_check)
        fps = source_info.frame_rate or 24.0
        duration_tolerance = max(0.15, 2.0 / fps)
        if abs(output_info.duration - source_info.duration) > duration_tolerance:
            raise AudioMixerError(
                f"Rendered duration {output_info.duration:.3f}s differs from source "
                f"{source_info.duration:.3f}s by more than {duration_tolerance:.3f}s."
            )

        published_path = _reserve_output_path(out_video)
        try:
            os.replace(render_temp, published_path)
        except Exception:
            published_path.unlink(missing_ok=True)
            raise
        return published_path

    def make_cpu_fallback(exec_cmd):
        fallback = []
        index = 0
        while index < len(exec_cmd):
            if exec_cmd[index:index + 2] == ["-c:v", "h264_nvenc"]:
                fallback.extend(["-c:v", "libx264", "-preset", "fast", "-crf", "22"])
                index += 6
            elif exec_cmd[index:index + 2] == ["-c:v", "copy"]:
                fallback.extend(["-c:v", "libx264", "-preset", "fast", "-crf", "22"])
                index += 2
            elif exec_cmd[index:index + 2] == ["-c:a", "copy"]:
                fallback.extend(["-c:a", "aac", "-b:a", "192k"])
                index += 2
            else:
                fallback.append(exec_cmd[index])
                index += 1
        return fallback

    try:
        run_ffmpeg_cancellable(cmd)
        result_path = validate_and_publish()
        if progress_callback:
            progress_callback(f"Xuất video hoàn tất: {result_path.name}", 100.0)
        return result_path
    except subprocess.CalledProcessError as primary_error:
        should_fallback = target_encoder == "h264_nvenc" or target_encoder == "copy"
        if should_fallback:
            render_temp.unlink(missing_ok=True)
            fallback_cmd = make_cpu_fallback(cmd)
            try:
                run_ffmpeg_cancellable(fallback_cmd)
                result_path = validate_and_publish()
                if progress_callback:
                    progress_callback(f"Xuất video hoàn tất (CPU fallback): {result_path.name}", 100.0)
                return result_path
            except InterruptedError:
                raise
            except subprocess.CalledProcessError as fallback_error:
                error_source = fallback_error
            except AudioMixerError:
                raise
        else:
            error_source = primary_error

        error_msg = error_source.stderr[-400:] if error_source.stderr else str(error_source)
        raise AudioMixerError(f"Lỗi khi render video bằng FFmpeg: {error_msg}") from error_source
    except TimeoutError as exc:
        raise AudioMixerError(str(exc)) from exc
    finally:
        render_temp.unlink(missing_ok=True)
