"""Benchmark Whisper model/beam/word-timestamp settings on a local audio file."""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from config import Config
from core.transcriber import get_whisper_model, transcribe_audio


def _csv_values(value: str, cast):
    try:
        return [cast(part.strip()) for part in value.split(",") if part.strip()]
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("audio", type=Path, help="Existing WAV/audio file; no fixture or provider is created")
    parser.add_argument("--models", default="base", help="Comma-separated faster-whisper model sizes")
    parser.add_argument("--beam-sizes", default="1,3,5", help="Comma-separated positive beam sizes")
    parser.add_argument("--word-timestamps", choices=("true", "false", "both"), default="both")
    parser.add_argument("--language", default="auto", help="Language code or auto")
    parser.add_argument("--repeats", type=int, default=2, help="Measured runs per setting")
    parser.add_argument("--warmup", type=int, default=1, help="Unmeasured warmup runs per setting")
    args = parser.parse_args()

    if not args.audio.is_file():
        parser.error(f"Audio file does not exist: {args.audio}")
    if args.repeats < 1 or args.warmup < 0:
        parser.error("repeats must be positive and warmup cannot be negative")
    models = _csv_values(args.models, str)
    beam_sizes = _csv_values(args.beam_sizes, int)
    if not models or not beam_sizes or any(size < 1 for size in beam_sizes):
        parser.error("models and beam sizes must be non-empty; beam sizes must be positive")
    word_modes = [True, False] if args.word_timestamps == "both" else [args.word_timestamps == "true"]

    results = []
    for model_name in models:
        Config.WHISPER_MODEL = model_name
        load_started = time.perf_counter()
        get_whisper_model(model_size=model_name)
        model_load_seconds = time.perf_counter() - load_started

        for beam_size in beam_sizes:
            Config.WHISPER_BEAM_SIZE = beam_size
            for word_timestamps in word_modes:
                for _ in range(args.warmup):
                    transcribe_audio(
                        args.audio,
                        language=args.language,
                        word_timestamps=word_timestamps,
                    )

                elapsed_runs = []
                segment_count = 0
                word_count = 0
                for _ in range(args.repeats):
                    started = time.perf_counter()
                    segments = transcribe_audio(
                        args.audio,
                        language=args.language,
                        word_timestamps=word_timestamps,
                    )
                    elapsed_runs.append(time.perf_counter() - started)
                    segment_count = len(segments)
                    word_count = sum(len(segment.get("words", [])) for segment in segments)

                results.append({
                    "model": model_name,
                    "beam_size": beam_size,
                    "word_timestamps": word_timestamps,
                    "model_load_seconds_first_use": model_load_seconds,
                    "runs_seconds": elapsed_runs,
                    "median_seconds": statistics.median(elapsed_runs),
                    "segments": segment_count,
                    "word_timestamps_returned": word_count,
                })

    print(json.dumps({
        "audio": str(args.audio.resolve()),
        "language": args.language,
        "device": Config.WHISPER_DEVICE,
        "compute_type": Config.WHISPER_COMPUTE_TYPE,
        "repeats": args.repeats,
        "warmup_runs": args.warmup,
        "results": results,
        "note": "The first model load may download model weights; compare settings on the same machine and audio.",
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
