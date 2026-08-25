"""Benchmark harness validation: correct DataFrame shape/columns, method-excitation
compatibility filtering, and sane accuracy on both simple and higher-order networks."""
import numpy as np
import pandas as pd
from rlc_id.synth import series_rlc, cascaded_ladder
from rlc_id.eval import run_benchmark, run_single, ALL_METHODS, METHOD_EXCITATION_SUPPORT


def test_run_single_era_returns_expected_keys():
    net = series_rlc(50.0, 1e-6, 1e-9)
    row = run_single("era", net, order=2, excitation_kind="impulse")
    expected_keys = {"method", "excitation", "snr_db", "true_order", "pole_err_rel",
                      "passive", "runtime_s", "order_selected", "success", "error"}
    assert expected_keys.issubset(row.keys())
    assert row["success"] is True
    assert row["pole_err_rel"] < 0.2  # finite-pulse approximation, not machine precision


def test_run_benchmark_returns_dataframe_with_all_methods():
    net = series_rlc(50.0, 1e-6, 1e-9)
    df = run_benchmark(net, order=2, methods=ALL_METHODS, excitations=["impulse"])
    assert isinstance(df, pd.DataFrame)
    assert set(df["method"]) == set(ALL_METHODS)
    assert len(df) == len(ALL_METHODS)  # one row per method for a single excitation/noise combo


def test_run_benchmark_skips_unsupported_excitation_combos():
    """Prony only supports 'impulse' -- requesting 'prbs' for it should be silently
    skipped rather than mis-run against data it can't model."""
    net = series_rlc(50.0, 1e-6, 1e-9)
    df = run_benchmark(net, order=2, methods=["prony", "subspace"], excitations=["prbs"])
    prony_rows = df[df["method"] == "prony"]
    subspace_rows = df[df["method"] == "subspace"]
    assert len(prony_rows) == 0
    assert len(subspace_rows) == 1
    assert subspace_rows.iloc[0]["excitation"] == "prbs"


def test_run_benchmark_sweeps_noise_levels():
    net = series_rlc(50.0, 1e-6, 1e-9)
    df = run_benchmark(net, order=2, methods=["vfit"], excitations=["impulse"],
                        noise_db_list=[None, 40, 20])
    assert len(df) == 3
    non_null = set(df["snr_db"].dropna())
    assert non_null == {40, 20}
    assert df["snr_db"].isna().sum() == 1  # the None entry becomes NaN in a numeric column


def test_run_benchmark_all_methods_succeed_on_clean_series_rlc():
    net = series_rlc(50.0, 1e-6, 1e-9)
    df = run_benchmark(net, order=2, methods=ALL_METHODS, excitations=["impulse"])
    assert df["success"].all()
    assert df["passive"].all()


def test_run_benchmark_cascaded_ladder_high_accuracy():
    """All methods should recover the higher-order mixed real/complex system to
    high accuracy with harness defaults (regression guard for the pole-seeding
    and default-window/bandwidth heuristics)."""
    net = cascaded_ladder(n_stages=3, seed=7)
    df = run_benchmark(net, order=6, methods=ALL_METHODS, excitations=["impulse"])
    assert df["success"].all()
    assert (df["pole_err_rel"] < 1e-4).all()


def test_method_excitation_support_table_matches_all_methods():
    assert set(METHOD_EXCITATION_SUPPORT.keys()) == set(ALL_METHODS)


def test_run_single_failure_reports_error_not_crash():
    """A deliberately impossible order should fail gracefully with success=False
    and a captured error message, not raise out of run_single."""
    net = series_rlc(50.0, 1e-6, 1e-9)
    row = run_single("prony", net, order=None, excitation_kind="impulse")
    assert row["success"] is False
    assert row["error"] is not None
