"""Repeatable live Edge TTS timing, ordering, and success-rate benchmark."""

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
from core.tts_engine import process_dubbing_segments


PHRASES = [
    "Nay mình cùng khám phá món này nhé.",
    "Nhìn nhỏ vậy mà thơm quá đi.",
    "Đầu tiên, mình rửa thật sạch đã.",
    "Cho thêm một chút gia vị thôi.",
    "Mọi người nhìn màu sắc này nè.",
    "Chờ thêm vài phút là dùng được.",
    "Cách làm cũng đơn giản lắm.",
    "Thành phẩm trông hấp dẫn chưa?",
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--concurrencies", default="1,2", help="Comma-separated limits (1–4)")
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--pacing", type=float, default=Config.TTS_REQUEST_PACING_SECONDS)
    parser.add_argument("--output-json", type=Path, help="Defaults to output/benchmarks/tts.json")
    args = parser.parse_args()
    try:
        limits = [int(value.strip()) for value in args.concurrencies.split(",") if value.strip()]
    except ValueError:
        parser.error("--concurrencies must be comma-separated integers")
    if not limits or any(value < 1 or value > 4 for value in limits):
        parser.error("concurrency limits must be between 1 and 4")
    if args.repeats < 1 or not 0 <= args.pacing <= 2:
        parser.error("repeats must be positive and pacing must be between 0 and 2 seconds")

    output_root = Config.OUTPUT_DIR / "benchmarks" / "tts_runs"
    output_root.mkdir(parents=True, exist_ok=True)
    report_path = args.output_json or Config.OUTPUT_DIR / "benchmarks" / "tts_concurrency.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    original_concurrency = Config.TTS_MAX_CONCURRENCY
    original_pacing = Config.TTS_REQUEST_PACING_SECONDS
    records = []

    def save_report(complete=False):
        report_path.write_text(json.dumps({
            "voice": Config.DEFAULT_VOICE,
            "phrases_per_run": len(PHRASES),
            "concurrencies": limits,
            "repeats": args.repeats,
            "request_start_pacing_seconds": args.pacing,
            "complete": complete,
            "results": records,
        }, ensure_ascii=False, indent=2), encoding="utf-8")

    try:
        Config.TTS_REQUEST_PACING_SECONDS = args.pacing
        for concurrency in limits:
            Config.TTS_MAX_CONCURRENCY = concurrency
            elapsed_runs = []
            run_records = []
            group = {"concurrency": concurrency, "median_seconds": None, "runs": run_records}
            records.append(group)
            for repeat in range(1, args.repeats + 1):
                run_dir = output_root / f"concurrency_{concurrency}_repeat_{repeat}"
                logs = []
                segments = [
                    {
                        "index": index,
                        "start": index * 2.5,
                        "end": index * 2.5 + 2.3,
                        "translated_text": phrase,
                    }
                    for index, phrase in enumerate(PHRASES)
                ]
                started = time.perf_counter()
                results = process_dubbing_segments(
                    segments,
                    output_dir=run_dir,
                    progress_callback=lambda message, _percent: logs.append(message),
                )
                elapsed = time.perf_counter() - started
                elapsed_runs.append(elapsed)
                success_count = sum(
                    item.get("tts_status") == "success" and item.get("sync_status") == "success"
                    for item in results
                )
                ordering_ok = [item.get("index") for item in results] == list(range(len(PHRASES)))
                timing_message = next((message for message in logs if message.startswith("TTS performance timings:")), "")
                request_wall = re.search(r"TTS request wall time=([0-9.]+)s", timing_message)
                cumulative = re.search(r"TTS requests incl\. retries=([0-9.]+)s", timing_message)
                run_records.append({
                    "repeat": repeat,
                    "elapsed_seconds": elapsed,
                    "successful_segments": success_count,
                    "failed_segments": len(results) - success_count,
                    "tts_successful_segments": sum(item.get("tts_status") == "success" for item in results),
                    "sync_failures": sum(item.get("sync_status") != "success" for item in results),
                    "stable_source_order": ordering_ok,
                    "request_wall_seconds": float(request_wall.group(1)) if request_wall else None,
                    "cumulative_request_seconds": float(cumulative.group(1)) if cumulative else None,
                })
                group["median_seconds"] = statistics.median(elapsed_runs)
                save_report()
                print(
                    f"concurrency={concurrency} repeat={repeat}: {elapsed:.2f}s; "
                    f"{success_count}/{len(results)} successful; order_ok={ordering_ok}",
                    flush=True,
                )
    finally:
        Config.TTS_MAX_CONCURRENCY = original_concurrency
        Config.TTS_REQUEST_PACING_SECONDS = original_pacing

    save_report(complete=True)
    print(f"TTS benchmark saved to: {report_path.resolve()}")
    return 0 if all(run["failed_segments"] == 0 and run["stable_source_order"] for group in records for run in group["runs"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
