"""Dịch vụ kiểm tra Tab 3 — Tầng A (tiền kiểm) + Tầng B (topology/thuộc tính).

Chỉ đọc. Không ghi dữ liệu nguồn. Mọi lỗi mang rule_id, rule_version, trạng thái xác minh.
"""
from __future__ import annotations

import time
from collections import defaultdict
from decimal import Decimal
from typing import Optional

from shapely import STRtree
from shapely.geometry import Point, Polygon

from ..domain.labels import count_by_kind, extract_labels
from ..domain.level_resolve import resolve_levels
from ..domain.area_tolerance import area_tolerance_tt26, LEGAL_REF as PL04_REF
from ..domain.area_reference import compare_area
from ..domain.models import Issue, Label, LabelKind, MapSheet, Parcel, SheetResult
from ..domain.rules import RulePack
from ..domain.textparse import count_decimals, parse_area, round_half_up, validate_land_code
from ..domain import topology as topo
from ..infrastructure.config import AppConfig

PRECHECK_MSG = ('Tập tin "{name}" chưa chuẩn hóa. Thiếu nhãn lớp 2 (loại đất), lớp 4 (diện tích) '
                'hoặc lớp 13 (số hiệu thửa) ngay từ đầu. Số lượng sau lọc: lớp 2 = {lt}, lớp 4 = {ar}, lớp 13 = {pn}.')


class Validator:
    def __init__(self, cfg: AppConfig, pack: RulePack):
        self.cfg = cfg
        self.pack = pack

    # ---------------------------------------------------------------- helpers
    def _issue(self, res: SheetResult, code: str, message: str, pt: Optional[tuple[float, float]] = None,
               parcel_ids=None, element_ids=None, evidence=None, suggested_fix=None, geom=None,
               severity: Optional[str] = None) -> Optional[Issue]:
        if not self.pack.enabled(code):
            return None
        rule = self.pack.rule(code)
        iss = Issue(code=code, rule_id=rule.rule_id, severity=severity or rule.severity, sheet_id=res.sheet_id,
                    message=message, x=pt[0] if pt else None, y=pt[1] if pt else None,
                    parcel_ids=list(parcel_ids or []), source_element_ids=list(element_ids or []),
                    evidence=evidence or {}, suggested_fix=suggested_fix,
                    rule_version=self.pack.version, verification_status=rule.verification_status,
                    geometry_wkt=geom.wkt if geom is not None else None)
        iss.compute_id()
        res.issues.append(iss)
        return iss

    # ------------------------------------------------------------------ entry
    def validate(self, sheet: MapSheet) -> SheetResult:
        t0 = time.perf_counter()
        res = SheetResult(sheet_id=sheet.sheet_id, file_name=sheet.file_name, status="OK")
        params = self.pack.params_for_scale(sheet.scale)
        res.stats["scale"] = sheet.scale
        res.stats["rule_pack"] = f"{self.pack.rule_pack_id}@{self.pack.version}"
        res.stats["config_hash"] = self.pack.config_hash[:16]
        res.stats["source_sha256"] = sheet.source.sha256
        res.stats["reader"] = sheet.source.reader
        res.stats["synthetic"] = sheet.source.is_synthetic
        prof = self.cfg.crs_profiles.get(sheet.crs_profile_id or "")
        self._ctx = {"scale": sheet.scale, "area_ref": sheet.area_reference, "h": sheet.mean_height_m,
                     "crs": prof if (prof and sheet.crs_confirmed) else None}
        res.stats["area_reference"] = sheet.area_reference
        res.stats["mean_height_m"] = sheet.mean_height_m

        self._check_crs(sheet, res)
        if sheet.features:
            self._validate_polygons(sheet, res, params)
        else:
            self._validate_linework(sheet, res, params)

        res.stats["errors"] = res.count("error")
        res.stats["warnings"] = res.count("warning")
        res.stats["infos"] = res.count("info")
        if res.status == "OK" and (res.stats["errors"] or res.stats["warnings"]):
            res.status = "CO_LOI" if res.stats["errors"] else "CAN_XEM"
        res.stats["seconds"] = round(time.perf_counter() - t0, 3)
        return res

    # -------------------------------------------------------------------- CRS
    def _check_crs(self, sheet: MapSheet, res: SheetResult):
        prof = self.cfg.crs_profiles.get(sheet.crs_profile_id or "")
        res.stats["crs_profile"] = sheet.crs_profile_id
        res.stats["crs_confirmed"] = bool(sheet.crs_confirmed and prof)
        if not prof or not sheet.crs_confirmed:
            self._issue(res, "CRS_CHUA_XAC_NHAN",
                        "CRS/kinh tuyến trục chưa được người dùng xác nhận cho tờ này: so sánh diện tích nhãn–hình học "
                        "chỉ mang tính tham khảo; mọi thao tác sửa theo mét bị chặn.",
                        evidence={"crs_profile_id": sheet.crs_profile_id})
        if prof and prof.get("axis_check"):
            xs, ys = [], []
            for el in sheet.elements:
                for x, y in el.coords[:2]:
                    xs.append(x); ys.append(y)
            for f in sheet.features[:200]:
                c = f.geometry.representative_point()
                xs.append(c.x); ys.append(c.y)
            if xs:
                xr, yr = prof["axis_check"]["x_range_m"], prof["axis_check"]["y_range_m"]
                out = sum(1 for x, y in zip(xs, ys) if not (xr[0] <= x <= xr[1] and yr[0] <= y <= yr[1]))
                if out / len(xs) > 0.5:
                    self._issue(res, "TOA_DO_NGOAI_KHOANG",
                                f"{out}/{len(xs)} điểm mẫu nằm ngoài khoảng X {xr}, Y {yr} của profile "
                                f"{prof['id']} — nghi sai CRS hoặc đảo trục X-Y.",
                                evidence={"sample": len(xs), "outside": out})

    # ------------------------------------------------------- linework (DGN)
    def _validate_linework(self, sheet: MapSheet, res: SheetResult, params: dict):
        lv, lvinfo = resolve_levels(self.cfg.levels, sheet)
        n_lverr = sum(1 for e in sheet.elements if e.extra.get("level_error"))
        if n_lverr:
            res.stats["phan_tu_khong_doc_duoc_level"] = n_lverr
        res.stats["level_profile"] = self.cfg.levels.profile_id
        res.stats["level_resolution"] = lvinfo
        if lvinfo.get("missing"):
            res.message = f"Không tìm thấy Level theo tên: {', '.join(sorted(lvinfo['missing']))}."
        labels, suggestions, opaque_cells = extract_labels(sheet.elements, lv, self.cfg.patterns)
        labels = self._apply_exclusions(res, labels, lv)
        res.labels = labels
        counts = count_by_kind(labels)
        res.stats.update({"nhan_lop2": counts["land_type"], "nhan_lop4": counts["area"],
                          "nhan_lop13": counts["parcel_no"], "cell_nhan_chua_phan_ra": len(opaque_cells)})
        for s in suggestions:
            self._issue(res, "DE_XUAT_CHUYEN_LEVEL",
                        f"Nhãn '{s.text}' ở Level {s.current_level} có dạng {s.suggested_kind}; đề xuất chuyển Level "
                        f"{s.suggested_level} (độ tin cậy {s.confidence:.0%}). Chỉ xem trước, không tự ghi.",
                        s.anchor, element_ids=[s.element_id],
                        evidence={"confidence": s.confidence, "suggested_level": s.suggested_level})

        # Tầng A — tiền kiểm
        if 0 in (counts["land_type"], counts["area"], counts["parcel_no"]):
            msg = PRECHECK_MSG.format(name=sheet.file_name, lt=counts["land_type"], ar=counts["area"],
                                      pn=counts["parcel_no"])
            if opaque_cells:
                msg += f" Có {len(opaque_cells)} Cell nhãn chưa phân rã được (đặc tính Cell chưa xác minh)."
            self._issue(res, "THIEU_NHOM_NHAN", msg, evidence=counts)
            res.status = "DUNG_TIEN_KIEM"
            res.message = msg
            return

        # Tầng B — dựng vùng
        frame_lines = topo.collect_lines(sheet.elements, lv.frame_levels)
        frame = topo.frame_polygon(frame_lines)
        res.frame = frame
        b_levels = set(lv.boundary_levels)
        if params.get("include_frame_in_noding", True):
            b_levels |= lv.frame_levels
        lines = topo.collect_lines(sheet.elements, b_levels)
        res.stats["so_net_ranh"] = len(lines)
        frame_boundary = frame.exterior if frame is not None else None
        lw = topo.build_regions(lines, params["snap_tolerance_m"], frame_boundary, params["dangle_near_frame_m"])
        res.linework = lw.noded
        res.stats["max_snap_shift_m"] = round(lw.max_snap_shift, 4)

        for sl in lw.zero_length:
            c = sl.geom.coords[0]
            self._issue(res, "DOAN_RANH_DO_DAI_0", f"Đoạn ranh độ dài 0 (Level {sl.level}).", c,
                        element_ids=[sl.element_id])
        for p, ids in lw.dangles:
            self._issue(res, "DAU_MUT_TREO",
                        f"Đầu mút treo (ranh không nối vào ranh khác) tại X={p.x:.3f}, Y={p.y:.3f}.",
                        (p.x, p.y), element_ids=ids, suggested_fix="Kiểm tra thừa nét/thiếu nét; nối hoặc xóa đoạn "
                        "thừa sau khi rà soát (mức B — cần phê duyệt).")
        res.stats["dau_mut_treo"] = len(lw.dangles)

        regions = [r for r in lw.regions if frame is None or not self._is_frame_ring(r, frame)]
        res.stats["so_vung"] = len(regions)
        labels = self._detect_stat_table(res, labels, regions)
        self._associate_and_check(res, regions, labels, params, frame)

    def _apply_exclusions(self, res: SheetResult, labels: list[Label], lv) -> list[Label]:
        if not lv.exclusion_boxes:
            return labels
        keep, n = [], 0
        for lb in labels:
            x, y = lb.anchor
            if any(b[0] <= x <= b[2] and b[1] <= y <= b[3] for b in lv.exclusion_boxes):
                n += 1
            else:
                keep.append(lb)
        res.stats["nhan_trong_vung_loai_tru"] = n
        return keep

    def _detect_stat_table(self, res: SheetResult, labels: list[Label], regions: list[Polygon]) -> list[Label]:
        """Heuristic: nhãn NGOÀI mọi vùng xếp thành lưới hàng–cột được coi là nghi thuộc bảng thống kê/chú dẫn
        -> báo một dòng mức info, không tính vào lỗi nhãn ngoài vùng. Người dùng xác nhận bằng exclusion_boxes."""
        if not self.pack.enabled("NHAN_TRONG_BANG_THONG_KE"):
            return labels
        tree = STRtree(regions) if regions else None
        outside = []
        for i, lb in enumerate(labels):
            pt = Point(lb.anchor)
            inside = tree is not None and any(regions[int(j)].intersects(pt) for j in tree.query(pt))
            if not inside:
                outside.append(i)
        # 1) Ứng viên: nhãn ngoài vùng cùng hàng (|dY| ≤ 1,5 m) với ≥ 3 nhãn khác VÀ cùng cột (|dX| ≤ 4 m) với ≥ 3 nhãn khác
        P = [labels[i].anchor for i in outside]
        cand = []
        for a, i in enumerate(outside):
            xa, ya = P[a]
            row = sum(1 for b, (x, y) in enumerate(P) if b != a and abs(y - ya) <= 1.5)
            col = sum(1 for b, (x, y) in enumerate(P) if b != a and abs(x - xa) <= 4.0)
            if row >= 3 and col >= 3:
                cand.append(i)
        if not cand:
            return labels
        # 2) Gom cụm liền nhau (khoảng cách ≤ 100 m) — mỗi cụm là một bảng riêng
        parent = {i: i for i in cand}

        def find(i):
            while parent[i] != i:
                parent[i] = parent[parent[i]]
                i = parent[i]
            return i
        for x in range(len(cand)):
            for y in range(x + 1, len(cand)):
                (x1, y1), (x2, y2) = labels[cand[x]].anchor, labels[cand[y]].anchor
                if abs(x1 - x2) <= 100 and abs(y1 - y2) <= 100:
                    parent[find(cand[x])] = find(cand[y])
        groups: dict[int, list[int]] = defaultdict(list)
        for i in cand:
            groups[find(i)].append(i)
        # 3) Chỉ nhận cụm có ≥ 3 hàng, ≥ 3 cột, kích thước ≤ 20 cm trên giấy theo tỷ lệ
        try:
            denom = float(str(res.stats.get("scale", "1:1000")).split(":")[1])
        except (IndexError, ValueError):
            denom = 1000.0
        max_size = 0.20 * denom
        table_idx: set[int] = set()
        boxes = []
        for idx in groups.values():
            xs = [labels[i].anchor[0] for i in idx]
            ys = [labels[i].anchor[1] for i in idx]
            nrows = len({round(y / 1.5) for y in ys})
            ncols = len({round(x / 4.0) for x in xs})
            w, h = max(xs) - min(xs), max(ys) - min(ys)
            # bảng thống kê có hình gần chữ nhật: loại dải hẹp (nhãn các thửa dạng dải thẳng hàng)
            if nrows < 3 or ncols < 3 or w > max_size or h > max_size or w < 0.25 * h or h < 0.25 * w:
                continue
            rows = sorted({round(y, 0) for y in ys})
            gaps = sorted(b2 - a2 for a2, b2 in zip(rows, rows[1:]) if b2 - a2 > 1.5)
            my = 1.2 * gaps[len(gaps) // 2] if gaps else 2.0
            bx = (min(xs) - 5, min(ys) - my, max(xs) + 5, max(ys) + my)
            members = {i for i in outside if bx[0] <= labels[i].anchor[0] <= bx[2] and bx[1] <= labels[i].anchor[1] <= bx[3]}
            table_idx |= members
            boxes.append((bx, len(members)))
        if not table_idx:
            return labels
        for bx, n in boxes:
            self._issue(res, "NHAN_TRONG_BANG_THONG_KE",
                        f"{n} nhãn ngoài vùng xếp thành bảng (nghi Bảng thống kê/chú dẫn) trong khung "
                        f"X {bx[0]:.1f}–{bx[2]:.1f}, Y {bx[1]:.1f}–{bx[3]:.1f}; không tính là lỗi nhãn ngoài vùng. "
                        f"Nếu đúng, khai báo vào exclusion_boxes của hồ sơ Level.",
                        ((bx[0] + bx[2]) / 2, (bx[1] + bx[3]) / 2),
                        evidence={"box": [round(v, 3) for v in bx], "count": n})
        res.stats["nhan_nghi_bang_thong_ke"] = len(table_idx)
        return [lb for i, lb in enumerate(labels) if i not in table_idx]

    @staticmethod
    def _is_frame_ring(region: Polygon, frame: Polygon) -> bool:
        """Loại vùng 'vành khung' (giữa khung trong/ngoài) nếu có: vùng nằm ngoài khung."""
        try:
            return region.representative_point().within(frame) is False
        except Exception:
            return False

    def _associate_and_check(self, res: SheetResult, regions: list[Polygon], labels: list[Label], params: dict,
                             frame: Optional[Polygon]):
        near = params["label_near_boundary_m"]
        tree = STRtree(regions) if regions else None
        assigned: dict[int, list[Label]] = defaultdict(list)
        for lb in labels:
            pt = Point(lb.anchor)
            hit = None
            if tree is not None:
                for j in tree.query(pt):
                    if regions[int(j)].contains(pt):
                        hit = int(j)
                        break
            if hit is None:
                on_edge = tree is not None and any(regions[int(j)].touches(pt) for j in tree.query(pt.buffer(1e-6)))
                self._issue(res, "NHAN_NGOAI_VUNG" if not on_edge else "NHAN_SAT_RANH",
                            (f"Nhãn '{lb.text_norm}' (lớp {lb.level}) nằm ngoài mọi vùng thửa." if not on_edge else
                             f"Nhãn '{lb.text_norm}' (lớp {lb.level}) nằm đè đúng trên ranh — không xác định thửa."),
                            lb.anchor, element_ids=[lb.source_element_id],
                            severity=None if not on_edge else "error")
                continue
            d = regions[hit].exterior.distance(pt)
            for ring in regions[hit].interiors:
                d = min(d, ring.distance(pt))
            if d < near:
                self._issue(res, "NHAN_SAT_RANH",
                            f"Nhãn '{lb.text_norm}' cách ranh {d:.3f} m (< {near} m) — AMBIGUOUS, cần xem lại vị trí.",
                            lb.anchor, element_ids=[lb.source_element_id], evidence={"distance_m": round(d, 4)})
            assigned[hit].append(lb)

        parcels: list[Parcel] = []
        for i, reg in enumerate(regions):
            pid = f"{res.sheet_id}#V{i + 1}"
            lbs = assigned.get(i, [])
            by = defaultdict(list)
            for lb in lbs:
                by[lb.kind].append(lb)
            parcel = Parcel(internal_id=pid, geometry=reg, area_geom=reg.area, labels=lbs)
            pn, ar, lt = by[LabelKind.PARCEL_NO], by[LabelKind.AREA], by[LabelKind.LAND_TYPE]
            if pn:
                parcel.parcel_no = pn[0].text_norm
            if len(ar) == 1:   # nhiều nhãn diện tích -> đã báo TRUNG_NHAN, không so diện tích (tránh so nhầm)
                parcel.area_label = ar[0].text_norm
            if lt:
                parcel.land_type = lt[0].text_norm
            parcels.append(parcel)
            rp = reg.representative_point()
            loc = (rp.x, rp.y)
            ids = [lb.source_element_id for lb in lbs]

            if not pn:
                codes = {c.text_norm.upper() for c in lt}
                if codes and codes <= set(params.get("non_parcel_land_codes", [])):
                    continue  # giao thông/thủy hệ: không phải lỗi
                if reg.area < params["unlabeled_region_min_area_m2"]:
                    self._issue(res, "KHE_HO",
                                f"Mảnh vụn/khe hở không nhãn ({reg.area:.3f} m² < "
                                f"{params['unlabeled_region_min_area_m2']} m²).", loc, [pid], ids,
                                evidence={"area_m2": round(reg.area, 4), "compactness": round(topo.compactness(reg), 4)},
                                geom=reg)
                else:
                    self._issue(res, "VUNG_KHONG_NHAN", f"Vùng thửa không có nhãn số thửa ({reg.area:.1f} m²).",
                                loc, [pid], ids, evidence={"area_m2": round(reg.area, 3)}, geom=reg)
                continue
            for kind, lst, ten in ((LabelKind.PARCEL_NO, pn, "số thửa"), (LabelKind.AREA, ar, "diện tích"),
                                   (LabelKind.LAND_TYPE, lt, "loại đất")):
                if len(lst) > 1:
                    self._issue(res, "TRUNG_NHAN",
                                f"Thửa chứa {len(lst)} nhãn {ten}: {[l.text_norm for l in lst]}.", loc, [pid],
                                [l.source_element_id for l in lst], geom=reg)
            missing = [t for k, t in ((ar, "diện tích"), (lt, "loại đất")) if not k]
            if missing:
                self._issue(res, "THIEU_NHAN_PHU", f"Thửa {parcel.parcel_no}: thiếu nhãn {', '.join(missing)}.",
                            loc, [pid], ids, geom=reg)
            self._check_parcel_attrs(res, parcel, params, loc, ids,
                                     area_label_elem=ar[0].source_element_id if len(ar) == 1 else None)
            if frame is not None:
                outside = reg.difference(frame).area / reg.area if reg.area else 0
                if outside > params.get("outside_frame_ratio", 0.5):
                    self._issue(res, "THUA_NGOAI_KHUNG",
                                f"Thửa {parcel.parcel_no}: {outside:.0%} diện tích nằm ngoài khung tờ.", loc, [pid], ids)
        res.parcels = parcels
        self._check_duplicates(res, parcels)

    # ----------------------------------------------------- thuộc tính thửa
    def _check_parcel_attrs(self, res: SheetResult, parcel: Parcel, params: dict, loc, ids, area_label_elem=None):
        pn = parcel.parcel_no or "?"
        if parcel.land_type:
            ok, bad = validate_land_code(parcel.land_type, self.cfg.land.codes, self.cfg.land.allow_combined,
                                         self.cfg.land.separator)
            if not ok:
                sug = [m["to"] for m in self.cfg.land.mappings if m["from"] == parcel.land_type.upper()]
                self._issue(res, "MA_DAT_KHONG_HOP_LE",
                            f"Thửa {pn}: mã loại đất '{parcel.land_type}' có mã ngoài danh mục cấu hình: {bad}.",
                            loc, [parcel.internal_id], ids,
                            suggested_fix=("Người dùng tự nhập mã loại đất mới (cột 'Mã loại đất mới'); "
                                           "phần mềm không tự ánh xạ."
                                           + (f" Tham khảo ánh xạ CHƯA PHÊ DUYỆT: {sug[0]}" if sug else "")))
        if parcel.area_geom < params["min_parcel_warning_area_m2"]:
            self._issue(res, "THUA_NHO", f"Thửa {pn}: diện tích hình học {parcel.area_geom:.2f} m² nhỏ hơn "
                        f"{params['min_parcel_warning_area_m2']} m² — cần kiểm tra.", loc, [parcel.internal_id], ids)
        if parcel.area_label is None:
            return
        pat = self.cfg.patterns
        val = parse_area(parcel.area_label, pat.decimal_sep, pat.thousands_sep)
        if val is None:
            self._issue(res, "DIEN_TICH_KHONG_PHAI_SO",
                        f"Thửa {pn}: nhãn diện tích '{parcel.area_label}' không phải số hợp lệ theo locale cấu hình.",
                        loc, [parcel.internal_id], [area_label_elem] if area_label_elem else ids)
            return
        dp = params.get("area_decimal_places")
        if isinstance(dp, int) and count_decimals(parcel.area_label, pat.decimal_sep) != dp:
            self._issue(res, "SAI_QUY_CACH_LAM_TRON",
                        f"Thửa {pn}: diện tích '{parcel.area_label}' không đúng {dp} chữ số thập phân theo cấu hình.",
                        loc, [parcel.internal_id], [area_label_elem] if area_label_elem else ids)
        ctx = getattr(self, "_ctx", {"scale": res.stats.get("scale"), "area_ref": "grid", "h": None, "crs": None})
        a_cmp, a_note = compare_area(parcel.geometry, ctx["area_ref"], ctx["crs"], ctx["h"])
        method = params.get("area_tolerance_method", "ABS")
        if method == "TT26_PL04":
            tol = area_tolerance_tt26(ctx["scale"], a_cmp)
            basis = "PL04 TT 26/2024 (khoản 5 Điều 8)"
        else:
            tol = params.get("area_abs_tolerance_m2")
            basis = "ngưỡng tuyệt đối cấu hình"
        delta = abs(float(val) - a_cmp)
        rounded = round_half_up(a_cmp, dp if isinstance(dp, int) else 1)
        ev = {"nhan": str(val), "dien_tich_so_sanh": round(a_cmp, 4), "mat_so_sanh": a_note,
              "dien_tich_luoi": round(parcel.area_geom, 4), "lech": round(delta, 4), "nguong": tol,
              "can_cu_nguong": basis, "crs_confirmed": res.stats.get("crs_confirmed")}
        if tol is None:
            return
        if delta > tol:
            note = "" if res.stats.get("crs_confirmed") else " [CRS chưa xác nhận — chỉ tham khảo]"
            self._issue(res, "SAI_DIEN_TICH",
                        f"Thửa {pn}: sai lệch diện tích (Nhãn={val}, Tọa độ={rounded} m² [{a_note}], "
                        f"Lệch={delta:.2f} m² > Hạn sai={tol} m² theo {basis}).{note} Không tự sửa diện tích pháp lý.",
                        loc, [parcel.internal_id], ids, evidence=ev)

    def _check_duplicates(self, res: SheetResult, parcels: list[Parcel]):
        seen: dict[str, list[Parcel]] = defaultdict(list)
        for p in parcels:
            if p.parcel_no:
                seen[p.parcel_no].append(p)
        for no, ps in seen.items():
            if len(ps) > 1:
                for p in ps[1:]:
                    rp = p.geometry.representative_point()
                    self._issue(res, "TRUNG_SO_THUA", f"Trùng số hiệu thửa {no} trên cùng tờ ({len(ps)} thửa).",
                                (rp.x, rp.y), [q.internal_id for q in ps])

    # ------------------------------------------------- polygon (GML/SHP)
    def _validate_polygons(self, sheet: MapSheet, res: SheetResult, params: dict):
        polys, parcels = [], []
        for f in sheet.features:
            geoms = [f.geometry] if f.geometry.geom_type == "Polygon" else list(getattr(f.geometry, "geoms", []))
            reason = topo.validity_reason(f.geometry)
            rp = f.geometry.representative_point() if not f.geometry.is_empty else None
            loc = (rp.x, rp.y) if rp else None
            if f.geometry.is_empty:
                self._issue(res, "HINH_HOC_KHONG_HOP_LE", f"Đối tượng {f.feature_id} rỗng.", None, [f.feature_id])
                continue
            if reason:
                self._issue(res, "HINH_HOC_KHONG_HOP_LE", f"Thửa {f.parcel_no or f.feature_id}: {reason}.", loc,
                            [f.feature_id], evidence={"reason": reason})
                continue
            p = Parcel(internal_id=f.feature_id, geometry=f.geometry, area_geom=f.geometry.area,
                       parcel_no=f.parcel_no, area_label=f.area_label, land_type=f.land_type)
            parcels.append(p)
            polys.append(f.geometry)
            if not f.parcel_no:
                self._issue(res, "VUNG_KHONG_NHAN", f"Đối tượng {f.feature_id} thiếu số thửa.", loc, [f.feature_id])
            self._check_parcel_attrs(res, p, params, loc, [])
            _ = geoms
        res.parcels = parcels
        res.stats["so_vung"] = len(parcels)
        for i, j, inter in topo.find_overlaps(polys, params["overlap_error_threshold_m2"]):
            rp = inter.representative_point()
            self._issue(res, "CHONG_LAN",
                        f"Chồng lấn giữa thửa {parcels[i].parcel_no or parcels[i].internal_id} và "
                        f"{parcels[j].parcel_no or parcels[j].internal_id}: {inter.area:.3f} m². Không tự cắt.",
                        (rp.x, rp.y), [parcels[i].internal_id, parcels[j].internal_id],
                        evidence={"area_m2": round(inter.area, 4)}, geom=inter)
        if sheet.coverage is not None:
            for g in topo.find_gaps(polys, sheet.coverage):
                c = topo.compactness(g)
                if g.area <= params["sliver_max_area_m2"] or c <= params["sliver_compactness_threshold"]:
                    rp = g.representative_point()
                    self._issue(res, "KHE_HO", f"Khe hở/mảnh vụn {g.area:.3f} m² (compactness {c:.3f}).",
                                (rp.x, rp.y), evidence={"area_m2": round(g.area, 4), "compactness": round(c, 4)},
                                geom=g)
        else:
            res.stats["gap_check"] = "NOT_EVALUATED: chưa có vùng bao phủ hợp lệ"
        self._check_duplicates(res, parcels)
        _ = Decimal
