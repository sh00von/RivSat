# 🚀 RivSat User Guide & Quickstart Tutorial

This guide provides step-by-step instructions to set up, configure, and execute **RivSat** for satellite water quality estimation and river engineering analytics.

---

## 1. Installation & Environment Setup

### 1.1. Environment Prerequisites
- Python **3.9+** (Miniforge / Anaconda recommended)
- `earthengine-api`, `rasterio`, `folium`, `geopandas`, `matplotlib`, `pandas`, `scipy`, `pytest`

### 1.2. Install Dependencies
In your PowerShell / Terminal:

```powershell
# Clone or open RivSat repository
cd d:\Softw\bio-optic-river

# Install required dependencies
pip install -r requirements.txt

# Install RivSat in editable development mode
pip install -e .
```

---

## 2. Google Earth Engine (GEE) Authentication

RivSat queries GEE to download cloud-masked satellite imagery composites. Authenticate GEE once in your terminal:

```powershell
earthengine authenticate
```

---

## 3. Step-by-Step Workflow Guide

Launch Jupyter Lab to run the master workflow notebook:

```powershell
python -m jupyterlab RivSat_Workflow.ipynb
```

---

### Step 1: User Configuration Block
Open Cell 1 of `RivSat_Workflow.ipynb` and set your top-level study parameters:

```python
SITE_NAME = "Karnaphuli_River_Site"     # Unique site identifier
START_DATE = "2023-01-01"                # Acquisition start date
END_DATE = "2023-12-31"                  # Acquisition end date
ACQUISITION_MODE = "seasonal"            # Modes: 'annual', 'seasonal', 'monthly', 'daily_overpass'
SENSORS = ["S2", "L8"]                   # Sensors: Sentinel-2 ("S2"), Landsat 8/9 ("L8", "L9")
MAX_CLOUD_COVER = 20.0                   # Max cloud cover %
```

---

### Step 2: Spatial Layer Ingestion & Interactive Drawing
RivSat automatically ingests vector features from `./data/`:
- **`user_roi.geojson`**: Study area bounding box / polygon.
- **`centerline.geojson`**: River centerline polyline.
- **`stations.geojson`**: Virtual monitoring station pins.

*Note: If `centerline.geojson` or `stations.geojson` are missing, interactive folium maps in **Step 2B & 2C** allow you to draw them directly inside Jupyter Lab and click **Export**!*

---

### Step 3: GEE Satellite Acquisition
Downloads Sentinel-2 MSI and Landsat 8/9 OLI surface reflectance composites into `./data/<SITE_NAME>/`.

---

### Step 4 & 5: Batch Radiative Transfer Inversion & Product Suite
Executes parallel bio-optical processing for all 6 water quality parameters and renders a 6-panel scientific grid comparison figure (`multiparameter_grid_plot.png`).

---

### Step 6: Virtual Stations Time-Series & Mann-Kendall Trends
Extracts multi-temporal time-series records across all virtual stations for **all 6 parameters** and calculates:
- Non-parametric **Mann-Kendall trend $Z$-statistic** and $p$-value.
- **Sen's slope annual rate of change**.

---

### Step 7: Along-River Profiles & Active Channel Width
Extracts along-river longitudinal chainage profiles ($km$ vs parameter value) and calculates **Active River Channel Width ($W$ in meters)** along perpendicular transects.

---

### Step 8: GIS GeoTIFF Exporter
Summarizes all generated GeoTIFF rasters in `outputs/<SITE_NAME>/rasters/` ready for loading into QGIS or ArcGIS.

---

## 4. Running Automated Unit Tests

To verify package integrity:

```powershell
python -m pytest tests/test_rivsat.py -v
```
