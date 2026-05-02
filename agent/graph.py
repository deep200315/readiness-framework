"""LangGraph StateGraph for the data quality workflow."""
from __future__ import annotations

import logging
from typing import Literal

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from agent.workflow_state import WorkflowState
from agent.nodes.fetch_data import fetch_data
from agent.nodes.run_metrics import run_metrics
from agent.nodes.generate_suggestions import generate_suggestions
from agent.nodes.trigger_pipeline import push_to_target, trigger_pipeline
from config import get_config

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Interrupt nodes (human-in-the-loop checkpoints)
# ---------------------------------------------------------------------------

async def await_approval_suggestions(state: WorkflowState) -> dict:
    """Pause and wait for human to approve/reject fix suggestions."""
    decision = interrupt(
        {
            "type": "approval_request",
            "checkpoint": "suggestions",
            "run_id": state["run_id"],
            "score": state["score"],
            "suggestions": state["suggestions"],
            "metric_results": state["metric_results"],
        }
    )
    # decision injected by FastAPI via graph.update_state()
    status = "running" if decision == "approved" else "failed"
    return {"approval_status": decision, "status": status}


async def await_approval_pipeline(state: WorkflowState) -> dict:
    """Pause after pipeline completes; show sample data before re-running metrics."""
    decision = interrupt(
        {
            "type": "approval_request",
            "checkpoint": "pipeline_result",
            "run_id": state["run_id"],
            "pipeline_run_id": state.get("pipeline_run_id"),
        }
    )
    status = "running" if decision == "approved" else "failed"
    return {"approval_status": decision, "status": status}


# ---------------------------------------------------------------------------
# Routing functions
# ---------------------------------------------------------------------------

def route_after_metrics(state: WorkflowState) -> Literal["push_to_target", "generate_suggestions", "end_failed"]:
    cfg = get_config()
    max_iter = int(cfg["metrics"].get("max_iterations", 5))
    if state["score"] >= float(cfg["metrics"]["passing_threshold"]):
        return "push_to_target"
    if state["iteration"] >= max_iter:
        logger.warning("run_id=%s exceeded max_iterations=%d", state["run_id"], max_iter)
        return "end_failed"
    return "generate_suggestions"


def route_after_suggestions_approval(state: WorkflowState) -> Literal["trigger_pipeline", "end_failed"]:
    return "trigger_pipeline" if state["approval_status"] == "approved" else "end_failed"


def route_after_pipeline_approval(state: WorkflowState) -> Literal["run_metrics", "end_failed"]:
    return "run_metrics" if state["approval_status"] == "approved" else "end_failed"


async def increment_iteration(state: WorkflowState) -> dict:
    return {"iteration": state["iteration"] + 1}


async def end_failed(state: WorkflowState) -> dict:
    reason = "rejected" if state["approval_status"] == "rejected" else "max_retries_exceeded"
    return {"status": f"failed:{reason}"}


# ---------------------------------------------------------------------------
# Graph assembly
# ---------------------------------------------------------------------------

def build_graph() -> StateGraph:
    graph = StateGraph(WorkflowState)

    graph.add_node("fetch_data", fetch_data)
    graph.add_node("run_metrics", run_metrics)
    graph.add_node("generate_suggestions", generate_suggestions)
    graph.add_node("await_approval_suggestions", await_approval_suggestions)
    graph.add_node("trigger_pipeline", trigger_pipeline)
    graph.add_node("await_approval_pipeline", await_approval_pipeline)
    graph.add_node("increment_iteration", increment_iteration)
    graph.add_node("push_to_target", push_to_target)
    graph.add_node("end_failed", end_failed)

    graph.add_edge(START, "fetch_data")
    graph.add_edge("fetch_data", "run_metrics")
    graph.add_conditional_edges(
        "run_metrics",
        route_after_metrics,
        {
            "push_to_target": "push_to_target",
            "generate_suggestions": "generate_suggestions",
            "end_failed": "end_failed",
        },
    )
    graph.add_edge("generate_suggestions", "await_approval_suggestions")
    graph.add_conditional_edges(
        "await_approval_suggestions",
        route_after_suggestions_approval,
        {
            "trigger_pipeline": "trigger_pipeline",
            "end_failed": "end_failed",
        },
    )
    graph.add_edge("trigger_pipeline", "await_approval_pipeline")
    graph.add_conditional_edges(
        "await_approval_pipeline",
        route_after_pipeline_approval,
        {
            "run_metrics": "increment_iteration",
            "end_failed": "end_failed",
        },
    )
    graph.add_edge("increment_iteration", "run_metrics")
    graph.add_edge("push_to_target", END)
    graph.add_edge("end_failed", END)

    return graph


_checkpointer = MemorySaver()
compiled_graph = build_graph().compile(checkpointer=_checkpointer, interrupt_before=["await_approval_suggestions", "await_approval_pipeline"])
