"""
AutoDub Studio - UI Package.
Provides clean modular desktop components, dialogs, canvases, and background workers.
"""

from .worker import DubbingWorker
from .main_window import MainWindow
from .dialogs.paste_links_dialog import PasteLinksDialog
from .dialogs.watermark_dialog import WatermarkConfigDialog
from .dialogs.subtitle_dialog import SubtitlePreviewDialog
from .components.spinbox import RobustSpinBox
from .components.watermark_canvas import WatermarkPreviewCanvas
from .components.subtitle_canvas import SubtitlePreviewCanvas

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
