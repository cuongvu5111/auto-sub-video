"""
Pipeline điều phối toàn trình (End-to-End Orchestrator) cho AutoSub Dubbing Studio.
Kết nối tuần tự: Tải video -> Tách âm -> Phiên âm -> Dịch thuật -> Lồng tiếng -> Hòa âm & Render.
"""

import sys
import argparse
import math
import time
from pathlib import Path
from typing import Optional, Callable, Dict, Any
from config import Config

# Cấu hình encoding UTF-8 nếu chạy trên Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

from core.downloader import download_video
from core.audio_extractor import extract_audio
from core.job_workspace import cleanup_job_workspace, create_job_workspace
from core.job_result import JobResult, JobStatus
from core.media_probe import validate_video_input
from core.transcriber import transcribe_audio
from core.translator import translate_segments
from core.tts_engine import process_dubbing_segments
from core.audio_mixer import generate_ass_file, create_mixed_audio_track, render_final_video
from core.subtitles import parse_srt
from core.video_profiles import ass_play_resolution, resolve_video_export_profile


def _normalize_segments(segments, duration: float, warning_callback=None):
    """Validate the segment contract and keep all dialogue inside the video timeline."""
    normalized = []
    seen_indexes = set()
    previous_start = -1.0
    clipped_count = 0
    dropped_count = 0

    for ordinal, segment in enumerate(segments):
        try:
            start = float(segment["start"])
            end = float(segment["end"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"Subtitle segment {ordinal + 1} has invalid timestamps.") from exc
        if not (math.isfinite(start) and math.isfinite(end)) or start < 0 or end <= start:
            raise ValueError(f"Subtitle segment {ordinal + 1} must have finite timestamps with 0 <= start < end.")
        if start < previous_start:
            raise ValueError(f"Subtitle segment {ordinal + 1} is out of chronological order.")
        previous_start = start

        index = segment.get("index", ordinal)
        try:
            duplicate = index in seen_indexes
            seen_indexes.add(index)
        except TypeError as exc:
            raise ValueError(f"Subtitle segment {ordinal + 1} has an invalid index.") from exc
        if duplicate:
            raise ValueError(f"Subtitle segment index {index!r} is duplicated.")

        text = str(segment.get("text", "")).strip()
        if not text:
            raise ValueError(f"Subtitle segment {index!r} has no text.")
        if start >= duration:
            dropped_count += 1
            continue

        normalized_segment = dict(segment)
        normalized_segment.update({"index": index, "start": start, "end": min(end, duration), "text": text})
        if end > duration:
            clipped_count += 1
        normalized.append(normalized_segment)

    if warning_callback and (clipped_count or dropped_count):
        warning_callback(
            f"Warning: subtitle timing was adjusted to the video duration "
            f"(clipped {clipped_count}, removed {dropped_count} out-of-range segment(s)).",
            39.0,
        )
    return normalized


def _shift_subtitle_segments(segments, delay_offset: float, duration: float):
    """Shift translated captions with dubbed speech while keeping source fallbacks aligned."""
    shifted = []
    for segment in segments:
        preserves_source_audio = (
            segment.get("translation_status") == "source_fallback"
            or segment.get("tts_status") == "failed_silence_fallback"
            or segment.get("sync_status") == "failed_silence_fallback"
        )
        offset = 0.0 if preserves_source_audio else delay_offset
        start = max(0.0, float(segment["start"]) + offset)
        end = min(duration, float(segment["end"]) + offset)
        if start >= duration or end <= start:
            continue
        shifted_segment = dict(segment)
        shifted_segment.update({"start": start, "end": end})
        shifted.append(shifted_segment)
    return shifted


def _run_pipeline(
    source: str,
    source_lang: Optional[str] = "auto",
    voice: Optional[str] = None,
    ducking_volume: float = 0.10,
    burn_subtitles: bool = True,
    genre: str = "Daily Life / Social Media",
    custom_terms: str = "",
    subtitle_options: Optional[Dict[str, Any]] = None,
    watermark_options: Optional[Dict[str, Any]] = None,
    encoder: Optional[str] = None,
    output_dir: Optional[Path] = None,
    enable_dubbing: bool = True,
    progress_callback: Optional[Callable[[str, float], None]] = None,
    cancel_check: Optional[Callable[[], bool]] = None,
    workspace_dir: Optional[Path] = None,
    subtitle_path: Optional[Path] = None,
    prefer_attached_subtitle: bool = True,
    translate_srt_only: bool = False,
    delay_offset: float = 0.0,
    export_profile: Optional[Dict[str, Any]] = None,
) -> Path:
    """
    Điều phối toàn bộ luồng xử lý tự động từ Video nguồn (Link/Tệp) ra Video thành phẩm.

    Args:
        source: URL mạng xã hội (TikTok, Douyin,...) hoặc tệp MP4 cục bộ.
        voice: Giọng đọc (mặc định từ Config.DEFAULT_VOICE).
        ducking_volume: Âm lượng tiếng gốc khi lồng tiếng (0.05 đến 0.20).
        burn_subtitles: True nếu muốn nung chữ phụ đề vào khung hình video.
        genre: Thể loại nội dung phục vụ LLM dịch thuật.
        custom_terms: Quy tắc từ khóa hoặc tên riêng cố định.
        subtitle_options: Tùy chỉnh màu sắc, cỡ chữ, căn chỉnh vị trí (margin_v, alignment).
        watermark_options: Tùy chỉnh Text Watermark (giữa video) và Logo Watermark (ảnh, opacity).
        encoder: Bộ mã hóa phần cứng (h264_nvenc, libx264,...).
        output_dir: Thư mục lưu video thành phẩm.
        progress_callback: Hàm nhận (thông điệp, phần trăm tiến độ tổng thể).
        cancel_check: Hàm kiểm tra xem người dùng có yêu cầu dừng tiến trình hay không.

    Returns:
        Path: Đường dẫn video thành phẩm đã được lồng tiếng Việt và gắn phụ đề.
    """
    workspace_dir = Path(workspace_dir or Config.TEMP_DIR).resolve()
    target_out_dir = Path(output_dir or Config.OUTPUT_DIR).resolve()
    target_out_dir.mkdir(parents=True, exist_ok=True)
    stage_timings = {}

    def measure_stage(stage_name: str, operation: Callable, *args, **kwargs):
        started_at = time.perf_counter()
        try:
            return operation(*args, **kwargs)
        finally:
            stage_timings[stage_name] = time.perf_counter() - started_at

    def check_cancel():
        if cancel_check and cancel_check():
            raise InterruptedError("Tiến trình đã bị dừng bởi người dùng.")

    def report(msg: str, percent: float):
        check_cancel()
        if progress_callback:
            progress_callback(msg, percent)
        else:
            print(f"[{percent:5.1f}%] {msg}")

    check_cancel()
    profile = resolve_video_export_profile(export_profile)
    subtitle_segments = None
    if translate_srt_only and not subtitle_path:
        raise ValueError("Translate SRT only is enabled, but no SRT file is attached to this video.")
    if subtitle_path and (translate_srt_only or prefer_attached_subtitle):
        subtitle_segments = measure_stage("SRT parsing", parse_srt, subtitle_path)

    # STEP 1: Download or load local video
    report("Step 1/6: Preparing and loading input video...", 5.0)
    video_path = measure_stage(
        "download/load",
        download_video,
        source,
        output_dir=workspace_dir,
        progress_callback=lambda m, p: report(f"Step 1/6: {m}", 5.0 + p * 0.15),
        cancel_check=cancel_check
    )

    check_cancel()

    use_attached_subtitle = subtitle_segments is not None
    media_info = measure_stage(
        "media preflight",
        validate_video_input,
        video_path,
        require_audio=not use_attached_subtitle,
    )
    report(
        f"Input validated: {media_info.duration:.2f}s, {media_info.width or '?'}x{media_info.height or '?'}, "
        f"audio={media_info.has_audio}",
        19.0
    )
    if profile.transforms_video and media_info.width and media_info.height:
        if profile.fit_mode == "crop":
            upscale_factor = max(profile.width / media_info.width, profile.height / media_info.height)
        else:
            upscale_factor = min(profile.width / media_info.width, profile.height / media_info.height)
        if upscale_factor > 1.01:
            report(
                f"Warning: portrait export will upscale source pixels by about {upscale_factor:.2f}x; "
                "this changes output dimensions but does not add image detail.",
                19.1,
            )

    whisper_lang = None if (not source_lang or source_lang.lower() in ("auto", "none")) else source_lang.lower()
    raw_audio_path = None
    if media_info.has_audio and (enable_dubbing or not use_attached_subtitle):
        report("Step 2/6: Extracting audio from video...", 20.0)
        raw_audio_path = workspace_dir / "source_audio.wav"
        measure_stage("audio extraction", extract_audio, video_path, raw_audio_path, cancel_check=cancel_check)

    check_cancel()

    # STEP 3: Use timed SRT entries or run speech recognition.
    if use_attached_subtitle:
        report(f"Step 3/6: Loaded {len(subtitle_segments)} timed SRT entries...", 35.0)
        segments = subtitle_segments
    else:
        if raw_audio_path is None:
            raise ValueError("Speech transcription requires an audio stream in the input video.")
        report("Step 3/6: Transcribing speech and timestamps with Whisper...", 35.0)
        segments = measure_stage(
            "Whisper transcription",
            transcribe_audio,
            raw_audio_path,
            language=whisper_lang,
            word_timestamps=Config.WHISPER_WORD_TIMESTAMPS,
            progress_callback=lambda m, p: report(f"Step 3/6: {m}", 35.0 + p * 0.15),
            cancel_check=cancel_check,
        )

    if not segments:
        raise ValueError("No speech or dialogue detected in this video.")
    segments = _normalize_segments(segments, media_info.duration, warning_callback=report)
    if not segments:
        raise ValueError("No speech or dialogue falls within the video duration.")

    check_cancel()

    # STEP 4: Contextual LLM translation
    report("Step 4/6: Translating dialogues with LLM...", 55.0)
    translated_segments = measure_stage(
        "LLM translation",
        translate_segments,
        segments,
        source_lang="Chinese" if whisper_lang == "zh" else "Original Language",
        target_lang="Vietnamese",
        genre=genre,
        custom_terms=custom_terms,
        progress_callback=lambda m, p: report(f"Step 4/6: {m}", 55.0 + p * 0.10),
        cancel_check=cancel_check
    )

    check_cancel()

    # STEP 5: AI voice synthesis and atempo synchronization
    if enable_dubbing:
        report("Step 5/6: Synthesizing AI voice dubbing and syncing tempo...", 68.0)
        dubbed_segments = measure_stage(
            "TTS and tempo sync",
            process_dubbing_segments,
            translated_segments,
            voice=voice,
            output_dir=workspace_dir / "dubbing_segments",
            progress_callback=lambda m, p: report(f"Step 5/6: {m}", 68.0 + p * 0.17),
            cancel_check=cancel_check
        )
    else:
        report("Step 5/6: AI voice dubbing disabled. Preserving original video audio...", 75.0)
        dubbed_segments = translated_segments

    check_cancel()

    # STEP 6: Audio ducking and video rendering
    if enable_dubbing:
        report("Step 6/6: Mixing audio and rendering final video...", 88.0)
        # 6a. Create mixed audio track
        mixed_audio_file = workspace_dir / "mixed_audio.wav"
        measure_stage(
            "audio mix",
            create_mixed_audio_track,
            raw_audio_path,
            dubbed_segments,
            mixed_audio_file,
            ducking_volume=ducking_volume,
            total_duration=media_info.duration,
            delay_offset=delay_offset,
            cancel_check=cancel_check
        )
    else:
        report("Step 6/6: Burning subtitles and rendering with original audio...", 88.0)
        mixed_audio_file = None

    check_cancel()

    # 6b. Generate ASS subtitle file if requested (or if text watermark enabled)
    ass_file = None
    sub_opts = subtitle_options or {}
    wm_opts = watermark_options or {}
    target_width = profile.width if profile.transforms_video else (media_info.width or 720)
    target_height = profile.height if profile.transforms_video else (media_info.height or 1280)
    play_res_x, play_res_y = ass_play_resolution(target_width, target_height)

    text_wm_config = None
    if wm_opts.get("text_enabled", False) and wm_opts.get("text", "").strip():
        text_wm_config = {
            "enabled": True,
            "text": wm_opts.get("text", "").strip(),
            "timing_mode": wm_opts.get("text_timing", "mid_video"),
            "position": wm_opts.get("text_position", "center"),
            "font_size": wm_opts.get("text_font_size", 22)
        }

    if burn_subtitles or text_wm_config:
        ass_file = workspace_dir / "subtitles.ass"
        subtitle_delay = delay_offset if enable_dubbing else 0.0
        subtitle_segments = _shift_subtitle_segments(dubbed_segments, subtitle_delay, media_info.duration)
        measure_stage(
            "subtitle generation",
            generate_ass_file,
            subtitle_segments if burn_subtitles else [],
            ass_file,
            font_name=sub_opts.get("font_name", "Arial"),
            font_size=sub_opts.get("font_size", 46),
            primary_color=sub_opts.get("primary_color", "&H00000000"),
            outline_color=sub_opts.get("outline_color", "&H00FFFFFF"),
            back_color=sub_opts.get("back_color", "&H00FFFFFF"),
            border_style=sub_opts.get("border_style", 3),
            outline_width=sub_opts.get("outline_width", 6),
            shadow_width=sub_opts.get("shadow_width", 0),
            margin_v=sub_opts.get("margin_v", 40),
            alignment=sub_opts.get("alignment", 2),
            box_padding=sub_opts.get("box_padding"),
            total_duration=media_info.duration,
            text_watermark=text_wm_config,
            play_res_x=play_res_x,
            play_res_y=play_res_y
        )

    check_cancel()

    # 6c. Render finalized video
    final_video_name = f"{video_path.stem}_vi.mp4"
    final_video_path = target_out_dir / final_video_name

    final_video_path = measure_stage(
        "video rendering",
        render_final_video,
        video_path,
        mixed_audio_file,
        final_video_path,
        ass_subtitle_path=ass_file,
        watermark_options=wm_opts,
        encoder=encoder,
        progress_callback=lambda m, p: report(f"Step 6/6: {m}", 90.0 + p * 0.10),
        cancel_check=cancel_check,
        export_profile=export_profile,
    )


    timing_summary = ", ".join(
        f"{stage}={elapsed:.2f}s" for stage, elapsed in stage_timings.items()
    )
    completion_message = (
        f"Pipeline completed! Video successfully saved to: {final_video_path}. "
        f"Stage timings: {timing_summary}"
    )
    if progress_callback:
        progress_callback(completion_message, 100.0)
    else:
        print(f"[100.0%] {completion_message}")
    return final_video_path


def run_pipeline(
    source: str,
    source_lang: Optional[str] = "auto",
    voice: Optional[str] = None,
    ducking_volume: float = 0.10,
    burn_subtitles: bool = True,
    genre: str = "Daily Life / Social Media",
    custom_terms: str = "",
    subtitle_options: Optional[Dict[str, Any]] = None,
    watermark_options: Optional[Dict[str, Any]] = None,
    encoder: Optional[str] = None,
    output_dir: Optional[Path] = None,
    enable_dubbing: bool = True,
    progress_callback: Optional[Callable[[str, float], None]] = None,
    cancel_check: Optional[Callable[[], bool]] = None,
    subtitle_path: Optional[Path] = None,
    prefer_attached_subtitle: bool = True,
    translate_srt_only: bool = False,
    delay_offset: float = 0.0,
    export_profile: Optional[Dict[str, Any]] = None,
) -> Path:
    """Run one job in an isolated workspace and clean it up on every exit path."""
    workspace_dir = create_job_workspace()
    try:
        return _run_pipeline(
            source=source,
            source_lang=source_lang,
            voice=voice,
            ducking_volume=ducking_volume,
            burn_subtitles=burn_subtitles,
            genre=genre,
            custom_terms=custom_terms,
            subtitle_options=subtitle_options,
            watermark_options=watermark_options,
            encoder=encoder,
            output_dir=output_dir,
            enable_dubbing=enable_dubbing,
            progress_callback=progress_callback,
            cancel_check=cancel_check,
            workspace_dir=workspace_dir,
            subtitle_path=subtitle_path,
            prefer_attached_subtitle=prefer_attached_subtitle,
            translate_srt_only=translate_srt_only,
            delay_offset=delay_offset,
            export_profile=export_profile,
        )
    finally:
        if not Config.KEEP_INTERMEDIATES:
            try:
                cleanup_job_workspace(workspace_dir)
            except OSError as exc:
                import logging
                if progress_callback:
                    try:
                        progress_callback(f"Warning: could not clean temporary job files: {exc}", 99.0)
                    except Exception:
                        logging.getLogger(__name__).warning("Could not clean temporary job files: %s", exc)
                else:
                    logging.getLogger(__name__).warning("Could not clean temporary job files: %s", exc)


def run_pipeline_job(
    source: str,
    *,
    progress_callback: Optional[Callable[[str, float], None]] = None,
    cancel_check: Optional[Callable[[], bool]] = None,
    **pipeline_options,
) -> JobResult:
    """Return a typed terminal state while preserving the exception-based API."""
    warnings = []

    def report(message: str, percent: float) -> None:
        lower_message = message.lower()
        if "⚠" in message or "warning" in lower_message or "cảnh báo" in lower_message:
            warnings.append(message)
        if progress_callback:
            progress_callback(message, percent)

    try:
        output_path = run_pipeline(
            source=source,
            progress_callback=report,
            cancel_check=cancel_check,
            **pipeline_options,
        )
    except InterruptedError as exc:
        return JobResult(JobStatus.CANCELLED, warnings=tuple(warnings), error=str(exc) or None)
    except Exception as exc:
        return JobResult(JobStatus.FAILED, warnings=tuple(warnings), error=str(exc))

    status = JobStatus.COMPLETED_WITH_WARNINGS if warnings else JobStatus.COMPLETED
    return JobResult(status, output_path=Path(output_path), warnings=tuple(warnings))


def main():
    """Hỗ trợ chạy pipeline trực tiếp qua dòng lệnh CLI."""
    parser = argparse.ArgumentParser(description="AutoSub Dubbing Studio CLI")
    parser.add_argument("--source", "-s", required=True, help="URL video TikTok/Douyin hoặc đường dẫn tệp MP4 cục bộ")
    parser.add_argument("--voice", "-v", default=Config.DEFAULT_VOICE, help="Giọng lồng tiếng (NamMinh / HoaiMy)")
    parser.add_argument("--ducking", "-d", type=float, default=Config.DEFAULT_DUCKING_VOLUME, help="Âm lượng tiếng nền (mặc định 0.10)")
    parser.add_argument("--no-sub", action="store_true", help="Không nung phụ đề vào video")
    parser.add_argument("--no-dub", action="store_true", help="Không lồng tiếng AI (giữ nguyên âm thanh gốc)")
    parser.add_argument("--output", "-o", default=str(Config.OUTPUT_DIR), help="Thư mục xuất video")

    args = parser.parse_args()

    try:
        final_path = run_pipeline(
            source=args.source,
            voice=args.voice,
            ducking_volume=args.ducking,
            burn_subtitles=not args.no_sub,
            enable_dubbing=not args.no_dub,
            output_dir=Path(args.output)
        )
        print(f"\n✓ THÀNH CÔNG: {final_path}")
    except Exception as e:
        print(f"\n❌ THẤT BẠI: {str(e)}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
