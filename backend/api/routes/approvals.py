from fastapi import APIRouter, Depends, HTTPException
from backend.api.deps import get_workflow_service
from backend.models.workflow import ApproveStepRequest, ApproveStepResponse
from backend.services.workflow_service import WorkflowService

router = APIRouter()


@router.post("/approve-step", response_model=ApproveStepResponse)
async def approve_step(body: ApproveStepRequest, svc: WorkflowService = Depends(get_workflow_service)):
    if body.decision not in ("approved", "rejected"):
        raise HTTPException(status_code=400, detail="decision must be 'approved' or 'rejected'")
    await svc.approve_step(body.run_id, body.decision, body.checkpoint)
    return ApproveStepResponse(run_id=body.run_id, status="resuming" if body.decision == "approved" else "rejected")
