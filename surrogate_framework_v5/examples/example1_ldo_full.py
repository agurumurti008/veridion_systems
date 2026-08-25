"""
examples/example1_ldo_full.py
LDO Phase 1 + FSM + Phase 2 full walkthrough.
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

print("=" * 60)
print("  Example 1 — LDO Full Pipeline")
print("=" * 60)

# ── 1. Build specKG and export ──────────────────────────────────────────────
from core.spec_kg.knowledge_graph import build_ldo_kg
import tempfile, json

kg = build_ldo_kg()
kg.summary()

kg_json_path = os.path.join('output', 'ldo_speckg_example1.json')
os.makedirs('output', exist_ok=True)
kg.export_to_json(kg_json_path)
print(f"[Example1] SpecKG exported → {kg_json_path}")

# ── 2. Phase 1 ──────────────────────────────────────────────────────────────
print("\n── Phase 1: Spec-Based Code Generation ──")
from core.phases.phase1_spec_based import Phase1SpecBasedGenerator

gen1 = Phase1SpecBasedGenerator(kg)
va_path, sv_path = gen1.generate_all(fsm_code='', output_dir='output')
print(f"  Verilog-A: {va_path}")
print(f"  SystemVerilog: {sv_path}")

# ── 3. FSM Derivation ───────────────────────────────────────────────────────
print("\n── FSM Auto-Derivation ──")
from core.fsm.signal_capture import SignalCapture
from core.fsm.state_detector import FSMStateDetector
from core.fsm.transition_learner import TransitionLearner
from core.fsm.fsm_codegen import FSMValidator, FSMCodeGenerator

sc = SignalCapture(spec_kg=kg)
sc.load_synthetic(n_points=1000, t_end=100e-6, ip_type='LDO')
print(f"  Signals loaded: {list(sc.signals.keys())}")
print(f"  Digital: {sc.digital_signals}")
print(f"  Analog:  {sc.analog_signals}")

lm, ln, lt = sc.get_logic_signal_matrix()
af = sc.get_analog_features(n_windows=10)

detector = FSMStateDetector(strategy='hybrid', spec_kg=kg)
seq = detector.detect(lm, ln, af)
detector.print_summary()

print(f"  State count: {len(detector.state_defs)}")

learner = TransitionLearner(fsm_tree_depth=4)
transitions = learner.learn(seq, lm, ln, detector.state_defs)
learner.print_summary()
print(f"  Transition count: {len(transitions)}")

validator = FSMValidator(spec_kg=kg)
report = validator.validate(detector.state_defs, transitions, ip_type='LDO')
print(f"  Validation: reachability={report.reachability}, "
      f"completeness={report.completeness}, determinism={report.determinism}")
print(f"  specKG coverage: {report.speckg_coverage:.1%}")

codegen = FSMCodeGenerator(spec_kg=kg, ip_type='LDO')
fsm_va = codegen.generate_veriloga(detector.state_defs, transitions, kg.ports)
fsm_sv = codegen.generate_systemverilog(detector.state_defs, transitions)

fsm_va_path = 'output/ldo_fsm_example1.vams'
fsm_sv_path = 'output/ldo_fsm_example1.sv'
with open(fsm_va_path, 'w', encoding='utf-8') as f: f.write(fsm_va)
with open(fsm_sv_path, 'w', encoding='utf-8') as f: f.write(fsm_sv)
print(f"  FSM Verilog-A: {fsm_va_path}")
print(f"  FSM SystemVerilog: {fsm_sv_path}")

# ── 4. Phase 2 Training ─────────────────────────────────────────────────────
print("\n── Phase 2: PINN + GPR Training ──")
from data.pipeline import SyntheticDataGenerator
from core.phases.phase2_sim_augmented import Phase2SimAugmented
from core.models.gpr_surrogate import ModelSelector

gen_data = SyntheticDataGenerator(ip_type='LDO', seed=42)
data = gen_data.to_torch_dataset(n_samples=300, include_transient=False)

from core.tensor_utils import to_np; X_np = to_np(data['X']).astype(np.float32)
Y_np = to_np(data['Y']).astype(np.float32)
input_dim  = X_np.shape[1]
output_dim = Y_np.shape[1]

active_bridges = kg.get_bridges_for_keys(['AC', 'PSRR', 'DC'])

phase2 = Phase2SimAugmented(kg, use_wandb=False)
phase2.initialize_models(
    input_dim=input_dim,
    output_dim=output_dim,
    n_fsm_states=len(kg.fsm_states),
    state_dim=2,
    user_bridges=active_bridges,
    model_names=['PINN', 'GPR'],
)

analysis_data = {
    'phase_margin': 60.0,
    'gain_bandwidth': 50e6,
    'psrr_dc': 80.0,
    'dc_op': 1.8,
}

metrics = phase2.incremental_train(
    data=data,
    analysis_data=analysis_data,
    iteration=0,
    epochs=100,
)

mse_dict = {k: v['test_mse'] for k, v in metrics.items()}
best_name = ModelSelector.select_best(mse_dict, phase2.models)
print(f"\n  Best model: {best_name}")
for name, m in metrics.items():
    print(f"  {name:<8} MSE = {m['test_mse']:.6f}")

# ── 5. Symbolic Extraction ──────────────────────────────────────────────────
print("\n── Symbolic Equation Extraction ──")
interp = phase2.extract_interpretable(
    X_np, gen_data.feature_names, gen_data.output_names
)

print(f"\n  {'Output':<20} {'Equation':<45} {'R²':>6}")
print(f"  {'-'*74}")
for name, res in list(interp.items())[:5]:
    eq = res.get('equation', '')[:40]
    r2 = res.get('r2', 0.0)
    print(f"  {name:<20} {eq:<45} {r2:>6.3f}")

# ── 6. Active Bridge Summary ─────────────────────────────────────────────────
print("\n── Active Bridge Summary ──")
print(f"  {'Bridge Key':<30} {'Transient Effect'}")
print(f"  {'-'*55}")
for bkey, binfo in active_bridges.items():
    print(f"  {bkey:<30} {binfo['transient_effect']}")

# ── 7. Phase 2 Verilog-A ────────────────────────────────────────────────────
p2_path = phase2.generate_phase2_veriloga(
    fsm_code=fsm_va, interpretable=interp, output_dir='output'
)
print(f"\n  Phase 2 Verilog-A: {p2_path}")

print("\n" + "=" * 60)
print("  Example 1 COMPLETE")
print("=" * 60)
