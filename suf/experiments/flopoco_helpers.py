#!/usr/bin/env python
"""Flopoco-specific helpers for experiment entrypoints."""
from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

from .flow_helpers_common import load_module_from_path, parse_params_from_strings


@dataclass
class DesignSpec:
    name: str
    operator: str
    params: Dict[str, Any]
    args: List[str]
    meta: Dict[str, Any]


def resolve_flopoco_bin(allow_missing: bool) -> str:
    path = os.environ.get("SUF_FLOPOCO_BIN")
    if path and Path(path).expanduser().exists():
        return str(Path(path).expanduser())
    if allow_missing:
        return "flopoco"
    raise RuntimeError("Flopoco binary not found. Export SUF_FLOPOCO_BIN before running.")


def resolve_vh2v_bin(allow_missing: bool) -> str:
    path = os.environ.get("SUF_VH2V_BIN")
    if path and Path(path).expanduser().exists():
        return str(Path(path).expanduser())
    if allow_missing:
        return "vh2v.py"
    raise RuntimeError("vh2v script not found. Export SUF_VH2V_BIN before running.")


def load_designs(config_path: Path) -> List[DesignSpec]:
    module = load_module_from_path(config_path)
    data = getattr(module, "DESIGNS", getattr(module, "CONFIGS", None))
    if data is None:
        raise ValueError("Config module must define DESIGNS (list or dict).")

    designs: List[DesignSpec] = []
    if isinstance(data, dict):
        for name, entry in data.items():
            if isinstance(entry, (list, tuple)) and len(entry) >= 1:
                operator = entry[0]
                params = parse_params_from_strings(list(entry[1:]))
                designs.append(DesignSpec(name, operator, params, [], {}))
            elif isinstance(entry, dict):
                operator = entry.get("operator")
                if not operator:
                    raise ValueError(f"Entry {name} missing 'operator'")
                params = entry.get("params", {})
                args = entry.get("args", [])
                meta = {k: v for k, v in entry.items() if k not in {"operator", "params", "args"}}
                designs.append(DesignSpec(name, operator, params, args, meta))
            else:
                raise ValueError(f"Unsupported entry type for {name}")
        return designs

    if not isinstance(data, list):
        raise ValueError("DESIGNS must be a list or dict.")

    for entry in data:
        if isinstance(entry, (list, tuple)) and len(entry) >= 2:
            name = str(entry[0])
            operator = str(entry[1])
            params = parse_params_from_strings(list(entry[2:]))
            designs.append(DesignSpec(name, operator, params, [], {}))
        elif isinstance(entry, dict):
            if "name" not in entry or "operator" not in entry:
                raise ValueError("Dict entries require 'name' and 'operator'.")
            params = entry.get("params") or {}
            args = entry.get("args") or []
            meta = {k: v for k, v in entry.items() if k not in {"name", "operator", "params", "args"}}
            designs.append(DesignSpec(entry["name"], entry["operator"], params, args, meta))
        else:
            raise ValueError("Each list entry must be a tuple/list or dict.")
    return designs


def load_performance(config_path: Path) -> Dict[str, Any]:
    module = load_module_from_path(config_path)
    data = getattr(module, "PERFORMANCE", None)
    if not isinstance(data, dict):
        raise ValueError("Performance module must define PERFORMANCE as a dict.")
    return data


def parse_pdks(perf: Dict[str, Any]) -> tuple[List[str], Dict[str, Dict[str, Any]]]:
    pdks = perf.get("pdks", [])
    if not isinstance(pdks, list):
        raise ValueError("PERFORMANCE['pdks'] must be a list.")
    names: List[str] = []
    meta: Dict[str, Dict[str, Any]] = {}
    for entry in pdks:
        if isinstance(entry, str):
            names.append(entry)
            meta[entry] = {}
        elif isinstance(entry, dict):
            name = entry.get("name")
            if not name:
                raise ValueError("PDK entries must include a 'name' field.")
            names.append(name)
            meta[name] = {k: v for k, v in entry.items() if k != "name"}
        else:
            raise ValueError("PDK entries must be strings or dicts.")
    return names, meta


def sync_translated_sources(src_dir: Path, dest_dir: Path, dry_run: bool) -> None:
    if dry_run:
        return
    dest_dir.mkdir(parents=True, exist_ok=True)
    for item in src_dir.glob("*.v"):
        shutil.copy2(item, dest_dir / item.name)


def flopoco_command(bin_path: str, spec: DesignSpec, vhdl_out: Path) -> List[str]:
    cmd = [bin_path, spec.operator]
    for k, v in spec.params.items():
        if isinstance(v, bool):
            if v:
                cmd.append(str(k))
            continue
        cmd.append(f"{k}={v}")
    for arg in spec.args:
        cmd.append(str(arg))
    if not any(a.startswith("name=") for a in cmd):
        cmd.append(f"name={spec.name}")
    cmd.append(f"outputFile={vhdl_out}")
    return cmd


def run_flopoco(bin_path: str, spec: DesignSpec, vhdl_out: Path, dry_run: bool, verbose: bool) -> None:
    cmd = flopoco_command(bin_path, spec, vhdl_out)
    if dry_run:
        return
    proc = subprocess.run(
        cmd,
        check=False,
        capture_output=not verbose,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"Flopoco failed for {spec.name}: {proc.stdout or proc.stderr}")


def translate_vhdl(vh2v_bin: str, vhdl_path: Path, out_dir: Path, dry_run: bool, verbose: bool) -> None:
    cmd = ["python", vh2v_bin, "--input_file", str(vhdl_path), "--output_dir", str(out_dir)]
    if dry_run:
        return
    proc = subprocess.run(
        cmd,
        check=False,
        capture_output=not verbose,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"vh2v failed for {vhdl_path.name}: {proc.stdout or proc.stderr}")
