"""Điểm khởi động GUI (dùng cho PyInstaller và chạy trực tiếp)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from cadastral_validator.ui.main_window import run_gui  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(run_gui())
