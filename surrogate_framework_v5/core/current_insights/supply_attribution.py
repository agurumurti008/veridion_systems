"""
core/current_insights/supply_attribution.py — 3.1 multi-supply attribution
+ 3.4 true-logic (mux) verification via current redistribution.
"""
from __future__ import annotations

from typing import List, Optional

import numpy as np

from core.templates.pin_taxonomy import hook_for_pin
from .findings import Finding, RunView, current_of


class SupplyAttribution:
    """3.1 — per-state current per input supply, dominance ranking, and a
    mismatch Finding when the taxonomy's primary supply (`vin` hook) is not
    the dominant source in an active (non-DISABLED) state."""

    analyzer = '3.1 supply-attribution'

    def __init__(self, k_floor: float = 3.0):
        self.k_floor = k_floor

    def _primary(self, registry) -> Optional[str]:
        for c in registry.input_supplies():
            if hook_for_pin(c.pin) == 'vin':
                return c.pin
        sup = registry.input_supplies()
        return sup[0].pin if sup else None

    def analyze(self, views: List[RunView], registry,
                fsm_result=None) -> List[Finding]:
        findings: List[Finding] = []
        supplies = registry.input_supplies()
        primary = self._primary(registry)

        for v in views:
            if v.state_sequence is None or v.state_defs is None:
                continue
            for sid in np.unique(v.state_sequence):
                mask = v.state_sequence == sid
                if mask.sum() < 3:
                    continue
                sname = v.state_name(int(sid))
                ranking = []
                for s in supplies:
                    cs = current_of(v, s.pin)
                    if cs is None:
                        continue
                    seg = cs.filtered[mask]
                    ranking.append((s.pin, float(np.mean(np.abs(seg))),
                                    float(np.sqrt(np.mean(seg ** 2)))))
                if not ranking:
                    continue
                ranking.sort(key=lambda r: -r[1])
                findings.append(Finding(
                    analyzer=self.analyzer, category='supply-dominance',
                    severity='info',
                    summary=f'{sname}: dominant supply {ranking[0][0]} '
                    f'({ranking[0][1]*1e6:.1f} uA)',
                    evidence={'state': sname, 'ranking_uA_mean_rms': [
                        (p, round(m * 1e6, 2), round(r * 1e6, 2))
                        for p, m, r in ranking]},
                    affected_states=[sname]))
                # mismatch: primary not dominant in a non-DISABLED state
                if (primary and not sname.upper().startswith('DISABLED')
                        and ranking[0][0] != primary):
                    prim = next((r for r in ranking if r[0] == primary), None)
                    if prim is None or ranking[0][1] > 3 * prim[1]:
                        findings.append(Finding(
                            analyzer=self.analyzer,
                            category='unexpected-supply-domain',
                            severity='high',
                            summary=f'{sname} powered mainly from {ranking[0][0]}'
                            f', not primary {primary}',
                            evidence={'state': sname, 'dominant': ranking[0][0],
                                      'primary': primary,
                                      'ranking': [(p, round(m * 1e6, 2))
                                                  for p, m, _ in ranking]},
                            affected_pins=[ranking[0][0], primary],
                            affected_states=[sname],
                            recommended_action='confirm intended supply for '
                            'this state; possible mux/routing bug'))
        return findings


class MuxVerification:
    """3.4 — SEL-class pins are unverifiable from voltages when all candidate
    supplies are high; per-supply current redistribution on a SEL toggle is
    the proof. No candidate shift on toggle -> untested-mux (high)."""

    analyzer = '3.4 mux-verification'

    def __init__(self, k_floor: float = 4.0, guard: int = 3):
        self.k_floor = k_floor
        self.guard = guard

    def _edges(self, v: RunView, pin: str):
        vv = v.voltages.get(pin)
        if vv is None:
            return [], None
        lo, hi = float(np.nanmin(vv)), float(np.nanmax(vv))
        if hi - lo < 0.5:
            return [], None
        b = (vv > (lo + hi) / 2).astype(int)
        return list(np.where(np.diff(b) != 0)[0] + 1), b

    def analyze(self, views: List[RunView], registry,
                fsm_result=None) -> List[Finding]:
        findings: List[Finding] = []
        for sel in registry.selects():
            cands = registry.mux_candidates(sel.pin)
            if len(cands) < 2:
                continue
            for v in views:
                edges, _ = self._edges(v, sel.pin)
                if not edges:
                    continue
                shifts_seen = False
                for e in edges:
                    n = len(v.t)
                    w = max(5, n // 50)
                    a0, a1 = max(0, e - w), max(1, e - self.guard)
                    b0, b1 = min(n - 1, e + self.guard), min(n, e + w)
                    if a1 <= a0 or b1 <= b0:
                        continue
                    deltas = []
                    for c in cands:
                        cs = current_of(v, c.pin)
                        if cs is None:
                            continue
                        before = np.mean(cs.filtered[a0:a1])
                        after = np.mean(cs.filtered[b0:b1])
                        d = float(after - before)
                        if abs(d) > self.k_floor * cs.noise_floor:
                            deltas.append((c.pin, d))
                    if deltas:
                        shifts_seen = True
                        gain = max(deltas, key=lambda x: x[1])
                        drop = min(deltas, key=lambda x: x[1])
                        findings.append(Finding(
                            analyzer=self.analyzer, category='mux-verified',
                            severity='info',
                            summary=f'{sel.pin} toggle: current shifted to '
                            f'{gain[0]} from {drop[0]}',
                            evidence={'sel': sel.pin, 'run': v.run_id,
                                      'gained_uA': round(gain[1] * 1e6, 2),
                                      'dropped_uA': round(drop[1] * 1e6, 2)},
                            affected_pins=[sel.pin, gain[0], drop[0]]))
                if edges and not shifts_seen:
                    findings.append(Finding(
                        analyzer=self.analyzer, category='untested-mux',
                        severity='high',
                        summary=f'{sel.pin} toggled but no candidate supply '
                        f'current redistributed — mux path unverified',
                        evidence={'sel': sel.pin, 'run': v.run_id,
                                  'candidates': [c.pin for c in cands],
                                  'n_toggles': len(edges)},
                        affected_pins=[sel.pin] + [c.pin for c in cands],
                        recommended_action='provide a SEL-toggle run with all '
                        'candidate supplies live to prove the selected path'))
        return findings
