# modules/data_loader.py
import pandas as pd
import os
from datetime import datetime
from pathlib import Path
import hashlib

from config import REQUIRED_COLUMNS, DATE_COL

def compute_file_hash(path_or_buffer):
    """Return sha256 hex digest of a file path or file-like buffer (if buffer, it must be seekable)."""
    sha256 = hashlib.sha256()
    if isinstance(path_or_buffer, (str, Path)):
        with open(path_or_buffer, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
    else:
        # assume file-like
        path_or_buffer.seek(0)
        while True:
            chunk = path_or_buffer.read(8192)
            if not chunk:
                break
            if isinstance(chunk, str):
                chunk = chunk.encode()
            sha256.update(chunk)
        path_or_buffer.seek(0)
    return sha256.hexdigest()

def load_data(filepath_or_buffer=None, default_path="data/112_calls_synthetic.csv"):
    """
    Load CSV or Excel into a pandas DataFrame.
    If filepath_or_buffer is None, load default_path.
    Returns (df, metadata) where metadata contains file_hash and source_path.
    """
    source = filepath_or_buffer or default_path
    # Detect buffer vs path
    try:
        if hasattr(source, "read"):
            # file-like
            file_hash = compute_file_hash(source)
            df = _read_file(source)
            source_repr = getattr(source, "name", "uploaded_buffer")
        else:
            # assume path-like string
            if not os.path.exists(source):
                raise FileNotFoundError(f"File not found: {source}")
            file_hash = compute_file_hash(source)
            df = _read_file(source)
            source_repr = str(source)
    except Exception as e:
        raise

    # Basic validation: required columns
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    # Return dataframe and metadata
    metadata = {
        "source": source_repr,
        "record_count": len(df),
        "file_hash": file_hash,
        "loaded_ts": datetime.utcnow().isoformat()
    }
    return df, metadata

def _read_file(path_or_buffer):
    """Helper: read CSV or XLSX into pandas DataFrame (no heavy parsing yet)."""
    if hasattr(path_or_buffer, "read"):
        # file-like: pandas can handle it directly
        try:
            return pd.read_csv(path_or_buffer)
        except Exception:
            path_or_buffer.seek(0)
            return pd.read_excel(path_or_buffer)
    else:
        path = str(path_or_buffer)
        if path.lower().endswith(".csv"):
            return pd.read_csv(path)
        elif path.lower().endswith((".xls", ".xlsx")):
            return pd.read_excel(path)
        else:
            # fallback try both
            try:
                return pd.read_csv(path)
            except Exception:
                return pd.read_excel(path)

def preprocess(df, datetime_col=DATE_COL):
    """
    Preprocess raw DataFrame:
    - parse datetime
    - derive date, hour, weekday, month
    - normalize category/jurisdiction fields (trim, lower)
    - ensure lat/lon numeric
    Returns cleaned DataFrame.
    """
    df = df.copy()

    # Parse call timestamp
    df[datetime_col] = pd.to_datetime(df[datetime_col], errors="coerce")
    if df[datetime_col].isna().any():
        # Keep rows but mark bad timestamps
        df["bad_timestamp"] = df[datetime_col].isna()

    # Derived time features
    df["date"] = df[datetime_col].dt.date
    df["hour"] = df[datetime_col].dt.hour
    df["weekday"] = df[datetime_col].dt.day_name()
    df["month"] = df[datetime_col].dt.month
    df["year"] = df[datetime_col].dt.year
    df["is_weekend"] = df["weekday"].isin(["Saturday", "Sunday"])

    # Normalize textual fields
    if "category" in df.columns:
        df["category"] = df["category"].astype(str).str.strip().str.lower()
    if "jurisdiction" in df.columns:
        df["jurisdiction"] = df["jurisdiction"].astype(str).str.strip()

    # Lat/Lon numeric coercion
    for col in ["caller_lat", "caller_lon"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Flag rows with missing coords
    df["has_coords"] = df["caller_lat"].notna() & df["caller_lon"].notna()

    # Optionally compute response_time if response_ts present
    if "response_ts" in df.columns:
        df["response_ts"] = pd.to_datetime(df["response_ts"], errors="coerce")
        df["response_time_min"] = (df["response_ts"] - df[datetime_col]).dt.total_seconds() / 60.0
        # If negative or NaN, set to NaN
        df.loc[df["response_time_min"] < 0, "response_time_min"] = pd.NA

    return df
