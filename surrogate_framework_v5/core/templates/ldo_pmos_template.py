"""
core/templates/ldo_pmos_template.py — canonical PMOS-pass LDO backbone.

Normative physics (A+B build prompt, Section 3):

  states x = [v_co, v_g, v_c]
    v_co : voltage across C_out (reported v_out adds the R_esr drop)
    v_g  : error-amp output / pass-gate node
    v_c  : compensator cap node (series Rz–Cc, Miller-connected to v_out)

  v_fb   = v_out · Rf2/(Rf1+Rf2)
  i_ea   = Gm_ea·(V_ref − v_fb), slew-limited to ±I_ea_max
           (implemented as I_ea_max·tanh(Gm_ea·err/I_ea_max): identical
           small-signal gm at small error, smooth saturation for LSODA)
  C_g·dv_g/dt = i_ea − v_g/R_ea − i_comp + Cgs·dvin/dt
           with C_g = C_ea + Cgs (the pass-device Cgs loads the same node,
           and — source at V_in — injects the Cgs·dvin/dt supply path)
  i_comp = (v_g − v_c)/Rz ; Cc·d(v_c − v_out)/dt = i_comp  (Miller to
           v_out; zero at 1/(Rz·Cc))
  pass PMOS: v_sg = V_in − v_g, vov = v_sg − |Vth_p|
    saturation (v_sd ≥ vov): i = ½·Kp·vov²·(1+λ·v_sd)
    triode     (v_sd <  vov): i = Kp·(vov·v_sd − v_sd²/2)·(1+λ·v_sd)
           — the triode branch IS the dropout behavior (no artificial clamp)
  current limit: i_pass ← I_lim·tanh(i_pass/I_lim)
  output node: i_c = i_pass − i_load − v_out/(Rf1+Rf2) − k_load·v_out
               + i_comp + Cgd·d(V_in − v_g)/dt
               C_out·dv_co/dt = i_c ;  v_out = v_co + R_esr·i_c
  PSRR emerges from structure: the (1+λ·v_sd) supply dependence, the Cgd
  feed-forward Cgd·d(V_in − v_g)/dt into the output node, and the Cgs
  supply path into the gate — no fitted gain block anywhere.

Mode hooks (pin taxonomy):
  enable : gates the EA (disabled → i_ea = 0 and the gate leaks to V_in so
           the PMOS turns off — a grounded leak would turn it fully ON)
  hp_lp  : HIGH_POWER_MODE=1 scales {Gm_ea, I_ea_max} by hp_gm_scale and
           I_lim by hp_ilim_scale; LP (=0) scales I_q by lp_iq_scale
  uvlo   : comparator on V_in with {V_uvlo_r, V_uvlo_f} hysteresis; the
           hysteresis trace is precomputed from vin(t) in simulate()
  bypass/mux + trim : hooks declared via pin_taxonomy; parameter values
           deferred to configs/sref_architecture_questionnaire.yaml
"""
from __future__ import annotations

from typing import Callable, Dict, List, Optional

import numpy as np
from scipy.integrate import solve_ivp
from scipy.optimize import brentq

from .base_template import AnalogTemplate
from .param_manifest import ParamSpec, ParamManifest


def _p(name, unit, default, lo, hi, log, mode, stage, desc):
    return ParamSpec(name=name, unit=unit, default=default, lo=lo, hi=hi,
                     log_scale=log, mode_affected=mode, fit_stage=stage,
                     description=desc)


LDO_PMOS_MANIFEST = ParamManifest([
    _p('Gm_ea',       'S',   1.0e-3, 1e-6,  1e-2,  True,  True,  'linear',
       'Error-amp transconductance'),
    _p('I_ea_max',    'A',   1.0e-4, 1e-7,  1e-3,  True,  True,  'transient',
       'EA output current limit (slew limit on the gate node)'),
    _p('R_ea',        'Ohm', 2.0e6,  1e4,   1e9,   True,  False, 'linear',
       'EA output resistance (gate-node leak; sets EA DC gain Gm_ea*R_ea)'),
    _p('C_ea',        'F',   2.0e-12, 1e-13, 1e-9,  True,  False, 'linear',
       'EA output-node capacitance (excl. pass-device Cgs)'),
    _p('Rz',          'Ohm', 1.0e5,  1e3,   1e8,   True,  False, 'linear',
       'Compensator series resistance (zero at 1/(Rz*Cc))'),
    _p('Cc',          'F',   3.0e-11, 1e-13, 1e-8,  True,  False, 'linear',
       'Compensator capacitance (series Rz–Cc, Miller to v_out)'),
    _p('Kp',          'A/V^2', 2.0,  1e-2,  2e1,   True,  False, 'dc',
       'Pass PMOS transconductance factor (1/2·Kp·vov^2 in saturation)'),
    _p('Vth_p',       'V',   0.6,    0.3,   1.0,   False, False, 'dc',
       'Pass PMOS |Vth|'),
    _p('lambda_p',    '1/V', 0.03,   1e-3,  0.5,   True,  False, 'dc',
       'Channel-length modulation (supply-coupling path in PSRR)'),
    _p('Cgd',         'F',   1.0e-11, 1e-12, 2e-9,  True,  False, 'linear',
       'Pass-device gate-drain cap (supply feed-forward into v_out)'),
    _p('Cgs',         'F',   2.0e-11, 1e-12, 5e-9,  True,  False, 'linear',
       'Pass-device gate-source cap (loads the EA node; supply path)'),
    _p('Rf1',         'Ohm', 1.0e5,  1e4,   1e7,   True,  False, 'dc',
       'Top feedback resistor (v_out -> v_fb)'),
    _p('Rf2',         'Ohm', 3.0e5,  1e4,   1e7,   True,  False, 'fixed',
       'Bottom feedback resistor (held fixed: only the ratio and the '
       'divider current are identifiable, so Rf1 floats and Rf2 anchors)'),
    _p('V_ref',       'V',   0.9,    0.5,   1.0,   False, False, 'fixed',
       'Bandgap reference at the EA positive input. Held fixed: from '
       'vout data only the product V_ref*(1+Rf1/Rf2) is identifiable, so '
       'the divider ratio (Rf1) floats and V_ref anchors — floating both '
       'is structurally degenerate (identifiability contract)'),
    _p('C_out',       'F',   4.7e-6, 1e-7,  2.2e-5, True, False, 'linear',
       'Output capacitor'),
    _p('R_esr',       'Ohm', 3.0e-1, 1e-3,  2.0,   True,  False, 'linear',
       'Output capacitor ESR (in series with C_out)'),
    _p('I_lim',       'A',   0.4,    0.05,  2.0,   True,  True,  'transient',
       'Soft current limit (tanh clamp on i_pass)'),
    _p('I_q',         'A',   2.0e-5, 1e-6,  2e-4,  True,  True,  'dc',
       'Quiescent supply current (added to I(vin), not load-delivered)'),
    _p('V_uvlo_r',    'V',   3.6,    1.0,   4.5,   False, False, 'fixed',
       'UVLO rising threshold on V_in (SREF value -> questionnaire)'),
    _p('V_uvlo_f',    'V',   3.4,    1.0,   4.5,   False, False, 'fixed',
       'UVLO falling threshold on V_in (SREF value -> questionnaire)'),
    _p('hp_gm_scale', '-',   3.0,    1.0,   10.0,  False, True,  'transient',
       'HIGH_POWER_MODE multiplier on {Gm_ea, I_ea_max}'),
    _p('hp_ilim_scale', '-', 2.0,    1.0,   10.0,  False, True,  'transient',
       'HIGH_POWER_MODE multiplier on I_lim'),
    _p('lp_iq_scale', '-',   0.25,   0.01,  1.0,   False, True,  'dc',
       'Low-power-mode multiplier on I_q'),
    _p('k_load',      'S',   1.0e-6, 1e-9,  1e-3,  True,  False, 'dc',
       'Output-node shunt conductance (load-regulation slope term)'),
])


def _as_callable(v, t_ref: Optional[np.ndarray] = None) -> Callable[[float], float]:
    """Normalize a scalar / aligned array / callable input to a callable."""
    if callable(v):
        return v
    if np.isscalar(v):
        val = float(v)
        return lambda t, _v=val: _v
    arr = np.asarray(v, dtype=float)
    if t_ref is None or len(arr) != len(t_ref):
        raise ValueError("array input requires an aligned time grid")
    tt = np.asarray(t_ref, dtype=float)
    return lambda t, _tt=tt, _a=arr: float(np.interp(t, _tt, _a))


class LdoPmosTemplate(AnalogTemplate):
    """Canonical PMOS-pass LDO (1.2 V / 200 mA / 5 V-input class)."""

    N_STATES = 3
    STATE_NAMES = ('v_co', 'v_g', 'v_c')

    def manifest(self) -> ParamManifest:
        return LDO_PMOS_MANIFEST

    # ─── Mode handling ───────────────────────────────────────────────────────

    @staticmethod
    def _mode_dict(mode: Optional[Dict]) -> Dict[str, float]:
        m = {'enable': 1.0, 'hp': 0.0, 'uvlo_ok': None}
        if mode:
            m.update(mode)
        return m

    @staticmethod
    def effective_params(params: Dict[str, float], hp: float) -> Dict[str, float]:
        """Apply the hp_lp mode hook to the affected parameter set."""
        p = dict(params)
        if hp >= 0.5:
            p['Gm_ea'] = params['Gm_ea'] * params['hp_gm_scale']
            p['I_ea_max'] = params['I_ea_max'] * params['hp_gm_scale']
            p['I_lim'] = params['I_lim'] * params['hp_ilim_scale']
            p['I_q'] = params['I_q']
        else:
            p['I_q'] = params['I_q'] * params['lp_iq_scale']
        return p

    def uvlo_trace(self, params: Dict[str, float], vin: np.ndarray,
                   initial: Optional[bool] = None) -> np.ndarray:
        """Hysteretic UVLO comparator scan over a vin waveform: rises when
        vin > V_uvlo_r, falls when vin < V_uvlo_f. The trace depends only
        on the (known) input waveform, so it is precomputed rather than
        carried as a discrete ODE state."""
        vr, vf = params['V_uvlo_r'], params['V_uvlo_f']
        vin = np.asarray(vin, dtype=float)
        ok = np.zeros(len(vin), dtype=bool)
        state = bool(vin[0] > vr) if initial is None else bool(initial)
        for i, v in enumerate(vin):
            if state and v < vf:
                state = False
            elif (not state) and v > vr:
                state = True
            ok[i] = state
        return ok

    # ─── Device / node physics ───────────────────────────────────────────────

    @staticmethod
    def _i_pass(p: Dict[str, float], vin: float, v_g: float, v_out: float) -> float:
        v_g_c = min(max(v_g, 0.0), max(vin, 0.0))  # EA output rails
        v_sg = vin - v_g_c
        vov = v_sg - p['Vth_p']
        if vov <= 0.0:
            return 0.0
        v_sd = vin - v_out
        if v_sd <= 0.0:
            return 0.0  # no reverse conduction (body diode not modeled)
        clm = 1.0 + p['lambda_p'] * v_sd
        if v_sd >= vov:
            i = 0.5 * p['Kp'] * vov * vov * clm          # saturation
        else:
            i = p['Kp'] * (vov * v_sd - 0.5 * v_sd * v_sd) * clm  # triode = dropout
        ilim = p['I_lim']
        return float(ilim * np.tanh(i / ilim))

    @staticmethod
    def _i_ea(p: Dict[str, float], v_fb: float, enabled: float) -> float:
        """EA output current INTO the gate node. Sign note (real bug found
        during the build): the build prompt writes i_ea = Gm·(V_ref − v_fb),
        but combined with the gate/pass equations as given that closes the
        loop with POSITIVE feedback (v_out↑ → v_g↓ → v_sg↑ → i_pass↑ → v_out↑)
        and DC solves land on a spurious root at v_out ≈ v_in with the EA
        railed. A PMOS pass device needs an INVERTING gate drive, so the
        current into the gate node is Gm·(v_fb − V_ref) — v_out above target
        pushes v_g toward V_in and turns the device off."""
        if enabled < 0.5:
            return 0.0
        err = v_fb - p['V_ref']
        imax = p['I_ea_max']
        return float(imax * np.tanh(p['Gm_ea'] * err / imax))

    def _node_currents(self, x: np.ndarray, p: Dict[str, float], vin: float,
                       iload: float, enabled: float, dvin_dt: float):
        """Shared algebraic core: given states and inputs, resolve the
        output node (2-pass fixed point over the R_esr drop) and return
        every branch current plus the reported v_out."""
        v_co, v_g, v_c = float(x[0]), float(x[1]), float(x[2])
        beta_den = p['Rf1'] + p['Rf2']
        i_comp = (v_g - v_c) / p['Rz']

        c_g = p['C_ea'] + p['Cgs']
        # Rail-recovery pull when v_g integrates outside [0, vin]
        v_g_clamped = min(max(v_g, 0.0), max(vin, 0.0))
        i_rail = (v_g - v_g_clamped) / 1e3

        # Fixed point on v_out = v_co + R_esr·i_c (i_pass depends on v_out)
        v_out = v_co
        i_c = 0.0
        i_pass = 0.0
        dv_g = 0.0
        for _ in range(2):
            v_fb = v_out * p['Rf2'] / beta_den
            i_ea = self._i_ea(p, v_fb, enabled)
            if enabled >= 0.5:
                leak = v_g / p['R_ea']
            else:
                # disabled: EA output stage parks the gate at V_in (PMOS off)
                leak = (v_g - vin) / p['R_ea']
            dv_g = (i_ea - leak - i_comp - i_rail + p['Cgs'] * dvin_dt) / c_g
            i_pass = self._i_pass(p, vin, v_g, v_out)
            i_cgd = p['Cgd'] * (dvin_dt - dv_g)  # Cgd·d(V_in − v_g)/dt
            i_c = (i_pass - iload - v_out / beta_den - p['k_load'] * v_out
                   + i_comp + i_cgd)
            v_out = v_co + p['R_esr'] * i_c
        return {
            'v_out': v_out, 'i_c': i_c, 'i_pass': i_pass, 'i_comp': i_comp,
            'dv_g': dv_g,
        }

    # ─── AnalogTemplate interface ────────────────────────────────────────────

    def odes(self, t: float, x: np.ndarray, params: Dict[str, float],
             inputs: Dict, mode: Optional[Dict[str, float]] = None) -> np.ndarray:
        m = self._mode_dict(mode)
        vin_f = inputs['vin'] if callable(inputs['vin']) else None
        vin = float(vin_f(t)) if vin_f else float(inputs['vin'])
        iload_f = inputs.get('iload', 0.0)
        iload = float(iload_f(t)) if callable(iload_f) else float(iload_f)

        if 'dvin_dt' in inputs:
            dv = inputs['dvin_dt']
            dvin_dt = float(dv(t)) if callable(dv) else float(dv)
        elif vin_f is not None:
            h = float(inputs.get('_dvin_h', 1e-9))
            dvin_dt = (float(vin_f(t + h)) - float(vin_f(t - h))) / (2 * h)
        else:
            dvin_dt = 0.0

        uvlo_ok = m['uvlo_ok']
        if uvlo_ok is None:
            uvlo_ok = 1.0 if vin > params['V_uvlo_r'] else 0.0
        enabled = 1.0 if (m['enable'] >= 0.5 and uvlo_ok >= 0.5) else 0.0

        p = self.effective_params(params, m['hp'])
        nc = self._node_currents(np.asarray(x, dtype=float), p, vin, iload,
                                 enabled, dvin_dt)
        dv_co = nc['i_c'] / p['C_out']
        # Miller connection: Cc·d(v_c − v_out)/dt = i_comp
        # dv_out/dt = dv_co/dt + R_esr·(di_c/dt); the ESR term is second-
        # order small for R_esr ≪ Rz and is dropped here (documented).
        dv_c = nc['i_comp'] / p['Cc'] + dv_co
        return np.array([dv_co, nc['dv_g'], dv_c], dtype=float)

    def dc_solve(self, params: Dict[str, float], vin: float, iload: float,
                 mode: Optional[Dict[str, float]] = None) -> Dict[str, float]:
        m = self._mode_dict(mode)
        uvlo_ok = m['uvlo_ok']
        if uvlo_ok is None:
            uvlo_ok = 1.0 if vin > params['V_uvlo_r'] else 0.0
        enabled = 1.0 if (m['enable'] >= 0.5 and uvlo_ok >= 0.5) else 0.0
        p = self.effective_params(params, m['hp'])
        beta_den = p['Rf1'] + p['Rf2']

        if enabled < 0.5 or vin <= 0.0:
            vg_off = max(vin, 0.0)  # gate parked at V_in -> pass device off
            return {'vout': 0.0, 'vg': vg_off, 'vc': vg_off,
                    'iq': 0.0 if vin <= 0 else p['I_q'] * 0.05,
                    'i_pass': 0.0, 'dropout_margin': 0.0, 'in_dropout': False,
                    'enabled': 0.0, 'vin': vin, 'iload': iload,
                    'hp': m['hp'], 'uvlo_ok': uvlo_ok}

        def vg_of(v_out: float) -> float:
            v_fb = v_out * p['Rf2'] / beta_den
            i_ea = self._i_ea(p, v_fb, 1.0)
            return min(max(p['R_ea'] * i_ea, 0.0), vin)  # EA rails

        def f(v_out: float) -> float:
            i_pass = self._i_pass(p, vin, vg_of(v_out), v_out)
            return i_pass - iload - v_out / beta_den - p['k_load'] * v_out

        # Bracket the root on [0, vin]: f decreases with v_out in regulation
        grid = np.linspace(0.0, vin, 201)
        fv = np.array([f(v) for v in grid])
        v_out = 0.0
        sign_change = np.where(np.sign(fv[:-1]) * np.sign(fv[1:]) < 0)[0]
        if len(sign_change) > 0:
            k = sign_change[-1]
            v_out = brentq(f, grid[k], grid[k + 1], xtol=1e-9)
        elif fv[0] <= 0.0:
            v_out = 0.0            # cannot support the load at all
        else:
            v_out = float(grid[np.argmin(np.abs(fv))])

        v_g = vg_of(v_out)
        i_pass = self._i_pass(p, vin, v_g, v_out)
        v_sg = vin - min(max(v_g, 0.0), vin)
        vov = max(v_sg - p['Vth_p'], 0.0)
        v_sd = vin - v_out
        margin = v_sd - vov
        return {'vout': float(v_out), 'vg': float(v_g), 'vc': float(v_g),
                'iq': float(p['I_q']), 'i_pass': float(i_pass),
                'dropout_margin': float(margin),
                'in_dropout': bool(v_sd < vov and vov > 0),
                'enabled': 1.0, 'vin': float(vin), 'iload': float(iload),
                'hp': m['hp'], 'uvlo_ok': float(uvlo_ok)}

    # ─── Small signal ────────────────────────────────────────────────────────

    def _output_fn(self, x: np.ndarray, params: Dict[str, float], vin: float,
                   iload: float, mode: Optional[Dict] = None) -> float:
        m = self._mode_dict(mode)
        uvlo_ok = m['uvlo_ok']
        if uvlo_ok is None:
            uvlo_ok = 1.0 if vin > params['V_uvlo_r'] else 0.0
        enabled = 1.0 if (m['enable'] >= 0.5 and uvlo_ok >= 0.5) else 0.0
        p = self.effective_params(params, m['hp'])
        return self._node_currents(x, p, vin, iload, enabled, 0.0)['v_out']

    @staticmethod
    def _siso_zeros(A, b, c, d, e=None):
        """Transmission zeros of H(s) = c(sI−A)⁻¹(b + s·e) + d via the
        generalized pencil [[A,b],[c,d]] − s·[[I,−e],[0,0]]. e=None means
        no input-rate feedthrough. Infinite eigenvalues filtered."""
        import scipy.linalg as sla
        n = A.shape[0]
        M = np.zeros((n + 1, n + 1))
        M[:n, :n] = A
        M[:n, n] = b
        M[n, :n] = c
        M[n, n] = d
        E = np.zeros((n + 1, n + 1))
        E[:n, :n] = np.eye(n)
        if e is not None:
            E[:n, n] = -np.asarray(e, dtype=float)
        w = sla.eigvals(M, E)
        return w[np.isfinite(w)]

    def small_signal(self, params: Dict[str, float], op: Dict[str, float],
                     freqs: Optional[np.ndarray] = None) -> Dict:
        if freqs is None:
            freqs = np.logspace(1, 7, 121)
        freqs = np.asarray(freqs, dtype=float)
        mode = {'enable': op.get('enabled', 1.0), 'hp': op.get('hp', 0.0),
                'uvlo_ok': op.get('uvlo_ok', 1.0)}
        x_op = np.array([op['vout'], op['vg'], op.get('vc', op['vg'])])
        u_op = {'vin': op['vin'], 'iload': op['iload']}

        A, B = self.linearize(params, x_op, u_op, mode=mode)

        # Input-RATE feedthrough column (real bug found during the build:
        # a static ∂f/∂vin linearization silently drops the Cgs·dvin/dt and
        # Cgd·dvin/dt supply paths, so PSRR(f) came from an incomplete
        # model). The system is descriptor-form dx/dt = Ax + Bu + E·du/dt
        # with E = ∂f/∂(dvin/dt); H_vin(s) = C(sI−A)⁻¹(B_vin + s·E_vin) + D.
        eps_r = 1e-3
        def _rhs_rate(rate):
            ins = {'vin': u_op['vin'], 'iload': u_op['iload'],
                   'dvin_dt': rate}
            return np.asarray(self.odes(0.0, x_op, params, ins, mode=mode))
        E_vin = (_rhs_rate(eps_r) - _rhs_rate(-eps_r)) / (2 * eps_r)

        # Numeric output row: y = v_out(x, u) including the ESR/Cgd algebra
        eps = 1e-7
        C = np.zeros(3)
        for j in range(3):
            dx = np.zeros(3)
            step = eps * max(1.0, abs(x_op[j]))
            dx[j] = step
            C[j] = (self._output_fn(x_op + dx, params, op['vin'], op['iload'], mode)
                    - self._output_fn(x_op - dx, params, op['vin'], op['iload'], mode)
                    ) / (2 * step)
        D = np.zeros(2)
        for j, name in enumerate(('vin', 'iload')):
            base = float(u_op[name])
            step = eps * max(1.0, abs(base))
            hiu = dict(u_op); hiu[name] = base + step
            lou = dict(u_op); lou[name] = base - step
            D[j] = (self._output_fn(x_op, params, hiu['vin'], hiu['iload'], mode)
                    - self._output_fn(x_op, params, lou['vin'], lou['iload'], mode)
                    ) / (2 * step)

        s = 2j * np.pi * freqs
        H_vin = np.empty(len(freqs), dtype=complex)
        H_il = np.empty(len(freqs), dtype=complex)
        for k, sk in enumerate(s):
            Rv = np.linalg.solve(sk * np.eye(3) - A, B[:, 0] + sk * E_vin)
            Ri = np.linalg.solve(sk * np.eye(3) - A, B[:, 1])
            H_vin[k] = C @ Rv + D[0]
            H_il[k] = C @ Ri + D[1]

        psrr_db = -20.0 * np.log10(np.maximum(np.abs(H_vin), 1e-15))
        zout = np.abs(H_il)  # iload defined as a draw: |dvout/diload|

        # Structural loop gain (broken at v_fb)
        p = self.effective_params(params, mode['hp'])
        beta = p['Rf2'] / (p['Rf1'] + p['Rf2'])
        v_g_c = min(max(op['vg'], 0.0), op['vin'])
        vov = max(op['vin'] - v_g_c - p['Vth_p'], 0.0)
        v_sd = op['vin'] - op['vout']
        clm = 1.0 + p['lambda_p'] * v_sd
        if v_sd >= vov:
            gm_p = p['Kp'] * vov * clm
            gds = 0.5 * p['Kp'] * vov * vov * p['lambda_p']
        else:
            gm_p = p['Kp'] * v_sd * clm
            gds = (p['Kp'] * (vov - v_sd) * clm
                   + p['Kp'] * (vov * v_sd - 0.5 * v_sd ** 2) * p['lambda_p'])
        c_g = p['C_ea'] + p['Cgs']
        z_comp = p['Rz'] + 1.0 / (s * p['Cc'])
        z_g = 1.0 / (1.0 / p['R_ea'] + s * c_g + 1.0 / z_comp)
        g_o = gds + 1.0 / (p['Rf1'] + p['Rf2']) + p['k_load']
        z_co = p['R_esr'] + 1.0 / (s * p['C_out'])
        z_o = 1.0 / (g_o + 1.0 / z_co)
        loop_gain = p['Gm_ea'] * z_g * gm_p * z_o * beta

        return {
            'A': A, 'B': B, 'C': C, 'D': D,
            'poles': np.linalg.eigvals(A),
            'zeros_psrr': self._siso_zeros(A, B[:, 0], C, D[0], e=E_vin),
            'zeros_zout': self._siso_zeros(A, B[:, 1], C, D[1]),
            'freqs': freqs,
            'psrr_db': psrr_db,
            'zout': zout,
            'loop_gain': loop_gain,
            'gm_p': gm_p, 'gds': gds, 'beta': beta,
        }

    # ─── Transient ───────────────────────────────────────────────────────────

    def simulate(self, params: Dict[str, float], t: np.ndarray, inputs: Dict,
                 mode: Optional[Dict[str, float]] = None,
                 x0: Optional[np.ndarray] = None) -> Dict[str, np.ndarray]:
        t = np.asarray(t, dtype=float)
        m = self._mode_dict(mode)

        vin_f = _as_callable(inputs['vin'], t)
        iload_f = _as_callable(inputs.get('iload', 0.0), t)
        en_f = _as_callable(inputs.get('en', m['enable']), t)
        hp_f = _as_callable(inputs.get('hp', m['hp']), t)

        vin_grid = np.array([vin_f(tk) for tk in t])
        uvlo_grid = self.uvlo_trace(params, vin_grid).astype(float)
        en_grid = (np.array([en_f(tk) for tk in t]) >= 0.5).astype(float)
        hp_grid = (np.array([hp_f(tk) for tk in t]) >= 0.5).astype(float)

        # Segment at every discrete mode edge; integrate each segment with
        # LSODA and chain x0 across segments (state continuity).
        disc = (en_grid.astype(int) * 4 + hp_grid.astype(int) * 2
                + uvlo_grid.astype(int))
        edges = [0] + [i for i in range(1, len(t)) if disc[i] != disc[i - 1]] \
                + [len(t)]

        if x0 is None:
            op0 = self.dc_solve(params, vin_grid[0], iload_f(t[0]),
                                mode={'enable': en_grid[0], 'hp': hp_grid[0],
                                      'uvlo_ok': uvlo_grid[0]})
            x0 = np.array([op0['vout'], op0['vg'], op0['vc']])
        x = np.asarray(x0, dtype=float).copy()

        xs = np.zeros((len(t), 3))
        for a, b in zip(edges[:-1], edges[1:]):
            seg = slice(a, b)
            seg_mode = {'enable': en_grid[a], 'hp': hp_grid[a],
                        'uvlo_ok': uvlo_grid[a]}
            seg_inputs = {'vin': vin_f, 'iload': iload_f,
                          '_dvin_h': max((t[1] - t[0]) * 1e-3, 1e-12)}
            t_seg = t[seg]
            if len(t_seg) == 1:
                xs[a] = x
                continue
            sol = solve_ivp(
                lambda tt, xx: self.odes(tt, xx, params, seg_inputs, seg_mode),
                (t_seg[0], t_seg[-1]), x, method='LSODA', t_eval=t_seg,
                rtol=1e-6, atol=1e-9, max_step=(t_seg[-1] - t_seg[0]) / 10,
            )
            if not sol.success:
                raise RuntimeError(f"LSODA failed in segment "
                                   f"[{t_seg[0]:.3e},{t_seg[-1]:.3e}]: "
                                   f"{sol.message}")
            xs[seg] = sol.y.T
            x = sol.y[:, -1].copy()

        # Post-pass: reported outputs per sample
        vout = np.zeros(len(t))
        ipass = np.zeros(len(t))
        ivin = np.zeros(len(t))
        for i, tk in enumerate(t):
            en_i = 1.0 if (en_grid[i] >= 0.5 and uvlo_grid[i] >= 0.5) else 0.0
            p = self.effective_params(params, hp_grid[i])
            nc = self._node_currents(xs[i], p, vin_grid[i], iload_f(tk),
                                     en_i, 0.0)
            vout[i] = nc['v_out']
            ipass[i] = nc['i_pass']
            ivin[i] = nc['i_pass'] + (p['I_q'] if en_i >= 0.5
                                      else 0.05 * p['I_q'])
        return {
            't': t, 'vout': vout, 'vg': xs[:, 1], 'vc': xs[:, 2],
            'v_co': xs[:, 0], 'i_pass': ipass, 'i_vin': ivin,
            'vin': vin_grid, 'uvlo_ok': uvlo_grid, 'en': en_grid,
            'hp': hp_grid,
        }

    # ─── Verilog-A core ──────────────────────────────────────────────────────

    def emit_veriloga_core(self, params: Dict[str, float]) -> str:
        p = dict(self.manifest().defaults())
        p.update(params)
        L = []
        L.append('// Auto-generated Verilog-A — canonical PMOS-pass LDO core')
        L.append('// (analog backbone only; FSM/pin wrapper comes from ab_codegen)')
        L.append('`include "disciplines.vams"')
        L.append('`include "constants.vams"')
        L.append('')
        L.append('module ldo_pmos_core(vin, vout, gnd, en, hp);')
        L.append('    inout vin, vout, gnd;')
        L.append('    input en, hp;')
        L.append('    electrical vin, vout, gnd, en, hp;')
        L.append('    electrical n_vg, n_vc;  // EA output node, compensator node')
        L.append('')
        for name in self.manifest().names:
            spec = self.manifest().spec(name)
            L.append(f'    parameter real {name} = {p[name]:.6g};'
                     f'  // {spec.unit} — {spec.description}')
        L.append('')
        L.append('    real v_fb, err, i_ea, i_comp, v_sg, vov, v_sd, i_sq, i_pass;')
        L.append('    real gm_eff, ieamax_eff, ilim_eff, iq_eff, en_v, hp_v;')
        L.append('')
        L.append('    analog begin')
        L.append('        en_v = (V(en, gnd) > 0.5) ? 1.0 : 0.0;')
        L.append('        hp_v = (V(hp, gnd) > 0.5) ? 1.0 : 0.0;')
        L.append('        gm_eff     = Gm_ea    * (hp_v > 0.5 ? hp_gm_scale   : 1.0);')
        L.append('        ieamax_eff = I_ea_max * (hp_v > 0.5 ? hp_gm_scale   : 1.0);')
        L.append('        ilim_eff   = I_lim    * (hp_v > 0.5 ? hp_ilim_scale : 1.0);')
        L.append('        iq_eff     = I_q      * (hp_v > 0.5 ? 1.0 : lp_iq_scale);')
        L.append('')
        L.append('        v_fb  = V(vout, gnd) * Rf2 / (Rf1 + Rf2);')
        L.append('        // Inverting gate drive (negative feedback with a PMOS pass')
        L.append('        // device): v_fb above V_ref pushes the gate toward V_in.')
        L.append('        err   = v_fb - V_ref;')
        L.append('        // EA: gm-limited (slew-limited) transconductor, gated by en')
        L.append('        i_ea  = en_v * ieamax_eff * tanh(gm_eff * err / ieamax_eff);')
        L.append('        i_comp = (V(n_vg, gnd) - V(n_vc, gnd)) / Rz;')
        L.append('')
        L.append('        // Gate node: C_ea+Cgs load, R_ea leak (to vin when disabled)')
        L.append('        I(n_vg) <+ (C_ea + Cgs) * ddt(V(n_vg, gnd));')
        L.append('        I(n_vg) <+ -i_ea + i_comp;')
        L.append('        I(n_vg) <+ en_v > 0.5 ? V(n_vg, gnd) / R_ea')
        L.append('                              : (V(n_vg, gnd) - V(vin, gnd)) / R_ea;')
        L.append('        I(n_vg) <+ -Cgs * ddt(V(vin, gnd));  // supply path via Cgs')
        L.append('')
        L.append('        // Compensator: series Rz–Cc, Miller to vout')
        L.append('        I(n_vc) <+ Cc * ddt(V(n_vc, vout));')
        L.append('        I(n_vc) <+ -i_comp;')
        L.append('')
        L.append('        // Pass PMOS: square-law with CLM; triode branch = dropout')
        L.append('        v_sg = V(vin, gnd) - V(n_vg, gnd);')
        L.append('        vov  = v_sg - Vth_p;')
        L.append('        v_sd = V(vin, gnd) - V(vout, gnd);')
        L.append('        if ((vov > 0) && (v_sd > 0)) begin')
        L.append('            if (v_sd >= vov)')
        L.append('                i_sq = 0.5 * Kp * vov * vov * (1 + lambda_p * v_sd);')
        L.append('            else')
        L.append('                i_sq = Kp * (vov * v_sd - 0.5 * v_sd * v_sd)'
                 ' * (1 + lambda_p * v_sd);')
        L.append('        end else')
        L.append('            i_sq = 0.0;')
        L.append('        i_pass = ilim_eff * tanh(i_sq / ilim_eff);  // soft current limit')
        L.append('')
        L.append('        // Output node: pass current in, load/divider/k_load out,')
        L.append('        // Cgd supply feed-forward, C_out + R_esr branch')
        L.append('        I(vin, vout)  <+ i_pass;')
        L.append('        I(vin, gnd)   <+ iq_eff * (en_v > 0.5 ? 1.0 : 0.05);')
        L.append('        I(vout, gnd)  <+ V(vout, gnd) / (Rf1 + Rf2);')
        L.append('        I(vout, gnd)  <+ k_load * V(vout, gnd);')
        L.append('        I(vout, gnd)  <+ -Cgd * ddt(V(vin, gnd) - V(n_vg, gnd));')
        L.append('        // C_out in series with R_esr: internal cap node folded into')
        L.append('        // a single branch contribution')
        L.append('        I(vout, gnd)  <+ C_out * ddt(V(vout, gnd)'
                 ' - R_esr * C_out * ddt(V(vout, gnd)));')
        L.append('    end')
        L.append('endmodule')
        return '\n'.join(L)
