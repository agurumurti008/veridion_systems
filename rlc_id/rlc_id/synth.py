"""Synthetic RLC network generator with known analytical poles for benchmarking.

Provides ground-truth (poles, zeros, state-space) plus a simulate() to generate
noisy/bandwidth-limited time-domain responses for any excitation.
"""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np
from scipy import signal


@dataclass
class GroundTruthNetwork:
    name: str
    poles: np.ndarray          # known analytical poles (rad/s)
    zeros: np.ndarray
    gain: float
    ss: tuple                  # (A, B, C, D)
    components: dict           # R/L/C values used, for reference / netlist export

    def tf(self):
        """Return (num, den) polynomial transfer function coefficients."""
        A, B, C, D = self.ss
        return signal.ss2tf(A, B, C, D)

    def simulate(self, t: np.ndarray, u: np.ndarray, snr_db: float | None = None,
                 bandwidth_hz: float | None = None) -> np.ndarray:
        """Simulate y(t) for input u(t), optionally add noise / bandwidth limiting.
        Uses zero-order-hold interpolation (interp=False): scipy's default linear
        interpolation turns a single-sample impulse into a triangular pulse with
        HALF the intended area, silently corrupting impulse/pulse excitation gain
        by 2x. ZOH also better matches a real sampled-DAC excitation physically."""
        A, B, C, D = self.ss
        sys = signal.StateSpace(A, B, C, D)
        _, y, _ = signal.lsim(sys, U=u, T=t, interp=False)
        if bandwidth_hz is not None:
            fs = 1.0 / (t[1] - t[0])
            wn = min(bandwidth_hz / (fs / 2), 0.999)
            b, a = signal.butter(4, wn)
            y = signal.filtfilt(b, a, y)
        if snr_db is not None:
            sig_power = np.mean(y ** 2)
            noise_power = sig_power / (10 ** (snr_db / 10))
            y = y + np.random.normal(0, np.sqrt(max(noise_power, 1e-30)), size=y.shape)
        return y


def series_rlc(R: float, L: float, C: float) -> GroundTruthNetwork:
    """Series RLC one-port, admittance Y(s) driven by voltage; state x=[i, v_c].
    Closed-form poles: s = -R/(2L) +/- sqrt((R/(2L))^2 - 1/(LC))."""
    A = np.array([[-R / L, -1 / L], [1 / C, 0]])
    B = np.array([[1 / L], [0]])
    C_ = np.array([[1, 0]])   # output = current
    D = np.array([[0]])
    alpha = R / (2 * L)
    wn2 = 1 / (L * C)
    disc = alpha ** 2 - wn2
    if disc >= 0:
        poles = np.array([-alpha + np.sqrt(disc), -alpha - np.sqrt(disc)])
    else:
        poles = np.array([-alpha + 1j * np.sqrt(-disc), -alpha - 1j * np.sqrt(-disc)])
    return GroundTruthNetwork("series_rlc", poles, np.array([]), 1.0, (A, B, C_, D),
                               {"R": R, "L": L, "C": C})


def parallel_rlc(R: float, L: float, C: float) -> GroundTruthNetwork:
    """Parallel RLC one-port, impedance Z(s) driven by current; state x=[v, i_l].
    Closed-form poles: s = -1/(2RC) +/- sqrt((1/(2RC))^2 - 1/(LC))."""
    A = np.array([[-1 / (R * C), -1 / C], [1 / L, 0]])
    B = np.array([[1 / C], [0]])
    C_ = np.array([[1, 0]])   # output = voltage
    D = np.array([[0]])
    alpha = 1 / (2 * R * C)
    wn2 = 1 / (L * C)
    disc = alpha ** 2 - wn2
    if disc >= 0:
        poles = np.array([-alpha + np.sqrt(disc), -alpha - np.sqrt(disc)])
    else:
        poles = np.array([-alpha + 1j * np.sqrt(-disc), -alpha - 1j * np.sqrt(-disc)])
    return GroundTruthNetwork("parallel_rlc", poles, np.array([]), 1.0, (A, B, C_, D),
                               {"R": R, "L": L, "C": C})


def _build_ladder_ss(stage_params: list[dict]) -> tuple:
    """Assemble the ladder state-space from explicit [{'R':.,'L':.,'C':.}, ...]
    stage parameters. Shared by cascaded_ladder() (random generation) and
    anomaly.py's sensitivity analysis (controlled single-component perturbation
    of an otherwise-identical topology)."""
    n_stages = len(stage_params)
    n_states = 2 * n_stages
    A = np.zeros((n_states, n_states))
    B = np.zeros((n_states, 1))
    C_ = np.zeros((1, n_states))
    D = np.zeros((1, 1))
    for k, sp in enumerate(stage_params):
        i_idx, v_idx = 2 * k, 2 * k + 1
        R, L, Cv = sp["R"], sp["L"], sp["C"]
        A[i_idx, i_idx] = -R / L
        A[i_idx, v_idx] = -1 / L
        if k == 0:
            B[i_idx, 0] = 1 / L
        else:
            A[i_idx, v_idx - 2] = 1 / L
        A[v_idx, i_idx] = 1 / Cv
        if k < n_stages - 1:
            A[v_idx, i_idx + 2] = -1 / Cv
    C_[0, -1] = 1.0
    return A, B, C_, D


def cascaded_ladder(n_stages: int, R_range=(0.05, 2.0), L_range=(1e-9, 50e-9),
                     C_range=(1e-9, 100e-9), near_degenerate: bool = False,
                     seed: int | None = None) -> GroundTruthNetwork:
    """N-stage cascaded RLC ladder (models multi-stage PDN: bulk->mid->die decap).
    Each stage: series R-L to next node, shunt C to ground. Poles computed numerically
    from the assembled state-space (no closed form for n_stages > 1)."""
    rng = np.random.default_rng(seed)
    stage_params = []
    Rs, Ls, Cs = [], [], []
    for k in range(n_stages):
        R = rng.uniform(*R_range)
        L = rng.uniform(*L_range)
        Cv = rng.uniform(*C_range)
        if near_degenerate and k > 0:
            prev_wn = 1.0 / np.sqrt(Ls[-1] * Cs[-1])
            Cv = 1.0 / (L * prev_wn ** 2) * rng.uniform(0.97, 1.03)
        Rs.append(R); Ls.append(L); Cs.append(Cv)
        stage_params.append({"R": R, "L": L, "C": Cv})

    A, B, C_, D = _build_ladder_ss(stage_params)
    poles = np.linalg.eigvals(A)
    comps = {"stages": stage_params}
    return GroundTruthNetwork(f"cascaded_ladder_{n_stages}", poles, np.array([]), 1.0,
                               (A, B, C_, D), comps)


def cascaded_ladder_from_components(stage_params: list[dict]) -> GroundTruthNetwork:
    """Rebuild a cascaded ladder from explicit component values -- used to construct
    a controlled perturbation of an existing network (anomaly.py sensitivity
    analysis) rather than a fresh random draw."""
    A, B, C_, D = _build_ladder_ss(stage_params)
    poles = np.linalg.eigvals(A)
    comps = {"stages": stage_params}
    return GroundTruthNetwork(f"cascaded_ladder_{len(stage_params)}", poles, np.array([]),
                               1.0, (A, B, C_, D), comps)


def foster_realization(poles: np.ndarray, residues: np.ndarray) -> dict:
    """Foster-II component values for a set of real poles (parallel R//C branches).
    Demonstrates non-uniqueness: same Y(s) as any Cauer realization of the same poles."""
    branches = []
    for p, r in zip(poles, residues):
        if abs(p.imag) > 1e-9:
            continue  # complex pairs need RLC branch, handled in base.to_spice_netlist
        Cv = r.real
        Rv = -1.0 / (p.real * Cv) if p.real != 0 else np.inf
        branches.append({"R": Rv, "C": Cv})
    return {"form": "Foster-II", "branches": branches}


def cauer_realization(num: np.ndarray, den: np.ndarray) -> dict:
    """Cauer-I continued-fraction ladder realization of the same Z(s)=num/den.
    Same poles/zeros as Foster form -> different topology -> proves §1 non-uniqueness."""
    # Continued fraction expansion via polynomial long division (Cauer I: L-series, C-shunt ladder)
    n = den.copy().astype(float)
    d = num.copy().astype(float)
    elements = []
    for _ in range(len(den) - 1):
        if len(n) <= 1 or np.allclose(n, 0):
            break
        deg_diff = len(n) - len(d)
        if deg_diff < 0:
            n, d = d, n
            continue
        quotient_lead = n[0] / d[0] if d[0] != 0 else 0
        elements.append(quotient_lead)
        # subtract quotient*d shifted appropriately, then swap (standard Euclidean-like step)
        q_poly = np.zeros(deg_diff + 1)
        q_poly[0] = quotient_lead
        sub = np.polymul(q_poly, d)
        sub = np.pad(sub, (len(n) - len(sub), 0)) if len(sub) < len(n) else sub[-len(n):]
        remainder = n - sub
        remainder = np.trim_zeros(remainder, 'f')
        n, d = d, remainder if len(remainder) else np.array([0.0])
    return {"form": "Cauer-I", "continued_fraction_terms": elements}
