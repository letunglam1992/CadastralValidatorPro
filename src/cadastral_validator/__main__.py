"""CLI: python -m cadastral_validator <lệnh>

  check   Kiểm tra DGN/exchange JSON/SHP/GML theo bộ quy tắc (Tab 3)
  probe   Khảo sát tệp DGN (phiên bản, OLE, hash) — không cần MicroStation
  com     Kiểm tra khả năng MicroStation COM trên máy này
  gui     Mở giao diện
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .infrastructure.config import ROOT
from .infrastructure.logging_setup import setup_logging


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="cadastral_validator", description="CadastralValidatorPro (G1)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check", help="Kiểm tra theo bộ quy tắc")
    c.add_argument("inputs", nargs="+", type=Path)
    c.add_argument("-o", "--out", type=Path, default=ROOT / "output")
    c.add_argument("--rulepack", type=Path, default=ROOT / "config" / "rulepacks" / "son_la_draft.json")
    c.add_argument("--scale", default=None, help="Mặc định lấy theo hồ sơ Level/tờ, nếu không có thì 1:1000")
    c.add_argument("--crs-profile")
    c.add_argument("--confirm-crs", action="store_true", help="Người dùng xác nhận CRS profile cho các tờ")
    c.add_argument("--no-html", action="store_true")
    c.add_argument("--field", action="append", default=[], help="Ánh xạ trường SHP/GML, vd parcel_no=SoThua")
    c.add_argument("--dbf-encoding")
    c.add_argument("--gml-swap-xy", action="store_true")
    c.add_argument("--area-ref", choices=["grid", "ellipsoid", "ground"], default=None,
                   help="Mặt tính diện tích ghi trên nhãn: mặt phẳng chiếu / ellipsoid / mặt đất thực")
    c.add_argument("--mean-height", type=float, help="Độ cao trung bình khu đo (m) khi --area-ref ground")
    c.add_argument("--levels", type=Path, help="Hồ sơ Level (vd config/level_profiles/dc8_phieng_luong.json)")
    p = sub.add_parser("probe", help="Khảo sát DGN")
    p.add_argument("inputs", nargs="+", type=Path)
    sub.add_parser("com", help="Kiểm tra COM")
    sub.add_parser("gui", help="Mở giao diện")
    a = ap.parse_args(argv)

    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    if a.cmd == "probe":
        from .adapters.dgn_probe import probe_dgn
        for f in a.inputs:
            print(json.dumps(probe_dgn(f).to_dict(), ensure_ascii=False, indent=1))
        return 0
    if a.cmd == "com":
        from .adapters.microstation_com import com_capability
        st, msg = com_capability()
        print(f"{st}: {msg}")
        return 0
    if a.cmd == "gui":
        from .ui.main_window import run_gui
        return run_gui()

    setup_logging(ROOT / "logs")
    from .application.check_service import CheckOptions, run_check
    fm = dict(kv.split("=", 1) for kv in a.field)
    if a.confirm_crs and not a.crs_profile:
        ap.error("--confirm-crs cần --crs-profile")
    o = CheckOptions(inputs=a.inputs, out_dir=a.out, rulepack=a.rulepack, scale=a.scale or "1:1000",
                     scale_from_cli=a.scale is not None,
                     crs_profile_id=a.crs_profile, crs_confirmed=a.confirm_crs, html=not a.no_html,
                     field_map=fm, dbf_encoding=a.dbf_encoding, gml_swap_xy=a.gml_swap_xy,
                     levels_path=a.levels, area_reference=a.area_ref, mean_height_m=a.mean_height)
    results, info = run_check(o, progress=lambda k, n, name: print(f"[{k}/{n}] {name}"))
    for r in results:
        print(f"  {r.file_name}: {r.status} — lỗi {r.count('error')}, cần xem {r.count('warning')}"
              + (f" — {r.message}" if r.message else ""))
    print("Báo cáo:")
    for k, v in info["paths"].items():
        print(f"  {k}: {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
