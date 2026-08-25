"""
core/numpy_mlp.py — tiny 2-layer tanh MLP with analytic gradients + Adam.

Why this exists (build discovery, recorded in CHANGELOG): torch_shim has
NO autograd — _Tensor.backward() is a no-op and the shim's Adam only
consumes externally-set .grad, so any code that "trains" through the
shim with loss.backward() silently performs zero updates (the repo's
Phase-2 fallback resorts to random perturbation). The A+B NN provider
and the optional NODE-style residual net need genuine convergence with
or without real PyTorch, so the shim path trains THIS network instead:
closed-form gradients, deterministic, dependency-free.
"""
from __future__ import annotations

from typing import Optional

import numpy as np


class NumpyMLP:
    """y = W2·tanh(W1·x + b1) + b2 trained with full-batch Adam on MSE."""

    def __init__(self, n_in: int, n_hidden: int, n_out: int, seed: int = 42):
        rng = np.random.RandomState(seed)
        s1 = np.sqrt(2.0 / max(n_in, 1))
        s2 = np.sqrt(2.0 / max(n_hidden, 1))
        self.W1 = rng.randn(n_in, n_hidden) * s1
        self.b1 = np.zeros(n_hidden)
        self.W2 = rng.randn(n_hidden, n_out) * s2
        self.b2 = np.zeros(n_out)

    def forward(self, X: np.ndarray) -> np.ndarray:
        return np.tanh(X @ self.W1 + self.b1) @ self.W2 + self.b2

    __call__ = forward

    def fit(self, X: np.ndarray, Y: np.ndarray, epochs: int = 2000,
            lr: float = 1e-2, weight_decay: float = 0.0,
            verbose: bool = False) -> float:
        X = np.asarray(X, dtype=float)
        Y = np.asarray(Y, dtype=float)
        n = len(X)
        params = [self.W1, self.b1, self.W2, self.b2]
        m = [np.zeros_like(p) for p in params]
        v = [np.zeros_like(p) for p in params]
        b1m, b2m, eps = 0.9, 0.999, 1e-8
        loss = float('nan')
        for t in range(1, epochs + 1):
            H = np.tanh(X @ self.W1 + self.b1)
            P = H @ self.W2 + self.b2
            E = P - Y
            loss = float(np.mean(E ** 2))
            gP = 2.0 * E / E.size
            gW2 = H.T @ gP + weight_decay * self.W2
            gb2 = gP.sum(axis=0)
            gH = gP @ self.W2.T
            gZ = gH * (1.0 - H ** 2)
            gW1 = X.T @ gZ + weight_decay * self.W1
            gb1 = gZ.sum(axis=0)
            grads = [gW1, gb1, gW2, gb2]
            for i, (p, g) in enumerate(zip(params, grads)):
                m[i] = b1m * m[i] + (1 - b1m) * g
                v[i] = b2m * v[i] + (1 - b2m) * g ** 2
                p -= lr * (m[i] / (1 - b1m ** t)) / (
                    np.sqrt(v[i] / (1 - b2m ** t)) + eps)
            if verbose and t % max(1, epochs // 5) == 0:
                print(f"  [NumpyMLP] epoch {t}: mse={loss:.3e}  (n={n})")
        return loss


def torch_is_real() -> bool:
    """True when the imported `torch` is real PyTorch (has autograd), False
    when it's the repo's torch_shim (backward is a no-op)."""
    try:
        import torch
    except ImportError:
        return False
    t = torch.tensor([0.0])
    # the shim's _Tensor carries the raw numpy array in ._d
    return not hasattr(t, '_d')
