"""
AutoDub Studio - Native Windows Desktop Application Entry Point (PySide6 / Qt).
Designed for Go-Global distribution with an English UI, batch queue processing,
dual-column settings, smooth progress bar, and real-time terminal console log.

This module acts as the primary desktop application entry point and backward-compatible
Facade re-exporting all core UI components, dialogs, and background workers.
"""

import sys
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
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    # Apply stylesheet to whole QApplication for crisp rendering across all dialogs and modals
    app.setStyleSheet(window.styleSheet())
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
