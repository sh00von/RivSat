# 🌊 RivSat

**A universal, physics-based satellite remote sensing and hydro-engineering platform designed for multi-parameter water quality mapping (Turbidity, TSS, Chlorophyll-a, CDOM, Estuarine Salinity, Secchi Depth), active river channel width ($W$) tracking, and longitudinal chainage analytics in rivers, estuaries, and coastal plumes.**

RivSat provides a complete native desktop application (PyQt6) for downloading, processing, analyzing, and exporting water quality retrievals from **Sentinel-2 MSI** and **Landsat 8/9 OLI** via **Google Earth Engine (GEE)**.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![PyQt6](https://img.shields.io/badge/GUI-PyQt6-green.svg)](https://pypi.org/project/PyQt6/)
[![Tests](https://img.shields.io/badge/tests-51%20passed-brightgreen.svg)](tests/)

---

## 📚 Official Documentation Suite

- 📖 [**Documentation Portal (`docs/INDEX.md`)**](docs/INDEX.md)
- 📚 [**Peer-Reviewed Literature Review**](docs/LITERATURE_REVIEW.md)
- 🧮 [**Algorithms & Physics Guide**](docs/ALGORITHMS_GUIDE.md)
- 🚀 [**User Guide & Quickstart**](docs/USER_GUIDE.md)
- 🏗️ [**Hydro-Engineering Guide**](docs/HYDRO_ENGINEERING_GUIDE.md)
- 🗺️ [**GIS Integration Guide**](docs/GIS_INTEGRATION.md)

---

## 📋 Table of Contents

- [Documentation Suite](#-official-documentation-suite)
- [System Requirements](#-system-requirements)
- [Installation Guide](#-installation-guide)
- [Google Earth Engine Setup](#-google-earth-engine-gee-setup)
- [Launching the Desktop App](#-launching-the-desktop-app)
- [Troubleshooting & Common Issues](#-troubleshooting--common-issues)
- [Scientific Capabilities](#-key-scientific-capabilities)
- [Codebase Structure](#-codebase-structure)
- [Scientific References](#-scientific-references)
- [License](#-license)

---

## 💻 System Requirements

- **Operating System**: Windows 10/11, macOS (Intel & Apple Silicon), or Linux (Ubuntu 20.04+)
- **Python**: Version `3.9` to `3.13`
- **Google Earth Engine Account**: Active GEE account & Google Cloud Project ID
- **Disk Space**: ~500 MB for environment & dependencies (satellite rasters are downloaded on-demand)

---

## 📦 Installation Guide

### Option A: Python Virtual Environment (pip)

Standard installation using Python's built-in `venv`:

```bash
# 1. Clone the repository
git clone https://github.com/shovon/rivsat.git
cd rivsat

# 2. Create a virtual environment
python -m venv venv

# 3. Activate the virtual environment
# Windows (PowerShell):
.\venv\Scripts\Activate.ps1
# Windows (Command Prompt):
.\venv\Scripts\activate.bat
# macOS / Linux:
source venv/bin/activate

# 4. Upgrade pip and setuptools
python -m pip install --upgrade pip setuptools

# 5. Install RivSat in editable mode
pip install -e .
```

---

### Option B: Conda / Mamba Environment

Recommended for users managing multiple GIS/remote sensing environments:

```bash
# 1. Clone the repository
git clone https://github.com/shovon/rivsat.git
cd rivsat

# 2. Create the conda environment from environment.yml
conda env create -f environment.yml

# 3. Activate the environment
conda activate rivsat

# 4. Install RivSat package in editable mode
pip install -e .
```

---

## 🌍 Google Earth Engine (GEE) Setup

RivSat queries, cloud-masks, and temporal-composites satellite scenes directly on Google Earth Engine servers.

### 1. Register for Google Earth Engine
If you don't already have an account, register at:  
👉 [https://earthengine.google.com/signup/](https://earthengine.google.com/signup/)

### 2. Authenticate the Earth Engine Python API
Run the following command in your terminal/conda prompt:

```bash
earthengine authenticate
```

This will open a browser window requesting access to your Google account. Copy the authentication token code and paste it back into your terminal.

### 3. Google Cloud Project Registration
Earth Engine requires a Google Cloud Project ID. You can pass your project ID during initialization:

```python
import rivsat

# Pass your Google Cloud Project ID (optional if default project is configured)
rivsat.initialize_gee(project_id="your-gcp-project-id")
```

---

## 🖥️ Launching the Desktop App

Install the GUI extra, then launch the native desktop application:

```bash
# Activate your environment if not already active
conda activate rivsat  # or: source venv/bin/activate

# Install with the GUI extra (PyQt6 + WebEngine)
pip install -e .[gui]

# Launch the app
rivsat-gui
# or equivalently:
python -m rivsat.app
```

The app opens with six workflow tabs — **Map & Layers**, **Acquisition**,
**Processing**, **Time-Series**, **Profiles**, and **Export** — plus a
dockable configuration panel. Draw your AOI, river centerline, transects,
and monitoring stations directly on the interactive map.

### Quick verification (Python):

```python
import rivsat

# 1. Test Earth Engine Connection
rivsat.initialize_gee()

# 2. Ingest Spatial Layers
features = rivsat.load_geojson_features("./data/user_roi.geojson")
print(f"[OK] Ingested AOI with {len(features['aoi_polygon'])} vertices")
```

To build a standalone `.exe`, see [`build/README_BUILD.md`](build/README_BUILD.md).

---

## ❓ Troubleshooting & Common Issues

### 1. `ee.EEException: Not authenticated`
- **Solution**: Run `earthengine authenticate` in your terminal and follow the browser authorization prompt.

### 2. Rasterio / GDAL Binary Wheels on Windows
- **Solution**: If `pip install -e .` fails to compile `rasterio` or `shapely` on Windows, install them via conda first:
  ```bash
  conda install -c conda-forge rasterio shapely geopandas
  ```

### 3. Map Panel Blank in the Desktop App
- **Solution**: Ensure `PyQt6-WebEngine` is installed (`pip install -e .[gui]`).
  The interactive map requires the Qt WebEngine (Chromium) component.

---

## ✨ Key Scientific Capabilities

| Feature | Description |
|---|---|
| **Dogliotti Blended Dual-Band** | Adaptive Red↔NIR switching algorithm (Dogliotti et al., 2015) with continuous blending at $\rho_w(665) \in [0.05, 0.07]$ |
| **Nechad Semi-Analytical Model** | Single-band radiative transfer inversion $T = (A \cdot \rho_w) / (1 - \rho_w/C)$ (Nechad et al., 2010/2016) |
| **Red-Edge Extension** | Sentinel-2 Band 5 (704 nm) for hyper-turbid river plumes exceeding Red-band saturation |
| **Cross-Sensor Harmonization** | Spectral Band Adjustment Factors (SBAFs) aligning Landsat OLI to Sentinel-2 MSI |
| **Dynamic Water Masking** | Hybrid NDWI/MNDWI + SCL/QA_PIXEL cloud/shadow/vegetation filtering |
| **Cloud-Side Compositing** | Annual, Seasonal, Monthly, or Daily temporal composites computed directly on GEE servers |
| **CoastSat-Style Analytics** | Longitudinal centerline profiles, cross-river transects, virtual station time-series |
| **Mann-Kendall Trend Analysis** | Non-parametric trend tests with Sen's slope and seasonal climatology |
| **In-Situ Validation** | Spatio-temporal matchups with $R^2$, RMSE, MAPE, Bias scorecards |
| **Local Recalibration** | Non-linear least squares optimization of site-specific Nechad $A_T$ coefficients |

---

## 📁 Codebase Structure

```
rivsat/
├── rivsat/                    # Core Python package
│   ├── __init__.py            # Top-level API facade
│   ├── app/                   # 🖥️ Native PyQt6 desktop application
│   │   ├── qt/                #   Main window, tabs, interactive Leaflet map, theme
│   │   └── state.py           #   Shared application state
│   ├── core/                  # Nechad/Dogliotti equations & water masking
│   ├── acquisition/           # Earth Engine query engine & compositing
│   ├── processing/            # Multi-core parallel batch processor
│   ├── analytics/             # Longitudinal profiles, transects & trends
│   ├── validation/            # KD-Tree matchups & parameter optimization
│   ├── visualization/         # Spatial maps, product triplets & scatter plots
│   └── utils/                 # GeoJSON spatial tools & framework logger
├── data/                      # User spatial layers & field measurements
│   ├── user_roi.geojson       # Study area bounding polygon
│   ├── centerline.geojson     # Traced river channel centerline
│   ├── stations.geojson       # Virtual monitoring station pins
│   └── sample_insitu_measurements.csv  # Field survey dataset
├── outputs/                   # Exported GeoTIFFs, figures, and CSV datasets
├── tests/                     # Pytest test suite (46 tests)
├── setup.py                   # Package installer (`pip install -e .`)
├── requirements.txt           # Python dependencies
├── environment.yml            # Conda environment
└── README.md                  # Installation & documentation guide
```

---

## 🔬 Scientific References

- **Dogliotti, A.I., et al. (2015)**. A single algorithm to retrieve turbidity from remotely-sensed data in coastal and case 2 waters. *Remote Sensing of Environment*, 163, 256-268.
- **Nechad, B., et al. (2010)**. Calibration and validation of a generic multisensor algorithm for mapping of total suspended matter in turbid waters. *Remote Sensing of Environment*, 114(4), 854-866.
- **Nechad, B., et al. (2016)**. Sensor-specific calibration of a semi-analytical algorithm for turbidity and TSS from Sentinel-2 MSI and Landsat-8 OLI. *Earth System Science Data*, 8(2), 227-250.
- **Vos, K., et al. (2019)**. CoastSat: A Google Earth Engine-enabled Python toolkit to extract shorelines from publicly available satellite imagery. *Environmental Modelling & Software*, 122, 104528.

---

## 🧪 Testing

```bash
python -m pytest tests/ -v
```

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.
