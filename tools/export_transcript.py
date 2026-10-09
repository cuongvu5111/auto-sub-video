"""Transcribe a local audio file to a reusable JSON segment fixture."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from config import Config
from core.transcriber import transcribe_audio


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("audio", type=Path, help="Existing audio file")
    parser.add_argument("output", type=Path, help="JSON file to create")
    parser.add_argument("--language", default="auto")
    parser.add_argument("--model", default=Config.WHISPER_MODEL)
    parser.add_argument("--beam-size", type=int, default=Config.WHISPER_BEAM_SIZE)
    args = parser.parse_args()
    if not args.audio.is_file():
        parser.error(f"Audio file does not exist: {args.audio}")
    if args.beam_size < 1:
        parser.error("--beam-size must be positive")

    Config.WHISPER_MODEL = args.model
    Config.WHISPER_BEAM_SIZE = args.beam_size
    segments = transcribe_audio(
        args.audio,
        language=args.language,
        word_timestamps=Config.WHISPER_WORD_TIMESTAMPS,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps({
            "audio": str(args.audio.resolve()),
            "language": args.language,
            "model": args.model,
            "beam_size": args.beam_size,
            "word_timestamps": Config.WHISPER_WORD_TIMESTAMPS,
            "segments": segments,
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Saved {len(segments)} segments to {args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
