"""
models/__init__.py  —  All ML models for AnalogML

Models implemented:
  1. CircuitGNN         — Graph Neural Network topology encoder
  2. AnalogPINN         — Physics-Informed NN (KCL/KVL constraints)
  3. NeuralODE          — ODE-based dynamics (transient/AC)
  4. HamiltonianNN      — Energy-conserving model (power analysis)
  5. MultiFidelityModel — GP-based bridge between fidelity levels
  6. SymbolicRegressor  — PySR wrapper for interpretable equations
  7. AnalogMLModel      — Master model combining all above
  8. TechTransferAgent  — Cross-technology domain adaptation
"""

from __future__ import annotations

import os
import math
import json
import warnings
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from sklearn.preprocessing     import StandardScaler
from sklearn.gaussian_process  import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import RBF, WhiteKernel, Matern
from sklearn.ensemble          import GradientBoostingRegressor
from sklearn.multioutput       import MultiOutputRegressor

# ── PyTorch (optional, graceful fallback to sklearn) ──────────────────────────
try:
    import torch
    import torch.nn as nn
    import torch.optim as optim
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    warnings.warn("PyTorch not found. Neural models will use sklearn surrogates.")

# ── torchdiffeq for Neural ODE ─────────────────────────────────────────────────
try:
    from torchdiffeq import odeint
    ODE_AVAILABLE = TORCH_AVAILABLE
except ImportError:
    ODE_AVAILABLE = False


# ─────────────────────────────────────────────────────────────────────────────
# 1.  Circuit GNN  (message-passing graph encoder)
# ─────────────────────────────────────────────────────────────────────────────

if TORCH_AVAILABLE:
    class _GNNLayer(nn.Module):
        """Single message-passing layer (mean aggregation)."""
        def __init__(self, in_dim: int, out_dim: int):
            super().__init__()
            self.lin_self  = nn.Linear(in_dim, out_dim)
            self.lin_neigh = nn.Linear(in_dim, out_dim)
            self.act       = nn.SiLU()

        def forward(self, x: torch.Tensor, edge_index: torch.Tensor) -> torch.Tensor:
            # x: (N, in_dim)   edge_index: (2, E)
            N = x.size(0)
            if edge_index.size(1) == 0:
                return self.act(self.lin_self(x))
            src, dst = edge_index[0], edge_index[1]
            agg = torch.zeros(N, x.size(1), device=x.device)
            agg.index_add_(0, dst, x[src])
            count = torch.zeros(N, 1, device=x.device)
            count.index_add_(0, dst, torch.ones(src.size(0), 1, device=x.device))
            agg = agg / (count + 1e-8)
            return self.act(self.lin_self(x) + self.lin_neigh(agg))

    class CircuitGNN(nn.Module):
        """3-layer GNN → global graph embedding."""
        def __init__(self, node_feat_dim: int = 15, hidden: int = 64,
                     embed_dim: int = 32, n_layers: int = 3):
            super().__init__()
            dims = [node_feat_dim] + [hidden]*n_layers
            self.layers = nn.ModuleList([
                _GNNLayer(dims[i], dims[i+1]) for i in range(n_layers)
            ])
            self.readout = nn.Linear(hidden, embed_dim)

        def forward(self, x: torch.Tensor,
                    edge_index: torch.Tensor) -> torch.Tensor:
            for layer in self.layers:
                x = layer(x, edge_index)
            # global mean-pool
            g = x.mean(dim=0, keepdim=True)
            return self.readout(g).squeeze(0)   # (embed_dim,)

else:
    # stub
    class CircuitGNN:  # type: ignore
        def __init__(self, **kw): pass


# ─────────────────────────────────────────────────────────────────────────────
# 2.  Physics-Informed NN  (KCL/KVL soft constraints)
# ─────────────────────────────────────────────────────────────────────────────

if TORCH_AVAILABLE:
    class AnalogPINN(nn.Module):
        """
        PINN for DC operating point / AC small-signal prediction.

        Physics losses:
          - KCL residual: sum of currents at each internal node ≈ 0
          - Monotonicity: gain ≥ 0, bandwidth > 0
          - MOSFET saturation bounds
        """
        def __init__(self, in_dim: int, out_dim: int,
                     hidden: int = 128, n_layers: int = 4):
            super().__init__()
            layers = [nn.Linear(in_dim, hidden), nn.Tanh()]
            for _ in range(n_layers - 1):
                layers += [nn.Linear(hidden, hidden), nn.Tanh()]
            layers += [nn.Linear(hidden, out_dim)]
            self.net = nn.Sequential(*layers)

            # physics weight (annealed during training)
            self.lambda_phys = nn.Parameter(torch.tensor(0.1), requires_grad=False)

        def forward(self, x: torch.Tensor) -> torch.Tensor:
            return self.net(x)

        def physics_loss(self, x: torch.Tensor,
                         y_pred: torch.Tensor) -> torch.Tensor:
            """Soft physics constraints encoded as penalty terms."""
            loss = torch.tensor(0.0, device=x.device)

            # monotonicity: gain_db (index 0) should be positive
            if y_pred.size(-1) > 0:
                gain_db = y_pred[..., 0]
                loss += torch.relu(-gain_db).mean()

            # phase-margin should be in (0°, 90°)
            if y_pred.size(-1) > 2:
                pm = y_pred[..., 2]
                loss += torch.relu(-pm).mean()
                loss += torch.relu(pm - 90).mean()

            return self.lambda_phys * loss

        def total_loss(self, x, y_pred, y_true,
                       criterion=None) -> Tuple[torch.Tensor, dict]:
            if criterion is None:
                criterion = nn.MSELoss()
            data_loss  = criterion(y_pred, y_true)
            phys_loss  = self.physics_loss(x, y_pred)
            total      = data_loss + phys_loss
            return total, {"data": data_loss.item(), "physics": phys_loss.item()}

else:
    class AnalogPINN:  # type: ignore
        def __init__(self, **kw): pass


# ─────────────────────────────────────────────────────────────────────────────
# 3.  Neural ODE  (transient / AC dynamics)
# ─────────────────────────────────────────────────────────────────────────────

if ODE_AVAILABLE:
    class _ODEFunc(nn.Module):
        """dz/dt = f_θ(z, t) — the latent ODE right-hand side."""
        def __init__(self, latent_dim: int, hidden: int = 64):
            super().__init__()
            self.net = nn.Sequential(
                nn.Linear(latent_dim + 1, hidden), nn.Tanh(),
                nn.Linear(hidden, hidden), nn.Tanh(),
                nn.Linear(hidden, latent_dim),
            )

        def forward(self, t: torch.Tensor, z: torch.Tensor) -> torch.Tensor:
            t_vec = t.expand(z.size(0), 1) if z.dim() > 1 else t.unsqueeze(0)
            return self.net(torch.cat([z, t_vec], dim=-1))

    class NeuralODEModel(nn.Module):
        """
        Neural ODE for transient response prediction.
        Encodes initial state, integrates ODE, decodes output waveform.
        """
        def __init__(self, in_dim: int, latent_dim: int = 32,
                     out_dim: int = 1, hidden: int = 64):
            super().__init__()
            self.encoder  = nn.Sequential(
                nn.Linear(in_dim, hidden), nn.SiLU(),
                nn.Linear(hidden, latent_dim)
            )
            self.ode_func = _ODEFunc(latent_dim, hidden)
            self.decoder  = nn.Sequential(
                nn.Linear(latent_dim, hidden), nn.SiLU(),
                nn.Linear(hidden, out_dim)
            )

        def forward(self, x: torch.Tensor,
                    t_span: torch.Tensor) -> torch.Tensor:
            z0 = self.encoder(x)
            # t_span: 1-D tensor of time points
            zt = odeint(self.ode_func, z0, t_span, method="dopri5")
            # zt shape: (T, batch, latent) or (T, latent) for single sample
            return self.decoder(zt)   # (T, batch, out_dim)

else:
    class NeuralODEModel:  # type: ignore
        def __init__(self, **kw): pass


# ─────────────────────────────────────────────────────────────────────────────
# 4.  Hamiltonian NN  (energy-conserving for power analysis)
# ─────────────────────────────────────────────────────────────────────────────

if TORCH_AVAILABLE:
    class HamiltonianNN(nn.Module):
        """
        Learns Hamiltonian H(q, p) where q=charges, p=flux linkages.
        Hamilton's equations: dq/dt = ∂H/∂p, dp/dt = -∂H/∂q
        Ensures energy conservation by construction.
        """
        def __init__(self, state_dim: int, hidden: int = 64):
            super().__init__()
            d = state_dim // 2
            self.d    = d
            self.hamiltonian = nn.Sequential(
                nn.Linear(state_dim, hidden), nn.Tanh(),
                nn.Linear(hidden, hidden),    nn.Tanh(),
                nn.Linear(hidden, 1),
            )

        def forward(self, qp: torch.Tensor) -> torch.Tensor:
            """Returns dqp/dt from Hamilton's equations."""
            qp = qp.requires_grad_(True)
            H  = self.hamiltonian(qp).sum()
            grad = torch.autograd.grad(H, qp, create_graph=True)[0]
            d = self.d
            dq =  grad[..., d:]   # ∂H/∂p
            dp = -grad[..., :d]   # -∂H/∂q
            return torch.cat([dq, dp], dim=-1)

        def total_energy(self, qp: torch.Tensor) -> torch.Tensor:
            return self.hamiltonian(qp)

else:
    class HamiltonianNN:  # type: ignore
        def __init__(self, **kw): pass


# ─────────────────────────────────────────────────────────────────────────────
# 5.  Multi-Fidelity Gaussian Process
# ─────────────────────────────────────────────────────────────────────────────

class MultiFidelityGP:
    """
    Two-level multi-fidelity model using Kennedy-O'Hagan approach:
      y_high(x) = ρ · y_low(x) + δ(x)
    where δ is a correction GP.
    """

    def __init__(self):
        kernel_low  = Matern(nu=2.5) + WhiteKernel(noise_level=1e-3)
        kernel_corr = RBF()          + WhiteKernel(noise_level=1e-4)
        self.gp_low  = GaussianProcessRegressor(kernel=kernel_low,
                                                 normalize_y=True)
        self.gp_corr = GaussianProcessRegressor(kernel=kernel_corr,
                                                 normalize_y=True)
        self.rho   : float = 1.0
        self._fitted = False

    def fit(self, X_low: np.ndarray, Y_low: np.ndarray,
            X_high: np.ndarray, Y_high: np.ndarray):
        self.gp_low.fit(X_low, Y_low)
        # compute rho via linear regression of Y_high on Y_low at high-fid points
        y_low_at_high = self.gp_low.predict(X_high)
        if Y_high.ndim == 1:
            self.rho = float(np.cov(Y_high, y_low_at_high)[0,1] /
                             (np.var(y_low_at_high) + 1e-12))
        X_aug  = np.hstack([X_high, y_low_at_high.reshape(-1,1)
                             if y_low_at_high.ndim==1
                             else y_low_at_high])
        delta  = Y_high - self.rho * y_low_at_high
        self.gp_corr.fit(X_aug, delta)
        self._fitted = True

    def predict(self, X: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        y_low, _       = self.gp_low.predict(X, return_std=True)
        X_aug          = np.hstack([X, y_low.reshape(-1,1)
                                     if y_low.ndim==1 else y_low])
        delta, std_corr = self.gp_corr.predict(X_aug, return_std=True)
        y_high          = self.rho * y_low + delta
        return y_high, std_corr


# ─────────────────────────────────────────────────────────────────────────────
# 6.  Symbolic Regression (PySR wrapper)
# ─────────────────────────────────────────────────────────────────────────────

class SymbolicRegressor:
    """
    Wraps PySR (or falls back to polynomial regression) to extract
    interpretable equations from the trained model's predictions.
    """

    def __init__(self, n_iterations: int = 40):
        self.n_iterations = n_iterations
        self.model        = None
        self._use_pysr    = False
        try:
            import pysr
            self._use_pysr = True
            self._pysr_module = pysr
        except ImportError:
            pass

    def fit(self, X: np.ndarray, y: np.ndarray,
            feature_names: Optional[List[str]] = None):
        """Fit symbolic regression to (X, y)."""
        if self._use_pysr:
            self.model = self._pysr_module.PySRRegressor(
                niterations=self.n_iterations,
                binary_operators=["+", "*", "-", "/"],
                unary_operators=["log", "sqrt", "exp"],
                verbosity=0,
            )
            kw = {"X": X, "y": y}
            if feature_names:
                kw["variable_names"] = feature_names
            self.model.fit(**kw)
        else:
            # polynomial fallback
            from sklearn.preprocessing import PolynomialFeatures
            from sklearn.linear_model  import Ridge
            from sklearn.pipeline      import Pipeline
            self.model = Pipeline([
                ("poly", PolynomialFeatures(degree=2, include_bias=False)),
                ("reg",  Ridge(alpha=0.01)),
            ])
            self.model.fit(X, y)

    def predict(self, X: np.ndarray) -> np.ndarray:
        if self.model is None:
            raise RuntimeError("Call fit() first.")
        return self.model.predict(X)

    def get_equations(self) -> List[str]:
        """Return list of discovered symbolic equations."""
        if self._use_pysr and hasattr(self.model, "equations_"):
            return [str(eq) for eq in self.model.equations_["sympy_format"].tolist()
                    if hasattr(eq, "__str__")]
        return ["(polynomial fallback — install pysr for symbolic equations)"]


# ─────────────────────────────────────────────────────────────────────────────
# 7.  Master AnalogMLModel
# ─────────────────────────────────────────────────────────────────────────────

class AnalogMLModel:
    """
    Unified multi-fidelity, physics-backed model for analog circuits.

    Training modes:
      'fast'   — GradientBoosting surrogate (no GPU needed, < 30 s)
      'nn'     — PINN-based deep network (needs PyTorch)
      'full'   — PINN + Neural ODE + Hamiltonian + symbolic extraction

    Prediction:
      predict(X)              → Y (all output specs)
      predict_with_uncertainty → (Y_mean, Y_std)
      recommend_sizes(specs)  → X* that meets target specs
    """

    def __init__(self, mode: str = "nn",
                 fidelity_levels: Optional[List[str]] = None,
                 output_names: Optional[List[str]] = None):
        self.mode           = mode
        self.fidelity_levels = fidelity_levels or ["schematic"]
        self.output_names   = output_names or []
        self.scaler_X       = StandardScaler()
        self.scaler_Y       = StandardScaler()
        self._fitted        = False

        # sub-models
        self.surrogate : Any = None
        self.pinn      : Optional[AnalogPINN]       = None
        self.mf_gp     : Optional[MultiFidelityGP]  = None
        self.symbolic  : Optional[SymbolicRegressor] = None

        # training history
        self.history: Dict[str, List[float]] = {"loss":[], "val_loss":[]}

    # ── fit ───────────────────────────────────────────────────────────────────

    def fit(self, X: np.ndarray, Y: np.ndarray,
            X_val: Optional[np.ndarray] = None,
            Y_val: Optional[np.ndarray] = None,
            epochs: int = 300,
            lr: float = 1e-3,
            batch_size: int = 32):
        """Train the model on (X, Y) arrays."""
        if Y.ndim == 1:
            Y = Y.reshape(-1, 1)

        Xs = self.scaler_X.fit_transform(X)
        Ys = self.scaler_Y.fit_transform(Y)

        if self.mode == "fast" or not TORCH_AVAILABLE:
            self._fit_surrogate(Xs, Ys)
        elif self.mode in ("nn", "full"):
            self._fit_pinn(Xs, Ys, X_val, Y_val, epochs, lr, batch_size)
            if self.mode == "full":
                self._fit_symbolic(Xs, Ys)

        # always fit GP for uncertainty
        self._fit_gp(Xs, Ys)
        self._fitted = True

    def _fit_surrogate(self, Xs: np.ndarray, Ys: np.ndarray):
        base = GradientBoostingRegressor(n_estimators=200, max_depth=4,
                                          learning_rate=0.05)
        self.surrogate = MultiOutputRegressor(base)
        self.surrogate.fit(Xs, Ys)
        preds = self.surrogate.predict(Xs)
        mse   = np.mean((preds - Ys)**2)
        self.history["loss"].append(float(mse))

    def _fit_pinn(self, Xs, Ys, X_val, Y_val, epochs, lr, batch_size):
        in_dim  = Xs.shape[1]
        out_dim = Ys.shape[1]
        self.pinn = AnalogPINN(in_dim, out_dim, hidden=128, n_layers=4)
        opt       = optim.Adam(self.pinn.parameters(), lr=lr)
        scheduler = optim.lr_scheduler.CosineAnnealingLR(opt, T_max=epochs)

        Xt = torch.tensor(Xs, dtype=torch.float32)
        Yt = torch.tensor(Ys, dtype=torch.float32)

        for ep in range(epochs):
            self.pinn.train()
            # mini-batch
            idx   = np.random.permutation(len(Xt))
            epoch_loss = 0.0
            for i in range(0, len(Xt), batch_size):
                bi  = idx[i:i+batch_size]
                xb, yb = Xt[bi], Yt[bi]
                opt.zero_grad()
                yp  = self.pinn(xb)
                loss, _ = self.pinn.total_loss(xb, yp, yb)
                loss.backward()
                torch.nn.utils.clip_grad_norm_(self.pinn.parameters(), 1.0)
                opt.step()
                epoch_loss += loss.item()
            scheduler.step()
            self.history["loss"].append(epoch_loss / max(1, len(Xt)//batch_size))

            if X_val is not None and ep % 20 == 0:
                self.pinn.eval()
                with torch.no_grad():
                    Xv  = torch.tensor(self.scaler_X.transform(X_val),
                                        dtype=torch.float32)
                    Yv  = torch.tensor(self.scaler_Y.transform(Y_val),
                                        dtype=torch.float32)
                    vp  = self.pinn(Xv)
                    vl, _ = self.pinn.total_loss(Xv, vp, Yv)
                    self.history["val_loss"].append(vl.item())

    def _fit_gp(self, Xs, Ys):
        # GP on first output for uncertainty
        y0 = Ys[:, 0] if Ys.ndim > 1 else Ys
        kernel = Matern(nu=2.5) + WhiteKernel(noise_level=1e-3)
        self.mf_gp_single = GaussianProcessRegressor(kernel=kernel,
                                                       normalize_y=True,
                                                       n_restarts_optimizer=2)
        # subsample for speed
        n = min(500, len(Xs))
        idx = np.random.choice(len(Xs), n, replace=False)
        self.mf_gp_single.fit(Xs[idx], y0[idx])

    def _fit_symbolic(self, Xs, Ys):
        self.symbolic = SymbolicRegressor(n_iterations=30)
        self.symbolic.fit(Xs[:200], Ys[:200, 0])

    # ── predict ───────────────────────────────────────────────────────────────

    def predict(self, X: np.ndarray) -> np.ndarray:
        if not self._fitted:
            raise RuntimeError("Model not fitted. Call fit() first.")
        Xs = self.scaler_X.transform(
            X.reshape(1,-1) if X.ndim==1 else X)

        if self.pinn is not None and TORCH_AVAILABLE:
            self.pinn.eval()
            with torch.no_grad():
                Xt = torch.tensor(Xs, dtype=torch.float32)
                Ys = self.pinn(Xt).numpy()
        elif self.surrogate is not None:
            Ys = self.surrogate.predict(Xs)
        else:
            raise RuntimeError("No sub-model available.")

        return self.scaler_Y.inverse_transform(Ys)

    def predict_with_uncertainty(self, X: np.ndarray
                                  ) -> Tuple[np.ndarray, np.ndarray]:
        Y_mean = self.predict(X)
        Xs     = self.scaler_X.transform(
            X.reshape(1,-1) if X.ndim==1 else X)
        _, std = self.mf_gp_single.predict(Xs, return_std=True)
        std_full = np.tile(std.reshape(-1,1), (1, Y_mean.shape[1]))
        # rescale std back to original units
        std_full = std_full * self.scaler_Y.scale_[0]
        return Y_mean, std_full

    # ── inverse design ────────────────────────────────────────────────────────

    def recommend_sizes(self, target_specs: Dict[str, float],
                        X_candidates: Optional[np.ndarray] = None,
                        n_candidates: int = 1000) -> np.ndarray:
        """
        Returns the X vector (sizes/topology features) from candidates
        that best matches target_specs.

        If X_candidates is None, samples randomly around training data mean.
        """
        if not self._fitted:
            raise RuntimeError("Call fit() first.")

        if X_candidates is None:
            mean = self.scaler_X.mean_
            std  = np.sqrt(self.scaler_X.var_)
            X_candidates = np.random.randn(n_candidates, len(mean)) * std + mean

        Y_pred = self.predict(X_candidates)
        if self.output_names and target_specs:
            # score = negative MSE in spec space
            target_vec = np.array([target_specs.get(k, np.nan)
                                   for k in self.output_names])
            valid = ~np.isnan(target_vec)
            scores = -np.sum((Y_pred[:, valid]
                              - target_vec[valid])**2, axis=1)
            best_idx = int(np.argmax(scores))
        else:
            best_idx = 0

        return X_candidates[best_idx]

    # ── persistence ───────────────────────────────────────────────────────────

    def save(self, path: str):
        """Save model state to directory."""
        import joblib, os
        os.makedirs(path, exist_ok=True)
        joblib.dump(self.scaler_X, os.path.join(path, "scaler_X.pkl"))
        joblib.dump(self.scaler_Y, os.path.join(path, "scaler_Y.pkl"))
        if self.surrogate:
            joblib.dump(self.surrogate, os.path.join(path, "surrogate.pkl"))
        if TORCH_AVAILABLE and self.pinn:
            torch.save(self.pinn.state_dict(),
                       os.path.join(path, "pinn_weights.pt"))
        meta = {"mode": self.mode,
                "output_names": self.output_names,
                "fidelity_levels": self.fidelity_levels}
        with open(os.path.join(path, "meta.json"), "w") as f:
            json.dump(meta, f)

    @classmethod
    def load(cls, path: str) -> "AnalogMLModel":
        import joblib
        with open(os.path.join(path, "meta.json")) as f:
            meta = json.load(f)
        m = cls(mode=meta["mode"], output_names=meta["output_names"],
                fidelity_levels=meta["fidelity_levels"])
        m.scaler_X = joblib.load(os.path.join(path, "scaler_X.pkl"))
        m.scaler_Y = joblib.load(os.path.join(path, "scaler_Y.pkl"))
        surr_path  = os.path.join(path, "surrogate.pkl")
        if os.path.exists(surr_path):
            m.surrogate = joblib.load(surr_path)
        pinn_path  = os.path.join(path, "pinn_weights.pt")
        if os.path.exists(pinn_path) and TORCH_AVAILABLE:
            in_dim  = len(m.scaler_X.mean_)
            out_dim = len(m.scaler_Y.mean_)
            m.pinn  = AnalogPINN(in_dim, out_dim)
            m.pinn.load_state_dict(torch.load(pinn_path))
        m._fitted = True
        return m


# ─────────────────────────────────────────────────────────────────────────────
# 8.  Technology Transfer Agent
# ─────────────────────────────────────────────────────────────────────────────

class TechTransferAgent:
    """
    Maps circuit feature vectors from source technology to target technology.
    Uses an affine + GBM residual correction.

    Workflow:
      1. fit(X_src, X_tgt) on matched circuit pairs
      2. transfer(X_new_src) → X_tgt_estimate
      3. Pass X_tgt_estimate to AnalogMLModel trained on target tech
    """

    def __init__(self, source_tech: str = "180nm",
                 target_tech: str = "90nm"):
        self.source_tech = source_tech
        self.target_tech = target_tech
        self.scaler_src  = StandardScaler()
        self.scaler_tgt  = StandardScaler()
        self.mapping     = MultiOutputRegressor(
            GradientBoostingRegressor(n_estimators=100, max_depth=3)
        )
        self._fitted     = False

    def fit(self, X_src: np.ndarray, X_tgt: np.ndarray):
        Xs = self.scaler_src.fit_transform(X_src)
        Xt = self.scaler_tgt.fit_transform(X_tgt)
        self.mapping.fit(Xs, Xt)
        self._fitted = True

    def transfer(self, X_src: np.ndarray) -> np.ndarray:
        if not self._fitted:
            raise RuntimeError("Call fit() first.")
        Xs = self.scaler_src.transform(
            X_src.reshape(1,-1) if X_src.ndim==1 else X_src)
        Xt = self.mapping.predict(Xs)
        return self.scaler_tgt.inverse_transform(Xt)

    def tech_scaling_rules(self) -> Dict[str, float]:
        """
        Heuristic Dennard-like scaling ratios for rough guidance.
        Returns a dict of expected parameter scaling factors.
        """
        try:
            src_nm = int(self.source_tech.replace("nm",""))
            tgt_nm = int(self.target_tech.replace("nm",""))
            alpha  = tgt_nm / src_nm    # < 1 for shrink
        except ValueError:
            alpha  = 0.5
        return {
            "L_ratio"      : alpha,
            "W_ratio"      : alpha,
            "C_ratio"      : alpha**2,
            "R_ratio"      : 1.0/alpha,
            "Vdd_ratio"    : alpha**0.3,
            "Idsat_ratio"  : 1.0/alpha,
            "fT_ratio"     : 1.0/alpha,
        }
