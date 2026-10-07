"""
AutoDub Studio - Native Windows Desktop Application (PySide6 / Qt).
Designed for Go-Global distribution with an English UI, batch queue processing,
dual-column settings, smooth progress bar, and real-time terminal console log.
"""

import sys
import os
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
from PySide6.QtGui import QFont, QColor
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QTabWidget, QTableWidget, QTableWidgetItem, QHeaderView,
    QPushButton, QComboBox, QDoubleSpinBox, QSpinBox, QLineEdit, QCheckBox,
    QLabel, QProgressBar, QTextEdit, QFileDialog, QInputDialog, QMessageBox,
    QGroupBox, QColorDialog, QDialog
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



class MainWindow(QMainWindow):
    """Main window for AutoDub Studio."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("AutoDub Studio - AI Video Dubbing & Subtitles")
        self.resize(1280, 860)
        self.setMinimumSize(1080, 760)

        # Căn giữa cửa sổ trên màn hình desktop
        try:
            screen_geo = QApplication.primaryScreen().availableGeometry()
            self.move(
                max(0, (screen_geo.width() - 1280) // 2),
                max(0, (screen_geo.height() - 860) // 2)
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
                "api_key": Config.LLM_API_KEY if "vnptsi" in Config.LLM_BASE_URL else "no-key-required",
                "model": "google/gemma-4-26B-A4B-it"
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

        self.init_ui()
        self.apply_styles()

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
        self.btn_attach_srt = QPushButton("Attach .srt to Selected...")
        self.btn_attach_srt.setFixedHeight(32)
        self.btn_remove_row = QPushButton("Remove Selected")
        self.btn_remove_row.setFixedHeight(32)
        self.chk_only_srt = QCheckBox("Translate .srt only...")

        self.btn_paste_links.clicked.connect(self.action_paste_links)
        self.btn_add_files.clicked.connect(self.action_add_files)
        self.btn_remove_row.clicked.connect(self.action_remove_selected_rows)

        queue_toolbar.addWidget(self.btn_paste_links)
        queue_toolbar.addWidget(self.btn_add_files)
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
        self.table_queue.setFixedHeight(105)
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
        grp_export.setMinimumHeight(245)
        layout_export = QGridLayout(grp_export)
        layout_export.setContentsMargins(18, 14, 18, 14)
        layout_export.setVerticalSpacing(12)
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
        self.cbo_font.setFixedHeight(32)
        self.cbo_font.setFixedWidth(200)
        self.cbo_font.addItems(["Arial", "DejaVu Sans Bold", "Montserrat", "Segoe UI"])
        lbl_size = QLabel("Size:")
        lbl_size.setFixedWidth(34)
        self.spn_font_size = QSpinBox()
        self.spn_font_size.setFixedHeight(32)
        self.spn_font_size.setFixedWidth(80)
        self.spn_font_size.setRange(10, 100)
        self.spn_font_size.setValue(22)
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
        self.cbo_sub_style.setFixedHeight(32)
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

        layout_export.addWidget(QLabel("Encoder:"), 3, 0)
        h_enc = QHBoxLayout()
        h_enc.setSpacing(12)
        self.cbo_encoder = QComboBox()
        self.cbo_encoder.setFixedHeight(32)
        self.cbo_encoder.setFixedWidth(200)
        self.cbo_encoder.addItems(["libx264 (CPU)", "copy (Passthrough - Instant)"])
        lbl_quality = QLabel("Quality:")
        lbl_quality.setFixedWidth(48)
        self.cbo_quality = QComboBox()
        self.cbo_quality.setFixedHeight(32)
        self.cbo_quality.setFixedWidth(100)
        self.cbo_quality.addItems(["Best", "1080p", "720p"])
        h_enc.addWidget(self.cbo_encoder)
        h_enc.addWidget(lbl_quality)
        h_enc.addWidget(self.cbo_quality)
        h_enc.addStretch()
        layout_export.addLayout(h_enc, 3, 1)

        layout_export.addWidget(QLabel("Save To:"), 4, 0)
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
        layout_export.addLayout(h_out, 4, 1)
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

    @Slot()
    def action_paste_links(self):
        """Open dialog allowing user to paste multiple video links."""
        text, ok = QInputDialog.getMultiLineText(
            self,
            "Paste Video Links",
            "Paste one or more video links (one URL per line):"
        )
        if ok and text.strip():
            links = [line.strip() for line in text.strip().splitlines() if line.strip()]
            for link in links:
                row = self.table_queue.rowCount()
                self.table_queue.insertRow(row)
                self.table_queue.setItem(row, 0, QTableWidgetItem(link))
                self.table_queue.setItem(row, 1, QTableWidgetItem("-"))
                item_status = QTableWidgetItem("Queued")
                item_status.setForeground(QColor("#7F8C8D"))
                self.table_queue.setItem(row, 2, item_status)
            self.lbl_stats.setText(f"{self.table_queue.rowCount()} video(s) in queue")

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

    @Slot()
    def action_remove_selected_rows(self):
        """Remove selected rows from queue table."""
        selected_rows = sorted(set(index.row() for index in self.table_queue.selectedIndexes()), reverse=True)
        for row in selected_rows:
            self.table_queue.removeRow(row)
        self.lbl_stats.setText(f"{self.table_queue.rowCount()} video(s) in queue")

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

    @Slot()
    def action_start_dubbing(self):
        """Start batch processing via DubbingWorker thread."""
        count = self.table_queue.rowCount()
        if count == 0:
            QMessageBox.warning(self, "Notice", "Queue is empty! Please add video files or paste video links first.")
            return

        tasks = []
        for row in range(count):
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
            "margin_v": 40
        }
        options = {
            "source_lang": source_lang,
            "voice": voice_key,
            "ducking_volume": self.spn_ducking.value(),
            "burn_subtitles": self.chk_burn_sub.isChecked(),
            "genre": self.cbo_genre.currentText(),
            "custom_terms": self.txt_custom_terms.text().strip(),
            "subtitle_options": subtitle_options,
            "output_dir": Path(self.txt_output_dir.text()).resolve()
        }

        self.btn_run.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.progress_bar.setValue(0)
        self.lbl_stats.setText(f"Processing 0/{count} video(s)...")

        # Launch Worker Thread
        self.worker = DubbingWorker(tasks, options)
        self.worker.sig_log.connect(self.append_log)
        self.worker.sig_progress.connect(self.update_progress)
        self.worker.sig_item_status.connect(self.update_item_status)
        self.worker.sig_finished.connect(self.on_worker_finished)
        self.worker.start()

    @Slot()
    def action_stop_dubbing(self):
        """Request worker thread to stop."""
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.btn_stop.setEnabled(False)
            self.lbl_stats.setText("Cancelling process...")

    @Slot(float)
    def update_progress(self, percent: float):
        self.progress_bar.setValue(int(percent))

    @Slot(int, str, str)
    def update_item_status(self, row: int, status: str, hex_color: str):
        item = QTableWidgetItem(status)
        item.setForeground(QColor(hex_color))
        self.table_queue.setItem(row, 2, item)

    @Slot(int, int)
    def on_worker_finished(self, success_count: int, total_count: int):
        self.btn_run.setEnabled(True)
        self.btn_stop.setEnabled(False)
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
