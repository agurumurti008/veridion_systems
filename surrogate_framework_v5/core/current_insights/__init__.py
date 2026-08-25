"""
core/current_insights — Capability A: current signals as first-class
intrinsic-behavior evidence (attribution, verification, drive strength,
bug detection, impedance), never as FSM state variables.

Contract boundary: analyzers consume SignalCapture.current_signals / run
dicts and FSMStateDetector outputs (read-only); nothing here writes the
logic matrix passed to detect(). Only state_signatures (3.10) proposes
post-detection relabels.
"""
from .filtering import (
    FilteredSignal, FilterLog, estimate_noise_floor, filter_current,
    filter_signals,
)
from .registry import CurrentRegistry, PinChannel
from .findings import (
    Finding, RunView, build_run_views, InsightReport, EfficiencySequencing,
    current_of,
)
from .supply_attribution import SupplyAttribution, MuxVerification
from .edge_correlation import EdgeThresholdCorrelation
from .drive_strength import DriveStrength
from .vi_correlation import VIConsistency
from .load_detection import LoadDetection
from .state_signatures import StateSignatures
from .transition_health import TransitionHealth


def default_analyzers(template=None, params=None, fitted_c_out=None):
    """The standard analyzer battery. template/params/fitted_c_out enable
    the fit-reconciliation paths (3.9 Zout, 3.11 C_out); omit them for a
    data-only pass."""
    return [
        SupplyAttribution(), MuxVerification(), EdgeThresholdCorrelation(),
        DriveStrength(), VIConsistency(template=template, params=params),
        LoadDetection(), StateSignatures(),
        TransitionHealth(fitted_c_out=fitted_c_out), EfficiencySequencing(),
    ]


def run_analyzers(views, registry, analyzers=None, fsm_result=None,
                  template=None, params=None, fitted_c_out=None):
    """Run every analyzer, collect findings; also return the analyzer
    objects so callers can read side outputs (LoadDetection.enrichment_
    proposals, StateSignatures.relabel_proposals/signatures)."""
    analyzers = analyzers or default_analyzers(template, params, fitted_c_out)
    findings = []
    for az in analyzers:
        findings.extend(az.analyze(views, registry, fsm_result=fsm_result))
    return findings, analyzers


__all__ = [
    'FilteredSignal', 'FilterLog', 'estimate_noise_floor', 'filter_current',
    'filter_signals', 'CurrentRegistry', 'PinChannel',
    'Finding', 'RunView', 'build_run_views', 'InsightReport', 'current_of',
    'SupplyAttribution', 'MuxVerification', 'EdgeThresholdCorrelation',
    'DriveStrength', 'VIConsistency', 'LoadDetection', 'StateSignatures',
    'TransitionHealth', 'EfficiencySequencing',
    'default_analyzers', 'run_analyzers',
]
