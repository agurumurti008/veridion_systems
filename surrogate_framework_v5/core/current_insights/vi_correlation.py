"""
core/current_insights/vi_correlation.py — 3.5 deep-bug V/I consistency
+ 3.9 V–I impedance extraction. Same (Vout, Iload) via different mode/mux
paths must draw consistent supply current; Zout from V/I spectra (Welch)
+ large-signal secants, reconciled against the template prediction.
"""
from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np

try:
    from scipy.signal import welch, csd
    _SCIPY = True
except ImportError:                       # pragma: no cover
    _SCIPY = False

from .findings import Finding, RunView, current_of, pick_output_rail


class VIConsistency:
    analyzer = '3.5/3.9 vi-consistency'

    def __init__(self, template=None, params=None, tol_frac: float = 0.20,
                 k_floor: float = 3.0):
        self.template = template
        self.params = params
        self.tol_frac = tol_frac
        self.k_floor = k_floor

    def _primary_supply(self, registry):
        # role/taxonomy-driven (no pin-name literals): see
        # CurrentRegistry.primary_input_supply
        return registry.primary_input_supply()

    def analyze(self, views: List[RunView], registry,
                fsm_result=None) -> List[Finding]:
        findings: List[Finding] = []
        findings += self._consistency(views, registry)
        findings += self._impedance(views, registry)
        return findings

    # 3.5 — same operating point, different path -> consistent supply current
    def _consistency(self, views, registry) -> List[Finding]:
        out = []
        sup = self._primary_supply(registry)
        rail = pick_output_rail(views, registry)
        if rail is None or sup is None:
            return out
        # Key by (state, vout_bin, iout_bin) and compare the SAME state at the
        # SAME op-point ACROSS runs (different mux/mode paths). Comparing
        # different states would flag legitimate STARTUP-vs-REGULATION
        # differences (false positive); the deep-bug signature is identical
        # state + op-point drawing different supply current on a different
        # path.
        # Compare TOTAL input-supply current (sum over all supplies), not
        # just the primary: a make-before-break mux handover moves current
        # between supplies but keeps the total constant, so summing avoids
        # false positives while still catching a genuine internal leak.
        supplies = [c for c in registry.input_supplies() if c.has_current]
        buckets: Dict[tuple, Dict[str, list]] = {}
        for v in views:
            if v.state_sequence is None or v.state_defs is None:
                continue
            vv = v.voltages.get(rail.pin)
            io = current_of(v, rail.pin)
            if vv is None or io is None:
                continue
            sup_traces = [current_of(v, c.pin) for c in supplies]
            sup_traces = [s for s in sup_traces if s is not None]
            if not sup_traces:
                continue
            i_tot = np.sum([np.abs(s.filtered) for s in sup_traces], axis=0)
            for i in range(len(v.t)):
                st = v.state_name(int(v.state_sequence[i])) \
                    if i < len(v.state_sequence) else '?'
                key = (st, round(float(vv[i]), 2),
                       round(float(io.filtered[i]) * 1e4) / 1e4)
                path = f'{v.run_id}@{v.corner}'
                buckets.setdefault(key, {}).setdefault(path, []).append(
                    float(i_tot[i]))
        for (st, vb, ib), per_path in buckets.items():
            means = {p: float(np.mean(xs)) for p, xs in per_path.items()
                     if len(xs) >= 3}
            if len(means) < 2:            # need ≥2 paths at this op-point
                continue
            lo, hi = min(means.values()), max(means.values())
            ref = max(abs(hi), abs(lo), 1e-9)
            if (hi - lo) / ref > self.tol_frac:
                out.append(Finding(
                    analyzer=self.analyzer, category='vi-inconsistency',
                    severity='high',
                    summary=f'{st} at (Vout={vb}V, Iout={ib*1e3:.2f}mA) draws '
                    f'inconsistent supply current across paths',
                    evidence={'state': st, 'vout_V': vb, 'iout_A': ib,
                              'supply_current_by_path_uA':
                              {p: round(m * 1e6, 2) for p, m in means.items()},
                              'spread_frac': round((hi - lo) / ref, 3)},
                    affected_pins=[sup.pin, rail.pin], affected_states=[st],
                    recommended_action='same state+op-point via different '
                    'mode/mux should match; investigate internal leakage/'
                    'routing'))
        return out

    # 3.9 — Zout extraction + template reconciliation
    def _impedance(self, views, registry) -> List[Finding]:
        out = []
        rail = pick_output_rail(views, registry)
        if rail is None:
            return out
        secants = []
        zout_f = None
        for v in views:
            vv = v.voltages.get(rail.pin)
            io = current_of(v, rail.pin)
            if vv is None or io is None:
                continue
            # Large-signal Zout = |dV/dI| as the regression slope of V(out)
            # on I(out) over the trace — robust to smoothing and noise
            # (per-sample dv/di is destroyed by the SG window and pollutes
            # 0/0 in flat regions). Needs a meaningful current excursion.
            i_ptp = float(np.max(io.filtered) - np.min(io.filtered))
            if i_ptp > max(5 * io.noise_floor, 1e-4):
                slope = np.polyfit(io.filtered, vv, 1)[0]
                if np.isfinite(slope) and abs(slope) > 0:
                    secants.append(abs(float(slope)))
            if _SCIPY and zout_f is None and len(v.t) >= 64:
                dt = float(np.median(np.diff(v.t)))
                fs = 1.0 / dt if dt > 0 else 1.0
                nps = min(256, len(v.t))
                f, pii = welch(io.filtered, fs=fs, nperseg=nps)
                _, pvi = csd(io.filtered, vv, fs=fs, nperseg=nps)
                with np.errstate(divide='ignore', invalid='ignore'):
                    z = np.abs(pvi) / np.maximum(pii, 1e-30)
                zout_f = (f, z)
        if not secants and zout_f is None:
            return out
        z_ls = float(np.median(secants)) if secants else None
        ev = {'rail': rail.pin}
        if z_ls is not None:
            ev['large_signal_Zout_ohm'] = round(z_ls, 3)
        sev = 'info'
        action = ''
        if self.template is not None and self.params is not None and z_ls:
            op = self.template.dc_solve(self.params, 5.0, 0.05)
            ss = self.template.small_signal(self.params, op)
            z_dc = float(ss['zout'][0])
            ev['template_Zout_dc_ohm'] = round(z_dc, 3)
            if z_dc > 0 and abs(z_ls - z_dc) / z_dc > self.tol_frac:
                sev = 'medium'
                action = 'measured Zout disagrees with template; trigger refit'
                ev['refit_trigger'] = True
        out.append(Finding(
            analyzer=self.analyzer, category='impedance',
            severity=sev,
            summary=f'{rail.pin} Zout extracted'
            + (f' ({z_ls:.2f} ohm large-signal)' if z_ls else ''),
            evidence=ev, affected_pins=[rail.pin],
            recommended_action=action))
        return out
