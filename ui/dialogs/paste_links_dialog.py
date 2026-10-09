"""
AutoDub Studio - PasteLinksDialog.
Modal dialog for batch pasting video URLs with clear light theme styling.
"""

from typing import List
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit,
    QPushButton, QApplication
)
from ui.styles import get_paste_links_dialog_stylesheet


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
        self.setStyleSheet(get_paste_links_dialog_stylesheet())

    def action_paste_clipboard(self):
        clipboard = QApplication.clipboard()
        text = clipboard.text()
        if text:
            self.txt_links.append(text.strip())

    def get_links(self) -> List[str]:
        raw_text = self.txt_links.toPlainText()
        return [line.strip() for line in raw_text.splitlines() if line.strip()]
