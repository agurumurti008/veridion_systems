#!/usr/bin/env python3
"""
main.py — CLI orchestrator for the surrogate_framework.
"""
import sys
import os
import argparse
import numpy as np

# ── Torch / shim bootstrap ───────────────────────────────────────────────────
try:
    import torch
except ImportError:
    import torch_shim  # noqa
    import torch


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description='Surrogate Behavioural Model Development Platform',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Required
    p.add_argument('--ip_type', type=str, required=True,
                   choices=['LDO', 'OTA', 'DCDC'],
                   help='IP type: LDO | OTA | DCDC')

    # Phase control
    p.add_argument('--phase', type=str, default='1',
                   help='Phases to run: 1 | fsm | 2 | 3 | all | comma-list')
    p.add_argument('--model', type=str, default='PINN,GPR',
                   help='Models: PINN | NODE | GPR | all | comma-list')
    p.add_argument('--bridges', type=str, default='AC,PSRR,DC',
                   help='Bridge keys: AC,PSRR,DC,NOISE,CMRR | all | none')

    # FSM
    p.add_argument('--fsm_strategy', type=str, default='hybrid',
                   choices=['logic', 'cluster', 'hybrid'],
                   help='FSM detection strategy')
    p.add_argument('--fsm_tree_depth', type=int, default=4,
                   help='Max depth of transition guard decision tree')

    # Data inputs
    p.add_argument('--data_csv', type=str, default=None,
                   help='Path to SPICE training data CSV; None → synthetic')
    p.add_argument('--sim_csv', type=str, default=None,
                   help='Path to transient waveform CSV for FSM; None → synthetic')
    p.add_argument('--silicon_csv', type=str, default=None,
                   help='Path to silicon measurements CSV; None → demo data')
    p.add_argument('--spec_json', type=str, default=None,
                   help='Load specKG from JSON instead of built-in builder')

    # digiTwin BLUT ingestion (Phase 2). Omitting --blut_path preserves
    # today's synthetic/CSV Phase 2 behavior exactly.
    p.add_argument('--blut_path', type=str, default=None,
                   help='Path to a digiTwin BLUT (.blut) file for Phase 2 '
                        'training; if given, takes priority over --data_csv '
                        'and synthetic data for Phase 2. None → unchanged '
                        'synthetic/CSV behavior.')
    p.add_argument('--blut_run_id', type=str, default=None,
                   help='Restrict BLUT ingestion to a single run_id; if '
                        'omitted, ALL runs in the BLUT file are used '
                        '(multi-run is the normal case).')
    p.add_argument('--signal_map_json', type=str, default=None,
                   help='Path to a JSON file with a top-level "signal_map" '
                        'array (see configs/*_spec.json for schema). If '
                        'omitted and --blut_path is given, falls back to '
                        'reading "signal_map" from --spec_json (if any); '
                        'if neither has one, BLUT ingestion proceeds with '
                        'raw BLUT signal names and prints an unmapped-name '
                        'warning.')
    p.add_argument('--blut_input_signals', type=str, default=None,
                   help='Comma-separated SpecKG-native input signal names '
                        'for BLUT-sourced Phase 2 training (e.g. "VIN,EN"). '
                        'Required when --blut_path is given.')
    p.add_argument('--blut_output_signals', type=str, default=None,
                   help='Comma-separated SpecKG-native output signal names '
                        'for BLUT-sourced Phase 2 training (e.g. '
                        '"VOUT,IOUT"). Required when --blut_path is given.')

    # Data generation
    p.add_argument('--export_data', action='store_true',
                   help='Generate synthetic CSV and exit immediately')
    p.add_argument('--n_samples', type=int, default=300,
                   help='LHS sample count for synthetic data')
    p.add_argument('--include_transient', action='store_true',
                   help='Add transient trajectories for NODE training')

    # Signal capture
    p.add_argument('--n_points', type=int, default=1000,
                   help='Time points in synthetic signal capture')
    p.add_argument('--t_end', type=float, default=100e-6,
                   help='Simulation end time for signal capture')

    # Training
    p.add_argument('--epochs', type=int, default=150,
                   help='Training epochs for PINN and NODE')
    p.add_argument('--silicon_epochs', type=int, default=200,
                   help='Epochs for gap correction ODE fitting')

    # Misc
    p.add_argument('--seed', type=int, default=42,
                   help='Random seed')
    p.add_argument('--save_kg', action='store_true',
                   help='Export specKG JSON to output dir')
    p.add_argument('--use_wandb', action='store_true',
                   help='Enable W&B logging (graceful skip if not installed)')
    p.add_argument('--output_dir', type=str, default='output',
                   help='Root output directory')

    return p


def _parse_phases(phase_str: str) -> list:
    if phase_str == 'all':
        return ['1', 'fsm', '2', '3']
    return [p.strip() for p in phase_str.split(',')]


def _parse_models(model_str: str) -> list:
    if model_str == 'all':
        return ['PINN', 'NODE', 'GPR']
    return [m.strip().upper() for m in model_str.split(',')]


def _parse_bridges(bridge_str: str) -> list:
    if bridge_str == 'all':
        return ['AC', 'PSRR', 'NOISE', 'DC', 'CMRR']
    if bridge_str == 'none':
        return []
    return [b.strip() for b in bridge_str.split(',')]


def _build_kg(args):
    from core.spec_kg.knowledge_graph import (
        build_ldo_kg, build_ota_kg, build_dcdc_kg, SpecKG
    )
    if args.spec_json:
        kg = SpecKG.from_json(args.spec_json)
        print(f"[main] Loaded specKG from {args.spec_json}")
    else:
        builders = {'LDO': build_ldo_kg, 'OTA': build_ota_kg, 'DCDC': build_dcdc_kg}
        kg = builders[args.ip_type]()
        print(f"[main] Built {args.ip_type} specKG")
    return kg


def _resolve_signal_map(args):
    """Resolve the SignalMap to use for BLUT ingestion:
      1. --signal_map_json if given (standalone JSON with a top-level
         "signal_map" array — same schema as the embedded block).
      2. Otherwise, the "signal_map" embedded in --spec_json, if any
         (SignalMap.from_spec_json already returns an empty map when the
         key is absent, so this is always safe to call).
      3. Otherwise, an empty SignalMap (BLUT ingestion falls back to raw
         BLUT signal names and prints an unmapped-name warning once)."""
    from digitwin.spec_signal_map import SignalMap
    if args.signal_map_json:
        sm = SignalMap.from_spec_json(args.signal_map_json)
        print(f"[main] Loaded signal_map from {args.signal_map_json} "
              f"({len(sm.entries)} entries)")
        return sm
    if args.spec_json:
        sm = SignalMap.from_spec_json(args.spec_json)
        if sm.entries:
            print(f"[main] Loaded signal_map embedded in {args.spec_json} "
                  f"({len(sm.entries)} entries)")
        return sm
    return SignalMap()


def run_fsm_phase(args, kg, output_files):
    """FSM auto-derivation from --blut_path / --sim_csv / synthetic data.

    Causality contract: only digital input/inout-direction FSM ports enter
    the state space and guard features; digital output/status ports are
    summarized as per-state output signatures (printed below and returned)
    and refine state naming. Returns a dict with the capture, detector,
    state sequence, transitions, output signatures, validation report,
    generated code, and artifact paths — reused by examples (example7) so
    the CLI and API paths are the same code."""
    print(f"\n{'='*50}")
    print(f"  FSM AUTO-DERIVATION")
    print(f"{'='*50}")
    from core.fsm.signal_capture import SignalCapture
    from core.fsm.state_detector import FSMStateDetector
    from core.fsm.transition_learner import TransitionLearner
    from core.fsm.fsm_codegen import FSMValidator, FSMCodeGenerator

    # Signal capture
    sc = SignalCapture(spec_kg=kg)
    if args.blut_path:
        signal_map = _resolve_signal_map(args)
        sc.load_from_blut(args.blut_path, run_id=args.blut_run_id,
                          signal_map=signal_map)
    elif args.sim_csv:
        sc.load_from_csv(args.sim_csv)
    else:
        sc.load_synthetic(n_points=args.n_points,
                          t_end=args.t_end,
                          ip_type=args.ip_type)

    # State detection: inputs define states; outputs become signatures
    lm, ln, lt = sc.get_logic_signal_matrix()
    om, on, _ = sc.get_output_signal_matrix()
    af = sc.get_analog_features(n_windows=10)
    detector = FSMStateDetector(strategy=args.fsm_strategy, spec_kg=kg)
    seq = detector.detect(lm, ln, af, output_matrix=om, output_names=on)
    detector.print_summary()

    if detector.output_signatures:
        print(f"  Output signatures (digital output/status ports; "
              f"observed mean per state):")
        print(f"  {'State':<20} " + ' '.join(f'{n:<14}' for n in on))
        print(f"  {'-'*(20 + 15*len(on))}")
        for sname in sorted(detector.output_signatures):
            sig = detector.output_signatures[sname]
            row = ' '.join(f'{sig.get(n, float("nan")):<14.2f}' for n in on)
            print(f"  {sname:<20} {row}")
        print()

    # Transition learning — pass the run-seam boundary mask whenever
    # this SignalCapture was built from a (possibly multi-run) BLUT
    # source, so concatenation seams are never misread as real
    # transitions (no-op / all-False mask for the synthetic/CSV path).
    feat_mat = lm
    learner = TransitionLearner(fsm_tree_depth=args.fsm_tree_depth)
    boundary_mask = sc.get_boundary_mask() if args.blut_path else None
    transitions = learner.learn(seq, feat_mat, ln, detector.state_defs,
                                boundary_mask=boundary_mask)
    learner.print_summary()

    # Validation
    validator = FSMValidator(spec_kg=kg)
    report = validator.validate(detector.state_defs, transitions,
                                ip_type=args.ip_type)
    print(f"[FSM] Validation: {report}")

    # Code generation
    codegen = FSMCodeGenerator(spec_kg=kg, ip_type=args.ip_type)
    fsm_va_code = codegen.generate_veriloga(
        detector.state_defs, transitions, kg.ports
    )
    fsm_sv_code = codegen.generate_systemverilog(
        detector.state_defs, transitions
    )

    ip = args.ip_type.lower()
    fsm_va_path = os.path.join(args.output_dir, f'{ip}_fsm.vams')
    fsm_sv_path = os.path.join(args.output_dir, f'{ip}_fsm.sv')
    with open(fsm_va_path, 'w', encoding='utf-8') as f:
        f.write(fsm_va_code)
    with open(fsm_sv_path, 'w', encoding='utf-8') as f:
        f.write(fsm_sv_code)
    output_files.append(('FSM Verilog-A', fsm_va_path))
    output_files.append(('FSM SystemVerilog', fsm_sv_path))

    return {
        'signal_capture': sc,
        'detector': detector,
        'state_sequence': seq,
        'state_defs': detector.state_defs,
        'transitions': transitions,
        'output_signatures': detector.output_signatures,
        'validation': report,
        'fsm_va_code': fsm_va_code,
        'fsm_sv_code': fsm_sv_code,
        'paths': {'vams': fsm_va_path, 'sv': fsm_sv_path},
    }


def main():
    parser = build_parser()
    args = parser.parse_args()

    # Seeds
    torch.manual_seed(args.seed)
    np.random.seed(args.seed)

    os.makedirs(args.output_dir, exist_ok=True)
    output_files = []

    # ── Export data shortcut ─────────────────────────────────────────────────
    if args.export_data:
        from data.pipeline import SyntheticDataGenerator
        gen = SyntheticDataGenerator(ip_type=args.ip_type, seed=args.seed)
        csv_path = os.path.join(args.output_dir,
                                f'{args.ip_type.lower()}_synthetic.csv')
        gen.export_csv(n_samples=args.n_samples, filepath=csv_path)
        output_files.append(('Synthetic CSV', csv_path))
        _print_summary(output_files)
        return

    # ── Build specKG ─────────────────────────────────────────────────────────
    kg = _build_kg(args)

    if args.save_kg:
        kg_path = os.path.join(args.output_dir, f'{args.ip_type.lower()}_speckg.json')
        kg.export_to_json(kg_path)
        output_files.append(('SpecKG JSON', kg_path))
        print(f"[main] SpecKG saved to {kg_path}")

    # Parse options
    phases    = _parse_phases(args.phase)
    models    = _parse_models(args.model)
    bridge_keys = _parse_bridges(args.bridges)

    # Build active bridges dict
    active_bridges = kg.get_bridges_for_keys(bridge_keys)

    # ── Phase 1 ──────────────────────────────────────────────────────────────
    fsm_code = ''
    if '1' in phases:
        print(f"\n{'='*50}")
        print(f"  PHASE 1 — Spec-Based Code Generation")
        print(f"{'='*50}")
        from core.phases.phase1_spec_based import Phase1SpecBasedGenerator
        gen1 = Phase1SpecBasedGenerator(kg)
        va_path, sv_path = gen1.generate_all(
            fsm_code='', output_dir=args.output_dir
        )
        output_files.append(('Phase1 Verilog-A', va_path))
        output_files.append(('Phase1 SystemVerilog', sv_path))

    # ── FSM Phase ────────────────────────────────────────────────────────────
    if 'fsm' in phases:
        fsm_phase = run_fsm_phase(args, kg, output_files)
        fsm_code = fsm_phase['fsm_va_code']

    # ── Phase 2 ──────────────────────────────────────────────────────────────
    if '2' in phases:
        print(f"\n{'='*50}")
        print(f"  PHASE 2 — Sim-Augmented Training")
        print(f"{'='*50}")
        from core.phases.phase2_sim_augmented import Phase2SimAugmented

        phase2 = Phase2SimAugmented(kg, use_wandb=args.use_wandb)

        if args.blut_path:
            if not args.blut_input_signals or not args.blut_output_signals:
                raise ValueError(
                    "--blut_path requires both --blut_input_signals and "
                    "--blut_output_signals (comma-separated SpecKG-native "
                    "signal names, e.g. --blut_input_signals VIN,EN "
                    "--blut_output_signals VOUT,IOUT)."
                )
            from core.fsm.state_detector import FSMStateDetector as _FSMStateDetector
            signal_map = _resolve_signal_map(args)
            fsm_detector_for_blut = _FSMStateDetector(strategy=args.fsm_strategy, spec_kg=kg)
            data = phase2.build_dataset_from_blut(
                args.blut_path, signal_map,
                input_signal_names=[s.strip() for s in args.blut_input_signals.split(',')],
                output_signal_names=[s.strip() for s in args.blut_output_signals.split(',')],
                fsm_detector=fsm_detector_for_blut,
            )
        else:
            from data.pipeline import SyntheticDataGenerator
            gen = SyntheticDataGenerator(ip_type=args.ip_type, seed=args.seed)
            if args.data_csv:
                data = gen.load_from_csv(args.data_csv)
            else:
                data = gen.to_torch_dataset(
                    n_samples=args.n_samples,
                    include_transient=args.include_transient,
                )

        from core.tensor_utils import to_np as _to_np; X_np = _to_np(data['X']).astype(np.float32)
        input_dim  = X_np.shape[1]
        Y_np = _to_np(data['Y']).astype(np.float32)
        output_dim = Y_np.shape[1]

        phase2.initialize_models(
            input_dim=input_dim,
            output_dim=output_dim,
            n_fsm_states=len(kg.fsm_states) or 4,
            state_dim=2,
            user_bridges=active_bridges,
            model_names=models,
        )

        metrics = phase2.incremental_train(
            data=data,
            analysis_data={'phase_margin': 60, 'gain_bandwidth': 50e6},
            iteration=0,
            epochs=args.epochs,
        )

        # feature_names/output_names: build_dataset_from_blut already sets
        # these on phase2 directly; the synthetic/CSV branch sets them from
        # the SyntheticDataGenerator instance here so both paths converge
        # on the same phase2.feature_names/phase2.output_names contract.
        if not args.blut_path:
            phase2.feature_names = gen.feature_names
            phase2.output_names = gen.output_names

        interp = phase2.extract_interpretable(
            X_np, phase2.feature_names, phase2.output_names
        )

        p2_path = phase2.generate_phase2_veriloga(
            fsm_code=fsm_code,
            interpretable=interp,
            output_dir=args.output_dir,
        )
        output_files.append(('Phase2 Verilog-A', p2_path))

        # Print model comparison
        from core.models.gpr_surrogate import ModelSelector
        mse_dict = {k: v['test_mse'] for k, v in metrics.items()}
        best = ModelSelector.select_best(mse_dict, phase2.models)
        print(f"[Phase2] Best model: {best}")

    # ── Phase 3 ──────────────────────────────────────────────────────────────
    if '3' in phases:
        print(f"\n{'='*50}")
        print(f"  PHASE 3 — Silicon Calibration")
        print(f"{'='*50}")
        from core.phases.phase3_silicon import Phase3SiliconCalibration, SiliconMeasurement
        import json

        phase3 = Phase3SiliconCalibration(kg)

        # Demo sim predictions
        sim_preds = {s.name: s.nominal for s in kg.specs[:3]}

        if args.silicon_csv:
            # Load from CSV
            silicon_data = _load_silicon_csv(args.silicon_csv)
        else:
            silicon_data = phase3.generate_demo_silicon_data(kg, sim_preds)

        gaps = phase3.compute_gaps(silicon_data, sim_preds)

        # Fit gap ODE on first chip's data (demo)
        n_t = 50
        t_sp = np.linspace(0, 1e-4, n_t)
        sim_traj = np.ones((n_t, 1)) * list(sim_preds.values())[0]
        sil_val  = list(silicon_data[0].measurements.values())[0]
        sil_traj = np.ones((n_t, 1)) * sil_val * 1.03

        phase3.fit_gap_correction(
            sim_traj, sil_traj, t_sp, epochs=args.silicon_epochs
        )
        insights = phase3.extract_device_insights()
        p3_path  = phase3.generate_phase3_veriloga(output_dir=args.output_dir)
        output_files.append(('Phase3 Verilog-A', p3_path))

        # Save JSON reports
        gap_report_path = os.path.join(args.output_dir, 'gap_report.json')
        insights_path   = os.path.join(args.output_dir, 'device_insights.json')
        with open(gap_report_path, 'w', encoding='utf-8') as f:
            json.dump({cid: [{k: str(v) for k, v in g.items()} for g in glist]
                       for cid, glist in gaps.items()}, f, indent=2)
        with open(insights_path, 'w', encoding='utf-8') as f:
            json.dump({k: {ik: str(iv) for ik, iv in v.items()}
                       for k, v in insights.items()}, f, indent=2)

        output_files.append(('Gap Report', gap_report_path))
        output_files.append(('Device Insights', insights_path))

    _print_summary(output_files)


def _load_silicon_csv(filepath: str):
    """Load silicon measurements from CSV."""
    from core.phases.phase3_silicon import SiliconMeasurement
    try:
        import pandas as pd
        df = pd.read_csv(filepath)
        measurements = []
        for _, row in df.iterrows():
            meas = {}
            for col in df.columns:
                if col not in ['chip_id', 'pvt_corner', 'temperature', 'vdd']:
                    try:
                        meas[col] = float(row[col])
                    except Exception:
                        pass
            measurements.append(SiliconMeasurement(
                chip_id=str(row.get('chip_id', 'chip_000')),
                pvt_corner=str(row.get('pvt_corner', 'TT')),
                temperature=float(row.get('temperature', 27.0)),
                vdd=float(row.get('vdd', 1.8)),
                measurements=meas,
            ))
        return measurements
    except Exception as e:
        print(f"[main] Failed to load silicon CSV: {e}")
        return []


def _print_summary(output_files: list):
    print(f"\n{'='*55}")
    print(f"  OUTPUT FILES SUMMARY")
    print(f"{'='*55}")
    for label, path in output_files:
        exists = '✓' if os.path.exists(path) else '✗'
        print(f"  {exists} {label:<25} {path}")
    print()


if __name__ == '__main__':
    main()
