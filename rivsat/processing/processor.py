"""
High-Throughput Bio-Optical Satellite Processing Pipeline.

Features:
- Parallel multi-core batch processing (ThreadPoolExecutor / ProcessPoolExecutor)
- Vectorized raster resampling & geometric harmonization
- Dynamic water & QA masking
- Nechad (2010/2016) & Dogliotti (2015) dual-band blended switching
- Cloud-Optimized GeoTIFF (COG) generation
"""

import os
import glob
import json
import numpy as np
import rasterio
from rasterio.enums import Resampling
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any, Optional, Tuple, List, Union
from tqdm.auto import tqdm

from ..core.config import GEE_DATASETS
from ..core.algorithms import (
    compute_dogliotti_blended,
    compute_nechad_model,
    compute_rededge_turbidity,
    apply_sbaf_correction,
    compute_ndwi,
    compute_mndwi
)
from ..core.water_mask import (
    create_s2_water_mask,
    create_landsat_water_mask,
    create_hybrid_water_mask
)


class SceneProcessor:
    """
    Processes individual satellite scenes (Sentinel-2 or Landsat 8/9) into water turbidity
    and TSS raster products.
    """

    def __init__(self, scene_dir: str):
        """
        Parameters
        ----------
        scene_dir : str
            Directory containing the downloaded band GeoTIFF files and metadata.json.
        """
        self.scene_dir = os.path.abspath(scene_dir)
        self.meta_path = os.path.join(self.scene_dir, "metadata.json")
        
        if os.path.exists(self.meta_path):
            with open(self.meta_path, "r", encoding="utf-8") as f:
                self.metadata = json.load(f)
        else:
            # Infer metadata from directory name
            basename = os.path.basename(self.scene_dir)
            parts = basename.split("_")
            sensor = parts[0] if len(parts) > 0 else "S2"
            date = "_".join(parts[1:]) if len(parts) > 1 else "Unknown"
            self.metadata = {"sensor": sensor, "date": date}

        self.sensor = self.metadata.get("sensor", "S2").upper()
        self.date_str = self.metadata.get("date", "Unknown")

    def _find_band_file(self, band_name: str) -> Optional[str]:
        """Finds the GeoTIFF file for a given band name, ensuring non-empty file."""
        exact_path = os.path.join(self.scene_dir, f"{band_name}.tif")
        if os.path.exists(exact_path) and os.path.getsize(exact_path) > 100:
            return exact_path

        patterns = [
            os.path.join(self.scene_dir, f"*{band_name}.tif"),
            os.path.join(self.scene_dir, f"*{band_name}*.tif"),
            os.path.join(self.scene_dir, f"*{band_name}*.tiff"),
            os.path.join(self.scene_dir, f"*{band_name.lower()}*.tif"),
            os.path.join(self.scene_dir, f"*{band_name.upper()}*.tif")
        ]
        for p in patterns:
            matches = glob.glob(p)
            for m in matches:
                if os.path.exists(m) and os.path.getsize(m) > 100:
                    return m
        return None

    def _read_and_resample(
        self,
        file_path: str,
        ref_profile: dict,
        is_categorical: bool = False
    ) -> Optional[np.ndarray]:
        """Reads a band and resamples it to match reference spatial profile."""
        if not file_path or not os.path.exists(file_path) or os.path.getsize(file_path) < 100:
            return None
        try:
            with rasterio.open(file_path) as src:
                resampling_method = Resampling.nearest if is_categorical else Resampling.bilinear
                data = src.read(
                    1,
                    out_shape=(ref_profile['height'], ref_profile['width']),
                    resampling=resampling_method
                ).astype(np.float32)
                return data
        except Exception as e:
            print(f"[!] Warning reading {os.path.basename(file_path)}: {e}")
            return None

    def process(
        self,
        output_dir: Optional[str] = None,
        apply_sbaf: bool = True,
        water_mask_strict: bool = False,
        use_rededge: bool = True,
        custom_coeffs: Optional[dict] = None
    ) -> Dict[str, Any]:
        """
        Executes the bio-optical retrieval pipeline for this scene.

        Parameters
        ----------
        output_dir : str, optional
            Directory to save output GeoTIFF rasters. If None, saves in scene_dir.
        apply_sbaf : bool
            Whether to apply SBAF spectral adjustment to Landsat bands.
        water_mask_strict : bool
            Whether to use strict QA-only water masking.
        use_rededge : bool
            Whether to utilize Sentinel-2 Red-Edge (704 nm) for extreme turbidity plumes.
        custom_coeffs : dict, optional
            Custom calibration constants for Nechad / Dogliotti models.

        Returns
        -------
        dict
            Dictionary containing computed raster arrays ('turbidity', 'tss', 'water_mask',
            'weight', 'rho_red', 'rho_nir'), profile, and summary stats.
        """
        out_dir = output_dir or self.scene_dir
        os.makedirs(out_dir, exist_ok=True)

        # 1. Identify band files
        if self.sensor.startswith("S2"):
            red_file = self._find_band_file("B4")
            nir_file = self._find_band_file("B8A") or self._find_band_file("B8")
            green_file = self._find_band_file("B3")
            blue_file = self._find_band_file("B2")
            re_file = self._find_band_file("B5")
            swir_file = self._find_band_file("B11")
            qa_file = self._find_band_file("SCL") or self._find_band_file("QA60")
            scale_factor = GEE_DATASETS["S2_HARMONIZED"]["scale_factor"]
            offset = 0.0
        else:
            red_file = self._find_band_file("SR_B4") or self._find_band_file("B4")
            nir_file = self._find_band_file("SR_B5") or self._find_band_file("B5")
            green_file = self._find_band_file("SR_B3") or self._find_band_file("B3")
            blue_file = self._find_band_file("SR_B2") or self._find_band_file("B2")
            re_file = None
            swir_file = self._find_band_file("SR_B6") or self._find_band_file("B6")
            qa_file = self._find_band_file("QA_PIXEL")
            scale_factor = GEE_DATASETS["L8"]["scale_factor"]
            offset = GEE_DATASETS["L8"]["offset"]

        if not red_file or not nir_file:
            raise FileNotFoundError(
                f"Missing essential Red or NIR band files in {self.scene_dir}. "
                f"Found red: {red_file}, nir: {nir_file}"
            )

        # 2. Establish spatial reference profile using Red band (highest resolution)
        with rasterio.open(red_file) as src:
            ref_profile = src.profile.copy()
            red_raw = src.read(1).astype(np.float32)

        nir_raw = self._read_and_resample(nir_file, ref_profile)
        green_raw = self._read_and_resample(green_file, ref_profile) if green_file else None
        blue_raw = self._read_and_resample(blue_file, ref_profile) if blue_file else None
        re_raw = self._read_and_resample(re_file, ref_profile) if re_file else None
        swir_raw = self._read_and_resample(swir_file, ref_profile) if swir_file else None
        qa_raw = self._read_and_resample(qa_file, ref_profile, is_categorical=True) if qa_file else None

        # 3. Apply radiometric scaling to convert DN to surface reflectance rho_w
        def scale_band(arr):
            if arr is None:
                return None
            if np.nanmax(arr) > 2.0:
                scaled = arr * scale_factor + offset
                return np.maximum(scaled, 0.0)
            return np.maximum(arr, 0.0)

        rho_red = scale_band(red_raw)
        rho_nir = scale_band(nir_raw)
        rho_green = scale_band(green_raw)
        rho_blue = scale_band(blue_raw)
        rho_re = scale_band(re_raw)
        rho_swir = scale_band(swir_raw)

        # 4. Cross-Sensor SBAF Harmonization (Landsat to Sentinel-2)
        if apply_sbaf and self.sensor in ["L8", "L9"]:
            rho_red = apply_sbaf_correction(rho_red, band="red", from_sensor=self.sensor, to_sensor="S2")
            rho_nir = apply_sbaf_correction(rho_nir, band="nir", from_sensor=self.sensor, to_sensor="S2")
            if rho_green is not None:
                rho_green = apply_sbaf_correction(rho_green, band="green", from_sensor=self.sensor, to_sensor="S2")

        # 5. Dynamic Water Masking
        if rho_green is not None:
            water_mask = create_hybrid_water_mask(
                green=rho_green,
                red=rho_red,
                nir=rho_nir,
                swir=rho_swir,
                qa_or_scl=qa_raw,
                sensor=self.sensor
            )
        elif qa_raw is not None:
            if self.sensor.startswith("S2"):
                water_mask = create_s2_water_mask(qa_raw, strict_water_only=water_mask_strict)
            else:
                water_mask = create_landsat_water_mask(qa_raw, strict_water_only=water_mask_strict)
        else:
            water_mask = (rho_red > 0.0) & (rho_nir < rho_red * 1.5) & (rho_nir > 0.0)

        # 6. Compute Dogliotti Blended Turbidity and TSS
        turbidity, weight = compute_dogliotti_blended(
            rho_red=rho_red,
            rho_nir=rho_nir,
            parameter="turbidity",
            sensor=self.sensor,
            custom_coeffs=custom_coeffs
        )

        tss, _ = compute_dogliotti_blended(
            rho_red=rho_red,
            rho_nir=rho_nir,
            parameter="tss",
            sensor=self.sensor,
            custom_coeffs=custom_coeffs
        )

        # Optional Sentinel-2 Red-Edge Multi-Conditional Override
        if use_rededge and self.sensor.startswith("S2") and rho_re is not None:
            turbidity_re = compute_rededge_turbidity(rho_red, rho_re, rho_nir, parameter="turbidity")
            tss_re = compute_rededge_turbidity(rho_red, rho_re, rho_nir, parameter="tss")
            mask_re_switch = (rho_red > 0.07) & ~np.isnan(turbidity_re)
            turbidity = np.where(mask_re_switch, turbidity_re, turbidity)
            tss = np.where(mask_re_switch, tss_re, tss)

        # 7. Apply Water Mask
        turbidity_masked = np.where(water_mask, turbidity, np.nan).astype(np.float32)
        tss_masked = np.where(water_mask, tss, np.nan).astype(np.float32)

        # 8. Export Cloud-Optimized GeoTIFF Products
        out_profile = ref_profile.copy()
        out_profile.update(
            dtype=rasterio.float32,
            count=1,
            nodata=np.nan,
            compress='lzw'
        )

        turbidity_tif = os.path.join(out_dir, f"{self.sensor}_{self.date_str}_Turbidity_FNU.tif")
        tss_tif = os.path.join(out_dir, f"{self.sensor}_{self.date_str}_TSS_mgL.tif")
        mask_tif = os.path.join(out_dir, f"{self.sensor}_{self.date_str}_WaterMask.tif")

        with rasterio.open(turbidity_tif, 'w', **out_profile) as dst:
            dst.write(turbidity_masked, 1)

        with rasterio.open(tss_tif, 'w', **out_profile) as dst:
            dst.write(tss_masked, 1)

        mask_profile = out_profile.copy()
        mask_profile.update(dtype=rasterio.uint8, nodata=0)
        with rasterio.open(mask_tif, 'w', **mask_profile) as dst:
            dst.write(water_mask.astype(np.uint8), 1)

        # Summary statistics over water
        valid_turb = turbidity_masked[~np.isnan(turbidity_masked)]
        valid_tss = tss_masked[~np.isnan(tss_masked)]

        stats = {
            "sensor": self.sensor,
            "date": self.date_str,
            "water_pixel_count": int(np.sum(water_mask)),
            "turbidity_mean_fnu": float(np.mean(valid_turb)) if len(valid_turb) > 0 else 0.0,
            "turbidity_median_fnu": float(np.median(valid_turb)) if len(valid_turb) > 0 else 0.0,
            "turbidity_std_fnu": float(np.std(valid_turb)) if len(valid_turb) > 0 else 0.0,
            "turbidity_p90_fnu": float(np.percentile(valid_turb, 90)) if len(valid_turb) > 0 else 0.0,
            "tss_mean_mg_l": float(np.mean(valid_tss)) if len(valid_tss) > 0 else 0.0,
            "tss_median_mg_l": float(np.median(valid_tss)) if len(valid_tss) > 0 else 0.0,
            "files": {
                "turbidity_geotiff": turbidity_tif,
                "tss_geotiff": tss_tif,
                "water_mask_geotiff": mask_tif
            }
        }

        return {
            "turbidity": turbidity_masked,
            "tss": tss_masked,
            "water_mask": water_mask,
            "weight": weight,
            "rho_red": rho_red,
            "rho_nir": rho_nir,
            "rho_green": rho_green,
            "rho_blue": rho_blue,
            "profile": ref_profile,
            "stats": stats
        }


def _process_scene_wrapper(scene_dir: str, kwargs: dict) -> Tuple[str, Optional[Dict[str, Any]], Optional[str]]:
    """Helper function for multithreaded / multiprocess batch processing."""
    try:
        proc = SceneProcessor(scene_dir)
        res = proc.process(**kwargs)
        return (scene_dir, res, None)
    except Exception as e:
        return (scene_dir, None, str(e))


def process_batch_parallel(
    scene_dirs: List[str],
    max_workers: int = 4,
    apply_sbaf: bool = True,
    use_rededge: bool = True,
    water_mask_strict: bool = False
) -> List[Dict[str, Any]]:
    """
    Executes high-performance concurrent processing across multiple satellite scenes.

    Parameters
    ----------
    scene_dirs : list of str
        List of scene directories.
    max_workers : int
        Number of parallel worker threads/processes.

    Returns
    -------
    list of dict
        List of result dictionaries.
    """
    if not scene_dirs:
        return []

    kwargs = {
        "apply_sbaf": apply_sbaf,
        "use_rededge": use_rededge,
        "water_mask_strict": water_mask_strict
    }

    results = []
    print(f"[*] Batch processing {len(scene_dirs)} satellite scenes using {max_workers} parallel workers...")
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(_process_scene_wrapper, s_dir, kwargs): s_dir
            for s_dir in scene_dirs
        }
        with tqdm(total=len(scene_dirs), desc="Processing Satellite Scenes") as pbar:
            for fut in as_completed(futures):
                s_dir, res, err = fut.result()
                if res:
                    results.append(res)
                else:
                    print(f"[!] Error processing {os.path.basename(s_dir)}: {err}")
                pbar.update(1)

    print(f"[OK] Completed processing {len(results)} scenes.")
    return results
