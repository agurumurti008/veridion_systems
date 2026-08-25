"""
core/current_insights/findings.py — Finding dataclass, RunView packaging,
report assembly, and 3.12 (efficiency + power-domain sequencing).

Every analyzer returns list[Finding]; each Finding is machine-readable
enough for a verification lead to file as a bug or a stimulus request.
RunView is the per-run bundle analyzers consume: filtered currents +
raw voltages + (voltage-derived) FSM labels — currents are never in the
FSM side, preserving the evidence-not-state boundary.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional

import numpy as np

from .filtering import FilteredSignal, filter_current

SEVERITY_ORDER = {'info': 0, 'low': 1, 'medium': 2, 'high': 3, 'critical': 4}


@dataclass
class Finding:
    analyzer: str                # e.g. "3.4 mux-verification"
    category: str                # kebab slug, e.g. "untested-mux"
    severity: str                # info|low|medium|high|critical
    summary: str
    evidence: dict = field(default_factory=dict)
    affected_pins: List[str] = field(default_factory=list)
    affected_states: List[str] = field(default_factory=list)
    recommended_action: str = ''

    def as_row(self) -> dict:
        return asdict(self)


@dataclass
class RunView:
    run_id: str
    corner: str
    t: np.ndarray
    voltages: Dict[str, np.ndarray]         # speckg voltage name -> trace
    currents: Dict[str, FilteredSignal]     # current name -> FILTERED signal
    state_sequence: Optional[np.ndarray] = None
    state_defs: Optional[dict] = None

    def state_name(self, sid: int) -> str:
        if self.state_defs and sid in self.state_defs:
            return self.state_defs[sid]['name']
        return f'STATE_{sid}'


def build_run_views(runs: List[dict], registry,
                    state_sequences: Optional[Dict[str, np.ndarray]] = None,
                    state_defs: Optional[dict] = None,
                    **filter_kw) -> List[RunView]:
    """Package load_all_runs run dicts into RunViews: filter every current
    column (3.6), keep voltages raw, attach caller-provided per-run state
    sequences (keyed by run_id, or run_id@corner). Currents are filtered
    here and never handed to the FSM detector."""
    views = []
    for run in runs:
        t = np.asarray(run['time'], dtype=float)
        volts = {n: run['voltage_matrix'][:, i]
                 for i, n in enumerate(run['voltage_names'])}
        cur_raw = {n: run['current_matrix'][:, i]
                   for i, n in enumerate(run['current_names'])}
        currents = {n: filter_current(n, t, x, **filter_kw)
                    for n, x in cur_raw.items()}
        rid = run['run_id']
        corner = run.get('corner_id', '')
        seq = None
        if state_sequences is not None:
            seq = state_sequences.get(f'{rid}@{corner}')
            if seq is None:
                seq = state_sequences.get(rid)
        views.append(RunView(run_id=rid, corner=corner, t=t, voltages=volts,
                             currents=currents, state_sequence=seq,
                             state_defs=state_defs))
    return views


# ─── Report assembly ─────────────────────────────────────────────────────────

class InsightReport:
    """Findings + filter logs + registry coverage -> md/json twin. Token-
    efficient: one summary table + per-finding rows, no narrative."""

    def __init__(self, findings: List[Finding], registry=None,
                 filter_logs: Optional[List[dict]] = None):
        self.findings = sorted(
            findings, key=lambda f: -SEVERITY_ORDER.get(f.severity, 0))
        self.registry = registry
        self.filter_logs = filter_logs or []

    def counts(self) -> Dict[str, int]:
        c: Dict[str, int] = {}
        for f in self.findings:
            c[f.severity] = c.get(f.severity, 0) + 1
        return c

    def to_dict(self) -> dict:
        return {
            'summary': {'n_findings': len(self.findings),
                        'by_severity': self.counts()},
            'findings': [f.as_row() for f in self.findings],
            'current_coverage': (self.registry.coverage_summary()
                                 if self.registry else {}),
            'filter_logs': self.filter_logs,
        }

    def to_json(self, path: Optional[str] = None) -> str:
        s = json.dumps(self.to_dict(), indent=2, default=_json_default)
        if path:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(s)
        return s

    def to_markdown(self, path: Optional[str] = None) -> str:
        L = ['# Current-Insight Findings', '']
        c = self.counts()
        L.append('| severity | count |')
        L.append('|---|---|')
        for sev in ('critical', 'high', 'medium', 'low', 'info'):
            if c.get(sev):
                L.append(f'| {sev} | {c[sev]} |')
        L.append('')
        L.append('| # | analyzer | severity | summary | pins | states | action |')
        L.append('|---|---|---|---|---|---|---|')
        for i, f in enumerate(self.findings, 1):
            L.append(f"| {i} | {f.analyzer} | {f.severity} | {f.summary} | "
                     f"{','.join(f.affected_pins) or '-'} | "
                     f"{','.join(f.affected_states) or '-'} | "
                     f"{f.recommended_action} |")
        if self.registry:
            L += ['', '## Current-probe coverage by role', '',
                  '| role | with_current / total |', '|---|---|']
            for role, s in sorted(self.registry.coverage_summary().items()):
                L.append(f"| {role} | {s['with_current']}/{s['total']} |")
        text = '\n'.join(L) + '\n'
        if path:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(text)
        return text


def current_of(view: RunView, pin: str) -> Optional[FilteredSignal]:
    """A pin's filtered current channel from a RunView (<pin>_I convention
    or a direct name), or None if that pin has no probe in this run."""
    return view.currents.get(f'{pin}_I') or view.currents.get(pin)


def pick_output_rail(views: List[RunView], registry):
    """The regulated output among candidate rails: the one carrying the most
    current in the data (VDD_1V2, not the tiny STB floop_out probe). Falls
    back to the first current-probed rail, or None."""
    rails = [c for c in registry.output_rails() if c.has_current]
    best, best_act = None, -1.0
    for c in rails:
        act = 0.0
        for v in views:
            cs = current_of(v, c.pin)
            if cs is not None:
                act = max(act, float(np.max(np.abs(cs.filtered))))
        if act > best_act:
            best_act, best = act, c
    if best is not None and best_act > 0:
        return best
    return rails[0] if rails else None


def _json_default(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    return str(o)


# ─── 3.12 Efficiency & power-domain sequencing ───────────────────────────────

class EfficiencySequencing:
    """Per-state P_out/P_in efficiency table + supply-before-dependent
    sequencing check. Sequencing violations (a dependent domain draws
    current before its supply is inside its _ok window) are top severity."""

    analyzer = '3.12 efficiency+sequencing'

    def __init__(self, k_floor: float = 3.0):
        self.k_floor = k_floor

    def _window(self, port) -> tuple:
        lo, hi = float(port.voltage_range[0]), float(port.voltage_range[1])
        if hi <= lo:
            lo, hi = lo - 0.1, hi + 0.1
        return lo, hi

    def analyze(self, views: List[RunView], registry,
                fsm_result=None) -> List[Finding]:
        findings: List[Finding] = []
        supplies = registry.input_supplies()
        outs = registry.output_rails()
        port_by = {p.name: p for p in registry.spec_kg.ports}

        for v in views:
            # Efficiency per state: P_out = sum(V_out*I_out), P_in = sum over
            # input supplies. Only computed where both currents are present.
            if v.state_sequence is not None and v.state_defs:
                eff_rows = self._efficiency(v, supplies, outs)
                for sname, eff in eff_rows.items():
                    if eff is not None and (eff < 0 or eff > 1.05):
                        findings.append(Finding(
                            analyzer=self.analyzer, category='efficiency-anomaly',
                            severity='medium',
                            summary=f'Non-physical efficiency {eff:.2f} in {sname}',
                            evidence={'state': sname, 'efficiency': round(eff, 3)},
                            affected_states=[sname],
                            recommended_action='check supply/output current '
                            'sign convention or missing supply probe'))

            # Sequencing: a dependent (output-rail) current above floor while
            # its input supply is outside the _ok window.
            for out in outs:
                i_out = self._cur(v, out.pin)
                if i_out is None:
                    continue
                active = i_out.above_floor(self.k_floor)
                for sup in supplies:
                    vv = v.voltages.get(sup.pin)
                    if vv is None:
                        continue
                    lo, hi = self._window(port_by[sup.pin])
                    invalid = (vv < lo) | (vv > hi)
                    bad = active & invalid
                    if bad.mean() > 0.02:
                        findings.append(Finding(
                            analyzer=self.analyzer, category='sequencing-violation',
                            severity='critical',
                            summary=f'{out.pin} draws current while {sup.pin} '
                            f'outside [{lo:g},{hi:g}] V',
                            evidence={'run': v.run_id, 'corner': v.corner,
                                      'frac_samples': round(float(bad.mean()), 3),
                                      'dependent': out.pin, 'supply': sup.pin},
                            affected_pins=[out.pin, sup.pin],
                            recommended_action='enforce supply-valid-before-'
                            'activity sequencing; add power-up ramp run'))
        return findings

    def _cur(self, v: RunView, pin: str) -> Optional[FilteredSignal]:
        return current_of(v, pin)

    def _efficiency(self, v: RunView, supplies, outs) -> Dict[str, Optional[float]]:
        out = {}
        seq = v.state_sequence
        for sid in np.unique(seq):
            mask = seq == sid
            if mask.sum() < 3:
                continue
            p_out = 0.0
            for o in outs:
                io = self._cur(v, o.pin)
                vv = v.voltages.get(o.pin)
                if io is None or vv is None:
                    continue
                p_out += float(np.mean(np.abs(io.filtered[mask]) * vv[mask]))
            p_in = 0.0
            for s in supplies:
                ii = self._cur(v, s.pin)
                vv = v.voltages.get(s.pin)
                if ii is None or vv is None:
                    continue
                p_in += float(np.mean(np.abs(ii.filtered[mask]) * vv[mask]))
            out[v.state_name(int(sid))] = (p_out / p_in
                                           if p_in > 1e-18 else None)
        return out
