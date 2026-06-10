"""
metrics.py – Compute summary metrics for a normalised Trace session.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


# ── Small helpers ─────────────────────────────────────────────────────────────

def _safe_max(series: pd.Series) -> float | None:
    """Return max of *series* ignoring NaN, or None if all NaN / missing."""
    if series is None or series.dropna().empty:
        return None
    return float(series.max())


def _safe_min(series: pd.Series) -> float | None:
    """Return min of *series* ignoring NaN, or None if all NaN / missing."""
    if series is None or series.dropna().empty:
        return None
    return float(series.min())


def _col(df: pd.DataFrame, name: str) -> pd.Series | None:
    """Return column *name* from *df*, or None if it doesn't exist."""
    return df[name] if name in df.columns else None


def _last_valid(series: pd.Series | None) -> float | None:
    if series is None:
        return None
    valid = series.dropna()
    return float(valid.iloc[-1]) if not valid.empty else None


# ── Main function ─────────────────────────────────────────────────────────────

def compute_session_metrics(df: pd.DataFrame) -> dict:
    """
    Compute summary metrics from a normalised Trace DataFrame.

    All fields are robust to missing columns or all-NaN columns.
    Numeric fields are plain Python floats (or None when unavailable).

    Parameters
    ----------
    df : pd.DataFrame
        Output of normalize_trace_data().

    Returns
    -------
    dict
        Flat dictionary of named metric values.
    """
    metrics: dict = {}

    # ── Sample count ──────────────────────────────────────────────────────────
    metrics["sample_count"] = int(len(df))

    # ── Duration ──────────────────────────────────────────────────────────────
    time_s = _col(df, "time_s")
    if time_s is not None and not time_s.dropna().empty:
        metrics["duration_s"] = float(time_s.dropna().iloc[-1] - time_s.dropna().iloc[0])
    else:
        metrics["duration_s"] = None

    # ── Sample rate ───────────────────────────────────────────────────────────
    sample_dt = _col(df, "sample_dt_s")
    if sample_dt is not None:
        valid_dt = sample_dt.dropna()
        metrics["median_sample_dt_s"] = float(valid_dt.median()) if not valid_dt.empty else None
        dur = metrics.get("duration_s")
        n   = metrics["sample_count"]
        metrics["mean_sample_rate_hz"] = float(n / dur) if dur and dur > 0 else None
    else:
        metrics["median_sample_dt_s"]  = None
        metrics["mean_sample_rate_hz"] = None

    # ── Distance ──────────────────────────────────────────────────────────────
    metrics["distance_from_speed_m"] = _last_valid(_col(df, "distance_from_speed_m"))
    metrics["distance_from_gnss_m"]  = _last_valid(_col(df, "distance_from_gnss_m"))
    metrics["distance_m"]            = _last_valid(_col(df, "distance_m"))

    # ── Speed ─────────────────────────────────────────────────────────────────
    spd_col = _col(df, "speed_obd_kmh")
    metrics["max_speed_kmh"] = _safe_max(spd_col)

    # ── Engine / OBD ──────────────────────────────────────────────────────────
    metrics["max_rpm"]          = _safe_max(_col(df, "rpm"))
    metrics["max_throttle_pct"] = _safe_max(_col(df, "throttle_pct"))
    metrics["max_load_pct"]     = _safe_max(_col(df, "load_pct"))

    # ── Longitudinal acceleration ─────────────────────────────────────────────
    acc_lon = _col(df, "acc_lon_G")
    metrics["max_acc_lon_G"] = _safe_max(acc_lon)
    metrics["min_acc_lon_G"] = _safe_min(acc_lon)   # negative = braking

    # ── Lateral acceleration ──────────────────────────────────────────────────
    acc_lat = _col(df, "acc_lat_G")
    if acc_lat is not None and not acc_lat.dropna().empty:
        metrics["max_abs_acc_lat_G"] = float(acc_lat.abs().max())
    else:
        metrics["max_abs_acc_lat_G"] = None

    # ── Jerk (Phase 7) ────────────────────────────────────────────────────────
    jerk_lon = _col(df, "jerk_lon_mps3")
    if jerk_lon is not None and not jerk_lon.dropna().empty:
        metrics["max_abs_jerk_lon_mps3"] = float(jerk_lon.abs().max())
    else:
        metrics["max_abs_jerk_lon_mps3"] = None

    jerk_lat = _col(df, "jerk_lat_mps3")
    if jerk_lat is not None and not jerk_lat.dropna().empty:
        metrics["max_abs_jerk_lat_mps3"] = float(jerk_lat.abs().max())
    else:
        metrics["max_abs_jerk_lat_mps3"] = None

    # ── Curvature and radius (Phase 7) ────────────────────────────────────────
    radius = _col(df, "curve_radius_m")
    if radius is not None and not radius.dropna().empty:
        metrics["min_curve_radius_m"] = _safe_min(radius)
    else:
        metrics["min_curve_radius_m"] = None

    # ── Altitude ──────────────────────────────────────────────────────────────
    metrics["min_alt_m"] = _safe_min(_col(df, "alt_m"))
    metrics["max_alt_m"] = _safe_max(_col(df, "alt_m"))

    # ── UTC labels (human-readable only) ─────────────────────────────────────
    utc_col = _col(df, "timestamp_utc_str")
    if utc_col is not None and not utc_col.dropna().empty:
        metrics["start_utc_label"] = str(utc_col.dropna().iloc[0])
        metrics["end_utc_label"]   = str(utc_col.dropna().iloc[-1])
    else:
        metrics["start_utc_label"] = None
        metrics["end_utc_label"]   = None
    
    # ── Estimated gear ────────────────────────────────────────────────────────
    gear_col = _col(df, "estimated_gear")
    if gear_col is not None and not gear_col.dropna().empty:
        metrics["min_estimated_gear"] = int(gear_col.min())
        metrics["max_estimated_gear"] = int(gear_col.max())
    else:
        metrics["min_estimated_gear"] = None
        metrics["max_estimated_gear"] = None
    
    return metrics