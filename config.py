"""
Tệp quản lý cấu hình tập trung cho AutoSub Dubbing Studio.
Đọc các thiết lập từ tệp .env và cung cấp các giá trị mặc định an toàn.
"""

import sys
import os
import subprocess
from pathlib import Path

# Cờ ẩn cửa sổ console phụ khi gọi subprocess trên Windows (tránh hiện popup terminal đen)
SUBPROCESS_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0

# Xác định thư mục gốc ứng dụng (hỗ trợ cả môi trường dev lẫn exe đóng gói bằng PyInstaller)
if getattr(sys, "frozen", False):
    _app_dir = Path(sys.executable).resolve().parent
    _internal_dir = Path(getattr(sys, "_MEIPASS", _app_dir))
else:
    _app_dir = Path(__file__).resolve().parent
    _internal_dir = _app_dir

# Vô hiệu hóa cảnh báo symlink của HuggingFace trên Windows
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
os.environ.setdefault("PYTHONUTF8", "1")

# Tự động đưa thư mục bin vào PATH để FFmpeg portable luôn sẵn sàng
for _b in [_app_dir / "bin", _internal_dir / "bin"]:
    if _b.exists() and str(_b) not in os.environ.get("PATH", ""):
        os.environ["PATH"] = str(_b) + os.pathsep + os.environ.get("PATH", "")

# Thử nạp biến môi trường từ tệp .env nếu thư viện python-dotenv đã được cài đặt
env_path = _app_dir / ".env"
if not env_path.exists():
    env_path = _internal_dir / ".env"

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

    _HARDWARE_CAPABILITIES: dict | None = None

    # Đường dẫn thư mục gốc dự án (nơi người dùng lưu file exe hoặc mã nguồn)
    BASE_DIR: Path = _app_dir
    INTERNAL_DIR: Path = _internal_dir

    # Thư mục chứa các tệp thực thi portable (FFmpeg)
    BIN_DIR: Path = BASE_DIR / "bin"

    # Thư mục chứa dữ liệu tạm (audio cắt nhỏ, video tải về)
    TEMP_DIR: Path = BASE_DIR / "temp"

    # Keep intermediates only when explicitly requested for troubleshooting.
    KEEP_INTERMEDIATES: bool = os.getenv("KEEP_INTERMEDIATES", "false").lower() in ("true", "1", "yes")

    # Thư mục xuất video kết quả mặc định
    OUTPUT_DIR: Path = BASE_DIR / os.getenv("DEFAULT_OUTPUT_DIR", "output")

    # Cấu hình API LLM (Chuẩn OpenAI-compatible, hỗ trợ cả alias VNPT)
    _raw_url = os.getenv("LLM_BASE_URL") or os.getenv("VNPT_LLM_URL", "http://localhost:11434/v1")
    if _raw_url.endswith("/chat/completions"):
        _raw_url = _raw_url[:-len("/chat/completions")]
    LLM_BASE_URL: str = _raw_url

    LLM_MODEL: str = os.getenv("LLM_MODEL") or os.getenv("VNPT_LLM_MODEL", "global-llm")
    LLM_API_KEY: str = os.getenv("LLM_API_KEY") or os.getenv("VNPT_LLM_API_KEY", "no-key-required")
    LLM_TIMEOUT: float = float(os.getenv("LLM_TIMEOUT", "60.0"))
    LLM_TRANSLATION_BATCH_SIZE: int = int(os.getenv("LLM_TRANSLATION_BATCH_SIZE", "4"))
    FFMPEG_TIMEOUT: float = float(os.getenv("FFMPEG_TIMEOUT", "1800"))
    TTS_REQUEST_TIMEOUT: float = float(os.getenv("TTS_REQUEST_TIMEOUT", "20"))
    TTS_SEGMENT_TIMEOUT: float = float(os.getenv("TTS_SEGMENT_TIMEOUT", "60"))
    TTS_MAX_CONCURRENCY: int = int(os.getenv("TTS_MAX_CONCURRENCY", "2"))
    TTS_REQUEST_PACING_SECONDS: float = float(os.getenv("TTS_REQUEST_PACING_SECONDS", "0.2"))

    # Cấu hình LLM dự phòng (Fallback / Backup Provider khi chạm Rate Limit 429)
    LLM_BACKUP_ENABLED: bool = os.getenv("LLM_BACKUP_ENABLED", "false").lower() in ("true", "1", "yes")
    _raw_backup_url = os.getenv("LLM_BACKUP_BASE_URL", "")
    if _raw_backup_url.endswith("/chat/completions"):
        _raw_backup_url = _raw_backup_url[:-len("/chat/completions")]
    LLM_BACKUP_BASE_URL: str = _raw_backup_url
    LLM_BACKUP_API_KEY: str = os.getenv("LLM_BACKUP_API_KEY", "")
    LLM_BACKUP_MODEL: str = os.getenv("LLM_BACKUP_MODEL", "")

    # Cấu hình Whisper Speech-to-Text (Mặc định 'auto' để tự động phát hiện GPU/CPU)
    WHISPER_MODEL: str = os.getenv("WHISPER_MODEL", "base")
    WHISPER_DEVICE: str = os.getenv("WHISPER_DEVICE", "auto")
    WHISPER_COMPUTE_TYPE: str = os.getenv("WHISPER_COMPUTE_TYPE", "auto")
    WHISPER_BEAM_SIZE: int = int(os.getenv("WHISPER_BEAM_SIZE", "5"))
    WHISPER_WORD_TIMESTAMPS: bool = os.getenv("WHISPER_WORD_TIMESTAMPS", "true").lower() in ("true", "1", "yes")

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
    def detect_hardware_capabilities(cls, refresh: bool = False) -> dict:
        """
        Tự động phát hiện khả năng tăng tốc phần cứng của hệ thống:
        - NVIDIA CUDA (qua ctranslate2) cho mô hình Whisper Speech-to-Text.
        - NVIDIA NVENC (qua ffmpeg h264_nvenc) cho tác vụ mã hóa video.

        Kết quả được cache trong phiên chạy vì kiểm tra NVENC khởi chạy FFmpeg.
        Truyền refresh=True khi cần dò lại rõ ràng.
        """
        if cls._HARDWARE_CAPABILITIES is not None and not refresh:
            return dict(cls._HARDWARE_CAPABILITIES)

        import subprocess
        capabilities = {
            "has_cuda": False,
            "has_nvenc": False,
            "recommended_device": "cpu",
            "recommended_compute": "int8",
            "recommended_encoder": "libx264"
        }

        # 1. Kiểm tra CUDA cho Whisper
        try:
            import ctranslate2
            if ctranslate2.get_cuda_device_count() > 0:
                capabilities["has_cuda"] = True
                capabilities["recommended_device"] = "cuda"
                capabilities["recommended_compute"] = "float16"
        except Exception:
            pass

        # 2. Kiểm tra NVENC cho FFmpeg
        try:
            ffmpeg_bin = cls.BIN_DIR / "ffmpeg.exe"
            if ffmpeg_bin.exists():
                res = subprocess.run(
                    [str(ffmpeg_bin), "-v", "error", "-f", "lavfi", "-i", "color=c=black:s=64x64:d=0.04", "-c:v", "h264_nvenc", "-f", "null", "-"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=3,
                    creationflags=SUBPROCESS_NO_WINDOW
                )
                if res.returncode == 0:
                    capabilities["has_nvenc"] = True
                    capabilities["recommended_encoder"] = "h264_nvenc"
        except Exception:
            pass

        cls._HARDWARE_CAPABILITIES = dict(capabilities)
        return dict(capabilities)

    @classmethod
    def save_llm_config(cls, base_url: str, api_key: str, model: str,
                        backup_enabled: bool = False,
                        backup_base_url: str = "",
                        backup_api_key: str = "",
                        backup_model: str = "") -> None:
        """
        Lưu cấu hình LLM chính và LLM dự phòng vào tệp .env và cập nhật biến trong runtime Config.
        """
        base_url = base_url.strip()
        if base_url.endswith("/chat/completions"):
            base_url = base_url[:-len("/chat/completions")]

        backup_base_url = backup_base_url.strip()
        if backup_base_url.endswith("/chat/completions"):
            backup_base_url = backup_base_url[:-len("/chat/completions")]

        cls.LLM_BASE_URL = base_url
        cls.LLM_API_KEY = api_key.strip()
        cls.LLM_MODEL = model.strip()

        cls.LLM_BACKUP_ENABLED = bool(backup_enabled)
        cls.LLM_BACKUP_BASE_URL = backup_base_url
        cls.LLM_BACKUP_API_KEY = backup_api_key.strip()
        cls.LLM_BACKUP_MODEL = backup_model.strip()

        os.environ["LLM_BASE_URL"] = cls.LLM_BASE_URL
        os.environ["LLM_API_KEY"] = cls.LLM_API_KEY
        os.environ["LLM_MODEL"] = cls.LLM_MODEL

        os.environ["LLM_BACKUP_ENABLED"] = "true" if cls.LLM_BACKUP_ENABLED else "false"
        os.environ["LLM_BACKUP_BASE_URL"] = cls.LLM_BACKUP_BASE_URL
        os.environ["LLM_BACKUP_API_KEY"] = cls.LLM_BACKUP_API_KEY
        os.environ["LLM_BACKUP_MODEL"] = cls.LLM_BACKUP_MODEL

        env_file = cls.BASE_DIR / ".env"
        lines = []
        keys_updated = set()

        val_map = {
            "LLM_BASE_URL": cls.LLM_BASE_URL,
            "LLM_API_KEY": cls.LLM_API_KEY,
            "LLM_MODEL": cls.LLM_MODEL,
            "LLM_BACKUP_ENABLED": "true" if cls.LLM_BACKUP_ENABLED else "false",
            "LLM_BACKUP_BASE_URL": cls.LLM_BACKUP_BASE_URL,
            "LLM_BACKUP_API_KEY": cls.LLM_BACKUP_API_KEY,
            "LLM_BACKUP_MODEL": cls.LLM_BACKUP_MODEL,
        }

        if env_file.exists():
            with open(env_file, "r", encoding="utf-8") as f:
                for line in f:
                    matched = False
                    for k, v in val_map.items():
                        if line.strip().startswith(f"{k}="):
                            lines.append(f"{k}={v}\n")
                            keys_updated.add(k)
                            matched = True
                            break
                    if not matched:
                        lines.append(line)

        for k, v in val_map.items():
            if k not in keys_updated:
                lines.append(f"{k}={v}\n")

        with open(env_file, "w", encoding="utf-8") as f:
            f.writelines(lines)


# Tự động khởi tạo thư mục tạm và xuất file ngay khi module được import
Config.ensure_directories()
