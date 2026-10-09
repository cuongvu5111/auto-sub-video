"""
AutoDub Studio - Background Processing Worker Thread.
Handles batch video queue processing asynchronously, keeping the UI responsive.
"""

from typing import List, Dict, Any
from PySide6.QtCore import QThread, Signal
from pipeline import run_pipeline


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
        self._is_cancelled = False

    def cancel(self):
        """Request the worker thread to cancel gracefully."""
        self._is_cancelled = True

    def run(self):
        total = len(self.tasks)
        success_count = 0
        try:
            self.sig_log.emit(f"=== BATCH PROCESSING STARTED ({total} VIDEOS) ===")

            for idx, task in enumerate(self.tasks):
                if self._is_cancelled:
                    self.sig_log.emit("⚠️ Cancel signal received from user.")
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
                    final_video = run_pipeline(
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
                        progress_callback=progress_hook,
                        cancel_check=lambda: self._is_cancelled
                    )
                    success_count += 1
                    self.sig_item_status.emit(row, f"✓ Done - {final_video.name}", "#27AE60")
                    self.sig_log.emit(f"✓ COMPLETED: {final_video.name}")

                except InterruptedError:
                    self.sig_item_status.emit(row, "⏹ Stopped", "#95A5A6")
                    self.sig_log.emit("⏹ STOPPED: Tiến trình đã dừng ngay lập tức theo yêu cầu.")
                    break
                except Exception as e:
                    self.sig_item_status.emit(row, f"❌ Failed: {str(e)[:30]}", "#E74C3C")
                    self.sig_log.emit(f"❌ ERROR PROCESSING: {str(e)}")

            if self._is_cancelled:
                self.sig_log.emit("\n⚠️ Batch processing cancelled by user.")
            self.sig_progress.emit(100.0)
            self.sig_log.emit(f"\n=== FINISHED: {success_count}/{total} VIDEOS SUCCESSFUL ===")
        finally:
            # Phát tín hiệu hoàn tất để MainWindow phục hồi trạng thái nút bấm
            self.sig_finished.emit(success_count, total)
