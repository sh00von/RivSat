"""
Interactive Region of Interest (ROI), GeoJSON Ingestion, and Virtual Station Definition Tools.

Provides:
- Real GeoJSON / Shapefile / GeoPackage parser for user ROIs, stations, and centerlines
- Automatic CRS re-projection to WGS84 (EPSG:4326)
- GeoJSON / bounding box serializers and exporters
- Folium interactive map builder for visualizing and choosing study sites
"""

import os
import json
import glob
import numpy as np
from typing import List, Tuple, Dict, Any, Optional, Union
from shapely.geometry import shape, mapping, Polygon, MultiPolygon, Point, LineString

try:
    import geopandas as gpd
    GEOPANDAS_AVAILABLE = True
except ImportError:
    GEOPANDAS_AVAILABLE = False

try:
    import folium
    from folium.plugins import Draw
    FOLIUM_AVAILABLE = True
except ImportError:
    FOLIUM_AVAILABLE = False


def bbox_to_polygon(min_lon: float, min_lat: float, max_lon: float, max_lat: float) -> List[List[float]]:
    """
    Converts a bounding box [min_lon, min_lat, max_lon, max_lat] into a closed polygon
    format compatible with Google Earth Engine ee.Geometry.Polygon.
    """
    return [
        [min_lon, min_lat],
        [max_lon, min_lat],
        [max_lon, max_lat],
        [min_lon, max_lat],
        [min_lon, min_lat]
    ]


def load_geojson_polygon(geojson_source: Union[str, dict]) -> List[List[float]]:
    """
    Loads and extracts closed polygon coordinates [[lon, lat], ...] from a real GeoJSON file,
    GeoJSON dictionary, Shapefile, or GeoDataFrame.
    
    Automatically handles:
    - GeoJSON Files (.geojson, .json, .shp, .gpkg)
    - FeatureCollections, Features, Polygon, and MultiPolygon geometries
    - Automatic reprojection to WGS84 (EPSG:4326) if coordinates are in UTM / projected CRS
    - Ensures closed polygon ring structure for Earth Engine compatibility

    Parameters
    ----------
    geojson_source : str or dict
        Path to GeoJSON file, GeoJSON JSON string, or GeoJSON dict structure.

    Returns
    -------
    list of list of float
        Coordinates array in format [[lon1, lat1], [lon2, lat2], ..., [lon1, lat1]]
    """
    if isinstance(geojson_source, str) and os.path.exists(geojson_source):
        # File path provided
        if GEOPANDAS_AVAILABLE:
            try:
                gdf = gpd.read_file(geojson_source)
                if gdf.crs is not None and gdf.crs.to_epsg() != 4326:
                    gdf = gdf.to_crs(epsg=4326)
                
                # Filter specifically for polygon geometries if present
                poly_gdf = gdf[gdf.geometry.geom_type.isin(['Polygon', 'MultiPolygon'])]
                if not poly_gdf.empty:
                    if hasattr(poly_gdf.geometry, 'union_all'):
                        geom = poly_gdf.geometry.union_all()
                    else:
                        geom = poly_gdf.geometry.unary_union
                    
                    if geom.geom_type == 'Polygon':
                        coords = list(geom.exterior.coords)
                        return [[float(x), float(y)] for x, y in coords]
                    elif geom.geom_type == 'MultiPolygon':
                        largest = max(geom.geoms, key=lambda p: p.area)
                        coords = list(largest.exterior.coords)
                        return [[float(x), float(y)] for x, y in coords]
                
                # Otherwise compute total bounds
                minx, miny, maxx, maxy = gdf.total_bounds
                return bbox_to_polygon(minx, miny, maxx, maxy)
            except Exception:
                pass

        # Fallback to direct json parsing
        with open(geojson_source, "r", encoding="utf-8") as f:
            data = json.load(f)
    elif isinstance(geojson_source, str):
        # Maybe a JSON string
        try:
            data = json.loads(geojson_source)
        except Exception as err:
            raise ValueError(f"Invalid GeoJSON string or file path: {geojson_source}")
    elif isinstance(geojson_source, dict):
        data = geojson_source
    else:
        raise TypeError(f"Unsupported geojson_source type: {type(geojson_source)}")

    # Parse dictionary structure (FeatureCollection, Feature, or Geometry)
    if "type" in data:
        if data["type"] == "FeatureCollection":
            features = data.get("features", [])
            if not features:
                raise ValueError("GeoJSON FeatureCollection contains no features.")
            
            # Find first polygon or union
            for feat in features:
                geom = feat.get("geometry", {})
                if geom.get("type") in ["Polygon", "MultiPolygon"]:
                    s_geom = shape(geom)
                    if s_geom.geom_type == "Polygon":
                        return [[float(x), float(y)] for x, y in s_geom.exterior.coords]
                    elif s_geom.geom_type == "MultiPolygon":
                        largest = max(s_geom.geoms, key=lambda p: p.area)
                        return [[float(x), float(y)] for x, y in largest.exterior.coords]
            
            # If no polygon, take bbox of all features
            all_coords = []
            for feat in features:
                geom = feat.get("geometry", {})
                if "coordinates" in geom:
                    s = shape(geom)
                    minx, miny, maxx, maxy = s.bounds
                    all_coords.append((minx, miny, maxx, maxy))
            if all_coords:
                minx = min(c[0] for c in all_coords)
                miny = min(c[1] for c in all_coords)
                maxx = max(c[2] for c in all_coords)
                maxy = max(c[3] for c in all_coords)
                return bbox_to_polygon(minx, miny, maxx, maxy)

        elif data["type"] == "Feature":
            geom = shape(data.get("geometry", {}))
            if geom.geom_type == "Polygon":
                return [[float(x), float(y)] for x, y in geom.exterior.coords]
            elif geom.geom_type == "MultiPolygon":
                largest = max(geom.geoms, key=lambda p: p.area)
                return [[float(x), float(y)] for x, y in largest.exterior.coords]
            else:
                minx, miny, maxx, maxy = geom.bounds
                return bbox_to_polygon(minx, miny, maxx, maxy)

        elif data["type"] in ["Polygon", "MultiPolygon"]:
            geom = shape(data)
            if geom.geom_type == "Polygon":
                return [[float(x), float(y)] for x, y in geom.exterior.coords]
            elif geom.geom_type == "MultiPolygon":
                largest = max(geom.geoms, key=lambda p: p.area)
                return [[float(x), float(y)] for x, y in largest.exterior.coords]

    raise ValueError("Could not extract valid Polygon coordinates from provided GeoJSON.")


def load_geojson_features(
    geojson_path: str,
    stations_path: Optional[str] = None,
    centerline_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Parses a study site's spatial layers from either a combined GeoJSON or separate files
    (e.g., 'user_roi.geojson', 'stations.geojson', 'centerline.geojson').

    Parameters
    ----------
    geojson_path : str
        Path to main .geojson file (AOI Polygon).
    stations_path : str, optional
        Path to separate stations .geojson file.
    centerline_path : str, optional
        Path to separate centerline .geojson file.

    Returns
    -------
    dict
        Dictionary with keys 'aoi_polygon', 'stations', 'centerline'.
    """
    aoi_polygon = None
    stations = []
    centerline = None

    if os.path.exists(geojson_path):
        with open(geojson_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        features = data.get("features", []) if data.get("type") == "FeatureCollection" else [data]

        for feat in features:
            geom = feat.get("geometry", {})
            props = feat.get("properties", {})
            g_type = geom.get("type")

            if g_type in ["Polygon", "MultiPolygon"] and aoi_polygon is None:
                s_geom = shape(geom)
                if s_geom.geom_type == "Polygon":
                    aoi_polygon = [[float(x), float(y)] for x, y in s_geom.exterior.coords]
                elif s_geom.geom_type == "MultiPolygon":
                    largest = max(s_geom.geoms, key=lambda p: p.area)
                    aoi_polygon = [[float(x), float(y)] for x, y in largest.exterior.coords]

            elif g_type == "Point":
                coords = geom.get("coordinates", [])
                if len(coords) >= 2:
                    name = props.get("name") or props.get("station_name") or props.get("id") or f"Station_{len(stations)+1}"
                    buffer_pix = int(props.get("buffer_pixels", 2))
                    stations.append({
                        "name": str(name),
                        "coords": (float(coords[0]), float(coords[1])),
                        "buffer_pixels": buffer_pix
                    })

            elif g_type == "LineString" and centerline is None:
                coords = geom.get("coordinates", [])
                centerline = [(float(pt[0]), float(pt[1])) for pt in coords]

    # Check separate stations file if not yet loaded
    st_path = stations_path or os.path.join(os.path.dirname(geojson_path), "stations.geojson")
    if not stations and os.path.exists(st_path):
        try:
            with open(st_path, "r", encoding="utf-8") as f:
                s_data = json.load(f)
            s_feats = s_data.get("features", []) if s_data.get("type") == "FeatureCollection" else [s_data]
            for feat in s_feats:
                geom = feat.get("geometry", {})
                props = feat.get("properties", {})
                if geom.get("type") == "Point":
                    coords = geom.get("coordinates", [])
                    name = props.get("name") or props.get("station_name") or f"Station_{len(stations)+1}"
                    stations.append({
                        "name": str(name),
                        "coords": (float(coords[0]), float(coords[1])),
                        "buffer_pixels": int(props.get("buffer_pixels", 2))
                    })
        except Exception:
            pass

    # Check separate centerline file if not yet loaded
    c_path = centerline_path or os.path.join(os.path.dirname(geojson_path), "centerline.geojson")
    if not centerline and os.path.exists(c_path):
        try:
            with open(c_path, "r", encoding="utf-8") as f:
                c_data = json.load(f)
            c_feats = c_data.get("features", []) if c_data.get("type") == "FeatureCollection" else [c_data]
            for feat in c_feats:
                geom = feat.get("geometry", {})
                if geom.get("type") == "LineString":
                    coords = geom.get("coordinates", [])
                    centerline = [(float(pt[0]), float(pt[1])) for pt in coords]
                    break
        except Exception:
            pass

    # Check Downloads folder for browser-exported GeoJSON files from Folium
    downloads_dir = os.path.expanduser("~/Downloads")
    if os.path.exists(downloads_dir):
        # 1. Search for exported centerline files in Downloads
        if not centerline:
            import glob
            dl_centerlines = sorted(glob.glob(os.path.join(downloads_dir, "*centerline*.geojson")), key=os.path.getmtime, reverse=True)
            if dl_centerlines:
                try:
                    with open(dl_centerlines[0], "r", encoding="utf-8") as f:
                        c_data = json.load(f)
                    c_feats = c_data.get("features", []) if c_data.get("type") == "FeatureCollection" else [c_data]
                    for feat in c_feats:
                        geom = feat.get("geometry", {})
                        if geom.get("type") == "LineString":
                            centerline = [(float(pt[0]), float(pt[1])) for pt in geom.get("coordinates", [])]
                            print(f"[i] Automatically imported river centerline from Downloads: {dl_centerlines[0]}")
                            # Cache into ./data/centerline.geojson
                            os.makedirs(os.path.dirname(geojson_path), exist_ok=True)
                            with open(os.path.join(os.path.dirname(geojson_path), "centerline.geojson"), "w") as cf:
                                json.dump(c_data, cf, indent=2)
                            break
                except Exception:
                    pass

        # 2. Search for exported stations files in Downloads
        if not stations:
            import glob
            dl_stations = sorted(glob.glob(os.path.join(downloads_dir, "*station*.geojson")), key=os.path.getmtime, reverse=True)
            if dl_stations:
                try:
                    with open(dl_stations[0], "r", encoding="utf-8") as f:
                        s_data = json.load(f)
                    s_feats = s_data.get("features", []) if s_data.get("type") == "FeatureCollection" else [s_data]
                    for feat in s_feats:
                        geom = feat.get("geometry", {})
                        props = feat.get("properties", {})
                        if geom.get("type") == "Point":
                            coords = geom.get("coordinates", [])
                            name = props.get("name") or props.get("station_name") or f"Station_{len(stations)+1}"
                            stations.append({
                                "name": str(name),
                                "coords": (float(coords[0]), float(coords[1])),
                                "buffer_pixels": int(props.get("buffer_pixels", 2))
                            })
                    if stations:
                        print(f"[i] Automatically imported {len(stations)} virtual station(s) from Downloads: {dl_stations[0]}")
                        os.makedirs(os.path.dirname(geojson_path), exist_ok=True)
                        with open(os.path.join(os.path.dirname(geojson_path), "stations.geojson"), "w") as sf:
                            json.dump(s_data, sf, indent=2)
                except Exception:
                    pass

    return {
        "aoi_polygon": aoi_polygon,
        "stations": stations,
        "centerline": centerline
    }


def validate_spatial_features(features: Dict[str, Any]) -> bool:
    """
    Validates whether ingested GeoJSON features contain AOI, stations, and centerline.
    """
    aoi = features.get("aoi_polygon")
    stations = features.get("stations", [])
    centerline = features.get("centerline")

    valid_aoi = bool(aoi and len(aoi) >= 3)
    valid_stations = bool(stations and len(stations) >= 1)
    valid_centerline = bool(centerline and len(centerline) >= 2)

    if not valid_aoi:
        print("[!] Error: No valid AOI Polygon found in GeoJSON.")
    if not valid_stations:
        print("[!] Notice: No Virtual Station Point features found in GeoJSON. (Step 6 Station Time-Series requires at least 1 Point feature).")
    if not valid_centerline:
        print("[!] Notice: No River Centerline LineString feature found in GeoJSON. (Step 7 Centerline Transect requires at least 1 LineString feature).")

    return valid_aoi


def export_to_geojson(
    output_path: str,
    aoi_polygon: Optional[List[List[float]]] = None,
    stations: Optional[List[Dict[str, Any]]] = None,
    centerline: Optional[List[Tuple[float, float]]] = None,
    site_name: str = "Study_Site"
) -> str:
    """
    Exports study site configurations into a standard GeoJSON FeatureCollection.
    """
    features = []

    # 1. AOI Polygon Feature
    if aoi_polygon:
        poly_geom = Polygon(aoi_polygon)
        features.append({
            "type": "Feature",
            "geometry": mapping(poly_geom),
            "properties": {
                "layer": "AOI",
                "site_name": site_name
            }
        })

    # 2. Virtual Station Points
    if stations:
        for st in stations:
            lon, lat = st["coords"]
            pt_geom = Point(lon, lat)
            features.append({
                "type": "Feature",
                "geometry": mapping(pt_geom),
                "properties": {
                    "layer": "Virtual_Station",
                    "name": st.get("name", "Station"),
                    "buffer_pixels": st.get("buffer_pixels", 2)
                }
            })

    # 3. River Centerline
    if centerline:
        line_geom = LineString(centerline)
        features.append({
            "type": "Feature",
            "geometry": mapping(line_geom),
            "properties": {
                "layer": "River_Centerline",
                "site_name": site_name
            }
        })

    fc = {
        "type": "FeatureCollection",
        "name": site_name,
        "features": features
    }

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(fc, f, indent=2)

    print(f"[OK] Exported GeoJSON to {output_path}")
    return output_path


def _build_base_satellite_map(center_coords: Tuple[float, float], zoom_start: int) -> Any:
    """
    Builds a multi-layer base map with Google Satellite, Esri World Imagery, and OpenStreetMap.
    """
    m = folium.Map(
        location=center_coords,
        zoom_start=zoom_start,
        tiles=None
    )

    # 1. Google Maps Satellite (Fast, high-res global imagery)
    folium.TileLayer(
        tiles="https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}",
        attr="Google Satellite",
        name="Google Satellite",
        overlay=False,
        control=True
    ).add_to(m)

    # 2. Esri World Imagery
    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Esri World Imagery",
        name="Esri World Imagery",
        overlay=False,
        control=True
    ).add_to(m)

    # 3. OpenStreetMap
    folium.TileLayer(
        "OpenStreetMap",
        name="OpenStreetMap",
        overlay=False,
        control=True
    ).add_to(m)

    return m


def create_centerline_draw_map(
    aoi_polygon: List[List[float]],
    center_coords: Optional[Tuple[float, float]] = None,
    zoom_start: int = 13,
    save_html_path: Optional[str] = None
) -> Any:
    """
    Creates an interactive satellite map specifically designed for tracing the River Centerline.
    Only the Polyline drawing tool is enabled.
    """
    if not FOLIUM_AVAILABLE:
        print("Folium is not installed.")
        return None

    if center_coords is None and aoi_polygon:
        lons = [float(pt[0]) for pt in aoi_polygon]
        lats = [float(pt[1]) for pt in aoi_polygon]
        center_coords = (float(sum(lats) / len(lats)), float(sum(lons) / len(lons)))
    elif center_coords is None:
        center_coords = (23.8103, 90.4125)

    m = folium.Map(location=center_coords, zoom_start=zoom_start, tiles="OpenStreetMap")

    # 1. Google Maps Satellite
    folium.TileLayer(
        tiles="https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}",
        attr="Google Satellite",
        name="Google Satellite",
        overlay=False,
        control=True
    ).add_to(m)

    # 2. Esri World Imagery
    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Esri World Imagery",
        name="Esri World Imagery",
        overlay=False,
        control=True
    ).add_to(m)

    # 3. OpenStreetMap
    folium.TileLayer(
        "OpenStreetMap",
        name="OpenStreetMap",
        overlay=False,
        control=True
    ).add_to(m)

    # Render AOI Polygon Boundary
    folium_coords = [[float(pt[1]), float(pt[0])] for pt in aoi_polygon]
    folium.Polygon(
        locations=folium_coords,
        color="#00f3ff",
        weight=3,
        fill=True,
        fill_opacity=0.15,
        popup="Target Area of Interest (AOI)"
    ).add_to(m)

    # Enable ONLY Polyline tool for centerline tracing
    draw = Draw(
        export=True,
        filename="centerline.geojson",
        position="topleft",
        draw_options={
            "polyline": {
                "shapeOptions": {
                    "color": "#ffff00",
                    "weight": 4,
                    "opacity": 0.9
                }
            },
            "polygon": False,
            "rectangle": False,
            "circle": False,
            "marker": False,
            "circlemarker": False
        }
    )
    draw.add_to(m)
    folium.LayerControl().add_to(m)

    if save_html_path:
        m.save(save_html_path)

    return m


def create_stations_draw_map(
    aoi_polygon: List[List[float]],
    centerline: Optional[List[Tuple[float, float]]] = None,
    center_coords: Optional[Tuple[float, float]] = None,
    zoom_start: int = 13,
    save_html_path: Optional[str] = None
) -> Any:
    """
    Creates an interactive satellite map specifically designed for placing Virtual Monitoring Stations.
    Only the Marker / Point tool is enabled.
    """
    if not FOLIUM_AVAILABLE:
        print("Folium is not installed.")
        return None

    if center_coords is None and aoi_polygon:
        lons = [float(pt[0]) for pt in aoi_polygon]
        lats = [float(pt[1]) for pt in aoi_polygon]
        center_coords = (float(sum(lats) / len(lats)), float(sum(lons) / len(lons)))
    elif center_coords is None:
        center_coords = (23.8103, 90.4125)

    m = folium.Map(location=center_coords, zoom_start=zoom_start, tiles="OpenStreetMap")

    # 1. Google Maps Satellite
    folium.TileLayer(
        tiles="https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}",
        attr="Google Satellite",
        name="Google Satellite",
        overlay=False,
        control=True
    ).add_to(m)

    # 2. Esri World Imagery
    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Esri World Imagery",
        name="Esri World Imagery",
        overlay=False,
        control=True
    ).add_to(m)

    # 3. OpenStreetMap
    folium.TileLayer(
        "OpenStreetMap",
        name="OpenStreetMap",
        overlay=False,
        control=True
    ).add_to(m)

    # Render AOI Polygon Boundary
    folium_coords = [[float(pt[1]), float(pt[0])] for pt in aoi_polygon]
    folium.Polygon(
        locations=folium_coords,
        color="#00f3ff",
        weight=3,
        fill=True,
        fill_opacity=0.15,
        popup="Target Area of Interest (AOI)"
    ).add_to(m)

    # Render River Centerline if available
    if centerline:
        line_coords = [[float(pt[1]), float(pt[0])] for pt in centerline]
        folium.PolyLine(
            locations=line_coords,
            color="#ffff00",
            weight=3,
            dash_array="5, 5",
            popup="River Centerline"
        ).add_to(m)

    # Enable ONLY Marker tool for placing stations
    draw = Draw(
        export=True,
        filename="stations.geojson",
        position="topleft",
        draw_options={
            "polyline": False,
            "polygon": False,
            "rectangle": False,
            "circle": False,
            "marker": True,
            "circlemarker": False
        }
    )
    draw.add_to(m)
    folium.LayerControl().add_to(m)

    if save_html_path:
        m.save(save_html_path)

    return m


def create_interactive_roi_map(
    center_coords: Tuple[float, float] = (23.8103, 90.4125),
    zoom_start: int = 12,
    aoi_polygon: Optional[List[List[float]]] = None,
    stations: Optional[List[Dict[str, Any]]] = None,
    centerline: Optional[List[Tuple[float, float]]] = None,
    save_html_path: Optional[str] = None
) -> Any:
    """
    Builds a Folium interactive satellite map with drawing tools for defining AOIs, stations, and centerlines.
    """
    if not FOLIUM_AVAILABLE:
        print("Folium is not installed. Run 'pip install folium' for interactive maps.")
        return None

    m = folium.Map(location=center_coords, zoom_start=zoom_start, tiles="OpenStreetMap")

    folium.TileLayer(
        tiles="https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}",
        attr="Google Satellite",
        name="Google Satellite",
        overlay=False,
        control=True
    ).add_to(m)

    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Esri World Imagery",
        name="Esri World Imagery",
        overlay=False,
        control=True
    ).add_to(m)

    folium.TileLayer(
        "OpenStreetMap",
        name="OpenStreetMap",
        overlay=False,
        control=True
    ).add_to(m)

    # Add draw plugin
    draw = Draw(
        export=True,
        filename="user_roi.geojson",
        position="topleft",
        draw_options={
            "polyline": True,
            "polygon": True,
            "rectangle": True,
            "circle": False,
            "marker": True,
            "circlemarker": False
        }
    )
    draw.add_to(m)

    # If AOI polygon provided, render on map
    if aoi_polygon:
        folium_coords = [[pt[1], pt[0]] for pt in aoi_polygon]
        folium.Polygon(
            locations=folium_coords,
            color="#00ffff",
            weight=3,
            fill=True,
            fill_opacity=0.15,
            popup="Target Area of Interest (AOI)"
        ).add_to(m)

    # If centerline provided, render on map
    if centerline:
        line_coords = [[pt[1], pt[0]] for pt in centerline]
        folium.PolyLine(
            locations=line_coords,
            color="#ffff00",
            weight=3,
            dash_array="5, 5",
            popup="River Centerline Transect"
        ).add_to(m)

    # If stations provided, render pins
    if stations:
        for st in stations:
            lon, lat = st["coords"]
            name = st.get("name", "Station")
            folium.Marker(
                location=[lat, lon],
                popup=f"<b>{name}</b><br>Lon: {lon:.4f}, Lat: {lat:.4f}",
                tooltip=name,
                icon=folium.Icon(color="red", icon="tint", prefix="fa")
            ).add_to(m)

    folium.LayerControl().add_to(m)

    if save_html_path:
        m.save(save_html_path)
        print(f"[OK] Saved interactive ROI map to {save_html_path}")

    return m


def save_study_site_config(
    file_path: str,
    site_name: str,
    aoi_polygon: List[List[float]],
    stations: List[Dict[str, Any]],
    centerline: Optional[List[Tuple[float, float]]] = None
) -> None:
    """Saves a study site's spatial configuration into a reusable JSON file."""
    config = {
        "site_name": site_name,
        "aoi_polygon": aoi_polygon,
        "stations": stations,
        "centerline": centerline
    }
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
    print(f"[OK] Saved site configuration to {file_path}")


def load_study_site_config(file_path: str) -> Dict[str, Any]:
    """Loads a study site's spatial configuration from a JSON file."""
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)
