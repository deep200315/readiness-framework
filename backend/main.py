"""FastAPI application entry point."""
from __future__ import annotations

import logging
import logging.handlers
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes import checks, approvals, suggestions, status, pipeline
from backend.db.state_store import StateStore
from backend.services.workflow_service import WorkflowService
from config import get_config

# ---------------------------------------------------------------------------
# Logging: console + rotating file (logs/logs.log)
# ---------------------------------------------------------------------------
_LOG_FORMAT = "%(asctime)s %(levelname)-8s %(name)s — %(message)s"
_LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
_LOG_DIR.mkdir(exist_ok=True)

_file_handler = logging.handlers.RotatingFileHandler(
    _LOG_DIR / "logs.log",
    maxBytes=20 * 1024 * 1024,   # 20 MB per file
    backupCount=10,               # keep up to 10 rotated files
    encoding="utf-8",
    delay=False,
)
_file_handler.setFormatter(logging.Formatter(_LOG_FORMAT))
_file_handler.setLevel(logging.DEBUG)

_console_handler = logging.StreamHandler()
_console_handler.setFormatter(logging.Formatter(_LOG_FORMAT))
_console_handler.setLevel(logging.INFO)

logging.root.setLevel(logging.DEBUG)
logging.root.addHandler(_file_handler)
logging.root.addHandler(_console_handler)

# Silence noisy third-party loggers in the file (still visible in console at INFO)
for _noisy in ("databricks.sql", "presidio-analyzer", "httpcore", "httpx", "urllib3"):
    logging.getLogger(_noisy).setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    cfg = get_config()
    redis_url = cfg["state"]["redis_url"]
    ttl = int(cfg["state"].get("run_ttl_seconds", 86400))
    store = StateStore(redis_url=redis_url, ttl=ttl)
    if not await store.ping():
        logger.warning("Redis not reachable at %s — state will not persist across restarts", redis_url)
    app.state.workflow_service = WorkflowService(store)
    logger.info("Data Readiness Agent API started")
    yield
    logger.info("Shutting down")


app = FastAPI(
    title="Data Readiness Agent API",
    version="1.0.0",
    description="AI-driven data quality agent with human-in-the-loop approvals",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(checks.router, tags=["Checks"])
app.include_router(approvals.router, tags=["Approvals"])
app.include_router(suggestions.router, tags=["Suggestions"])
app.include_router(status.router, tags=["Status"])
app.include_router(pipeline.router, tags=["Pipeline"])


@app.get("/health")
async def health():
    return {"status": "ok"}
