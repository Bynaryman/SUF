#!/usr/bin/env python
"""
Simple flow experiment.

Run an existing Verilog design across multiple PDKs and clock periods using the
OpenROAD flow, collect key metrics (GDS area, synth area, synth cell count,
wirelength, WNS/TNS), and emit reports (terminal table, LaTeX table, PGF plots).

The experiment is built using the custom Scenario/Taskmap scheduler to execute
independent (pdk, clock) runs in parallel.
"""
from __future__ import annotations

import argparse
import json
import logging
import math
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from functools import partial
from typing import Dict, List, Sequence, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from jinja2 import Environment, FileSystemLoader

# Ensure we can import the scenario helper
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from graft_road.libs.scenario import Scenario
from suf import FLOW_ROOT, GRAFT_ROAD_ROOT

LOG = logging.getLogger(__name__)


def _to_float(val: object) -> float:
    try:
        return float(val)
    except (TypeError, ValueError):
        return float("nan")


@dataclass
class FlowCase:
    pdk: str
    clock_ns: float
    run_tag: str
    config_path: Path
    sdc_path: Path
    metrics: Dict[str, float] = field(default_factory=dict)


class SimpleFlowExperiment:
    """Drive a basic OpenROAD flow sweep for an existing RTL design."""

    def __init__(
        self,
        design_dir: Path,
        design_name: str,
        pdks: Sequence[str],
        clocks_ns: Sequence[float],
        density: float = 0.60,
        flow_root: Path | None = None,
        output_root: Path | None = None,
        concurrency: int = 2,
    ) -> None:
        self.design_dir = design_dir.resolve()
        self.design_name = design_name
        self.pdks = list(pdks)
        self.clocks_ns = list(clocks_ns)
        self.density = density
        self.flow_root = flow_root if flow_root is not None else FLOW_ROOT
        self.concurrency = concurrency

        self.templates_dir = REPO_ROOT / "suf" / "templates"

        self.output_root = (
            output_root
            if output_root is not None
            else GRAFT_ROAD_ROOT / "outputs" / "simple_flow"
        )
        self.output_root.mkdir(parents=True, exist_ok=True)
        self.metrics_path = self.output_root / "metrics.jsonl"
        self.plots_dir = self.output_root / "plots"
        self.plots_dir.mkdir(parents=True, exist_ok=True)

        self.cases: List[FlowCase] = []

    # ------------------------------------------------------------------ #
    # Preparation
    # ------------------------------------------------------------------ #
    def _link_design_sources(self) -> None:
        """Expose the RTL folder under flow/designs/src/<design_name> via symlinks."""
        src_root = self.flow_root / "designs" / "src" / self.design_name
        src_root.mkdir(parents=True, exist_ok=True)

        for item in self.design_dir.glob("*.v"):
            dest = src_root / item.name
            if dest.exists():
                continue
            dest.symlink_to(item)

    def _render_config_and_sdc(self, pdk: str, clock_ns: float) -> FlowCase:
        """Render config.mk and constraint.sdc for a specific (pdk, clock) tuple."""
        util_percent, place_density = self._normalize_density(self.density)
        design_dir = self.flow_root / "designs" / pdk / self.design_name
        design_dir.mkdir(parents=True, exist_ok=True)

        verilog_glob = f"./designs/src/{self.design_name}/*.v"
        sdc_rel = Path("designs") / pdk / self.design_name / "constraint.sdc"
        sdc_path = design_dir / "constraint.sdc"
        config_path = design_dir / "config.mk"

        env = Environment(
            loader=FileSystemLoader(self.templates_dir),
            autoescape=False,
            trim_blocks=True,
            lstrip_blocks=True,
        )

        cfg_template = env.get_template("config.mk.j2")
        cfg_text = cfg_template.render(
            design_name=self.design_name,
            platform=pdk,
            verilog_glob=verilog_glob,
            sdc_path=f"./{sdc_rel}",
            core_utilization=int(util_percent),
            place_density=round(place_density, 3),
            clock_period=clock_ns,
            flow_overrides={},
        )
        config_path.write_text(cfg_text)

        sdc_template = env.get_template("constraint.sdc.j2")
        sdc_text = sdc_template.render(
            design_name=self.design_name,
            clock_name="core_clock",
            clock_port="clk",
            clock_period=clock_ns,
            clock_io_pct=0.2,
        )
        sdc_path.write_text(sdc_text)

        run_tag = f"c{clock_ns:.2f}".replace(".", "p")
        return FlowCase(
            pdk=pdk,
            clock_ns=clock_ns,
            run_tag=run_tag,
            config_path=config_path,
            sdc_path=sdc_path,
        )

    @staticmethod
    def _normalize_density(density: float) -> Tuple[float, float]:
        """Return (util_percent, place_density) from a user-provided value."""
        if density > 1:
            util = density
            place = density / 100.0
        else:
            util = density * 100
            place = density
        return util, place

    # ------------------------------------------------------------------ #
    # Flow execution
    # ------------------------------------------------------------------ #
    def _run_flow(self, case: FlowCase) -> None:
        """Invoke the OpenROAD flow for a single case."""
        cmd = [
            "make",
            "-C",
            str(self.flow_root),
            f"DESIGN_CONFIG=./designs/{case.pdk}/{self.design_name}/config.mk",
        ]
        env = os.environ.copy()
        env["RUN_TAG"] = case.run_tag
        LOG.info("Running flow: %s", " ".join(cmd))
        proc = subprocess.run(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        if proc.returncode != 0:
            LOG.error("Flow failed for %s/%s: %s", case.pdk, case.run_tag, proc.stdout.decode())
            raise RuntimeError(f"Flow failed for {case.pdk}/{case.run_tag}")

    # ------------------------------------------------------------------ #
    # Metrics parsing
    # ------------------------------------------------------------------ #
    def _metric_paths(self, case: FlowCase) -> Dict[str, Path]:
        base = self.flow_root / "logs" / case.pdk / self.design_name / case.run_tag
        return {
            "report": base / "6_report.json",
            "cts": base / "4_1_cts.json",
            "place": base / "3_4_place_resized.json",
            "route": base / "5_2_route.json",
            "final_log": base / "6_report.log",
            "route_log": base / "5_2_route.log",
        }

    def _load_json(self, path: Path) -> Dict[str, float]:
        try:
            return json.loads(path.read_text())
        except Exception:
            return {}

    def _parse_metrics(self, case: FlowCase) -> Dict[str, float]:
        """Aggregate metrics across report/stage JSONs and logs."""
        paths = self._metric_paths(case)
        data = self._load_json(paths["report"])

        # Backfill from stage JSONs
        for stage_path in (paths["route"], paths["cts"], paths["place"]):
            stage_data = self._load_json(stage_path)
            for k, v in stage_data.items():
                if k not in data:
                    data[k] = v

        metrics: Dict[str, float] = {}

        key_map = {
            "gds_area": [
                "finish__design__die__area",
                "cts__design__die__area",
                "design__die__area",
            ],
            "synth_area": [
                "finish__design__instance__area",
                "design__instance__area",
            ],
            "wirelength": [
                "detailedroute__route__wirelength",
                "route__wirelength",
                "globalroute__route__wirelength__estimated",
            ],
            "wns": [
                "finish__timing__setup__wns",
                "timing__setup__wns",
            ],
            "tns": [
                "finish__timing__setup__tns",
                "timing__setup__tns",
            ],
            "synth_cell_count": [
                "synth__design__instance__count__stdcell",
                "design__instance__count__stdcell",
            ],
        }

        for metric, keys in key_map.items():
            for key in keys:
                if key in data:
                    metrics[metric] = _to_float(data[key])
                    break
            metrics.setdefault(metric, float("nan"))

        # Buffer counts may be split between setup/hold buffers.
        buffer_keys = [
            "finish__design__instance__count__class:timing_repair_buffer",
            "cts__design__instance__count__setup_buffer",
            "cts__design__instance__count__hold_buffer",
        ]
        buf_total = 0.0
        for key in buffer_keys:
            if key in data:
                buf_total += _to_float(data[key])
        if buf_total > 0:
            metrics["buffer_count"] = buf_total

        # Fallback: scrape logs
        if math.isnan(metrics["gds_area"]) or math.isnan(metrics["wirelength"]):
            self._scrape_logs_for_metrics(paths["final_log"], metrics)
            self._scrape_logs_for_metrics(paths["route_log"], metrics)

        return metrics

    @staticmethod
    def _scrape_logs_for_metrics(path: Path, metrics: Dict[str, float]) -> None:
        if not path.exists():
            return
        text = path.read_text(errors="ignore")
        wl_match = _first_match(r"Total wire length\s*=\s*([0-9.]+)", text)
        if wl_match and math.isnan(metrics.get("wirelength", float("nan"))):
            metrics["wirelength"] = _to_float(wl_match)
        area_match = _first_match(r"Design area\s*([0-9.]+)", text)
        if area_match and math.isnan(metrics.get("gds_area", float("nan"))):
            metrics["gds_area"] = _to_float(area_match)
        buf_match = _first_match(r"Timing Repair Buffer\s+([0-9]+)", text)
        if buf_match and "buffer_count" not in metrics:
            metrics["buffer_count"] = _to_float(buf_match)

    # ------------------------------------------------------------------ #
    # Reporting
    # ------------------------------------------------------------------ #
    def _emit_metrics(self, rows: List[Dict[str, object]]) -> pd.DataFrame:
        df = pd.DataFrame(rows)
        with self.metrics_path.open("w") as handle:
            for row in rows:
                handle.write(json.dumps(row) + "\n")
        return df

    def _terminal_table(self, df: pd.DataFrame) -> str:
        cols = ["pdk", "clock_ns", "gds_area", "synth_area", "synth_cell_count", "wns", "tns", "wirelength"]
        df_disp = df[cols].copy()
        return df_disp.to_string(index=False)

    def _latex_table(self, df: pd.DataFrame) -> str:
        cols = ["pdk", "clock_ns", "gds_area", "synth_area", "synth_cell_count", "wns", "tns", "wirelength"]
        return df[cols].to_latex(index=False, float_format="%.3f")

    def _plot(self, df: pd.DataFrame) -> None:
        if df.empty:
            return
        for metric in ["gds_area", "wns", "tns", "wirelength"]:
            fig, ax = plt.subplots()
            for pdk, group in df.groupby("pdk"):
                ax.plot(group["clock_ns"], group[metric], marker="o", label=pdk)
            ax.set_xlabel("Clock period (ns)")
            ax.set_ylabel(metric)
            ax.legend()
            ax.grid(True, linestyle="--", alpha=0.4)
            out_png = self.plots_dir / f"{metric}.png"
            out_pgf = self.plots_dir / f"{metric}.pgf"
            fig.savefig(out_png, bbox_inches="tight")
            fig.savefig(out_pgf, bbox_inches="tight")
            plt.close(fig)

    # ------------------------------------------------------------------ #
    # Scenario assembly
    # ------------------------------------------------------------------ #
    def run(self) -> None:
        """Execute the experiment using the Scenario scheduler."""
        self._link_design_sources()

        actions: Dict[str, object] = {}
        deps: Dict[str, List[str]] = {}

        # Rendering actions
        for pdk in self.pdks:
            render_name = f"render_cfg_{pdk}"
            actions[render_name] = partial(self._render_cases_for_pdk, pdk)
            deps[render_name] = []

        # Flow and metrics actions per case
        for pdk in self.pdks:
            for clk in self.clocks_ns:
                run_tag = f"c{clk:.2f}".replace(".", "p")
                case_name = f"{pdk}_{run_tag}"
                flow_name = f"flow_{case_name}"
                metrics_name = f"metrics_{case_name}"
                actions[flow_name] = partial(self._run_flow_for_case, pdk, clk)
                deps[flow_name] = [f"render_cfg_{pdk}"]

                actions[metrics_name] = partial(self._collect_metrics_for_case, pdk, clk)
                deps[metrics_name] = [flow_name]

        scenario = Scenario(actions, deps, log=True)
        scenario.exec_once_sync_parallel(self.concurrency)

        # Aggregate metrics
        rows: List[Dict[str, object]] = []
        for case in self.cases:
            row = {
                "design": self.design_name,
                "pdk": case.pdk,
                "clock_ns": case.clock_ns,
                **case.metrics,
            }
            rows.append(row)
        df = self._emit_metrics(rows)
        print(self._terminal_table(df))

        # Save LaTeX table
        latex_path = self.output_root / "metrics.tex"
        latex_path.write_text(self._latex_table(df))

        # Plots (PNG + PGF)
        self._plot(df)

    # Helpers used by Scenario
    def _render_cases_for_pdk(self, pdk: str) -> None:
        for clk in self.clocks_ns:
            case = self._render_config_and_sdc(pdk, clk)
            self.cases.append(case)

    def _run_flow_for_case(self, pdk: str, clk: float) -> None:
        case = next(fc for fc in self.cases if fc.pdk == pdk and abs(fc.clock_ns - clk) < 1e-6)
        self._run_flow(case)

    def _collect_metrics_for_case(self, pdk: str, clk: float) -> None:
        case = next(fc for fc in self.cases if fc.pdk == pdk and abs(fc.clock_ns - clk) < 1e-6)
        case.metrics = self._parse_metrics(case)


def _first_match(pattern: str, text: str) -> str | None:
    import re

    m = re.search(pattern, text)
    return m.group(1) if m else None


def _parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Simple OpenROAD flow experiment driver.")
    parser.add_argument("--design-dir", type=Path, required=True, help="Path to directory containing Verilog sources.")
    parser.add_argument("--design-name", type=str, required=True, help="Design name/top module.")
    parser.add_argument("--pdks", nargs="+", default=["sky130hd", "asap7"], help="List of PDKs to target.")
    parser.add_argument("--clocks", nargs="+", type=float, default=[5.0, 2.5, 1.0], help="Clock periods (ns).")
    parser.add_argument("--density", type=float, default=0.60, help="Core utilization (0-1 or percent).")
    parser.add_argument("--concurrency", type=int, default=2, help="Parallel flows to run.")
    parser.add_argument("--flow-root", type=Path, default=None, help="Override FLOW_ROOT.")
    parser.add_argument("--output-root", type=Path, default=None, help="Override output directory.")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    args = _parse_args(argv or sys.argv[1:])
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    exp = SimpleFlowExperiment(
        design_dir=args.design_dir,
        design_name=args.design_name,
        pdks=args.pdks,
        clocks_ns=args.clocks,
        density=args.density,
        flow_root=args.flow_root,
        output_root=args.output_root,
        concurrency=args.concurrency,
    )
    exp.run()


if __name__ == "__main__":
    main()
