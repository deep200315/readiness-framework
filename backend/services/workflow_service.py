"""Bridge between FastAPI and LangGraph agent."""
from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any

from agent.graph import compiled_graph
from agent.workflow_state import WorkflowState
from backend.db.state_store import StateStore

logger = logging.getLogger(__name__)


def _initial_state(run_id: str, source_table: str, usecase: str) -> WorkflowState:
    return WorkflowState(
        run_id=run_id,
        source_table=source_table,
        usecase=usecase,
        dataframe_json="",
        local_parquet_path="",
        metric_results={},
        score=0.0,
        iteration=0,
        suggestions=[],
        approval_status="pending",
        pipeline_run_id="",
        pipeline_status={},
        status="running",
        error=None,
    )


class WorkflowService:
    def __init__(self, store: StateStore) -> None:
        self._store = store

    async def start_run(self, source_table: str, usecase: str) -> str:
        run_id = uuid.uuid4().hex
        state = _initial_state(run_id, source_table, usecase)
        config = {"configurable": {"thread_id": run_id}}

        await self._store.set(run_id, {"run_id": run_id, "status": "running", "score": 0.0, "iteration": 0})
        logger.info("▶ run_id=%s STARTED table=%s", run_id, source_table)

        asyncio.create_task(self._run_graph(run_id, state, config))
        return run_id

    async def _run_graph(self, run_id: str, state: WorkflowState, config: dict) -> None:
        logger.info("⚙ run_id=%s graph execution BEGIN", run_id)
        try:
            async for event in compiled_graph.astream(state, config=config):
                if not event:
                    continue
                node_name = list(event.keys())[0]
                node_output: dict[str, Any] = list(event.values())[0] or {}
                patch = {k: v for k, v in node_output.items() if k not in ("dataframe_json",)}
                await self._store.update(run_id, patch)
                logger.info(
                    "⚙ run_id=%s NODE=%-35s status=%-30s score=%s",
                    run_id,
                    node_name,
                    patch.get("status", "—"),
                    patch.get("score", "—"),
                )
        except Exception as exc:
            logger.exception("❌ run_id=%s graph CRASHED: %s", run_id, exc)
            await self._store.update(run_id, {"status": "failed:error", "error": str(exc)})
        else:
            logger.info("✅ run_id=%s graph execution END", run_id)

    async def approve_step(self, run_id: str, decision: str, checkpoint: str) -> None:
        config = {"configurable": {"thread_id": run_id}}
        node_name = f"await_approval_{checkpoint.replace('_result', '')}"
        compiled_graph.update_state(config, {"approval_status": decision}, as_node=node_name)
        logger.info("👤 run_id=%s APPROVAL checkpoint=%s decision=%s", run_id, checkpoint, decision)
        asyncio.create_task(self._resume_graph(run_id, config))
        await self._store.update(run_id, {"approval_status": decision, "status": "running"})

    async def _resume_graph(self, run_id: str, config: dict) -> None:
        logger.info("⚙ run_id=%s graph RESUMED", run_id)
        try:
            async for event in compiled_graph.astream(None, config=config):
                if not event:
                    continue
                node_name = list(event.keys())[0]
                node_output: dict[str, Any] = list(event.values())[0] or {}
                patch = {k: v for k, v in node_output.items() if k not in ("dataframe_json",)}
                await self._store.update(run_id, patch)
                logger.info(
                    "⚙ run_id=%s NODE=%-35s status=%-30s score=%s",
                    run_id,
                    node_name,
                    patch.get("status", "—"),
                    patch.get("score", "—"),
                )
        except Exception as exc:
            logger.exception("❌ run_id=%s resume CRASHED: %s", run_id, exc)
            await self._store.update(run_id, {"status": "failed:error", "error": str(exc)})

    async def get_status(self, run_id: str) -> dict | None:
        return await self._store.get(run_id)

    async def list_runs(self) -> list[str]:
        return await self._store.list_runs()
