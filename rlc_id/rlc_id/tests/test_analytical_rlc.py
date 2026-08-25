"""Ground-truth sanity check: synth.py state-space eigenvalues must match the
closed-form series/parallel RLC pole formulas exactly (noiseless, analytical)."""
import numpy as np
import pytest
from rlc_id.synth import series_rlc, parallel_rlc, cascaded_ladder


def analytical_series_poles(R, L, C):
    alpha = R / (2 * L)
    wn2 = 1 / (L * C)
    disc = alpha ** 2 - wn2
    if disc >= 0:
        return np.array([-alpha + np.sqrt(disc), -alpha - np.sqrt(disc)])
    return np.array([-alpha + 1j * np.sqrt(-disc), -alpha - 1j * np.sqrt(-disc)])


@pytest.mark.parametrize("R,L,C", [
    (10.0, 1e-6, 1e-9),      # underdamped
    (5000.0, 1e-6, 1e-9),    # overdamped
    (2000.0, 1e-6, 1e-9),    # near critical
])
def test_series_rlc_poles_match_closed_form(R, L, C):
    net = series_rlc(R, L, C)
    expected = analytical_series_poles(R, L, C)
    # state-space eigenvalues should equal the stored analytical poles exactly (same formula)
    ss_poles = np.linalg.eigvals(net.ss[0])
    got_sorted = np.sort_complex(ss_poles)
    exp_sorted = np.sort_complex(expected)
    assert np.allclose(got_sorted, exp_sorted, rtol=1e-9)


def analytical_parallel_poles(R, L, C):
    alpha = 1 / (2 * R * C)
    wn2 = 1 / (L * C)
    disc = alpha ** 2 - wn2
    if disc >= 0:
        return np.array([-alpha + np.sqrt(disc), -alpha - np.sqrt(disc)])
    return np.array([-alpha + 1j * np.sqrt(-disc), -alpha - 1j * np.sqrt(-disc)])


@pytest.mark.parametrize("R,L,C", [
    (1000.0, 1e-6, 1e-9),   # underdamped
    (5.0, 1e-6, 1e-9),      # overdamped (alpha >> wn for parallel RLC at low R)
])
def test_parallel_rlc_poles_match_closed_form(R, L, C):
    net = parallel_rlc(R, L, C)
    ss_poles = np.sort_complex(np.linalg.eigvals(net.ss[0]))
    expected = np.sort_complex(analytical_parallel_poles(R, L, C))
    assert np.allclose(ss_poles, expected, rtol=1e-6)
    assert np.all(ss_poles.real <= 1e-9), "parallel RLC must be passive (poles in LHP)"


def test_series_rlc_is_passive():
    net = series_rlc(50.0, 1e-6, 1e-9)
    poles = np.linalg.eigvals(net.ss[0])
    assert np.all(poles.real <= 1e-9)


def test_cascaded_ladder_pole_count_and_passivity():
    net = cascaded_ladder(n_stages=4, seed=42)
    poles = net.poles
    assert len(poles) == 8  # 2 states per stage
    assert np.all(poles.real <= 1e-6), "cascaded ladder must be passive"


def test_cascaded_ladder_near_degenerate_stresses_conditioning():
    net = cascaded_ladder(n_stages=3, near_degenerate=True, seed=1)
    poles = net.poles
    assert len(poles) == 6
    # near-degenerate construction should produce at least one closely-spaced pole pair
    sorted_by_imag = np.sort(np.abs(poles.imag))
    gaps = np.diff(sorted_by_imag)
    assert np.min(gaps) < 0.15 * np.max(np.abs(poles.imag))


def test_simulate_step_response_reasonable():
    net = series_rlc(50.0, 1e-6, 1e-9)
    t = np.linspace(0, 5e-6, 2000)
    u = np.ones_like(t)
    y = net.simulate(t, u)
    assert y.shape == t.shape
    assert np.all(np.isfinite(y))


def test_simulate_with_noise_and_bandwidth_limit():
    net = series_rlc(50.0, 1e-6, 1e-9)
    t = np.linspace(0, 5e-6, 2000)
    u = np.ones_like(t)
    y_clean = net.simulate(t, u)
    y_noisy = net.simulate(t, u, snr_db=20)
    assert not np.allclose(y_clean, y_noisy)
    y_bw = net.simulate(t, u, bandwidth_hz=50e6)
    assert np.all(np.isfinite(y_bw))
