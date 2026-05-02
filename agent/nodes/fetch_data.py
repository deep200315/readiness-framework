"""Node: fetch source table from Databricks and store locally."""
from __future__ import annotations

import logging
import os

import pandas as pd

from agent.workflow_state import WorkflowState
from config import get_config
from connectors.databricks import connector_from_config

logger = logging.getLogger(__name__)


async def fetch_data(state: WorkflowState) -> dict:
    cfg = get_config()
    connector = connector_from_config(cfg)

    max_rows = int(cfg.get("app", {}).get("max_fetch_rows", 50_000))
    logger.info("[fetch_data] run_id=%s table=%s", state["run_id"], state["source_table"])

    df: pd.DataFrame = connector.fetch_table(state["source_table"], limit=max_rows)

    parquet_dir = cfg.get("app", {}).get("local_parquet_dir", "/tmp")
    parquet_path = os.path.join(parquet_dir, f"run_{state['run_id']}.parquet")
    df.to_parquet(parquet_path, index=False)

    return {
        "dataframe_json": df.to_json(orient="split"),
        "local_parquet_path": parquet_path,
        "status": "running",
        "error": None,
    }
