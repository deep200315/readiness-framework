"""Node: run metric engine on the current DataFrame."""
from __future__ import annotations

import logging
from io import StringIO

import pandas as pd

from agent.workflow_state import WorkflowState
from config import get_config
from metrics.engine import MetricEngine

logger = logging.getLogger(__name__)


def _to_python(obj):
    """Recursively convert numpy scalars to native Python so msgpack can serialize them."""
    try:
        import numpy as np
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            return float(obj)
        if isinstance(obj, np.bool_):
            return bool(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
    except ImportError:
        pass
    if isinstance(obj, dict):
        return {k: _to_python(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_to_python(v) for v in obj]
    return obj


async def run_metrics(state: WorkflowState) -> dict:
    cfg = get_config()
    engine = MetricEngine(cfg)

    df = pd.read_json(StringIO(state["dataframe_json"]), orient="split")
    logger.info("[run_metrics] run_id=%s iteration=%d rows=%d", state["run_id"], state["iteration"], len(df))

    suite = await engine.run(
        df=df,
        run_id=state["run_id"],
        table_ref=state["source_table"],
        usecase=state["usecase"],
        iteration=state["iteration"],
    )

    return {
        "metric_results": _to_python(suite.to_dict()),
        "score": float(suite.overall_score),
        "status": "running",
    }
