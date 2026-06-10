"""
performance.py – Single-session performance analysis for Trace Studio.

Phase 9 MVP:
- 0–50 km/h
- 0–100 km/h
- 80–120 km/h
- strongest braking
- maximum lateral acceleration
- maximum speed / RPM / throttle / load
- threshold durations
- friction circle figure
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import plotly.graph_objects as go

def _num(df: pd.DataFrame, col: str) -> pd.Series:
    if col not in df.columns:
        return pd.Series(np.nan, index=df.index, dtype=float)
    return pd.to_numeric(df[col], errors="coerce")


def _preferred_col(df: pd.DataFrame, candidates: list[str]) -> pd.Series | None:
    for col in candidates:
        if col in df.columns:
            series = pd.to_numeric(df[col], errors="coerce")
            if series.notna().any():
                return series
    return None


def _finite(value: object) -> bool:
    try:
        return math.isfinite(float(value))
    except Exception:
        return False


def _row_float(df: pd.DataFrame, idx: object, col: str) -> float | None:
    if col not in df.columns or idx not in df.index:
        return None
    value = df.loc[idx, col]
    if not _finite(value):
        return None
    return float(value)


def _max_with_time(df: pd.DataFrame, series: pd.Series | None) -> tuple[object, float] | None:
    if series is None:
        return None

    s = pd.to_numeric(series, errors="coerce")
    s = s.replace([np.inf, -np.inf], np.nan).dropna()

    if s.empty:
        return None

    idx = s.idxmax()
    return idx, float(s.loc[idx])


def _min_with_time(df: pd.DataFrame, series: pd.Series | None) -> tuple[object, float] | None:
    if series is None:
        return None

    s = pd.to_numeric(series, errors="coerce")
    s = s.replace([np.inf, -np.inf], np.nan).dropna()

    if s.empty:
        return None

    idx = s.idxmin()
    return idx, float(s.loc[idx])


def _duration_per_row(df: pd.DataFrame) -> pd.Series:
    """
    Duration represented by each row.

    Uses time_s.diff(). The first row contributes 0. Invalid, negative or very
    large gaps are ignored.
    """
    if "time_s" not in df.columns:
        return pd.Series(0.0, index=df.index, dtype=float)

    t = pd.to_numeric(df["time_s"], errors="coerce")
    dt = t.diff().fillna(0.0)
    dt[~np.isfinite(dt)] = 0.0
    dt[dt < 0.0] = 0.0
    dt[dt > 5.0] = 0.0
    return dt.astype(float)


def _time_where(dt: pd.Series, condition: pd.Series) -> float | None:
    if dt is None or condition is None:
        return None

    condition = condition.reindex(dt.index).fillna(False)
    value = float(dt[condition].sum())

    if not math.isfinite(value):
        return None

    return value


def _best_accel_time(
    time_s: pd.Series,
    speed_kmh: pd.Series,
    lower_kmh: float,
    upper_kmh: float,
) -> float | None:
    """
    Return the fastest time interval from lower_kmh to upper_kmh.

    For 0-x measurements, the start is accepted only if speed is close to zero
    (<= 3 km/h), because many logs start while already moving.
    """
    t = pd.to_numeric(time_s, errors="coerce")
    v = pd.to_numeric(speed_kmh, errors="coerce")

    data = pd.DataFrame({"t": t, "v": v}).replace([np.inf, -np.inf], np.nan).dropna()
    if len(data) < 2:
        return None

    data = data.sort_values("t").drop_duplicates(subset=["t"], keep="first")
    if len(data) < 2:
        return None

    t_arr = data["t"].to_numpy(dtype=float)
    v_arr = data["v"].to_numpy(dtype=float)

    best: float | None = None
    n = len(data)

    for i in range(1, n):
        v0 = v_arr[i - 1]
        v1 = v_arr[i]
        t0 = t_arr[i - 1]
        t1 = t_arr[i]

        start_time: float | None = None

        if lower_kmh <= 0.0:
            if v0 <= 3.0 and v1 > v0:
                start_time = t0
        else:
            if v0 <= lower_kmh < v1:
                start_time = _crossing_time(t0, v0, t1, v1, lower_kmh)

        if start_time is None:
            continue

        for j in range(i, n):
            pv = v_arr[j - 1]
            cv = v_arr[j]
            pt = t_arr[j - 1]
            ct = t_arr[j]

            if pv < upper_kmh <= cv:
                end_time = _crossing_time(pt, pv, ct, cv, upper_kmh)
                if end_time is None:
                    continue

                duration = end_time - start_time
                if duration <= 0 or not math.isfinite(duration):
                    continue

                if best is None or duration < best:
                    best = float(duration)

                break

    return best

def _best_accel_time_with_reason(
    time_s: pd.Series,
    speed_kmh: pd.Series,
    lower_kmh: float,
    upper_kmh: float,
) -> dict:
    """
    Return fastest acceleration interval plus a human-readable reason when missing.
    """
    t = pd.to_numeric(time_s, errors="coerce")
    v = pd.to_numeric(speed_kmh, errors="coerce")

    data = pd.DataFrame({"t": t, "v": v}).replace([np.inf, -np.inf], np.nan).dropna()

    if len(data) < 2:
        return {
            "value": None,
            "reason": "Dati velocità insufficienti.",
        }

    data = data.sort_values("t").drop_duplicates(subset=["t"], keep="first")

    if len(data) < 2:
        return {
            "value": None,
            "reason": "Timestamp insufficienti o duplicati.",
        }

    v_min = float(data["v"].min())
    v_max = float(data["v"].max())

    if v_max < upper_kmh:
        return {
            "value": None,
            "reason": f"Velocità massima insufficiente: {v_max:.1f} km/h < {upper_kmh:.0f} km/h.",
        }

    if lower_kmh <= 0.0 and v_min > 3.0:
        return {
            "value": None,
            "reason": f"La sessione non parte da fermo: velocità minima {v_min:.1f} km/h.",
        }

    if lower_kmh > 0.0 and v_min > lower_kmh:
        return {
            "value": None,
            "reason": f"La sessione non contiene il passaggio da {lower_kmh:.0f} km/h.",
        }

    value = _best_accel_time(time_s, speed_kmh, lower_kmh, upper_kmh)

    if value is None:
        return {
            "value": None,
            "reason": "Transizione crescente non trovata nella sessione.",
        }

    return {
        "value": value,
        "reason": "OK",
    }

def _crossing_time(
    t0: float,
    v0: float,
    t1: float,
    v1: float,
    target: float,
) -> float | None:
    if not all(math.isfinite(x) for x in [t0, v0, t1, v1, target]):
        return None

    if t1 <= t0:
        return None

    if v1 == v0:
        return None

    alpha = (target - v0) / (v1 - v0)

    if alpha < 0.0 or alpha > 1.0:
        return None

    return float(t0 + alpha * (t1 - t0))

def compute_performance_metrics(
    df: pd.DataFrame,
    *,
    rpm_threshold: float = 6000.0,
    lat_acc_threshold_g: float = 0.3,
    throttle_threshold_pct: float = 80.0,
) -> dict:
    """
    Compute MVP single-session performance metrics.

    The function is defensive: missing columns, NaN values and short sessions
    produce None values instead of exceptions.
    """
    metrics: dict = {
        "accel_0_50_s": None,
        "accel_0_100_s": None,
        "accel_80_120_s": None,
        "best_braking_g": None,
        "best_braking_time_s": None,
        "best_braking_speed_kmh": None,
        "max_abs_lat_acc_g": None,
        "max_abs_lat_acc_time_s": None,
        "max_speed_kmh": None,
        "max_speed_time_s": None,
        "max_rpm": None,
        "max_rpm_time_s": None,
        "max_throttle_pct": None,
        "max_throttle_time_s": None,
        "max_load_pct": None,
        "max_load_time_s": None,
        "time_abs_lat_acc_gt_threshold_s": None,
        "time_throttle_gt_threshold_s": None,
        "time_rpm_gt_threshold_s": None,
        "thresholds": {
            "lat_acc_threshold_g": float(lat_acc_threshold_g),
            "throttle_threshold_pct": float(throttle_threshold_pct),
            "rpm_threshold": float(rpm_threshold),
        },
        "friction_circle_sample_count": 0,
    }

    if df.empty or "time_s" not in df.columns:
        return metrics

    time_s = _num(df, "time_s")
    if time_s.dropna().empty:
        return metrics

    speed = _num(df, "speed_obd_kmh")
    accel_0_50 = _best_accel_time_with_reason(time_s, speed, 0.0, 50.0)
    accel_0_100 = _best_accel_time_with_reason(time_s, speed, 0.0, 100.0)
    accel_80_120 = _best_accel_time_with_reason(time_s, speed, 80.0, 120.0)

    metrics["accel_0_50_s"] = accel_0_50["value"]
    metrics["accel_0_50_reason"] = accel_0_50["reason"]

    metrics["accel_0_100_s"] = accel_0_100["value"]
    metrics["accel_0_100_reason"] = accel_0_100["reason"]

    metrics["accel_80_120_s"] = accel_80_120["value"]
    metrics["accel_80_120_reason"] = accel_80_120["reason"]

    acc_lon_g = _preferred_col(df, ["acc_lon_G_filt", "acc_lon_G"])
    acc_lat_g = _preferred_col(df, ["acc_lat_G_filt", "acc_lat_G"])

    braking = _min_with_time(df, acc_lon_g)
    if braking is not None:
        idx, value = braking
        metrics["best_braking_g"] = value
        metrics["best_braking_time_s"] = _row_float(df, idx, "time_s")
        metrics["best_braking_speed_kmh"] = _row_float(df, idx, "speed_obd_kmh")

    lat = pd.to_numeric(acc_lat_g, errors="coerce") if acc_lat_g is not None else None
    if lat is not None and lat.dropna().shape[0] > 0:
        abs_lat = lat.abs()
        idx = abs_lat.idxmax()
        val = abs_lat.loc[idx]
        if _finite(val):
            metrics["max_abs_lat_acc_g"] = float(val)
            metrics["max_abs_lat_acc_time_s"] = _row_float(df, idx, "time_s")

    for col, value_key, time_key in [
        ("speed_obd_kmh", "max_speed_kmh", "max_speed_time_s"),
        ("rpm", "max_rpm", "max_rpm_time_s"),
        ("throttle_pct", "max_throttle_pct", "max_throttle_time_s"),
        ("load_pct", "max_load_pct", "max_load_time_s"),
    ]:
        found = _max_with_time(df, df[col] if col in df.columns else None)
        if found is not None:
            idx, value = found
            metrics[value_key] = value
            metrics[time_key] = _row_float(df, idx, "time_s")

    dt = _duration_per_row(df)

    if acc_lat_g is not None:
        abs_lat = pd.to_numeric(acc_lat_g, errors="coerce").abs()
        metrics["time_abs_lat_acc_gt_threshold_s"] = _time_where(
            dt,
            abs_lat > float(lat_acc_threshold_g),
        )

    if "throttle_pct" in df.columns:
        throttle = _num(df, "throttle_pct")
        metrics["time_throttle_gt_threshold_s"] = _time_where(
            dt,
            throttle > float(throttle_threshold_pct),
        )

    if "rpm" in df.columns:
        rpm = _num(df, "rpm")
        metrics["time_rpm_gt_threshold_s"] = _time_where(
            dt,
            rpm > float(rpm_threshold),
        )

    if acc_lon_g is not None and acc_lat_g is not None:
        lon = pd.to_numeric(acc_lon_g, errors="coerce")
        lat = pd.to_numeric(acc_lat_g, errors="coerce")
        valid = np.isfinite(lon) & np.isfinite(lat)
        metrics["friction_circle_sample_count"] = int(valid.sum())

    return metrics


def build_friction_circle_figure(df: pd.DataFrame) -> go.Figure:
    """
    Build a friction-circle-like scatter plot.

    X axis: lateral acceleration [G]
    Y axis: longitudinal acceleration [G]
    Color: speed_obd_kmh if available.
    """
    fig = go.Figure()

    acc_lon = _preferred_col(df, ["acc_lon_G_filt", "acc_lon_G"])
    acc_lat = _preferred_col(df, ["acc_lat_G_filt", "acc_lat_G"])

    if acc_lon is None or acc_lat is None:
        fig.update_layout(
            template="plotly_dark",
            title="Friction circle non disponibile",
            annotations=[
                dict(
                    text="Mancano acc_lon_G/acc_lat_G.",
                    x=0.5,
                    y=0.5,
                    xref="paper",
                    yref="paper",
                    showarrow=False,
                )
            ],
        )
        return fig

    x = pd.to_numeric(acc_lat, errors="coerce")
    y = pd.to_numeric(acc_lon, errors="coerce")

    valid = np.isfinite(x) & np.isfinite(y)
    if valid.sum() == 0:
        fig.update_layout(
            template="plotly_dark",
            title="Friction circle non disponibile",
            annotations=[
                dict(
                    text="Nessun campione accelerometrico valido.",
                    x=0.5,
                    y=0.5,
                    xref="paper",
                    yref="paper",
                    showarrow=False,
                )
            ],
        )
        return fig

    marker_kwargs = {
        "size": 5,
        "opacity": 0.65,
    }

    if "speed_obd_kmh" in df.columns:
        speed = pd.to_numeric(df["speed_obd_kmh"], errors="coerce")
        marker_kwargs["color"] = speed.loc[valid]
        marker_kwargs["colorscale"] = "Turbo"
        marker_kwargs["showscale"] = True
        marker_kwargs["colorbar"] = {
            "title": {"text": "km/h", "side": "top"},
            "x": 1.03,
            "y": 0.46,
            "len": 0.72,
            "thickness": 18,
        }

    fig.add_trace(
        go.Scattergl(
            x=x.loc[valid],
            y=y.loc[valid],
            mode="markers",
            marker=marker_kwargs,
            name="Campioni",
            showlegend=False,
        )
    )

    # Reference circles at 0.3g, 0.6g, 1.0g.
    theta = np.linspace(0, 2 * np.pi, 240)
    for r in [0.3, 0.6, 1.0]:
        fig.add_trace(
            go.Scatter(
                x=r * np.cos(theta),
                y=r * np.sin(theta),
                mode="lines",
                line={"width": 1, "dash": "dot"},
                name=f"{r:.1f} g",
                hoverinfo="skip",
            )
        )

    fig.update_layout(
        template="plotly_dark",
        title="Friction circle",
        xaxis_title="Accelerazione laterale [G]",
        yaxis_title="Accelerazione longitudinale [G]",
        height=620,
        legend_title="Riferimenti",
        margin={"l": 20, "r": 20, "t": 60, "b": 20},
    )

    fig.update_xaxes(
        zeroline=True,
        scaleanchor="y",
        scaleratio=1,
        gridcolor="#2a2a2e",
    )
    fig.update_yaxes(
        zeroline=True,
        gridcolor="#2a2a2e",
    )

    return fig