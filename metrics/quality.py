"""Data quality metrics: outliers, duplicates, completeness."""
from __future__ import annotations

import numpy as np
import pandas as pd

from metrics.models import CategoryResult, MetricCheck
from metrics.thresholds import build_check


def _iqr_outlier_rate(series: pd.Series) -> float:
    q1, q3 = series.quantile(0.25), series.quantile(0.75)
    iqr = q3 - q1
    if iqr == 0:
        return 0.0
    mask = (series < q1 - 1.5 * iqr) | (series > q3 + 1.5 * iqr)
    return mask.sum() / max(len(series), 1)


def run(df: pd.DataFrame, cfg: dict) -> CategoryResult:
    checks: list[MetricCheck] = []
    thresholds = cfg.get("quality_thresholds", {})

    # 1. Duplicate row rate
    dup_rate = df.duplicated().sum() / max(len(df), 1)
    checks.append(
        build_check(
            "duplicate_row_rate",
            dup_rate,
            thresholds.get("max_duplicate_rate", 0.05),
            higher_is_worse=True,
            detail=f"{dup_rate:.1%} duplicate rows",
        )
    )

    # 2. Completeness (inverse of any-null rate per row)
    completeness = 1.0 - (df.isnull().any(axis=1).sum() / max(len(df), 1))
    checks.append(
        build_check(
            "row_completeness",
            completeness,
            thresholds.get("min_completeness", 0.90),
            higher_is_worse=False,
            detail=f"{completeness:.1%} complete rows",
        )
    )

    # 3. Per-column outlier rate (numeric only)
    max_outlier_rate = thresholds.get("max_outlier_rate", 0.05)
    num_cols = df.select_dtypes(include=[np.number]).columns
    for col in num_cols:
        series = df[col].dropna()
        if len(series) < 4:
            continue
        rate = _iqr_outlier_rate(series)
        checks.append(
            build_check(
                f"outlier_rate:{col}",
                rate,
                max_outlier_rate,
                higher_is_worse=True,
                detail=f"{col}: {rate:.1%} outliers (IQR)",
            )
        )

    # 4. Constant columns (zero variance)
    const_cols = [c for c in df.columns if df[c].nunique(dropna=True) <= 1]
    checks.append(MetricCheck(
        name="constant_columns",
        passed=len(const_cols) == 0,
        score=10.0 if not const_cols else max(0.0, 10.0 * (1 - len(const_cols) / max(len(df.columns), 1))),
        value=const_cols,
        threshold=[],
        detail=f"Constant/empty columns: {const_cols}" if const_cols else "OK",
    ))

    score = sum(c.score for c in checks) / max(len(checks), 1)
    failures = [c.detail for c in checks if not c.passed]
    return CategoryResult(
        category="quality",
        score=round(score, 2),
        passed=score >= cfg.get("category_thresholds", {}).get("quality", 7.0),
        checks=checks,
        failures=failures,
    )
