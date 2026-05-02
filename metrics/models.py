"""Shared data models for metric results."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class MetricCheck:
    name: str
    passed: bool
    score: float          # 0–10
    value: Any            # computed value
    threshold: Any        # expected value / threshold
    detail: str = ""


@dataclass
class CategoryResult:
    category: str         # metadata | quality | governance | fairness
    score: float          # 0–10 weighted
    passed: bool
    checks: list[MetricCheck] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)


@dataclass
class MetricSuite:
    run_id: str
    table_ref: str
    usecase: str
    overall_score: float
    passed: bool
    iteration: int
    categories: dict[str, CategoryResult] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "table_ref": self.table_ref,
            "usecase": self.usecase,
            "overall_score": round(self.overall_score, 2),
            "passed": self.passed,
            "iteration": self.iteration,
            "categories": {
                k: {
                    "score": round(v.score, 2),
                    "passed": v.passed,
                    "failures": v.failures,
                    "checks": [
                        {
                            "name": c.name,
                            "passed": c.passed,
                            "score": round(c.score, 2),
                            "value": c.value,
                            "threshold": c.threshold,
                            "detail": c.detail,
                        }
                        for c in v.checks
                    ],
                }
                for k, v in self.categories.items()
            },
        }
