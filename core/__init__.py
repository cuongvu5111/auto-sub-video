"""
Gói module lõi (Core Engine) xử lý video, âm thanh và AI cho AutoSub Dubbing Studio.
Bao gồm:
- downloader: Tải video từ mạng xã hội (TikTok, Douyin,...)
- audio_extractor: Trích xuất audio chuẩn phục vụ Speech-to-Text
- transcriber: Nhận diện giọng nói và mốc thời gian (faster-whisper)
- translator: Dịch thuật ngữ cảnh bằng LLM (OpenAI-compatible)
- tts_engine: Sinh giọng lồng tiếng tiếng Việt và đồng bộ tốc độ (edge-tts + atempo)
- audio_mixer: Hòa âm ducking và đóng gói video thành phẩm (FFmpeg)
"""

__all__ = [
    "downloader",
    "audio_extractor",
    "transcriber",
    "translator",
    "tts_engine",
    "audio_mixer"
]
