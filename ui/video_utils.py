"""
AutoDub Studio - Video Frame Extraction & Metadata Probe Utilities.
Provides fast FFmpeg frame snapshots and PyAV video resolution probing for live preview canvas.
"""

import sys
import subprocess
from pathlib import Path
from typing import Union, Optional, Dict, Any
from config import Config


def extract_video_frame_at(video_path: Union[str, Path], timestamp_sec: float = 1.0) -> Optional[str]:
    """
    Trích xuất nhanh một khung hình từ video tại mốc thời gian timestamp_sec bằng FFmpeg.
    Lưu vào thư mục temp/ để phục vụ preview subtitle và watermark.
    """
    try:
        vp = Path(video_path).resolve()
        if not vp.is_file():
            return None
        Config.TEMP_DIR.mkdir(parents=True, exist_ok=True)
        safe_sec = max(0.0, float(timestamp_sec))
        thumb_name = f"{vp.stem}_frame_{int(safe_sec * 100):06d}.jpg"
        thumb_path = Config.TEMP_DIR / thumb_name
        if thumb_path.is_file() and thumb_path.stat().st_size > 0:
            return str(thumb_path)

        from core.audio_extractor import find_ffmpeg
        ffmpeg_bin = find_ffmpeg()
        cmd = [
            str(ffmpeg_bin), "-y",
            "-ss", f"{safe_sec:.2f}",
            "-i", str(vp),
            "-vframes", "1",
            "-q:v", "2",
            str(thumb_path)
        ]
        flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=flags, timeout=5)
        if thumb_path.is_file() and thumb_path.stat().st_size > 0:
            return str(thumb_path)
    except Exception:
        pass
    return None


def get_video_meta(video_path: Union[str, Path]) -> Dict[str, Any]:
    """
    Lấy thông tin duration, kích thước width x height và aspect ratio của video
    sử dụng PyAV hoặc fallback nhẹ.
    """
    meta = {"duration": 15.0, "width": 720, "height": 1280, "aspect_ratio": "9:16"}
    try:
        import av
        with av.open(str(video_path)) as container:
            if container.duration:
                meta["duration"] = max(1.0, float(container.duration / av.time_base))
            if container.streams.video:
                v = container.streams.video[0]
                if v.width and v.height:
                    meta["width"] = v.width
                    meta["height"] = v.height
                    meta["aspect_ratio"] = "16:9" if v.width > v.height else "9:16"
            return meta
    except Exception:
        pass
    return meta
