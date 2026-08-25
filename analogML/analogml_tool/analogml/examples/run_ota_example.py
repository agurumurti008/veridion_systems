#!/usr/bin/env python3
"""
examples/run_ota_example.py

Complete end-to-end example:
  1. Generate synthetic OTA dataset (no simulator needed)
  2. Parse an example netlist
  3. Train AnalogMLModel
  4. Predict specs for a new design point
  5. Run inverse design (size recommendation)
  6. Show technology transfer to 90nm
  7. Extract symbolic equations
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np
import matplotlib
matplotlib.use("Agg")   # non-interactive backend for CI
import matplotlib.pyplot as plt

from analogml.parsers   import SpiceParser
from analogml.core      import CircuitGraph, FeatureExtractor, build_dataset
from analogml.models    import AnalogMLModel, TechTransferAgent
from analogml.data      import SyntheticCircuitDataset, MultiFidelityDataset


def separator(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print('='*60)


# ─────────────────────────────────────────────────────────────────────────────
# STEP 1 — Generate synthetic data
# ─────────────────────────────────────────────────────────────────────────────
separator("STEP 1: Synthetic Data Generation")

synth = SyntheticCircuitDataset(seed=7)
X, Y, x_names, y_names = synth.generate("ota_5t", n_samples=300,
                                         technology="180nm")
print(f"  Generated {len(X)} samples")
print(f"  Input features  : {x_names}")
print(f"  Output specs    : {y_names}")
print(f"  X shape: {X.shape}   Y shape: {Y.shape}")
print(f"\n  Sample Y (first row):")
for k, v in zip(y_names, Y[0]):
    print(f"    {k:30s} = {v:.3f}")


# ─────────────────────────────────────────────────────────────────────────────
# STEP 2 — Parse netlist → CircuitGraph → FeatureExtractor
# ─────────────────────────────────────────────────────────────────────────────
separator("STEP 2: Netlist Parsing & Graph Encoding")

parser = SpiceParser()
netlist = parser.parse(
    os.path.join(os.path.dirname(__file__), "ota_180nm.sp"),
    technology="180nm"
)
print(f"  Parsed netlist: '{netlist.subckt_name}'")
print(f"  Components : {len(netlist.components)}")
print(f"  Nets       : {len(netlist.nets)}")
print(f"  Pins       : {[(p.name, p.pin_type) for p in netlist.pins]}")

graph = CircuitGraph.from_netlist(netlist, technology="180nm")
print(f"\n  Graph nodes  : {list(graph.G.nodes)}")
fp = graph.structural_fingerprint()
print(f"  Structural fingerprint dim: {fp.shape}")

fe = FeatureExtractor()
x_graph = fe.extract(graph)
print(f"  Feature vector dim: {x_graph.shape}")


# ─────────────────────────────────────────────────────────────────────────────
# STEP 3 — Train model
# ─────────────────────────────────────────────────────────────────────────────
separator("STEP 3: Model Training")

# Train / test split
split = int(0.8 * len(X))
idx   = np.random.permutation(len(X))
X_tr, Y_tr = X[idx[:split]], Y[idx[:split]]
X_te, Y_te = X[idx[split:]], Y[idx[split:]]

model = AnalogMLModel(mode="fast",    # use 'nn' for PINN if torch available
                      output_names=y_names)
model.fit(X_tr, Y_tr, X_val=X_te, Y_val=Y_te, epochs=200)
print(f"  Training complete.  Final loss: {model.history['loss'][-1]:.4f}")


# ─────────────────────────────────────────────────────────────────────────────
# STEP 4 — Predict without simulation
# ─────────────────────────────────────────────────────────────────────────────
separator("STEP 4: Simulation-less Prediction")

x_test  = X_te[0:1]
y_true  = Y_te[0]
y_pred  = model.predict(x_test)[0]

print(f"\n  {'Spec':<30} {'Predicted':>12} {'True':>12} {'Error%':>8}")
print(f"  {'-'*64}")
for name, yp, yt in zip(y_names, y_pred, y_true):
    err = abs(yp - yt) / (abs(yt) + 1e-9) * 100
    print(f"  {name:<30} {yp:>12.3f} {yt:>12.3f} {err:>7.1f}%")


# ─────────────────────────────────────────────────────────────────────────────
# STEP 5 — Inverse design: size recommendation
# ─────────────────────────────────────────────────────────────────────────────
separator("STEP 5: Inverse Design (Size Recommendation)")

target = {
    "gain_dB"          : 65.0,
    "ugf_MHz"          : 15.0,
    "phase_margin_deg" : 60.0,
    "power_uW"         : 50.0,
}
print(f"  Target specs: {target}")

x_best = model.recommend_sizes(target, X_candidates=X_tr, n_candidates=len(X_tr))
y_best = model.predict(x_best.reshape(1,-1))[0]

print(f"\n  Recommended sizes:")
for name, xv in zip(x_names, x_best):
    print(f"    {name:<20} = {xv:.3f}")
print(f"\n  Predicted performance:")
for name, yv in zip(y_names, y_best):
    print(f"    {name:<30} = {yv:.3f}")


# ─────────────────────────────────────────────────────────────────────────────
# STEP 6 — Technology transfer 180nm → 90nm
# ─────────────────────────────────────────────────────────────────────────────
separator("STEP 6: Technology Transfer 180nm → 90nm")

synth_90 = SyntheticCircuitDataset(seed=99)
X_90, Y_90, _, _ = synth_90.generate("ota_5t", n_samples=200, technology="90nm")

agent = TechTransferAgent(source_tech="180nm", target_tech="90nm")
agent.fit(X_tr, X_90[:len(X_tr)])

x_180 = X_te[0]
x_90_est = agent.transfer(x_180)[0]
print(f"\n  Original 180nm sizes : W1={x_180[0]:.2f}μm  L1={x_180[1]:.2f}μm")
print(f"  Estimated 90nm sizes : W1={x_90_est[0]:.2f}μm  L1={x_90_est[1]:.2f}μm")

rules = agent.tech_scaling_rules()
print(f"\n  Dennard scaling rules (180nm→90nm):")
for k, v in rules.items():
    print(f"    {k:<25} ×{v:.3f}")


# ─────────────────────────────────────────────────────────────────────────────
# STEP 7 — Save model
# ─────────────────────────────────────────────────────────────────────────────
separator("STEP 7: Model Persistence")

save_path = "/tmp/analogml_ota_model"
model.save(save_path)
print(f"  Model saved to: {save_path}")

loaded = AnalogMLModel.load(save_path)
y_loaded = loaded.predict(x_test)[0]
match = np.allclose(y_pred, y_loaded, rtol=1e-3)
print(f"  Reload check: {'PASS ✓' if match else 'FAIL ✗'}")


# ─────────────────────────────────────────────────────────────────────────────
# STEP 8 — Visualize
# ─────────────────────────────────────────────────────────────────────────────
separator("STEP 8: Visualization")

fig, axes = plt.subplots(2, 3, figsize=(14, 8))
fig.suptitle("AnalogML — OTA 180nm Prediction vs Truth", fontsize=14)

for i, (name, ax) in enumerate(zip(y_names[:6], axes.flatten())):
    y_all_pred = model.predict(X_te)[:, i]
    y_all_true = Y_te[:, i]
    ax.scatter(y_all_true, y_all_pred, alpha=0.5, s=15, c="#2196F3")
    mn, mx = y_all_true.min(), y_all_true.max()
    ax.plot([mn, mx], [mn, mx], "r--", lw=1.5, label="ideal")
    r2 = np.corrcoef(y_all_true, y_all_pred)[0,1]**2
    ax.set_title(f"{name}\nR²={r2:.3f}", fontsize=9)
    ax.set_xlabel("True", fontsize=8)
    ax.set_ylabel("Pred", fontsize=8)

plt.tight_layout()
out_png = "/tmp/analogml_ota_results.png"
plt.savefig(out_png, dpi=120)
print(f"  Plot saved to: {out_png}")

separator("ALL STEPS COMPLETE")
print("""
  Summary:
    ✓ Netlist parsed → name-agnostic graph encoding
    ✓ Multi-output model trained on synthetic OTA data
    ✓ Simulation-less spec prediction
    ✓ Inverse design: size recommendation to meet specs
    ✓ Technology transfer 180nm → 90nm
    ✓ Model saved and reloaded
    ✓ Parity plot generated
""")
