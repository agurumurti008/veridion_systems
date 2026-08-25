"""
examples/example2_ota_csv.py
OTA CSV round-trip + model comparison + pole-zero extraction.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

try:
    import torch
except ImportError:
    import torch_shim  # noqa
    import torch

import numpy as np
import math

print("=" * 60)
print("  Example 2 — OTA CSV Round-Trip + Model Comparison")
print("=" * 60)

os.makedirs('output', exist_ok=True)

# ── 1. Generate OTA CSV ─────────────────────────────────────────────────────
from data.pipeline import SyntheticDataGenerator

gen = SyntheticDataGenerator(ip_type='OTA', seed=99)
csv_path = 'output/ota_synthetic_400.csv'
gen.export_csv(n_samples=400, filepath=csv_path)
print(f"\n[Example2] OTA CSV → {csv_path}")

# ── 2. Load CSV and inspect ─────────────────────────────────────────────────
data = gen.load_from_csv(csv_path)
from core.tensor_utils import to_np; X_np = to_np(data['X']).astype(np.float32)
Y_np = to_np(data['Y']).astype(np.float32)
print(f"  Shape: X={X_np.shape}, Y={Y_np.shape}")
print(f"  First 3 rows (features): ")
for i in range(min(3, len(X_np))):
    vals = ', '.join(f'{v:.4g}' for v in X_np[i])
    print(f"    [{vals}]")

# ── 3. Build OTA specKG ─────────────────────────────────────────────────────
from core.spec_kg.knowledge_graph import build_ota_kg
kg = build_ota_kg()
kg.summary()

# ── 4. FSM on synthetic OTA signals ────────────────────────────────────────
print("\n── FSM on OTA Signals ──")
from core.fsm.signal_capture import SignalCapture
from core.fsm.state_detector import FSMStateDetector
from core.fsm.transition_learner import TransitionLearner

sc = SignalCapture(spec_kg=kg)
sc.load_synthetic(n_points=800, t_end=5e-6, ip_type='OTA')
print(f"  Signals: {list(sc.signals.keys())}")
print(f"  Digital: {sc.digital_signals}, Analog: {sc.analog_signals}")

lm, ln, lt = sc.get_logic_signal_matrix()
af = sc.get_analog_features(n_windows=8)

detector = FSMStateDetector(strategy='hybrid', spec_kg=kg)
seq = detector.detect(lm, ln, af)
detector.print_summary()

learner = TransitionLearner(fsm_tree_depth=3)
transitions = learner.learn(seq, lm, ln, detector.state_defs)
print(f"  Transitions found: {len(transitions)}")

# ── 5. Phase 2: PINN vs GPR ─────────────────────────────────────────────────
print("\n── Phase 2: PINN vs GPR ──")
from core.phases.phase2_sim_augmented import Phase2SimAugmented
from core.models.gpr_surrogate import ModelSelector

active_bridges = kg.get_bridges_for_keys(['AC', 'PSRR', 'CMRR'])
input_dim  = X_np.shape[1]
output_dim = Y_np.shape[1]

phase2 = Phase2SimAugmented(kg, use_wandb=False)
phase2.initialize_models(
    input_dim=input_dim,
    output_dim=output_dim,
    n_fsm_states=len(kg.fsm_states),
    state_dim=2,
    user_bridges=active_bridges,
    model_names=['PINN', 'GPR'],
)

metrics = phase2.incremental_train(
    data=data,
    analysis_data={'phase_margin': 65.0, 'gain_bandwidth': 50e6, 'cmrr_dc': 80.0},
    iteration=0,
    epochs=80,
)

mse_dict = {k: v['test_mse'] for k, v in metrics.items()}
best_name = ModelSelector.select_best(mse_dict, phase2.models)

print("\n  Accuracy Comparison:")
print(f"  {'Model':<10} {'MSE':>12}  {'Winner'}")
print(f"  {'-'*30}")
for name, mse in sorted(mse_dict.items(), key=lambda x: x[1]):
    marker = '← WINNER' if name == best_name else ''
    print(f"  {name:<10} {mse:>12.6f}  {marker}")

# ── 6. Pole-Zero Extraction ──────────────────────────────────────────────────
print("\n── Pole-Zero Extraction from Synthetic AC Curve ──")
from core.interpretability.symbolic_regression import PoleZeroExtractor

# Generate synthetic AC curve
freq = np.logspace(4, 9, 200)   # 10kHz to 1GHz
gbw = 50e6
fp1 = gbw / 50
dc_gain_db = 60.0
mag_db = dc_gain_db - 20 * np.log10(
    np.sqrt(1 + (freq / fp1) ** 2) * np.sqrt(1 + (freq / (gbw * 5)) ** 2)
)

pz = PoleZeroExtractor.extract_from_ac_curve(freq, mag_db)
print(f"  fp1          = {pz['fp1']:.3g} Hz")
print(f"  fug (UGF)    = {pz['fug']:.3g} Hz")
print(f"  DC gain      = {pz['dc_gain_db']:.2f} dB")
print(f"  Rolloff slope= {pz['slope_dbdec']:.1f} dB/decade")

# ── 7. Symbolic Equation Extraction ─────────────────────────────────────────
print("\n── Symbolic Equation R² for All Outputs ──")
interp = phase2.extract_interpretable(
    X_np, gen.feature_names, gen.output_names
)

print(f"\n  {'Output':<20} {'R²':>8}  {'Validity'}")
print(f"  {'-'*55}")
for name, res in interp.items():
    r2 = res.get('r2', 0.0)
    valid = res.get('validity', 'unknown')[:25]
    print(f"  {name:<20} {r2:>8.3f}  {valid}")

# ── 8. Sensitivity Report ───────────────────────────────────────────────────
print("\n── Top-3 Sensitivity Features per Output ──")
from core.interpretability.symbolic_regression import CircuitSymbolicExtractor

# Use best model predictions for sensitivity
if phase2.best_model_name == 'GPR' and 'GPR' in phase2.models:
    Y_pred, _ = phase2.models['GPR'].predict(X_np)
else:
    Y_pred = Y_np

extractor = CircuitSymbolicExtractor(gen.feature_names, gen.output_names)
extractor.results = interp  # reuse extracted results
sensitivity = extractor.sensitivity_report(X_np)

for out_name in list(gen.output_names)[:4]:
    if out_name in sensitivity:
        smap = sensitivity[out_name]
        top3 = sorted(smap.items(), key=lambda x: x[1], reverse=True)[:3]
        features_str = ', '.join(f'{n}({v:.3f})' for n, v in top3)
        print(f"  {out_name:<20}: {features_str}")

print("\n" + "=" * 60)
print("  Example 2 COMPLETE")
print("=" * 60)
