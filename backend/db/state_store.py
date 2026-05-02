"""Redis-backed run state store."""
from __future__ import annotations

import json
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


class _SafeEncoder(json.JSONEncoder):
    def default(self, obj):
        try:
            import numpy as np
            if isinstance(obj, (np.bool_, np.integer, np.floating)):
                return obj.item()
        except ImportError:
            pass
        if isinstance(obj, bool):
            return bool(obj)
        return super().default(obj)


class StateStore:
    def __init__(self, redis_url: str, ttl: int = 86400) -> None:
        import redis.asyncio as aioredis
        self._client = aioredis.from_url(redis_url, decode_responses=True)
        self._ttl = ttl

    async def set(self, run_id: str, data: dict[str, Any]) -> None:
        key = f"run:{run_id}"
        await self._client.set(key, json.dumps(data, cls=_SafeEncoder), ex=self._ttl)

    async def get(self, run_id: str) -> Optional[dict[str, Any]]:
        key = f"run:{run_id}"
        raw = await self._client.get(key)
        return json.loads(raw) if raw else None

    async def update(self, run_id: str, patch: dict[str, Any]) -> None:
        existing = await self.get(run_id) or {}
        existing.update(patch)
        await self.set(run_id, existing)

    async def delete(self, run_id: str) -> None:
        await self._client.delete(f"run:{run_id}")

    async def list_runs(self, limit: int = 100) -> list[str]:
        keys = await self._client.keys("run:*")
        return [k.removeprefix("run:") for k in keys[:limit]]

    async def ping(self) -> bool:
        try:
            return await self._client.ping()
        except Exception:
            return False
