"""
core/fitting/vector_fitting.py — minimal Vector Fitting + ERA.

The repo had no rational-approximation machinery, so this vendors:

- vector_fit(): the pole-relocation Vector Fitting algorithm
  (Gustavsen & Semlyen, "Rational approximation of frequency domain
  responses by vector fitting", IEEE Trans. Power Delivery 14(3), 1999),
  scalar-response form with complex-conjugate pole handling and an
  asymptotic (d) term.
- era(): the Eigensystem Realization Algorithm on a sampled impulse (or
  differenced step) response — Hankel SVD -> reduced (A, B, C) -> poles.

Both are used by Stage LINEAR of SingleCornerFitter: vector_fit when AC
data (PSRR/Zout vs frequency) exists, era on load-step ring-down when
only transient data exists.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

import numpy as np


@dataclass
class RationalFit:
    poles: np.ndarray      # complex poles (rad/s)
    residues: np.ndarray   # complex residues, aligned with poles
    d: float               # constant (asymptotic) term
    rms_error: float       # fit residual on the provided samples

    def __call__(self, s: np.ndarray) -> np.ndarray:
        s = np.atleast_1d(np.asarray(s, dtype=complex))
        H = np.full(len(s), self.d, dtype=complex)
        for p, r in zip(self.poles, self.residues):
            H += r / (s - p)
        return H


def _initial_poles(freqs: np.ndarray, n_poles: int) -> np.ndarray:
    """Log-spaced complex-conjugate starting poles with small real parts
    (the standard VF initialization)."""
    f_lo = max(freqs[0], 1e-3)
    f_hi = freqs[-1]
    n_pairs = n_poles // 2
    poles = []
    if n_pairs > 0:
        betas = 2 * np.pi * np.logspace(np.log10(f_lo), np.log10(f_hi), n_pairs)
        for b in betas:
            a = -b / 100.0
            poles.append(complex(a, b))
            poles.append(complex(a, -b))
    if n_poles % 2 == 1:
        poles.append(complex(-2 * np.pi * np.sqrt(f_lo * f_hi), 0.0))
    return np.array(poles, dtype=complex)


def _build_basis(s: np.ndarray, poles: np.ndarray) -> np.ndarray:
    """Real-valued regression basis for complex-conjugate pole sets:
    conjugate pairs are folded into (real, imag) column pairs so the LS
    solve stays real and the result is guaranteed conjugate-symmetric."""
    n_s = len(s)
    cols = []
    skip = False
    for k, p in enumerate(poles):
        if skip:
            skip = False
            continue
        if abs(p.imag) > 1e-12:
            phi = 1.0 / (s - p)
            phi_c = 1.0 / (s - np.conj(p))
            cols.append(phi + phi_c)          # real-residue direction
            cols.append(1j * (phi - phi_c))   # imag-residue direction
            skip = True                        # partner pole consumed
        else:
            cols.append(1.0 / (s - p))
    return np.array(cols, dtype=complex).T.reshape(n_s, -1)


def _unfold_residues(x: np.ndarray, poles: np.ndarray) -> np.ndarray:
    """Inverse of _build_basis packing: (real, imag) coefficient pairs back
    to complex-conjugate residues aligned with `poles`."""
    residues = np.zeros(len(poles), dtype=complex)
    xi = 0
    k = 0
    while k < len(poles):
        p = poles[k]
        if abs(p.imag) > 1e-12:
            rr, ri = x[xi], x[xi + 1]
            residues[k] = complex(rr, ri)
            residues[k + 1] = complex(rr, -ri)
            xi += 2
            k += 2
        else:
            residues[k] = complex(x[xi], 0.0)
            xi += 1
            k += 1
    return residues


def vector_fit(freqs: np.ndarray, H: np.ndarray, n_poles: int = 4,
               n_iter: int = 12, enforce_stable: bool = True) -> RationalFit:
    """Fit H(j·2πf) ≈ d + Σ r_k/(s − p_k) by VF pole relocation.

    freqs : Hz, strictly positive, ascending.
    H     : complex response samples at freqs.
    """
    freqs = np.asarray(freqs, dtype=float)
    H = np.asarray(H, dtype=complex)
    if len(freqs) != len(H):
        raise ValueError("freqs and H must be the same length")
    if len(freqs) < 2 * n_poles + 2:
        raise ValueError(f"need >= {2 * n_poles + 2} samples for {n_poles} poles")
    s = 2j * np.pi * freqs
    poles = _initial_poles(freqs, n_poles)

    # weight ~ 1/|H| flattens dynamic range (standard practice)
    w = 1.0 / np.maximum(np.abs(H), 1e-12)

    for _ in range(n_iter):
        # Solve for sigma residues: [phi, 1, -H*phi] [r; d; r_sigma] = H
        basis = _build_basis(s, poles)
        n_r = basis.shape[1]
        A_cplx = np.hstack([
            basis,
            np.ones((len(s), 1), dtype=complex),
            -(H[:, None]) * basis,
        ])
        b_cplx = H
        Aw = A_cplx * w[:, None]
        bw = b_cplx * w
        A_real = np.vstack([Aw.real, Aw.imag])
        b_real = np.concatenate([bw.real, bw.imag])
        x, *_ = np.linalg.lstsq(A_real, b_real, rcond=None)
        sigma_res = _unfold_residues(x[n_r + 1:], poles)

        # New poles = zeros of sigma = eig(A_p - b·c^T)
        A_p = np.diag(poles)
        b_v = np.ones(len(poles), dtype=complex)
        new_poles = np.linalg.eigvals(A_p - np.outer(b_v, sigma_res))
        if enforce_stable:
            new_poles = np.where(new_poles.real > 0,
                                 -new_poles.real + 1j * new_poles.imag,
                                 new_poles)
        # Re-pair conjugates cleanly
        new_poles = np.sort_complex(new_poles)
        poles = new_poles

    # Final residue solve with fixed poles
    basis = _build_basis(s, poles)
    A_cplx = np.hstack([basis, np.ones((len(s), 1), dtype=complex)])
    Aw = A_cplx * w[:, None]
    bw = H * w
    A_real = np.vstack([Aw.real, Aw.imag])
    b_real = np.concatenate([bw.real, bw.imag])
    x, *_ = np.linalg.lstsq(A_real, b_real, rcond=None)
    residues = _unfold_residues(x[:-1], poles)
    d = float(x[-1])

    fit = RationalFit(poles=poles, residues=residues, d=d, rms_error=0.0)
    err = fit(s) - H
    fit.rms_error = float(np.sqrt(np.mean(np.abs(err * w) ** 2)))
    return fit


def era(y: np.ndarray, dt: float, order: int = 4,
        n_rows: Optional[int] = None) -> Tuple[np.ndarray, dict]:
    """Eigensystem Realization Algorithm on a uniformly sampled impulse
    response y (pass np.diff(step)/dt for step data).

    Returns (continuous-time poles [rad/s], info dict with discrete
    (A, B, C), Hankel singular values, and the model-vs-data rms error).
    """
    y = np.asarray(y, dtype=float).reshape(-1)
    n = len(y)
    if n < 2 * order + 2:
        raise ValueError(f"need >= {2 * order + 2} samples for order {order}")
    if n_rows is None:
        n_rows = min(n // 2, 20 * order)
    n_cols = n - n_rows
    if n_cols < order + 1:
        n_rows = n - order - 1
        n_cols = n - n_rows

    H0 = np.array([[y[i + j] for j in range(n_cols)] for i in range(n_rows)])
    H1 = np.array([[y[i + j + 1] for j in range(n_cols)] for i in range(n_rows)])

    U, S, Vt = np.linalg.svd(H0, full_matrices=False)
    r = min(order, int(np.sum(S > S[0] * 1e-10)))
    Ur, Sr, Vr = U[:, :r], S[:r], Vt[:r, :]
    S_sqrt = np.sqrt(Sr)
    A_d = np.diag(1.0 / S_sqrt) @ Ur.T @ H1 @ Vr.T @ np.diag(1.0 / S_sqrt)
    B_d = (np.diag(S_sqrt) @ Vr)[:, :1]
    C_d = (Ur @ np.diag(S_sqrt))[:1, :]

    eig_d = np.linalg.eigvals(A_d)
    eig_d = np.where(np.abs(eig_d) < 1e-12, 1e-12, eig_d)
    poles_ct = np.log(eig_d.astype(complex)) / dt

    # reconstruction error
    y_hat = np.zeros(n)
    x = B_d[:, 0].astype(complex)
    Ad_c = A_d.astype(complex)
    Cd_c = C_d[0].astype(complex)
    for i in range(n):
        y_hat[i] = float(np.real(Cd_c @ x))
        x = Ad_c @ x
    rms = float(np.sqrt(np.mean((y - y_hat) ** 2)))
    return poles_ct, {'A_d': A_d, 'B_d': B_d, 'C_d': C_d,
                      'hankel_sv': S, 'order_used': r, 'rms_error': rms,
                      'y_hat': y_hat}
