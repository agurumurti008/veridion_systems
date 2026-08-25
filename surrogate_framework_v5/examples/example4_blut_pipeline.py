"""
examples/example4_blut_pipeline.py
End-to-end BLUT -> FSM -> Phase2 -> Verilog-A walkthrough.

Since no real .blut file is available in this environment, this example
builds a synthetic multi-run BLUT in-memory using the vendored
digitwin.blut_format write functions (the same functions
digitwin_blut_builder.py itself uses) — three runs standing in for the
kind of regression file a real digiTwin export would produce:
    - line_transient     (Vin stepped)
    - load_transient     (Iload stepped)
    - corner_ff_125c     (PVT corner sweep)

To use a REAL BLUT file instead, skip the "build a synthetic BLUT" section
below and just point BLUT_PATH at your file — everything downstream
(discovery, signal_map, FSM detection, Phase 2 training, Verilog-A
generation) works identically either way.
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
import tempfile

print("=" * 60)
print("  Example 4 — digiTwin BLUT Pipeline (multi-run)")
print("=" * 60)

os.makedirs('output', exist_ok=True)

# ── 1. Build a synthetic multi-run BLUT in-memory ───────────────────────────
print("\n── Step 1: Building synthetic multi-run BLUT (stand-in for a real file) ──")
print("  NOTE: to use a real file, just set BLUT_PATH = '/path/to/regression.blut'")
print("        and skip straight to Step 2 — every step below is identical.")

import digitwin.blut_format as bf

BLUT_PATH = tempfile.mktemp(suffix='.blut')

RUN_SPECS = [
    ('line_transient', 'stim=vin_step,corner=tt'),
    ('load_transient', 'stim=iload_step,corner=tt'),
    ('corner_ff_125c', 'stim=nominal,corner=ff,temp=125'),
]
N_PER_RUN = 200

with open(BLUT_PATH, 'wb') as f:
    bf.write_file_header(f, n_runs=len(RUN_SPECS))
    for run_idx, (run_id, meta) in enumerate(RUN_SPECS):
        run_off = f.tell()
        times = np.linspace(0, 100e-6, N_PER_RUN)
        bf.write_run_header(f, run_idx, run_id, meta, times)

        # EN: low for first 10%, then high (startup -> regulation).
        # Using 10% (not 5%) keeps clear of the _is_bimodal near-rail
        # threshold's exact-boundary edge case at exactly 5.0%.
        en = np.zeros(N_PER_RUN)
        en[int(0.10 * N_PER_RUN):] = 1.0

        # VOUT: exponential startup ramp to 1.8V, then regulation with
        # small per-run perturbations that emulate line/load/corner effects
        tau = 100e-6 * 0.1
        vout_base = 1.8 * (1 - np.exp(-times / tau))
        if run_id == 'line_transient':
            vin = 3.3 + 1.5 * (times / times[-1])  # Vin ramps 3.3V -> 4.8V
            vout = vout_base + 0.01 * np.sin(2 * np.pi * 5e3 * times)
        elif run_id == 'load_transient':
            vin = np.full(N_PER_RUN, 3.3)
            iload = 0.05 + 0.4 / (1 + np.exp(-2e5 * (times - 50e-6)))
            vout = vout_base - 0.02 * (iload - iload[0])
        else:  # corner_ff_125c
            vin = np.full(N_PER_RUN, 3.3)
            vout = vout_base * 1.02  # fast corner -> slightly higher Vout

        if run_id != 'load_transient':
            iload = np.full(N_PER_RUN, 0.1)
        iout = iload  # current probe mirrors load current for this synthetic example

        # FAULT: brief fault only in the load_transient run, near the end
        fault = np.zeros(N_PER_RUN)
        if run_id == 'load_transient':
            fault[int(0.9 * N_PER_RUN):] = 1.0

        idxs = np.arange(N_PER_RUN)
        n_sig = 0
        bf.write_signal_block(f, 'top.u1.vin',  idxs, vin,  bf.ENC_FLOAT64, 0.0, 1.0, compress=False); n_sig += 1
        bf.write_signal_block(f, 'top.u1.vout', idxs, vout, bf.ENC_FLOAT64, 0.0, 1.0, compress=False); n_sig += 1
        bf.write_signal_block(f, 'top.u1.en',   idxs, en,   bf.ENC_FLOAT64, 0.0, 1.0, compress=False); n_sig += 1
        bf.write_signal_block(f, 'top.u1.fault', idxs, fault, bf.ENC_FLOAT64, 0.0, 1.0, compress=False); n_sig += 1
        bf.write_signal_block(f, 'top.u1.vout$flow', idxs, iout, bf.ENC_FLOAT64, 0.0, 1.0, compress=False); n_sig += 1
        bf.patch_run_n_signals(f, run_off, n_sig)
    bf.patch_file_header_counts(f, len(RUN_SPECS))

print(f"  Synthetic BLUT written → {BLUT_PATH}")
print(f"  Runs: {[r[0] for r in RUN_SPECS]}, {N_PER_RUN} samples/run")

# ── 2. Discovery: list_all_signal_base_names + auto_suggest ─────────────────
print("\n── Step 2: Signal Discovery ──")
from digitwin.blut_reader_ext import open_blut, list_all_signal_base_names, print_signal_discovery_table
from digitwin.spec_signal_map import SignalMap, SignalMapEntry

blut = open_blut(BLUT_PATH)
discovered = list_all_signal_base_names(blut)
print_signal_discovery_table(discovered)

from core.spec_kg.knowledge_graph import build_ldo_kg
kg = build_ldo_kg()
suggestions = SignalMap().auto_suggest(kg, discovered)

# ── 3. Apply a hand-written SignalMap covering VIN/VOUT/EN/IOUT ─────────────
print("── Step 3: Applying hand-written SignalMap ──")
signal_map = SignalMap([
    SignalMapEntry('VIN',   'top.u1.vin',   'voltage'),
    SignalMapEntry('VOUT',  'top.u1.vout',  'voltage'),
    SignalMapEntry('EN',    'top.u1.en',    'voltage'),
    SignalMapEntry('FAULT', 'top.u1.fault', 'voltage'),
    SignalMapEntry('IOUT',  'top.u1.vout',  'current'),
])
kg.apply_signal_map(signal_map)
signal_map.print_unmapped_warning(kg)

# ── 4. FSM detection across ALL 3 runs ──────────────────────────────────────
print("── Step 4: FSM Detection Across All Runs ──")
from core.fsm.signal_capture import SignalCapture
from core.fsm.state_detector import FSMStateDetector
from core.fsm.transition_learner import TransitionLearner
from core.fsm.fsm_codegen import FSMValidator, FSMCodeGenerator

sc = SignalCapture(spec_kg=kg)
sc.load_from_blut(BLUT_PATH, run_id=None, signal_map=signal_map)
print(f"  Concatenated samples: {len(sc.time)}  (run_boundaries={sc.run_boundaries})")
print(f"  Voltage signals: {list(sc.signals.keys())}")
print(f"  Current signals: {list(sc.current_signals.keys())}")

lm, ln, lt = sc.get_logic_signal_matrix()
af = sc.get_analog_features(n_windows=15)

detector = FSMStateDetector(strategy='hybrid', spec_kg=kg)
state_seq = detector.detect(lm, ln, af)
detector.print_summary()

boundary_mask = sc.get_boundary_mask()
learner = TransitionLearner(fsm_tree_depth=4)
transitions = learner.learn(state_seq, lm, ln, detector.state_defs, boundary_mask=boundary_mask)
learner.print_summary()

# Confirm no transition spans a run seam: every learned transition's
# probability was estimated with seam pairs excluded (Section 5 guarantee).
n_seams = int(boundary_mask.sum())
print(f"  Run seams in concatenated sequence: {n_seams} "
      f"(all excluded from transition training by construction)")

validator = FSMValidator(spec_kg=kg)
report = validator.validate(detector.state_defs, transitions, ip_type='LDO')
print(f"  Validation: reachability={report.reachability}, "
      f"completeness={report.completeness}, determinism={report.determinism}")

codegen = FSMCodeGenerator(spec_kg=kg, ip_type='LDO')
fsm_va = codegen.generate_veriloga(detector.state_defs, transitions, kg.ports)

# ── 5. Phase 2: build_dataset_from_blut + incremental_train ─────────────────
print("\n── Step 5: Phase 2 Training on BLUT-Sourced Multi-Run Data ──")
from core.phases.phase2_sim_augmented import Phase2SimAugmented
from core.models.gpr_surrogate import ModelSelector

phase2 = Phase2SimAugmented(kg, use_wandb=False)
data = phase2.build_dataset_from_blut(
    BLUT_PATH, signal_map,
    input_signal_names=['VIN', 'EN'],
    output_signal_names=['VOUT', 'IOUT'],
    fsm_detector=FSMStateDetector(strategy='logic', spec_kg=kg),
)
print(f"  Dataset rows: {data['X'].shape[0] if hasattr(data['X'],'shape') else len(data['X'])}")
print(f"  feature_names: {data['feature_names']}")
print(f"  output_names:  {data['output_names']}")
print(f"  Contributing runs: {sorted(set(data['run_ids']))}")

input_dim  = data['X'].shape[1] if hasattr(data['X'], 'shape') else len(data['X'][0])
output_dim = data['Y'].shape[1] if hasattr(data['Y'], 'shape') else len(data['Y'][0])

phase2.initialize_models(
    input_dim=input_dim, output_dim=output_dim,
    n_fsm_states=len(kg.fsm_states) or 4, state_dim=2,
    user_bridges=kg.get_bridges_for_keys(['AC', 'PSRR', 'DC']),
    model_names=['PINN', 'GPR'],
)
metrics = phase2.incremental_train(data=data, epochs=100)

mse_dict = {k: v['test_mse'] for k, v in metrics.items()}
best_name = ModelSelector.select_best(mse_dict, phase2.models)
print(f"  Best model: {best_name}")

# ── 6. digiTwin as state-transition reference/filler ────────────────────────
print("\n── Step 6: digiTwin as State-Transition Reference/Filler ──")
from core.phases.blut_reference import (
    find_thin_states, fill_missing_state_transient,
    compare_model_to_blut_reference, StateReferenceNotFoundError,
)
from digitwin.blut_reader_ext import open_blut as _open_blut_step6

thin_states = find_thin_states(state_seq, detector.state_defs, min_samples=20)
print(f"  Thin state(s) in primary training data (< 20 samples): {thin_states}")

# Build per-run dicts with SIGNAL-MAP-RENAMED columns (not raw BLUT names),
# since fill_missing_state_transient's signal_names filter matches against
# whatever names appear in each run dict's voltage_names/current_names —
# SignalCapture.load_from_blut is what performs that renaming, so we build
# each run dict from it rather than from a bare load_all_runs() call (which
# only ever sees raw BLUT names and has no signal_map argument of its own).
_blut_for_step6 = _open_blut_step6(BLUT_PATH)
per_run_detector = FSMStateDetector(strategy='logic', spec_kg=kg)
all_run_dicts = []
# v8: qualify each run with its corner when non-empty so
# SignalCapture.load_from_blut resolves the exact (run_id, corner_id).
_run_qids = [rid if not cid else f"{rid}@{cid}"
             for rid, cmap in _blut_for_step6.runs.items() for cid in cmap.keys()]
for run_id in _run_qids:
    sc_run = SignalCapture(spec_kg=kg)
    sc_run.load_from_blut(BLUT_PATH, run_id=run_id, signal_map=signal_map)
    lm_r, ln_r, _ = sc_run.get_logic_signal_matrix()
    af_r = sc_run.get_analog_features(n_windows=min(10, max(2, len(sc_run.time) // 10)))
    run_state_seq = per_run_detector.detect(lm_r, ln_r, af_r)

    voltage_names = list(sc_run.signals.keys())
    voltage_matrix = (np.column_stack([sc_run.signals[n] for n in voltage_names])
                       if voltage_names else np.zeros((len(sc_run.time), 0)))
    current_names = list(sc_run.current_signals.keys())
    current_matrix = (np.column_stack([sc_run.current_signals[n] for n in current_names])
                        if current_names else np.zeros((len(sc_run.time), 0)))

    all_run_dicts.append({
        'run_id': run_id,
        'time': sc_run.time,
        'voltage_names': voltage_names,
        'voltage_matrix': voltage_matrix,
        'current_names': current_names,
        'current_matrix': current_matrix,
        'state_sequence': run_state_seq,
        'state_defs': per_run_detector.state_defs,
    })

target_state = thin_states[0] if thin_states else next(iter(
    s['name'] for s in detector.state_defs.values()
))
try:
    reference = fill_missing_state_transient(
        detector.state_defs, transitions, all_run_dicts, target_state,
        signal_names=['VOUT', 'IOUT'],
    )
    print(f"  Pulled BLUT reference for state '{target_state}': shape {reference.shape}")

    # Compare against a trivial constant "model output" for illustration —
    # a real caller would pass the trained surrogate's prediction here.
    dummy_model_pred = np.tile(reference.mean(axis=0), (reference.shape[0], 1))
    comparison = compare_model_to_blut_reference(dummy_model_pred, reference)
    print(f"  Model-vs-BLUT-reference comparison for '{target_state}': {comparison}")
except StateReferenceNotFoundError as e:
    print(f"  No BLUT reference available for '{target_state}': {e}")

# ── 7. Generate Phase 2 Verilog-A ────────────────────────────────────────────
print("\n── Step 7: Phase 2 Verilog-A Generation ──")
interp = phase2.extract_interpretable(data['X'], data['feature_names'], data['output_names'])
p2_path = phase2.generate_phase2_veriloga(
    fsm_code=fsm_va, interpretable=interp, output_dir='output',
)
print(f"  Phase 2 Verilog-A → {p2_path}")

os.unlink(BLUT_PATH)

print("\n" + "=" * 60)
print("  Example 4 COMPLETE")
print("=" * 60)
