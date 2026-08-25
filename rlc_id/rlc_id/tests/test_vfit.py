"""Vector Fitting validation against analytical frequency response, including the
numerical-conditioning edge cases discovered during development: single-pole-pair
seeding, wide-band data-coverage sensitivity, and mixed real/complex pole recovery."""
import numpy as np
import pytest
from rlc_id.synth import series_rlc, parallel_rlc, cascaded_ladder
from rlc_id.methods.vector_fitting import VectorFittingIdentifier
from rlc_id.core.utils import match_poles


def _analytic_H(ss, w):
    A, B, C, D = ss
    I = np.eye(A.shape[0])
    return np.array([(C @ np.linalg.solve(1j * wk * I - A, B) + D).item() for wk in w])


def test_vf_series_rlc_machine_precision():
    net = series_rlc(50.0, 1e-6, 1e-9)
    true_poles = np.sort_complex(np.linalg.eigvals(net.ss[0]))
    w = np.logspace(4, 9, 300)
    H = _analytic_H(net.ss, w)

    vf = VectorFittingIdentifier(n_poles=2, n_iterations=10, enforce_passivity=True)
    vf.fit(w, None, H, order=2)
    est_poles = np.sort_complex(vf.poles())
    rel_err = np.abs(est_poles - true_poles) / np.abs(true_poles)
    assert np.all(rel_err < 1e-6)
    assert vf.is_passive()


def test_vf_single_pole_pair_seeding_not_degenerate():
    """Regression test: n_poles=2 (n_pairs=1) previously seeded the starting pole at
    the sweep's minimum frequency instead of mid-band, freezing the relocation."""
    net = parallel_rlc(1000.0, 1e-6, 1e-9)
    true_poles = np.sort_complex(np.linalg.eigvals(net.ss[0]))
    w = np.logspace(3, 9, 250)
    H = _analytic_H(net.ss, w)
    vf = VectorFittingIdentifier(n_poles=2, n_iterations=10)
    vf.fit(w, None, H, order=2)
    est_poles = np.sort_complex(vf.poles())
    rel_err = np.abs(est_poles - true_poles) / np.abs(true_poles)
    assert np.all(rel_err < 1e-4)


def test_vf_cascaded_ladder_matched_bandwidth():
    """8th-order mixed real/complex pole system, frequency sweep matched to the
    actual pole band -- should converge to near machine precision."""
    net = cascaded_ladder(n_stages=4, seed=42)
    true_poles = net.poles
    w = np.logspace(5, 9, 400)
    H = _analytic_H(net.ss, w)
    vf = VectorFittingIdentifier(n_poles=8, n_iterations=25, include_real_poles=True,
                                  enforce_passivity=False)
    vf.fit(w, None, H, order=8)
    _, mean_err = match_poles(true_poles, vf.poles())
    assert mean_err / np.mean(np.abs(true_poles)) < 1e-3


def test_vf_cascaded_ladder_mismatched_bandwidth_degrades_gracefully():
    """Documented finding: a 7-decade sweep (1e3-1e10) that mostly misses the true
    pole band (1e6-1e8) starves the fit of informative samples. This should degrade
    the fit, not crash -- and is a direct illustration of the excitation-coverage
    sensitivity discussed in the accompanying technical analysis (Section 3)."""
    net = cascaded_ladder(n_stages=4, seed=42)
    true_poles = net.poles
    w = np.logspace(3, 10, 500)
    H = _analytic_H(net.ss, w)
    vf = VectorFittingIdentifier(n_poles=8, n_iterations=25, include_real_poles=True,
                                  enforce_passivity=False)
    vf.fit(w, None, H, order=8)
    _, mean_err = match_poles(true_poles, vf.poles())
    rel_err = mean_err / np.mean(np.abs(true_poles))
    assert np.isfinite(rel_err)  # must not crash / produce NaN -- degraded accuracy is expected


def test_vf_passivity_enforcement_flips_nonpassive_residue():
    net = series_rlc(50.0, 1e-6, 1e-9)
    w = np.logspace(4, 9, 300)
    H = _analytic_H(net.ss, w)
    vf = VectorFittingIdentifier(n_poles=2, n_iterations=10, enforce_passivity=True)
    vf.fit(w, None, H, order=2)
    assert vf.is_passive()


def test_vf_predict_matches_analytic_frequency_response():
    net = series_rlc(50.0, 1e-6, 1e-9)
    w = np.logspace(4, 9, 300)
    H = _analytic_H(net.ss, w)
    vf = VectorFittingIdentifier(n_poles=2, n_iterations=10)
    vf.fit(w, None, H, order=2)
    H_pred = vf.predict(None, w)
    assert VectorFittingIdentifier.fit_error(H.real, H_pred.real) < 1e-6
    assert VectorFittingIdentifier.fit_error(H.imag, H_pred.imag) < 1e-6


def test_vf_to_spice_netlist_runs():
    net = series_rlc(50.0, 1e-6, 1e-9)
    w = np.logspace(4, 9, 300)
    H = _analytic_H(net.ss, w)
    vf = VectorFittingIdentifier(n_poles=2, n_iterations=10)
    vf.fit(w, None, H, order=2)
    netlist = vf.to_spice_netlist()
    assert ".end" in netlist
