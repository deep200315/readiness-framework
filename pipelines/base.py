"""Abstract pipeline interface — swap Databricks Jobs / Airflow / local."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class AbstractPipeline(ABC):
    @abstractmethod
    async def trigger(self, params: dict[str, Any]) -> str:
        """Kick off the pipeline. Returns a run_id string."""

    @abstractmethod
    async def poll_status(self, run_id: str) -> dict[str, Any]:
        """Return status dict with keys: run_id, state, done, success, message."""

    @abstractmethod
    async def apply_local(self, df, fixes: list[dict[str, Any]]):
        """Apply fixes directly to a pandas DataFrame (local mode). Returns cleaned df."""
