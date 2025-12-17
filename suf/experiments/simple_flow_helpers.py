#!/usr/bin/env python
"""Shared helpers for simple flow experiments (actions stay tiny)."""
from __future__ import annotations

import json
import logging
import math
import os
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

import matplotlib.pyplot as plt
import pandas as pd
from jinja2 import Environment, FileSystemLoader

LOG = logging.getLogger(__name__)


@dataclass
class FlowCase:
    pdk: str
    clock_ns: float
    run_tag: str
    config_dir: Path
    config_path: Path
    sdc_path: Path
    config_text: str
    sdc_text: str
    metrics: Dict[str, float] = field(default_factory=dict)


def normalize_density(density: float) -> Tuple[float, float]:
    if density > 1:
        util = density
        place = density / 100.0
    else:
        util = density * 100
        place = density
    return util, place


def link_design_sources(
    design_dir: Path,
    flow_root: Path,
    experiment: str,
    design_name: str,
    dry_run: bool = False,
) -> Tuple[List[Tuple[Path, Path]], Path]:
    """Plan/perform symlinks into flow/designs/src/<experiment>/<design>."""
    design_dir = design_dir.resolve()
    src_root = flow_root / "designs" / "src" / experiment / design_name
    if not dry_run:
        src_root.mkdir(parents=True, exist_ok=True)
    planned: List[Tuple[Path, Path]] = []
    for item in design_dir.glob("*.v"):
        src = item.resolve()
        dest = src_root / item.name
        planned.append((src, dest))
        if not dry_run:
            try:
                if not dest.exists():
                    dest.symlink_to(src)
            except FileExistsError:
                # Ignore if already present
                pass
    return planned, src_root


def plan_cases(
    design_name: str,
    experiment: str,
    pdks: Sequence[str],
    clocks_ns: Sequence[float],
    density: float,
    flow_root: Path,
    templates_dir: Path,
) -> List[FlowCase]:
    """Prepare FlowCase objects with rendered text (no writes)."""
    env = Environment(
        loader=FileSystemLoader(templates_dir),
        autoescape=False,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    cfg_template = env.get_template("config.mk.j2")
    sdc_template = env.get_template("constraint.sdc.j2")

    util_percent, place_density = normalize_density(density)

    cases: List[FlowCase] = []
    for pdk in pdks:
        for clk in clocks_ns:
            run_tag = f"c{clk:.2f}".replace(".", "p")
            design_dir = flow_root / "designs" / pdk / experiment / design_name / run_tag
            verilog_glob = f"./designs/src/{experiment}/{design_name}/*.v"
            sdc_rel = Path("designs") / pdk / experiment / design_name / run_tag / "constraint.sdc"
            sdc_path = design_dir / "constraint.sdc"
            config_path = design_dir / "config.mk"

            cfg_text = cfg_template.render(
                design_name=design_name,
                platform=pdk,
                verilog_glob=verilog_glob,
                sdc_path=f"./{sdc_rel}",
                core_utilization=int(util_percent),
                place_density=round(place_density, 3),
                clock_period=clk,
                flow_overrides={},
            )
            sdc_text = sdc_template.render(
                design_name=design_name,
                clock_name="core_clock",
                clock_port="clk",
                clock_period=clk,
                clock_io_pct=0.2,
            )

            cases.append(
                FlowCase(
                    pdk=pdk,
                    clock_ns=clk,
                    run_tag=run_tag,
                    config_dir=design_dir,
                    config_path=config_path,
                    sdc_path=sdc_path,
                    config_text=cfg_text,
                    sdc_text=sdc_text,
                )
            )
    return cases


def ensure_dir(path: Path, dry_run: bool) -> None:
    if dry_run:
        return
    path.mkdir(parents=True, exist_ok=True)


def write_file(path: Path, text: str, dry_run: bool) -> None:
    if dry_run:
        return
    path.write_text(text)


def create_symlinks(planned: List[Tuple[Path, Path]], dry_run: bool) -> None:
    if dry_run:
        return
    for src, dst in planned:
        if dst.exists() or dst.is_symlink():
            dst.unlink()
        dst.symlink_to(src)


def planned_command(flow_root: Path, case: FlowCase, experiment: str, design_name: str) -> List[str]:
    return [
        "make",
        "-C",
        str(flow_root),
        f"DESIGN_CONFIG=./designs/{case.pdk}/{experiment}/{design_name}/{case.run_tag}/config.mk",
        f"RUN_TAG={case.run_tag}",
    ]


def run_flow(flow_root: Path, case: FlowCase, experiment: str, design_name: str, dry_run: bool) -> None:
    cmd = planned_command(flow_root, case, experiment, design_name)
    env = os.environ.copy()
    env["RUN_TAG"] = case.run_tag
    LOG.info("Running flow: %s", " ".join(cmd))
    if dry_run:
        return
    proc = subprocess.run(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if proc.returncode != 0:
        LOG.error("Flow failed for %s/%s: %s", case.pdk, case.run_tag, proc.stdout.decode())
        raise RuntimeError(f"Flow failed for {case.pdk}/{case.run_tag}")


def assign_metrics(flow_root: Path, experiment: str, design_name: str, case: FlowCase, dry_run: bool) -> None:
    if dry_run:
        case.metrics = {}
        return
    case.metrics = parse_metrics(flow_root, experiment, design_name, case)


def parse_metrics(flow_root: Path, experiment: str, design_name: str, case: FlowCase) -> Dict[str, float]:
    paths = _metric_paths(flow_root, experiment, design_name, case)
    data = _load_json(paths["report"])
    for stage_path in (paths["route"], paths["cts"], paths["place"]):
        stage_data = _load_json(stage_path)
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
        metrics[metric] = float("nan")
        for key in keys:
            if key in data:
                metrics[metric] = _to_float(data[key])
                break

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

    if math.isnan(metrics.get("gds_area", float("nan"))) or math.isnan(metrics.get("wirelength", float("nan"))):
        _scrape_logs_for_metrics(paths["final_log"], metrics)
        _scrape_logs_for_metrics(paths["route_log"], metrics)
    return metrics


def emit_metrics(rows: List[Dict[str, object]], metrics_path: Path, dry_run: bool) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    if df.empty or dry_run:
        return df
    with metrics_path.open("w") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")
    return df


def terminal_table(df: pd.DataFrame) -> str:
    if df.empty:
        return "No metrics (possibly dry-run)."
    cols = ["pdk", "clock_ns", "gds_area", "synth_area", "synth_cell_count", "wns", "tns", "wirelength"]
    df_disp = df.reindex(columns=cols)
    return df_disp.to_string(index=False)


def latex_table(df: pd.DataFrame) -> str:
    if df.empty:
        return "% No metrics (possibly dry-run)."
    cols = ["pdk", "clock_ns", "gds_area", "synth_area", "synth_cell_count", "wns", "tns", "wirelength"]
    df_disp = df.reindex(columns=cols)
    return df_disp.to_latex(index=False, float_format="%.3f")


def plot_metrics(df: pd.DataFrame, plots_dir: Path, dry_run: bool) -> None:
    if df.empty or dry_run:
        return
    plots_dir.mkdir(parents=True, exist_ok=True)
    for metric in ["gds_area", "wns", "tns", "wirelength"]:
        fig, ax = plt.subplots()
        for pdk, group in df.groupby("pdk"):
            ax.plot(group["clock_ns"], group[metric], marker="o", label=pdk)
        ax.set_xlabel("Clock period (ns)")
        ax.set_ylabel(metric)
        ax.legend()
        ax.grid(True, linestyle="--", alpha=0.4)
        out_png = plots_dir / f"{metric}.png"
        out_pgf = plots_dir / f"{metric}.pgf"
        fig.savefig(out_png, bbox_inches="tight")
        fig.savefig(out_pgf, bbox_inches="tight")
        plt.close(fig)


# Internal helpers
def _metric_paths(flow_root: Path, experiment: str, design_name: str, case: FlowCase) -> Dict[str, Path]:
    base = flow_root / "logs" / case.pdk / design_name / case.run_tag
    return {
        "report": base / "6_report.json",
        "cts": base / "4_1_cts.json",
        "place": base / "3_4_place_resized.json",
        "route": base / "5_2_route.json",
        "final_log": base / "6_report.log",
        "route_log": base / "5_2_route.log",
    }


def _load_json(path: Path) -> Dict[str, float]:
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}


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


def _to_float(val: object) -> float:
    try:
        return float(val)
    except (TypeError, ValueError):
        return float("nan")


def _first_match(pattern: str, text: str) -> str | None:
    m = re.search(pattern, text)
    return m.group(1) if m else None
