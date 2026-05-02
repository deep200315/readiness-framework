"""Governance metrics: PII detection, entropy, anonymity."""
from __future__ import annotations

import logging
import math
import re

import pandas as pd

from metrics.models import CategoryResult, MetricCheck

logger = logging.getLogger(__name__)

# Lightweight regex-based PII patterns (Presidio used when available)
_PII_PATTERNS = {
    "email": re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"),
    "phone": re.compile(r"\b(\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"),
    "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "credit_card": re.compile(r"\b(?:\d[ -]?){13,16}\b"),
    "ip_address": re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
}

_PII_COLUMN_HINTS = {
    "name", "first_name", "last_name", "fullname", "email", "phone",
    "ssn", "social_security", "address", "zip", "dob", "birth_date",
    "passport", "license", "credit_card", "card_number",
}


def _column_entropy(series: pd.Series) -> float:
    counts = series.dropna().value_counts(normalize=True)
    return -sum(p * math.log2(p) for p in counts if p > 0)


def _detect_pii_column(col_name: str, series: pd.Series) -> list[str]:
    hits: list[str] = []
    if col_name.lower().strip() in _PII_COLUMN_HINTS:
        hits.append(f"column name '{col_name}' matches PII hint")

    try:
        from presidio_analyzer import AnalyzerEngine
        engine = AnalyzerEngine()
        sample = series.dropna().astype(str).head(50)
        for val in sample:
            results = engine.analyze(text=val, language="en")
            if results:
                entity_types = list({r.entity_type for r in results})
                hits.append(f"Presidio detected: {entity_types} in '{col_name}'")
                break
    except Exception:
        # Fall back to regex
        sample = series.dropna().astype(str).head(100)
        for name, pattern in _PII_PATTERNS.items():
            if sample.str.contains(pattern, regex=True).any():
                hits.append(f"Regex PII pattern '{name}' in '{col_name}'")
    return hits


def run(df: pd.DataFrame, cfg: dict) -> CategoryResult:
    checks: list[MetricCheck] = []
    thresholds = cfg.get("governance_thresholds", {})

    # 1. PII detection
    pii_findings: list[str] = []
    for col in df.select_dtypes(include="object").columns:
        pii_findings.extend(_detect_pii_column(col, df[col]))

    checks.append(MetricCheck(
        name="pii_detection",
        passed=len(pii_findings) == 0,
        score=0.0 if pii_findings else 10.0,
        value=pii_findings,
        threshold=[],
        detail=f"PII detected in columns: {pii_findings[:3]}" if pii_findings else "No PII detected",
    ))

    # 2. Column entropy (low entropy → potential sensitive ID columns)
    min_entropy = thresholds.get("min_column_entropy", 1.0)
    for col in df.select_dtypes(include="object").columns:
        ent = _column_entropy(df[col])
        checks.append(MetricCheck(
            name=f"entropy:{col}",
            passed=ent >= min_entropy or df[col].nunique() <= 5,
            score=min(10.0, ent * 2),
            value=round(ent, 3),
            threshold=min_entropy,
            detail=f"{col}: entropy={ent:.2f} (min {min_entropy})" if ent < min_entropy else f"{col}: entropy OK",
        ))

    # 3. Uniqueness rate for high-cardinality columns (potential leaked IDs)
    max_unique_rate = thresholds.get("max_id_unique_rate", 0.95)
    for col in df.select_dtypes(include="object").columns:
        unique_rate = df[col].nunique() / max(len(df), 1)
        if unique_rate > max_unique_rate:
            checks.append(MetricCheck(
                name=f"high_cardinality:{col}",
                passed=False,
                score=5.0,
                value=round(unique_rate, 3),
                threshold=max_unique_rate,
                detail=f"{col}: {unique_rate:.1%} unique — possible ID/PII column",
            ))

    score = sum(c.score for c in checks) / max(len(checks), 1)
    failures = [c.detail for c in checks if not c.passed]
    return CategoryResult(
        category="governance",
        score=round(score, 2),
        passed=score >= cfg.get("category_thresholds", {}).get("governance", 8.0),
        checks=checks,
        failures=failures,
    )
