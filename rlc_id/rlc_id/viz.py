"""Visualization: Bode plots, pole-zero maps, time-domain overlays, residual plots.
All functions save to a file path and return that path (headless-safe, no plt.show())."""
from __future__ import annotations
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def plot_pole_zero_map(poles_dict: dict, path: str, title: str = "Pole-Zero Map") -> str:
    """poles_dict: {label: poles_array, ...} -- overlays multiple pole sets
    (e.g. {'true': true_poles, 'era': era_poles, 'vfit': vf_poles})."""
    fig, ax = plt.subplots(figsize=(7, 6))
    markers = ["x", "o", "^", "s", "d", "*", "+"]
    for i, (label, poles) in enumerate(poles_dict.items()):
        poles = np.asarray(poles)
        ax.scatter(poles.real, poles.imag, marker=markers[i % len(markers)],
                   label=label, s=80, alpha=0.75)
    ax.axvline(0, color="gray", linewidth=0.5)
    ax.axhline(0, color="gray", linewidth=0.5)
    ax.set_xlabel("Re(s) [rad/s]")
    ax.set_ylabel("Im(s) [rad/s]")
    ax.set_title(title)
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)
    return path


def plot_bode(w: np.ndarray, H_dict: dict, path: str, title: str = "Bode Plot") -> str:
    """H_dict: {label: complex_H_array, ...} evaluated at the SAME w for all entries."""
    fig, (ax_mag, ax_phase) = plt.subplots(2, 1, figsize=(8, 7), sharex=True)
    for label, H in H_dict.items():
        H = np.asarray(H)
        mag_db = 20 * np.log10(np.maximum(np.abs(H), 1e-30))
        ax_mag.semilogx(w, mag_db, label=label)
        ax_phase.semilogx(w, np.degrees(np.angle(H)), label=label)
    ax_mag.set_ylabel("Magnitude [dB]")
    ax_mag.set_title(title)
    ax_mag.grid(True, which="both", alpha=0.3)
    ax_mag.legend()
    ax_phase.set_ylabel("Phase [deg]")
    ax_phase.set_xlabel("Angular frequency [rad/s]")
    ax_phase.grid(True, which="both", alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)
    return path


def plot_time_domain_overlay(t: np.ndarray, y_dict: dict, path: str,
                              title: str = "Time-Domain Response") -> str:
    """y_dict: {label: y_array, ...} -- overlays measured/true vs. predicted traces."""
    fig, ax = plt.subplots(figsize=(9, 5))
    for label, y in y_dict.items():
        ax.plot(t, y, label=label, linewidth=1.2)
    ax.set_xlabel("Time [s]")
    ax.set_ylabel("Amplitude")
    ax.set_title(title)
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)
    return path


def plot_residuals(t: np.ndarray, y_true: np.ndarray, y_pred: np.ndarray, path: str,
                    title: str = "Fit Residuals") -> str:
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.plot(t, np.asarray(y_true) - np.asarray(y_pred), color="firebrick", linewidth=1.0)
    ax.axhline(0, color="gray", linewidth=0.5)
    ax.set_xlabel("Time [s]")
    ax.set_ylabel("Residual (true - predicted)")
    ax.set_title(title)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)
    return path


def plot_benchmark_comparison(df, path: str, metric: str = "pole_err_rel",
                               title: str = "Method Comparison") -> str:
    """df: pandas DataFrame from eval.run_benchmark -- grouped bar chart of `metric`
    by method, one bar group per excitation type."""
    import pandas as pd
    fig, ax = plt.subplots(figsize=(9, 5))
    methods = df["method"].unique()
    excitations = df["excitation"].unique()
    x = np.arange(len(methods))
    width = 0.8 / max(len(excitations), 1)
    for i, exc_kind in enumerate(excitations):
        sub = df[df["excitation"] == exc_kind].groupby("method")[metric].mean()
        vals = [sub.get(m, np.nan) for m in methods]
        ax.bar(x + i * width, vals, width, label=exc_kind)
    ax.set_yscale("log")
    ax.set_xticks(x + width * (len(excitations) - 1) / 2)
    ax.set_xticklabels(methods)
    ax.set_ylabel(metric)
    ax.set_title(title)
    ax.legend()
    ax.grid(True, axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)
    return path
