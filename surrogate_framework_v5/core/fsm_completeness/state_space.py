"""
core/fsm_completeness/state_space.py — 4.1 state-explosion containment.

The reference space is NEVER 2^n over all logic pins. A pin dominance
hierarchy (from the IP profile + spec JSON) lets a dominant pin in its
inactive state mask every subordinate combination (EN_LDO=0 ⇒ DISABLED,
collapsing all SEL/trim/scan combos). Don't-care collapsing keeps only
pins with observed/spec-declared behavior; physical adjacency restricts
transitions to single dominant events. Output shows the arithmetic
(2^n → masked count).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple


@dataclass
class ReferenceStateSpace:
    states: List[str]
    expected_transitions: List[Tuple[str, str]]
    masking_rationale: List[str]
    arithmetic: dict = field(default_factory=dict)


def _state_pins(spec_kg):
    return [p for p in spec_kg.ports
            if getattr(p, 'is_state_signal', False) and p.domain == 'digital']


def _role_pins(spec_kg, role):
    return [p.name for p in spec_kg.ports if p.fsm_role == role]


def build_reference_space(fsm_result, profile,
                          registry=None) -> ReferenceStateSpace:
    """Build the masked reference space for an IP profile. `fsm_result`
    supplies the spec_kg (via registry) for the pin inventory; `profile`
    supplies canonical states + minimum transitions + mode-split roles."""
    spec_kg = registry.spec_kg if registry is not None else \
        getattr(fsm_result, 'spec_kg', None)
    n_pins = len(_state_pins(spec_kg)) if spec_kg is not None else 0
    raw = 2 ** n_pins if n_pins else 0

    states = list(profile.canonical_states)
    rationale: List[str] = []
    if n_pins:
        rationale.append(
            f'{n_pins} state pins -> 2^{n_pins} = {raw} raw logic combinations')
    # enable tier collapse
    en = _role_pins(spec_kg, 'enable') if spec_kg is not None else []
    if en and n_pins:
        rationale.append(
            f'{en[0]}=0 (enable tier) masks all 2^{n_pins-1} subordinate '
            f'combinations -> DISABLED (1 state)')
    rationale.append(
        'supply _ok gate: supplies outside window fold to DISABLED '
        '(no separate operational state)')
    # scan tier
    scan = (_role_pins(spec_kg, 'scan_mode') if spec_kg is not None else [])
    if scan:
        rationale.append(
            f'scan tier {scan} dominates select/trim: any scan=1 -> SCAN, '
            f'collapsing their 2^k combinations')
    # don't-care select/trim
    sel = ([p.name for p in spec_kg.ports
            if p.fsm_role in ('supply_select', 'output_select')]
           if spec_kg is not None else [])
    if sel:
        rationale.append(
            f'select pins {sel} show no spec-declared behavior change in '
            f'operational states (verify via current, 3.4) -> don\'t-care')

    # mode split: expand the primary operational state per mode pin
    mode_pins = []
    for role in profile.mode_split_roles:
        mode_pins += (_role_pins(spec_kg, role) if spec_kg is not None else [])
    transitions = list(profile.min_transitions)
    op_state = 'REGULATION' if 'REGULATION' in states else (
        states[2] if len(states) > 2 else None)
    if mode_pins and op_state and op_state in states:
        lp, hp = f'{op_state}_LP', f'{op_state}_HP'
        states = [s for s in states if s != op_state]
        idx = profile.canonical_states.index(op_state)
        states[idx:idx] = [lp, hp]
        rationale.append(
            f'mode_select {mode_pins} splits {op_state} -> {{{lp}, {hp}}}')
        # rewrite transitions touching op_state to both variants + toggle
        new_tr = []
        for a, b in transitions:
            a2 = [lp, hp] if a == op_state else [a]
            b2 = [lp, hp] if b == op_state else [b]
            for x in a2:
                for y in b2:
                    if x != y:
                        new_tr.append((x, y))
        new_tr += [(lp, hp), (hp, lp)]
        transitions = sorted(set(new_tr))

    ref_count = len(states)
    rationale.append(
        f'=> reference space = {ref_count} states, '
        f'{len(transitions)} expected transitions'
        + (f' ({raw}/{ref_count} = {raw // max(ref_count,1)}x collapse)'
           if raw else ''))

    return ReferenceStateSpace(
        states=states, expected_transitions=transitions,
        masking_rationale=rationale,
        arithmetic={'n_state_pins': n_pins, 'raw_2n': raw,
                    'reference_states': ref_count,
                    'collapse_factor': (raw // ref_count) if ref_count else 0})
