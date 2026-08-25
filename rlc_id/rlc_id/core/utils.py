"""Shared numerical helpers: Hankel construction, order selection, pole matching."""
from __future__ import annotations
import numpy as np
from scipy.optimize import linear_sum_assignment


def hankel_block(markov_params: np.ndarray, n_rows: int, n_cols: int,
                  n_outputs: int = 1, n_inputs: int = 1) -> np.ndarray:
    """Build block Hankel matrix from Markov parameters (impulse response samples).
    markov_params: shape (n_samples, n_outputs, n_inputs)."""
    H = np.zeros((n_rows * n_outputs, n_cols * n_inputs))
    for i in range(n_rows):
        for j in range(n_cols):
            H[i * n_outputs:(i + 1) * n_outputs, j * n_inputs:(j + 1) * n_inputs] = markov_params[i + j]
    return H


def svd_knee_order(sing_vals: np.ndarray, rel_threshold: float = 1e-3, max_order: int | None = None) -> int:
    """Order selection via relative singular-value knee. Default threshold 1e-3 (per spec)."""
    sv = np.asarray(sing_vals)
    if sv[0] <= 0:
        return 1
    normalized = sv / sv[0]
    idx = np.where(normalized < rel_threshold)[0]
    order = int(idx[0]) if len(idx) else len(sv)
    order = max(order, 1)
    if max_order is not None:
        order = min(order, max_order)
    # state-space order from SISO real system should be even-ish for complex pairs,
    # but we don't force parity here -- caller may round as needed.
    return order


def pair_complex_conjugates(poles: np.ndarray, tol: float = 1e-6) -> np.ndarray:
    """Enforce exact complex-conjugate symmetry on a pole set (numerical cleanup)."""
    poles = np.asarray(poles, dtype=complex).copy()
    used = np.zeros(len(poles), dtype=bool)
    out = poles.copy()
    for i, p in enumerate(poles):
        if used[i] or abs(p.imag) < tol:
            continue
        # find closest conjugate partner
        dists = np.abs(poles - np.conj(p))
        dists[used] = np.inf
        dists[i] = np.inf
        j = int(np.argmin(dists))
        if dists[j] < 1e-3 * max(abs(p), 1.0):
            avg_re = (p.real + poles[j].real) / 2
            avg_im = (abs(p.imag) + abs(poles[j].imag)) / 2
            out[i] = avg_re + 1j * avg_im
            out[j] = avg_re - 1j * avg_im
            used[i] = used[j] = True
    return out


def canonicalize_poles(poles: np.ndarray, tol: float = 1e-6) -> np.ndarray:
    """Reorders a pole set so complex-conjugate partners are ADJACENT (poles[i],
    poles[i+1]) and real poles stand alone. Required because eigenvalue solvers
    (np.linalg.eigvals) return poles in arbitrary order -- consumers that walk the
    array assuming adjacent pairing (e.g. the real-coefficient VF basis) will
    silently mis-pair or drop poles otherwise. Supersedes pair_complex_conjugates
    for any caller that also needs positional guarantees, not just value cleanup."""
    poles = np.asarray(poles, dtype=complex)
    n = len(poles)
    used = np.zeros(n, dtype=bool)
    ordered = []
    for i in range(n):
        if used[i]:
            continue
        p = poles[i]
        if abs(p.imag) < tol:
            ordered.append(complex(p.real, 0.0))
            used[i] = True
            continue
        dists = np.abs(poles - np.conj(p))
        dists[used] = np.inf
        dists[i] = np.inf
        j = int(np.argmin(dists)) if n > 1 else -1
        if j >= 0 and dists[j] < 1e-2 * max(abs(p), 1.0):
            avg_re = (p.real + poles[j].real) / 2
            avg_im = (abs(p.imag) + abs(poles[j].imag)) / 2
            ordered.append(complex(avg_re, avg_im))
            ordered.append(complex(avg_re, -avg_im))
            used[i] = used[j] = True
        else:
            ordered.append(p)
            used[i] = True
    return np.array(ordered, dtype=complex)


def match_poles(true_poles: np.ndarray, est_poles: np.ndarray) -> tuple[np.ndarray, float]:
    """Hungarian-match estimated poles to ground-truth poles; returns (assignment, mean_abs_error)."""
    true_poles = np.asarray(true_poles, dtype=complex)
    est_poles = np.asarray(est_poles, dtype=complex)
    nt, ne = len(true_poles), len(est_poles)
    n = max(nt, ne)
    cost = np.full((n, n), 1e12)
    for i in range(nt):
        for j in range(ne):
            cost[i, j] = abs(true_poles[i] - est_poles[j])
    row_ind, col_ind = linear_sum_assignment(cost)
    errors = []
    assignment = []
    for r, c in zip(row_ind, col_ind):
        if r < nt and c < ne:
            errors.append(cost[r, c])
            assignment.append((r, c))
    mean_err = float(np.mean(errors)) if errors else float("inf")
    return np.array(assignment), mean_err


def is_positive_real_proxy(poles: np.ndarray) -> bool:
    """Cheap stability/passivity proxy: all poles in open left half-plane."""
    return bool(np.all(np.real(poles) < 1e-9))


def ss_to_pole_residue(A: np.ndarray, B: np.ndarray, C: np.ndarray, D: np.ndarray):
    """Eigendecompose SISO state-space into pole-residue form: G(s)=C(sI-A)^-1 B + D
    = sum_i residue_i/(s-pole_i) + d. Used by ERA/Subspace to enable netlist export."""
    w, V = np.linalg.eig(A)
    Vinv = np.linalg.inv(V)
    CV = (C @ V).flatten()
    VinvB = (Vinv @ B).flatten()
    residues = CV * VinvB
    d = float(np.real(D.flatten()[0])) if D.size else 0.0
    return w, residues, d
