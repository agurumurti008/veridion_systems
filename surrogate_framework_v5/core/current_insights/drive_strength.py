"""
core/current_insights/drive_strength.py — 3.3 drive-strength interdependency
+ 3.7 max-capacity check. Output current vs output droop gives the effective
sustainable drive; demand beyond it collapses the rail (fault propagation);
the fitted capacity tightens the template's I_lim/k_load bounds.
"""
from __future__ import annotations

from typing import List, Optional

import numpy as np

from .findings import Finding, RunView, current_of, pick_output_rail


class DriveStrength:
    analyzer = '3.3/3.7 drive-strength'

    def __init__(self, max_load_default: float = 0.2, k_floor: float = 3.0):
        self.max_load_default = max_load_default
        self.k_floor = k_floor

    def _vout_min(self, registry) -> float:
        for s in registry.spec_kg.specs:
            if s.name == 'Output_Voltage':
                return float(s.min_val)
        return 1.176

    @staticmethod
    def _to_amps(val: float, unit: str) -> float:
        u = (unit or '').lower()
        return {'a': 1.0, 'ma': 1e-3, 'ua': 1e-6, 'µa': 1e-6,
                'na': 1e-9}.get(u, 1.0) * float(val)

    def _max_load_spec(self, registry) -> float:
        # required sustainable current = the spec's guaranteed minimum
        # (e.g. Max_Load_Current 200 mA @ SS), unit-converted to Amps.
        for s in registry.spec_kg.specs:
            if 'Load' in s.name and 'Current' in s.name:
                return self._to_amps(s.min_val, s.unit)
        return self.max_load_default

    def analyze(self, views: List[RunView], registry,
                fsm_result=None) -> List[Finding]:
        findings: List[Finding] = []
        rail = pick_output_rail(views, registry)
        if rail is None:
            return findings
        vmin = self._vout_min(registry)
        max_spec = self._max_load_spec(registry)

        cap_obs = 0.0
        collapse_evidence = None
        for v in views:
            vv = v.voltages.get(rail.pin)
            cs = current_of(v, rail.pin)
            if vv is None or cs is None:
                continue
            i_out = np.abs(cs.filtered)
            in_reg = vv >= vmin
            if in_reg.any():
                cap_obs = max(cap_obs, float(i_out[in_reg].max()))
            # collapse regime: out of regulation while sourcing high current
            collapse = (~in_reg) & (i_out > self.k_floor * cs.noise_floor)
            if collapse.any() and collapse_evidence is None:
                k = int(np.argmax(collapse & (i_out == i_out[collapse].max())))
                collapse_evidence = {'run': v.run_id, 'vout': round(float(vv[k]), 4),
                                     'i_out_A': round(float(i_out[k]), 4)}

        if cap_obs <= 0:
            return findings

        # 3.7 shortfall
        if cap_obs < max_spec * 0.98:
            findings.append(Finding(
                analyzer=self.analyzer, category='capacity-shortfall',
                severity='high',
                summary=f'{rail.pin} sustains only {cap_obs*1e3:.3g} mA in reg '
                f'(spec {max_spec*1e3:.0f} mA)',
                evidence={'observed_capacity_A': round(cap_obs, 6),
                          'spec_max_load_A': max_spec, 'vout_min_V': vmin},
                affected_pins=[rail.pin],
                recommended_action='provide a load-sweep run to full spec '
                'current; if real, raise pass-device drive'))
        else:
            findings.append(Finding(
                analyzer=self.analyzer, category='capacity-ok',
                severity='info',
                summary=f'{rail.pin} sustains {cap_obs*1e3:.0f} mA in regulation',
                evidence={'observed_capacity_A': round(cap_obs, 4),
                          'spec_max_load_A': max_spec},
                affected_pins=[rail.pin]))

        # 3.3 fault propagation on collapse
        if collapse_evidence is not None:
            findings.append(Finding(
                analyzer=self.analyzer, category='drive-collapse',
                severity='high',
                summary=f'{rail.pin} collapses below reg when demand exceeds '
                f'capacity',
                evidence=collapse_evidence,
                affected_pins=[rail.pin],
                affected_states=[],
                recommended_action='downstream loads on this rail see the sag; '
                'confirm current-limit/foldback intent'))

        # feed capacity into template bounds (tightening recommendation only —
        # never silently overwrites the manifest)
        findings.append(Finding(
            analyzer=self.analyzer, category='param-bound',
            severity='info',
            summary=f'fitted capacity -> tighten I_lim upper bound to '
            f'{cap_obs:.3g} A',
            evidence={'param': 'I_lim', 'suggested_upper_bound_A':
                      round(cap_obs, 4), 'basis': 'observed sustained i_out'},
            affected_pins=[rail.pin],
            recommended_action='apply as a bound in the manifest, not an '
            'overwrite; refit within [lo, capacity]'))
        return findings
