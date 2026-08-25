"""
core/fitting/state_delta_fitter.py — A+B per-state parameter deltas.

Consumes the EXISTING FSM pipeline output (state_defs with bit patterns +
state_sequence from FSMStateDetector / TransitionLearner, boundary-mask
aware) and fits, per detected state, sparse deltas on the manifest's
mode_affected parameters only:

- switch-semantics states (enable bit low, scan bits high, DISABLED/
  SHUTDOWN-class names): zero analog deltas by construction.
- HP-class states (HIGH_POWER_MODE bit high): deltas restricted to
  {Gm_ea, I_ea_max, I_lim, I_q}.
- everything else: deltas on {Gm_ea, I_q} (conservative default set).

Deltas are fit in the manifest fit space (log where flagged), additively
on the baseline's fit-space coordinates, L2-regularized to zero. Thin
states (via core.phases.blut_reference.find_thin_states) are skipped with
a note rather than fitted on noise. A hard cap of 40 total floated
dimensions is enforced by tightening the per-state set (documented in
the report when it triggers).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np
from scipy.optimize import least_squares

from .objectives import transient_residual, spec_weights

HP_DELTA_SET = ['Gm_ea', 'I_ea_max', 'I_lim', 'I_q']
DEFAULT_DELTA_SET = ['Gm_ea', 'I_q']
TIGHT_DELTA_SET = ['Gm_ea']
MAX_TOTAL_DIMS = 40


@dataclass
class StateParamSet:
    baseline: Dict[str, float]
    deltas: Dict[str, Dict[str, float]] = field(default_factory=dict)
    reports: Dict[str, dict] = field(default_factory=dict)

    def params_for(self, state_name: str) -> Dict[str, float]:
        p = dict(self.baseline)
        for k, dv in self.deltas.get(state_name, {}).items():
            p[k] = p.get(k, 0.0) + dv
        return p

    def to_json_dict(self) -> dict:
        return {'baseline': self.baseline, 'deltas': self.deltas}

    @classmethod
    def from_json_dict(cls, d: dict) -> "StateParamSet":
        return cls(baseline=dict(d['baseline']),
                   deltas={k: dict(v) for k, v in d.get('deltas', {}).items()})


def _role_map(spec_kg) -> Dict[str, str]:
    """{pin name: fsm_role} from the spec — the only sanctioned way to
    interpret pattern bits (no pin-name literals)."""
    if spec_kg is None:
        return {}
    return {p.name: p.fsm_role for p in getattr(spec_kg, 'ports', [])
            if getattr(p, 'fsm_role', None)}


def _is_switch_state(name: str, pattern: Dict[str, int],
                     role_of: Optional[Dict[str, str]] = None) -> bool:
    """Switch-semantics states get zero analog deltas: the analog core is
    off or in a test topology, so any 'fitted' delta would be noise.
    Detected from the state-name family and, when a spec role map is
    given, from the pattern bits (enable-role pin low / scan-role pin
    high)."""
    u = name.upper()
    if u.startswith(('DISABLED', 'SHUTDOWN', 'FAULT', 'SCAN')):
        return True
    for k, v in (pattern or {}).items():
        role = (role_of or {}).get(k)
        if role == 'enable' and int(v) == 0:
            return True
        if role == 'scan_mode' and int(v) == 1:
            return True
    return False


def _is_hp_state(pattern: Dict[str, int],
                 role_of: Optional[Dict[str, str]] = None) -> bool:
    """High-power sub-mode: the spec's mode_select-role pin asserted."""
    for k, v in (pattern or {}).items():
        if (role_of or {}).get(k) == 'mode_select' and int(v) == 1:
            return True
    return False


def extract_state_records(t: np.ndarray, inputs: Dict[str, np.ndarray],
                          vout_ref: np.ndarray, state_sequence: np.ndarray,
                          state_defs: Dict[int, dict],
                          boundary_mask: Optional[np.ndarray] = None,
                          min_samples: int = 20) -> Dict[str, List[dict]]:
    """Slice a labeled waveform into per-state transient records usable by
    transient_residual: contiguous runs of one state (never crossing a
    concatenation seam from boundary_mask) become records with that
    state's time span. Segments shorter than min_samples are dropped —
    thin-state handling is reported by the fitter."""
    t = np.asarray(t, dtype=float)
    seq = np.asarray(state_sequence, dtype=int)
    n = min(len(t), len(seq))
    bm = (np.asarray(boundary_mask, dtype=bool)[:n]
          if boundary_mask is not None else np.zeros(n, dtype=bool))
    records: Dict[str, List[dict]] = {}
    start = 0
    for i in range(1, n + 1):
        cut = (i == n) or (seq[i] != seq[start]) or bm[i - 1]
        if not cut:
            continue
        if i - start >= min_samples:
            name = state_defs.get(int(seq[start]), {}).get(
                'name', f'STATE_{seq[start]}')
            seg = slice(start, i)
            rec_inputs = {k: (np.asarray(v)[seg] if not np.isscalar(v) else v)
                          for k, v in inputs.items()}
            records.setdefault(name, []).append({
                't': t[seg], 'inputs': rec_inputs,
                'vout_ref': np.asarray(vout_ref)[seg],
            })
        start = i
    return records


class StateDeltaFitter:
    def __init__(self, template, spec_kg=None, l2_lambda: float = 0.05,
                 sensitivity_threshold: float = 1e-3,
                 max_total_dims: int = MAX_TOTAL_DIMS):
        self.template = template
        self.spec_kg = spec_kg
        self.l2_lambda = l2_lambda
        self.sensitivity_threshold = sensitivity_threshold
        self.max_total_dims = max_total_dims
        self._role_of = _role_map(spec_kg)

    def _delta_names_for(self, name: str, pattern: Dict[str, int],
                         tight: bool) -> List[str]:
        man = self.template.manifest()
        allowed = set(man.mode_affected_names())
        if _is_switch_state(name, pattern, self._role_of):
            return []
        if _is_hp_state(pattern, self._role_of):
            base = HP_DELTA_SET
        else:
            base = DEFAULT_DELTA_SET
        if tight:
            base = TIGHT_DELTA_SET
        return [n for n in base if n in allowed]

    def fit(self, baseline_params: Dict[str, float],
            state_records: Dict[str, List[dict]],
            state_defs: Dict[int, dict],
            state_sequence: Optional[np.ndarray] = None) -> StateParamSet:
        man = self.template.manifest()
        w = spec_weights(self.spec_kg)
        result = StateParamSet(baseline=dict(baseline_params))

        pattern_by_name = {d.get('name', f'STATE_{sid}'): d.get('pattern', {})
                           for sid, d in state_defs.items()}

        # Thin-state report (reuses the repo's thin-state detector)
        thin: List[str] = []
        if state_sequence is not None:
            try:
                from core.phases.blut_reference import find_thin_states
                thin = find_thin_states(np.asarray(state_sequence, dtype=int),
                                        state_defs, min_samples=20)
            except Exception:
                thin = []

        # Dimension budget: tighten sets if the plain allocation exceeds cap
        plain_dims = sum(
            len(self._delta_names_for(nm, pattern_by_name.get(nm, {}), False))
            for nm in state_records)
        tight = plain_dims > self.max_total_dims
        if tight:
            result.reports['_budget'] = {
                'note': (f'{plain_dims} floated dims exceeded the cap of '
                         f'{self.max_total_dims}; per-state sets tightened '
                         f'to {TIGHT_DELTA_SET}.')}

        used_dims = 0
        for name, records in state_records.items():
            pattern = pattern_by_name.get(name, {})
            names = self._delta_names_for(name, pattern, tight)
            report = {'delta_names': list(names), 'n_records': len(records),
                      'switch_state': _is_switch_state(name, pattern,
                                                       self._role_of),
                      'thin': name in thin, 'frozen': [], 'sensitivity': {}}
            if not names or name in thin or not records:
                if name in thin:
                    report['note'] = 'thin state — deltas held at zero'
                result.deltas[name] = {}
                result.reports[name] = report
                continue
            if used_dims + len(names) > self.max_total_dims:
                report['note'] = 'dimension cap reached — deltas held at zero'
                result.deltas[name] = {}
                result.reports[name] = report
                continue
            used_dims += len(names)

            base_f = man.to_fit_space(man.to_vector(baseline_params, names),
                                      names)
            lo_f, hi_f = man.fit_space_bounds(names)

            def resid(d_f):
                trial = dict(baseline_params)
                x_f = np.clip(base_f + d_f, lo_f, hi_f)
                trial.update(man.from_vector(man.from_fit_space(x_f, names),
                                             names))
                parts = [transient_residual(self.template, trial, tr, w)
                         for tr in records]
                parts.append(self.l2_lambda * np.asarray(d_f))  # L2 to zero
                return np.concatenate(parts)

            span = np.minimum(hi_f - base_f, base_f - lo_f)
            span = np.maximum(span, 1e-3)
            sol = least_squares(resid, np.zeros(len(names)),
                                bounds=(-span, span), method='trf',
                                max_nfev=40 * len(names))

            # Per-state identifiability: forward sensitivity of the data
            # part of the residual to each delta dim; insensitive deltas
            # freeze to zero (fitted noise is a defect).
            r0 = resid(sol.x)[:-len(names)]
            sens = {}
            keep = np.ones(len(names), dtype=bool)
            for j, nmj in enumerate(names):
                h = 1e-3
                dp = sol.x.copy(); dp[j] += h
                rj = resid(dp)[:-len(names)]
                s = float(np.linalg.norm(rj - r0) / h
                          / max(np.linalg.norm(r0), 1e-9))
                sens[nmj] = s
                if s < self.sensitivity_threshold:
                    keep[j] = False
                    report['frozen'].append(nmj)
            report['sensitivity'] = sens

            x_f = np.clip(base_f + np.where(keep, sol.x, 0.0), lo_f, hi_f)
            fitted_nat = man.from_fit_space(x_f, names)
            base_nat = man.to_vector(baseline_params, names)
            result.deltas[name] = {
                nmj: float(fv - bv)
                for nmj, fv, bv, k in zip(names, fitted_nat, base_nat, keep)
                if k and abs(fv - bv) > 0}
            report['rms'] = float(np.sqrt(np.mean(sol.fun ** 2)))
            result.reports[name] = report

        result.reports['_dims'] = {'floated': used_dims,
                                   'cap': self.max_total_dims}
        return result
