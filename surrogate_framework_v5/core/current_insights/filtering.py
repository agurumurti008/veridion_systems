"""
core/current_insights/filtering.py — 3.6 mandatory current preprocessing.

Contract: every current-derived metric runs on FILTERED signals; raw µA–nA
traces are never thresholded directly. Per-signal choices (noise floor,
median kernel, Savitzky–Golay window/order, decimation) are auto-derived
from sample rate + estimated floor and logged in FilterLog for the report.
Work in log-magnitude only where the signal is sign-stable; never threshold
below the estimated floor (use `above_floor`).
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict, Optional

import numpy as np

try:
    from scipy.signal import medfilt, savgol_filter
    _SCIPY = True
except ImportError:                       # pragma: no cover
    _SCIPY = False


@dataclass
class FilterLog:
    signal: str
    n: int
    dt: float
    noise_floor: float          # A (robust, quiet-window MAD)
    median_kernel: int
    savgol_window: int
    savgol_polyorder: int
    decimation: int
    sign_stable: bool
    method: str

    def as_row(self) -> dict:
        return asdict(self)


@dataclass
class FilteredSignal:
    name: str
    t: np.ndarray
    raw: np.ndarray
    filtered: np.ndarray        # median prefilter -> Savitzky–Golay
    derivative: np.ndarray      # d(filtered)/dt (SG-derivative where available)
    noise_floor: float
    log: FilterLog

    def above_floor(self, k: float = 3.0) -> np.ndarray:
        """Boolean mask where |filtered| exceeds k× the noise floor — the
        only sanctioned way to threshold a current trace."""
        return np.abs(self.filtered) > k * self.noise_floor


def estimate_noise_floor(x: np.ndarray, n_windows: int = 12) -> float:
    """Robust noise floor = min over quiet windows of MAD(x)·1.4826. Falls
    back to the global diff-MAD estimator for very short traces. NaNs
    ignored; returns a small positive floor even for constant signals so
    downstream k·floor thresholds never collapse to zero."""
    x = np.asarray(x, dtype=float)
    valid = x[~np.isnan(x)]
    if valid.size < 4:
        return max(float(np.std(valid)) if valid.size else 0.0, 1e-15)
    win = max(4, valid.size // n_windows)
    mads = []
    for s in range(0, valid.size - win + 1, win):
        seg = valid[s:s + win]
        mads.append(np.median(np.abs(seg - np.median(seg))))
    floor = 1.4826 * float(np.min(mads)) if mads else 0.0
    if floor <= 0:
        # constant/flat quiet window — use the diff-based estimator
        d = np.diff(valid)
        floor = 1.4826 * float(np.median(np.abs(d - np.median(d)))) / np.sqrt(2)
    return max(floor, 1e-15)


def _odd(n: int) -> int:
    return n if n % 2 == 1 else n + 1


def filter_current(name: str, t: np.ndarray, x: np.ndarray,
                   median_kernel: Optional[int] = None,
                   savgol_window: Optional[int] = None,
                   savgol_polyorder: int = 2,
                   decimation: int = 1) -> FilteredSignal:
    """Filter one current trace. Auto-parameterizes the SG window from n
    (≈ n/20, odd, ≥5) and uses a 3-sample median prefilter for single-sample
    spikes unless overridden."""
    t = np.asarray(t, dtype=float)
    x = np.asarray(x, dtype=float)
    n = len(x)
    dt = float(np.median(np.diff(t))) if n > 1 else 0.0
    # NaN-fill (missing-in-run alignment) by nearest valid so filters run
    xf = x.copy()
    if np.isnan(xf).any():
        idx = np.arange(n)
        good = ~np.isnan(xf)
        if good.any():
            xf = np.interp(idx, idx[good], xf[good])
        else:
            xf = np.zeros(n)

    floor = estimate_noise_floor(xf)
    sign_stable = bool(np.all(xf >= -floor) or np.all(xf <= floor))

    mk = median_kernel if median_kernel is not None else (3 if n >= 3 else 1)
    mk = _odd(min(mk, n if n % 2 == 1 else n - 1)) if n >= 3 else 1

    if savgol_window is not None:
        sw = savgol_window
    else:
        sw = max(5, _odd(n // 20))
    sw = min(sw, n if n % 2 == 1 else n - 1)
    sw = max(sw, savgol_polyorder + 1 + (1 - (savgol_polyorder + 1) % 2))
    sw = _odd(sw)

    if _SCIPY and n >= 5 and mk >= 3:
        med = medfilt(xf, kernel_size=mk)
    else:
        med = xf
    if _SCIPY and n > sw > savgol_polyorder:
        filt = savgol_filter(med, sw, savgol_polyorder)
        deriv = savgol_filter(med, sw, savgol_polyorder, deriv=1,
                              delta=max(dt, 1e-18))
        method = 'medfilt+savgol'
    else:
        filt = med
        deriv = np.gradient(med, t) if n > 1 else np.zeros(n)
        method = 'medfilt+gradient' if not _SCIPY else 'gradient'

    if decimation > 1:
        t = t[::decimation]
        raw_out = x[::decimation]
        filt = filt[::decimation]
        deriv = deriv[::decimation]
    else:
        raw_out = x

    log = FilterLog(signal=name, n=n, dt=dt, noise_floor=floor,
                    median_kernel=mk, savgol_window=sw,
                    savgol_polyorder=savgol_polyorder, decimation=decimation,
                    sign_stable=sign_stable, method=method)
    return FilteredSignal(name=name, t=t, raw=raw_out, filtered=filt,
                          derivative=deriv, noise_floor=floor, log=log)


def filter_signals(t: np.ndarray, signals: Dict[str, np.ndarray],
                   **kw) -> Dict[str, FilteredSignal]:
    """Filter a dict of current traces (e.g. SignalCapture.current_signals or
    a run dict's current columns keyed by name)."""
    return {name: filter_current(name, t, x, **kw)
            for name, x in signals.items()}
