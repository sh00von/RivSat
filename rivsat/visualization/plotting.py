"""
Publication-quality visualization and charting tools for water turbidity and TSS.

Provides:
- Spatial turbidity & TSS map rendering with oceanographic colormaps
- Multi-panel True-Color RGB vs. Bio-Optical product comparisons
- Virtual station time-series ribbon charts (with S2/L8 sensor discrimination)
- Longitudinal river centerline gradient plots (Chainage vs Turbidity)
- In-situ 1:1 validation scatter plots with statistical scorecards
"""

import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from typing import Optional, List, Dict, Any, Tuple

# Try to import cmocean for oceanographic colormaps; fallback gracefully
try:
    import cmocean
    TURBID_CMAP = cmocean.cm.turbid
    SPEED_CMAP = cmocean.cm.speed
except ImportError:
    TURBID_CMAP = "turbo"
    SPEED_CMAP = "viridis"

from scipy.ndimage import distance_transform_edt

def fill_spatial_cloud_gaps(
    raster_arr: np.ndarray,
    water_mask: Optional[np.ndarray] = None
) -> np.ndarray:
    """
    Smoothly interpolates missing/cloud-masked pixels inside river channel using
    Euclidean distance transform inpainting.

    Parameters
    ----------
    raster_arr : np.ndarray
        Turbidity or TSS raster array with NaNs for cloud/masked areas.
    water_mask : np.ndarray, optional
        Boolean water mask. If provided, restricts gap-filling strictly to water pixels.

    Returns
    -------
    np.ndarray
        Spatially reconstructed raster array with cloud holes filled.
    """
    if raster_arr is None:
        return raster_arr
    arr = np.asarray(raster_arr, dtype=np.float32).copy()
    nan_mask = np.isnan(arr)
    if not np.any(nan_mask) or np.all(nan_mask):
        return arr
    
    indices = distance_transform_edt(nan_mask, return_distances=False, return_indices=True)
    filled = arr[tuple(indices)]
    
    if water_mask is not None:
        filled = np.where(water_mask, filled, np.nan)
        
    return filled.astype(np.float32)


def plot_turbidity_map(
    turbidity_arr: np.ndarray,
    extent: Optional[Tuple[float, float, float, float]] = None,
    title: str = "Water Turbidity (Dogliotti Blended)",
    unit: str = "FNU",
    vmin: float = 0.0,
    vmax: Optional[float] = None,
    cmap: Any = TURBID_CMAP,
    stations: Optional[List[Dict[str, Any]]] = None,
    centerline_coords: Optional[List[Tuple[float, float]]] = None,
    save_path: Optional[str] = None,
    figsize: Tuple[int, int] = (10, 8),
    dpi: int = 300
) -> plt.Figure:
    """
    Renders a high-resolution spatial map of retrieved turbidity or TSS.
    """
    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)

    valid_vals = turbidity_arr[~np.isnan(turbidity_arr)]
    if vmax is None:
        vmax = float(np.percentile(valid_vals, 98)) if len(valid_vals) > 0 else 100.0
        vmax = max(vmax, 10.0)

    # Set background color to light gray for non-water pixels
    ax.set_facecolor("#e8ecef")

    # Render image
    im = ax.imshow(
        turbidity_arr,
        origin="upper",
        extent=extent,
        cmap=cmap,
        vmin=vmin,
        vmax=vmax,
        interpolation="nearest"
    )

    # Plot river centerline if provided
    if centerline_coords is not None and extent is not None:
        xs = [pt[0] for pt in centerline_coords]
        ys = [pt[1] for pt in centerline_coords]
        ax.plot(xs, ys, color="#ffffff", linestyle="--", linewidth=1.5, label="River Centerline", alpha=0.8)

    # Plot virtual stations if provided
    if stations is not None and extent is not None:
        for st in stations:
            lon, lat = st["coords"]
            name = st.get("name", "")
            ax.plot(lon, lat, marker="o", color="#ff0055", markersize=7, markeredgecolor="white", markeredgewidth=1.2)
            ax.text(lon + 0.001, lat + 0.001, name, color="black", fontsize=9, fontweight="bold",
                    bbox=dict(boxstyle="round,pad=0.2", facecolor="white", alpha=0.7, edgecolor="none"))

    # Colorbar
    cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label(f"Turbidity [{unit}]", fontsize=11, fontweight="bold")
    cbar.ax.tick_params(labelsize=10)

    ax.set_title(title, fontsize=13, fontweight="bold", pad=12)
    if extent is not None:
        ax.set_xlabel("Longitude (deg)", fontsize=10)
        ax.set_ylabel("Latitude (deg)", fontsize=10)
    else:
        ax.set_xlabel("Pixel Column", fontsize=10)
        ax.set_ylabel("Pixel Row", fontsize=10)

    ax.grid(True, linestyle=":", alpha=0.4, color="gray")
    plt.tight_layout()

    if save_path:
        os.makedirs(os.path.dirname(os.path.abspath(save_path)), exist_ok=True)
        fig.savefig(save_path, bbox_inches="tight", dpi=dpi)
        print(f"[OK] Saved turbidity map figure: {save_path}")

    return fig


def plot_scene_triplet(
    rgb_composite: Optional[np.ndarray],
    turbidity_arr: np.ndarray,
    tss_arr: np.ndarray,
    scene_title: str = "Satellite Scene Analysis",
    save_path: Optional[str] = None,
    figsize: Tuple[int, int] = (16, 5),
    dpi: int = 300
) -> plt.Figure:
    """
    Renders side-by-side 3-panel comparison: True-Color RGB, Turbidity (FNU), and TSS (mg/L).
    """
    fig, axes = plt.subplots(1, 3, figsize=figsize, dpi=dpi)

    # 1. RGB True Color
    if rgb_composite is not None:
        rgb_clean = np.nan_to_num(rgb_composite, nan=0.0, posinf=1.0, neginf=0.0)
        axes[0].imshow(np.clip(rgb_clean, 0.0, 1.0))
        axes[0].set_title("True Color (RGB Composite)", fontsize=11, fontweight="bold")
    else:
        axes[0].text(0.5, 0.5, "RGB Not Available", ha="center", va="center")
        axes[0].set_title("True Color (RGB)", fontsize=11, fontweight="bold")
    axes[0].axis("off")

    # 2. Turbidity
    valid_turb = turbidity_arr[~np.isnan(turbidity_arr)]
    vmax_t = float(np.percentile(valid_turb, 98)) if len(valid_turb) > 0 else 100.0
    axes[1].set_facecolor("#e8ecef")
    im_t = axes[1].imshow(turbidity_arr, cmap=TURBID_CMAP, vmin=0, vmax=max(vmax_t, 10.0))
    axes[1].set_title("Turbidity (Dogliotti Blended)", fontsize=11, fontweight="bold")
    cbar_t = fig.colorbar(im_t, ax=axes[1], fraction=0.046, pad=0.04)
    cbar_t.set_label("FNU", fontsize=10, fontweight="bold")
    axes[1].axis("off")

    # 3. TSS
    valid_tss = tss_arr[~np.isnan(tss_arr)]
    vmax_s = float(np.percentile(valid_tss, 98)) if len(valid_tss) > 0 else 100.0
    axes[2].set_facecolor("#e8ecef")
    im_s = axes[2].imshow(tss_arr, cmap="YlOrBr", vmin=0, vmax=max(vmax_s, 10.0))
    axes[2].set_title("Total Suspended Solids (TSS)", fontsize=11, fontweight="bold")
    cbar_s = fig.colorbar(im_s, ax=axes[2], fraction=0.046, pad=0.04)
    cbar_s.set_label("mg/L", fontsize=10, fontweight="bold")
    axes[2].axis("off")

    fig.suptitle(scene_title, fontsize=13, fontweight="bold", y=0.98)
    plt.tight_layout()

    if save_path:
        os.makedirs(os.path.dirname(os.path.abspath(save_path)), exist_ok=True)
        fig.savefig(save_path, bbox_inches="tight", dpi=dpi)
        print(f"[OK] Saved comparison triplet figure: {save_path}")

    return fig


def plot_station_timeseries(
    df: pd.DataFrame,
    parameter: str = "turbidity",
    unit: str = "FNU",
    title: str = "Water Quality Multi-Temporal Dynamics",
    save_path: Optional[str] = None,
    figsize: Tuple[int, int] = (12, 6),
    dpi: int = 300
) -> plt.Figure:
    """
    Renders publication-ready time-series chart showing variations across virtual stations.
    """
    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)

    col_mean = f"{parameter}_mean"
    col_std = f"{parameter}_std"
    col_p10 = f"{parameter}_p10"
    col_p90 = f"{parameter}_p90"

    station_names = df["station_name"].unique()
    unique_dates = df["datetime"].dropna().unique() if "datetime" in df.columns else []

    # Single-date / composite comparison mode -> Bar Chart with Error Bars
    if len(unique_dates) <= 1:
        labels = [st.replace("_", " ") for st in df["station_name"]]
        means = df[col_mean].values
        stds = df[col_std].values if col_std in df.columns else np.zeros_like(means)
        
        colors = plt.cm.viridis(np.linspace(0.25, 0.85, max(len(labels), 1)))
        bars = ax.bar(labels, means, yerr=stds, capsize=7, color=colors, edgecolor="#2c3e50", linewidth=1.2, alpha=0.85, width=0.45)
        
        for b, m, s in zip(bars, means, stds):
            y_pos = m + (s if not np.isnan(s) else 0) + (max(means) * 0.03)
            ax.text(b.get_x() + b.get_width()/2.0, y_pos, f"{m:.1f} {unit}", ha="center", va="bottom", fontweight="bold", fontsize=10)

        date_label = df["date_str"].iloc[0] if "date_str" in df.columns and not df.empty else ""
        ax.set_title(f"{title} ({date_label})", fontsize=13, fontweight="bold", pad=14)
        ax.set_xlabel("Virtual Station", fontsize=11, fontweight="bold")
        ax.set_ylabel(f"{parameter.capitalize()} [{unit}]", fontsize=11, fontweight="bold")
        ax.set_ylim(0, max(means) * 1.25 if len(means) > 0 and max(means) > 0 else 100)
        ax.grid(True, linestyle=":", alpha=0.5, axis="y")

    else:
        # Multi-date time-series ribbon mode
        colors = plt.cm.tab10(np.linspace(0, 1, max(len(station_names), 1)))
        for i, st_name in enumerate(station_names):
            sub = df[df["station_name"] == st_name].sort_values("datetime")
            if sub.empty:
                continue

            c = colors[i]
            times = sub["datetime"]
            means = sub[col_mean]

            # Draw line and ribbon if available
            ax.plot(times, means, label=st_name.replace("_", " "), color=c, linewidth=2.2, marker="o", markersize=7)
            if col_p10 in sub.columns and col_p90 in sub.columns:
                ax.fill_between(times, sub[col_p10], sub[col_p90], color=c, alpha=0.18)
            elif col_std in sub.columns:
                ax.fill_between(times, means - sub[col_std], means + sub[col_std], color=c, alpha=0.18)

        ax.set_title(title, fontsize=13, fontweight="bold", pad=12)
        ax.set_xlabel("Date", fontsize=11, fontweight="bold")
        ax.set_ylabel(f"{parameter.capitalize()} [{unit}]", fontsize=11, fontweight="bold")
        ax.grid(True, linestyle="--", alpha=0.5)
        ax.legend(frameon=True, loc="best", fontsize=10)

    plt.tight_layout()
    if save_path:
        os.makedirs(os.path.dirname(os.path.abspath(save_path)), exist_ok=True)
        fig.savefig(save_path, bbox_inches="tight", dpi=dpi)
        print(f"[OK] Saved time-series plot: {save_path}")

    return fig


def plot_longitudinal_gradient(
    df: pd.DataFrame,
    param_name: str = "Turbidity",
    unit: str = "FNU",
    title: str = "Longitudinal River Centerline Gradient",
    save_path: Optional[str] = None,
    figsize: Tuple[int, int] = (10, 5),
    dpi: int = 300
) -> plt.Figure:
    """
    Plots distance along river (Chainage in km) vs. Turbidity/TSS.
    """
    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)

    dist = df["distance_km"]
    vals = df["value"]
    stds = df["std"] if "std" in df.columns else np.zeros_like(vals)

    ax.plot(dist, vals, color="#0066cc", linewidth=2.2, label=f"Mean {param_name}")
    ax.fill_between(dist, vals - stds, vals + stds, color="#0066cc", alpha=0.2, label="+-1 Std Dev")

    ax.set_title(title, fontsize=13, fontweight="bold", pad=12)
    ax.set_xlabel("Distance from Source / Upstream (km)", fontsize=11, fontweight="bold")
    ax.set_ylabel(f"{param_name} [{unit}]", fontsize=11, fontweight="bold")
    ax.grid(True, linestyle=":", alpha=0.6)
    ax.legend(frameon=True, loc="upper right", fontsize=10)

    plt.tight_layout()
    if save_path:
        os.makedirs(os.path.dirname(os.path.abspath(save_path)), exist_ok=True)
        fig.savefig(save_path, bbox_inches="tight", dpi=dpi)
        print(f"[OK] Saved longitudinal gradient plot: {save_path}")

    return fig


def plot_cross_transects(
    df: pd.DataFrame,
    param_name: str = "Turbidity",
    unit: str = "FNU",
    title: str = "CoastSat-Style Cross-Sectional River Transects",
    save_path: Optional[str] = None,
    figsize: Tuple[int, int] = (12, 5),
    dpi: int = 300
) -> plt.Figure:
    """
    Renders multi-transect cross-channel profiles to illustrate lateral sediment plume diffusion.
    """
    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)

    if df.empty or "transect_id" not in df.columns:
        ax.text(0.5, 0.5, "No Transect Data Available", ha="center", va="center")
        return fig

    transect_ids = df["transect_id"].unique()
    colors = plt.cm.plasma(np.linspace(0.1, 0.9, len(transect_ids)))

    for i, t_id in enumerate(transect_ids):
        sub = df[df["transect_id"] == t_id].sort_values("cross_dist_m")
        sub_valid = sub.dropna(subset=["value"])
        if sub_valid.empty:
            continue
        ch_km = sub["chainage_km"].iloc[0] if "chainage_km" in sub.columns else 0.0
        ax.plot(
            sub_valid["cross_dist_m"],
            sub_valid["value"],
            label=f"{t_id} (Chainage: {ch_km:.1f} km)",
            color=colors[i],
            linewidth=2.0,
            marker="o",
            markersize=4
        )

    ax.set_title(title, fontsize=13, fontweight="bold", pad=12)
    ax.set_xlabel("Cross-River Distance from Centerline (m) [Left Bank <-> Right Bank]", fontsize=11, fontweight="bold")
    ax.set_ylabel(f"{param_name} [{unit}]", fontsize=11, fontweight="bold")
    ax.axvline(0, color="gray", linestyle="--", alpha=0.6, label="Centerline")
    ax.grid(True, linestyle=":", alpha=0.6)
    ax.legend(frameon=True, loc="best", fontsize=9)

    plt.tight_layout()
    if save_path:
        os.makedirs(os.path.dirname(os.path.abspath(save_path)), exist_ok=True)
        fig.savefig(save_path, bbox_inches="tight", dpi=dpi)
        print(f"[OK] Saved cross-transect plot: {save_path}")

    return fig


def plot_validation_scatter(
    satellite_vals: np.ndarray,
    in_situ_vals: np.ndarray,
    metrics: Optional[Dict[str, float]] = None,
    param_name: str = "Turbidity",
    unit: str = "FNU",
    title: str = "Satellite vs. In-Situ Bio-Optical Validation",
    save_path: Optional[str] = None,
    figsize: Tuple[int, int] = (7, 7),
    dpi: int = 300
) -> plt.Figure:
    """
    Plots 1:1 validation scatter plot with statistical scorecard box.
    """
    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)

    sat = np.asarray(satellite_vals)
    obs = np.asarray(in_situ_vals)

    valid = ~np.isnan(sat) & ~np.isnan(obs) & (obs > 0)
    sat_v = sat[valid]
    obs_v = obs[valid]

    max_val = max(float(np.max(sat_v)), float(np.max(obs_v))) * 1.15 if len(sat_v) > 0 else 100.0

    # 1:1 Identity Line
    ax.plot([0, max_val], [0, max_val], color="gray", linestyle="--", linewidth=1.5, label="1:1 Line")

    # Scatter points
    ax.scatter(obs_v, sat_v, color="#008080", edgecolors="black", s=50, alpha=0.85, zorder=3, label="Matchups")

    # Trend line
    if len(sat_v) > 2:
        m, b = np.polyfit(obs_v, sat_v, 1)
        ax.plot([0, max_val], [b, m * max_val + b], color="#d9534f", linestyle="-", linewidth=1.8,
                label=f"Fit (y = {m:.2f}x + {b:.2f})")

    # Scorecard annotation
    if metrics:
        def _fmt(val, fmt_str, suffix=""):
            """Safely format a metric value that may be None or NaN."""
            if val is None:
                return "N/A"
            try:
                if np.isnan(val):
                    return "N/A"
            except (TypeError, ValueError):
                return "N/A"
            return f"{val:{fmt_str}}{suffix}"

        r2_str = _fmt(metrics.get('R2'), ".3f")
        rmse_str = _fmt(metrics.get('RMSE'), ".2f", f" {unit}")
        mape_str = _fmt(metrics.get('MAPE_pct'), ".1f", "%")
        bias_str = _fmt(metrics.get('Bias'), ".2f", f" {unit}")

        text_str = (
            f"N = {metrics.get('N', len(sat_v))}\n"
            f"R² = {r2_str}\n"
            f"RMSE = {rmse_str}\n"
            f"MAPE = {mape_str}\n"
            f"Bias = {bias_str}"
        )
        ax.text(0.05, 0.95, text_str, transform=ax.transAxes, fontsize=10, verticalalignment='top',
                bbox=dict(boxstyle='round,pad=0.5', facecolor='#f8f9fa', alpha=0.85, edgecolor='#cccccc'))

    ax.set_xlim(0, max_val)
    ax.set_ylim(0, max_val)
    ax.set_title(title, fontsize=12, fontweight="bold", pad=10)
    ax.set_xlabel(f"In-Situ Measured {param_name} [{unit}]", fontsize=10, fontweight="bold")
    ax.set_ylabel(f"Satellite Retrieved {param_name} [{unit}]", fontsize=10, fontweight="bold")
    ax.grid(True, linestyle=":", alpha=0.5)
    ax.legend(frameon=True, loc="lower right", fontsize=9)

    plt.tight_layout()
    if save_path:
        os.makedirs(os.path.dirname(os.path.abspath(save_path)), exist_ok=True)
        fig.savefig(save_path, bbox_inches="tight", dpi=dpi)
        print(f"[OK] Saved validation scatter plot: {save_path}")

    return fig
