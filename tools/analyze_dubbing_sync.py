"""Re-synthesize a saved translation fixture and report subtitle/voice overlap."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from config import Config
from core.tts_engine import process_dubbing_segments


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("translation_report", type=Path, help="JSON from benchmark_translation.py")
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--repeat", type=int, default=1, help="Run number in the translation report")
    parser.add_argument("--output-json", type=Path, help="Defaults to output/benchmarks/dubbing_sync.json")
    args = parser.parse_args()
    if not args.translation_report.is_file():
        parser.error(f"Translation report does not exist: {args.translation_report}")

    report = json.loads(args.translation_report.read_text(encoding="utf-8"))
    group = next((item for item in report.get("results", []) if item.get("batch_size") == args.batch_size), None)
    if group is None or not 1 <= args.repeat <= len(group.get("runs", [])):
        parser.error("Requested batch size/repeat is not present in the translation report")
    segments = group["runs"][args.repeat - 1].get("segments", [])
    if not segments:
        parser.error("Selected translation run contains no segments")

    output_path = args.output_json or Config.OUTPUT_DIR / "benchmarks" / "dubbing_sync.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    progress = []
    with tempfile.TemporaryDirectory(prefix="dubbing_sync_", dir=Config.TEMP_DIR) as tmp:
        synced = process_dubbing_segments(
            segments,
            output_dir=Path(tmp),
            progress_callback=lambda message, _percent: progress.append(message),
        )
        items = []
        overrun_count = 0
        overlap_count = 0
        for index, segment in enumerate(synced):
            start = float(segment.get("start", 0.0))
            end = float(segment.get("end", start))
            duration = float(segment.get("dubbed_duration", 0.0))
            next_start = float(synced[index + 1]["start"]) if index + 1 < len(synced) else None
            interval_overrun = max(0.0, duration - (end - start))
            next_line_overlap = max(0.0, start + duration - next_start) if next_start is not None else 0.0
            overrun_count += interval_overrun > 0.10
            overlap_count += next_line_overlap > 0.10
            items.append({
                "index": segment.get("index", index),
                "start": start,
                "subtitle_end": end,
                "next_start": next_start,
                "dubbed_duration": duration,
                "subtitle_overrun_seconds": round(interval_overrun, 3),
                "next_line_overlap_seconds": round(next_line_overlap, 3),
                "tts_status": segment.get("tts_status"),
                "sync_status": segment.get("sync_status"),
            })
        report_data = {
            "translation_report": str(args.translation_report.resolve()),
            "batch_size": args.batch_size,
            "repeat": args.repeat,
            "segments": len(synced),
            "tts_failures": sum(item.get("tts_status") != "success" for item in synced),
            "sync_failures": sum(item.get("sync_status") != "success" for item in synced),
            "subtitle_overrun_segments_over_0_10s": int(overrun_count),
            "actual_next_line_overlap_segments_over_0_10s": int(overlap_count),
            "maximum_subtitle_overrun_seconds": max((item["subtitle_overrun_seconds"] for item in items), default=0.0),
            "maximum_next_line_overlap_seconds": max((item["next_line_overlap_seconds"] for item in items), default=0.0),
            "elapsed_seconds": time.perf_counter() - started,
            "segments_detail": items,
        }

    output_path.write_text(json.dumps(report_data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"TTS {report_data['segments']}/{report_data['segments']} complete; "
        f"overrun={report_data['subtitle_overrun_segments_over_0_10s']}, "
        f"actual overlap={report_data['actual_next_line_overlap_segments_over_0_10s']}, "
        f"elapsed={report_data['elapsed_seconds']:.2f}s",
        flush=True,
    )
    print(f"Sync report saved to: {output_path.resolve()}")
    return 0 if not report_data["tts_failures"] and not report_data["sync_failures"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
