"""
AutoDub Studio - MainWindow Component.
Native Windows Desktop Application (PySide6 / Qt).
"""

import sys
import os
import shutil
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QFont, QColor, QPixmap
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

from ui.worker import DubbingWorker
from ui.dialogs.paste_links_dialog import PasteLinksDialog
from ui.dialogs.watermark_dialog import WatermarkConfigDialog
from ui.dialogs.subtitle_dialog import SubtitlePreviewDialog
from ui.components.watermark_canvas import WatermarkPreviewCanvas
from ui.components.subtitle_canvas import SubtitlePreviewCanvas
from ui.components.spinbox import RobustSpinBox
from ui.video_utils import extract_video_frame_at, get_video_meta
from ui.styles import get_main_window_stylesheet


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
                # Never ship a provider credential in source; users configure their own key.
                "api_key": Config.LLM_API_KEY if ("vnptsi" in Config.LLM_BASE_URL and Config.LLM_API_KEY != "no-key-required") else "",
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
        self.chk_only_srt = QCheckBox("Use attached SRT only (skip Whisper)")

        self.btn_paste_links.clicked.connect(self.action_paste_links)
        self.btn_add_files.clicked.connect(self.action_add_files)
        self.btn_cookies.clicked.connect(self.action_manage_cookies)
        self.btn_attach_srt.clicked.connect(self.action_attach_srt)
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
        self.cbo_mode.addItems(["Prefer attached SRT; otherwise run Whisper", "Always run STT (Whisper)"])
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

        # Group ④ Voice Dubbing / Audio Translation
        grp_tts = QGroupBox("④ Voice Dubbing & Audio Translation")
        layout_tts = QGridLayout(grp_tts)
        layout_tts.setContentsMargins(18, 14, 18, 14)
        layout_tts.setVerticalSpacing(10)
        layout_tts.setHorizontalSpacing(14)
        layout_tts.setColumnStretch(0, 0)
        layout_tts.setColumnStretch(1, 1)
        layout_tts.setColumnMinimumWidth(0, 110)

        # Row 0: On/Off Audio Dubbing Checkbox
        h_dub_enable = QHBoxLayout()
        h_dub_enable.setSpacing(12)
        self.chk_enable_dubbing = QCheckBox("Enable AI Voice Dubbing (Lồng tiếng AI)")
        self.chk_enable_dubbing.setChecked(True)
        self.chk_enable_dubbing.setStyleSheet("font-weight: bold; font-size: 13px; color: #1E293B;")
        self.chk_enable_dubbing.toggled.connect(self.on_toggle_dubbing)
        h_dub_enable.addWidget(self.chk_enable_dubbing)

        self.lbl_dub_hint = QLabel("(Uncheck to preserve original audio & burn subtitles only)")
        self.lbl_dub_hint.setStyleSheet("color: #64748B; font-size: 11px;")
        h_dub_enable.addWidget(self.lbl_dub_hint)
        h_dub_enable.addStretch()
        layout_tts.addLayout(h_dub_enable, 0, 0, 1, 2)

        # Row 1: Voice
        self.lbl_voice = QLabel("Voice:")
        layout_tts.addWidget(self.lbl_voice, 1, 0)
        self.cbo_voice = QComboBox()
        self.cbo_voice.setFixedHeight(32)
        for label, voice_key in Config.AVAILABLE_VOICES.items():
            self.cbo_voice.addItem(label, voice_key)
        layout_tts.addWidget(self.cbo_voice, 1, 1)

        # Row 2: Volume & Delay
        self.lbl_vol_delay = QLabel("Volume & Delay:")
        layout_tts.addWidget(self.lbl_vol_delay, 2, 0)
        h_tuning = QHBoxLayout()
        h_tuning.setSpacing(10)

        self.lbl_ducking = QLabel("Ducking:")
        self.spn_ducking = QDoubleSpinBox()
        self.spn_ducking.setFixedHeight(32)
        self.spn_ducking.setFixedWidth(85)
        self.spn_ducking.setRange(0.0, 1.0)
        self.spn_ducking.setSingleStep(0.02)
        self.spn_ducking.setValue(Config.DEFAULT_DUCKING_VOLUME)

        self.lbl_delay = QLabel("Dubbing Delay:")
        self.lbl_delay.setFixedWidth(90)
        self.spn_delay = QDoubleSpinBox()
        self.spn_delay.setFixedHeight(32)
        self.spn_delay.setFixedWidth(85)
        self.spn_delay.setRange(-2.0, 5.0)
        self.spn_delay.setValue(0.0)

        h_tuning.addWidget(self.lbl_ducking)
        h_tuning.addWidget(self.spn_ducking)
        h_tuning.addWidget(self.lbl_delay)
        h_tuning.addWidget(self.spn_delay)
        h_tuning.addStretch()
        layout_tts.addLayout(h_tuning, 2, 1)

        # Row 3: Voice Cloning
        self.lbl_clone = QLabel("Voice Cloning:")
        layout_tts.addWidget(self.lbl_clone, 3, 0)
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
        layout_tts.addLayout(h_clone, 3, 1)
        self.lbl_clone.setEnabled(False)
        self.txt_clone.setEnabled(False)
        self.btn_browse_clone.setEnabled(False)
        self.txt_clone.setToolTip("Voice cloning is not supported by the selected Edge TTS engine.")
        right_col.addWidget(grp_tts)

        # Group ⑤ Export
        grp_export = QGroupBox("⑤ Export")
        grp_export.setMinimumHeight(340)
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
        self.chk_blur_orig.setEnabled(False)
        self.chk_blur_orig.setToolTip("Subtitle blur is unavailable until a blur region can be configured.")
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
        self.spn_font_size.setRange(12, 120)
        self.spn_font_size.setValue(46)
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

        layout_export.addWidget(QLabel("Video Profile:"), 6, 0)
        h_profile = QHBoxLayout()
        h_profile.setSpacing(10)
        self.cbo_export_profile = QComboBox()
        self.cbo_export_profile.setFixedHeight(32)
        self.cbo_export_profile.addItem("Original size", "original")
        self.cbo_export_profile.addItem("TikTok Portrait 9:16 (1080×1920)", "tiktok_9_16")
        self.cbo_export_fit = QComboBox()
        self.cbo_export_fit.setFixedHeight(32)
        self.cbo_export_fit.addItem("Crop to fill", "crop")
        self.cbo_export_fit.addItem("Fit with black bars", "contain")
        self.cbo_export_profile.currentIndexChanged.connect(
            lambda _index: self.cbo_export_fit.setEnabled(
                self.cbo_export_profile.currentData() == "tiktok_9_16"
            )
        )
        self.cbo_export_fit.setEnabled(False)
        h_profile.addWidget(self.cbo_export_profile)
        h_profile.addWidget(self.cbo_export_fit)
        h_profile.addStretch()
        layout_export.addLayout(h_profile, 6, 1)

        # Row 7: Save To
        layout_export.addWidget(QLabel("Save To:"), 7, 0)
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
        layout_export.addLayout(h_out, 7, 1)
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
        self.setStyleSheet(get_main_window_stylesheet())

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
        for widget in (
            self.btn_paste_links, self.btn_add_files, self.btn_cookies,
            self.btn_attach_srt, self.btn_remove_row, self.chk_only_srt,
            self.table_queue,
        ):
            widget.setEnabled(not is_running)

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
                    source_item = QTableWidgetItem(link)
                    source_item.setFlags(source_item.flags() & ~Qt.ItemIsEditable)
                    self.table_queue.setItem(row, 0, source_item)
                    subtitle_item = QTableWidgetItem("-")
                    subtitle_item.setFlags(subtitle_item.flags() & ~Qt.ItemIsEditable)
                    self.table_queue.setItem(row, 1, subtitle_item)
                    item_status = QTableWidgetItem("Queued")
                    item_status.setFlags(item_status.flags() & ~Qt.ItemIsEditable)
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
                source_item = QTableWidgetItem(file_path)
                source_item.setFlags(source_item.flags() & ~Qt.ItemIsEditable)
                self.table_queue.setItem(row, 0, source_item)
                subtitle_item = QTableWidgetItem("-")
                subtitle_item.setFlags(subtitle_item.flags() & ~Qt.ItemIsEditable)
                self.table_queue.setItem(row, 1, subtitle_item)
                item_status = QTableWidgetItem("Queued")
                item_status.setFlags(item_status.flags() & ~Qt.ItemIsEditable)
                item_status.setForeground(QColor("#7F8C8D"))
                self.table_queue.setItem(row, 2, item_status)
            self.lbl_stats.setText(f"{self.table_queue.rowCount()} video(s) in queue")
            self.update_control_buttons()

    @Slot()
    def action_attach_srt(self):
        """Attach one validated SRT path to each selected video row."""
        selected_rows = sorted({index.row() for index in self.table_queue.selectedIndexes()})
        if not selected_rows:
            QMessageBox.warning(self, "Attach subtitles", "Select one or more video rows first.")
            return

        files, _ = QFileDialog.getOpenFileNames(self, "Select SRT Files", "", "Subtitles (*.srt)")
        if not files:
            return
        if len(files) != len(selected_rows):
            QMessageBox.warning(
                self,
                "Attach subtitles",
                "Select exactly one SRT file per selected video row. Select one video row to attach a single file.",
            )
            return

        from core.subtitles import parse_srt, SubtitleFileError
        try:
            for srt_path in files:
                parse_srt(srt_path)
        except SubtitleFileError as exc:
            QMessageBox.warning(self, "Invalid SRT", str(exc))
            return

        for row, srt_path in zip(selected_rows, files):
            item = QTableWidgetItem(Path(srt_path).name)
            item.setData(Qt.UserRole, str(Path(srt_path).resolve()))
            item.setToolTip(str(Path(srt_path).resolve()))
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            self.table_queue.setItem(row, 1, item)

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

    @Slot(bool)
    def on_toggle_dubbing(self, enabled: bool):
        """Bật/tắt chế độ lồng tiếng AI: khi tắt thì giữ trọn vẹn 100% âm thanh gốc của video."""
        self.cbo_voice.setEnabled(enabled)
        self.spn_ducking.setEnabled(enabled)
        self.spn_delay.setEnabled(enabled)
        self.txt_clone.setEnabled(False)
        self.btn_browse_clone.setEnabled(False)
        self.lbl_voice.setEnabled(enabled)
        self.lbl_vol_delay.setEnabled(enabled)
        self.lbl_clone.setEnabled(enabled)
        self.lbl_ducking.setEnabled(enabled)
        self.lbl_delay.setEnabled(enabled)

        if enabled:
            self.lbl_dub_hint.setText("(AI voice will replace/duck original dialogue)")
            self.lbl_dub_hint.setStyleSheet("color: #64748B; font-size: 11px;")
        else:
            self.lbl_dub_hint.setText("(⚡ Preserves 100% original video audio, generates subtitles only)")
            self.lbl_dub_hint.setStyleSheet("color: #2563EB; font-weight: 500; font-size: 11px;")

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
            "export_profile_name": self.cbo_export_profile.currentData() or "original",
            "export_fit_mode": self.cbo_export_fit.currentData() or "crop",
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
            if not status_text.startswith(("✓ Done", "⚠ Done with warnings")):
                pending_rows.append(row)

        target_rows = pending_rows if pending_rows else list(range(count))

        tasks = []
        for row in target_rows:
            source_item = self.table_queue.item(row, 0)
            source = source_item.text().strip() if source_item else ""
            subtitle_item = self.table_queue.item(row, 1)
            subtitle_path = subtitle_item.data(Qt.UserRole) if subtitle_item else None
            tasks.append({"row": row, "source": source, "subtitle_path": subtitle_path})

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
        profile_name = self.cbo_export_profile.currentData() or "original"
        export_profile = {"name": profile_name}
        if profile_name == "tiktok_9_16":
            export_profile.update({"width": 1080, "height": 1920, "fit_mode": self.cbo_export_fit.currentData() or "crop"})
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
            "export_profile": export_profile,
            "enable_dubbing": self.chk_enable_dubbing.isChecked(),
            "prefer_attached_subtitle": self.cbo_mode.currentIndex() == 0,
            "translate_srt_only": self.chk_only_srt.isChecked(),
            "delay_offset": self.spn_delay.value(),
            "output_dir": Path(self.txt_output_dir.text()).resolve()
        }

        self.btn_run.setEnabled(False)
        self.btn_stop.setEnabled(True)
        for widget in (
            self.btn_paste_links, self.btn_add_files, self.btn_cookies,
            self.btn_attach_srt, self.btn_remove_row, self.chk_only_srt,
            self.table_queue,
        ):
            widget.setEnabled(False)
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
            self.append_log("⏹ Cancellation requested. Active operations will stop at the next safe point...")
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


