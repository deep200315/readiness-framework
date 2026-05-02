"""Node: use Azure OpenAI GPT-4o to generate actionable fix suggestions."""
from __future__ import annotations

import json
import logging

from agent.workflow_state import WorkflowState
from config import get_config
from pipelines.transformations import list_available

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are a senior data engineer specializing in data quality remediation.
Given metric failures and the data usecase, produce a JSON list of actionable fixes.

Each fix must follow this schema:
{{
  "type": "<category: metadata|quality|governance|fairness>",
  "description": "<plain-English explanation of what this fix does and why>",
  "transform_fn_name": "<one of the available transform names>",
  "params": {{ <optional keyword args for the transform> }},
  "expected_score_improvement": <float 0.0-2.0 estimated score delta>
}}

Available transform names: {transforms}

Rules:
- Only recommend transforms from the available list.
- Params must match what the transform expects (see descriptions).
- Order fixes from highest to lowest expected_score_improvement.
- Return ONLY a JSON array, no prose, no markdown fences.
"""


async def generate_suggestions(state: WorkflowState) -> dict:
    cfg = get_config()
    oai_cfg = cfg["azure_openai"]

    failures_by_category: dict[str, list[str]] = {}
    for cat, cat_data in state["metric_results"].get("categories", {}).items():
        if cat_data.get("failures"):
            failures_by_category[cat] = cat_data["failures"]

    available_transforms = list_available()

    user_message = json.dumps({
        "usecase": state["usecase"],
        "overall_score": state["score"],
        "failures": failures_by_category,
        "iteration": state["iteration"],
    }, indent=2)

    system = _SYSTEM_PROMPT.format(transforms=", ".join(available_transforms))

    from openai import AzureOpenAI
    client = AzureOpenAI(
        api_version=oai_cfg["api_version"],
        azure_endpoint=oai_cfg["endpoint"],
        api_key=oai_cfg["key"],
    )

    response = client.chat.completions.create(
        model=oai_cfg["deployment"],
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_message},
        ],
        max_tokens=int(oai_cfg.get("max_tokens", 2048)),
        temperature=float(oai_cfg.get("temperature", 0.2)),
    )

    usage = response.usage
    logger.info(
        "[generate_suggestions] GPT-4o tokens — input: %d, output: %d, total: %d | run_id: %s iteration: %d",
        usage.prompt_tokens,
        usage.completion_tokens,
        usage.total_tokens,
        state["run_id"],
        state["iteration"],
    )

    raw = response.choices[0].message.content.strip()
    try:
        suggestions = json.loads(raw)
        if not isinstance(suggestions, list):
            suggestions = [suggestions]
    except json.JSONDecodeError:
        logger.warning("[generate_suggestions] GPT-4o returned non-JSON; wrapping: %s", raw[:200])
        suggestions = [{"type": "quality", "description": raw, "transform_fn_name": None, "params": {}, "expected_score_improvement": 0.0}]

    logger.info("[generate_suggestions] run_id=%s generated %d suggestions", state["run_id"], len(suggestions))
    return {
        "suggestions": suggestions,
        "status": "awaiting_approval_suggestions",
        "approval_status": "pending",
    }
