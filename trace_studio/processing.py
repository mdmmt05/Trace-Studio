"""
processing.py – Derive normalized columns from a raw Trace DataFrame.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from trace_studio.config import G_TO_MPS2, KMH_TO_MPS

def _haversine_series(lat: pd.Series, lon: pd.Series) -> pd.Series:
    """
    Return step distances in metres between consecutive lat/lon rows.

    Robust to:
    - empty series
    - NaN coordinates
    - origin coordinates 0,0
    """
    if lat is None or lon is None or len(lat) == 0 or len(lon) == 0:
        return pd.Series(np.nan, index=lat.index if lat is not None else None, dtype=float)

    R = 6_371_000.0

    lat_num = pd.to_numeric(lat, errors="coerce")
    lon_num = pd.to_numeric(lon, errors="coerce")

    lat_np = lat_num.to_numpy(dtype=float)
    lon_np = lon_num.to_numpy(dtype=float)

    distances = np.zeros(len(lat_np), dtype=float)

    if len(lat_np) == 0:
        return pd.Series(distances, index=lat.index, dtype=float)

    lat_r = np.radians(lat_np)
    lon_r = np.radians(lon_np)

    invalid_current = (
        ~np.isfinite(lat_np)
        | ~np.isfinite(lon_np)
        | ((lat_np == 0.0) & (lon_np == 0.0))
    )

    if len(lat_np) == 1:
        distances[0] = 0.0
        return pd.Series(distances, index=lat.index, dtype=float)

    dlat = np.diff(lat_r, prepend=lat_r[0])
    dlon = np.diff(lon_r, prepend=lon_r[0])

    a = (
        np.sin(dlat / 2.0) ** 2
        + np.cos(lat_r) * np.cos(np.roll(lat_r, 1)) * np.sin(dlon / 2.0) ** 2
    )
    a = np.clip(a, 0.0, 1.0)

    distances = R * 2.0 * np.arcsin(np.sqrt(a))
    distances[0] = 0.0

    invalid_previous = np.roll(invalid_current, 1)
    invalid_previous[0] = True

    bad_step = invalid_current | invalid_previous
    distances[bad_step] = 0.0

    return pd.Series(distances, index=lat.index, dtype=float)


def _rolling_median_filter(series: pd.Series, window: int = 5) -> pd.Series:
    """
    Apply a small rolling median filter.

    Do not forward/backward fill: keeping NaN gaps visible is better for
    derivatives and diagnostic analysis.
    """
    if series is None:
        return pd.Series(dtype=float)

    if series.empty:
        return pd.Series(np.nan, index=series.index, dtype=float)

    numeric = pd.to_numeric(series, errors="coerce")
    return numeric.rolling(window=window, center=True, min_periods=1).median()

def _compute_filtered_acceleration(
    df: pd.DataFrame,
    raw_col: str,
    mps2_col: str,
    window: int = 5,
) -> tuple[pd.Series, pd.Series]:
    """
    Compute filtered acceleration channels in G and m/s².

    Parameters
    ----------
    df : pd.DataFrame
        Normalized dataframe.
    raw_col : str
        Raw acceleration column in G, for example "acc_lon_G".
    mps2_col : str
        Acceleration column in m/s², for example "acc_lon_mps2".
    window : int
        Rolling median window in samples.

    Returns
    -------
    (filt_g, filt_mps2)
        Filtered acceleration in G and m/s².
    """
    index = df.index

    has_raw_g = raw_col in df.columns
    has_mps2 = mps2_col in df.columns

    if has_raw_g:
        raw_g = pd.to_numeric(df[raw_col], errors="coerce")
    elif has_mps2:
        raw_mps2_tmp = pd.to_numeric(df[mps2_col], errors="coerce")
        raw_g = raw_mps2_tmp / G_TO_MPS2
    else:
        raw_g = pd.Series(np.nan, index=index, dtype=float)

    if has_mps2:
        raw_mps2 = pd.to_numeric(df[mps2_col], errors="coerce")
    elif has_raw_g:
        raw_mps2 = raw_g * G_TO_MPS2
    else:
        raw_mps2 = pd.Series(np.nan, index=index, dtype=float)

    filt_g = _rolling_median_filter(raw_g, window=window)
    filt_mps2 = _rolling_median_filter(raw_mps2, window=window)

    # Guarantee index alignment with the dataframe.
    filt_g = filt_g.reindex(index)
    filt_mps2 = filt_mps2.reindex(index)

    return filt_g.astype(float), filt_mps2.astype(float)

def _compute_jerk(
    acc_mps2_filt: pd.Series,
    dt_s: pd.Series,
    max_dt: float = 2.0,
) -> pd.Series:
    """
    Compute jerk = d(acceleration) / dt.

    Invalid where:
    - dt <= 0
    - dt is NaN/inf
    - dt > max_dt
    - acceleration is NaN/inf
    """
    if acc_mps2_filt is None:
        return pd.Series(dtype=float)

    if acc_mps2_filt.empty:
        return pd.Series(np.nan, index=acc_mps2_filt.index, dtype=float)

    acc = pd.to_numeric(acc_mps2_filt, errors="coerce")
    dt = pd.to_numeric(dt_s, errors="coerce").reindex(acc.index)

    acc_diff = acc.diff()
    jerk = acc_diff / dt

    invalid = (
        ~np.isfinite(acc)
        | ~np.isfinite(acc_diff)
        | ~np.isfinite(dt)
        | (dt <= 0.0)
        | (dt > max_dt)
    )

    jerk[invalid] = np.nan
    return jerk.astype(float)


def _compute_curvature_from_yaw_rate(
    yaw_rate_dps: pd.Series,
    speed_mps: pd.Series,
    min_speed_mps: float = 1.0,
) -> pd.Series:
    """
    Curvature = yaw_rate_rad_s / speed_mps.

    Invalid at very low speed and for non-finite input.
    """
    yaw = pd.to_numeric(yaw_rate_dps, errors="coerce")
    speed = pd.to_numeric(speed_mps, errors="coerce").reindex(yaw.index)

    yaw_rate_rad_s = np.radians(yaw)
    curvature = yaw_rate_rad_s / speed

    invalid = (
        ~np.isfinite(yaw_rate_rad_s)
        | ~np.isfinite(speed)
        | (speed < min_speed_mps)
    )

    curvature[invalid] = np.nan
    return curvature.astype(float)


def _compute_curvature_from_heading(
    heading_deg: pd.Series,
    time_s: pd.Series,
    speed_mps: pd.Series,
    min_speed_mps: float = 1.0,
    max_dt_s: float = 2.0,
) -> pd.Series:
    """
    Approximate curvature from heading derivative.

    This fallback is intentionally conservative: it does not interpolate through
    NaN heading values.
    """
    heading = pd.to_numeric(heading_deg, errors="coerce")
    time = pd.to_numeric(time_s, errors="coerce").reindex(heading.index)
    speed = pd.to_numeric(speed_mps, errors="coerce").reindex(heading.index)

    curvature = pd.Series(np.nan, index=heading.index, dtype=float)

    valid_heading = heading.notna() & np.isfinite(heading)
    if valid_heading.sum() < 2:
        return curvature

    heading_rad = pd.Series(np.nan, index=heading.index, dtype=float)
    heading_rad.loc[valid_heading] = np.unwrap(np.radians(heading.loc[valid_heading].to_numpy(dtype=float)))

    dt = time.diff()
    d_heading = heading_rad.diff()
    yaw_rate_rad_s = d_heading / dt

    valid = (
        np.isfinite(yaw_rate_rad_s)
        & np.isfinite(speed)
        & np.isfinite(dt)
        & (dt > 0.0)
        & (dt <= max_dt_s)
        & (speed >= min_speed_mps)
    )

    curvature.loc[valid] = yaw_rate_rad_s.loc[valid] / speed.loc[valid]
    return curvature

# ── Main normalization function ───────────────────────────────────────────────

def normalize_trace_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Return a *copy* of *df* with additional derived columns.

    Added columns (basics)
    ----------------------
    time_s               – Elapsed seconds from first valid t_mono_us.
    sample_dt_s          – Time delta between consecutive rows (NaN for first row).
    speed_mps            – speed_obd_kmh converted to m/s.
    acc_lon_mps2         – acc_lon_G converted to m/s².
    acc_lat_mps2         – acc_lat_G converted to m/s².
    distance_from_speed_m– Cumulative distance from OBD speed integration (m).
    gnss_step_distance_m – Haversine distance between consecutive GNSS points (m).
    distance_from_gnss_m – Cumulative distance from GNSS positions (m).
    valid_position       – True when lat/lon are finite and not both zero.
    valid_time           – True when t_mono_us and time_s are finite.

    Added columns (Phase 7 – essential derived)
    --------------------------------------------
    distance_m           – Canonical cumulative distance (GNSS preferred, else speed)
    distance_km          – distance_m in km
    acc_lon_G_filt       – Smoothed longitudinal acceleration (G)
    acc_lat_G_filt       – Smoothed lateral acceleration (G)
    acc_lon_mps2_filt    – Smoothed longitudinal acceleration (m/s²)
    acc_lat_mps2_filt    – Smoothed lateral acceleration (m/s²)
    jerk_lon_mps3        – Longitudinal jerk (m/s³)
    jerk_lat_mps3        – Lateral jerk (m/s³)
    curvature_1pm        – Approximate signed path curvature (1/m)
    abs_curvature_1pm    – Absolute curvature (1/m)
    curve_radius_m       – Approximate curve radius (m)
    """
    out = df.copy()

    # ── Time axis ─────────────────────────────────────────────────────────────
    if "t_mono_us" in out.columns:
        t0 = out["t_mono_us"].dropna().iloc[0] if not out["t_mono_us"].dropna().empty else 0.0
        out["time_s"] = (out["t_mono_us"] - t0) / 1_000_000.0
        out["sample_dt_s"] = out["time_s"].diff()
    else:
        out["time_s"] = np.nan
        out["sample_dt_s"] = np.nan

    # ── Speed ─────────────────────────────────────────────────────────────────
    if "speed_obd_kmh" in out.columns:
        out["speed_mps"] = out["speed_obd_kmh"] * KMH_TO_MPS
    else:
        out["speed_mps"] = np.nan

    # ── Accelerations (raw SI) ────────────────────────────────────────────────
    if "acc_lon_G" in out.columns:
        out["acc_lon_mps2"] = out["acc_lon_G"] * G_TO_MPS2
    else:
        out["acc_lon_mps2"] = np.nan

    if "acc_lat_G" in out.columns:
        out["acc_lat_mps2"] = out["acc_lat_G"] * G_TO_MPS2
    else:
        out["acc_lat_mps2"] = np.nan

    # ── Distance from OBD speed (rectangular integration) ────────────────────
    if "speed_mps" in out.columns and "sample_dt_s" in out.columns:
        dt = out["sample_dt_s"].fillna(0.0).clip(lower=0.0)
        spd = out["speed_mps"].fillna(0.0)
        increments = spd * dt
        out["distance_from_speed_m"] = increments.cumsum()
    else:
        out["distance_from_speed_m"] = np.nan

    # ── GNSS-based distance ───────────────────────────────────────────────────
    if "lat" in out.columns and "lon" in out.columns:
        out["gnss_step_distance_m"] = _haversine_series(out["lat"], out["lon"])
        out["distance_from_gnss_m"] = out["gnss_step_distance_m"].fillna(0.0).cumsum()
    else:
        out["gnss_step_distance_m"] = np.nan
        out["distance_from_gnss_m"] = np.nan

    # ── Validity flags ────────────────────────────────────────────────────────
    if "lat" in out.columns and "lon" in out.columns:
        lat_ok = np.isfinite(out["lat"])
        lon_ok = np.isfinite(out["lon"])
        not_origin = ~((out["lat"] == 0) & (out["lon"] == 0))
        out["valid_position"] = lat_ok & lon_ok & not_origin
    else:
        out["valid_position"] = False

    if "t_mono_us" in out.columns and "time_s" in out.columns:
        out["valid_time"] = np.isfinite(out["t_mono_us"]) & np.isfinite(out["time_s"])
    else:
        out["valid_time"] = False

    # ──────────────────────────────────────────────────────────────────────────
    # Phase 7 derived channels
    # ──────────────────────────────────────────────────────────────────────────

    # 1. Canonical distance
    use_gnss = False
    if "distance_from_gnss_m" in out.columns and "valid_position" in out.columns:
        valid_gnss = out["valid_position"].sum()
        final_gnss_dist = out["distance_from_gnss_m"].dropna().iloc[-1] if not out["distance_from_gnss_m"].dropna().empty else 0.0
        if valid_gnss >= 2 and final_gnss_dist > 1.0:
            use_gnss = True
    if use_gnss:
        out["distance_m"] = out["distance_from_gnss_m"]
    else:
        out["distance_m"] = out["distance_from_speed_m"] if "distance_from_speed_m" in out.columns else np.nan
    out["distance_km"] = out["distance_m"] / 1000.0

    # 2. Filtered accelerations
    window = 5
    lon_filt_G, lon_filt_mps2 = _compute_filtered_acceleration(out, "acc_lon_G", "acc_lon_mps2", window)
    lat_filt_G, lat_filt_mps2 = _compute_filtered_acceleration(out, "acc_lat_G", "acc_lat_mps2", window)
    out["acc_lon_G_filt"] = lon_filt_G
    out["acc_lon_mps2_filt"] = lon_filt_mps2
    out["acc_lat_G_filt"] = lat_filt_G
    out["acc_lat_mps2_filt"] = lat_filt_mps2

    # 3. Jerk
    dt_series = out["time_s"].diff()  # already computed as sample_dt_s, but recompute to be safe
    out["jerk_lon_mps3"] = _compute_jerk(out["acc_lon_mps2_filt"], dt_series)
    out["jerk_lat_mps3"] = _compute_jerk(out["acc_lat_mps2_filt"], dt_series)

    # 4. Curvature and radius
    speed_mps = out["speed_mps"]
    curvature = pd.Series(np.nan, index=out.index)

    # Prefer yawRate_dps
    if "yawRate_dps" in out.columns and out["yawRate_dps"].notna().any():
        curvature = _compute_curvature_from_yaw_rate(out["yawRate_dps"], speed_mps)
    elif "heading_deg" in out.columns and out["heading_deg"].notna().any():
        # Fallback to heading derivative
        curvature = _compute_curvature_from_heading(out["heading_deg"], out["time_s"], speed_mps)
    else:
        curvature[:] = np.nan

    out["curvature_1pm"] = pd.to_numeric(curvature, errors="coerce")
    out["abs_curvature_1pm"] = out["curvature_1pm"].abs()
    
    abs_curv = out["abs_curvature_1pm"]
    radius = pd.Series(np.nan, index=out.index, dtype=float)
    
    valid_radius = np.isfinite(abs_curv) & (abs_curv >= 1e-5)
    radius.loc[valid_radius] = 1.0 / abs_curv.loc[valid_radius]
    radius[radius > 10_000.0] = np.nan
    
    out["curve_radius_m"] = radius

    return out