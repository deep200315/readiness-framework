"""Node: apply approved fixes (locally or via Databricks Job)."""
from __future__ import annotations

import logging
import os

import pandas as pd

from agent.workflow_state import WorkflowState
from config import get_config
from connectors.databricks import connector_from_config
from pipelines.databricks_jobs import pipeline_from_config

logger = logging.getLogger(__name__)


async def trigger_pipeline(state: WorkflowState) -> dict:
    cfg = get_config()
    connector = connector_from_config(cfg)
    pipeline = pipeline_from_config(cfg, connector)

    df = pd.read_json(state["dataframe_json"], orient="split")
    fixes = [s for s in state["suggestions"] if s.get("transform_fn_name")]

    logger.info("[trigger_pipeline] run_id=%s applying %d fixes", state["run_id"], len(fixes))

    cleaned_df = await pipeline.apply_local(df, fixes)

    # Persist cleaned DataFrame
    parquet_path = state.get("local_parquet_path", f"/tmp/run_{state['run_id']}.parquet")
    cleaned_df.to_parquet(parquet_path, index=False)

    pipeline_run_id = await pipeline.trigger({"run_id": state["run_id"], "fixes": [f.get("transform_fn_name") for f in fixes]})

    require_approval = cfg.get("pipeline", {}).get("require_approval_after_pipeline", True)
    next_status = "awaiting_approval_pipeline" if require_approval else "running"

    return {
        "dataframe_json": cleaned_df.to_json(orient="split"),
        "local_parquet_path": parquet_path,
        "pipeline_run_id": pipeline_run_id,
        "pipeline_status": {"state": "TRIGGERED", "done": False},
        "status": next_status,
        "approval_status": "pending" if require_approval else "approved",
    }


async def push_to_target(state: WorkflowState) -> dict:
    cfg = get_config()
    connector = connector_from_config(cfg)
    db_cfg = cfg["databricks"]

    df = pd.read_json(state["dataframe_json"], orient="split")
    logger.info("[push_to_target] run_id=%s rows=%d → %s.%s.%s",
                state["run_id"], len(df),
                db_cfg["target_catalog"], db_cfg["target_schema"], db_cfg["target_table"])

    connector.write_table(
        df,
        catalog=db_cfg["target_catalog"],
        schema=db_cfg["target_schema"],
        table=db_cfg["target_table"],
    )

    # Clean up local parquet
    try:
        parquet_path = state.get("local_parquet_path", "")
        if parquet_path and os.path.exists(parquet_path):
            os.remove(parquet_path)
    except Exception:
        pass

    return {"status": "done"}
