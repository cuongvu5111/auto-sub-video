"""
AutoDub Studio - Centralized UI Stylesheet and Theme Definitions.
Provides polished, high-contrast styles compatible with both Windows Light and Dark themes.
"""

from pathlib import Path
from config import Config


def get_main_window_stylesheet() -> str:
    """Return complete QSS stylesheet for MainWindow and global application widgets."""
    icon_up = (Config.BASE_DIR / "assets" / "icons" / "arrow_up.svg").resolve().as_posix()
    icon_down = (Config.BASE_DIR / "assets" / "icons" / "arrow_down.svg").resolve().as_posix()
    icon_chk_checked = (Config.BASE_DIR / "assets" / "icons" / "checkbox_checked.svg").resolve().as_posix()
    icon_chk_un = (Config.BASE_DIR / "assets" / "icons" / "checkbox_unchecked.svg").resolve().as_posix()

    return f"""
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
    """


def get_paste_links_dialog_stylesheet() -> str:
    """Return styling for PasteLinksDialog."""
    return """
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
    """


def get_watermark_dialog_stylesheet() -> str:
    """Return styling for WatermarkConfigDialog."""
    return """
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
            font-weight: bold;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 4px;
            color: #1E293B;
        }
    """


def get_subtitle_dialog_stylesheet() -> str:
    """Return styling for SubtitlePreviewDialog."""
    return """
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
            font-weight: bold;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 4px;
            color: #1E293B;
        }
    """
