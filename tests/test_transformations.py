"""Unit tests for transformation functions."""
import numpy as np
import pandas as pd
import pytest

from pipelines.transformations import apply_fixes


def _df():
    rng = np.random.default_rng(0)
    df = pd.DataFrame({
        "a": [1.0, None, 3.0, None, 5.0],
        "b": ["x", "y", "x", "x", None],
        "c": [1.0, 2.0, 1e9, 2.0, 1.0],
    })
    return df


def test_fill_nulls_median():
    df = _df()
    out = apply_fixes(df, [{"transform_fn_name": "fill_nulls_median", "params": {"columns": ["a"]}}])
    assert out["a"].isnull().sum() == 0


def test_fill_nulls_mode():
    df = _df()
    out = apply_fixes(df, [{"transform_fn_name": "fill_nulls_mode", "params": {"columns": ["b"]}}])
    assert out["b"].isnull().sum() == 0


def test_drop_duplicates():
    df = pd.DataFrame({"x": [1, 1, 2], "y": [3, 3, 4]})
    out = apply_fixes(df, [{"transform_fn_name": "drop_duplicates", "params": {}}])
    assert len(out) == 2


def test_clip_outliers():
    df = _df()
    out = apply_fixes(df, [{"transform_fn_name": "clip_outliers_iqr", "params": {"columns": ["c"]}}])
    assert out["c"].max() < 1e8


def test_unknown_transform_skipped():
    df = _df()
    out = apply_fixes(df, [{"transform_fn_name": "nonexistent_fn", "params": {}}])
    assert len(out) == len(df)
