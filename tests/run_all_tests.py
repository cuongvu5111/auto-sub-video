"""
Bộ chạy kiểm thử toàn diện (Test Suite Runner) cho AutoSub Dubbing Studio.
Thực thi tuần tự các bài kiểm thử từ Phase 2 đến Phase 7.
"""

import sys
import subprocess
from pathlib import Path

# Cấu hình encoding UTF-8 cho console Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

ROOT_DIR = Path(__file__).resolve().parent.parent
TESTS_DIR = ROOT_DIR / "tests"

TEST_FILES = [
    "test_phase2.py",
    "test_phase3.py",
    "test_phase4.py",
    "test_phase5.py",
    "test_phase6.py",
    "test_phase7.py",
    "test_reliability.py",
]


def run_all():
    print("=" * 65)
    print("      BẮT ĐẦU CHẠY KIỂM THỬ TOÀN TRÌNH AUTODUB STUDIO")
    print("=" * 65)

    passed_count = 0
    total_count = len(TEST_FILES)

    for test_file in TEST_FILES:
        test_path = TESTS_DIR / test_file
        print(f"\n--- Đang chạy: {test_file} ---")
        
        result = subprocess.run(
            [sys.executable, str(test_path)],
            cwd=str(ROOT_DIR),
            text=True,
            capture_output=True,
            encoding="utf-8"
        )
        
        if result.returncode == 0:
            passed_count += 1
            print(result.stdout.strip())
            print(f"-> KẾT QUẢ: [ĐẠT] ({test_file})")
        else:
            print(result.stdout.strip())
            print(result.stderr.strip(), file=sys.stderr)
            print(f"-> KẾT QUẢ: [THẤT BẠI] ({test_file})")

    print("\n" + "=" * 65)
    print(f"KẾT QUẢ TỔNG KẾT: {passed_count}/{total_count} BÀI TEST THÀNH CÔNG")
    print("=" * 65)

    if passed_count == total_count:
        print("🎉 TẤT CẢ MODULE HOẠT ĐỘNG HOÀN HẢO!")
        return 0
    else:
        print("⚠️ Có bài kiểm thử thất bại, vui lòng kiểm tra chi tiết ở trên.")
        return 1


if __name__ == "__main__":
    sys.exit(run_all())
