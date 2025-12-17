#!/usr/bin/env python
"""
Lightweight helpers shared by SUF experiment tooling.

This package is intentionally minimal; import the individual modules you need.
"""

from pathlib import Path
import os
import shutil


def _env_path(key: str) -> Path | None:
    val = os.environ.get(key)
    if not val:
        return None
    return Path(val).expanduser().resolve()


def _first_existing(paths: list[Path | str | None]) -> Path | None:
    """Return the first existing path from a list of candidates."""
    for candidate in paths:
        if not candidate:
            continue
        path = Path(candidate).expanduser().resolve()
        if path.exists():
            return path
    return None


# Repository anchors
REPO_ROOT = Path(__file__).resolve().parents[1]

# Allow overriding the OpenROAD flow location (external checkout) via env.
# SUF now expects an existing OpenROAD-flow-scripts checkout to be provided.
# Preference order:
#   1) SUF_FLOW_ROOT env
#   2) FLOW_HOME env (commonly exported by OpenROAD-flow-scripts setup)
_flow_candidates = [
    _env_path("SUF_FLOW_ROOT"),
    _env_path("FLOW_HOME"),
]
FLOW_ROOT = _first_existing(_flow_candidates)
if FLOW_ROOT is None:
    raise RuntimeError(
        "Unable to locate OpenROAD-flow-scripts. Set SUF_FLOW_ROOT or FLOW_HOME to an existing flow checkout."
    )

_translation_candidates = [
    _env_path("SUF_TRANSLATION_ROOT"),
]
TRANSLATION_ROOT = _first_existing(_translation_candidates)

GRAFT_ROAD_ROOT = REPO_ROOT / "graft_road"

# Optional external tool overrides
_openroad_candidates = [
    os.environ.get("SUF_OPENROAD_EXE"),
    os.environ.get("OPENROAD_EXE"),
    FLOW_ROOT.parent / "tools" / "install" / "OpenROAD" / "bin" / "openroad",
    shutil.which("openroad"),
]
OPENROAD_EXE = next((str(p) for p in _openroad_candidates if p and Path(p).exists()), None)

_yosys_candidates = [
    os.environ.get("SUF_YOSYS_CMD"),
    os.environ.get("YOSYS_CMD"),
    FLOW_ROOT.parent / "tools" / "install" / "yosys" / "bin" / "yosys",
    shutil.which("yosys"),
]
YOSYS_CMD = next((str(p) for p in _yosys_candidates if p and Path(p).exists()), None)

_vh2v_candidates = [
    os.environ.get("SUF_VH2V_BIN"),
    os.environ.get("VH2V_BIN"),
    TRANSLATION_ROOT / "vh2v" / "vh2v.py" if TRANSLATION_ROOT else None,
]
VH2V_BIN = next((str(p) for p in _vh2v_candidates if p and Path(p).exists()), None)

__all__ = [
    "REPO_ROOT",
    "FLOW_ROOT",
    "GRAFT_ROAD_ROOT",
    "OPENROAD_EXE",
    "YOSYS_CMD",
    "TRANSLATION_ROOT",
    "VH2V_BIN",
]
