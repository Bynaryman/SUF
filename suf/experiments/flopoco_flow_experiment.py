#!/usr/bin/env python
"""Run Flopoco-generated designs through the OpenROAD flow."""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List

THIS_FILE = Path(__file__).resolve()
REPO_ROOT = THIS_FILE.parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from suf import FLOW_ROOT  # noqa: E402
try:  # noqa: E402
    from . import simple_flow_helpers as helpers  # type: ignore
except Exception:  # noqa: E402
    import suf.experiments.simple_flow_helpers as helpers  # type: ignore
try:  # noqa: E402
    from . import flopoco_helpers  # type: ignore
except Exception:  # noqa: E402
    import suf.experiments.flopoco_helpers as flopoco_helpers  # type: ignore
from graft_road.libs.scenario import Scenario  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Run Flopoco-generated designs through OpenROAD.")
    p.add_argument(
        "--experiment-root",
        default="graft_road/experiments/flopoco",
        help="Experiment folder with specs/functional.py and specs/performance.py.",
    )
    p.add_argument("--concurrency", type=int, default=2)
    p.add_argument("--flow-root", default=str(FLOW_ROOT))
    p.add_argument("--output-root", default=None)
    p.add_argument("--report-only", action="store_true", help="Skip flow, regenerate tables/plots from metrics.")
    p.add_argument("--metrics-path", default=None, help="Override metrics.jsonl path for report-only mode.")
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
    experiment_root = Path(args.experiment_root).resolve()
    specs_dir = experiment_root / "specs"
    functional_path = specs_dir / "functional.py"
    performance_path = specs_dir / "performance.py"

    flopoco_bin = flopoco_helpers.resolve_flopoco_bin(allow_missing=args.dry_run)
    vh2v_bin = flopoco_helpers.resolve_vh2v_bin(allow_missing=args.dry_run)

    designs = flopoco_helpers.load_designs(functional_path)
    performance = flopoco_helpers.load_performance(performance_path)
    pdks, pdk_meta = flopoco_helpers.parse_pdks(performance)
    clocks = performance.get("clocks", [5.0, 2.5, 1.0])
    if not isinstance(clocks, list):
        raise ValueError("PERFORMANCE['clocks'] must be a list.")
    density = performance.get("density", 0.5)
    experiment_name = performance.get("experiment", experiment_root.name)
    stages_dir = experiment_root / "stages"
    results_dir = experiment_root / "results"
    output_root = Path(args.output_root).resolve() if args.output_root else results_dir

    actions: Dict[str, Any] = {}
    deps: Dict[str, List[str]] = {}
    cases_with_specs: List[tuple[flopoco_helpers.DesignSpec, helpers.FlowCase]] = []

    actions["mkdir_experiment"] = lambda d=experiment_root: helpers.ensure_dir(d, args.dry_run)
    deps["mkdir_experiment"] = []
    actions["mkdir_stages"] = lambda d=stages_dir: helpers.ensure_dir(d, args.dry_run)
    deps["mkdir_stages"] = ["mkdir_experiment"]
    actions["mkdir_results"] = lambda d=results_dir: helpers.ensure_dir(d, args.dry_run)
    deps["mkdir_results"] = ["mkdir_experiment"]
    actions["mkdir_output"] = lambda d=output_root: helpers.ensure_dir(d, args.dry_run)
    deps["mkdir_output"] = ["mkdir_experiment"]

    # Generation actions per design
    for spec in designs:
        stage_design_dir = stages_dir / spec.name
        flopoco_dir = stage_design_dir / "flopoco"
        translated_dir = stage_design_dir / "translated"
        flow_src_dir = flow_root / "designs" / "src" / experiment_name / spec.name
        vhdl_out = flopoco_dir / f"{spec.name}.vhdl"

        mkdir_src = f"mkdir_src_{spec.name}"
        mkdir_stage = f"mkdir_stage_{spec.name}"
        mkdir_flopoco = f"mkdir_flopoco_{spec.name}"
        mkdir_translated = f"mkdir_translated_{spec.name}"
        flopoco_task = f"flopoco_{spec.name}"
        translate_task = f"translate_{spec.name}"
        sync_task = f"sync_sources_{spec.name}"

        actions[mkdir_stage] = lambda d=stage_design_dir: helpers.ensure_dir(d, args.dry_run)
        deps[mkdir_stage] = ["mkdir_stages"]
        actions[mkdir_flopoco] = lambda d=flopoco_dir: helpers.ensure_dir(d, args.dry_run)
        deps[mkdir_flopoco] = [mkdir_stage]
        actions[mkdir_translated] = lambda d=translated_dir: helpers.ensure_dir(d, args.dry_run)
        deps[mkdir_translated] = [mkdir_stage]
        actions[mkdir_src] = lambda d=flow_src_dir: helpers.ensure_dir(d, args.dry_run)
        deps[mkdir_src] = ["mkdir_stages"]

        actions[flopoco_task] = lambda b=flopoco_bin, s=spec, v=vhdl_out: flopoco_helpers.run_flopoco(
            b, s, v, args.dry_run, args.verbose
        )
        deps[flopoco_task] = [mkdir_flopoco]

        actions[translate_task] = lambda vb=vh2v_bin, v=vhdl_out, d=translated_dir: flopoco_helpers.translate_vhdl(
            vb, v, d, args.dry_run, args.verbose
        )
        deps[translate_task] = [mkdir_translated, flopoco_task]

        actions[sync_task] = lambda s=translated_dir, d=flow_src_dir: flopoco_helpers.sync_translated_sources(
            s, d, args.dry_run
        )
        deps[sync_task] = [translate_task, mkdir_src]

        # Plan flow cases for this design
        cases = helpers.plan_cases(
            spec.name,
            experiment_name,
            pdks,
            clocks,
            density,
            flow_root,
            templates_dir=Path(__file__).resolve().parent.parent / "templates",
        )
        for case in cases:
            cases_with_specs.append((spec, case))

    # Per-case actions (after translation)
    for spec, case in cases_with_specs:
        design_name = spec.name
        prefix = f"{spec.name}_{case.pdk}_{case.run_tag}"
        mkdir_name = f"mkdir_{prefix}"
        write_cfg_name = f"write_cfg_{prefix}"
        write_sdc_name = f"write_sdc_{prefix}"
        flow_name = f"flow_{prefix}"
        metrics_name = f"metrics_{prefix}"

        actions[mkdir_name] = lambda d=case.config_dir: helpers.ensure_dir(d, args.dry_run)
        deps[mkdir_name] = [f"sync_sources_{spec.name}"]

        actions[write_cfg_name] = lambda p=case.config_path, t=case.config_text: helpers.write_file(
            p, t, args.dry_run
        )
        deps[write_cfg_name] = [mkdir_name]

        actions[write_sdc_name] = lambda p=case.sdc_path, t=case.sdc_text: helpers.write_file(p, t, args.dry_run)
        deps[write_sdc_name] = [mkdir_name]

        actions[flow_name] = lambda c=case, d=design_name: helpers.run_flow(
            flow_root, c, experiment_name, d, args.dry_run, args.verbose
        )
        deps[flow_name] = [write_cfg_name, write_sdc_name]

        actions[metrics_name] = lambda c=case, d=design_name: helpers.assign_metrics(
            flow_root, experiment_name, d, c, args.dry_run
        )
        deps[metrics_name] = [flow_name]

    def report_action():
        rows = []
        for spec, case in cases_with_specs:
            helpers.assign_metrics(flow_root, experiment_name, spec.name, case, args.dry_run)
            rows.append(
                {
                    "design": spec.name,
                    "pdk": case.pdk,
                    "clock_ns": case.clock_ns,
                    "status": "failed" if case.failed else "ok",
                    "log_dir": str(helpers.metric_log_dir(flow_root, spec.name, case)),
                    "experiment": experiment_name,
                    "density": density,
                    "flopoco_operator": spec.operator,
                    **{f"pdk_{k}": v for k, v in pdk_meta.get(case.pdk, {}).items()},
                    **{
                        f"perf_{k}": v
                        for k, v in performance.items()
                        if k not in {"pdks", "clocks", "density", "experiment"}
                    },
                    **{f"param_{k}": v for k, v in spec.params.items()},
                    **spec.meta,
                    **case.metrics,
                }
            )
        metrics_path = output_root / "metrics.jsonl"
        plots_dir = output_root / "plots"
        df = helpers.emit_metrics(rows, metrics_path, args.dry_run)
        print(helpers.terminal_table(df))
        (output_root / "metrics.tex").write_text(helpers.latex_table(df))
        helpers.plot_metrics(df, plots_dir, args.dry_run)

    actions["report"] = report_action
    deps["report"] = (
        [f"metrics_{spec.name}_{case.pdk}_{case.run_tag}" for spec, case in cases_with_specs]
        + ["mkdir_output"]
    )

    if args.report_only:
        metrics_path = Path(args.metrics_path).resolve() if args.metrics_path else output_root / "metrics.jsonl"
        df = helpers.load_metrics_jsonl(metrics_path)
        if df.empty:
            report_action()
            return
        output_root.mkdir(parents=True, exist_ok=True)
        plots_dir = output_root / "plots"
        print(helpers.terminal_table(df))
        (output_root / "metrics.tex").write_text(helpers.latex_table(df))
        helpers.plot_metrics(df, plots_dir, args.dry_run)
        return

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
                    "experiment": experiment_name,
                    "density": density,
                    **{f"pdk_{k}": v for k, v in pdk_meta.get(case.pdk, {}).items()},
                    **{
                        f"perf_{k}": v
                        for k, v in performance.items()
                        if k not in {"pdks", "clocks", "density", "experiment"}
                    },
                    **{f"param_{k}": v for k, v in spec.params.items()},
                }
            )
        import pandas as pd

        print("\nPlanned cases:")
        print(pd.DataFrame(rows).sort_values(["design", "pdk", "clock_ns"]).to_string(index=False))
        if cases_with_specs:
            spec, case = cases_with_specs[0]
            stage_design_dir = stages_dir / spec.name
            flopoco_dir = stage_design_dir / "flopoco"
            translated_dir = stage_design_dir / "translated"
            flow_src_dir = flow_root / "designs" / "src" / experiment_name / spec.name
            vhdl_out = flopoco_dir / f"{spec.name}.vhdl"
            flow_cmd = helpers.planned_command(flow_root, case, experiment_name, spec.name)
            print("\nExample command chain (first case):")
            print(f"mkdir -p {experiment_root}")
            print(f"mkdir -p {stages_dir}")
            print(f"mkdir -p {results_dir}")
            print(f"mkdir -p {output_root}")
            print(f"mkdir -p {stage_design_dir}")
            print(f"mkdir -p {flopoco_dir}")
            print(f"mkdir -p {translated_dir}")
            print(f"mkdir -p {flow_src_dir}")
            flopoco_cmd = flopoco_helpers.flopoco_command(flopoco_bin, spec, vhdl_out)
            print(" ".join(str(c) for c in flopoco_cmd))
            print(f"python {vh2v_bin} --input_file {vhdl_out} --output_dir {translated_dir}")
            print(f"cp {translated_dir}/*.v {flow_src_dir}/")
            print(f"mkdir -p {case.config_dir}")
            print(f"write {case.config_path}")
            print(f"write {case.sdc_path}")
            print(" ".join(flow_cmd))
        return

    scenario = Scenario(actions, deps, log=args.verbose)
    scenario.exec_once_sync_parallel(args.concurrency)


if __name__ == "__main__":
    main()
