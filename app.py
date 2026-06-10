"""
app.py - Trace Studio entry point.

Run with:
    streamlit run app.py
"""

from __future__ import annotations

import streamlit as st

from trace_studio.importer import load_trace_csv
from trace_studio.metrics import compute_session_metrics
from trace_studio.processing import normalize_trace_data
from trace_studio.theme import (
    apply_trace_theme,
    clean_exception_message,
    render_sidebar_brand,
    render_shortcuts_reference,
)
from trace_studio.ui import (
    render_column_catalogue,
    render_dataframe_preview,
    render_header,
    render_validation_report,
    render_dashboard,
    render_charts_tab,
    render_map_tab,
    render_performance_tab,
)
from trace_studio.warnings import compute_basic_warnings


st.set_page_config(
    page_title="Trace Studio",
    layout="wide",
    page_icon="🏁",
    initial_sidebar_state="expanded",
)

apply_trace_theme()


@st.cache_data(show_spinner="Caricamento e normalizzazione CSV…")
def _load(file_bytes: bytes, file_name: str):
    """Load and normalise the CSV; cached by raw bytes so re-uploads re-run."""
    import io

    df_raw, report = load_trace_csv(io.BytesIO(file_bytes))
    df_norm = normalize_trace_data(df_raw)
    metrics = compute_session_metrics(df_norm)
    warnings = compute_basic_warnings(df_norm)
    return df_norm, report, metrics, warnings


render_header()

with st.sidebar:
    render_sidebar_brand()
    st.markdown("### Apri sessione")
    uploaded = st.file_uploader(
        "File CSV Trace",
        type=["csv"],
        help="Seleziona un file .csv prodotto dal logger Trace ESP32-S3.",
    )

    st.divider()

    with st.expander("Shortcut e uso rapido", expanded=False):
        st.markdown(
            """
            - **Ctrl+R**: ricarica l'app/browser.
            - **Drag sui grafici**: zoom temporale.
            - **Doppio click sui grafici**: reset zoom Plotly.
            - **Click sulla mappa**: sposta il cursore al campione GNSS più vicino.
            """
        )


if uploaded is None:
    st.markdown(
        """
        <div class="trace-panel">
            <div class="trace-panel-title">Nessuna sessione caricata</div>
            <div class="trace-muted">
                Carica un CSV Trace dalla sidebar. L'app analizzerà una singola registrazione con dashboard,
                grafici sincronizzati, mappa raw GNSS e performance base.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    render_shortcuts_reference()
    st.stop()


try:
    df, report, metrics, warnings = _load(uploaded.getvalue(), uploaded.name)
except ValueError as exc:
    st.error(f"File non caricato. {clean_exception_message(exc)}")
    st.stop()
except Exception as exc:
    st.error("Errore inatteso durante il caricamento della sessione.")
    with st.expander("Dettaglio tecnico", expanded=False):
        st.code(clean_exception_message(exc))
    st.stop()


render_validation_report(report)

st.divider()


tab_dash, tab_charts, tab_map, tab_perf, tab_data, tab_columns, tab_debug = st.tabs(
    [
        "Dashboard",
        "Grafici",
        "Mappa",
        "Performance",
        "Dati",
        "Colonne",
        "Debug",
    ]
)

with tab_dash:
    render_dashboard(df, metrics, warnings, uploaded.name)

with tab_charts:
    render_charts_tab(df)

with tab_map:
    render_map_tab(df)

with tab_perf:
    render_performance_tab(df)

with tab_data:
    render_dataframe_preview(df)

with tab_columns:
    st.subheader("Catalogo colonne")
    st.caption(
        "Tutte le colonne presenti nella sessione caricata, incluse quelle derivate. "
        "'Non-null' conta le righe con valore valido."
    )
    render_column_catalogue(df)

with tab_debug:
    st.subheader("Debug sessione")
    st.caption("Informazioni tecniche utili per verificare parsing, schema e pipeline dati.")

    with st.expander("Report di validazione", expanded=True):
        st.json(report)

    with st.expander("Metriche sessione", expanded=False):
        st.json({k: (v if v is None or isinstance(v, (int, float, str, bool)) else str(v))
                 for k, v in metrics.items()})

    with st.expander("Warning tecnici", expanded=False):
        st.json(warnings)

    with st.expander("Tipi colonne", expanded=False):
        dtype_df = df.dtypes.reset_index()
        dtype_df.columns = ["Colonna", "Tipo"]
        dtype_df["Tipo"] = dtype_df["Tipo"].astype(str)
        st.dataframe(dtype_df, width="stretch", hide_index=True)

    st.write(f"Dimensioni: **{df.shape[0]:,}** righe × **{df.shape[1]:,}** colonne")
