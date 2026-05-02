"""MetricEngine: orchestrates all 4 metric categories and produces a scored MetricSuite."""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

import pandas as pd

from metrics import metadata, quality, governance, fairness
from metrics.models import MetricSuite

logger = logging.getLogger(__name__)


class MetricEngine:
    def __init__(self, cfg: dict) -> None:
        self._cfg = cfg
        self._weights: dict[str, float] = cfg["metrics"]["weights"]
        self._threshold: float = float(cfg["metrics"]["passing_threshold"])

    async def run(
        self,
        df: pd.DataFrame,
        run_id: str,
        table_ref: str,
        usecase: str,
        iteration: int = 0,
    ) -> MetricSuite:
        loop = asyncio.get_event_loop()

        # Run all 4 categories concurrently in a thread pool (they are CPU-bound)
        results = await asyncio.gather(
            loop.run_in_executor(None, metadata.run, df, self._cfg["metrics"]),
            loop.run_in_executor(None, quality.run, df, self._cfg["metrics"]),
            loop.run_in_executor(None, governance.run, df, self._cfg["metrics"]),
            loop.run_in_executor(None, fairness.run, df, self._cfg["metrics"]),
        )

        category_map = {r.category: r for r in results}

        overall_score = sum(
            self._weights.get(cat, 0.25) * r.score
            for cat, r in category_map.items()
        )

        suite = MetricSuite(
            run_id=run_id,
            table_ref=table_ref,
            usecase=usecase,
            overall_score=round(overall_score, 2),
            passed=overall_score >= self._threshold,
            iteration=iteration,
            categories=category_map,
        )

        logger.info(
            "run_id=%s iteration=%d score=%.2f passed=%s",
            run_id,
            iteration,
            overall_score,
            suite.passed,
        )
        return suite
