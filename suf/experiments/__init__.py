#!/usr/bin/env python
"""Experiment orchestrators for SUF.

Imports are kept lazy to avoid double-import warnings when running modules via
`python -m suf.experiments.<module>`.
"""

__all__ = ["FlowCase", "RSCMShiftExperiment", "SimpleFlowExperiment", "SimpleFlowCase", "SimpleFlowMain"]


def __getattr__(name):
    if name in ("FlowCase", "RSCMShiftExperiment"):
        from .rscm_shift_experiment import FlowCase, RSCMShiftExperiment

        return {"FlowCase": FlowCase, "RSCMShiftExperiment": RSCMShiftExperiment}[name]
    if name == "SimpleFlowExperiment":
        from .simple_flow_experiment import SimpleFlowExperiment

        return SimpleFlowExperiment
    if name == "SimpleFlowCase":
        from .simple_flow_helpers import FlowCase as SimpleFlowCase

        return SimpleFlowCase
    if name == "SimpleFlowMain":
        from .simple_flow_experiment import main as SimpleFlowMain

        return SimpleFlowMain
    raise AttributeError(f"module {__name__} has no attribute {name}")
