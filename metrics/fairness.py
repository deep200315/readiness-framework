"""Fairness metrics: representation rates, class imbalance."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from metrics.models import CategoryResult, MetricCheck


def _imbalance_ratio(series: pd.Series) -> float:
    """Max class count / min class count. 1.0 = perfectly balanced."""
    counts = series.dropna().value_counts()
    if len(counts) < 2:
        return 1.0
    return counts.iloc[0] / max(counts.iloc[-1], 1)


def _gini_impurity(series: pd.Series) -> float:
    probs = series.dropna().value_counts(normalize=True).values
    return 1.0 - sum(p ** 2 for p in probs)


def run(df: pd.DataFrame, cfg: dict) -> CategoryResult:
    checks: list[MetricCheck] = []
    thresholds = cfg.get("fairness_thresholds", {})
    max_imbalance = thresholds.get("max_imbalance_ratio", 10.0)

    cat_cols = df.select_dtypes(include=["object", "category"]).columns
    bool_cols = df.select_dtypes(include=["bool"]).columns
    candidate_cols = list(cat_cols) + list(bool_cols)

    if not candidate_cols:
        # No categorical columns — fairness metrics not applicable
        checks.append(MetricCheck(
            name="fairness_applicability",
            passed=True,
            score=10.0,
            value="no categorical columns",
            threshold=None,
            detail="No categorical columns; fairness metrics not applicable",
        ))
    else:
        for col in candidate_cols:
            n_unique = df[col].nunique(dropna=True)
            if n_unique < 2 or n_unique > 50:
                continue

            imbalance = _imbalance_ratio(df[col])
            passed = imbalance <= max_imbalance
            score = min(10.0, 10.0 / math.log1p(max(imbalance - 1, 0) + 1))
            checks.append(MetricCheck(
                name=f"imbalance_ratio:{col}",
                passed=passed,
                score=round(score, 2),
                value=round(imbalance, 2),
                threshold=max_imbalance,
                detail=f"{col}: imbalance ratio {imbalance:.1f}x (max {max_imbalance}x)",
            ))

            gini = _gini_impurity(df[col])
            checks.append(MetricCheck(
                name=f"gini_impurity:{col}",
                passed=gini >= thresholds.get("min_gini", 0.1),
                score=min(10.0, gini * 10),
                value=round(gini, 3),
                threshold=thresholds.get("min_gini", 0.1),
                detail=f"{col}: Gini={gini:.3f}",
            ))

    # Numeric representation: coefficient of variation across numeric columns
    num_cols = df.select_dtypes(include=[np.number]).columns
    for col in num_cols:
        series = df[col].dropna()
        mean = series.mean()
        std = series.std()
        cv = std / abs(mean) if mean != 0 else float("inf")
        max_cv = thresholds.get("max_cv", 5.0)
        checks.append(MetricCheck(
            name=f"coeff_variation:{col}",
            passed=cv <= max_cv,
            score=min(10.0, 10.0 * max_cv / max(cv, 0.001)),
            value=round(cv, 3),
            threshold=max_cv,
            detail=f"{col}: CV={cv:.2f}",
        ))

    if not checks:
        checks.append(MetricCheck(
            name="fairness_default",
            passed=True,
            score=10.0,
            value=None,
            threshold=None,
            detail="No columns eligible for fairness evaluation",
        ))

    score = sum(c.score for c in checks) / max(len(checks), 1)
    failures = [c.detail for c in checks if not c.passed]
    return CategoryResult(
        category="fairness",
        score=round(score, 2),
        passed=score >= cfg.get("category_thresholds", {}).get("fairness", 7.0),
        checks=checks,
        failures=failures,
    )
