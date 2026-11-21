"""Gate 0 — khảo sát MicroStation COM trên máy Windows thật. CHỈ ĐỌC.

python scripts\\probe_microstation.py "D:\\du_lieu\\DC8.dgn"
Ghi kết quả ra probe_result.json cạnh script. Không sửa tệp DGN, không đóng MicroStation đang mở.
"""
import json
import platform
import struct
import sys
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

out = {"python": sys.version, "python_bits": struct.calcsize("P") * 8, "os": platform.platform(), "steps": []}


def step(name, fn):
    t = time.perf_counter()
    try:
        v = fn()
        out["steps"].append({"step": name, "ok": True, "result": v, "s": round(time.perf_counter() - t, 2)})
        return v
    except Exception as e:
        out["steps"].append({"step": name, "ok": False, "error": f"{type(e).__name__}: {e}",
                             "trace": traceback.format_exc()[-1500:]})
        return None


def main(dgn):
    from cadastral_validator.adapters.dgn_probe import probe_dgn
    from cadastral_validator.adapters.microstation_com import com_capability
    before = probe_dgn(dgn).sha256
    out["dgn"] = probe_dgn(dgn).to_dict()
    step("com_capability", lambda: com_capability())

    def reg():
        import winreg
        k = winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, r"MicroStationDGN.Application\CLSID")
        clsid = winreg.QueryValue(k, None)
        res = {"clsid": clsid}
        for view in (winreg.KEY_WOW64_32KEY, winreg.KEY_WOW64_64KEY):
            try:
                kk = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, rf"SOFTWARE\Classes\CLSID\{clsid}\LocalServer32",
                                    0, winreg.KEY_READ | view)
                res["LocalServer32_" + ("32" if view == winreg.KEY_WOW64_32KEY else "64")] = winreg.QueryValue(kk, None)
            except OSError:
                pass
        return res
    step("registry", reg)

    import pythoncom
    import win32com.client
    pythoncom.CoInitialize()
    app = step("dispatch", lambda: win32com.client.Dispatch("MicroStationDGN.Application"))
    if app is not None:
        step("version", lambda: str(app.Version))
        d = step("open_readonly", lambda: app.OpenDesignFileForProgram(str(Path(dgn).resolve()), True))
        if d is not None:
            def scan():
                en = d.DefaultModelReference.Scan()
                n, types, sample = 0, {}, []
                while en.MoveNext() and n < 5000:
                    el = en.Current
                    t = int(el.Type)
                    types[t] = types.get(t, 0) + 1
                    if len(sample) < 5 and t in (3, 4, 6, 17):
                        s = {"type": t, "level": int(el.Level.Number) if el.Level is not None else None}
                        if t == 17:
                            s["text"] = el.AsTextElement.Text
                            o = el.AsTextElement.Origin
                            s["origin_type"] = str(type(o))
                            s["origin"] = [o.X, o.Y]
                        else:
                            v = el.AsVertexList.GetVertices()
                            s["n_vertices"] = len(v)
                            s["vertex_type"] = str(type(v[0]))
                            s["v0"] = [v[0].X, v[0].Y]
                        sample.append(s)
                    n += 1
                return {"scanned": n, "types": types, "sample": sample}
            step("scan_first_5000", scan)
            step("close", lambda: d.Close())
    pythoncom.CoUninitialize()
    out["sha256_unchanged"] = probe_dgn(dgn).sha256 == before


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Cách dùng: python scripts\\probe_microstation.py <tệp.dgn>")
        sys.exit(2)
    try:
        main(sys.argv[1])
    finally:
        p = Path(__file__).with_name("probe_result.json")
        p.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
        print(f"Đã ghi {p}")
