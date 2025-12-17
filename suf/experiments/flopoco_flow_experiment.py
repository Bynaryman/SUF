#!/usr/bin/env python
"""Run Flopoco-generated designs through the OpenROAD flow."""
from __future__ import annotations

import argparse
import importlib.util
import json
import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

THIS_FILE = Path(__file__).resolve()
REPO_ROOT = THIS_FILE.parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from suf import FLOW_ROOT, VH2V_BIN  # noqa: E402
try:  # noqa: E402
    from . import simple_flow_helpers as helpers  # type: ignore
except Exception:  # noqa: E402
    import suf.experiments.simple_flow_helpers as helpers  # type: ignore
from graft_road.libs.scenario import Scenario  # noqa: E402

LOG = logging.getLogger(__name__)


@dataclass
class DesignSpec:
    name: str
    operator: str
    params: Dict[str, Any]
    args: List[str]
    meta: Dict[str, Any]


def _resolve_flopoco_bin(allow_missing: bool) -> str:
    candidates = [
        os.environ.get("SUF_FLOPOCO_BIN"),
        os.environ.get("FLOPOCO_BIN"),
    ]
    try:
        from graft_road.config import FLOPOCO_BIN  # type: ignore

        candidates.append(str(FLOPOCO_BIN))
    except Exception:
        pass
    for cand in candidates:
        if cand and Path(cand).expanduser().exists():
            return str(Path(cand).expanduser())
    if allow_missing:
        return "flopoco"
    raise RuntimeError("Flopoco binary not found. Set --flopoco-bin or SUF_FLOPOCO_BIN/FLOPOCO_BIN to a valid path.")


def _resolve_vh2v_bin(cli_bin: str | None, allow_missing: bool) -> str:
    candidates = [
        os.environ.get("SUF_VH2V_BIN"),
        os.environ.get("VH2V_BIN"),
        VH2V_BIN,
    ]
    for cand in candidates:
        if cand and Path(cand).expanduser().exists():
            return str(Path(cand).expanduser())
    if allow_missing:
        return "vh2v.py"
    raise RuntimeError("vh2v script not found. Set --vh2v-bin or SUF_VH2V_BIN/VH2V_BIN.")


def _load_module_from_path(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load config module from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore
    return module


def _parse_params_from_strings(items: List[str]) -> Dict[str, Any]:
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


def load_designs(config_path: Path) -> List[DesignSpec]:
    module = _load_module_from_path(config_path)
    data = getattr(module, "DESIGNS", getattr(module, "CONFIGS", None))
    if data is None:
        raise ValueError("Config module must define DESIGNS (list or dict).")

    designs: List[DesignSpec] = []
    if isinstance(data, dict):
        for name, entry in data.items():
            if isinstance(entry, (list, tuple)) and len(entry) >= 1:
                operator = entry[0]
                params = _parse_params_from_strings(list(entry[1:]))
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
            params = _parse_params_from_strings(list(entry[2:]))
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
    LOG.info("Generating with Flopoco: %s", " ".join(cmd))
    if dry_run:
        return
    proc = helpers.subprocess.run(
        cmd,
        check=False,
        capture_output=not verbose,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"Flopoco failed for {spec.name}: {proc.stdout or proc.stderr}")


def translate_vhdl(vh2v_bin: str, vhdl_path: Path, out_dir: Path, dry_run: bool, verbose: bool) -> None:
    cmd = ["python", vh2v_bin, "--input_file", str(vhdl_path), "--output_dir", str(out_dir)]
    LOG.info("Translating VHDL→Verilog: %s", " ".join(cmd))
    if dry_run:
        return
    proc = helpers.subprocess.run(
        cmd,
        check=False,
        capture_output=not verbose,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"vh2v failed for {vhdl_path.name}: {proc.stdout or proc.stderr}")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Run Flopoco-generated designs through OpenROAD.")
    p.add_argument("--config-file", required=True, help="Python file defining DESIGNS (list or dict of specs).")
    p.add_argument("--experiment", default="flopoco", help="Experiment namespace under designs/ (default: flopoco)")
    p.add_argument("--pdks", nargs="+", default=["sky130hd", "asap7"])
    p.add_argument("--clocks", nargs="+", type=float, default=[5.0, 2.5, 1.0])
    p.add_argument("--density", type=float, default=0.50)
    p.add_argument("--concurrency", type=int, default=2)
    p.add_argument("--flow-root", default=str(FLOW_ROOT))
    p.add_argument("--output-root", default=None)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--verbose", action="store_true")
    return p


def main(argv=None) -> None:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    flow_root = Path(args.flow_root).resolve()
    output_root = (
        Path(args.output_root).resolve()
        if args.output_root
        else Path("graft_road") / "outputs" / args.experiment
    )
    flopoco_bin = _resolve_flopoco_bin(allow_missing=args.dry_run)
    vh2v_bin = _resolve_vh2v_bin(None, allow_missing=args.dry_run)

    designs = load_designs(Path(args.config_file))

    actions: Dict[str, Any] = {}
    deps: Dict[str, List[str]] = {}
    cases_with_specs: List[tuple[DesignSpec, helpers.FlowCase]] = []

    # Generation actions per design
    for spec in designs:
        src_dir = flow_root / "designs" / "src" / args.experiment / spec.name
        vhdl_out = src_dir / f"{spec.name}.vhdl"

        mkdir_src = f"mkdir_src_{spec.name}"
        flopoco_task = f"flopoco_{spec.name}"
        translate_task = f"translate_{spec.name}"

        actions[mkdir_src] = lambda d=src_dir: helpers.ensure_dir(d, args.dry_run)
        deps[mkdir_src] = []

        actions[flopoco_task] = lambda b=flopoco_bin, s=spec, v=vhdl_out: run_flopoco(
            b, s, v, args.dry_run, args.verbose
        )
        deps[flopoco_task] = [mkdir_src]

        actions[translate_task] = lambda vb=vh2v_bin, v=vhdl_out, d=src_dir: translate_vhdl(
            vb, v, d, args.dry_run, args.verbose
        )
        deps[translate_task] = [flopoco_task]

        # Plan flow cases for this design
        cases = helpers.plan_cases(
            spec.name,
            args.experiment,
            args.pdks,
            args.clocks,
            args.density,
            flow_root,
            templates_dir=Path(__file__).resolve().parent.parent / "templates",
        )
        for case in cases:
            cases_with_specs.append((spec, case))

    # Per-case actions (after translation)
    for spec, case in cases_with_specs:
        prefix = f"{spec.name}_{case.pdk}_{case.run_tag}"
        mkdir_name = f"mkdir_{prefix}"
        write_cfg_name = f"write_cfg_{prefix}"
        write_sdc_name = f"write_sdc_{prefix}"
        flow_name = f"flow_{prefix}"
        metrics_name = f"metrics_{prefix}"

        actions[mkdir_name] = lambda d=case.config_dir: helpers.ensure_dir(d, args.dry_run)
        deps[mkdir_name] = [f"translate_{spec.name}"]

        actions[write_cfg_name] = lambda p=case.config_path, t=case.config_text: helpers.write_file(
            p, t, args.dry_run
        )
        deps[write_cfg_name] = [mkdir_name]

        actions[write_sdc_name] = lambda p=case.sdc_path, t=case.sdc_text: helpers.write_file(p, t, args.dry_run)
        deps[write_sdc_name] = [mkdir_name]

        actions[flow_name] = lambda c=case: helpers.run_flow(
            flow_root, c, args.experiment, spec.name, args.dry_run, args.verbose
        )
        deps[flow_name] = [write_cfg_name, write_sdc_name]

        actions[metrics_name] = lambda c=case: helpers.assign_metrics(
            flow_root, args.experiment, spec.name, c, args.dry_run
        )
        deps[metrics_name] = [flow_name]

    def report_action():
        rows = []
        for spec, case in cases_with_specs:
            helpers.assign_metrics(flow_root, args.experiment, spec.name, case, args.dry_run)
            rows.append(
                {
                    "design": spec.name,
                    "pdk": case.pdk,
                    "clock_ns": case.clock_ns,
                    "status": "failed" if case.failed else "ok",
                    "log_dir": str(helpers.metric_log_dir(flow_root, spec.name, case)),
                    "flopoco_operator": spec.operator,
                    **{f"param_{k}": v for k, v in spec.params.items()},
                    **spec.meta,
                    **case.metrics,
                }
            )
        output_root.mkdir(parents=True, exist_ok=True)
        metrics_path = output_root / "metrics.jsonl"
        plots_dir = output_root / "plots"
        df = helpers.emit_metrics(rows, metrics_path, args.dry_run)
        print(helpers.terminal_table(df))
        (output_root / "metrics.tex").write_text(helpers.latex_table(df))
        helpers.plot_metrics(df, plots_dir, args.dry_run)

    actions["report"] = report_action
    deps["report"] = [f"metrics_{spec.name}_{case.pdk}_{case.run_tag}" for spec, case in cases_with_specs]

    if args.dry_run:
        print("Dry run: planned actions")
        for name in actions:
            print(f"- {name} (depends on {deps.get(name, [])})")
        rows = []
        for spec, case in cases_with_specs:
            rows.append(
                {
                    "design": spec.name,
                    "pdk": case.pdk,
                    "clock_ns": case.clock_ns,
                    "run_tag": case.run_tag,
                    "operator": spec.operator,
                    **{f"param_{k}": v for k, v in spec.params.items()},
                }
            )
        import pandas as pd

        print("\nPlanned cases:")
        print(pd.DataFrame(rows).sort_values(["design", "pdk", "clock_ns"]).to_string(index=False))
        return

    scenario = Scenario(actions, deps, log=args.verbose)
    scenario.exec_once_sync_parallel(args.concurrency)


if __name__ == "__main__":
    main()
