"""
AutoDub Studio - WatermarkConfigDialog.
Modal dialog for configuring Text & Logo Watermarks with live video frame preview.
"""

from pathlib import Path
from typing import Optional, Dict, Any
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QComboBox, QSlider, QCheckBox, QPushButton,
    QGroupBox, QTabWidget, QFileDialog
)

from ui.components.spinbox import RobustSpinBox
from ui.components.watermark_canvas import WatermarkPreviewCanvas
from ui.styles import get_watermark_dialog_stylesheet


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
        self.setStyleSheet(get_watermark_dialog_stylesheet())

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
