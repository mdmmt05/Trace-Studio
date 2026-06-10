"""
charts.py – Plotly‑based synchronized time‑series charts.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from trace_studio.schema import COLUMN_UNITS
from trace_studio.theme import CHANNEL_TOOLTIPS

# Lista dei canali principali da mostrare (in ordine consigliato)
DEFAULT_CHANNELS = [
    "speed_obd_kmh",
    "rpm",
    "throttle_pct",
    "acc_lon_G",
    "acc_lat_G",
]

# Tutti i canali supportati per il grafico (inclusi quelli derivati Phase 7)

CHANNEL_LABELS = {
    "speed_obd_kmh": "Velocità OBD",
    "distance_m": "Distanza",
    "distance_km": "Distanza",
    "rpm": "RPM",
    "throttle_pct": "Throttle",
    "load_pct": "Load",
    "acc_lon_G": "Acc. longitudinale",
    "acc_lon_G_filt": "Acc. longitudinale filtrata",
    "acc_lat_G": "Acc. laterale",
    "acc_lat_G_filt": "Acc. laterale filtrata",
    "acc_lon_mps2": "Acc. longitudinale SI",
    "acc_lon_mps2_filt": "Acc. longitudinale SI filtrata",
    "acc_lat_mps2": "Acc. laterale SI",
    "acc_lat_mps2_filt": "Acc. laterale SI filtrata",
    "jerk_lon_mps3": "Jerk longitudinale",
    "jerk_lat_mps3": "Jerk laterale",
    "roll_deg": "Roll",
    "pitch_deg": "Pitch",
    "slope_deg": "Pendenza",
    "heading_deg": "Heading",
    "yawRate_dps": "Yaw rate",
    "curvature_1pm": "Curvatura",
    "abs_curvature_1pm": "Curvatura assoluta",
    "curve_radius_m": "Raggio curva",
    "estimated_gear": "Marcia stimata",
}

ALL_PLOT_CHANNELS = [
    "speed_obd_kmh",
    "distance_m",
    "distance_km",
    "rpm",
    "throttle_pct",
    "load_pct",
    "acc_lon_G",
    "acc_lon_G_filt",
    "acc_lat_G",
    "acc_lat_G_filt",
    "acc_lon_mps2",
    "acc_lon_mps2_filt",
    "acc_lat_mps2",
    "acc_lat_mps2_filt",
    "jerk_lon_mps3",
    "jerk_lat_mps3",
    "roll_deg",
    "pitch_deg",
    "slope_deg",
    "heading_deg",
    "yawRate_dps",
    "curvature_1pm",
    "abs_curvature_1pm",
    "curve_radius_m",
    "estimated_gear",
]


def get_available_plot_channels(df: pd.DataFrame) -> list[dict]:
    """
    Return a list of channels that exist in df and have at least one non‑NaN value.
    Each dict: {"id": col, "label": str, "unit": str}
    """
    available = []
    for col in ALL_PLOT_CHANNELS:
        if col in df.columns and df[col].notna().any():
            unit = COLUMN_UNITS.get(col, "")
            label = CHANNEL_LABELS.get(col, col.replace("_", " ").title())
            if unit:
                label += f" [{unit}]"
            available.append({
                "id": col,
                "label": label,
                "unit": unit,
                "tooltip": CHANNEL_TOOLTIPS.get(col, ""),
            })
    return available


def build_time_series_figure(
    df: pd.DataFrame,
    selected_channels: list[str],
    cursor_time_s: float | None = None,
) -> go.Figure:
    """
    Create a Plotly figure with vertically stacked subplots, one per selected channel.
    Shared x‑axis, unified hover, and an optional vertical line at cursor_time_s.
    """
    if not selected_channels:
        return go.Figure()
    
    if "time_s" not in df.columns or pd.to_numeric(df["time_s"], errors="coerce").dropna().empty:
        return go.Figure()

    n_rows = len(selected_channels)
    vertical_spacing = min(0.11, max(0.055, 0.24 / max(n_rows, 2)))
    fig = make_subplots(
        rows=n_rows,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=vertical_spacing,
        subplot_titles=[_channel_title(df, ch) for ch in selected_channels],
    )

    # Tema scuro coerente con lo Streamlit theme
    dark_bg = "#0a0a0c"
    plot_bg = "#111115"
    text_color = "#e8e4dc"
    accent = "#c8aa7a"

    for i, channel in enumerate(selected_channels, start=1):
        if channel not in df.columns:
            continue
        y = df[channel]
        # Usa Scattergl per prestazioni con molti punti
        trace = go.Scattergl(
            x=df["time_s"],
            y=y,
            mode="lines",
            name=channel,
            line=dict(width=1.5),
            opacity=0.9,
            showlegend=False,
        )
        fig.add_trace(trace, row=i, col=1)

        # Personalizza l'asse y
        fig.update_yaxes(title_text="", row=i, col=1, gridcolor="#2a2a2e", color=text_color)

    # Asse X comune
    fig.update_xaxes(title_text="Tempo (s)", row=n_rows, col=1, gridcolor="#2a2a2e", color=text_color)

    # Layout globale
    fig.update_layout(
        template="plotly_dark",
        hovermode="x unified",
        dragmode="zoom",
        plot_bgcolor=plot_bg,
        paper_bgcolor=dark_bg,
        font=dict(color=text_color, family="sans serif"),
        height=max(380, 320 * n_rows),
        margin=dict(l=58, r=34, t=82, b=58),
        hoverlabel=dict(bgcolor="#2a2a2e", font_size=11),
    )

    # Linea verticale del cursore
    if cursor_time_s is not None:
        fig.add_vline(
            x=cursor_time_s,
            line_width=1.5,
            line_dash="dash",
            line_color=accent,
        )

    return fig


def _channel_title(df: pd.DataFrame, channel: str) -> str:
    """Return a readable title for a channel (e.g. 'Speed OBD [km/h]')."""
    unit = COLUMN_UNITS.get(channel, "")
    base = CHANNEL_LABELS.get(channel, channel.replace("_", " ").title())
    if unit:
        return f"{base}<br><sup>[{unit}]</sup>"
    return base


def get_nearest_sample(df: pd.DataFrame, time_s: float) -> pd.Series | None:
    """
    Return the row (as a Series) with time_s closest to the given value.
    Returns None if df is empty or time_s column missing.
    """
    if df.empty or "time_s" not in df.columns:
        return None
    time_col = df["time_s"].dropna()
    if time_col.empty:
        return None
    idx = (time_col - time_s).abs().idxmin()
    return df.loc[idx]