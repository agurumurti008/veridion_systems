"""Eigensystem Realization Algorithm -- Juang & Pappa 1985."""
from __future__ import annotations
import numpy as np
from scipy import signal
from scipy.linalg import svd, logm, solve
from ..core.base import RLCIdentifier, StateSpaceModel, PoleZeroModel
from ..core.utils import svd_knee_order, ss_to_pole_residue


class ERAIdentifier(RLCIdentifier):
    """Impulse/step response -> minimal (A,B,C,D) via Hankel SVD.
    kwargs: input_type ('impulse'|'step'), svd_rel_threshold (default 1e-3).

    input_type='impulse' expects u as the actual driven excitation (a realistic
    finite-height pulse, e.g. u[0]=1/dt approximating a unit-area Dirac -- NOT the
    system's exact analytic impulse response). The dt-scaling this implies is what
    makes the recovered (B,C) gain correct; pole recovery alone is scale-invariant
    and works even with an idealized marker amplitude, but predict() will not be
    correctly scaled unless u reflects a real finite-width pulse."""

    name = "era"

    def fit(self, t_or_f, u, y, order: int | None = None) -> "ERAIdentifier":
        import time as _time
        t0 = _time.perf_counter()
        t = np.asarray(t_or_f, dtype=float)
        u = np.asarray(u, dtype=float)
        y = np.asarray(y, dtype=float)
        dt = t[1] - t[0]
        input_type = self.kwargs.get("input_type", "impulse")

        if input_type == "step":
            step_amp = u[len(u) // 2] if np.any(u != 0) else 1.0
            step_amp = step_amp if step_amp != 0 else 1.0
            # d/dt(step response)/step_amp = continuous unit-impulse response h(t);
            # discrete Markov parameters need h(k*dt)*dt (rectangle-rule equivalent of
            # the ZOH-discretized realization) -- the *dt is required, not optional.
            markov = (np.gradient(y, dt) / step_amp) * dt
        else:
            impulse_amp = np.max(np.abs(u)) if np.any(u != 0) else 1.0
            markov = y / impulse_amp

        n_samples = len(markov)
        n_rc = max(4, n_samples // 3)
        n_rc = min(n_rc, n_samples // 2 - 1)
        markov_use = markov[:2 * n_rc + 1]

        H0 = self._hankel(markov_use, n_rc, n_rc, 0)
        H1 = self._hankel(markov_use, n_rc, n_rc, 1)

        U, S, Vt = svd(H0, full_matrices=False)
        rel_thresh = self.kwargs.get("svd_rel_threshold", 1e-3)
        r = order if order is not None else svd_knee_order(S, rel_thresh, max_order=len(S))
        r = max(2, min(r, len(S)))
        self._order_selected = r
        self._singular_values = S

        U_r, S_r, Vt_r = U[:, :r], S[:r], Vt[:r, :]
        Sr_inv_sqrt = np.diag(1.0 / np.sqrt(S_r))
        Sr_sqrt = np.diag(np.sqrt(S_r))

        Ad = Sr_inv_sqrt @ U_r.T @ H1 @ Vt_r.T @ Sr_inv_sqrt
        Bd = (Sr_sqrt @ Vt_r)[:, :1]
        Cd = (U_r @ Sr_sqrt)[:1, :]
        # D=0: RLC one-ports are strictly proper (no instantaneous V/I feedthrough), and
        # markov[0] under the finite-pulse convention samples *during* the driving pulse
        # itself, not the free impulse response -- using it as D injects a spurious
        # non-decaying DC offset into predict(). Override via kwarg if a true D is needed.
        Dd = np.zeros((1, 1)) if self.kwargs.get("assume_strictly_proper", True) else np.array([[markov[0]]])

        self._dt = dt
        self._ss_discrete = StateSpaceModel(Ad, Bd, Cd, Dd)
        self._ss = self._to_continuous(Ad, Bd, Cd, Dd, dt)

        poles, residues, d = ss_to_pole_residue(self._ss.A, self._ss.B, self._ss.C, self._ss.D)
        self._pz = PoleZeroModel(poles=poles, residues=residues, d=d)
        self._fit_time_s = _time.perf_counter() - t0
        return self

    @staticmethod
    def _hankel(markov_1d: np.ndarray, n_rows: int, n_cols: int, shift: int) -> np.ndarray:
        H = np.zeros((n_rows, n_cols))
        for i in range(n_rows):
            for j in range(n_cols):
                H[i, j] = markov_1d[i + j + shift]
        return H

    @staticmethod
    def _to_continuous(Ad, Bd, Cd, Dd, dt) -> StateSpaceModel:
        """Discrete -> continuous via matrix log (ZOH inversion, standard realization step)."""
        n = Ad.shape[0]
        Ac = logm(Ad).real / dt
        try:
            M = solve(Ac, Ad - np.eye(n))  # Ac^-1 (Ad - I)
            Bc = solve(M, Bd)
        except np.linalg.LinAlgError:
            Bc = Bd / dt
        return StateSpaceModel(Ac.real, Bc.real, Cd.real, Dd.real)

    def predict(self, u_new: np.ndarray, t_new: np.ndarray) -> np.ndarray:
        sys = signal.StateSpace(self._ss.A, self._ss.B, self._ss.C, self._ss.D)
        _, y_out, _ = signal.lsim(sys, U=u_new, T=t_new)
        return y_out
