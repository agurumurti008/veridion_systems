"""
core/templates/base_template.py — AnalogTemplate ABC.

Every Strategy-B backbone implements this interface. The contract is
deliberately simulation-centric: dc_solve/small_signal/simulate are what
the staged fitter (core/fitting) drives, odes is what the A+B composer
(core/ab_integration) integrates with per-state parameters, and
emit_veriloga_core is what ab_codegen wraps with the FSM/pin layer.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, Optional

import numpy as np


class AnalogTemplate(ABC):
    """Parameterized analog architecture backbone."""

    @abstractmethod
    def manifest(self):
        """Return the template's ParamManifest (ordering + bounds +
        fit-stage/mode metadata for every parameter)."""

    @abstractmethod
    def dc_solve(self, params: Dict[str, float], vin: float, iload: float,
                 mode: Optional[Dict[str, float]] = None) -> Dict[str, float]:
        """Solve the DC operating point at (vin, iload, mode). Returns at
        minimum: vout, vg, iq, i_pass, dropout_margin, in_dropout."""

    @abstractmethod
    def small_signal(self, params: Dict[str, float], op: Dict[str, float],
                     freqs: Optional[np.ndarray] = None) -> Dict:
        """Linearize at the operating point `op` (a dc_solve result) and
        return numeric small-signal views: state-space (A, B, C, D),
        poles/zeros, and PSRR(f) / Zout(f) / loop-gain(f) arrays over
        `freqs` (default log grid). PSRR and Zout must emerge from the
        linearized structure, not from fitted gain blocks."""

    @abstractmethod
    def odes(self, t: float, x: np.ndarray, params: Dict[str, float],
             inputs: Dict, mode: Optional[Dict[str, float]] = None) -> np.ndarray:
        """Nonlinear large-signal ODE right-hand side dx/dt at time t.
        `inputs` supplies vin(t)/iload(t) (callables or scalars)."""

    @abstractmethod
    def simulate(self, params: Dict[str, float], t: np.ndarray, inputs: Dict,
                 mode: Optional[Dict[str, float]] = None,
                 x0: Optional[np.ndarray] = None) -> Dict[str, np.ndarray]:
        """Integrate the template ODEs over the time grid t with the given
        input waveforms and (possibly time-varying) mode. Returns aligned
        waveform arrays, at minimum: t, vout, vg, vc, i_pass, i_vin."""

    @abstractmethod
    def emit_veriloga_core(self, params: Dict[str, float]) -> str:
        """Emit the analog core as a standalone Verilog-A module string
        (no FSM wrapper — that comes from core/ab_integration.ab_codegen)."""

    # ─── Shared conveniences (concrete, subclass-agnostic) ──────────────────

    def default_params(self) -> Dict[str, float]:
        return self.manifest().defaults()

    def linearize(self, params: Dict[str, float], x_op: np.ndarray,
                  u_op: Dict[str, float],
                  mode: Optional[Dict[str, float]] = None,
                  input_names=('vin', 'iload'), eps: float = 1e-7):
        """Numerical (central-difference) linearization of self.odes at an
        operating point: returns (A, B) with A = d f/d x and B = d f/d u
        for the named scalar inputs. Used by small_signal implementations
        and by identifiability checks; kept in the base class so every
        template linearizes the same way."""
        x_op = np.asarray(x_op, dtype=float)
        n = len(x_op)
        m = len(input_names)

        def rhs(x, u):
            ins = dict(u_op)
            ins.update(u)
            return np.asarray(
                self.odes(0.0, x, params, ins, mode=mode), dtype=float)

        A = np.zeros((n, n))
        for j in range(n):
            dx = np.zeros(n)
            step = eps * max(1.0, abs(x_op[j]))
            dx[j] = step
            A[:, j] = (rhs(x_op + dx, {}) - rhs(x_op - dx, {})) / (2 * step)

        B = np.zeros((n, m))
        for j, name in enumerate(input_names):
            base = float(u_op[name])
            step = eps * max(1.0, abs(base))
            B[:, j] = (rhs(x_op, {name: base + step})
                       - rhs(x_op, {name: base - step})) / (2 * step)
        return A, B
