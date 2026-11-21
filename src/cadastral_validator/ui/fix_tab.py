"""Tab 2 — Xử lý đầu mút treo có kiểm soát (đề xuất → duyệt → mô phỏng → ChangeSet trên bản sao)."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, Qt, QThread, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QFont
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog, QGridLayout,
                               QGroupBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMessageBox, QPushButton,
                               QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from ..application.check_service import CheckOptions
from ..application.fix_service import analyze, evaluate_each, export, simulate
from ..infrastructure.config import CONFIG_DIR, OUTPUT_DIR, load_crs_profiles

ACTION_VI = {"TRIM": "Cắt nét thừa", "EXTEND": "Kéo dài nét hụt", "JOIN": "Nối 2 đầu treo", "SNAP": "Bắt điểm gần nhất"}


class _Job(QObject):
    done = Signal(object)
    failed = Signal(str)
    progress = Signal(int, int)

    def __init__(self, fn):
        super().__init__()
        self.fn = fn

    def run(self):
        try:
            self.done.emit(self.fn(lambda k, n, *_: self.progress.emit(k, n)))
        except Exception as e:  # hiện lỗi rõ cho người dùng
            self.failed.emit(f"{type(e).__name__}: {e}")


class FixTab(QWidget):
    COLS = ["Duyệt", "Thao tác", "Khoảng hở (m)", "Phần tử", "X trước", "Y trước", "X sau", "Y sau",
            "Tác động (đánh giá riêng)", "Ghi chú", "Mã"]

    def __init__(self):
        super().__init__()
        self.session = None
        self.impacts = {}
        self._threads = []
        root = QVBoxLayout(self)
        t = QLabel("Xử lý đầu mút treo có kiểm soát (mức rủi ro B — duyệt từng đối tượng)")
        t.setFont(QFont("Segoe UI", 13, QFont.Bold))
        root.addWidget(t)
        n = QLabel("Không sửa tệp gốc. Kết quả là ChangeSet + BẢN SAO DGN + macro áp dụng/hoàn tác chạy trên bản sao. "
                   "Không tự cắt/lấp thửa, không đổi diện tích pháp lý.")
        n.setWordWrap(True)
        n.setStyleSheet("color:#b91c1c")
        root.addWidget(n)

        g = QGroupBox("A. Tờ cần xử lý")
        gl = QGridLayout(g)
        self.src = QLineEdit()
        self.src.setPlaceholderText("Tệp .dgn (đã có <tên>.dgn.cvp.json cạnh tệp) hoặc .cvp.json")
        b = QPushButton("Chọn tệp…"); b.clicked.connect(self.pick)
        gl.addWidget(QLabel("Tệp"), 0, 0); gl.addWidget(self.src, 0, 1); gl.addWidget(b, 0, 2)
        self.lvp = QComboBox(); self.lvp.addItem("Mặc định (config/levels.json)", None)
        for f in sorted((CONFIG_DIR / "level_profiles").glob("*.json")):
            self.lvp.addItem(f.stem, str(f))
        i = self.lvp.findText("son_la_ten_level_chung")
        if i >= 0:
            self.lvp.setCurrentIndex(i)
        gl.addWidget(QLabel("Hồ sơ Level"), 1, 0); gl.addWidget(self.lvp, 1, 1)
        self.crs = QComboBox(); self.crs.addItem("— chưa chọn —", None)
        for pid, p in load_crs_profiles().items():
            self.crs.addItem(p["name"], pid)
        self.crs_ok = QCheckBox("Tôi xác nhận CRS")
        gl.addWidget(QLabel("Hệ tọa độ"), 2, 0); gl.addWidget(self.crs, 2, 1); gl.addWidget(self.crs_ok, 2, 2)
        self.gap = QDoubleSpinBox(); self.gap.setRange(0.01, 5.0); self.gap.setSingleStep(0.1); self.gap.setValue(1.0)
        self.gap.setSuffix(" m")
        gl.addWidget(QLabel("Ngưỡng khoảng hở"), 3, 0); gl.addWidget(self.gap, 3, 1)
        self.out = QLineEdit(str(OUTPUT_DIR / "ChangeSet"))
        gl.addWidget(QLabel("Thư mục ChangeSet"), 4, 0); gl.addWidget(self.out, 4, 1)
        root.addWidget(g)

        row = QHBoxLayout()
        self.b_find = QPushButton("Tìm đề xuất"); self.b_find.setObjectName("primary"); self.b_find.clicked.connect(self.find)
        self.b_all = QPushButton("Chọn tất cả"); self.b_all.clicked.connect(lambda: self.check(lambda f: True))
        self.b_safe = QPushButton("Chọn không lỗi mới, trừ SNAP")
        self.b_safe.clicked.connect(lambda: self.check(lambda f: f.action != "SNAP" and not self.impacts.get(f.fix_id, {}).get("loi_moi")))
        self.b_none = QPushButton("Bỏ chọn"); self.b_none.clicked.connect(lambda: self.check(lambda f: False))
        self.b_eval = QPushButton("Đánh giá từng đề xuất"); self.b_eval.clicked.connect(self.evaluate)
        self.b_sim = QPushButton("Mô phỏng"); self.b_sim.clicked.connect(self.simulate)
        self.b_exp = QPushButton("Xuất ChangeSet + bản sao"); self.b_exp.clicked.connect(self.export)
        for w in (self.b_find, self.b_all, self.b_safe, self.b_none, self.b_eval, self.b_sim, self.b_exp):
            row.addWidget(w)
        row.addStretch(1)
        root.addLayout(row)
        self.status = QLabel("Chọn tệp rồi bấm Tìm đề xuất.")
        self.status.setWordWrap(True)
        root.addWidget(self.status)
        self.table = QTableWidget(0, len(self.COLS))
        self.table.setHorizontalHeaderLabels(self.COLS)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(8, QHeaderView.Stretch)
        root.addWidget(self.table, 1)
        self._enable(False)

    def _enable(self, on: bool):
        for w in (self.b_all, self.b_safe, self.b_none, self.b_eval, self.b_sim, self.b_exp):
            w.setEnabled(on)

    def pick(self):
        f, _ = QFileDialog.getOpenFileName(self, "Chọn tờ", "", "Bản đồ (*.dgn *.json)")
        if f:
            self.src.setText(f)

    def _options(self) -> CheckOptions:
        p = Path(self.src.text().strip())
        if not p.exists():
            raise ValueError("Chưa chọn tệp hoặc tệp không tồn tại.")
        crs = self.crs.currentData()
        return CheckOptions(inputs=[p], out_dir=Path(self.out.text()), scale_from_cli=False,
                            crs_profile_id=crs, crs_confirmed=self.crs_ok.isChecked() and bool(crs),
                            levels_path=Path(self.lvp.currentData()) if self.lvp.currentData() else None)

    def _run(self, fn, on_done, label):
        self.status.setText(label)
        self.b_find.setEnabled(False); self._enable(False)
        th = QThread(self); job = _Job(fn); job.moveToThread(th)
        th.started.connect(job.run)
        job.progress.connect(lambda k, n: self.status.setText(f"{label} {k}/{n}"))
        job.done.connect(on_done); job.failed.connect(self._fail)
        job.done.connect(th.quit); job.failed.connect(th.quit)
        self._threads.append((th, job))
        th.start()

    def _fail(self, msg):
        self.b_find.setEnabled(True); self._enable(self.session is not None)
        self.status.setText("Lỗi.")
        QMessageBox.critical(self, "Lỗi", msg)

    def find(self):
        try:
            o = self._options()
        except ValueError as e:
            QMessageBox.warning(self, "Thiếu thông tin", str(e)); return
        gap = self.gap.value()
        self._run(lambda prog: analyze(o.inputs[0], o, gap), self._found, "Đang tìm đề xuất…")

    def _found(self, s):
        self.session, self.impacts = s, {}
        self.b_find.setEnabled(True); self._enable(bool(s.proposals))
        self.fill()
        by = {}
        for k in s.skipped:
            r = k["reason"].split(" ")[0:2]
            by[" ".join(r)] = by.get(" ".join(r), 0) + 1
        self.status.setText(f"{s.sheet.file_name}: {s.before.stats.get('dau_mut_treo')} đầu mút treo → "
                            f"{len(s.proposals)} đề xuất (ngưỡng {s.max_gap} m). Không đề xuất: "
                            + ", ".join(f"{k} {v}" for k, v in by.items()))

    def fill(self):
        s = self.session
        self.table.setRowCount(0)
        for f in s.proposals:
            r = self.table.rowCount(); self.table.insertRow(r)
            chk = QTableWidgetItem(); chk.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            chk.setCheckState(Qt.Checked if f.approved else Qt.Unchecked)
            self.table.setItem(r, 0, chk)
            imp = self.impacts.get(f.fix_id, {}).get("tom_tat", "")
            vals = [ACTION_VI.get(f.action, f.action), f"{f.gap_m:.3f}", f.element_id, f"{f.before[0]:.3f}",
                    f"{f.before[1]:.3f}", f"{f.after[0]:.3f}", f"{f.after[1]:.3f}", imp, f.note, f.fix_id]
            for c, v in enumerate(vals, 1):
                it = QTableWidgetItem(v)
                if c == 8 and "MỚI" in v:
                    it.setForeground(Qt.red)
                self.table.setItem(r, c, it)

    def _sync(self):
        for r, f in enumerate(self.session.proposals):
            f.approved = self.table.item(r, 0).checkState() == Qt.Checked

    def check(self, pred):
        for r, f in enumerate(self.session.proposals):
            self.table.item(r, 0).setCheckState(Qt.Checked if pred(f) else Qt.Unchecked)

    def evaluate(self):
        self._sync()
        s = self.session
        self._run(lambda prog: evaluate_each(s, prog), self._evaluated, "Đang đánh giá…")

    def _evaluated(self, imp):
        self.impacts = imp
        self.b_find.setEnabled(True); self._enable(True)
        self.fill()
        bad = sum(1 for v in imp.values() if v["loi_moi"])
        self.status.setText(f"Đã đánh giá {len(imp)} đề xuất; {bad} đề xuất làm phát sinh lỗi mới (chữ đỏ).")

    def simulate(self):
        self._sync()
        _after, imp = simulate(self.session)
        self.status.setText(
            f"Mô phỏng {imp['so_de_xuat_duyet']} đề xuất: đầu mút treo {imp['truoc']['dau_mut_treo']} → "
            f"{imp['sau']['dau_mut_treo']}; vùng {imp['truoc']['vung']} → {imp['sau']['vung']}; lỗi "
            f"{imp['truoc']['loi']} → {imp['sau']['loi']}. Lỗi mới: {imp['loi_moi_phat_sinh'] or 'không'}. "
            + imp.get("canh_bao", ""))

    def export(self):
        self._sync()
        n = sum(f.approved for f in self.session.proposals)
        if n == 0:
            QMessageBox.warning(self, "Chưa duyệt", "Chưa chọn đề xuất nào."); return
        if QMessageBox.question(self, "Xác nhận", f"Xuất ChangeSet gồm {n} sửa đổi đã duyệt?\n"
                                "Tệp gốc không bị thay đổi; phần mềm tạo BẢN SAO DGN và macro áp dụng/hoàn tác."
                                ) != QMessageBox.Yes:
            return
        try:
            cs = export(self.session, Path(self.out.text()))
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"{type(e).__name__}: {e}"); return
        d = Path(cs.outputs["changeset_json"]).parent
        self.status.setText(f"Đã xuất {cs.changeset_id} vào {d}. Mở bản sao trong MicroStation, nạp CVP_ApDung.bas, "
                            f"chạy ApDungChangeSet; sau đó xuất lại bản sao bằng macro và kiểm tra lại ở Tab 3.")
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(d)))
