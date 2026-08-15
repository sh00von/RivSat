# 🌊 RivSat Documentation Portal

Welcome to the official documentation for **RivSat** — a universal, physics-based, multi-parameter satellite remote sensing and hydro-engineering platform designed for **Water Resources Engineers**, **Hydrologists**, and **Environmental Researchers**.

> [!NOTE]
> **RivSat** provides an interactive, end-to-end Python pipeline for downloading, processing, analyzing, and exporting water quality products from **Sentinel-2 MSI** and **Landsat 8/9 OLI** via **Google Earth Engine (GEE)**.

---

## 📚 Complete Documentation Suite

| Guide | Description | Target Audience |
| :--- | :--- | :--- |
| 📖 [**Literature Review**](LITERATURE_REVIEW.md) | Comprehensive academic review of bio-optical algorithms and peer-reviewed studies (Dogliotti 2015, Nechad 2010/2016, Mishra 2012, Griffin 2018, Subramaniam 2011, Lee 2015). | Researchers, Academics, Remote Sensing Specialists |
| 🧮 [**Algorithms & Physics Guide**](ALGORITHMS_GUIDE.md) | Mathematical equations, spectral band formulations, radiative transfer models, and water masking logic for all 6 parameters. | Bio-Optical Scientists, Software Developers |
| 🚀 [**User Guide & Quickstart**](USER_GUIDE.md) | Step-by-step instructions for installation, GEE setup, spatial vector layer creation, and notebook execution. | All Users & Practitioners |
| 🏗️ [**Hydro-Engineering Guide**](HYDRO_ENGINEERING_GUIDE.md) | Practical applications for river engineering: Active channel width ($W$), longitudinal chainage profiles, and estuarine salinity tracking. | Civil & Water Resources Engineers, Hydrologists |
| 🗺️ [**GIS Integration Guide**](GIS_INTEGRATION.md) | Details on Cloud-Optimized GeoTIFF exports, QGIS/ArcGIS workflows, CSV reports, and GeoJSON vector layers. | GIS Analysts, Spatial Data Engineers |

---

## 🏗️ System Architecture

```
+-----------------------------------------------------------------------------------------+
|                                    RIVSAT PLATFORM                                      |
+-----------------------------------------------------------------------------------------+
|                                                                                         |
|  [1. USER INPUTS & VECTOR LAYERS]                                                       |
|   ├── user_roi.geojson      (AOI Bounding Polygon)                                      |
|   ├── centerline.geojson    (River Centerline Polyline)                                 |
|   └── stations.geojson      (Virtual Monitoring Pins)                                   |
|                                                                                         |
|  [2. GOOGLE EARTH ENGINE DATA ENGINE]                                                   |
|   ├── Sentinel-2 MSI SR     (Harmonized COPERNICUS/S2_SR_HARMONIZED - 20m)               |
|   └── Landsat 8/9 OLI       (Collection 2 Tier 1 Level 2 - 30m)                         |
|                                                                                         |
|  [3. RADIATIVE TRANSFER & INVERSION ENGINE]                                             |
|   ├── 1. Turbidity (FNU)      [Dogliotti Dual-Band Blended Switching]                   |
|   ├── 2. TSS (mg/L)           [Nechad Semi-Analytical Model]                            |
|   ├── 3. Chlorophyll-a (ug/L) [NDCI Red-Edge Algorithm]                                 |
|   ├── 4. CDOM (m^-1)          [Green/Red Ratio Model]                                   |
|   ├── 5. Salinity (PSU)       [CDOM Estuarine Mixing Proxy]                             |
|   └── 6. Secchi Depth (m)     [QAA Underwater Visibility Model]                         |
|                                                                                         |
|  [4. HYDRO-ENGINEERING ANALYTICS]                                                       |
|   ├── Active Channel Width (W in meters) along Cross-River Transects                   |
|   ├── Along-River Longitudinal Chainage Profiles (km vs Parameters)                    |
|   └── Mann-Kendall Trend & Sen's Slope Rate of Change Tests                             |
|                                                                                         |
|  [5. GIS & REPORT EXPORTS]                                                              |
|   ├── Cloud-Optimized GeoTIFF Rasters (outputs/<SITE_NAME>/rasters/*.tif)               |
|   ├── CSV Time-Series Data Reports                                                      |
|   └── Publication-Ready Figures (6-Panel Suites, Transects, Trends)                    |
+-----------------------------------------------------------------------------------------+
```

---

## 🛰️ Supported Satellite Constellations

RivSat seamlessly harmonizes imagery across satellite platforms using **Cross-Sensor Spectral Band Adjustment Factors (SBAF)**:

- **Sentinel-2A / 2B / 2C MSI**: $10\text{m}-20\text{m}$ resolution, 5-day revisit rate. Features the key **$705\text{ nm}$ Red-Edge Band (B5)** for high-turbidity plumes and Chlorophyll-a (NDCI).
- **Landsat 8 / 9 OLI**: $30\text{m}$ resolution ($100\text{m}$ thermal TIRS), 8-day combined revisit rate. Provides historical continuity extending back to 2013.

> [!TIP]
> **Multi-Sensor Fusion**: Combining Sentinel-2 and Landsat 8/9 increases satellite revisit frequency to **2–3 days**, crucial for capturing flash flood turbidity pulses and seasonal estuarine dynamics!

---

## 📜 Citation

If you use **RivSat** in your academic research, thesis, or engineering reports, please cite:

```bibtex
@software{rivsat2026,
  author = {Shovon et al.},
  title = {RivSat: A Universal Multi-Parameter Satellite Remote Sensing & Hydro-Engineering Platform for Rivers and Estuaries},
  year = {2026},
  url = {https://github.com/sh00von/RivSat}
}
```
