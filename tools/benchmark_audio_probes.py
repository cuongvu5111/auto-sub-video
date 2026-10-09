"""Compare PyAV audio duration probes with the FFmpeg subprocess fallback."""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from core.audio_extractor import find_ffmpeg
from core.tts_engine import get_audio_duration
from core.process import run_process


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--probes", type=int, default=30, help="Duration probes per measurement")
    parser.add_argument("--repeats", type=int, default=3, help="Number of measurements")
    args = parser.parse_args()
    if args.probes < 1 or args.repeats < 1:
        parser.error("probes and repeats must be positive")

    temp_root = PROJECT_ROOT / "temp"
    temp_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="duration_benchmark_", dir=temp_root) as tmp:
        audio_path = Path(tmp) / "sample.mp3"
        run_process(
            [
                find_ffmpeg(), "-y", "-f", "lavfi", "-i",
                "sine=frequency=440:sample_rate=24000:duration=1.0",
                "-c:a", "libmp3lame", "-b:a", "48k", str(audio_path),
            ],
            timeout=30,
            check=True,
        )

        pyav_seconds = []
        ffmpeg_seconds = []
        for _ in range(args.repeats):
            started = time.perf_counter()
            pyav_duration = None
            for _ in range(args.probes):
                pyav_duration = get_audio_duration(audio_path)
            pyav_seconds.append(time.perf_counter() - started)

            started = time.perf_counter()
            with patch("core.tts_engine._get_audio_duration_from_pyav", return_value=None):
                ffmpeg_duration = None
                for _ in range(args.probes):
                    ffmpeg_duration = get_audio_duration(audio_path)
            ffmpeg_seconds.append(time.perf_counter() - started)

        if pyav_duration is None or ffmpeg_duration is None or abs(pyav_duration - ffmpeg_duration) > 0.10:
            raise RuntimeError(
                f"Duration probe mismatch: PyAV={pyav_duration}, FFmpeg={ffmpeg_duration}"
            )

    pyav_median = statistics.median(pyav_seconds)
    ffmpeg_median = statistics.median(ffmpeg_seconds)
    print(json.dumps({
        "workload": {"format": "MP3", "probes_per_run": args.probes, "repeats": args.repeats},
        "duration_seconds": {"pyav": pyav_duration, "ffmpeg": ffmpeg_duration},
        "duration_difference_seconds": abs(pyav_duration - ffmpeg_duration),
        "runs": {"pyav_total_seconds": pyav_seconds, "ffmpeg_total_seconds": ffmpeg_seconds},
        "summary": {
            "pyav_median_seconds_per_probe": pyav_median / args.probes,
            "ffmpeg_median_seconds_per_probe": ffmpeg_median / args.probes,
            "speedup_factor": ffmpeg_median / pyav_median if pyav_median else None,
        },
        "note": "MP3 encoder delay/padding can make container durations differ by a few frames.",
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
