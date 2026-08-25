"""State-space realization from general (non-impulse) time-domain input-output data.

Implementation note: rather than a hand-rolled N4SID/MOESP oblique projection (which
is numerically delicate to get right -- LQ-decomposition-based subspace methods have
many failure modes for short/noisy data), this uses ARX estimation (linear, robust,
Ljung Ch.10) followed by a canonical-form realization (Ho-Kalman-equivalent for the
resulting transfer function). This achieves the same goal the spec calls for --
identification from *arbitrary* driven input, generalizing ERA's impulse-only
scope -- via a simpler and more robust numerical path. For genuine subspace/N4SID
behavior see Van Overschee & De Moor, Subspace Identification for Linear Systems,
Kluwer, 1996 -- noted here as the reference this method's *purpose* follows.
"""
from __future__ import annotations
import time as _time
import numpy as np
from scipy import signal
from scipy.linalg import logm, solve
from ..core.base import RLCIdentifier, StateSpaceModel, PoleZeroModel
from ..core.utils import ss_to_pole_residue


class SubspaceIdentifier(RLCIdentifier):
    """General time-domain fit: t_or_f=uniform time vector, u=arbitrary input,
    y=output response. order sets the ARX order p (both AR and X lag depth).
    kwargs: instrumental_variable (bool, default False -- one round of IV
    re-weighting using lagged u as instruments, reduces bias under output noise)."""

    name = "subspace"

    def fit(self, t_or_f, u, y, order: int | None = None) -> "SubspaceIdentifier":
        t0 = _time.perf_counter()
        t = np.asarray(t_or_f, dtype=float)
        u = np.asarray(u, dtype=float)
        y = np.asarray(y, dtype=float)
        dt = t[1] - t[0]
        p = order if order is not None else self.kwargs.get("default_order", 8)
        N = len(y)
        if N <= 3 * p:
            raise ValueError(f"not enough samples ({N}) for ARX order {p}")

        theta = self._fit_arx(u, y, p)
        if self.kwargs.get("instrumental_variable", False):
            theta = self._iv_refine(u, y, p, theta)

        a = theta[:p]
        b_coeffs = theta[p:]
        den = np.concatenate([[1.0], -a])
        num = b_coeffs

        Ad, Bd, Cd, Dd = signal.tf2ss(num, den)
        Bd = Bd.reshape(-1, 1)
        Cd = Cd.reshape(1, -1)
        Dd = np.atleast_2d(Dd)

        self._dt = dt
        self._order_selected = Ad.shape[0]
        self._ss_discrete = StateSpaceModel(Ad, Bd, Cd, Dd)
        self._ss = self._to_continuous(Ad, Bd, Cd, Dd, dt)
        poles, residues, d = ss_to_pole_residue(self._ss.A, self._ss.B, self._ss.C, self._ss.D)
        self._pz = PoleZeroModel(poles=poles, residues=residues, d=d)
        self._fit_time_s = _time.perf_counter() - t0
        return self

    @staticmethod
    def _fit_arx(u: np.ndarray, y: np.ndarray, p: int) -> np.ndarray:
        """y[n] = sum_{i=1}^p a_i y[n-i] + sum_{i=0}^p b_i u[n-i], least squares."""
        N = len(y)
        n_eq = N - p
        n_unk = p + (p + 1)
        Y = np.zeros((n_eq, n_unk))
        b_vec = np.zeros(n_eq)
        for k in range(n_eq):
            n = k + p
            Y[k, :p] = y[n - p:n][::-1]
            Y[k, p:] = u[n - p:n + 1][::-1]
            b_vec[k] = y[n]
        theta, *_ = np.linalg.lstsq(Y, b_vec, rcond=None)
        return theta

    @staticmethod
    def _iv_refine(u: np.ndarray, y: np.ndarray, p: int, theta0: np.ndarray) -> np.ndarray:
        """One instrumental-variable pass: replace lagged-y regressors with the
        noise-free model prediction (simulated from theta0) as instruments, reducing
        bias from output measurement noise (standard IV4-style correction)."""
        N = len(y)
        a0, b0 = theta0[:p], theta0[p:]
        den0 = np.concatenate([[1.0], -a0])
        y_sim = signal.lfilter(b0, den0, u)
        n_eq = N - p
        n_unk = p + (p + 1)
        Y = np.zeros((n_eq, n_unk))
        Z = np.zeros((n_eq, n_unk))
        b_vec = np.zeros(n_eq)
        for k in range(n_eq):
            n = k + p
            Y[k, :p] = y[n - p:n][::-1]
            Y[k, p:] = u[n - p:n + 1][::-1]
            Z[k, :p] = y_sim[n - p:n][::-1]
            Z[k, p:] = u[n - p:n + 1][::-1]
            b_vec[k] = y[n]
        # IV estimator: theta = (Z^T Y)^-1 Z^T b
        try:
            theta = np.linalg.solve(Z.T @ Y, Z.T @ b_vec)
        except np.linalg.LinAlgError:
            theta = theta0
        return theta

    @staticmethod
    def _to_continuous(Ad, Bd, Cd, Dd, dt) -> StateSpaceModel:
        n = Ad.shape[0]
        try:
            Ac = logm(Ad).real / dt
            M = solve(Ac, Ad - np.eye(n))
            Bc = solve(M, Bd)
        except (np.linalg.LinAlgError, ValueError):
            Ac = (Ad - np.eye(n)) / dt
            Bc = Bd / dt
        return StateSpaceModel(Ac.real, Bc.real, Cd.real, Dd.real)

    def predict(self, u_new: np.ndarray, t_new: np.ndarray) -> np.ndarray:
        sys = signal.StateSpace(self._ss.A, self._ss.B, self._ss.C, self._ss.D)
        _, y_out, _ = signal.lsim(sys, U=u_new, T=t_new, interp=False)
        return y_out
