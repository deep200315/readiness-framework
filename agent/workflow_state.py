"""Shared LangGraph state TypedDict for the data quality workflow."""
from __future__ import annotations

from typing import Any, Optional
from typing_extensions import TypedDict


class WorkflowState(TypedDict):
    run_id: str
    source_table: str          # user-selected: "catalog.schema.table"
    usecase: str               # user-provided description for GPT-4o reasoning
    dataframe_json: str        # pandas DataFrame serialized as JSON (orient="split")
    local_parquet_path: str    # /tmp/run_{run_id}.parquet — disk checkpoint
    metric_results: dict       # MetricSuite.to_dict()
    score: float
    iteration: int
    suggestions: list[dict]    # list of ActionableFix from GPT-4o
    approval_status: str       # "pending" | "approved" | "rejected"
    pipeline_run_id: str
    pipeline_status: dict
    status: str                # "running" | "awaiting_approval_suggestions"
                               # | "awaiting_approval_pipeline" | "done" | "failed"
    error: Optional[str]
