"""Anomaly detection validation: golden-vs-measured differencing correctly flags
injected component perturbations, and sensitivity analysis correctly identifies
the actual perturbed component as the top explanation."""
import copy
import numpy as np
import pytest
from rlc_id.synth import cascaded_ladder, cascaded_ladder_from_components
from rlc_id.anomaly import (fit_golden_and_measured, diff_poles, component_sensitivity,
                             explain_shift, AnomalyReport)


def _analytic_H(net, w):
    A, B, C, D = net.ss
    I = np.eye(A.shape[0])
    return np.array([(C @ np.linalg.solve(1j * wk * I - A, B) + D).item() for wk in w])


def test_diff_poles_no_change_flags_nothing():
    net = cascaded_ladder(n_stages=3, seed=7)
    report = diff_poles(net.poles, net.poles, rel_threshold=0.02)
    assert len(report.anomalies) == 0
    assert len(report.unmatched_golden) == 0
    assert len(report.unmatched_measured) == 0


def test_diff_poles_detects_injected_perturbation():
    golden = cascaded_ladder(n_stages=3, seed=7)
    measured_stages = copy.deepcopy(golden.components["stages"])
    measured_stages[1]["L"] *= 1.30
    measured_net = cascaded_ladder_from_components(measured_stages)

    pole_mags = np.abs(golden.poles)
    w = np.logspace(np.log10(pole_mags.min() / 10), np.log10(pole_mags.max() * 10), 400)
    H_measured = _analytic_H(measured_net, w)

    vf_golden, vf_measured = fit_golden_and_measured(
        golden, w, H_measured, order=6,
        vf_kwargs={"include_real_poles": True, "n_iterations": 15})
    report = diff_poles(vf_golden.poles(), vf_measured.poles(), rel_threshold=0.02)
    assert len(report.anomalies) > 0
    assert isinstance(report.summary(), str)
    assert "flagged" in report.summary()


def test_component_sensitivity_identifies_correct_component():
    """The top-ranked explanation for an injected L perturbation should be the
    ACTUAL perturbed (stage, component) pair, with a plausible implied fraction."""
    golden = cascaded_ladder(n_stages=3, seed=7)
    stages = golden.components["stages"]
    measured_stages = copy.deepcopy(stages)
    measured_stages[1]["L"] *= 1.30
    measured_net = cascaded_ladder_from_components(measured_stages)

    pole_mags = np.abs(golden.poles)
    w = np.logspace(np.log10(pole_mags.min() / 10), np.log10(pole_mags.max() * 10), 400)
    H_measured = _analytic_H(measured_net, w)
    vf_golden, vf_measured = fit_golden_and_measured(
        golden, w, H_measured, order=6,
        vf_kwargs={"include_real_poles": True, "n_iterations": 15})
    report = diff_poles(vf_golden.poles(), vf_measured.poles(), rel_threshold=0.02)
    sens = component_sensitivity(stages)

    assert len(report.anomalies) > 0
    top = explain_shift(report.anomalies[0], sens, top_n=1)[0]
    assert top["stage"] == 1
    assert top["component"] == "L"
    assert 0.1 < top["implied_delta_frac"] < 0.6  # true injected fraction was 0.30


def test_component_sensitivity_returns_all_component_combinations():
    golden = cascaded_ladder(n_stages=3, seed=7)
    sens = component_sensitivity(golden.components["stages"])
    expected_keys = {(i, p) for i in range(3) for p in ("R", "L", "C")}
    assert set(sens.keys()) == expected_keys
    for key, info in sens.items():
        assert "d_pole" in info and "baseline_value" in info
        assert len(info["d_pole"]) == len(golden.poles)


def test_explain_shift_ranks_by_residual():
    golden = cascaded_ladder(n_stages=3, seed=7)
    stages = golden.components["stages"]
    sens = component_sensitivity(stages)
    from rlc_id.anomaly import PoleShift
    # synthetic shift matching stage 0's R sensitivity exactly
    d_pole0 = sens[(0, "R")]["d_pole"][0]
    baseline_R = sens[(0, "R")]["baseline_value"]
    fake_delta = baseline_R * 0.1
    fake_shift = PoleShift(0, 0, golden.poles[0], golden.poles[0] + d_pole0 * fake_delta,
                            abs(d_pole0 * fake_delta), 0.1, True)
    candidates = explain_shift(fake_shift, sens, top_n=3)
    assert candidates[0]["stage"] == 0
    assert candidates[0]["component"] == "R"
    assert candidates[0]["fit_residual"] < candidates[1]["fit_residual"]


def test_anomaly_report_dataclass_fields():
    net = cascaded_ladder(n_stages=2, seed=1)
    report = diff_poles(net.poles, net.poles * 1.5, rel_threshold=0.01)
    assert isinstance(report, AnomalyReport)
    assert report.threshold == 0.01
    assert len(report.shifts) == len(net.poles)
