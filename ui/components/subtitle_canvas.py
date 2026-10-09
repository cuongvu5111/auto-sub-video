"""
AutoDub Studio - SubtitlePreviewCanvas Component.
Accurate real-time LibASS subtitle simulation canvas with interactive Margin V dragging.
"""

from typing import Optional
from PySide6.QtCore import Qt, Signal, QRectF
from PySide6.QtGui import (
    QPainter, QColor, QFont, QFontMetrics, QPixmap,
    QLinearGradient, QPainterPath, QPen
)
from PySide6.QtWidgets import QWidget


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

        # 4. Render Subtitle and Hardsub Cover Box (1:1 chuẩn xác theo FFmpeg LibASS)
        scale_h = canvas_h / ref_h
        scale_w = canvas_w / ref_w

        # Trong ASS, Fontsize tính bằng pixel theo chiều cao chuẩn PlayResY (1280).
        # Trên canvas có chiều cao canvas_h, kích thước font chính xác 1:1 là:
        canvas_font_px = max(6, int(round(self.font_size * scale_h)))
        font_fam = self.font_name if self.font_name else "Arial"
        sub_font = QFont(font_fam)
        sub_font.setPixelSize(canvas_font_px)
        sub_font.setBold(True)
        p.setFont(sub_font)
        fm = QFontMetrics(sub_font)

        raw_text = self.sub_text.strip() if self.sub_text else "Phụ đề tiếng Việt mẫu"
        lines = [ln.strip() for ln in raw_text.split("\n") if ln.strip()]
        if not lines:
            lines = ["Phụ đề tiếng Việt mẫu"]

        line_height = fm.height()
        line_spacing = max(1, int(round(3 * scale_h)))
        total_text_h = len(lines) * line_height + (len(lines) - 1) * line_spacing

        max_line_w = 0
        for ln in lines:
            tw = fm.horizontalAdvance(ln)
            if tw > max_line_w:
                max_line_w = tw

        # Padding xung quanh chữ chuẩn LibASS (outline_width co giãn theo scale)
        pad_x = max(2.0, float(self.box_padding) * scale_w + 3.0 * scale_w)
        pad_y = max(2.0, float(self.box_padding) * scale_h + 1.5 * scale_h)

        bw = min(canvas_w - 12.0, max_line_w + pad_x * 2.0)
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
