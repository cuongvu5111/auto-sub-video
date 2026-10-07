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


if __name__ == "__main__":
    print("=== CHẠY KIỂM THỬ PHASE 7 ===")
    test_gui_syntax_and_structure()
    test_worker_signals_and_button_recovery()
    print("=== TẤT CẢ TEST ĐƠN VỊ PHASE 7 ĐÃ VƯỢT QUA ===")
