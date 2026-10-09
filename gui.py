"""
AutoDub Studio - Native Windows Desktop Application Entry Point (PySide6 / Qt).
Designed for Go-Global distribution with an English UI, batch queue processing,
dual-column settings, smooth progress bar, and real-time terminal console log.

This module acts as the primary desktop application entry point and backward-compatible
Facade re-exporting all core UI components, dialogs, and background workers.
"""

import sys
import argparse
import json
from pathlib import Path
from PySide6.QtWidgets import QApplication

# Backward-compatible Re-exports
from ui.worker import DubbingWorker
from ui.main_window import MainWindow
from ui.dialogs.paste_links_dialog import PasteLinksDialog
from ui.dialogs.watermark_dialog import WatermarkConfigDialog
from ui.dialogs.subtitle_dialog import SubtitlePreviewDialog
from ui.components.spinbox import RobustSpinBox
from ui.components.watermark_canvas import WatermarkPreviewCanvas
from ui.components.subtitle_canvas import SubtitlePreviewCanvas

__all__ = [
    "DubbingWorker",
    "MainWindow",
    "PasteLinksDialog",
    "WatermarkConfigDialog",
    "SubtitlePreviewDialog",
    "RobustSpinBox",
    "WatermarkPreviewCanvas",
    "SubtitlePreviewCanvas",
]


def main():
    """Main application launcher."""
    if len(sys.argv) > 1 and sys.argv[1] == "--runtime-self-check":
        parser = argparse.ArgumentParser(description="Check a frozen AutoDub Studio runtime")
        parser.add_argument("--runtime-self-check", dest="input_video", required=True, type=Path)
        parser.add_argument("--expect-llm-model")
        parser.add_argument("--report-json", type=Path)
        args = parser.parse_args()
        from core.runtime_check import run_runtime_self_check

        report = run_runtime_self_check(args.input_video, args.expect_llm_model)
        rendered = json.dumps(report, ensure_ascii=False, indent=2)
        if args.report_json:
            args.report_json.parent.mkdir(parents=True, exist_ok=True)
            args.report_json.write_text(rendered, encoding="utf-8")
        if sys.stdout is not None:
            print(rendered)
        return 0

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    # Apply stylesheet to whole QApplication for crisp rendering across all dialogs and modals
    app.setStyleSheet(window.styleSheet())
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
