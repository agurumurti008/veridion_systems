"""
core/ab_integration/ab_model_builder.py — FSM(A) + template(B) + deltas +
PVT provider -> ABModel.

ABModel.simulate() is the Python reference simulation of the composed
model: the learned FSM (states + pattern-diff guards from the repo's
detector/learner) is evaluated per timestep on binarized control-pin
waveforms, `supplies_ok` (spec-JSON window checks on supply/ground/bias
pins) gates everything to DISABLED when low, and the active state's
parameters (provider(corner) ⊕ state delta) drive the template ODEs
segment-by-segment with state continuity (x0 chaining) across
transitions.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

from core.pvt.provider import ParamProvider
from core.fitting.state_delta_fitter import StateParamSet


DEFAULT_PIN_MAP = {
    # template port -> spec-JSON pin (caller-overridable last resort;
    # derive_pin_map resolves these from the spec/taxonomy first.
    # VPWR_SEL / PAD_VDD1V2_SEL mux semantics deferred to questionnaire)
    'vin': 'V_SUPPLY',
    'vout': 'VDD_1V2',
    'gnd': 'AVSS',
    'enable': 'EN_LDO',
    'hp': 'HIGH_POWER_MODE',
}


def derive_pin_map(spec_kg) -> Dict[str, str]:
    """Template-port -> spec pin, derived from the spec itself: taxonomy
    hooks for vin/vout/gnd, fsm_role for enable ('enable') and hp
    ('mode_select'); first spec-order hit wins. DEFAULT_PIN_MAP fills only
    slots the spec cannot resolve."""
    from core.templates.pin_taxonomy import hook_for_pin
    m = dict(DEFAULT_PIN_MAP)
    if spec_kg is None:
        return m
    hooks: Dict[str, str] = {}
    roles: Dict[str, str] = {}
    for p in getattr(spec_kg, 'ports', []):
        h = hook_for_pin(p.name)
        if h in ('vin', 'vout', 'gnd') and h not in hooks:
            hooks[h] = p.name
        r = getattr(p, 'fsm_role', None)
        if r in ('enable', 'mode_select') and r not in roles:
            roles[r] = p.name
    m.update(hooks)
    if 'enable' in roles:
        m['enable'] = roles['enable']
    if 'mode_select' in roles:
        m['hp'] = roles['mode_select']
    return m

_COND_RE = re.compile(r'([A-Za-z_][\w.\[\]]*)\s*==\s*([01])')


def _parse_guard(conditions: List[str]) -> List[Tuple[str, int]]:
    out = []
    for cond in conditions:
        m = _COND_RE.search(cond)
        if m:
            out.append((m.group(1), int(m.group(2))))
    return out


@dataclass
class ABModel:
    template: object
    state_defs: Dict[int, dict]
    transitions: list
    provider: ParamProvider
    spec_kg: object
    state_param_set: Optional[StateParamSet] = None
    pin_map: Dict[str, str] = field(default_factory=lambda: dict(DEFAULT_PIN_MAP))
    fsm_timestep: float = 1e-7

    # ─── Spec-JSON-derived pin metadata ─────────────────────────────────────

    def _port(self, name: str):
        for p in self.spec_kg.ports:
            if p.name == name:
                return p
        return None

    def logic_threshold(self, pin: str) -> float:
        p = self._port(pin)
        if p is None:
            return 0.5
        lo, hi = p.voltage_range
        return (float(lo) + float(hi)) / 2.0 if hi > lo else 0.5

    def ok_windows(self) -> Dict[str, dict]:
        """<pin>_ok window definitions from the spec JSON: voltage windows
        for supply/ground/bulk pins, current windows for bias pins.
        Degenerate [0,0] ground ranges get a ±100 mV tolerance (recorded;
        exact bounce budget is a questionnaire item). Window derivation
        itself lives in core.spec_kg.port_bounds.port_ok_window, shared
        with core.fsm.fsm_codegen's runtime self-checks."""
        from core.spec_kg.port_bounds import port_ok_window
        wins = {}
        for p in self.spec_kg.ports:
            win = port_ok_window(p)
            if win is not None:
                wins[p.name] = win
        return wins

    # ─── FSM machinery ──────────────────────────────────────────────────────

    def _state_id_by_name(self, prefix: str) -> int:
        for sid in sorted(self.state_defs.keys()):
            if self.state_defs[sid]['name'].upper().startswith(prefix):
                return sid
        return sorted(self.state_defs.keys())[0]

    def _binarize_pins(self, t: np.ndarray,
                       pins: Dict[str, np.ndarray]) -> Dict[str, np.ndarray]:
        out = {}
        for name, wave in pins.items():
            th = self.logic_threshold(name)
            arr = np.full(len(t), float(wave)) if np.isscalar(wave) \
                else np.asarray(wave, dtype=float)
            out[name] = (arr > th).astype(int)
        return out

    def _supplies_ok_trace(self, t: np.ndarray,
                           pins: Dict[str, np.ndarray]) -> Dict[str, np.ndarray]:
        """Per-pin _ok traces + ANDed supplies_ok. Pins absent from the
        stimulus are assumed within their window (documented: the emitted
        Verilog-A checks every pin; the Python reference can only check
        what the stimulus drives)."""
        n = len(t)
        traces = {}
        overall = np.ones(n, dtype=bool)
        for pin, win in self.ok_windows().items():
            if pin not in pins:
                continue
            wave = pins[pin]
            arr = np.full(n, float(wave)) if np.isscalar(wave) \
                else np.asarray(wave, dtype=float)
            ok = (arr >= win['lo']) & (arr <= win['hi'])
            traces[f'{pin}_ok'] = ok
            overall &= ok
        traces['supplies_ok'] = overall
        return traces

    def fsm_step(self, sid: int, pin_bits: Dict[str, int]) -> int:
        """One FSM evaluation: most-specific-first guard scan of the
        learned transitions out of `sid`."""
        outs = sorted((tr for tr in self.transitions if tr.from_state == sid),
                      key=lambda tr: -len(tr.conditions))
        for tr in outs:
            terms = _parse_guard(tr.conditions)
            if terms and all(pin_bits.get(nm, 0) == val for nm, val in terms):
                return tr.to_state
        return sid

    # ─── Reference simulation ───────────────────────────────────────────────

    def simulate(self, stimulus: Dict, corner: str) -> Dict[str, np.ndarray]:
        """stimulus: {'t': array, 'pins': {pin_name: waveform-or-scalar}}.
        Pin names are spec-JSON names; pin_map picks which drive the
        template's vin/vout/gnd/enable/hp hooks."""
        t = np.asarray(stimulus['t'], dtype=float)
        pins = stimulus['pins']
        n = len(t)

        bits = self._binarize_pins(
            t, {k: v for k, v in pins.items()
                if self._port(k) is not None
                and self._port(k).domain == 'digital'})
        ok = self._supplies_ok_trace(t, pins)
        supplies_ok = ok['supplies_ok']

        vin_pin = self.pin_map['vin']
        vin_wave = pins.get(vin_pin, 5.0)
        vin_arr = np.full(n, float(vin_wave)) if np.isscalar(vin_wave) \
            else np.asarray(vin_wave, dtype=float)
        iload_wave = stimulus.get('iload', 0.0)
        iload_arr = np.full(n, float(iload_wave)) if np.isscalar(iload_wave) \
            else np.asarray(iload_wave, dtype=float)

        disabled_sid = self._state_id_by_name('DISABLED')

        # FSM trace (per sample; while supplies_ok is low the FSM is held
        # in DISABLED — the _ok gate outranks every learned transition)
        state_trace = np.zeros(n, dtype=int)
        sid = disabled_sid
        for i in range(n):
            if not supplies_ok[i]:
                sid = disabled_sid
            else:
                sid = self.fsm_step(sid, {k: int(v[i]) for k, v in bits.items()})
            state_trace[i] = sid

        # Segment on state changes; integrate the template per segment with
        # per-state params and x0 continuity (v_out, v_g, v_c carry over).
        en_pin = self.pin_map['enable']
        hp_pin = self.pin_map['hp']
        en_bits = bits.get(en_pin, np.ones(n, dtype=int))
        hp_bits = bits.get(hp_pin, np.zeros(n, dtype=int))

        vout = np.zeros(n)
        i_vin = np.zeros(n)
        vg = np.zeros(n)
        vc = np.zeros(n)
        x = None
        edges = [0] + [i for i in range(1, n)
                       if state_trace[i] != state_trace[i - 1]] + [n]
        for a, b in zip(edges[:-1], edges[1:]):
            seg = slice(a, b)
            name = self.state_defs[int(state_trace[a])]['name']
            params = self.provider.get_params_for_corner(corner, state=name)
            if not supplies_ok[a]:
                # Mirror the emitted Verilog-A safe-hold: pass device off
                # (enable already gated) and V(vout) bled to the ground
                # reference through 1 kOhm.
                params = dict(params)
                params['k_load'] = params.get('k_load', 0.0) + 1e-3
            t_seg = t[seg]
            inputs = {'vin': vin_arr[seg], 'iload': iload_arr[seg],
                      'en': en_bits[seg].astype(float) *
                            supplies_ok[seg].astype(float),
                      'hp': hp_bits[seg].astype(float)}
            if len(t_seg) < 2:
                if x is None:
                    op = self.template.dc_solve(
                        params, vin_arr[a], iload_arr[a],
                        mode={'enable': float(en_bits[a]),
                              'hp': float(hp_bits[a])})
                    x = np.array([op['vout'], op['vg'], op['vc']])
                vout[seg], vg[seg], vc[seg] = x[0], x[1], x[2]
                continue
            w = self.template.simulate(params, t_seg, inputs, x0=x)
            vout[seg] = w['vout']
            vg[seg] = w['vg']
            vc[seg] = w['vc']
            i_vin[seg] = w['i_vin']
            x = np.array([w['v_co'][-1], w['vg'][-1], w['vc'][-1]])

        # supplies_ok low -> analog held safe: enable is gated off and the
        # 1 kOhm bleed (added above, mirroring the emitted Verilog-A) pulls
        # V(vout) toward the ground reference; I(vin) is leakage only.
        bad = ~supplies_ok
        if bad.any():
            i_vin[bad] = 0.0

        out = {'t': t, 'vout': vout, 'i_vin': i_vin, 'vg': vg, 'vc': vc,
               'state_trace': state_trace,
               'state_names': {sid: d['name']
                               for sid, d in self.state_defs.items()},
               'vin': vin_arr, 'iload': iload_arr}
        out.update(ok)
        return out


def build_ab_model(template, state_defs, transitions, provider, spec_kg,
                   state_param_set=None, pin_map=None,
                   fsm_timestep: float = 1e-7) -> ABModel:
    return ABModel(template=template, state_defs=state_defs,
                   transitions=transitions, provider=provider,
                   spec_kg=spec_kg, state_param_set=state_param_set,
                   pin_map=dict(pin_map or derive_pin_map(spec_kg)),
                   fsm_timestep=fsm_timestep)
