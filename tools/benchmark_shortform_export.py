"""Benchmark local, SRT-only TikTok portrait renders without network providers."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from core.audio_extractor import find_ffmpeg
from core.media_probe import probe_media
from pipeline import run_pipeline
from tools.benchmark_pipeline import PeakRssSampler


def _write_srt(path: Path, duration: int) -> int:
    entries = []
    start = 0.25
    index = 1
    while start < duration - 0.2:
        end = min(start + 1.6, duration - 0.05)
        start_ms = round(start * 1000)
        end_ms = round(end * 1000)
        entries.append(
            f"{index}\n{start_ms // 3600000:02d}:{(start_ms // 60000) % 60:02d}:"
            f"{(start_ms // 1000) % 60:02d},{start_ms % 1000:03d} --> "
            f"{end_ms // 3600000:02d}:{(end_ms // 60000) % 60:02d}:"
            f"{(end_ms // 1000) % 60:02d},{end_ms % 1000:03d}\n"
            f"Sample short-form dialogue {index}\n"
        )
        start += 2.2
        index += 1
    path.write_text("\n".join(entries), encoding="utf-8")
    return len(entries)


def run_benchmark(durations: list[int], repeats: int, output_json: Path) -> dict:
    ffmpeg = find_ffmpeg()
    output_json.parent.mkdir(parents=True, exist_ok=True)
    fixture_root = output_json.parent / "shortform_fixtures"
    fixture_root.mkdir(parents=True, exist_ok=True)
    output_root = output_json.parent / "shortform_runs"
    output_root.mkdir(parents=True, exist_ok=True)

    records = []
    for duration in durations:
        source = fixture_root / f"landscape_{duration}s.mp4"
        subtitle = fixture_root / f"landscape_{duration}s.srt"
        if not source.exists():
            subprocess.run(
                [ffmpeg, "-y", "-f", "lavfi", "-i", f"testsrc2=size=640x360:rate=30:duration={duration}",
                 "-f", "lavfi", "-i", f"sine=frequency=220:duration={duration}", "-c:v", "libx264",
                 "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(source)],
                check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        cue_count = _write_srt(subtitle, duration)
        for fit_mode in ("crop", "contain"):
            for repeat in range(1, repeats + 1):
                target_dir = output_root / f"{duration}s_{fit_mode}_run_{repeat}"
                target_dir.mkdir(parents=True, exist_ok=True)
                messages = []

                def translate(segments, **_kwargs):
                    return [
                        {**item, "translated_text": f"Thoại mẫu {item['index'] + 1}", "translation_status": "translated"}
                        for item in segments
                    ]

                started = time.perf_counter()
                with PeakRssSampler() as sampler, patch("pipeline.translate_segments", side_effect=translate):
                    output = run_pipeline(
                        source=str(source), subtitle_path=subtitle, prefer_attached_subtitle=True,
                        translate_srt_only=True, enable_dubbing=False, burn_subtitles=True,
                        encoder="libx264", output_dir=target_dir,
                        export_profile={"name": "tiktok_9_16", "width": 1080, "height": 1920, "fit_mode": fit_mode},
                        progress_callback=lambda message, _percent: messages.append(message),
                    )
                elapsed = time.perf_counter() - started
                info = probe_media(output)
                completion = next((message for message in reversed(messages) if "Stage timings:" in message), "")
                match = re.search(r"Stage timings: (.*)$", completion)
                records.append({
                    "source_duration_seconds": duration,
                    "fit_mode": fit_mode,
                    "repeat": repeat,
                    "subtitle_cues": cue_count,
                    "elapsed_seconds": round(elapsed, 3),
                    "stage_timings": match.group(1) if match else None,
                    "output_width": info.width,
                    "output_height": info.height,
                    "output_video_codec": info.video_codec,
                    "output_audio_codec": info.audio_codec,
                    "output_duration_seconds": round(info.duration, 3),
                    "output_bytes": output.stat().st_size,
                    "peak_rss_bytes": sampler.peak_bytes or None,
                    "peak_rss_source": sampler.source,
                    "provider_calls": 0,
                })
                print(
                    f"{duration}s {fit_mode} run {repeat}: {elapsed:.2f}s, "
                    f"{info.width}x{info.height}, {output.stat().st_size} bytes"
                )

    report = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "benchmark": "local SRT-only, no TTS, no network providers",
        "durations_seconds": durations,
        "repeats": repeats,
        "records": records,
    }
    output_json.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--durations", nargs="+", type=int, default=[10, 30])
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--output-json", type=Path, default=PROJECT_ROOT / "output/benchmarks/shortform_export.json")
    args = parser.parse_args()
    if args.repeats < 1 or any(duration < 1 for duration in args.durations):
        parser.error("Durations and repeats must be positive integers.")
    run_benchmark(args.durations, args.repeats, args.output_json.resolve())
    print(f"Report saved to {args.output_json.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
