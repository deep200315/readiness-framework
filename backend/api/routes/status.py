from fastapi import APIRouter, Depends, HTTPException
from backend.api.deps import get_workflow_service
from backend.models.workflow import StatusResponse
from backend.services.workflow_service import WorkflowService

router = APIRouter()


@router.get("/status/{run_id}", response_model=StatusResponse)
async def get_status(run_id: str, svc: WorkflowService = Depends(get_workflow_service)):
    state = await svc.get_status(run_id)
    if not state:
        raise HTTPException(status_code=404, detail=f"run_id {run_id} not found")
    return StatusResponse(
        run_id=run_id,
        status=state.get("status", "unknown"),
        score=state.get("score"),
        iteration=state.get("iteration"),
        metric_results=state.get("metric_results"),
        suggestions=state.get("suggestions"),
        pipeline_run_id=state.get("pipeline_run_id"),
        error=state.get("error"),
    )


@router.get("/runs")
async def list_runs(svc: WorkflowService = Depends(get_workflow_service)):
    return {"runs": await svc.list_runs()}


@router.get("/debug/{run_id}")
async def debug_run(run_id: str, svc: WorkflowService = Depends(get_workflow_service)):
    """Raw Redis state for a run — excludes dataframe_json to keep response small."""
    state = await svc.get_status(run_id)
    if not state:
        raise HTTPException(status_code=404, detail=f"run_id {run_id} not found")
    return {k: v for k, v in state.items() if k != "dataframe_json"}
