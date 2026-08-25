"""Laplace-domain analytical verification -- NOT a blind identifier.

This module takes an ALREADY-FITTED candidate pole-residue model (from ERA, Prony,
Vector Fitting, or Subspace) and produces the analytical time-domain response via
partial-fraction inversion, for cross-checking a candidate model's time response
against simulated/measured data. It does not estimate poles from data itself --
conflating this with the identification methods in methods/ would be a category
error (see the accompanying technical analysis, Section 4: Laplace-domain analytical
inversion has no noise-averaging mechanism and assumes the model order/structure is
already known, making it unsuitable as a standalone identification method).
"""
from __future__ import annotations
import numpy as np
from ..core.base import PoleZeroModel


class LaplaceAnalyticVerifier:
    """Forward-model-only verification: NOT an RLCIdentifier subclass, since it does
    not fit anything from data -- it only evaluates a given PoleZeroModel."""

    def __init__(self, pz: PoleZeroModel):
        self.pz = pz

    def impulse_response(self, t: np.ndarray) -> np.ndarray:
        """h(t) = sum_k residue_k * exp(pole_k * t) + d*delta(t) (delta term omitted,
        d is reported separately since it cannot be sampled on a discrete grid)."""
        t = np.asarray(t, dtype=float)
        h = np.zeros_like(t, dtype=complex)
        for p, r in zip(self.pz.poles, self.pz.residues):
            h += r * np.exp(p * t)
        return h.real

    def step_response(self, t: np.ndarray) -> np.ndarray:
        """Unit-step response via partial-fraction inversion of H(s)/s:
        y(t) = d + sum_k (residue_k/pole_k) * (exp(pole_k*t) - 1), for pole_k != 0."""
        t = np.asarray(t, dtype=float)
        y = np.full_like(t, self.pz.d, dtype=complex)
        for p, r in zip(self.pz.poles, self.pz.residues):
            if abs(p) < 1e-30:
                y += r * t  # pole at origin -> ramp contribution
            else:
                y += (r / p) * (np.exp(p * t) - 1)
        return y.real

    def frequency_response(self, w: np.ndarray) -> np.ndarray:
        """H(jw) evaluated directly from the pole-residue model (exact, no fitting)."""
        return self.pz.eval(1j * np.asarray(w, dtype=float))

    def cross_check(self, t: np.ndarray, y_reference: np.ndarray,
                     response_type: str = "impulse") -> dict:
        """Compare the candidate model's analytical response against reference
        (measured/simulated) data. Returns a dict with nrmse and the predicted trace
        -- use this to sanity-check an identified model, not to fit one."""
        if response_type == "impulse":
            y_pred = self.impulse_response(t)
        elif response_type == "step":
            y_pred = self.step_response(t)
        else:
            raise ValueError("response_type must be 'impulse' or 'step'")
        y_reference = np.asarray(y_reference, dtype=float)
        err = y_reference - y_pred
        rng = np.max(y_reference) - np.min(y_reference)
        rng = rng if rng > 0 else 1.0
        nrmse = float(np.sqrt(np.mean(err ** 2)) / rng)
        return {"nrmse": nrmse, "y_pred": y_pred}
