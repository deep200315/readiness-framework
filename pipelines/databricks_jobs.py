"""Databricks Jobs pipeline: triggers a remote Job and polls for completion."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import pandas as pd

from connectors.databricks import DatabricksConnector
from pipelines.base import AbstractPipeline
from pipelines.transformations import apply_fixes

logger = logging.getLogger(__name__)

_TERMINAL_STATES = {"TERMINATED", "SKIPPED", "INTERNAL_ERROR"}


class DatabricksJobsPipeline(AbstractPipeline):
    def __init__(self, connector: DatabricksConnector, job_id: int, poll_interval: int = 30) -> None:
        self._connector = connector
        self._job_id = job_id
        self._poll_interval = poll_interval

    async def trigger(self, params: dict[str, Any]) -> str:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._connector.trigger_job, self._job_id, params)

    async def poll_status(self, run_id: str) -> dict[str, Any]:
        loop = asyncio.get_event_loop()
        raw = await loop.run_in_executor(None, self._connector.get_job_run_status, run_id)
        state = raw["life_cycle_state"]
        result = raw.get("result_state")
        done = state in _TERMINAL_STATES
        success = done and result == "SUCCESS"
        return {
            "run_id": run_id,
            "state": state,
            "result_state": result,
            "done": done,
            "success": success,
            "message": raw.get("state_message", ""),
        }

    async def apply_local(self, df: pd.DataFrame, fixes: list[dict[str, Any]]) -> pd.DataFrame:
        # Fallback: apply locally when large-data remote path is not needed
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, apply_fixes, df, fixes)


def pipeline_from_config(cfg: dict, connector: DatabricksConnector) -> AbstractPipeline:
    from pipelines.local_pipeline import LocalPipeline

    pipeline_type = cfg.get("pipeline", {}).get("type", "local")
    if pipeline_type == "databricks_jobs":
        job_id = cfg["pipeline"]["databricks_job_id"]
        if not job_id:
            raise ValueError("pipeline.databricks_job_id must be set for databricks_jobs pipeline type")
        poll_interval = cfg["pipeline"].get("poll_interval_seconds", 30)
        return DatabricksJobsPipeline(connector, int(job_id), poll_interval)
    return LocalPipeline()
