"""
importer.py – Load and clean a Trace CSV file.
"""

from __future__ import annotations

import io
import pathlib
from typing import Union

import pandas as pd

from trace_studio.schema import NUMERIC_COLUMNS, validate_columns


def load_trace_csv(
    file: Union[str, pathlib.Path, io.IOBase],
) -> tuple[pd.DataFrame, dict]:
    """
    Load a Trace CSV file, validate its schema, and return a clean DataFrame.

    Parameters
    ----------
    file : str | Path | file-like
        A file path or a Streamlit UploadedFile / any file-like object.

    Returns
    -------
    (df, report)
        df     – Cleaned and sorted DataFrame.
        report – Validation report from validate_columns().

    Raises
    ------
    ValueError
        If the file cannot be read or mandatory columns are missing.
    """
    # ── 1. Read CSV ───────────────────────────────────────────────────────────
    try:
        df = pd.read_csv(file)
    except Exception as exc:
        raise ValueError(f"Cannot read CSV file: {exc}") from exc

    # ── 2. Normalize column names ─────────────────────────────────────────────
    df.columns = [c.strip() for c in df.columns]

    # ── 3. Schema validation ──────────────────────────────────────────────────
    report = validate_columns(df)
    if not report["ok"]:
        raise ValueError(
            f"Mandatory columns missing: {report['missing']}. "
            "Please check that this is a valid Trace CSV file."
        )

    # ── 4. Numeric conversion ─────────────────────────────────────────────────
    # Only convert columns that are actually present (handles extra columns safely)
    cols_to_convert = [c for c in NUMERIC_COLUMNS if c in df.columns]
    for col in cols_to_convert:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # ── 5. Sort by primary time axis ─────────────────────────────────────────
    if "t_mono_us" in df.columns:
        df = df.dropna(subset=["t_mono_us"])   # drop rows with no time reference
        df = df.drop_duplicates(subset=["t_mono_us"], keep="first")
        df = df.sort_values("t_mono_us").reset_index(drop=True)

    return df, report
