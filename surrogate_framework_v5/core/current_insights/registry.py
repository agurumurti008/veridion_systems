"""
core/current_insights/registry.py — pin ↔ current-path ↔ domain resolution.

Bridges spec-JSON ports (name/port_type/domain/current_range/fsm_role) to
the SignalMap current entries (convention: voltage `<PIN>`, current
`<PIN>_I` at `X_DUT.<PIN>_$flow`; bias pins mapped directly). Every
analyzer resolves a pin's current channel through this registry rather than
guessing BLUT paths. Currents are evidence only — the registry never
touches the FSM logic matrix.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

import numpy as np

from core.templates.pin_taxonomy import categorize_pin, hook_for_pin


@dataclass
class PinChannel:
    pin: str                    # spec voltage-side port name
    port_type: str
    domain: str                 # digital | analog | power
    role: str                   # input_supply|output_rail|ground|bias|select|
                                #   load_control|enable|control|sense|analog_io
    v_name: Optional[str]       # speckg voltage signal name (usually == pin)
    i_name: Optional[str]       # speckg current signal name (<pin>_I or direct)
    v_range: tuple
    i_range: tuple

    @property
    def has_current(self) -> bool:
        return self.i_name is not None


def _role(port, cat: str) -> str:
    pt = port.port_type
    hi = float(port.voltage_range[1])
    if pt == 'supply':
        return 'input_supply' if hi >= 3.0 else 'output_rail'
    if pt == 'output':
        return 'output_rail'
    if pt in ('ground', 'bulk'):
        return 'ground'
    if pt.startswith('bias_current'):
        return 'bias'
    if pt == 'select' or port.fsm_role in ('supply_select', 'output_select'):
        return 'select'
    if port.fsm_role == 'load_control':
        return 'load_control'
    if pt == 'enable' or port.fsm_role == 'enable':
        return 'enable'
    if cat == 'sense' or pt in ('feedback', 'feedback_input', 'reference',
                                'reference_input'):
        return 'sense'
    if port.domain == 'digital':
        return 'control'
    return 'analog_io'


class CurrentRegistry:
    """Resolved pin channels + role queries for the current analyzers."""

    def __init__(self, spec_kg, signal_map=None):
        self.spec_kg = spec_kg
        self.signal_map = signal_map
        self.channels: Dict[str, PinChannel] = {}

        # Current speckg names available from the map, indexed by the pin
        # they belong to: '<pin>_I' -> pin, plus direct bias entries.
        cur_by_pin: Dict[str, str] = {}
        direct_currents: set = set()
        if signal_map is not None:
            for e in signal_map.entries:
                if e.kind != 'current':
                    continue
                if e.speckg_name.endswith('_I'):
                    cur_by_pin[e.speckg_name[:-2]] = e.speckg_name
                else:
                    direct_currents.add(e.speckg_name)

        for p in spec_kg.ports:
            cat = categorize_pin(p.name)
            i_name = cur_by_pin.get(p.name)
            if i_name is None and p.name in direct_currents:
                i_name = p.name              # bias pin mapped directly
            self.channels[p.name] = PinChannel(
                pin=p.name, port_type=p.port_type, domain=p.domain,
                role=_role(p, cat), v_name=p.name, i_name=i_name,
                v_range=tuple(p.voltage_range),
                i_range=tuple(p.current_range))

    # ─── Role queries ───────────────────────────────────────────────────────

    def _by_role(self, *roles) -> List[PinChannel]:
        return [c for c in self.channels.values() if c.role in roles]

    def input_supplies(self) -> List[PinChannel]:
        return self._by_role('input_supply')

    def primary_input_supply(self) -> Optional[PinChannel]:
        """The main input supply, resolved without pin-name literals:
        1) the input supply whose taxonomy hook is 'vin' (the template's
           declared primary), preferring one with a current probe;
        2) otherwise the input supply with the largest declared current
           capability (|current_range|), again preferring probed channels.
        Ties break on spec declaration order (deterministic)."""
        sup = self.input_supplies()
        if not sup:
            return None
        hooked = [c for c in sup if hook_for_pin(c.pin) == 'vin']
        pool = hooked or sup
        return max(pool, key=lambda c: (int(c.has_current),
                                        max(abs(c.i_range[0]),
                                            abs(c.i_range[1]))))

    def output_rails(self) -> List[PinChannel]:
        return self._by_role('output_rail')

    def grounds(self) -> List[PinChannel]:
        return self._by_role('ground')

    def bias(self) -> List[PinChannel]:
        return self._by_role('bias')

    def selects(self) -> List[PinChannel]:
        return self._by_role('select')

    def load_controls(self) -> List[PinChannel]:
        return self._by_role('load_control')

    def channel(self, pin: str) -> Optional[PinChannel]:
        return self.channels.get(pin)

    def with_current(self) -> List[PinChannel]:
        return [c for c in self.channels.values() if c.has_current]

    # ─── SEL-class mux candidates (3.4) ─────────────────────────────────────

    def mux_candidates(self, sel_pin: str) -> List[PinChannel]:
        """Candidate supplies a SEL pin chooses between. Heuristic (honest,
        general; exact mapping is a questionnaire item): supply-selects pick
        among input supplies, output-selects among output rails. The SEL
        pin's own current channel is excluded."""
        ch = self.channels.get(sel_pin)
        if ch is None:
            return []
        role = self.spec_kg_fsm_role(sel_pin)
        if role == 'output_select':
            cands = self.output_rails()
        else:
            cands = self.input_supplies()
        return [c for c in cands if c.pin != sel_pin and c.has_current]

    def spec_kg_fsm_role(self, pin: str) -> Optional[str]:
        for p in self.spec_kg.ports:
            if p.name == pin:
                return p.fsm_role
        return None

    # ─── Signal resolution ──────────────────────────────────────────────────

    def resolve_current(self, pin: str,
                        current_signals: Dict[str, np.ndarray]
                        ) -> Optional[np.ndarray]:
        """Return the (speckg-renamed) current trace for a pin from a
        SignalCapture.current_signals dict, or None if unmapped/absent."""
        ch = self.channels.get(pin)
        if ch is None or ch.i_name is None:
            return None
        return current_signals.get(ch.i_name)

    def resolve_from_run(self, pin: str, run: dict) -> Optional[np.ndarray]:
        """Resolve a pin current from a load_all_runs run dict (current_names
        / current_matrix, already speckg-renamed by the reader)."""
        ch = self.channels.get(pin)
        if ch is None or ch.i_name is None:
            return None
        names = run.get('current_names', [])
        if ch.i_name in names:
            return run['current_matrix'][:, names.index(ch.i_name)]
        return None

    def voltage_from_run(self, pin: str, run: dict) -> Optional[np.ndarray]:
        names = run.get('voltage_names', [])
        if pin in names:
            return run['voltage_matrix'][:, names.index(pin)]
        return None

    def coverage_summary(self) -> dict:
        """Which roles have current probes — drives the recon-style
        'evaluable vs missing' note in the insight report."""
        out: Dict[str, dict] = {}
        for c in self.channels.values():
            slot = out.setdefault(c.role, {'total': 0, 'with_current': 0})
            slot['total'] += 1
            slot['with_current'] += int(c.has_current)
        return out
