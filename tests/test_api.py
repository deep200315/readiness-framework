"""Integration tests for FastAPI endpoints (requires mock state store)."""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.main import app


@pytest.fixture
def mock_workflow_service():
    svc = AsyncMock()
    svc.start_run.return_value = "test-run-abc"
    svc.get_status.return_value = {
        "run_id": "test-run-abc",
        "status": "running",
        "score": 7.5,
        "iteration": 1,
        "metric_results": {},
        "suggestions": [],
        "pipeline_run_id": "",
        "error": None,
    }
    svc.approve_step.return_value = None
    return svc


@pytest.fixture
def client(mock_workflow_service):
    app.state.workflow_service = mock_workflow_service
    return TestClient(app)


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_run_checks(client):
    resp = client.post("/run-checks", json={"source_table": "cat.sch.tbl", "usecase": "test"})
    assert resp.status_code == 200
    assert resp.json()["run_id"] == "test-run-abc"


def test_get_status(client):
    resp = client.get("/status/test-run-abc")
    assert resp.status_code == 200
    data = resp.json()
    assert data["run_id"] == "test-run-abc"
    assert data["score"] == 7.5


def test_approve_step(client):
    resp = client.post("/approve-step", json={
        "run_id": "test-run-abc",
        "decision": "approved",
        "checkpoint": "suggestions",
    })
    assert resp.status_code == 200


def test_approve_step_bad_decision(client):
    resp = client.post("/approve-step", json={
        "run_id": "test-run-abc",
        "decision": "maybe",
        "checkpoint": "suggestions",
    })
    assert resp.status_code == 400
