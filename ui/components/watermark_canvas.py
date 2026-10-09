"""
AutoDub Studio - WatermarkPreviewCanvas Component.
Real-time QPainter canvas for Text & Logo Watermark placement and opacity visualization.
"""

from pathlib import Path
from typing import Optional
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import (
    QPainter, QColor, QFont, QFontMetrics, QPixmap,
    QLinearGradient, QPainterPath, QPen
)
from PySide6.QtWidgets import QWidget


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
            wm_font_px = max(6, int(round(self.text_font_size * scale_h)))
            wm_font = QFont("Arial")
            wm_font.setPixelSize(wm_font_px)
            wm_font.setBold(True)
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
