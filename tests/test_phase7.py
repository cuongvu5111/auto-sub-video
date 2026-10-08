"""
Kiểm thử cho Phase 7: Giao Diện Desktop Studio Native (PySide6).
"""

import sys
import ast
from pathlib import Path

# Cấu hình encoding UTF-8 cho console Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir))
gui_file = root_dir / "gui.py"


def test_gui_syntax_and_structure():
    """Kiểm tra cú pháp AST của gui.py và đảm bảo đầy đủ các class cốt lõi."""
    assert gui_file.exists(), "gui.py không tồn tại"
    source = gui_file.read_text(encoding="utf-8")
    tree = ast.parse(source)

    class_names = [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
    assert "DubbingWorker" in class_names, "Thiếu class DubbingWorker trong gui.py"
    assert "MainWindow" in class_names, "Thiếu class MainWindow trong gui.py"
    print("✓ test_gui_syntax_and_structure: PASSED (Cú pháp hợp lệ, có DubbingWorker và MainWindow)")


def test_worker_signals_and_button_recovery():
    """Kiểm tra DubbingWorker luôn phát sig_finished và MainWindow có update_control_buttons."""
    from PySide6.QtWidgets import QApplication
    from gui import DubbingWorker, MainWindow
    
    app = QApplication.instance() or QApplication(sys.argv)
    
    # Kiểm tra phương thức update_control_buttons có tồn tại trên MainWindow
    assert hasattr(MainWindow, "update_control_buttons"), "MainWindow thiếu phương thức update_control_buttons"
    
    # Kiểm tra worker với task giả định lỗi
    fake_tasks = [{"row": 0, "source": "non_existent_fake_video.mp4"}]
    worker = DubbingWorker(fake_tasks, {})
    
    finished_called = []
    def on_finished(success, total):
        finished_called.append((success, total))
        
    worker.sig_finished.connect(on_finished)
    worker.run()  # Chạy trực tiếp phương thức run để kiểm tra khối try...finally
    
    assert len(finished_called) == 1, "sig_finished không được phát khi worker kết thúc hoặc gặp lỗi"
    assert finished_called[0] == (0, 1), f"Kết quả trả về không đúng: {finished_called[0]}"
    print("✓ test_worker_signals_and_button_recovery: PASSED (sig_finished luôn phát dù video bị lỗi)")


def test_paste_links_dialog():
    """Kiểm tra khởi tạo PasteLinksDialog, styling và phương thức bóc tách links."""
    from PySide6.QtWidgets import QApplication
    from gui import PasteLinksDialog

    app = QApplication.instance() or QApplication(sys.argv)
    dlg = PasteLinksDialog()
    assert dlg.windowTitle() == "🔗 Paste Video Links"
    
    # Test bóc tách link
    sample_text = "https://v.douyin.com/W6GuKycdLJs/\n\n   https://www.tiktok.com/@test/video/123   \n"
    dlg.txt_links.setPlainText(sample_text)
    links = dlg.get_links()
    assert len(links) == 2
    assert links[0] == "https://v.douyin.com/W6GuKycdLJs/"
    assert links[1] == "https://www.tiktok.com/@test/video/123"
    print("✓ test_paste_links_dialog: PASSED (Khởi tạo, styling và bóc tách URL hoàn hảo)")


def test_cookie_button_and_management():
    """Kiểm tra nút quản lý Cookies, trạng thái hiển thị động và các slot liên quan."""
    from PySide6.QtWidgets import QApplication
    from gui import MainWindow
    from config import Config

    app = QApplication.instance() or QApplication(sys.argv)
    win = MainWindow()

    assert hasattr(win, "btn_cookies"), "MainWindow thiếu thuộc tính btn_cookies"
    assert hasattr(win, "update_cookie_button_state"), "MainWindow thiếu phương thức update_cookie_button_state"
    assert hasattr(win, "action_manage_cookies"), "MainWindow thiếu phương thức action_manage_cookies"

    cookie_file = Config.BASE_DIR / "cookies.txt"
    backup_file = Config.BASE_DIR / "cookies.txt.bak_test"

    try:
        # Nếu đang có cookies.txt thật, backup tạm thời
        if cookie_file.exists():
            cookie_file.rename(backup_file)

        # 1. Trạng thái khi chưa có cookie
        win.update_cookie_button_state()
        assert win.btn_cookies.text() == "🍪 Cookies (.txt)"

        # 2. Trạng thái khi có cookie file
        cookie_file.write_text("# Netscape HTTP Cookie File\n.douyin.com\tTRUE\t/\tFALSE\t0\tsid_guard\t123456\n", encoding="utf-8")
        win.update_cookie_button_state()
        assert "Active ✓" in win.btn_cookies.text()
        assert "#10B981" in win.btn_cookies.styleSheet()

        # 3. Trạng thái sau khi xóa cookie
        cookie_file.unlink(missing_ok=True)
        win.update_cookie_button_state()
        assert win.btn_cookies.text() == "🍪 Cookies (.txt)"

    finally:
        # Khôi phục trạng thái ban đầu
        if cookie_file.exists():
            cookie_file.unlink(missing_ok=True)
        if backup_file.exists():
            backup_file.rename(cookie_file)

    print("✓ test_cookie_button_and_management: PASSED (Nút Cookies, đổi trạng thái động và dọn dẹp hoạt động chuẩn xác)")


def test_worker_immediate_cancel():
    """Kiểm tra DubbingWorker và pipeline dừng ngay lập tức khi nhận yêu cầu cancel."""
    from gui import DubbingWorker
    from pipeline import run_pipeline

    tasks = [{"row": 0, "source": "dummy_video.mp4"}]
    worker = DubbingWorker(tasks, {})
    worker.cancel()
    assert worker._is_cancelled is True

    # Kiểm tra pipeline phát hiện cancel_check và ngắt lập tức
    interrupted = False
    try:
        run_pipeline("dummy_video.mp4", cancel_check=lambda: True)
    except InterruptedError:
        interrupted = True
    assert interrupted, "run_pipeline không dừng ngay khi cancel_check trả về True!"

    print("✓ test_worker_immediate_cancel: PASSED (Huỷ ngang tức thì khi nhận tín hiệu Stop)")


def test_watermark_spinbox_and_persistence():
    """Kiểm tra WatermarkConfigDialog bóc tách số từ input và lưu cấu hình không bị reset."""
    from gui import WatermarkConfigDialog

    dlg = WatermarkConfigDialog(None, {"logo_max_width": 160})
    dlg.spn_logo_max_width.lineEdit().setText("350")
    dlg.action_save()
    assert dlg.config["logo_max_width"] == 350, f"Expected 350, got {dlg.config['logo_max_width']}"

    dlg2 = WatermarkConfigDialog(None, {"logo_max_width": 160})
    dlg2.spn_logo_max_width.lineEdit().setText("450px")
    dlg2.action_save()
    assert dlg2.config["logo_max_width"] == 450

    dlg3 = WatermarkConfigDialog(None, {"logo_max_width": 160})
    dlg3.spn_logo_max_width.lineEdit().setText("   800 px  ")
    dlg3.action_save()
    assert dlg3.config["logo_max_width"] == 800

    print("✓ test_watermark_spinbox_and_persistence: PASSED (Bóc tách chuỗi, tự động lọc đơn vị px và lưu cấu hình thành công)")


def test_watermark_live_preview_canvas():
    """Kiểm tra WatermarkPreviewCanvas và tích hợp live preview trong WatermarkConfigDialog."""
    from gui import WatermarkPreviewCanvas, WatermarkConfigDialog
    from PySide6.QtGui import QPixmap

    # 1. Kiểm tra khởi tạo và cập nhật trạng thái canvas
    canvas = WatermarkPreviewCanvas()
    canvas.resize(320, 480)
    canvas.set_aspect_ratio("9:16")
    canvas.set_text_watermark(True, "Kênh Vũ Mạnh Cường", "center", 24)
    canvas.set_logo_watermark(True, "", "top-right", 0.85, 220)
    assert canvas.aspect_ratio == "9:16"
    assert canvas.text_enabled is True
    assert canvas.text_content == "Kênh Vũ Mạnh Cường"

    # Đổi sang 16:9
    canvas.set_aspect_ratio("16:9")
    assert canvas.aspect_ratio == "16:9"

    # 2. Kiểm tra WatermarkConfigDialog tích hợp live preview
    dlg = WatermarkConfigDialog(None, {
        "text_enabled": True,
        "text": "Banner Test",
        "text_position": "top",
        "logo_enabled": True,
        "logo_position": "bottom-right",
        "logo_max_width": 250
    })
    assert hasattr(dlg, "preview_canvas")
    assert hasattr(dlg, "cbo_aspect_ratio")
    assert hasattr(dlg, "btn_choose_frame")

    # Kiểm tra đồng bộ dữ liệu vào canvas
    dlg.refresh_preview()
    assert dlg.preview_canvas.text_enabled is True
    assert dlg.preview_canvas.text_content == "Banner Test"
    assert dlg.preview_canvas.logo_max_width == 250

    print("✓ test_watermark_live_preview_canvas: PASSED (Khởi tạo, đồng bộ thời gian thực và canvas preview hoạt động chuẩn xác)")


def test_subtitle_live_preview_and_dialog():
    """Kiểm tra SubtitlePreviewCanvas, SubtitlePreviewDialog và đồng bộ 2 chiều với MainWindow."""
    from gui import SubtitlePreviewCanvas, SubtitlePreviewDialog, MainWindow
    from PySide6.QtCore import Qt

    # 1. Kiểm tra SubtitlePreviewCanvas
    canvas = SubtitlePreviewCanvas()
    canvas.resize(360, 520)
    canvas.set_aspect_ratio("9:16")
    canvas.set_subtitle_config(
        sub_text="Phụ đề tiếng Việt mẫu để che kín sub cũ",
        alignment=2,
        margin_v=120,
        font_name="Arial",
        font_size=32,
        border_style=3,
        box_padding=8,
        text_color="#FFE600",
        bg_color="#000000"
    )
    assert canvas.sub_text == "Phụ đề tiếng Việt mẫu để che kín sub cũ"
    assert canvas.margin_v == 120
    assert canvas.border_style == 3
    assert canvas.box_padding == 8
    assert canvas.text_color == "#FFE600"
    assert canvas.bg_color == "#000000"

    # Kiểm tra tín hiệu margin_v_changed
    received_margin = []
    canvas.margin_v_changed.connect(lambda m: received_margin.append(m))
    canvas.margin_v_changed.emit(180)
    assert received_margin == [180]

    # 2. Kiểm tra SubtitlePreviewDialog
    test_sub_settings = {
        "position": "Cover Low Sub (120px)",
        "margin_v": 120,
        "alignment": 2,
        "box_padding": 8,
        "font_size": 34,
        "font_name": "Arial",
        "sub_style": "TikTok Black Box (Yellow Text) [Che Sub Chuẩn]",
        "border_style": 3,
        "text_color": "#FFE600",
        "bg_color": "#000000"
    }
    dlg = SubtitlePreviewDialog(None, video_paths=[], current_settings=test_sub_settings)
    assert hasattr(dlg, "canvas")
    assert hasattr(dlg, "slider_margin_v")
    assert hasattr(dlg, "spn_margin_v")
    assert hasattr(dlg, "slider_padding")
    assert hasattr(dlg, "cbo_style_preset")
    assert hasattr(dlg, "btn_apply")

    # Kiểm tra giá trị ban đầu đã load đúng
    assert dlg.spn_margin_v.value() == 120
    assert dlg.spn_padding.value() == 8
    assert dlg.spn_font_sz.value() == 34

    # Thay đổi Margin V sang 220px (Cover Mid Sub)
    dlg.cbo_preset_pos.setCurrentText("Cover Mid Sub (220px)")
    assert dlg.spn_margin_v.value() == 220

    # Thay đổi Box Padding sang 12px
    dlg.spn_padding.setValue(12)
    assert dlg.spn_padding.value() == 12

    # Áp dụng cấu hình
    dlg.action_apply_settings()
    res = dlg.result_settings
    assert res["margin_v"] == 220
    assert res["box_padding"] == 12
    assert res["border_style"] == 3
    assert res["text_color"] == "#FFE600"
    assert res["bg_color"] == "#000000"

    # 3. Kiểm tra MainWindow có nút btn_preview_sub và method action_open_subtitle_preview_dialog
    win = MainWindow()
    assert hasattr(win, "btn_preview_sub")
    assert hasattr(win, "action_open_subtitle_preview_dialog")
    assert win.btn_preview_sub.text().startswith("👁️ Preview Sub")

    print("✓ test_subtitle_live_preview_and_dialog: PASSED (Canvas, Dialog, Hardsub Box và đồng bộ 2 chiều hoàn hảo)")


def test_toggle_dubbing_ui():
    """Kiểm tra checkbox bật/tắt lồng tiếng (Voice Dubbing) trên MainWindow."""
    from gui import MainWindow
    win = MainWindow()

    # 1. Kiểm tra tồn tại checkbox chk_enable_dubbing và mặc định là True
    assert hasattr(win, "chk_enable_dubbing")
    assert win.chk_enable_dubbing.isChecked() is True
    assert win.cbo_voice.isEnabled() is True
    assert win.spn_ducking.isEnabled() is True

    # 2. Tắt lồng tiếng: chuyển sang False
    win.chk_enable_dubbing.setChecked(False)
    assert win.chk_enable_dubbing.isChecked() is False
    assert win.cbo_voice.isEnabled() is False
    assert win.spn_ducking.isEnabled() is False
    assert win.spn_delay.isEnabled() is False
    assert win.txt_clone.isEnabled() is False
    assert win.btn_browse_clone.isEnabled() is False
    assert "Preserves 100% original video audio" in win.lbl_dub_hint.text()

    # 3. Bật lại lồng tiếng: chuyển sang True
    win.chk_enable_dubbing.setChecked(True)
    assert win.chk_enable_dubbing.isChecked() is True
    assert win.cbo_voice.isEnabled() is True
    assert win.spn_ducking.isEnabled() is True
    assert win.spn_delay.isEnabled() is True
    assert win.txt_clone.isEnabled() is True
    assert win.btn_browse_clone.isEnabled() is True

    print("✓ test_toggle_dubbing_ui: PASSED (Bật/tắt lồng tiếng AI & giữ âm thanh gốc hoạt động chuẩn xác)")


if __name__ == "__main__":
    print("=== CHẠY KIỂM THỬ PHASE 7 ===")
    test_gui_syntax_and_structure()
    test_worker_signals_and_button_recovery()
    test_paste_links_dialog()
    test_cookie_button_and_management()
    test_worker_immediate_cancel()
    test_watermark_spinbox_and_persistence()
    test_watermark_live_preview_canvas()
    test_subtitle_live_preview_and_dialog()
    test_toggle_dubbing_ui()
    print("=== TẤT CẢ TEST ĐƠN VỊ PHASE 7 ĐÃ VƯỢT QUA ===")
