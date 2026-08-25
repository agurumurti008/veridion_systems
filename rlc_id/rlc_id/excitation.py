"""Excitation waveform generators for RLC identification. Each returns (t, u).
See the accompanying technical analysis, Section 3, for the persistence-of-excitation
tradeoffs between these (step/ramp are broadband-weak; chirp/PRBS/multitone are the
practical choices for full-bandwidth pole/zero characterization).
"""
from __future__ import annotations
import numpy as np


def step(duration: float, n_points: int = 2000, amplitude: float = 1.0, t_start: float = 0.0):
    t = np.linspace(0, duration, n_points)
    u = np.where(t >= t_start, amplitude, 0.0)
    return t, u


def ramp(duration: float, n_points: int = 2000, slope: float = 1.0, t_start: float = 0.0):
    t = np.linspace(0, duration, n_points)
    u = np.where(t >= t_start, slope * (t - t_start), 0.0)
    return t, u


def impulse(duration: float, n_points: int = 2000, area: float = 1.0):
    """Realistic finite-width pulse (NOT a literal Dirac delta): single sample of
    height area/dt at t=0, area-normalized so downstream ERA/Prony markov-parameter
    scaling is correct (see methods/era.py docstring on the impulse-input convention).
    """
    t = np.linspace(0, duration, n_points)
    dt = t[1] - t[0]
    u = np.zeros(n_points)
    u[0] = area / dt
    return t, u


def chirp(duration: float, n_points: int = 2000, f0: float = 1e3, f1: float = 1e9,
          amplitude: float = 1.0, method: str = "logarithmic"):
    """Swept-sine excitation. method='logarithmic' matches log-spaced RLC/PDN poles
    better than a linear sweep for a given duration (see Section 3 of the analysis)."""
    from scipy.signal import chirp as _scipy_chirp
    t = np.linspace(0, duration, n_points)
    u = amplitude * _scipy_chirp(t, f0=f0, f1=f1, t1=duration, method=method)
    return t, u


def multitone(duration: float, n_points: int = 2000, frequencies: np.ndarray | None = None,
              amplitude: float = 1.0, n_tones: int = 20, f_min: float = 1e3,
              f_max: float = 1e9, random_phase: bool = True, seed: int | None = None):
    """Sum of sinusoids at chosen (default log-spaced) frequencies -- exact energy
    placement per frequency, best SNR-per-frequency of any excitation type but
    requires knowing/choosing the frequencies of interest up front."""
    t = np.linspace(0, duration, n_points)
    if frequencies is None:
        frequencies = np.logspace(np.log10(f_min), np.log10(f_max), n_tones)
    rng = np.random.default_rng(seed)
    phases = rng.uniform(0, 2 * np.pi, size=len(frequencies)) if random_phase else np.zeros(len(frequencies))
    u = np.zeros(n_points)
    for f, phi in zip(frequencies, phases):
        u += np.sin(2 * np.pi * f * t + phi)
    u *= amplitude / max(len(frequencies), 1)
    return t, u


def prbs(duration: float, n_points: int = 2000, amplitude: float = 1.0,
         bit_period: float | None = None, seed: int | None = None):
    """Pseudo-random binary sequence: flat (white) spectrum up to ~1/(2*bit_period).
    Standard bench-characterization excitation for broadband SI/PDN measurement."""
    t = np.linspace(0, duration, n_points)
    dt = t[1] - t[0]
    if bit_period is None:
        bit_period = 20 * dt  # default: 20 samples per bit
    n_bits = int(np.ceil(duration / bit_period)) + 1
    rng = np.random.default_rng(seed)
    bits = rng.choice([-1.0, 1.0], size=n_bits) * amplitude
    bit_idx = np.minimum((t / bit_period).astype(int), n_bits - 1)
    u = bits[bit_idx]
    return t, u


GENERATORS = {
    "step": step,
    "ramp": ramp,
    "impulse": impulse,
    "chirp": chirp,
    "multitone": multitone,
    "prbs": prbs,
}


def generate(kind: str, duration: float, **kwargs):
    if kind not in GENERATORS:
        raise ValueError(f"unknown excitation kind '{kind}', choose from {list(GENERATORS)}")
    return GENERATORS[kind](duration, **kwargs)
