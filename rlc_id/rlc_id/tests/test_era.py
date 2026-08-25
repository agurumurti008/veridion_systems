"""ERA validation: exact recovery from analytic impulse response, degradation
under the practical finite-pulse approximation, and noise robustness."""
import numpy as np
from scipy import signal
import pytest
from rlc_id.synth import series_rlc, parallel_rlc
from rlc_id.methods.era import ERAIdentifier


def test_era_exact_impulse_response_series_rlc():
    """Given scipy's exact analytic impulse response (no finite-pulse approx error),
    ERA should recover poles to near machine precision."""
    net = series_rlc(50.0, 1e-6, 1e-9)
    true_poles = np.sort_complex(np.linalg.eigvals(net.ss[0]))
    alpha = 25e6
    t = np.linspace(0, 8 / alpha, 800)
    sys = signal.StateSpace(*net.ss)
    _, y = signal.impulse(sys, T=t)
    u = np.zeros_like(t)
    u[0] = 1.0

    era = ERAIdentifier(input_type="impulse", svd_rel_threshold=1e-6)
    era.fit(t, u, y, order=2)
    est_poles = np.sort_complex(era.poles())
    rel_err = np.abs(est_poles - true_poles) / np.abs(true_poles)
    assert np.all(rel_err < 1e-6)


def test_era_finite_pulse_practical_approximation():
    """Realistic case: impulse approximated by a single narrow finite-height sample
    (as any real excitation must be). Documents the expected accuracy degradation
    from a non-ideal Dirac approximation -- looser tolerance by design."""
    net = series_rlc(50.0, 1e-6, 1e-9)
    true_poles = np.sort_complex(np.linalg.eigvals(net.ss[0]))
    alpha = 25e6
    t = np.linspace(0, 8 / alpha, 800)
    dt = t[1] - t[0]
    u = np.zeros_like(t)
    u[0] = 1.0 / dt
    y = net.simulate(t, u)

    era = ERAIdentifier(input_type="impulse", svd_rel_threshold=1e-6)
    era.fit(t, u, y, order=2)
    est_poles = np.sort_complex(era.poles())
    rel_err = np.abs(est_poles - true_poles) / np.abs(true_poles)
    assert np.all(rel_err < 0.15)  # loose: finite-pulse approximation error is expected


def test_era_step_input_type_uses_differentiation():
    net = parallel_rlc(1000.0, 1e-6, 1e-9)
    true_poles = np.sort_complex(np.linalg.eigvals(net.ss[0]))
    alpha = 1 / (2 * 1000.0 * 1e-9)
    t = np.linspace(0, 10 / alpha, 1000)
    u = np.ones_like(t)
    y = net.simulate(t, u)

    era = ERAIdentifier(input_type="step", svd_rel_threshold=1e-6)
    era.fit(t, u, y, order=2)
    est_poles = np.sort_complex(era.poles())
    rel_err = np.abs(est_poles - true_poles) / np.abs(true_poles)
    assert np.all(rel_err < 0.1)


def test_era_order_selection_below_data_order():
    """SVD-knee order selection should not wildly overshoot the true order (2) for
    a clean series RLC impulse response."""
    net = series_rlc(50.0, 1e-6, 1e-9)
    t = np.linspace(0, 8 / 25e6, 800)
    sys = signal.StateSpace(*net.ss)
    _, y = signal.impulse(sys, T=t)
    u = np.zeros_like(t)
    u[0] = 1.0

    era = ERAIdentifier(input_type="impulse", svd_rel_threshold=1e-3)
    era.fit(t, u, y, order=None)  # let it auto-select
    assert era._order_selected <= 6  # should stay small for a clean 2nd-order system


def test_era_is_passive_for_stable_network():
    net = series_rlc(50.0, 1e-6, 1e-9)
    t = np.linspace(0, 8 / 25e6, 800)
    sys = signal.StateSpace(*net.ss)
    _, y = signal.impulse(sys, T=t)
    u = np.zeros_like(t)
    u[0] = 1.0
    era = ERAIdentifier(input_type="impulse")
    era.fit(t, u, y, order=2)
    assert era.is_passive()


def test_era_predict_matches_simulated_response():
    """Uses the realistic finite-pulse convention (not the exact-impulse marker
    used above, which is scale-invariant for poles but not for gain/predict)."""
    net = series_rlc(50.0, 1e-6, 1e-9)
    alpha = 25e6
    t = np.linspace(0, 8 / alpha, 2000)
    dt = t[1] - t[0]
    u_impulse = np.zeros_like(t)
    u_impulse[0] = 1.0 / dt
    y_impulse = net.simulate(t, u_impulse)

    era = ERAIdentifier(input_type="impulse")
    era.fit(t, u_impulse, y_impulse, order=2)

    u_step = np.ones_like(t)
    y_pred = era.predict(u_step, t)
    y_true = net.simulate(t, u_step)
    nrmse = ERAIdentifier.fit_error(y_true, y_pred)
    assert nrmse < 0.1


def test_era_to_spice_netlist_runs():
    net = series_rlc(50.0, 1e-6, 1e-9)
    t = np.linspace(0, 8 / 25e6, 800)
    sys = signal.StateSpace(*net.ss)
    _, y = signal.impulse(sys, T=t)
    u = np.zeros_like(t)
    u[0] = 1.0
    era = ERAIdentifier(input_type="impulse")
    era.fit(t, u, y, order=2)
    netlist = era.to_spice_netlist()
    assert ".end" in netlist
    assert len(netlist.splitlines()) > 2
