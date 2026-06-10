"""
schema.py – Column definitions, units, descriptions, and CSV validation.
"""

import pandas as pd

# ── Required columns ──────────────────────────────────────────────────────────

EXPECTED_COLUMNS: list[str] = [
    "timestamp_utc_str",
    "lat", "lon", "alt_m",
    "sat", "hdop",
    "speed_obd_kmh",
    "acc_lon_G", "acc_lat_G",
    "roll_deg", "pitch_deg", "slope_deg", "slope_confidence",
    "heading_deg", "yawRate_dps", "heading_confidence",
    "rpm", "load_pct", "throttle_pct",
    "estimated_gear",
    "t_mono_us", "utc_epoch_us", "utc_valid", "sync_quality",
    "imu_t_us", "gnss_t_us", "obd_speed_t_us",
    "imu_age_ms", "gnss_age_ms", "obd_speed_age_ms",
]

# All columns that should be numeric (everything except the human-readable label)
NUMERIC_COLUMNS: list[str] = [
    c for c in EXPECTED_COLUMNS if c != "timestamp_utc_str"
]

# ── Units ─────────────────────────────────────────────────────────────────────

COLUMN_UNITS: dict[str, str] = {
    # Raw columns
    "lat":                  "°",
    "lon":                  "°",
    "alt_m":                "m",
    "sat":                  "–",
    "hdop":                 "–",
    "speed_obd_kmh":        "km/h",
    "acc_lon_G":            "G",
    "acc_lat_G":            "G",
    "roll_deg":             "°",
    "pitch_deg":            "°",
    "slope_deg":            "°",
    "slope_confidence":     "–",
    "heading_deg":          "°",
    "yawRate_dps":          "°/s",
    "heading_confidence":   "–",
    "rpm":                  "rpm",
    "load_pct":             "%",
    "throttle_pct":         "%",
    "estimated_gear":       "–",
    "t_mono_us":            "µs",
    "utc_epoch_us":         "µs",
    "utc_valid":            "–",
    "sync_quality":         "–",
    "imu_t_us":             "µs",
    "gnss_t_us":            "µs",
    "obd_speed_t_us":       "µs",
    "imu_age_ms":           "ms",
    "gnss_age_ms":          "ms",
    "obd_speed_age_ms":     "ms",
    # Derived / normalized columns
    "time_s":               "s",
    "sample_dt_s":          "s",
    "speed_mps":            "m/s",
    "acc_lon_mps2":         "m/s²",
    "acc_lat_mps2":         "m/s²",
    "distance_from_speed_m":"m",
    "gnss_step_distance_m": "m",
    "distance_from_gnss_m": "m",
    "valid_position":       "bool",
    "valid_time":           "bool",
        # Phase 7 derived channels
    "distance_m":           "m",
    "distance_km":          "km",
    "acc_lon_G_filt":       "G",
    "acc_lat_G_filt":       "G",
    "acc_lon_mps2_filt":    "m/s²",
    "acc_lat_mps2_filt":    "m/s²",
    "jerk_lon_mps3":        "m/s³",
    "jerk_lat_mps3":        "m/s³",
    "curvature_1pm":        "1/m",
    "abs_curvature_1pm":    "1/m",
    "curve_radius_m":       "m",
}

# ── Descriptions ──────────────────────────────────────────────────────────────

COLUMN_DESCRIPTIONS: dict[str, str] = {
    "timestamp_utc_str":    "Human-readable UTC timestamp (label only, not used as time axis)",
    "lat":                  "Latitude from GNSS",
    "lon":                  "Longitude from GNSS",
    "alt_m":                "Altitude above sea level from GNSS",
    "sat":                  "Number of visible GNSS satellites",
    "hdop":                 "Horizontal Dilution of Precision",
    "speed_obd_kmh":        "Vehicle speed from OBD-II",
    "acc_lon_G":            "Longitudinal acceleration (G) – positive = forward",
    "acc_lat_G":            "Lateral acceleration (G) – positive = left",
    "roll_deg":             "Vehicle roll angle",
    "pitch_deg":            "Vehicle pitch angle",
    "slope_deg":            "Road slope estimate",
    "slope_confidence":     "Confidence score for slope estimate",
    "heading_deg":          "Vehicle heading (0 = North)",
    "yawRate_dps":          "Yaw rate from IMU",
    "heading_confidence":   "Confidence score for heading estimate",
    "rpm":                  "Engine RPM from OBD-II",
    "load_pct":             "Engine load percentage from OBD-II",
    "throttle_pct":         "Throttle position percentage from OBD-II",
    "estimated_gear":       "Estimated current gear",
    "t_mono_us":            "Monotonic timer in microseconds – primary time axis",
    "utc_epoch_us":         "UTC epoch in microseconds (reference, not primary axis)",
    "utc_valid":            "1 if UTC time is valid/synced",
    "sync_quality":         "Multi-source sync quality score",
    "imu_t_us":             "Timestamp of latest IMU sample",
    "gnss_t_us":            "Timestamp of latest GNSS sample",
    "obd_speed_t_us":       "Timestamp of latest OBD speed sample",
    "imu_age_ms":           "Age of IMU data at log time",
    "gnss_age_ms":          "Age of GNSS data at log time",
    "obd_speed_age_ms":     "Age of OBD speed data at log time",
    # Derived
    "time_s":               "Elapsed time from session start (derived from t_mono_us)",
    "sample_dt_s":          "Time delta between consecutive samples",
    "speed_mps":            "Vehicle speed in m/s (converted from speed_obd_kmh)",
    "acc_lon_mps2":         "Longitudinal acceleration in m/s² (converted from acc_lon_G)",
    "acc_lat_mps2":         "Lateral acceleration in m/s² (converted from acc_lat_G)",
    "distance_from_speed_m":"Cumulative distance from OBD speed integration",
    "gnss_step_distance_m": "Haversine distance between consecutive GNSS points",
    "distance_from_gnss_m": "Cumulative distance from GNSS positions",
    "valid_position":       "True when lat/lon are finite and non-zero",
    "valid_time":           "True when t_mono_us and time_s are finite",
    "distance_m":           "Canonical cumulative distance, GNSS preferred, speed integration fallback",
    "distance_km":          "Canonical cumulative distance in km",
    "acc_lon_G_filt":       "Smoothed longitudinal acceleration",
    "acc_lat_G_filt":       "Smoothed lateral acceleration",
    "acc_lon_mps2_filt":    "Smoothed longitudinal acceleration in SI units",
    "acc_lat_mps2_filt":    "Smoothed lateral acceleration in SI units",
    "jerk_lon_mps3":        "Time derivative of filtered longitudinal acceleration",
    "jerk_lat_mps3":        "Time derivative of filtered lateral acceleration",
    "curvature_1pm":        "Approximate signed path curvature from yaw rate or heading derivative",
    "abs_curvature_1pm":    "Absolute approximate path curvature",
    "curve_radius_m":       "Approximate curve radius from curvature",
}


# ── Validation ────────────────────────────────────────────────────────────────

def validate_columns(df: pd.DataFrame) -> dict:
    """
    Check that all EXPECTED_COLUMNS are present in *df*.

    Returns
    -------
    dict with keys:
        ok       – True if all mandatory columns are present
        missing  – list of expected columns not found in df
        extra    – list of columns in df not in EXPECTED_COLUMNS
        present  – list of expected columns found in df
    """
    df_cols = set(df.columns)
    expected = set(EXPECTED_COLUMNS)

    missing = sorted(expected - df_cols)
    extra   = sorted(df_cols - expected)
    present = sorted(expected & df_cols)

    return {
        "ok":      len(missing) == 0,
        "missing": missing,
        "extra":   extra,
        "present": present,
    }
