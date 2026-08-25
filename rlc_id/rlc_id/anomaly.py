"""Golden-vs-measured anomaly detection: Vector-Fits both a golden (expected/design)
model and measured data on the same frequency grid, differences poles/residues,
flags shifts above threshold, and uses golden-model sensitivity analysis to report
which physical components COULD explain an observed shift -- surfacing ambiguity
rather than a single point answer (see accompanying analysis, Section 6: multiple
parasitic sources often produce indistinguishable pole shifts from port data alone).
"""
from __future__ import annotations
from dataclasses import dataclass
import copy
import numpy as np
from .methods.vector_fitting import VectorFittingIdentifier
from .core.utils import match_poles
from .synth import cascaded_ladder_from_components


@dataclass
class PoleShift:
    golden_idx: int
    measured_idx: int
    golden_pole: complex
    measured_pole: complex
    abs_shift: float
    rel_shift: float
    is_anomaly: bool


@dataclass
class AnomalyReport:
    golden_poles: np.ndarray
    measured_poles: np.ndarray
    shifts: list  # list[PoleShift]
    anomalies: list  # subset of shifts where is_anomaly=True
    unmatched_golden: list  # golden pole indices with no measured counterpart (vanished mode)
    unmatched_measured: list  # measured pole indices with no golden counterpart (new resonance)
    threshold: float

    def summary(self) -> str:
        lines = [f"Anomaly report ({len(self.anomalies)}/{len(self.shifts)} poles flagged, "
                 f"threshold={self.threshold:.1%} relative shift):"]
        for s in self.anomalies:
            lines.append(f"  pole[{s.golden_idx}]: {s.golden_pole:.4e} -> {s.measured_pole:.4e} "
                         f"({s.rel_shift:.1%} shift)")
        if self.unmatched_golden:
            lines.append(f"  {len(self.unmatched_golden)} golden pole(s) not observed in measured data "
                         f"(possibly vanished/over-damped mode)")
        if self.unmatched_measured:
            lines.append(f"  {len(self.unmatched_measured)} new pole(s) in measured data with no golden "
                         f"counterpart (possible new resonance / added parasitic)")
        return "\n".join(lines)


def fit_golden_and_measured(golden_net, w: np.ndarray, measured_H: np.ndarray,
                             order: int | None = None, vf_kwargs: dict | None = None):
    """Fit Vector Fitting to both the golden network's analytic response and
    measured data on the SAME frequency grid (required for a well-posed comparison
    -- fitting on different grids would confound genuine shifts with fit-grid
    artifacts)."""
    vf_kwargs = dict(vf_kwargs or {})
    A, B, C, D = golden_net.ss
    I = np.eye(A.shape[0])
    H_golden = np.array([(C @ np.linalg.solve(1j * wk * I - A, B) + D).item() for wk in w])

    order = order or len(golden_net.poles)
    vf_golden = VectorFittingIdentifier(**vf_kwargs)
    vf_golden.fit(w, None, H_golden, order=order)

    vf_measured = VectorFittingIdentifier(**vf_kwargs)
    vf_measured.fit(w, None, measured_H, order=order)
    return vf_golden, vf_measured


def diff_poles(golden_poles: np.ndarray, measured_poles: np.ndarray,
                rel_threshold: float = 0.05) -> AnomalyReport:
    """Hungarian-match golden and measured poles, flag shifts exceeding threshold."""
    assignment, _ = match_poles(golden_poles, measured_poles)
    shifts = []
    matched_g, matched_m = set(), set()
    for gi, mi in assignment:
        gp, mp = golden_poles[gi], measured_poles[mi]
        abs_shift = abs(mp - gp)
        rel_shift = abs_shift / abs(gp) if abs(gp) > 0 else np.inf
        shifts.append(PoleShift(gi, mi, gp, mp, abs_shift, rel_shift, rel_shift > rel_threshold))
        matched_g.add(gi)
        matched_m.add(mi)
    anomalies = [s for s in shifts if s.is_anomaly]
    unmatched_golden = [i for i in range(len(golden_poles)) if i not in matched_g]
    unmatched_measured = [i for i in range(len(measured_poles)) if i not in matched_m]
    return AnomalyReport(golden_poles, measured_poles, shifts, anomalies,
                          unmatched_golden, unmatched_measured, rel_threshold)


def component_sensitivity(golden_stage_params: list, delta_frac: float = 0.01) -> dict:
    """Finite-difference sensitivity d(pole)/d(component) for every {R,L,C} in a
    cascaded-ladder golden model, used to disambiguate which physical component
    could explain an observed pole shift. Returns {(stage_idx, 'R'|'L'|'C'):
    {'d_pole': array of d(pole_k)/d(param) per golden pole index k,
     'baseline_value': the component's golden value}}."""
    baseline_net = cascaded_ladder_from_components(golden_stage_params)
    baseline_poles = baseline_net.poles
    sensitivities = {}
    for stage_idx, stage in enumerate(golden_stage_params):
        for param in ("R", "L", "C"):
            perturbed = copy.deepcopy(golden_stage_params)
            baseline_value = perturbed[stage_idx][param]
            delta = baseline_value * delta_frac
            perturbed[stage_idx][param] += delta
            perturbed_net = cascaded_ladder_from_components(perturbed)
            assignment, _ = match_poles(baseline_poles, perturbed_net.poles)
            d_pole = np.zeros(len(baseline_poles), dtype=complex)
            for gi, mi in assignment:
                d_pole[gi] = (perturbed_net.poles[mi] - baseline_poles[gi]) / delta
            sensitivities[(stage_idx, param)] = {"d_pole": d_pole, "baseline_value": baseline_value}
    return sensitivities


def explain_shift(pole_shift: PoleShift, sensitivities: dict, top_n: int = 3) -> list:
    """Rank candidate (stage, component) explanations for a single observed pole
    shift by how well d(pole)/d(param)*delta could reproduce the observed shift --
    reports the top_n candidates with their implied delta, NOT a single answer,
    since multiple physical causes are often indistinguishable from port data alone."""
    gi = pole_shift.golden_idx
    observed = pole_shift.measured_pole - pole_shift.golden_pole
    candidates = []
    for (stage_idx, param), info in sensitivities.items():
        sens = info["d_pole"][gi]
        if abs(sens) < 1e-30:
            continue
        implied_delta_abs = (observed / sens).real  # linear approx: observed ~= sens * delta
        residual = abs(observed - sens * implied_delta_abs)
        candidates.append({
            "stage": stage_idx, "component": param,
            "implied_delta_abs": implied_delta_abs,
            "implied_delta_frac": implied_delta_abs / info["baseline_value"],
            "fit_residual": residual,
        })
    candidates.sort(key=lambda c: c["fit_residual"])
    return candidates[:top_n]
