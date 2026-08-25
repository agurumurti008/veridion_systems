"""
tests/test_extended.py  —  Extended tests for physics, analysis models, export
Run with:  pytest tests/ -v
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import math, json, tempfile
import pytest
import numpy as np

from analogml.core.physics import (
    mosfet_region, MOSFETRegion,
    ids_saturation, gm_saturation,
    thermal_noise_current, input_referred_noise_voltage,
    junction_temperature, hot_carrier_stress,
    nbti_degradation_factor, kcl_residual,
    validate_spec, SPEC_BOUNDS
)
from analogml.models.analysis_models import (
    ACAnalysisModel, NoiseAnalysisModel, ThermalAnalysisModel,
    ReliabilityAnalysisModel, PowerAnalysisModel,
    MultiAnalysisPredictor
)
from analogml.data.export import (
    export_predictions_csv, export_training_data_csv,
    model_report, print_report
)
from analogml.data   import SyntheticCircuitDataset
from analogml.models import AnalogMLModel


# ─────────────────────────────────────────────────────────────────────────────
# Physics tests
# ─────────────────────────────────────────────────────────────────────────────

class TestPhysics:
    def test_mosfet_sat(self):
        r = mosfet_region(vgs=0.9, vds=1.2, vth=0.5, device="nmos")
        assert r == MOSFETRegion.SATURATION

    def test_mosfet_linear(self):
        r = mosfet_region(vgs=0.9, vds=0.1, vth=0.5, device="nmos")
        assert r == MOSFETRegion.LINEAR

    def test_mosfet_off(self):
        r = mosfet_region(vgs=0.2, vds=1.0, vth=0.5, device="nmos")
        assert r == MOSFETRegion.OFF

    def test_mosfet_pmos(self):
        # PMOS: vgs=-0.9, vds=-1.0, vth=-0.5 → saturation
        r = mosfet_region(vgs=-0.9, vds=-1.0, vth=-0.5, device="pmos")
        assert r == MOSFETRegion.SATURATION

    def test_ids_positive(self):
        mu_n = 0.04; Cox = 8.6e-3/4e-9; W = 4e-6; L = 0.18e-6
        ids = ids_saturation(0.9, 0.5, mu_n, Cox, W, L)
        assert ids > 0

    def test_gm_formula(self):
        # gm = 2*Id/Vov
        ids = 50e-6; vov = 0.3
        gm  = gm_saturation(ids, vov)
        assert math.isclose(gm, 2*ids/vov, rel_tol=1e-6)

    def test_thermal_noise(self):
        gm = 1e-3
        Si = thermal_noise_current(gm)
        assert Si > 0
        # Si = 4kT(2/3)gm  ≈ 4*1.38e-23*300*(2/3)*1e-3
        expected = 4 * 1.38e-23 * 300 * (2/3) * gm
        assert math.isclose(Si, expected, rel_tol=1e-4)

    def test_input_noise_voltage(self):
        gm  = 2e-3
        Svn = input_referred_noise_voltage(gm)
        assert Svn > 0
        # Svn = sqrt(4kT*gamma/gm)
        expected = math.sqrt(4 * 1.38e-23 * 300 * (2/3) / gm)
        assert math.isclose(Svn, expected, rel_tol=1e-4)

    def test_junction_temperature(self):
        Tj = junction_temperature(P_diss=0.1, R_theta_ja=150, T_ambient=25)
        assert math.isclose(Tj, 25 + 0.1*150, rel_tol=1e-6)

    def test_hci_risk_clamp(self):
        assert 0 <= hot_carrier_stress(1.5, 0.9, 0.5, 1.8) <= 1.0
        assert 0 <= hot_carrier_stress(0.0, 0.0, 0.5, 1.8) <= 1.0

    def test_nbti_clamp(self):
        assert 0 <= nbti_degradation_factor(-1.5, 400) <= 1.0

    def test_kcl(self):
        res, ok = kcl_residual([1e-6, -0.5e-6, -0.5e-6], tol=1e-9)
        assert ok

    def test_spec_bounds_valid(self):
        ok, msg = validate_spec("gain_dB", 60.0)
        assert ok

    def test_spec_bounds_invalid(self):
        ok, msg = validate_spec("phase_margin_deg", 150.0)
        assert not ok

    def test_spec_bounds_unknown(self):
        ok, msg = validate_spec("unknown_spec", 999.0)
        assert ok  # unknown specs pass through


# ─────────────────────────────────────────────────────────────────────────────
# Analysis model tests
# ─────────────────────────────────────────────────────────────────────────────

class TestAnalysisModels:
    @pytest.fixture
    def sample_data(self):
        rng = np.random.default_rng(0)
        X   = rng.standard_normal((100, 10)).astype(np.float32)
        return X

    def test_ac_model(self, sample_data):
        X   = sample_data
        Y   = np.random.rand(100, 6).astype(np.float32) * 60 + 10
        m   = ACAnalysisModel()
        m.fit(X, Y)
        pred = m.predict(X[:5])
        assert pred.shape == (5, 6)

    def test_noise_model(self, sample_data):
        X   = sample_data
        Y   = np.random.rand(100, 5).astype(np.float32)
        m   = NoiseAnalysisModel()
        m.fit(X, Y)
        pred = m.predict(X[:3])
        assert pred.shape == (3, 5)

    def test_noise_spectrum(self):
        m   = NoiseAnalysisModel()
        f   = np.array([1e3, 10e3, 100e3, 1e6])
        S   = m.noise_spectrum(f, white_level=10.0, corner_freq=10e3)
        # At f=10kHz (=corner): S ≈ white * sqrt(2)
        assert math.isclose(float(S[1]), 10.0 * math.sqrt(2), rel_tol=0.01)

    def test_thermal_model(self, sample_data):
        X   = sample_data
        Y   = np.random.rand(100, 4).astype(np.float32) * 50 + 25
        m   = ThermalAnalysisModel()
        m.fit(X, Y)
        pred = m.predict(X[:2])
        assert pred.shape == (2, 4)

    def test_reliability_model(self, sample_data):
        X   = sample_data
        Y   = np.random.rand(100, 5).astype(np.float32)
        m   = ReliabilityAnalysisModel()
        m.fit(X, Y)
        pred = m.predict(X[:4])
        assert pred.shape == (4, 5)

    def test_power_model(self, sample_data):
        X   = sample_data
        Y   = np.random.rand(100, 5).astype(np.float32) * 100
        m   = PowerAnalysisModel()
        m.fit(X, Y)
        pred = m.predict(X[:6])
        assert pred.shape == (6, 5)

    def test_dynamic_power_formula(self):
        m  = PowerAnalysisModel()
        p  = m.dynamic_power(alpha=0.5, C_eff_fF=100, VDD=1.8, f_MHz=100)
        # P = 0.5 * 100e-15 * 1.8^2 * 100e6 * 1e6
        expected = 0.5 * 100e-15 * 1.8**2 * 100e6 * 1e6
        assert math.isclose(p, expected, rel_tol=1e-6)

    def test_multi_analysis_predictor(self, sample_data):
        X = sample_data
        Y_ac    = np.random.rand(100, 6).astype(np.float32)
        Y_noise = np.random.rand(100, 5).astype(np.float32)
        pred = MultiAnalysisPredictor(["ac","noise"])
        pred.fit_all(X, {"ac": Y_ac, "noise": Y_noise})
        assert set(pred.fitted_analyses()) == {"ac", "noise"}
        res = pred.predict_all(X[:3])
        assert "ac" in res and "noise" in res
        assert res["ac"].shape == (3, 6)

    def test_multi_partial_fit(self, sample_data):
        """Only fit 'ac', reliability should not be fitted."""
        X = sample_data
        pred = MultiAnalysisPredictor(["ac","reliability"])
        pred.fit_all(X, {"ac": np.random.rand(100, 6).astype(np.float32)})
        assert "ac" in pred.fitted_analyses()
        assert "reliability" not in pred.fitted_analyses()


# ─────────────────────────────────────────────────────────────────────────────
# Export tests
# ─────────────────────────────────────────────────────────────────────────────

class TestExport:
    def test_export_predictions_csv(self):
        X  = np.random.rand(20, 5).astype(np.float32)
        Yp = np.random.rand(20, 3).astype(np.float32)
        Yt = np.random.rand(20, 3).astype(np.float32)
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            path = export_predictions_csv(X, Yp, Yt, path=f.name)
        import csv as _csv
        with open(path) as fh:
            rows = list(_csv.DictReader(fh))
        assert len(rows) == 20
        assert "pred_y_0" in rows[0]
        assert "true_y_0" in rows[0]
        assert "err_pct_y_0" in rows[0]

    def test_export_training_data_csv(self):
        X  = np.random.rand(15, 4).astype(np.float32)
        Y  = np.random.rand(15, 2).astype(np.float32)
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            path = export_training_data_csv(X, Y, technology="90nm", path=f.name)
        import csv as _csv
        with open(path) as fh:
            rows = list(_csv.DictReader(fh))
        assert len(rows) == 15
        assert rows[0]["technology"] == "90nm"
        assert "x_0" in rows[0]
        assert "y_0" in rows[0]

    def test_model_report(self):
        ds = SyntheticCircuitDataset(seed=5)
        X, Y, _, yn = ds.generate("ota_5t", 50)
        m = AnalogMLModel(mode="fast", output_names=yn)
        m.fit(X[:40], Y[:40], epochs=5)
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            report = model_report(m, X[40:], Y[40:],
                                   output_names=yn, path=f.name)
        assert "mean_R2"     in report
        assert "output_metrics" in report
        assert len(report["output_metrics"]) == len(yn)
        # R2 should be a float (possibly negative for very small test)
        assert isinstance(report["mean_R2"], float)

    def test_report_keys(self):
        ds = SyntheticCircuitDataset(seed=6)
        X, Y, _, yn = ds.generate("ldo", 60)
        m = AnalogMLModel(mode="fast", output_names=yn)
        m.fit(X[:50], Y[:50], epochs=5)
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            report = model_report(m, X[50:], Y[50:],
                                   output_names=yn, path=f.name)
        for name in yn:
            assert name in report["output_metrics"]
            m_  = report["output_metrics"][name]
            assert set(m_.keys()) == {"R2","MAE","RMSE","MAPE_pct"}


# ─────────────────────────────────────────────────────────────────────────────
# GNN trainer smoke test
# ─────────────────────────────────────────────────────────────────────────────

class TestGNNTrainer:
    def test_embed_shape(self):
        from analogml.core.gnn_trainer import GNNTrainer
        trainer = GNNTrainer(node_feat_dim=15, embed_dim=32)
        X_n  = np.random.rand(7, 15).astype(np.float32)
        E    = np.array([[0,1,2],[1,2,3]], dtype=np.int64)
        emb  = trainer.embed(X_n, E)
        assert emb.shape == (32,)
