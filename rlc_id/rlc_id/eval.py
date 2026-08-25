"""Benchmark harness -- runs identification methods against synthetic ground-truth
RLC networks across excitation types and noise levels, scoring against known poles.
This is the core empirical deliverable: it lets you PROVE which method wins under
which regime rather than assert it (see accompanying technical analysis, Section 4).
"""
from __future__ import annotations
import time as _time
import numpy as np
import pandas as pd

from . import excitation as exc
from .core.utils import match_poles
from .methods.era import ERAIdentifier
from .methods.vector_fitting import VectorFittingIdentifier
from .methods.prony import PronyIdentifier
from .methods.subspace import SubspaceIdentifier
from .methods.sparam import SParameterIdentifier

TIME_DOMAIN_METHODS = {"era": ERAIdentifier, "prony": PronyIdentifier, "subspace": SubspaceIdentifier}
FREQ_DOMAIN_METHODS = {"vfit": VectorFittingIdentifier, "sparam": SParameterIdentifier}
ALL_METHODS = list(TIME_DOMAIN_METHODS) + list(FREQ_DOMAIN_METHODS)

# Which excitation kinds are meaningful for each method, given its actual data model
# (Prony fits free decay only -- no u in its fit(); ERA needs impulse/step markov-
# parameter construction; Subspace's ARX genuinely uses arbitrary u; VF/S-param work
# from an internal frequency sweep, not a time-domain excitation at all).
METHOD_EXCITATION_SUPPORT = {
    "era": ["impulse", "step"],
    "prony": ["impulse"],
    "subspace": ["step", "chirp", "multitone", "prbs", "impulse"],
    "vfit": ["freq_sweep"],
    "sparam": ["freq_sweep"],
}


def _analytic_freq_response(net, w: np.ndarray) -> np.ndarray:
    A, B, C, D = net.ss
    I = np.eye(A.shape[0])
    return np.array([(C @ np.linalg.solve(1j * wk * I - A, B) + D).item() for wk in w])


def _add_freq_noise(H: np.ndarray, snr_db: float | None) -> np.ndarray:
    if snr_db is None:
        return H
    sig_power = np.mean(np.abs(H) ** 2)
    noise_power = sig_power / (10 ** (snr_db / 10))
    noise = (np.random.normal(0, np.sqrt(noise_power / 2), size=H.shape) +
             1j * np.random.normal(0, np.sqrt(noise_power / 2), size=H.shape))
    return H + noise


def _default_duration(net) -> float:
    nz = net.poles.real[net.poles.real != 0]
    slowest = np.min(np.abs(nz)) if len(nz) else np.min(np.abs(net.poles))
    return 15 / slowest


def _adequate_n_points(net, duration: float, requested_n_points: int, max_n_points: int = 4000) -> int:
    """A fixed n_points can badly under-sample the fastest pole once duration is
    set by the slowest pole (wide pole-magnitude spread -> dt*|fastest pole| >> 1,
    aliasing the fast dynamics). Scales n_points up so dt*|fastest_pole| <= 0.1,
    matching the excitation/sampling-coverage lesson from the accompanying analysis.
    Capped at max_n_points: for very wide pole spreads this heuristic alone cannot
    fully resolve both timescales at equal per-sample weighting (a step's late,
    near-steady-state samples dominate the least-squares fit) -- the harness should
    surface that regime honestly rather than mask it with unbounded sample growth."""
    fastest = np.max(np.abs(net.poles))
    dt_required = 0.1 / fastest
    n_required = int(np.ceil(duration / dt_required)) + 1
    return min(max(requested_n_points, n_required), max_n_points)


def run_single(method_name: str, net, order: int, excitation_kind: str = "impulse",
               n_points: int = 2000, snr_db: float | None = None,
               method_kwargs: dict | None = None, n_freq: int = 300,
               freq_range: tuple | None = None) -> dict:
    """Run one (method, excitation, noise) combination, scored against net's known poles."""
    method_kwargs = dict(method_kwargs or {})
    result = {"method": method_name, "excitation": excitation_kind, "snr_db": snr_db,
              "true_order": len(net.poles)}
    t0 = _time.perf_counter()
    try:
        if method_name in TIME_DOMAIN_METHODS:
            duration = method_kwargs.pop("duration", None) or _default_duration(net)
            n_points = _adequate_n_points(net, duration, n_points)
            if method_name == "era":
                method_kwargs.setdefault("input_type", "impulse" if excitation_kind == "impulse" else "step")
            exc_kwargs = {"seed": 0} if excitation_kind in ("multitone", "prbs") else {}
            t, u = exc.generate(excitation_kind, duration, n_points=n_points, **exc_kwargs)
            y = net.simulate(t, u, snr_db=snr_db)
            ident = TIME_DOMAIN_METHODS[method_name](**method_kwargs)
            ident.fit(t, u, y, order=order)
        else:
            if freq_range is None:
                pole_mags = np.abs(net.poles)
                freq_range = (pole_mags.min() / 10, pole_mags.max() * 10)
            w = np.logspace(np.log10(freq_range[0]), np.log10(freq_range[1]), n_freq)
            H = _add_freq_noise(_analytic_freq_response(net, w), snr_db)
            if method_name == "sparam":
                z0 = method_kwargs.pop("z0", 50.0)
                S = (H - z0) / (H + z0)
                ident = SParameterIdentifier(z0=z0, param_type="Z", **method_kwargs)
                ident.fit(w, None, S, order=order)
            else:
                ident = VectorFittingIdentifier(**method_kwargs)
                ident.fit(w, None, H, order=order)

        runtime = _time.perf_counter() - t0
        _, pole_err = match_poles(net.poles, ident.poles())
        result.update({
            "pole_err_rel": pole_err / np.mean(np.abs(net.poles)),
            "passive": ident.is_passive(),
            "runtime_s": runtime,
            "order_selected": getattr(ident, "_order_selected", None),
            "success": True,
            "error": None,
        })
    except Exception as e:
        result.update({
            "pole_err_rel": np.nan, "passive": None,
            "runtime_s": _time.perf_counter() - t0,
            "order_selected": None, "success": False, "error": str(e),
        })
    return result


def run_benchmark(net, order: int | None = None, methods: list | None = None,
                   excitations: list | None = None, noise_db_list: list | None = None,
                   method_kwargs: dict | None = None, n_points: int = 2000,
                   n_freq: int = 300) -> pd.DataFrame:
    """Sweep methods x excitations x noise levels for one ground-truth network.
    Combinations a method doesn't support (see METHOD_EXCITATION_SUPPORT) are
    skipped rather than silently mis-run."""
    methods = methods or ALL_METHODS
    excitations = excitations or ["impulse"]
    noise_db_list = noise_db_list if noise_db_list is not None else [None]
    order = order or len(net.poles)
    method_kwargs = method_kwargs or {}

    rows = []
    for method_name in methods:
        supported = METHOD_EXCITATION_SUPPORT.get(method_name, [])
        exc_list = ["freq_sweep"] if supported == ["freq_sweep"] else \
            [e for e in excitations if e in supported]
        for exc_kind in exc_list:
            for snr in noise_db_list:
                row = run_single(method_name, net, order, excitation_kind=exc_kind,
                                  n_points=n_points, snr_db=snr,
                                  method_kwargs=method_kwargs.get(method_name, {}), n_freq=n_freq)
                rows.append(row)
    return pd.DataFrame(rows)
