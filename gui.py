"""
AutoDub Studio - Native Windows Desktop Application (PySide6 / Qt).
Designed for Go-Global distribution with an English UI, batch queue processing,
dual-column settings, smooth progress bar, and real-time terminal console log.
"""

import sys
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional, Union

# Configure UTF-8 encoding on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

from PySide6.QtCore import Qt, QThread, Signal, Slot, QRectF
from PySide6.QtGui import QFont, QColor, QPixmap, QValidator, QPainter, QFontMetrics, QPainterPath, QLinearGradient, QPen
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QTabWidget, QTableWidget, QTableWidgetItem, QHeaderView,
    QPushButton, QComboBox, QDoubleSpinBox, QSpinBox, QLineEdit, QCheckBox,
    QLabel, QProgressBar, QTextEdit, QFileDialog, QInputDialog, QMessageBox,
    QGroupBox, QColorDialog, QDialog, QSlider, QScrollArea
)

from config import Config
from pipeline import run_pipeline
from core.translator import test_llm_connection


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


class PasteLinksDialog(QDialog):
    """
    Hộp thoại dán liên kết video với giao diện sáng rõ, tương phản cao,
    khắc phục triệt để lỗi chữ đen trên nền tối.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🔗 Paste Video Links")
        self.setMinimumSize(540, 380)
        self.resize(580, 420)
        self.setModal(True)
        self.init_ui()
        self.apply_dialog_styles()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        lbl_title = QLabel("Nhập hoặc dán các đường link video (mỗi URL một dòng):")
        lbl_title.setStyleSheet("font-size: 13px; font-weight: 600; color: #1E293B;")
        layout.addWidget(lbl_title)

        self.txt_links = QTextEdit()
        self.txt_links.setPlaceholderText(
            "Ví dụ:\n"
            "https://v.douyin.com/W6GuKycdLJs/\n"
            "https://www.tiktok.com/@user/video/7182938475618293849\n"
            "..."
        )
        self.txt_links.setAcceptRichText(False)
        layout.addWidget(self.txt_links)

        # Toolbar phụ (Paste từ Clipboard, Xóa trắng)
        tools_layout = QHBoxLayout()
        tools_layout.setSpacing(8)

        btn_clipboard = QPushButton("📋 Dán từ Clipboard")
        btn_clipboard.setFixedHeight(28)
        btn_clipboard.setStyleSheet("""
            QPushButton {
                background-color: #F1F5F9;
                color: #334155;
                border: 1px solid #CBD5E1;
                border-radius: 4px;
                padding: 4px 12px;
                font-size: 12px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #E2E8F0;
                color: #0F172A;
            }
        """)
        btn_clipboard.clicked.connect(self.action_paste_clipboard)

        btn_clear = QPushButton("🗑️ Xóa trắng")
        btn_clear.setFixedHeight(28)
        btn_clear.setStyleSheet("""
            QPushButton {
                background-color: #F1F5F9;
                color: #64748B;
                border: 1px solid #CBD5E1;
                border-radius: 4px;
                padding: 4px 12px;
                font-size: 12px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #FEE2E2;
                color: #DC2626;
                border-color: #FCA5A5;
            }
        """)
        btn_clear.clicked.connect(self.txt_links.clear)

        tools_layout.addWidget(btn_clipboard)
        tools_layout.addWidget(btn_clear)
        tools_layout.addStretch()
        layout.addLayout(tools_layout)

        # Action Buttons (OK / Cancel)
        btn_box = QHBoxLayout()
        btn_box.setSpacing(10)
        btn_box.addStretch()

        self.btn_cancel = QPushButton("Hủy bỏ")
        self.btn_cancel.setFixedHeight(34)
        self.btn_cancel.setFixedWidth(100)
        self.btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: #F1F5F9;
                color: #475569;
                border: 1px solid #CBD5E1;
                border-radius: 6px;
                font-weight: 500;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #E2E8F0;
                color: #1E293B;
            }
        """)
        self.btn_cancel.clicked.connect(self.reject)

        self.btn_ok = QPushButton("Xác nhận")
        self.btn_ok.setFixedHeight(34)
        self.btn_ok.setFixedWidth(120)
        self.btn_ok.setStyleSheet("""
            QPushButton {
                background-color: #2563EB;
                color: #FFFFFF;
                border: none;
                border-radius: 6px;
                font-weight: 600;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #1D4ED8;
            }
        """)
        self.btn_ok.clicked.connect(self.accept)

        btn_box.addWidget(self.btn_cancel)
        btn_box.addWidget(self.btn_ok)
        layout.addLayout(btn_box)

    def apply_dialog_styles(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #FFFFFF;
            }
            QTextEdit {
                background-color: #F8FAFC;
                color: #0F172A;
                border: 1.5px solid #CBD5E1;
                border-radius: 8px;
                font-family: 'Consolas', 'Segoe UI', monospace;
                font-size: 13px;
                padding: 10px;
                selection-background-color: #2563EB;
                selection-color: #FFFFFF;
            }
            QTextEdit:focus {
                background-color: #FFFFFF;
                border: 1.5px solid #2563EB;
            }
        """)

    def action_paste_clipboard(self):
        clipboard = QApplication.clipboard()
        text = clipboard.text()
        if text:
            self.txt_links.append(text.strip())

    def get_links(self) -> List[str]:
        raw_text = self.txt_links.toPlainText()
        return [line.strip() for line in raw_text.splitlines() if line.strip()]


class RobustSpinBox(QSpinBox):
    """
    QSpinBox thông minh tự động bóc tách số và bỏ qua hậu tố ' px' hoặc nhập thiếu khoảng trắng,
    tránh việc reset về giá trị mặc định khi người dùng gõ rồi click ra ngoài (focus loss).
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setKeyboardTracking(False)
        self.lineEdit().editingFinished.connect(self._on_editing_finished)

    def _on_editing_finished(self):
        self.interpretText()

    def valueFromText(self, text: str) -> int:
        nums = re.findall(r"\d+", text)
        if nums:
            val = int(nums[0])
            return max(self.minimum(), min(self.maximum(), val))
        return self.value()

    def validate(self, text: str, pos: int):
        return (QValidator.State.Acceptable, text, pos)


class WatermarkPreviewCanvas(QWidget):
    """
    Live visual canvas rendering an accurate real-time preview of Text Watermark
    and Logo Image Watermark on a simulated or real video frame (9:16 or 16:9).
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(320, 420)
        self.aspect_ratio: str = "9:16"
        self.bg_pixmap: Optional[QPixmap] = None

        # Text watermark state
        self.text_enabled: bool = False
        self.text_content: str = ""
        self.text_position: str = "center"
        self.text_font_size: int = 22

        # Logo watermark state
        self.logo_enabled: bool = False
        self.logo_path: str = ""
        self.logo_pixmap: Optional[QPixmap] = None
        self.logo_position: str = "top-right"
        self.logo_opacity: float = 0.8
        self.logo_max_width: int = 160

    def set_aspect_ratio(self, ratio_str: str):
        self.aspect_ratio = ratio_str
        self.update()

    def set_background_pixmap(self, pixmap: Optional[QPixmap]):
        self.bg_pixmap = pixmap
        self.update()

    def set_text_watermark(self, enabled: bool, text: str, pos: str, font_size: int):
        self.text_enabled = enabled
        self.text_content = text
        self.text_position = pos
        self.text_font_size = font_size
        self.update()

    def set_logo_watermark(self, enabled: bool, logo_path: str, pos: str, opacity: float, max_width: int):
        self.logo_enabled = enabled
        self.logo_position = pos
        self.logo_opacity = opacity
        self.logo_max_width = max_width

        if logo_path != self.logo_path:
            self.logo_path = logo_path
            p = Path(logo_path.strip()) if logo_path else None
            if p and p.is_file():
                pix = QPixmap(str(p))
                self.logo_pixmap = pix if not pix.isNull() else None
            else:
                self.logo_pixmap = None

        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.TextAntialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)

        # 1. Fill entire widget background with subtle container tone
        p.fillRect(self.rect(), QColor(248, 250, 252))

        # 2. Compute proportional canvas area respecting selected aspect ratio
        margin_pad = 12.0
        avail_w = max(100.0, self.width() - margin_pad * 2)
        avail_h = max(100.0, self.height() - margin_pad * 2)

        is_vertical = (self.aspect_ratio == "9:16")
        target_ratio = (9.0 / 16.0) if is_vertical else (16.0 / 9.0)
        ref_w = 720.0 if is_vertical else 1280.0
        ref_h = 1280.0 if is_vertical else 720.0

        if (avail_w / avail_h) > target_ratio:
            canvas_h = avail_h
            canvas_w = canvas_h * target_ratio
        else:
            canvas_w = avail_w
            canvas_h = canvas_w / target_ratio

        canvas_x = (self.width() - canvas_w) / 2.0
        canvas_y = (self.height() - canvas_h) / 2.0
        canvas_rect = QRectF(canvas_x, canvas_y, canvas_w, canvas_h)

        # 3. Draw video canvas background (Real frame if available, else dark cinematic gradient)
        p.save()
        clip_path = QPainterPath()
        clip_path.addRoundedRect(canvas_rect, 8.0, 8.0)
        p.setClipPath(clip_path)

        if self.bg_pixmap and not self.bg_pixmap.isNull():
            scaled_bg = self.bg_pixmap.scaled(
                int(canvas_w), int(canvas_h),
                Qt.KeepAspectRatioByExpanding,
                Qt.SmoothTransformation
            )
            crop_x = (scaled_bg.width() - int(canvas_w)) // 2
            crop_y = (scaled_bg.height() - int(canvas_h)) // 2
            p.drawPixmap(int(canvas_x), int(canvas_y), scaled_bg, crop_x, crop_y, int(canvas_w), int(canvas_h))
        else:
            grad = QLinearGradient(canvas_rect.topLeft(), canvas_rect.bottomRight())
            grad.setColorAt(0.0, QColor(15, 23, 42))
            grad.setColorAt(1.0, QColor(30, 41, 59))
            p.fillRect(canvas_rect, grad)

            # Center text hint
            p.setPen(QColor(255, 255, 255, 35))
            p.setFont(QFont("Segoe UI", 10, QFont.Bold))
            ratio_label = "📱 9:16 Video Frame (TikTok / Shorts)" if is_vertical else "🖥️ 16:9 Video Frame (Landscape)"
            p.drawText(QRectF(canvas_x, canvas_y + canvas_h * 0.44, canvas_w, 24), Qt.AlignCenter, ratio_label)
            p.setFont(QFont("Segoe UI", 9))
            p.setPen(QColor(148, 163, 184, 80))
            p.drawText(QRectF(canvas_x, canvas_y + canvas_h * 0.44 + 22, canvas_w, 20), Qt.AlignCenter, f"{int(ref_w)} x {int(ref_h)}")

        # 4. Render Logo Watermark (matches FFmpeg overlay filter)
        if self.logo_enabled and self.logo_pixmap and not self.logo_pixmap.isNull():
            scale_logo = canvas_w / ref_w
            lw = max(16.0, float(self.logo_max_width) * scale_logo)
            lh = lw * (float(self.logo_pixmap.height()) / float(max(1, self.logo_pixmap.width())))
            pad_edge = 24.0 * scale_logo

            pos = self.logo_position.lower()
            if "top-left" in pos:
                lx = canvas_rect.left() + pad_edge
                ly = canvas_rect.top() + pad_edge
            elif "bottom-left" in pos:
                lx = canvas_rect.left() + pad_edge
                ly = canvas_rect.bottom() - pad_edge - lh
            elif "bottom-right" in pos:
                lx = canvas_rect.right() - pad_edge - lw
                ly = canvas_rect.bottom() - pad_edge - lh
            elif "center" in pos:
                lx = canvas_rect.left() + (canvas_w - lw) / 2.0
                ly = canvas_rect.top() + (canvas_h - lh) / 2.0
            else:  # top-right (default)
                lx = canvas_rect.right() - pad_edge - lw
                ly = canvas_rect.top() + pad_edge

            p.setOpacity(max(0.05, min(1.0, self.logo_opacity)))
            p.drawPixmap(QRectF(lx, ly, lw, lh), self.logo_pixmap, QRectF(self.logo_pixmap.rect()))
            p.setOpacity(1.0)

        # 5. Render Text Watermark (matches ASS subtitle WatermarkStyle)
        if self.text_enabled and self.text_content:
            scale_h = canvas_h / ref_h
            font_pt = max(8, int(round(self.text_font_size * scale_h * 1.35)))
            wm_font = QFont("Arial", font_pt, QFont.Bold)
            p.setFont(wm_font)
            fm = QFontMetrics(wm_font)

            pad_x = 12.0 * scale_h
            pad_y = 6.0 * scale_h
            text_str = self.text_content.strip()
            max_avail_tw = canvas_w - 32.0 * scale_h
            elided_str = fm.elidedText(text_str, Qt.ElideMiddle, int(max_avail_tw))

            tw = fm.horizontalAdvance(elided_str)
            th = fm.height()
            bw = min(canvas_w - 20.0, tw + pad_x * 2.0)
            bh = th + pad_y * 2.0
            bx = canvas_rect.left() + (canvas_w - bw) / 2.0

            pos = self.text_position.lower()
            if "top" in pos:
                by = canvas_rect.top() + (45.0 * scale_h)
            elif "bottom" in pos:
                by = canvas_rect.bottom() - (45.0 * scale_h) - bh
            else:  # center
                by = canvas_rect.top() + (canvas_h - bh) / 2.0

            badge_rect = QRectF(bx, by, bw, bh)
            p.setPen(QColor(255, 255, 255, 30))
            p.setBrush(QColor(0, 0, 0, 168))
            p.drawRoundedRect(badge_rect, 5.0, 5.0)

            p.setPen(QColor(255, 255, 255))
            p.drawText(badge_rect, Qt.AlignCenter, elided_str)

        p.restore()

        # 6. Outer border around video frame
        p.setPen(QPen(QColor(203, 213, 225), 1.5))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(canvas_rect, 8.0, 8.0)
        p.end()


class WatermarkConfigDialog(QDialog):
    """
    Modal dialog allowing users to configure Text Watermark and Logo Image Watermark
    with an interactive side-by-side live video frame preview.
    """
    def __init__(self, parent=None, config: Optional[Dict[str, Any]] = None, sample_frame_path: Optional[str] = None):
        super().__init__(parent)
        self.setWindowTitle("🎨 Watermark & Branding Settings - Live Preview")
        self.resize(960, 580)
        self.setMinimumSize(880, 520)
        self.setModal(True)
        self.config = dict(config or {})
        self.sample_frame_path = sample_frame_path

        self.init_ui()
        self.load_values()
        self.apply_dialog_styles()

    def apply_dialog_styles(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #F8FAFC;
                color: #0F172A;
            }
            QLabel {
                color: #0F172A;
                font-size: 12px;
            }
            QPushButton {
                background-color: #FFFFFF;
                color: #0F172A;
                border: 1px solid #CBD5E1;
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #F1F5F9;
                color: #1E293B;
                border-color: #94A3B8;
            }
            QLineEdit, QComboBox, QSpinBox {
                border: 1px solid #CBD5E1;
                border-radius: 6px;
                padding: 4px 8px;
                background-color: #FFFFFF;
                color: #0F172A;
                font-size: 12px;
            }
            QLineEdit:focus, QComboBox:focus, QSpinBox:focus {
                border: 1px solid #2563EB;
            }
            QTabWidget::pane {
                border: 1px solid #CBD5E1;
                background-color: #FFFFFF;
                border-radius: 6px;
                padding: 14px;
            }
            QTabBar::tab {
                background-color: #E2E8F0;
                color: #334155;
                font-weight: bold;
                padding: 7px 18px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                margin-right: 3px;
                border: 1px solid #CBD5E1;
                border-bottom: none;
            }
            QTabBar::tab:selected {
                background-color: #FFFFFF;
                color: #2563EB;
                border-bottom: 2px solid #FFFFFF;
            }
            QSlider::groove:horizontal {
                height: 6px;
                background: #E2E8F0;
                border-radius: 3px;
            }
            QSlider::sub-page:horizontal {
                background: #2563EB;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #1D4ED8;
                border: 2px solid #FFFFFF;
                width: 16px;
                margin-top: -5px;
                margin-bottom: -5px;
                border-radius: 8px;
            }
            QGroupBox {
                background-color: #FFFFFF;
                border: 1px solid #CBD5E1;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 14px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 14px;
                padding: 0 6px;
                color: #0F172A;
                font-weight: bold;
                font-size: 12px;
            }
        """)

    def init_ui(self):
        root_layout = QHBoxLayout(self)
        root_layout.setContentsMargins(18, 16, 18, 16)
        root_layout.setSpacing(16)

        # ================= LEFT COLUMN: SETTINGS TABS =================
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(12)

        header_lbl = QLabel("<b>Watermark & Branding Settings</b>")
        header_lbl.setStyleSheet("font-size: 15px; color: #0F172A;")
        left_layout.addWidget(header_lbl)

        sub_desc = QLabel("Configure promotional text banner and channel logo to brand your videos.")
        sub_desc.setStyleSheet("font-size: 11px; color: #64748B; margin-bottom: 2px;")
        sub_desc.setWordWrap(True)
        left_layout.addWidget(sub_desc)

        self.tab_widget = QTabWidget()

        # TAB 1: TEXT WATERMARK
        tab_text = QWidget()
        layout_text = QVBoxLayout(tab_text)
        layout_text.setSpacing(10)

        self.chk_text_enable = QCheckBox("Enable Text Watermark")
        self.chk_text_enable.setStyleSheet("font-weight: bold; font-size: 13px; color: #1E293B;")
        self.chk_text_enable.toggled.connect(self.refresh_preview)
        layout_text.addWidget(self.chk_text_enable)

        grid_text = QGridLayout()
        grid_text.setVerticalSpacing(10)
        grid_text.setHorizontalSpacing(10)

        grid_text.addWidget(QLabel("Watermark Text:"), 0, 0)
        self.txt_text_content = QLineEdit()
        self.txt_text_content.setFixedHeight(32)
        self.txt_text_content.setPlaceholderText("e.g. Bạn đang xem video được sub bởi Vũ Mạnh Cường")
        self.txt_text_content.textChanged.connect(self.refresh_preview)
        grid_text.addWidget(self.txt_text_content, 0, 1)

        grid_text.addWidget(QLabel("Timing:"), 1, 0)
        self.cbo_text_timing = QComboBox()
        self.cbo_text_timing.setFixedHeight(32)
        self.cbo_text_timing.addItem("Mid-video (Highlight 6s at midpoint)", "mid_video")
        self.cbo_text_timing.addItem("Throughout Video (Full duration)", "full")
        grid_text.addWidget(self.cbo_text_timing, 1, 1)

        grid_text.addWidget(QLabel("Position:"), 2, 0)
        self.cbo_text_pos = QComboBox()
        self.cbo_text_pos.setFixedHeight(32)
        self.cbo_text_pos.addItem("Center (Chính giữa màn hình)", "center")
        self.cbo_text_pos.addItem("Top (Phía trên)", "top")
        self.cbo_text_pos.addItem("Bottom (Phía dưới)", "bottom")
        self.cbo_text_pos.currentIndexChanged.connect(self.refresh_preview)
        grid_text.addWidget(self.cbo_text_pos, 2, 1)

        grid_text.addWidget(QLabel("Font Size:"), 3, 0)
        self.spn_text_font_size = RobustSpinBox()
        self.spn_text_font_size.setFixedHeight(32)
        self.spn_text_font_size.setRange(10, 120)
        self.spn_text_font_size.setValue(22)
        self.spn_text_font_size.valueChanged.connect(self.refresh_preview)
        grid_text.addWidget(self.spn_text_font_size, 3, 1)

        layout_text.addLayout(grid_text)

        tip_lbl = QLabel("💡 <i>Text watermark is rendered with a sleek semi-transparent badge for optimal readability on all backgrounds.</i>")
        tip_lbl.setStyleSheet("font-size: 11px; color: #64748B; margin-top: 4px;")
        tip_lbl.setWordWrap(True)
        layout_text.addWidget(tip_lbl)
        layout_text.addStretch()

        self.tab_widget.addTab(tab_text, "✍️ Text Watermark")

        # TAB 2: LOGO IMAGE WATERMARK
        tab_logo = QWidget()
        layout_logo = QVBoxLayout(tab_logo)
        layout_logo.setSpacing(10)

        self.chk_logo_enable = QCheckBox("Enable Logo Watermark")
        self.chk_logo_enable.setStyleSheet("font-weight: bold; font-size: 13px; color: #1E293B;")
        self.chk_logo_enable.toggled.connect(self.refresh_preview)
        layout_logo.addWidget(self.chk_logo_enable)

        grid_logo = QGridLayout()
        grid_logo.setVerticalSpacing(10)
        grid_logo.setHorizontalSpacing(10)

        grid_logo.addWidget(QLabel("Logo Image:"), 0, 0)
        h_file = QHBoxLayout()
        h_file.setSpacing(6)
        self.txt_logo_path = QLineEdit()
        self.txt_logo_path.setFixedHeight(32)
        self.txt_logo_path.setPlaceholderText("Select PNG / JPG image...")
        self.txt_logo_path.textChanged.connect(self.refresh_preview)

        self.btn_browse_logo = QPushButton("Browse...")
        self.btn_browse_logo.setFixedHeight(32)
        self.btn_browse_logo.setFixedWidth(75)
        self.btn_browse_logo.setStyleSheet("background-color: #F8FAFC; border: 1px solid #CBD5E1; border-radius: 6px; font-weight: 500;")
        self.btn_browse_logo.clicked.connect(self.action_browse_logo)
        h_file.addWidget(self.txt_logo_path)
        h_file.addWidget(self.btn_browse_logo)
        grid_logo.addLayout(h_file, 0, 1)

        grid_logo.addWidget(QLabel("Position:"), 1, 0)
        self.cbo_logo_pos = QComboBox()
        self.cbo_logo_pos.setFixedHeight(32)
        self.cbo_logo_pos.addItem("Top-Right (Standard for short video)", "top-right")
        self.cbo_logo_pos.addItem("Top-Left", "top-left")
        self.cbo_logo_pos.addItem("Bottom-Right", "bottom-right")
        self.cbo_logo_pos.addItem("Bottom-Left", "bottom-left")
        self.cbo_logo_pos.addItem("Center", "center")
        self.cbo_logo_pos.currentIndexChanged.connect(self.refresh_preview)
        grid_logo.addWidget(self.cbo_logo_pos, 1, 1)

        grid_logo.addWidget(QLabel("Opacity:"), 2, 0)
        h_op = QHBoxLayout()
        h_op.setSpacing(8)
        self.slider_opacity = QSlider(Qt.Horizontal)
        self.slider_opacity.setRange(10, 100)
        self.slider_opacity.setValue(80)
        self.lbl_op_val = QLabel("80%")
        self.lbl_op_val.setFixedWidth(36)
        self.lbl_op_val.setStyleSheet("font-weight: bold; color: #2563EB;")
        self.slider_opacity.valueChanged.connect(lambda v: self.lbl_op_val.setText(f"{v}%"))
        self.slider_opacity.valueChanged.connect(self.refresh_preview)
        h_op.addWidget(self.slider_opacity)
        h_op.addWidget(self.lbl_op_val)
        grid_logo.addLayout(h_op, 2, 1)

        grid_logo.addWidget(QLabel("Max Width:"), 3, 0)
        self.spn_logo_max_width = RobustSpinBox()
        self.spn_logo_max_width.setFixedHeight(32)
        self.spn_logo_max_width.setRange(10, 1920)
        self.spn_logo_max_width.setValue(160)
        self.spn_logo_max_width.setSuffix(" px")
        self.spn_logo_max_width.valueChanged.connect(self.refresh_preview)
        grid_logo.addWidget(self.spn_logo_max_width, 3, 1)

        layout_logo.addLayout(grid_logo)
        layout_logo.addStretch()

        self.tab_widget.addTab(tab_logo, "🖼️ Logo Image")
        left_layout.addWidget(self.tab_widget)

        # Dialog Buttons
        btn_box = QHBoxLayout()
        btn_box.setSpacing(10)
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setFixedHeight(34)
        self.btn_cancel.setStyleSheet("background-color: #FFFFFF; color: #64748B; border: 1px solid #CBD5E1; border-radius: 6px; padding: 0 16px;")
        self.btn_cancel.clicked.connect(self.reject)

        self.btn_save = QPushButton("Save Settings")
        self.btn_save.setFixedHeight(34)
        self.btn_save.setStyleSheet("background-color: #2563EB; color: #FFFFFF; font-weight: bold; border-radius: 6px; padding: 0 20px;")
        self.btn_save.clicked.connect(self.action_save)

        btn_box.addStretch()
        btn_box.addWidget(self.btn_cancel)
        btn_box.addWidget(self.btn_save)
        left_layout.addLayout(btn_box)

        root_layout.addWidget(left_widget, stretch=5)

        # ================= RIGHT COLUMN: LIVE VIDEO PREVIEW =================
        grp_preview = QGroupBox("🎬 Live Video Preview")
        grp_preview.setStyleSheet("""
            QGroupBox {
                background-color: #FFFFFF;
                border: 1px solid #CBD5E1;
                border-radius: 8px;
                padding-top: 12px;
            }
        """)
        preview_layout = QVBoxLayout(grp_preview)
        preview_layout.setContentsMargins(12, 10, 12, 12)
        preview_layout.setSpacing(8)

        # Preview toolbar: Aspect ratio + Sample frame selector
        h_prev_tools = QHBoxLayout()
        h_prev_tools.setSpacing(8)

        lbl_ratio = QLabel("Aspect:")
        lbl_ratio.setStyleSheet("font-weight: 500; font-size: 11px;")
        h_prev_tools.addWidget(lbl_ratio)

        self.cbo_aspect_ratio = QComboBox()
        self.cbo_aspect_ratio.setFixedHeight(28)
        self.cbo_aspect_ratio.addItem("📱 9:16 (Shorts/TikTok)", "9:16")
        self.cbo_aspect_ratio.addItem("🖥️ 16:9 (Landscape)", "16:9")
        self.cbo_aspect_ratio.currentIndexChanged.connect(self.refresh_preview)
        h_prev_tools.addWidget(self.cbo_aspect_ratio)

        self.btn_choose_frame = QPushButton("🖼️ Sample Frame...")
        self.btn_choose_frame.setFixedHeight(28)
        self.btn_choose_frame.setStyleSheet("""
            QPushButton {
                background-color: #FFFFFF;
                color: #0F172A;
                border: 1px solid #CBD5E1;
                border-radius: 5px;
                font-size: 11px;
                font-weight: 600;
                padding: 0 10px;
            }
            QPushButton:hover {
                background-color: #EFF6FF;
                color: #1D4ED8;
                border-color: #93C5FD;
            }
        """)
        self.btn_choose_frame.clicked.connect(self.action_choose_sample_frame)
        h_prev_tools.addWidget(self.btn_choose_frame)

        preview_layout.addLayout(h_prev_tools)

        # Visual Canvas
        self.preview_canvas = WatermarkPreviewCanvas()
        preview_layout.addWidget(self.preview_canvas, stretch=1)

        tip_prev = QLabel("💡 <i>Live preview renders real-time positions, scaling, and opacity.</i>")
        tip_prev.setStyleSheet("font-size: 11px; color: #64748B;")
        tip_prev.setAlignment(Qt.AlignCenter)
        preview_layout.addWidget(tip_prev)

        root_layout.addWidget(grp_preview, stretch=6)

    def refresh_preview(self):
        """Update live preview canvas based on current widget settings."""
        text_en = self.chk_text_enable.isChecked()
        text_val = self.txt_text_content.text().strip()
        text_pos = self.cbo_text_pos.currentData() or "center"
        font_sz = self.spn_text_font_size.value()

        logo_en = self.chk_logo_enable.isChecked()
        logo_path = self.txt_logo_path.text().strip()
        logo_pos = self.cbo_logo_pos.currentData() or "top-right"
        logo_op = self.slider_opacity.value() / 100.0
        logo_mw = self.spn_logo_max_width.value()

        aspect = self.cbo_aspect_ratio.currentData() or "9:16"

        self.preview_canvas.set_aspect_ratio(aspect)
        self.preview_canvas.set_text_watermark(text_en, text_val, text_pos, font_sz)
        self.preview_canvas.set_logo_watermark(logo_en, logo_path, logo_pos, logo_op, logo_mw)

    def action_choose_sample_frame(self):
        """Allow user to pick any background image to test overlay positions."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Background Sample Frame",
            "",
            "Images (*.png *.jpg *.jpeg *.webp *.bmp)"
        )
        if file_path:
            pix = QPixmap(file_path)
            if not pix.isNull():
                self.preview_canvas.set_background_pixmap(pix)

    def load_values(self):
        # Text Watermark values
        self.chk_text_enable.setChecked(self.config.get("text_enabled", False))
        self.txt_text_content.setText(self.config.get("text", "Bạn đang xem video được sub bởi Vũ Mạnh Cường"))

        timing = self.config.get("text_timing", "mid_video")
        idx_timing = self.cbo_text_timing.findData(timing)
        if idx_timing >= 0:
            self.cbo_text_timing.setCurrentIndex(idx_timing)

        pos = self.config.get("text_position", "center")
        idx_pos = self.cbo_text_pos.findData(pos)
        if idx_pos >= 0:
            self.cbo_text_pos.setCurrentIndex(idx_pos)

        self.spn_text_font_size.setValue(int(self.config.get("text_font_size", 22)))

        # Logo Watermark values
        logo_path = self.config.get("logo_path", "")
        self.txt_logo_path.setText(logo_path)
        has_logo_file = bool(logo_path and Path(logo_path).is_file())
        self.chk_logo_enable.setChecked(self.config.get("logo_enabled", has_logo_file))

        logo_pos = self.config.get("logo_position", "top-right")
        idx_logo_pos = self.cbo_logo_pos.findData(logo_pos)
        if idx_logo_pos >= 0:
            self.cbo_logo_pos.setCurrentIndex(idx_logo_pos)

        opacity_val = int(round(float(self.config.get("logo_opacity", 0.8)) * 100))
        self.slider_opacity.setValue(opacity_val)
        self.lbl_op_val.setText(f"{opacity_val}%")

        self.spn_logo_max_width.setValue(int(self.config.get("logo_max_width", 160)))

        # Nạp khung hình mẫu nếu được truyền từ video queue
        if self.sample_frame_path and Path(self.sample_frame_path).is_file():
            pix = QPixmap(self.sample_frame_path)
            if not pix.isNull():
                self.preview_canvas.set_background_pixmap(pix)
                # Tự động chọn aspect ratio tương ứng
                if pix.width() > pix.height():
                    self.cbo_aspect_ratio.setCurrentIndex(1)  # 16:9
                else:
                    self.cbo_aspect_ratio.setCurrentIndex(0)  # 9:16

        # Cập nhật khung preview ngay khi mở hộp thoại
        self.refresh_preview()

    def action_browse_logo(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Logo Image",
            "",
            "Image Files (*.png *.jpg *.jpeg *.webp)"
        )
        if file_path:
            self.txt_logo_path.setText(file_path)
            self.chk_logo_enable.setChecked(True)
            self.refresh_preview()

    def action_save(self):
        # Đảm bảo bóc tách giá trị mới nhất trong ô nhập kể cả khi vừa gõ xong chưa bấm Enter
        self.spn_text_font_size.interpretText()
        self.spn_logo_max_width.interpretText()

        self.config["text_enabled"] = self.chk_text_enable.isChecked()
        self.config["text"] = self.txt_text_content.text().strip()
        self.config["text_timing"] = self.cbo_text_timing.currentData() or "mid_video"
        self.config["text_position"] = self.cbo_text_pos.currentData() or "center"
        self.config["text_font_size"] = self.spn_text_font_size.value()

        logo_raw_path = self.txt_logo_path.text().strip()
        has_file = bool(logo_raw_path and Path(logo_raw_path).is_file())
        self.config["logo_enabled"] = self.chk_logo_enable.isChecked() if has_file else False
        self.config["logo_path"] = logo_raw_path
        self.config["logo_position"] = self.cbo_logo_pos.currentData() or "top-right"
        self.config["logo_opacity"] = self.slider_opacity.value() / 100.0
        self.config["logo_max_width"] = self.spn_logo_max_width.value()

        self.accept()


def extract_video_frame_at(video_path: Union[str, Path], timestamp_sec: float = 1.0) -> Optional[str]:
    """
    Trích xuất nhanh một khung hình từ video tại mốc thời gian timestamp_sec bằng FFmpeg.
    Lưu vào thư mục temp/ để phục vụ preview subtitle và watermark.
    """
    try:
        vp = Path(video_path).resolve()
        if not vp.is_file():
            return None
        Config.TEMP_DIR.mkdir(parents=True, exist_ok=True)
        safe_sec = max(0.0, float(timestamp_sec))
        thumb_name = f"{vp.stem}_frame_{int(safe_sec * 100):06d}.jpg"
        thumb_path = Config.TEMP_DIR / thumb_name
        if thumb_path.is_file() and thumb_path.stat().st_size > 0:
            return str(thumb_path)

        from core.audio_extractor import find_ffmpeg
        ffmpeg_bin = find_ffmpeg()
        cmd = [
            str(ffmpeg_bin), "-y",
            "-ss", f"{safe_sec:.2f}",
            "-i", str(vp),
            "-vframes", "1",
            "-q:v", "2",
            str(thumb_path)
        ]
        flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=flags, timeout=5)
        if thumb_path.is_file() and thumb_path.stat().st_size > 0:
            return str(thumb_path)
    except Exception:
        pass
    return None


def get_video_meta(video_path: Union[str, Path]) -> Dict[str, Any]:
    """
    Lấy thông tin duration, kích thước width x height và aspect ratio của video
    sử dụng PyAV hoặc fallback nhẹ.
    """
    meta = {"duration": 15.0, "width": 720, "height": 1280, "aspect_ratio": "9:16"}
    try:
        import av
        with av.open(str(video_path)) as container:
            if container.duration:
                meta["duration"] = max(1.0, float(container.duration / av.time_base))
            if container.streams.video:
                v = container.streams.video[0]
                if v.width and v.height:
                    meta["width"] = v.width
                    meta["height"] = v.height
                    meta["aspect_ratio"] = "16:9" if v.width > v.height else "9:16"
            return meta
    except Exception:
        pass
    return meta


class SubtitlePreviewCanvas(QWidget):
    """
    Visual canvas rendering an accurate real-time preview of Subtitle placement,
    font size, and hardsub background cover box (ASS BorderStyle 3 & 1) on actual video frames.
    Supports interactive mouse dragging to adjust Margin V intuitively.
    """
    margin_v_changed = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(320, 440)
        self.setMouseTracking(True)

        self.aspect_ratio: str = "9:16"
        self.bg_pixmap: Optional[QPixmap] = None

        # Subtitle styling attributes
        self.sub_text: str = "Phụ đề tiếng Việt mẫu che sub cũ"
        self.alignment: int = 2  # 2: Bottom-center, 8: Top-center
        self.margin_v: int = 40  # pixels from bottom/top
        self.font_name: str = "Arial"
        self.font_size: int = 32
        self.border_style: int = 3  # 3: Opaque Box, 1: Outline
        self.box_padding: int = 6
        self.text_color: str = "#FFE600"  # Yellow default for TikTok
        self.bg_color: str = "#000000"    # Black solid box
        self.outline_width: int = 3
        self.shadow_width: int = 1

        # Interactive dragging state
        self.current_box_rect: QRectF = QRectF()
        self.is_dragging: bool = False
        self.drag_start_y: float = 0.0
        self.drag_start_margin_v: int = 40
        self.is_hovering_box: bool = False

    def set_aspect_ratio(self, ratio_str: str):
        self.aspect_ratio = ratio_str
        self.update()

    def set_background_pixmap(self, pixmap: Optional[QPixmap]):
        self.bg_pixmap = pixmap
        self.update()

    def set_subtitle_config(
        self,
        sub_text: str,
        alignment: int,
        margin_v: int,
        font_name: str,
        font_size: int,
        border_style: int,
        box_padding: int,
        text_color: str,
        bg_color: str
    ):
        self.sub_text = sub_text
        self.alignment = alignment
        self.margin_v = margin_v
        self.font_name = font_name
        self.font_size = font_size
        self.border_style = border_style
        self.box_padding = box_padding
        self.text_color = text_color
        self.bg_color = bg_color
        self.update()

    def set_margin_v(self, val: int):
        self.margin_v = max(0, min(600, val))
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.TextAntialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)

        # 1. Fill entire widget background with clean surface tone
        p.fillRect(self.rect(), QColor(248, 250, 252))

        # 2. Compute proportional canvas area respecting aspect ratio
        margin_pad = 12.0
        avail_w = max(100.0, self.width() - margin_pad * 2)
        avail_h = max(100.0, self.height() - margin_pad * 2)

        is_vertical = (self.aspect_ratio == "9:16")
        target_ratio = (9.0 / 16.0) if is_vertical else (16.0 / 9.0)
        ref_w = 720.0 if is_vertical else 1280.0
        ref_h = 1280.0 if is_vertical else 720.0

        if (avail_w / avail_h) > target_ratio:
            canvas_h = avail_h
            canvas_w = canvas_h * target_ratio
        else:
            canvas_w = avail_w
            canvas_h = canvas_w / target_ratio

        canvas_x = (self.width() - canvas_w) / 2.0
        canvas_y = (self.height() - canvas_h) / 2.0
        canvas_rect = QRectF(canvas_x, canvas_y, canvas_w, canvas_h)

        # 3. Clip and draw video background
        p.save()
        clip_path = QPainterPath()
        clip_path.addRoundedRect(canvas_rect, 8.0, 8.0)
        p.setClipPath(clip_path)

        if self.bg_pixmap and not self.bg_pixmap.isNull():
            scaled_bg = self.bg_pixmap.scaled(
                int(canvas_w), int(canvas_h),
                Qt.KeepAspectRatioByExpanding,
                Qt.SmoothTransformation
            )
            crop_x = (scaled_bg.width() - int(canvas_w)) // 2
            crop_y = (scaled_bg.height() - int(canvas_h)) // 2
            p.drawPixmap(int(canvas_x), int(canvas_y), scaled_bg, crop_x, crop_y, int(canvas_w), int(canvas_h))
        else:
            grad = QLinearGradient(canvas_rect.topLeft(), canvas_rect.bottomRight())
            grad.setColorAt(0.0, QColor(15, 23, 42))
            grad.setColorAt(1.0, QColor(30, 41, 59))
            p.fillRect(canvas_rect, grad)

            # Center text hint
            p.setPen(QColor(255, 255, 255, 45))
            p.setFont(QFont("Segoe UI", 10, QFont.Bold))
            ratio_label = "📱 9:16 Vertical Video" if is_vertical else "🖥️ 16:9 Landscape Video"
            p.drawText(QRectF(canvas_x, canvas_y + canvas_h * 0.42, canvas_w, 24), Qt.AlignCenter, ratio_label)
            p.setFont(QFont("Segoe UI", 9))
            p.setPen(QColor(148, 163, 184, 80))
            p.drawText(QRectF(canvas_x, canvas_y + canvas_h * 0.42 + 22, canvas_w, 20), Qt.AlignCenter, f"{int(ref_w)} x {int(ref_h)}")

        # 4. Render Subtitle and Hardsub Cover Box
        scale_h = canvas_h / ref_h
        scale_w = canvas_w / ref_w

        # Font sizing proportional to video reference resolution
        font_pt = max(8, int(round(self.font_size * scale_h * 1.32)))
        font_fam = self.font_name if self.font_name else "Arial"
        sub_font = QFont(font_fam, font_pt, QFont.Bold)
        p.setFont(sub_font)
        fm = QFontMetrics(sub_font)

        raw_text = self.sub_text.strip() if self.sub_text else "Phụ đề tiếng Việt mẫu"
        lines = [ln.strip() for ln in raw_text.split("\n") if ln.strip()]
        if not lines:
            lines = ["Phụ đề tiếng Việt mẫu"]

        line_height = fm.height()
        line_spacing = max(2, int(4 * scale_h))
        total_text_h = len(lines) * line_height + (len(lines) - 1) * line_spacing

        max_line_w = 0
        for ln in lines:
            tw = fm.horizontalAdvance(ln)
            if tw > max_line_w:
                max_line_w = tw

        # Padding around text
        pad_x = (self.box_padding + 10) * scale_w
        pad_y = (self.box_padding + 4) * scale_h

        bw = min(canvas_w - 24.0, max_line_w + pad_x * 2.0)
        bh = total_text_h + pad_y * 2.0
        bx = canvas_rect.left() + (canvas_w - bw) / 2.0

        # Calculate Y based on alignment and margin_v
        scaled_margin_v = float(self.margin_v) * scale_h
        if self.alignment == 8:  # Top
            by = canvas_rect.top() + scaled_margin_v
        else:  # Bottom (default: 2)
            by = canvas_rect.bottom() - scaled_margin_v - bh

        self.current_box_rect = QRectF(bx, by, bw, bh)

        # Draw Hardsub Covering Box (border_style == 3)
        if self.border_style == 3:
            box_col = QColor(self.bg_color) if self.bg_color else QColor(0, 0, 0)
            p.setPen(Qt.NoPen)
            p.setBrush(box_col)
            # Subtle rounded corners for modern TikTok badge appearance
            p.drawRoundedRect(self.current_box_rect, 4.0, 4.0)

            # Draw text inside box
            txt_col = QColor(self.text_color) if self.text_color else QColor(255, 230, 0)
            p.setPen(txt_col)
            curr_y = by + pad_y
            for ln in lines:
                ln_rect = QRectF(bx, curr_y, bw, line_height)
                p.drawText(ln_rect, Qt.AlignCenter, ln)
                curr_y += line_height + line_spacing
        else:
            # Traditional Outline & Shadow (border_style == 1)
            txt_col = QColor(self.text_color) if self.text_color else QColor(255, 255, 255)
            curr_y = by + pad_y
            for ln in lines:
                ln_rect = QRectF(bx, curr_y, bw, line_height)
                # Shadow
                p.setPen(QColor(0, 0, 0, 220))
                p.drawText(ln_rect.translated(1.5, 1.5), Qt.AlignCenter, ln)
                # Main text
                p.setPen(txt_col)
                p.drawText(ln_rect, Qt.AlignCenter, ln)
                curr_y += line_height + line_spacing

        # 5. Visual Guide Lines (Dashed line and Margin V indicator)
        if self.is_hovering_box or self.is_dragging:
            guide_pen = QPen(QColor(56, 189, 248), 1.5, Qt.DashLine)
            p.setPen(guide_pen)
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(self.current_box_rect.adjusted(-2, -2, 2, 2), 5.0, 5.0)

            # Vertical guide line to edge
            p.setPen(QPen(QColor(56, 189, 248, 180), 1.2, Qt.DashLine))
            center_x = bx + bw / 2.0
            if self.alignment == 8:
                p.drawLine(center_x, canvas_rect.top(), center_x, by)
            else:
                p.drawLine(center_x, by + bh, center_x, canvas_rect.bottom())

            # Margin V Badge
            badge_txt = f"Margin V: {self.margin_v}px"
            p.setFont(QFont("Segoe UI", 8, QFont.Bold))
            badge_fm = QFontMetrics(p.font())
            bg_w = badge_fm.horizontalAdvance(badge_txt) + 12
            bg_h = 20

            badge_y = (by + bh + 6) if (self.alignment != 8 and by + bh + 26 < canvas_rect.bottom()) else (by - 24)
            badge_rect = QRectF(center_x - bg_w / 2.0, badge_y, bg_w, bg_h)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(15, 23, 42, 230))
            p.drawRoundedRect(badge_rect, 4.0, 4.0)
            p.setPen(QColor(56, 189, 248))
            p.drawText(badge_rect, Qt.AlignCenter, badge_txt)

        p.restore()

        # 6. Outer border around video frame
        p.setPen(QPen(QColor(203, 213, 225), 1.5))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(canvas_rect, 8.0, 8.0)
        p.end()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            pos = event.position()
            # Allow click within or near the box
            if self.current_box_rect.adjusted(-12, -12, 12, 12).contains(pos):
                self.is_dragging = True
                self.drag_start_y = pos.y()
                self.drag_start_margin_v = self.margin_v
                self.setCursor(Qt.ClosedHandCursor)
                self.update()

    def mouseMoveEvent(self, event):
        pos = event.position()
        if self.is_dragging:
            delta_y = pos.y() - self.drag_start_y
            is_vertical = (self.aspect_ratio == "9:16")
            ref_h = 1280.0 if is_vertical else 720.0
            margin_pad = 12.0
            avail_h = max(100.0, self.height() - margin_pad * 2)
            target_ratio = (9.0 / 16.0) if is_vertical else (16.0 / 9.0)
            avail_w = max(100.0, self.width() - margin_pad * 2)

            if (avail_w / avail_h) > target_ratio:
                canvas_h = avail_h
            else:
                canvas_h = avail_w / target_ratio

            scale_h = max(0.001, canvas_h / ref_h)

            if self.alignment == 8:  # Top
                delta_m = int(round(delta_y / scale_h))
            else:  # Bottom
                delta_m = - int(round(delta_y / scale_h))

            new_margin = max(0, min(600, self.drag_start_margin_v + delta_m))
            if new_margin != self.margin_v:
                self.margin_v = new_margin
                self.margin_v_changed.emit(self.margin_v)
                self.update()
        else:
            near_box = self.current_box_rect.adjusted(-12, -12, 12, 12).contains(pos)
            if near_box != self.is_hovering_box:
                self.is_hovering_box = near_box
                self.setCursor(Qt.SizeVerCursor if near_box else Qt.ArrowCursor)
                self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.is_dragging:
            self.is_dragging = False
            self.setCursor(Qt.ArrowCursor)
            self.update()


class SubtitlePreviewDialog(QDialog):
    """
    Modal dialog allowing users to preview subtitle placement, font size, and background cover
    on real video frames to accurately cover old hardcoded subtitles (Chinese, English, etc.).
    """
    def __init__(
        self,
        parent=None,
        video_paths: Optional[List[str]] = None,
        current_settings: Optional[Dict[str, Any]] = None
    ):
        super().__init__(parent)
        self.setWindowTitle("🎯 Subtitle Overlay & Hardsub Cover Preview - AutoDub")
        self.resize(1020, 640)
        self.setMinimumSize(920, 560)
        self.setModal(True)

        self.video_paths = [str(p) for p in (video_paths or []) if Path(p).is_file()]
        self.current_video_path = self.video_paths[0] if self.video_paths else None
        self.video_duration = 15.0
        self.video_aspect = "9:16"

        self.settings = dict(current_settings or {})
        self.result_settings = dict(self.settings)

        self.init_ui()
        self.load_initial_video_and_settings()
        self.apply_dialog_styles()

    def apply_dialog_styles(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #F8FAFC;
                color: #0F172A;
            }
            QLabel {
                color: #0F172A;
                font-size: 12px;
            }
            QPushButton {
                background-color: #FFFFFF;
                color: #0F172A;
                border: 1px solid #CBD5E1;
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #F1F5F9;
                color: #1E293B;
                border-color: #94A3B8;
            }
            QLineEdit, QComboBox, QSpinBox {
                border: 1px solid #CBD5E1;
                border-radius: 6px;
                padding: 4px 8px;
                background-color: #FFFFFF;
                color: #0F172A;
                font-size: 12px;
            }
            QLineEdit:focus, QComboBox:focus, QSpinBox:focus {
                border: 1px solid #2563EB;
            }
            QSlider::groove:horizontal {
                height: 6px;
                background: #E2E8F0;
                border-radius: 3px;
            }
            QSlider::sub-page:horizontal {
                background: #2563EB;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #1D4ED8;
                border: 2px solid #FFFFFF;
                width: 16px;
                margin-top: -5px;
                margin-bottom: -5px;
                border-radius: 8px;
            }
            QGroupBox {
                background-color: #FFFFFF;
                border: 1px solid #CBD5E1;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 14px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 14px;
                padding: 0 6px;
                color: #0F172A;
                font-weight: bold;
                font-size: 12px;
            }
        """)

    def init_ui(self):
        root_layout = QHBoxLayout(self)
        root_layout.setContentsMargins(16, 14, 16, 14)
        root_layout.setSpacing(16)

        # ================= LEFT COLUMN: CONTROLS & FINE TUNING =================
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(10)

        header_lbl = QLabel("<b>Subtitle Placement & Hardsub Cover</b>")
        header_lbl.setStyleSheet("font-size: 15px; color: #0F172A;")
        left_layout.addWidget(header_lbl)

        desc_lbl = QLabel("Align subtitle position and black cover box to perfectly overlay original hardsubs.")
        desc_lbl.setStyleSheet("font-size: 11px; color: #64748B;")
        desc_lbl.setWordWrap(True)
        left_layout.addWidget(desc_lbl)

        # --- GROUP 1: VIDEO SOURCE & FRAME TIMELINE SCRUBBER ---
        grp_timeline = QGroupBox("🎞️ Video & Frame Timeline")
        tl_layout = QVBoxLayout(grp_timeline)
        tl_layout.setContentsMargins(14, 12, 14, 12)
        tl_layout.setSpacing(8)

        # Video selector row
        h_vid = QHBoxLayout()
        h_vid.setSpacing(8)
        self.cbo_video = QComboBox()
        self.cbo_video.setFixedHeight(30)
        if self.video_paths:
            for p in self.video_paths:
                self.cbo_video.addItem(f"📹 {Path(p).name}", p)
        else:
            self.cbo_video.addItem("No video in queue (Simulated Canvas)", "")
        self.cbo_video.currentIndexChanged.connect(self.on_video_selection_changed)
        h_vid.addWidget(self.cbo_video, stretch=1)

        self.btn_open_custom_video = QPushButton("📂 Browse...")
        self.btn_open_custom_video.setFixedHeight(30)
        self.btn_open_custom_video.setStyleSheet("""
            QPushButton {
                background-color: #FFFFFF;
                color: #0F172A;
                border: 1px solid #CBD5E1;
                border-radius: 6px;
                font-size: 11px;
                font-weight: 600;
                padding: 0 10px;
            }
            QPushButton:hover {
                background-color: #EFF6FF;
                color: #1D4ED8;
                border-color: #93C5FD;
            }
        """)
        self.btn_open_custom_video.clicked.connect(self.action_browse_custom_video)
        h_vid.addWidget(self.btn_open_custom_video)
        tl_layout.addLayout(h_vid)

        # Frame scrubber slider row
        h_scrub = QHBoxLayout()
        self.slider_timeline = QSlider(Qt.Horizontal)
        self.slider_timeline.setRange(0, 150)  # 0.1s steps
        self.slider_timeline.setValue(10)      # 1.0s
        self.slider_timeline.valueChanged.connect(self.on_timeline_slider_changed)
        h_scrub.addWidget(self.slider_timeline, stretch=1)

        self.lbl_time_pos = QLabel("00:01.0 / 00:15.0")
        self.lbl_time_pos.setStyleSheet("font-family: Consolas, monospace; font-size: 11px; font-weight: bold; color: #0F172A;")
        h_scrub.addWidget(self.lbl_time_pos)
        tl_layout.addLayout(h_scrub)

        # Quick seek buttons
        h_seek_btns = QHBoxLayout()
        h_seek_btns.setSpacing(6)
        seek_btn_qss = """
            QPushButton {
                background-color: #FFFFFF;
                color: #0F172A;
                border: 1px solid #CBD5E1;
                border-radius: 5px;
                font-size: 11px;
                font-weight: bold;
                padding: 2px 4px;
            }
            QPushButton:hover {
                background-color: #EFF6FF;
                color: #1D4ED8;
                border-color: #93C5FD;
            }
            QPushButton:pressed {
                background-color: #DBEAFE;
                color: #1E40AF;
            }
        """
        for label, delta in [("⏮ -5s", -5.0), ("◀ -1s", -1.0), ("+1s ▶", 1.0), ("+5s ⏭", 5.0)]:
            btn = QPushButton(label)
            btn.setFixedHeight(26)
            btn.setStyleSheet(seek_btn_qss)
            btn.clicked.connect(lambda checked, d=delta: self.seek_relative(d))
            h_seek_btns.addWidget(btn)
        tl_layout.addLayout(h_seek_btns)
        left_layout.addWidget(grp_timeline)

        # --- GROUP 2: PLACEMENT & MARGIN V ---
        grp_pos = QGroupBox("📍 Placement & Vertical Offset (Margin V)")
        pos_layout = QGridLayout(grp_pos)
        pos_layout.setContentsMargins(14, 12, 14, 12)
        pos_layout.setVerticalSpacing(10)
        pos_layout.setHorizontalSpacing(10)

        pos_layout.addWidget(QLabel("Preset Position:"), 0, 0)
        self.cbo_preset_pos = QComboBox()
        self.cbo_preset_pos.setFixedHeight(30)
        self.cbo_preset_pos.addItems([
            "Bottom Standard (40px)",
            "Cover Low Sub (120px)",
            "Cover Mid Sub (220px)",
            "Top Header (50px)",
            "Custom..."
        ])
        self.cbo_preset_pos.currentTextChanged.connect(self.on_preset_pos_changed)
        pos_layout.addWidget(self.cbo_preset_pos, 0, 1)

        pos_layout.addWidget(QLabel("Margin V (Offset):"), 1, 0)
        h_margin = QHBoxLayout()
        self.slider_margin_v = QSlider(Qt.Horizontal)
        self.slider_margin_v.setRange(0, 600)
        self.slider_margin_v.setValue(40)
        self.slider_margin_v.valueChanged.connect(self.on_margin_slider_changed)
        h_margin.addWidget(self.slider_margin_v, stretch=1)

        self.spn_margin_v = QSpinBox()
        self.spn_margin_v.setRange(0, 600)
        self.spn_margin_v.setValue(40)
        self.spn_margin_v.setSuffix(" px")
        self.spn_margin_v.setFixedWidth(82)
        self.spn_margin_v.setFixedHeight(30)
        self.spn_margin_v.valueChanged.connect(self.on_margin_spin_changed)
        h_margin.addWidget(self.spn_margin_v)
        pos_layout.addLayout(h_margin, 1, 1)

        pos_layout.addWidget(QLabel("Alignment:"), 2, 0)
        self.cbo_align = QComboBox()
        self.cbo_align.setFixedHeight(30)
        self.cbo_align.addItem("Bottom-Center (Standard)", 2)
        self.cbo_align.addItem("Top-Center (Header)", 8)
        self.cbo_align.currentIndexChanged.connect(self.refresh_canvas)
        pos_layout.addWidget(self.cbo_align, 2, 1)
        left_layout.addWidget(grp_pos)

        # --- GROUP 3: HARDSUB COVER & STYLING ---
        grp_style = QGroupBox("🎨 Subtitle Style & Hardsub Cover Box")
        style_layout = QGridLayout(grp_style)
        style_layout.setContentsMargins(14, 12, 14, 12)
        style_layout.setVerticalSpacing(10)
        style_layout.setHorizontalSpacing(10)

        style_layout.addWidget(QLabel("Box / Style Preset:"), 0, 0)
        self.cbo_style_preset = QComboBox()
        self.cbo_style_preset.setFixedHeight(30)
        self.cbo_style_preset.addItems([
            "TikTok Black Box (Yellow Text) [Che Sub Chuẩn]",
            "White Box (Black Text)",
            "Black Box (White Text)",
            "Yellow Box (Black Text)",
            "Classic Outline (White / Shadow)",
            "Custom..."
        ])
        self.cbo_style_preset.currentTextChanged.connect(self.on_style_preset_changed)
        style_layout.addWidget(self.cbo_style_preset, 0, 1)

        style_layout.addWidget(QLabel("Box Padding:"), 1, 0)
        h_pad = QHBoxLayout()
        self.slider_padding = QSlider(Qt.Horizontal)
        self.slider_padding.setRange(0, 30)
        self.slider_padding.setValue(6)
        self.slider_padding.valueChanged.connect(self.on_padding_slider_changed)
        h_pad.addWidget(self.slider_padding, stretch=1)

        self.spn_padding = QSpinBox()
        self.spn_padding.setRange(0, 30)
        self.spn_padding.setValue(6)
        self.spn_padding.setSuffix(" px")
        self.spn_padding.setFixedWidth(78)
        self.spn_padding.setFixedHeight(30)
        self.spn_padding.valueChanged.connect(self.on_padding_spin_changed)
        h_pad.addWidget(self.spn_padding)
        style_layout.addLayout(h_pad, 1, 1)

        style_layout.addWidget(QLabel("Font & Size:"), 2, 0)
        h_font_row = QHBoxLayout()
        self.cbo_font_name = QComboBox()
        self.cbo_font_name.setFixedHeight(30)
        self.cbo_font_name.addItems(["Arial", "DejaVu Sans Bold", "Montserrat", "Segoe UI"])
        self.cbo_font_name.currentTextChanged.connect(self.refresh_canvas)
        h_font_row.addWidget(self.cbo_font_name, stretch=1)

        self.spn_font_sz = QSpinBox()
        self.spn_font_sz.setRange(12, 72)
        self.spn_font_sz.setValue(32)
        self.spn_font_sz.setSuffix(" pt")
        self.spn_font_sz.setFixedWidth(78)
        self.spn_font_sz.setFixedHeight(30)
        self.spn_font_sz.valueChanged.connect(self.refresh_canvas)
        h_font_row.addWidget(self.spn_font_sz)
        style_layout.addLayout(h_font_row, 2, 1)

        style_layout.addWidget(QLabel("Colors:"), 3, 0)
        h_colors = QHBoxLayout()
        h_colors.setSpacing(10)
        self.btn_text_color = QPushButton("Text Color")
        self.btn_text_color.setFixedHeight(28)
        self.btn_text_color.setCursor(Qt.PointingHandCursor)
        self.btn_text_color.clicked.connect(self.action_choose_text_color)
        h_colors.addWidget(self.btn_text_color)

        self.btn_bg_color = QPushButton("Box Color")
        self.btn_bg_color.setFixedHeight(28)
        self.btn_bg_color.setCursor(Qt.PointingHandCursor)
        self.btn_bg_color.clicked.connect(self.action_choose_bg_color)
        h_colors.addWidget(self.btn_bg_color)
        style_layout.addLayout(h_colors, 3, 1)
        left_layout.addWidget(grp_style)

        # --- GROUP 4: SAMPLE SUBTITLE TEXT ---
        grp_sample = QGroupBox("📝 Sample Subtitle Preview Text")
        samp_layout = QVBoxLayout(grp_sample)
        samp_layout.setContentsMargins(14, 10, 14, 10)
        samp_layout.setSpacing(6)

        self.txt_sample_sub = QLineEdit("Phụ đề tiếng Việt mẫu để che kín sub cũ")
        self.txt_sample_sub.setFixedHeight(30)
        self.txt_sample_sub.textChanged.connect(self.refresh_canvas)
        samp_layout.addWidget(self.txt_sample_sub)

        self.chk_two_lines = QCheckBox("Show 2-line sample (Check box height)")
        self.chk_two_lines.stateChanged.connect(self.on_two_lines_toggled)
        samp_layout.addWidget(self.chk_two_lines)
        left_layout.addWidget(grp_sample)

        # Dialog Buttons
        left_layout.addStretch()
        h_btns = QHBoxLayout()
        h_btns.setSpacing(10)

        self.btn_cancel = QPushButton("Close")
        self.btn_cancel.setFixedHeight(36)
        self.btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: #F1F5F9;
                color: #0F172A;
                font-weight: 600;
                border: 1px solid #CBD5E1;
                border-radius: 6px;
                padding: 0 16px;
            }
            QPushButton:hover {
                background-color: #E2E8F0;
                color: #0F172A;
                border-color: #94A3B8;
            }
        """)
        self.btn_cancel.clicked.connect(self.reject)
        h_btns.addWidget(self.btn_cancel)

        self.btn_apply = QPushButton("✓ Apply to Project")
        self.btn_apply.setFixedHeight(36)
        self.btn_apply.setStyleSheet("""
            QPushButton {
                background-color: #2563EB;
                color: #FFFFFF;
                font-weight: bold;
                border-radius: 6px;
                padding: 0 20px;
            }
            QPushButton:hover {
                background-color: #1D4ED8;
            }
        """)
        self.btn_apply.clicked.connect(self.action_apply_settings)
        h_btns.addWidget(self.btn_apply)
        left_layout.addLayout(h_btns)

        root_layout.addWidget(left_widget, stretch=5)

        # ================= RIGHT COLUMN: INTERACTIVE LIVE CANVAS =================
        grp_preview = QGroupBox("🎬 Real-Time Subtitle & Video Frame Canvas")
        grp_preview.setStyleSheet("""
            QGroupBox {
                background-color: #FFFFFF;
                border: 1px solid #CBD5E1;
                border-radius: 8px;
                padding-top: 12px;
            }
        """)
        prev_layout = QVBoxLayout(grp_preview)
        prev_layout.setContentsMargins(12, 10, 12, 12)
        prev_layout.setSpacing(8)

        # Canvas toolbar: Aspect ratio + Sample frame file
        h_tb = QHBoxLayout()
        h_tb.setSpacing(8)

        lbl_r = QLabel("Aspect:")
        lbl_r.setStyleSheet("font-weight: 500; font-size: 11px; color: #0F172A;")
        h_tb.addWidget(lbl_r)

        self.cbo_aspect = QComboBox()
        self.cbo_aspect.setFixedHeight(28)
        self.cbo_aspect.addItem("📱 9:16 (Shorts/TikTok)", "9:16")
        self.cbo_aspect.addItem("🖥️ 16:9 (Landscape)", "16:9")
        self.cbo_aspect.currentIndexChanged.connect(self.on_aspect_changed)
        h_tb.addWidget(self.cbo_aspect)

        self.btn_pick_img = QPushButton("🖼️ Load Image Frame...")
        self.btn_pick_img.setFixedHeight(28)
        self.btn_pick_img.setStyleSheet("""
            QPushButton {
                background-color: #FFFFFF;
                color: #0F172A;
                border: 1px solid #CBD5E1;
                border-radius: 5px;
                font-size: 11px;
                font-weight: 600;
                padding: 0 10px;
            }
            QPushButton:hover {
                background-color: #EFF6FF;
                color: #1D4ED8;
                border-color: #93C5FD;
            }
        """)
        self.btn_pick_img.clicked.connect(self.action_pick_image_frame)
        h_tb.addWidget(self.btn_pick_img)
        prev_layout.addLayout(h_tb)

        # Interactive Canvas
        self.canvas = SubtitlePreviewCanvas()
        self.canvas.margin_v_changed.connect(self.on_canvas_margin_v_changed)
        prev_layout.addWidget(self.canvas, stretch=1)

        # Tip bar at bottom of canvas
        lbl_tip = QLabel("💡 <i>Tip: Click & drag the subtitle box directly on the video canvas to adjust Margin V!</i>")
        lbl_tip.setStyleSheet("font-size: 11px; color: #2563EB; font-weight: 500;")
        lbl_tip.setAlignment(Qt.AlignCenter)
        prev_layout.addWidget(lbl_tip)

        root_layout.addWidget(grp_preview, stretch=6)

    def load_initial_video_and_settings(self):
        # 1. Load Subtitle settings from parent
        self.spn_margin_v.setValue(int(self.settings.get("margin_v", 40)))
        self.slider_margin_v.setValue(self.spn_margin_v.value())

        pos_str = self.settings.get("position", "Bottom Standard (40px)")
        idx_pos = self.cbo_preset_pos.findText(pos_str)
        if idx_pos >= 0:
            self.cbo_preset_pos.setCurrentIndex(idx_pos)

        self.spn_padding.setValue(int(self.settings.get("box_padding", 6)))
        self.slider_padding.setValue(self.spn_padding.value())

        self.spn_font_sz.setValue(int(self.settings.get("font_size", 32)))

        font_name = self.settings.get("font_name", "Arial")
        idx_font = self.cbo_font_name.findText(font_name)
        if idx_font >= 0:
            self.cbo_font_name.setCurrentIndex(idx_font)

        style_name = self.settings.get("sub_style", "TikTok Black Box (Yellow Text) [Che Sub Chuẩn]")
        idx_st = self.cbo_style_preset.findText(style_name)
        if idx_st >= 0:
            self.cbo_style_preset.setCurrentIndex(idx_st)

        self.border_style = int(self.settings.get("border_style", 3))
        self.text_color = str(self.settings.get("text_color", "#FFE600"))
        self.bg_color = str(self.settings.get("bg_color", "#000000"))
        self.update_color_buttons()

        # 2. Inspect video metadata and load 1st frame
        if self.current_video_path and Path(self.current_video_path).is_file():
            meta = get_video_meta(self.current_video_path)
            self.video_duration = max(1.0, float(meta.get("duration", 15.0)))
            self.video_aspect = meta.get("aspect_ratio", "9:16")

            # Update timeline slider maximum (steps of 0.1s)
            max_steps = int(round(self.video_duration * 10))
            self.slider_timeline.setRange(0, max(10, max_steps))
            self.slider_timeline.setValue(min(10, max_steps))

            if self.video_aspect == "16:9":
                self.cbo_aspect.setCurrentIndex(1)
            else:
                self.cbo_aspect.setCurrentIndex(0)

            self.load_frame_at(1.0)
        else:
            self.refresh_canvas()

    def update_color_buttons(self):
        def _get_fg(hex_col: str) -> str:
            try:
                qc = QColor(hex_col)
                lum = 0.299 * qc.red() + 0.587 * qc.green() + 0.114 * qc.blue()
                return "#000000" if lum > 140 else "#FFFFFF"
            except Exception:
                return "#000000"

        fg_text = _get_fg(self.text_color)
        fg_bg = _get_fg(self.bg_color)
        self.btn_text_color.setStyleSheet(f"background-color: {self.text_color}; color: {fg_text}; font-weight: bold; border: 1px solid #64748B; border-radius: 4px; padding: 2px 6px;")
        self.btn_bg_color.setStyleSheet(f"background-color: {self.bg_color}; color: {fg_bg}; font-weight: bold; border: 1px solid #64748B; border-radius: 4px; padding: 2px 6px;")

    def load_frame_at(self, sec: float):
        sec = max(0.0, min(self.video_duration, sec))
        self.lbl_time_pos.setText(f"{int(sec//60):02d}:{sec%60:04.1f} / {int(self.video_duration//60):02d}:{self.video_duration%60:04.1f}")
        if self.current_video_path and Path(self.current_video_path).is_file():
            frame_path = extract_video_frame_at(self.current_video_path, sec)
            if frame_path and Path(frame_path).is_file():
                pix = QPixmap(frame_path)
                if not pix.isNull():
                    self.canvas.set_background_pixmap(pix)
                    if pix.width() > pix.height():
                        self.cbo_aspect.setCurrentIndex(1)
                    else:
                        self.cbo_aspect.setCurrentIndex(0)
        self.refresh_canvas()

    def on_timeline_slider_changed(self, val: int):
        sec = val / 10.0
        self.load_frame_at(sec)

    def seek_relative(self, delta: float):
        curr_sec = self.slider_timeline.value() / 10.0
        new_sec = max(0.0, min(self.video_duration, curr_sec + delta))
        self.slider_timeline.setValue(int(round(new_sec * 10)))

    def on_video_selection_changed(self, idx: int):
        data = self.cbo_video.currentData()
        if data and Path(data).is_file():
            self.current_video_path = data
            meta = get_video_meta(self.current_video_path)
            self.video_duration = max(1.0, float(meta.get("duration", 15.0)))
            self.video_aspect = meta.get("aspect_ratio", "9:16")
            max_steps = int(round(self.video_duration * 10))
            self.slider_timeline.setRange(0, max(10, max_steps))
            self.slider_timeline.setValue(min(10, max_steps))
            self.load_frame_at(1.0)

    def action_browse_custom_video(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Video to Preview Subtitles",
            "",
            "Video Files (*.mp4 *.mkv *.mov *.avi *.webm);;All Files (*.*)"
        )
        if file_path:
            self.cbo_video.blockSignals(True)
            self.cbo_video.addItem(f"📹 {Path(file_path).name}", file_path)
            self.cbo_video.setCurrentIndex(self.cbo_video.count() - 1)
            self.cbo_video.blockSignals(False)
            self.on_video_selection_changed(self.cbo_video.currentIndex())

    def action_pick_image_frame(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Frame Image",
            "",
            "Images (*.png *.jpg *.jpeg *.webp *.bmp)"
        )
        if file_path:
            pix = QPixmap(file_path)
            if not pix.isNull():
                self.canvas.set_background_pixmap(pix)
                if pix.width() > pix.height():
                    self.cbo_aspect.setCurrentIndex(1)
                else:
                    self.cbo_aspect.setCurrentIndex(0)
                self.refresh_canvas()

    def on_aspect_changed(self):
        aspect = self.cbo_aspect.currentData() or "9:16"
        self.canvas.set_aspect_ratio(aspect)

    def on_canvas_margin_v_changed(self, val: int):
        self.slider_margin_v.blockSignals(True)
        self.spn_margin_v.blockSignals(True)
        self.slider_margin_v.setValue(val)
        self.spn_margin_v.setValue(val)
        self.slider_margin_v.blockSignals(False)
        self.spn_margin_v.blockSignals(False)
        self.update_preset_from_margin(val)

    def on_margin_slider_changed(self, val: int):
        self.spn_margin_v.blockSignals(True)
        self.spn_margin_v.setValue(val)
        self.spn_margin_v.blockSignals(False)
        self.canvas.set_margin_v(val)
        self.update_preset_from_margin(val)

    def on_margin_spin_changed(self, val: int):
        self.slider_margin_v.blockSignals(True)
        self.slider_margin_v.setValue(val)
        self.slider_margin_v.blockSignals(False)
        self.canvas.set_margin_v(val)
        self.update_preset_from_margin(val)

    def update_preset_from_margin(self, val: int):
        preset_map = {
            40: "Bottom Standard (40px)",
            120: "Cover Low Sub (120px)",
            220: "Cover Mid Sub (220px)",
            50: "Top Header (50px)"
        }
        name = preset_map.get(val, "Custom...")
        self.cbo_preset_pos.blockSignals(True)
        self.cbo_preset_pos.setCurrentText(name)
        self.cbo_preset_pos.blockSignals(False)

    def on_preset_pos_changed(self, text: str):
        preset_map = {
            "Bottom Standard (40px)": (40, 2),
            "Cover Low Sub (120px)": (120, 2),
            "Cover Mid Sub (220px)": (220, 2),
            "Top Header (50px)": (50, 8)
        }
        if text in preset_map:
            m, align = preset_map[text]
            self.spn_margin_v.setValue(m)
            self.cbo_align.blockSignals(True)
            self.cbo_align.setCurrentIndex(0 if align == 2 else 1)
            self.cbo_align.blockSignals(False)
            self.refresh_canvas()

    def on_padding_slider_changed(self, val: int):
        self.spn_padding.blockSignals(True)
        self.spn_padding.setValue(val)
        self.spn_padding.blockSignals(False)
        self.refresh_canvas()

    def on_padding_spin_changed(self, val: int):
        self.slider_padding.blockSignals(True)
        self.slider_padding.setValue(val)
        self.slider_padding.blockSignals(False)
        self.refresh_canvas()

    def on_style_preset_changed(self, text: str):
        if "TikTok Black Box" in text:
            self.border_style = 3
            self.text_color = "#FFE600"
            self.bg_color = "#000000"
        elif "White Box" in text:
            self.border_style = 3
            self.text_color = "#000000"
            self.bg_color = "#FFFFFF"
        elif "Black Box (White Text)" in text:
            self.border_style = 3
            self.text_color = "#FFFFFF"
            self.bg_color = "#000000"
        elif "Yellow Box" in text:
            self.border_style = 3
            self.text_color = "#000000"
            self.bg_color = "#FACC15"
        elif "Classic Outline" in text:
            self.border_style = 1
            self.text_color = "#FFFFFF"
            self.bg_color = "#000000"
        self.update_color_buttons()
        self.refresh_canvas()

    def action_choose_text_color(self):
        col = QColorDialog.getColor(QColor(self.text_color), self, "Select Text Color")
        if col.isValid():
            self.text_color = col.name().upper()
            self.cbo_style_preset.blockSignals(True)
            self.cbo_style_preset.setCurrentText("Custom...")
            self.cbo_style_preset.blockSignals(False)
            self.update_color_buttons()
            self.refresh_canvas()

    def action_choose_bg_color(self):
        col = QColorDialog.getColor(QColor(self.bg_color), self, "Select Box Background Color")
        if col.isValid():
            self.bg_color = col.name().upper()
            self.cbo_style_preset.blockSignals(True)
            self.cbo_style_preset.setCurrentText("Custom...")
            self.cbo_style_preset.blockSignals(False)
            self.update_color_buttons()
            self.refresh_canvas()

    def on_two_lines_toggled(self, checked: bool):
        if checked:
            self.txt_sample_sub.setText("Dòng 1: Phụ đề tiếng Việt che kín sub cũ\nDòng 2: Mô phỏng phụ đề 2 dòng chuẩn xác")
        else:
            self.txt_sample_sub.setText("Phụ đề tiếng Việt mẫu để che kín sub cũ")

    def refresh_canvas(self):
        text = self.txt_sample_sub.text().strip()
        align = self.cbo_align.currentData() or 2
        margin = self.spn_margin_v.value()
        font_nm = self.cbo_font_name.currentText()
        font_sz = self.spn_font_sz.value()
        pad = self.spn_padding.value()

        self.canvas.set_subtitle_config(
            sub_text=text,
            alignment=align,
            margin_v=margin,
            font_name=font_nm,
            font_size=font_sz,
            border_style=self.border_style,
            box_padding=pad,
            text_color=self.text_color,
            bg_color=self.bg_color
        )

    def action_apply_settings(self):
        """Save settings and accept dialog to synchronize with MainWindow."""
        self.result_settings = {
            "position": self.cbo_preset_pos.currentText(),
            "margin_v": self.spn_margin_v.value(),
            "alignment": self.cbo_align.currentData() or 2,
            "box_padding": self.spn_padding.value(),
            "font_size": self.spn_font_sz.value(),
            "font_name": self.cbo_font_name.currentText(),
            "sub_style": self.cbo_style_preset.currentText(),
            "border_style": self.border_style,
            "text_color": self.text_color,
            "bg_color": self.bg_color
        }
        self.accept()


class MainWindow(QMainWindow):
    """Main window for AutoDub Studio."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("AutoDub Studio - AI Video Dubbing & Subtitles")
        self.resize(1280, 890)
        self.setMinimumSize(1080, 780)

        # Căn giữa cửa sổ trên màn hình desktop
        try:
            screen_geo = QApplication.primaryScreen().availableGeometry()
            self.move(
                max(0, (screen_geo.width() - 1280) // 2),
                max(0, (screen_geo.height() - 890) // 2)
            )
        except Exception:
            pass

        self.worker: Optional[DubbingWorker] = None

        # Cấu hình Presets cho Subtitle Styling
        self.SUB_STYLE_PRESETS = {
            "TikTok Black Box (Yellow Text) [Che Sub Chuẩn]": {
                "border_style": 3,
                "text_color": "#FFE600",
                "bg_color": "#000000",
                "outline_color": "#000000",
                "outline_width": 6,
                "shadow_width": 0
            },
            "White Box (Black Text)": {
                "border_style": 3,
                "text_color": "#000000",
                "bg_color": "#FFFFFF",
                "outline_color": "#FFFFFF",
                "outline_width": 6,
                "shadow_width": 0
            },
            "Black Box (White Text)": {
                "border_style": 3,
                "text_color": "#FFFFFF",
                "bg_color": "#000000",
                "outline_color": "#000000",
                "outline_width": 6,
                "shadow_width": 0
            },
            "Yellow Box (Black Text)": {
                "border_style": 3,
                "text_color": "#000000",
                "bg_color": "#FACC15",
                "outline_color": "#FACC15",
                "outline_width": 6,
                "shadow_width": 0
            },
            "Classic Outline (White / Shadow)": {
                "border_style": 1,
                "text_color": "#FFFFFF",
                "bg_color": "#000000",
                "outline_color": "#000000",
                "outline_width": 3,
                "shadow_width": 1
            },
            "Custom...": None
        }
        self.sub_border_style = 3
        self.sub_text_color = "#000000"
        self.sub_bg_color = "#FFFFFF"
        self.sub_outline_width = 6
        self.sub_shadow_width = 0

        # Presets cấu hình LLM Provider
        self.LLM_PRESETS = {
            "Custom Settings": {
                "base_url": Config.LLM_BASE_URL,
                "api_key": Config.LLM_API_KEY,
                "model": Config.LLM_MODEL
            },
            "VNPT-SI AI Gateway": {
                "base_url": "https://llm.vnptsi.vn/v1",
                "api_key": Config.LLM_API_KEY if ("vnptsi" in Config.LLM_BASE_URL and Config.LLM_API_KEY != "no-key-required") else "sk-FPLy2OadJQoN9haTvKjGHg",
                "model": "global-llm"
            },
            "Ollama (Local - http://localhost:11434/v1)": {
                "base_url": "http://localhost:11434/v1",
                "api_key": "ollama",
                "model": "gemma3:4b"
            },
            "OpenAI Official (https://api.openai.com/v1)": {
                "base_url": "https://api.openai.com/v1",
                "api_key": "",
                "model": "gpt-4o-mini"
            },
            "Google AI Studio (Gemini)": {
                "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
                "api_key": "",
                "model": "gemini-2.5-flash"
            },
            "Groq Cloud (https://api.groq.com/openai/v1)": {
                "base_url": "https://api.groq.com/openai/v1",
                "api_key": "",
                "model": "qwen/qwen3.8-27b"
            },
            "DeepSeek API (https://api.deepseek.com/v1)": {
                "base_url": "https://api.deepseek.com/v1",
                "api_key": "",
                "model": "deepseek-chat"
            }
        }

        # Cấu hình Watermark mặc định
        self.watermark_config = {
            "text_enabled": True,
            "text": "Bạn đang xem video được sub bởi Vũ Mạnh Cường",
            "text_timing": "mid_video",
            "text_position": "center",
            "text_font_size": 22,
            "logo_enabled": False,
            "logo_path": "",
            "logo_position": "top-right",
            "logo_opacity": 0.80,
            "logo_max_width": 160
        }

        self.init_ui()
        self.apply_styles()
        self.update_cookie_button_state()

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(14, 10, 14, 12)
        main_layout.setSpacing(10)

        # 1. TOP TABS (Full Width across the window)
        self.tabs = QTabWidget()
        self.tab_dubbing = QWidget()
        self.tab_subs = QWidget()
        self.tab_models = QWidget()

        self.tabs.addTab(self.tab_dubbing, "🎬 Video Dubbing")
        self.tabs.addTab(self.tab_subs, "📝 Subtitle Translation")
        self.tabs.addTab(self.tab_models, "⚙️ Model Manager")

        # Status Indicators in the top-right corner of tabs
        self.lbl_indicators = QLabel("Network: ✓  |  LLM: ✓  |  Whisper: ✓  |  FFmpeg: ✓   ")
        self.lbl_indicators.setStyleSheet("color: #16A34A; font-weight: bold; font-size: 12px; margin-right: 10px;")
        self.tabs.setCornerWidget(self.lbl_indicators, Qt.TopRightCorner)

        main_layout.addWidget(self.tabs)

        # MAIN VIDEO DUBBING TAB LAYOUT
        tab_layout = QVBoxLayout(self.tab_dubbing)
        tab_layout.setContentsMargins(8, 8, 8, 8)
        tab_layout.setSpacing(8)

        # 2. VIDEO QUEUE SECTION
        lbl_queue = QLabel("<b>Videos to Dub</b>")
        tab_layout.addWidget(lbl_queue)

        # Queue Toolbar
        queue_toolbar = QHBoxLayout()
        queue_toolbar.setSpacing(8)

        self.btn_paste_links = QPushButton("+ Paste Video Links...")
        self.btn_paste_links.setFixedHeight(32)
        self.btn_add_files = QPushButton("+ Add Videos...")
        self.btn_add_files.setFixedHeight(32)
        self.btn_cookies = QPushButton("🍪 Cookies (.txt)")
        self.btn_cookies.setFixedHeight(32)
        self.btn_attach_srt = QPushButton("Attach .srt to Selected...")
        self.btn_attach_srt.setFixedHeight(32)
        self.btn_remove_row = QPushButton("Remove Selected")
        self.btn_remove_row.setFixedHeight(32)
        self.chk_only_srt = QCheckBox("Translate .srt only...")

        self.btn_paste_links.clicked.connect(self.action_paste_links)
        self.btn_add_files.clicked.connect(self.action_add_files)
        self.btn_cookies.clicked.connect(self.action_manage_cookies)
        self.btn_remove_row.clicked.connect(self.action_remove_selected_rows)

        queue_toolbar.addWidget(self.btn_paste_links)
        queue_toolbar.addWidget(self.btn_add_files)
        queue_toolbar.addWidget(self.btn_cookies)
        queue_toolbar.addWidget(self.btn_attach_srt)
        queue_toolbar.addWidget(self.btn_remove_row)
        queue_toolbar.addStretch()
        queue_toolbar.addWidget(self.chk_only_srt)
        tab_layout.addLayout(queue_toolbar)

        # Queue Table (QTableWidget)
        self.table_queue = QTableWidget(0, 3)
        self.table_queue.setHorizontalHeaderLabels(["Source (File or URL)", "Attached Subtitle", "Status"])
        self.table_queue.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table_queue.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table_queue.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table_queue.setFixedHeight(95)
        self.table_queue.setSelectionBehavior(QTableWidget.SelectRows)
        tab_layout.addWidget(self.table_queue)

        # 3. PIPELINE STEPPER
        stepper_lbl = QLabel(
            "<span style='color: #27AE60;'><b>① Source</b></span>  ➔  "
            "<span style='color: #27AE60;'><b>② Original Subtitle</b></span>  ➔  "
            "<span style='color: #27AE60;'><b>③ Translation</b></span>  ➔  "
            "<span style='color: #27AE60;'><b>④ Dubbing</b></span>  ➔  "
            "<span style='color: #27AE60;'><b>⑤ Export Video</b></span>"
        )
        stepper_lbl.setAlignment(Qt.AlignCenter)
        tab_layout.addWidget(stepper_lbl)

        # 4. TWO-COLUMN CONFIGURATION GRID
        config_grid = QGridLayout()
        config_grid.setSpacing(12)

        # --- LEFT COLUMN: Original Subtitles & Translation ---
        left_col = QVBoxLayout()
        left_col.setSpacing(10)

        # Group ② Original Subtitles
        grp_source = QGroupBox("② Original Subtitle")
        layout_source = QGridLayout(grp_source)
        layout_source.setContentsMargins(18, 14, 18, 14)
        layout_source.setVerticalSpacing(12)
        layout_source.setHorizontalSpacing(14)
        layout_source.setColumnStretch(0, 0)
        layout_source.setColumnStretch(1, 1)
        layout_source.setColumnMinimumWidth(0, 110)

        layout_source.addWidget(QLabel("Mode:"), 0, 0)
        self.cbo_mode = QComboBox()
        self.cbo_mode.setFixedHeight(32)
        self.cbo_mode.addItems(["Auto — detect hardcoded subtitles", "Always run STT (Whisper)"])
        layout_source.addWidget(self.cbo_mode, 0, 1)

        layout_source.addWidget(QLabel("Source Language:"), 1, 0)
        self.cbo_lang = QComboBox()
        self.cbo_lang.setFixedHeight(32)
        self.cbo_lang.addItems(["auto (Auto Detect)", "zh (Chinese)", "en (English)"])
        layout_source.addWidget(self.cbo_lang, 1, 1)
        left_col.addWidget(grp_source)

        # Group ③ Translation
        grp_trans = QGroupBox("③ Translation")
        layout_trans = QGridLayout(grp_trans)
        layout_trans.setContentsMargins(18, 14, 18, 14)
        layout_trans.setVerticalSpacing(12)
        layout_trans.setHorizontalSpacing(14)
        layout_trans.setColumnStretch(0, 0)
        layout_trans.setColumnStretch(1, 1)
        layout_trans.setColumnMinimumWidth(0, 110)

        layout_trans.addWidget(QLabel("Translate With:"), 0, 0)
        h_model = QHBoxLayout()
        h_model.setSpacing(6)
        self.txt_model = QLineEdit(Config.LLM_MODEL)
        self.txt_model.setFixedHeight(32)
        self.txt_model.setReadOnly(True)
        self.btn_change_model = QPushButton("Change...")
        self.btn_change_model.setFixedHeight(32)
        self.btn_change_model.clicked.connect(self.action_change_model)
        h_model.addWidget(self.txt_model)
        h_model.addWidget(self.btn_change_model)
        layout_trans.addLayout(h_model, 0, 1)

        layout_trans.addWidget(QLabel("Engine Mode:"), 1, 0)
        self.cbo_trans_mode = QComboBox()
        self.cbo_trans_mode.setFixedHeight(32)
        self.cbo_trans_mode.addItems(["Fast — Parallel", "Sequential — Accurate"])
        layout_trans.addWidget(self.cbo_trans_mode, 1, 1)

        layout_trans.addWidget(QLabel("Genre:"), 2, 0)
        self.cbo_genre = QComboBox()
        self.cbo_genre.setFixedHeight(32)
        self.cbo_genre.addItems([
            "Daily Life / Social Media",
            "Humor / Comedy",
            "Period / Drama",
            "Movie Recap / Storytelling",
            "Tech / Tutorial"
        ])
        layout_trans.addWidget(self.cbo_genre, 2, 1)

        layout_trans.addWidget(QLabel("Custom Terms:"), 3, 0)
        self.txt_custom_terms = QLineEdit()
        self.txt_custom_terms.setFixedHeight(32)
        self.txt_custom_terms.setPlaceholderText("Rules/Names, e.g., Luffy: Lu; Douyin: TikTok")
        layout_trans.addWidget(self.txt_custom_terms, 3, 1)
        left_col.addWidget(grp_trans)

        config_grid.addLayout(left_col, 0, 0)

        # --- RIGHT COLUMN: Dubbing & Export ---
        right_col = QVBoxLayout()
        right_col.setSpacing(10)

        # Group ④ Dubbing
        grp_tts = QGroupBox("④ Dubbing")
        layout_tts = QGridLayout(grp_tts)
        layout_tts.setContentsMargins(18, 14, 18, 14)
        layout_tts.setVerticalSpacing(12)
        layout_tts.setHorizontalSpacing(14)
        layout_tts.setColumnStretch(0, 0)
        layout_tts.setColumnStretch(1, 1)
        layout_tts.setColumnMinimumWidth(0, 110)

        layout_tts.addWidget(QLabel("Voice:"), 0, 0)
        self.cbo_voice = QComboBox()
        self.cbo_voice.setFixedHeight(32)
        for label, voice_key in Config.AVAILABLE_VOICES.items():
            self.cbo_voice.addItem(label, voice_key)
        layout_tts.addWidget(self.cbo_voice, 0, 1)

        # Gom 2 input number (Ducking & Delay) vào 1 hàng ngang với nhãn gọn
        layout_tts.addWidget(QLabel("Volume & Delay:"), 1, 0)
        h_tuning = QHBoxLayout()
        h_tuning.setSpacing(10)

        lbl_ducking = QLabel("Ducking:")
        self.spn_ducking = QDoubleSpinBox()
        self.spn_ducking.setFixedHeight(32)
        self.spn_ducking.setFixedWidth(85)
        self.spn_ducking.setRange(0.0, 1.0)
        self.spn_ducking.setSingleStep(0.02)
        self.spn_ducking.setValue(Config.DEFAULT_DUCKING_VOLUME)

        lbl_delay = QLabel("Delay:")
        lbl_delay.setFixedWidth(40)
        self.spn_delay = QDoubleSpinBox()
        self.spn_delay.setFixedHeight(32)
        self.spn_delay.setFixedWidth(85)
        self.spn_delay.setRange(-2.0, 5.0)
        self.spn_delay.setValue(0.0)

        h_tuning.addWidget(lbl_ducking)
        h_tuning.addWidget(self.spn_ducking)
        h_tuning.addWidget(lbl_delay)
        h_tuning.addWidget(self.spn_delay)
        h_tuning.addStretch()
        layout_tts.addLayout(h_tuning, 1, 1)

        layout_tts.addWidget(QLabel("Voice Cloning:"), 2, 0)
        h_clone = QHBoxLayout()
        h_clone.setSpacing(6)
        self.txt_clone = QLineEdit()
        self.txt_clone.setFixedHeight(32)
        self.txt_clone.setPlaceholderText("(Optional) Select reference audio...")
        self.btn_browse_clone = QPushButton("📁")
        self.btn_browse_clone.setFixedSize(38, 32)
        self.btn_browse_clone.setStyleSheet("background-color: #F8FAFC; color: #0F172A; font-size: 14px; border: 1px solid #CBD5E1; border-radius: 6px;")
        h_clone.addWidget(self.txt_clone)
        h_clone.addWidget(self.btn_browse_clone)
        layout_tts.addLayout(h_clone, 2, 1)
        right_col.addWidget(grp_tts)

        # Group ⑤ Export
        grp_export = QGroupBox("⑤ Export")
        grp_export.setMinimumHeight(280)
        layout_export = QGridLayout(grp_export)
        layout_export.setContentsMargins(18, 10, 18, 10)
        layout_export.setVerticalSpacing(8)
        layout_export.setHorizontalSpacing(14)
        layout_export.setColumnStretch(0, 0)
        layout_export.setColumnStretch(1, 1)
        layout_export.setColumnMinimumWidth(0, 110)

        h_sub_opts = QHBoxLayout()
        h_sub_opts.setSpacing(20)
        self.chk_burn_sub = QCheckBox("Burn translated subtitles into video")
        self.chk_burn_sub.setChecked(True)
        self.chk_blur_orig = QCheckBox("Blur original subtitles")
        h_sub_opts.addWidget(self.chk_burn_sub)
        h_sub_opts.addWidget(self.chk_blur_orig)
        h_sub_opts.addStretch()
        layout_export.addLayout(h_sub_opts, 0, 0, 1, 2)

        layout_export.addWidget(QLabel("Font:"), 1, 0)
        h_font = QHBoxLayout()
        h_font.setSpacing(12)
        self.cbo_font = QComboBox()
        self.cbo_font.setFixedHeight(30)
        self.cbo_font.setFixedWidth(200)
        self.cbo_font.addItems(["Arial", "DejaVu Sans Bold", "Montserrat", "Segoe UI"])
        lbl_size = QLabel("Size:")
        lbl_size.setFixedWidth(34)
        self.spn_font_size = QSpinBox()
        self.spn_font_size.setFixedHeight(30)
        self.spn_font_size.setFixedWidth(80)
        self.spn_font_size.setRange(10, 100)
        self.spn_font_size.setValue(32)
        h_font.addWidget(self.cbo_font)
        h_font.addWidget(lbl_size)
        h_font.addWidget(self.spn_font_size)
        h_font.addStretch()
        layout_export.addLayout(h_font, 1, 1)

        # Row 2: Sub Style (Presets + Color Swatches)
        layout_export.addWidget(QLabel("Sub Style:"), 2, 0)
        h_sub_style = QHBoxLayout()
        h_sub_style.setSpacing(10)

        self.cbo_sub_style = QComboBox()
        self.cbo_sub_style.setFixedHeight(30)
        self.cbo_sub_style.setFixedWidth(200)
        self.cbo_sub_style.addItems(list(self.SUB_STYLE_PRESETS.keys()))
        self.cbo_sub_style.currentTextChanged.connect(self.on_sub_style_changed)

        lbl_sub_text = QLabel("Text:")
        lbl_sub_text.setFixedWidth(34)
        self.btn_sub_text_color = QPushButton()
        self.btn_sub_text_color.setFixedSize(36, 28)
        self.btn_sub_text_color.setCursor(Qt.PointingHandCursor)
        self.btn_sub_text_color.clicked.connect(self.action_pick_sub_text_color)

        lbl_sub_bg = QLabel("Box:")
        lbl_sub_bg.setFixedWidth(30)
        self.btn_sub_bg_color = QPushButton()
        self.btn_sub_bg_color.setFixedSize(36, 28)
        self.btn_sub_bg_color.setCursor(Qt.PointingHandCursor)
        self.btn_sub_bg_color.clicked.connect(self.action_pick_sub_bg_color)

        self.update_sub_color_swatches()

        h_sub_style.addWidget(self.cbo_sub_style)
        h_sub_style.addWidget(lbl_sub_text)
        h_sub_style.addWidget(self.btn_sub_text_color)
        h_sub_style.addWidget(lbl_sub_bg)
        h_sub_style.addWidget(self.btn_sub_bg_color)
        h_sub_style.addStretch()
        layout_export.addLayout(h_sub_style, 2, 1)

        # Row 3: Sub Position (Che phụ đề cũ)
        layout_export.addWidget(QLabel("Sub Position:"), 3, 0)
        h_sub_pos = QHBoxLayout()
        h_sub_pos.setSpacing(10)
        self.cbo_sub_pos = QComboBox()
        self.cbo_sub_pos.setFixedHeight(30)
        self.cbo_sub_pos.setFixedWidth(180)
        self.cbo_sub_pos.addItems([
            "Bottom Standard (40px)",
            "Cover Low Sub (120px)",
            "Cover Mid Sub (220px)",
            "Top Header (50px)",
            "Custom..."
        ])
        self.cbo_sub_pos.currentTextChanged.connect(self.on_sub_pos_changed)

        lbl_margin_v = QLabel("Margin:")
        lbl_margin_v.setFixedWidth(46)
        self.spn_sub_margin_v = QSpinBox()
        self.spn_sub_margin_v.setFixedHeight(30)
        self.spn_sub_margin_v.setFixedWidth(84)
        self.spn_sub_margin_v.setRange(0, 600)
        self.spn_sub_margin_v.setValue(40)
        self.spn_sub_margin_v.setSuffix(" px")
        self.spn_sub_margin_v.valueChanged.connect(self.on_sub_margin_spin_changed)

        lbl_pad = QLabel("Box Pad:")
        lbl_pad.setFixedWidth(52)
        self.spn_box_padding = QSpinBox()
        self.spn_box_padding.setFixedHeight(30)
        self.spn_box_padding.setFixedWidth(78)
        self.spn_box_padding.setRange(0, 30)
        self.spn_box_padding.setValue(6)
        self.spn_box_padding.setSuffix(" px")

        h_sub_pos.addWidget(self.cbo_sub_pos)
        h_sub_pos.addWidget(lbl_margin_v)
        h_sub_pos.addWidget(self.spn_sub_margin_v)
        h_sub_pos.addWidget(lbl_pad)
        h_sub_pos.addWidget(self.spn_box_padding)

        self.btn_preview_sub = QPushButton("👁️ Preview Sub Placement...")
        self.btn_preview_sub.setFixedHeight(30)
        self.btn_preview_sub.setStyleSheet("background-color: #EFF6FF; color: #1D4ED8; font-weight: 600; font-size: 12px; border: 1px solid #93C5FD; border-radius: 6px; padding: 0 12px;")
        self.btn_preview_sub.setToolTip("Open Live Frame Preview to align subtitle position and cover hardsubs perfectly")
        self.btn_preview_sub.clicked.connect(self.action_open_subtitle_preview_dialog)
        h_sub_pos.addWidget(self.btn_preview_sub)

        h_sub_pos.addStretch()
        layout_export.addLayout(h_sub_pos, 3, 1)

        # Row 4: Watermark
        layout_export.addWidget(QLabel("Watermark:"), 4, 0)
        h_wm = QHBoxLayout()
        h_wm.setSpacing(10)
        self.chk_watermark = QCheckBox("Enable")
        self.chk_watermark.setChecked(True)
        self.chk_watermark.setFixedHeight(30)

        self.btn_watermark_cfg = QPushButton("🎨 Watermark Settings...")
        self.btn_watermark_cfg.setFixedHeight(30)
        self.btn_watermark_cfg.setFixedWidth(180)
        self.btn_watermark_cfg.setStyleSheet("background-color: #F8FAFC; color: #0F172A; font-weight: 500; font-size: 12px; border: 1px solid #CBD5E1; border-radius: 6px;")
        self.btn_watermark_cfg.clicked.connect(self.action_open_watermark_dialog)

        self.lbl_watermark_summary = QLabel("(Text: On, Logo: Off)")
        self.lbl_watermark_summary.setStyleSheet("color: #64748B; font-size: 11px;")

        h_wm.addWidget(self.chk_watermark)
        h_wm.addWidget(self.btn_watermark_cfg)
        h_wm.addWidget(self.lbl_watermark_summary)
        h_wm.addStretch()
        layout_export.addLayout(h_wm, 4, 1)

        # Row 5: Encoder & Hardware Acceleration
        layout_export.addWidget(QLabel("Encoder:"), 5, 0)
        h_enc = QHBoxLayout()
        h_enc.setSpacing(10)
        self.cbo_encoder = QComboBox()
        self.cbo_encoder.setFixedHeight(32)
        self.cbo_encoder.setFixedWidth(260)

        hw_caps = Config.detect_hardware_capabilities()
        if hw_caps["has_nvenc"]:
            self.cbo_encoder.addItem("⚡ h264_nvenc (NVIDIA GPU - Super Fast)", "h264_nvenc")
            self.cbo_encoder.addItem("libx264 (CPU Standard)", "libx264")
            self.cbo_encoder.addItem("copy (Passthrough - Instant)", "copy")
        else:
            self.cbo_encoder.addItem("libx264 (CPU Standard)", "libx264")
            self.cbo_encoder.addItem("copy (Passthrough - Instant)", "copy")
            self.cbo_encoder.addItem("⚡ h264_nvenc (NVIDIA GPU - Auto Fallback)", "h264_nvenc")

        # Hardware status indicator badge
        if hw_caps["has_cuda"] or hw_caps["has_nvenc"]:
            hw_text = "🚀 GPU Active (NVIDIA CUDA/NVENC)"
            hw_style = "color: #16A34A; font-weight: bold; font-size: 11px; background-color: #DCFCE7; padding: 4px 8px; border-radius: 4px;"
        else:
            hw_text = "💻 CPU Engine (Intel/AMD)"
            hw_style = "color: #475569; font-size: 11px; background-color: #F1F5F9; padding: 4px 8px; border-radius: 4px;"

        self.lbl_hw_status = QLabel(hw_text)
        self.lbl_hw_status.setStyleSheet(hw_style)

        h_enc.addWidget(self.cbo_encoder)
        h_enc.addWidget(self.lbl_hw_status)
        h_enc.addStretch()
        layout_export.addLayout(h_enc, 5, 1)

        # Row 6: Save To
        layout_export.addWidget(QLabel("Save To:"), 6, 0)
        h_out = QHBoxLayout()
        h_out.setSpacing(8)
        self.txt_output_dir = QLineEdit(str(Config.OUTPUT_DIR))
        self.txt_output_dir.setFixedHeight(32)
        self.btn_browse_out = QPushButton("Browser")
        self.btn_browse_out.setFixedHeight(32)
        self.btn_browse_out.setFixedWidth(78)
        self.btn_browse_out.setStyleSheet("background-color: #F8FAFC; color: #0F172A; font-weight: 500; font-size: 12px; border: 1px solid #CBD5E1; border-radius: 6px; padding: 0 8px;")
        self.btn_browse_out.clicked.connect(self.action_browse_output_dir)
        h_out.addWidget(self.txt_output_dir)
        h_out.addWidget(self.btn_browse_out)
        layout_export.addLayout(h_out, 6, 1)
        right_col.addWidget(grp_export)

        config_grid.addLayout(right_col, 0, 1)
        tab_layout.addLayout(config_grid)

        # 5. CONTROL BAR & PROGRESS
        ctrl_layout = QHBoxLayout()
        self.btn_run = QPushButton("▶  Start")
        self.btn_run.setFixedHeight(36)
        self.btn_run.setStyleSheet("background-color: #16A34A; color: #FFFFFF; font-weight: bold; font-size: 13px; border-radius: 6px; padding: 0 22px; border: 1px solid #15803D;")
        self.btn_run.clicked.connect(self.action_start_dubbing)

        self.btn_stop = QPushButton("■  Stop")
        self.btn_stop.setFixedHeight(36)
        self.btn_stop.setEnabled(False)
        self.btn_stop.setStyleSheet("background-color: #DC2626; color: #FFFFFF; font-weight: bold; font-size: 13px; border-radius: 6px; padding: 0 18px; border: 1px solid #B91C1C;")
        self.btn_stop.clicked.connect(self.action_stop_dubbing)

        self.btn_open_folder = QPushButton("📁 Open Result Folder")
        self.btn_open_folder.setFixedHeight(36)
        self.btn_open_folder.setStyleSheet("background-color: #FFFFFF; color: #0F172A; font-weight: bold; font-size: 12px; border-radius: 6px; padding: 0 16px; border: 1px solid #CBD5E1;")
        self.btn_open_folder.clicked.connect(self.action_open_output_folder)

        self.lbl_stats = QLabel("Ready to process")
        self.lbl_stats.setStyleSheet("color: #475569; font-size: 12px; font-weight: 500;")

        ctrl_layout.addWidget(self.btn_run)
        ctrl_layout.addWidget(self.btn_stop)
        ctrl_layout.addWidget(self.btn_open_folder)
        ctrl_layout.addSpacing(16)
        ctrl_layout.addWidget(self.lbl_stats)
        ctrl_layout.addStretch()
        tab_layout.addLayout(ctrl_layout)

        # Smooth Green Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(12)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #DDD;
                border-radius: 6px;
                background-color: #EAEAEA;
            }
            QProgressBar::chunk {
                background-color: #27AE60;
                border-radius: 5px;
            }
        """)
        tab_layout.addWidget(self.progress_bar)

        # 6. TERMINAL CONSOLE LOG VIEWER
        self.txt_console = QTextEdit()
        self.txt_console.setReadOnly(True)
        self.txt_console.setFixedHeight(95)
        self.txt_console.setFont(QFont("Consolas", 10))
        self.txt_console.setStyleSheet("""
            QTextEdit {
                background-color: #111111;
                color: #00FF66;
                border: 1px solid #333333;
                border-radius: 6px;
                padding: 6px 10px;
            }
        """)
        self.append_log("=== AutoDub Studio Initialized ===")
        self.append_log(f"• LLM Model: {Config.LLM_MODEL} | Base URL: {Config.LLM_BASE_URL}")
        self.append_log(f"• Whisper: {Config.WHISPER_MODEL} ({Config.WHISPER_DEVICE})")
        self.append_log("• Ready! Paste TikTok links or add video files to begin.")
        tab_layout.addWidget(self.txt_console)

        # 7. MODEL MANAGER TAB (Scrollable for Multi-Provider AI Failover)
        scroll_models = QScrollArea(self.tab_models)
        scroll_models.setWidgetResizable(True)
        scroll_models.setFrameShape(QScrollArea.NoFrame)
        scroll_models.setStyleSheet("background-color: transparent;")

        models_container = QWidget()
        models_container.setStyleSheet("background-color: transparent;")
        layout_models = QVBoxLayout(models_container)
        layout_models.setContentsMargins(30, 20, 30, 30)
        layout_models.setSpacing(18)
        layout_models.setAlignment(Qt.AlignTop | Qt.AlignHCenter)

        tab_models_outer = QVBoxLayout(self.tab_models)
        tab_models_outer.setContentsMargins(0, 0, 0, 0)
        tab_models_outer.addWidget(scroll_models)
        scroll_models.setWidget(models_container)

        # Header description
        info_box = QWidget()
        info_box.setMaximumWidth(780)
        info_box_layout = QVBoxLayout(info_box)
        info_box_layout.setContentsMargins(0, 0, 0, 0)
        info_box_layout.setSpacing(4)

        info_title = QLabel("<b>Configure AI Translation Services (Multi-Model Failover)</b>")
        info_title.setStyleSheet("font-size: 16px; color: #0F172A;")
        info_box_layout.addWidget(info_title)

        info_desc = QLabel(
            "AutoDub Studio supports multiple AI model providers with <b>automatic failover</b>. "
            "If your Primary provider hits a rate limit (HTTP 429) or experiences an outage, "
            "the system instantly switches to your Fallback provider without interrupting video processing."
        )
        info_desc.setWordWrap(True)
        info_desc.setStyleSheet("font-size: 12px; color: #475569; line-height: 1.4;")
        info_box_layout.addWidget(info_desc)
        layout_models.addWidget(info_box)

        group_style = """
            QGroupBox {
                background-color: #FFFFFF;
                border: 1px solid #CBD5E1;
                border-radius: 8px;
                margin-top: 14px;
                padding-top: 20px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 20px;
                padding: 0 8px;
                color: #0F172A;
                font-weight: bold;
                font-size: 13px;
            }
        """

        # --- GROUP 1: PRIMARY PROVIDER ---
        grp_primary = QGroupBox("🥇 Primary AI Provider (Main)")
        grp_primary.setMaximumWidth(780)
        grp_primary.setStyleSheet(group_style)
        layout_primary = QVBoxLayout(grp_primary)
        layout_primary.setContentsMargins(24, 20, 24, 20)
        layout_primary.setSpacing(14)

        grid_primary = QGridLayout()
        grid_primary.setVerticalSpacing(12)
        grid_primary.setHorizontalSpacing(16)
        grid_primary.setColumnMinimumWidth(0, 130)

        grid_primary.addWidget(QLabel("Provider Preset:"), 0, 0)
        self.cbo_tab_preset = QComboBox()
        self.cbo_tab_preset.setFixedHeight(34)
        self.cbo_tab_preset.addItems(list(self.LLM_PRESETS.keys()))
        self.cbo_tab_preset.currentTextChanged.connect(self.on_tab_preset_changed)
        grid_primary.addWidget(self.cbo_tab_preset, 0, 1)

        grid_primary.addWidget(QLabel("Base URL:"), 1, 0)
        self.txt_tab_url = QLineEdit(Config.LLM_BASE_URL)
        self.txt_tab_url.setFixedHeight(34)
        self.txt_tab_url.setPlaceholderText("https://api.groq.com/openai/v1")
        grid_primary.addWidget(self.txt_tab_url, 1, 1)

        grid_primary.addWidget(QLabel("API Key:"), 2, 0)
        h_primary_key = QHBoxLayout()
        h_primary_key.setSpacing(6)
        self.txt_tab_key = QLineEdit(Config.LLM_API_KEY)
        self.txt_tab_key.setFixedHeight(34)
        self.txt_tab_key.setEchoMode(QLineEdit.Password)
        self.txt_tab_key.setPlaceholderText("sk-... or gsk_... or no-key-required")
        self.btn_toggle_tab_key = QPushButton("👁️")
        self.btn_toggle_tab_key.setFixedSize(38, 34)
        self.btn_toggle_tab_key.setToolTip("Show / Hide API Key")
        self.btn_toggle_tab_key.setStyleSheet("background-color: #F8FAFC; color: #0F172A; border: 1px solid #CBD5E1; border-radius: 6px;")
        self.btn_toggle_tab_key.clicked.connect(self.toggle_tab_key_visibility)
        h_primary_key.addWidget(self.txt_tab_key)
        h_primary_key.addWidget(self.btn_toggle_tab_key)
        grid_primary.addLayout(h_primary_key, 2, 1)

        grid_primary.addWidget(QLabel("Model Name:"), 3, 0)
        self.txt_tab_model = QLineEdit(Config.LLM_MODEL)
        self.txt_tab_model.setFixedHeight(34)
        self.txt_tab_model.setPlaceholderText("e.g. qwen/qwen3.8-27b, gpt-4o-mini")
        grid_primary.addWidget(self.txt_tab_model, 3, 1)

        layout_primary.addLayout(grid_primary)

        h_prim_btn = QHBoxLayout()
        self.lbl_tab_status = QLabel("")
        self.lbl_tab_status.setFixedHeight(24)
        self.lbl_tab_status.setStyleSheet("font-size: 12px; font-weight: 500;")
        self.btn_tab_test = QPushButton("🔌 Test Primary Connection")
        self.btn_tab_test.setFixedHeight(34)
        self.btn_tab_test.setStyleSheet("background-color: #F8FAFC; color: #0F172A; border: 1px solid #CBD5E1; border-radius: 6px; font-weight: 600; padding: 0 16px;")
        self.btn_tab_test.clicked.connect(self.action_test_tab_connection)
        h_prim_btn.addWidget(self.lbl_tab_status)
        h_prim_btn.addStretch()
        h_prim_btn.addWidget(self.btn_tab_test)
        layout_primary.addLayout(h_prim_btn)

        layout_models.addWidget(grp_primary)

        # --- GROUP 2: FALLBACK / BACKUP PROVIDER ---
        grp_backup = QGroupBox("🥈 Fallback AI Provider (Auto-Switch on Rate Limit)")
        grp_backup.setMaximumWidth(780)
        grp_backup.setStyleSheet(group_style)
        layout_backup = QVBoxLayout(grp_backup)
        layout_backup.setContentsMargins(24, 20, 24, 20)
        layout_backup.setSpacing(14)

        self.chk_backup_enable = QCheckBox("Enable Fallback Provider (Auto-switch on 429 Rate Limit / Outage)")
        self.chk_backup_enable.setStyleSheet("font-weight: bold; font-size: 13px; color: #1E293B;")
        self.chk_backup_enable.setChecked(getattr(Config, "LLM_BACKUP_ENABLED", False))
        layout_backup.addWidget(self.chk_backup_enable)

        grid_backup = QGridLayout()
        grid_backup.setVerticalSpacing(12)
        grid_backup.setHorizontalSpacing(16)
        grid_backup.setColumnMinimumWidth(0, 130)

        grid_backup.addWidget(QLabel("Provider Preset:"), 0, 0)
        self.cbo_backup_preset = QComboBox()
        self.cbo_backup_preset.setFixedHeight(34)
        self.cbo_backup_preset.addItems(list(self.LLM_PRESETS.keys()))
        grid_backup.addWidget(self.cbo_backup_preset, 0, 1)

        grid_backup.addWidget(QLabel("Base URL:"), 1, 0)
        default_backup_url = Config.LLM_BACKUP_BASE_URL or "https://generativelanguage.googleapis.com/v1beta/openai/"
        self.txt_backup_url = QLineEdit(default_backup_url)
        self.txt_backup_url.setFixedHeight(34)
        self.txt_backup_url.setPlaceholderText("https://generativelanguage.googleapis.com/v1beta/openai/")
        grid_backup.addWidget(self.txt_backup_url, 1, 1)

        grid_backup.addWidget(QLabel("API Key:"), 2, 0)
        h_backup_key = QHBoxLayout()
        h_backup_key.setSpacing(6)
        self.txt_backup_key = QLineEdit(Config.LLM_BACKUP_API_KEY)
        self.txt_backup_key.setFixedHeight(34)
        self.txt_backup_key.setEchoMode(QLineEdit.Password)
        self.txt_backup_key.setPlaceholderText("API key for fallback provider...")
        self.btn_toggle_backup_key = QPushButton("👁️")
        self.btn_toggle_backup_key.setFixedSize(38, 34)
        self.btn_toggle_backup_key.setToolTip("Show / Hide API Key")
        self.btn_toggle_backup_key.setStyleSheet("background-color: #F8FAFC; color: #0F172A; border: 1px solid #CBD5E1; border-radius: 6px;")
        self.btn_toggle_backup_key.clicked.connect(self.toggle_backup_key_visibility)
        h_backup_key.addWidget(self.txt_backup_key)
        h_backup_key.addWidget(self.btn_toggle_backup_key)
        grid_backup.addLayout(h_backup_key, 2, 1)

        grid_backup.addWidget(QLabel("Model Name:"), 3, 0)
        default_backup_model = Config.LLM_BACKUP_MODEL or "gemini-2.5-flash"
        self.txt_backup_model = QLineEdit(default_backup_model)
        self.txt_backup_model.setFixedHeight(34)
        self.txt_backup_model.setPlaceholderText("e.g. gemini-2.5-flash, deepseek-chat")
        grid_backup.addWidget(self.txt_backup_model, 3, 1)

        layout_backup.addLayout(grid_backup)

        h_back_btn = QHBoxLayout()
        self.lbl_backup_status = QLabel("")
        self.lbl_backup_status.setFixedHeight(24)
        self.lbl_backup_status.setStyleSheet("font-size: 12px; font-weight: 500;")
        self.btn_backup_test = QPushButton("🔌 Test Fallback Connection")
        self.btn_backup_test.setFixedHeight(34)
        self.btn_backup_test.setStyleSheet("background-color: #F8FAFC; color: #0F172A; border: 1px solid #CBD5E1; border-radius: 6px; font-weight: 600; padding: 0 16px;")
        self.btn_backup_test.clicked.connect(self.action_test_backup_connection)
        h_back_btn.addWidget(self.lbl_backup_status)
        h_back_btn.addStretch()
        h_back_btn.addWidget(self.btn_backup_test)
        layout_backup.addLayout(h_back_btn)

        layout_models.addWidget(grp_backup)

        # Connect preset change for backup
        self.cbo_backup_preset.currentTextChanged.connect(self.on_backup_preset_changed)

        # Set initial preset dropdown selection for backup
        if Config.LLM_BACKUP_BASE_URL:
            for p_name, p_data in self.LLM_PRESETS.items():
                if p_data["base_url"].rstrip("/") == Config.LLM_BACKUP_BASE_URL.rstrip("/"):
                    self.cbo_backup_preset.setCurrentText(p_name)
                    break
        else:
            self.cbo_backup_preset.setCurrentText("Google AI Studio (Gemini)")

        # Function to enable/disable backup fields based on checkbox
        def _toggle_backup_fields(enabled: bool):
            self.cbo_backup_preset.setEnabled(enabled)
            self.txt_backup_url.setEnabled(enabled)
            self.txt_backup_key.setEnabled(enabled)
            self.btn_toggle_backup_key.setEnabled(enabled)
            self.txt_backup_model.setEnabled(enabled)
            self.btn_backup_test.setEnabled(enabled)

        self.chk_backup_enable.toggled.connect(_toggle_backup_fields)
        _toggle_backup_fields(self.chk_backup_enable.isChecked())

        # Save Button bar at bottom
        save_box = QWidget()
        save_box.setMaximumWidth(780)
        h_save_bar = QHBoxLayout(save_box)
        h_save_bar.setContentsMargins(0, 6, 0, 0)
        self.lbl_global_save_status = QLabel("")
        self.lbl_global_save_status.setStyleSheet("font-size: 13px; font-weight: bold; color: #16A34A;")

        self.btn_tab_save = QPushButton("💾 Save All AI Settings")
        self.btn_tab_save.setFixedHeight(40)
        self.btn_tab_save.setStyleSheet("background-color: #2563EB; color: #FFFFFF; font-weight: bold; font-size: 13px; border-radius: 6px; padding: 0 32px;")
        self.btn_tab_save.clicked.connect(self.action_save_tab_llm_config)

        h_save_bar.addWidget(self.lbl_global_save_status)
        h_save_bar.addStretch()
        h_save_bar.addWidget(self.btn_tab_save)
        layout_models.addWidget(save_box)
        layout_models.addStretch()

    def apply_styles(self):
        """Apply high-contrast, polished stylesheet compatible with both Light and Dark Windows themes."""
        icon_up = (Config.BASE_DIR / "assets" / "icons" / "arrow_up.svg").resolve().as_posix()
        icon_down = (Config.BASE_DIR / "assets" / "icons" / "arrow_down.svg").resolve().as_posix()
        icon_chk_checked = (Config.BASE_DIR / "assets" / "icons" / "checkbox_checked.svg").resolve().as_posix()
        icon_chk_un = (Config.BASE_DIR / "assets" / "icons" / "checkbox_unchecked.svg").resolve().as_posix()

        self.setStyleSheet(f"""
            QMainWindow {{
                background-color: #F1F5F9;
            }}
            QWidget {{
                color: #0F172A;
                font-family: "Segoe UI", Arial, sans-serif;
            }}
            QTabWidget::pane {{
                border: 1px solid #CBD5E1;
                background-color: #F8FAFC;
                border-radius: 6px;
            }}
            QTabBar::tab {{
                background-color: #E2E8F0;
                color: #334155;
                font-weight: bold;
                padding: 8px 20px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                margin-right: 3px;
                border: 1px solid #CBD5E1;
                border-bottom: none;
            }}
            QTabBar::tab:selected {{
                background-color: #FFFFFF;
                color: #0F172A;
                border: 1px solid #CBD5E1;
                border-bottom: 1px solid #FFFFFF;
            }}
            QGroupBox {{
                font-weight: bold;
                font-size: 13px;
                border: 1px solid #CBD5E1;
                border-radius: 8px;
                margin-top: 8px;
                padding-top: 10px;
                padding-bottom: 6px;
                background-color: #FFFFFF;
                color: #0F172A;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 14px;
                padding: 0 6px;
                background-color: #FFFFFF;
                color: #0F172A;
            }}
            QLabel {{
                color: #1E293B;
                font-size: 12px;
            }}
            QCheckBox {{
                color: #1E293B;
                font-size: 12px;
                spacing: 8px;
            }}
            QCheckBox::indicator {{
                width: 16px;
                height: 16px;
                border: none;
                background-color: transparent;
            }}
            QCheckBox::indicator:unchecked {{
                image: url("{icon_chk_un}");
            }}
            QCheckBox::indicator:checked {{
                image: url("{icon_chk_checked}");
            }}
            QPushButton {{
                background-color: #FFFFFF;
                color: #0F172A;
                border: 1px solid #CBD5E1;
                border-radius: 6px;
                padding: 4px 12px;
                font-size: 12px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background-color: #F1F5F9;
                border-color: #64748B;
                color: #0F172A;
            }}
            QPushButton:pressed {{
                background-color: #E2E8F0;
            }}
            QPushButton:disabled {{
                background-color: #F8FAFC;
                color: #94A3B8;
                border-color: #E2E8F0;
            }}
            QLineEdit, QComboBox {{
                border: 1px solid #CBD5E1;
                border-radius: 6px;
                padding: 4px 10px;
                background-color: #FFFFFF;
                color: #0F172A;
                font-size: 12px;
            }}
            QLineEdit:focus, QComboBox:focus, QDoubleSpinBox:focus, QSpinBox:focus {{
                border: 1px solid #2563EB;
                background-color: #FFFFFF;
            }}
            QDoubleSpinBox, QSpinBox {{
                border: 1px solid #CBD5E1;
                border-radius: 6px;
                padding: 4px 24px 4px 10px;
                background-color: #FFFFFF;
                color: #0F172A;
                font-size: 12px;
            }}
            QDoubleSpinBox::up-button, QSpinBox::up-button {{
                subcontrol-origin: border;
                subcontrol-position: top right;
                width: 22px;
                height: 15px;
                border-left: 1px solid #CBD5E1;
                border-bottom: 1px solid #CBD5E1;
                border-top-right-radius: 5px;
                background-color: #F8FAFC;
            }}
            QDoubleSpinBox::up-button:hover, QSpinBox::up-button:hover {{
                background-color: #E2E8F0;
            }}
            QDoubleSpinBox::up-arrow, QSpinBox::up-arrow {{
                image: url("{icon_up}");
                width: 8px;
                height: 6px;
            }}
            QDoubleSpinBox::down-button, QSpinBox::down-button {{
                subcontrol-origin: border;
                subcontrol-position: bottom right;
                width: 22px;
                height: 15px;
                border-left: 1px solid #CBD5E1;
                border-bottom-right-radius: 5px;
                background-color: #F8FAFC;
            }}
            QDoubleSpinBox::down-button:hover, QSpinBox::down-button:hover {{
                background-color: #E2E8F0;
            }}
            QDoubleSpinBox::down-arrow, QSpinBox::down-arrow {{
                image: url("{icon_down}");
                width: 8px;
                height: 6px;
            }}
            QComboBox QAbstractItemView {{
                background-color: #FFFFFF;
                color: #0F172A;
                border: 1px solid #CBD5E1;
                selection-background-color: #E0F2FE;
                selection-color: #0F172A;
                padding: 4px;
            }}
            QTableWidget {{
                background-color: #FFFFFF;
                color: #0F172A;
                border: 1px solid #CBD5E1;
                border-radius: 6px;
                gridline-color: #E2E8F0;
                selection-background-color: #E0F2FE;
                selection-color: #0F172A;
            }}
            QHeaderView::section {{
                background-color: #F8FAFC;
                color: #334155;
                font-weight: bold;
                border: none;
                border-bottom: 1px solid #CBD5E1;
                border-right: 1px solid #E2E8F0;
                padding: 6px;
            }}
            QDialog, QMessageBox, QInputDialog, QFileDialog {{
                background-color: #FFFFFF;
                color: #0F172A;
            }}
            QMessageBox QLabel, QDialog QLabel {{
                color: #0F172A;
                font-size: 13px;
                font-weight: 500;
            }}
            QMessageBox QPushButton, QDialog QPushButton {{
                background-color: #0F172A;
                color: #FFFFFF;
                font-weight: bold;
                font-size: 12px;
                border-radius: 6px;
                padding: 6px 20px;
                min-width: 75px;
            }}
            QMessageBox QPushButton:hover, QDialog QPushButton:hover {{
                background-color: #334155;
            }}
        """)

    def append_log(self, text: str):
        """Append log message to terminal console viewer."""
        self.txt_console.append(text)
        scrollbar = self.txt_console.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    # --- ACTIONS / SLOTS ---

    def update_control_buttons(self):
        """Đồng bộ và phục hồi trạng thái các nút Start và Stop theo tiến trình."""
        is_running = self.worker is not None and self.worker.isRunning()
        self.btn_stop.setEnabled(is_running)
        self.btn_run.setEnabled(not is_running and self.table_queue.rowCount() > 0)

    @Slot()
    def action_paste_links(self):
        """Open dialog allowing user to paste multiple video links."""
        dlg = PasteLinksDialog(self)
        if dlg.exec() == QDialog.Accepted:
            links = dlg.get_links()
            if links:
                for link in links:
                    row = self.table_queue.rowCount()
                    self.table_queue.insertRow(row)
                    self.table_queue.setItem(row, 0, QTableWidgetItem(link))
                    self.table_queue.setItem(row, 1, QTableWidgetItem("-"))
                    item_status = QTableWidgetItem("Queued")
                    item_status.setForeground(QColor("#7F8C8D"))
                    self.table_queue.setItem(row, 2, item_status)
                self.lbl_stats.setText(f"{self.table_queue.rowCount()} video(s) in queue")
                self.update_control_buttons()

    @Slot()
    def action_add_files(self):
        """Open file dialog to add local video files."""
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Video Files",
            "",
            "Video Files (*.mp4 *.mkv *.mov *.avi *.flv)"
        )
        if files:
            for file_path in files:
                row = self.table_queue.rowCount()
                self.table_queue.insertRow(row)
                self.table_queue.setItem(row, 0, QTableWidgetItem(file_path))
                self.table_queue.setItem(row, 1, QTableWidgetItem("-"))
                item_status = QTableWidgetItem("Queued")
                item_status.setForeground(QColor("#7F8C8D"))
                self.table_queue.setItem(row, 2, item_status)
            self.lbl_stats.setText(f"{self.table_queue.rowCount()} video(s) in queue")
            self.update_control_buttons()

    @Slot()
    def action_remove_selected_rows(self):
        """Remove selected rows from queue table."""
        selected_rows = sorted(set(index.row() for index in self.table_queue.selectedIndexes()), reverse=True)
        for row in selected_rows:
            self.table_queue.removeRow(row)
        self.lbl_stats.setText(f"{self.table_queue.rowCount()} video(s) in queue")
        self.update_control_buttons()

    def update_cookie_button_state(self):
        """Cập nhật giao diện nút Cookies theo trạng thái tồn tại của tệp cookies.txt."""
        cookie_path = Config.BASE_DIR / "cookies.txt"
        if cookie_path.exists() and cookie_path.stat().st_size > 0:
            self.btn_cookies.setText("🍪 Cookies: Active ✓")
            self.btn_cookies.setToolTip(f"Active cookies loaded from:\n{cookie_path}\nClick to replace or remove.")
            self.btn_cookies.setStyleSheet(
                "QPushButton { background-color: #ECFDF5; color: #065F46; border: 1px solid #10B981; font-weight: bold; border-radius: 6px; padding: 4px 12px; }"
                "QPushButton:hover { background-color: #D1FAE5; border-color: #059669; }"
            )
        else:
            self.btn_cookies.setText("🍪 Cookies (.txt)")
            self.btn_cookies.setToolTip("Import cookies.txt for Douyin / TikTok download access.")
            self.btn_cookies.setStyleSheet("")

    @Slot()
    def action_manage_cookies(self):
        """Quản lý hoặc nạp tệp cookies.txt để vượt tường lửa Douyin và TikTok."""
        cookie_path = Config.BASE_DIR / "cookies.txt"

        if cookie_path.exists():
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle("Manage Cookies")
            msg_box.setIcon(QMessageBox.Information)
            msg_box.setText("<b>Active Cookies Detected</b>")
            msg_box.setInformativeText(
                f"Currently using cookies file:\n{cookie_path}\n\n"
                "You can import a new cookies file to replace it, or remove the existing cookies."
            )
            btn_replace = msg_box.addButton("Replace Cookies...", QMessageBox.AcceptRole)
            btn_remove = msg_box.addButton("Remove Cookies", QMessageBox.DestructiveRole)
            btn_cancel = msg_box.addButton("Cancel", QMessageBox.RejectRole)
            msg_box.setDefaultButton(btn_replace)
            msg_box.exec()

            clicked = msg_box.clickedButton()
            if clicked == btn_cancel:
                return
            elif clicked == btn_remove:
                try:
                    cookie_path.unlink(missing_ok=True)
                    self.update_cookie_button_state()
                    self.append_log("🗑️ Đã gỡ bỏ file cookies.txt.")
                    QMessageBox.information(self, "Cookies Removed", "cookies.txt has been removed successfully.")
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"Failed to delete cookies.txt: {e}")
                return

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select cookies.txt File",
            "",
            "Text Files (*.txt);;All Files (*.*)"
        )
        if file_path:
            try:
                shutil.copyfile(file_path, cookie_path)
                self.update_cookie_button_state()
                self.append_log(f"🍪 Đã nạp thành công cookies.txt từ: {file_path}")
                QMessageBox.information(
                    self,
                    "Cookies Loaded",
                    f"cookies.txt was successfully imported!\n\nLocation: {cookie_path}\n"
                    "Douyin & TikTok downloads will now use these session credentials."
                )
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to import cookies file: {e}")

    @Slot()
    def action_browse_output_dir(self):
        """Browse directory for exported videos."""
        directory = QFileDialog.getExistingDirectory(self, "Select Output Directory", self.txt_output_dir.text())
        if directory:
            self.txt_output_dir.setText(directory)

    @Slot()
    def action_change_model(self):
        """Switch directly to Model Manager tab."""
        self.tabs.setCurrentIndex(2)

    @Slot(str)
    def on_tab_preset_changed(self, preset_name: str):
        """Auto-populate fields when provider preset changes in Model Manager tab."""
        if preset_name == "Custom Settings":
            self.txt_tab_url.setText(Config.LLM_BASE_URL)
            self.txt_tab_key.setText(Config.LLM_API_KEY)
            self.txt_tab_model.setText(Config.LLM_MODEL)
            self.lbl_tab_status.setText("")
            return

        preset = self.LLM_PRESETS.get(preset_name)
        if preset:
            self.txt_tab_url.setText(preset["base_url"])
            if preset.get("api_key"):
                self.txt_tab_key.setText(preset["api_key"])
            elif Config.LLM_BASE_URL.rstrip("/") == preset["base_url"].rstrip("/"):
                self.txt_tab_key.setText(Config.LLM_API_KEY)
            else:
                self.txt_tab_key.setText("")
            self.txt_tab_model.setText(preset["model"])
            self.lbl_tab_status.setText("")

    @Slot(str)
    def on_backup_preset_changed(self, preset_name: str):
        """Auto-populate fields when backup provider preset changes."""
        if preset_name == "Custom Settings":
            self.lbl_backup_status.setText("")
            return

        preset = self.LLM_PRESETS.get(preset_name)
        if preset:
            self.txt_backup_url.setText(preset["base_url"])
            if preset.get("api_key"):
                self.txt_backup_key.setText(preset["api_key"])
            elif Config.LLM_BACKUP_BASE_URL and Config.LLM_BACKUP_BASE_URL.rstrip("/") == preset["base_url"].rstrip("/"):
                self.txt_backup_key.setText(Config.LLM_BACKUP_API_KEY)
            else:
                self.txt_backup_key.setText("")
            self.txt_backup_model.setText(preset["model"])
            self.lbl_backup_status.setText("")

    @Slot()
    def toggle_tab_key_visibility(self):
        """Toggle password masking for Primary API Key in Model Manager tab."""
        if self.txt_tab_key.echoMode() == QLineEdit.Password:
            self.txt_tab_key.setEchoMode(QLineEdit.Normal)
            self.btn_toggle_tab_key.setText("🔒")
        else:
            self.txt_tab_key.setEchoMode(QLineEdit.Password)
            self.btn_toggle_tab_key.setText("👁️")

    @Slot()
    def toggle_backup_key_visibility(self):
        """Toggle password masking for Fallback API Key."""
        if self.txt_backup_key.echoMode() == QLineEdit.Password:
            self.txt_backup_key.setEchoMode(QLineEdit.Normal)
            self.btn_toggle_backup_key.setText("🔒")
        else:
            self.txt_backup_key.setEchoMode(QLineEdit.Password)
            self.btn_toggle_backup_key.setText("👁️")

    @Slot()
    def action_test_tab_connection(self):
        """Test connection ping to the entered Primary LLM endpoint."""
        url = self.txt_tab_url.text().strip()
        key = self.txt_tab_key.text().strip()
        model = self.txt_tab_model.text().strip()
        self.lbl_tab_status.setStyleSheet("color: #2563EB; font-size: 12px; font-weight: 500;")
        self.lbl_tab_status.setText("⏳ Testing Primary connection, please wait...")
        QApplication.processEvents()

        ok, msg = test_llm_connection(url, key, model)
        if ok:
            self.lbl_tab_status.setStyleSheet("color: #16A34A; font-size: 12px; font-weight: bold;")
            self.lbl_tab_status.setText(msg)
        else:
            self.lbl_tab_status.setStyleSheet("color: #DC2626; font-size: 12px; font-weight: 500;")
            self.lbl_tab_status.setText(msg)

    @Slot()
    def action_test_backup_connection(self):
        """Test connection ping to the entered Fallback LLM endpoint."""
        url = self.txt_backup_url.text().strip()
        key = self.txt_backup_key.text().strip()
        model = self.txt_backup_model.text().strip()
        self.lbl_backup_status.setStyleSheet("color: #2563EB; font-size: 12px; font-weight: 500;")
        self.lbl_backup_status.setText("⏳ Testing Fallback connection, please wait...")
        QApplication.processEvents()

        ok, msg = test_llm_connection(url, key, model)
        if ok:
            self.lbl_backup_status.setStyleSheet("color: #16A34A; font-size: 12px; font-weight: bold;")
            self.lbl_backup_status.setText(msg)
        else:
            self.lbl_backup_status.setStyleSheet("color: #DC2626; font-size: 12px; font-weight: 500;")
            self.lbl_backup_status.setText(msg)

    @Slot()
    def action_save_tab_llm_config(self):
        """Validate, save Primary & Fallback LLM configuration to .env, and synchronize UI."""
        url = self.txt_tab_url.text().strip()
        key = self.txt_tab_key.text().strip()
        model = self.txt_tab_model.text().strip()

        if not url:
            QMessageBox.warning(self, "Invalid Input", "Primary Base URL cannot be empty!")
            return
        if not model:
            QMessageBox.warning(self, "Invalid Input", "Primary Model Name cannot be empty!")
            return

        backup_enabled = self.chk_backup_enable.isChecked()
        backup_url = self.txt_backup_url.text().strip()
        backup_key = self.txt_backup_key.text().strip()
        backup_model = self.txt_backup_model.text().strip()

        if backup_enabled:
            if not backup_url:
                QMessageBox.warning(self, "Invalid Input", "Fallback Base URL cannot be empty when Fallback is enabled!")
                return
            if not backup_model:
                QMessageBox.warning(self, "Invalid Input", "Fallback Model Name cannot be empty when Fallback is enabled!")
                return

        Config.save_llm_config(
            url, key, model,
            backup_enabled=backup_enabled,
            backup_base_url=backup_url,
            backup_api_key=backup_key,
            backup_model=backup_model
        )
        self.txt_model.setText(Config.LLM_MODEL)

        # Cập nhật bộ nhớ presets
        current_preset = self.cbo_tab_preset.currentText()
        if current_preset in self.LLM_PRESETS:
            self.LLM_PRESETS[current_preset]["base_url"] = url
            self.LLM_PRESETS[current_preset]["api_key"] = key
            self.LLM_PRESETS[current_preset]["model"] = model
        self.LLM_PRESETS["Custom Settings"]["base_url"] = url
        self.LLM_PRESETS["Custom Settings"]["api_key"] = key
        self.LLM_PRESETS["Custom Settings"]["model"] = model

        self.lbl_global_save_status.setText("✓ All AI configurations saved permanently to .env!")
        log_txt = f"• AI Config saved: Primary={Config.LLM_MODEL}"
        if Config.LLM_BACKUP_ENABLED:
            log_txt += f" | Fallback={Config.LLM_BACKUP_MODEL} (Auto-failover ON)"
        else:
            log_txt += " | Fallback=Disabled"
        self.append_log(log_txt)

        msg_body = f"AI model settings saved successfully!\n\n• Primary: {Config.LLM_MODEL}\n• Base URL: {Config.LLM_BASE_URL}"
        if Config.LLM_BACKUP_ENABLED:
            msg_body += f"\n\n• Fallback (Backup): {Config.LLM_BACKUP_MODEL}\n• Fallback URL: {Config.LLM_BACKUP_BASE_URL}\n• Auto-failover: Enabled ✓"
        else:
            msg_body += "\n\n• Fallback Provider: Disabled"

        QMessageBox.information(self, "Settings Saved", msg_body)

    @Slot()
    def action_open_output_folder(self):
        """Open the result output folder in Windows File Explorer."""
        folder = Path(self.txt_output_dir.text()).resolve()
        folder.mkdir(parents=True, exist_ok=True)
        if sys.platform == "win32":
            os.startfile(str(folder))
        else:
            subprocess.run(["xdg-open", str(folder)])

    def update_sub_color_swatches(self):
        """Update the background color and tooltip of the subtitle color preview buttons."""
        self.btn_sub_text_color.setStyleSheet(
            f"background-color: {self.sub_text_color}; border: 1px solid #94A3B8; border-radius: 4px;"
        )
        self.btn_sub_text_color.setToolTip(f"Text Color: {self.sub_text_color} (Click to change)")

        self.btn_sub_bg_color.setStyleSheet(
            f"background-color: {self.sub_bg_color}; border: 1px solid #94A3B8; border-radius: 4px;"
        )
        self.btn_sub_bg_color.setToolTip(f"Box / Background Color: {self.sub_bg_color} (Click to change)")

    @Slot(str)
    def on_sub_style_changed(self, style_name: str):
        """Apply preset styling for subtitles."""
        preset = self.SUB_STYLE_PRESETS.get(style_name)
        if preset:
            self.sub_border_style = preset["border_style"]
            self.sub_text_color = preset["text_color"]
            self.sub_bg_color = preset["bg_color"]
            self.sub_outline_width = preset["outline_width"]
            self.sub_shadow_width = preset["shadow_width"]
            self.update_sub_color_swatches()

    @Slot()
    def action_pick_sub_text_color(self):
        """Open color dialog to pick subtitle text color."""
        color = QColorDialog.getColor(QColor(self.sub_text_color), self, "Select Text Color")
        if color.isValid():
            self.sub_text_color = color.name().upper()
            self.cbo_sub_style.blockSignals(True)
            self.cbo_sub_style.setCurrentText("Custom...")
            self.cbo_sub_style.blockSignals(False)
            self.update_sub_color_swatches()

    @Slot()
    def action_pick_sub_bg_color(self):
        """Open color dialog to pick subtitle background box color."""
        color = QColorDialog.getColor(QColor(self.sub_bg_color), self, "Select Box Background Color")
        if color.isValid():
            self.sub_bg_color = color.name().upper()
            self.cbo_sub_style.blockSignals(True)
            self.cbo_sub_style.setCurrentText("Custom...")
            self.cbo_sub_style.blockSignals(False)
            self.update_sub_color_swatches()

    @Slot(str)
    def on_sub_pos_changed(self, pos_name: str):
        """Adjust margin_v spinbox based on position preset."""
        preset_margins = {
            "Bottom Standard (40px)": 40,
            "Cover Low Sub (120px)": 120,
            "Cover Mid Sub (220px)": 220,
            "Top Header (50px)": 50
        }
        if pos_name in preset_margins:
            self.spn_sub_margin_v.blockSignals(True)
            self.spn_sub_margin_v.setValue(preset_margins[pos_name])
            self.spn_sub_margin_v.blockSignals(False)

    @Slot(int)
    def on_sub_margin_spin_changed(self, val: int):
        """Switch preset dropdown to Custom if user manually edits the margin spinbox."""
        found = False
        preset_margins = {
            "Bottom Standard (40px)": 40,
            "Cover Low Sub (120px)": 120,
            "Cover Mid Sub (220px)": 220,
            "Top Header (50px)": 50
        }
        for name, m in preset_margins.items():
            if m == val:
                self.cbo_sub_pos.blockSignals(True)
                self.cbo_sub_pos.setCurrentText(name)
                self.cbo_sub_pos.blockSignals(False)
                found = True
                break
        if not found:
            self.cbo_sub_pos.blockSignals(True)
            self.cbo_sub_pos.setCurrentText("Custom...")
            self.cbo_sub_pos.blockSignals(False)

    def extract_sample_frame(self, video_path: Path) -> Optional[str]:
        """Trích xuất 1 khung hình mẫu nhanh (0.05s) bằng FFmpeg để hiển thị trong live preview."""
        return extract_video_frame_at(video_path, timestamp_sec=1.0)

    @Slot()
    def action_open_subtitle_preview_dialog(self):
        """Open modal dialog to preview and align subtitle overlay to cover original hardsubs."""
        # 1. Thu thập tất cả các video hiện có trong hàng đợi
        video_paths = []
        for r in range(self.table_queue.rowCount()):
            item = self.table_queue.item(r, 0)
            if item:
                val = item.text().strip()
                if val and Path(val).is_file():
                    video_paths.append(val)

        # 2. Thu thập cấu hình subtitle hiện tại từ MainWindow
        current_sub_settings = {
            "position": self.cbo_sub_pos.currentText(),
            "margin_v": self.spn_sub_margin_v.value(),
            "alignment": 8 if "Top" in self.cbo_sub_pos.currentText() else 2,
            "box_padding": self.spn_box_padding.value(),
            "font_size": self.spn_font_size.value(),
            "font_name": self.cbo_font.currentText(),
            "sub_style": self.cbo_sub_style.currentText(),
            "border_style": getattr(self, "sub_border_style", 3),
            "text_color": getattr(self, "sub_text_color", "#FFE600"),
            "bg_color": getattr(self, "sub_bg_color", "#000000"),
        }

        # 3. Khởi tạo và hiển thị Dialog
        dialog = SubtitlePreviewDialog(self, video_paths=video_paths, current_settings=current_sub_settings)
        if dialog.exec():
            # Đồng bộ các giá trị đã tinh chỉnh từ Preview ngược về MainWindow
            res = dialog.result_settings

            # Margin V
            if "margin_v" in res:
                self.spn_sub_margin_v.setValue(int(res["margin_v"]))

            # Preset Vị trí
            if "position" in res:
                self.cbo_sub_pos.blockSignals(True)
                idx = self.cbo_sub_pos.findText(res["position"])
                if idx >= 0:
                    self.cbo_sub_pos.setCurrentIndex(idx)
                else:
                    self.cbo_sub_pos.setCurrentText("Custom...")
                self.cbo_sub_pos.blockSignals(False)

            # Box padding
            if "box_padding" in res:
                self.spn_box_padding.setValue(int(res["box_padding"]))

            # Font & Font size
            if "font_size" in res:
                self.spn_font_size.setValue(int(res["font_size"]))
            if "font_name" in res:
                idx = self.cbo_font.findText(res["font_name"])
                if idx >= 0:
                    self.cbo_font.setCurrentIndex(idx)

            # Style preset and colors
            if "sub_style" in res:
                idx = self.cbo_sub_style.findText(res["sub_style"])
                if idx >= 0:
                    self.cbo_sub_style.setCurrentIndex(idx)
                else:
                    self.cbo_sub_style.setCurrentText("Custom...")

            if "border_style" in res:
                self.sub_border_style = int(res["border_style"])
            if "text_color" in res:
                self.sub_text_color = res["text_color"]
            if "bg_color" in res:
                self.sub_bg_color = res["bg_color"]

            self.update_sub_color_swatches()
            self.append_log(
                f"🎯 Đã cập nhật cấu hình phụ đề từ Preview: Margin V={self.spn_sub_margin_v.value()}px, "
                f"Box Pad={self.spn_box_padding.value()}px, Font={self.cbo_font.currentText()} ({self.spn_font_size.value()}pt)"
            )

    @Slot()
    def action_open_watermark_dialog(self):
        """Open modal dialog to configure text and logo watermarks with real-time live preview."""
        sample_frame = None
        if self.table_queue.rowCount() > 0:
            first_src = self.table_queue.item(0, 0).text() if self.table_queue.item(0, 0) else ""
            if first_src and Path(first_src).is_file():
                sample_frame = self.extract_sample_frame(Path(first_src))

        dialog = WatermarkConfigDialog(self, self.watermark_config, sample_frame_path=sample_frame)
        if dialog.exec():
            self.watermark_config = dialog.config
            self.update_watermark_summary()

    def update_watermark_summary(self):
        """Update summary label next to Watermark Settings button."""
        parts = []
        if self.watermark_config.get("text_enabled", False):
            parts.append("Text: On")
        else:
            parts.append("Text: Off")

        if self.watermark_config.get("logo_enabled", False) and self.watermark_config.get("logo_path"):
            fname = Path(self.watermark_config["logo_path"]).name
            if len(fname) > 14:
                fname = fname[:11] + "..."
            parts.append(f"Logo: {fname}")
        else:
            parts.append("Logo: Off")

        summary = f"({', '.join(parts)})"
        self.lbl_watermark_summary.setText(summary)

    @Slot()
    def action_start_dubbing(self):
        """Start batch processing via DubbingWorker thread."""
        count = self.table_queue.rowCount()
        if count == 0:
            QMessageBox.warning(self, "Notice", "Queue is empty! Please add video files or paste video links first.")
            return

        # Lọc các video cần xử lý: ưu tiên các video chưa xong (Queued hoặc Failed)
        pending_rows = []
        for row in range(count):
            status_item = self.table_queue.item(row, 2)
            status_text = status_item.text() if status_item else ""
            if not status_text.startswith("✓ Done"):
                pending_rows.append(row)

        target_rows = pending_rows if pending_rows else list(range(count))

        tasks = []
        for row in target_rows:
            source = self.table_queue.item(row, 0).text().strip()
            tasks.append({"row": row, "source": source})

        selected_lang_text = self.cbo_lang.currentText().lower()
        if "zh" in selected_lang_text:
            source_lang = "zh"
        elif "en" in selected_lang_text:
            source_lang = "en"
        else:
            source_lang = "auto"

        voice_key = self.cbo_voice.currentData()
        subtitle_options = {
            "font_name": self.cbo_font.currentText(),
            "font_size": self.spn_font_size.value(),
            "primary_color": self.sub_text_color,
            "outline_color": self.sub_bg_color if self.sub_border_style == 3 else "#000000",
            "back_color": self.sub_bg_color,
            "border_style": self.sub_border_style,
            "outline_width": self.sub_outline_width,
            "shadow_width": self.sub_shadow_width,
            "margin_v": self.spn_sub_margin_v.value(),
            "alignment": 8 if "top" in self.cbo_sub_pos.currentText().lower() else 2,
            "box_padding": self.spn_box_padding.value()
        }

        watermark_options = {}
        if self.chk_watermark.isChecked():
            watermark_options = dict(self.watermark_config)

        encoder_key = self.cbo_encoder.currentData() or "libx264"
        options = {
            "source_lang": source_lang,
            "voice": voice_key,
            "ducking_volume": self.spn_ducking.value(),
            "burn_subtitles": self.chk_burn_sub.isChecked(),
            "genre": self.cbo_genre.currentText(),
            "custom_terms": self.txt_custom_terms.text().strip(),
            "subtitle_options": subtitle_options,
            "watermark_options": watermark_options,
            "encoder": encoder_key,
            "output_dir": Path(self.txt_output_dir.text()).resolve()
        }

        self.btn_run.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.progress_bar.setValue(0)
        self.lbl_stats.setText(f"Processing 0/{len(tasks)} video(s)...")

        # Launch Worker Thread
        self.worker = DubbingWorker(tasks, options)
        self.worker.sig_log.connect(self.append_log)
        self.worker.sig_progress.connect(self.update_progress)
        self.worker.sig_item_status.connect(self.update_item_status)
        self.worker.sig_finished.connect(self.on_worker_finished)
        self.worker.finished.connect(self.on_worker_thread_terminated)
        self.worker.start()

    @Slot()
    def action_stop_dubbing(self):
        """Request worker thread to stop."""
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.btn_stop.setEnabled(False)
            self.lbl_stats.setText("Cancelling process...")
            self.append_log("⏹ Stopping pipeline immediately on user request...")
        else:
            self.update_control_buttons()

    @Slot(float)
    def update_progress(self, percent: float):
        self.progress_bar.setValue(int(percent))

    @Slot(int, str, str)
    def update_item_status(self, row: int, status: str, hex_color: str):
        item = QTableWidgetItem(status)
        item.setForeground(QColor(hex_color))
        self.table_queue.setItem(row, 2, item)

    @Slot()
    def on_worker_thread_terminated(self):
        """Dự phòng an toàn: đảm bảo nút Start/Stop được phục hồi khi luồng worker kết thúc."""
        self.update_control_buttons()

    @Slot(int, int)
    def on_worker_finished(self, success_count: int, total_count: int):
        self.update_control_buttons()
        self.lbl_stats.setText(f"Completed: {success_count}/{total_count} video(s)")

        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Finished")
        if success_count == total_count and total_count > 0:
            msg_box.setIcon(QMessageBox.Information)
            msg_box.setText(f"Batch processing completed successfully!\nAll {success_count}/{total_count} video(s) dubbed and exported.")
        elif success_count > 0:
            msg_box.setIcon(QMessageBox.Warning)
            msg_box.setText(f"Batch processing finished with partial results.\nSuccessful: {success_count}/{total_count} video(s).")
        else:
            msg_box.setIcon(QMessageBox.Critical)
            msg_box.setText(f"Batch processing completed.\nSuccessful: {success_count}/{total_count} video(s).\nPlease check the terminal log below for details.")
        
        msg_box.setStyleSheet("background-color: #FFFFFF; color: #0F172A; font-size: 13px;")
        msg_box.exec()


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    # Áp dụng stylesheet trực tiếp lên toàn bộ QApplication để mọi dialog, alert đều sắc nét
    app.setStyleSheet(window.styleSheet())
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
