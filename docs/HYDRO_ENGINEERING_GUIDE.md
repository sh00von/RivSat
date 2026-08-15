# 🏗️ Hydro-Engineering Guide: River & Estuarine Analytics

This guide explains how **Water Resources Engineers**, **Hydrologists**, and **River Basin Managers** can utilize **RivSat** for engineering analytics.

---

## 1. Active River Channel Width ($W$ in Meters) & Bank Erosion Tracking

### Engineering Importance:
Riverbank erosion, channel bar (sandbar/char) migration, and sediment accretion threaten bridges, embankments, and coastal infrastructure.

### How RivSat Computes Channel Width ($W$):
RivSat generates CoastSat-style perpendicular transects along the river centerline. By intersecting transects with the hybrid water mask, RivSat measures the active channel width:

$$W = \text{cross\_dist}_{\max(\text{water})} - \text{cross\_dist}_{\min(\text{water})} \quad (\text{meters})$$

```
          Left Bank                                 Right Bank
           |~~~~~~~~~~~~~~~~ Active Water Channel ~~~~~~~~~~~~~~~~|
   --------+======================================================+--------
           | <--------------------- W (meters) -----------------> |
```

#### Application:
By tracking $W$ across multi-year satellite composites, engineers can quantify annual **bank retreat rates ($\text{m/year}$)** and identify critical erosion hotspots before structural failure occurs.

---

## 2. Along-River Longitudinal Chainage Profiles

### Engineering Importance:
Estuaries and river channels exhibit strong spatial gradients driven by tidal action, tributary confluence, and point-source discharge.

### RivSat Longitudinal Extraction:
RivSat samples water quality parameters at regular distance increments along the river centerline from upstream ($0\text{ km}$) to downstream mouth ($X\text{ km}$):

```
Upstream (0 km) ==============================================> Downstream Mouth (X km)
  [Turbidity: Low] --------------> [Tributary Confluence: High] ------> [Plume Dispersal]
```

#### Output Columns (`extract_longitudinal_profile`):
- `distance_km`: Chainage distance along river length.
- `lon`, `lat`: Geographic coordinates of sample node.
- `value`: Median water quality retrieval (FNU, mg/L, ug/L, PSU, or m).
- `std`: Spatial variability across local sampling window.

---

## 3. Estuarine Salinity Intrusion Monitoring

### Engineering Importance:
During dry seasonal periods, sea water moves upstream into estuaries, threatening municipal water supply intakes, industrial cooling plants, and agricultural irrigation.

### RivSat Salinity Proxy:
RivSat maps surface salinity ($\text{PSU}$) using the empirical CDOM dilution relationship:

$$\text{Salinity (PSU)} = 35.0 - 4.2 \cdot a_{cdom}(440)$$

Engineers can set safety thresholds (e.g. $1.0\text{ PSU}$ limit for drinking water intakes) and monitor the spatial boundary of the salt wedge across seasons!

---

## 4. Non-Parametric Mann-Kendall Trend & Sen's Slope Rate Analysis

RivSat computes non-parametric **Mann-Kendall trend tests** ($Z$-statistic, $p$-value) and **Sen's slope annual rate of change**:

- **$\text{Sen's Slope} > 0$**: Statistically significant degradation/increase in turbidity or sediment load ($\text{FNU/year}$ or $\text{mg/L/year}$).
- **$\text{Sen's Slope} < 0$**: Water clarity improvement or sediment trapping upstream (e.g. behind dams or reservoirs).
