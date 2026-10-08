"""
AutoDub Studio - Native Windows Desktop Application (PySide6 / Qt).
Designed for Go-Global distribution with an English UI, batch queue processing,
dual-column settings, smooth progress bar, and real-time terminal console log.
"""

import sys
import os
import shutil
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional

# Configure UTF-8 encoding on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

from PySide6.QtCore import Qt, QThread, Signal, Slot
from PySide6.QtGui import QFont, QColor, QPixmap
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QTabWidget, QTableWidget, QTableWidgetItem, QHeaderView,
    QPushButton, QComboBox, QDoubleSpinBox, QSpinBox, QLineEdit, QCheckBox,
    QLabel, QProgressBar, QTextEdit, QFileDialog, QInputDialog, QMessageBox,
    QGroupBox, QColorDialog, QDialog, QSlider
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
                        progress_callback=progress_hook
                    )
                    success_count += 1
                    self.sig_item_status.emit(row, f"✓ Done - {final_video.name}", "#27AE60")
                    self.sig_log.emit(f"✓ COMPLETED: {final_video.name}")

                except Exception as e:
                    self.sig_item_status.emit(row, f"❌ Failed: {str(e)[:30]}", "#E74C3C")
                    self.sig_log.emit(f"❌ ERROR PROCESSING: {str(e)}")

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


class WatermarkConfigDialog(QDialog):
    """
    Modal dialog allowing users to configure Text Watermark and Logo Image Watermark
    with live thumbnail preview and opacity slider.
    """
    def __init__(self, parent=None, config: Optional[Dict[str, Any]] = None):
        super().__init__(parent)
        self.setWindowTitle("🎨 Watermark & Branding Settings")
        self.setFixedSize(540, 500)
        self.setModal(True)
        self.config = dict(config or {})

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
        """)

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 16, 20, 16)
        main_layout.setSpacing(14)

        header_lbl = QLabel("<b>Watermark & Branding Settings</b>")
        header_lbl.setStyleSheet("font-size: 15px; color: #0F172A;")
        main_layout.addWidget(header_lbl)

        sub_desc = QLabel("Configure promotional text banner and channel logo to protect and brand your videos.")
        sub_desc.setStyleSheet("font-size: 11px; color: #64748B; margin-bottom: 4px;")
        sub_desc.setWordWrap(True)
        main_layout.addWidget(sub_desc)

        self.tab_widget = QTabWidget()

        # TAB 1: TEXT WATERMARK
        tab_text = QWidget()
        layout_text = QVBoxLayout(tab_text)
        layout_text.setSpacing(12)

        self.chk_text_enable = QCheckBox("Enable Text Watermark")
        self.chk_text_enable.setStyleSheet("font-weight: bold; font-size: 13px; color: #1E293B;")
        layout_text.addWidget(self.chk_text_enable)

        grid_text = QGridLayout()
        grid_text.setVerticalSpacing(10)
        grid_text.setHorizontalSpacing(12)

        grid_text.addWidget(QLabel("Watermark Text:"), 0, 0)
        self.txt_text_content = QLineEdit()
        self.txt_text_content.setFixedHeight(32)
        self.txt_text_content.setPlaceholderText("e.g. Bạn đang xem video được sub bởi Vũ Mạnh Cường")
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
        grid_text.addWidget(self.cbo_text_pos, 2, 1)

        grid_text.addWidget(QLabel("Font Size:"), 3, 0)
        self.spn_text_font_size = QSpinBox()
        self.spn_text_font_size.setFixedHeight(32)
        self.spn_text_font_size.setRange(14, 48)
        self.spn_text_font_size.setValue(22)
        grid_text.addWidget(self.spn_text_font_size, 3, 1)

        layout_text.addLayout(grid_text)

        tip_lbl = QLabel("💡 <i>Text watermark is rendered with a sleek semi-transparent badge for optimal readability on all video backgrounds.</i>")
        tip_lbl.setStyleSheet("font-size: 11px; color: #64748B; margin-top: 6px;")
        tip_lbl.setWordWrap(True)
        layout_text.addWidget(tip_lbl)
        layout_text.addStretch()

        self.tab_widget.addTab(tab_text, "✍️ Text Watermark")

        # TAB 2: LOGO IMAGE WATERMARK
        tab_logo = QWidget()
        layout_logo = QVBoxLayout(tab_logo)
        layout_logo.setSpacing(12)

        self.chk_logo_enable = QCheckBox("Enable Logo Watermark")
        self.chk_logo_enable.setStyleSheet("font-weight: bold; font-size: 13px; color: #1E293B;")
        layout_logo.addWidget(self.chk_logo_enable)

        grid_logo = QGridLayout()
        grid_logo.setVerticalSpacing(10)
        grid_logo.setHorizontalSpacing(12)

        grid_logo.addWidget(QLabel("Logo Image:"), 0, 0)
        h_file = QHBoxLayout()
        h_file.setSpacing(6)
        self.txt_logo_path = QLineEdit()
        self.txt_logo_path.setFixedHeight(32)
        self.txt_logo_path.setPlaceholderText("Select PNG / JPG image...")
        self.txt_logo_path.textChanged.connect(self.update_logo_preview)

        self.btn_browse_logo = QPushButton("Browse...")
        self.btn_browse_logo.setFixedHeight(32)
        self.btn_browse_logo.setFixedWidth(80)
        self.btn_browse_logo.setStyleSheet("background-color: #F8FAFC; border: 1px solid #CBD5E1; border-radius: 6px; font-weight: 500;")
        self.btn_browse_logo.clicked.connect(self.action_browse_logo)
        h_file.addWidget(self.txt_logo_path)
        h_file.addWidget(self.btn_browse_logo)
        grid_logo.addLayout(h_file, 0, 1)

        grid_logo.addWidget(QLabel("Preview:"), 1, 0)
        self.lbl_logo_preview = QLabel("No image selected")
        self.lbl_logo_preview.setFixedHeight(54)
        self.lbl_logo_preview.setAlignment(Qt.AlignCenter)
        self.lbl_logo_preview.setStyleSheet("border: 1px dashed #CBD5E1; border-radius: 6px; background-color: #F8FAFC; color: #94A3B8; font-size: 11px;")
        grid_logo.addWidget(self.lbl_logo_preview, 1, 1)

        grid_logo.addWidget(QLabel("Position:"), 2, 0)
        self.cbo_logo_pos = QComboBox()
        self.cbo_logo_pos.setFixedHeight(32)
        self.cbo_logo_pos.addItem("Top-Right (Standard for short video)", "top-right")
        self.cbo_logo_pos.addItem("Top-Left", "top-left")
        self.cbo_logo_pos.addItem("Bottom-Right", "bottom-right")
        self.cbo_logo_pos.addItem("Bottom-Left", "bottom-left")
        self.cbo_logo_pos.addItem("Center", "center")
        grid_logo.addWidget(self.cbo_logo_pos, 2, 1)

        grid_logo.addWidget(QLabel("Opacity:"), 3, 0)
        h_op = QHBoxLayout()
        h_op.setSpacing(10)
        self.slider_opacity = QSlider(Qt.Horizontal)
        self.slider_opacity.setRange(10, 100)
        self.slider_opacity.setValue(80)
        self.lbl_op_val = QLabel("80%")
        self.lbl_op_val.setFixedWidth(38)
        self.lbl_op_val.setStyleSheet("font-weight: bold; color: #2563EB;")
        self.slider_opacity.valueChanged.connect(lambda v: self.lbl_op_val.setText(f"{v}%"))
        h_op.addWidget(self.slider_opacity)
        h_op.addWidget(self.lbl_op_val)
        grid_logo.addLayout(h_op, 3, 1)

        grid_logo.addWidget(QLabel("Max Width:"), 4, 0)
        self.spn_logo_max_width = QSpinBox()
        self.spn_logo_max_width.setFixedHeight(32)
        self.spn_logo_max_width.setRange(60, 400)
        self.spn_logo_max_width.setValue(160)
        self.spn_logo_max_width.setSuffix(" px")
        grid_logo.addWidget(self.spn_logo_max_width, 4, 1)

        layout_logo.addLayout(grid_logo)
        layout_logo.addStretch()

        self.tab_widget.addTab(tab_logo, "🖼️ Logo Image")
        main_layout.addWidget(self.tab_widget)

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
        main_layout.addLayout(btn_box)

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
        self.update_logo_preview(logo_path)
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

    def update_logo_preview(self, path_str: str):
        path = Path(path_str.strip())
        if path.is_file():
            pix = QPixmap(str(path))
            if not pix.isNull():
                scaled = pix.scaled(160, 48, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.lbl_logo_preview.setPixmap(scaled)
                self.lbl_logo_preview.setText("")
                return
        self.lbl_logo_preview.setPixmap(QPixmap())
        self.lbl_logo_preview.setText("No valid image selected")

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

    def action_save(self):
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
            "Groq Cloud (https://api.groq.com/openai/v1)": {
                "base_url": "https://api.groq.com/openai/v1",
                "api_key": "",
                "model": "llama-3.3-70b-versatile"
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

        # 7. MODEL MANAGER TAB
        layout_models = QVBoxLayout(self.tab_models)
        layout_models.setContentsMargins(40, 30, 40, 30)
        layout_models.setSpacing(16)
        layout_models.setAlignment(Qt.AlignTop | Qt.AlignHCenter)

        grp_model_cfg = QGroupBox("⚙️ LLM && AI Service Settings")
        grp_model_cfg.setMaximumWidth(760)
        grp_model_cfg.setStyleSheet("""
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
        """)
        layout_cfg = QVBoxLayout(grp_model_cfg)
        layout_cfg.setContentsMargins(28, 22, 28, 22)
        layout_cfg.setSpacing(16)

        info_title = QLabel("<b>Configure AI Translation Services</b>")
        info_title.setStyleSheet("font-size: 15px; color: #0F172A;")
        layout_cfg.addWidget(info_title)

        info_desc = QLabel(
            "AutoDub Studio supports any OpenAI-compatible LLM endpoint (Ollama local, VNPT-SI, Groq, DeepSeek, OpenAI).<br>"
            "Select a preset or customize parameters. Settings are saved permanently to your <code>.env</code> file."
        )
        info_desc.setWordWrap(True)
        info_desc.setStyleSheet("font-size: 12px; color: #475569; line-height: 1.4;")
        layout_cfg.addWidget(info_desc)

        # Form Grid
        form_grid = QGridLayout()
        form_grid.setVerticalSpacing(14)
        form_grid.setHorizontalSpacing(16)
        form_grid.setColumnStretch(0, 0)
        form_grid.setColumnStretch(1, 1)
        form_grid.setColumnMinimumWidth(0, 130)

        # Row 0: Provider Preset
        lbl_preset = QLabel("Provider Preset:")
        lbl_preset.setStyleSheet("font-weight: 500; font-size: 12px;")
        form_grid.addWidget(lbl_preset, 0, 0)
        self.cbo_tab_preset = QComboBox()
        self.cbo_tab_preset.setFixedHeight(34)
        self.cbo_tab_preset.addItems(list(self.LLM_PRESETS.keys()))
        self.cbo_tab_preset.currentTextChanged.connect(self.on_tab_preset_changed)
        form_grid.addWidget(self.cbo_tab_preset, 0, 1)

        # Row 1: Base URL
        lbl_url = QLabel("Base URL:")
        lbl_url.setStyleSheet("font-weight: 500; font-size: 12px;")
        form_grid.addWidget(lbl_url, 1, 0)
        self.txt_tab_url = QLineEdit(Config.LLM_BASE_URL)
        self.txt_tab_url.setFixedHeight(34)
        self.txt_tab_url.setPlaceholderText("https://api.openai.com/v1")
        form_grid.addWidget(self.txt_tab_url, 1, 1)

        # Row 2: API Key with Show/Hide toggle
        lbl_key = QLabel("API Key:")
        lbl_key.setStyleSheet("font-weight: 500; font-size: 12px;")
        form_grid.addWidget(lbl_key, 2, 0)
        h_tab_key = QHBoxLayout()
        h_tab_key.setSpacing(6)
        self.txt_tab_key = QLineEdit(Config.LLM_API_KEY)
        self.txt_tab_key.setFixedHeight(34)
        self.txt_tab_key.setEchoMode(QLineEdit.Password)
        self.txt_tab_key.setPlaceholderText("sk-... or no-key-required")
        self.btn_toggle_tab_key = QPushButton("👁️")
        self.btn_toggle_tab_key.setFixedSize(38, 34)
        self.btn_toggle_tab_key.setToolTip("Show / Hide API Key")
        self.btn_toggle_tab_key.setStyleSheet("background-color: #F8FAFC; color: #0F172A; border: 1px solid #CBD5E1; border-radius: 6px;")
        self.btn_toggle_tab_key.clicked.connect(self.toggle_tab_key_visibility)
        h_tab_key.addWidget(self.txt_tab_key)
        h_tab_key.addWidget(self.btn_toggle_tab_key)
        form_grid.addLayout(h_tab_key, 2, 1)

        # Row 3: Model Name
        lbl_model = QLabel("Model Name:")
        lbl_model.setStyleSheet("font-weight: 500; font-size: 12px;")
        form_grid.addWidget(lbl_model, 3, 0)
        self.txt_tab_model = QLineEdit(Config.LLM_MODEL)
        self.txt_tab_model.setFixedHeight(34)
        self.txt_tab_model.setPlaceholderText("e.g. gpt-4o-mini, gemma-4-26B-A4B-it")
        form_grid.addWidget(self.txt_tab_model, 3, 1)

        layout_cfg.addLayout(form_grid)

        # Status feedback label
        self.lbl_tab_status = QLabel("")
        self.lbl_tab_status.setFixedHeight(24)
        self.lbl_tab_status.setStyleSheet("font-size: 12px; font-weight: 500;")
        self.lbl_tab_status.setWordWrap(True)
        layout_cfg.addWidget(self.lbl_tab_status)

        # Buttons bar
        btn_bar = QHBoxLayout()
        btn_bar.setSpacing(12)

        self.btn_tab_test = QPushButton("🔌 Test Connection")
        self.btn_tab_test.setFixedHeight(36)
        self.btn_tab_test.setStyleSheet("background-color: #FFFFFF; color: #0F172A; border: 1px solid #CBD5E1; border-radius: 6px; font-weight: 600; padding: 0 18px;")
        self.btn_tab_test.clicked.connect(self.action_test_tab_connection)

        self.btn_tab_save = QPushButton("💾 Save Settings")
        self.btn_tab_save.setFixedHeight(36)
        self.btn_tab_save.setStyleSheet("background-color: #2563EB; color: #FFFFFF; font-weight: bold; border-radius: 6px; padding: 0 24px;")
        self.btn_tab_save.clicked.connect(self.action_save_tab_llm_config)

        btn_bar.addWidget(self.btn_tab_test)
        btn_bar.addStretch()
        btn_bar.addWidget(self.btn_tab_save)
        layout_cfg.addLayout(btn_bar)

        layout_models.addWidget(grp_model_cfg)
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
        preset = self.LLM_PRESETS.get(preset_name)
        if preset:
            self.txt_tab_url.setText(preset["base_url"])
            if preset["api_key"]:
                self.txt_tab_key.setText(preset["api_key"])
            self.txt_tab_model.setText(preset["model"])
            self.lbl_tab_status.setText("")

    @Slot()
    def toggle_tab_key_visibility(self):
        """Toggle password masking for API Key in Model Manager tab."""
        if self.txt_tab_key.echoMode() == QLineEdit.Password:
            self.txt_tab_key.setEchoMode(QLineEdit.Normal)
            self.btn_toggle_tab_key.setText("🔒")
        else:
            self.txt_tab_key.setEchoMode(QLineEdit.Password)
            self.btn_toggle_tab_key.setText("👁️")

    @Slot()
    def action_test_tab_connection(self):
        """Test connection ping to the entered LLM endpoint."""
        url = self.txt_tab_url.text().strip()
        key = self.txt_tab_key.text().strip()
        model = self.txt_tab_model.text().strip()
        self.lbl_tab_status.setStyleSheet("color: #2563EB; font-size: 12px; font-weight: 500;")
        self.lbl_tab_status.setText("⏳ Testing connection, please wait...")
        QApplication.processEvents()

        ok, msg = test_llm_connection(url, key, model)
        if ok:
            self.lbl_tab_status.setStyleSheet("color: #16A34A; font-size: 12px; font-weight: bold;")
            self.lbl_tab_status.setText(msg)
        else:
            self.lbl_tab_status.setStyleSheet("color: #DC2626; font-size: 12px; font-weight: 500;")
            self.lbl_tab_status.setText(msg)

    @Slot()
    def action_save_tab_llm_config(self):
        """Validate, save LLM configuration to .env, and synchronize UI."""
        url = self.txt_tab_url.text().strip()
        key = self.txt_tab_key.text().strip()
        model = self.txt_tab_model.text().strip()

        if not url:
            QMessageBox.warning(self, "Invalid Input", "Base URL cannot be empty!")
            return
        if not model:
            QMessageBox.warning(self, "Invalid Input", "Model Name cannot be empty!")
            return

        Config.save_llm_config(url, key, model)
        self.txt_model.setText(Config.LLM_MODEL)
        self.lbl_tab_status.setStyleSheet("color: #16A34A; font-size: 12px; font-weight: bold;")
        self.lbl_tab_status.setText("✓ Configuration saved permanently to .env!")
        self.append_log(f"• LLM Configuration updated: Model={Config.LLM_MODEL} | Base URL={Config.LLM_BASE_URL}")

        QMessageBox.information(
            self,
            "Settings Saved",
            f"LLM settings saved successfully!\n\n• Model: {Config.LLM_MODEL}\n• Base URL: {Config.LLM_BASE_URL}"
        )

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

    @Slot()
    def action_open_watermark_dialog(self):
        """Open modal dialog to configure text and logo watermarks."""
        dialog = WatermarkConfigDialog(self, self.watermark_config)
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
