#!/usr/bin/env python3
"""
examples/run_ldo_example.py  —  LDO Regulator prediction + multi-fidelity demo
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np
from analogml.data   import SyntheticCircuitDataset, MultiFidelityDataset
from analogml.models import AnalogMLModel, MultiFidelityGP


def sep(t): print(f"\n{'─'*55}\n  {t}\n{'─'*55}")


# ── 1. Generate LDO data ─────────────────────────────────────────────────────
sep("LDO Dataset Generation")
synth = SyntheticCircuitDataset(seed=11)
X, Y, xn, yn = synth.generate("ldo", n_samples=400, technology="180nm")
print(f"  {len(X)} samples  |  X{X.shape}  Y{Y.shape}")
print(f"  Inputs : {xn}")
print(f"  Outputs: {yn}")


# ── 2. Multi-fidelity dataset ─────────────────────────────────────────────────
sep("Multi-Fidelity Data")
mf = MultiFidelityDataset()
mf.from_synthetic("ldo", n_low=300, n_high=60, tech="180nm")
print(f"  Low-fidelity  : {mf.X_low.shape}  High-fidelity: {mf.X_high.shape}")
print(f"  Average gain drop (layout parasitics):")
for i, name in enumerate(yn[:3]):
    diff = np.mean(mf.Y_high[:,i]) - np.mean(mf.Y_low[:mf.X_high.shape[0],i])
    print(f"    {name:<30}: Δ = {diff:+.3f}")


# ── 3. Train ─────────────────────────────────────────────────────────────────
sep("Training LDO Model")
split = int(0.8 * len(X))
perm  = np.random.permutation(len(X))
model = AnalogMLModel(mode="fast", output_names=yn)
model.fit(X[perm[:split]], Y[perm[:split]], epochs=150)
print(f"  Done. Loss = {model.history['loss'][-1]:.5f}")


# ── 4. PSRR / dropout analysis ─────────────────────────────────────────────
sep("Spec Prediction — PSRR & Dropout Analysis")
X_te = X[perm[split:]]
Y_te = Y[perm[split:]]
Y_p  = model.predict(X_te)

psrr_idx   = yn.index("psrr_dB")
drop_idx   = yn.index("dropout_mV")
print(f"\n  {'':>5}  {'PSRR True':>12} {'PSRR Pred':>12} "
      f"{'Drop True':>12} {'Drop Pred':>12}")
for i in range(min(8, len(X_te))):
    print(f"  [{i:2d}]  {Y_te[i,psrr_idx]:12.1f} {Y_p[i,psrr_idx]:12.1f} "
          f"{Y_te[i,drop_idx]:12.1f} {Y_p[i,drop_idx]:12.1f}")


# ── 5. Inverse: design for target PSRR ──────────────────────────────────────
sep("Inverse Design for PSRR ≥ 60 dB, Dropout ≤ 200 mV")
target = {"psrr_dB": 62.0, "dropout_mV": 180.0, "quiescent_uA": 20.0}
xbest = model.recommend_sizes(target, X_candidates=X_te)
ybest = model.predict(xbest.reshape(1,-1))[0]
print("  Recommended design:")
for n, v in zip(xn, xbest): print(f"    {n:<20} = {v:.3f}")
print("  Predicted specs:")
for n, v in zip(yn, ybest):  print(f"    {n:<30} = {v:.3f}")

print("\n  LDO example complete ✓")
