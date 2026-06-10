"""
map_view.py - Folium map rendering for Trace Studio.

Builds a raw-GNSS map with a color-coded path and a cursor marker.
No map matching, no road correction.
"""

from __future__ import annotations

import math

import folium
import numpy as np
import pandas as pd
from branca.colormap import LinearColormap


MAP_COLOR_CHANNELS = [
    "speed_obd_kmh",
    "rpm",
    "throttle_pct",
    "acc_lon_G",
    "acc_lon_G_filt",
    "acc_lat_G",
    "acc_lat_G_filt",
    "jerk_lon_mps3",
    "jerk_lat_mps3",
    "slope_deg",
    "curvature_1pm",
    "abs_curvature_1pm",
    "curve_radius_m",
    "estimated_gear",
    "distance_m",
]

CHANNEL_LABELS = {
    "speed_obd_kmh": "Velocità OBD [km/h]",
    "rpm": "RPM [rpm]",
    "throttle_pct": "Throttle [%]",
    "acc_lon_G": "Accelerazione longitudinale [G]",
    "acc_lon_G_filt": "Acc. longitudinale filtrata [G]",
    "acc_lat_G": "Accelerazione laterale [G]",
    "acc_lat_G_filt": "Acc. laterale filtrata [G]",
    "jerk_lon_mps3": "Strappo longitudinale [m/s³]",
    "jerk_lat_mps3": "Strappo laterale [m/s³]",
    "slope_deg": "Pendenza [°]",
    "curvature_1pm": "Curvatura [1/m]",
    "abs_curvature_1pm": "|Curvatura| [1/m]",
    "curve_radius_m": "Raggio di curvatura [m]",
    "estimated_gear": "Marcia stimata [-]",
    "distance_m": "Distanza progressiva [m]",
}

GEAR_COLORS = {
    0: "#808080",
    1: "#1f77b4",
    2: "#ff7f0e",
    3: "#2ca02c",
    4: "#d62728",
    5: "#9467bd",
}

DEFAULT_GEAR_COLOR = "#aaaaaa"
NAN_COLOR = "#777777"


def get_valid_path_points(df: pd.DataFrame) -> pd.DataFrame:
    """
    Return only rows with valid GNSS coordinates.

    Valid means:
    - lat/lon columns exist
    - lat and lon are finite
    - lat/lon are not both zero
    """
    if df.empty or "lat" not in df.columns or "lon" not in df.columns:
        return df.iloc[0:0].copy()

    lat = pd.to_numeric(df["lat"], errors="coerce")
    lon = pd.to_numeric(df["lon"], errors="coerce")

    mask = (
        np.isfinite(lat)
        & np.isfinite(lon)
        & ~((lat == 0.0) & (lon == 0.0))
    )

    if "time_s" in df.columns:
        time_s = pd.to_numeric(df["time_s"], errors="coerce")
        mask = mask & np.isfinite(time_s)

    out = df.loc[mask].copy()
    out["lat"] = lat.loc[mask].astype(float)
    out["lon"] = lon.loc[mask].astype(float)

    if "time_s" in out.columns:
        out["time_s"] = pd.to_numeric(out["time_s"], errors="coerce")

    return out


def get_available_map_color_channels(df: pd.DataFrame) -> list[dict]:
    """
    Return map color channels that exist and contain at least one finite value.
    """
    available: list[dict] = []

    for ch in MAP_COLOR_CHANNELS:
        if ch not in df.columns:
            continue

        values = pd.to_numeric(df[ch], errors="coerce")
        if np.isfinite(values).any():
            available.append(
                {
                    "id": ch,
                    "label": CHANNEL_LABELS.get(ch, ch),
                    "unit": "",
                }
            )

    return available


def get_nearest_position_sample(
    df: pd.DataFrame,
    cursor_time_s: float,
) -> pd.Series | None:
    """
    Return the valid-position row closest to cursor_time_s.
    """
    valid = get_valid_path_points(df)
    if valid.empty:
        return None

    if "time_s" not in valid.columns:
        return valid.iloc[0]

    time_s = pd.to_numeric(valid["time_s"], errors="coerce")
    time_s = time_s.replace([np.inf, -np.inf], np.nan).dropna()

    if time_s.empty:
        return valid.iloc[0]

    idx = (time_s - float(cursor_time_s)).abs().idxmin()
    return valid.loc[idx]

def get_nearest_position_sample_by_latlon(
    df: pd.DataFrame,
    lat: float,
    lon: float,
) -> pd.Series | None:
    """
    Return the valid-position row geographically closest to (lat, lon).

    Uses haversine distance and valid GNSS rows only.
    """
    valid = get_valid_path_points(df)

    if valid.empty:
        return None

    try:
        lat0 = float(lat)
        lon0 = float(lon)
    except Exception:
        return None

    if not np.isfinite(lat0) or not np.isfinite(lon0):
        return None

    earth_radius_m = 6_371_000.0

    lat1 = np.radians(pd.to_numeric(valid["lat"], errors="coerce").to_numpy(dtype=float))
    lon1 = np.radians(pd.to_numeric(valid["lon"], errors="coerce").to_numpy(dtype=float))
    lat2 = np.radians(lat0)
    lon2 = np.radians(lon0)

    dlat = lat1 - lat2
    dlon = lon1 - lon2

    a = (
        np.sin(dlat / 2.0) ** 2
        + np.cos(lat2) * np.cos(lat1) * np.sin(dlon / 2.0) ** 2
    )
    a = np.clip(a, 0.0, 1.0)

    dist_m = earth_radius_m * 2.0 * np.arcsin(np.sqrt(a))

    if len(dist_m) == 0 or not np.isfinite(dist_m).any():
        return None

    local_pos = int(np.nanargmin(dist_m))
    return valid.iloc[local_pos]


def extract_clicked_latlon(map_result: dict) -> tuple[float, float] | None:
    """
    Extract (lat, lon) from streamlit-folium output.

    Supports:
    - {"last_clicked": {"lat": ..., "lng": ...}}
    - {"last_clicked": {"lat": ..., "lon": ...}}
    - {"last_object_clicked": {"lat": ..., "lng": ...}}
    - {"last_object_clicked": {"lat": ..., "lon": ...}}
    """
    if not isinstance(map_result, dict):
        return None

    for key in ("last_clicked", "last_object_clicked"):
        clicked = map_result.get(key)

        if not isinstance(clicked, dict):
            continue

        lat = clicked.get("lat")
        lon = clicked.get("lng", clicked.get("lon"))

        if lat is None or lon is None:
            continue

        try:
            lat_f = float(lat)
            lon_f = float(lon)
        except Exception:
            continue

        if np.isfinite(lat_f) and np.isfinite(lon_f):
            return lat_f, lon_f

    return None

def _make_base_map(center: list[float], zoom_start: int = 13) -> folium.Map:
    """
    Create the base Folium map.
    """
    return folium.Map(
        location=center,
        zoom_start=zoom_start,
        tiles="OpenStreetMap",
        control_scale=True,
        prefer_canvas=True,
    )


def _downsample_indices(n_points: int, max_segments: int) -> list[int]:
    """
    Return point indices such that number of segments is <= max_segments.
    """
    if n_points <= 0:
        return []

    max_points = max(2, int(max_segments) + 1)

    if n_points <= max_points:
        return list(range(n_points))

    stride = int(math.ceil(n_points / max_points))
    indices = list(range(0, n_points, stride))

    if indices[-1] != n_points - 1:
        indices.append(n_points - 1)

    return indices


def _make_colormap(values: pd.Series, caption: str) -> LinearColormap:
    """
    Build a robust continuous color map using 2%-98% quantiles.
    """
    clean = pd.to_numeric(values, errors="coerce")
    clean = clean.replace([np.inf, -np.inf], np.nan).dropna()

    if clean.empty:
        vmin, vmax = 0.0, 1.0
    elif len(clean) == 1:
        vmin = float(clean.iloc[0]) - 0.5
        vmax = float(clean.iloc[0]) + 0.5
    else:
        vmin = float(clean.quantile(0.02))
        vmax = float(clean.quantile(0.98))

        if not np.isfinite(vmin) or not np.isfinite(vmax):
            vmin, vmax = 0.0, 1.0

        if vmin == vmax:
            vmin -= 0.5
            vmax += 0.5

    return LinearColormap(
        colors=["#2b6cb0", "#00bcd4", "#7bd88f", "#f2c94c", "#eb5757"],
        vmin=vmin,
        vmax=vmax,
        caption=caption,
    )


def _color_for_value(value: object, channel: str, colormap: LinearColormap | None) -> str:
    """
    Convert a channel value to a CSS color.
    """
    value_num = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]

    if pd.isna(value_num) or not np.isfinite(value_num):
        return NAN_COLOR

    if channel == "estimated_gear":
        gear = int(round(float(value_num)))
        return GEAR_COLORS.get(gear, DEFAULT_GEAR_COLOR)

    if colormap is None:
        return NAN_COLOR

    return colormap(float(value_num))


def _popup_value(row: pd.Series, col: str, decimals: int = 2) -> str | None:
    """
    Format a value from a row for popup display.
    """
    if col not in row.index:
        return None

    val = row[col]
    if pd.isna(val):
        return None

    if col == "estimated_gear":
        try:
            return str(int(round(float(val))))
        except Exception:
            return str(val)

    if isinstance(val, (int, float, np.integer, np.floating)):
        return f"{float(val):.{decimals}f}"

    return str(val)


def _build_marker_popup(row: pd.Series, title: str) -> str:
    """
    Build popup HTML for start/end/cursor markers.
    """
    html = f"<b>{title}</b><br>"

    if "time_s" in row.index and pd.notna(row["time_s"]):
        html += f"time: {float(row['time_s']):.2f} s<br>"

    if "timestamp_utc_str" in row.index and pd.notna(row["timestamp_utc_str"]):
        html += f"UTC: {row['timestamp_utc_str']}<br>"

    if "lat" in row.index and "lon" in row.index:
        html += f"lat: {float(row['lat']):.6f}<br>"
        html += f"lon: {float(row['lon']):.6f}<br>"

    for ch in [
        "speed_obd_kmh",
        "rpm",
        "throttle_pct",
        "acc_lon_G",
        "acc_lat_G",
        "slope_deg",
        "estimated_gear",
    ]:
        formatted = _popup_value(row, ch)
        if formatted is not None:
            html += f"{CHANNEL_LABELS.get(ch, ch)}: {formatted}<br>"

    return html


def _add_gear_legend(m: folium.Map) -> None:
    """
    Add a simple HTML legend for estimated gear.
    """
    legend_html = """
    <div style="
        position: fixed;
        bottom: 30px;
        right: 30px;
        z-index: 1000;
        background-color: white;
        padding: 8px 10px;
        border: 1px solid #999;
        border-radius: 5px;
        font-size: 12px;
        color: #111;
    ">
    <b>Marcia stimata</b><br>
    """

    for gear, color in GEAR_COLORS.items():
        legend_html += (
            f'<span style="background:{color}; width:12px; height:12px; '
            f'display:inline-block; margin-right:4px;"></span>{gear}<br>'
        )

    legend_html += "</div>"
    m.get_root().html.add_child(folium.Element(legend_html))


def build_trace_map(
    df: pd.DataFrame,
    color_channel: str,
    cursor_time_s: float | None = None,
    max_segments: int = 5000,
) -> folium.Map:
    """
    Build a Folium map with raw GNSS path, color-coded segments and cursor marker.
    """
    valid = get_valid_path_points(df)

    if valid.empty:
        center = [45.4642, 9.1900]  # Milan fallback
        m = _make_base_map(center=center, zoom_start=6)
        folium.Marker(
            location=center,
            popup="Nessun punto GNSS valido nel file.",
            icon=folium.Icon(color="red", icon="info-sign"),
        ).add_to(m)
        return m

    center = [
        float(valid["lat"].median()),
        float(valid["lon"].median()),
    ]

    m = _make_base_map(center=center, zoom_start=13)

    if len(valid) == 1:
        row = valid.iloc[0]
        folium.Marker(
            location=[float(row["lat"]), float(row["lon"])],
            popup=_build_marker_popup(row, "Punto GNSS"),
            icon=folium.Icon(color="blue", icon="map-marker"),
        ).add_to(m)
        return m

    if color_channel not in valid.columns:
        fallback_channels = get_available_map_color_channels(valid)
        color_channel = fallback_channels[0]["id"] if fallback_channels else "speed_obd_kmh"

    values = pd.to_numeric(valid[color_channel], errors="coerce")

    if color_channel == "estimated_gear":
        colormap = None
    else:
        colormap = _make_colormap(values, CHANNEL_LABELS.get(color_channel, color_channel))

    indices = _downsample_indices(len(valid), max_segments)
    valid_ds = valid.iloc[indices].copy()
    values_ds = pd.to_numeric(valid_ds[color_channel], errors="coerce")

    # Folium expects [lat, lon], not [lon, lat].
    coords = [
        [float(row["lat"]), float(row["lon"])]
        for _, row in valid_ds.iterrows()
    ]

    for i in range(len(coords) - 1):
        value = values_ds.iloc[i + 1]
        color = _color_for_value(value, color_channel, colormap)

        folium.PolyLine(
            locations=[coords[i], coords[i + 1]],
            color=color,
            weight=4,
            opacity=0.85,
        ).add_to(m)

    start_row = valid.iloc[0]
    end_row = valid.iloc[-1]

    folium.Marker(
        location=[float(start_row["lat"]), float(start_row["lon"])],
        popup=_build_marker_popup(start_row, "Start"),
        icon=folium.Icon(color="green", icon="play"),
    ).add_to(m)

    folium.Marker(
        location=[float(end_row["lat"]), float(end_row["lon"])],
        popup=_build_marker_popup(end_row, "End"),
        icon=folium.Icon(color="red", icon="stop"),
    ).add_to(m)

    if cursor_time_s is not None:
        cursor_row = get_nearest_position_sample(df, cursor_time_s)
        if cursor_row is not None:
            folium.Marker(
                location=[float(cursor_row["lat"]), float(cursor_row["lon"])],
                popup=_build_marker_popup(cursor_row, f"Cursore t = {float(cursor_time_s):.2f} s"),
                icon=folium.Icon(color="orange", icon="record"),
            ).add_to(m)

    if color_channel == "estimated_gear":
        _add_gear_legend(m)
    elif colormap is not None:
        colormap.add_to(m)

    lat_min = float(valid["lat"].min())
    lat_max = float(valid["lat"].max())
    lon_min = float(valid["lon"].min())
    lon_max = float(valid["lon"].max())

    if lat_min == lat_max and lon_min == lon_max:
        m.location = [lat_min, lon_min]
        m.zoom_start = 16
    else:
        m.fit_bounds([[lat_min, lon_min], [lat_max, lon_max]], padding=(20, 20))

    return m