"""Databricks SQL + Jobs connector."""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any, Optional

import pandas as pd

logger = logging.getLogger(__name__)

SYSTEM_CATALOGS = {"system", "hive_metastore", "__databricks_internal"}
SYSTEM_SCHEMAS = {"information_schema"}
SOCKET_TIMEOUT = 900


@dataclass
class DatabricksCredentials:
    server_hostname: str
    http_path: str
    access_token: str
    socket_timeout: int = SOCKET_TIMEOUT


class DatabricksConnector:
    """Thread-safe Databricks SQL connector with connection pooling."""

    def __init__(self, credentials: DatabricksCredentials) -> None:
        self._creds = credentials
        self._import_sdk()

    def _import_sdk(self) -> None:
        try:
            import databricks.sql as dsql  # noqa: F401
            self._dsql = dsql
        except ImportError as exc:
            raise ImportError(
                "databricks-sql-connector not installed. Run: pip install databricks-sql-connector"
            ) from exc

    def _connect(self):
        return self._dsql.connect(
            server_hostname=self._creds.server_hostname,
            http_path=self._creds.http_path,
            access_token=self._creds.access_token,
            _socket_timeout=self._creds.socket_timeout,
        )

    def _connect_retry(self, retries: int = 3):
        last_exc: Exception | None = None
        for attempt in range(retries):
            try:
                return self._connect()
            except Exception as exc:
                last_exc = exc
                logger.warning("Databricks connect attempt %d failed: %s", attempt + 1, exc)
        raise RuntimeError(f"Databricks connection failed after {retries} attempts") from last_exc

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------

    def list_tables(self) -> list[str]:
        """Return fully-qualified table names using a single connection."""
        conn = self._connect_retry()
        all_tables: list[str] = []
        try:
            with conn.cursor() as cur:
                cur.execute("SHOW CATALOGS")
                catalogs = [r[0] for r in cur.fetchall() if r[0].lower() not in SYSTEM_CATALOGS]
                for catalog in catalogs:
                    try:
                        cur.execute(f"SHOW SCHEMAS IN `{catalog}`")
                        schemas = [r[0] for r in cur.fetchall() if r[0].lower() not in SYSTEM_SCHEMAS]
                    except Exception:
                        continue
                    for schema in schemas:
                        try:
                            cur.execute(f"SHOW TABLES IN `{catalog}`.`{schema}`")
                            all_tables.extend(f"{catalog}.{schema}.{r[1]}" for r in cur.fetchall())
                        except Exception:
                            continue
        finally:
            try:
                conn.close()
            except Exception:
                pass
        return sorted(all_tables)

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def fetch_table(
        self,
        table_ref: str,
        limit: int = 50_000,
        columns: Optional[list[str]] = None,
    ) -> pd.DataFrame:
        """Fetch up to *limit* rows from *table_ref* ('catalog.schema.table')."""
        col_expr = ", ".join(f"`{c}`" for c in columns) if columns else "*"
        query = f"SELECT {col_expr} FROM {table_ref} LIMIT {limit}"
        logger.info("Fetching: %s", query)
        conn = self._connect_retry()
        try:
            with conn.cursor() as cur:
                cur.execute(query)
                rows = cur.fetchall()
                col_names = [d[0] for d in cur.description]
                return pd.DataFrame(rows, columns=col_names)
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def get_schema(self, table_ref: str) -> list[dict[str, str]]:
        """Return [{name, type}] column metadata."""
        conn = self._connect_retry()
        try:
            with conn.cursor() as cur:
                cur.execute(f"DESCRIBE TABLE {table_ref}")
                return [{"name": r[0], "type": r[1]} for r in cur.fetchall() if r[0] and not r[0].startswith("#")]
        finally:
            try:
                conn.close()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def write_table(
        self,
        df: pd.DataFrame,
        catalog: str,
        schema: str,
        table: str,
        mode: str = "overwrite",
    ) -> None:
        """Write *df* to target table using INSERT (small DataFrames) or stage+COPY."""
        full_ref = f"`{catalog}`.`{schema}`.`{table}`"
        logger.info("Writing %d rows to %s (mode=%s)", len(df), full_ref, mode)
        conn = self._connect_retry()
        try:
            with conn.cursor() as cur:
                if mode == "overwrite":
                    try:
                        cur.execute(f"DROP TABLE IF EXISTS {full_ref}")
                    except Exception:
                        pass
                cols = ", ".join(f"`{c}`" for c in df.columns)
                cur.execute(
                    f"CREATE TABLE IF NOT EXISTS {full_ref} ({', '.join(f'`{c}` STRING' for c in df.columns)})"
                )

                def _escape(v) -> str:
                    if v is None:
                        return "NULL"
                    return "'" + str(v).replace("\\", "\\\\").replace("'", "\\'") + "'"

                rows = [
                    [_escape(v) for v in row]
                    for row in df.itertuples(index=False)
                ]
                batch_size = 500
                for i in range(0, len(rows), batch_size):
                    batch = rows[i : i + batch_size]
                    values_clause = ", ".join(
                        "(" + ", ".join(row_vals) + ")" for row_vals in batch
                    )
                    cur.execute(f"INSERT INTO {full_ref} ({cols}) VALUES {values_clause}")
        finally:
            try:
                conn.close()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Jobs (large-data pipeline path)
    # ------------------------------------------------------------------

    def trigger_job(self, job_id: int, params: dict[str, Any]) -> str:
        """Trigger a Databricks Job run. Returns the run_id string."""
        import json
        import urllib.request

        host = self._creds.server_hostname.rstrip("/")
        url = f"https://{host}/api/2.1/jobs/run-now"
        payload = json.dumps({"job_id": job_id, "notebook_params": params}).encode()
        req = urllib.request.Request(
            url,
            data=payload,
            headers={
                "Authorization": f"Bearer {self._creds.access_token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
        run_id = str(result["run_id"])
        logger.info("Triggered Databricks Job %s → run_id=%s", job_id, run_id)
        return run_id

    def get_job_run_status(self, run_id: str) -> dict[str, Any]:
        """Return life_cycle_state and result_state for a job run."""
        import json
        import urllib.request

        host = self._creds.server_hostname.rstrip("/")
        url = f"https://{host}/api/2.1/jobs/runs/get?run_id={run_id}"
        req = urllib.request.Request(
            url,
            headers={"Authorization": f"Bearer {self._creds.access_token}"},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
        state = data.get("state", {})
        return {
            "run_id": run_id,
            "life_cycle_state": state.get("life_cycle_state", "UNKNOWN"),
            "result_state": state.get("result_state"),
            "state_message": state.get("state_message", ""),
        }


def connector_from_config(cfg: dict) -> DatabricksConnector:
    db_cfg = cfg["databricks"]
    creds = DatabricksCredentials(
        server_hostname=db_cfg["server_hostname"],
        http_path=db_cfg["http_path"],
        access_token=db_cfg.get("access_token", ""),
        socket_timeout=int(db_cfg.get("socket_timeout", SOCKET_TIMEOUT)),
    )
    return DatabricksConnector(creds)
