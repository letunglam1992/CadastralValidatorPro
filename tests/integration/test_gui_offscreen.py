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


def test_gui_shows_full_read_error(tmp_path):
    from PySide6.QtWidgets import QApplication
    from cadastral_validator.ui.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    dgn = tmp_path / "DC9.dgn"
    dgn.write_bytes(bytes.fromhex("d0cf11e0a1b11ae1") + b"\0" * 64)
    res, info = run_check(CheckOptions(inputs=[dgn], out_dir=tmp_path / "o", html=False))
    win = MainWindow()
    tab = win.stack.widget(2)
    tab.show_results(res, info)
    assert tab.issues.rowCount() == 1
    assert "XuatThuMucJSON" in tab.issues.item(0, 2).text()
    assert tab.sheets.item(0, 8).toolTip() == res[0].message
    win.close()
    win.deleteLater()
    app.processEvents()


def test_gui_fix_tab_flow(tmp_path):
    from PySide6.QtWidgets import QApplication
    from cadastral_validator.ui.main_window import MainWindow
    from cadastral_validator.application.fix_service import analyze, evaluate_each
    import copy
    from fixtures.builders import X0, Y0, W
    app = QApplication.instance() or QApplication([])
    els = copy.deepcopy(grid_elements())
    for e in els:
        if e.id == "L1":
            e.coords = [(X0 + W, Y0 + 0.4), e.coords[1]]
    p = tmp_path / "u.json"
    save_exchange(sheet(els, "DC_U"), p)
    win = MainWindow()
    tab = win.stack.widget(1)
    assert type(tab).__name__ == "FixTab"
    s = analyze(p, CheckOptions(inputs=[p], out_dir=tmp_path, crs_profile_id="VN2000_TM3_104", crs_confirmed=True))
    tab._found(s)
    assert tab.table.rowCount() == 1
    tab._evaluated(evaluate_each(s))
    tab.check(lambda f: f.action != "SNAP")
    tab.simulate()
    assert "1 → 0" in tab.status.text()
    win.close(); win.deleteLater(); app.processEvents()
