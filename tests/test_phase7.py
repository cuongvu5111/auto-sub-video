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


if __name__ == "__main__":
    print("=== CHẠY KIỂM THỬ PHASE 7 ===")
    test_gui_syntax_and_structure()
    print("=== TẤT CẢ TEST ĐƠN VỊ PHASE 7 ĐÃ VƯỢT QUA ===")
