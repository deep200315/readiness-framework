"""Unit tests for the metrics engine."""
import asyncio

import numpy as np
import pandas as pd
import pytest

from metrics import metadata, quality, governance, fairness
from metrics.engine import MetricEngine

_MOCK_CFG = {
    "metrics": {
        "passing_threshold": 8.0,
        "max_iterations": 5,
        "weights": {"metadata": 0.20, "quality": 0.35, "governance": 0.30, "fairness": 0.15},
        "category_thresholds": {"metadata": 6.0, "quality": 7.0, "governance": 8.0, "fairness": 7.0},
    }
}


def _clean_df(n=200):
    rng = np.random.default_rng(42)
    return pd.DataFrame({
        "age": rng.integers(20, 70, n).astype(float),
        "income": rng.normal(50000, 10000, n),
        "category": rng.choice(["A", "B", "C"], n),
        "label": rng.choice([0, 1], n),
    })


def _dirty_df(n=200):
    df = _clean_df(n)
    df.loc[:20, "age"] = None
    df.loc[50:60, "income"] = 1e9  # outliers
    df = pd.concat([df, df.iloc[:10]], ignore_index=True)  # duplicates
    return df


class TestMetadata:
    def test_clean_data_passes(self):
        result = metadata.run(_clean_df(), _MOCK_CFG["metrics"])
        assert result.score > 5.0
        assert result.category == "metadata"

    def test_row_count_check(self):
        small_df = _clean_df(5)
        result = metadata.run(small_df, _MOCK_CFG["metrics"])
        row_check = next(c for c in result.checks if c.name == "row_count")
        assert not row_check.passed


class TestQuality:
    def test_dirty_data_lower_score(self):
        clean = quality.run(_clean_df(), _MOCK_CFG["metrics"])
        dirty = quality.run(_dirty_df(), _MOCK_CFG["metrics"])
        assert dirty.score <= clean.score

    def test_duplicate_detection(self):
        df = _clean_df(100)
        df = pd.concat([df, df], ignore_index=True)
        result = quality.run(df, _MOCK_CFG["metrics"])
        dup_check = next(c for c in result.checks if c.name == "duplicate_row_rate")
        assert not dup_check.passed


class TestFairness:
    def test_balanced_data_passes(self):
        df = _clean_df()
        result = fairness.run(df, _MOCK_CFG["metrics"])
        assert result.score > 0


class TestMetricEngine:
    def test_engine_produces_suite(self):
        engine = MetricEngine(_MOCK_CFG)
        df = _clean_df()
        suite = asyncio.run(engine.run(df, "test-run-1", "cat.sch.tbl", "test usecase", 0))
        assert suite.run_id == "test-run-1"
        assert 0 <= suite.overall_score <= 10
        assert set(suite.categories.keys()) == {"metadata", "quality", "governance", "fairness"}

    def test_suite_to_dict(self):
        engine = MetricEngine(_MOCK_CFG)
        df = _clean_df()
        suite = asyncio.run(engine.run(df, "test-run-2", "cat.sch.tbl", "test", 0))
        d = suite.to_dict()
        assert "overall_score" in d
        assert "categories" in d
