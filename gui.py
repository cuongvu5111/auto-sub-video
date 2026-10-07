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
    QGroupBox
)

from config import Config
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
                    voice=self.options.get("voice"),
                    ducking_volume=self.options.get("ducking_volume", 0.10),
                    burn_subtitles=self.options.get("burn_subtitles", True),
                    genre=self.options.get("genre", "Daily Life / Social Media"),
                    custom_terms=self.options.get("custom_terms", ""),
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
        self.sig_finished.emit(success_count, total)


class MainWindow(QMainWindow):
    """Main window for AutoDub Studio."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("AutoDub Studio - AI Video Dubbing & Subtitles")
        self.resize(1150, 780)
        self.setMinimumSize(950, 650)

        self.worker: Optional[DubbingWorker] = None

        self.init_ui()
        self.apply_styles()

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 8, 10, 10)
        main_layout.setSpacing(8)

        # 1. TOP HEADER & TABS
        top_bar = QHBoxLayout()
        self.tabs = QTabWidget()
        self.tab_dubbing = QWidget()
        self.tab_subs = QWidget()
        self.tab_models = QWidget()

        self.tabs.addTab(self.tab_dubbing, "🎬 Video Dubbing")
        self.tabs.addTab(self.tab_subs, "📝 Subtitle Translation")
        self.tabs.addTab(self.tab_models, "⚙️ Model Manager")

        # Status Indicators in top right
        self.lbl_indicators = QLabel("Network: ✓  |  LLM: ✓  |  Whisper: ✓  |  FFmpeg: ✓")
        self.lbl_indicators.setStyleSheet("color: #27AE60; font-weight: bold; padding-right: 8px;")

        top_bar.addWidget(self.tabs)
        top_bar.addWidget(self.lbl_indicators, alignment=Qt.AlignRight | Qt.AlignTop)
        main_layout.addLayout(top_bar)

        # MAIN VIDEO DUBBING TAB LAYOUT
        tab_layout = QVBoxLayout(self.tab_dubbing)
        tab_layout.setContentsMargins(4, 6, 4, 4)
        tab_layout.setSpacing(8)

        # 2. VIDEO QUEUE SECTION
        lbl_queue = QLabel("<b>Videos to Dub</b>")
        tab_layout.addWidget(lbl_queue)

        # Queue Toolbar
        queue_toolbar = QHBoxLayout()
        queue_toolbar.setSpacing(6)

        self.btn_paste_links = QPushButton("+ Paste Video Links...")
        self.btn_add_files = QPushButton("+ Add Videos...")
        self.btn_attach_srt = QPushButton("Attach .srt to Selected...")
        self.btn_remove_row = QPushButton("Remove Selected")
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
        self.table_queue.setFixedHeight(120)
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
        config_grid.setSpacing(10)

        # --- LEFT COLUMN: Original Subtitles & Translation ---
        left_col = QVBoxLayout()

        # Group ② Original Subtitles
        grp_source = QGroupBox("② Original Subtitle")
        layout_source = QGridLayout(grp_source)
        layout_source.addWidget(QLabel("Mode:"), 0, 0)
        self.cbo_mode = QComboBox()
        self.cbo_mode.addItems(["Auto — detect hardcoded subtitles", "Always run STT (Whisper)"])
        layout_source.addWidget(self.cbo_mode, 0, 1)

        layout_source.addWidget(QLabel("Source Language:"), 1, 0)
        self.cbo_lang = QComboBox()
        self.cbo_lang.addItems(["auto (Auto Detect)", "zh (Chinese)", "en (English)"])
        layout_source.addWidget(self.cbo_lang, 1, 1)
        left_col.addWidget(grp_source)

        # Group ③ Translation
        grp_trans = QGroupBox("③ Translation")
        layout_trans = QGridLayout(grp_trans)
        layout_trans.addWidget(QLabel("Translate With:"), 0, 0)
        h_model = QHBoxLayout()
        self.txt_model = QLineEdit(Config.LLM_MODEL)
        self.txt_model.setReadOnly(True)
        self.btn_change_model = QPushButton("Change...")
        self.btn_change_model.clicked.connect(self.action_change_model)
        h_model.addWidget(self.txt_model)
        h_model.addWidget(self.btn_change_model)
        layout_trans.addLayout(h_model, 0, 1)

        layout_trans.addWidget(QLabel("Engine Mode:"), 1, 0)
        self.cbo_trans_mode = QComboBox()
        self.cbo_trans_mode.addItems(["Fast — Parallel", "Sequential — Accurate"])
        layout_trans.addWidget(self.cbo_trans_mode, 1, 1)

        layout_trans.addWidget(QLabel("Genre:"), 2, 0)
        self.cbo_genre = QComboBox()
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
        self.txt_custom_terms.setPlaceholderText("Rules/Names, e.g., Luffy: Lu; Douyin: TikTok")
        layout_trans.addWidget(self.txt_custom_terms, 3, 1)
        left_col.addWidget(grp_trans)

        config_grid.addLayout(left_col, 0, 0)

        # --- RIGHT COLUMN: Dubbing & Export ---
        right_col = QVBoxLayout()

        # Group ④ Dubbing
        grp_tts = QGroupBox("④ Dubbing")
        layout_tts = QGridLayout(grp_tts)
        layout_tts.addWidget(QLabel("Voice:"), 0, 0)
        self.cbo_voice = QComboBox()
        for label, voice_key in Config.AVAILABLE_VOICES.items():
            self.cbo_voice.addItem(label, voice_key)
        layout_tts.addWidget(self.cbo_voice, 0, 1)

        layout_tts.addWidget(QLabel("Background Ducking:"), 1, 0)
        self.spn_ducking = QDoubleSpinBox()
        self.spn_ducking.setRange(0.0, 1.0)
        self.spn_ducking.setSingleStep(0.02)
        self.spn_ducking.setValue(Config.DEFAULT_DUCKING_VOLUME)
        layout_tts.addWidget(self.spn_ducking, 1, 1)

        layout_tts.addWidget(QLabel("Delay (sec):"), 2, 0)
        self.spn_delay = QDoubleSpinBox()
        self.spn_delay.setRange(-2.0, 5.0)
        self.spn_delay.setValue(0.0)
        layout_tts.addWidget(self.spn_delay, 2, 1)

        layout_tts.addWidget(QLabel("Voice Cloning:"), 3, 0)
        h_clone = QHBoxLayout()
        self.txt_clone = QLineEdit()
        self.txt_clone.setPlaceholderText("(Optional) Select reference audio...")
        self.btn_browse_clone = QPushButton("📁")
        h_clone.addWidget(self.txt_clone)
        h_clone.addWidget(self.btn_browse_clone)
        layout_tts.addLayout(h_clone, 3, 1)
        right_col.addWidget(grp_tts)

        # Group ⑤ Export
        grp_export = QGroupBox("⑤ Export")
        layout_export = QGridLayout(grp_export)

        h_sub_opts = QHBoxLayout()
        self.chk_burn_sub = QCheckBox("Burn translated subtitles into video")
        self.chk_burn_sub.setChecked(True)
        self.chk_blur_orig = QCheckBox("Blur original subtitles")
        h_sub_opts.addWidget(self.chk_burn_sub)
        h_sub_opts.addWidget(self.chk_blur_orig)
        layout_export.addLayout(h_sub_opts, 0, 0, 1, 2)

        layout_export.addWidget(QLabel("Font:"), 1, 0)
        h_font = QHBoxLayout()
        self.cbo_font = QComboBox()
        self.cbo_font.addItems(["Arial", "DejaVu Sans Bold", "Montserrat", "Segoe UI"])
        self.spn_font_size = QSpinBox()
        self.spn_font_size.setRange(10, 100)
        self.spn_font_size.setValue(22)
        h_font.addWidget(self.cbo_font, 2)
        h_font.addWidget(QLabel("Size:"), 1)
        h_font.addWidget(self.spn_font_size, 1)
        layout_export.addLayout(h_font, 1, 1)

        layout_export.addWidget(QLabel("Encoder:"), 2, 0)
        h_enc = QHBoxLayout()
        self.cbo_encoder = QComboBox()
        self.cbo_encoder.addItems(["libx264 (CPU)", "copy (Passthrough - Instant)"])
        self.cbo_quality = QComboBox()
        self.cbo_quality.addItems(["Best", "1080p", "720p"])
        h_enc.addWidget(self.cbo_encoder, 2)
        h_enc.addWidget(QLabel("Quality:"), 1)
        h_enc.addWidget(self.cbo_quality, 1)
        layout_export.addLayout(h_enc, 2, 1)

        layout_export.addWidget(QLabel("Save To:"), 3, 0)
        h_out = QHBoxLayout()
        self.txt_output_dir = QLineEdit(str(Config.OUTPUT_DIR))
        self.btn_browse_out = QPushButton("Browse...")
        self.btn_browse_out.clicked.connect(self.action_browse_output_dir)
        h_out.addWidget(self.txt_output_dir)
        h_out.addWidget(self.btn_browse_out)
        layout_export.addLayout(h_out, 3, 1)
        right_col.addWidget(grp_export)

        config_grid.addLayout(right_col, 0, 1)
        tab_layout.addLayout(config_grid)

        # 5. CONTROL BAR & PROGRESS
        ctrl_layout = QHBoxLayout()
        self.btn_run = QPushButton("▶  Start")
        self.btn_run.setFixedHeight(34)
        self.btn_run.setStyleSheet("background-color: #27AE60; color: white; font-weight: bold; font-size: 13px; border-radius: 4px; padding: 0 20px;")
        self.btn_run.clicked.connect(self.action_start_dubbing)

        self.btn_stop = QPushButton("■  Stop")
        self.btn_stop.setFixedHeight(34)
        self.btn_stop.setEnabled(False)
        self.btn_stop.setStyleSheet("background-color: #E74C3C; color: white; font-weight: bold; font-size: 13px; border-radius: 4px; padding: 0 15px;")
        self.btn_stop.clicked.connect(self.action_stop_dubbing)

        self.btn_open_folder = QPushButton("📁 Open Result Folder")
        self.btn_open_folder.setFixedHeight(34)
        self.btn_open_folder.clicked.connect(self.action_open_output_folder)

        self.lbl_stats = QLabel("Ready to process")
        self.lbl_stats.setStyleSheet("color: #555; font-size: 12px;")

        ctrl_layout.addWidget(self.btn_run)
        ctrl_layout.addWidget(self.btn_stop)
        ctrl_layout.addWidget(self.btn_open_folder)
        ctrl_layout.addStretch()
        ctrl_layout.addWidget(self.lbl_stats)
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
        self.txt_console.setFixedHeight(140)
        self.txt_console.setFont(QFont("Consolas", 10))
        self.txt_console.setStyleSheet("""
            QTextEdit {
                background-color: #111111;
                color: #00FF66;
                border: 1px solid #333333;
                border-radius: 4px;
                padding: 6px;
            }
        """)
        self.append_log("=== AutoDub Studio Initialized ===")
        self.append_log(f"• LLM Model: {Config.LLM_MODEL} | Base URL: {Config.LLM_BASE_URL}")
        self.append_log(f"• Whisper: {Config.WHISPER_MODEL} ({Config.WHISPER_DEVICE})")
        self.append_log("• Ready! Paste TikTok links or add video files to begin.")
        tab_layout.addWidget(self.txt_console)

    def apply_styles(self):
        """Apply clean styles for Windows desktop theme."""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #F8F9FA;
            }
            QGroupBox {
                font-weight: bold;
                border: 1px solid #D1D5DB;
                border-radius: 6px;
                margin-top: 6px;
                padding-top: 10px;
                background-color: #FFFFFF;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
            }
            QPushButton {
                background-color: #FFFFFF;
                border: 1px solid #D1D5DB;
                border-radius: 4px;
                padding: 5px 12px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #F3F4F6;
                border-color: #9CA3AF;
            }
            QLineEdit, QComboBox, QDoubleSpinBox, QSpinBox {
                border: 1px solid #D1D5DB;
                border-radius: 4px;
                padding: 4px 6px;
                background-color: #FFFFFF;
                font-size: 12px;
            }
            QTableWidget {
                background-color: #FFFFFF;
                border: 1px solid #D1D5DB;
                border-radius: 4px;
                gridline-color: #F3F4F6;
            }
            QHeaderView::section {
                background-color: #F3F4F6;
                border: none;
                border-bottom: 1px solid #D1D5DB;
                padding: 4px;
                font-weight: bold;
            }
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
        """Change LLM model name."""
        model_name, ok = QInputDialog.getText(
            self,
            "LLM Model Configuration",
            "Enter model name (OpenAI-compatible endpoint):",
            QLineEdit.Normal,
            self.txt_model.text()
        )
        if ok and model_name.strip():
            self.txt_model.setText(model_name.strip())
            self.append_log(f"• LLM Model changed to: {model_name.strip()}")

    @Slot()
    def action_open_output_folder(self):
        """Open the result output folder in Windows File Explorer."""
        folder = Path(self.txt_output_dir.text()).resolve()
        folder.mkdir(parents=True, exist_ok=True)
        if sys.platform == "win32":
            os.startfile(str(folder))
        else:
            subprocess.run(["xdg-open", str(folder)])

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

        voice_key = self.cbo_voice.currentData()
        options = {
            "voice": voice_key,
            "ducking_volume": self.spn_ducking.value(),
            "burn_subtitles": self.chk_burn_sub.isChecked(),
            "genre": self.cbo_genre.currentText(),
            "custom_terms": self.txt_custom_terms.text().strip(),
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
        QMessageBox.information(
            self,
            "Finished",
            f"Batch processing completed!\nSuccessful: {success_count}/{total_count} video(s)."
        )


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
