"""
Module tải video từ TikTok, Douyin và các mạng xã hội không watermark.
Sử dụng thư viện yt-dlp để lấy video chất lượng cao nhất.
"""

import os
import re
from pathlib import Path
from typing import Optional, Callable
from config import Config


class DownloadError(Exception):
    """Lỗi xảy ra trong quá trình tải video."""
    pass


def is_url(path_or_url: str) -> bool:
    """Kiểm tra xem chuỗi đầu vào là URL mạng hay đường dẫn tệp cục bộ."""
    return bool(re.match(r"^https?://", path_or_url.strip()))


def download_video(
    source: str,
    output_dir: Optional[Path] = None,
    progress_callback: Optional[Callable[[str, float], None]] = None,
    cancel_check: Optional[Callable[[], bool]] = None
) -> Path:
    """
    Tải video từ URL hoặc xác thực tệp video cục bộ.

    Args:
        source: Đường dẫn URL (TikTok, Douyin,...) hoặc đường dẫn tệp MP4 cục bộ.
        output_dir: Thư mục lưu video tải về (mặc định dùng Config.TEMP_DIR).
        progress_callback: Hàm callback nhận (thông điệp, phần trăm hoàn thành).

    Returns:
        Path: Đường dẫn tuyệt đối đến tệp video MP4 sẵn sàng xử lý.
    """
    source = source.strip()
    target_dir = output_dir or Config.TEMP_DIR
    target_dir.mkdir(parents=True, exist_ok=True)

    # 1. Trường hợp người dùng chọn tệp video cục bộ có sẵn
    if not is_url(source):
        local_path = Path(source).resolve()
        if not local_path.exists():
            raise FileNotFoundError(f"Không tìm thấy tệp video cục bộ: {source}")
        if progress_callback:
            progress_callback(f"Sử dụng video cục bộ: {local_path.name}", 100.0)
        return local_path

    # 2. Trường hợp là URL cần tải qua yt-dlp
    if progress_callback:
        progress_callback(f"Bắt đầu phân tích và tải video từ URL: {source}", 10.0)

    try:
        import yt_dlp
    except ImportError:
        raise DownloadError("Thư viện yt-dlp chưa được cài đặt. Vui lòng chạy: pip install yt-dlp")

    # Mẫu đặt tên file xuất ra (dùng id của video để tránh trùng lặp)
    output_template = str(target_dir / "%(id)s.%(ext)s")

    # Hook theo dõi tiến độ tải về
    def ydl_hook(d):
        if cancel_check and cancel_check():
            raise InterruptedError("The download was cancelled by the user.")
        if d.get("status") == "downloading" and progress_callback:
            total_bytes = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            downloaded = d.get("downloaded_bytes") or 0
            if total_bytes > 0:
                percent = min(99.0, (downloaded / total_bytes) * 100.0)
                progress_callback(f"Đang tải video: {percent:.1f}%", percent)
        elif d.get("status") == "finished" and progress_callback:
            progress_callback("Tải video hoàn tất, đang kiểm tra tệp...", 100.0)

    ydl_opts = {
        # Ưu tiên lấy định dạng MP4 có cả hình và tiếng tốt nhất
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "outtmpl": output_template,
        "quiet": True,
        "no_warnings": True,
        "socket_timeout": 20,
        "retries": 2,
        "fragment_retries": 2,
        "extractor_retries": 2,
        "progress_hooks": [ydl_hook],
        # Thêm user-agent giả lập trình duyệt để tránh bị chặn IP
        "http_headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
    }

    # 1. Tự động nạp cookies.txt nếu người dùng đặt trong thư mục dự án
    cookie_candidate = Config.BASE_DIR / "cookies.txt"
    if cookie_candidate.exists():
        ydl_opts["cookiefile"] = str(cookie_candidate)

    # 2. Tự động kích hoạt impersonation chrome (qua curl-cffi) nếu có cài đặt
    try:
        import curl_cffi
        from yt_dlp.networking.impersonate import ImpersonateTarget
        ydl_opts["impersonate"] = ImpersonateTarget.from_str("chrome")
    except (ImportError, Exception):
        pass

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(source, download=True)
            if not info:
                raise DownloadError("Không thể trích xuất thông tin video từ đường link cung cấp.")
            
            # Lấy đường dẫn file đã tải
            downloaded_file = ydl.prepare_filename(info)
            downloaded_path = Path(downloaded_file)

            # Nếu yt-dlp tự động đổi đuôi file sau khi merge (ví dụ mkv sang mp4)
            if not downloaded_path.exists():
                potential_mp4 = downloaded_path.with_suffix(".mp4")
                if potential_mp4.exists():
                    downloaded_path = potential_mp4
                else:
                    raise FileNotFoundError(f"Không tìm thấy file sau khi tải: {downloaded_file}")

            return downloaded_path.resolve()

    except InterruptedError:
        raise
    except Exception as e:
        err_msg = str(e)
        if "Fresh cookies" in err_msg or "403" in err_msg:
            friendly_msg = (
                "Douyin/TikTok yêu cầu xác thực Cookie chống bot! "
                "Vui lòng tải video về máy qua trang trung gian (như unduhtiktok.com / snaptik) rồi chọn tệp video cục bộ qua nút '+ Add Videos...', "
                "hoặc đặt tệp cookies.txt vào thư mục dự án."
            )
            raise DownloadError(friendly_msg) from e
        raise DownloadError(f"Lỗi khi tải video từ {source}: {err_msg}") from e
