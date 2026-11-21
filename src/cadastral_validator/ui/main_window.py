"""Giao diện PySide6 — sidebar 6 phân hệ; Tab 3 hoạt động ở G1, các tab khác hiển thị
trạng thái 'Chưa triển khai' (không có nút giả)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtCore import QObject, Qt, QThread, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QFont
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QCheckBox, QComboBox, QFileDialog, QFrame,
                               QGridLayout, QGroupBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QListWidget,
                               QListWidgetItem, QMainWindow, QMessageBox, QPlainTextEdit, QProgressBar, QPushButton,
                               QSplitter, QStackedWidget, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from ..adapters.microstation_com import com_capability
from ..application.check_service import CheckOptions, run_check
from ..infrastructure.config import CONFIG_DIR, LOG_DIR, OUTPUT_DIR, load_crs_profiles
from ..infrastructure.logging_setup import setup_logging

STYLE = """
QWidget{font-family:'Segoe UI',Arial;font-size:10pt}
#side{background:#1f2937;color:#e5e7eb;border:none}
#side::item{padding:9px 10px}#side::item:selected{background:#f59e0b;color:#111827;border-radius:6px}
#brand{background:#111827;color:#fff;font-weight:600;padding:10px}
QGroupBox{font-weight:600;border:1px solid #d1d5db;border-radius:6px;margin-top:10px;padding-top:6px}
QGroupBox::title{subcontrol-origin:margin;left:8px;padding:0 4px}
QPushButton#primary{background:#2563eb;color:white;font-weight:600;padding:6px 14px;border-radius:4px}
QPushButton#primary:disabled{background:#93c5fd}
"""

TABS = [
    ("1  Chuyển GML/SHP → DGN", "G2", "Chưa triển khai: cần writer DGN V8 đã xác minh (MicroStation COM) và seed/Level được duyệt."),
    ("2  Xử lý chồng/hở", "G3", "Chưa triển khai: sửa có kiểm soát cần ChangeSet, phê duyệt và rollback."),
    ("3  Kiểm tra DGN", "G1", ""),
    ("4  Vẽ khung bản đồ", "G4", "Chưa triển khai: cần template khung đã đối chiếu TT 26/2024 (đã sửa đổi)."),
    ("5  So sánh bản đồ", "G5", "Chưa triển khai."),
    ("6  Trích lục thửa đất", "G6", "Chưa triển khai: cần mẫu trích lục được phê duyệt."),
]
SEV_VI = {"error": "Lỗi", "warning": "Cần xem", "info": "Thông tin"}
STATUS_VI = {"OK": "Đạt (nháp)", "CO_LOI": "Có lỗi", "CAN_XEM": "Cần xem", "DUNG_TIEN_KIEM": "Dừng tiền kiểm",
             "KHONG_DOC_DUOC": "Không đọc được"}


class Worker(QObject):
    progress = Signal(int, int, str)
    done = Signal(object, object)
    failed = Signal(str)

    def __init__(self, opts: CheckOptions):
        super().__init__()
        self.opts = opts
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):
        try:
            res, info = run_check(self.opts, progress=lambda k, n, s: self.progress.emit(k, n, s),
                                  should_stop=lambda: self._stop)
            self.done.emit(res, info)
        except Exception as e:  # báo lỗi rõ cho người dùng
            self.failed.emit(f"{type(e).__name__}: {e}")


class PlaceholderTab(QWidget):
    def __init__(self, title, gate, note):
        super().__init__()
        lay = QVBoxLayout(self)
        h = QLabel(title.split("  ", 1)[1])
        h.setFont(QFont("Segoe UI", 14, QFont.Bold))
        lay.addWidget(h)
        st = QLabel(f"Trạng thái: CHƯA TRIỂN KHAI — thuộc Gate {gate}.\n{note}")
        st.setWordWrap(True)
        st.setStyleSheet("color:#b45309;background:#fffbeb;border:1px solid #fcd34d;padding:10px;border-radius:6px")
        lay.addWidget(st)
        lay.addStretch(1)


class CheckTab(QWidget):
    def __init__(self):
        super().__init__()
        self.results = []
        self.info = None
        self.thread = None
        self.worker = None
        root = QVBoxLayout(self)
        title = QLabel("Kiểm tra DGN theo bộ quy tắc offline cấu hình")
        title.setFont(QFont("Segoe UI", 13, QFont.Bold))
        root.addWidget(title)
        note = QLabel("Chỉ đọc — không sửa tệp gốc. Bộ quy tắc nháp, chưa xác minh pháp lý; "
                      "không phải kết quả kiểm định/chứng nhận LANDINFO.")
        note.setStyleSheet("color:#b91c1c")
        note.setWordWrap(True)
        root.addWidget(note)

        g = QGroupBox("A. Tệp cần kiểm tra")
        gl = QGridLayout(g)
        self.inp = QLineEdit()
        self.inp.setPlaceholderText("Thư mục hoặc tệp .dgn / .cvp.json / .shp / .gml")
        b1 = QPushButton("Thư mục…"); b1.clicked.connect(self.pick_dir)
        b2 = QPushButton("Tệp…"); b2.clicked.connect(self.pick_files)
        gl.addWidget(QLabel("Nguồn"), 0, 0); gl.addWidget(self.inp, 0, 1); gl.addWidget(b1, 0, 2); gl.addWidget(b2, 0, 3)
        self.out = QLineEdit(str(OUTPUT_DIR))
        b3 = QPushButton("Chọn…"); b3.clicked.connect(self.pick_out)
        gl.addWidget(QLabel("Thư mục báo cáo"), 1, 0); gl.addWidget(self.out, 1, 1); gl.addWidget(b3, 1, 2)
        self.scale = QComboBox()
        self.scale.addItem("Theo hồ sơ Level (không có thì 1:1000)", None)
        for sc in ["1:200", "1:500", "1:1000", "1:2000", "1:5000", "1:10000"]:
            self.scale.addItem(sc, sc)
        self.crs = QComboBox(); self.crs.addItem("— chưa chọn —", None)
        for pid, p in load_crs_profiles().items():
            self.crs.addItem(p["name"], pid)
        self.crs_ok = QCheckBox("Tôi xác nhận CRS này đúng cho các tờ")
        gl.addWidget(QLabel("Tỷ lệ"), 2, 0); gl.addWidget(self.scale, 2, 1)
        gl.addWidget(QLabel("Hệ tọa độ"), 3, 0); gl.addWidget(self.crs, 3, 1); gl.addWidget(self.crs_ok, 3, 2, 1, 2)
        self.rp = QLineEdit(str(CONFIG_DIR / "rulepacks" / "son_la_draft.json"))
        gl.addWidget(QLabel("Bộ quy tắc"), 4, 0); gl.addWidget(self.rp, 4, 1)
        self.lvp = QComboBox(); self.lvp.addItem("Mặc định (config/levels.json)", None)
        for f in sorted((CONFIG_DIR / "level_profiles").glob("*.json")):
            self.lvp.addItem(f.stem, str(f))
        gl.addWidget(QLabel("Hồ sơ Level"), 6, 0); gl.addWidget(self.lvp, 6, 1)
        st, msg = com_capability()
        self.com_lbl = QLabel(f"MicroStation COM: {st} — {msg}")
        self.com_lbl.setWordWrap(True)
        self.com_lbl.setStyleSheet("color:#374151")
        gl.addWidget(self.com_lbl, 5, 0, 1, 4)
        root.addWidget(g)

        run = QHBoxLayout()
        self.btn = QPushButton("▶ Kiểm tra"); self.btn.setObjectName("primary"); self.btn.clicked.connect(self.start)
        self.stop_btn = QPushButton("Dừng"); self.stop_btn.setEnabled(False); self.stop_btn.clicked.connect(self.stop)
        self.bar = QProgressBar(); self.bar.setValue(0)
        run.addWidget(self.btn); run.addWidget(self.bar, 1); run.addWidget(self.stop_btn)
        root.addLayout(run)
        self.status = QLabel("Sẵn sàng.")
        root.addWidget(self.status)

        split = QSplitter(Qt.Vertical)
        self.sheets = QTableWidget(0, 9)
        self.sheets.setHorizontalHeaderLabels(["Tệp", "Kết quả", "Lỗi", "Cần xem", "Vùng", "Nhãn 13", "Nhãn 4",
                                               "Nhãn 2", "Ghi chú"])
        self.sheets.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.sheets.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.sheets.horizontalHeader().setSectionResizeMode(8, QHeaderView.Stretch)
        self.sheets.itemSelectionChanged.connect(self.fill_issues)
        split.addWidget(self.sheets)
        box = QWidget(); bl = QVBoxLayout(box); bl.setContentsMargins(0, 0, 0, 0)
        flt = QHBoxLayout()
        self.f_err = QCheckBox("Lỗi"); self.f_err.setChecked(True)
        self.f_warn = QCheckBox("Cần xem"); self.f_warn.setChecked(True)
        self.f_info = QCheckBox("Thông tin")
        self.search = QLineEdit(); self.search.setPlaceholderText("Tìm số thửa / mã lỗi / nội dung")
        for w in (self.f_err, self.f_warn, self.f_info):
            w.stateChanged.connect(self.fill_issues)
        self.search.textChanged.connect(self.fill_issues)
        flt.addWidget(self.f_err); flt.addWidget(self.f_warn); flt.addWidget(self.f_info); flt.addWidget(self.search, 1)
        self.b_html = QPushButton("Mở bản đồ HTML"); self.b_html.clicked.connect(self.open_html)
        self.b_xlsx = QPushButton("Mở Excel"); self.b_xlsx.clicked.connect(lambda: self.open_path("xlsx"))
        self.b_dir = QPushButton("Mở thư mục kết quả"); self.b_dir.clicked.connect(self.open_dir)
        for b in (self.b_html, self.b_xlsx, self.b_dir):
            b.setEnabled(False); flt.addWidget(b)
        bl.addLayout(flt)
        self.issues = QTableWidget(0, 6)
        self.issues.setHorizontalHeaderLabels(["Mức độ", "Mã", "Nội dung", "X", "Y", "ID"])
        self.issues.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.issues.setSortingEnabled(True)
        self.issues.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.issues.setWordWrap(True)
        bl.addWidget(self.issues)
        split.addWidget(box)
        split.setSizes([180, 320])
        root.addWidget(split, 1)
        self.log = QPlainTextEdit(); self.log.setReadOnly(True); self.log.setMaximumHeight(90)
        root.addWidget(self.log)

    # ---------------------------------------------------------- chọn tệp
    def pick_dir(self):
        d = QFileDialog.getExistingDirectory(self, "Chọn thư mục DGN/JSON")
        if d:
            self.inp.setText(d)

    def pick_files(self):
        fs, _ = QFileDialog.getOpenFileNames(self, "Chọn tệp", "", "Dữ liệu (*.dgn *.json *.shp *.gml)")
        if fs:
            self.inp.setText(";".join(fs))

    def pick_out(self):
        d = QFileDialog.getExistingDirectory(self, "Chọn thư mục báo cáo")
        if d:
            self.out.setText(d)

    # ---------------------------------------------------------- chạy
    def options(self) -> CheckOptions:
        inputs = [Path(p) for p in self.inp.text().split(";") if p.strip()]
        if not inputs:
            raise ValueError("Chưa chọn nguồn dữ liệu.")
        missing = [str(p) for p in inputs if not p.exists()]
        if missing:
            raise ValueError("Không tìm thấy: " + ", ".join(missing))
        crs = self.crs.currentData()
        if self.crs_ok.isChecked() and not crs:
            raise ValueError("Đã tích xác nhận CRS nhưng chưa chọn hệ tọa độ.")
        return CheckOptions(inputs=inputs, out_dir=Path(self.out.text()), rulepack=Path(self.rp.text()),
                            scale=self.scale.currentData() or "1:1000",
                            scale_from_cli=self.scale.currentData() is not None, crs_profile_id=crs,
                            crs_confirmed=self.crs_ok.isChecked() and bool(crs),
                            levels_path=Path(self.lvp.currentData()) if self.lvp.currentData() else None)

    def start(self):
        try:
            opts = self.options()
        except ValueError as e:
            QMessageBox.warning(self, "Thiếu thông tin", str(e))
            return
        self.btn.setEnabled(False); self.stop_btn.setEnabled(True)
        self.status.setText("Đang kiểm tra…")
        self.thread = QThread(self)
        self.worker = Worker(opts)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.progress.connect(self.on_progress)
        self.worker.done.connect(self.on_done)
        self.worker.failed.connect(self.on_failed)
        self.worker.done.connect(self.thread.quit)
        self.worker.failed.connect(self.thread.quit)
        self.thread.start()

    def stop(self):
        if self.worker:
            self.worker.stop()
            self.status.setText("Sẽ dừng ở checkpoint an toàn (sau tệp hiện tại)…")

    def on_progress(self, k, n, name):
        self.bar.setMaximum(n); self.bar.setValue(k - 1)
        self.status.setText(f"Kiểm tra {k}/{n}: {name}")
        self.log.appendPlainText(f"[{k}/{n}] {name}")

    def on_failed(self, msg):
        self.btn.setEnabled(True); self.stop_btn.setEnabled(False)
        self.status.setText("Lỗi khi chạy.")
        QMessageBox.critical(self, "Lỗi", msg)

    def on_done(self, results, info):
        self.btn.setEnabled(True); self.stop_btn.setEnabled(False)
        self.bar.setMaximum(max(1, len(results))); self.bar.setValue(len(results))
        self.show_results(results, info)

    def show_results(self, results, info):
        self.results, self.info = results, info
        self.sheets.setRowCount(0)
        for r in results:
            row = self.sheets.rowCount(); self.sheets.insertRow(row)
            s = r.stats
            vals = [r.file_name, STATUS_VI.get(r.status, r.status), r.count("error"), r.count("warning"),
                    s.get("so_vung", ""), s.get("nhan_lop13", ""), s.get("nhan_lop4", ""), s.get("nhan_lop2", ""),
                    r.message]
            for c, v in enumerate(vals):
                it = QTableWidgetItem(str(v))
                if c == 8 and r.message:
                    it.setToolTip(r.message)
                if c == 1:
                    it.setForeground(Qt.darkGreen if r.status == "OK" else Qt.red)
                self.sheets.setItem(row, c, it)
        n_err = sum(r.count("error") for r in results)
        self.status.setText(f"Xong {len(results)} tệp — {n_err} lỗi. Báo cáo: {info['paths'].get('xlsx')}")
        for b in (self.b_html, self.b_xlsx, self.b_dir):
            b.setEnabled(True)
        if results:
            self.sheets.selectRow(0)
        self.fill_issues()

    def current(self):
        rows = self.sheets.selectionModel().selectedRows() if self.sheets.selectionModel() else []
        return self.results[rows[0].row()] if rows and self.results else None

    def fill_issues(self):
        r = self.current()
        self.issues.setSortingEnabled(False)
        self.issues.setRowCount(0)
        if r is None:
            return
        allow = {k for k, w in (("error", self.f_err), ("warning", self.f_warn), ("info", self.f_info)) if w.isChecked()}
        q = self.search.text().strip().lower()
        pn = {p.internal_id: (p.parcel_no or "") for p in r.parcels}
        if r.status == "KHONG_DOC_DUOC" and r.message:
            self.issues.insertRow(0)
            for c, v in enumerate(["Lỗi đọc tệp", "KHONG_DOC_DUOC", r.message, "", "", ""]):
                it = QTableWidgetItem(v)
                it.setToolTip(r.message)
                self.issues.setItem(0, c, it)
            self.issues.resizeRowToContents(0)
        for i in r.issues:
            if i.severity not in allow:
                continue
            hay = f"{i.code} {i.message} {' '.join(pn.get(x, '') for x in i.parcel_ids)}".lower()
            if q and q not in hay:
                continue
            row = self.issues.rowCount(); self.issues.insertRow(row)
            for c, v in enumerate([SEV_VI.get(i.severity, i.severity), i.code, i.message,
                                   "" if i.x is None else f"{i.x:.3f}", "" if i.y is None else f"{i.y:.3f}",
                                   i.issue_id]):
                self.issues.setItem(row, c, QTableWidgetItem(v))
        self.issues.setSortingEnabled(True)

    def open_path(self, key):
        if self.info and key in self.info["paths"]:
            QDesktopServices.openUrl(QUrl.fromLocalFile(self.info["paths"][key]))

    def open_html(self):
        r = self.current()
        if r and self.info:
            self.open_path(f"html:{r.sheet_id}")

    def open_dir(self):
        Path(self.out.text()).mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(self.out.text()))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CadastralValidatorPro 0.2.2 — Kiểm tra dữ liệu bản đồ địa chính")
        self.resize(1280, 800)
        w = QWidget(); lay = QHBoxLayout(w); lay.setContentsMargins(0, 0, 0, 0); lay.setSpacing(0)
        left = QFrame(); left.setFixedWidth(270); ll = QVBoxLayout(left); ll.setContentsMargins(0, 0, 0, 0)
        brand = QLabel("CadastralValidatorPro"); brand.setObjectName("brand"); ll.addWidget(brand)
        self.side = QListWidget(); self.side.setObjectName("side"); self.side.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff); ll.addWidget(self.side)
        self.stack = QStackedWidget()
        for title, gate, note in TABS:
            item = QListWidgetItem(title if gate == "G1" else f"{title}  ·  chưa có")
            self.side.addItem(item)
            self.stack.addWidget(CheckTab() if gate == "G1" else PlaceholderTab(title, gate, note))
        self.side.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.side.setCurrentRow(2)
        lay.addWidget(left); lay.addWidget(self.stack, 1)
        self.setCentralWidget(w)
        self.statusBar().showMessage("Chế độ offline · không gửi dữ liệu ra Internet")


def run_gui() -> int:
    try:
        setup_logging(LOG_DIR)
    except OSError:
        pass
    app = QApplication.instance() or QApplication(sys.argv)
    app.setStyleSheet(STYLE)
    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")
    raise SystemExit(run_gui())
