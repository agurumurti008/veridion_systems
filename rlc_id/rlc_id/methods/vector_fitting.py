"""Vector Fitting -- Gustavsen & Semlyen, IEEE Trans. Power Del. 14(3), 1999.
Frequency-domain rational fitting via iterative pole relocation.

Numerical conditioning notes (required for real RLC/PDN bandwidths spanning
many decades): frequencies are internally normalized by w_scale=sqrt(w_min*w_max)
so pole search operates on O(1) values, and rows are weighted by 1/|H(s_k)|
(standard weighted-VF trick) so the fit is not dominated purely by the
largest-magnitude samples. Both are undone before poles/residues are returned.
"""
from __future__ import annotations
import time as _time
import numpy as np
from ..core.base import RLCIdentifier, StateSpaceModel, PoleZeroModel
from ..core.utils import canonicalize_poles


def _init_poles(n_poles: int, w_min: float, w_max: float, spacing: str = "log",
                 include_real: bool = False) -> np.ndarray:
    """Seed starting poles spread across [w_min, w_max]. Pure complex-conjugate seeding
    (Gustavsen-Semlyen default) works well for resonant systems; include_real=True mixes
    in real-axis poles too, useful when the target may have overdamped/real modes
    (e.g. multi-stage cascaded ladders) that a complex-only seed converges to poorly."""
    w_min = max(w_min, 1e-6)
    if include_real:
        n_real = n_poles // 4
        if (n_poles - n_real) % 2 != 0:
            n_real += 1  # remaining count must be even (splits into conjugate pairs)
        n_cplx_poles = n_poles - n_real
    else:
        n_real, n_cplx_poles = 0, n_poles
    n_pairs = max(1, n_cplx_poles // 2)

    if spacing == "log":
        grid = np.logspace(np.log10(w_min), np.log10(w_max), n_pairs + n_real + 2)[1:-1]
    else:
        grid = np.linspace(w_min, w_max, n_pairs + n_real + 2)[1:-1]

    real_poles = [-abs(g) for g in grid[:n_real]]
    beta = grid[n_real:n_real + n_pairs]
    cplx_poles = []
    for b in beta:
        alpha = -b * 0.01
        cplx_poles += [alpha + 1j * b, alpha - 1j * b]
    poles = real_poles + cplx_poles
    return np.array(poles[:n_poles], dtype=complex)


def _real_basis_matrix(s: np.ndarray, poles: np.ndarray):
    """Real-coefficient basis for complex-conjugate pole pairs (standard VF trick)."""
    cols, kinds = [], []
    i, n = 0, len(poles)
    while i < n:
        p = poles[i]
        if abs(p.imag) < 1e-12:
            cols.append(1.0 / (s - p.real))
            kinds.append(("real",))
            i += 1
        else:
            pc = np.conj(p)
            cols.append(1.0 / (s - p) + 1.0 / (s - pc))
            cols.append(1j / (s - p) - 1j / (s - pc))
            kinds.append(("cplx",))
            i += 2
    return np.array(cols).T, kinds


def _solve_scaled(A: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Column-equilibrated least squares: normalizes each column to unit norm before
    solving, then un-scales the result. Required when candidate poles span many decades
    (basis columns 1/(s-p_k) then differ in magnitude by many orders), which otherwise
    collapses the effective rank of the system regardless of row weighting."""
    col_norms = np.linalg.norm(A, axis=0)
    col_norms[col_norms == 0] = 1.0
    x_scaled, *_ = np.linalg.lstsq(A / col_norms, b, rcond=None)
    return x_scaled / col_norms


def _real_coeffs_to_complex_residues(coeffs: np.ndarray, kinds: list) -> np.ndarray:
    out, idx = [], 0
    for k in kinds:
        if k[0] == "real":
            out.append(complex(coeffs[idx]))
            idx += 1
        else:
            cr, ci = coeffs[idx], coeffs[idx + 1]
            out += [complex(cr, ci), complex(cr, -ci)]
            idx += 2
    return np.array(out, dtype=complex)


class VectorFittingIdentifier(RLCIdentifier):
    """Frequency-domain fit: t_or_f is angular frequency (rad/s), y is complex H(jw)
    (Y, Z, or S parameter samples). kwargs: n_poles, pole_spacing ('log'|'linear'),
    n_iterations, enforce_passivity (bool, default True), weighting (bool, default True),
    fit_proportional (bool, default False -- include s*h term for non-strictly-proper H)."""

    name = "vector_fitting"

    def fit(self, t_or_f, u, y, order: int | None = None) -> "VectorFittingIdentifier":
        t0 = _time.perf_counter()
        w = np.asarray(t_or_f, dtype=float)
        H = np.asarray(y, dtype=complex)

        n_poles = order if order is not None else self.kwargs.get("n_poles", 10)
        n_poles = n_poles + (n_poles % 2)
        spacing = self.kwargs.get("pole_spacing", "log")
        n_iter = self.kwargs.get("n_iterations", 8)
        fit_prop = self.kwargs.get("fit_proportional", False)
        use_weighting = self.kwargs.get("weighting", True)

        w_pos = w[w > 0]
        w_scale = np.sqrt(w_pos.min() * w_pos.max()) if len(w_pos) else 1.0
        self._w_scale = w_scale
        wn = w / w_scale
        sn = 1j * wn
        wn_pos = wn[wn > 0]

        include_real = self.kwargs.get("include_real_poles", True)
        poles_n = _init_poles(n_poles, wn_pos.min() if len(wn_pos) else 1.0, wn.max(),
                               spacing, include_real=include_real)
        weights = 1.0 / np.maximum(np.abs(H), 1e-30) if use_weighting else np.ones_like(H, dtype=float)

        for _ in range(n_iter):
            poles_n = self._iterate(sn, H, poles_n, weights, fit_prop)

        residues_n, d, h_n = self._final_residues(sn, H, poles_n, weights, fit_prop)

        poles = poles_n * w_scale
        residues = residues_n * w_scale
        h = (h_n / w_scale) if fit_prop else 0.0

        self._order_selected = len(poles)
        self._pz = PoleZeroModel(poles=poles, residues=residues, d=d, h=h)

        if self.kwargs.get("enforce_passivity", True):
            self._enforce_passivity()

        self._ss = self._pz_to_ss(self._pz)
        self._fit_time_s = _time.perf_counter() - t0
        return self

    def _iterate(self, s: np.ndarray, H: np.ndarray, poles: np.ndarray,
                 weights: np.ndarray, fit_prop: bool) -> np.ndarray:
        Phi, kinds = _real_basis_matrix(s, poles)
        n = Phi.shape[1]
        cols = [Phi, np.ones_like(s).reshape(-1, 1)]
        if fit_prop:
            cols.append(s.reshape(-1, 1))
        cols.append(-(Phi * H.reshape(-1, 1)))
        A = np.hstack(cols) * weights.reshape(-1, 1)
        b = H * weights
        A_stack = np.vstack([A.real, A.imag])
        b_stack = np.concatenate([b.real, b.imag])
        x = _solve_scaled(A_stack, b_stack)
        c_tilde = x[-n:]
        sigma_residues = _real_coeffs_to_complex_residues(c_tilde, kinds)
        return self._sigma_zeros(poles, sigma_residues)

    @staticmethod
    def _sigma_zeros(poles: np.ndarray, sigma_residues: np.ndarray) -> np.ndarray:
        """New poles = eigenvalues of diag(poles) - ones*sigma_residues^T (VF relocation)."""
        n = len(poles)
        M = np.diag(poles) - np.ones((n, 1), dtype=complex) @ sigma_residues.reshape(1, n)
        new_poles = np.linalg.eigvals(M)
        new_poles = np.where(new_poles.real > 0, -new_poles.real + 1j * new_poles.imag, new_poles)
        return canonicalize_poles(new_poles)

    def _final_residues(self, s: np.ndarray, H: np.ndarray, poles: np.ndarray,
                         weights: np.ndarray, fit_prop: bool):
        Phi, kinds = _real_basis_matrix(s, poles)
        cols = [Phi, np.ones_like(s).reshape(-1, 1)]
        if fit_prop:
            cols.append(s.reshape(-1, 1))
        A = np.hstack(cols) * weights.reshape(-1, 1)
        b = H * weights
        A_stack = np.vstack([A.real, A.imag])
        b_stack = np.concatenate([b.real, b.imag])
        x = _solve_scaled(A_stack, b_stack)
        n = Phi.shape[1]
        residues = _real_coeffs_to_complex_residues(x[:n], kinds)
        d = float(x[n])
        h = float(x[n + 1]) if fit_prop else 0.0
        return residues, d, h

    def _enforce_passivity(self):
        """Simplified residue-sign perturbation (full form: Gustavsen, IEEE TPD 16(4), 2001)."""
        r, p = self._pz.residues.copy(), self._pz.poles
        for i in range(len(p)):
            if abs(p[i].imag) < 1e-9 and r[i].real < 0:
                r[i] = complex(abs(r[i].real), 0)
        self._pz.residues = r

    @staticmethod
    def _pz_to_ss(pz: PoleZeroModel) -> StateSpaceModel:
        n = len(pz.poles)
        A = np.diag(pz.poles)
        B = np.ones((n, 1), dtype=complex)
        C = pz.residues.reshape(1, n)
        D = np.array([[pz.d]], dtype=complex)
        return StateSpaceModel(A, B, C, D)

    def predict(self, u_new: np.ndarray, t_new: np.ndarray) -> np.ndarray:
        """t_new is treated as the angular-frequency axis (rad/s) to evaluate H(jw) at;
        u_new is unused -- VF predicts the transfer function directly, not a driven response."""
        w = np.asarray(t_new, dtype=float)
        return self._pz.eval(1j * w)

    def is_passive(self) -> bool:
        r, p = self._pz.residues, self._pz.poles
        for i in range(len(p)):
            if abs(p[i].imag) < 1e-9 and r[i].real < 0:
                return False
        return bool(np.all(p.real <= 1e-9))
