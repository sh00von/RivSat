# Building the RivSat Desktop App (.exe)

The RivSat GUI is a native PyQt6 desktop application. This guide packages it
into a standalone Windows executable with **PyInstaller** — end users do not
need Python installed.

## 1. Prerequisites

```powershell
# From the project root, in your dev environment:
pip install -e .[gui]        # installs PyQt6 + PyQt6-WebEngine + deps
pip install pyinstaller
```

Confirm the app runs from source first:

```powershell
python -m rivsat.app
```

## 2. Build

```powershell
# From the project root (NOT from inside build/):
pyinstaller build/rivsat.spec
```

Output:

```
dist/
└── RivSat/
    ├── RivSat.exe          ← double-click to launch
    └── _internal/          ← bundled Python, Qt, GDAL, etc.
```

- **Folder build (default):** faster startup, easy to zip and distribute.
- **Single-file build:** edit `build/rivsat.spec` and set `ONEFILE = True`.
  Produces one `dist/RivSat.exe` (~200–300 MB, slower first launch).

## 3. First run & Google Earth Engine auth

On first use, click **Initialize GEE** in the Configuration dock. This opens a
browser for Google OAuth. Credentials are cached under the user's home
directory (`~/.config/earthengine/`), so subsequent launches skip the prompt.

## 4. Custom app icon (optional)

Drop a `rivsat.ico` file at:

```
rivsat/app/qt/assets/rivsat.ico
```

The spec picks it up automatically for both the window and the `.exe`.

## 5. Common issues

| Symptom | Fix |
|---|---|
| `rasterio`/GDAL `.dll` not found at runtime | Ensure `collect_dynamic_libs("rasterio")` ran; rebuild in the same env where `import rasterio` works |
| Blank white map panel | `PyQt6.QtWebEngineCore` missing — it's in `hiddenimports`; verify `PyQt6-WebEngine` is installed |
| `proj.db` errors | `collect_data_files("pyproj")` bundles it; confirm `pyproj` is importable in the build env |
| Huge exe / slow AV scan | Use the folder build (`ONEFILE = False`) and distribute as a zip or via an Inno Setup installer |

## 6. Optional: Windows installer

For a professional setup wizard (Start Menu shortcut, uninstaller), wrap the
`dist/RivSat/` folder with [Inno Setup](https://jrsoftware.org/isinfo.php) or
NSIS. Point the installer at `dist/RivSat/RivSat.exe` as the main executable.
