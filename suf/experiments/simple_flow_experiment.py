#!/usr/bin/env python
"""
Thin Scenario-based experiment runner.

This mirrors the short graft_road scripts: wire actions/deps, delegate work to helpers.
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from functools import partial

# Ensure repo root on sys.path for graft_road imports
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Local imports
from graft_road.libs.scenario import Scenario
from suf import FLOW_ROOT, GRAFT_ROAD_ROOT
from suf.experiments import simple_flow_helpers as helpers


def _parse_args(argv):
    p = argparse.ArgumentParser(description="Simple OpenROAD flow experiment (Scenario style).")
    p.add_argument("--design-dir", type=Path, required=True, help="Directory containing Verilog sources.")
    p.add_argument("--design-name", type=str, required=True, help="Design name/top module.")
    p.add_argument("--experiment", type=str, default="suf", help="Experiment namespace under flow/designs.")
    p.add_argument("--pdks", nargs="+", default=["sky130hd", "asap7"], help="PDKs to run.")
    p.add_argument("--clocks", nargs="+", type=float, default=[5.0, 2.5, 1.0], help="Clock periods (ns).")
    p.add_argument("--density", type=float, default=0.60, help="Core utilization (0-1 or percent).")
    p.add_argument("--concurrency", type=int, default=2, help="Parallel flows.")
    p.add_argument("--flow-root", type=Path, default=None, help="Override FLOW_ROOT.")
    p.add_argument("--output-root", type=Path, default=None, help="Where to dump metrics/plots.")
    p.add_argument("--dry-run", action="store_true", help="Print planned commands, do not run.")
    return p.parse_args(argv)


def main(argv=None):
    args = _parse_args(argv or sys.argv[1:])
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    flow_root = args.flow_root if args.flow_root is not None else FLOW_ROOT
    output_root = args.output_root if args.output_root is not None else (GRAFT_ROAD_ROOT / "outputs" / args.experiment)

    helpers.link_design_sources(args.design_dir, flow_root, args.experiment, args.design_name)
    cases = helpers.render_cases(
        design_name=args.design_name,
        experiment=args.experiment,
        pdks=args.pdks,
        clocks_ns=args.clocks,
        density=args.density,
        flow_root=flow_root,
        templates_dir=Path(__file__).resolve().parents[1] / "templates",
    )

    if args.dry_run:
        print("Dry run: planned flow commands")
        for case in cases:
            cmd = helpers.planned_command(flow_root, case, args.experiment, args.design_name)
            print(" ".join(cmd), f"(RUN_TAG={case.run_tag})")
        return

    # Build Scenario: one flow action per case
    actions = {}
    deps = {}
    for case in cases:
        action_name = f"flow_{case.pdk}_{case.run_tag}"
        actions[action_name] = partial(helpers.run_flow, flow_root, case, args.experiment, args.design_name)
        deps[action_name] = []

    scenario = Scenario(actions, deps, log=True)
    scenario.exec_once_sync_parallel(args.concurrency)

    # Collect metrics and report
    rows = []
    for case in cases:
        metrics = helpers.parse_metrics(flow_root, args.experiment, args.design_name, case)
        rows.append({"design": args.design_name, "pdk": case.pdk, "clock_ns": case.clock_ns, **metrics})

    output_root.mkdir(parents=True, exist_ok=True)
    metrics_path = output_root / "metrics.jsonl"
    plots_dir = output_root / "plots"

    df = helpers.emit_metrics(rows, metrics_path)
    print(helpers.terminal_table(df))
    (output_root / "metrics.tex").write_text(helpers.latex_table(df))
    helpers.plot_metrics(df, plots_dir)


if __name__ == "__main__":
    main()
