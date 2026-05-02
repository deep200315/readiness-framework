from fastapi import APIRouter, Depends, HTTPException
from backend.api.deps import get_workflow_service
from backend.models.workflow import TriggerPipelineRequest, TriggerPipelineResponse
from backend.services.workflow_service import WorkflowService

router = APIRouter()


@router.post("/trigger-pipeline", response_model=TriggerPipelineResponse)
async def trigger_pipeline(body: TriggerPipelineRequest, svc: WorkflowService = Depends(get_workflow_service)):
    state = await svc.get_status(body.run_id)
    if not state:
        raise HTTPException(status_code=404, detail=f"run_id {body.run_id} not found")
    # Pipeline triggering is handled automatically by the graph after approval;
    # this endpoint is a manual override for external orchestrators.
    await svc.approve_step(body.run_id, "approved", "suggestions")
    return TriggerPipelineResponse(
        run_id=body.run_id,
        pipeline_run_id=state.get("pipeline_run_id", ""),
        status="triggered",
    )
