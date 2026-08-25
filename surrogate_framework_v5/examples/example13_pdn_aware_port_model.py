#!/usr/bin/env python3
"""
examples/example13_pdn_aware_port_model.py — EXPLORATORY branch. First
version to try/test, not a finished capability (per the request that
spawned it: "if this ask is complex, strategize this as a separate
branch of example to try and test it").

Idea: a modeled port's V-I behavior should look like it's actually
sitting behind a power-delivery network (PDN), not an ideal source.
Concretely — "if the capacitor is charging, the current driven by the
port reduces as the delta potential between port and capacitor voltage
(connected by a resistor) shrinks" — classic RC charging current,
extended here with an optional series inductance:

    V(port_ideal, port) <+ R_pdn*I(port_ideal, port)
                          + L_pdn*ddt(I(port_ideal, port));   // series R(+L)
    I(port, gnd)         <+ C_pdn*ddt(V(port, gnd));          // shunt decoupling C

`port_ideal` is a new internal/diagnostic node driven, per FSM state,
by the SAME kind of fitted equation example12 embeds directly on the
real pin — here it represents the port's intrinsic/open-circuit target
(e.g. a regulator's set-point) rather than its final, PDN-loaded value.
The real `port` pin's actual V/I then emerges from the simulator
solving that RLC branch's KCL/KVL together with whatever the external
testbench connects — current genuinely reduces as V(port_ideal) and
V(port) converge, exactly the behavior described above. `L_pdn` set to
0 degenerates to a pure RC network.

Multiple named PDN variants (R/L/C triples — think "board decap X" vs
"board decap Y") are selectable via --pdn_variant; each produces a
.vams differing ONLY in the inlined R_pdn/L_pdn/C_pdn defaults
(themselves plain `parameter real`s, still overridable per simulation
instance — nothing here is hardcoded past the default).

Implementation notes:
  - No changes to core/fsm/fsm_codegen.py. The new `<port>_ideal` node
    is produced entirely through FSMCodeGenerator.generate_veriloga's
    EXISTING output_equations/equation_parameters mechanism (a target
    name that isn't a real port and doesn't match a "<port>_I" current
    convention becomes a brand-new diagnostic output port, per that
    method's own docstring) — the RLC branch itself is then spliced in
    as a few hand-written lines, right before the `end  // analog
    begin` marker that method always emits.
  - Reuses example12_phase2_refined_modeling.py's `_polynomial_equation`
    (smooth, +/-/* only — see that module's docstring) for the port's
    intrinsic per-state equation; steps 1-2 (global FSM + corner-and-
    state-labeled dataset, target-encoded categorical meta) are the
    same pipeline as example12, trimmed to the single chosen port.

Known simplifications (first version — documented, not hidden):
  - One RLC network per port; no cross-port/rail coupling modeled.
  - R/L/C are linear, fixed-per-run (no temperature/aging dependence).
  - The "ideal" node only updates when the FSM's current_state changes
    (matching how output_equations already works) — it's a per-state
    set-point, not a continuously-varying intrinsic waveform.
  - Only ONE port gets PDN-aware treatment per run (--pdn_port); other
    ports are left exactly as the plain FSM control skeleton drives them
    (i.e. undriven unless a 'ready'/'fault' role applies).

Run:  uv run examples/example13_pdn_aware_port_model.py \\
          [--correlation_json output/per_corner_correlation.json] \\
          [--blut_path PATH] [--spec_json PATH] [--signal_map_json PATH] \\
          [--fsm_strategy hybrid] [--fsm_tree_depth 4] [--ip_type LDO] \\
          [--blut_input_signals VPWR,EN_LDO,VPWR_SEL,HIGH_POWER_MODE] \\
          [--pdn_port VDD_1V2] [--pdn_variant decap_1uF_tight] \\
          [--equation_degree 2] \\
          [--min_state_samples 30] [--max_state_samples 3000] \\
          [--output_dir output/phase2_pdn_aware_port]
"""
import argparse
import json
import os
import sys
from typing import Dict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

try:
    import torch  # noqa: F401
except ImportError:
    import torch_shim  # noqa: F401

import numpy as np

from example12_phase2_refined_modeling import _polynomial_equation

ROOT = os.path.join(os.path.dirname(__file__), '..')
CFG = os.path.join(ROOT, 'configs')

# Named R/L/C variants — mirrors core/pvt/param_lut.py's LutParamProvider
# "named-variant dict" shape, kept local (no natural SpecKG field for
# external board/package PDN metadata; confirmed via repo-wide search).
# Users can add real board/package-measured R/L/C directly here.
PDN_VARIANTS: Dict[str, Dict[str, float]] = {
    'decap_1uF_tight':   {'R': 0.05, 'L': 1e-9,  'C': 1e-6},
    'decap_100nF_loose': {'R': 0.30, 'L': 5e-9,  'C': 100e-9},
    'decap_10uF_bulk':   {'R': 0.02, 'L': 2e-9,  'C': 10e-6},
}


def build_parser():
    ap = argparse.ArgumentParser()
    ap.add_argument('--correlation_json', default=os.path.join(
        ROOT, 'output', 'per_corner_correlation.json'))
    ap.add_argument('--blut_path', default=None,
                    help='Defaults to the blut_path recorded in '
                         '--correlation_json')
    ap.add_argument('--spec_json', default=os.path.join(CFG, 'LDO_1V2.json'))
    ap.add_argument('--signal_map_json',
                    default=os.path.join(CFG, 'signal_map_ldo.json'))
    ap.add_argument('--fsm_strategy', default='hybrid',
                    choices=['logic', 'cluster', 'hybrid'])
    ap.add_argument('--fsm_tree_depth', type=int, default=4)
    ap.add_argument('--ip_type', default='LDO')
    ap.add_argument('--blut_input_signals',
                    default='VPWR,EN_LDO,VPWR_SEL,HIGH_POWER_MODE')
    ap.add_argument('--pdn_port', default='VDD_1V2',
                    help='Real SpecKG port name to wire through a PDN '
                         'RLC network (must be an existing electrical '
                         'port — e.g. a regulator output rail).')
    ap.add_argument('--pdn_variant', default=next(iter(PDN_VARIANTS)),
                    choices=list(PDN_VARIANTS),
                    help='Which named R/L/C triple to inline as the '
                         'default PDN parameters for this run.')
    ap.add_argument('--equation_degree', type=int, default=2,
                    help='Polynomial degree for the intrinsic/ideal '
                         'per-state port equation (see example12).')
    ap.add_argument('--min_state_samples', type=int, default=30)
    ap.add_argument('--max_state_samples', type=int, default=3000)
    ap.add_argument('--output_dir',
                    default=os.path.join(ROOT, 'output', 'phase2_pdn_aware_port'))
    return ap


def _write_json(path, obj):
    with open(path, 'w') as f:
        json.dump(obj, f, indent=2, default=str)


def main() -> int:
    args = build_parser().parse_args()

    with open(args.correlation_json) as f:
        correlation = json.load(f)
    blut_path = args.blut_path or correlation['blut_path']
    corners = correlation['corners']
    good = [r for r in corners if not r['outlier'] and not r['fsm_generation_failed']]
    good_qids = [r['qid'] for r in good]
    if not good_qids:
        print("FAIL: no non-outlier corners available in "
              f"{args.correlation_json} — run example9 first.")
        return 1

    os.makedirs(args.output_dir, exist_ok=True)
    pdn = PDN_VARIANTS[args.pdn_variant]

    import main as framework_main
    from core.fsm.signal_capture import SignalCapture
    from core.fsm.state_detector import FSMStateDetector
    from core.fsm.transition_learner import TransitionLearner
    from core.fsm.fsm_codegen import FSMValidator, FSMCodeGenerator, _vid
    from core.phases.phase2_sim_augmented import Phase2SimAugmented
    from core.tensor_utils import to_np

    kg = framework_main._build_kg(args)
    sm = framework_main._resolve_signal_map(args)

    port_names = [p.name for p in kg.ports]
    if args.pdn_port not in port_names:
        print(f"FAIL: --pdn_port '{args.pdn_port}' is not a SpecKG port "
              f"for --ip_type {args.ip_type} (available: {port_names})")
        return 1

    print(f"\n{'='*60}\n  1. Authoritative global FSM (control-logic skeleton)"
          f"\n{'='*60}")
    print(f"  {len(good_qids)}/{len(corners)} good corners")
    sc = SignalCapture(spec_kg=kg)
    sc.load_from_blut(blut_path, run_id=good_qids, signal_map=sm)
    lm, ln, _ = sc.get_logic_signal_matrix()
    om, on, _ = sc.get_output_signal_matrix()
    af = sc.get_analog_features(n_windows=10)
    detector = FSMStateDetector(strategy=args.fsm_strategy, spec_kg=kg)
    seq = detector.detect(lm, ln, af, output_matrix=om, output_names=on)
    detector.print_summary()
    learner = TransitionLearner(fsm_tree_depth=args.fsm_tree_depth)
    transitions = learner.learn(seq, lm, ln, detector.state_defs,
                                boundary_mask=sc.get_boundary_mask())
    learner.print_summary()
    validator = FSMValidator(spec_kg=kg)
    fsm_report = validator.validate(detector.state_defs, transitions,
                                    ip_type=args.ip_type)
    print(f"  Validation: {fsm_report}")
    sc.signals = {}
    sc.current_signals = {}

    print(f"\n{'='*60}\n  2. Corner-and-state-labeled dataset for "
          f"'{args.pdn_port}'\n{'='*60}")
    input_names = [s.strip() for s in args.blut_input_signals.split(',')]
    phase2 = Phase2SimAugmented(kg)
    fsm_detector_for_blut = FSMStateDetector(strategy=args.fsm_strategy, spec_kg=kg)
    data = phase2.build_dataset_from_blut(
        blut_path, sm, input_names, [args.pdn_port],
        fsm_detector=fsm_detector_for_blut, run_ids=good_qids,
    )
    if len(data['X']) != len(seq):
        print(f"FAIL: row-count mismatch between build_dataset_from_blut "
              f"({len(data['X'])} rows) and the global FSM capture "
              f"({len(seq)} samples) — cannot trust per-row state labels.")
        return 1
    data = phase2.target_encode_categorical_meta(data)
    categorical_codes = data.get('categorical_codes', {})
    if categorical_codes:
        print("  categorical corner codes:")
        for key, mapping in categorical_codes.items():
            print(f"    meta_{key}: " +
                  '  '.join(f"{v}={c:.4g}" for v, c in mapping.items()))

    X_np = to_np(data['X']).astype(np.float64)
    Y_np = to_np(data['Y']).astype(np.float64)
    feature_names = [_vid(n) for n in data['feature_names']]
    equation_parameters = {
        name: float(X_np[:, i].mean())
        for i, name in enumerate(feature_names) if name.startswith('meta_')
    }
    # PDN R/L/C ride the same equation_parameters -> `parameter real ...`
    # declaration mechanism as the meta/corner terms above.
    equation_parameters['R_pdn'] = pdn['R']
    equation_parameters['L_pdn'] = pdn['L']
    equation_parameters['C_pdn'] = pdn['C']

    print(f"\n{'='*60}\n  3. Per-state intrinsic/ideal equation for "
          f"'{args.pdn_port}'\n{'='*60}")
    print(f"  PDN variant: {args.pdn_variant}  "
          f"R={pdn['R']:g}  L={pdn['L']:g}  C={pdn['C']:g}")

    rng = np.random.RandomState(42)
    ideal_name = f'{args.pdn_port}_ideal'
    output_equations = {}   # {state_id: {ideal_name: equation_text}}
    equation_info = {}      # {state_id: {equation, r2, n_samples}}
    for sid in sorted(detector.state_defs.keys()):
        sname = detector.state_defs[sid]['name']
        mask = (seq == sid)
        n_state = int(mask.sum())
        if n_state < args.min_state_samples:
            print(f"  state {sid} ({sname}): n={n_state} < "
                  f"--min_state_samples={args.min_state_samples}, skipped")
            continue

        X_s, Y_s = X_np[mask], Y_np[mask]
        if n_state > args.max_state_samples:
            sub_idx = rng.choice(n_state, size=args.max_state_samples, replace=False)
            X_s, Y_s = X_s[sub_idx], Y_s[sub_idx]
            n_state = args.max_state_samples

        eq_text, r2 = _polynomial_equation(
            X_s, Y_s[:, 0], feature_names, degree=args.equation_degree)
        output_equations[sid] = {ideal_name: eq_text}
        equation_info[sid] = {'equation': eq_text, 'r2': r2, 'n_samples': n_state}
        print(f"  state {sid} ({sname}): n={n_state}  R2={r2:.3f}")

    print(f"\n{'='*60}\n  4. PDN-aware codegen\n{'='*60}")
    codegen = FSMCodeGenerator(spec_kg=kg, ip_type=args.ip_type)
    va_code = codegen.generate_veriloga(
        detector.state_defs, transitions, kg.ports,
        output_equations=output_equations,
        equation_parameters=equation_parameters,
    )
    sv_code = codegen.generate_systemverilog(detector.state_defs, transitions)

    # Splice the RLC branch in right before the analog block closes —
    # `port_ident`/`ideal_ident` are already declared `electrical` (real
    # port + new diagnostic output port, both handled by generate_veriloga
    # above); gnd resolved the exact same way generate_veriloga does.
    port_ident = _vid(args.pdn_port)
    ideal_ident = _vid(ideal_name)
    ground_ports = [p for p in kg.ports if p.port_type == 'ground']
    gnd_ident = _vid(ground_ports[0].name) if ground_ports else '0'
    pdn_block = (
        '        // ── PDN-aware port loading (example13, exploratory) ──\n'
        f'        // series R(+L): "ideal" intrinsic node -> real pin\n'
        f'        V({ideal_ident}, {port_ident}) <+ R_pdn*I({ideal_ident}, {port_ident})'
        f' + L_pdn*ddt(I({ideal_ident}, {port_ident}));\n'
        f'        // shunt decoupling C at the real pin -- current drawn\n'
        f'        // from {ideal_ident} shrinks as V({port_ident}) settles\n'
        f'        // toward V({ideal_ident}), i.e. as their delta-V shrinks\n'
        f'        I({port_ident}, {gnd_ident}) <+ C_pdn*ddt(V({port_ident}, {gnd_ident}));\n'
        '\n'
    )
    marker = '    end  // analog begin'
    marker_idx = va_code.index(marker)
    va_code = va_code[:marker_idx] + pdn_block + va_code[marker_idx:]

    ip = args.ip_type.lower()
    va_path = os.path.join(args.output_dir, f'{ip}_pdn_aware_{args.pdn_variant}.vams')
    sv_path = os.path.join(args.output_dir, f'{ip}_pdn_aware_{args.pdn_variant}.sv')
    with open(va_path, 'w') as f:
        f.write(va_code)
    with open(sv_path, 'w') as f:
        f.write(sv_code)

    embedded_ok = ('R_pdn*I(' in va_code and 'C_pdn*ddt(V(' in va_code
                   and len(output_equations) > 0)
    print(f"\n  PDN-aware port loading: {'EMBEDDED' if embedded_ok else 'NOT EMBEDDED'}")
    print(f"    port: {args.pdn_port}  ideal node: {ideal_name}  "
          f"states with equation: {len(output_equations)}")

    manifest_path = os.path.join(args.output_dir, 'manifest.md')
    model_json = {
        'blut_path': blut_path,
        'good_corners': len(good_qids),
        'total_corners': len(corners),
        'pdn_port': args.pdn_port,
        'pdn_variant': args.pdn_variant,
        'pdn_params': pdn,
        'categorical_codes': categorical_codes,
        'equation_parameters': equation_parameters,
        'states': {
            str(sid): {
                'name': detector.state_defs[sid]['name'],
                **info,
            } for sid, info in equation_info.items()
        },
        'pdn_aware_embedded': embedded_ok,
    }
    _write_json(os.path.join(args.output_dir,
                             f'model_{args.pdn_variant}.json'), model_json)

    with open(manifest_path, 'w') as f:
        L = ['# example13 Run Manifest — PDN-Aware Port Model (exploratory)', '',
             '```',
             '1. Load per_corner_correlation.json -> filter good corners',
             '2. Global FSM (SignalCapture + FSMStateDetector + '
             'TransitionLearner + FSMValidator) -> state_defs, transitions',
             f'3. Phase2SimAugmented.build_dataset_from_blut(output=[{args.pdn_port}])',
             '   -> target_encode_categorical_meta (single meta_corner variable)',
             f'4. Per state: degree-{args.equation_degree} polynomial equation for '
             f'{args.pdn_port}_ideal (intrinsic/set-point target, embedded)',
             '5. FSMCodeGenerator.generate_veriloga(output_equations={<port>_ideal: eq})',
             '   -> new diagnostic port <port>_ideal, driven per-state',
             '6. Hand-spliced PDN RLC branch (this script, not fsm_codegen.py):',
             f'   V({ideal_ident}, {port_ident}) <+ R_pdn*I(...) + L_pdn*ddt(I(...));',
             f'   I({port_ident}, {gnd_ident}) <+ C_pdn*ddt(V({port_ident}, {gnd_ident}));',
             '```', '',
             f'BLUT: `{blut_path}`',
             f'Correlation source: `{args.correlation_json}`',
             f'Good corners: {len(good_qids)}/{len(corners)}',
             f'FSM strategy: `{args.fsm_strategy}`',
             f'PDN port: `{args.pdn_port}`  (ideal/intrinsic node: `{ideal_name}`)',
             f'PDN variant: `{args.pdn_variant}`  '
             f'R_pdn={pdn["R"]:g}  L_pdn={pdn["L"]:g}  C_pdn={pdn["C"]:g}',
             f'Available PDN variants: {list(PDN_VARIANTS)}',
             '']
        if categorical_codes:
            L += ['## Categorical corner codes', '']
            for key, mapping in categorical_codes.items():
                L.append(f"- `meta_{key}`: " +
                        ', '.join(f"{v}={c:.4g}" for v, c in mapping.items()))
            L.append('')
        L += ['## Per-state intrinsic/ideal equation', '',
              '| state | n_samples | R2 | equation |', '|---|---|---|---|']
        for sid, info in equation_info.items():
            sname = detector.state_defs[sid]['name']
            eq_str = (info['equation'] or 'FAILED')[:160]
            L.append(f"| {sname} | {info['n_samples']} | {info['r2']:.3f} | `{eq_str}` |")
        L += ['',
             '## Known simplifications (first version)', '',
             '- One RLC network per port; no cross-port/rail coupling.',
             '- R/L/C are linear and fixed for the run (no temp/aging dependence).',
             '- The intrinsic/ideal node only updates on FSM state change '
             '(a per-state set-point, not a continuously-varying source).',
             '- Only `--pdn_port` gets PDN-aware treatment; other ports are '
             'left exactly as the plain FSM control skeleton drives them.',
             '',
             f'**PDN-aware port loading: '
             f'{"EMBEDDED" if embedded_ok else "NOT EMBEDDED"}**',
             '',
             '## Output files', '',
             f'- `{va_path}` — Verilog-A (FSM + intrinsic equation + PDN RLC branch)',
             f'- `{sv_path}` — SystemVerilog control skeleton',
             f'- `{os.path.join(args.output_dir, f"model_{args.pdn_variant}.json")}`',
             '']
        f.write('\n'.join(L))

    print(f"\n{'='*60}\n  OUTPUT FILES")
    print(f"{'='*60}")
    print(f"  Final Verilog-A       {va_path}")
    print(f"  Final SystemVerilog   {sv_path}")
    print(f"  Manifest              {manifest_path}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
