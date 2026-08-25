"""
data/export.py
Utilities to export predictions, training data, and model reports to CSV/JSON.
"""
from __future__ import annotations
import csv
import json
import os
from datetime import datetime
from typing import Dict, List, Optional, Any
import numpy as np


def export_predictions_csv(X: np.ndarray, Y_pred: np.ndarray,
                            Y_true: Optional[np.ndarray] = None,
                            x_names: Optional[List[str]] = None,
                            y_names: Optional[List[str]] = None,
                            path: str = "predictions.csv"):
    """Write (X, Y_pred, [Y_true]) to CSV."""
    n, dx = X.shape
    _, dy = Y_pred.shape

    xn = x_names or [f"x_{i}" for i in range(dx)]
    yn = y_names or [f"y_{i}" for i in range(dy)]

    with open(path, "w", newline="") as fh:
        cols  = xn + [f"pred_{k}" for k in yn]
        if Y_true is not None:
            cols += [f"true_{k}" for k in yn]
            cols += [f"err_pct_{k}" for k in yn]
        writer = csv.DictWriter(fh, fieldnames=cols)
        writer.writeheader()
        for i in range(n):
            row = {xn[j]: float(X[i, j]) for j in range(dx)}
            row.update({f"pred_{yn[j]}": float(Y_pred[i, j])
                        for j in range(dy)})
            if Y_true is not None:
                row.update({f"true_{yn[j]}": float(Y_true[i, j])
                            for j in range(dy)})
                row.update({
                    f"err_pct_{yn[j]}": float(
                        abs(Y_pred[i,j] - Y_true[i,j]) /
                        (abs(Y_true[i,j]) + 1e-9) * 100)
                    for j in range(dy)
                })
            writer.writerow(row)
    return path


def export_training_data_csv(X: np.ndarray, Y: np.ndarray,
                              x_names: Optional[List[str]] = None,
                              y_names: Optional[List[str]] = None,
                              technology: str = "180nm",
                              path: str = "training_data.csv"):
    """Export (X, Y) training dataset to CSV with x_/y_ prefixes."""
    n, dx = X.shape
    _, dy = Y.shape
    xn = x_names or [f"x_{i}" for i in range(dx)]
    yn = y_names or [f"y_{i}" for i in range(dy)]
    x_cols = [f"x_{k}" for k in xn]
    y_cols = [f"y_{k}" for k in yn]

    with open(path, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["technology"]+x_cols+y_cols)
        writer.writeheader()
        for i in range(n):
            row = {"technology": technology}
            row.update({f"x_{xn[j]}": float(X[i,j]) for j in range(dx)})
            row.update({f"y_{yn[j]}": float(Y[i,j]) for j in range(dy)})
            writer.writerow(row)
    return path


def model_report(model, X_test: np.ndarray, Y_test: np.ndarray,
                 output_names: Optional[List[str]] = None,
                 path: str = "model_report.json") -> Dict[str, Any]:
    """Compute and save model performance report."""
    Y_pred = model.predict(X_test)
    n_out  = Y_test.shape[1]
    yn     = output_names or [f"output_{i}" for i in range(n_out)]

    metrics = {}
    for i, name in enumerate(yn):
        yt = Y_test[:, i]
        yp = Y_pred[:, i]
        ss_res = np.sum((yt - yp)**2)
        ss_tot = np.sum((yt - np.mean(yt))**2) + 1e-12
        r2 = 1 - ss_res / ss_tot
        mape = float(np.mean(np.abs((yt - yp) / (np.abs(yt) + 1e-9))) * 100)
        metrics[name] = {
            "R2"      : float(r2),
            "MAE"     : float(np.mean(np.abs(yt - yp))),
            "RMSE"    : float(np.sqrt(np.mean((yt - yp)**2))),
            "MAPE_pct": mape,
        }

    report = {
        "timestamp"   : datetime.utcnow().isoformat(),
        "n_test"      : int(n_out),
        "n_samples"   : len(X_test),
        "output_metrics": metrics,
        "mean_R2"     : float(np.mean([v["R2"] for v in metrics.values()])),
        "mean_MAPE"   : float(np.mean([v["MAPE_pct"] for v in metrics.values()])),
    }

    with open(path, "w") as fh:
        json.dump(report, fh, indent=2)

    return report


def print_report(report: Dict[str, Any]):
    """Pretty-print a model report dict."""
    print(f"\n  Model Performance Report  [{report['timestamp']}]")
    print(f"  Test samples: {report['n_samples']}")
    print(f"  Mean R²: {report['mean_R2']:.4f}   Mean MAPE: {report['mean_MAPE']:.2f}%")
    print(f"\n  {'Output':<30} {'R²':>8} {'RMSE':>12} {'MAPE%':>8}")
    print(f"  {'-'*60}")
    for name, m in report["output_metrics"].items():
        print(f"  {name:<30} {m['R2']:>8.4f} {m['RMSE']:>12.4f} {m['MAPE_pct']:>7.1f}%")
