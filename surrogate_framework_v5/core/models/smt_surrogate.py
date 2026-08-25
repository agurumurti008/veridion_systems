"""
core/models/smt_surrogate.py
Surrogate-Modeling-Toolbox-style surrogate: tries the `smt` package
(Kriging), falls back to scipy's RBFInterpolator when `smt` isn't
installed — matching this repo's established optional-dependency
convention (PySR -> linear regression, wandb -> skip; see
INSTRUCTIONS.md's "Optional extras" table). Interface mirrors
CircuitGPR (core/models/gpr_surrogate.py) closely enough to slot into
the same comparison table: fit(X, Y), predict(X) -> (mean, std),
evaluate(X, Y) -> float.
"""
import numpy as np

from core.models.gpr_surrogate import (
    _SimpleScaler, drop_degenerate_columns, fit_with_wallclock_timeout,
)

try:
    from sklearn.preprocessing import StandardScaler
    _SKLEARN = True
except ImportError:
    _SKLEARN = False

try:
    from smt.surrogate_models import KRG
    import functools as _functools
    _SMT = True
except ImportError:
    _SMT = False


def _bound_smt_optimizer_iterations(model, limit: int = 30):
    """KRG._optimize_hyperparam(D, use_multistart=True, limit=None)
    computes its OWN iteration limit when none is given:
    `limit = max(12 * len(self._theta0), 50)` (smt/surrogate_models/
    krg_based/krg_based.py) — len(self._theta0) is the correlation
    function's ANISOTROPIC per-input-dimension parameter count, so a
    31-feature Phase2 dataset (the width a differential-feature-
    augmented pipeline produces) alone drives this to max(12*31,50)=372
    TNC iterations, each an expensive reduced-likelihood evaluation —
    confirmed directly: an unmodified KRG().fit() on 1500 points x 31
    features still hadn't returned after 90s. There is no public KRG()
    constructor option for this (hyper_opt only accepts its three
    documented strings, 'TNC'/'Cobyla'/'NoOp' — despite krg_based.py's
    _get_optimizer() ALSO having an `isinstance(hyper_opt,
    HyperparamOptimizer)` passthrough branch, options-validation rejects
    a custom instance before that branch is ever reached in this smt
    version, confirmed directly). This binds a fixed, small `limit` onto
    THIS model instance's already-bound _optimize_hyperparam via
    functools.partial — an instance-level override (Python attribute
    lookup prefers the instance dict over the class), so it only affects
    this one model, not KRG globally, and _train()'s internal
    `self._optimize_hyperparam(D)` call (smt/surrogate_models/krg_based/
    krg_based.py:533, no limit kwarg) picks it up transparently. Keeps
    REAL (bounded) TNC optimization rather than skipping it entirely via
    hyper_opt='NoOp' — a better fit-quality tradeoff for an informational,
    never-embedded comparison-table model, while still guaranteeing a
    bounded worst-case fit time."""
    if hasattr(model, '_optimize_hyperparam'):
        model._optimize_hyperparam = _functools.partial(
            model._optimize_hyperparam, limit=limit)
    return model

try:
    from scipy.interpolate import RBFInterpolator
    _SCIPY_RBF = True
except ImportError:
    _SCIPY_RBF = False


class _RBFFallback:
    """scipy.interpolate.RBFInterpolator wrapped to look like an
    smt.surrogate_models model (.set_training_values/.train/.predict_values
    -> plain .fit/.predict), for the no-`smt` fallback path."""

    def __init__(self):
        self._interp = None
        self._y_mean = 0.0

    def fit(self, X: np.ndarray, y: np.ndarray):
        # RBFInterpolator needs distinct points; duplicate rows (possible
        # after standardization of near-identical corner samples) are
        # jittered a negligible amount rather than dropped, so row count
        # stays aligned with the caller's y.
        Xu = X.copy()
        _, inv, counts = np.unique(Xu, axis=0, return_inverse=True, return_counts=True)
        if (counts > 1).any():
            Xu = Xu + np.random.RandomState(0).normal(0, 1e-9, Xu.shape)
        self._y_mean = float(np.mean(y))
        try:
            # A small nonzero `smoothing` turns exact interpolation into a
            # regularized least-squares fit (scipy's analogue of a
            # Kriging "nugget" term) — without it, near-duplicate rows
            # (common here: control pins like EN_LDO/VPWR_SEL sit at a
            # constant digital level for long stretches, so many samples
            # share near-identical X vectors) leave the RBF system
            # ill-conditioned, and thin_plate_spline extrapolates without
            # bound past the training hull, producing wildly unstable
            # predictions on held-out points.
            self._interp = RBFInterpolator(Xu, y, kernel='thin_plate_spline',
                                           smoothing=1e-3)
        except Exception:
            self._interp = None

    def predict(self, X: np.ndarray) -> np.ndarray:
        if self._interp is None:
            return np.full(len(X), self._y_mean)
        try:
            return self._interp(X)
        except Exception:
            return np.full(len(X), self._y_mean)


class CircuitSMT:
    """Multi-output surrogate: one Kriging (smt) or RBF (scipy fallback)
    model per output dimension, matching CircuitGPR's fit/predict/
    evaluate contract for direct use in a per-model comparison table."""

    def __init__(self, input_dim: int, output_dim: int, fit_timeout_s: float = 30.0):
        self.input_dim = input_dim
        self.output_dim = output_dim
        self.models = []
        self.x_scaler = None
        self.is_fitted = False
        self.kept_cols_ = None  # set in fit(); indices surviving drop_degenerate_columns
        self.backend = 'smt' if _SMT else ('scipy_rbf' if _SCIPY_RBF else 'mean_fallback')
        # Hard wall-clock cap per-output KRG fit — see gpr_surrogate.py's
        # fit_with_wallclock_timeout docstring for why
        # _bound_smt_optimizer_iterations's iteration bound alone isn't a
        # sufficient guarantee (confirmed directly: even a maxfun=5-
        # bounded TNC run exceeded 60s at 1500 points x 31 features).
        self.fit_timeout_s = fit_timeout_s

        if not _SMT:
            if _SCIPY_RBF:
                print("[CircuitSMT] smt not available — using scipy "
                      "RBFInterpolator fallback")
            else:
                print("[CircuitSMT] neither smt nor scipy available — "
                      "using a constant-mean fallback")

    def _build_model(self):
        if _SMT:
            # By default KRG builds an exactly-interpolating correlation
            # matrix (equivalent to GPR's alpha=0) — any two training
            # rows close enough for the correlation matrix to be near-
            # singular (e.g. after collinear columns are dropped, only a
            # couple of numerically-close values remain in the sole
            # surviving dimension) sends its internal Cholesky
            # factorization into the same pathological retry loop as
            # sklearn's GaussianProcessRegressor without a nugget. This
            # is the Kriging analogue of CircuitGPR's alpha=1e-3.
            # n_start (default 10 -> ~12 total multistart optimizer runs,
            # each a repeated O(n^3) Cholesky-factorization likelihood
            # eval) is the dominant, directly-controllable cost driver for
            # a small/low-dim fit — confirmed against
            # smt/surrogate_models/krg_based/krg_based.py. 1 keeps the 2
            # fixed starting points (theta0, theta0_rand) and drops the
            # 10 LHS-sampled restarts, cutting fit time roughly 8-10x;
            # an acceptable accuracy trade for a few-hundred-point,
            # single/few-dimension (post collinear-column-drop) problem.
            # n_start bounds the number of RESTARTS, not the cost of any
            # single one — at higher input dimensionality (e.g. a
            # derivative-feature-augmented pipeline) each restart's own
            # TNC optimization can itself run unbounded (see
            # _bound_smt_optimizer_iterations's docstring), so that's
            # applied separately to the returned instance below.
            return _bound_smt_optimizer_iterations(
                KRG(print_global=False, nugget=1e-3, n_start=1))
        if _SCIPY_RBF:
            return _RBFFallback()
        return _RBFFallback()  # predict() degrades to the constant-mean path

    def fit(self, X: np.ndarray, Y: np.ndarray):
        X = np.array(X, dtype=np.float64)
        Y = np.array(Y, dtype=np.float64)
        if Y.ndim == 1:
            Y = Y.reshape(-1, 1)

        self.x_scaler = StandardScaler() if _SKLEARN else _SimpleScaler()
        X_scaled = self.x_scaler.fit_transform(X)
        # Kriging (smt's KRG) and RBFInterpolator are both kernel-matrix
        # methods with the SAME failure mode as CircuitGPR on collinear
        # inputs (e.g. several supply rails moving together across a
        # corner sweep) — a near-singular correlation matrix sends smt's
        # internal likelihood/Cholesky computation into the same
        # pathologically slow territory. Same guard, same reason.
        self.kept_cols_ = drop_degenerate_columns(X_scaled) if _SKLEARN \
            else np.arange(X_scaled.shape[1])
        if len(self.kept_cols_) < X_scaled.shape[1]:
            print(f"[CircuitSMT] dropped "
                  f"{X_scaled.shape[1] - len(self.kept_cols_)} near-"
                  f"constant/collinear input column(s) before fitting "
                  f"(a degenerate design matrix otherwise stalls the "
                  f"{self.backend} kernel computation)")
        X_scaled = X_scaled[:, self.kept_cols_]

        self.models = []
        for d in range(self.output_dim):
            model = self._build_model()
            y_d = Y[:, d]
            try:
                if _SMT:
                    model.set_training_values(X_scaled, y_d.reshape(-1, 1))
                    fit_with_wallclock_timeout(model.train, self.fit_timeout_s)
                else:
                    model.fit(X_scaled, y_d)
            except Exception as e:
                print(f"[CircuitSMT] fit failed for output {d}: {e} — "
                      f"falling back to constant-mean model")
                model = _RBFFallback()
                model._interp = None
                model._y_mean = float(np.mean(y_d))
            self.models.append(model)

        self.is_fitted = True

    def predict(self, X: np.ndarray, return_std: bool = True):
        X = np.array(X, dtype=np.float64)
        if not self.is_fitted:
            mean = np.zeros((len(X), self.output_dim))
            std = np.ones((len(X), self.output_dim))
            return mean, std

        X_scaled = self.x_scaler.transform(X)
        if self.kept_cols_ is not None:
            X_scaled = X_scaled[:, self.kept_cols_]
        means = []
        for model in self.models:
            try:
                if _SMT and hasattr(model, 'predict_values'):
                    mu = model.predict_values(X_scaled).ravel()
                else:
                    mu = np.asarray(model.predict(X_scaled)).ravel()
            except Exception:
                mu = np.zeros(len(X))
            means.append(mu)

        mean_arr = np.stack(means, axis=1)
        # Neither Kriging-without-variance-query nor the RBF fallback
        # expose a cheap per-sample uncertainty here; a flat placeholder
        # (matching CircuitGPR's own no-fit/failure fallback convention)
        # keeps the (mean, std) contract intact for callers that expect it.
        std_arr = np.ones_like(mean_arr) * 0.1
        return mean_arr, std_arr

    def evaluate(self, X: np.ndarray, Y: np.ndarray) -> float:
        """Return scalar MSE across all outputs — same contract as
        CircuitGPR.evaluate, used to populate a model-comparison table."""
        Y = np.array(Y, dtype=np.float64)
        if Y.ndim == 1:
            Y = Y.reshape(-1, 1)
        mean, _ = self.predict(X)
        return float(np.mean((mean - Y) ** 2))
