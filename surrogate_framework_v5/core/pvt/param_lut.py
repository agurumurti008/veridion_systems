"""
core/pvt/param_lut.py — (P, V, T) parameter look-up table provider.

Stores fitted StateParamSets at discrete corners on a (process, vdd,
temp) grid. get_params() multilinearly interpolates over the (V, T)
plane within the requested process; a process with no stored corners —
or a (V, T) point outside the stored hull when extrapolation is off —
falls back to the nearest stored corner (Euclidean in normalized (V, T),
process mismatch penalized), which is also the documented behavior for
sparse grids.

State deltas do NOT interpolate: deltas are sparse, per-state fitted
quantities, so the deltas of the nearest stored corner apply on top of
the interpolated baseline (documented; matches how mode deltas are
fitted per corner).
"""
from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np

from core.fitting.state_delta_fitter import StateParamSet
from .provider import ParamProvider, parse_corner


class LutParamProvider(ParamProvider):
    def __init__(self):
        self._entries: Dict[str, dict] = {}  # corner -> {p, v, t, sps}

    def add_corner(self, corner: str, param_set: StateParamSet) -> None:
        p, v, t = parse_corner(corner)
        self._entries[corner] = {'p': p, 'v': v, 't': t, 'sps': param_set}

    def corners(self) -> List[str]:
        return sorted(self._entries.keys())

    # ─── Internals ──────────────────────────────────────────────────────────

    def _norm_scales(self):
        vs = [e['v'] for e in self._entries.values()]
        ts = [e['t'] for e in self._entries.values()]
        return (max(max(vs) - min(vs), 1e-9), max(max(ts) - min(ts), 1e-9))

    def _nearest(self, process: str, vdd: float, temp: float) -> dict:
        sv, st = self._norm_scales()

        def dist(e):
            d = ((e['v'] - vdd) / sv) ** 2 + ((e['t'] - temp) / st) ** 2
            if e['p'] != process:
                d += 10.0  # strong process-mismatch penalty
            return d
        return min(self._entries.values(), key=dist)

    def _interp_baseline(self, process: str, vdd: float,
                         temp: float) -> Optional[Dict[str, float]]:
        """Multilinear interpolation over the (V, T) plane of the given
        process. Needs the point inside the stored V/T bounding box and at
        least two distinct corners; returns None when interpolation isn't
        possible (caller falls back to nearest-corner)."""
        ents = [e for e in self._entries.values() if e['p'] == process]
        if len(ents) < 2:
            return None
        vs = sorted({e['v'] for e in ents})
        ts = sorted({e['t'] for e in ents})
        if not (vs[0] <= vdd <= vs[-1] and ts[0] <= temp <= ts[-1]):
            return None

        def bracket(vals, x):
            lo = max([v for v in vals if v <= x], default=vals[0])
            hi = min([v for v in vals if v >= x], default=vals[-1])
            return lo, hi

        v0, v1 = bracket(vs, vdd)
        t0, t1 = bracket(ts, temp)

        def entry_at(v, t):
            for e in ents:
                if abs(e['v'] - v) < 1e-12 and abs(e['t'] - t) < 1e-12:
                    return e
            return None

        corners = [entry_at(v0, t0), entry_at(v0, t1),
                   entry_at(v1, t0), entry_at(v1, t1)]
        if any(c is None for c in corners):
            return None  # sparse grid cell — nearest-corner fallback

        wv = 0.0 if v1 == v0 else (vdd - v0) / (v1 - v0)
        wt = 0.0 if t1 == t0 else (temp - t0) / (t1 - t0)
        weights = [(1 - wv) * (1 - wt), (1 - wv) * wt,
                   wv * (1 - wt), wv * wt]
        names = set()
        for c in corners:
            names |= set(c['sps'].baseline.keys())
        out = {}
        for n in names:
            out[n] = float(sum(
                w * c['sps'].baseline.get(n, 0.0)
                for w, c in zip(weights, corners)))
        return out

    # ─── ParamProvider ──────────────────────────────────────────────────────

    def get_params(self, process: str, vdd: float, temp: float,
                   state: Optional[str] = None) -> Dict[str, float]:
        if not self._entries:
            raise RuntimeError("LutParamProvider has no stored corners")
        baseline = self._interp_baseline(process, vdd, temp)
        nearest = self._nearest(process, vdd, temp)
        if baseline is None:
            baseline = dict(nearest['sps'].baseline)
        params = dict(baseline)
        if state is not None:
            for k, dv in nearest['sps'].deltas.get(state, {}).items():
                params[k] = params.get(k, 0.0) + dv
        return params

    def state_param_set(self, corner: str) -> StateParamSet:
        return self._entries[corner]['sps']
