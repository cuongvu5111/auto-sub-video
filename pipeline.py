"""
Pipeline điều phối toàn trình (End-to-End Orchestrator) cho AutoSub Dubbing Studio.
Kết nối tuần tự: Tải video -> Tách âm -> Phiên âm -> Dịch thuật -> Lồng tiếng -> Hòa âm & Render.
"""

import sys
import argparse
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
from core.transcriber import transcribe_audio
from core.translator import translate_segments
from core.tts_engine import process_dubbing_segments
from core.audio_mixer import generate_ass_file, create_mixed_audio_track, render_final_video


def run_pipeline(
    source: str,
    source_lang: Optional[str] = "auto",
    voice: Optional[str] = None,
    ducking_volume: float = 0.10,
    burn_subtitles: bool = True,
    genre: str = "Daily Life / Social Media",
    custom_terms: str = "",
    subtitle_options: Optional[Dict[str, Any]] = None,
    output_dir: Optional[Path] = None,
    progress_callback: Optional[Callable[[str, float], None]] = None
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
        output_dir: Thư mục lưu video thành phẩm.
        progress_callback: Hàm nhận (thông điệp, phần trăm tiến độ tổng thể).

    Returns:
        Path: Đường dẫn video thành phẩm đã được lồng tiếng Việt và gắn phụ đề.
    """
    target_out_dir = Path(output_dir or Config.OUTPUT_DIR).resolve()
    target_out_dir.mkdir(parents=True, exist_ok=True)

    def report(msg: str, percent: float):
        if progress_callback:
            progress_callback(msg, percent)
        else:
            print(f"[{percent:5.1f}%] {msg}")

    # STEP 1: Download or load local video
    report("Step 1/6: Preparing and loading input video...", 5.0)
    video_path = download_video(source, progress_callback=lambda m, p: report(f"Step 1/6: {m}", 5.0 + p * 0.15))

    # STEP 2: Extract audio to 16kHz mono WAV
    report("Step 2/6: Extracting audio from video...", 20.0)
    raw_audio_path = Config.TEMP_DIR / f"{video_path.stem}_raw.wav"
    extract_audio(video_path, raw_audio_path)

    # STEP 3: Speech-to-Text with word timestamps
    report("Step 3/6: Transcribing speech and timestamps with Whisper...", 35.0)
    whisper_lang = None if (not source_lang or source_lang.lower() in ("auto", "none")) else source_lang.lower()
    segments = transcribe_audio(
        raw_audio_path,
        language=whisper_lang,
        word_timestamps=True,
        progress_callback=lambda m, p: report(f"Step 3/6: {m}", 35.0 + p * 0.15)
    )

    if not segments:
        raise ValueError("No speech or dialogue detected in this video.")

    # STEP 4: Contextual LLM translation
    report("Step 4/6: Translating dialogues with LLM...", 55.0)
    translated_segments = translate_segments(
        segments,
        source_lang="Chinese" if whisper_lang == "zh" else "Original Language",
        target_lang="Vietnamese",
        genre=genre,
        custom_terms=custom_terms,
        progress_callback=lambda m, p: report(f"Step 4/6: {m}", 55.0 + p * 0.10)
    )

    # STEP 5: AI voice synthesis and atempo synchronization
    report("Step 5/6: Synthesizing AI voice dubbing and syncing tempo...", 68.0)
    dubbed_segments = process_dubbing_segments(
        translated_segments,
        voice=voice,
        progress_callback=lambda m, p: report(f"Step 5/6: {m}", 68.0 + p * 0.17)
    )

    # STEP 6: Audio ducking and video rendering
    report("Step 6/6: Mixing audio and rendering final video...", 88.0)
    
    # 6a. Create mixed audio track
    mixed_audio_file = Config.TEMP_DIR / f"{video_path.stem}_mixed.mp3"
    create_mixed_audio_track(
        raw_audio_path,
        dubbed_segments,
        mixed_audio_file,
        ducking_volume=ducking_volume
    )

    # 6b. Generate ASS subtitle file if requested
    ass_file = None
    if burn_subtitles:
        ass_file = Config.TEMP_DIR / f"{video_path.stem}_sub.ass"
        sub_opts = subtitle_options or {}
        generate_ass_file(
            dubbed_segments,
            ass_file,
            font_name=sub_opts.get("font_name", "Arial"),
            font_size=sub_opts.get("font_size", 24),
            primary_color=sub_opts.get("primary_color", "&H00000000"),
            outline_color=sub_opts.get("outline_color", "&H00FFFFFF"),
            back_color=sub_opts.get("back_color", "&H00FFFFFF"),
            border_style=sub_opts.get("border_style", 3),
            outline_width=sub_opts.get("outline_width", 6),
            shadow_width=sub_opts.get("shadow_width", 0),
            margin_v=sub_opts.get("margin_v", 40)
        )

    # 6c. Render finalized video
    final_video_name = f"{video_path.stem}_vi.mp4"
    final_video_path = target_out_dir / final_video_name

    render_final_video(
        video_path,
        mixed_audio_file,
        final_video_path,
        ass_subtitle_path=ass_file,
        progress_callback=lambda m, p: report(f"Step 6/6: {m}", 90.0 + p * 0.10)
    )

    report(f"Pipeline completed! Video successfully saved to: {final_video_path}", 100.0)
    return final_video_path


def main():
    """Hỗ trợ chạy pipeline trực tiếp qua dòng lệnh CLI."""
    parser = argparse.ArgumentParser(description="AutoSub Dubbing Studio CLI")
    parser.add_argument("--source", "-s", required=True, help="URL video TikTok/Douyin hoặc đường dẫn tệp MP4 cục bộ")
    parser.add_argument("--voice", "-v", default=Config.DEFAULT_VOICE, help="Giọng lồng tiếng (NamMinh / HoaiMy)")
    parser.add_argument("--ducking", "-d", type=float, default=Config.DEFAULT_DUCKING_VOLUME, help="Âm lượng tiếng nền (mặc định 0.10)")
    parser.add_argument("--no-sub", action="store_true", help="Không nung phụ đề vào video")
    parser.add_argument("--output", "-o", default=str(Config.OUTPUT_DIR), help="Thư mục xuất video")

    args = parser.parse_args()

    try:
        final_path = run_pipeline(
            source=args.source,
            voice=args.voice,
            ducking_volume=args.ducking,
            burn_subtitles=not args.no_sub,
            output_dir=Path(args.output)
        )
        print(f"\n✓ THÀNH CÔNG: {final_path}")
    except Exception as e:
        print(f"\n❌ THẤT BẠI: {str(e)}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
