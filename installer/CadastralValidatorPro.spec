# PyInstaller spec — chạy: pyinstaller --noconfirm installer/CadastralValidatorPro.spec
# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

ROOT = Path(SPECPATH).parent

datas = [
    (str(ROOT / "config"), "config"),
    (str(ROOT / "scripts" / "microstation"), "scripts/microstation"),
    (str(ROOT / "docs" / "huong_dan_xuat_DGN_bang_macro.md"), "docs"),
    (str(ROOT / "docs" / "huong_dan_tab2_sua_dau_mut_treo.md"), "docs"),
]

hidden = ["shapely", "pyproj", "openpyxl", "lxml.etree", "olefile", "shapefile"]
try:
    import win32com  # noqa: F401
    hidden += ["win32com.client", "pythoncom", "pywintypes"]
except ImportError:
    pass

a = Analysis([str(ROOT / "main.py")], pathex=[str(ROOT / "src")], datas=datas, hiddenimports=hidden,
             excludes=["tkinter", "matplotlib", "PySide6.QtWebEngineCore", "PySide6.Qt3DCore", "PySide6.QtQuick"],
             noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="CadastralValidatorPro", console=False,
          upx=False, version=str(ROOT / "installer" / "version_info.txt"))
coll = COLLECT(exe, a.binaries, a.datas, name="CadastralValidatorPro", upx=False)
