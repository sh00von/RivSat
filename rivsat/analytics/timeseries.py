"""
Time-series compilation, temporal aggregation, and outlier filtering.

Builds chronological datasets from multi-scene satellite passes for virtual stations
and river transects.
"""

import os
import glob
import json
import numpy as np
import pandas as pd
import rasterio
from typing import List, Dict, Any, Optional

from .transects import extract_station_data


class TimeSeriesEngine:
    """
    Assembles and analyzes multi-temporal water quality time-series across processed scenes.
    """

    def __init__(self, processed_dirs: List[str]):
        """
        Parameters
        ----------
        processed_dirs : list of str
            List of directories containing processed scene rasters and metadata.
        """
        self.scene_dirs = [os.path.abspath(d) for d in processed_dirs]

    @classmethod
    def from_site_folder(cls, site_folder: str) -> "TimeSeriesEngine":
        """Discovers all processed scene folders within a site root directory."""
        candidates = [
            os.path.join(site_folder, d)
            for d in os.listdir(site_folder)
            if os.path.isdir(os.path.join(site_folder, d))
        ]
        return cls(candidates)

    def extract_station_timeseries(
        self,
        stations: List[Dict[str, Any]],
        parameter: str = "turbidity",
        buffer_pixels: int = 1
    ) -> pd.DataFrame:
        """
        Extracts chronological time-series records for all stations.

        Parameters
        ----------
        stations : list of dict
            List of virtual station definitions.
        parameter : str
            'turbidity' (FNU) or 'tss' (mg/L).

        Returns
        -------
        pd.DataFrame
            Sorted time-series DataFrame.
        """
        records = []

        file_tag = "Turbidity_FNU" if parameter.lower().startswith("turb") else "TSS_mgL"

        for s_dir in self.scene_dirs:
            meta_path = os.path.join(s_dir, "metadata.json")
            if os.path.exists(meta_path):
                with open(meta_path, "r") as f:
                    meta = json.load(f)
                sensor = meta.get("sensor", "Unknown")
                date_str = meta.get("date", "Unknown")
            else:
                bname = os.path.basename(s_dir)
                parts = bname.split("_")
                sensor = parts[0]
                date_str = "_".join(parts[1:])

            # Locate target GeoTIFF
            tifs = glob.glob(os.path.join(s_dir, f"*{file_tag}*.tif"))
            if not tifs:
                continue

            target_tif = tifs[0]
            with rasterio.open(target_tif) as src:
                data = src.read(1)
                transform = src.transform

            station_stats = extract_station_data(data, transform, stations, buffer_pixels=buffer_pixels)

            # Robust composite & scene datetime parsing
            dt = pd.NaT
            try:
                dt = pd.to_datetime(date_str.replace("_", " "))
            except Exception:
                pass

            if pd.isna(dt):
                parts = date_str.split("_")
                if len(parts) >= 1 and parts[0].isdigit() and len(parts[0]) == 4:
                    year = int(parts[0])
                    if "Monthly" in date_str and len(parts) >= 2 and parts[1].isdigit():
                        month = int(parts[1])
                        dt = pd.Timestamp(year, month, 15)
                    elif "Winter" in date_str:
                        dt = pd.Timestamp(year, 1, 15)
                    elif "PreMonsoon" in date_str:
                        dt = pd.Timestamp(year, 4, 15)
                    elif "Monsoon" in date_str:
                        dt = pd.Timestamp(year, 7, 15)
                    elif "PostMonsoon" in date_str:
                        dt = pd.Timestamp(year, 10, 15)
                    else: # Annual
                        dt = pd.Timestamp(year, 7, 1)

            for stat in station_stats:
                records.append({
                    "datetime": dt,
                    "date_str": date_str,
                    "sensor": sensor,
                    "station_name": stat["station_name"],
                    "lon": stat["lon"],
                    "lat": stat["lat"],
                    "valid_pixels": stat["valid_pixels"],
                    f"{parameter}_mean": stat["mean"],
                    f"{parameter}_median": stat["median"],
                    f"{parameter}_std": stat["std"],
                    f"{parameter}_p10": stat["p10"],
                    f"{parameter}_p90": stat["p90"],
                })

        df = pd.DataFrame(records)
        if not df.empty and "datetime" in df.columns:
            df = df.sort_values("datetime").reset_index(drop=True)

        return df

    @staticmethod
    def interpolate_gaps(
        df: pd.DataFrame,
        parameter: str = "turbidity",
        method: str = "linear"
    ) -> pd.DataFrame:
        """
        Fills missing temporal observation gaps across virtual stations using linear or time interpolation.
        """
        if df.empty or "datetime" not in df.columns:
            return df

        val_col = f"{parameter}_mean"
        interpolated_groups = []
        for _, group in df.groupby("station_name"):
            group = group.sort_values("datetime").copy()
            if val_col in group.columns:
                group[val_col] = group[val_col].interpolate(method=method, limit_direction="both")
                med_col = f"{parameter}_median"
                if med_col in group.columns:
                    group[med_col] = group[med_col].interpolate(method=method, limit_direction="both")
            interpolated_groups.append(group)

        if interpolated_groups:
            result = pd.concat(interpolated_groups, ignore_index=True)
            return result.sort_values("datetime").reset_index(drop=True)
        return df

    @staticmethod
    def filter_outliers(
        df: pd.DataFrame,
        value_column: str,
        z_threshold: float = 3.0,
        min_valid_pixels: int = 1
    ) -> pd.DataFrame:
        """
        Filters anomalous outliers from the time-series using statistical Z-score thresholding
        and minimum valid pixel constraints.
        """
        if df.empty:
            return df

        cleaned = df[df["valid_pixels"] >= min_valid_pixels].copy()

        # Group by station to filter per station
        filtered_dfs = []
        for _, group in cleaned.groupby("station_name"):
            vals = group[value_column].dropna()
            if len(vals) > 3:
                mean = vals.mean()
                std = vals.std()
                if std > 0:
                    z_scores = np.abs((group[value_column] - mean) / std)
                    group = group[z_scores <= z_threshold]
            filtered_dfs.append(group)

        if filtered_dfs:
            result = pd.concat(filtered_dfs, ignore_index=True)
            if "datetime" in result.columns:
                result = result.sort_values("datetime").reset_index(drop=True)
            return result
        return cleaned

    @staticmethod
    def compute_monthly_climatology(
        df: pd.DataFrame,
        value_column: str
    ) -> pd.DataFrame:
        """
        Aggregates time-series into monthly climatological means and percentiles
        to reveal seasonal sediment hydrodynamics.
        """
        if df.empty or "datetime" not in df.columns:
            return pd.DataFrame()

        clean = df.dropna(subset=["datetime", value_column]).copy()
        clean["month"] = clean["datetime"].dt.month

        climatology = clean.groupby(["station_name", "month"])[value_column].agg(
            mean="mean",
            median="median",
            std="std",
            p10=lambda x: np.percentile(x, 10),
            p90=lambda x: np.percentile(x, 90),
            count="count"
        ).reset_index()

        return climatology


def calculate_temporal_trends(
    df: pd.DataFrame,
    parameter: str = "turbidity"
) -> Dict[str, Any]:
    """
    Computes Mann-Kendall monotonic trend test, Sen's slope, and seasonal breakdown
    across virtual monitoring stations.

    Parameters
    ----------
    df : pd.DataFrame
        Time-series DataFrame from extract_station_timeseries.
    parameter : str
        Parameter name ('turbidity' or 'tss').

    Returns
    -------
    dict
        {'trends': DataFrame of Mann-Kendall & Sen's Slope statistics,
         'seasonal': DataFrame of seasonal mean/std breakdown}
    """
    from math import erf

    val_col = f"{parameter}_mean"
    if df.empty or val_col not in df.columns:
        return {"trends": pd.DataFrame(), "seasonal": pd.DataFrame()}

    trend_records = []
    season_records = []

    for st_name, sub in df.groupby("station_name"):
        sub_valid = sub.dropna(subset=[val_col]).copy()
        if "datetime" in sub_valid.columns:
            sub_valid = sub_valid.sort_values("datetime")

        y = sub_valid[val_col].values
        n = len(y)

        if n >= 3:
            # Mann-Kendall test statistic S
            diffs = y[:, None] - y[None, :]
            s = np.sum(np.sign(np.triu(diffs, 1)))

            # Variance of S
            var_s = (n * (n - 1) * (2 * n + 5)) / 18.0
            if s > 0:
                z = (s - 1.0) / np.sqrt(var_s)
            elif s < 0:
                z = (s + 1.0) / np.sqrt(var_s)
            else:
                z = 0.0

            # Two-tailed p-value using standard normal CDF
            p_val = float(2.0 * (1.0 - 0.5 * (1.0 + erf(abs(z) / np.sqrt(2.0)))))

            # Sen's slope
            if "datetime" in sub_valid.columns and sub_valid["datetime"].notna().all():
                dts = sub_valid["datetime"].values.astype("datetime64[D]").astype(float)
                dt_diffs = dts[:, None] - dts[None, :]
                mask = np.triu(np.ones((n, n), dtype=bool), 1) & (dt_diffs > 0)
                if np.any(mask):
                    slopes = diffs[mask] / dt_diffs[mask]
                    sens_slope_annual = float(np.median(slopes)) * 365.25
                else:
                    sens_slope_annual = 0.0
            else:
                sens_slope_annual = 0.0

            trend_dir = "Increasing" if z > 1.96 else ("Decreasing" if z < -1.96 else "Stable")
        else:
            z, p_val, sens_slope_annual = 0.0, 1.0, 0.0
            trend_dir = "Single Observation" if n == 1 else "Insufficient Data (N < 3)"

        trend_records.append({
            "station_name": st_name,
            "N_observations": n,
            "mean_val": float(np.mean(y)) if n > 0 else np.nan,
            "min_val": float(np.min(y)) if n > 0 else np.nan,
            "max_val": float(np.max(y)) if n > 0 else np.nan,
            "mann_kendall_z": round(z, 3),
            "p_value": round(p_val, 4),
            "sens_slope_annual": round(sens_slope_annual, 3),
            "trend_direction": trend_dir
        })

        # Seasonal breakdown
        if "datetime" in sub_valid.columns and sub_valid["datetime"].notna().any():
            months = sub_valid["datetime"].dt.month
            season_map = {
                12: "Winter/Dry", 1: "Winter/Dry", 2: "Winter/Dry",
                3: "Pre-Monsoon", 4: "Pre-Monsoon", 5: "Pre-Monsoon",
                6: "Monsoon", 7: "Monsoon", 8: "Monsoon",
                9: "Post-Monsoon", 10: "Post-Monsoon", 11: "Post-Monsoon"
            }
            sub_valid["season"] = months.map(season_map)
            for s_name, s_group in sub_valid.groupby("season"):
                season_records.append({
                    "station_name": st_name,
                    "season": s_name,
                    "mean": float(s_group[val_col].mean()),
                    "std": float(s_group[val_col].std()) if len(s_group) > 1 else 0.0,
                    "count": int(len(s_group))
                })

    return {
        "trends": pd.DataFrame(trend_records),
        "seasonal": pd.DataFrame(season_records)
    }
