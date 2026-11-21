"""GUI khởi động (offscreen) và Tab 3 hiển thị kết quả thật từ pipeline."""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from fixtures.builders import grid_elements, replace_text, sheet  # noqa: E402
from cadastral_validator.adapters.dgn_exchange import save_exchange  # noqa: E402
from cadastral_validator.application.check_service import CheckOptions, run_check  # noqa: E402


def test_gui_six_tabs_and_tab3_results(tmp_path):
    from PySide6.QtWidgets import QApplication
    from cadastral_validator.ui.main_window import CheckTab, MainWindow
    app = QApplication.instance() or QApplication([])
    win = MainWindow()
    assert win.side.count() == 6
    assert win.stack.currentIndex() == 2
    tab = win.stack.widget(2)
    assert isinstance(tab, CheckTab)
    save_exchange(sheet(replace_text(grid_elements(), "T4_3", "412.5"), "DC2"), tmp_path / "DC2.json")
    res, info = run_check(CheckOptions(inputs=[tmp_path / "DC2.json"], out_dir=tmp_path / "o", html=False))
    tab.show_results(res, info)
    assert tab.sheets.rowCount() == 1
    assert tab.issues.rowCount() >= 1
    tab.search.setText("SAI_DIEN_TICH")
    assert tab.issues.rowCount() == 1
    win.close()
    app.processEvents()
