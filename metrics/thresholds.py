"""Threshold evaluation helpers."""
from __future__ import annotations

from metrics.models import MetricCheck


def pct_score(actual_pct: float, threshold_pct: float) -> tuple[bool, float]:
    """Higher actual is worse (e.g. null rate). Returns (passed, score 0–10)."""
    passed = actual_pct <= threshold_pct
    score = max(0.0, 10.0 * (1.0 - actual_pct / max(threshold_pct, 0.001)))
    return passed, round(min(score, 10.0), 2)


def ratio_score(actual: float, target: float = 1.0) -> tuple[bool, float]:
    """Actual should be close to target (e.g. completeness rate). Returns (passed, score)."""
    passed = actual >= target * 0.95
    score = min(10.0, actual * 10.0 / max(target, 0.001))
    return passed, round(score, 2)


def build_check(
    name: str,
    actual: float,
    threshold: float,
    higher_is_worse: bool = True,
    detail: str = "",
) -> MetricCheck:
    if higher_is_worse:
        passed, score = pct_score(actual, threshold)
    else:
        passed, score = ratio_score(actual, threshold)
    return MetricCheck(
        name=name,
        passed=passed,
        score=score,
        value=round(actual, 4),
        threshold=threshold,
        detail=detail,
    )
