"""Prony's method -- linear prediction + polynomial rooting for sum-of-exponentials fit.
Reference: Marple, S.L., Digital Spectral Analysis with Applications, Prentice-Hall, 1987.
"""
from __future__ import annotations
import time as _time
import numpy as np
from scipy import signal
from ..core.base import RLCIdentifier, StateSpaceModel, PoleZeroModel
from ..core.utils import canonicalize_poles


class PronyIdentifier(RLCIdentifier):
    """Time-domain fit: t_or_f=uniform time vector, y=free/impulse response samples.
    order is REQUIRED (classic Prony has no built-in order-selection mechanism).

    kwargs: robust (bool, default True). Classic Prony (robust=False) solves the
    minimal 2p-sample system (Marple Ch. 12) -- exact but noise-fragile since every
    sample fully determines the fit with no averaging. robust=True instead
    over-specifies the linear-prediction order (SVD-averaged overdetermined LS,
    order q>p) and keeps only the p roots with the largest fitted residue magnitude
    -- the standard "order over-specification + dominant pole selection" robust
    Prony variant, closely related to the matrix pencil method (Hua & Sarkar, IEEE
    Trans. ASSP, 1990), which discards the extra roots as noise modes."""

    name = "prony"

    def fit(self, t_or_f, u, y, order: int | None = None) -> "PronyIdentifier":
        t0 = _time.perf_counter()
        if order is None:
            raise ValueError("Prony requires a fixed model order (no auto order-selection)")
        t = np.asarray(t_or_f, dtype=float)
        y = np.asarray(y, dtype=float)
        dt = t[1] - t[0]
        p = order
        robust = self.kwargs.get("robust", True)

        # Drop the leading sample: under a finite-pulse excitation (methods/era.py's
        # convention) a strictly-proper response has y[0]=0 exactly, which is an
        # initial-condition artifact, not part of the smooth exponential decay --
        # forcing a p-term sum-of-exponentials through y[0]=0 exactly otherwise
        # creates a spurious near-z=0 "correction" pole that can dominate residue-
        # magnitude-based pole selection in the robust/over-specified variant.
        skip = self.kwargs.get("skip_leading", 1)
        y_fit = y[skip:]

        if robust:
            z_poles = self._overspecified_denoise(y_fit, p)
        else:
            z_poles = self._linear_prediction_roots(y_fit, p, robust=False)
        z_poles = self._stabilize(z_poles)
        z_poles = canonicalize_poles(z_poles, tol=1e-6)

        n_fit = min(len(y_fit), max(10 * p, 50))
        residues_shifted = self._solve_residues(y_fit[:n_fit], z_poles)
        # residues_shifted reference t'=0 at true time t=skip*dt; correct back to t=0:
        # r_true = r_shifted / z_k^skip  (h(t)=sum r_k exp(pole_k t) consistency)
        residues = residues_shifted / (z_poles ** skip)
        s_poles = np.log(z_poles) / dt

        self._dt = dt
        self._order_selected = p
        self._pz = PoleZeroModel(poles=s_poles, residues=residues, d=0.0)
        self._ss = self._pz_to_ss(self._pz)
        self._fit_time_s = _time.perf_counter() - t0
        return self

    @staticmethod
    def _overspecified_denoise(y: np.ndarray, p: int) -> np.ndarray:
        """Fit at an over-specified order q>p (extra averaging via more LS equations
        AND more roots), then keep the p roots whose fitted residue magnitude is
        largest -- the extra roots absorb noise energy and are discarded."""
        N = len(y)
        q = min(max(2 * p, p + 6), max(N // 4, p + 1))
        z_all = PronyIdentifier._linear_prediction_roots(y, q, robust=True)
        z_all = PronyIdentifier._stabilize(z_all)
        n_fit = min(N, max(10 * q, 50))
        residues_all = PronyIdentifier._solve_residues(y[:n_fit], z_all)
        keep = np.argsort(-np.abs(residues_all))[:p]
        return z_all[keep]

    @staticmethod
    def _stabilize(z_poles: np.ndarray, margin: float = 0.999) -> np.ndarray:
        """Reflect any |z|>=1 root to just inside the unit circle, preserving phase.
        Physically justified: a passive RLC network cannot have non-decaying modes,
        so |z|>=1 is a noise artifact, not a legitimate estimate. Also prevents
        Vandermonde overflow in the subsequent residue fit."""
        z = z_poles.copy()
        unstable = np.abs(z) >= 1.0
        if np.any(unstable):
            z[unstable] = margin * np.exp(1j * np.angle(z[unstable]))
        return z

    @staticmethod
    def _linear_prediction_roots(y: np.ndarray, p: int, robust: bool) -> np.ndarray:
        """y[n] = sum_j a_j*y[n-j] (order-p linear recurrence); roots of the
        characteristic polynomial z^p - a_1 z^{p-1} - ... - a_p = 0 are the poles."""
        N = len(y)
        if robust:
            n_eq = N - p
            Y = np.zeros((n_eq, p))
            b = np.zeros(n_eq)
            for i in range(n_eq):
                Y[i, :] = y[i:i + p][::-1]
                b[i] = y[i + p]
            a, *_ = np.linalg.lstsq(Y, b, rcond=None)
        else:
            Y = np.zeros((p, p))
            b = np.zeros(p)
            for i in range(p):
                Y[i, :] = y[i:i + p][::-1]
                b[i] = y[i + p]
            a = np.linalg.solve(Y, b)
        poly_coeffs = np.concatenate([[1.0], -a])
        return np.roots(poly_coeffs).astype(complex)

    @staticmethod
    def _solve_residues(y: np.ndarray, z_poles: np.ndarray) -> np.ndarray:
        """y[n] = sum_k residue_k * z_k^n -- Vandermonde-style complex least squares."""
        N, p = len(y), len(z_poles)
        Z = np.zeros((N, p), dtype=complex)
        for k in range(N):
            Z[k, :] = z_poles ** k
        residues, *_ = np.linalg.lstsq(Z, y.astype(complex), rcond=None)
        return residues

    @staticmethod
    def _pz_to_ss(pz: PoleZeroModel) -> StateSpaceModel:
        n = len(pz.poles)
        A = np.diag(pz.poles)
        B = np.ones((n, 1), dtype=complex)
        C = pz.residues.reshape(1, n)
        D = np.array([[pz.d]], dtype=complex)
        return StateSpaceModel(A, B, C, D)

    def predict(self, u_new: np.ndarray, t_new: np.ndarray) -> np.ndarray:
        sys = signal.StateSpace(self._ss.A, self._ss.B, self._ss.C, self._ss.D)
        _, y_out, _ = signal.lsim(sys, U=u_new, T=t_new, interp=False)
        return np.real(y_out)
