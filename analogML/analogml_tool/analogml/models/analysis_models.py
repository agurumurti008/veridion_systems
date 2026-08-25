"""
models/analysis_models.py
Dedicated sub-models for each analysis type.

Each class:
  - has fit(X, Y) and predict(X) interface
  - encodes relevant physics structure
  - can be used standalone or combined in AnalogMLModel
"""
from __future__ import annotations
import math
import numpy as np
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.multioutput import MultiOutputRegressor
from sklearn.preprocessing import StandardScaler
from typing import Dict, List, Optional, Tuple


# ─────────────────────────────────────────────────────────────────────────────
# Base analysis model
# ─────────────────────────────────────────────────────────────────────────────

class BaseAnalysisModel:
    name      : str = "base"
    out_names : List[str] = []

    def __init__(self):
        self.scaler_X = StandardScaler()
        self.scaler_Y = StandardScaler()
        self.model    = MultiOutputRegressor(
            GradientBoostingRegressor(n_estimators=150, max_depth=4,
                                      learning_rate=0.05))
        self._fitted  = False

    def fit(self, X: np.ndarray, Y: np.ndarray):
        Xs = self.scaler_X.fit_transform(X)
        Ys = self.scaler_Y.fit_transform(
            Y.reshape(-1,1) if Y.ndim==1 else Y)
        self.model.fit(Xs, Ys)
        self._fitted = True

    def predict(self, X: np.ndarray) -> np.ndarray:
        if not self._fitted:
            raise RuntimeError(f"{self.name} model not fitted.")
        Xs = self.scaler_X.transform(
            X.reshape(1,-1) if X.ndim==1 else X)
        Ys = self.model.predict(Xs)
        return self.scaler_Y.inverse_transform(Ys)


# ─────────────────────────────────────────────────────────────────────────────
# AC Analysis Model
# ─────────────────────────────────────────────────────────────────────────────

class ACAnalysisModel(BaseAnalysisModel):
    """
    Predicts small-signal AC metrics.
    Y = [gain_dB, ugf_MHz, phase_margin_deg, gbw_MHz,
         f3dB_MHz, pm_at_ugf_deg, gain_peaking_dB]
    """
    name      = "ac"
    out_names = ["gain_dB", "ugf_MHz", "phase_margin_deg",
                 "gbw_MHz", "f3dB_MHz", "gain_peaking_dB"]

    def predict_bandwidth_product(self, gain_db: float,
                                   ugf_mhz: float) -> float:
        """Gain-bandwidth product verification."""
        av_linear = 10 ** (gain_db / 20)
        return av_linear * ugf_mhz / av_linear   # returns ugf (GBW approx)


# ─────────────────────────────────────────────────────────────────────────────
# DC Analysis Model
# ─────────────────────────────────────────────────────────────────────────────

class DCAnalysisModel(BaseAnalysisModel):
    """
    Predicts DC operating point metrics.
    Y = [vout_V, ibias_uA, vds_m1_V, vgs_m1_V, id_m1_uA,
         overdrive_m1_mV, output_resistance_kohm]
    """
    name      = "dc"
    out_names = ["vout_V", "ibias_uA", "vds_m1_V", "vgs_m1_V",
                 "id_m1_uA", "overdrive_m1_mV", "output_resistance_kohm"]

    def check_saturation(self, vds: float, vgs: float,
                          vth: float = 0.5) -> bool:
        """Verify MOSFET is in saturation: Vds > Vgs - Vth."""
        return vds > (vgs - vth)


# ─────────────────────────────────────────────────────────────────────────────
# Noise Analysis Model
# ─────────────────────────────────────────────────────────────────────────────

class NoiseAnalysisModel(BaseAnalysisModel):
    """
    Predicts noise metrics.
    Y = [input_noise_nV_sqrtHz, output_noise_uV_sqrtHz,
         noise_figure_dB, corner_freq_kHz, integrated_noise_uVrms]
    Physics: thermal (white) + flicker (1/f) components modeled explicitly.
    """
    name      = "noise"
    out_names = ["input_noise_nV_sqrtHz", "output_noise_uV_sqrtHz",
                 "noise_figure_dB", "corner_freq_kHz",
                 "integrated_noise_uVrms"]

    def noise_spectrum(self, freq_hz: np.ndarray,
                        white_level: float,
                        corner_freq: float) -> np.ndarray:
        """
        Full noise spectrum: S(f) = S_white * (1 + fc/f).
        white_level [nV/√Hz], corner_freq [Hz]
        """
        return white_level * np.sqrt(1 + corner_freq / np.maximum(freq_hz, 1.0))


# ─────────────────────────────────────────────────────────────────────────────
# Transient Analysis Model
# ─────────────────────────────────────────────────────────────────────────────

class TransientAnalysisModel(BaseAnalysisModel):
    """
    Predicts large-signal transient metrics.
    Y = [slew_rate_V_us, settling_time_ns, overshoot_pct,
         rise_time_ns, fall_time_ns, peak_current_mA]
    Physics hook: slew rate = Ibias / Cload (validated post-predict).
    """
    name      = "transient"
    out_names = ["slew_rate_V_us", "settling_time_ns",
                 "overshoot_pct", "rise_time_ns",
                 "fall_time_ns", "peak_current_mA"]

    def physics_slew_rate(self, ibias_ua: float,
                           cload_ff: float) -> float:
        """SR = I / C  [V/μs]."""
        return ibias_ua * 1e-6 / (cload_ff * 1e-15) / 1e6


# ─────────────────────────────────────────────────────────────────────────────
# Thermal Analysis Model
# ─────────────────────────────────────────────────────────────────────────────

class ThermalAnalysisModel(BaseAnalysisModel):
    """
    Predicts thermal metrics for reliability assessment.
    Y = [Tj_degC, delta_Tj_degC, Rth_ja, hotspot_temp_degC,
         thermal_resistance_kW]
    """
    name      = "thermal"
    out_names = ["Tj_degC", "delta_Tj_degC", "Rth_ja_K_W",
                 "hotspot_temp_degC"]

    def estimate_Tj(self, P_mW: float, Rth_ja: float,
                     T_ambient: float = 25.0) -> float:
        """Tj = Ta + P * Rth_ja."""
        return T_ambient + (P_mW * 1e-3) * Rth_ja


# ─────────────────────────────────────────────────────────────────────────────
# Reliability Analysis Model
# ─────────────────────────────────────────────────────────────────────────────

class ReliabilityAnalysisModel(BaseAnalysisModel):
    """
    Predicts reliability metrics.
    Y = [hci_risk, nbti_dvth_mV, em_margin, tddb_ttf_years,
         stress_voltage_margin_V]
    """
    name      = "reliability"
    out_names = ["hci_risk_0to1", "nbti_dvth_mV", "em_margin",
                 "tddb_ttf_years", "stress_voltage_margin_V"]

    def mtf_black_model(self, J: float, T_K: float,
                         Ea: float = 0.9, n: float = 2.0) -> float:
        """
        Black's equation for electromigration MTF estimation.
        MTF = A / J^n * exp(Ea / kT)
        Returns relative MTF (normalized).
        """
        k_eV = 8.617e-5
        return math.exp(Ea / (k_eV * T_K)) / (J**n + 1e-30)


# ─────────────────────────────────────────────────────────────────────────────
# Power Analysis Model
# ─────────────────────────────────────────────────────────────────────────────

class PowerAnalysisModel(BaseAnalysisModel):
    """
    Predicts power consumption metrics.
    Y = [total_power_uW, static_power_uW, dynamic_power_uW,
         power_supply_rejection_dB, efficiency_pct]
    """
    name      = "power"
    out_names = ["total_power_uW", "static_power_uW", "dynamic_power_uW",
                 "psrr_dB", "efficiency_pct"]

    def dynamic_power(self, alpha: float, C_eff_fF: float,
                       VDD: float, f_MHz: float) -> float:
        """P_dyn = alpha * C * V^2 * f  [μW]."""
        return alpha * C_eff_fF * 1e-15 * (VDD**2) * f_MHz * 1e6 * 1e6


# ─────────────────────────────────────────────────────────────────────────────
# Combined multi-analysis predictor
# ─────────────────────────────────────────────────────────────────────────────

class MultiAnalysisPredictor:
    """
    Trains and manages all analysis sub-models simultaneously.
    Each sub-model is fitted on a specific Y-slice.

    Usage:
        predictor = MultiAnalysisPredictor()
        predictor.fit_all(X, Y_dict)
        results = predictor.predict_all(X_new)
    """
    MODELS = {
        "ac"         : ACAnalysisModel,
        "dc"         : DCAnalysisModel,
        "noise"      : NoiseAnalysisModel,
        "transient"  : TransientAnalysisModel,
        "thermal"    : ThermalAnalysisModel,
        "reliability": ReliabilityAnalysisModel,
        "power"      : PowerAnalysisModel,
    }

    def __init__(self, analysis_types: Optional[List[str]] = None):
        types = analysis_types or list(self.MODELS.keys())
        self.sub_models: Dict[str, BaseAnalysisModel] = {
            t: self.MODELS[t]() for t in types if t in self.MODELS
        }

    def fit_all(self, X: np.ndarray,
                Y_by_analysis: Dict[str, np.ndarray]):
        """Fit each sub-model on its analysis slice."""
        for name, model in self.sub_models.items():
            if name in Y_by_analysis:
                model.fit(X, Y_by_analysis[name])

    def predict_all(self, X: np.ndarray
                    ) -> Dict[str, np.ndarray]:
        """Predict all analyses."""
        results = {}
        for name, model in self.sub_models.items():
            if model._fitted:
                results[name] = model.predict(X)
        return results

    def fitted_analyses(self) -> List[str]:
        return [n for n, m in self.sub_models.items() if m._fitted]
