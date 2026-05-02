import json
import logging
from time import time

from fastapi import APIRouter, Depends
from backend.api.deps import get_workflow_service
from backend.models.workflow import RunChecksRequest, RunChecksResponse, ListTablesResponse
from backend.services.workflow_service import WorkflowService
from config import get_config
from connectors.databricks import connector_from_config

logger = logging.getLogger(__name__)
router = APIRouter()

# Simple in-process TTL cache for table list (avoids repeated Databricks scans)
_tables_cache: tuple[float, list[str]] = (0.0, [])
_TABLES_TTL = 300  # 5 minutes


@router.post("/run-checks", response_model=RunChecksResponse)
async def run_checks(body: RunChecksRequest, svc: WorkflowService = Depends(get_workflow_service)):
    run_id = await svc.start_run(source_table=body.source_table, usecase=body.usecase)
    return RunChecksResponse(run_id=run_id, status="running", message="Workflow started")


@router.get("/tables", response_model=ListTablesResponse)
async def list_tables(refresh: bool = False):
    global _tables_cache
    age = time() - _tables_cache[0]

    if not refresh and age < _TABLES_TTL and _tables_cache[1]:
        logger.info("[tables] serving from cache (age=%.0fs)", age)
        return ListTablesResponse(tables=_tables_cache[1])

    cfg = get_config()
    connector = connector_from_config(cfg)
    tables = connector.list_tables()
    _tables_cache = (time(), tables)
    logger.info("[tables] refreshed cache — %d tables found", len(tables))
    return ListTablesResponse(tables=tables)


@router.get("/preview/{catalog}/{schema}/{table}")
async def preview_table(catalog: str, schema: str, table: str):
    """Return schema, 5 sample rows, and an AI-suggested usecase.
    GPT-4o only receives column names + types (not sample values) to minimise tokens.
    """
    from openai import AzureOpenAI

    cfg = get_config()
    connector = connector_from_config(cfg)
    table_ref = f"{catalog}.{schema}.{table}"

    # Single connection: get schema then fetch 5 rows
    schema_info = connector.get_schema(table_ref)
    sample_df = connector.fetch_table(table_ref, limit=5)
    sample_rows = sample_df.to_dict(orient="records")

    # Build a compact schema string — column name + type only, no sample values
    # This cuts input tokens from ~500-1500 down to ~100-200 for typical tables
    compact_schema = ", ".join(f"{c['name']} ({c['type']})" for c in schema_info)

    oai_cfg = cfg["azure_openai"]
    client = AzureOpenAI(
        api_version=oai_cfg["api_version"],
        azure_endpoint=oai_cfg["endpoint"],
        api_key=oai_cfg["key"],
    )

    prompt = (
        f"Table name: {table_ref}\n"
        f"Columns: {compact_schema}\n\n"
        "Write 2-3 sentences describing SPECIFICALLY what this table contains and "
        "its most likely business use case (e.g. customer churn prediction, sales "
        "forecasting, fraud detection, inventory analysis). "
        "Reference the actual column names to make it specific. "
        "Reply with ONLY the description, no preamble."
    )

    try:
        response = client.chat.completions.create(
            model=oai_cfg["deployment"],
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200,
            temperature=0.4,
        )
        suggested_usecase = response.choices[0].message.content.strip()
        usage = response.usage
        logger.info(
            "[preview] GPT-4o tokens — input: %d, output: %d, total: %d | table: %s",
            usage.prompt_tokens,
            usage.completion_tokens,
            usage.total_tokens,
            table_ref,
        )
    except Exception as exc:
        logger.warning("[preview] GPT-4o call failed: %s", exc)
        suggested_usecase = f"General data quality evaluation for {table_ref}"

    return {
        "table_ref": table_ref,
        "schema": schema_info,
        "sample_rows": sample_rows,
        "suggested_usecase": suggested_usecase,
    }
