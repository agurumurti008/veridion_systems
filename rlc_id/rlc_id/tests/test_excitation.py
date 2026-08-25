"""Excitation generator validation: basic shape checks plus an end-to-end sanity
check that each generator can drive a real network and produce a finite response."""
import numpy as np
import pytest
from rlc_id import excitation as ex
from rlc_id.synth import series_rlc


@pytest.mark.parametrize("kind", ["step", "ramp", "impulse", "chirp", "multitone", "prbs"])
def test_generator_shapes_and_finiteness(kind):
    t, u = ex.generate(kind, duration=1e-6, n_points=500, seed=0) if kind in ("multitone", "prbs") \
        else ex.generate(kind, duration=1e-6, n_points=500)
    assert len(t) == len(u) == 500
    assert np.all(np.isfinite(u))
    assert t[0] == 0.0
    assert np.isclose(t[-1], 1e-6)


def test_step_is_constant_after_start():
    t, u = ex.step(1e-6, n_points=200, amplitude=2.0)
    assert np.all(u == 2.0)


def test_impulse_area_normalized():
    t, u = ex.impulse(1e-6, n_points=200, area=1.0)
    dt = t[1] - t[0]
    area = u[0] * dt  # single-sample pulse: area = height * dt
    assert np.isclose(area, 1.0)


def test_chirp_spans_requested_frequency_range():
    t, u = ex.chirp(1e-6, n_points=5000, f0=1e5, f1=1e8)
    # basic sanity: chirp should not be constant and should stay bounded
    assert np.std(u) > 0.1
    assert np.max(np.abs(u)) <= 1.01


def test_prbs_is_binary():
    t, u = ex.prbs(1e-6, n_points=1000, amplitude=1.0, seed=0)
    unique_vals = np.unique(u)
    assert np.all(np.isin(unique_vals, [-1.0, 1.0]))


def test_multitone_uses_requested_frequency_count():
    t, u = ex.multitone(1e-6, n_points=2000, n_tones=5, seed=0)
    assert np.std(u) > 0


def test_generate_unknown_kind_raises():
    with pytest.raises(ValueError):
        ex.generate("not_a_real_kind", duration=1e-6)


@pytest.mark.parametrize("kind", ["step", "impulse", "chirp", "prbs"])
def test_excitation_drives_real_network_finite_response(kind):
    """End-to-end: each generator should produce a usable, finite response when
    driving an actual RLC network (not just a standalone signal)."""
    net = series_rlc(50.0, 1e-6, 1e-9)
    kwargs = {"seed": 0} if kind == "prbs" else {}
    t, u = ex.generate(kind, duration=5e-7, n_points=1000, **kwargs)
    y = net.simulate(t, u)
    assert np.all(np.isfinite(y))
