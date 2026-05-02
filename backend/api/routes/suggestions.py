from fastapi import APIRouter, Depends, HTTPException
from backend.api.deps import get_workflow_service
from backend.models.workflow import SuggestionsResponse
from backend.services.workflow_service import WorkflowService

router = APIRouter()


@router.get("/agent-suggestions/{run_id}", response_model=SuggestionsResponse)
async def get_suggestions(run_id: str, svc: WorkflowService = Depends(get_workflow_service)):
    state = await svc.get_status(run_id)
    if not state:
        raise HTTPException(status_code=404, detail=f"run_id {run_id} not found")
    return SuggestionsResponse(
        run_id=run_id,
        suggestions=state.get("suggestions", []),
        score=state.get("score", 0.0),
        metric_results=state.get("metric_results", {}),
    )
