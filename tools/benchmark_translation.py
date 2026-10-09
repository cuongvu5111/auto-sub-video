"""Compare LLM batch sizes against one saved, identical transcript."""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from config import Config
from core.translator import translate_segments


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("transcript", type=Path, help="JSON fixture created by export_transcript.py")
    parser.add_argument("--batch-sizes", default="4,8", help="Comma-separated batch sizes to compare")
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--output-json", type=Path, help="Defaults to output/benchmarks/translation.json")
    args = parser.parse_args()
    if not args.transcript.is_file():
        parser.error(f"Transcript JSON does not exist: {args.transcript}")
    try:
        batch_sizes = [int(value.strip()) for value in args.batch_sizes.split(",") if value.strip()]
    except ValueError:
        parser.error("--batch-sizes must be comma-separated integers")
    if not batch_sizes or any(size < 1 or size > 32 for size in batch_sizes):
        parser.error("batch sizes must be between 1 and 32")
    if args.repeats < 1:
        parser.error("--repeats must be at least 1")

    fixture = json.loads(args.transcript.read_text(encoding="utf-8"))
    segments = fixture.get("segments")
    if not isinstance(segments, list) or not segments:
        parser.error("Transcript must contain a non-empty 'segments' list")

    report_path = args.output_json or Config.OUTPUT_DIR / "benchmarks" / "translation.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    records = []

    def save_report(complete: bool = False) -> None:
        report_path.write_text(
            json.dumps({
                "transcript": str(args.transcript.resolve()),
                "segment_count": len(segments),
                "model": Config.LLM_MODEL,
                "batch_sizes": batch_sizes,
                "repeats": args.repeats,
                "complete": complete,
                "results": records,
            }, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    for batch_size in batch_sizes:
        elapsed_runs = []
        run_results = []
        batch_record = {"batch_size": batch_size, "median_seconds": None, "runs": run_results}
        records.append(batch_record)
        for repeat in range(1, args.repeats + 1):
            messages = []
            started = time.perf_counter()
            translated = translate_segments(
                segments,
                source_lang="Chinese",
                target_lang="Vietnamese",
                batch_size=batch_size,
                progress_callback=lambda message, _percent: messages.append(message),
            )
            elapsed = time.perf_counter() - started
            elapsed_runs.append(elapsed)
            fallbacks = sum(item.get("translation_status") == "source_fallback" for item in translated)
            requests = sum(1 for message in messages if re.search(r"Translating batch", message))
            run_results.append({
                "repeat": repeat,
                "elapsed_seconds": elapsed,
                "request_count_including_splits": requests,
                "translated_segments": len(translated),
                "fallback_segments": fallbacks,
                "segments": translated,
            })
            batch_record["median_seconds"] = statistics.median(elapsed_runs)
            save_report()
            print(f"batch={batch_size} repeat={repeat}: {elapsed:.2f}s; requests={requests}; fallbacks={fallbacks}", flush=True)

    save_report(complete=True)
    print(f"Translation benchmark saved to: {report_path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
