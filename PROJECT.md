# PROJECT CONTEXT: Auto-Sub & AI Dubbing Video TikTok

## 1. Giới Thiệu Dự Án
Công cụ tự động hóa toàn trình (end-to-end) tải video ngắn từ TikTok/Douyin (đặc biệt là tiếng Trung), trích xuất giọng nói, phiên âm, dịch sang tiếng Việt bằng mô hình LLM chuyên sâu, tạo giọng lồng tiếng tiếng Việt tự nhiên (AI Dubbing) và đóng gói video thành phẩm kèm phụ đề chữ kiểu TikTok.

Tiêu chí tiên quyết: **Tối ưu chi phí (100% miễn phí / mã nguồn mở), chạy mượt mà trên môi trường máy tính cá nhân (hệ điều hành Windows, hỗ trợ chạy tốt trên CPU không cần GPU rời).**

---

## 2. Tech Stack & Hạ Tầng

* **Ngôn ngữ**: Python 3.10+
* **Tải Video**: `yt-dlp` (hỗ trợ TikTok/Douyin không watermark)
* **Speech-to-Text (STT)**: `faster-whisper` (sử dụng model `base` hoặc `small`, cấu hình chạy CPU với chế độ lượng tử hóa `compute_type="int8"`)
* **Mô hình Ngôn ngữ (LLM)**:
  * **Endpoint**: Hỗ trợ chuẩn OpenAI-compatible (cấu hình qua `LLM_BASE_URL`, có thể dùng Ollama local `http://localhost:11434/v1`, hoặc custom gateway).
  * **Model**: Mô hình ngôn ngữ mở tối ưu (ví dụ: `gemma3:4b`, `gemma-4-26B-A4B-it`, `gpt-4o-mini`).
  * **Mục đích**: Dịch thoát ý, tối ưu độ dài câu thoại phù hợp với nhịp độ video ngắn, ngắt dòng phụ đề chuẩn xác.
* **Text-to-Speech (TTS)**: `edge-tts` (Microsoft Edge Neural Voice)
  * Giọng Nam: `vi-VN-NamMinhNeural`
  * Giọng Nữ: `vi-VN-HoaiMyNeural`
* **Xử lý Audio/Video**: `FFmpeg` (kết hợp `pydub` và lệnh subprocess native)
  * Bộ lọc `atempo`: Điều chỉnh tốc độ giọng đọc ăn khớp thời lượng video gốc.
  * Bộ lọc `amix` & `volume`: Audio Ducking (giảm âm lượng tiếng gốc xuống 10-15%, đè tiếng lồng tiếng Việt 100%).
* **Giao diện Người dùng**: `Streamlit` (giao diện Web trực quan) hoặc Python CLI.

---

## 3. Kiến Trúc Thư Mục Dự Án

```
auto-sub-video/
├── .env.example              # Mẫu biến môi trường (LLM_BASE_URL, LLM_MODEL, LLM_API_KEY,...)
├── requirements.txt          # Danh sách thư viện Python
├── config.py                 # Quản lý cấu hình tập trung (Pydantic / Dataclass)
├── core/
│   ├── __init__.py
│   ├── downloader.py         # Module tải video TikTok không watermark (yt-dlp)
│   ├── audio_extractor.py    # Module tách audio từ video sang định dạng WAV 16kHz
│   ├── transcriber.py        # Module STT nhận diện câu thoại & timestamp (faster-whisper)
│   ├── translator.py         # Module dịch thuật & chuẩn hóa qua LLM (OpenAI-compatible)
│   ├── tts_engine.py         # Module sinh giọng đọc tiếng Việt & căn chỉnh tốc độ (edge-tts + atempo)
│   └── audio_mixer.py        # Module hòa âm (ducking audio gốc + lồng tiếng) & xuất video (FFmpeg)
├── pipeline.py               # Điều phối toàn bộ luồng xử lý từ URL -> Video kết quả
├── app.py                    # Giao diện WebUI Streamlit
├── docs/                     # Tài liệu kế hoạch & hướng dẫn kiến trúc
│   └── implementation_plan.md
└── temp/                     # Thư mục lưu trữ file tạm (video tải về, audio cắt lẻ, cache)
```

---

## 4. Quy Ước Phát Triển (Conventions)

1. **Ngôn ngữ giao tiếp & Ghi chú mã nguồn**: Sử dụng Tiếng Việt cho toàn bộ comment trong code, docstring và commit message.
2. **Xử lý ngoại lệ**: Luôn bắt exception cụ thể (ví dụ: `DownloadError`, `APIConnectionError`), không dùng `except Exception: pass`. Ghi log rõ ràng từng bước.
3. **Quản lý file tạm**: Mọi file audio/video trung gian phải được lưu trong thư mục `temp/` và có cơ chế tự động dọn dẹp sau khi hoàn thành pipeline.
4. **Định dạng dữ liệu trung gian**: Dữ liệu timeline giữa các module luôn tuân theo schema chuẩn:
   ```json
   [
     {
       "index": 1,
       "start": 0.0,
       "end": 2.5,
       "original_text": "今天我们要分享一个实用技巧",
       "translated_text": "Hôm nay mình chia sẻ một mẹo siêu hay nè",
       "audio_path": "temp/segment_1.mp3",
       "duration": 2.3
     }
   ]
   ```
5. **Tương thích Windows**: Mọi đường dẫn file phải dùng `pathlib.Path` hoặc chuẩn hóa dấu gạch chéo để tương thích môi trường Windows.
