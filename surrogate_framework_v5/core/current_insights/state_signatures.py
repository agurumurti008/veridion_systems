"""
core/current_insights/state_signatures.py — 3.10 Iq state signatures
(expert addition). Per-state quiescent-current fingerprints as an AUXILIARY
disambiguation channel: a state whose Iq is bimodal hides an unobserved
sub-mode (e.g. HP vs LP). Strictly advisory — returns relabel/split
PROPOSALS applied post-detection; never feeds the FSM detector (contract).
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import numpy as np

from .findings import Finding, RunView, current_of


class StateSignatures:
    analyzer = '3.10 iq-signature'

    def __init__(self, bimodal_sep: float = 3.0, k_floor: float = 3.0):
        self.bimodal_sep = bimodal_sep     # min gap/σ to call bimodal
        self.k_floor = k_floor
        self.relabel_proposals: List[dict] = []

    def _primary(self, registry):
        # role/taxonomy-driven (no pin-name literals): see
        # CurrentRegistry.primary_input_supply
        return registry.primary_input_supply()

    def signatures(self, views: List[RunView], registry
                   ) -> Dict[str, Tuple[float, float]]:
        """{state_name: (Iq_mean_A, Iq_std_A)} from the primary supply,
        pooled across runs. Used by codegen for per-state I(vin) currents."""
        sup = self._primary(registry)
        if sup is None:
            return {}
        pooled: Dict[str, list] = {}
        for v in views:
            if v.state_sequence is None or v.state_defs is None:
                continue
            cs = current_of(v, sup.pin)
            if cs is None:
                continue
            for sid in np.unique(v.state_sequence):
                mask = v.state_sequence == sid
                if mask.sum() < 3:
                    continue
                pooled.setdefault(v.state_name(int(sid)), []).extend(
                    cs.filtered[mask].tolist())
        return {s: (float(np.mean(xs)), float(np.std(xs)))
                for s, xs in pooled.items() if xs}

    def analyze(self, views: List[RunView], registry,
                fsm_result=None) -> List[Finding]:
        findings: List[Finding] = []
        self.relabel_proposals = []
        sup = self._primary(registry)
        if sup is None:
            return findings
        # per state, per run occurrence: mean Iq -> detect a bimodal split
        occ: Dict[str, list] = {}
        for v in views:
            if v.state_sequence is None or v.state_defs is None:
                continue
            cs = current_of(v, sup.pin)
            if cs is None:
                continue
            seq = v.state_sequence
            i = 0
            while i < len(seq):
                j = i
                while j < len(seq) and seq[j] == seq[i]:
                    j += 1
                if j - i >= 5:
                    occ.setdefault(v.state_name(int(seq[i])), []).append(
                        float(np.mean(cs.filtered[i:j])))
                i = j
        for sname, means in occ.items():
            if len(means) < 4:
                continue
            m = np.sort(np.array(means))
            gap = np.diff(m)
            k = int(np.argmax(gap))
            lo, hi = m[:k + 1], m[k + 1:]
            if lo.size and hi.size:
                sep = (hi.mean() - lo.mean())
                spread = (np.std(lo) + np.std(hi)) / 2 + 1e-15
                if sep / spread > self.bimodal_sep and sep > self.k_floor * \
                        current_of(views[0], sup.pin).noise_floor:
                    prop = {'state': sname, 'proposal': 'split',
                            'sub_modes': [{'label': f'{sname}_LOWIQ',
                                           'Iq_uA': round(lo.mean() * 1e6, 2)},
                                          {'label': f'{sname}_HIGHIQ',
                                           'Iq_uA': round(hi.mean() * 1e6, 2)}]}
                    self.relabel_proposals.append(prop)
                    findings.append(Finding(
                        analyzer=self.analyzer, category='iq-bimodal',
                        severity='low',
                        summary=f'{sname} Iq bimodal ({lo.mean()*1e6:.1f}/'
                        f'{hi.mean()*1e6:.1f} uA) — hidden sub-mode',
                        evidence=prop, affected_states=[sname],
                        recommended_action='ADVISORY: post-detection relabel '
                        'into HP/LP sub-modes; add a mode-pin-tagged run to '
                        'confirm (does not change FSM detection)'))
        return findings
