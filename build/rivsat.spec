# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for the RivSat desktop app.

Build from the project root:
    pyinstaller build/rivsat.spec

Produces:
    dist/RivSat/RivSat.exe        (folder build — recommended, faster start)

For a single-file build, set ONEFILE = True below (slower start, ~1 file).
"""
import os
from PyInstaller.utils.hooks import (
    collect_data_files, collect_submodules, collect_dynamic_libs
)

ONEFILE = False
PROJECT_ROOT = os.path.abspath(os.getcwd())
ENTRY = os.path.join("rivsat", "app", "qt", "app.py")

# ── Data files: packages that ship non-Python resources ───────────────────────
datas = []
datas += collect_data_files("rasterio")      # GDAL data / proj
datas += collect_data_files("pyproj")         # proj.db
datas += collect_data_files("geopandas")
datas += collect_data_files("folium")         # JS/CSS templates
datas += collect_data_files("branca")         # folium dependency templates
datas += collect_data_files("earthengine_api", include_py_files=True)
datas += collect_data_files("cmocean")

# Bundle the rivsat package's own non-code assets if any
datas += [("rivsat/app/qt/assets", "rivsat/app/qt/assets")]

# ── Hidden imports: dynamically-imported modules PyInstaller can't see ─────────
hiddenimports = []
hiddenimports += collect_submodules("rasterio")
hiddenimports += collect_submodules("rivsat")
hiddenimports += collect_submodules("scipy")
hiddenimports += [
    "PyQt6.QtWebEngineWidgets",
    "PyQt6.QtWebEngineCore",
    "PyQt6.QtWebChannel",
    "PyQt6.QtSvg",
    "PyQt6.QtPrintSupport",
    "matplotlib.backends.backend_qtagg",
    "sklearn.utils._typedefs",
    "google.auth", "google_auth_httplib2", "httplib2",
]

# ── Native libraries (GDAL, PROJ) ─────────────────────────────────────────────
binaries = []
binaries += collect_dynamic_libs("rasterio")


a = Analysis(
    [ENTRY],
    pathex=[PROJECT_ROOT],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        "tkinter", "PySide6", "PyQt5",
        "panel", "bokeh",           # legacy web GUI not needed in native build
        "pytest", "IPython", "notebook", "jupyter",
    ],
    noarchive=False,
)
pyz = PYZ(a.pure)

_icon = os.path.join("rivsat", "app", "qt", "assets", "rivsat.ico")
_icon = _icon if os.path.exists(_icon) else None

if ONEFILE:
    exe = EXE(
        pyz, a.scripts, a.binaries, a.datas, [],
        name="RivSat",
        console=False,
        icon=_icon,
        upx=False,
    )
else:
    exe = EXE(
        pyz, a.scripts, [],
        exclude_binaries=True,
        name="RivSat",
        console=False,
        icon=_icon,
        upx=False,
    )
    coll = COLLECT(
        exe, a.binaries, a.datas,
        name="RivSat",
        upx=False,
    )
