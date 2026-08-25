"""
tests/test_framework.py
≥28 tests for the surrogate_framework. All must pass.
"""
import sys
import os
import traceback
import numpy as np

# ── Path bootstrap ────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

try:
    import torch
except ImportError:
    import torch_shim  # noqa
    import torch


TESTS = []


def test(fn):
    TESTS.append((fn.__name__, fn))
    return fn


# ═══════════════════════════════════════════════════════════════════════════════
# specKG tests
# ═══════════════════════════════════════════════════════════════════════════════

@test
def test_ldo_kg_build():
    from core.spec_kg.knowledge_graph import build_ldo_kg
    kg = build_ldo_kg()
    assert len(kg.ports) >= 4, f"Expected ≥4 ports, got {len(kg.ports)}"
    assert len(kg.specs) >= 5, f"Expected ≥5 specs, got {len(kg.specs)}"
    assert len(kg.physics_rules) >= 3, f"Expected ≥3 rules, got {len(kg.physics_rules)}"


@test
def test_ota_kg_build():
    from core.spec_kg.knowledge_graph import build_ota_kg
    kg = build_ota_kg()
    assert len(kg.ports) >= 4
    assert len(kg.specs) >= 5
    assert len(kg.physics_rules) >= 3


@test
def test_kg_json_roundtrip():
    from core.spec_kg.knowledge_graph import build_ldo_kg
    import tempfile
    kg = build_ldo_kg()
    with tempfile.NamedTemporaryFile(suffix='.json', delete=False, mode='w') as f:
        path = f.name
    try:
        kg.export_to_json(path)
        from core.spec_kg.knowledge_graph import SpecKG
        kg2 = SpecKG.from_json(path)
        names1 = {p.name for p in kg.ports}
        names2 = {p.name for p in kg2.ports}
        assert names1 == names2, f"Port names mismatch: {names1} vs {names2}"
    finally:
        os.unlink(path)


@test
def test_kg_physics_rules_list():
    from core.spec_kg.knowledge_graph import build_ldo_kg
    kg = build_ldo_kg()
    terms = kg.get_physics_loss_terms()
    assert isinstance(terms, list)
    assert len(terms) >= 1
    for t in terms:
        assert 'type' in t and 'equation' in t


@test
def test_kg_analysis_bridge_filtering():
    from core.spec_kg.knowledge_graph import build_ldo_kg
    kg = build_ldo_kg()
    active = kg.get_active_analysis_bridges({'AC.phase_margin': True, 'PSRR.psrr_dc': True})
    assert isinstance(active, dict)
    assert 'AC.phase_margin' in active


@test
def test_kg_fsm_ports():
    from core.spec_kg.knowledge_graph import build_ldo_kg
    kg = build_ldo_kg()
    fsm_ports = kg.get_fsm_relevant_ports()
    assert len(fsm_ports) >= 1


# ═══════════════════════════════════════════════════════════════════════════════
# Signal capture tests
# ═══════════════════════════════════════════════════════════════════════════════

@test
def test_signal_capture_synthetic_load():
    from core.fsm.signal_capture import SignalCapture
    sc = SignalCapture()
    sc.load_synthetic(n_points=500, t_end=100e-6, ip_type='LDO')
    assert len(sc.signals) >= 3, f"Expected ≥3 signals, got {len(sc.signals)}"
    assert sc.time is not None


@test
def test_logic_matrix_shape():
    from core.fsm.signal_capture import SignalCapture
    sc = SignalCapture()
    sc.load_synthetic(n_points=500, ip_type='LDO')
    lm, names, t = sc.get_logic_signal_matrix()
    assert lm.ndim == 2
    assert lm.shape[0] == 500
    assert len(names) >= 1


@test
def test_analog_features_not_none():
    from core.fsm.signal_capture import SignalCapture
    sc = SignalCapture()
    sc.load_synthetic(n_points=500, ip_type='LDO')
    af = sc.get_analog_features(n_windows=5)
    assert af is not None


# ═══════════════════════════════════════════════════════════════════════════════
# FSM tests
# ═══════════════════════════════════════════════════════════════════════════════

@test
def test_fsm_logic_strategy():
    from core.fsm.signal_capture import SignalCapture
    from core.fsm.state_detector import FSMStateDetector
    sc = SignalCapture()
    sc.load_synthetic(n_points=500, ip_type='LDO')
    lm, names, t = sc.get_logic_signal_matrix()
    det = FSMStateDetector(strategy='logic')
    seq = det.detect(lm, names)
    assert len(det.state_defs) >= 2, f"Expected ≥2 states, got {len(det.state_defs)}"
    assert len(seq) == 500


@test
def test_fsm_hybrid_strategy():
    from core.fsm.signal_capture import SignalCapture
    from core.fsm.state_detector import FSMStateDetector
    sc = SignalCapture()
    sc.load_synthetic(n_points=500, ip_type='LDO')
    lm, names, t = sc.get_logic_signal_matrix()
    af = sc.get_analog_features(n_windows=5)
    det = FSMStateDetector(strategy='hybrid')
    seq = det.detect(lm, names, analog_features=af)
    assert len(seq) == 500
    assert len(det.state_defs) >= 1


@test
def test_transition_learner():
    from core.fsm.signal_capture import SignalCapture
    from core.fsm.state_detector import FSMStateDetector
    from core.fsm.transition_learner import TransitionLearner
    sc = SignalCapture()
    sc.load_synthetic(n_points=500, ip_type='LDO')
    lm, names, t = sc.get_logic_signal_matrix()
    det = FSMStateDetector(strategy='logic')
    seq = det.detect(lm, names)
    learner = TransitionLearner(fsm_tree_depth=3)
    transitions = learner.learn(seq, lm, names, det.state_defs)
    assert isinstance(transitions, list)


@test
def test_fsm_validator():
    from core.fsm.signal_capture import SignalCapture
    from core.fsm.state_detector import FSMStateDetector
    from core.fsm.transition_learner import TransitionLearner
    from core.fsm.fsm_codegen import FSMValidator
    sc = SignalCapture()
    sc.load_synthetic(n_points=500, ip_type='LDO')
    lm, names, t = sc.get_logic_signal_matrix()
    det = FSMStateDetector(strategy='logic')
    seq = det.detect(lm, names)
    learner = TransitionLearner()
    transitions = learner.learn(seq, lm, names, det.state_defs)
    validator = FSMValidator()
    report = validator.validate(det.state_defs, transitions, ip_type='LDO')
    assert hasattr(report, 'reachability')
    assert hasattr(report, 'determinism')


@test
def test_veriloga_codegen():
    from core.fsm.signal_capture import SignalCapture
    from core.fsm.state_detector import FSMStateDetector
    from core.fsm.transition_learner import TransitionLearner
    from core.fsm.fsm_codegen import FSMCodeGenerator
    from core.spec_kg.knowledge_graph import build_ldo_kg
    sc = SignalCapture()
    sc.load_synthetic(n_points=500, ip_type='LDO')
    lm, names, t = sc.get_logic_signal_matrix()
    det = FSMStateDetector(strategy='logic')
    seq = det.detect(lm, names)
    learner = TransitionLearner()
    transitions = learner.learn(seq, lm, names, det.state_defs)
    kg = build_ldo_kg()
    cg = FSMCodeGenerator(spec_kg=kg, ip_type='LDO')
    va = cg.generate_veriloga(det.state_defs, transitions, kg.ports)
    assert 'endmodule' in va, "Verilog-A missing endmodule"


@test
def test_sv_codegen():
    from core.fsm.signal_capture import SignalCapture
    from core.fsm.state_detector import FSMStateDetector
    from core.fsm.transition_learner import TransitionLearner
    from core.fsm.fsm_codegen import FSMCodeGenerator
    from core.spec_kg.knowledge_graph import build_ldo_kg
    sc = SignalCapture()
    sc.load_synthetic(n_points=500, ip_type='LDO')
    lm, names, t = sc.get_logic_signal_matrix()
    det = FSMStateDetector(strategy='logic')
    seq = det.detect(lm, names)
    learner = TransitionLearner()
    transitions = learner.learn(seq, lm, names, det.state_defs)
    kg = build_ldo_kg()
    cg = FSMCodeGenerator(spec_kg=kg, ip_type='LDO')
    sv = cg.generate_systemverilog(det.state_defs, transitions)
    assert 'typedef enum' in sv, "SV missing typedef enum"
    assert 'always_ff' in sv, "SV missing always_ff"


# ═══════════════════════════════════════════════════════════════════════════════
# Data pipeline tests
# ═══════════════════════════════════════════════════════════════════════════════

@test
def test_ldo_lhs_shape():
    from data.pipeline import SyntheticDataGenerator
    gen = SyntheticDataGenerator(ip_type='LDO', seed=0)
    X, Y = gen.generate_lhs(n_samples=50)
    assert X.shape == (50, 8), f"LDO X shape: {X.shape}"
    assert Y.shape == (50, 8), f"LDO Y shape: {Y.shape}"


@test
def test_ota_lhs_shape():
    from data.pipeline import SyntheticDataGenerator
    gen = SyntheticDataGenerator(ip_type='OTA', seed=0)
    X, Y = gen.generate_lhs(n_samples=50)
    assert X.shape == (50, 8), f"OTA X shape: {X.shape}"
    assert Y.shape == (50, 8), f"OTA Y shape: {Y.shape}"


@test
def test_pvt_corners_45_rows():
    from data.pipeline import SyntheticDataGenerator
    gen = SyntheticDataGenerator(ip_type='LDO', seed=0)
    X, Y = gen.generate_pvt_corners()
    assert X.shape[0] == 45, f"PVT rows: {X.shape[0]}"


@test
def test_torch_dataset_keys():
    from data.pipeline import SyntheticDataGenerator
    gen = SyntheticDataGenerator(ip_type='LDO', seed=0)
    ds = gen.to_torch_dataset(n_samples=30)
    assert 'X' in ds and 'Y' in ds


@test
def test_transient_dataset_has_t_span():
    from data.pipeline import SyntheticDataGenerator
    gen = SyntheticDataGenerator(ip_type='LDO', seed=0)
    ds = gen.to_torch_dataset(n_samples=30, include_transient=True)
    assert 't_span' in ds, "Missing t_span in transient dataset"


@test
def test_export_csv_readable():
    import tempfile
    from data.pipeline import SyntheticDataGenerator
    gen = SyntheticDataGenerator(ip_type='LDO', seed=0)
    with tempfile.NamedTemporaryFile(suffix='.csv', delete=False, mode='w') as f:
        path = f.name
    try:
        gen.export_csv(n_samples=20, filepath=path)
        assert os.path.exists(path)
        with open(path, encoding='utf-8') as f:
            header = f.readline()
        assert 'Vin' in header, f"CSV missing Vin column: {header}"
    finally:
        if os.path.exists(path):
            os.unlink(path)


# ═══════════════════════════════════════════════════════════════════════════════
# Model tests
# ═══════════════════════════════════════════════════════════════════════════════

@test
def test_pinn_forward_shape():
    from core.models.pinn import CircuitPINN
    pinn = CircuitPINN(input_dim=8, output_dim=8, hidden_dims=[32, 16], n_states=3)
    X = torch.FloatTensor(np.random.randn(10, 8).astype(np.float32))
    out = pinn(X)
    pred = out['predictions']
    from core.tensor_utils import to_np; pred_np = to_np(pred)
    assert pred_np.shape == (10, 8), f"PINN output shape: {pred_np.shape}"


@test
def test_pinn_loss_has_total():
    from core.models.pinn import CircuitPINN
    pinn = CircuitPINN(input_dim=8, output_dim=8, hidden_dims=[32, 16], n_states=3)
    X = torch.FloatTensor(np.random.randn(10, 8).astype(np.float32))
    Y = torch.FloatTensor(np.random.randn(10, 8).astype(np.float32))
    out = pinn(X)
    loss = pinn.compute_loss(out, Y, {})
    assert 'total' in loss, "Loss dict missing 'total'"


@test
def test_node_forward_has_trajectory():
    from core.models.neural_ode import CircuitNeuralODE
    node = CircuitNeuralODE(state_dim=2, param_dim=8, n_fsm_states=3, ip_type='LDO')
    params = np.random.randn(8).astype(np.float32)
    t_span = np.linspace(0, 100e-6, 50)
    result = node(params, t_span)
    assert 'trajectory' in result
    assert 'fsm_sequence' in result
    assert result['trajectory'].shape[1] == 2


@test
def test_gpr_fit_predict_shape():
    from core.models.gpr_surrogate import CircuitGPR
    gpr = CircuitGPR(input_dim=8, output_dim=8)
    X = np.random.randn(40, 8).astype(np.float32)
    Y = np.random.randn(40, 8).astype(np.float32)
    gpr.fit(X, Y)
    X_te = np.random.randn(10, 8).astype(np.float32)
    mean, std = gpr.predict(X_te)
    assert mean.shape == (10, 8), f"GPR mean shape: {mean.shape}"
    assert std.shape == (10, 8), f"GPR std shape: {std.shape}"


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 1 tests
# ═══════════════════════════════════════════════════════════════════════════════

@test
def test_phase1_ldo_veriloga():
    from core.spec_kg.knowledge_graph import build_ldo_kg
    from core.phases.phase1_spec_based import Phase1SpecBasedGenerator
    kg = build_ldo_kg()
    gen = Phase1SpecBasedGenerator(kg)
    va = gen.generate_veriloga()
    assert 'endmodule' in va, "LDO Verilog-A missing endmodule"


@test
def test_phase1_ota_veriloga():
    from core.spec_kg.knowledge_graph import build_ota_kg
    from core.phases.phase1_spec_based import Phase1SpecBasedGenerator
    kg = build_ota_kg()
    gen = Phase1SpecBasedGenerator(kg)
    va = gen.generate_veriloga()
    assert 'endmodule' in va, "OTA Verilog-A missing endmodule"


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 3 tests
# ═══════════════════════════════════════════════════════════════════════════════

@test
def test_phase3_gap_compute_returns_chip_id():
    from core.spec_kg.knowledge_graph import build_ldo_kg
    from core.phases.phase3_silicon import Phase3SiliconCalibration
    kg = build_ldo_kg()
    p3 = Phase3SiliconCalibration(kg)
    sim_preds = {'Output_Voltage': 1.80, 'PSRR_1kHz': 80.0, 'Phase_Margin': 60.0}
    silicon_data = p3.generate_demo_silicon_data(kg, sim_preds, n_chips=2)
    gaps = p3.compute_gaps(silicon_data, sim_preds)
    assert len(gaps) >= 1
    # Check chip_id key exists
    for chip_id in gaps:
        assert isinstance(chip_id, str)
        assert chip_id.startswith('chip_')


@test
def test_phase3_gap_ode_fit():
    from core.spec_kg.knowledge_graph import build_ldo_kg
    from core.phases.phase3_silicon import Phase3SiliconCalibration
    kg = build_ldo_kg()
    p3 = Phase3SiliconCalibration(kg)
    n_t = 20
    sim_traj = np.ones((n_t, 1)) * 1.80
    sil_traj = np.ones((n_t, 1)) * 1.86
    t_span = np.linspace(0, 1e-4, n_t)
    p3.fit_gap_correction(sim_traj, sil_traj, t_span, epochs=10)
    assert p3.gap_model is not None, "gap_model not set after fitting"


# ═══════════════════════════════════════════════════════════════════════════════
# Runner
# ═══════════════════════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════════════════════
# BLUT ingestion tests (Section 8 of the BLUT-integration prompt)
# Appended after the original 29 tests — numbering/order of the tests above
# is untouched. TESTS list order below determines print order only.
# ═══════════════════════════════════════════════════════════════════════════════

def _write_synthetic_blut(path, n_per_run=20, n_runs=2, with_current=True):
    """Shared test helper: build a small multi-run BLUT in-memory using the
    vendored blut_format write functions, exactly the pattern
    digitwin_blut_builder.py itself uses."""
    import digitwin.blut_format as bf
    run_specs = [
        (f'run{i}', f'corner=tt,idx={i}') for i in range(n_runs)
    ]
    with open(path, 'wb') as f:
        bf.write_file_header(f, n_runs=n_runs)
        for run_idx, (rid, meta) in enumerate(run_specs):
            run_off = f.tell()
            times = np.linspace(0, 1e-6, n_per_run)
            bf.write_run_header(f, run_idx, rid, meta, times)
            n_sig = 0
            idxs = np.arange(n_per_run)
            vout = 1.8 + 0.01 * np.arange(n_per_run) + 0.1 * run_idx
            bf.write_signal_block(f, 'top.u1.vout', idxs, vout, bf.ENC_FLOAT64, 0.0, 1.0, compress=False)
            n_sig += 1
            en = np.ones(n_per_run)
            bf.write_signal_block(f, 'top.u1.en', idxs, en, bf.ENC_FLOAT64, 0.0, 1.0, compress=False)
            n_sig += 1
            if with_current:
                iout = 0.1 + 0.001 * np.arange(n_per_run)
                bf.write_signal_block(f, 'top.u1.vout$flow', idxs, iout, bf.ENC_FLOAT64, 0.0, 1.0, compress=False)
                n_sig += 1
            bf.patch_run_n_signals(f, run_off, n_sig)
        bf.patch_file_header_counts(f, n_runs)


@test
def test_blut_roundtrip_2run_4signal():
    import tempfile
    from digitwin.blut_reader_ext import open_blut
    path = tempfile.mktemp(suffix='.blut')
    try:
        _write_synthetic_blut(path, n_per_run=15, n_runs=2, with_current=True)
        blut = open_blut(path)
        # v8 nested shape: runs[run_id][corner_id]; writes without an
        # explicit corner land under corner_id="".
        assert len(blut.runs) == 2, f"Expected 2 runs, got {len(blut.runs)}"
        from digitwin.blut_reader_ext import iter_runs
        for run in iter_runs(blut):
            assert run.corner_id == "", f"Expected empty corner_id, got {run.corner_id!r}"
            assert len(run.signals) == 3, f"Expected 3 signals, got {len(run.signals)}"
    finally:
        if os.path.exists(path):
            os.unlink(path)


@test
def test_classify_signal_kind_and_strip_suffix():
    from digitwin.blut_reader_ext import classify_signal_kind, strip_kind_suffix
    assert classify_signal_kind('top.u1.vout$flow') == 'current'
    assert classify_signal_kind('top.u1.vout') == 'voltage'
    assert strip_kind_suffix('top.u1.vout$flow') == 'top.u1.vout'
    assert strip_kind_suffix('top.u1.vout') == 'top.u1.vout'


@test
def test_load_run_matrix_shapes():
    import tempfile
    from digitwin.blut_reader_ext import open_blut, load_run_matrix
    path = tempfile.mktemp(suffix='.blut')
    try:
        _write_synthetic_blut(path, n_per_run=18, n_runs=1, with_current=True)
        blut = open_blut(path)
        from digitwin.blut_reader_ext import get_run
        run = get_run(blut, 'run0')
        rd = load_run_matrix(path, run)
        assert rd['voltage_matrix'].shape[0] == 18
        assert rd['current_matrix'].shape[0] == 18
        assert len(rd['time']) == 18
        assert rd['voltage_matrix'].shape[1] == len(rd['voltage_names'])
        assert rd['current_matrix'].shape[1] == len(rd['current_names'])
    finally:
        if os.path.exists(path):
            os.unlink(path)


@test
def test_load_all_runs_order_preserved():
    import tempfile
    from digitwin.blut_reader_ext import load_all_runs
    path = tempfile.mktemp(suffix='.blut')
    try:
        _write_synthetic_blut(path, n_per_run=10, n_runs=3, with_current=False)
        results = load_all_runs(path)
        assert len(results) == 3
        assert [r['run_id'] for r in results] == ['run0', 'run1', 'run2']
    finally:
        if os.path.exists(path):
            os.unlink(path)


@test
def test_signal_map_from_spec_json_backward_compat():
    from digitwin.spec_signal_map import SignalMap
    sm = SignalMap.from_spec_json('configs/ldo_spec.json')
    assert isinstance(sm.entries, list)
    assert len(sm.entries) == 0, "Existing spec JSON without signal_map key must yield empty map"


@test
def test_signal_map_kind_disambiguation():
    from digitwin.spec_signal_map import SignalMap, SignalMapEntry
    sm = SignalMap([
        SignalMapEntry('VOUT', 'top.u1.vout', 'voltage'),
        SignalMapEntry('IOUT', 'top.u1.vout', 'current'),
    ])
    assert sm.resolve_with_kind('VOUT', 'voltage') == 'top.u1.vout'
    assert sm.resolve_with_kind('IOUT', 'current') == 'top.u1.vout'
    assert sm.reverse_resolve('top.u1.vout', kind='voltage') == 'VOUT'
    assert sm.reverse_resolve('top.u1.vout', kind='current') == 'IOUT'


@test
def test_signal_capture_load_from_blut_populates_and_boundaries():
    import tempfile
    from core.fsm.signal_capture import SignalCapture
    from digitwin.spec_signal_map import SignalMap, SignalMapEntry
    path = tempfile.mktemp(suffix='.blut')
    try:
        _write_synthetic_blut(path, n_per_run=12, n_runs=2, with_current=True)
        sm = SignalMap([
            SignalMapEntry('VOUT', 'top.u1.vout', 'voltage'),
            SignalMapEntry('IOUT', 'top.u1.vout', 'current'),
            SignalMapEntry('EN', 'top.u1.en', 'voltage'),
        ])
        sc = SignalCapture()
        sc.load_from_blut(path, run_id=None, signal_map=sm)
        assert 'VOUT' in sc.signals
        assert 'IOUT' in sc.current_signals
        assert len(sc.run_boundaries) > 0, "Expected non-empty run_boundaries for 2-run file"
        assert len(sc.time) == 24
    finally:
        if os.path.exists(path):
            os.unlink(path)


@test
def test_transition_learner_boundary_mask_suppresses_seam():
    from core.fsm.transition_learner import TransitionLearner
    seq = np.array([0] * 10 + [1] * 10)
    feat = np.random.RandomState(0).randn(20, 2)
    state_defs = {0: {'name': 'STATE_A'}, 1: {'name': 'STATE_B'}}

    unmasked = TransitionLearner(fsm_tree_depth=2).learn(seq, feat, ['f0', 'f1'], state_defs)
    assert len(unmasked) >= 1, "Sanity check: un-masked seam should look like a real transition"

    bmask = np.zeros(20, dtype=bool)
    bmask[9] = True
    masked = TransitionLearner(fsm_tree_depth=2).learn(
        seq, feat, ['f0', 'f1'], state_defs, boundary_mask=bmask
    )
    assert len(masked) == 0, "boundary_mask must suppress the spurious cross-run transition"


@test
def test_build_dataset_from_blut_consistent_row_counts():
    import tempfile
    from digitwin.spec_signal_map import SignalMap, SignalMapEntry
    from core.spec_kg.knowledge_graph import build_ldo_kg
    from core.fsm.state_detector import FSMStateDetector
    from core.phases.phase2_sim_augmented import Phase2SimAugmented

    path = tempfile.mktemp(suffix='.blut')
    try:
        _write_synthetic_blut(path, n_per_run=16, n_runs=2, with_current=True)
        sm = SignalMap([
            SignalMapEntry('VOUT', 'top.u1.vout', 'voltage'),
            SignalMapEntry('IOUT', 'top.u1.vout', 'current'),
            SignalMapEntry('EN', 'top.u1.en', 'voltage'),
        ])
        kg = build_ldo_kg()
        kg.apply_signal_map(sm)
        detector = FSMStateDetector(strategy='logic', spec_kg=kg)
        p2 = Phase2SimAugmented(kg)
        data = p2.build_dataset_from_blut(
            path, sm, input_signal_names=['VOUT', 'EN'],
            output_signal_names=['VOUT', 'IOUT'], fsm_detector=detector,
        )
        n_x = data['X'].shape[0] if hasattr(data['X'], 'shape') else len(data['X'])
        n_y = data['Y'].shape[0] if hasattr(data['Y'], 'shape') else len(data['Y'])
        n_seq = len(data['state_sequence'])
        n_runs = len(data['run_ids'])
        assert n_x == n_y == n_seq == n_runs == 32, (
            f"Row counts must match: X={n_x} Y={n_y} seq={n_seq} run_ids={n_runs}"
        )
    finally:
        if os.path.exists(path):
            os.unlink(path)


@test
def test_per_state_rows_produce_distinct_state_onehot():
    from core.tensor_utils import to_np, make_float_tensor
    from core.models.pinn import CircuitPINN
    n_states = 3
    pinn = CircuitPINN(input_dim=4, output_dim=2, hidden_dims=[16, 8], n_states=n_states)

    # Trivially separable rows: 5 rows for state 0, 5 rows for state 1
    X = np.random.RandomState(1).randn(10, 4).astype(np.float32)
    state_seq = np.array([0] * 5 + [1] * 5)

    state_oh = np.zeros((10, n_states), dtype=np.float32)
    for i, s in enumerate(state_seq):
        state_oh[i, min(int(s), n_states - 1)] = 1.0

    # Confirm the two halves really do produce distinct one-hot patterns
    half_a = state_oh[:5]
    half_b = state_oh[5:]
    assert not np.allclose(half_a, half_b), "State one-hot rows must differ across detected states"
    assert np.allclose(half_a[:, 0], 1.0) and np.allclose(half_a[:, 1:], 0.0)
    assert np.allclose(half_b[:, 1], 1.0)

    X_t = make_float_tensor(X)
    S_t = make_float_tensor(state_oh)
    out = pinn(X_t, S_t)
    pred = to_np(out['predictions'])
    assert pred.shape == (10, 2)


@test
def test_map_predictions_to_physics_keys_activates_kvl():
    from core.spec_kg.knowledge_graph import build_ldo_kg
    from core.phases.phase2_sim_augmented import Phase2SimAugmented
    from core.models.pinn import PhysicsConstraintLayer

    kg = build_ldo_kg()
    p2 = Phase2SimAugmented(kg)
    physics_rules = kg.get_physics_loss_terms()

    output_names = ['VIN', 'Dropout_Voltage', 'VOUT']
    Y_row = np.array([[5.0, 0.2, 10.0]])  # 5 - 0.2 - 10 = -5.2 -> clear KVL violation

    circuit_state = p2._map_predictions_to_physics_keys(output_names, Y_row)
    assert set(circuit_state.keys()) >= {'V_vin', 'V_dropout', 'V_vout'}

    pcl = PhysicsConstraintLayer(physics_rules)
    kvl = pcl.kvl_loss(circuit_state)
    assert kvl > 0, "KVL loss must be non-zero for a constructed KVL-violating case"


@test
def test_fill_missing_state_transient_positive_and_negative():
    from core.phases.blut_reference import (
        fill_missing_state_transient, StateReferenceNotFoundError,
    )
    state_defs = {0: {'name': 'REGULATION'}, 1: {'name': 'FAULT'}}
    run1 = {
        'run_id': 'run1', 'time': np.linspace(0, 1e-6, 10),
        'voltage_names': ['VOUT'], 'voltage_matrix': np.full((10, 1), 1.8),
        'current_names': [], 'current_matrix': np.zeros((10, 0)),
        'state_sequence': np.zeros(10, dtype=int), 'state_defs': state_defs,
    }
    run2 = {
        'run_id': 'run2', 'time': np.linspace(0, 1e-6, 10),
        'voltage_names': ['VOUT'], 'voltage_matrix': np.full((10, 1), 0.0),
        'current_names': [], 'current_matrix': np.zeros((10, 0)),
        'state_sequence': np.concatenate([np.zeros(6, dtype=int), np.ones(4, dtype=int)]),
        'state_defs': state_defs,
    }

    ref = fill_missing_state_transient(state_defs, [], [run1, run2], 'FAULT')
    assert ref.shape[0] == 4, f"Expected 4 FAULT samples, got {ref.shape[0]}"

    try:
        fill_missing_state_transient(state_defs, [], [run1, run2], 'NOPE')
        assert False, "Expected StateReferenceNotFoundError for an absent state"
    except StateReferenceNotFoundError:
        pass


# ═══════════════════════════════════════════════════════════════════════════════
# FSM derivation fixes (constant rails / adaptive-timestep dwell / guards)
# ═══════════════════════════════════════════════════════════════════════════════

@test
def test_constant_signals_excluded_from_logic_matrix():
    from core.fsm.signal_capture import SignalCapture
    sc = SignalCapture()
    sc.load_synthetic(n_points=500, ip_type='LDO')
    # Ground-like rail: constant ~0V for the whole capture (AVSS analogue)
    sc.signals['AVSS'] = np.zeros(500)
    sc._classify_signals()
    assert 'AVSS' in sc.constant_signals, "Constant rail must be flagged constant"
    assert 'AVSS' not in sc.digital_signals, "Constant rail must not be a state signal"
    _, names, _ = sc.get_logic_signal_matrix()
    assert 'AVSS' not in names, "Constant rail must not enter the logic matrix"


@test
def test_adaptive_timestep_control_classified_digital():
    from core.fsm.signal_capture import SignalCapture
    sc = SignalCapture()
    # Non-uniform time axis: edge region heavily oversampled, as a SPICE
    # adaptive-timestep solver produces. By sample count the signal dwells
    # "mid-rail" >30% of samples; by time it switches essentially instantly.
    t_flat1 = np.linspace(0, 50e-6, 100)
    t_edge = 50e-6 + np.linspace(1e-9, 100e-9, 100)   # 100 samples in 100ns
    t_flat2 = np.linspace(51e-6, 100e-6, 100)
    sc.time = np.concatenate([t_flat1, t_edge, t_flat2])
    ramp = np.linspace(0, 5, 100)
    sc.signals = {'EN_CTRL': np.concatenate([np.zeros(100), ramp, np.full(100, 5.0)])}
    sc._classify_signals()
    assert 'EN_CTRL' in sc.digital_signals, \
        "Rail-to-rail control with oversampled edge must classify digital"


@test
def test_logic_guards_not_degenerate():
    from core.fsm.signal_capture import SignalCapture
    from core.fsm.state_detector import FSMStateDetector
    from core.fsm.transition_learner import TransitionLearner
    sc = SignalCapture()
    sc.load_synthetic(n_points=500, ip_type='LDO')
    lm, names, _ = sc.get_logic_signal_matrix()
    det = FSMStateDetector(strategy='logic')
    seq = det.detect(lm, names)
    transitions = TransitionLearner().learn(seq, lm, names, det.state_defs)
    assert len(transitions) >= 1
    for t in transitions:
        assert t.guard_expression != '(1)', \
            f"{t.from_name}->{t.to_name} guard degenerated to (1)"
        assert '==' in t.guard_expression, \
            f"Expected bit-test guard, got {t.guard_expression}"


@test
def test_state_name_dedup_no_duplicate_identifiers():
    from core.fsm.state_detector import FSMStateDetector
    from core.spec_kg.knowledge_graph import build_ldo_kg
    det = FSMStateDetector(strategy='logic', spec_kg=build_ldo_kg())
    # Two distinct patterns that both name to DISABLED (EN=0)
    defs = {
        0: {'id': 0, 'name': 'STATE_0', 'method': 'logic',
            'pattern': {'EN': 0, 'POK': 0}, 'count': 10},
        1: {'id': 1, 'name': 'STATE_1', 'method': 'logic',
            'pattern': {'EN': 0, 'POK': 1}, 'count': 10},
    }
    named = det._apply_speckg_naming(defs)
    names = [named[k]['name'] for k in sorted(named)]
    assert len(set(names)) == len(names), f"Duplicate state names: {names}"


@test
def test_rare_glitch_patterns_merged():
    from core.fsm.state_detector import FSMStateDetector
    det = FSMStateDetector(strategy='logic')
    # 2000 samples of two dominant patterns with a 2-sample glitch pattern
    # (one bit lagging the other) at the switchover
    matrix = np.zeros((2000, 2))
    matrix[1000:, 0] = 1.0
    matrix[1002:, 1] = 1.0
    seq = det.detect(matrix, ['A', 'B'])
    assert len(det.state_defs) == 2, \
        f"Glitch pattern must merge; got {len(det.state_defs)} states"
    assert len(seq) == 2000


@test
def test_va_codegen_ports_and_guards_consistent():
    from core.fsm.fsm_codegen import FSMCodeGenerator
    from core.fsm.transition_learner import Transition
    from core.spec_kg.knowledge_graph import build_ldo_kg
    kg = build_ldo_kg()
    defs = {
        0: {'id': 0, 'name': 'DISABLED', 'pattern': {'EN': 0}, 'count': 10},
        1: {'id': 1, 'name': 'STARTUP', 'pattern': {'EN': 1}, 'count': 10},
    }
    trans = [Transition(0, 1, 'DISABLED', 'STARTUP', ['EN == 1'],
                        '(EN == 1)', 0.1, {'EN': 1.0})]
    va = FSMCodeGenerator(spec_kg=kg, ip_type='LDO').generate_veriloga(
        defs, trans, kg.ports)
    # EN is a pure-digital enable pin (domain='digital', fsm_role='enable')
    # so it's declared `logic` with supplySensitivity/groundSensitivity
    # attributes and used directly in guards — no V()/VTH wrap needed.
    assert 'logic EN;' in va, "Pure-digital EN must be declared logic"
    assert 'supplySensitivity' in va, "EN must carry a supplySensitivity attribute"
    assert 'if (EN)' in va, "Bit guard on a logic pin must be a bare comparison"
    assert '@(cross(V(vin)' not in va, "Hard-coded cross event must be gone"
    assert 'electrical vin, vout, gnd;' not in va, \
        "Hard-coded lowercase declarations must be gone"
    assert 'VIN' in va, "SpecKG port names must be used"


@test
def test_sv_guard_conversion():
    from core.fsm.fsm_codegen import _sv_guard, _vid
    assert _sv_guard('(EN == 1 && POK == 0)') == '(EN && !POK)'
    assert _sv_guard('(1)') == "1'b1"
    assert _vid('SREF_TB.EN_LDO') == 'SREF_TB_EN_LDO'
    assert _vid('IBIAS[0]!') == 'IBIAS_0__'


# ═══════════════════════════════════════════════════════════════════════════════
# A+B strategy tests (Sections 3-7: templates, fitting, pvt, ab_integration)
# Appended after the existing tests — never renumbered.
# ═══════════════════════════════════════════════════════════════════════════════

def _ab_fixture():
    """Shared lazily-built A+B fixture (template, spec_kg, small FSM,
    providers, emitted VA) reused across the tests below to keep the
    suite runtime bounded."""
    global _AB_FIX
    try:
        return _AB_FIX
    except NameError:
        pass
    from core.spec_kg.knowledge_graph import SpecKG
    from core.templates import LdoPmosTemplate
    from core.fsm.transition_learner import Transition
    from core.fitting.state_delta_fitter import StateParamSet
    from core.pvt import LutParamProvider
    from core.ab_integration import build_ab_model, emit

    kg = SpecKG.from_json(os.path.join(os.path.dirname(__file__), '..',
                                       'configs', 'LDO_1V2.json'))
    tpl = LdoPmosTemplate()
    base = tpl.default_params()
    sdefs = {
        0: {'name': 'DISABLED', 'pattern': {'EN_LDO': 0, 'HIGH_POWER_MODE': 0}},
        1: {'name': 'REGULATION', 'pattern': {'EN_LDO': 1, 'HIGH_POWER_MODE': 0}},
        2: {'name': 'REGULATION_HP', 'pattern': {'EN_LDO': 1, 'HIGH_POWER_MODE': 1}},
    }

    def T(a, b, conds):
        return Transition(a, b, sdefs[a]['name'], sdefs[b]['name'], conds,
                          '(' + ' && '.join(conds) + ')', 0.01, {})
    trans = [T(0, 1, ['EN_LDO == 1']), T(1, 0, ['EN_LDO == 0']),
             T(1, 2, ['HIGH_POWER_MODE == 1']),
             T(2, 1, ['HIGH_POWER_MODE == 0'])]
    sps = StateParamSet(baseline=base,
                        deltas={'REGULATION_HP': {'I_q': 1.5e-5}})
    lut = LutParamProvider()
    for c in ('TT_1p8V_27C', 'SS_1p5V_125C', 'FF_2p0V_N40C'):
        lut.add_corner(c, sps)
    ab = build_ab_model(tpl, sdefs, trans, lut, kg, state_param_set=sps)
    va = emit(ab, corner='TT_1p8V_27C')
    _AB_FIX = {'kg': kg, 'tpl': tpl, 'base': base, 'sdefs': sdefs,
               'trans': trans, 'sps': sps, 'lut': lut, 'ab': ab, 'va': va}
    return _AB_FIX


@test
def test_param_manifest_roundtrip():
    from core.templates import LdoPmosTemplate, ParamManifest
    man = LdoPmosTemplate().manifest()
    man2 = ParamManifest.from_json(man.to_json())
    assert man2.names == man.names
    assert man2.defaults() == man.defaults()
    d = man.defaults()
    v = man.to_vector(d)
    assert man.from_vector(v) == d
    f = man.to_fit_space(v)
    back = man.from_fit_space(f)
    assert np.allclose(back, v, rtol=1e-12)


@test
def test_template_dc_solve_sanity():
    from core.templates import LdoPmosTemplate
    tpl = LdoPmosTemplate()
    p = tpl.default_params()
    op = tpl.dc_solve(p, 5.0, 0.05)
    target = p['V_ref'] * (1 + p['Rf1'] / p['Rf2'])
    assert abs(op['vout'] - target) < 0.01 * target, \
        f"vout={op['vout']} vs Vref*(1+Rf1/Rf2)={target}"
    assert not op['in_dropout']
    off = tpl.dc_solve(p, 5.0, 0.05, mode={'enable': 0})
    assert off['vout'] < 0.05


@test
def test_template_dropout_from_triode_branch():
    from core.templates import LdoPmosTemplate
    tpl = LdoPmosTemplate()
    p = tpl.default_params()
    hi = tpl.dc_solve(p, 5.0, 0.2, mode={'uvlo_ok': 1})
    lo = tpl.dc_solve(p, 1.30, 0.2, mode={'uvlo_ok': 1})
    assert not hi['in_dropout'] and hi['vout'] > 1.18
    assert lo['in_dropout'], "low vin @ 200 mA must be in the triode branch"
    assert lo['vout'] < hi['vout'], "dropout must actually droop vout"
    p2 = dict(p); p2['Kp'] = p['Kp'] * 2
    lo2 = tpl.dc_solve(p2, 1.30, 0.2, mode={'uvlo_ok': 1})
    assert lo2['vout'] > lo['vout'], \
        "no artificial clamp: stronger device must droop less"


@test
def test_template_psrr_from_structure():
    from core.templates import LdoPmosTemplate
    tpl = LdoPmosTemplate()
    p = tpl.default_params()
    op = tpl.dc_solve(p, 5.0, 0.05)
    ss = tpl.small_signal(p, op)
    f = ss['freqs']
    p1k = ss['psrr_db'][np.argmin(np.abs(f - 1e3))]
    p1M = ss['psrr_db'][np.argmin(np.abs(f - 1e6))]
    assert p1k > 40 and p1M > 10
    # PSRR must respond to a structural supply path: the lambda_p (CLM)
    # coupling shows at high frequency where the loop no longer hides it
    p2 = dict(p); p2['lambda_p'] = p['lambda_p'] * 5
    ss2 = tpl.small_signal(p2, tpl.dc_solve(p2, 5.0, 0.05))
    d_max = float(np.max(np.abs(ss2['psrr_db'] - ss['psrr_db'])))
    assert d_max > 1.0, \
        f"PSRR did not respond to the lambda_p supply path (max d={d_max:.2f} dB)"
    assert np.all(np.real(ss['poles']) < 0), "op point must be stable"


@test
def test_vector_fit_recovers_known_poles():
    from core.fitting import vector_fit
    f = np.logspace(1, 6, 160)
    s = 2j * np.pi * f
    p_true = complex(-2 * np.pi * 5e4, 2 * np.pi * 2e5)
    H = (1 + 2j) / (s - p_true) + (1 - 2j) / (s - np.conj(p_true)) + 0.01
    fit = vector_fit(f, H, n_poles=2)
    assert fit.rms_error < 1e-3
    got = fit.poles[np.argmax(fit.poles.imag)]
    assert abs(got - p_true) / abs(p_true) < 1e-3


@test
def test_era_recovers_known_poles():
    from core.fitting import era
    dt = 1e-6
    t = np.arange(300) * dt
    y = np.exp(-3e4 * t) * np.cos(2 * np.pi * 8e4 * t)
    poles, info = era(y, dt, order=2)
    assert info['rms_error'] < 1e-9
    assert abs(abs(poles[0].imag) - 2 * np.pi * 8e4) / (2 * np.pi * 8e4) < 1e-6
    assert abs(-poles[0].real - 3e4) / 3e4 < 1e-6


@test
def test_dc_stage_recovers_known_params():
    from core.templates import LdoPmosTemplate
    from core.fitting import SingleCornerFitter
    tpl = LdoPmosTemplate()
    gt = tpl.default_params()
    gt.update(Rf1=1.15e5, Vth_p=0.55, Kp=2.5)
    dc = []
    for vin in (4.5, 5.0, 5.5):
        for il in (0.001, 0.01, 0.1, 0.2):
            op = tpl.dc_solve(gt, vin, il)
            dc.append({'vin': vin, 'iload': il, 'vout': op['vout'],
                       'iq': op['iq']})
    for vin in np.arange(1.30, 1.75, 0.05):
        op = tpl.dc_solve(gt, float(vin), 0.2, mode={'uvlo_ok': 1})
        dc.append({'vin': float(vin), 'iload': 0.2, 'mode': {'uvlo_ok': 1},
                   'vout': op['vout']})
    fitter = SingleCornerFitter(tpl)
    params, rms = fitter._stage_dc(tpl.default_params(), {'dc': dc}, [])
    assert abs(params['Rf1'] - gt['Rf1']) / gt['Rf1'] < 0.02, params['Rf1']
    assert abs(params['Vth_p'] - gt['Vth_p']) < 0.05, params['Vth_p']
    assert abs(params['Kp'] - gt['Kp']) / gt['Kp'] < 0.25, params['Kp']
    assert rms < 1e-3


@test
def test_transient_stage_recovers_functional_response():
    from core.templates import LdoPmosTemplate
    from core.fitting import SingleCornerFitter
    tpl = LdoPmosTemplate()
    gt = tpl.default_params()
    gt.update(I_ea_max=2.0e-4)
    t = np.linspace(0, 30e-6, 300)
    il = np.where(t < 8e-6, 0.01, 0.2)
    ref = tpl.simulate(gt, t, {'vin': 5.0, 'iload': il})
    tr = {'t': t, 'inputs': {'vin': 5.0, 'iload': il},
          'vout_ref': ref['vout'], 't_event': 8e-6}
    fitter = SingleCornerFitter(tpl, de_maxiter=2, de_popsize=4)
    params, rms = fitter._stage_transient(tpl.default_params(),
                                          {'transient': [tr]}, [])
    sim = tpl.simulate(params, t, {'vin': 5.0, 'iload': il})
    err = np.sqrt(np.mean((sim['vout'] - ref['vout']) ** 2))
    assert err < 5e-3, f"transient stage left {err*1e3:.2f} mV rms"


@test
def test_identifiability_freeze_on_degenerate_case():
    from core.templates import LdoPmosTemplate
    from core.fitting import SingleCornerFitter
    tpl = LdoPmosTemplate()
    # DC-only data cannot identify transient-stage params like I_ea_max
    # -> the gate must freeze them back to manifest defaults.
    gt = tpl.default_params()
    dc = [{'vin': 5.0, 'iload': il,
           'vout': tpl.dc_solve(gt, 5.0, il)['vout']}
          for il in (0.001, 0.05, 0.2)]
    fitter = SingleCornerFitter(tpl)
    params = dict(gt); params['I_ea_max'] = gt['I_ea_max'] * 3  # wrong value
    out, frozen, sens = fitter._identifiability(params, {'dc': dc}, [])
    assert 'I_ea_max' in frozen, f"frozen={frozen}"
    assert out['I_ea_max'] == tpl.manifest().spec('I_ea_max').default


@test
def test_state_delta_switch_states_zero_and_sparse():
    from core.templates import LdoPmosTemplate
    from core.fitting import StateDeltaFitter
    tpl = LdoPmosTemplate()
    base = tpl.default_params()
    t = np.linspace(0, 20e-6, 200)
    recs = {
        'DISABLED': [{'t': t, 'inputs': {'vin': 5.0, 'iload': 0.0},
                      'vout_ref': np.zeros(len(t))}],
        'SCAN': [{'t': t, 'inputs': {'vin': 5.0, 'iload': 0.0},
                  'vout_ref': np.zeros(len(t))}],
    }
    sdefs = {0: {'name': 'DISABLED', 'pattern': {'EN_LDO': 0}},
             1: {'name': 'SCAN', 'pattern': {'SCAN_MODE_VSUPPLY': 1}}}
    sps = StateDeltaFitter(tpl).fit(base, recs, sdefs)
    assert sps.deltas['DISABLED'] == {}, "switch state must carry no deltas"
    assert sps.deltas['SCAN'] == {}, "scan state must carry no deltas"
    assert sps.reports['_dims']['floated'] == 0


@test
def test_param_providers_roundtrip_and_agree_at_training_corners():
    import tempfile
    from core.fitting.state_delta_fitter import StateParamSet
    from core.pvt import (LutParamProvider, BlutStoreParamProvider,
                          NNParamProvider, save_param_store)
    fx = _ab_fixture()
    base = fx['base']

    def cs(scale):
        b = dict(base); b['Kp'] = base['Kp'] * scale
        return StateParamSet(baseline=b,
                             deltas={'REGULATION_HP': {'I_q': 1e-5}})
    fits = {'TT_1p8V_27C': cs(1.0), 'SS_1p5V_125C': cs(0.8),
            'FF_2p0V_N40C': cs(1.25)}
    path = tempfile.mktemp(suffix='.blut')
    try:
        save_param_store(path, fits)
        provs = {'blut': BlutStoreParamProvider(path),
                 'nn': NNParamProvider(epochs=1500).fit(fits)}
        lut = LutParamProvider()
        for c, s in fits.items():
            lut.add_corner(c, s)
        provs['lut'] = lut
        for c, s in fits.items():
            truth = s.baseline['Kp']
            for name, prov in provs.items():
                got = prov.get_params_for_corner(c)['Kp']
                assert abs(got - truth) / truth < 0.02, \
                    f"{name}@{c}: Kp={got} vs {truth}"
                withd = prov.get_params_for_corner(c, state='REGULATION_HP')
                assert withd['I_q'] > prov.get_params_for_corner(c)['I_q']
    finally:
        if os.path.exists(path):
            os.unlink(path)


@test
def test_provider_holdout_error_table_shape():
    from core.pvt import evaluate_providers
    fx = _ab_fixture()
    tbl = evaluate_providers({'lut': fx['lut']}, 'TT_1p8V_85C',
                             fx['base'], template=fx['tpl'])
    param_rows = [r for r in tbl if not r['param'].startswith('_spec')]
    drift_rows = [r for r in tbl if r['param'].startswith('_spec_drift')]
    assert len(param_rows) == len(fx['base'])
    assert len(drift_rows) == 1
    assert all('lut_pct_err' in r for r in param_rows)
    assert 'lut_vout_drift_mV' in drift_rows[0]


@test
def test_ab_model_state_switch_continuity():
    fx = _ab_fixture()
    t = np.linspace(0, 60e-6, 1200)
    en = np.full(len(t), 5.0)
    hp = np.where(t > 30e-6, 5.0, 0.0)
    stim = {'t': t, 'pins': {'V_SUPPLY': np.full(len(t), 5.0), 'AVSS': 0.0,
                             'EN_LDO': en, 'HIGH_POWER_MODE': hp},
            'iload': 0.05}
    w = fx['ab'].simulate(stim, 'TT_1p8V_27C')
    i_sw = int(np.argmax(w['state_trace'] == 2))
    assert i_sw > 0, "HP state never entered"
    jump = abs(w['vout'][i_sw] - w['vout'][i_sw - 1])
    assert jump < 5e-3, f"vout discontinuity at state switch: {jump*1e3:.2f} mV"


@test
def test_ab_va_bound_step_and_no_cross_in_case():
    fx = _ab_fixture()
    va = fx['va']
    assert '$bound_step' in va, "FSM must use the $bound_step pattern"
    assert '@(cross' not in va, "@(cross) is illegal inside case arms"
    assert 'endmodule' in va


@test
def test_ab_va_connect_modules_and_ok_checks_match_spec():
    from core.ab_integration.ab_codegen import _logic_domains
    fx = _ab_fixture()
    va, kg = fx['va'], fx['kg']
    n_domains = len(_logic_domains(kg))
    assert va.count('connectmodule ab_e2l_') == n_domains
    assert va.count('connectmodule ab_l2e_') == n_domains
    for p in kg.ports:
        if p.port_type in ('supply', 'ground', 'bulk'):
            assert f'{p.name}_ok =' in va, p.name
            if p.voltage_range[1] > p.voltage_range[0]:
                assert f'{p.voltage_range[1]:g}' in va, p.name
        elif p.port_type.startswith('bias_current'):
            pid = p.name.replace('[', '_').replace(']', '_')
            assert f'{pid}_ok =' in va, p.name
    assert 'supplies_ok =' in va


@test
def test_ab_supplies_ok_gates_model_inert():
    fx = _ab_fixture()
    t = np.linspace(0, 40e-6, 800)
    vsup = np.where(t < 20e-6, 4.0, 5.0)  # below the [4.5, 5.5] JSON window
    stim = {'t': t, 'pins': {'V_SUPPLY': vsup, 'AVSS': 0.0,
                             'EN_LDO': np.full(len(t), 5.0),
                             'HIGH_POWER_MODE': 0.0},
            'iload': 0.0}
    w = fx['ab'].simulate(stim, 'TT_1p8V_27C')
    first = t < 18e-6
    assert not w['supplies_ok'][first].any()
    assert np.all(w['state_trace'][first] == 0), "must be held DISABLED"
    assert np.all(np.abs(w['i_vin'][first]) < 1e-6), "must be inert"
    late = t > 35e-6
    assert w['supplies_ok'][late].all()
    assert (w['state_trace'][late] != 0).any(), "must run once _ok asserts"


@test
def test_example5_scorecard_executes():
    import subprocess
    root = os.path.join(os.path.dirname(__file__), '..')
    proc = subprocess.run(
        [sys.executable, os.path.join(root, 'examples',
                                      'example5_sref_ab_poc.py'), '--smoke'],
        capture_output=True, text=True, cwd=root, timeout=1200)
    out = proc.stdout + proc.stderr
    assert 'POC SCORECARD' in out, out[-2000:]
    assert 'POC RESULT: ALL BARS MET' in out, out[-3000:]
    assert proc.returncode == 0


# ═══════════════════════════════════════════════════════════════════════════════
# Current-insights (Capability A) + FSM-completeness (Capability B) tests.
# Appended after the A+B block — never renumbered.
# ═══════════════════════════════════════════════════════════════════════════════

def _cfg(name):
    return os.path.join(os.path.dirname(__file__), '..', 'configs', name)


def _insights_env():
    """Registry + a synthetic multi-run view set with known ground truth:
    startup+load, a mux-good redistribution, a mux-bug no-shift, and a
    dummy-load assertion — reused across the tests below."""
    global _INS_ENV
    try:
        return _INS_ENV
    except NameError:
        pass
    from core.spec_kg.knowledge_graph import SpecKG
    from digitwin.spec_signal_map import SignalMap
    from core.current_insights import CurrentRegistry, build_run_views
    kg = SpecKG.from_json(_cfg('LDO_1V2.json'))
    sm = SignalMap.from_spec_json(_cfg('signal_map_ldo.json'))
    reg = CurrentRegistry(kg, sm)
    rng = np.random.RandomState(3)

    def run(kind, corner):
        n = 1400
        t = np.linspace(0, 140e-6, n)
        seq = np.zeros(n, int); seq[t > 8e-6] = 1; seq[t > 18e-6] = 2
        V = {p: np.zeros(n) for p in ('V_SUPPLY', 'VDD_1V2', 'EN_LDO',
                                      'HIGH_POWER_MODE', 'VPWR', 'VPWR_SEL',
                                      'SREF_ADD_LDO1V2_LOAD_MPOS')}
        V['V_SUPPLY'][:] = 5.0; V['VPWR'][:] = 5.0
        V['EN_LDO'][:] = np.where(t > 8e-6, 5.0, 0.0)
        V['VDD_1V2'][:] = np.where(t > 18e-6, 1.2, 0.0)
        I = {'V_SUPPLY': np.where(t > 8e-6, 5e-5, 1e-6) + 3e-7 * rng.randn(n),
             'VDD_1V2': np.where(t > 18e-6, 5e-5, 0.0) + 3e-7 * rng.randn(n),
             'VPWR': 1e-6 * rng.randn(n)}
        if kind == 'mux_good':
            V['VPWR_SEL'][:] = np.where(t > 70e-6, 5.0, 0.0)
            I['V_SUPPLY'][t > 70e-6] -= 4e-5; I['VPWR'][t > 70e-6] += 4e-5
        elif kind == 'mux_bug':
            V['VPWR_SEL'][:] = np.where(t > 70e-6, 5.0, 0.0)
        elif kind == 'dummy':
            m = (t > 95e-6) & (t < 120e-6)
            V['SREF_ADD_LDO1V2_LOAD_MPOS'][:] = np.where(m, 5.0, 0.0)
            I['VDD_1V2'][m] += 3e-5
        vn = list(V.keys()); cn = ['V_SUPPLY_I', 'VDD_1V2_I', 'VPWR_I']
        return {'run_id': kind, 'corner_id': corner, 'time': t,
                'voltage_names': vn,
                'voltage_matrix': np.column_stack([V[p] for p in vn]),
                'current_names': cn,
                'current_matrix': np.column_stack(
                    [I['V_SUPPLY'], I['VDD_1V2'], I['VPWR']])}, seq
    runs, seqs = [], {}
    for kind, corner in [('mux_good', 'TT_1p8V_27C'), ('mux_bug', 'FF_2p0V_N40C'),
                         ('dummy', 'TT_1p8V_27C')]:
        r, s = run(kind, corner)
        runs.append(r); seqs[f'{kind}@{corner}'] = s
    sd = {0: {'name': 'DISABLED', 'pattern': {}},
          1: {'name': 'STARTUP', 'pattern': {}},
          2: {'name': 'REGULATION', 'pattern': {}}}
    views = build_run_views(runs, reg, state_sequences=seqs, state_defs=sd)
    _INS_ENV = {'kg': kg, 'sm': sm, 'reg': reg, 'runs': runs, 'seqs': seqs,
                'views': views, 'state_defs': sd}
    return _INS_ENV


@test
def test_filtering_floor_spike_and_derivative():
    from core.current_insights import filter_current, estimate_noise_floor
    rng = np.random.RandomState(0)
    t = np.linspace(0, 1e-3, 2000)
    x = 5e-5 + 3e-5 * (t > 5e-4) + 2e-6 * rng.randn(2000)
    x[1000] = 1e-2                       # single-sample spike
    fs = filter_current('I', t, x)
    assert 0.5e-6 < fs.noise_floor < 6e-6, fs.noise_floor
    assert abs(fs.filtered[1000]) < 1e-3, 'median prefilter must kill the spike'
    assert abs(int(np.argmax(np.abs(fs.derivative))) - 1000) < 60
    assert fs.log.method.startswith('medfilt')
    # constant signal -> positive floor (never zero)
    assert estimate_noise_floor(np.ones(500)) > 0


@test
def test_registry_resolves_flow_currents():
    env = _insights_env()
    reg = env['reg']
    assert reg.channel('V_SUPPLY').i_name == 'V_SUPPLY_I'
    assert [c.pin for c in reg.input_supplies()].count('V_SUPPLY') == 1
    assert reg.channel('SREF_ADD_LDO1V2_LOAD_MPOS').role == 'load_control'
    assert [c.pin for c in reg.selects()] == ['VPWR_SEL', 'PAD_VDD1V2_SEL']
    # $flow kind resolution: the current entry is distinct from the voltage
    v = env['views'][0]
    from core.current_insights import current_of
    assert current_of(v, 'V_SUPPLY') is not None


@test
def test_supply_attribution_ranking():
    from core.current_insights import SupplyAttribution
    env = _insights_env()
    fs = SupplyAttribution().analyze(env['views'], env['reg'])
    dom = [f for f in fs if f.category == 'supply-dominance'
           and 'REGULATION' in f.affected_states]
    assert dom, 'expected a REGULATION dominance finding'
    top = dom[0].evidence['ranking_uA_mean_rms'][0][0]
    assert top == 'V_SUPPLY', f'V_SUPPLY should dominate, got {top}'


@test
def test_edge_threshold_localization():
    from core.spec_kg.knowledge_graph import SpecKG
    from digitwin.spec_signal_map import SignalMap
    from core.current_insights import (CurrentRegistry, build_run_views,
                                       EdgeThresholdCorrelation)
    kg = SpecKG.from_json(_cfg('LDO_1V2.json'))
    sm = SignalMap.from_spec_json(_cfg('signal_map_ldo.json'))
    reg = CurrentRegistry(kg, sm)
    n = 2400
    t = np.linspace(0, 120e-6, n)
    # EN_LDO ramps up then down through its threshold (two crossings);
    # EN_LDO_I spikes each time it crosses ~2.75 V
    en = np.where(t < 60e-6, np.clip((t - 40e-6) / 5e-6, 0, 1) * 5.0,
                  np.clip(1 - (t - 80e-6) / 5e-6, 0, 1) * 5.0)
    ien = np.zeros(n)
    for cross in (int(np.argmin(np.abs(en[:n // 2] - 2.75))),
                  n // 2 + int(np.argmin(np.abs(en[n // 2:] - 2.75)))):
        ien[cross - 2:cross + 3] = 5e-6
    run = {'run_id': 'r', 'corner_id': '', 'time': t,
           'voltage_names': ['EN_LDO'], 'voltage_matrix': en[:, None],
           'current_names': ['EN_LDO_I'], 'current_matrix': ien[:, None]}
    views = build_run_views([run], reg)
    fs = EdgeThresholdCorrelation().analyze(views, reg)
    en_f = [f for f in fs if f.affected_pins == ['EN_LDO']]
    assert en_f, 'expected an EN_LDO effective-threshold finding'
    assert abs(en_f[0].evidence['effective_V'] - 2.75) < 0.4


@test
def test_mux_verification_pass_and_bug():
    from core.current_insights import MuxVerification
    env = _insights_env()
    fs = MuxVerification().analyze(env['views'], env['reg'])
    cats = {f.category for f in fs}
    assert 'mux-verified' in cats, 'mux_good run must verify redistribution'
    assert 'untested-mux' in cats, 'mux_bug run must flag no-shift'
    bug = [f for f in fs if f.category == 'untested-mux'][0]
    assert bug.severity == 'high'


@test
def test_vi_inconsistency_uses_total_supply():
    # A mux handover (current moves between supplies at constant TOTAL) must
    # NOT be flagged; only a genuine total-current mismatch should be.
    from core.current_insights import VIConsistency
    env = _insights_env()
    fs = VIConsistency().analyze(env['views'], env['reg'])
    bad = [f for f in fs if f.category == 'vi-inconsistency']
    assert not bad, f'mux handover falsely flagged: {[f.summary for f in bad]}'


@test
def test_capacity_estimate_vs_ground_truth():
    from core.spec_kg.knowledge_graph import SpecKG
    from digitwin.spec_signal_map import SignalMap
    from core.current_insights import (CurrentRegistry, build_run_views,
                                       DriveStrength)
    kg = SpecKG.from_json(_cfg('LDO_1V2.json'))
    sm = SignalMap.from_spec_json(_cfg('signal_map_ldo.json'))
    reg = CurrentRegistry(kg, sm)
    n = 1500
    t = np.linspace(0, 150e-6, n)
    # sustain 150 mA in regulation, collapse beyond
    ramp = np.clip((t - 20e-6) / 100e-6, 0, 1)
    iout = 0.01 + 0.30 * ramp
    vout = np.where(iout <= 0.15, 1.2, 1.2 - 2.0 * (iout - 0.15))
    run = {'run_id': 'r', 'corner_id': '', 'time': t,
           'voltage_names': ['VDD_1V2'], 'voltage_matrix': vout[:, None],
           'current_names': ['VDD_1V2_I'], 'current_matrix': iout[:, None]}
    views = build_run_views([run], reg)
    fs = DriveStrength().analyze(views, reg)
    cap = [f for f in fs if 'capacity' in f.category][0]
    obs = cap.evidence['observed_capacity_A']
    assert 0.14 < obs < 0.17, f'capacity {obs} should be ~0.15 A'
    assert cap.category == 'capacity-shortfall'   # 150 mA < 200 mA spec


@test
def test_dummy_load_classification():
    from core.current_insights import LoadDetection
    env = _insights_env()
    ld = LoadDetection()
    fs = ld.analyze(env['views'], env['reg'])
    pins = {e['pin'] for e in ld.enrichment_proposals}
    assert pins == {'SREF_ADD_LDO1V2_LOAD_MPOS'}, pins
    e = ld.enrichment_proposals[0]
    assert 2e-5 < e['added_load_A'] < 4e-5
    assert e['proposed_category'] == 'internal_load'


@test
def test_impedance_extraction_vs_template():
    from core.spec_kg.knowledge_graph import SpecKG
    from digitwin.spec_signal_map import SignalMap
    from core.templates import LdoPmosTemplate
    from core.current_insights import (CurrentRegistry, build_run_views,
                                       VIConsistency)
    kg = SpecKG.from_json(_cfg('LDO_1V2.json'))
    sm = SignalMap.from_spec_json(_cfg('signal_map_ldo.json'))
    reg = CurrentRegistry(kg, sm)
    tpl = LdoPmosTemplate()
    rng = np.random.RandomState(1)
    n = 1200
    t = np.linspace(0, 60e-6, n)
    # a noisy load step: dI = +20 mA at 30us gives dV ~ -2 mV -> Zout ~ 0.1 ohm
    iout = 0.05 + 0.02 * (t > 30e-6) + 3e-4 * rng.randn(n)
    vout = 1.2 - 0.1 * 0.02 * (t > 30e-6) + 5e-5 * rng.randn(n)
    run = {'run_id': 'r', 'corner_id': '', 'time': t,
           'voltage_names': ['VDD_1V2'], 'voltage_matrix': vout[:, None],
           'current_names': ['VDD_1V2_I'], 'current_matrix': iout[:, None]}
    views = build_run_views([run], reg)
    fs = VIConsistency(template=tpl, params=tpl.default_params()).analyze(
        views, reg)
    imp = [f for f in fs if f.category == 'impedance']
    assert imp and 'large_signal_Zout_ohm' in imp[0].evidence
    assert 'template_Zout_dc_ohm' in imp[0].evidence   # reconciliation ran


@test
def test_iq_signature_advisory_only():
    # 3.10 proposes relabels but must NOT alter the detector's inputs
    # (contract). Verify the detected state matrix is unchanged after the
    # signature pass and that proposals are advisory.
    from core.current_insights import StateSignatures, build_run_views
    env = _insights_env()
    reg = env['reg']
    # a state with bimodal Iq across occurrences
    n = 1600
    t = np.linspace(0, 160e-6, n)
    seq = np.zeros(n, int)
    for k in range(8):
        seq[(t > (k * 20e-6)) & (t < (k * 20e-6 + 10e-6))] = 1
    hi = (np.arange(n) // 200) % 2      # alternate Iq level per occurrence
    isup = np.where(seq == 1, np.where(hi, 9e-5, 3e-5), 1e-6)
    run = {'run_id': 'r', 'corner_id': '', 'time': t,
           'voltage_names': ['V_SUPPLY'],
           'voltage_matrix': np.full((n, 1), 5.0),
           'current_names': ['V_SUPPLY_I'], 'current_matrix': isup[:, None]}
    sd = {0: {'name': 'DISABLED', 'pattern': {}},
          1: {'name': 'REGULATION', 'pattern': {}}}
    views = build_run_views([run], reg, state_sequences={'r@': seq},
                            state_defs=sd)
    before = views[0].state_sequence.copy()
    ss = StateSignatures()
    fs = ss.analyze(views, reg)
    assert np.array_equal(views[0].state_sequence, before), \
        'analyzer must not mutate the state sequence'
    assert any(p['proposal'] == 'split' for p in ss.relabel_proposals)
    assert all(f.severity in ('low', 'info') for f in fs), 'advisory only'


@test
def test_state_space_containment_arithmetic():
    from types import SimpleNamespace
    from core.spec_kg.knowledge_graph import SpecKG
    from core.current_insights import CurrentRegistry
    from core.fsm_completeness import build_reference_space
    from core.fsm_completeness.ip_profiles import get_profile
    kg = SpecKG.from_json(_cfg('LDO_1V2.json'))
    reg = CurrentRegistry(kg, None)
    fsm = SimpleNamespace(state_defs={}, transitions=[], spec_kg=kg)
    ref = build_reference_space(fsm, get_profile('LDO')[0], registry=reg)
    a = ref.arithmetic
    assert a['raw_2n'] == 2 ** a['n_state_pins']       # 2^n, not asserted
    assert 6 <= a['reference_states'] <= 12            # contained
    assert a['collapse_factor'] > 100                  # massive collapse
    # the EN >- SEL example must appear in the rationale
    joined = ' '.join(ref.masking_rationale)
    assert 'EN_LDO=0' in joined and 'DISABLED' in joined
    assert 'select' in joined.lower()


@test
def test_coverage_richness_clipped_is_gap():
    from types import SimpleNamespace
    from core.spec_kg.knowledge_graph import SpecKG
    from digitwin.spec_signal_map import SignalMap
    from core.fsm.transition_learner import Transition
    from core.current_insights import CurrentRegistry, build_run_views
    from core.fsm_completeness import evaluate
    kg = SpecKG.from_json(_cfg('LDO_1V2.json'))
    sm = SignalMap.from_spec_json(_cfg('signal_map_ldo.json'))
    reg = CurrentRegistry(kg, sm)
    n = 600
    t = np.linspace(0, 60e-6, n)
    # STARTUP entered then the capture ends mid-ramp (never settles) -> clipped
    seq = np.zeros(n, int); seq[t > 40e-6] = 1
    vout = np.where(t > 40e-6, 0.3 + 5e4 * (t - 40e-6), 0.0)  # still ramping
    run = {'run_id': 'r', 'corner_id': 'TT_1p8V_27C', 'time': t,
           'voltage_names': ['VDD_1V2'], 'voltage_matrix': vout[:, None],
           'current_names': ['VDD_1V2_I'],
           'current_matrix': np.where(t > 40e-6, 5e-5, 0.0)[:, None]}
    sd = {0: {'name': 'DISABLED', 'pattern': {}},
          1: {'name': 'STARTUP', 'pattern': {}}}
    views = build_run_views([run], reg, state_sequences={'r@TT_1p8V_27C': seq},
                            state_defs=sd)
    fsm = SimpleNamespace(
        state_defs=sd, spec_kg=kg,
        transitions=[Transition(0, 1, 'DISABLED', 'STARTUP', [], '', 0.1, {})])
    result, _, _ = evaluate('LDO', fsm, views, registry=reg)
    assert ('DISABLED', 'STARTUP') in result.clipped_transitions
    assert result.richness < 1.0


@test
def test_gap_report_option2_limitations_reach_veriloga():
    from types import SimpleNamespace
    from core.spec_kg.knowledge_graph import SpecKG
    from core.fsm.transition_learner import Transition
    from core.templates import LdoPmosTemplate
    from core.fitting.state_delta_fitter import StateParamSet
    from core.pvt import LutParamProvider
    from core.ab_integration import build_ab_model, emit
    from core.current_insights import CurrentRegistry
    from core.fsm_completeness import evaluate, build_gap_report
    kg = SpecKG.from_json(_cfg('LDO_1V2.json'))
    reg = CurrentRegistry(kg, None)
    sd = {0: {'name': 'DISABLED', 'pattern': {'EN_LDO': 0}},
          1: {'name': 'REGULATION', 'pattern': {'EN_LDO': 1}}}
    tr = [Transition(0, 1, 'DISABLED', 'REGULATION', ['EN_LDO == 1'],
                     '(EN_LDO == 1)', 0.1, {})]
    fsm = SimpleNamespace(state_defs=sd, transitions=tr, spec_kg=kg)
    result, ref, prof = evaluate('LDO', fsm, [], registry=reg)
    gap = build_gap_report(result, ref, prof)
    assert gap.option2_limitations, 'missing states should yield limitations'
    tpl = LdoPmosTemplate()
    sps = StateParamSet(baseline=tpl.default_params(), deltas={})
    lut = LutParamProvider()
    for c in ('TT_1p8V_27C', 'SS_1p5V_125C', 'FF_2p0V_N40C'):
        lut.add_corner(c, sps)
    ab = build_ab_model(tpl, sd, tr, lut, kg, state_param_set=sps)
    va = emit(ab, limitations=gap.option2_limitations)
    assert va.count('// LIMITATIONS:') >= len(gap.option2_limitations)


@test
def test_disabled_insights_regression_guard():
    # emit() with no insight args must be deterministic and byte-identical to
    # the POC emitter (no LIMITATIONS / measured-Iq / internal_load markers).
    from core.spec_kg.knowledge_graph import SpecKG
    from core.fsm.transition_learner import Transition
    from core.templates import LdoPmosTemplate
    from core.fitting.state_delta_fitter import StateParamSet
    from core.pvt import LutParamProvider
    from core.ab_integration import build_ab_model, emit
    kg = SpecKG.from_json(_cfg('LDO_1V2.json'))
    tpl = LdoPmosTemplate()
    sd = {0: {'name': 'DISABLED', 'pattern': {'EN_LDO': 0}},
          1: {'name': 'REGULATION', 'pattern': {'EN_LDO': 1}}}
    tr = [Transition(0, 1, 'DISABLED', 'REGULATION', ['EN_LDO == 1'],
                     '(EN_LDO == 1)', 0.1, {})]
    sps = StateParamSet(baseline=tpl.default_params(),
                        deltas={'REGULATION': {'I_q': 1.5e-5}})
    lut = LutParamProvider()
    for c in ('TT_1p8V_27C', 'SS_1p5V_125C', 'FF_2p0V_N40C'):
        lut.add_corner(c, sps)
    ab = build_ab_model(tpl, sd, tr, lut, kg, state_param_set=sps)
    a = emit(ab, corner='TT_1p8V_27C')
    b = emit(ab, corner='TT_1p8V_27C')
    assert a == b, 'emit must be deterministic'
    assert 'LIMITATIONS' not in a
    assert 'measured Iq' not in a
    assert 'internal_load' not in a
    # enabling insights only ADDS lines
    c = emit(ab, corner='TT_1p8V_27C', limitations=['x'],
             iq_signatures={'REGULATION': (5e-5, 1e-6)})
    assert len(c.splitlines()) > len(a.splitlines())
    assert 'LIMITATIONS: x' in c


# ═══════════════════════════════════════════════════════════════════════════════
# Port-direction causality + output-signature tests (branch-audit fix).
# Appended after the insights block — never renumbered.
# ═══════════════════════════════════════════════════════════════════════════════

@test
def test_port_direction_precedence_and_json_roundtrip():
    import json
    import tempfile
    from core.spec_kg.knowledge_graph import SpecKG, Port, port_direction
    # derived: status/output -> output; supply/ground -> inout; control -> input
    assert port_direction(Port('A', 'status', 'digital')) == 'output'
    assert port_direction(Port('B', 'output', 'digital')) == 'output'
    assert port_direction(Port('C', 'supply', 'power')) == 'inout'
    assert port_direction(Port('D', 'control', 'digital')) == 'input'
    # explicit direction wins over the derived rule
    assert port_direction(Port('E', 'status', 'digital',
                               direction='input')) == 'input'
    # from_json reads "direction"; export round-trips it
    spec = {'ip_type': 'LDO', 'specs': [], 'fsm_states': [],
            'ports': [{'name': 'IND', 'port_type': 'status',
                       'domain': 'digital', 'voltage_range': [0, 5.5],
                       'current_range': [0, 1e-3], 'is_state_signal': True,
                       'fsm_role': 'ready', 'direction': 'inout'}]}
    path = tempfile.mktemp(suffix='.json')
    try:
        json.dump(spec, open(path, 'w', encoding='utf-8'))
        kg = SpecKG.from_json(path)
        assert port_direction(kg.ports[0]) == 'inout'
        out = tempfile.mktemp(suffix='.json')
        kg.export_to_json(out)
        assert json.load(open(out, encoding='utf-8'))['ports'][0]['direction'] == 'inout'
        os.unlink(out)
    finally:
        os.unlink(path)


def _direction_kg():
    """Mini spec: enable input + ready status output, both state signals."""
    from core.spec_kg.knowledge_graph import SpecKG, Port
    kg = SpecKG(ip_type='LDO')
    kg.add_port(Port('ENA', 'enable', 'digital', (0, 5.5), (0, 1e-3),
                     True, 'enable'))
    kg.add_port(Port('RDY', 'status', 'digital', (0, 5.5), (0, 1e-3),
                     True, 'ready'))
    kg.add_port(Port('MODE', 'control', 'digital', (0, 5.5), (0, 1e-3),
                     True, 'mode_select'))
    return kg


def _direction_capture(kg):
    from core.fsm.signal_capture import SignalCapture
    n = 400
    sc = SignalCapture(spec_kg=kg)
    sc.time = np.linspace(0, 40e-6, n)
    t = sc.time
    sc.signals = {
        'ENA': np.where(t > 5e-6, 5.5, 0.0),
        'RDY': np.where(t > 12e-6, 5.5, 0.0),   # ready follows enable
        # MODE pulses BEFORE ready asserts: the (ENA=1, MODE=1) state
        # never sees RDY high, so it must stay STARTUP-family
        'MODE': np.where((t > 6e-6) & (t < 10e-6), 5.5, 0.0),
    }
    sc._classify_signals()
    return sc


@test
def test_output_pins_never_state_bits_or_guards():
    from core.fsm.state_detector import FSMStateDetector
    from core.fsm.transition_learner import TransitionLearner
    kg = _direction_kg()
    sc = _direction_capture(kg)
    lm, ln, _ = sc.get_logic_signal_matrix()
    om, on, _ = sc.get_output_signal_matrix()
    assert 'RDY' not in ln, 'output pin leaked into the logic matrix'
    assert set(ln) == {'ENA', 'MODE'}
    assert on == ['RDY'], f'output matrix must carry RDY, got {on}'
    det = FSMStateDetector(strategy='logic', spec_kg=kg)
    seq = det.detect(lm, ln, None, output_matrix=om, output_names=on)
    for sdef in det.state_defs.values():
        assert 'RDY' not in sdef.get('pattern', {}), sdef
    trs = TransitionLearner().learn(seq, lm, ln, det.state_defs)
    for t in trs:
        assert 'RDY' not in t.guard_expression, t.guard_expression


@test
def test_output_signatures_and_name_refinement():
    from core.fsm.state_detector import (FSMStateDetector,
                                         compute_output_signatures)
    kg = _direction_kg()
    sc = _direction_capture(kg)
    lm, ln, _ = sc.get_logic_signal_matrix()
    om, on, _ = sc.get_output_signal_matrix()
    det = FSMStateDetector(strategy='logic', spec_kg=kg)
    det.detect(lm, ln, None, output_matrix=om, output_names=on)
    sigs = det.output_signatures
    names = [d['name'] for d in det.state_defs.values()]
    # enabled + ready-asserted states became REGULATION-family; the
    # DISABLED state kept its name; the pre-ready window stays STARTUP
    assert any(n.startswith('REGULATION') for n in names), names
    assert any(n.startswith('DISABLED') for n in names), names
    assert any(n.startswith('STARTUP') for n in names), names
    for sname, sig in sigs.items():
        if sname.startswith('REGULATION'):
            assert sig['RDY'] >= 0.5, (sname, sig)
        if sname.startswith('STARTUP'):
            assert sig['RDY'] < 0.5, (sname, sig)
    # direct computation on a constructed sequence
    seq = np.array([0, 0, 1, 1])
    out = np.array([[0.0], [0.0], [1.0], [1.0]])
    sd = {0: {'name': 'A'}, 1: {'name': 'B'}}
    s = compute_output_signatures(seq, out, ['X'], sd)
    assert s == {'A': {'X': 0.0}, 'B': {'X': 1.0}}


@test
def test_spec_direction_flip_changes_fsm_semantics():
    # The audit experiment, now with teeth: flipping EN_UVLO_1V2 between
    # an input role and output/status MUST move it between the guard-legal
    # input set and the signature-only output set.
    from core.spec_kg.knowledge_graph import SpecKG
    kg = SpecKG.from_json(_cfg('LDO_1V2.json'))
    pin = next(p for p in kg.ports if p.name == 'EN_UVLO_1V2')
    for ptype, expect_out in (('status', True), ('output', True),
                              ('control', False)):
        pin.port_type = ptype
        ins = {p.name for p in kg.get_fsm_input_ports()}
        outs = {p.name for p in kg.get_fsm_output_ports()}
        if expect_out:
            assert 'EN_UVLO_1V2' in outs and 'EN_UVLO_1V2' not in ins, ptype
        else:
            assert 'EN_UVLO_1V2' in ins and 'EN_UVLO_1V2' not in outs, ptype
    # explicit direction overrides even an input-ish port_type
    pin.port_type = 'control'
    pin.direction = 'output'
    assert 'EN_UVLO_1V2' in {p.name for p in kg.get_fsm_output_ports()}


@test
def test_output_consistency_gaps_reach_gap_report():
    from types import SimpleNamespace
    from core.fsm_completeness import evaluate, build_gap_report
    kg = _direction_kg()
    sd = {0: {'name': 'DISABLED', 'pattern': {'ENA': 0}},
          1: {'name': 'REGULATION', 'pattern': {'ENA': 1}}}
    # contradiction both ways: ready asserted while DISABLED, deasserted
    # while REGULATION
    sigs = {'DISABLED': {'RDY': 0.98}, 'REGULATION': {'RDY': 0.02}}
    fsm = SimpleNamespace(state_defs=sd, transitions=[], spec_kg=kg,
                          output_signatures=sigs)
    result, ref, prof = evaluate('LDO', fsm, [], registry=None)
    oc = result.output_consistency
    assert len(oc) == 2, oc
    assert result.scorecard()['n_output_contradictions'] == 2
    gap = build_gap_report(result, ref, prof)
    assert any('output-consistency' in l for l in gap.option2_limitations)
    assert any(g.gap.startswith('output-consistency') for g in gap.gaps)


@test
def test_gap_report_pins_derived_from_spec_roles():
    from types import SimpleNamespace
    from core.spec_kg.knowledge_graph import SpecKG
    from core.current_insights import CurrentRegistry
    from core.fsm_completeness import evaluate, build_gap_report
    kg = SpecKG.from_json(_cfg('LDO_1V2.json'))
    reg = CurrentRegistry(kg, None)
    fsm = SimpleNamespace(state_defs={}, transitions=[], spec_kg=kg)
    result, ref, prof = evaluate('LDO', fsm, [], registry=reg)
    with_reg = build_gap_report(result, ref, prof, registry=reg)
    joined = ' '.join(','.join(r.get('pins', []))
                      for r in with_reg.option1_runs)
    assert 'EN_LDO=' in joined and 'SCAN_MODE_VSUPPLY=1' in joined, joined
    assert '<enable>' not in joined
    # without a registry the report is honest about the missing roles
    # (explicit placeholders, never guessed pin names)
    without = build_gap_report(result, ref, prof)
    joined2 = ' '.join(','.join(r.get('pins', []))
                       for r in without.option1_runs)
    assert '<enable>=' in joined2, joined2
    assert 'EN_LDO' not in joined2


@test
def test_example7_cli_example_executes():
    import subprocess
    root = os.path.join(os.path.dirname(__file__), '..')
    proc = subprocess.run(
        [sys.executable, os.path.join(root, 'examples',
                                      'example7_fsm_blut_cli.py')],
        capture_output=True, text=True, cwd=root, timeout=1200)
    out = proc.stdout + proc.stderr
    assert proc.returncode == 0, out[-3000:]
    assert 'absent from all guards' in out, out[-2000:]
    assert 'gap report:' in out, out[-2000:]


# ═══════════════════════════════════════════════════════════════════════════════
# Runner
# ═══════════════════════════════════════════════════════════════════════════════

def run_all():
    passed = 0
    failed = 0
    print(f"\n{'='*55}")
    print(f"  surrogate_framework Test Suite — {len(TESTS)} tests")
    print(f"{'='*55}\n")

    for name, fn in TESTS:
        try:
            fn()
            print(f"  ✓  {name}")
            passed += 1
        except Exception as e:
            print(f"  ✗  {name}")
            print(f"       {type(e).__name__}: {e}")
            tb = traceback.format_exc()
            for line in tb.strip().split('\n')[-5:]:
                print(f"       {line}")
            failed += 1

    total = passed + failed
    print(f"\n{'='*55}")
    print(f"  Results: {passed}/{total} passed")
    print(f"{'='*55}\n")
    return failed == 0


if __name__ == '__main__':
    success = run_all()
    sys.exit(0 if success else 1)
