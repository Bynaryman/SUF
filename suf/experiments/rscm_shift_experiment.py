#!/usr/bin/env python
"""
RSCM shift experiment.

Creates families of RSCM designs that share logical complexity (same mux2/HA/FA
counts) but permute bit slices to stress placement/routing. The experiment:

- Generates RTL variants with controlled permutations.
- Computes displacement metrics L = Σ|π(i)-i| and Q = Σ|π(i)-i|².
- Runs synthesis (Yosys) and PNR (OpenROAD) across PDK/density/clock sweeps.
- Collects metrics into JSON rows.
- Fits linear models (area, wirelength, timing) against L and Q.
- Produces exploratory plots and α/β heatmaps.
"""
from __future__ import annotations

import json
import os
import logging
import subprocess
import sys
from dataclasses import dataclass, field
from itertools import product
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Sequence, Tuple
import math
import shutil
import argparse
import re
from functools import lru_cache

def _to_float(val: object) -> float:
    try:
        return float(val)
    except (TypeError, ValueError):
        return float("nan")

# Allow running this file directly without installing the package
if __package__ in (None, ""):
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from jinja2 import Environment, FileSystemLoader

from suf import FLOW_ROOT, GRAFT_ROAD_ROOT, OPENROAD_EXE, YOSYS_CMD
from suf.generators import RSCMShiftGenerator, RSCMVariant

LOG = logging.getLogger(__name__)


def _normalize_density(density: float) -> Tuple[float, float]:
    """Return (util_percent, place_density) from a user-provided value."""
    if density > 1:
        util = density
        place = density / 100.0
    else:
        util = density * 100
        place = density
    return util, place


@dataclass
class FlowCase:
    variant: RSCMVariant
    pdk: str
    density: float
    clock_ns: float
    config_path: Path
    sdc_path: Path
    run_tag: str = "base"
    metrics: Dict[str, object] = field(default_factory=dict)


class RSCMShiftExperiment:
    experiment_name = "rscm_shift"

    def __init__(
        self,
        n: int = 32,
        k: int = 4,
        pdks: Sequence[str] | None = None,
        densities: Sequence[float] | None = None,
        clock_periods_ns: Sequence[float] | None = None,
        output_root: Path | None = None,
        flow_root: Path | None = None,
        openroad_exe: str | None = None,
        yosys_cmd: str | None = None,
    ) -> None:
        self.pdks = list(pdks or ["sky130hd", "nangate45", "asap7", "gf180"])
        self.densities = list(densities or [0.40, 0.50, 0.60])
        self.clock_periods_ns = list(clock_periods_ns or [1.0, 0.5, 0.25])
        self.flow_root = flow_root if flow_root is not None else FLOW_ROOT
        self.openroad_exe = openroad_exe or OPENROAD_EXE or shutil.which("openroad")
        self.yosys_cmd = yosys_cmd or YOSYS_CMD or shutil.which("yosys")

        self.generator = RSCMShiftGenerator(
            module_basename=self.experiment_name, n=n, k=k, flow_root=self.flow_root
        )
        self.templates_dir = Path(__file__).resolve().parents[1] / "templates"
        self.env = Environment(
            loader=FileSystemLoader(self.templates_dir),
            autoescape=False,
            trim_blocks=True,
            lstrip_blocks=True,
        )

        self.output_root = (
            output_root
            if output_root is not None
            else GRAFT_ROAD_ROOT / "outputs" / self.experiment_name
        )
        self.output_root.mkdir(parents=True, exist_ok=True)
        self.metrics_path = self.output_root / "metrics.jsonl"
        self.plots_dir = self.output_root / "plots"
        self.plots_dir.mkdir(parents=True, exist_ok=True)

    # ---------------------------------------------------------------------- #
    # Variant generation and bookkeeping
    # ---------------------------------------------------------------------- #
    def generate_rscm_variants(
        self,
        permutations: Iterable[Sequence[int]] | None = None,
        count: int = 8,
    ) -> List[RSCMVariant]:
        """
        Generate RTL variants for the experiment.

        Args:
            permutations: Optional explicit permutations. If omitted, uses
                deterministic shifts plus random shuffles for coverage.
            count: Number of variants (ignored when permutations provided).
        """
        perms = list(permutations) if permutations is not None else self._default_perms(count)
        variants = self.generator.generate_variants(perms, prefix=self.experiment_name)
        self._persist_variants(variants)
        return variants

    def _default_perms(self, count: int) -> List[List[int]]:
        base = list(range(self.generator.n))
        perms: List[List[int]] = []

        # First batch: cyclic shifts for predictable L/Q spread
        for shift in range(min(count, self.generator.n)):
            rotated = base[shift:] + base[:shift]
            perms.append(rotated)
            if len(perms) >= count:
                return perms

        # Remaining variants: randomized but reproducible
        rng = np.random.default_rng(seed=42)
        while len(perms) < count:
            perm = base.copy()
            rng.shuffle(perm)
            perms.append(perm)
        return perms

    def compute_displacement_metrics(self, variant: RSCMVariant) -> Dict[str, int]:
        """Expose L and Q for a given variant."""
        return {
            "L": variant.metrics.linear,
            "Q": variant.metrics.quadratic,
        }

    def _persist_variants(self, variants: Sequence[RSCMVariant]) -> None:
        meta_path = self.output_root / "variants.jsonl"
        with meta_path.open("w") as handle:
            for variant in variants:
                payload = {
                    "name": variant.name,
                    "permutation": variant.permutation,
                    "metrics": {
                        "L": variant.metrics.linear,
                        "Q": variant.metrics.quadratic,
                    },
                    "rtl_path": str(variant.rtl_path),
                    **variant.metadata,
                }
                handle.write(json.dumps(payload) + "\n")
        LOG.info("Wrote %s", meta_path)

    # ---------------------------------------------------------------------- #
    # Flow preparation and execution
    # ---------------------------------------------------------------------- #
    def _render_templates(
        self,
        variant: RSCMVariant,
        pdk: str,
        density: float,
        clock_ns: float,
        run_tag: str | None = None,
    ) -> FlowCase:
        util_percent, place_density = _normalize_density(density)
        design_dir = (
            self.flow_root / "designs" / pdk / self.experiment_name / variant.name
        )
        design_dir.mkdir(parents=True, exist_ok=True)

        verilog_glob = f"./designs/src/{self.experiment_name}/{variant.name}/*.v"
        sdc_rel = Path("designs") / pdk / self.experiment_name / variant.name / "constraint.sdc"
        sdc_path = design_dir / "constraint.sdc"
        config_path = design_dir / "config.mk"

        # Render config.mk
        cfg_template = self.env.get_template("config.mk.j2")
        cfg_text = cfg_template.render(
            design_name=variant.name,
            platform=pdk,
            verilog_glob=verilog_glob,
            sdc_path=f"./{sdc_rel}",
            core_utilization=int(util_percent),
            place_density=round(place_density, 3),
            clock_period=clock_ns,
            flow_overrides={},
        )
        config_path.write_text(cfg_text)

        # Render constraint.sdc
        sdc_template = self.env.get_template("constraint.sdc.j2")
        sdc_text = sdc_template.render(
            design_name=variant.name,
            clock_name="core_clock",
            clock_port="clk",
            clock_period=clock_ns,
            clock_io_pct=0.2,
        )
        sdc_path.write_text(sdc_text)

        return FlowCase(
            variant=variant,
            pdk=pdk,
            density=density,
            clock_ns=clock_ns,
            config_path=config_path,
            sdc_path=sdc_path,
            run_tag=run_tag or f"d{int(util_percent):02d}_c{clock_ns:.2f}",
        )

    def run_synthesis(
        self, variants: Sequence[RSCMVariant], pdk: str | None = None, force: bool = False
    ) -> None:
        """
        Run synthesis via the OpenROAD flow.

        Args:
            variants: Variants to synthesize.
            pdk: Use a single PDK for the synthesis-area sanity check.
            force: Re-run even if reports already exist.
        """
        target_pdk = pdk or self.pdks[0]
        for variant in variants:
            case = self._render_templates(
                variant=variant,
                pdk=target_pdk,
                density=self.densities[0],
                clock_ns=self.clock_periods_ns[0],
            )
            if not force and self._has_metrics(case):
                LOG.info("Skip synth for %s (reports found)", variant.name)
                continue
            self._invoke_flow(case, target="synth")

    def run_pnr(
        self,
        variants: Sequence[RSCMVariant],
        force: bool = False,
    ) -> List[FlowCase]:
        """Run PNR for all combinations of PDK, density, and clock."""
        cases = self.build_cases(variants)
        for case in cases:
            if not force and self._has_metrics(case):
                LOG.info(
                    "Skip PNR for %s/%s@%.0f%%/%.2fns (reports found)",
                    case.variant.name,
                    case.pdk,
                    case.density * 100,
                    case.clock_ns,
                )
                continue
            self._invoke_flow(case, target="finish")
        return cases

    def build_cases(self, variants: Sequence[RSCMVariant]) -> List[FlowCase]:
        """Materialize all FlowCase combinations and render configs/SDCs."""
        cases: List[FlowCase] = []
        for variant, pdk, density, clock_ns in product(
            variants, self.pdks, self.densities, self.clock_periods_ns
        ):
            cases.append(
                self._render_templates(
                    variant=variant,
                    pdk=pdk,
                    density=density,
                    clock_ns=clock_ns,
                    run_tag=f"d{int(density*100):02d}_c{clock_ns:.2f}",
                )
            )
        return cases

    def _invoke_flow(self, case: FlowCase, target: str) -> None:
        design_config = f"./designs/{case.pdk}/{self.experiment_name}/{case.variant.name}/config.mk"
        cmd = [
            "make",
            "-C",
            str(self.flow_root),
            f"DESIGN_CONFIG={design_config}",
            target,
        ]
        env = os.environ.copy()
        if self.openroad_exe:
            env["OPENROAD_EXE"] = str(self.openroad_exe)
        if self.yosys_cmd:
            env["YOSYS_CMD"] = str(self.yosys_cmd)
        env.setdefault("YOSYS_FLAGS", "-v 3")
        env["RUN_TAG"] = case.run_tag
        LOG.info(
            "Running %s for %s (%s, %.0f%%, %.2fns)",
            target,
            case.variant.name,
            case.pdk,
            case.density * 100,
            case.clock_ns,
        )
        subprocess.run(cmd, check=True, env=env)

    # ---------------------------------------------------------------------- #
    # Metrics parsing
    # ---------------------------------------------------------------------- #
    def _has_metrics(self, case: FlowCase) -> bool:
        return self._find_metric_file(case) is not None

    def _find_metric_file(self, case: FlowCase) -> Path | None:
        candidates = [
            self.flow_root
            / "reports"
            / case.pdk
            / case.variant.name
            / case.run_tag
            / "metrics.json",
            self.flow_root
            / "reports"
            / case.pdk
            / case.variant.name
            / case.run_tag
            / "metrics.csv",
            self.flow_root
            / "reports"
            / case.pdk
            / self.experiment_name
            / case.variant.name
            / "metrics.json",
            self.flow_root
            / "logs"
            / case.pdk
            / case.variant.name
            / case.run_tag
            / "6_report.json",
            self.flow_root
            / "designs"
            / case.pdk
            / self.experiment_name
            / case.variant.name
            / "metadata-base.json",
            self.flow_root
            / "designs"
            / case.pdk
            / self.experiment_name
            / case.variant.name
            / "metadata-base-ok.json",
        ]
        for path in candidates:
            if path.exists():
                return path
        return None

    def collect_metrics(self, cases: Sequence[FlowCase]) -> pd.DataFrame:
        """Collect PNR results and persist JSON rows."""
        rows: List[Mapping[str, object]] = []
        if self.metrics_path.exists():
            self.metrics_path.unlink()
        with self.metrics_path.open("w") as handle:
            for case in cases:
                metrics = self._extract_metrics(case)
                row = {
                    "variant": case.variant.name,
                    "pdk": case.pdk,
                    "density": case.density,
                    "clock_ns": case.clock_ns,
                    "L": case.variant.metrics.linear,
                    "Q": case.variant.metrics.quadratic,
                    **metrics,
                }
                rows.append(row)
                handle.write(json.dumps(row) + "\n")
        df = pd.DataFrame(rows)
        return df

    def _extract_metrics(self, case: FlowCase) -> Dict[str, float]:
        path = self._find_metric_file(case)
        data: Dict[str, float] = {}
        if path is None:
            LOG.warning("No metrics found for %s (%s)", case.variant.name, case.pdk)
        else:
            if path.suffix == ".csv":
                df = pd.read_csv(path)
                cols = {c.lower(): c for c in df.columns}
                metric_col = cols.get("metric") or cols.get("name")
                value_col = cols.get("value")
                if metric_col and value_col:
                    data = {
                        row[metric_col]: _to_float(row[value_col])
                        for _, row in df.iterrows()
                        if metric_col in row and value_col in row
                    }
            else:
                data = json.loads(path.read_text())

        # Fallback: parse logs to fill any missing metrics
        log_data = self._parse_logs_for_metrics(case)
        for k, v in log_data.items():
            if k not in data or math.isnan(_to_float(data[k])):
                data[k] = v

        # Fallback: probe stage JSONs for missing pieces
        stage_data = self._parse_stage_jsons(case)
        for k, v in stage_data.items():
            if k not in data or math.isnan(_to_float(data[k])):
                data[k] = v

        # Candidate keys for each metric across flow versions
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
            "wirelength",
            ],
            "buffer_count": [
                "finish__design__instance__count__buf",
                "cts__design__instance__count__hold_buffer",
                "cts__design__instance__count__setup_buffer",
                "finish__design__instance__count__class:timing_repair_buffer",
                "finish__design__instance__count__class:buffer",
            ],
            "wns": [
                "finish__timing__setup__wns",
                "finish__timing__wns_percent_delay",
                "timing__setup__wns",
            ],
            "tns": [
                "finish__timing__setup__tns",
                "timing__setup__tns",
            ],
        }

        metrics: Dict[str, float] = {}
        for metric, keys in key_map.items():
            for key in keys:
                if key in data:
                    metrics[metric] = _to_float(data[key])
                    break
            metrics.setdefault(metric, float("nan"))

        # Buffer counts may be split between setup/hold buffers.
        if math.isnan(metrics["buffer_count"]):
            hold = _to_float(data.get("cts__design__instance__count__hold_buffer", 0))
            setup = _to_float(data.get("cts__design__instance__count__setup_buffer", 0))
            trb = _to_float(data.get("finish__design__instance__count__class:timing_repair_buffer", 0))
            metrics["buffer_count"] = hold + setup + trb
        return metrics

    def _parse_logs_for_metrics(self, case: FlowCase) -> Dict[str, float]:
        """Best-effort scrape of OpenROAD logs for metrics when JSON is absent."""
        metrics: Dict[str, float] = {}

        route_log = (
            self.flow_root
            / "logs"
            / case.pdk
            / case.variant.name
            / case.run_tag
            / "5_2_route.log"
        )
        final_log = (
            self.flow_root
            / "logs"
            / case.pdk
            / case.variant.name
            / case.run_tag
            / "6_report.log"
        )

        def scrape(path: Path) -> None:
            if not path.exists():
                return
            text = path.read_text(errors="ignore")
            wl_match = re.search(r"Total wire length\s*=\s*([0-9.]+)", text)
            if wl_match:
                metrics["wirelength"] = _to_float(wl_match.group(1))
            area_match = re.search(r"Design area\s*([0-9.]+)", text)
            if area_match:
                metrics["gds_area"] = _to_float(area_match.group(1))
            buf_match = re.search(r"Timing Repair Buffer\s+([0-9]+)", text)
            if buf_match:
                metrics["buffer_count"] = _to_float(buf_match.group(1))

        scrape(route_log)
        scrape(final_log)
        return metrics

    def _parse_stage_jsons(self, case: FlowCase) -> Dict[str, float]:
        """Pull metrics from per-stage JSON files (cts/place/route)."""
        metrics: Dict[str, float] = {}
        for path in self._stage_jsons(case):
            data = self._load_json(path)
            # Wirelength
            for key in (k for k in data if "wirelength" in k and "iter" not in k):
                metrics.setdefault("wirelength", _to_float(data[key]))
            # Instance area (proxy for synth area)
            for key in (
                k
                for k in data
                if "instance__area" in k and "class" not in k
            ):
                metrics.setdefault("synth_area", _to_float(data[key]))
            # Timing
            for key in (k for k in data if "timing__setup__wns" in k):
                metrics.setdefault("wns", _to_float(data[key]))
            for key in (k for k in data if "timing__setup__tns" in k):
                metrics.setdefault("tns", _to_float(data[key]))
            # Area (die area if present)
            for key in (k for k in data if "design__die__area" in k):
                metrics.setdefault("gds_area", _to_float(data[key]))
            # Buffers
            for key in (
                "finish__design__instance__count__class:timing_repair_buffer",
                "cts__design__instance__count__setup_buffer",
                "cts__design__instance__count__hold_buffer",
            ):
                if key in data:
                    metrics["buffer_count"] = metrics.get("buffer_count", 0.0) + _to_float(data[key])
        return metrics

    @lru_cache(maxsize=None)
    def _load_json(self, path: Path) -> Dict[str, float]:
        try:
            return json.loads(path.read_text())
        except Exception:
            return {}

    def _stage_jsons(self, case: FlowCase) -> List[Path]:
        candidates = [
            self.flow_root / "logs" / case.pdk / case.variant.name / case.run_tag / fname
            for fname in [
                "6_report.json",
                "6_1_fill.json",
                "5_2_route.json",
                "5_1_grt.json",
                "4_1_cts.json",
                "3_4_place_resized.json",
            ]
        ]
        return [p for p in candidates if p.exists()]

    # ---------------------------------------------------------------------- #
    # Regression and visualization
    # ---------------------------------------------------------------------- #
    def fit_alpha_beta(self, df: pd.DataFrame) -> pd.DataFrame:
        """Fit α, β for area, wirelength, and timing."""
        results: List[Dict[str, object]] = []
        for (pdk, density, clock_ns), group in df.groupby(["pdk", "density", "clock_ns"]):
            if len(group) < 2:
                continue
            features = group[["L", "Q"]].to_numpy()
            with np.errstate(all="ignore"):
                area_model = self._fit_two_var(features, group["gds_area"].to_numpy())
                wl_model = self._fit_two_var(features, group["wirelength"].to_numpy())
                tns_model = self._fit_two_var(features, group["tns"].to_numpy())

            results.append(
                {
                    "pdk": pdk,
                    "density": density,
                    "clock_ns": clock_ns,
                    "alpha_area": area_model[0],
                    "beta_area": area_model[1],
                    "alpha_wirelength": wl_model[0],
                    "beta_wirelength": wl_model[1],
                    "alpha_tns": tns_model[0],
                    "beta_tns": tns_model[1],
                }
            )
        coef_df = pd.DataFrame(results)
        if not coef_df.empty:
            self._plot_heatmap(coef_df, "alpha_area", "α (area)")
            self._plot_heatmap(coef_df, "beta_area", "β (area)")
            self._plot_heatmap(coef_df, "alpha_wirelength", "α (wirelength)")
            self._plot_heatmap(coef_df, "beta_wirelength", "β (wirelength)")
        self._plot_scatter(df)
        self._plot_costs(df, coef_df)
        return coef_df

    @staticmethod
    def _fit_two_var(features: np.ndarray, target: np.ndarray) -> Tuple[float, float, float]:
        """Linear regression with intercept: target ≈ αL + βQ + c."""
        if features.size == 0 or target.size == 0:
            return float("nan"), float("nan"), float("nan")
        A = np.column_stack((features, np.ones(len(features))))
        coef, _, _, _ = np.linalg.lstsq(A, target, rcond=None)
        alpha, beta, intercept = coef
        return float(alpha), float(beta), float(intercept)

    def _plot_scatter(self, df: pd.DataFrame) -> None:
        if df.empty:
            return
        plt.figure(figsize=(10, 6))
        plt.scatter(df["L"], df["gds_area"], c=df["clock_ns"], cmap="viridis", alpha=0.8)
        plt.xlabel("L = Σ|π(i)-i|")
        plt.ylabel("GDS area")
        plt.colorbar(label="clock (ns)")
        plt.title("Area vs L")
        plt.savefig(self.plots_dir / "area_vs_L.png", dpi=200, bbox_inches="tight")
        plt.close()

        plt.figure(figsize=(10, 6))
        plt.scatter(df["Q"], df["gds_area"], c=df["density"], cmap="plasma", alpha=0.8)
        plt.xlabel("Q = Σ|π(i)-i|²")
        plt.ylabel("GDS area")
        plt.colorbar(label="density")
        plt.title("Area vs Q")
        plt.savefig(self.plots_dir / "area_vs_Q.png", dpi=200, bbox_inches="tight")
        plt.close()

        if {"tns", "Q"}.issubset(df.columns):
            plt.figure(figsize=(10, 6))
            plt.scatter(df["Q"], df["tns"], c=df["clock_ns"], cmap="cividis", alpha=0.8)
            plt.xlabel("Q = Σ|π(i)-i|²")
            plt.ylabel("TNS")
            plt.title("Timing vs Q")
            plt.savefig(self.plots_dir / "timing_vs_Q.png", dpi=200, bbox_inches="tight")
            plt.close()

        if {"L", "wirelength"}.issubset(df.columns):
            plt.figure(figsize=(10, 6))
            plt.scatter(df["L"], df["wirelength"], c=df["pdk"].astype("category").cat.codes, cmap="tab20", alpha=0.8)
            plt.xlabel("L = Σ|π(i)-i|")
            plt.ylabel("Wirelength")
            plt.title("Wirelength vs L")
            plt.savefig(self.plots_dir / "wirelength_vs_L.png", dpi=200, bbox_inches="tight")
            plt.close()

    def _plot_costs(self, df: pd.DataFrame, coef_df: pd.DataFrame) -> None:
        """Plot synthesis area, PNR area, and heuristic costs across permutations."""
        if df.empty:
            return
        df = self._compute_costs(df, coef_df)
        for (pdk, density, clock_ns), group in df.groupby(["pdk", "density", "clock_ns"]):
            group = group.sort_values("variant")
            x = range(len(group))
            plt.figure(figsize=(10, 6))
            plt.plot(x, group["synth_area"], marker="o", label="A_synth (logic cost)")
            plt.plot(x, group["gds_area"], marker="o", label="PNR area (actual)")
            plt.plot(x, group["C_phys_pred"], marker="o", label="C_phys predicted")
            plt.xlabel("Permutation index")
            plt.ylabel("Area / cost")
            plt.title(f"Costs for {pdk} density={density*100:.0f}% clock={clock_ns}ns")
            plt.legend()
            fname = f"costs_{pdk}_d{int(density*100)}_c{clock_ns:.2f}.png"
            plt.savefig(self.plots_dir / fname, dpi=200, bbox_inches="tight")
            plt.close()

            # Predicted vs actual scatter
            plt.figure(figsize=(6, 6))
            plt.scatter(group["C_phys_pred"], group["gds_area"], c=group["L"], cmap="viridis", alpha=0.8)
            lims = [
                min(group["C_phys_pred"].min(), group["gds_area"].min()),
                max(group["C_phys_pred"].max(), group["gds_area"].max()),
            ]
            plt.plot(lims, lims, "k--", label="ideal")
            plt.xlabel("Predicted C_phys")
            plt.ylabel("Actual PNR area")
            plt.title(f"Prediction vs actual ({pdk}, d={density*100:.0f}%, c={clock_ns}ns)")
            plt.legend()
            fname = f"pred_vs_actual_{pdk}_d{int(density*100)}_c{clock_ns:.2f}.png"
            plt.savefig(self.plots_dir / fname, dpi=200, bbox_inches="tight")
            plt.close()

    def _plot_heatmap(self, coef_df: pd.DataFrame, column: str, title: str) -> None:
        pivot = coef_df.pivot_table(
            index="pdk",
            columns=["density", "clock_ns"],
            values=column,
        )
        if pivot.empty:
            return
        plt.figure(figsize=(12, 6))
        im = plt.imshow(pivot, aspect="auto", cmap="coolwarm")
        plt.colorbar(im, label=title)
        plt.yticks(range(len(pivot.index)), pivot.index)
        xticks = [f"d{int(d*100)}_c{c:.2f}ns" for d, c in pivot.columns]
        plt.xticks(range(len(xticks)), xticks, rotation=45, ha="right")
        plt.title(f"{title} heatmap")
        plt.tight_layout()
        plt.savefig(self.plots_dir / f"{column}_heatmap.png", dpi=200, bbox_inches="tight")
        plt.close()

    def _compute_costs(self, df: pd.DataFrame, coef_df: pd.DataFrame) -> pd.DataFrame:
        """Compute C_logic and C_phys_pred given alpha/beta per (pdk,density,clock)."""
        df = df.copy()
        df["C_logic"] = df.get("synth_area", df["gds_area"])
        df["C_phys_actual"] = df["gds_area"]

        if coef_df is None or coef_df.empty:
            df["alpha"] = np.nan
            df["beta"] = np.nan
            df["C_phys_pred"] = np.nan
            return df

        coef_map = {
            (row["pdk"], row["density"], row["clock_ns"]): (row["alpha_area"], row["beta_area"])
            for _, row in coef_df.iterrows()
        }

        alphas = []
        betas = []
        preds = []
        for _, row in df.iterrows():
            key = (row["pdk"], row["density"], row["clock_ns"])
            alpha, beta = coef_map.get(key, (np.nan, np.nan))
            alphas.append(alpha)
            betas.append(beta)
            preds.append(row["C_logic"] + alpha * row["L"] + beta * row["Q"] if not math.isnan(alpha) else np.nan)
        df["alpha"] = alphas
        df["beta"] = betas
        df["C_phys_pred"] = preds
        return df

    # ---------------------------------------------------------------------- #
    # Scenario-style orchestration (SUF essence)
    # ---------------------------------------------------------------------- #
    def run_scenario(
        self,
        variants: Sequence[RSCMVariant],
        concurrency: int = 4,
        force: bool = False,
        continue_on_error: bool = True,
    ) -> Tuple[pd.DataFrame, pd.DataFrame | None]:
        """
        Orchestrate PNR runs with simple threaded parallelism, then collect/fit.

        Returns:
            metrics_df, coef_df
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed

        cases = self.build_cases(variants)
        completed: List[FlowCase] = []

        def runner(c: FlowCase) -> FlowCase | None:
            if not force and self._has_metrics(c):
                LOG.info(
                    "Skip PNR for %s/%s@%.0f%%/%.2fns (reports found)",
                    c.variant.name,
                    c.pdk,
                    c.density * 100,
                    c.clock_ns,
                )
                return c
            try:
                self._invoke_flow(c, target="finish")
                return c
            except subprocess.CalledProcessError as exc:
                LOG.error(
                    "PNR failed for %s/%s@%.0f%%/%.2fns: %s",
                    c.variant.name,
                    c.pdk,
                    c.density * 100,
                    c.clock_ns,
                    exc,
                )
                if continue_on_error:
                    return None
                raise

        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            futures = {pool.submit(runner, case): case for case in cases}
            for fut in as_completed(futures):
                res = fut.result()  # may re-raise if continue_on_error=False
                if res is not None:
                    completed.append(res)

        if not completed:
            return pd.DataFrame(), None

        metrics_df = self.collect_metrics(completed)
        coef_df = self.fit_alpha_beta(metrics_df)
        return metrics_df, coef_df


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the RSCM shift experiment.")
    parser.add_argument("--flow-root", type=str, default=None, help="Path to OpenROAD-flow-scripts/flow to use.")
    parser.add_argument("--openroad-exe", type=str, default=None, help="Path to openroad binary.")
    parser.add_argument("--yosys-cmd", type=str, default=None, help="Path to yosys binary.")
    parser.add_argument("--pdks", type=str, default=None, help="Comma-separated PDK list.")
    parser.add_argument("--densities", type=str, default=None, help="Comma-separated densities (e.g., 0.4,0.5,0.6).")
    parser.add_argument("--clocks", type=str, default=None, help="Comma-separated clock periods in ns (e.g., 1.0,0.5).")
    parser.add_argument("--variants", type=int, default=4, help="Number of RTL variants to generate.")
    parser.add_argument("--n", type=int, default=32, help="Operand width N.")
    parser.add_argument("--k", type=int, default=4, help="Slice factor K.")
    parser.add_argument("--concurrency", type=int, default=4, help="Parallel PNR jobs.")
    parser.add_argument("--force", action="store_true", help="Force rerun even if metrics exist.")
    parser.add_argument("--mode", choices=["scenario", "sequential"], default="scenario", help="Execution mode.")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    pdks = args.pdks.split(",") if args.pdks else None
    densities = [float(x) for x in args.densities.split(",")] if args.densities else None
    clocks = [float(x) for x in args.clocks.split(",")] if args.clocks else None

    exp = RSCMShiftExperiment(
        n=args.n,
        k=args.k,
        pdks=pdks,
        densities=densities,
        clock_periods_ns=clocks,
        flow_root=Path(args.flow_root) if args.flow_root else None,
        openroad_exe=args.openroad_exe,
        yosys_cmd=args.yosys_cmd,
    )
    variants = exp.generate_rscm_variants(count=args.variants)

    if args.mode == "scenario":
        metrics_df, coef_df = exp.run_scenario(variants, concurrency=args.concurrency, force=args.force)
    else:
        cases = exp.run_pnr(variants, force=args.force)
        metrics_df = exp.collect_metrics(cases)
        coef_df = exp.fit_alpha_beta(metrics_df)

    if metrics_df is not None:
        print(metrics_df.head())
