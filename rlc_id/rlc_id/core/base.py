"""Common interface for all RLC identification strategies."""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import numpy as np


@dataclass
class StateSpaceModel:
    """Minimal LTI state-space realization x' = Ax + Bu, y = Cx + Du."""
    A: np.ndarray
    B: np.ndarray
    C: np.ndarray
    D: np.ndarray

    @property
    def order(self) -> int:
        return self.A.shape[0]

    def eig_poles(self) -> np.ndarray:
        return np.linalg.eigvals(self.A)


@dataclass
class PoleZeroModel:
    """Pole-residue (partial-fraction) representation of Y(s) or Z(s)."""
    poles: np.ndarray
    residues: np.ndarray
    d: float = 0.0   # constant (direct) term
    h: float = 0.0   # proportional-to-s term (Vector Fitting convention)
    zeros: np.ndarray = field(default_factory=lambda: np.array([]))

    def eval(self, s: np.ndarray) -> np.ndarray:
        s = np.atleast_1d(s)
        out = np.full(s.shape, self.d + 0j, dtype=complex)
        out = out + self.h * s
        for p, r in zip(self.poles, self.residues):
            out = out + r / (s - p)
        return out


class RLCIdentifier(ABC):
    """Common strategy interface. All methods (Prony, ERA, VF, Subspace, S-param)
    implement this so eval.py can loop over them uniformly."""

    name: str = "base"

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self._ss: StateSpaceModel | None = None
        self._pz: PoleZeroModel | None = None
        self._fit_time_s: float = 0.0
        self._order_selected: int | None = None

    @abstractmethod
    def fit(self, t_or_f, u, y, order: int | None = None) -> "RLCIdentifier":
        """t_or_f: time vector (time-domain methods) or frequency vector (freq-domain).
        u: input excitation samples (ignored by freq-domain-only methods).
        y: output response samples (or complex Y/Z/S data for freq-domain methods)."""
        raise NotImplementedError

    def poles(self) -> np.ndarray:
        if self._pz is not None:
            return self._pz.poles
        if self._ss is not None:
            return self._ss.eig_poles()
        raise RuntimeError("fit() must be called before poles()")

    def zeros(self) -> np.ndarray:
        if self._pz is not None:
            return self._pz.zeros
        return np.array([])

    def state_space(self) -> StateSpaceModel:
        if self._ss is None:
            raise RuntimeError("No state-space realization available for this method")
        return self._ss

    @abstractmethod
    def predict(self, u_new: np.ndarray, t_new: np.ndarray) -> np.ndarray:
        raise NotImplementedError

    @staticmethod
    def fit_error(y_true: np.ndarray, y_pred: np.ndarray, metric: str = "nrmse") -> float:
        y_true = np.asarray(y_true).ravel()
        y_pred = np.asarray(y_pred).ravel()
        n = min(len(y_true), len(y_pred))
        y_true, y_pred = y_true[:n], y_pred[:n]
        err = y_true - y_pred
        if metric == "nrmse":
            rng = np.max(y_true) - np.min(y_true)
            rng = rng if rng > 0 else 1.0
            return float(np.sqrt(np.mean(err ** 2)) / rng)
        if metric == "rmse":
            return float(np.sqrt(np.mean(err ** 2)))
        if metric == "mae":
            return float(np.mean(np.abs(err)))
        raise ValueError(f"unknown metric {metric}")

    def is_passive(self) -> bool:
        """Default: real part of poles must be <= 0 (stability proxy for passivity)."""
        try:
            p = self.poles()
        except RuntimeError:
            return False
        return bool(np.all(p.real <= 1e-9))

    def to_spice_netlist(self) -> str:
        """Foster-II (parallel RLC branches) export from pole-residue form.
        Real pole -> R//C branch; complex-conjugate pair -> R-L-C branch."""
        if self._pz is None:
            raise RuntimeError("to_spice_netlist requires a pole-residue model (fit VF/ERA/subspace first)")
        lines = ["* Foster-II realization, auto-generated"]
        node = 1
        seen = set()
        comp_idx = 0
        for p, r in zip(self._pz.poles, self._pz.residues):
            if id(p) in seen:
                continue
            comp_idx += 1
            if abs(p.imag) < 1e-9:
                # real pole -> single R,C parallel branch: pole = -1/(R C), residue = 1/C
                C = 1.0 / r.real if r.real != 0 else 1e-15
                R = -1.0 / (p.real * C) if p.real != 0 else 1e9
                lines.append(f"C{comp_idx} n{node} 0 {C:.6e}")
                lines.append(f"R{comp_idx} n{node} 0 {R:.6e}")
            else:
                # complex-conjugate pair -> series R-L-C branch (approximate mapping)
                wn = abs(p)
                zeta = -p.real / wn if wn != 0 else 0
                L = 1.0 / (2 * abs(r.real) + 1e-15)
                C = 1.0 / (wn ** 2 * L) if wn != 0 else 1e-15
                R = 2 * zeta * wn * L
                lines.append(f"L{comp_idx} n{node} n{node+1} {L:.6e}")
                lines.append(f"C{comp_idx} n{node+1} n{node+2} {C:.6e}")
                lines.append(f"R{comp_idx} n{node+2} 0 {R:.6e}")
                node += 2
            node += 1
        lines.append(".end")
        return "\n".join(lines)
