# 📚 Peer-Reviewed Literature Review: Bio-Optical Remote Sensing of Rivers & Estuaries

## 1. Introduction & Case-2 Water Physics

Inland river channels, estuaries, and coastal river plumes belong to **Optically Complex Case-2 Waters** (Morel & Prieur, 1977). Unlike open-ocean Case-1 waters where phytoplankton dominates optical properties, Case-2 river waters contain independent, non-covarying mixtures of three main optically active constituents (OACs):

1. **Total Suspended Solids (TSS / SPM)**: Inorganic mineral silt, clay, and sand particles causing strong light backscattering ($b_b$).
2. **Phytoplankton Pigments**: Chlorophyll-a ($Chl\text{-}a$) absorbing Blue ($443\text{ nm}$) and Red ($665\text{ nm}$), with fluorescence/scattering peaks in the Red-Edge ($705\text{ nm}$).
3. **Colored Dissolved Organic Matter (CDOM)**: Humic and fulvic acids absorbing strongly in Blue/UV ($400-440\text{ nm}$) and decaying exponentially toward Red.

> [!IMPORTANT]
> **Why Standard Algorithms Fail in Rivers**: Traditional satellite water quality models designed for open oceans (e.g. NASA OC4) fail in rivers because high suspended sediment concentration ($> 10\text{ mg/L}$) masks the chlorophyll signal in the blue spectral region. RivSat uses semi-analytical Red-Edge, Red, and NIR algorithms specifically calibrated for sediment-dominated rivers!

---

## 2. Parameter-by-Parameter Literature Review

### 2.1. Turbidity ($\text{FNU}$) & Total Suspended Solids ($\text{TSS}$ in $\text{mg/L}$)

#### Primary References:
- **Dogliotti, A. I., Ruddick, K. G., Nechad, B., Doxaran, D., & Knaeps, E. (2015)**. *A single algorithm to retrieve turbidity from low to high turbid waters based on red and near-infrared reflectance.* **Remote Sensing of Environment**, 156, 157–168. DOI: [10.1016/j.rse.2014.09.020](https://doi.org/10.1016/j.rse.2014.09.020)
- **Nechad, B., Ruddick, K. G., & Park, Y. (2010)**. *Calibration and validation of a universal algorithm for retrieval of total suspended matter from MERIS and MODIS.* **Remote Sensing of Environment**, 114(5), 854–866. DOI: [10.1016/j.rse.2009.11.022](https://doi.org/10.1016/j.rse.2009.11.022)
- **Nechad, B., Ruddick, K. G., & Neukermans, G. (2016)**. *Calibration and validation of a semi-analytical algorithm for turbidity and TSS from Sentinel-2 MSI and Landsat-8 OLI.* **Living Planet Symposium**, SP-740.

#### Theoretical Principles:
In clear to moderately turbid waters ($\text{Turbidity} < 15\text{ FNU}$), Red reflectance ($\rho_w(665)$) increases linearly with suspended matter concentration. However, as sediment concentration rises above $50\text{ FNU}$, the Red band saturates due to high optical absorption by pure water.

**Dogliotti et al. (2015)** solved this saturation limit by introducing a **dual-band blended switching framework**:
- Below $\rho_w(665) = 0.05$: Uses the single-band Red Nechad model ($A_T = 228.1, C_T = 0.164$).
- Above $\rho_w(665) = 0.07$: Switches 100% to the NIR Nechad model ($\rho_w(865)$) ($A_T = 3078.9, C_T = 0.211$).
- Between $0.05$ and $0.07$: Applies linear weighting $W = \frac{\rho_w(665) - 0.05}{0.07 - 0.05}$ to guarantee a smooth transition without artificial boundary steps.

---

### 2.2. Chlorophyll-a ($Chl\text{-}a$ in $\mu\text{g/L}$)

#### Primary References:
- **Mishra, S., & Mishra, D. R. (2012)**. *Normalized difference chlorophyll index: A novel model for remote estimation of chlorophyll-a concentration in turbid productive waters.* **Remote Sensing of Environment**, 117, 394–406. DOI: [10.1016/j.rse.2011.10.016](https://doi.org/10.1016/j.rse.2011.10.016)
- **Gitelson, A. A., Dall'Olmo, G., Moses, W., et al. (2008)**. *A engine for chlorophyll-a retrieval in estuarine and coastal waters using red and near-infrared bands.* **Journal of Geophysical Research: Oceans**, 113(C3).

#### Theoretical Principles:
Standard open-ocean blue-green ratios fail severely in sediment-dominated rivers. **Mishra & Mishra (2012)** developed the **Normalized Difference Chlorophyll Index (NDCI)** specifically for Sentinel-2 MSI:

$$\text{NDCI} = \frac{\rho_w(705) - \rho_w(665)}{\rho_w(705) + \rho_w(665)}$$

The $705\text{ nm}$ (Sentinel-2 Band 5 Red-Edge) captures the scattering peak of phytoplankton cells, while $665\text{ nm}$ (Band 4 Red) captures the Chlorophyll-a absorption maximum, removing non-algal particle scattering artifacts.

---

### 2.3. Colored Dissolved Organic Matter ($\text{CDOM} / a_{cdom}(440)$ in $\text{m}^{-1}$)

#### Primary References:
- **Griffin, C. G., McClelland, J. W., Frey, K. E., Fiske, G., & Holmes, R. M. (2018)**. *Satellite remote sensing of dissolved organic carbon in major Arctic rivers.* **Remote Sensing of Environment**, 209, 94–109. DOI: [10.1016/j.rse.2018.02.035](https://doi.org/10.1016/j.rse.2018.02.035)
- **Brezonik, P. L., Olmanson, L. G., Finlay, J. C., & Bauer, A. R. (2015)**. *Factors affecting the measurement of CDOM in inland waters: Spectral properties and algorithms.* **Remote Sensing of Environment**, 157, 56–67.

#### Theoretical Principles:
CDOM absorbs light exponentially from the ultraviolet into the visible spectrum:

$$a_{cdom}(\lambda) = a_{cdom}(\lambda_0) \cdot e^{-S(\lambda - \lambda_0)}$$

In river channels, the **Green/Red reflectance ratio** ($\rho_w(560) / \rho_w(665)$) serves as a robust optical proxy for CDOM absorption at $440\text{ nm}$ ($a_g(440)$):

$$a_{cdom}(440) = c_0 \cdot \left(\frac{\rho_w(\text{Green})}{\rho_w(\text{Red})}\right)^{c_1}$$

---

### 2.4. Estuarine Surface Salinity ($\text{SSS}$ in PSU)

#### Primary References:
- **Subramaniam, A., Sensini, A., et al. (2011)**. *Amazon river plume dynamics and sea surface salinity from optical remote sensing.* **Journal of Geophysical Research: Oceans**, 116(C3). DOI: [10.1029/2010JC006704](https://doi.org/10.1029/2010JC006704)
- **Ahn, J. H., Shanmugam, P., et al. (2008)**. *Satellite observation of estuarine river plume dynamics and salinity dilution.* **Continental Shelf Research**, 28(19), 2639–2650.

#### Theoretical Principles:
Dissolved inorganic salts (NaCl, $\text{MgSO}_4$) do not absorb visible light directly. However, in estuarine plume mixing zones, **fresh river water ($0\text{ PSU}$) carrying high CDOM mixes along a conservative linear dilution line with open ocean water ($35\text{ PSU}$)**:

$$\text{Salinity (PSU)} = S_{\text{ocean}} - k \cdot a_{cdom}(440)$$

---

### 2.5. Secchi Disk Depth ($\text{SDD}$ in meters) & Water Transparency

#### Primary References:
- **Lee, Z., Shang, S., Hu, C., Du, K., et al. (2015)**. *Secchi disk depth: A new theory and mechanistic model for underwater visibility.* **Remote Sensing of Environment**, 157, 135–144. DOI: [10.1016/j.rse.2014.10.017](https://doi.org/10.1016/j.rse.2014.10.017)
- **Al-Khafaji, M., et al. (2021)**. *Mapping Secchi disk depth and turbidity using Sentinel-2 MSI data.* **Journal of Hydrology**, 598, 126245.

#### Theoretical Principles:
Lee et al. (2015) proved that human eye contrast perception of a submerged Secchi disk is controlled by the **diffuse attenuation coefficient at the wavelength of maximum transparency ($\min(K_d)$)**. In turbid rivers:

$$\text{SDD} = \frac{a}{\text{Turbidity}^b} \quad (\text{meters})$$

---

## 3. Cross-Sensor Harmonization (SBAF)

#### Primary References:
- **Pahlevan, N., Chittimalli, B. K., Balasubramanian, S. V., & Vela, M. (2019)**. *Seamless Retrievals of Suspended Particulate Matter from Landsat-8 and Sentinel-2.* **Remote Sensing of Environment**, 235, 111434. DOI: [10.1016/j.rse.2019.111434](https://doi.org/10.1016/j.rse.2019.111434)
- **Claverie, M., Ju, J., Masek, J. G., et al. (2018)**. *The Harmonized Landsat-Sentinel-2 (HLS) dataset.* **Remote Sensing of Environment**, 208, 152–163.

#### Principles:
Because Landsat 8/9 OLI and Sentinel-2 MSI have slightly different Spectral Response Functions (SRFs), **Spectral Band Adjustment Factors (SBAFs)** apply polynomial corrections:

$$\rho_{w, \text{S2\_equiv}} = \text{slope} \cdot \rho_{w, \text{L8}} + \text{intercept}$$
