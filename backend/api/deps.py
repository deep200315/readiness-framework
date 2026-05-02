from __future__ import annotations
from fastapi import Request
from backend.services.workflow_service import WorkflowService


def get_workflow_service(request: Request) -> WorkflowService:
    return request.app.state.workflow_service
