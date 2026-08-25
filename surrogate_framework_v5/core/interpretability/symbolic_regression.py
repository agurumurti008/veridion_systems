"""
core/interpretability/symbolic_regression.py
PySR wrapper + pole-zero extractor + SHAP + sensitivity analysis.
"""
import numpy as np
import math
from typing import Dict, List, Optional

try:
    from pysr import PySRRegressor
    _PYSR = True
except ImportError:
    _PYSR = False

try:
    import shap as _shap_lib
    _SHAP = True
except ImportError:
    _SHAP = False


KNOWN_FORMULAS = {
    'GBW':        'Gm / (2 * pi * CL)',
    'SR':         'I_tail / CL',
    'PM_approx':  '90 - arctan(GBW / fp2) * 180 / pi',
    'PSRR':       '20 * log10(A_diff / A_cm)',
    'noise_floor': 'sqrt(kT / C)',
}


class CircuitSymbolicExtractor:
    """Extract interpretable equations from black-box surrogate predictions."""

    def __init__(self, feature_names: List[str], output_names: List[str]):
        self.feature_names = feature_names
        self.output_names = output_names
        self.results: Dict[str, dict] = {}

    def extract(self, X: np.ndarray, Y: np.ndarray,
                output_idx: int = 0,
                max_complexity: int = 12,
                n_iterations: int = 40) -> dict:
        """Extract symbolic equation for one output."""
        X = np.array(X, dtype=np.float64)
        Y = np.array(Y, dtype=np.float64)
        if Y.ndim > 1:
            y = Y[:, output_idx]
        else:
            y = Y

        out_name = (self.output_names[output_idx]
                    if output_idx < len(self.output_names) else f'y{output_idx}')

        # A NaN/Inf feature or target column (e.g. an unresolved
        # --blut_output_signals name silently NaN-filled upstream) makes
        # every downstream fit degenerate: PySR rejects it and raises
        # (previously swallowed below with zero logging), and
        # _linear_fallback's lstsq doesn't raise on NaN — it returns an
        # all-NaN solution that `abs(c) > 1e-10` (always False for NaN)
        # silently collapses to the literal equation string "0" with
        # r2=NaN. Failing loudly here, with the offending output named,
        # turns a silently-wrong embedded equation into an actionable
        # error instead.
        if np.isnan(X).any() or np.isnan(y).any():
            raise ValueError(
                f"CircuitSymbolicExtractor.extract: NaN in input data for "
                f"output '{out_name}' — check that every requested input/"
                f"output signal name exactly matches the resolved signal "
                f"map (a typo silently NaN-fills that column upstream in "
                f"Phase2SimAugmented.build_dataset_from_blut)."
            )

        if _PYSR:
            try:
                model = PySRRegressor(
                    niterations=n_iterations,
                    maxsize=max_complexity,
                    binary_operators=['+', '*', '/', '-', 'pow'],
                    unary_operators=['log', 'exp', 'sqrt'],
                    # Without an explicit constraint PySR silently defaults
                    # 'pow' to (-1, -1) — unlimited complexity on BOTH the
                    # base and the exponent — which can search up deeply
                    # nested exponents (e.g. base^(complex sub-expression)),
                    # bad for an equation meant to be embedded as a compact
                    # Verilog-A expression. (-1, 1) keeps the base
                    # arbitrary-complexity but restricts the exponent to a
                    # single constant/variable — also what silences PySR's
                    # own "you have not set up constraints" warning.
                    constraints={'pow': (-1, 1)},
                    # Circuit V-I/V-V relationships are mostly smooth,
                    # differentiable, low-order polynomial-ish forms;
                    # exp/pow/log/sqrt terms produce numerically abrupt
                    # behavior when embedded as a Verilog-A contribution
                    # statement (e.g. near a pole/singularity or a fast-
                    # growing power). This doesn't forbid them — a real
                    # exponential/log relationship still wins when it
                    # clearly fits better — it just makes each use "cost"
                    # more of the fixed maxsize budget than a plain
                    # +/-/* term, so PySR reaches for them only when they
                    # earn their keep.
                    complexity_of_operators={
                        'pow': 4, 'exp': 3, 'log': 3, 'sqrt': 2,
                        '+': 1, '-': 1, '*': 1, '/': 1,
                    },
                    verbosity=0,
                )
                model.fit(X, y, variable_names=self.feature_names)
                best = model.get_best()
                equation = str(best['equation'])
                y_pred = model.predict(X)
                r2 = self._r2(y, y_pred)
            except Exception as e:
                print(f"[CircuitSymbolicExtractor] PySR fit failed for "
                      f"output '{out_name}': {e} — falling back to a "
                      f"linear fit.")
                equation, r2 = self._linear_fallback(X, y)
        else:
            equation, r2 = self._linear_fallback(X, y)

        validity = self._check_known_formula(equation, out_name)

        result = {
            'equation': equation,
            'r2': r2,
            'validity': validity,
            'output': out_name,
        }
        self.results[out_name] = result
        return result

    def extract_all(self, X: np.ndarray, Y: np.ndarray) -> Dict[str, dict]:
        """Extract equations for all outputs."""
        X = np.array(X, dtype=np.float64)
        Y = np.array(Y, dtype=np.float64)
        if Y.ndim == 1:
            Y = Y.reshape(-1, 1)

        results = {}
        for i in range(min(Y.shape[1], len(self.output_names))):
            try:
                result = self.extract(X, Y, output_idx=i)
                results[self.output_names[i]] = result
            except Exception as e:
                results[self.output_names[i]] = {
                    'equation': f'f(x) (extraction failed: {e})',
                    'r2': 0.0,
                    'validity': 'unknown',
                    'output': self.output_names[i],
                }
        self.results = results
        return results

    def _linear_fallback(self, X: np.ndarray, y: np.ndarray):
        """Linear regression fallback when PySR is unavailable."""
        X_b = np.hstack([X, np.ones((len(X), 1))])
        try:
            sol, _, _, _ = np.linalg.lstsq(X_b, y, rcond=None)
        except Exception:
            sol = np.zeros(X.shape[1] + 1)

        coeffs = sol[:-1]
        intercept = sol[-1]

        terms = []
        for i, (c, name) in enumerate(zip(coeffs, self.feature_names)):
            if abs(c) > 1e-10:
                terms.append(f"{c:.4g}*{name}")
        if abs(intercept) > 1e-10:
            terms.append(f"{intercept:.4g}")
        equation = ' + '.join(terms) if terms else '0'

        y_pred = X_b @ sol
        r2 = self._r2(y, y_pred)
        return equation, r2

    def _r2(self, y_true: np.ndarray, y_pred: np.ndarray) -> float:
        ss_res = np.sum((y_true - y_pred) ** 2)
        ss_tot = np.sum((y_true - y_true.mean()) ** 2)
        if ss_tot < 1e-30:
            return 1.0
        return float(1 - ss_res / ss_tot)

    def _check_known_formula(self, equation: str, out_name: str) -> str:
        """Check match quality against known circuit formulas."""
        known = KNOWN_FORMULAS.get(out_name, '')
        if not known:
            return 'no_reference'

        # Simple token overlap check
        eq_tokens = set(equation.lower().replace('*', ' ').split())
        known_tokens = set(known.lower().replace('*', ' ').split())
        overlap = len(eq_tokens & known_tokens) / max(len(known_tokens), 1)

        if overlap > 0.6:
            return f'good_match ({overlap:.0%} token overlap)'
        elif overlap > 0.3:
            return f'partial_match ({overlap:.0%} token overlap)'
        else:
            return f'low_match ({overlap:.0%} token overlap)'

    def to_veriloga_functions(self) -> str:
        """Generate Verilog-A function stubs with equation comments."""
        lines = ['// Auto-extracted symbolic equations']
        lines.append('// Generated by CircuitSymbolicExtractor')
        lines.append('')
        for name, res in self.results.items():
            r2 = res.get('r2', 0.0)
            eq = res.get('equation', 'unknown')
            lines.append(f'// {name}: {eq}  (R²={r2:.3f})')
            safe = name.replace(' ', '_').replace('.', '_')
            lines.append(f'analog function real compute_{safe};')
            lines.append(f'    input x;')
            lines.append(f'    real x;')
            lines.append(f'    begin')
            lines.append(f'        compute_{safe} = 0;  // TODO: implement {eq}')
            lines.append(f'    end')
            lines.append(f'endfunction')
            lines.append('')
        return '\n'.join(lines)

    def sensitivity_report(self, X: np.ndarray) -> Dict[str, Dict[str, float]]:
        """Numerical Jacobian sensitivity (output → feature → sensitivity)."""
        X = np.array(X, dtype=np.float64)
        report = {}

        for out_name, res in self.results.items():
            eq = res.get('equation', '')
            sensitivities = {}
            for i, fname in enumerate(self.feature_names):
                # Numerical Jacobian: perturb each feature
                eps = 1e-5 * (np.abs(X[:, i]).mean() + 1e-10)
                X_up = X.copy()
                X_up[:, i] += eps
                X_dn = X.copy()
                X_dn[:, i] -= eps

                # Use linear eval
                X_b = np.hstack([X, np.ones((len(X), 1))])
                X_up_b = np.hstack([X_up, np.ones((len(X_up), 1))])
                X_dn_b = np.hstack([X_dn, np.ones((len(X_dn), 1))])

                try:
                    sol, _, _, _ = np.linalg.lstsq(X_b, np.ones(len(X)), rcond=None)
                    dy = (X_up_b @ sol - X_dn_b @ sol) / (2 * eps)
                    sensitivities[fname] = float(np.abs(dy).mean())
                except Exception:
                    sensitivities[fname] = 0.0

            report[out_name] = sensitivities
        return report


class PoleZeroExtractor:
    """Extract pole-zero information from AC frequency response curves."""

    @staticmethod
    def extract_from_ac_curve(freq: np.ndarray,
                               magnitude_db: np.ndarray) -> dict:
        """
        Extract dominant pole fp1, unity-gain frequency, rolloff slope, DC gain.
        """
        freq = np.array(freq, dtype=np.float64)
        mag = np.array(magnitude_db, dtype=np.float64)

        if len(freq) == 0 or len(mag) == 0:
            return {'fp1': 0.0, 'fug': 0.0, 'dc_gain_db': 0.0, 'slope_dbdec': -20.0}

        dc_gain_db = float(mag[0])

        # fp1: first −3 dB from DC gain
        threshold = dc_gain_db - 3.0
        fp1 = float(freq[-1])
        for i in range(1, len(mag)):
            if mag[i] <= threshold:
                # Linear interpolation
                f1, f2 = freq[i - 1], freq[i]
                m1, m2 = mag[i - 1], mag[i]
                if abs(m2 - m1) > 1e-10:
                    t = (threshold - m1) / (m2 - m1)
                    fp1 = float(f1 + t * (f2 - f1))
                else:
                    fp1 = float(f1)
                break

        # Unity-gain: first zero crossing (0 dB)
        fug = float(freq[-1])
        for i in range(1, len(mag)):
            if mag[i] <= 0.0 and mag[i - 1] > 0.0:
                f1, f2 = freq[i - 1], freq[i]
                m1, m2 = mag[i - 1], mag[i]
                if abs(m2 - m1) > 1e-10:
                    t = (0.0 - m1) / (m2 - m1)
                    fug = float(f1 + t * (f2 - f1))
                else:
                    fug = float(f1)
                break

        # Rolloff slope: dB/decade between fp1 and fp1×10
        f_upper = fp1 * 10
        idx_upper = np.searchsorted(freq, f_upper)
        if idx_upper >= len(freq):
            idx_upper = len(freq) - 1
        idx_lower = max(0, np.searchsorted(freq, fp1) - 1)

        if idx_upper > idx_lower and freq[idx_upper] > freq[idx_lower]:
            decades = math.log10(freq[idx_upper] / (freq[idx_lower] + 1e-30))
            db_change = mag[idx_upper] - mag[idx_lower]
            slope = float(db_change / max(decades, 1e-10))
        else:
            slope = -20.0  # typical single-pole rolloff

        return {
            'fp1': fp1,
            'fug': fug,
            'dc_gain_db': dc_gain_db,
            'slope_dbdec': slope,
        }


def shap_attribution(model_predict_fn, X: np.ndarray,
                     n_background: int = 50):
    """
    Compute SHAP values if shap is installed; returns None otherwise.
    """
    if not _SHAP:
        print("[SHAP] shap not installed — skipping attribution. "
              "Install with: pip install shap")
        return None

    X = np.array(X, dtype=np.float64)
    background = X[:n_background]
    explainer = _shap_lib.KernelExplainer(model_predict_fn, background)
    try:
        shap_values = explainer.shap_values(X[:min(20, len(X))], silent=True)
        return shap_values
    except Exception as e:
        print(f"[SHAP] Attribution failed: {e}")
        return None
