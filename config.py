"""
Tệp quản lý cấu hình tập trung cho AutoSub Dubbing Studio.
Đọc các thiết lập từ tệp .env và cung cấp các giá trị mặc định an toàn.
"""

import os
from pathlib import Path

# Thử nạp biến môi trường từ tệp .env nếu thư viện python-dotenv đã được cài đặt
try:
    from dotenv import load_dotenv
    # Nạp từ file .env nằm cùng thư mục gốc của dự án
    env_path = Path(__file__).resolve().parent / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
    else:
        load_dotenv()
except ImportError:
    # Nếu chưa cài python-dotenv, vẫn tiếp tục bằng biến môi trường hệ thống
    pass


class Config:
    """Lớp chứa toàn bộ thông số cấu hình của ứng dụng."""

    # Đường dẫn thư mục gốc dự án
    BASE_DIR: Path = Path(__file__).resolve().parent

    # Thư mục chứa dữ liệu tạm (audio cắt nhỏ, video tải về)
    TEMP_DIR: Path = BASE_DIR / "temp"

    # Thư mục xuất video kết quả mặc định
    OUTPUT_DIR: Path = BASE_DIR / os.getenv("DEFAULT_OUTPUT_DIR", "output")

    # Cấu hình API LLM (Chuẩn OpenAI-compatible)
    LLM_BASE_URL: str = os.getenv("LLM_BASE_URL", "http://localhost:11434/v1")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "gemma3:4b")
    LLM_API_KEY: str = os.getenv("LLM_API_KEY", "no-key-required")

    # Cấu hình Whisper Speech-to-Text
    WHISPER_MODEL: str = os.getenv("WHISPER_MODEL", "base")
    WHISPER_DEVICE: str = os.getenv("WHISPER_DEVICE", "cpu")
    WHISPER_COMPUTE_TYPE: str = os.getenv("WHISPER_COMPUTE_TYPE", "int8")

    # Cấu hình lồng tiếng Text-to-Speech (edge-tts)
    DEFAULT_VOICE: str = os.getenv("DEFAULT_VOICE", "vi-VN-NamMinhNeural")

    # Cấu hình âm lượng tiếng nền khi hòa âm (10% tiếng gốc)
    DEFAULT_DUCKING_VOLUME: float = float(os.getenv("DEFAULT_DUCKING_VOLUME", "0.10"))

    # Danh sách các giọng tiếng Việt có sẵn từ Edge TTS
    AVAILABLE_VOICES: dict = {
        "Nam Minh (Truyền cảm - Nam)": "vi-VN-NamMinhNeural",
        "Hoài My (Nhẹ nhàng - Nữ)": "vi-VN-HoaiMyNeural"
    }

    @classmethod
    def ensure_directories(cls) -> None:
        """Tự động tạo các thư mục cần thiết nếu chưa tồn tại trên ổ đĩa."""
        cls.TEMP_DIR.mkdir(parents=True, exist_ok=True)
        cls.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# Tự động khởi tạo thư mục tạm và xuất file ngay khi module được import
Config.ensure_directories()
