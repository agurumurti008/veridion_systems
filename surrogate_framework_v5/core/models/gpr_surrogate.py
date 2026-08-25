"""
core/models/gpr_surrogate.py
Gaussian Process Regression surrogate + ModelSelector.
"""
import signal
import numpy as np

try:
    from sklearn.gaussian_process import GaussianProcessRegressor
    from sklearn.gaussian_process.kernels import Matern, RBF
    from sklearn.preprocessing import StandardScaler
    from sklearn.metrics import mean_squared_error
    _SKLEARN = True
except ImportError:
    _SKLEARN = False


class FitTimeout(Exception):
    """Raised by fit_with_wallclock_timeout when a fit call is killed
    for exceeding its wall-clock budget. Subclasses Exception (not a
    bespoke base) so it's caught for free by every `except Exception`
    fallback-to-a-simpler-model block already in this file/smt_surrogate.py
    — no separate except clause needed at call sites."""


def _alarm_handler(signum, frame):
    raise FitTimeout("fit exceeded its wall-clock time budget")


def fit_with_wallclock_timeout(fit_fn, timeout_s: float):
    """Runs fit_fn() under a hard SIGALRM wall-clock cap, raising
    FitTimeout if it doesn't return in time.

    Bounding an optimizer's ITERATION count (see _bounded_lbfgs here and
    smt_surrogate.py's _bound_smt_optimizer_iterations) assumes each
    iteration's own cost is roughly predictable — confirmed FALSE for
    smt's KRG at higher input dimensionality: even capped to 5 TNC
    function evaluations, a single fit on 1500 points x 31 features
    (the width a differential-feature-augmented Phase2 pipeline
    produces) still exceeded 60s. A per-iteration cap can't guard
    against a per-EVALUATION cost that itself scales unpredictably with
    data/dimensionality — a wall-clock cap is the only mechanism that
    actually guarantees a fit call returns, regardless of which internal
    operation turns out to be the expensive one.

    SIGALRM only works in the main thread of the main interpreter on
    Unix — if that's not the calling context (e.g. Windows, or fit()
    called from a worker thread), this degrades to no timeout at all
    (fit_fn still runs to completion) rather than raising, matching this
    codebase's established graceful-degradation convention elsewhere."""
    if not hasattr(signal, 'SIGALRM'):
        return fit_fn()
    try:
        old_handler = signal.signal(signal.SIGALRM, _alarm_handler)
    except ValueError:
        return fit_fn()  # not the main thread — can't install a handler
    try:
        signal.alarm(max(1, int(timeout_s)))
        return fit_fn()
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)


def _bounded_lbfgs(obj_func, initial_theta, bounds):
    """sklearn's documented custom-optimizer callable hook for
    GaussianProcessRegressor(optimizer=...) — same signature/contract as
    sklearn's own internal 'fmin_l_bfgs_b' default, just with an explicit
    maxiter/maxfun cap (see _build_gpr's comment for why the uncapped
    default is unsafe here). 50 iterations is still enough for L-BFGS-B
    to make real progress on a well-behaved likelihood surface; on a
    pathological one it now returns sklearn's own best-effort theta
    instead of never returning at all."""
    from scipy.optimize import minimize
    res = minimize(obj_func, initial_theta, method="L-BFGS-B", jac=True,
                   bounds=bounds, options={'maxiter': 15, 'maxfun': 15})
    return res.x, res.fun


def drop_degenerate_columns(X_scaled: np.ndarray) -> np.ndarray:
    """Indices of columns to KEEP: drop near-zero-variance columns (std <
    1e-8 after scaling — effectively constant) and, among the rest,
    greedily drop one column from any pair with |correlation| > 0.999
    (near-collinear inputs — e.g. several supply rails that move
    together across a corner sweep). A near-singular design matrix
    doesn't just fit worse: it sends a kernel-based regressor's internal
    Cholesky/jitter-retry loop into pathologically slow territory (LAPACK
    potrf failures / hangs) instead of fitting cleanly — this must run
    BEFORE the matrix ever reaches the optimizer. Shared by both
    CircuitGPR (sklearn's GaussianProcessRegressor) and CircuitSMT (smt's
    Kriging, or the scipy RBF fallback) — both are kernel-matrix methods
    with the identical failure mode on collinear inputs."""
    n_cols = X_scaled.shape[1]
    stds = X_scaled.std(axis=0)
    keep = [i for i in range(n_cols) if stds[i] > 1e-8]
    if len(keep) <= 1:
        return np.array(keep, dtype=int)
    corr = np.corrcoef(X_scaled[:, keep], rowvar=False)
    dropped = set()
    for i in range(len(keep)):
        if i in dropped:
            continue
        for j in range(i + 1, len(keep)):
            if j not in dropped and abs(corr[i, j]) > 0.999:
                dropped.add(j)
    return np.array([keep[i] for i in range(len(keep)) if i not in dropped],
                    dtype=int)


class CircuitGPR:
    """Multi-output GPR surrogate with active learning support."""

    def __init__(self, input_dim: int, output_dim: int, fit_timeout_s: float = 30.0):
        self.input_dim = input_dim
        self.output_dim = output_dim
        self.models = []
        self.x_scaler = None
        self.y_scalers = []
        self.is_fitted = False
        self.kept_cols_ = None  # set in fit(); indices surviving drop_degenerate_columns
        # Hard wall-clock cap per-output GPR fit — see
        # fit_with_wallclock_timeout's docstring for why an iteration
        # bound (_bounded_lbfgs) alone isn't a sufficient guarantee.
        self.fit_timeout_s = fit_timeout_s

        if not _SKLEARN:
            print("[CircuitGPR] scikit-learn not available — using linear fallback")

    def _build_gpr(self):
        if not _SKLEARN:
            return None
        kernel = Matern(nu=2.5) + RBF()
        return GaussianProcessRegressor(
            kernel=kernel,
            # Slightly larger nugget for numerical headroom against near-
            # singular kernels (see drop_degenerate_columns). No extra
            # optimizer restart (n_restarts_optimizer=0 still runs ONE
            # optimization from the kernel's default theta — this only
            # drops the ADDITIONAL random restart, not all optimization):
            # each restart independently pays the same _bounded_lbfgs
            # iteration cost below, and a SINGLE well-bounded optimization
            # pass is a better tradeoff here than two runs each individually
            # capped short of convergence.
            alpha=1e-3,
            normalize_y=True,
            n_restarts_optimizer=0,
            # sklearn's default optimizer='fmin_l_bfgs_b' has NO iteration
            # cap of its own (scipy's L-BFGS-B default is up to 15000
            # iterations/function evals) — and each function eval here is
            # an O(n^3) Cholesky factorization of the n-point kernel
            # matrix. On a feature set with weak/uninformative columns
            # (a flat-ish log-marginal-likelihood surface — exactly what
            # a wide auto-selected/derivative feature set can produce),
            # the optimizer can wander for thousands of evaluations
            # before converging — confirmed directly: an unmodified fit
            # on just 3000 points x 5 features ran for 8+ CPU-minutes
            # with no sign of finishing. _optimizer below is sklearn's
            # documented custom-optimizer callable hook (same "(obj_func,
            # initial_theta, bounds) -> (theta_opt, func_min)" signature
            # scipy's own default uses internally) — it just adds a hard
            # maxiter/maxfun cap, trading a little hyperparameter-
            # optimization quality (this is an informational comparison-
            # table model, never the embedded equation) for a GUARANTEED
            # bounded fit time regardless of how pathological the
            # likelihood surface is.
            optimizer=_bounded_lbfgs,
        )

    def fit(self, X: np.ndarray, Y: np.ndarray):
        """Fit one GPR per output with input/output standardization."""
        X = np.array(X, dtype=np.float64)
        Y = np.array(Y, dtype=np.float64)
        if Y.ndim == 1:
            Y = Y.reshape(-1, 1)

        if _SKLEARN:
            self.x_scaler = StandardScaler()
            X_scaled = self.x_scaler.fit_transform(X)
            self.kept_cols_ = drop_degenerate_columns(X_scaled)
            if len(self.kept_cols_) < X_scaled.shape[1]:
                print(f"[CircuitGPR] dropped "
                      f"{X_scaled.shape[1] - len(self.kept_cols_)} near-"
                      f"constant/collinear input column(s) before fitting "
                      f"(a degenerate design matrix otherwise stalls the "
                      f"kernel optimizer)")
            X_scaled = X_scaled[:, self.kept_cols_]
        else:
            self.x_scaler = _SimpleScaler()
            X_scaled = self.x_scaler.fit_transform(X)
            self.kept_cols_ = np.arange(X_scaled.shape[1])

        self.models = []
        self.y_scalers = []

        for d in range(self.output_dim):
            y_d = Y[:, d]
            if _SKLEARN:
                ys = StandardScaler()
                y_d_scaled = ys.fit_transform(y_d.reshape(-1, 1)).ravel()
                self.y_scalers.append(ys)
            else:
                ys = _SimpleScaler()
                y_d_scaled = ys.fit_transform(y_d.reshape(-1, 1)).ravel()
                self.y_scalers.append(ys)

            if _SKLEARN:
                gpr = self._build_gpr()
                try:
                    fit_with_wallclock_timeout(
                        lambda: gpr.fit(X_scaled, y_d_scaled), self.fit_timeout_s)
                except Exception as e:
                    print(f"[CircuitGPR] GPR fit failed/timed out for "
                          f"output {d}: {e} — falling back to a linear fit")
                    gpr = _LinearFallback()
                    gpr.fit(X_scaled, y_d_scaled)
            else:
                gpr = _LinearFallback()
                gpr.fit(X_scaled, y_d_scaled)

            self.models.append(gpr)

        self.is_fitted = True

    def predict(self, X: np.ndarray, return_std: bool = True):
        """Predict with inverse-transform. Returns (mean, std)."""
        X = np.array(X, dtype=np.float64)
        if not self.is_fitted:
            mean = np.zeros((len(X), self.output_dim))
            std = np.ones((len(X), self.output_dim))
            return mean, std

        X_scaled = self.x_scaler.transform(X)
        if self.kept_cols_ is not None:
            X_scaled = X_scaled[:, self.kept_cols_]
        means = []
        stds = []

        for d, (gpr, ys) in enumerate(zip(self.models, self.y_scalers)):
            if _SKLEARN and hasattr(gpr, 'predict') and not isinstance(gpr, _LinearFallback):
                try:
                    mu_s, sigma_s = gpr.predict(X_scaled, return_std=True)
                except Exception:
                    mu_s = gpr.predict(X_scaled)
                    sigma_s = np.ones_like(mu_s) * 0.1
            else:
                mu_s = gpr.predict(X_scaled)
                sigma_s = np.ones_like(mu_s) * 0.1

            # Inverse transform
            mu = ys.inverse_transform(mu_s.reshape(-1, 1)).ravel()
            # Scale std by y_scaler scale
            if hasattr(ys, 'scale_') and ys.scale_ is not None:
                sig = sigma_s * float(ys.scale_[0])
            else:
                sig = sigma_s * (ys.y_std if hasattr(ys, 'y_std') else 1.0)

            means.append(mu)
            stds.append(sig)

        mean_arr = np.stack(means, axis=1)
        std_arr = np.stack(stds, axis=1)
        return mean_arr, std_arr

    def evaluate(self, X: np.ndarray, Y: np.ndarray) -> float:
        """Return scalar MSE across all outputs."""
        Y = np.array(Y, dtype=np.float64)
        if Y.ndim == 1:
            Y = Y.reshape(-1, 1)
        mean, _ = self.predict(X)
        return float(np.mean((mean - Y) ** 2))

    def next_sample(self, candidate_pool: np.ndarray) -> np.ndarray:
        """Active learning: return row with highest mean predicted std."""
        _, std = self.predict(candidate_pool)
        mean_std = std.mean(axis=1)
        idx = int(np.argmax(mean_std))
        return candidate_pool[idx]


class _SimpleScaler:
    """NumPy-only standard scaler fallback."""
    def __init__(self):
        self.mean_ = None
        self.scale_ = None

    def fit_transform(self, X):
        X = np.array(X, dtype=np.float64)
        self.mean_ = X.mean(axis=0)
        self.scale_ = X.std(axis=0)
        self.scale_[self.scale_ < 1e-10] = 1.0
        return (X - self.mean_) / self.scale_

    def transform(self, X):
        return (np.array(X, dtype=np.float64) - self.mean_) / self.scale_

    def inverse_transform(self, X):
        X = np.array(X, dtype=np.float64)
        if X.ndim == 1:
            return X * self.scale_[0] + self.mean_[0]
        return X * self.scale_ + self.mean_

    @property
    def y_std(self):
        return float(self.scale_[0]) if self.scale_ is not None else 1.0


class _LinearFallback:
    """Linear regression fallback when GPR fails."""
    def __init__(self):
        self.coef_ = None
        self.intercept_ = 0.0

    def fit(self, X, y):
        X_b = np.hstack([X, np.ones((len(X), 1))])
        try:
            sol, _, _, _ = np.linalg.lstsq(X_b, y, rcond=None)
            self.coef_ = sol[:-1]
            self.intercept_ = sol[-1]
        except Exception:
            self.coef_ = np.zeros(X.shape[1])
            self.intercept_ = float(np.mean(y))

    def predict(self, X):
        return X @ self.coef_ + self.intercept_


class ModelSelector:
    """Select best surrogate model by MSE."""

    @staticmethod
    def select_best(metrics_dict: dict, models_dict: dict) -> str:
        """Print ranked table and return name of best model."""
        if not metrics_dict:
            return list(models_dict.keys())[0] if models_dict else 'PINN'

        sorted_models = sorted(metrics_dict.items(), key=lambda x: x[1])
        best_name = sorted_models[0][0]

        print(f"\n{'='*45}")
        print(f"  Model Comparison")
        print(f"  {'Model':<12} {'MSE':>12}  {'Winner'}")
        print(f"  {'-'*40}")
        for name, mse in sorted_models:
            marker = '← BEST' if name == best_name else ''
            print(f"  {name:<12} {mse:>12.6f}  {marker}")
        print(f"{'='*45}\n")

        return best_name

    @staticmethod
    def select_best_per_state(state_metrics: dict, models_dict: dict = None) -> dict:
        """Per-state variant of select_best: state_metrics is
        {state_id: {model_name: mse}}. Runs the existing ranking (and its
        printed table) once per state, reusing select_best rather than
        reimplementing the argmin/print logic, and returns
        {state_id: best_model_name}."""
        best_by_state = {}
        for state_id in sorted(state_metrics.keys()):
            metrics_dict = state_metrics[state_id]
            print(f"  -- state {state_id} --")
            best_by_state[state_id] = ModelSelector.select_best(
                metrics_dict, models_dict or {})
        return best_by_state
