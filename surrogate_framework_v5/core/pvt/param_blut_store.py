"""
core/pvt/param_blut_store.py — fitted parameter vectors persisted as BLUT v8.

Each stored vector is one BLUT run keyed by the v8 (run_id, corner_id)
pair — corner_id carries the PVT corner natively (no run_id-encoding
convention needed after the v8 re-vendor):

    run_id = 'baseline'            -> StateParamSet.baseline
    run_id = 'state:<state_name>'  -> that state's EFFECTIVE params
                                      (baseline + delta), so any BLUT
                                      tool can read absolute values;
                                      deltas are reconstructed on load.

Signals are the parameter names, each a 1-sample float64 waveform at
t=[0]; run meta records kind=param_vector,corner=<corner_id> so
parse_meta_string-based tooling can identify store files.
"""
from __future__ import annotations

import os
from typing import Dict, List, Optional

import numpy as np

from digitwin import blut_format as bf
from digitwin.blut_reader_core import open_blut, decode
from core.fitting.state_delta_fitter import StateParamSet
from .provider import ParamProvider, parse_corner, format_corner


def save_param_store(path: str, fits: Dict[str, StateParamSet]) -> None:
    """Write {corner_id: StateParamSet} to a BLUT v8 container. The file
    is rewritten whole (parameter stores are tiny)."""
    runs = []
    for corner, sps in fits.items():
        runs.append(('baseline', corner, sps.baseline))
        for state, delta in sps.deltas.items():
            eff = sps.params_for(state)
            runs.append((f'state:{state}', corner, eff))

    with open(path, 'wb') as f:
        bf.write_file_header(f, n_runs=len(runs))
        for run_number, (run_id, corner, params) in enumerate(runs):
            run_off = f.tell()
            bf.write_run_header(
                f, run_number, run_id,
                f'kind=param_vector,corner={corner}',
                np.array([0.0]), corner_id=corner)
            n_sig = 0
            for name in sorted(params.keys()):
                bf.write_signal_block(
                    f, name, np.array([0], dtype=np.int64),
                    np.array([float(params[name])]),
                    bf.ENC_FLOAT64, 0.0, 1.0, compress=False)
                n_sig += 1
            bf.patch_run_n_signals(f, run_off, n_sig)
        bf.patch_file_header_counts(f, len(runs))


def load_param_store(path: str) -> Dict[str, StateParamSet]:
    """Read a store written by save_param_store back into
    {corner_id: StateParamSet} (deltas reconstructed as effective −
    baseline, zero-valued deltas dropped)."""
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    blut = open_blut(path)
    per_corner: Dict[str, dict] = {}
    for run_id, corner_map in blut.runs.items():
        for corner_id, run in corner_map.items():
            vec = {name: float(decode(path, run, name)[0])
                   for name in run.signals.keys()}
            slot = per_corner.setdefault(corner_id,
                                         {'baseline': None, 'states': {}})
            if run_id == 'baseline':
                slot['baseline'] = vec
            elif run_id.startswith('state:'):
                slot['states'][run_id[len('state:'):]] = vec

    out: Dict[str, StateParamSet] = {}
    for corner, slot in per_corner.items():
        base = slot['baseline']
        if base is None:
            raise ValueError(
                f"{path}: corner {corner!r} has state runs but no "
                f"'baseline' run — not a valid param store")
        deltas = {}
        for state, eff in slot['states'].items():
            d = {k: eff[k] - base.get(k, 0.0) for k in eff
                 if abs(eff[k] - base.get(k, 0.0)) > 0}
            deltas[state] = d
        out[corner] = StateParamSet(baseline=base, deltas=deltas)
    return out


class BlutStoreParamProvider(ParamProvider):
    """ParamProvider over a param-store BLUT: exact corner hit returns the
    stored vector; anything else returns the nearest stored corner in
    normalized (V, T) with process mismatch penalized (a store is a set
    of measured points, not an interpolant — use LutParamProvider when
    interpolation is wanted)."""

    def __init__(self, path: str):
        self.path = path
        self._fits = load_param_store(path)
        self._meta = {c: parse_corner(c) for c in self._fits}

    def corners(self) -> List[str]:
        return sorted(self._fits.keys())

    def _nearest_corner(self, process: str, vdd: float, temp: float) -> str:
        vs = [m[1] for m in self._meta.values()]
        ts = [m[2] for m in self._meta.values()]
        sv = max(max(vs) - min(vs), 1e-9)
        st = max(max(ts) - min(ts), 1e-9)

        def dist(c):
            p, v, t = self._meta[c]
            d = ((v - vdd) / sv) ** 2 + ((t - temp) / st) ** 2
            if p != process:
                d += 10.0
            return d
        return min(self._fits.keys(), key=dist)

    def get_params(self, process: str, vdd: float, temp: float,
                   state: Optional[str] = None) -> Dict[str, float]:
        if not self._fits:
            raise RuntimeError(f"{self.path}: empty param store")
        exact = format_corner(process, vdd, temp)
        corner = exact if exact in self._fits else \
            self._nearest_corner(process, vdd, temp)
        sps = self._fits[corner]
        return sps.params_for(state) if state is not None \
            else dict(sps.baseline)

    def state_param_set(self, corner: str) -> StateParamSet:
        return self._fits[corner]
