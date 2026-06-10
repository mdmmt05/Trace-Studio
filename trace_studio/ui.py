"""
ui.py – Reusable Streamlit rendering components for Trace Studio.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

from trace_studio.charts import (
    build_time_series_figure,
    get_available_plot_channels,
    get_nearest_sample,
)
from trace_studio.config import APP_TAGLINE, DEFAULT_APP_TITLE, MAX_PREVIEW_ROWS
from trace_studio.schema import COLUMN_DESCRIPTIONS, COLUMN_UNITS
from trace_studio.theme import CHANNEL_TOOLTIPS
from trace_studio import cursor as cursor_utils
from trace_studio.map_view import (
    build_trace_map,
    get_available_map_color_channels,
    get_nearest_position_sample,
    get_valid_path_points,
    extract_clicked_latlon,
    get_nearest_position_sample_by_latlon,
)
from trace_studio.performance import (
    build_friction_circle_figure,
    compute_performance_metrics,
)


# ── Header ────────────────────────────────────────────────────────────────────

def render_header() -> None:
    """Render the Trace Studio branded header."""
    st.markdown(
        f"""
        <div class="trace-hero">
            <div class="trace-kicker">TRACE · STUDIO</div>
            <div class="trace-title">{DEFAULT_APP_TITLE}</div>
            <div class="trace-subtitle">{APP_TAGLINE}. Analisi locale di CSV Trace con dashboard, grafici sincronizzati, mappa GNSS raw e performance single-session.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ── Validation report ─────────────────────────────────────────────────────────

def render_validation_report(report: dict) -> None:
    """Show a clean column validation result in the UI."""
    if report["ok"]:
        st.success(f"Schema CSV valido: {len(report['present'])} colonne attese trovate.")
    else:
        missing = ", ".join(report.get("missing", []))
        st.error(f"Schema CSV non valido. Colonne obbligatorie mancanti: {missing}.")

    if report.get("extra"):
        with st.expander(f"Colonne extra rilevate ({len(report['extra'])})", expanded=False):
            st.write(", ".join(report["extra"]))

# ── Dashboard (Phase 3) ───────────────────────────────────────────────────────

def render_dashboard(df: pd.DataFrame, metrics: dict, warnings: list, file_name: str) -> None:
    """Render the synthetic overview dashboard with metrics and warnings."""
    st.subheader("Sintesi sessione")

    # Metric cards in rows
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Campioni", f"{metrics.get('sample_count', 0):,}")
    with col2:
        dur = metrics.get("duration_s")
        if dur:
            minutes = int(dur // 60)
            seconds = int(dur % 60)
            dur_str = f"{minutes:02d}:{seconds:02d}" if minutes else f"{seconds} s"
        else:
            dur_str = "—"
        st.metric("Durata", dur_str)
    with col3:
        st.metric("Frequenza media", _fmt(metrics.get("mean_sample_rate_hz"), 1, " Hz"))
    with col4:
        st.metric("Distanza (OBD)", _fmt(metrics.get("distance_from_speed_m"), 1, " m"))

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Velocità max", _fmt(metrics.get("max_speed_kmh"), 1, " km/h"))
    with col2:
        st.metric("RPM max", _fmt(metrics.get("max_rpm"), 0))
    with col3:
        st.metric("Throttle max", _fmt(metrics.get("max_throttle_pct"), 1, " %"))
    with col4:
        st.metric("Carico motore max", _fmt(metrics.get("max_load_pct"), 1, " %"))

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Acc lon max", _fmt(metrics.get("max_acc_lon_G"), 3, " G"))
    with col2:
        st.metric("Acc lon min", _fmt(metrics.get("min_acc_lon_G"), 3, " G"))
    with col3:
        st.metric("|Acc lat| max", _fmt(metrics.get("max_abs_acc_lat_G"), 3, " G"))
    with col4:
        st.metric("Altitudine (min/max)", f"{_fmt(metrics.get('min_alt_m'), 0, ' m')} / {_fmt(metrics.get('max_alt_m'), 0, ' m')}")

    col1, col2 = st.columns(2)
    with col1:
        gear_min = metrics.get("min_estimated_gear")
        gear_max = metrics.get("max_estimated_gear")
        gear_str = f"{_fmt(gear_min, 0)} – {_fmt(gear_max, 0)}" if gear_min is not None and gear_max is not None else "—"
        st.metric("Marcia stimata (min/max)", gear_str)
    with col2:
        st.metric("Inizio sessione", metrics.get("start_utc_label") or "—")
        st.metric("Fine sessione", metrics.get("end_utc_label") or "—")

    # Warning panel
    if warnings:
        with st.expander("⚠️ Warning tecnici", expanded=False):
            for w in warnings:
                if w["level"] == "error":
                    st.error(f"**{w['title']}**\n\n{w['detail']}")
                elif w["level"] == "warning":
                    st.warning(f"**{w['title']}**\n\n{w['detail']}")
                else:
                    st.info(f"**{w['title']}**\n\n{w['detail']}")

# ── Charts tab (Phase 4) ──────────────────────────────────────────────────────

def render_charts_tab(df: pd.DataFrame) -> None:
    """Render synchronized charts: channel selector, cursor slider, plot, values panel."""
    st.subheader("Grafici sincronizzati")

    tmin, tmax = cursor_utils.get_valid_time_range(df)
    if tmin is None or tmax is None:
        st.error("Nessun dato temporale valido (time_s). Impossibile visualizzare i grafici.")
        return

    cursor_time = cursor_utils.get_cursor_time(df, default_midpoint=True)
    if cursor_time is None:
        st.error("Impossibile determinare il cursore temporale.")
        return

    if tmin == tmax:
        st.warning("La sessione contiene un solo istante temporale valido. Il cursore non è interattivo.")
    else:
        new_cursor = st.slider(
            "Cursore temporale grafici",
            min_value=float(tmin),
            max_value=float(tmax),
            value=float(cursor_time),
            step=max((float(tmax) - float(tmin)) / 1000.0, 0.001),
            format="%.2f s",
        )

        if abs(float(new_cursor) - float(cursor_time)) > 1e-6:
            cursor_time = cursor_utils.set_cursor_time(df, new_cursor)
            if cursor_time is None:
                st.error("Errore durante l'aggiornamento del cursore.")
                return
            st.rerun()

    available = get_available_plot_channels(df)
    if not available:
        st.warning("Nessun canale plottabile trovato nel DataFrame.")
        return

    # Costruisci default: speed, rpm, throttle, e le versioni filtrate di acc se disponibili, altrimenti raw
    default_ids = []
    # Velocità
    if any(ch["id"] == "speed_obd_kmh" for ch in available):
        default_ids.append("speed_obd_kmh")
    # RPM
    if any(ch["id"] == "rpm" for ch in available):
        default_ids.append("rpm")
    # Throttle
    if any(ch["id"] == "throttle_pct" for ch in available):
        default_ids.append("throttle_pct")
    # Accelerazione longitudinale: preferisci filtrata
    if any(ch["id"] == "acc_lon_G_filt" for ch in available):
        default_ids.append("acc_lon_G_filt")
    elif any(ch["id"] == "acc_lon_G" for ch in available):
        default_ids.append("acc_lon_G")
    # Accelerazione laterale: preferisci filtrata
    if any(ch["id"] == "acc_lat_G_filt" for ch in available):
        default_ids.append("acc_lat_G_filt")
    elif any(ch["id"] == "acc_lat_G" for ch in available):
        default_ids.append("acc_lat_G")

    selected_ids = st.multiselect(
        "Canali da visualizzare",
        options=[ch["id"] for ch in available],
        format_func=lambda x: next((ch["label"] for ch in available if ch["id"] == x), x),
        default=default_ids,
        help="Seleziona uno o più canali. Passa dal pannello tooltip sotto per il significato dei canali principali.",
    )

    if not selected_ids:
        st.info("Seleziona almeno un canale per visualizzare il grafico.")
        return

    _render_selected_channel_tooltips(selected_ids)

    fig = build_time_series_figure(df, selected_ids, cursor_time)

    if fig.data:
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("Nessuna traccia generata per i canali selezionati.")

    nearest = cursor_utils.get_cursor_row(df, cursor_time)
    if nearest is not None:
        render_cursor_values(nearest, cursor_time)

def render_map_tab(df: pd.DataFrame) -> None:
    """Render the interactive map tab with colored raw-GNSS track."""
    st.subheader("Mappa del percorso")
    st.caption("Percorso GNSS raw: nessuna correzione su strada, nessun map matching.")
    st.info("Clicca sulla mappa per spostare il cursore al campione GNSS più vicino.")

    valid_pts = get_valid_path_points(df)

    col_a, col_b = st.columns(2)
    with col_a:
        st.metric("Punti GNSS validi", f"{len(valid_pts):,}")
    with col_b:
        st.metric("Punti totali", f"{len(df):,}")

    tmin, tmax = cursor_utils.get_valid_time_range(df)
    cursor_time = cursor_utils.get_cursor_time(df, default_midpoint=True)

    if cursor_time is not None:
        st.caption(f"Cursore attuale: **t = {cursor_time:.2f} s**")
    else:
        st.warning("Nessun dato temporale valido per il cursore.")

    available = get_available_map_color_channels(df)

    if not available:
        st.warning("Nessun canale disponibile per colorare la mappa.")
        selected_channel = "speed_obd_kmh"
    else:
        default_channel = (
            "speed_obd_kmh"
            if any(ch["id"] == "speed_obd_kmh" for ch in available)
            else available[0]["id"]
        )

        selected_channel = st.selectbox(
            "Canale colore",
            options=[ch["id"] for ch in available],
            format_func=lambda x: next((ch["label"] for ch in available if ch["id"] == x), x),
            index=[ch["id"] for ch in available].index(default_channel),
            key="map_color_channel",
        )

    if cursor_time is not None and tmin is not None and tmax is not None:
        if tmin == tmax:
            st.warning("La sessione contiene un solo istante temporale valido. Il cursore non è interattivo.")
        else:
            new_cursor = st.slider(
                "Cursore temporale mappa",
                min_value=float(tmin),
                max_value=float(tmax),
                value=float(cursor_time),
                step=max((float(tmax) - float(tmin)) / 1000.0, 0.001),
                format="%.2f s",
            )

            if abs(float(new_cursor) - float(cursor_time)) > 1e-6:
                cursor_time = cursor_utils.set_cursor_time(df, new_cursor)
                if cursor_time is None:
                    st.error("Errore durante l'aggiornamento del cursore.")
                    return
                st.rerun()

    if valid_pts.empty:
        st.warning("Nessuna posizione GNSS valida. Mostro una mappa di fallback.")
    elif len(valid_pts) < 2:
        st.info("È presente un solo punto GNSS valido: non è possibile tracciare un percorso.")

    try:
        m = build_trace_map(
            df=df,
            color_channel=selected_channel,
            cursor_time_s=cursor_time,
            max_segments=5000,
        )

        map_result = st_folium(
            m,
            width=None,
            height=560,
            returned_objects=["last_clicked", "last_object_clicked"],
            use_container_width=True,
        )
    except Exception as exc:
        st.error(f"Errore durante la generazione della mappa: {exc}")
        return

    click_latlon = extract_clicked_latlon(map_result) if map_result else None

    if click_latlon is not None:
        lat_click, lon_click = click_latlon
        nearest_row = get_nearest_position_sample_by_latlon(df, lat_click, lon_click)

        if nearest_row is not None and "time_s" in nearest_row.index and pd.notna(nearest_row["time_s"]):
            new_time = float(nearest_row["time_s"])
            current_time = cursor_utils.get_cursor_time(df, default_midpoint=False)

            if current_time is None or abs(new_time - float(current_time)) > 1e-6:
                cursor_utils.set_cursor_time(df, new_time)
                st.info(f"Cursore aggiornato dal click mappa: t = {new_time:.2f} s")
                st.rerun()

    cursor_time = cursor_utils.get_cursor_time(df, default_midpoint=False)

    if cursor_time is not None:
        nearest = get_nearest_position_sample(df, cursor_time)

        if nearest is not None:
            st.markdown("#### Posizione al cursore")

            cols = st.columns(4)

            with cols[0]:
                if "lat" in nearest.index and pd.notna(nearest["lat"]):
                    st.metric("Latitudine", f"{float(nearest['lat']):.6f}")
                if "lon" in nearest.index and pd.notna(nearest["lon"]):
                    st.metric("Longitudine", f"{float(nearest['lon']):.6f}")

            with cols[1]:
                if "speed_obd_kmh" in nearest.index and pd.notna(nearest["speed_obd_kmh"]):
                    st.metric("Velocità OBD", f"{float(nearest['speed_obd_kmh']):.1f} km/h")
                if "rpm" in nearest.index and pd.notna(nearest["rpm"]):
                    st.metric("RPM", f"{float(nearest['rpm']):.0f}")

            with cols[2]:
                if "throttle_pct" in nearest.index and pd.notna(nearest["throttle_pct"]):
                    st.metric("Throttle", f"{float(nearest['throttle_pct']):.1f} %")
                if "estimated_gear" in nearest.index and pd.notna(nearest["estimated_gear"]):
                    st.metric("Marcia", f"{int(round(float(nearest['estimated_gear'])))}")

            with cols[3]:
                if "acc_lon_G" in nearest.index and pd.notna(nearest["acc_lon_G"]):
                    st.metric("Acc lon", f"{float(nearest['acc_lon_G']):.3f} G")
                if "acc_lat_G" in nearest.index and pd.notna(nearest["acc_lat_G"]):
                    st.metric("Acc lat", f"{float(nearest['acc_lat_G']):.3f} G")

    st.caption("Il percorso mostrato usa coordinate GNSS raw e può non coincidere perfettamente con la strada reale.")

def render_performance_tab(df: pd.DataFrame) -> None:
    """Render single-session performance analysis."""
    st.subheader("Performance")
    st.caption("Metriche prestazionali della singola registrazione. Nessun confronto tra run.")

    with st.expander("Soglie", expanded=False):
        st.caption("Le soglie controllano solo il calcolo del tempo sopra soglia. Non modificano il CSV.")
        col1, col2, col3 = st.columns(3)
        with col1:
            lat_acc_threshold = st.slider(
                "Soglia accelerazione laterale [G]",
                min_value=0.0,
                max_value=2.0,
                value=0.3,
                step=0.05,
                help="Tempo trascorso con accelerazione laterale assoluta superiore a questa soglia.",
            )
        with col2:
            throttle_threshold = st.slider(
                "Soglia throttle [%]",
                min_value=0.0,
                max_value=100.0,
                value=80.0,
                step=5.0,
                help="Tempo trascorso con throttle superiore a questa soglia.",
            )
        with col3:
            rpm_threshold = st.slider(
                "Soglia RPM",
                min_value=0.0,
                max_value=20000.0,
                value=6000.0,
                step=250.0,
                help="Tempo trascorso con RPM superiori a questa soglia.",
            )

    perf = compute_performance_metrics(
        df,
        rpm_threshold=rpm_threshold,
        lat_acc_threshold_g=lat_acc_threshold,
        throttle_threshold_pct=throttle_threshold,
    )

    st.markdown("### Accelerazione")

    c1, c2, c3 = st.columns(3)
    
    with c1:
        st.metric("0–50 km/h", _fmt(perf.get("accel_0_50_s"), 2, " s"))
        if perf.get("accel_0_50_s") is None:
            st.caption(perf.get("accel_0_50_reason", "Non disponibile."))
    
    with c2:
        st.metric("0–100 km/h", _fmt(perf.get("accel_0_100_s"), 2, " s"))
        if perf.get("accel_0_100_s") is None:
            st.caption(perf.get("accel_0_100_reason", "Non disponibile."))
    
    with c3:
        st.metric("80–120 km/h", _fmt(perf.get("accel_80_120_s"), 2, " s"))
        if perf.get("accel_80_120_s") is None:
            st.caption(perf.get("accel_80_120_reason", "Non disponibile."))

    st.markdown("### Massimi sessione")

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Velocità max", _fmt(perf.get("max_speed_kmh"), 1, " km/h"))
    with c2:
        st.metric("RPM max", _fmt(perf.get("max_rpm"), 0))
    with c3:
        st.metric("Throttle max", _fmt(perf.get("max_throttle_pct"), 1, " %"))
    with c4:
        st.metric("Load max", _fmt(perf.get("max_load_pct"), 1, " %"))

    st.markdown("### Dinamica veicolo")

    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric(
            "Frenata più intensa",
            _fmt(perf.get("best_braking_g"), 3, " G"),
            help="Valore minimo di acc_lon_G_filt se disponibile, altrimenti acc_lon_G.",
        )
    with c2:
        st.metric(
            "|Acc laterale| max",
            _fmt(perf.get("max_abs_lat_acc_g"), 3, " G"),
            help="Valore massimo assoluto di acc_lat_G_filt se disponibile, altrimenti acc_lat_G.",
        )
    with c3:
        st.metric(
            "Campioni friction circle",
            f"{perf.get('friction_circle_sample_count', 0):,}",
        )

    st.markdown("### Tempo sopra soglia")

    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric(
            f"|Acc lat| > {lat_acc_threshold:.2f} G",
            _fmt(perf.get("time_abs_lat_acc_gt_threshold_s"), 2, " s"),
        )
    with c2:
        st.metric(
            f"Throttle > {throttle_threshold:.0f} %",
            _fmt(perf.get("time_throttle_gt_threshold_s"), 2, " s"),
        )
    with c3:
        st.metric(
            f"RPM > {rpm_threshold:.0f}",
            _fmt(perf.get("time_rpm_gt_threshold_s"), 2, " s"),
        )

    st.markdown("### Friction circle")
    st.caption(
        "Asse X = accelerazione laterale. Asse Y = accelerazione longitudinale. "
        "I cerchi tratteggiati sono riferimenti a 0.3 g, 0.6 g e 1.0 g."
    )

    fig = build_friction_circle_figure(df)
    st.plotly_chart(fig, use_container_width=True)

    with st.expander("Dettaglio numerico", expanded=False):
        rows = []
        labels = {
            "accel_0_50_s": "0–50 km/h [s]",
            "accel_0_100_s": "0–100 km/h [s]",
            "accel_80_120_s": "80–120 km/h [s]",
            "best_braking_g": "Frenata più intensa [G]",
            "best_braking_time_s": "Tempo frenata più intensa [s]",
            "best_braking_speed_kmh": "Velocità alla frenata più intensa [km/h]",
            "max_abs_lat_acc_g": "|Acc laterale| max [G]",
            "max_abs_lat_acc_time_s": "Tempo |acc laterale| max [s]",
            "max_speed_kmh": "Velocità max [km/h]",
            "max_speed_time_s": "Tempo velocità max [s]",
            "max_rpm": "RPM max",
            "max_rpm_time_s": "Tempo RPM max [s]",
            "max_throttle_pct": "Throttle max [%]",
            "max_throttle_time_s": "Tempo throttle max [s]",
            "max_load_pct": "Load max [%]",
            "max_load_time_s": "Tempo load max [s]",
            "time_abs_lat_acc_gt_threshold_s": "Tempo sopra soglia acc laterale [s]",
            "time_throttle_gt_threshold_s": "Tempo sopra soglia throttle [s]",
            "time_rpm_gt_threshold_s": "Tempo sopra soglia RPM [s]",
        }

        for key, label in labels.items():
            value = perf.get(key)
            rows.append(
                {
                    "Metrica": label,
                    "Valore": _fmt(value, 3) if isinstance(value, float) else (value if value is not None else "—"),
                }
            )

        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)

    st.caption(
        "Le metriche sono calcolate sulla singola sessione. I valori dipendono dalla qualità di OBD, IMU, GNSS e timestamp."
    )

def render_cursor_values(row: pd.Series, cursor_time: float) -> None:
    """Show a compact table of main channels at the nearest sample."""
    st.markdown(f"### Valori al cursore (t = {cursor_time:.3f} s)")

    # Canali principali da mostrare (inclusi derivati Phase 7)
    key_channels = [
        "timestamp_utc_str", "lat", "lon",
        "speed_obd_kmh", "rpm", "throttle_pct", "load_pct",
        "acc_lon_G", "acc_lat_G", "roll_deg", "pitch_deg",
        "slope_deg", "heading_deg", "yawRate_dps", "estimated_gear",
        "distance_m", "acc_lon_G_filt", "acc_lat_G_filt",
        "jerk_lon_mps3", "jerk_lat_mps3", "curvature_1pm", "curve_radius_m"
    ]

    data = []
    for ch in key_channels:
        if ch in row.index:
            val = row[ch]
            if pd.isna(val):
                val_str = "NaN"
            elif isinstance(val, float):
                if ch in ["lat", "lon"]:
                    val_str = f"{val:.6f}"
                elif "acc" in ch or "slope" in ch or "heading" in ch or "curvature" in ch:
                    val_str = f"{val:.3f}"
                elif "jerk" in ch:
                    val_str = f"{val:.2f}"
                elif "distance" in ch:
                    val_str = f"{val:.1f}"
                elif "rpm" in ch or "estimated_gear" in ch:
                    val_str = f"{int(val)}"
                else:
                    val_str = f"{val:.2f}"
            else:
                val_str = str(val)
            unit = COLUMN_UNITS.get(ch, "")
            label = ch.replace("_", " ").title()
            if unit:
                label += f" [{unit}]"
            data.append({"Grandezza": label, "Valore": val_str})

    if data:
        df_val = pd.DataFrame(data)
        st.dataframe(df_val, hide_index=True, use_container_width=True)
    else:
        st.info("Nessun valore disponibile.")


def _render_selected_channel_tooltips(selected_ids: list[str]) -> None:
    """Show concise explanations for selected analysis channels."""
    rows = []
    for channel in selected_ids:
        tip = CHANNEL_TOOLTIPS.get(channel)
        if tip:
            rows.append({"Canale": channel, "Nota": tip})

    if not rows:
        return

    with st.expander("Tooltip canali selezionati", expanded=False):
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)

# ── Data preview ──────────────────────────────────────────────────────────────

def render_dataframe_preview(df: pd.DataFrame) -> None:
    """Show the first MAX_PREVIEW_ROWS rows of *df*."""
    n = min(MAX_PREVIEW_ROWS, len(df))
    st.caption(f"Prime {n} righe su {len(df):,}.")
    st.dataframe(df.head(n), width="stretch")


# ── Column catalogue ──────────────────────────────────────────────────────────

def render_column_catalogue(df: pd.DataFrame) -> None:
    """Show a table of columns present in *df* with their unit and description."""
    rows = []
    for col in df.columns:
        rows.append(
            {
                "Colonna": col,
                "Unità": COLUMN_UNITS.get(col, "?"),
                "Descrizione": COLUMN_DESCRIPTIONS.get(col, ""),
                "Tooltip": CHANNEL_TOOLTIPS.get(col, ""),
                "Non-null": int(df[col].notna().sum()),
                # str() converts pandas ExtensionDtype objects (e.g. StringDtype)
                # to plain strings; without this PyArrow raises ArrowInvalid.
                "Dtype": str(df[col].dtype),
            }
        )
    catalogue = pd.DataFrame(rows)
    # Belt-and-suspenders: cast every object column to str so PyArrow
    # never encounters a raw dtype object in the Arrow serialisation path.
    for c in catalogue.select_dtypes(include="object").columns:
        catalogue[c] = catalogue[c].astype(str)
    st.dataframe(catalogue, width="stretch", hide_index=True)

# ── Helper ────────────────────────────────────────────────────────────────────

def _fmt(value: float | None, decimals: int = 1, suffix: str = "") -> str:
    """Format a numeric metric value for display."""
    if value is None:
        return "—"

    try:
        value_f = float(value)
    except Exception:
        return str(value)

    if pd.isna(value_f):
        return "—"

    return f"{value_f:,.{decimals}f}{suffix}"