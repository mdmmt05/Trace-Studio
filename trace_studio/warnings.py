"""
warnings.py – Basic technical warnings for a Trace session.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def compute_basic_warnings(df: pd.DataFrame) -> list[dict]:
    """
    Return a list of warnings (info/warning/error) about the session.

    Each warning is a dict:
        {"level": "info"/"warning"/"error", "title": str, "detail": str}
    """
    warnings = []

    # Empty dataframe
    if df.empty:
        warnings.append({
            "level": "error",
            "title": "DataFrame vuoto",
            "detail": "Il file caricato non contiene righe valide dopo la pulizia."
        })
        return warnings

    n_rows = len(df)

    # Very low sample count
    if n_rows < 10:
        warnings.append({
            "level": "warning",
            "title": "Numero di campioni molto basso",
            "detail": f"Solo {n_rows} righe. L'analisi potrebbe non essere significativa."
        })

    # Missing or invalid time_s
    if "time_s" not in df.columns:
        warnings.append({
            "level": "error",
            "title": "Asse temporale mancante",
            "detail": "Colonna 'time_s' non presente. Impossibile creare grafici temporali."
        })
    else:
        time_valid = df["time_s"].notna()
        if not time_valid.any():
            warnings.append({
                "level": "error",
                "title": "Nessun timestamp valido",
                "detail": "Tutti i valori di 'time_s' sono NaN."
            })
        else:
            # Non‑monotonic time (should not happen after processing, but check anyway)
            t = df.loc[time_valid, "time_s"]
            if not t.is_monotonic_increasing:
                warnings.append({
                    "level": "warning",
                    "title": "Tempo non monotono",
                    "detail": "L'asse temporale non è strettamente crescente. I grafici potrebbero essere incoerenti."
                })

            # Large sampling gaps
            if "sample_dt_s" in df.columns:
                dt = df["sample_dt_s"].dropna()
                if not dt.empty:
                    max_gap = dt.max()
                    if max_gap > 1.5:
                        warnings.append({
                            "level": "info",
                            "title": "Grande gap di campionamento",
                            "detail": f"Intervallo massimo tra campioni: {max_gap:.2f} s. Potrebbero esserci buchi nei dati."
                        })

    # GNSS position quality
    if "valid_position" in df.columns:
        valid_pos = df["valid_position"].sum()
        if valid_pos == 0:
            warnings.append({
                "level": "warning",
                "title": "Nessuna posizione GNSS valida",
                "detail": "Tutte le coordinate lat/lon sono NaN, zero o non valide."
            })
        elif valid_pos / n_rows < 0.5:
            warnings.append({
                "level": "info",
                "title": "Bassa copertura GNSS",
                "detail": f"Solo {valid_pos}/{n_rows} posizioni valide ({100*valid_pos/n_rows:.1f}%)."
            })

    # Critical channels all‑zero or all‑NaN
    def warn_all_invalid(col: str, name: str):
        if col in df.columns:
            series = df[col]
            if series.notna().any():
                if (series.dropna() == 0).all():
                    warnings.append({
                        "level": "info",
                        "title": f"Canale '{name}' sempre zero",
                        "detail": f"Tutti i valori validi di {col} sono 0."
                    })
            else:
                warnings.append({
                    "level": "info",
                    "title": f"Canale '{name}' completamente NaN",
                    "detail": f"Nessun valore valido in {col}."
                })

    warn_all_invalid("speed_obd_kmh", "Velocità OBD")
    warn_all_invalid("rpm", "RPM")
    warn_all_invalid("acc_lon_G", "Accelerazione longitudinale")
    warn_all_invalid("acc_lat_G", "Accelerazione laterale")

    # High fraction of NaN in important channels
    important_cols = ["speed_obd_kmh", "rpm", "acc_lon_G", "acc_lat_G"]
    for col in important_cols:
        if col in df.columns:
            nan_frac = df[col].isna().mean()
            if nan_frac > 0.8:
                warnings.append({
                    "level": "warning",
                    "title": f"Alta percentuale di NaN in {col}",
                    "detail": f"{100*nan_frac:.1f}% dei valori mancanti."
                })

    # UTC validity
    if "utc_valid" in df.columns:
        utc_ok = df["utc_valid"].fillna(0).astype(bool).any()
        if not utc_ok:
            warnings.append({
                "level": "info",
                "title": "UTC mai valido",
                "detail": "La colonna 'utc_valid' è sempre 0 o NaN. Le etichette UTC potrebbero non essere affidabili."
            })

    # Sync quality low
    if "sync_quality" in df.columns:
        qual = df["sync_quality"].dropna()
        if not qual.empty and qual.mean() < 50:
            warnings.append({
                "level": "info",
                "title": "Qualità di sincronizzazione bassa",
                "detail": f"Valore medio sync_quality = {qual.mean():.1f} (range 0-100)."
            })

    return warnings