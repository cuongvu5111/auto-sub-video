"""Benchmark the in-memory audio mixer with a repeatable synthetic workload."""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import tempfile
import time
import tracemalloc
import wave
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from core.audio_mixer import create_mixed_audio_track


def _write_silence(path: Path, duration: float, sample_rate: int, channels: int) -> None:
    frame_count = round(duration * sample_rate)
    bytes_per_second = sample_rate * channels * 2
    block = b"\0" * min(bytes_per_second, 1024 * 1024)
    remaining = frame_count * channels * 2

    with wave.open(str(path), "wb") as output:
        output.setnchannels(channels)
        output.setsampwidth(2)
        output.setframerate(sample_rate)
        while remaining:
            chunk = block[:min(len(block), remaining)]
            output.writeframesraw(chunk)
            remaining -= len(chunk)
        output.writeframes(b"")


def _run_once(
    source_audio: Path,
    segment_audio: Path,
    output_audio: Path,
    duration: float,
    segment_count: int,
    output_sample_rate: int,
) -> dict[str, float]:
    interval = duration / max(1, segment_count)
    segment_duration = min(1.0, interval)
    segments = [
        {
            "index": index,
            "start": index * interval,
            "end": min(duration, index * interval + segment_duration),
            "dubbed_audio_path": str(segment_audio),
        }
        for index in range(segment_count)
    ]

    tracemalloc.start()
    started = time.perf_counter()
    try:
        create_mixed_audio_track(
            source_audio,
            segments,
            output_audio,
            total_duration=duration,
        )
        elapsed = time.perf_counter() - started
        _, peak_python_bytes = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()

    with wave.open(str(output_audio), "rb") as rendered:
        rendered_duration = rendered.getnframes() / rendered.getframerate()
    if abs(rendered_duration - duration) > 1.0 / output_sample_rate:
        raise RuntimeError(
            f"Mixed audio duration mismatch: expected {duration:.3f}s, got {rendered_duration:.3f}s"
        )

    return {
        "elapsed_seconds": elapsed,
        "peak_python_mib": peak_python_bytes / (1024 * 1024),
        "rendered_duration_seconds": rendered_duration,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--duration", type=float, default=60.0, help="Synthetic source duration in seconds")
    parser.add_argument("--segments", type=int, default=100, help="Number of dubbed segments")
    parser.add_argument("--repeats", type=int, default=3, help="Number of measured mixer runs")
    parser.add_argument("--sample-rate", type=int, default=48000, help="Synthetic source sample rate")
    parser.add_argument("--channels", type=int, default=2, help="Synthetic source channel count")
    args = parser.parse_args()

    if args.duration <= 0 or args.segments < 0 or args.repeats < 1 or args.sample_rate <= 0:
        parser.error("duration, repeats, and sample rate must be positive; segments cannot be negative")
    if args.channels not in (1, 2):
        parser.error("channels must be either 1 (mono) or 2 (stereo)")

    workspace_root = PROJECT_ROOT / "temp"
    workspace_root.mkdir(parents=True, exist_ok=True)
    results = []
    with tempfile.TemporaryDirectory(prefix="mixer_benchmark_", dir=workspace_root) as tmp:
        folder = Path(tmp)
        source_audio = folder / "source.wav"
        segment_audio = folder / "segment.wav"
        _write_silence(source_audio, args.duration, args.sample_rate, args.channels)
        _write_silence(segment_audio, min(1.0, args.duration), 24000, 1)

        for repeat in range(args.repeats):
            output_audio = folder / f"mixed_{repeat}.wav"
            results.append(
                _run_once(
                    source_audio,
                    segment_audio,
                    output_audio,
                    args.duration,
                    args.segments,
                    args.sample_rate,
                )
            )

    elapsed_values = [item["elapsed_seconds"] for item in results]
    memory_values = [item["peak_python_mib"] for item in results]
    print(json.dumps({
        "workload": {
            "duration_seconds": args.duration,
            "segments": args.segments,
            "source_sample_rate": args.sample_rate,
            "source_channels": args.channels,
            "repeats": args.repeats,
        },
        "runs": results,
        "summary": {
            "median_elapsed_seconds": statistics.median(elapsed_values),
            "max_elapsed_seconds": max(elapsed_values),
            "max_peak_python_mib": max(memory_values),
        },
        "note": "Peak Python allocations are not the same as total process RSS.",
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
