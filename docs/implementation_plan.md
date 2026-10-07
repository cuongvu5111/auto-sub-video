# Kế Hoạch Triển Khai: Tool Tự Động Lồng Tiếng AI (Dubbing) & Tạo Phụ Đề Cho Video TikTok

Tài liệu kế hoạch phát triển toàn trình công cụ tự động lồng tiếng (AI Dubbing) và tạo phụ đề video ngắn từ TikTok/Douyin (tập trung chuyển đổi từ tiếng Trung sang tiếng Việt), tích hợp LLM Gemma (chuẩn OpenAI-compatible), faster-whisper và edge-tts.

---

## 1. Mục Tiêu Dự Án

* Tải video chất lượng cao từ TikTok/Douyin không dính watermark bằng `yt-dlp`.
* Nhận diện chính xác câu thoại và mốc thời gian (Speech-to-Text) bằng `faster-whisper` (chạy mượt trên CPU với INT8).
* Dịch thuật thoát ý, căn chỉnh độ dài câu thoại phù hợp với phong cách video ngắn bằng mô hình ngôn ngữ lớn (hỗ trợ endpoint OpenAI-compatible như Gemma 26B, Gemma 3 4B, hoặc Ollama local).
* Tạo giọng lồng tiếng tiếng Việt tự nhiên miễn phí bằng `edge-tts`.
* Căn chỉnh tốc độ giọng đọc (`atempo`) để khớp thời lượng câu gốc và hòa âm (audio ducking giảm 85% tiếng gốc để lót nền).
* Đóng gói video hoàn thiện (kèm tùy chọn burn phụ đề TikTok) và giao diện trực quan với `Streamlit`.

---

## 2. Kiến Trúc Pipeline Xử Lý

```
[TikTok URL]
     │
     ▼
[downloader.py: Tải video & trích xuất audio WAV 16kHz]
     │
     ▼
[transcriber.py: faster-whisper nhận diện text Trung + timestamps]
     │
     ▼
[translator.py: LLM (OpenAI-compatible) dịch câu thoại ngắn gọn sang tiếng Việt]
     │
     ▼
[tts_engine.py: edge-tts tạo audio tiếng Việt & atempo nén/giãn tốc độ]
     │
     ▼
[audio_mixer.py: Audio ducking tiếng gốc 15% + tiếng lồng 100% + render video]
     │
     ▼
[Video TikTok hoàn chỉnh đã lồng tiếng Việt]
```

---

## 3. Các Giai Đoạn Triển Khai (Phases)

### Giai đoạn 1: Khởi tạo môi trường & File cấu hình
- Tạo `.env.example`, `config.py` đọc biến môi trường.
- Tạo `requirements.txt` với các phiên bản ổn định.
- Hướng dẫn kiểm tra và cấu hình FFmpeg cho môi trường Windows.

### Giai đoạn 2: Module Tải Video & Audio (`downloader.py`, `audio_extractor.py`)
- Viết hàm dùng `yt-dlp` tải video MP4 tốt nhất không watermark.
- Trích xuất file audio WAV chuẩn mono 16kHz phục vụ Whisper.

### Giai đoạn 3: Module Nhận Diện Giọng Nói (`transcriber.py`)
- Tích hợp `faster-whisper` (model `base` hoặc `small`).
- Chạy trên CPU với `compute_type="int8"` để tiết kiệm RAM.
- Trả về danh sách phân đoạn: `[{start, end, text}]`.

### Giai đoạn 4: Module Dịch Thuật LLM (`translator.py`)
- Kết nối endpoint chuẩn OpenAI SDK (cấu hình qua biến môi trường `LLM_BASE_URL`).
- Prompt kỹ thuật yêu cầu dịch ngắn gọn, tương đương số âm tiết gốc, xuất JSON schema chuẩn.

### Giai đoạn 5: Module Lồng Tiếng AI & Đồng Bộ Tốc Độ (`tts_engine.py`)
- Dùng `edge-tts` sinh giọng Nam (`vi-VN-NamMinhNeural`) hoặc Nữ (`vi-VN-HoaiMyNeural`).
- Tính toán hệ số `speed_factor = vi_duration / zh_duration`.
- Dùng filter FFmpeg `atempo` điều chỉnh tốc độ đọc trong giới hạn an toàn [0.85x - 1.25x].

### Giai đoạn 6: Module Hòa Âm & Ghép Video (`audio_mixer.py`)
- Giảm âm lượng âm thanh gốc xuống 10-15%.
- Ghép các file thoại tiếng Việt vào đúng timeline mốc thời gian.
- Trộn (amix) 2 kênh âm thanh và đóng vào video gốc bằng FFmpeg.
- Tùy chọn sinh file phụ đề `.ass` để hiển thị chữ cùng lúc.

### Giai đoạn 7: Xây Dựng Pipeline Tổng & Giao Diện Web (`app.py`)
- Viết file `pipeline.py` chạy độc lập qua CLI.
- Viết giao diện Web `Streamlit` thân thiện: nhập link, chọn giọng đọc, xem preview và tải video.

---

## 4. Kế Hoạch Xác Minh (Verification Criteria)

1. **Kiểm tra môi trường**: Lệnh `ffmpeg -version` và import các thư viện cốt lõi thành công.
2. **Kiểm tra kết nối LLM**: Gửi request mẫu tới endpoint LLM đã cấu hình và nhận về kết quả JSON dịch thuật hợp lệ.
3. **Kiểm tra âm thanh TTS**: File sinh ra từ `edge-tts` phát rõ ràng, không bị ngắt tiếng.
4. **Kiểm tra đồng bộ video**: Video xuất ra có tiếng lồng tiếng Việt khớp hình, nhạc nền không bị lấn át giọng nói.
