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


if __name__ == "__main__":
    print("=== CHẠY KIỂM THỬ PHASE 7 ===")
    test_gui_syntax_and_structure()
    test_worker_signals_and_button_recovery()
    test_paste_links_dialog()
    test_cookie_button_and_management()
    print("=== TẤT CẢ TEST ĐƠN VỊ PHASE 7 ĐÃ VƯỢT QUA ===")
