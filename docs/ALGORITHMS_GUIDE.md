# 🧮 Algorithms & Radiative Transfer Formulation Guide

This document presents the complete mathematical, physical, and computational algorithms implemented in **RivSat**.

---

## 1. Bio-Optical Water Quality Inversion Suite

### 1.1. Turbidity ($\text{FNU}$) & TSS ($\text{mg/L}$)

#### Nechad Single-Band Model Formulation:
The semi-analytical Radiative Transfer equation (Nechad et al., 2010/2016):

$$T = \frac{A_T \cdot \rho_w(\lambda)}{1 - \frac{\rho_w(\lambda)}{C_T}} \qquad \text{and} \qquad \text{TSS} = \frac{A_S \cdot \rho_w(\lambda)}{1 - \frac{\rho_w(\lambda)}{C_S}}$$

where:
- $\rho_w(\lambda) = \pi \cdot R_{rs}(\lambda)$ is water-leaving reflectance (dimensionless).
- $A_T, A_S$ are dimensional calibration coefficients ($\text{FNU}$ or $\text{mg/L}$).
- $C_T, C_S$ are asymptotic saturation limits.

#### Nechad Model Coefficient Table:

| Parameter | Sensor | Band | Wavelength | $A$ | $C$ |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Turbidity (FNU)** | Sentinel-2 | B4 | $665\text{ nm}$ | $228.1$ | $0.164$ |
| | Sentinel-2 | B5 | $704\text{ nm}$ | $650.2$ | $0.185$ |
| | Sentinel-2 | B8A | $865\text{ nm}$ | $3078.9$ | $0.211$ |
| | Landsat 8/9 | B4 | $655\text{ nm}$ | $242.7$ | $0.169$ |
| | Landsat 8/9 | B5 | $865\text{ nm}$ | $2987.2$ | $0.211$ |
| **TSS (mg/L)** | Sentinel-2 | B4 | $665\text{ nm}$ | $245.5$ | $0.164$ |
| | Sentinel-2 | B5 | $704\text{ nm}$ | $710.0$ | $0.185$ |
| | Sentinel-2 | B8A | $865\text{ nm}$ | $3310.0$ | $0.211$ |
| | Landsat 8/9 | B4 | $655\text{ nm}$ | $260.8$ | $0.169$ |
| | Landsat 8/9 | B5 | $865\text{ nm}$ | $3215.0$ | $0.211$ |

#### Dogliotti Dual-Band Blended Switching Framework:
To prevent Red band saturation in turbid waters, Dogliotti et al. (2015) introduced a continuous linear blending weight $W$:

$$W = \text{clip}\left(\frac{\rho_w(665) - 0.05}{0.07 - 0.05}, 0.0, 1.0\right)$$
$$\text{Output} = (1 - W) \cdot T_{\text{red}} + W \cdot T_{\text{nir}}$$

---

### 1.2. Chlorophyll-a ($\mu\text{g/L}$) — NDCI Algorithm

$$\text{NDCI} = \frac{\rho_w(705) - \rho_w(665)}{\rho_w(705) + \rho_w(665)}$$
$$Chl\text{-}a = 14.039 + 86.11 \cdot \text{NDCI} + 194.32 \cdot \text{NDCI}^2 \quad (\mu\text{g/L})$$

---

### 1.3. Colored Dissolved Organic Matter ($\text{CDOM} / a_g(440)$ in $\text{m}^{-1}$)

$$a_{cdom}(440) = 1.25 \cdot \left(\frac{\rho_w(\text{Green})}{\rho_w(\text{Red})}\right)^{-1.42} \quad (\text{m}^{-1})$$

---

### 1.4. Estuarine Surface Salinity ($\text{SSS}$ in PSU)

$$\text{Salinity (PSU)} = \text{clip}\left(35.0 - 4.2 \cdot a_{cdom}(440), 0.0, 35.0\right)$$

---

### 1.5. Secchi Disk Depth ($\text{SDD}$ in meters)

$$\text{SDD} = \frac{1.7}{\text{maximum}(\text{Turbidity}, 0.1)^{0.8}} \quad (\text{meters})$$

---

## 2. Dynamic Water Masking Engine

RivSat combines physical spectral indices with satellite Quality Assurance (QA) bands to extract clean water surfaces without land contamination:

1. **Sentinel-2 SCL Masking**: Keeps class values `6` (Water), filtering `3` (Cloud Shadow), `8-10` (Clouds/Cirrus), and `4-5` (Vegetation/Bare Soil).
2. **Landsat 8/9 QA_PIXEL Bitmasking**: Decodes bit `7` (Water) and excludes cloud/shadow bits.
3. **MNDWI Spectral Index Water Extraction**:
   $$\text{MNDWI} = \frac{\text{Green} - \text{SWIR}}{\text{Green} + \text{SWIR}} > 0.0$$

---

## 3. Spatial Analytics & Active Channel Width ($W$)

### 3.1. Arc-Length Centerline Interpolation
RivSat computes parametric arc-length $S(t)$ along piecewise linear river centerlines using binary search (`np.searchsorted`) in $\mathcal{O}(M + N \log M)$ complexity:

$$t = \frac{S_{\text{target}} - S_{\text{cum}}[k]}{S_{\text{cum}}[k+1] - S_{\text{cum}}[k]}$$

### 3.2. Active Channel Width ($W$) Calculation
Along perpendicular cross-river transects of length $L$:
$$W = \max(X_{\text{water}}) - \min(X_{\text{water}}) \quad (\text{meters})$$
where $X_{\text{water}}$ represents valid contiguous water pixels along the transect line.
