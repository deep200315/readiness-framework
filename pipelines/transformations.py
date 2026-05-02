"""Registry of data cleaning transformations keyed by transform_fn_name."""
from __future__ import annotations

import logging
import re

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Each transform: (df, params) -> df


def drop_duplicates(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    subset = params.get("subset")
    before = len(df)
    df = df.drop_duplicates(subset=subset)
    logger.info("drop_duplicates: %d → %d rows", before, len(df))
    return df


def fill_nulls_median(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    columns = params.get("columns") or df.select_dtypes(include=[np.number]).columns.tolist()
    for col in columns:
        if col in df.columns:
            median = df[col].median()
            count = df[col].isnull().sum()
            df[col] = df[col].fillna(median)
            logger.info("fill_nulls_median: %s — filled %d nulls with median %.4f", col, count, median)
    return df


def fill_nulls_mode(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    columns = params.get("columns") or df.select_dtypes(include="object").columns.tolist()
    for col in columns:
        if col in df.columns and df[col].isnull().any():
            mode_val = df[col].mode(dropna=True)
            if len(mode_val):
                df[col] = df[col].fillna(mode_val.iloc[0])
                logger.info("fill_nulls_mode: %s filled with mode '%s'", col, mode_val.iloc[0])
    return df


def drop_null_rows(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    threshold = params.get("threshold", 0.5)
    min_cols = int(len(df.columns) * (1 - threshold))
    before = len(df)
    df = df.dropna(thresh=min_cols)
    logger.info("drop_null_rows: %d → %d rows (thresh=%.0f%%)", before, len(df), threshold * 100)
    return df


def clip_outliers_iqr(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    columns = params.get("columns") or df.select_dtypes(include=[np.number]).columns.tolist()
    factor = params.get("factor", 1.5)
    for col in columns:
        if col in df.columns:
            q1, q3 = df[col].quantile(0.25), df[col].quantile(0.75)
            iqr = q3 - q1
            lower, upper = q1 - factor * iqr, q3 + factor * iqr
            clipped = ((df[col] < lower) | (df[col] > upper)).sum()
            df[col] = df[col].clip(lower=lower, upper=upper)
            logger.info("clip_outliers_iqr: %s clipped %d values", col, clipped)
    return df


def normalize_minmax(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    columns = params.get("columns") or df.select_dtypes(include=[np.number]).columns.tolist()
    for col in columns:
        if col in df.columns:
            mn, mx = df[col].min(), df[col].max()
            if mx > mn:
                df[col] = (df[col] - mn) / (mx - mn)
    return df


def cast_numeric_columns(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    columns = params.get("columns", [])
    for col in columns:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def drop_high_null_columns(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    threshold = params.get("threshold", 0.8)
    null_rates = df.isnull().mean()
    to_drop = null_rates[null_rates > threshold].index.tolist()
    if to_drop:
        logger.info("drop_high_null_columns: dropping %s", to_drop)
        df = df.drop(columns=to_drop)
    return df


def anonymize_pii_columns(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    columns = params.get("columns", [])
    strategy = params.get("strategy", "hash")
    for col in columns:
        if col not in df.columns:
            continue
        if strategy == "hash":
            df[col] = df[col].apply(lambda x: str(hash(str(x)))[:8] if pd.notna(x) else x)
        elif strategy == "drop":
            df = df.drop(columns=[col])
        elif strategy == "mask":
            df[col] = "***"
        logger.info("anonymize_pii_columns: %s (strategy=%s)", col, strategy)
    return df


# Registry
_REGISTRY: dict[str, callable] = {
    "drop_duplicates": drop_duplicates,
    "fill_nulls_median": fill_nulls_median,
    "fill_nulls_mode": fill_nulls_mode,
    "drop_null_rows": drop_null_rows,
    "clip_outliers_iqr": clip_outliers_iqr,
    "normalize_minmax": normalize_minmax,
    "cast_numeric_columns": cast_numeric_columns,
    "drop_high_null_columns": drop_high_null_columns,
    "anonymize_pii_columns": anonymize_pii_columns,
}


def apply_fixes(df: pd.DataFrame, fixes: list[dict]) -> pd.DataFrame:
    """Apply a list of ActionableFix dicts to df in order."""
    for fix in fixes:
        fn_name = fix.get("transform_fn_name")
        params = fix.get("params", {})
        if not fn_name:
            logger.warning("Fix missing transform_fn_name: %s", fix)
            continue
        fn = _REGISTRY.get(fn_name)
        if not fn:
            logger.warning("Unknown transform '%s'; skipping", fn_name)
            continue
        try:
            df = fn(df, params)
        except Exception as exc:
            logger.error("Transform '%s' failed: %s", fn_name, exc)
    return df


def list_available() -> list[str]:
    return list(_REGISTRY.keys())
