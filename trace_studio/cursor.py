"""
cursor.py - Centralized management of the global cursor time.

Single source of truth:
    st.session_state["cursor_time_s"]
"""

from __future__ import annotations

import math

import pandas as pd
import streamlit as st


CURSOR_STATE_KEY = "cursor_time_s"
LEGACY_CURSOR_KEY = "time_cursor"


def _as_finite_float(value: object) -> float | None:
    """Convert value to finite float, or return None."""
    try:
        out = float(value)
    except Exception:
        return None

    if not math.isfinite(out):
        return None

    return out


def get_valid_time_range(df: pd.DataFrame) -> tuple[float | None, float | None]:
    """
    Return (min_time_s, max_time_s), ignoring NaN/inf.
    """
    if df.empty or "time_s" not in df.columns:
        return None, None

    time_s = pd.to_numeric(df["time_s"], errors="coerce")
    time_s = time_s.where(time_s.apply(lambda x: math.isfinite(float(x)) if pd.notna(x) else False))
    time_s = time_s.dropna()

    if time_s.empty:
        return None, None

    return float(time_s.min()), float(time_s.max())


def clamp_cursor_time(df: pd.DataFrame, value: object) -> float | None:
    """
    Clamp a candidate cursor time to the current dataframe time range.
    """
    value_f = _as_finite_float(value)
    if value_f is None:
        return None

    tmin, tmax = get_valid_time_range(df)
    if tmin is None or tmax is None:
        return None

    if value_f < tmin:
        return tmin

    if value_f > tmax:
        return tmax

    return value_f


def _migrate_legacy_cursor(state_key: str = CURSOR_STATE_KEY) -> None:
    """
    Migrate old key 'time_cursor' to canonical 'cursor_time_s'.
    """
    if LEGACY_CURSOR_KEY in st.session_state and state_key not in st.session_state:
        legacy = _as_finite_float(st.session_state[LEGACY_CURSOR_KEY])
        if legacy is not None:
            st.session_state[state_key] = legacy

    if LEGACY_CURSOR_KEY in st.session_state:
        del st.session_state[LEGACY_CURSOR_KEY]


def get_cursor_time(
    df: pd.DataFrame,
    state_key: str = CURSOR_STATE_KEY,
    default_midpoint: bool = True,
) -> float | None:
    """
    Get canonical cursor time.

    If missing or invalid, initialize/reset to the midpoint when allowed.
    """
    _migrate_legacy_cursor(state_key)

    tmin, tmax = get_valid_time_range(df)
    if tmin is None or tmax is None:
        return None

    if state_key not in st.session_state:
        if not default_midpoint:
            return None
        st.session_state[state_key] = (tmin + tmax) / 2.0

    cursor = clamp_cursor_time(df, st.session_state[state_key])

    if cursor is None:
        if not default_midpoint:
            return None
        cursor = (tmin + tmax) / 2.0

    st.session_state[state_key] = cursor
    return cursor


def set_cursor_time(
    df: pd.DataFrame,
    value: object,
    state_key: str = CURSOR_STATE_KEY,
) -> float | None:
    """
    Set canonical cursor time after clamping.
    """
    clamped = clamp_cursor_time(df, value)
    if clamped is None:
        return None

    st.session_state[state_key] = clamped
    return clamped


def get_cursor_row(df: pd.DataFrame, cursor_time_s: object) -> pd.Series | None:
    """
    Return the row closest to cursor_time_s.
    """
    cursor = _as_finite_float(cursor_time_s)
    if cursor is None:
        return None

    if df.empty or "time_s" not in df.columns:
        return None

    time_col = pd.to_numeric(df["time_s"], errors="coerce")
    time_col = time_col.where(time_col.apply(lambda x: math.isfinite(float(x)) if pd.notna(x) else False))
    time_col = time_col.dropna()

    if time_col.empty:
        return None

    idx = (time_col - cursor).abs().idxmin()
    return df.loc[idx]