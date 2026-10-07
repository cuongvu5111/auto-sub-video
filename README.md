# Tool Tự Động Lồng Tiếng AI (Dubbing) & Tạo Phụ Đề TikTok

Công cụ tự động tải video ngắn từ TikTok/Douyin, nhận diện giọng nói (Speech-to-Text), dịch thuật ngữ cảnh bằng mô hình LLM **Gemma 26B-A4B-it**, tạo giọng lồng tiếng tiếng Việt tự nhiên (**Microsoft Edge TTS**), đồng bộ thời gian và đóng gói thành video hoàn chỉnh kèm phụ đề.

---

## ✨ Tính Năng Nổi Bật

* 🚀 **Tải video không Watermark**: Hỗ trợ TikTok và Douyin với độ phân giải cao nhất qua `yt-dlp`.
* 🎙️ **Nhận diện giọng nói chính xác**: Sử dụng `faster-whisper` tối ưu chạy mượt mà ngay trên CPU với chế độ INT8.
* 🧠 **Dịch thuật thông minh với Gemma 26B**: Dịch thoát ý từ tiếng Trung sang tiếng Việt, phù hợp văn phong ngắn gọn, dí dỏm của video TikTok.
* 🗣️ **Lồng tiếng tự nhiên miễn phí (AI Dubbing)**: Tích hợp `edge-tts` với giọng Nam/Nữ truyền cảm, không giới hạn ký tự và không tốn phí API.
* ⏱️ **Tự động căn chỉnh tốc độ (Speed Sync)**: Điều chỉnh tốc độ giọng đọc linh hoạt (`0.85x` - `1.25x`) để khớp đúng thời lượng câu gốc.
* 🎧 **Hòa âm thông minh (Audio Ducking)**: Tự động hạ âm lượng tiếng gốc xuống 10-15% làm nền (giữ tiếng cười, nhạc nền), đè giọng lồng tiếng Việt nổi bật lên trên.
* 🖥️ **Giao diện Web trực quan**: Viết bằng `Streamlit`, thao tác đơn giản chỉ cần dán link và bấm bắt đầu.

---

## 🛠️ Yêu Cầu Môi Trường

* **Hệ điều hành**: Windows 10/11
* **Python**: Phiên bản 3.10 trở lên
* **FFmpeg**: Đã được cài đặt và thêm vào biến môi trường PATH hệ thống

### Hướng dẫn cài nhanh FFmpeg trên Windows:
Mở PowerShell (Run as Administrator) và chạy lệnh:
```powershell
winget install Gyan.FFmpeg
```
*Sau khi cài xong, khởi động lại terminal để nhận lệnh `ffmpeg`.*

---

## 🚀 Hướng Dẫn Cài Đặt & Sử Dụng

### 1. Cài đặt các thư viện phụ thuộc
```bash
pip install -r requirements.txt
```

### 2. Thiết lập cấu hình môi trường
Tạo file `.env` từ `.env.example`:
```bash
cp .env.example .env
```
Mở file `.env` và điền cấu hình API của VNPT SI:
```env
VNPT_LLM_URL=https://llm.vnptsi.vn/v1
VNPT_LLM_MODEL=google/gemma-4-26B-A4B-it
VNPT_API_KEY=your_api_key_here
```

### 3. Khởi chạy ứng dụng
Chạy giao diện Web:
```bash
streamlit run app.py
```
Hoặc chạy dòng lệnh CLI:
```bash
python pipeline.py --url "https://www.tiktok.com/@user/video/123456789" --voice "vi-VN-NamMinhNeural"
```

---

## 📂 Cấu Trúc Mã Nguồn

Chi tiết xem tại tệp [`PROJECT.md`](file:///d:/www/auto-sub-video/PROJECT.md) và kế hoạch triển khai tại [`docs/implementation_plan.md`](file:///d:/www/auto-sub-video/docs/implementation_plan.md).
