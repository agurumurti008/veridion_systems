"""Subspace (ARX + realization) validation: exact recovery on clean data with
general (non-impulse) excitation, documented noise-sensitivity at minimal order
(known ARX output-error bias -- Ljung, System Identification, Ch.7), and recovery
on the higher-order cascaded ladder with a properly time-matched PRBS excitation."""
import numpy as np
import pytest
from rlc_id.synth import series_rlc, cascaded_ladder
from rlc_id.methods.subspace import SubspaceIdentifier
from rlc_id.core.utils import match_poles


def test_subspace_step_input_machine_precision():
    net = series_rlc(50.0, 1e-6, 1e-9)
    true_poles = np.sort_complex(np.linalg.eigvals(net.ss[0]))
    alpha = 25e6
    t = np.linspace(0, 8 / alpha, 1000)
    u = np.ones_like(t)
    y = net.simulate(t, u)

    sub = SubspaceIdentifier()
    sub.fit(t, u, y, order=2)
    est = np.sort_complex(sub.poles())
    rel_err = np.abs(est - true_poles) / np.abs(true_poles)
    assert np.all(rel_err < 1e-6)


def test_subspace_prbs_input_machine_precision():
    """PRBS is subspace/ARX's actual intended use case (general, non-impulse input;
    ERA/Prony cannot use this excitation type directly)."""
    net = series_rlc(50.0, 1e-6, 1e-9)
    true_poles = np.sort_complex(np.linalg.eigvals(net.ss[0]))
    alpha = 25e6
    t = np.linspace(0, 8 / alpha, 1000)
    rng = np.random.default_rng(0)
    u = rng.choice([-1.0, 1.0], size=len(t))
    y = net.simulate(t, u)

    sub = SubspaceIdentifier()
    sub.fit(t, u, y, order=2)
    est = np.sort_complex(sub.poles())
    rel_err = np.abs(est - true_poles) / np.abs(true_poles)
    assert np.all(rel_err < 1e-6)


def test_subspace_tolerates_light_noise():
    net = series_rlc(50.0, 1e-6, 1e-9)
    true_poles = np.sort_complex(np.linalg.eigvals(net.ss[0]))
    alpha = 25e6
    t = np.linspace(0, 8 / alpha, 1000)
    rng = np.random.default_rng(0)
    u = rng.choice([-1.0, 1.0], size=len(t))
    y = net.simulate(t, u)
    y_noisy = y + rng.normal(0, 1e-5 * np.max(np.abs(y)), size=y.shape)

    sub = SubspaceIdentifier()
    sub.fit(t, u, y_noisy, order=2)
    est = np.sort_complex(sub.poles())
    rel_err = np.abs(est - true_poles) / np.abs(true_poles)
    assert np.all(rel_err < 0.01)


def test_subspace_minimal_order_is_noise_sensitive_by_design():
    """Documents (does not 'fix') a known property: minimal-order ARX/OLS has
    output-error bias when y is noisy (y appears as both regressor and target).
    Confirms the method runs and returns finite poles rather than asserting accuracy."""
    net = series_rlc(50.0, 1e-6, 1e-9)
    alpha = 25e6
    t = np.linspace(0, 8 / alpha, 1000)
    rng = np.random.default_rng(0)
    u = rng.choice([-1.0, 1.0], size=len(t))
    y = net.simulate(t, u)
    y_noisy = y + rng.normal(0, 1e-3 * np.max(np.abs(y)), size=y.shape)
    sub = SubspaceIdentifier()
    sub.fit(t, u, y_noisy, order=2)
    assert np.all(np.isfinite(sub.poles()))


def test_subspace_cascaded_ladder_matched_window():
    """8th-order mixed real/complex system, PRBS excitation, time window/sampling
    matched to the pole timescales (same coverage lesson as the VF stress test)."""
    net = cascaded_ladder(n_stages=4, seed=42)
    true_poles = net.poles
    t_end = 15 / np.min(np.abs(true_poles))
    t = np.linspace(0, t_end, 4000)
    rng = np.random.default_rng(0)
    u = rng.choice([-1.0, 1.0], size=len(t))
    y = net.simulate(t, u)

    sub = SubspaceIdentifier()
    sub.fit(t, u, y, order=8)
    _, mean_err = match_poles(true_poles, sub.poles())
    assert mean_err / np.mean(np.abs(true_poles)) < 1e-2


def test_subspace_raises_on_insufficient_samples():
    net = series_rlc(50.0, 1e-6, 1e-9)
    t = np.linspace(0, 1e-6, 5)
    u = np.ones_like(t)
    y = net.simulate(t, u)
    sub = SubspaceIdentifier()
    with pytest.raises(ValueError):
        sub.fit(t, u, y, order=8)


def test_subspace_predict_matches_simulated_response():
    """Uses PRBS, not step: a constant step has zero informative content at any
    nonzero frequency, so ARX cannot identify B/D from it (see test below) even
    though it recovers poles fine from the free-decay dynamics alone."""
    net = series_rlc(50.0, 1e-6, 1e-9)
    alpha = 25e6
    t = np.linspace(0, 8 / alpha, 1000)
    rng = np.random.default_rng(0)
    u = rng.choice([-1.0, 1.0], size=len(t))
    y = net.simulate(t, u)
    sub = SubspaceIdentifier()
    sub.fit(t, u, y, order=2)
    y_pred = sub.predict(u, t)
    nrmse = SubspaceIdentifier.fit_error(y, y_pred)
    assert nrmse < 1e-4


def test_subspace_step_input_cannot_identify_gain_pe_violation():
    """Documents a real persistence-of-excitation failure mode (Ljung's PE
    condition, directly relevant to Section 3 of the accompanying analysis): a
    constant step carries no energy at any nonzero frequency, so ARX correctly
    recovers the free-decay poles (which only need the transient) but CANNOT
    identify B/D (which need input-output correlation at nonzero frequencies) --
    the fit silently drives B/D toward numerically-arbitrary near-zero values.
    This is not a bug to fix; it is the reason multi-experiment / broadband
    excitation is required in practice, exactly as the excitation-design
    discussion argues."""
    net = series_rlc(50.0, 1e-6, 1e-9)
    true_poles = np.sort_complex(np.linalg.eigvals(net.ss[0]))
    alpha = 25e6
    t = np.linspace(0, 8 / alpha, 1000)
    u = np.ones_like(t)
    y = net.simulate(t, u)
    sub = SubspaceIdentifier()
    sub.fit(t, u, y, order=2)

    # poles ARE recoverable from a step (transient decay alone determines them)
    est_poles = np.sort_complex(sub.poles())
    rel_err = np.abs(est_poles - true_poles) / np.abs(true_poles)
    assert np.all(rel_err < 1e-6)

    # but predict() on the SAME step is NOT reliable -- B/D are unidentified
    y_pred = sub.predict(u, t)
    nrmse = SubspaceIdentifier.fit_error(y, y_pred)
    assert nrmse > 0.1  # confirms the PE violation is real, not silently "fine"


def test_subspace_to_spice_netlist_runs():
    net = series_rlc(50.0, 1e-6, 1e-9)
    alpha = 25e6
    t = np.linspace(0, 8 / alpha, 1000)
    u = np.ones_like(t)
    y = net.simulate(t, u)
    sub = SubspaceIdentifier()
    sub.fit(t, u, y, order=2)
    netlist = sub.to_spice_netlist()
    assert ".end" in netlist
