#!/usr/bin/env python
"""Scenario-driven simple flow experiment with explicit actions."""
from __future__ import annotations

import argparse
import logging
import sys
from functools import partial
from pathlib import Path

# Ensure repo root is on sys.path so graft_road imports resolve when executed as a script.
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from graft_road.libs.scenario import Scenario
from suf import FLOW_ROOT, GRAFT_ROAD_ROOT
from suf.experiments import simple_flow_helpers as helpers


def _parse_args(argv):
    p = argparse.ArgumentParser(description="Simple OpenROAD flow experiment (Scenario actions for all steps).")
    p.add_argument("--design-dir", type=Path, required=True, help="Directory containing Verilog sources.")
    p.add_argument("--design-name", type=str, help="Design name/top module (defaults to folder name).")
    p.add_argument("--experiment", type=str, default="suf", help="Experiment namespace under flow/designs.")
    p.add_argument("--pdks", nargs="+", default=["sky130hd", "asap7"], help="PDKs to run.")
    p.add_argument("--clocks", nargs="+", type=float, default=[5.0, 2.5, 1.0], help="Clock periods (ns).")
    p.add_argument("--density", type=float, default=0.60, help="Core utilization (0-1 or percent).")
    p.add_argument("--concurrency", type=int, default=2, help="Parallel flows.")
    p.add_argument("--flow-root", type=Path, default=None, help="Override FLOW_ROOT.")
    p.add_argument("--output-root", type=Path, default=None, help="Where to dump metrics/plots.")
    p.add_argument("--dry-run", action="store_true", help="Print planned actions, do not run.")
    return p.parse_args(argv)


def main(argv=None):
    args = _parse_args(argv or sys.argv[1:])
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    design_name = args.design_name or args.design_dir.name
    flow_root = args.flow_root if args.flow_root is not None else FLOW_ROOT
    output_root = args.output_root if args.output_root is not None else (GRAFT_ROAD_ROOT / "outputs" / args.experiment)

    planned_links, src_root = helpers.link_design_sources(
        args.design_dir, flow_root, args.experiment, design_name, dry_run=args.dry_run
    )
    cases = helpers.plan_cases(
        design_name=design_name,
        experiment=args.experiment,
        pdks=args.pdks,
        clocks_ns=args.clocks,
        density=args.density,
        flow_root=flow_root,
        templates_dir=Path(__file__).resolve().parents[1] / "templates",
    )

    # Build actions graph
    actions = {}
    deps = {}

    actions["mkdir_src"] = partial(helpers.ensure_dir, src_root, args.dry_run)
    deps["mkdir_src"] = []

    actions["symlink_sources"] = partial(helpers.create_symlinks, planned_links, args.dry_run)
    deps["symlink_sources"] = ["mkdir_src"]

    for case in cases:
        name_base = f"{case.pdk}_{case.run_tag}"
        mkdir_name = f"mkdir_{name_base}"
        write_cfg_name = f"write_cfg_{name_base}"
        write_sdc_name = f"write_sdc_{name_base}"
        flow_name = f"flow_{name_base}"
        metrics_name = f"metrics_{name_base}"

        actions[mkdir_name] = partial(helpers.ensure_dir, case.config_dir, args.dry_run)
        deps[mkdir_name] = ["symlink_sources"]

        actions[write_cfg_name] = partial(helpers.write_file, case.config_path, case.config_text, args.dry_run)
        deps[write_cfg_name] = [mkdir_name]

        actions[write_sdc_name] = partial(helpers.write_file, case.sdc_path, case.sdc_text, args.dry_run)
        deps[write_sdc_name] = [mkdir_name]

        actions[flow_name] = partial(helpers.run_flow, flow_root, case, args.experiment, design_name, args.dry_run)
        deps[flow_name] = [write_cfg_name, write_sdc_name]

        actions[metrics_name] = partial(
            helpers.assign_metrics, flow_root, args.experiment, design_name, case, args.dry_run
        )
        deps[metrics_name] = [flow_name]

    def report_action():
        rows = []
        for case in cases:
            rows.append({"design": design_name, "pdk": case.pdk, "clock_ns": case.clock_ns, **case.metrics})
        output_root.mkdir(parents=True, exist_ok=True)
        metrics_path = output_root / "metrics.jsonl"
        plots_dir = output_root / "plots"

        df = helpers.emit_metrics(rows, metrics_path, args.dry_run)
        print(helpers.terminal_table(df))
        (output_root / "metrics.tex").write_text(helpers.latex_table(df))
        helpers.plot_metrics(df, plots_dir, args.dry_run)

    actions["report"] = report_action
    deps["report"] = [f"metrics_{case.pdk}_{case.run_tag}" for case in cases]

    if args.dry_run:
        print("Dry run: planned actions")
        for name in actions:
            print(f"- {name} (depends on {deps.get(name, [])})")
        # Recap cases
        print("\nPlanned cases:")
        rows = [
            {"pdk": c.pdk, "clock_ns": c.clock_ns, "run_tag": c.run_tag, "config_dir": str(c.config_dir)}
            for c in cases
        ]
        import pandas as pd

        print(pd.DataFrame(rows).sort_values(["pdk", "clock_ns"]).to_string(index=False))
        return

    scenario = Scenario(actions, deps, log=True)
    scenario.exec_once_sync_parallel(args.concurrency)


if __name__ == "__main__":
    main()
