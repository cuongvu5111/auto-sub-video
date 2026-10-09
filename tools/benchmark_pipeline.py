"""Run repeatable end-to-end jobs and record stage timings and peak process RSS."""

from __future__ import annotations

import argparse
import ctypes
import json
import re
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from ctypes import wintypes

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from config import Config
from core.media_probe import probe_media
from pipeline import run_pipeline


def _current_rss_bytes() -> tuple[int | None, str]:
    if sys.platform == "win32":
        class ProcessMemoryCounters(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD),
                ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        counters = ProcessMemoryCounters()
        counters.cb = ctypes.sizeof(counters)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        psapi = ctypes.WinDLL("psapi", use_last_error=True)
        kernel32.GetCurrentProcess.restype = wintypes.HANDLE
        psapi.GetProcessMemoryInfo.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(ProcessMemoryCounters),
            wintypes.DWORD,
        ]
        psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
        process = kernel32.GetCurrentProcess()
        ok = psapi.GetProcessMemoryInfo(process, ctypes.byref(counters), counters.cb)
        return (int(counters.WorkingSetSize), "Windows WorkingSetSize") if ok else (None, "unavailable")

    status_path = Path("/proc/self/status")
    if status_path.exists():
        for line in status_path.read_text(encoding="ascii").splitlines():
            if line.startswith("VmRSS:"):
                return int(line.split()[1]) * 1024, "Linux VmRSS"
    return None, "unavailable"


class PeakRssSampler:
    def __init__(self, interval_seconds: float = 0.25):
        self.interval_seconds = interval_seconds
        self.peak_bytes = 0
        self.source = "unavailable"
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._sample, daemon=True)

    def _record_current(self) -> None:
        current, source = _current_rss_bytes()
        if current is not None:
            self.peak_bytes = max(self.peak_bytes, current)
            self.source = source

    def _sample(self) -> None:
        while not self._stop.is_set():
            self._record_current()
            self._stop.wait(self.interval_seconds)

    def __enter__(self):
        self._record_current()
        self._thread.start()
        return self

    def __exit__(self, *_exc):
        self._stop.set()
        self._thread.join()
        self._record_current()


def _parse_progress(messages: list[str]) -> dict:
    metrics = {
        "transcribed_segments": None,
        "translated_segments": None,
        "translation_fallback_segments": 0,
        "adaptive_translation_splits": 0,
        "warnings": 0,
        "stage_timings_seconds": {},
    }
    for message in messages:
        match = re.search(r"Nhận diện hoàn tất:\s*(\d+)\s*câu thoại", message, re.IGNORECASE)
        if match:
            metrics["transcribed_segments"] = int(match.group(1))
        match = re.search(r"Translation completed:\s*(\d+)\s+dialogues", message, re.IGNORECASE)
        if match:
            metrics["translated_segments"] = int(match.group(1))
        match = re.search(r"(\d+) dialogue\(s\) kept in the source language", message, re.IGNORECASE)
        if match:
            metrics["translation_fallback_segments"] = int(match.group(1))
        if "retrying as smaller batches" in message.lower():
            metrics["adaptive_translation_splits"] += 1
        if "⚠" in message or "warning" in message.lower() or "cảnh báo" in message.lower():
            metrics["warnings"] += 1
        if "Stage timings:" in message:
            timing_text = message.split("Stage timings:", 1)[1]
            metrics["stage_timings_seconds"] = {
                name.strip(): float(seconds)
                for name, seconds in re.findall(r"([^,=]+)=([0-9]+(?:\.[0-9]+)?)s", timing_text)
            }
    return metrics


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sources", nargs="+", help="One or more local videos or supported video URLs")
    parser.add_argument("--repeats", type=int, default=1, help="Runs per source (default: 1)")
    parser.add_argument("--output-json", type=Path, help="Result JSON path; defaults under output/benchmarks")
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error("--repeats must be at least 1")

    output_root = Config.OUTPUT_DIR / "benchmarks"
    output_root.mkdir(parents=True, exist_ok=True)
    report_path = args.output_json or output_root / f"pipeline_{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    records = []

    for source_index, source in enumerate(args.sources, start=1):
        source_path = Path(source)
        input_info = probe_media(source_path) if source_path.is_file() else None
        for repeat_index in range(1, args.repeats + 1):
            messages = []
            current_phase = [None]

            def capture_progress(message: str, _percent: float) -> None:
                messages.append(message)
                match = re.match(r"(Step \d+/6):", message)
                if match and match.group(1) != current_phase[0]:
                    current_phase[0] = match.group(1)
                    print(f"  {current_phase[0]}: {message.split(':', 1)[1].strip()[:100]}", flush=True)

            run_dir = output_root / f"source_{source_index:02d}_run_{repeat_index:02d}"
            run_dir.mkdir(parents=True, exist_ok=True)
            print(f"Running source {source_index}/{len(args.sources)}, repeat {repeat_index}/{args.repeats}...")
            sampler = PeakRssSampler()
            started = time.perf_counter()
            try:
                with sampler:
                    result_path = run_pipeline(
                        source,
                        output_dir=run_dir,
                        progress_callback=capture_progress,
                    )
                output_info = probe_media(result_path)
                record = {
                    "source": source,
                    "repeat": repeat_index,
                    "status": "completed",
                    "elapsed_seconds": time.perf_counter() - started,
                    "input_duration_seconds": input_info.duration if input_info else None,
                    "output_duration_seconds": output_info.duration,
                    "output_audio_duration_seconds": output_info.audio_duration,
                    "output_path": str(result_path.resolve()),
                    "output_bytes": result_path.stat().st_size,
                    "peak_rss_bytes": sampler.peak_bytes or None,
                    "peak_rss_source": sampler.source,
                    **_parse_progress(messages),
                }
            except InterruptedError as exc:
                record = {"source": source, "repeat": repeat_index, "status": "cancelled", "error": str(exc)}
            except Exception as exc:
                record = {"source": source, "repeat": repeat_index, "status": "failed", "error": str(exc)}
            records.append(record)
            report_path.write_text(
                json.dumps({
                    "created_at_utc": datetime.now(timezone.utc).isoformat(),
                    "repeats_per_source": args.repeats,
                    "records": records,
                }, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            print(f"{record['status']}: {record.get('elapsed_seconds', 0):.2f}s; peak RSS={record.get('peak_rss_bytes')}")

    print(f"Benchmark report saved to: {report_path.resolve()}")
    return 0 if all(item["status"] == "completed" for item in records) else 1


if __name__ == "__main__":
    raise SystemExit(main())
