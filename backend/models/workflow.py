from __future__ import annotations
from typing import Any, Optional
from pydantic import BaseModel


class RunChecksRequest(BaseModel):
    source_table: str
    usecase: str = "general data quality"


class RunChecksResponse(BaseModel):
    run_id: str
    status: str
    message: str


class ApproveStepRequest(BaseModel):
    run_id: str
    decision: str   # "approved" | "rejected"
    checkpoint: str  # "suggestions" | "pipeline_result"


class ApproveStepResponse(BaseModel):
    run_id: str
    status: str


class StatusResponse(BaseModel):
    run_id: str
    status: str
    score: Optional[float] = None
    iteration: Optional[int] = None
    metric_results: Optional[dict] = None
    suggestions: Optional[list[dict]] = None
    pipeline_run_id: Optional[str] = None
    error: Optional[str] = None


class SuggestionsResponse(BaseModel):
    run_id: str
    suggestions: list[dict]
    score: float
    metric_results: dict


class TriggerPipelineRequest(BaseModel):
    run_id: str


class TriggerPipelineResponse(BaseModel):
    run_id: str
    pipeline_run_id: str
    status: str


class ListTablesResponse(BaseModel):
    tables: list[str]
