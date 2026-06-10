"""
theme.py - Minimal Trace Studio visual polish.

This module contains only UI styling helpers. It does not touch data processing,
charts, map logic or performance calculations.
"""

from __future__ import annotations

import streamlit as st

TRACE_ACCENT = "#c8aa7a"
TRACE_ACCENT_SOFT = "#e8cfa0"
TRACE_BG = "#0a0a0c"
TRACE_PANEL = "#111115"
TRACE_PANEL_2 = "#18181e"
TRACE_TEXT = "#e8e4dc"
TRACE_MUTED = "#9a9490"
TRACE_BORDER = "rgba(255,255,255,0.10)"
TRACE_OK = "#7ac8a0"
TRACE_WARN = "#d0a85c"
TRACE_ERR = "#c87a7a"


CHANNEL_TOOLTIPS: dict[str, str] = {
    "speed_obd_kmh": "Velocità letta via OBD-II. È il riferimento principale per prestazioni e distanza integrata.",
    "rpm": "Regime motore da OBD-II. Utile per analisi motore, cambiate e soglie di utilizzo.",
    "throttle_pct": "Apertura farfalla da OBD-II. Aiuta a distinguere richiesta pilota da risposta veicolo.",
    "load_pct": "Carico motore OBD-II. Dipende dal veicolo e dalla ECU; va interpretato come indicatore relativo.",
    "acc_lon_G": "Accelerazione longitudinale raw in G. Positiva in accelerazione, negativa in frenata.",
    "acc_lon_G_filt": "Accelerazione longitudinale filtrata. Preferibile per lettura grafici e metriche prestazionali.",
    "acc_lat_G": "Accelerazione laterale raw in G. Il segno dipende dalla convenzione assi IMU del firmware.",
    "acc_lat_G_filt": "Accelerazione laterale filtrata. Preferibile per analisi curva e friction circle.",
    "jerk_lon_mps3": "Derivata temporale dell'accelerazione longitudinale filtrata. Evidenzia transitori bruschi.",
    "jerk_lat_mps3": "Derivata temporale dell'accelerazione laterale filtrata. Evidenzia ingressi curva e correzioni rapide.",
    "distance_m": "Distanza cumulativa canonica: GNSS se plausibile, altrimenti integrazione velocità.",
    "curvature_1pm": "Curvatura approssimata da yaw rate o heading. Non è map-matched e non corregge la strada reale.",
    "curve_radius_m": "Raggio curva approssimato dalla curvatura. Valori molto grandi o rettilinei sono riportati come NaN.",
    "heading_deg": "Direzione veicolo/fusione sensori. 0° corrisponde al Nord.",
    "yawRate_dps": "Velocità di imbardata in gradi al secondo. Utile per curvatura e dinamica laterale.",
    "slope_deg": "Pendenza longitudinale stimata dall'IMU. Affidabilità legata a slope_confidence.",
    "estimated_gear": "Marcia stimata dal rapporto RPM/velocità. Richiede calibrazione sensata per essere affidabile.",
}


def apply_trace_theme() -> None:
    """Inject minimal CSS for a polished dark motorsport UI."""
    st.markdown(
        f"""
        <style>
        :root {{
            --trace-bg: {TRACE_BG};
            --trace-panel: {TRACE_PANEL};
            --trace-panel-2: {TRACE_PANEL_2};
            --trace-accent: {TRACE_ACCENT};
            --trace-accent-soft: {TRACE_ACCENT_SOFT};
            --trace-text: {TRACE_TEXT};
            --trace-muted: {TRACE_MUTED};
            --trace-border: {TRACE_BORDER};
            --trace-ok: {TRACE_OK};
            --trace-warn: {TRACE_WARN};
            --trace-err: {TRACE_ERR};
        }}

        html, body, [data-testid="stAppViewContainer"] {{
            background:
                radial-gradient(circle at top left, rgba(200,170,122,0.08), transparent 32rem),
                linear-gradient(180deg, #0a0a0c 0%, #08080a 100%) !important;
            color: var(--trace-text);
        }}

        [data-testid="stSidebar"] {{
            background: linear-gradient(180deg, #0b0b0e 0%, #111115 100%) !important;
            border-right: 1px solid var(--trace-border);
        }}

        .block-container {{
            padding-top: 4.25rem !important;
            padding-bottom: 3rem;
            max-width: 1540px;
        }}

        h1, h2, h3 {{
            letter-spacing: -0.025em;
        }}

        h1 {{
            font-weight: 760 !important;
        }}

        div[data-testid="stMetric"] {{
            background: linear-gradient(180deg, rgba(255,255,255,0.035), rgba(255,255,255,0.015));
            border: 1px solid var(--trace-border);
            border-radius: 16px;
            padding: 1rem 1.05rem;
            box-shadow: 0 10px 28px rgba(0,0,0,0.24);
        }}

        div[data-testid="stMetricLabel"] p {{
            color: var(--trace-muted) !important;
            font-size: 0.78rem !important;
            letter-spacing: 0.04em;
            text-transform: uppercase;
        }}

        div[data-testid="stMetricValue"] {{
            color: var(--trace-text) !important;
            font-weight: 650;
        }}

        div[data-testid="stTabs"] [role="tablist"] {{
            gap: 0.35rem;
            padding-bottom: 0.65rem;
        }}

        div[data-testid="stTabs"] button {{
            border-radius: 999px !important;
            padding: 0.45rem 0.95rem !important;
            margin-bottom: 0.35rem !important;
        }}

        div[data-testid="stTabs"] button[aria-selected="true"] {{
            color: #0a0a0c !important;
            background: var(--trace-accent) !important;
        }}

        div[data-testid="stAlert"] {{
            border-radius: 14px;
            border: 1px solid var(--trace-border);
        }}

        .trace-hero {{
            position: relative;
            padding: 1.25rem 1.35rem;
            border: 1px solid var(--trace-border);
            border-radius: 22px;
            background:
                linear-gradient(135deg, rgba(200,170,122,0.12), rgba(255,255,255,0.02) 42%, rgba(255,255,255,0.00)),
                #101014;
            box-shadow: 0 18px 50px rgba(0,0,0,0.28);
            margin-top: 0.45rem;
            margin-bottom: 1.15rem;
        }}

        .trace-kicker {{
            color: var(--trace-accent);
            letter-spacing: 0.24em;
            text-transform: uppercase;
            font-size: 0.72rem;
            font-weight: 700;
            margin-bottom: 0.25rem;
        }}

        .trace-title {{
            color: var(--trace-text);
            font-size: clamp(2.0rem, 4vw, 3.2rem);
            line-height: 0.96;
            font-weight: 800;
            margin: 0;
        }}

        .trace-subtitle {{
            color: var(--trace-muted);
            max-width: 780px;
            margin-top: 0.65rem;
            font-size: 0.98rem;
        }}

        .trace-badges {{
            display: flex;
            gap: 0.5rem;
            flex-wrap: wrap;
            margin-top: 1rem;
        }}

        .trace-badge {{
            display: inline-flex;
            align-items: center;
            gap: 0.35rem;
            border: 1px solid rgba(200,170,122,0.28);
            background: rgba(200,170,122,0.08);
            color: var(--trace-accent-soft);
            border-radius: 999px;
            padding: 0.32rem 0.64rem;
            font-size: 0.76rem;
            font-weight: 650;
        }}

        .trace-panel {{
            border: 1px solid var(--trace-border);
            border-radius: 18px;
            background: rgba(17,17,21,0.75);
            padding: 1rem 1.1rem;
            margin: 0.75rem 0 1rem 0;
        }}

        .trace-panel-title {{
            color: var(--trace-accent);
            font-size: 0.78rem;
            font-weight: 720;
            letter-spacing: 0.13em;
            text-transform: uppercase;
            margin-bottom: 0.35rem;
        }}

        .trace-muted {{
            color: var(--trace-muted);
        }}

        .trace-file-pill {{
            display: inline-flex;
            align-items: center;
            gap: 0.45rem;
            padding: 0.42rem 0.7rem;
            border-radius: 999px;
            border: 1px solid var(--trace-border);
            background: rgba(255,255,255,0.035);
            font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
            color: var(--trace-text);
            font-size: 0.84rem;
        }}

        .trace-shortcut-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 0.55rem;
            margin-top: 0.5rem;
        }}

        .trace-shortcut {{
            border: 1px solid var(--trace-border);
            border-radius: 14px;
            background: rgba(255,255,255,0.03);
            padding: 0.68rem 0.78rem;
        }}

        .trace-key {{
            display: inline-block;
            min-width: 2rem;
            text-align: center;
            color: #0a0a0c;
            background: var(--trace-accent);
            border-radius: 8px;
            padding: 0.14rem 0.42rem;
            margin-right: 0.45rem;
            font-weight: 800;
            font-size: 0.78rem;
        }}

        .trace-logo-mark {{
            width: 34px;
            height: 34px;
            border-radius: 12px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            background: var(--trace-accent);
            color: #0a0a0c;
            font-weight: 900;
            letter-spacing: -0.08em;
            margin-right: 0.55rem;
        }}

        div[data-testid="stNumberInput"] div[data-baseweb="input"] {{
            margin-right: 0.45rem !important;
        }}

        div[data-testid="stNumberInput"] button {{
            margin-left: 0.32rem !important;
            border-radius: 999px !important;
        }}

        div[data-testid="stPlotlyChart"] {{
            margin-top: 0.35rem;
        }}

        a {{ color: var(--trace-accent-soft); }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar_brand() -> None:
    """Compact sidebar brand block."""
    st.markdown(
        """
        <div style="margin-bottom:1rem;">
            <div style="display:flex; align-items:center; gap:.6rem;">
                <div class="trace-logo-mark">T</div>
                <div>
                    <div style="font-weight:800; letter-spacing:.02em; color:#e8e4dc;">Trace Studio</div>
                    <div style="font-size:.78rem; color:#9a9490;">Local telemetry analysis</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_shortcuts_reference() -> None:
    """Document MVP shortcuts and fast actions."""
    st.markdown(
        """
        <div class="trace-panel">
            <div class="trace-panel-title">Shortcut</div>
            <div class="trace-shortcut-grid">
                <div class="trace-shortcut"><span class="trace-key">Ctrl+R</span>Ricarica l'app/browser.</div>
                <div class="trace-shortcut"><span class="trace-key">F</span>Carica un CSV dalla sidebar.</div>
                <div class="trace-shortcut"><span class="trace-key">Click</span>Sulla mappa sposta il cursore al GNSS più vicino.</div>
                <div class="trace-shortcut"><span class="trace-key">Drag</span>Sui grafici effettua zoom temporale.</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def clean_exception_message(exc: Exception) -> str:
    """Return a concise user-facing error message."""
    text = str(exc).strip()
    if not text:
        return "Errore non specificato."
    return text.replace("Cannot read CSV file:", "Impossibile leggere il CSV:")
