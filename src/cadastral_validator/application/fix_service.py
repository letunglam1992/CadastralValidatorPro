"""Tab 2 — quy trình sửa có kiểm soát:
chọn lỗi → đề xuất → (người dùng duyệt) → mô phỏng tác động → xuất ChangeSet + BẢN SAO DGN
+ macro áp dụng/hoàn tác (chạy trên bản sao) → người dùng xuất lại bản sao → kiểm tra lại.

Không bao giờ ghi vào tệp nguồn. Macro tự từ chối chạy nếu tên tệp không chứa "_BANSAO".
"""
from __future__ import annotations

import collections
import json
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..adapters.dgn_probe import sha256_file
from ..domain import topology as topo
from ..domain.fixes import ChangeSet, FixProposal, apply_fixes, propose_dangle_fixes
from ..domain.level_resolve import resolve_levels
from ..domain.models import MapSheet, SheetResult
from ..domain.rules import load_rulepack
from ..infrastructure.config import load_app_config
from .check_service import CheckOptions, load_sheet
from .validate_service import Validator


@dataclass
class FixSession:
    sheet: MapSheet
    source_path: Path
    before: SheetResult
    proposals: list[FixProposal]
    skipped: list[dict]
    options: CheckOptions
    validator: Validator
    max_gap: float


def _prepare_sheet(path: Path, o: CheckOptions, cfg) -> MapSheet:
    sheet, _ = load_sheet(path, o)
    lv = cfg.levels
    sheet.area_reference = o.area_reference or lv.area_reference or "grid"
    mh = o.mean_height_m if o.mean_height_m is not None else lv.mean_height_m
    if isinstance(mh, str) and mh.startswith("auto:"):
        from ..domain.level_resolve import auto_mean_height
        mh, _n = auto_mean_height(sheet, {x.strip() for x in mh[5:].split(",")})
    sheet.mean_height_m = mh
    if not o.scale_from_cli and lv.scale:
        sheet.scale = lv.scale
    return sheet


def analyze(path: Path, o: CheckOptions, max_gap: float = 1.0) -> FixSession:
    cfg = load_app_config(levels_path=o.levels_path)
    pack = load_rulepack(o.rulepack)
    validator = Validator(cfg, pack)
    sheet = _prepare_sheet(path, o, cfg)
    before = validator.validate(sheet)
    params = pack.params_for_scale(sheet.scale)
    lv, _ = resolve_levels(cfg.levels, sheet)
    b_levels = set(lv.boundary_levels) | (lv.frame_levels if params.get("include_frame_in_noding") else set())
    frame = topo.frame_polygon(topo.collect_lines(sheet.elements, lv.frame_levels))
    lw = topo.build_regions(topo.collect_lines(sheet.elements, b_levels), params["snap_tolerance_m"],
                            frame.exterior if frame is not None else None, params["dangle_near_frame_m"])
    props, skipped = propose_dangle_fixes(sheet, set(lv.boundary_levels), lw.dangles, max_gap,
                                          vertex_snap=params["snap_tolerance_m"])
    return FixSession(sheet, path, before, props, skipped, o, validator, max_gap)


def _count(res: SheetResult) -> dict:
    c = collections.Counter(i.code for i in res.issues if i.severity == "error")
    return {"vung": res.stats.get("so_vung"), "dau_mut_treo": res.stats.get("dau_mut_treo"),
            "loi": sum(c.values()), "theo_ma": dict(c)}


def simulate(s: FixSession) -> tuple[SheetResult, dict]:
    """Áp dụng các đề xuất đã duyệt lên bản sao trong bộ nhớ, kiểm tra lại, so sánh trước/sau."""
    approved = [p for p in s.proposals if p.approved]
    after_sheet = apply_fixes(s.sheet, approved)
    after = s.validator.validate(after_sheet)
    b, a = _count(s.before), _count(after)
    before_ids = {i.issue_id for i in s.before.issues}
    new = [i for i in after.issues if i.issue_id not in before_ids and i.severity == "error"
           and i.code != "DAU_MUT_TREO"]
    new_by = collections.Counter(i.code for i in new)
    impact = {"so_de_xuat_duyet": len(approved), "truoc": b, "sau": a,
              "loi_moi_phat_sinh": dict(new_by),
              "canh_bao": ("Có lỗi MỚI phát sinh sau khi sửa (thường do khép vùng làm lộ thửa thiếu/trùng nhãn) — "
                           "xem danh sách trước khi áp dụng." if new else "")}
    return after, impact


def evaluate_each(s: FixSession, progress=None) -> dict[str, dict]:
    """Tác động RIÊNG của từng đề xuất (áp dụng một mình): số đầu mút treo giảm, lỗi mới phát sinh."""
    import copy as _copy
    base_ids = {i.issue_id for i in s.before.issues}
    base_dm = s.before.stats.get("dau_mut_treo") or 0
    out = {}
    for k, fp in enumerate(s.proposals, 1):
        if progress:
            progress(k, len(s.proposals), fp.fix_id)
        one = _copy.copy(fp)
        one.approved = True
        res = s.validator.validate(apply_fixes(s.sheet, [one]))
        new = collections.Counter(i.code for i in res.issues if i.issue_id not in base_ids
                                  and i.severity == "error" and i.code != "DAU_MUT_TREO")
        out[fp.fix_id] = {"giam_dau_mut_treo": base_dm - (res.stats.get("dau_mut_treo") or 0),
                          "loi_moi": dict(new),
                          "tom_tat": (f"−{base_dm - (res.stats.get('dau_mut_treo') or 0)} treo"
                                      + ("; MỚI: " + ", ".join(f"{c}×{n}" for c, n in new.items()) if new else ""))}
    return out


VBA_HEADER = '''Attribute VB_Name = "{mod}"
' =============================================================================
' CadastralValidatorPro - {title}
' ChangeSet: {cs}  | To: {sheet} | Tao luc: {ts}
' CHI CHAY TREN BAN SAO: ten tep dang mo phai chua "_BANSAO". Truoc khi sua tung dinh,
' macro kiem tra toa do hien tai khop gia tri "truoc" (sai lech <= 1 mm), neu khong khop -> bo qua.
' TRANG THAI: NOT_TESTED tren MicroStation that.
' =============================================================================
Option Explicit

Private nOk As Long, nLech As Long, nLoi As Long, rep As String

Private Sub Sua(ByVal id As String, ByVal idx As Long, ByVal xb As Double, ByVal yb As Double, _
                ByVal xa As Double, ByVal ya As Double)
    Dim el As Element, v() As Point3d, p As Point3d, i As Long
    On Error GoTo Loi
    Set el = ActiveModelReference.GetElementByID(DLongFromString(id))
    v = el.AsVertexList.GetVertices
    If idx < 0 Then i = UBound(v) Else i = LBound(v) + idx
    If Abs(v(i).X - xb) > 0.001 Or Abs(v(i).Y - yb) > 0.001 Then
        nLech = nLech + 1
        rep = rep & id & ": LECH (toa do hien tai khac gia tri truoc)" & vbLf
        Exit Sub
    End If
    p = v(i)
    p.X = xa: p.Y = ya
    el.AsVertexList.ModifyVertex i, p
    el.Rewrite
    nOk = nOk + 1
    Exit Sub
Loi:
    nLoi = nLoi + 1
    rep = rep & id & ": LOI " & Err.Description & vbLf
End Sub

Public Sub {sub}()
    If InStr(1, ActiveDesignFile.Name, "_BANSAO", vbTextCompare) = 0 Then
        MsgBox "Tep dang mo khong phai BAN SAO (ten phai chua _BANSAO). Dung lai de bao ve tep goc.", vbCritical, "CVP"
        Exit Sub
    End If
    nOk = 0: nLech = 0: nLoi = 0: rep = ""
'''

VBA_FOOTER = '''    MsgBox "CVP {title}: thanh cong " & nOk & ", lech " & nLech & ", loi " & nLoi & vbLf & vbLf & rep, _
           vbInformation, "CVP"
End Sub
'''


def build_macro(cs: ChangeSet, rollback: bool) -> str:
    mod = "CVP_HoanTac" if rollback else "CVP_ApDung"
    sub = "HoanTacChangeSet" if rollback else "ApDungChangeSet"
    title = "Hoan tac ChangeSet" if rollback else "Ap dung ChangeSet"
    lines = [VBA_HEADER.format(mod=mod, title=title, cs=cs.changeset_id, sheet=cs.sheet_id, ts=cs.created_at,
                               sub=sub)]
    for f in cs.fixes:
        if not f.approved:
            continue
        b, a = (f.after, f.before) if rollback else (f.before, f.after)
        lines.append(f'    Sua "{f.element_id}", {0 if f.vertex_index == 0 else -1}, {b[0]:.6f}, {b[1]:.6f}, '
                     f'{a[0]:.6f}, {a[1]:.6f}   \' {f.action} {f.fix_id}\n')
    lines.append(VBA_FOOTER.format(title=title))
    text = "".join(lines)
    assert all(ord(ch) < 128 for ch in text)
    return text.replace("\r\n", "\n").replace("\n", "\r\n")


def export(s: FixSession, out_dir: Path, approved_by: str = "người dùng") -> ChangeSet:
    approved = [p for p in s.proposals if p.approved]
    if not approved:
        raise ValueError("Chưa duyệt đề xuất nào.")
    after, impact = simulate(s)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    cs = ChangeSet(changeset_id=f"CS_{s.sheet.sheet_id}_{ts}", created_at=datetime.now().isoformat(timespec="seconds"),
                   sheet_id=s.sheet.sheet_id, source_file=str(s.source_path),
                   source_sha256=sha256_file(s.source_path) if s.source_path.exists() else None,
                   rule_pack=s.before.stats.get("rule_pack", ""), level_profile=str(s.options.levels_path or ""),
                   max_gap_m=s.max_gap, approved_by=approved_by, fixes=approved, impact=impact, status="EXPORTED")
    d = out_dir / cs.changeset_id
    d.mkdir(parents=True, exist_ok=True)
    # bản sao DGN (chỉ khi nguồn là .dgn)
    if s.source_path.suffix.lower() == ".dgn":
        copy_path = d / f"{s.source_path.stem}_BANSAO_{ts}.dgn"
        h0 = sha256_file(s.source_path)
        shutil.copy2(s.source_path, copy_path)
        if sha256_file(copy_path) != h0 or sha256_file(s.source_path) != h0:
            raise RuntimeError("Sao chép DGN không toàn vẹn (hash khác) — dừng.")
        cs.outputs["ban_sao_dgn"] = str(copy_path)
    (d / "CVP_ApDung.bas").write_bytes(build_macro(cs, rollback=False).encode("ascii"))
    (d / "CVP_HoanTac.bas").write_bytes(build_macro(cs, rollback=True).encode("ascii"))
    cs.outputs.update({"macro_ap_dung": str(d / "CVP_ApDung.bas"), "macro_hoan_tac": str(d / "CVP_HoanTac.bas")})
    _write_excel(cs, d / f"{cs.changeset_id}.xlsx")
    cs.outputs["excel"] = str(d / f"{cs.changeset_id}.xlsx")
    tmp = d / "changeset.json.tmp"
    tmp.write_text(json.dumps(cs.to_dict(), ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(d / "changeset.json")
    cs.outputs["changeset_json"] = str(d / "changeset.json")
    return cs


def _write_excel(cs: ChangeSet, path: Path):
    from openpyxl import Workbook
    from openpyxl.styles import Font
    wb = Workbook()
    ws = wb.active
    ws.title = "ChangeSet"
    ws.append([f"ChangeSet {cs.changeset_id} — tờ {cs.sheet_id} — người duyệt: {cs.approved_by} — {cs.created_at}"])
    ws.append(["Chỉ áp dụng trên BẢN SAO DGN. Mức rủi ro B: cần duyệt từng đối tượng (Master Prompt mục VII)."])
    hdr = ["Mã sửa", "Phần tử", "Loại", "Level", "Đỉnh", "Thao tác", "Khoảng hở (m)", "X trước", "Y trước",
           "X sau", "Y sau", "Nét đích", "Rủi ro", "Ghi chú"]
    ws.append(hdr)
    for c in ws[3]:
        c.font = Font(bold=True)
    for f in cs.fixes:
        ws.append([f.fix_id, f.element_id, f.element_type, f.level, "đầu" if f.vertex_index == 0 else "cuối",
                   f.action, f.gap_m, f.before[0], f.before[1], f.after[0], f.after[1], f.target_element_id,
                   f.risk, f.note])
    wi = wb.create_sheet("TacDong")
    for k, v in cs.impact.items():
        wi.append([k, json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v])
    wb.save(path)
