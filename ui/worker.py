"""
AutoDub Studio - Background Processing Worker Thread.
Handles batch video queue processing asynchronously, keeping the UI responsive.
"""

import threading
from pathlib import Path
from typing import List, Dict, Any
from PySide6.QtCore import QThread, Signal
from pipeline import run_pipeline_job
from core.job_result import JobStatus
from config import Config


class DubbingWorker(QThread):
    """
    Background worker thread to handle video queue processing,
    keeping the UI completely responsive and freeze-free.
    """
    sig_log = Signal(str)
    sig_progress = Signal(float)
    sig_item_status = Signal(int, str, str)  # (row_index, status_text, hex_color)
    sig_finished = Signal(int, int)  # (success_count, total_count)

    def __init__(self, tasks: List[Dict[str, Any]], options: Dict[str, Any]):
        super().__init__()
        self.tasks = tasks
        self.options = options
        self._cancel_event = threading.Event()

    @property
    def _is_cancelled(self) -> bool:
        return self._cancel_event.is_set()

    def cancel(self):
        """Request the worker thread to cancel gracefully."""
        self._cancel_event.set()

    def run(self):
        total = len(self.tasks)
        success_count = 0
        try:
            self.sig_log.emit(f"=== BATCH PROCESSING STARTED ({total} VIDEOS) ===")

            for idx, task in enumerate(self.tasks):
                if self._is_cancelled:
                    self.sig_log.emit("⚠️ Cancel signal received from user.")
                    for pending_task in self.tasks[idx:]:
                        self.sig_item_status.emit(pending_task["row"], "⏹ Cancelled", "#95A5A6")
                    break

                row = task["row"]
                source = task["source"]
                self.sig_item_status.emit(row, "⏳ Processing...", "#E67E22")
                self.sig_log.emit(f"\n[Video {idx + 1}/{total}]: {source}")

                def progress_hook(msg: str, percent: float):
                    overall_percent = ((idx + (percent / 100.0)) / total) * 100.0
                    self.sig_progress.emit(overall_percent)
                    self.sig_log.emit(f"  » {msg}")

                try:
                    result = run_pipeline_job(
                        source=source,
                        source_lang=self.options.get("source_lang", "auto"),
                        voice=self.options.get("voice"),
                        ducking_volume=self.options.get("ducking_volume", 0.10),
                        burn_subtitles=self.options.get("burn_subtitles", True),
                        genre=self.options.get("genre", "Daily Life / Social Media"),
                        custom_terms=self.options.get("custom_terms", ""),
                        subtitle_options=self.options.get("subtitle_options"),
                        watermark_options=self.options.get("watermark_options"),
                        encoder=self.options.get("encoder"),
                        output_dir=self.options.get("output_dir"),
                        enable_dubbing=self.options.get("enable_dubbing", True),
                        subtitle_path=Path(task["subtitle_path"]) if task.get("subtitle_path") else None,
                        prefer_attached_subtitle=self.options.get("prefer_attached_subtitle", True),
                        translate_srt_only=self.options.get("translate_srt_only", False),
                        delay_offset=self.options.get("delay_offset", 0.0),
                        export_profile=self.options.get("export_profile"),
                        speech_rate=self.options.get("speech_speed", getattr(Config, "DEFAULT_SPEECH_SPEED", 1.15)),
                        progress_callback=progress_hook,
                        cancel_check=self._cancel_event.is_set
                    )
                    if result.status == JobStatus.CANCELLED:
                        self.sig_item_status.emit(row, "⏹ Stopped", "#95A5A6")
                        self.sig_log.emit("⏹ STOPPED: Tiến trình đã dừng ngay lập tức theo yêu cầu.")
                        for pending_task in self.tasks[idx + 1:]:
                            self.sig_item_status.emit(pending_task["row"], "⏹ Cancelled", "#95A5A6")
                        break
                    if result.status == JobStatus.FAILED:
                        error = result.error or "Unknown pipeline error"
                        self.sig_item_status.emit(row, f"❌ Failed: {error[:30]}", "#E74C3C")
                        self.sig_log.emit(f"❌ ERROR PROCESSING: {error}")
                        continue

                    final_video = result.output_path
                    if final_video is None:
                        self.sig_item_status.emit(row, "❌ Failed: missing output", "#E74C3C")
                        self.sig_log.emit("❌ ERROR PROCESSING: pipeline returned success without an output path")
                        continue

                    success_count += 1
                    if result.status == JobStatus.COMPLETED_WITH_WARNINGS:
                        self.sig_item_status.emit(row, f"⚠ Done with warnings - {final_video.name}", "#D97706")
                        self.sig_log.emit(f"⚠ COMPLETED WITH WARNINGS: {final_video.name}")
                    else:
                        self.sig_item_status.emit(row, f"✓ Done - {final_video.name}", "#27AE60")
                        self.sig_log.emit(f"✓ COMPLETED: {final_video.name}")
                except Exception as exc:
                    self.sig_item_status.emit(row, f"❌ Failed: {str(exc)[:30]}", "#E74C3C")
                    self.sig_log.emit(f"❌ ERROR PROCESSING: {exc}")

            if self._is_cancelled:
                self.sig_log.emit("\n⚠️ Batch processing cancelled by user.")
            if not self._is_cancelled:
                self.sig_progress.emit(100.0)
            self.sig_log.emit(f"\n=== FINISHED: {success_count}/{total} VIDEOS SUCCESSFUL ===")
        finally:
            # Phát tín hiệu hoàn tất để MainWindow phục hồi trạng thái nút bấm
            self.sig_finished.emit(success_count, total)
