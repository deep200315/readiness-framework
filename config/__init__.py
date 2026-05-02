from __future__ import annotations

import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

load_dotenv()

_CONFIG_PATH = Path(__file__).parent / "config.yaml"


def _expand_env(value: Any) -> Any:
    """Recursively expand ${VAR} and ${VAR:-default} in string values."""
    if isinstance(value, str):
        def _sub(m: re.Match) -> str:
            var, _, default = m.group(1).partition(":-")
            return os.environ.get(var, default)
        return re.sub(r"\$\{([^}]+)\}", _sub, value)
    if isinstance(value, dict):
        return {k: _expand_env(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_expand_env(i) for i in value]
    return value


@lru_cache(maxsize=1)
def get_config() -> dict:
    with open(_CONFIG_PATH) as f:
        raw = yaml.safe_load(f)
    return _expand_env(raw)
