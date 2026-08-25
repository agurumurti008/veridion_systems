"""
tests/test_analogml.py  —  Unit + integration tests
Run with:  pytest tests/ -v
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import math
import pytest
import numpy as np
import tempfile

from analogml.parsers import SpiceParser, SpectreParser, _parse_value
from analogml.core    import CircuitGraph, FeatureExtractor, build_dataset
from analogml.models  import AnalogMLModel, TechTransferAgent
from analogml.data    import SyntheticCircuitDataset, MultiFidelityDataset


# ─────────────────────────────────────────────────────────────────────────────
# Parser tests
# ─────────────────────────────────────────────────────────────────────────────

SIMPLE_SPICE = """\
* Simple OTA
.subckt ota INP INN OUT VDD VSS
M1 net1 INP net3 VSS nmos_18 W=4u L=0.18u
M2 net2 INN net3 VSS nmos_18 W=4u L=0.18u
M3 net1 net1 VDD VDD pmos_18 W=8u L=0.18u
M4 net2 net1 VDD VDD pmos_18 W=8u L=0.18u
M5 net3 VBIAS VSS VSS nmos_18 W=8u L=0.36u
Cc net2 OUT 500f
Cload OUT VSS 2p
.ends
.op
.ac DEC 100 1 1G
.end
"""

class TestParsers:
    def test_parse_value_suffix(self):
        assert math.isclose(_parse_value("500f"), 500e-15)
        assert math.isclose(_parse_value("2p"),   2e-12)
        assert math.isclose(_parse_value("10k"),  10e3)
        assert math.isclose(_parse_value("1meg"), 1e6)
        assert math.isclose(_parse_value("0.18u"),0.18e-6)

    def test_spice_parse_components(self):
        p = SpiceParser()
        nl = p.parse_text(SIMPLE_SPICE, technology="180nm")
        assert nl.subckt_name == "ota"
        # Should find 5 MOSFETs + 2 caps
        types = [c.comp_type for c in nl.components]
        assert types.count("nmos") == 3
        assert types.count("pmos") == 2
        assert types.count("capacitor") == 2

    def test_spice_parse_pins(self):
        p = SpiceParser()
        nl = p.parse_text(SIMPLE_SPICE, technology="180nm")
        pin_names = [pin.name for pin in nl.pins]
        assert "INP" in pin_names
        assert "VDD" in pin_names

    def test_spice_parse_analyses(self):
        p = SpiceParser()
        nl = p.parse_text(SIMPLE_SPICE)
        assert "dc_op" in nl.analyses
        assert "ac"    in nl.analyses

    def test_canonical_ids(self):
        p = SpiceParser()
        nl = p.parse_text(SIMPLE_SPICE)
        ids = [c.canonical_id for c in nl.components]
        assert "nmos_0" in ids
        assert "pmos_0" in ids

    def test_spectre_parser(self):
        spectre_text = """\
subckt ota (INP INN OUT VDD VSS)
M1 (net1 INP net3 VSS) nmos_18 W=4u L=0.18u
M2 (net2 INN net3 VSS) nmos_18 W=4u L=0.18u
ends
"""
        p = SpectreParser()
        nl = p.parse_text(spectre_text, technology="90nm")
        assert nl.technology == "90nm"
        assert len(nl.components) == 2


# ─────────────────────────────────────────────────────────────────────────────
# CircuitGraph tests
# ─────────────────────────────────────────────────────────────────────────────

class TestCircuitGraph:
    @pytest.fixture
    def graph(self):
        p = SpiceParser()
        nl = p.parse_text(SIMPLE_SPICE, technology="180nm")
        return CircuitGraph.from_netlist(nl)

    def test_node_count(self, graph):
        assert len(graph.G.nodes) == 7   # 5 FETs + 2 caps

    def test_edges_exist(self, graph):
        assert len(graph.G.edges) > 0

    def test_feature_matrix(self, graph):
        X, E = graph.to_feature_matrix()
        assert X.ndim == 2
        assert X.shape[1] == 15   # 8 type + 5 size + 2 structural
        assert E.shape[0] == 2

    def test_structural_fingerprint(self, graph):
        fp = graph.structural_fingerprint()
        assert fp.shape == (64,)
        assert not np.any(np.isnan(fp))

    def test_name_independence(self):
        """Same topology, different instance names → identical fingerprint."""
        sp1 = """\
.subckt c1 A B VDD VSS
MA A A VDD VDD pmos W=4u L=0.18u
MB B B VSS VSS nmos W=4u L=0.18u
.ends
"""
        sp2 = """\
.subckt c2 X Y PWR GND
Qfoo X X PWR PWR pmos W=4u L=0.18u
Qbar Y Y GND GND nmos W=4u L=0.18u
.ends
"""
        p = SpiceParser()
        g1 = CircuitGraph.from_netlist(p.parse_text(sp1))
        g2 = CircuitGraph.from_netlist(p.parse_text(sp2))
        fp1 = g1.structural_fingerprint()
        fp2 = g2.structural_fingerprint()
        # type counts must match even if net names differ
        assert np.allclose(fp1[:8], fp2[:8], atol=0.01)


# ─────────────────────────────────────────────────────────────────────────────
# FeatureExtractor tests
# ─────────────────────────────────────────────────────────────────────────────

class TestFeatureExtractor:
    def test_feature_dim(self):
        p = SpiceParser()
        nl = p.parse_text(SIMPLE_SPICE)
        g  = CircuitGraph.from_netlist(nl)
        fe = FeatureExtractor()
        x  = fe.extract(g)
        assert x.shape == (FeatureExtractor.FEATURE_DIM,)

    def test_tech_sensitivity(self):
        p = SpiceParser()
        nl180 = p.parse_text(SIMPLE_SPICE, technology="180nm")
        nl90  = p.parse_text(SIMPLE_SPICE, technology="90nm")
        fe = FeatureExtractor()
        x180 = fe.extract(CircuitGraph.from_netlist(nl180))
        x90  = fe.extract(CircuitGraph.from_netlist(nl90))
        # tech encoding must differ
        assert not np.allclose(x180[:7], x90[:7])


# ─────────────────────────────────────────────────────────────────────────────
# Synthetic data tests
# ─────────────────────────────────────────────────────────────────────────────

class TestSyntheticData:
    @pytest.mark.parametrize("topo", SyntheticCircuitDataset.TOPOLOGIES)
    def test_topologies(self, topo):
        ds = SyntheticCircuitDataset(seed=0)
        X, Y, xn, yn = ds.generate(topo, n_samples=20)
        assert X.shape[0] == 20
        assert Y.shape[0] == 20
        assert not np.any(np.isnan(Y))

    def test_physics_sanity_ota(self):
        """Gain should be positive, PM in 0-90 for OTA."""
        ds = SyntheticCircuitDataset(seed=1)
        _, Y, _, yn = ds.generate("ota_5t", n_samples=100)
        gain_idx = yn.index("gain_dB")
        pm_idx   = yn.index("phase_margin_deg")
        assert np.all(Y[:, gain_idx] > 0)
        assert np.all(Y[:, pm_idx]   > 0)
        assert np.all(Y[:, pm_idx]   < 90)


# ─────────────────────────────────────────────────────────────────────────────
# Model tests
# ─────────────────────────────────────────────────────────────────────────────

class TestAnalogMLModel:
    @pytest.fixture
    def trained_model(self):
        ds = SyntheticCircuitDataset(seed=42)
        X, Y, _, yn = ds.generate("ota_5t", n_samples=100)
        m = AnalogMLModel(mode="fast", output_names=yn)
        m.fit(X[:80], Y[:80], epochs=30)
        return m, X[80:], Y[80:], yn

    def test_predict_shape(self, trained_model):
        m, X_te, Y_te, yn = trained_model
        Y_pred = m.predict(X_te)
        assert Y_pred.shape == Y_te.shape

    def test_predict_single_row(self, trained_model):
        m, X_te, _, yn = trained_model
        y = m.predict(X_te[0])
        assert y.shape == (1, len(yn))

    def test_predict_uncertainty(self, trained_model):
        m, X_te, _, _ = trained_model
        ymean, ystd = m.predict_with_uncertainty(X_te[:5])
        assert ymean.shape == ystd.shape
        assert np.all(ystd >= 0)

    def test_r2_above_threshold(self, trained_model):
        m, X_te, Y_te, _ = trained_model
        Y_pred = m.predict(X_te)
        for i in range(Y_te.shape[1]):
            r2 = float(np.corrcoef(Y_te[:,i], Y_pred[:,i])[0,1]**2)
            assert r2 > 0.5, f"R² too low for output {i}: {r2:.3f}"

    def test_recommend_sizes(self, trained_model):
        m, X_te, _, yn = trained_model
        target = {yn[0]: 60.0, yn[2]: 55.0}
        x_best = m.recommend_sizes(target, X_candidates=X_te)
        assert x_best.shape == X_te.shape[1:]

    def test_save_load(self, trained_model):
        m, X_te, Y_te, _ = trained_model
        with tempfile.TemporaryDirectory() as tmpdir:
            m.save(tmpdir)
            m2 = AnalogMLModel.load(tmpdir)
            y1 = m.predict(X_te[:3])
            y2 = m2.predict(X_te[:3])
            assert np.allclose(y1, y2, rtol=1e-3)


# ─────────────────────────────────────────────────────────────────────────────
# Tech transfer tests
# ─────────────────────────────────────────────────────────────────────────────

class TestTechTransfer:
    def test_transfer_shape(self):
        ds = SyntheticCircuitDataset(seed=3)
        X180, _, _, _ = ds.generate("ota_5t", 80, "180nm")
        X90,  _, _, _ = ds.generate("ota_5t", 80, "90nm")
        agent = TechTransferAgent("180nm", "90nm")
        agent.fit(X180, X90)
        x_out = agent.transfer(X180[0])
        assert x_out.shape == (1, X180.shape[1])

    def test_scaling_rules(self):
        agent = TechTransferAgent("180nm", "90nm")
        rules = agent.tech_scaling_rules()
        assert rules["L_ratio"] == pytest.approx(0.5)
        assert rules["fT_ratio"] == pytest.approx(2.0)


# ─────────────────────────────────────────────────────────────────────────────
# Integration test: full pipeline
# ─────────────────────────────────────────────────────────────────────────────

class TestIntegration:
    def test_full_pipeline(self):
        """Parse netlist → graph → features → train → predict."""
        netlist_text = SIMPLE_SPICE
        p  = SpiceParser()
        nl = p.parse_text(netlist_text, technology="180nm")
        g  = CircuitGraph.from_netlist(nl)
        fe = FeatureExtractor()
        x  = fe.extract(g)
        assert x.shape == (117,)

        # fake simulation results
        sim = {"gain_dB": 58.3, "ugf_MHz": 12.1, "phase_margin_deg": 62.0}
        X_np = x.reshape(1, -1)
        Y_np = np.array([[58.3, 12.1, 62.0]])

        m = AnalogMLModel(mode="fast",
                          output_names=list(sim.keys()))
        # need a few more rows for sklearn
        X_np = np.tile(X_np, (20, 1)) + np.random.randn(20, 117)*0.01
        Y_np = np.tile(Y_np, (20, 1)) + np.random.randn(20, 3)*0.1
        m.fit(X_np, Y_np, epochs=10)
        y = m.predict(x)
        assert y.shape == (1, 3)
