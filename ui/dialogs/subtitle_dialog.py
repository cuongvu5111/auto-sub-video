"""
AutoDub Studio - SubtitlePreviewDialog.
Modal dialog for subtitle font sizing, hardsub cover box positioning, and interactive live preview.
"""

from pathlib import Path
from typing import Optional, List, Dict, Any
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QComboBox, QSlider, QSpinBox, QCheckBox,
    QPushButton, QGroupBox, QFileDialog, QColorDialog
)

from ui.components.subtitle_canvas import SubtitlePreviewCanvas
from ui.video_utils import extract_video_frame_at, get_video_meta
from ui.styles import get_subtitle_dialog_stylesheet


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
        self.output_profile_name = str(self.settings.get("export_profile_name", "original"))
        self.export_fit_mode = str(self.settings.get("export_fit_mode", "crop"))

        self.border_style = int(self.settings.get("border_style", 3))
        self.text_color = str(self.settings.get("text_color", "#FFE600"))
        self.bg_color = str(self.settings.get("bg_color", "#000000"))

        self.init_ui()
        self.load_initial_video_and_settings()
        self.apply_dialog_styles()

    def apply_dialog_styles(self):
        self.setStyleSheet(get_subtitle_dialog_stylesheet())

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

        style_layout.addWidget(QLabel("Font:"), 2, 0)
        self.cbo_font_name = QComboBox()
        self.cbo_font_name.setFixedHeight(30)
        self.cbo_font_name.addItems(["Arial", "DejaVu Sans Bold", "Montserrat", "Segoe UI"])
        self.cbo_font_name.currentTextChanged.connect(self.refresh_canvas)
        style_layout.addWidget(self.cbo_font_name, 2, 1)

        style_layout.addWidget(QLabel("Font Size:"), 3, 0)
        h_font_sz = QHBoxLayout()
        self.slider_font_sz = QSlider(Qt.Horizontal)
        self.slider_font_sz.setRange(16, 96)
        self.slider_font_sz.setValue(46)
        self.slider_font_sz.valueChanged.connect(self.on_font_slider_changed)
        h_font_sz.addWidget(self.slider_font_sz, stretch=1)

        self.spn_font_sz = QSpinBox()
        self.spn_font_sz.setRange(14, 120)
        self.spn_font_sz.setValue(46)
        self.spn_font_sz.setSuffix(" pt")
        self.spn_font_sz.setFixedWidth(78)
        self.spn_font_sz.setFixedHeight(30)
        self.spn_font_sz.valueChanged.connect(self.on_font_spin_changed)
        h_font_sz.addWidget(self.spn_font_sz)
        style_layout.addLayout(h_font_sz, 3, 1)

        # Quick size presets buttons
        h_sz_presets = QHBoxLayout()
        h_sz_presets.setSpacing(6)
        lbl_quick = QLabel("Quick Size:")
        lbl_quick.setStyleSheet("font-size: 11px; color: #64748B;")
        h_sz_presets.addWidget(lbl_quick)
        for label, sz in [("Small 32", 32), ("Medium 44", 44), ("Cover Sub 52", 52), ("Large 60", 60)]:
            btn = QPushButton(label)
            btn.setFixedHeight(22)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #F1F5F9;
                    color: #0F172A;
                    border: 1px solid #CBD5E1;
                    border-radius: 4px;
                    font-size: 10px;
                    font-weight: 500;
                    padding: 0 4px;
                }
                QPushButton:hover {
                    background-color: #EFF6FF;
                    color: #1D4ED8;
                    border-color: #93C5FD;
                }
            """)
            btn.clicked.connect(lambda chk, s=sz: self.set_quick_font_size(s))
            h_sz_presets.addWidget(btn)
        h_sz_presets.addStretch()
        style_layout.addLayout(h_sz_presets, 4, 1)

        style_layout.addWidget(QLabel("Colors:"), 5, 0)
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
        style_layout.addLayout(h_colors, 5, 1)
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

        self.chk_safe_area = QCheckBox("Show TikTok safe area")
        self.chk_safe_area.setChecked(self.output_profile_name == "tiktok_9_16")
        self.chk_safe_area.setToolTip("Visual guide only; TikTok controls vary by device and caption layout.")
        self.chk_safe_area.toggled.connect(self.canvas_safe_area_changed)
        h_tb.addWidget(self.chk_safe_area)

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

        font_sz_init = int(self.settings.get("font_size", 46))
        self.spn_font_sz.setValue(font_sz_init)
        self.slider_font_sz.setValue(font_sz_init)

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
        self.canvas.set_fit_mode(self.export_fit_mode)
        self.canvas.set_safe_area_visible(self.chk_safe_area.isChecked())
        if self.output_profile_name == "tiktok_9_16":
            self.cbo_aspect.setCurrentIndex(0)

        # 2. Inspect video metadata and load 1st frame
        if self.current_video_path and Path(self.current_video_path).is_file():
            meta = get_video_meta(self.current_video_path)
            self.video_duration = max(1.0, float(meta.get("duration", 15.0)))
            self.video_aspect = meta.get("aspect_ratio", "9:16")

            # Update timeline slider maximum (steps of 0.1s)
            max_steps = int(round(self.video_duration * 10))
            self.slider_timeline.setRange(0, max(10, max_steps))
            self.slider_timeline.setValue(min(10, max_steps))

            if self.output_profile_name == "tiktok_9_16":
                self.cbo_aspect.setCurrentIndex(0)
            else:
                self.cbo_aspect.setCurrentIndex(1 if self.video_aspect == "16:9" else 0)
            self.canvas.set_fit_mode(self.export_fit_mode)
            self.canvas.set_safe_area_visible(self.chk_safe_area.isChecked())

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
                    if self.output_profile_name == "tiktok_9_16":
                        self.cbo_aspect.setCurrentIndex(0)
                    elif pix.width() > pix.height():
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

    def canvas_safe_area_changed(self, visible: bool):
        self.canvas.set_safe_area_visible(visible)

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

    def on_font_slider_changed(self, val: int):
        self.spn_font_sz.blockSignals(True)
        self.spn_font_sz.setValue(val)
        self.spn_font_sz.blockSignals(False)
        self.refresh_canvas()

    def on_font_spin_changed(self, val: int):
        self.slider_font_sz.blockSignals(True)
        self.slider_font_sz.setValue(val)
        self.slider_font_sz.blockSignals(False)
        self.refresh_canvas()

    def set_quick_font_size(self, sz: int):
        self.spn_font_sz.setValue(sz)

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
            "bg_color": self.bg_color,
            "export_profile_name": self.output_profile_name,
            "export_fit_mode": self.export_fit_mode,
            "show_safe_area": self.chk_safe_area.isChecked(),
        }
        self.accept()
