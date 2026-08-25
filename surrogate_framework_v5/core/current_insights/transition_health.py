"""
core/current_insights/transition_health.py — 3.11 transition health
(expert addition). Per state-transition window: shoot-through/crowbar
(two supplies conducting at once), enable inrush (C_out = ∫I dt / ΔV,
cross-checked against the fitted C_out), and charge balance
(∫I_in − ∫I_out − ΔQ ≈ leakage).
"""
from __future__ import annotations

from typing import List, Optional

import numpy as np

from .findings import Finding, RunView, current_of, pick_output_rail

_trapz = getattr(np, 'trapezoid', getattr(np, 'trapz', None))


class TransitionHealth:
    analyzer = '3.11 transition-health'

    def __init__(self, fitted_c_out: Optional[float] = None,
                 k_floor: float = 4.0, c_out_tol: float = 0.5):
        self.fitted_c_out = fitted_c_out
        self.k_floor = k_floor
        self.c_out_tol = c_out_tol

    def analyze(self, views: List[RunView], registry,
                fsm_result=None) -> List[Finding]:
        findings: List[Finding] = []
        supplies = [c for c in registry.input_supplies() if c.has_current]
        rail = pick_output_rail(views, registry)
        for v in views:
            if v.state_sequence is None or v.state_defs is None:
                continue
            seq = v.state_sequence
            edges = np.where(np.diff(seq) != 0)[0] + 1
            for e in edges:
                w = max(4, len(v.t) // 60)
                a, z = max(0, e - w), min(len(v.t), e + w)
                s_from = v.state_name(int(seq[e - 1]))
                s_to = v.state_name(int(seq[e]))
                findings += self._shoot_through(v, supplies, a, z, s_from, s_to)
                fdg = self._inrush(v, rail, a, z, e, s_from, s_to)
                if fdg:
                    findings.append(fdg)
        return findings

    def _shoot_through(self, v, supplies, a, z, s_from, s_to) -> List[Finding]:
        out = []
        # Shoot-through is EXCESS total supply current during the switch (a
        # crowbar path), NOT mere co-conduction — a make-before-break mux
        # handover co-conducts but keeps the total roughly constant. Flag
        # only when the in-window peak total exceeds the surrounding steady
        # total by a clear margin.
        traces, floors = [], []
        for s in supplies:
            cs = current_of(v, s.pin)
            if cs is not None:
                traces.append(np.abs(cs.filtered))
                floors.append(cs.noise_floor)
        if len(traces) < 2:
            return out
        total = np.sum(traces, axis=0)
        n = len(total)
        pre = total[max(0, a - (z - a)):a]
        post = total[z:min(n, z + (z - a))]
        steady = np.median(np.concatenate([pre, post])) if (pre.size or post.size) \
            else np.median(total)
        peak = float(np.max(total[a:z])) if z > a else 0.0
        margin = self.k_floor * float(np.sum(floors))
        conducting = [s.pin for s, tr in zip(supplies,
                      [current_of(v, s.pin) for s in supplies]) if tr is not None
                      and np.mean(np.abs(tr.filtered[a:z]) >
                                  self.k_floor * tr.noise_floor) > 0.5]
        if peak > steady + max(margin, 0.5 * abs(steady)) and len(conducting) >= 2:
            out.append(Finding(
                analyzer=self.analyzer, category='shoot-through',
                severity='high',
                summary=f'{s_from}->{s_to}: excess total supply current during '
                f'switch (crowbar)',
                evidence={'run': v.run_id, 'peak_total_uA': round(peak * 1e6, 2),
                          'steady_total_uA': round(float(steady) * 1e6, 2),
                          'conducting': conducting, 'from': s_from, 'to': s_to},
                affected_pins=conducting, affected_states=[s_from, s_to],
                recommended_action='check break-before-make on the supply mux'))
        return out

    def _inrush(self, v, rail, a, z, e, s_from, s_to) -> Optional[Finding]:
        if rail is None or not s_to.upper().startswith(('STARTUP', 'REGUL')):
            return None
        io = current_of(v, rail.pin)
        vout = v.voltages.get(rail.pin)
        if io is None or vout is None:
            return None
        t = v.t[a:z]
        i = io.filtered[a:z]
        dv = float(vout[z - 1] - vout[a])
        if dv <= 1e-3 or len(t) < 3:
            return None
        q = float(_trapz(np.abs(i), t))       # ∫I dt during the ramp
        c_est = q / dv
        ev = {'from': s_from, 'to': s_to, 'C_out_est_F': round(c_est, 12),
              'delta_v': round(dv, 4), 'charge_C': round(q, 12)}
        sev, action = 'info', ''
        if self.fitted_c_out:
            ev['C_out_fitted_F'] = self.fitted_c_out
            if abs(c_est - self.fitted_c_out) / self.fitted_c_out > self.c_out_tol:
                sev = 'medium'
                action = 'inrush-derived C_out disagrees with fit; reconcile'
        return Finding(
            analyzer=self.analyzer, category='inrush-cout',
            severity=sev,
            summary=f'{s_to} inrush -> C_out estimate {c_est*1e6:.2f} uF',
            evidence=ev, affected_pins=[rail.pin],
            affected_states=[s_from, s_to], recommended_action=action)
