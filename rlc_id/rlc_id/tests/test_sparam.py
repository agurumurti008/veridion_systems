"""S-parameter wrapper (S->Z/Y conversion + delegation to Vector Fitting) and Laplace
analytical verifier (forward-model check, NOT a blind identifier) validation."""
import numpy as np
from scipy import signal
import pytest
from rlc_id.synth import series_rlc
from rlc_id.methods.sparam import SParameterIdentifier
from rlc_id.methods.era import ERAIdentifier
from rlc_id.methods.laplace_verify import LaplaceAnalyticVerifier


def _analytic_Z(ss, w):
    A, B, C, D = ss
    I = np.eye(A.shape[0])
    return np.array([(C @ np.linalg.solve(1j * wk * I - A, B) + D).item() for wk in w])


def test_sparam_roundtrip_recovers_poles():
    net = series_rlc(50.0, 1e-6, 1e-9)
    true_poles = np.sort_complex(np.linalg.eigvals(net.ss[0]))
    w = np.logspace(4, 9, 300)
    Z_true = _analytic_Z(net.ss, w)
    z0 = 50.0
    S_synth = (Z_true - z0) / (Z_true + z0)

    sp = SParameterIdentifier(z0=z0, param_type="Z", n_poles=2, n_iterations=10)
    sp.fit(w, None, S_synth, order=2)
    est_poles = np.sort_complex(sp.poles())
    rel_err = np.abs(est_poles - true_poles) / np.abs(true_poles)
    assert np.all(rel_err < 1e-6)
    assert sp.is_passive()


def test_sparam_predict_matches_z():
    net = series_rlc(50.0, 1e-6, 1e-9)
    w = np.logspace(4, 9, 300)
    Z_true = _analytic_Z(net.ss, w)
    z0 = 50.0
    S_synth = (Z_true - z0) / (Z_true + z0)
    sp = SParameterIdentifier(z0=z0, param_type="Z", n_poles=2, n_iterations=10)
    sp.fit(w, None, S_synth, order=2)
    Z_pred = sp.predict(None, w)
    assert SParameterIdentifier.fit_error(Z_true.real, Z_pred.real) < 1e-6


def test_sparam_to_spice_netlist_runs():
    net = series_rlc(50.0, 1e-6, 1e-9)
    w = np.logspace(4, 9, 300)
    Z_true = _analytic_Z(net.ss, w)
    S_synth = (Z_true - 50.0) / (Z_true + 50.0)
    sp = SParameterIdentifier(z0=50.0, n_poles=2, n_iterations=10)
    sp.fit(w, None, S_synth, order=2)
    assert ".end" in sp.to_spice_netlist()


def test_laplace_verifier_impulse_matches_ground_truth():
    """Uses the realistic finite-pulse ERA convention (see test_era.py) so residues
    have correct physical scale -- the verifier only reproduces what it's given."""
    net = series_rlc(50.0, 1e-6, 1e-9)
    alpha = 25e6
    t = np.linspace(0, 8 / alpha, 800)
    dt = t[1] - t[0]
    u = np.zeros_like(t)
    u[0] = 1.0 / dt
    y = net.simulate(t, u)
    era = ERAIdentifier(input_type="impulse")
    era.fit(t, u, y, order=2)

    verifier = LaplaceAnalyticVerifier(era._pz)
    result = verifier.cross_check(t, y, response_type="impulse")
    assert result["nrmse"] < 0.1


def test_laplace_verifier_step_matches_ground_truth():
    net = series_rlc(50.0, 1e-6, 1e-9)
    alpha = 25e6
    t = np.linspace(0, 8 / alpha, 800)
    dt = t[1] - t[0]
    u = np.zeros_like(t)
    u[0] = 1.0 / dt
    y = net.simulate(t, u)
    era = ERAIdentifier(input_type="impulse")
    era.fit(t, u, y, order=2)

    u_step = np.ones_like(t)
    y_step_true = net.simulate(t, u_step)
    verifier = LaplaceAnalyticVerifier(era._pz)
    result = verifier.cross_check(t, y_step_true, response_type="step")
    assert result["nrmse"] < 0.1


def test_laplace_verifier_frequency_response_exact():
    """Frequency response is a direct algebraic evaluation of the pole-residue
    model, so given a known-accurate model this should match to high precision."""
    net = series_rlc(50.0, 1e-6, 1e-9)
    A, B, C, D = net.ss
    w = np.logspace(4, 9, 300)
    Z_true = _analytic_Z(net.ss, w)

    from rlc_id.methods.vector_fitting import VectorFittingIdentifier
    vf = VectorFittingIdentifier(n_poles=2, n_iterations=10)
    vf.fit(w, None, Z_true, order=2)

    verifier = LaplaceAnalyticVerifier(vf._pz)
    H = verifier.frequency_response(w)
    assert np.max(np.abs(H - Z_true)) < 1e-6


def test_laplace_verifier_invalid_response_type_raises():
    net = series_rlc(50.0, 1e-6, 1e-9)
    from rlc_id.core.base import PoleZeroModel
    pz = PoleZeroModel(poles=np.array([-1.0]), residues=np.array([1.0]))
    verifier = LaplaceAnalyticVerifier(pz)
    with pytest.raises(ValueError):
        verifier.cross_check(np.linspace(0, 1, 10), np.zeros(10), response_type="bogus")
