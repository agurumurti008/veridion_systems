"""
core/fsm_completeness/gap_report.py — 4.3 customer-facing gap report.

One artifact (.md + .json twin): summary scorecard, per-gap rows
(gap | why it matters | recommended run | model impact if left open),
and the binary decision block — Option 1 provide the listed runs (each
spec'd concretely) OR Option 2 proceed now with the limitations stamped
into the emitted Verilog-A header. No third, vague option.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional


@dataclass
class GapRow:
    gap: str
    why: str
    recommended_run: dict          # {stimulus, pins, corner, min_duration_s}
    model_impact: str

    def as_row(self) -> dict:
        return asdict(self)


@dataclass
class GapReport:
    scorecard: dict
    gaps: List[GapRow]
    option1_runs: List[dict]
    option2_limitations: List[str]
    notices: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {'scorecard': self.scorecard,
                'gaps': [g.as_row() for g in self.gaps],
                'decision': {
                    'option_1_provide_runs': self.option1_runs,
                    'option_2_proceed_limitations': self.option2_limitations},
                'notices': self.notices}

    def to_json(self, path: Optional[str] = None) -> str:
        s = json.dumps(self.to_dict(), indent=2)
        if path:
            open(path, 'w', encoding='utf-8').write(s)
        return s

    def to_markdown(self, path: Optional[str] = None) -> str:
        sc = self.scorecard
        L = ['# FSM Completeness — Gap Report', '',
             '## Scorecard', '',
             '| metric | value |', '|---|---|',
             f"| state coverage | {sc.get('state_pct')}% |",
             f"| transition coverage | {sc.get('transition_pct')}% |",
             f"| transient richness | {sc.get('richness_pct')}% |",
             f"| missing states | {sc.get('n_missing_states')} |",
             f"| missing transitions | {sc.get('n_missing_transitions')} |",
             f"| clipped (counted as gaps) | {sc.get('n_clipped')} |",
             f"| current-informed gaps | {sc.get('n_current_gaps')} |",
             f"| output contradictions | {sc.get('n_output_contradictions', 0)} |",
             f"| corners exercised | {sc.get('n_corners')} |", '']
        if self.notices:
            L += ['> ' + '; '.join(self.notices), '']
        L += ['## Gaps', '',
              '| # | gap | why it matters | recommended run | impact if left open |',
              '|---|---|---|---|---|']
        for i, g in enumerate(self.gaps, 1):
            rr = g.recommended_run
            run = (f"{rr.get('stimulus','')} @ {rr.get('corner','any')}, "
                   f">={rr.get('min_duration_s','?')}s")
            L.append(f"| {i} | {g.gap} | {g.why} | {run} | {g.model_impact} |")
        L += ['', '## Decision (choose one)', '',
              '**Option 1 — provide these runs** (model improves proactively):']
        if self.option1_runs:
            L += ['', '| run | stimulus | pins | corner | min duration |',
                  '|---|---|---|---|---|']
            for r in self.option1_runs:
                L.append(f"| {r['id']} | {r['stimulus']} | "
                         f"{','.join(r.get('pins', []))} | {r.get('corner','any')} "
                         f"| {r.get('min_duration_s','?')}s |")
        else:
            L.append('\n_(none — coverage complete)_')
        L += ['', '**Option 2 — proceed now** (these limitations are stamped '
              'into the emitted Verilog-A `LIMITATIONS:` header):', '']
        if self.option2_limitations:
            L += [f'- `LIMITATIONS: {lim}`' for lim in self.option2_limitations]
        else:
            L.append('_(none — model is complete for the declared profile)_')
        text = '\n'.join(L) + '\n'
        if path:
            open(path, 'w', encoding='utf-8').write(text)
        return text


def _stimulus_roles(registry) -> Dict[str, str]:
    """Map fsm_role -> pin name from the spec (via the registry), plus the
    primary input supply under '_supply'. The recommended-run pin lists are
    derived from these roles — no hardcoded pin names; a spec that lacks a
    role yields an explicit '<role>' placeholder instead of a guess."""
    roles: Dict[str, str] = {}
    if registry is None:
        return roles
    kg = getattr(registry, 'spec_kg', None)
    for p in getattr(kg, 'ports', []) if kg is not None else []:
        if getattr(p, 'fsm_role', None) and p.fsm_role not in roles:
            roles[p.fsm_role] = p.name
    if hasattr(registry, 'primary_input_supply'):
        sup = registry.primary_input_supply()
        if sup is not None:
            roles['_supply'] = sup.pin
    return roles


def _run_for_state(state: str, profile, settling: float,
                   roles: Optional[Dict[str, str]] = None) -> dict:
    return {'stimulus': f'exercise entry into {state}',
            'pins': _pins_for_state(state, roles), 'corner': 'any',
            'min_duration_s': round(5 * settling, 9)}


def _pins_for_state(state: str,
                    roles: Optional[Dict[str, str]] = None) -> List[str]:
    r = roles or {}
    en = r.get('enable', '<enable>')
    scan = r.get('scan_mode', '<scan_mode>')
    mode = r.get('mode_select', '<mode_select>')
    sup = r.get('_supply', '<supply>')
    u = state.upper()
    if u.startswith('DISABLED'):
        return [f'{en}=0']
    if u.startswith('SCAN'):
        return [f'{scan}=1']
    if 'HP' in u:
        return [f'{en}=1', f'{mode}=1']
    if 'LP' in u:
        return [f'{en}=1', f'{mode}=0']
    if u.startswith('DROPOUT'):
        return [f'{en}=1', f'{sup}->dropout']
    if u.startswith('FAULT'):
        return ['fault-inject']
    return [f'{en}=1']


def build_gap_report(coverage_result, ref, profile, settling: Optional[float] = None,
                     corners_expected: int = 3, registry=None) -> GapReport:
    cr = coverage_result
    if settling is None:
        settling = getattr(cr, 'settling', 5e-6)
    roles = _stimulus_roles(registry)
    gaps: List[GapRow] = []
    runs: List[dict] = []
    limits: List[str] = []
    rid = 0

    def add_run(spec):
        nonlocal rid
        rid += 1
        runs.append({'id': f'R{rid}', **spec})

    for s in cr.missing_states:
        gaps.append(GapRow(
            gap=f'state {s} never observed',
            why='reference state absent from all runs',
            recommended_run=_run_for_state(s, profile, settling, roles),
            model_impact=f'{s} behavior defaults to nearest state; unmodeled'))
        add_run({'stimulus': f'enter {s}', 'pins': _pins_for_state(s, roles),
                 'corner': 'any', 'min_duration_s': round(5 * settling, 9)})
        limits.append(f'state {s} not characterized (no run enters it)')

    for (a, b) in cr.missing_transitions:
        gaps.append(GapRow(
            gap=f'transition {a}->{b} never observed',
            why='expected edge missing; guard unverified',
            recommended_run={'stimulus': f'drive {a}->{b} event',
                             'pins': _pins_for_state(b, roles), 'corner': 'any',
                             'min_duration_s': round(5 * settling, 9)},
            model_impact='transition guard unvalidated by data'))
        add_run({'stimulus': f'{a}->{b} event', 'pins': _pins_for_state(b, roles),
                 'corner': 'any', 'min_duration_s': round(5 * settling, 9)})
        limits.append(f'transition {a}->{b} unverified')

    for (a, b) in cr.clipped_transitions:
        gaps.append(GapRow(
            gap=f'transition {a}->{b} capture clipped',
            why='settling not fully captured (no recovery-to-band in window)',
            recommended_run={'stimulus': f'{a}->{b} with long capture',
                             'pins': _pins_for_state(b, roles), 'corner': 'any',
                             'min_duration_s': round(10 * settling, 9)},
            model_impact='undershoot/settling of this transition unmodeled'))
        add_run({'stimulus': f'{a}->{b} long capture',
                 'pins': _pins_for_state(b, roles),
                 'corner': 'any', 'min_duration_s': round(10 * settling, 9)})
        limits.append(f'{a}->{b} settling clipped; transient not characterized')

    for st, d in cr.per_state_dwell.items():
        if not d.get('dwell_ok', True):
            gaps.append(GapRow(
                gap=f'state {st} dwell insufficient',
                why=f'dwell < {int(3)}x settling; analog response not captured',
                recommended_run={'stimulus': f'hold {st} longer',
                                 'pins': _pins_for_state(st, roles),
                                 'corner': 'any',
                                 'min_duration_s': round(5 * settling, 9)},
                model_impact=f'{st} steady-state params under-constrained'))
            limits.append(f'{st} dwell too short for steady-state fit')

    # output-indicator consistency (target semantics: outputs are effects
    # of the state — a contradiction means the runs, the role declaration,
    # or the device disagree, and the emitted indicator drive is suspect)
    for oc in getattr(cr, 'output_consistency', []) or []:
        gaps.append(GapRow(
            gap=f"output-consistency: {oc['signal']} in {oc['state']}",
            why=(f"{oc['role']}-role indicator observed at mean "
                 f"{oc['observed_mean']} but the {oc['state']} family "
                 f"expects {oc['expected']}"),
            recommended_run={'stimulus': f"re-exercise {oc['state']} and "
                             f"capture {oc['signal']}; confirm the "
                             f"{oc['role']} role assignment",
                             'pins': _pins_for_state(oc['state'], roles),
                             'corner': 'any',
                             'min_duration_s': round(5 * settling, 9)},
            model_impact='emitted status-indicator drive may misrepresent '
            'this state'))
        limits.append(f"output-consistency: {oc['signal']} contradicts "
                      f"{oc['state']} ({oc['role']} role)")

    for cg in cr.current_gaps:
        if cg['kind'] == 'mux-unverified':
            pins = cg.get('pins', [])
            gaps.append(GapRow(
                gap=f'mux path {",".join(pins)} not current-verified',
                why=cg['why'],
                recommended_run={'stimulus': 'SEL toggle, all candidate '
                                 'supplies live', 'pins': pins, 'corner': 'any',
                                 'min_duration_s': round(5 * settling, 9)},
                model_impact='selected supply path unproven; possible '
                'untested-mux bug'))
            add_run({'stimulus': 'SEL toggle w/ candidates live', 'pins': pins,
                     'corner': 'any', 'min_duration_s': round(5 * settling, 9)})
            limits.append(f'mux {",".join(pins)} path not current-verified')
        elif cg['kind'] == 'hidden-sub-mode':
            sts = cg.get('states', [])
            gaps.append(GapRow(
                gap=f'hidden sub-mode in {",".join(sts)}',
                why=cg['why'],
                recommended_run={'stimulus': 'mode-pin-tagged run',
                                 'pins': [roles.get('mode_select',
                                                    '<mode_select>')],
                                 'corner': 'any',
                                 'min_duration_s': round(5 * settling, 9)},
                model_impact='sub-mode Iq/params merged into parent state'))
            limits.append(f'hidden sub-mode in {",".join(sts)} not split')

    # corner coverage gap
    if cr.corner_matrix and len(cr.corner_matrix) < corners_expected:
        gaps.append(GapRow(
            gap=f'only {len(cr.corner_matrix)}/{corners_expected} corners',
            why='states/transitions not exercised across PVT',
            recommended_run={'stimulus': 'repeat key runs at missing corners',
                             'pins': [], 'corner': 'SS/FF',
                             'min_duration_s': round(5 * settling, 9)},
            model_impact='PVT parameter grid sparse'))
        limits.append(f'corner coverage {len(cr.corner_matrix)}/'
                      f'{corners_expected}')

    return GapReport(scorecard=cr.scorecard(), gaps=gaps, option1_runs=runs,
                     option2_limitations=limits, notices=list(cr.notices))
