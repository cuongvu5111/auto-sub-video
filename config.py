"""
Tệp quản lý cấu hình tập trung cho AutoSub Dubbing Studio.
Đọc các thiết lập từ tệp .env và cung cấp các giá trị mặc định an toàn.
"""

import os
from pathlib import Path

# Vô hiệu hóa cảnh báo symlink của HuggingFace trên Windows
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
os.environ.setdefault("PYTHONUTF8", "1")

# Tự động đưa thư mục bin vào PATH để FFmpeg portable luôn sẵn sàng
_bin_dir = Path(__file__).resolve().parent / "bin"
if _bin_dir.exists() and str(_bin_dir) not in os.environ.get("PATH", ""):
    os.environ["PATH"] = str(_bin_dir) + os.pathsep + os.environ.get("PATH", "")

# Thử nạp biến môi trường từ tệp .env nếu thư viện python-dotenv đã được cài đặt
env_path = Path(__file__).resolve().parent / ".env"
try:
    from dotenv import load_dotenv
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
    else:
        load_dotenv()
except ImportError:
    # Bộ đọc tệp .env thủ công dự phòng nếu chưa cài python-dotenv
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    key = key.strip()
                    val = val.strip().strip('"').strip("'")
                    if key and key not in os.environ:
                        os.environ[key] = val


class Config:
    """Lớp chứa toàn bộ thông số cấu hình của ứng dụng."""

    # Đường dẫn thư mục gốc dự án
    BASE_DIR: Path = Path(__file__).resolve().parent

    # Thư mục chứa các tệp thực thi portable (FFmpeg)
    BIN_DIR: Path = BASE_DIR / "bin"

    # Thư mục chứa dữ liệu tạm (audio cắt nhỏ, video tải về)
    TEMP_DIR: Path = BASE_DIR / "temp"

    # Thư mục xuất video kết quả mặc định
    OUTPUT_DIR: Path = BASE_DIR / os.getenv("DEFAULT_OUTPUT_DIR", "output")

    # Cấu hình API LLM (Chuẩn OpenAI-compatible, hỗ trợ cả alias VNPT)
    _raw_url = os.getenv("LLM_BASE_URL") or os.getenv("VNPT_LLM_URL", "http://localhost:11434/v1")
    if _raw_url.endswith("/chat/completions"):
        _raw_url = _raw_url[:-len("/chat/completions")]
    LLM_BASE_URL: str = _raw_url

    LLM_MODEL: str = os.getenv("LLM_MODEL") or os.getenv("VNPT_LLM_MODEL", "google/gemma-4-26B-A4B-it")
    LLM_API_KEY: str = os.getenv("LLM_API_KEY") or os.getenv("VNPT_LLM_API_KEY", "no-key-required")

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

    @classmethod
    def save_llm_config(cls, base_url: str, api_key: str, model: str) -> None:
        """
        Lưu cấu hình LLM vào tệp .env và cập nhật biến trong runtime Config.
        """
        base_url = base_url.strip()
        if base_url.endswith("/chat/completions"):
            base_url = base_url[:-len("/chat/completions")]

        cls.LLM_BASE_URL = base_url
        cls.LLM_API_KEY = api_key.strip()
        cls.LLM_MODEL = model.strip()

        os.environ["LLM_BASE_URL"] = cls.LLM_BASE_URL
        os.environ["LLM_API_KEY"] = cls.LLM_API_KEY
        os.environ["LLM_MODEL"] = cls.LLM_MODEL

        env_file = cls.BASE_DIR / ".env"
        lines = []
        keys_updated = set()

        if env_file.exists():
            with open(env_file, "r", encoding="utf-8") as f:
                for line in f:
                    stripped = line.strip()
                    if stripped.startswith("LLM_BASE_URL="):
                        lines.append(f"LLM_BASE_URL={cls.LLM_BASE_URL}\n")
                        keys_updated.add("LLM_BASE_URL")
                    elif stripped.startswith("LLM_API_KEY="):
                        lines.append(f"LLM_API_KEY={cls.LLM_API_KEY}\n")
                        keys_updated.add("LLM_API_KEY")
                    elif stripped.startswith("LLM_MODEL="):
                        lines.append(f"LLM_MODEL={cls.LLM_MODEL}\n")
                        keys_updated.add("LLM_MODEL")
                    else:
                        lines.append(line)

        if "LLM_BASE_URL" not in keys_updated:
            lines.append(f"LLM_BASE_URL={cls.LLM_BASE_URL}\n")
        if "LLM_API_KEY" not in keys_updated:
            lines.append(f"LLM_API_KEY={cls.LLM_API_KEY}\n")
        if "LLM_MODEL" not in keys_updated:
            lines.append(f"LLM_MODEL={cls.LLM_MODEL}\n")

        with open(env_file, "w", encoding="utf-8") as f:
            f.writelines(lines)


# Tự động khởi tạo thư mục tạm và xuất file ngay khi module được import
Config.ensure_directories()
