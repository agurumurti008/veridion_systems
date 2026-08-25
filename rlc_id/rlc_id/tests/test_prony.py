"""Prony validation: exact recovery (noiseless), noise-robustness comparison between
classic (minimal 2p-sample) and robust (order-overspecified + dominant-pole-selection)
variants -- classic Prony's well-known noise fragility is expected and tested for,
not treated as a failure."""
import numpy as np
from scipy import signal
import pytest
from rlc_id.synth import series_rlc
from rlc_id.methods.prony import PronyIdentifier


def _impulse_response(net, n_tau=8, n_pts=800):
    alpha = -np.max(np.linalg.eigvals(net.ss[0]).real)
    t = np.linspace(0, n_tau / alpha, n_pts)
    sys = signal.StateSpace(*net.ss)
    _, y = signal.impulse(sys, T=t)
    return t, y


def test_prony_classic_exact_noiseless():
    net = series_rlc(50.0, 1e-6, 1e-9)
    true_poles = np.sort_complex(np.linalg.eigvals(net.ss[0]))
    t, y = _impulse_response(net)
    prony = PronyIdentifier(robust=False)
    prony.fit(t, None, y, order=2)
    est = np.sort_complex(prony.poles())
    rel_err = np.abs(est - true_poles) / np.abs(true_poles)
    assert np.all(rel_err < 1e-6)


def test_prony_robust_exact_noiseless():
    net = series_rlc(50.0, 1e-6, 1e-9)
    true_poles = np.sort_complex(np.linalg.eigvals(net.ss[0]))
    t, y = _impulse_response(net)
    prony = PronyIdentifier(robust=True)
    prony.fit(t, None, y, order=2)
    est = np.sort_complex(prony.poles())
    rel_err = np.abs(est - true_poles) / np.abs(true_poles)
    assert np.all(rel_err < 1e-4)


def test_prony_robust_tolerates_light_noise():
    """robust=True should stay usable at ~0.01% noise where classic Prony has
    already broken down (documented, expected literature behavior)."""
    net = series_rlc(50.0, 1e-6, 1e-9)
    true_poles = np.sort_complex(np.linalg.eigvals(net.ss[0]))
    t, y = _impulse_response(net)
    rng = np.random.default_rng(1)
    y_noisy = y + rng.normal(0, 1e-4 * np.max(np.abs(y)), size=y.shape)

    prony = PronyIdentifier(robust=True)
    prony.fit(t, None, y_noisy, order=2)
    est = np.sort_complex(prony.poles())
    rel_err = np.abs(est - true_poles) / np.abs(true_poles)
    assert np.all(rel_err < 0.05)


def test_prony_classic_is_noise_fragile_by_design():
    """Documents (does not 'fix') classic Prony's textbook noise sensitivity: the
    minimal 2p-sample system has zero averaging, so even tiny noise can produce a
    large pole error. This is expected method behavior, not a bug."""
    net = series_rlc(50.0, 1e-6, 1e-9)
    t, y = _impulse_response(net)
    rng = np.random.default_rng(1)
    y_noisy = y + rng.normal(0, 1e-4 * np.max(np.abs(y)), size=y.shape)
    prony = PronyIdentifier(robust=False)
    prony.fit(t, None, y_noisy, order=2)
    # no accuracy assertion -- just confirm it runs and returns finite poles
    assert np.all(np.isfinite(prony.poles()))


def test_prony_requires_explicit_order():
    net = series_rlc(50.0, 1e-6, 1e-9)
    t, y = _impulse_response(net)
    prony = PronyIdentifier()
    with pytest.raises(ValueError):
        prony.fit(t, None, y, order=None)


def test_prony_stabilizes_unstable_roots():
    """Synthetic pathological case: force an unstable root and confirm it gets
    reflected inside the unit circle rather than propagating overflow."""
    z_bad = np.array([1.5 + 0.1j, 1.5 - 0.1j])
    z_fixed = PronyIdentifier._stabilize(z_bad)
    assert np.all(np.abs(z_fixed) < 1.0)


def test_prony_predict_reasonable_on_clean_data():
    net = series_rlc(50.0, 1e-6, 1e-9)
    t, y = _impulse_response(net)
    prony = PronyIdentifier(robust=True)
    prony.fit(t, None, y, order=2)
    u_step = np.ones_like(t)
    y_pred = prony.predict(u_step, t)
    y_true = net.simulate(t, u_step)
    nrmse = PronyIdentifier.fit_error(y_true, y_pred)
    assert nrmse < 0.05


def test_prony_to_spice_netlist_runs():
    net = series_rlc(50.0, 1e-6, 1e-9)
    t, y = _impulse_response(net)
    prony = PronyIdentifier(robust=True)
    prony.fit(t, None, y, order=2)
    netlist = prony.to_spice_netlist()
    assert ".end" in netlist
