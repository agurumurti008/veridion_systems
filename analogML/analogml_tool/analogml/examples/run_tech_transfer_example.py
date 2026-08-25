#!/usr/bin/env python3
"""
examples/run_tech_transfer_example.py
Full technology transfer pipeline:
  1. Train on 180nm OTA data
  2. Transfer feature mapping to 90nm
  3. Evaluate performance of transferred model
  4. Compare Dennard scaling predictions vs ML predictions
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np
from analogml.data   import SyntheticCircuitDataset
from analogml.models import AnalogMLModel, TechTransferAgent
from analogml.data.export import model_report, print_report, export_predictions_csv

def sep(t): print(f"\n{'─'*60}\n  {t}\n{'─'*60}")


# ── 1. Dataset for each technology ───────────────────────────────────────────
sep("1. Generating multi-technology datasets")

techs   = ["180nm", "90nm", "65nm"]
datasets = {}
for tech in techs:
    ds = SyntheticCircuitDataset(seed=hash(tech) % 1000)
    X, Y, xn, yn = ds.generate("ota_5t", n_samples=250, technology=tech)
    datasets[tech] = (X, Y, xn, yn)
    print(f"  {tech}: X{X.shape}  Y{Y.shape}")


# ── 2. Train base model on 180nm ─────────────────────────────────────────────
sep("2. Training reference model on 180nm")

X_180, Y_180, xn, yn = datasets["180nm"]
perm = np.random.permutation(len(X_180))
sp   = int(0.8 * len(X_180))
model_180 = AnalogMLModel(mode="fast", output_names=yn)
model_180.fit(X_180[perm[:sp]], Y_180[perm[:sp]], epochs=150)

r180 = model_report(model_180, X_180[perm[sp:]], Y_180[perm[sp:]],
                     output_names=yn, path="/tmp/report_180nm.json")
print_report(r180)


# ── 3. Build transfer agent 180nm → 90nm ─────────────────────────────────────
sep("3. Technology Transfer  180nm → 90nm")

X_90, Y_90, _, _ = datasets["90nm"]
n_common = min(len(X_180), len(X_90), 150)

agent_90 = TechTransferAgent("180nm", "90nm")
agent_90.fit(X_180[:n_common], X_90[:n_common])
print("  Transfer agent trained.")

# Map all 90nm X-test via agent
perm90 = np.random.permutation(len(X_90))
X_90_te = X_90[perm90[int(0.8*len(X_90)):]]
Y_90_te = Y_90[perm90[int(0.8*len(X_90)):]]
X_90_mapped = agent_90.transfer(X_90_te)

# Predict with 180nm model on mapped features
Y_90_pred = model_180.predict(X_90_mapped)

print(f"\n  Transfer prediction results (using 180nm model on mapped 90nm X):")
for i, name in enumerate(yn[:5]):
    corr = float(np.corrcoef(Y_90_te[:, i], Y_90_pred[:, i])[0,1])
    print(f"    {name:<30} Pearson r = {corr:.3f}")


# ── 4. Retrain on 90nm data (upper bound) ────────────────────────────────────
sep("4. Retrained 90nm model (upper bound comparison)")

model_90 = AnalogMLModel(mode="fast", output_names=yn)
model_90.fit(X_90[perm90[:int(0.8*len(X_90))]], Y_90[perm90[:int(0.8*len(X_90))]])
r90 = model_report(model_90, X_90_te, Y_90_te,
                    output_names=yn, path="/tmp/report_90nm.json")
print(f"\n  Native 90nm model  — Mean R²: {r90['mean_R2']:.4f}")
print(f"  Transfer model     — (see correlations above)")


# ── 5. Dennard scaling rule comparison ───────────────────────────────────────
sep("5. Dennard Scaling vs ML-Transfer Comparison")

rules     = agent_90.tech_scaling_rules()
x_sample  = X_180[0]
x_mapped  = agent_90.transfer(x_sample)[0]

print(f"\n  {'Parameter':<20} {'180nm':>10} {'90nm_ML':>12} {'90nm_Dennard':>14}")
print(f"  {'-'*58}")
for i, name in enumerate(xn):
    ratio_key = None
    if "W" in name: ratio_key = "W_ratio"
    elif "L" in name: ratio_key = "L_ratio"
    elif "C" in name: ratio_key = "C_ratio"
    elif "VDD" in name: ratio_key = "Vdd_ratio"
    dennard = x_sample[i] * rules.get(ratio_key, 1.0) if ratio_key else float("nan")
    print(f"  {name:<20} {x_sample[i]:>10.3f} {x_mapped[i]:>12.3f} "
          f"{dennard:>14.3f}")


# ── 6. Export CSV ─────────────────────────────────────────────────────────────
sep("6. Export Results")

csv_path = export_predictions_csv(
    X_90_te, Y_90_pred, Y_90_te,
    x_names=xn, y_names=yn,
    path="/tmp/tech_transfer_predictions.csv"
)
print(f"  Predictions exported → {csv_path}")
print("\n  Technology transfer example complete ✓")
