"""
core/current_insights/edge_correlation.py — 3.2 current-edge ↔ logic-
threshold correlation. A logic input crossing its real switching point
draws an input-current spike; the pin voltage at that spike localizes the
effective VIH/VIL, compared against the spec-JSON domain nominal.
"""
from __future__ import annotations

from typing import List

import numpy as np

from .findings import Finding, RunView, current_of


class EdgeThresholdCorrelation:
    analyzer = '3.2 edge-threshold'

    def __init__(self, tol_frac: float = 0.15, k_floor: float = 4.0):
        self.tol_frac = tol_frac       # allowed |eff-nominal| as frac of span
        self.k_floor = k_floor

    def analyze(self, views: List[RunView], registry,
                fsm_result=None) -> List[Finding]:
        findings: List[Finding] = []
        digital = [c for c in registry.channels.values()
                   if c.domain == 'digital' and c.has_current]
        for ch in digital:
            lo, hi = float(ch.v_range[0]), float(ch.v_range[1])
            span = hi - lo
            if span <= 0:
                continue
            nominal = (lo + hi) / 2
            eff_thresholds = []
            for v in views:
                vv = v.voltages.get(ch.pin)
                cs = current_of(v, ch.pin)
                if vv is None or cs is None:
                    continue
                b = (vv > nominal).astype(int)
                crossings = np.where(np.diff(b) != 0)[0] + 1
                for cidx in crossings:
                    w = max(5, len(v.t) // 60)
                    a, z = max(0, cidx - w), min(len(v.t), cidx + w)
                    seg_c = np.abs(cs.filtered[a:z])
                    if seg_c.size == 0:
                        continue
                    # the input draws PEAK current as it crosses its real
                    # switching point — read the pin voltage at the current
                    # magnitude peak (not the derivative, which peaks at the
                    # bump edges, offset from the crossing).
                    if seg_c.max() < self.k_floor * cs.noise_floor:
                        continue
                    pk = a + int(np.argmax(seg_c))
                    eff_thresholds.append(float(vv[pk]))
            if len(eff_thresholds) < 2:
                continue
            eff = float(np.median(eff_thresholds))
            spread = float(np.std(eff_thresholds))
            conf = float(1.0 / (1.0 + spread / max(span, 1e-9)))
            dev = abs(eff - nominal)
            sev = 'medium' if dev > self.tol_frac * span else 'info'
            findings.append(Finding(
                analyzer=self.analyzer,
                category='effective-threshold',
                severity=sev,
                summary=f'{ch.pin} effective threshold {eff:.2f} V '
                f'(nominal {nominal:.2f} V, conf {conf:.2f})',
                evidence={'pin': ch.pin, 'effective_V': round(eff, 3),
                          'nominal_V': round(nominal, 3),
                          'n_edges': len(eff_thresholds),
                          'spread_V': round(spread, 3),
                          'confidence': round(conf, 3)},
                affected_pins=[ch.pin],
                recommended_action=('' if sev == 'info' else
                                    'effective switch point deviates from '
                                    'domain nominal; verify level-shifter')))
        return findings
