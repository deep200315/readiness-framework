"""Metadata metrics: null rates, row count, data types, distribution."""
from __future__ import annotations

import pandas as pd

from metrics.models import CategoryResult, MetricCheck
from metrics.thresholds import build_check


def run(df: pd.DataFrame, cfg: dict) -> CategoryResult:
    checks: list[MetricCheck] = []
    thresholds = cfg.get("metadata_thresholds", {})

    # 1. Row count
    row_count = len(df)
    min_rows = thresholds.get("min_rows", 10)
    row_check = MetricCheck(
        name="row_count",
        passed=row_count >= min_rows,
        score=10.0 if row_count >= min_rows else max(0.0, 10.0 * row_count / min_rows),
        value=row_count,
        threshold=min_rows,
        detail=f"{row_count} rows (min {min_rows})",
    )
    checks.append(row_check)

    # 2. Per-column null rate
    null_threshold = thresholds.get("max_null_rate", 0.10)
    col_nulls = (df.isnull().sum() / max(len(df), 1)).to_dict()
    for col, null_rate in col_nulls.items():
        checks.append(
            build_check(
                name=f"null_rate:{col}",
                actual=null_rate,
                threshold=null_threshold,
                higher_is_worse=True,
                detail=f"{col}: {null_rate:.1%} nulls",
            )
        )

    # 3. Data type consistency (no mixed object columns that could be numeric)
    type_issues = []
    for col in df.select_dtypes(include="object").columns:
        sample = df[col].dropna().head(200)
        numeric_count = sample.apply(lambda x: str(x).replace(".", "", 1).replace("-", "", 1).isdigit()).sum()
        if numeric_count / max(len(sample), 1) > 0.9:
            type_issues.append(col)
    type_check = MetricCheck(
        name="dtype_consistency",
        passed=len(type_issues) == 0,
        score=10.0 if not type_issues else max(0.0, 10.0 * (1 - len(type_issues) / max(len(df.columns), 1))),
        value=type_issues,
        threshold=[],
        detail=f"Likely numeric-as-string columns: {type_issues}" if type_issues else "OK",
    )
    checks.append(type_check)

    # 4. Duplicate column names
    dup_cols = [c for c in df.columns if list(df.columns).count(c) > 1]
    checks.append(MetricCheck(
        name="duplicate_columns",
        passed=len(dup_cols) == 0,
        score=0.0 if dup_cols else 10.0,
        value=dup_cols,
        threshold=[],
        detail=f"Duplicate column names: {dup_cols}" if dup_cols else "OK",
    ))

    score = sum(c.score for c in checks) / max(len(checks), 1)
    failures = [c.detail for c in checks if not c.passed]
    return CategoryResult(
        category="metadata",
        score=round(score, 2),
        passed=score >= cfg.get("category_thresholds", {}).get("metadata", 6.0),
        checks=checks,
        failures=failures,
    )
