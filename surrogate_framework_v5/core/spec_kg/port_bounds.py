"""
core/spec_kg/port_bounds.py
Shared Port-range-derived helpers for Verilog-A codegen: operating-window
derivation (voltage/current), runtime self-check line generation, and
best-effort supply/ground resolution for a digital pin.

Used by both core.ab_integration.ab_model_builder/ab_codegen (their
existing ok_windows()/`_domain_supply_nets()` delegate here) and
core.fsm.fsm_codegen (new logic-attribute self-checks), so both codegen
paths agree on what a pin's declared operating window is — sourced from
the same Port.voltage_range/current_range fields — and share one
supply/ground-resolution heuristic instead of maintaining two.
"""
from typing import List, Optional, Tuple


def port_ok_window(port) -> Optional[dict]:
    """Voltage window for supply/ground/bulk ports, current window for
    bias_current_sink/bias_current_source ports, else None (not a
    bounds-checkable pin). Degenerate [0,0] voltage ranges (e.g. a ground
    pin) get a +/-100 mV tolerance; bias current ranges get 20% headroom
    above the declared max so a nominal bias value doesn't flap the
    check."""
    if port.port_type in ('supply', 'ground', 'bulk'):
        lo, hi = float(port.voltage_range[0]), float(port.voltage_range[1])
        if hi <= lo:
            lo, hi = lo - 0.1, hi + 0.1
        return {'kind': 'voltage', 'lo': lo, 'hi': hi, 'source': 'voltage_range'}
    if port.port_type in ('bias_current_sink', 'bias_current_source'):
        lo, hi = float(port.current_range[0]), float(port.current_range[1])
        return {'kind': 'current', 'lo': lo, 'hi': hi * 1.2, 'source': 'current_range'}
    return None


def range_check_lines(port, ident: str, indent: str = '        ') -> List[str]:
    """Non-fatal runtime bounds check: a $strobe diagnostic (no
    simulation-altering behavior) when a port's V()/I() falls outside its
    declared operating window. Returns [] for a port with no derivable
    window (port_ok_window() -> None)."""
    win = port_ok_window(port)
    if win is None:
        return []
    access = f'V({ident})' if win['kind'] == 'voltage' else f'I({ident})'
    return [
        f'{indent}if (({access} < {win["lo"]:g}) || ({access} > {win["hi"]:g}))',
        f'{indent}    $strobe("[%m] {port.name} out of range: %g '
        f'(expected [{win["lo"]:g}, {win["hi"]:g}] {win["kind"]})", {access});',
    ]


def resolve_supply_ground(port, all_ports) -> Tuple[str, str]:
    """Best-effort (supply_pin_name, ground_pin_name) a digital port is
    referenced against: candidates are supply-typed pins whose declared
    voltage range covers this port's range; among them the taxonomy
    'vin'-hook pin wins, else the one with the largest current
    capability. No pin-name literals — an explicit *_UNRESOLVED
    placeholder is returned rather than a guessed name when the spec
    declares no supply/ground at all. `port` needs only a `voltage_range`
    attribute (a plain (lo, hi) tuple is enough), so callers resolving a
    whole domain group rather than one Port object can pass a lightweight
    stand-in."""
    from core.templates.pin_taxonomy import hook_for_pin
    hi = float(port.voltage_range[1])
    cands = [p for p in all_ports if p.port_type == 'supply'
             and float(p.voltage_range[1]) >= hi - 0.6]
    if not cands:
        cands = [p for p in all_ports if p.port_type == 'supply']
    hooked = [p for p in cands if hook_for_pin(p.name) == 'vin']
    pool = hooked or cands
    supply = max(pool, key=lambda p: max(abs(float(p.current_range[0])),
                                         abs(float(p.current_range[1])))
                 ).name if pool else 'VSUP_UNRESOLVED'
    grounds = [p.name for p in all_ports if p.port_type == 'ground']
    return supply, (grounds[0] if grounds else 'VGND_UNRESOLVED')
