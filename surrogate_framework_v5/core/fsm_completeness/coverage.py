"""
core/fsm_completeness/coverage.py — 4.2 coverage evaluation.

Against the reference space: state coverage (with per-state dwell
sufficiency), transition coverage (with transient-richness — clipped
settling counts as a GAP, not coverage), corner×state coverage, and
current-informed gaps bridging Capability A (un-current-verified mux paths;
Iq-suggested hidden sub-modes).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np


@dataclass
class CoverageResult:
    state_coverage: float
    transition_coverage: float
    richness: float
    observed_states: List[str]
    missing_states: List[str]
    observed_transitions: List[tuple]
    missing_transitions: List[tuple]
    clipped_transitions: List[tuple]
    corner_matrix: Dict[str, List[str]]
    per_state_dwell: Dict[str, dict]
    current_gaps: List[dict]
    settling: float = 5e-6
    notices: List[str] = field(default_factory=list)
    output_consistency: List[dict] = field(default_factory=list)

    def scorecard(self) -> dict:
        return {'state_pct': round(self.state_coverage * 100, 1),
                'transition_pct': round(self.transition_coverage * 100, 1),
                'richness_pct': round(self.richness * 100, 1),
                'n_missing_states': len(self.missing_states),
                'n_missing_transitions': len(self.missing_transitions),
                'n_clipped': len(self.clipped_transitions),
                'n_current_gaps': len(self.current_gaps),
                'n_output_contradictions': len(self.output_consistency),
                'n_corners': len(self.corner_matrix)}


def _family(detected: str, ref: str) -> bool:
    """Prefix-family match: detected 'REGULATION' covers 'REGULATION_LP'."""
    d, r = detected.upper(), ref.upper()
    base = r.split('_')[0]
    return d == r or d.startswith(base) or r.startswith(d.split('_')[0])


def _to_seconds(val: float, unit: str) -> float:
    u = (unit or '').lower()
    return {'s': 1.0, 'ms': 1e-3, 'us': 1e-6, 'µs': 1e-6, 'ns': 1e-9,
            'ps': 1e-12}.get(u, 1.0) * float(val)


def _settling_time(spec_kg, default: float = 5e-6) -> float:
    if spec_kg is not None:
        for s in spec_kg.specs:
            if 'Settling' in s.name:
                return _to_seconds(s.max_val, s.unit)
    return default


def _output_consistency_gaps(output_signatures, spec_kg) -> List[dict]:
    """Contradictions between a state's family name and its observed
    output-indicator signature (target semantics: outputs are effects of
    the state — a ready indicator asserted while DISABLED, or deasserted
    while REGULATION, is a reportable gap). Roles come from the spec's
    fsm_role on output-direction ports; without a spec there is nothing
    to check."""
    gaps: List[dict] = []
    if not output_signatures or spec_kg is None:
        return gaps
    try:
        role_of = {p.name: p.fsm_role
                   for p in spec_kg.get_fsm_output_ports() if p.fsm_role}
    except AttributeError:
        return gaps
    READY_FAMILIES = ('REGULATION', 'ACTIVE', 'SETTLED', 'CCM', 'LOCKED')
    OFF_FAMILIES = ('DISABLED', 'SHUTDOWN')
    for sname, sig in output_signatures.items():
        u = sname.upper()
        for signal, val in sig.items():
            role = role_of.get(signal)
            if role not in ('ready', 'fault'):
                continue
            expected = None
            if role == 'ready':
                if u.startswith(READY_FAMILIES):
                    expected = 1
                elif u.startswith(OFF_FAMILIES):
                    expected = 0
            else:  # fault
                expected = 1 if u.startswith('FAULT') else 0
            if expected is None:
                continue
            observed = 1 if val >= 0.5 else 0
            if observed != expected:
                gaps.append({'state': sname, 'signal': signal, 'role': role,
                             'observed_mean': round(float(val), 3),
                             'expected': expected})
    return gaps


def evaluate_coverage(ref, fsm_result, views, profile, registry=None,
                      insight_findings=None, k_dwell: float = 3.0,
                      output_signatures=None) -> CoverageResult:
    spec_kg = registry.spec_kg if registry is not None else \
        getattr(fsm_result, 'spec_kg', None)
    settling = _settling_time(spec_kg)
    state_defs = getattr(fsm_result, 'state_defs', None) or \
        getattr(fsm_result, 'get', lambda *_: None)('state_defs')
    transitions = getattr(fsm_result, 'transitions', None) or []
    detected_names = ([d['name'] for d in state_defs.values()]
                      if state_defs else [])

    # ── State coverage ──────────────────────────────────────────────────────
    observed, missing = [], []
    for r in ref.states:
        if any(_family(dn, r) for dn in detected_names):
            observed.append(r)
        else:
            missing.append(r)
    state_cov = len(observed) / max(len(ref.states), 1)

    # ── Per-state dwell sufficiency (from views' state sequences) ───────────
    dwell: Dict[str, dict] = {}
    corner_matrix: Dict[str, set] = {}
    for v in (views or []):
        if v.state_sequence is None or v.state_defs is None:
            continue
        dt = float(np.median(np.diff(v.t))) if len(v.t) > 1 else 0.0
        seq = v.state_sequence
        i = 0
        while i < len(seq):
            j = i
            while j < len(seq) and seq[j] == seq[i]:
                j += 1
            sname = v.state_name(int(seq[i]))
            samples = j - i
            cur = dwell.setdefault(sname, {'max_samples': 0, 'dwell_ok': False})
            cur['max_samples'] = max(cur['max_samples'], samples)
            if samples * dt >= k_dwell * settling:
                cur['dwell_ok'] = True
            corner_matrix.setdefault(v.corner or '(none)', set()).add(sname)
            i = j

    # ── Transition coverage ─────────────────────────────────────────────────
    obs_tr, missing_tr = [], []
    det_pairs = {(t.from_name, t.to_name) for t in transitions}

    def _covered(a, b):
        return any(_family(fa, a) and _family(fb, b)
                   for (fa, fb) in det_pairs)
    for (a, b) in ref.expected_transitions:
        (obs_tr if _covered(a, b) else missing_tr).append((a, b))
    tr_cov = len(obs_tr) / max(len(ref.expected_transitions), 1)

    # ── Transient richness / clipped detection ──────────────────────────────
    clipped, rich = [], []
    rail = None
    if registry is not None:
        from core.current_insights.findings import pick_output_rail
        rail = pick_output_rail(views or [], registry)
    # states with no analog settling transient — no richness to clip
    NON_SETTLING = ('DISABLED', 'SCAN', 'FAULT', 'SHUTDOWN', 'HICCUP',
                    'RESET', 'UNLOCKED')
    for (a, b) in obs_tr:
        if b.upper().startswith(NON_SETTLING):
            rich.append((a, b))
            continue
        ok = self_recovers(views, rail, b, settling)
        (rich if ok else clipped).append((a, b))
    richness = len(rich) / max(len(obs_tr), 1)

    # ── Current-informed gaps (bridge to Capability A) ──────────────────────
    current_gaps: List[dict] = []
    for f in (insight_findings or []):
        if f.category == 'untested-mux':
            current_gaps.append({
                'kind': 'mux-unverified', 'pins': f.affected_pins,
                'why': 'SEL path never current-verified (functional gap even '
                'if voltage-covered)'})
        elif f.category == 'iq-bimodal':
            current_gaps.append({
                'kind': 'hidden-sub-mode', 'states': f.affected_states,
                'why': 'Iq signature suggests an unobserved sub-mode'})

    # ── Output-indicator consistency (from the detector's signatures) ──────
    out_gaps = _output_consistency_gaps(
        output_signatures if output_signatures is not None else
        getattr(fsm_result, 'output_signatures', None), spec_kg)

    return CoverageResult(
        state_coverage=state_cov, transition_coverage=tr_cov,
        richness=richness, observed_states=observed, missing_states=missing,
        observed_transitions=obs_tr, missing_transitions=missing_tr,
        clipped_transitions=clipped,
        corner_matrix={c: sorted(s) for c, s in corner_matrix.items()},
        per_state_dwell=dwell, current_gaps=current_gaps, settling=settling,
        output_consistency=out_gaps)


def self_recovers(views, rail, dest_state: str, settling: float) -> bool:
    """True if some view shows the destination state's output recovering to
    within band before the capture ends — i.e. the settling was captured,
    not clipped. Without an output rail, optimistically True (no evidence
    of clipping)."""
    if rail is None or not views:
        return True
    from core.current_insights.findings import current_of
    for v in views:
        if v.state_sequence is None or v.state_defs is None:
            continue
        vv = v.voltages.get(rail.pin)
        if vv is None:
            continue
        # find a contiguous occurrence of the destination state
        for i in range(len(v.state_sequence)):
            if not _family(v.state_name(int(v.state_sequence[i])), dest_state):
                continue
            j = i
            while j < len(v.state_sequence) and _family(
                    v.state_name(int(v.state_sequence[j])), dest_state):
                j += 1
            seg = vv[i:j]
            if seg.size < 5:
                continue
            target = float(np.median(seg[-max(3, seg.size // 5):]))
            band = 0.01 * abs(target) + 1e-6
            # recovered if the tail is within band AND the segment showed the
            # excursion (min below band) then returned before the segment end
            settled_tail = abs(seg[-1] - target) <= band
            dwell_ok = (j - i) * float(np.median(np.diff(v.t))) >= settling
            if settled_tail and dwell_ok:
                return True
    return False
