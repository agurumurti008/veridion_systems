"""
core/ab_integration/insights_pipeline.py — Section 5 optional insights phase.

Ties Capability A (current_insights) + Capability B (fsm_completeness) into
one phase that runs AFTER FSM detection and alongside/after fitting. It is
strictly opt-in: nothing here runs unless a caller invokes it, so the POC
path (example5, plain emit) is unchanged (regression guard 5.4). Produces
the insight report, the gap report, and the three codegen extras
(iq_signatures, Option-2 limitations, load enrichment) that emit() consumes.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from core.current_insights import (
    CurrentRegistry, build_run_views, run_analyzers, InsightReport,
    StateSignatures,
)
from core.fsm_completeness import evaluate, build_gap_report


@dataclass
class InsightsPhaseResult:
    insight_report: InsightReport
    gap_report: object
    coverage: object
    reference_space: object
    findings: list
    iq_signatures: Dict[str, tuple] = field(default_factory=dict)
    limitations: List[str] = field(default_factory=list)
    load_enrichment: List[dict] = field(default_factory=list)
    relabel_proposals: List[dict] = field(default_factory=list)
    fit_cross_checks: List[str] = field(default_factory=list)


def run_insights_phase(spec_kg, signal_map, runs, fsm_result,
                       state_sequences=None, ip_type='LDO', template=None,
                       params=None, fit_result=None, output_dir=None,
                       corners_expected: int = 3) -> InsightsPhaseResult:
    """runs: load_all_runs run dicts (with $flow currents). state_sequences:
    {run_id@corner|run_id: per-run state seq}. fit_result: optional FitResult
    for the 3.3/3.9/3.11 reconciliation logs."""
    registry = CurrentRegistry(spec_kg, signal_map)
    state_defs = getattr(fsm_result, 'state_defs', None)
    views = build_run_views(runs, registry, state_sequences=state_sequences,
                            state_defs=state_defs)

    fitted_c_out = None
    if fit_result is not None:
        fitted_c_out = getattr(fit_result, 'params', {}).get('C_out')
    findings, analyzers = run_analyzers(
        views, registry, fsm_result=fsm_result, template=template,
        params=params, fitted_c_out=fitted_c_out)

    filter_logs = []
    for v in views:
        for cs in v.currents.values():
            filter_logs.append(cs.log.as_row())
    insight_report = InsightReport(findings, registry=registry,
                                   filter_logs=filter_logs)

    # side outputs
    load_enrichment: List[dict] = []
    relabel: List[dict] = []
    for az in analyzers:
        load_enrichment += getattr(az, 'enrichment_proposals', [])
        relabel += getattr(az, 'relabel_proposals', [])
    sig_az = next((a for a in analyzers if isinstance(a, StateSignatures)),
                  StateSignatures())
    iq_signatures = sig_az.signatures(views, registry)

    # completeness + gap report (output signatures — either passed on the
    # fsm_result or computed upstream by the detector — feed the
    # output-consistency section)
    coverage, ref, profile = evaluate(
        ip_type, fsm_result, views, registry=registry,
        insight_findings=findings,
        output_signatures=getattr(fsm_result, 'output_signatures', None))
    gap_report = build_gap_report(coverage, ref, profile,
                                  corners_expected=corners_expected,
                                  registry=registry)

    # fit cross-checks (3.3 capacity, 3.9 impedance, 3.11 C_out) reconciled
    cross = []
    for f in findings:
        if f.category == 'param-bound' and fit_result is not None:
            cur = getattr(fit_result, 'params', {}).get(
                f.evidence.get('param'))
            cross.append(f"{f.evidence.get('param')}: fit={cur} vs bound "
                         f"{f.evidence.get('suggested_upper_bound_A')} A")
        if f.category == 'impedance' and 'template_Zout_dc_ohm' in f.evidence:
            cross.append(
                f"Zout: measured {f.evidence.get('large_signal_Zout_ohm')} vs "
                f"template {f.evidence.get('template_Zout_dc_ohm')} ohm")
        if f.category == 'inrush-cout' and 'C_out_fitted_F' in f.evidence:
            cross.append(f"C_out: inrush {f.evidence.get('C_out_est_F')} vs "
                         f"fit {f.evidence.get('C_out_fitted_F')} F")

    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        insight_report.to_markdown(os.path.join(output_dir,
                                                 'insight_findings.md'))
        insight_report.to_json(os.path.join(output_dir,
                                            'insight_findings.json'))
        gap_report.to_markdown(os.path.join(output_dir, 'gap_report.md'))
        gap_report.to_json(os.path.join(output_dir, 'gap_report.json'))

    return InsightsPhaseResult(
        insight_report=insight_report, gap_report=gap_report,
        coverage=coverage, reference_space=ref, findings=findings,
        iq_signatures=iq_signatures,
        limitations=gap_report.option2_limitations,
        load_enrichment=load_enrichment, relabel_proposals=relabel,
        fit_cross_checks=cross)
