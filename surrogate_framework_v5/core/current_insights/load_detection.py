"""
core/current_insights/load_detection.py — 3.8 dummy-load auto-detection.

Without being told a pin's function, correlate each mode/control pin's
edges with output/supply current steps at constant external stimulus; a
consistent current increase on assertion classifies the pin as an internal
load and quantifies it. Emits a pin-taxonomy enrichment proposal.
"""
from __future__ import annotations

from typing import List, Optional

import numpy as np

from .findings import Finding, RunView, current_of, pick_output_rail


class LoadDetection:
    analyzer = '3.8 dummy-load-detect'

    def __init__(self, k_floor: float = 4.0, min_consistency: float = 0.6):
        self.k_floor = k_floor
        self.min_consistency = min_consistency
        self.enrichment_proposals: List[dict] = []

    def analyze(self, views: List[RunView], registry,
                fsm_result=None) -> List[Finding]:
        findings: List[Finding] = []
        self.enrichment_proposals = []
        sink = pick_output_rail(views, registry)
        if sink is None:
            return findings
        # Detection threshold is relative to the OUTPUT current's own noise
        # floor (not a fixed absolute): a real dummy load steps the output
        # current well above its floor, while a SEL/mode toggle only jitters
        # it at the floor (else every toggle would look like a load).
        sink_floors = [current_of(v, sink.pin).noise_floor for v in views
                       if current_of(v, sink.pin) is not None]
        sink_floor = float(np.median(sink_floors)) if sink_floors else 1e-9
        # candidate pins: digital controls, excluding enable (its edge changes
        # the whole operating point, not just an added load)
        cands = [c for c in registry.channels.values()
                 if c.domain == 'digital' and c.role in ('control', 'select',
                                                          'load_control')]
        for ch in cands:
            deltas = []
            for v in views:
                vv = v.voltages.get(ch.pin)
                io = current_of(v, sink.pin)
                vout = v.voltages.get(sink.pin)
                if vv is None or io is None:
                    continue
                lo, hi = float(np.nanmin(vv)), float(np.nanmax(vv))
                if hi - lo < 0.5:
                    continue
                b = (vv > (lo + hi) / 2).astype(int)
                for e in np.where(np.diff(b) != 0)[0] + 1:
                    w = max(5, len(v.t) // 40)
                    a0, a1 = max(0, e - w), max(1, e - 2)
                    b0, b1 = min(len(v.t) - 1, e + 2), min(len(v.t), e + w)
                    if a1 <= a0 or b1 <= b0:
                        continue
                    # constant external stimulus: output voltage steady
                    if vout is not None:
                        if abs(np.mean(vout[b0:b1]) - np.mean(vout[a0:a1])) > \
                                0.05 * max(abs(np.mean(vout[a0:a1])), 1e-3):
                            continue
                    d_on = (np.mean(io.filtered[b0:b1])
                            - np.mean(io.filtered[a0:a1]))
                    direction = 1 if b[e] == 1 else -1
                    deltas.append(direction * d_on)  # asserted -> +load
            if len(deltas) < 2:
                continue
            deltas = np.array(deltas)
            pos = float(np.mean(deltas > 0))
            mag = float(np.median(np.abs(deltas)))
            floor_ok = mag > self.k_floor * sink_floor
            if pos >= self.min_consistency and floor_ok:
                self.enrichment_proposals.append({
                    'pin': ch.pin, 'proposed_category': 'internal_load',
                    'added_load_A': round(mag, 6),
                    'evidence': 'assertion -> consistent output-current rise'})
                findings.append(Finding(
                    analyzer=self.analyzer, category='dummy-load-detected',
                    severity='info',
                    summary=f'{ch.pin} classified internal load '
                    f'(+{mag*1e6:.1f} uA on assertion)',
                    evidence={'pin': ch.pin, 'added_load_uA': round(mag * 1e6, 2),
                              'consistency': round(pos, 2),
                              'n_edges': len(deltas)},
                    affected_pins=[ch.pin],
                    recommended_action='accept taxonomy enrichment: '
                    f'{ch.pin} -> internal_load ({mag*1e6:.1f} uA)'))
        return findings
