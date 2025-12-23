#!/usr/bin/env python
"""Common helpers shared across experiment entrypoints."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any, Dict, List


def load_module_from_path(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load config module from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore
    return module


def parse_params_from_strings(items: List[str]) -> Dict[str, Any]:
    params: Dict[str, Any] = {}
    for it in items:
        if "=" not in it:
            continue
        k, v = it.split("=", 1)
        try:
            params[k] = json.loads(v)
        except Exception:
            params[k] = v
    return params
