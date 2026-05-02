"""Local pipeline: applies transformations directly to an in-memory DataFrame."""
from __future__ import annotations

import asyncio
import uuid
from typing import Any

import pandas as pd

from pipelines.base import AbstractPipeline
from pipelines.transformations import apply_fixes


class LocalPipeline(AbstractPipeline):
    """Runs all transforms in-process. Fast for small–medium DataFrames."""

    async def trigger(self, params: dict[str, Any]) -> str:
        # Local mode is synchronous; trigger returns a synthetic run_id immediately
        return f"local-{uuid.uuid4().hex[:8]}"

    async def poll_status(self, run_id: str) -> dict[str, Any]:
        return {"run_id": run_id, "state": "TERMINATED", "done": True, "success": True, "message": "local"}

    async def apply_local(self, df: pd.DataFrame, fixes: list[dict[str, Any]]) -> pd.DataFrame:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, apply_fixes, df, fixes)
