"""Parse timed SRT subtitles into the pipeline's segment schema."""

import re
from pathlib import Path
from typing import Any, Dict, List


class SubtitleFileError(Exception):
    """Raised when an SRT file is missing, unreadable, or malformed."""


_TIMESTAMP = re.compile(
    r"^(?P<sh>\d{1,2}):(?P<sm>\d{2}):(?P<ss>\d{2})[,.](?P<sms>\d{1,3})\s+-->\s+"
    r"(?P<eh>\d{1,2}):(?P<em>\d{2}):(?P<es>\d{2})[,.](?P<ems>\d{1,3})(?:\s+.*)?$"
)


def _to_seconds(match: re.Match, prefix: str) -> float:
    milliseconds = int(match.group(f"{prefix}ms").ljust(3, "0")[:3])
    return (
        int(match.group(f"{prefix}h")) * 3600
        + int(match.group(f"{prefix}m")) * 60
        + int(match.group(f"{prefix}s"))
        + milliseconds / 1000.0
    )


def parse_srt(srt_path: str | Path) -> List[Dict[str, Any]]:
    path = Path(srt_path).expanduser().resolve()
    if not path.is_file():
        raise SubtitleFileError(f"Subtitle file does not exist: {path}")
    if path.stat().st_size > 20 * 1024 * 1024:
        raise SubtitleFileError("Subtitle file is larger than the 20 MB limit.")

    content = None
    for encoding in ("utf-8-sig", "utf-8", "cp1258", "cp1252"):
        try:
            content = path.read_text(encoding=encoding)
            break
        except UnicodeDecodeError:
            continue
    if content is None:
        raise SubtitleFileError("Subtitle file encoding is not supported. Save it as UTF-8 and try again.")

    normalized = content.replace("\r\n", "\n").replace("\r", "\n")
    blocks = re.split(r"\n\s*\n", normalized.strip())
    segments: List[Dict[str, Any]] = []
    previous_start = -1.0
    for block_number, block in enumerate(blocks, start=1):
        lines = [line.strip("\ufeff") for line in block.split("\n")]
        if lines and lines[0].strip().isdigit():
            lines = lines[1:]
        if not lines:
            continue

        timing_index = next((idx for idx, line in enumerate(lines) if "-->" in line), None)
        if timing_index is None:
            raise SubtitleFileError(f"SRT block {block_number} has no timestamp line.")
        match = _TIMESTAMP.match(lines[timing_index].strip())
        if not match:
            raise SubtitleFileError(f"SRT block {block_number} has an invalid timestamp line.")

        for prefix in ("s", "e"):
            if int(match.group(f"{prefix}m")) > 59 or int(match.group(f"{prefix}s")) > 59:
                raise SubtitleFileError(f"SRT block {block_number} has out-of-range timestamp fields.")

        start = _to_seconds(match, "s")
        end = _to_seconds(match, "e")
        text = " ".join(line.strip() for line in lines[timing_index + 1:] if line.strip())
        if end <= start:
            raise SubtitleFileError(f"SRT block {block_number} ends before it starts.")
        if start < previous_start:
            raise SubtitleFileError(f"SRT block {block_number} is out of chronological order.")
        if not text:
            raise SubtitleFileError(f"SRT block {block_number} has no subtitle text.")

        previous_start = start
        segments.append({
            "index": len(segments),
            "start": start,
            "end": end,
            "text": text,
        })

    if not segments:
        raise SubtitleFileError("The SRT file contains no timed subtitle entries.")
    return segments
