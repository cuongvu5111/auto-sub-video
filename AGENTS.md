# Hướng Dẫn Dành Cho AI Agent (AGENTS.md)

Tài liệu này quy định các nguyên tắc, vai trò và quy chuẩn hành vi cho bất kỳ AI Coding Agent nào tham gia phát triển, bảo trì và mở rộng dự án `auto-sub-video`.

---

## 1. Nguyên Tắc Cốt Lõi

1. **Tuân thủ ngữ cảnh dự án (`PROJECT.md`)**:
   * Luôn đọc và bám sát các quyết định công nghệ trong [`PROJECT.md`](file:///d:/www/auto-sub-video/PROJECT.md).
   * Ưu tiên giải pháp **100% miễn phí / mã nguồn mở**. Tuyệt đối không tự ý thêm các thư viện trả phí hoặc dịch vụ đám mây có phí (như ElevenLabs, OpenAI Whisper API có phí, Azure Paid TTS) trừ khi người dùng yêu cầu rõ ràng.
2. **Ngôn ngữ sử dụng**:
   * Tất cả giải thích, giao tiếp với người dùng, tài liệu và **comment trong code** phải viết bằng **Tiếng Việt**.
   * Code comment cần giải thích *lý do tại sao làm vậy* (why), không chỉ mô tả lại code làm gì (what).
3. **Tính độc lập & Module hóa**:
   * Mỗi module trong `core/` chỉ đảm nhận đúng 1 nhiệm vụ duy nhất (Single Responsibility Principle).
   * Giao tiếp giữa các module thông qua đối tượng dữ liệu chuẩn (dataclass hoặc dict có schema rõ ràng).
   * Không import chéo vòng tròn giữa các module con trong `core/`.
4. **Tối ưu hóa tài nguyên**:
   * Mặc định hỗ trợ chạy trên máy tính phổ thông không có GPU rời (CPU mode INT8 cho faster-whisper, xử lý audio/video bằng FFmpeg CPU).
   * Dọn dẹp các tệp tin tạm sau khi xử lý thành công để tránh tràn ổ đĩa người dùng.

---

## 2. Quy Trình Làm Việc Khi Thay Đổi Mã Nguồn

1. **Đọc trước khi Sửa**: Luôn dùng công cụ đọc file trước khi thực hiện bất kỳ chỉnh sửa nào.
2. **Một thay đổi mỗi bước**: Nếu cần thay đổi nhiều module, hãy lập kế hoạch và thực hiện tuần tự.
3. **Xác minh có bằng chứng (Verification)**:
   * Sau khi viết code, bắt buộc chạy kiểm thử thực tế (test script, build, chạy thử lệnh).
   * Không bao giờ báo cáo "đã xong" nếu chưa kiểm tra lỗi runtime hoặc cú pháp.
4. **Bảo toàn tính nguyên vẹn**:
   * Giữ nguyên các comment và docstring hiện có không liên quan đến phạm vi thay đổi.
   * Tạo commit message súc tích, dạng mệnh lệnh bằng Tiếng Việt (< 72 ký tự).
