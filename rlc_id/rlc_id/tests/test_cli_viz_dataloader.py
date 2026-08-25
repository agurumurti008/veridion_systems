"""Validation for the CLI (argument parsing + end-to-end subcommand execution),
viz.py (plots save without error), and dataloader.py (CSV round-trip, FSDB stub)."""
import json
import copy
import os
import numpy as np
import pytest
from rlc_id.synth import series_rlc, cascaded_ladder, cascaded_ladder_from_components
from rlc_id.dataloader import WaveformData, save_csv, load_csv, load_fsdb
from rlc_id import viz
from rlc_id.cli import main as cli_main


# ---------------- dataloader ----------------

def test_csv_roundtrip_time_domain(tmp_path):
    net = series_rlc(50.0, 1e-6, 1e-9)
    t = np.linspace(0, 1e-6, 200)
    u = np.ones_like(t)
    y = net.simulate(t, u)
    path = str(tmp_path / "wave.csv")
    save_csv(WaveformData(t, u, y), path)
    loaded = load_csv(path)
    assert np.allclose(loaded.time_or_freq, t)
    assert np.allclose(loaded.y, y)
    assert not loaded.is_frequency_domain


def test_csv_roundtrip_frequency_domain(tmp_path):
    net = series_rlc(50.0, 1e-6, 1e-9)
    w = np.logspace(4, 9, 50)
    A, B, C, D = net.ss
    I = np.eye(2)
    H = np.array([(C @ np.linalg.solve(1j * wk * I - A, B) + D).item() for wk in w])
    path = str(tmp_path / "freq.csv")
    save_csv(WaveformData(w, None, H, is_frequency_domain=True), path)
    loaded = load_csv(path, freq_col="freq", real_col="real", imag_col="imag")
    assert np.allclose(loaded.y, H)
    assert loaded.is_frequency_domain


def test_load_csv_missing_column_raises(tmp_path):
    import pandas as pd
    path = str(tmp_path / "bad.csv")
    pd.DataFrame({"x": [1, 2, 3]}).to_csv(path, index=False)
    with pytest.raises(ValueError):
        load_csv(path)


def test_load_fsdb_raises_not_implemented():
    with pytest.raises(NotImplementedError):
        load_fsdb("/nonexistent.fsdb", "sig")


# ---------------- viz ----------------

def test_viz_pole_zero_map(tmp_path):
    path = str(tmp_path / "pz.png")
    result = viz.plot_pole_zero_map({"true": np.array([-1 + 1j, -1 - 1j])}, path)
    assert os.path.exists(result)


def test_viz_bode(tmp_path):
    path = str(tmp_path / "bode.png")
    w = np.logspace(3, 9, 50)
    H = 1 / (1j * w + 1)
    result = viz.plot_bode(w, {"model": H}, path)
    assert os.path.exists(result)


def test_viz_time_domain_overlay(tmp_path):
    path = str(tmp_path / "td.png")
    t = np.linspace(0, 1, 100)
    result = viz.plot_time_domain_overlay(t, {"true": np.sin(t), "pred": np.cos(t)}, path)
    assert os.path.exists(result)


def test_viz_residuals(tmp_path):
    path = str(tmp_path / "resid.png")
    t = np.linspace(0, 1, 100)
    result = viz.plot_residuals(t, np.sin(t), np.sin(t) + 0.01, path)
    assert os.path.exists(result)


def test_viz_benchmark_comparison(tmp_path):
    from rlc_id.eval import run_benchmark
    net = series_rlc(50.0, 1e-6, 1e-9)
    df = run_benchmark(net, order=2, methods=["era", "vfit"], excitations=["impulse"])
    path = str(tmp_path / "bench.png")
    result = viz.plot_benchmark_comparison(df, path)
    assert os.path.exists(result)


# ---------------- CLI ----------------

def test_cli_excite(tmp_path, monkeypatch):
    out = str(tmp_path / "exc.csv")
    monkeypatch.setattr("sys.argv", ["rlc-id", "excite", "--type", "prbs",
                                      "--duration", "1e-6", "--n-points", "300", "--out", out])
    cli_main()
    assert os.path.exists(out)


def test_cli_benchmark(tmp_path, monkeypatch):
    out = str(tmp_path / "bench.csv")
    monkeypatch.setattr("sys.argv", ["rlc-id", "benchmark", "--topology", "series",
                                      "--methods", "era,vfit", "--excitations", "impulse",
                                      "--out", out])
    cli_main()
    assert os.path.exists(out)


def test_cli_fit(tmp_path, monkeypatch):
    net = series_rlc(50.0, 1e-6, 1e-9)
    t = np.linspace(0, 8 / 25e6, 2000)
    dt = t[1] - t[0]
    u = np.zeros_like(t)
    u[0] = 1.0 / dt
    y = net.simulate(t, u)
    data_path = str(tmp_path / "data.csv")
    save_csv(WaveformData(t, u, y), data_path)
    netlist_path = str(tmp_path / "netlist.sp")

    monkeypatch.setattr("sys.argv", ["rlc-id", "fit", "--method", "era", "--data", data_path,
                                      "--order", "2", "--netlist-out", netlist_path])
    cli_main()
    assert os.path.exists(netlist_path)
    with open(netlist_path) as f:
        assert ".end" in f.read()


def test_cli_anomaly(tmp_path, monkeypatch):
    golden = cascaded_ladder(n_stages=3, seed=7)
    golden_path = str(tmp_path / "golden.json")
    with open(golden_path, "w") as f:
        json.dump({"stages": golden.components["stages"]}, f)

    measured_stages = copy.deepcopy(golden.components["stages"])
    measured_stages[1]["L"] *= 1.3
    measured_net = cascaded_ladder_from_components(measured_stages)
    pole_mags = np.abs(golden.poles)
    w = np.logspace(np.log10(pole_mags.min() / 10), np.log10(pole_mags.max() * 10), 400)
    A, B, C, D = measured_net.ss
    I = np.eye(A.shape[0])
    H = np.array([(C @ np.linalg.solve(1j * wk * I - A, B) + D).item() for wk in w])
    measured_path = str(tmp_path / "measured.csv")
    save_csv(WaveformData(w, None, H, is_frequency_domain=True), measured_path)

    out_path = str(tmp_path / "anomaly_out.json")
    monkeypatch.setattr("sys.argv", ["rlc-id", "anomaly", "--golden", golden_path,
                                      "--measured", measured_path, "--threshold", "0.02",
                                      "--explain", "--out", out_path])
    cli_main()
    assert os.path.exists(out_path)
    with open(out_path) as f:
        report = json.load(f)
    assert report["n_anomalies"] > 0
    assert "explanations" in report
