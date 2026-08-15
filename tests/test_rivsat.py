"""
Pytest test suite for Bio-Optic River algorithms, water masks, spatial analytics,
time-series, validation, visualization, and ROI tools.

Covers:
- Core bio-optical algorithm correctness (Nechad, Dogliotti, Red-Edge, SBAF)
- Water masking (SCL, QA_PIXEL, Hybrid)
- Spatial analytics (station extraction, longitudinal profiles, cross-transects)
- Time-series engine and trend analysis
- Validation metrics and model recalibration
- Visualization functions (scatter, map, triplet)
- ROI tools (GeoJSON ingestion, export, bounding box)
- Edge cases (empty arrays, NaN handling, single points)
"""

import os
import json
import pytest
import numpy as np
import pandas as pd
import rasterio
from rasterio.transform import from_origin

from rivsat.core import (
    compute_nechad_model,
    compute_dogliotti_blended,
    compute_rededge_turbidity,
    apply_sbaf_correction,
    compute_ndwi,
    compute_mndwi,
    compute_ndci_chlorophyll,
    compute_cdom,
    compute_salinity,
    compute_secchi_depth,
    create_s2_water_mask,
    create_landsat_water_mask,
    create_hybrid_water_mask
)
from rivsat.analytics import (
    extract_station_data,
    extract_longitudinal_profile,
    extract_cross_transects,
    TimeSeriesEngine,
    calculate_temporal_trends
)
from rivsat.validation import (
    calculate_validation_metrics,
    recalibrate_nechad_coefficient,
    find_spatiotemporal_matchups
)
from rivsat.processing import SceneProcessor
from rivsat.utils import (
    bbox_to_polygon,
    load_geojson_polygon,
    load_geojson_features,
    export_to_geojson,
    validate_spatial_features,
    get_logger
)
from rivsat.visualization import (
    plot_turbidity_map,
    plot_validation_scatter,
    plot_scene_triplet
)


# ===========================================================================
# 1. CORE ALGORITHMS
# ===========================================================================

class TestNechadModel:
    """Tests for the Nechad semi-analytical model."""

    def test_basic_calculation(self):
        """Validates mathematical correctness: T = (A * rho) / (1 - rho/C)."""
        # A=200, C=0.2, rho=0.05 => T = 10 / 0.75 = 13.3333
        res = compute_nechad_model(np.array([0.05]), a_param=200.0, c_param=0.2)
        assert np.isclose(res[0], 13.33333, atol=1e-4)

    def test_asymptote_protection(self):
        """Ensures values near or beyond saturation return NaN."""
        res = compute_nechad_model(np.array([0.25, -0.01]), a_param=200.0, c_param=0.2)
        assert np.isnan(res[0])
        assert np.isnan(res[1])

    def test_zero_reflectance(self):
        """Zero reflectance should yield zero turbidity."""
        res = compute_nechad_model(np.array([0.0]), a_param=228.1, c_param=0.164)
        assert np.isclose(res[0], 0.0)

    def test_vectorized_output(self):
        """Large array processing should not raise errors."""
        rho = np.random.uniform(0.001, 0.15, size=10000).astype(np.float32)
        res = compute_nechad_model(rho, a_param=228.1, c_param=0.164)
        assert res.shape == (10000,)
        assert np.all(res[~np.isnan(res)] >= 0.0)

    def test_nan_input(self):
        """NaN input should propagate cleanly."""
        res = compute_nechad_model(np.array([np.nan, 0.05]), a_param=200.0, c_param=0.2)
        assert np.isnan(res[0])
        assert not np.isnan(res[1])


class TestDogliottiBlending:
    """Tests for the Dogliotti (2015) dual-band blending algorithm."""

    def test_pure_red_regime(self):
        """rho_red <= 0.05 => W=0 (pure Red model)."""
        rho_r = np.array([0.02])
        rho_n = np.array([0.002])
        _, weight = compute_dogliotti_blended(rho_r, rho_n, sensor="S2")
        assert np.isclose(weight[0], 0.0, atol=1e-5)

    def test_pure_nir_regime(self):
        """rho_red >= 0.07 => W=1 (pure NIR model)."""
        rho_r = np.array([0.08])
        rho_n = np.array([0.04])
        _, weight = compute_dogliotti_blended(rho_r, rho_n, sensor="S2")
        assert np.isclose(weight[0], 1.0, atol=1e-5)

    def test_intermediate_blending(self):
        """rho_red = 0.06 => W=0.5 (50% blend)."""
        rho_r = np.array([0.06])
        rho_n = np.array([0.02])
        _, weight = compute_dogliotti_blended(rho_r, rho_n, sensor="S2")
        assert np.isclose(weight[0], 0.5, atol=1e-5)

    def test_landsat_sensor(self):
        """Landsat L8 coefficients should be selected correctly."""
        rho_r = np.array([0.03])
        rho_n = np.array([0.005])
        turb, _ = compute_dogliotti_blended(rho_r, rho_n, sensor="L8")
        assert turb[0] > 0.0

    def test_tss_parameter(self):
        """TSS retrieval should use different coefficients than turbidity."""
        rho_r = np.array([0.04])
        rho_n = np.array([0.01])
        turb, _ = compute_dogliotti_blended(rho_r, rho_n, parameter="turbidity")
        tss, _ = compute_dogliotti_blended(rho_r, rho_n, parameter="tss")
        # TSS and turbidity should differ due to different A coefficients
        assert not np.isclose(turb[0], tss[0])


class TestSBAF:
    """Tests for cross-sensor harmonization."""

    def test_l8_to_s2_red(self):
        """Landsat Red => S2 Red via SBAF."""
        l8_val = np.array([0.05], dtype=np.float32)
        s2_equiv = apply_sbaf_correction(l8_val, band="red", from_sensor="L8", to_sensor="S2")
        assert np.isclose(s2_equiv[0], 0.0499, atol=1e-4)

    def test_identity_for_s2(self):
        """S2 => S2 should return unchanged values."""
        s2_val = np.array([0.05], dtype=np.float32)
        result = apply_sbaf_correction(s2_val, band="red", from_sensor="S2", to_sensor="S2")
        assert np.isclose(result[0], 0.05)

    def test_negative_clamp(self):
        """Negative reflectances should be clamped to 0."""
        result = apply_sbaf_correction(np.array([-0.01]), band="red", from_sensor="L8", to_sensor="S2")
        assert result[0] >= 0.0


class TestWaterIndices:
    """Tests for NDWI and MNDWI computation."""

    def test_ndwi_water(self):
        """Pure water (high green, low NIR) should have positive NDWI."""
        ndwi = compute_ndwi(np.array([0.08]), np.array([0.01]))
        assert ndwi[0] > 0.0

    def test_ndwi_vegetation(self):
        """Vegetation (low green, high NIR) should have negative NDWI."""
        ndwi = compute_ndwi(np.array([0.03]), np.array([0.25]))
        assert ndwi[0] < 0.0

    def test_ndwi_range(self):
        """NDWI values should always be in [-1, 1]."""
        g = np.random.uniform(0, 0.3, 1000).astype(np.float32)
        n = np.random.uniform(0, 0.3, 1000).astype(np.float32)
        ndwi = compute_ndwi(g, n)
        assert np.all(ndwi >= -1.0) and np.all(ndwi <= 1.0)

    def test_mndwi_zero_denominator(self):
        """Zero denominator should return -1.0, not NaN/Inf."""
        mndwi = compute_mndwi(np.array([0.0]), np.array([0.0]))
        assert mndwi[0] == -1.0


# ===========================================================================
# 2. WATER MASKING
# ===========================================================================

class TestWaterMasking:
    """Tests for SCL, QA_PIXEL, and hybrid water masking."""

    def test_s2_scl_strict(self):
        """SCL class 6 = Water, others should be masked."""
        scl = np.array([[6, 3], [4, 6]], dtype=np.int32)
        mask = create_s2_water_mask(scl, strict_water_only=True)
        assert mask[0, 0] == True
        assert mask[0, 1] == False  # cloud shadow
        assert mask[1, 0] == False  # vegetation
        assert mask[1, 1] == True

    def test_s2_scl_relaxed(self):
        """Relaxed mode should keep water + unclassified."""
        scl = np.array([[6, 7], [2, 8]], dtype=np.int32)
        mask = create_s2_water_mask(scl, strict_water_only=False)
        assert mask[0, 0] == True   # water
        assert mask[0, 1] == True   # unclassified
        assert mask[1, 0] == True   # dark pixels
        assert mask[1, 1] == False  # cloud medium

    def test_landsat_qa_pixel(self):
        """Landsat QA_PIXEL bitmask decoding."""
        # Bit 7 = Water, Bit 3 = Cloud
        water_clear = np.array([[0b10000000]], dtype=np.uint16)  # water, no cloud
        mask = create_landsat_water_mask(water_clear, strict_water_only=True)
        assert mask[0, 0] == True

        cloud_water = np.array([[0b10001000]], dtype=np.uint16)  # water + cloud
        mask = create_landsat_water_mask(cloud_water, strict_water_only=True)
        assert mask[0, 0] == False  # cloud should mask out water

    def test_hybrid_mask_water_detection(self):
        """Hybrid mask should detect water with low NIR reflectance."""
        green = np.array([[0.06, 0.02], [0.03, 0.05]])
        red = np.array([[0.04, 0.08], [0.02, 0.04]])
        nir = np.array([[0.01, 0.20], [0.005, 0.02]])
        hybrid = create_hybrid_water_mask(green, red, nir)
        assert hybrid[0, 0] == True   # water
        assert hybrid[0, 1] == False  # dense vegetation (high NIR)


# ===========================================================================
# 3. SPATIAL ANALYTICS
# ===========================================================================

class TestSpatialAnalytics:
    """Tests for station extraction, longitudinal profiles, and cross-transects."""

    @pytest.fixture
    def synthetic_raster(self):
        """Creates a 100x100 synthetic raster with known values."""
        arr = np.ones((100, 100), dtype=np.float32) * 50.0
        # Add a gradient along columns
        for c in range(100):
            arr[:, c] = 30.0 + c * 0.5
        transform = from_origin(90.0, 23.0, 0.001, 0.001)
        return arr, transform

    def test_station_extraction(self, synthetic_raster):
        """Validates vectorized station data extraction."""
        arr, transform = synthetic_raster
        stations = [
            {"name": "St_A", "coords": (90.05, 22.95), "buffer_pixels": 1},
            {"name": "St_B", "coords": (90.08, 22.92), "buffer_pixels": 2},
        ]
        results = extract_station_data(arr, transform, stations)
        assert len(results) == 2
        assert results[0]["station_name"] == "St_A"
        assert results[0]["valid_pixels"] > 0
        assert results[0]["mean"] > 0

    def test_station_extraction_empty(self, synthetic_raster):
        """Empty stations list should return empty results."""
        arr, transform = synthetic_raster
        results = extract_station_data(arr, transform, [])
        assert results == []

    def test_longitudinal_profile(self, synthetic_raster):
        """Tests vectorized arc-length interpolation along centerline."""
        arr, transform = synthetic_raster
        centerline = [(90.01, 22.99), (90.03, 22.95), (90.07, 22.91)]
        df = extract_longitudinal_profile(arr, transform, centerline, num_samples=25)
        assert len(df) == 25
        assert "distance_km" in df.columns
        assert df["distance_km"].iloc[0] == 0.0
        assert df["distance_km"].is_monotonic_increasing

    def test_longitudinal_profile_min_points(self):
        """Centerline with <2 points should raise ValueError."""
        arr = np.ones((10, 10), dtype=np.float32)
        transform = from_origin(90.0, 23.0, 0.01, 0.01)
        with pytest.raises(ValueError, match="at least 2"):
            extract_longitudinal_profile(arr, transform, [(90.05, 22.95)], num_samples=5)

    def test_cross_transects(self, synthetic_raster):
        """Tests perpendicular cross-river transect extraction."""
        arr, transform = synthetic_raster
        centerline = [(90.01, 22.99), (90.05, 22.95), (90.09, 22.91)]
        df = extract_cross_transects(
            arr, transform, centerline,
            num_transects=3, transect_length_m=2000.0, samples_per_transect=10
        )
        assert "transect_id" in df.columns
        assert "cross_dist_m" in df.columns
        assert len(df["transect_id"].unique()) == 3
        assert len(df) == 30  # 3 transects * 10 samples


# ===========================================================================
# 4. VALIDATION
# ===========================================================================

class TestValidation:
    """Tests for validation metrics and model recalibration."""

    def test_perfect_match(self):
        """Perfect agreement should yield R²=1, RMSE=0, MAPE=0, Bias=0."""
        sat = np.array([10.0, 20.0, 30.0, 40.0, 50.0])
        obs = np.array([10.0, 20.0, 30.0, 40.0, 50.0])
        metrics = calculate_validation_metrics(sat, obs)
        assert metrics["N"] == 5
        assert np.isclose(metrics["R2"], 1.0)
        assert np.isclose(metrics["RMSE"], 0.0)
        assert np.isclose(metrics["MAPE_pct"], 0.0)
        assert np.isclose(metrics["Bias"], 0.0)

    def test_systematic_bias(self):
        """Constant offset should appear in Bias metric."""
        sat = np.array([15.0, 25.0, 35.0, 45.0, 55.0])
        obs = np.array([10.0, 20.0, 30.0, 40.0, 50.0])
        metrics = calculate_validation_metrics(sat, obs)
        assert np.isclose(metrics["Bias"], 5.0)
        # Note: R² = 1 - SS_res/SS_tot; with bias, SS_res > 0 so R² < 1
        assert metrics["R2"] > 0.8

    def test_insufficient_data(self):
        """N<2 should return NaN metrics."""
        metrics = calculate_validation_metrics(np.array([10.0]), np.array([10.0]))
        assert metrics["N"] == 1
        assert np.isnan(metrics["R2"])

    def test_nan_handling(self):
        """NaN values should be filtered out before computing metrics."""
        sat = np.array([10.0, np.nan, 30.0, 40.0])
        obs = np.array([10.0, 20.0, np.nan, 40.0])
        metrics = calculate_validation_metrics(sat, obs)
        assert metrics["N"] == 2  # Only 2 valid pairs

    def test_recalibration(self):
        """Recalibration should produce a valid A_T coefficient."""
        rho = np.array([0.025, 0.045, 0.065, 0.088, 0.115, 0.145])
        obs = np.array([28.4, 52.1, 76.5, 105.3, 154.0, 202.8])
        result = recalibrate_nechad_coefficient(reflectances=rho, in_situ_turbidity=obs, band="B4")
        assert result["A_T_calibrated"] > 0
        assert result["R2"] is not None  # Recalibration should produce R² metric

    def test_recalibration_insufficient_data(self):
        """Recalibration with <3 points should raise ValueError."""
        with pytest.raises(ValueError, match="At least 3"):
            recalibrate_nechad_coefficient(
                reflectances=np.array([0.03, 0.06]),
                in_situ_turbidity=np.array([30.0, 60.0]),
                band="B4"
            )


# ===========================================================================
# 5. TIME-SERIES
# ===========================================================================

class TestTimeSeries:
    """Tests for time-series assembly and trend analysis."""

    def test_trend_calculation_stable(self):
        """Stable values should produce z≈0 and p>0.05."""
        df = pd.DataFrame({
            "datetime": pd.date_range("2023-01-01", periods=12, freq="MS"),
            "station_name": ["St_A"] * 12,
            "turbidity_mean": [50.0] * 12,
            "valid_pixels": [9] * 12,
        })
        result = calculate_temporal_trends(df, parameter="turbidity")
        trends = result["trends"]
        assert len(trends) == 1
        assert trends.iloc[0]["trend_direction"] == "Stable"

    def test_trend_calculation_empty(self):
        """Empty DataFrame should return empty trends."""
        df = pd.DataFrame(columns=["datetime", "station_name", "turbidity_mean"])
        result = calculate_temporal_trends(df, parameter="turbidity")
        assert result["trends"].empty

    def test_seasonal_breakdown(self):
        """Seasonal breakdown should categorize months correctly."""
        df = pd.DataFrame({
            "datetime": pd.to_datetime(["2023-01-15", "2023-04-15", "2023-07-15", "2023-10-15"]),
            "station_name": ["St_A"] * 4,
            "turbidity_mean": [30.0, 45.0, 90.0, 50.0],
            "valid_pixels": [9] * 4,
        })
        result = calculate_temporal_trends(df, parameter="turbidity")
        seasonal = result["seasonal"]
        assert len(seasonal) > 0
        seasons = set(seasonal["season"].values)
        assert "Winter/Dry" in seasons
        assert "Monsoon" in seasons


# ===========================================================================
# 6. ROI TOOLS
# ===========================================================================

class TestROITools:
    """Tests for GeoJSON ingestion, export, and bounding box conversion."""

    def test_bbox_to_polygon(self):
        """Bounding box should produce a closed 5-point polygon."""
        poly = bbox_to_polygon(90.0, 23.0, 90.5, 23.5)
        assert len(poly) == 5
        assert poly[0] == [90.0, 23.0]
        assert poly[-1] == [90.0, 23.0]  # Closed ring

    def test_real_geojson_ingestion(self):
        """Tests loading a real GeoJSON file with AOI, stations, and centerline."""
        geojson_file = os.path.abspath("./data/sample_padma_river.geojson")
        if not os.path.exists(geojson_file):
            pytest.skip("Sample GeoJSON file not found")

        poly_coords = load_geojson_polygon(geojson_file)
        assert len(poly_coords) >= 4
        assert poly_coords[0] == poly_coords[-1]

        features = load_geojson_features(geojson_file)
        assert features["aoi_polygon"] is not None
        assert len(features["stations"]) == 3
        assert features["centerline"] is not None
        assert len(features["centerline"]) == 5

    def test_geojson_export_roundtrip(self):
        """Export and re-import should preserve all features."""
        geojson_file = os.path.abspath("./data/sample_padma_river.geojson")
        if not os.path.exists(geojson_file):
            pytest.skip("Sample GeoJSON file not found")

        features = load_geojson_features(geojson_file)
        out_path = os.path.abspath("./data/test_export_roundtrip.geojson")
        try:
            export_to_geojson(
                output_path=out_path,
                aoi_polygon=features["aoi_polygon"],
                stations=features["stations"],
                centerline=features["centerline"],
                site_name="Test_Site"
            )
            assert os.path.exists(out_path)
            reloaded = load_geojson_features(out_path)
            assert len(reloaded["stations"]) == 3
        finally:
            if os.path.exists(out_path):
                os.remove(out_path)

    def test_validate_spatial_features(self):
        """validate_spatial_features should not raise on valid input."""
        features = {
            "aoi_polygon": [[90.0, 23.0], [90.5, 23.0], [90.5, 23.5], [90.0, 23.5], [90.0, 23.0]],
            "stations": [{"name": "S1", "coords": (90.25, 23.25), "buffer_pixels": 2}],
            "centerline": [(90.1, 23.1), (90.4, 23.4)],
        }
        # Should not raise
        validate_spatial_features(features)


# ===========================================================================
# 7. VISUALIZATION
# ===========================================================================

class TestVisualization:
    """Tests for plot functions — validates they produce figures without errors."""

    def test_validation_scatter_basic(self):
        """Scatter plot should render without errors."""
        import matplotlib
        matplotlib.use("Agg")  # Non-interactive backend
        sat = np.array([10.0, 20.0, 30.0, 40.0, 50.0])
        obs = np.array([12.0, 18.0, 32.0, 38.0, 52.0])
        metrics = calculate_validation_metrics(sat, obs)
        fig = plot_validation_scatter(sat, obs, metrics=metrics)
        assert fig is not None
        import matplotlib.pyplot as plt
        plt.close(fig)

    def test_validation_scatter_empty(self):
        """Scatter plot with empty data should not crash."""
        import matplotlib
        matplotlib.use("Agg")
        sat = np.array([])
        obs = np.array([])
        fig = plot_validation_scatter(sat, obs)
        assert fig is not None
        import matplotlib.pyplot as plt
        plt.close(fig)

    def test_validation_scatter_none_metrics(self):
        """Scatter plot with None metric values should not crash."""
        import matplotlib
        matplotlib.use("Agg")
        sat = np.array([10.0, 20.0])
        obs = np.array([10.0, 20.0])
        metrics = {"N": 2, "R2": None, "RMSE": None, "MAPE_pct": None, "Bias": None}
        fig = plot_validation_scatter(sat, obs, metrics=metrics)
        assert fig is not None
        import matplotlib.pyplot as plt
        plt.close(fig)

    def test_turbidity_map(self):
        """Turbidity map should render without errors."""
        import matplotlib
        matplotlib.use("Agg")
        arr = np.random.uniform(10, 100, (50, 50)).astype(np.float32)
        arr[0:5, 0:5] = np.nan  # Non-water pixels
        fig = plot_turbidity_map(arr, title="Test Map")
        assert fig is not None
        import matplotlib.pyplot as plt
        plt.close(fig)


# ===========================================================================
# 8. LOGGING
# ===========================================================================

class TestLogger:
    """Tests for the centralized logging module."""

    def test_logger_creation(self):
        """Logger should be created without errors."""
        logger = get_logger("test_module")
        assert logger is not None
        assert logger.name == "test_module"

    def test_logger_output(self):
        """Logger should be able to log without errors."""
        logger = get_logger("test_output_module")
        # Should not raise any exception
        logger.info("Test message")
        logger.warning("Test warning")
        logger.debug("Test debug")


# ===========================================================================
# 9. KD-TREE MATCHUP ENGINE
# ===========================================================================

class TestMatchupEngine:
    """Tests for the spatio-temporal matchup engine."""

    def test_empty_input(self):
        """Empty DataFrame should return empty results."""
        empty_df = pd.DataFrame(columns=["datetime", "lon", "lat", "value"])
        res = find_spatiotemporal_matchups(empty_df, [])
        assert res.empty


# ===========================================================================
# 10. MULTI-PARAMETER WATER QUALITY ALGORITHMS
# ===========================================================================

class TestWaterQualityAlgorithms:
    """Tests for Chlorophyll-a, CDOM, Salinity, and Secchi Depth algorithms."""

    def test_compute_ndci_chlorophyll(self):
        """NDCI Chlorophyll-a should increase with higher Red-Edge reflectance."""
        r_red = np.array([0.02, 0.02], dtype=np.float32)
        r_re = np.array([0.03, 0.05], dtype=np.float32)
        chl = compute_ndci_chlorophyll(r_red, r_re)
        assert chl[1] > chl[0]
        assert not np.any(np.isnan(chl))

    def test_compute_cdom(self):
        """CDOM should decrease as Green/Red ratio increases."""
        g = np.array([0.04, 0.06], dtype=np.float32)
        r = np.array([0.02, 0.02], dtype=np.float32)
        cdom = compute_cdom(g, r)
        assert cdom[1] < cdom[0]
        assert not np.any(np.isnan(cdom))

    def test_compute_salinity(self):
        """Salinity should decrease with higher CDOM absorption."""
        cdom = np.array([0.5, 2.0], dtype=np.float32)
        sal = compute_salinity(cdom)
        assert sal[0] > sal[1]
        assert np.all(sal <= 35.0)

    def test_compute_secchi_depth(self):
        """Secchi depth should decrease with higher turbidity."""
        turb = np.array([10.0, 100.0], dtype=np.float32)
        sdd = compute_secchi_depth(turb)
        assert sdd[0] > sdd[1]


# ===========================================================================
# 11. SCENE PROCESSOR PIPELINE
# ===========================================================================

class TestSceneProcessor:
    """Tests for SceneProcessor end-to-end scene processing."""

    def test_scene_processor_execution(self, tmp_path):
        """SceneProcessor should execute without NameErrors or missing imports."""
        from rivsat.processing.processor import SceneProcessor

        scene_dir = tmp_path / "S2_2023_Test_Median"
        scene_dir.mkdir()

        # Create dummy raster files
        profile = {
            "driver": "GTiff", "dtype": "float32", "nodata": None,
            "width": 10, "height": 10, "count": 1, "crs": "EPSG:4326",
            "transform": from_origin(90.0, 23.0, 0.001, 0.001)
        }
        dummy = np.full((10, 10), 0.05, dtype=np.float32)

        for b in ["B2.tif", "B3.tif", "B4.tif", "B5.tif", "B8A.tif", "B11.tif", "SCL.tif"]:
            with rasterio.open(scene_dir / b, "w", **profile) as dst:
                dst.write(dummy if "SCL" not in b else np.full((10, 10), 6, dtype=np.uint8), 1)

        meta = {"sensor": "S2", "date": "2023_Test_Median"}
        with open(scene_dir / "metadata.json", "w") as f:
            json.dump(meta, f)

        proc = SceneProcessor(str(scene_dir))
        res = proc.process()
        assert "turbidity" in res
        assert "chlorophyll" in res
        assert "cdom" in res
        assert "salinity" in res
        assert "secchi_depth" in res


