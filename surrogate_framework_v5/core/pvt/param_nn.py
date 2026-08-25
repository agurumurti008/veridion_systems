"""
core/pvt/param_nn.py — NN parameter regression provider.

Small MLP mapping corner features [P one-hot ..., vdd_norm, temp_norm]
-> normalized parameter vector, trained on the fitted per-corner
vectors. Trains with real PyTorch when installed; without it, training
runs on core.numpy_mlp.NumpyMLP with analytic gradients — the shim's
backward() is a no-op (build discovery), so "training through the shim"
would silently do nothing.

State deltas do not go through the NN (they are sparse per-state fitted
quantities): the deltas of the nearest TRAINING corner apply on top of
the NN baseline, mirroring LutParamProvider's documented behavior.

Deployment note: Verilog-A cannot run NN inference — ab_codegen exports
LUT tables ($table_model form) for silicon-facing deployment; this
provider serves Python-side evaluation and the provider comparison.
"""
from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np

from core.numpy_mlp import NumpyMLP, torch_is_real
from core.fitting.state_delta_fitter import StateParamSet
from .provider import ParamProvider, parse_corner


class NNParamProvider(ParamProvider):
    def __init__(self, hidden: int = 24, epochs: int = 2000, lr: float = 1e-2,
                 seed: int = 42):
        self.hidden = hidden
        self.epochs = epochs
        self.lr = lr
        self.seed = seed
        self._corners: List[str] = []
        self._sets: Dict[str, StateParamSet] = {}
        self._proc_list: List[str] = []
        self._param_names: List[str] = []
        self._net = None
        self._x_stats = None
        self._y_stats = None
        self.train_mse: float = float('nan')

    # ─── Training ───────────────────────────────────────────────────────────

    def _features(self, process: str, vdd: float, temp: float) -> np.ndarray:
        onehot = [1.0 if process == p else 0.0 for p in self._proc_list]
        v_mu, v_sd, t_mu, t_sd = self._x_stats
        return np.array(onehot + [(vdd - v_mu) / v_sd, (temp - t_mu) / t_sd],
                        dtype=np.float32)

    def fit(self, fits: Dict[str, StateParamSet]) -> "NNParamProvider":
        np.random.seed(self.seed)
        self._sets = dict(fits)
        self._corners = sorted(fits.keys())
        meta = {c: parse_corner(c) for c in self._corners}
        self._proc_list = sorted({m[0] for m in meta.values()})
        self._param_names = sorted(fits[self._corners[0]].baseline.keys())

        vs = np.array([meta[c][1] for c in self._corners])
        ts = np.array([meta[c][2] for c in self._corners])
        self._x_stats = (float(vs.mean()), float(vs.std() + 1e-9),
                         float(ts.mean()), float(ts.std() + 1e-9))

        # Targets normalized per-param: log10 for positive-definite spread
        Y_raw = np.array([[fits[c].baseline[n] for n in self._param_names]
                          for c in self._corners], dtype=np.float64)
        y_log = Y_raw > 0
        y_pos = np.all(y_log, axis=0)
        Y = np.where(y_pos[None, :], np.log10(np.maximum(Y_raw, 1e-30)), Y_raw)
        y_mu = Y.mean(axis=0)
        y_sd = Y.std(axis=0) + 1e-9
        self._y_stats = (y_pos, y_mu, y_sd)
        Yn = (Y - y_mu) / y_sd

        X = np.stack([self._features(*meta[c]) for c in self._corners])
        n_in = X.shape[1]
        n_out = len(self._param_names)

        if torch_is_real():
            import torch
            import torch.nn as nn
            torch.manual_seed(self.seed)
            net = nn.Sequential(nn.Linear(n_in, self.hidden), nn.Tanh(),
                                nn.Linear(self.hidden, n_out))
            opt = torch.optim.Adam(net.parameters(), lr=self.lr)
            Xt = torch.tensor(X.astype(np.float32))
            Yt = torch.tensor(Yn.astype(np.float32))
            loss = None
            for _ in range(self.epochs):
                opt.zero_grad()
                loss = ((net(Xt) - Yt) ** 2).mean()
                loss.backward()
                opt.step()
            self.train_mse = float(loss.detach().cpu().numpy())
            self._net = ('torch', net)
        else:
            net = NumpyMLP(n_in, self.hidden, n_out, seed=self.seed)
            self.train_mse = net.fit(X.astype(float), Yn, epochs=self.epochs,
                                     lr=self.lr)
            self._net = ('numpy', net)
        return self

    # ─── ParamProvider ──────────────────────────────────────────────────────

    def corners(self) -> List[str]:
        return list(self._corners)

    def _nearest_training_corner(self, process, vdd, temp) -> str:
        meta = {c: parse_corner(c) for c in self._corners}
        vs = [m[1] for m in meta.values()]
        ts = [m[2] for m in meta.values()]
        sv = max(max(vs) - min(vs), 1e-9)
        st = max(max(ts) - min(ts), 1e-9)

        def dist(c):
            p, v, t = meta[c]
            d = ((v - vdd) / sv) ** 2 + ((t - temp) / st) ** 2
            if p != process:
                d += 10.0
            return d
        return min(self._corners, key=dist)

    def get_params(self, process: str, vdd: float, temp: float,
                   state: Optional[str] = None) -> Dict[str, float]:
        if self._net is None:
            raise RuntimeError("NNParamProvider.fit() has not been called")
        x = self._features(process, vdd, temp)
        kind, net = self._net
        if kind == 'torch':
            import torch
            with torch.no_grad():
                yn = net(torch.tensor(x[None, :].astype(np.float32))
                         ).detach().cpu().numpy().reshape(-1)
        else:
            yn = net(x[None, :].astype(float)).reshape(-1)
        y_pos, y_mu, y_sd = self._y_stats
        y = yn * y_sd + y_mu
        vals = np.where(y_pos, 10.0 ** y, y)
        params = {n: float(v) for n, v in zip(self._param_names, vals)}
        if state is not None:
            near = self._nearest_training_corner(process, vdd, temp)
            for k, dv in self._sets[near].deltas.get(state, {}).items():
                params[k] = params.get(k, 0.0) + dv
        return params
