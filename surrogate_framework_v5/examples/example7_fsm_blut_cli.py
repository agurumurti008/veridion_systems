#!/usr/bin/env python3
"""
examples/example7_fsm_blut_cli.py — FSM auto-derivation from a real digiTwin
BLUT via the SAME entry point the CLI uses.

This example is wired to the documented command:

    uv run main.py --phase fsm --fsm_strategy logic \
        --spec_json configs/LDO_1V2.json \
        --signal_map_json configs/signal_map_ldo.json \
        --ip_type LDO --blut_path blut_files/regression1.bin

It IMPORTS main.build_parser + main.run_fsm_phase (no shell-out), so the
example and `main.py` cannot drift apart. After the FSM phase it runs the
Capability-B completeness evaluation (including the output-consistency
check driven by the detected output signatures) and writes the customer
gap report.

If blut_files/regression1.bin is absent (fresh checkout without the data
drop), a v8-format stand-in covering every signal_map entry is generated
so the flow stays runnable end to end; the console states clearly which
source was used.

Run:  uv run examples/example7_fsm_blut_cli.py   [--blut PATH] [--output_dir DIR]
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import numpy as np

try:
    import torch  # noqa: F401
except ImportError:
    import torch_shim  # noqa: F401

ROOT = os.path.join(os.path.dirname(__file__), '..')
CFG = os.path.join(ROOT, 'configs')
DEFAULT_BLUT = os.path.join(ROOT, 'blut_files', 'regression1.bin')

# The exact CLI argument vector this example reproduces (spec/map paths
# resolved relative to the repo so the example runs from any cwd).
CLI_ARGS = ['--phase', 'fsm', '--fsm_strategy', 'logic',
            '--spec_json', os.path.join(CFG, 'LDO_1V2.json'),
            '--signal_map_json', os.path.join(CFG, 'signal_map_ldo.json'),
            '--ip_type', 'LDO']


def build_standin_blut(path: str, signal_map) -> None:
    """v8-format stand-in exercising every signal_map name: EN_LDO enable
    ramp with the ready indicator following, a mode toggle, and quiet
    supplies — enough for states, guards, and output signatures."""
    from digitwin import blut_format as bf
    n = 1200
    t = np.linspace(0, 120e-6, n)
    en = (t > 10e-6).astype(float)
    ready = (t > 22e-6).astype(float)
    hp = ((t > 60e-6) & (t < 90e-6)).astype(float)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'wb') as f:
        bf.write_file_header(f, n_runs=0)
        off = f.tell()
        bf.write_run_header(f, 0, 'standin', 'corner=TT_1p8V_27C', t,
                            corner_id='TT_1p8V_27C')
        idxs = np.arange(n, dtype=np.int64)
        n_sig = 0
        for e in signal_map.entries:
            name = e.speckg_name
            if e.kind == 'current':
                trace = np.where(en > 0, 5e-5, 1e-6)
            elif name == 'EN_LDO':
                trace = en * 5.5
            elif name == 'EN_UVLO_1V2':
                trace = ready * 5.5
            elif name == 'HIGH_POWER_MODE':
                trace = hp * 5.5
            elif name in ('AVSS', 'GND', 'PBKG'):
                trace = np.zeros(n)
            elif name == 'VDD_1V2':
                trace = ready * 1.2
            else:
                trace = np.full(n, 5.0)
            bf.write_signal_block(f, e.blut_signal, idxs, trace,
                                  bf.ENC_FLOAT64, 0.0, 1.0, compress=False)
            n_sig += 1
        bf.patch_run_n_signals(f, off, n_sig)
        bf.patch_file_header_counts(f, 1)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--blut', default=None,
                    help='BLUT path (default blut_files/regression1.bin)')
    ap.add_argument('--output_dir', default=os.path.join(ROOT, 'output'))
    ex_args = ap.parse_args()

    import main as framework_main
    from digitwin.spec_signal_map import SignalMap
    from digitwin.blut_reader_ext import load_all_runs
    from core.current_insights import CurrentRegistry, build_run_views
    from core.fsm_completeness import evaluate, build_gap_report

    blut_path = ex_args.blut or DEFAULT_BLUT
    if os.path.exists(blut_path):
        print(f'== 1. BLUT source: real file {blut_path} ==')
    else:
        print(f'== 1. BLUT source: {blut_path} missing — generating a '
              f'v8 stand-in covering every signal_map entry ==')
        sm_tmp = SignalMap.from_spec_json(
            os.path.join(CFG, 'signal_map_ldo.json'))
        build_standin_blut(blut_path, sm_tmp)

    # ── 2. The user's exact CLI, through main's own parser + phase ─────────
    argv = CLI_ARGS + ['--blut_path', blut_path,
                       '--output_dir', ex_args.output_dir]
    print(f'== 2. FSM phase via main.run_fsm_phase, argv: {" ".join(argv)} ==')
    args = framework_main.build_parser().parse_args(argv)
    kg = framework_main._build_kg(args)
    os.makedirs(args.output_dir, exist_ok=True)
    output_files = []
    fsm = framework_main.run_fsm_phase(args, kg, output_files)

    detector = fsm['detector']
    transitions = fsm['transitions']
    if not detector.state_defs or not transitions:
        print('FAIL: no states/transitions detected')
        return 1

    print('== 3. Detected FSM ==')
    print(f"   states ({len(detector.state_defs)}): "
          f"{[d['name'] for d in detector.state_defs.values()]}")
    print(f'   transitions: {len(transitions)}; guard features used: '
          f'{sorted({c.split(" ")[0] for t in transitions for c in t.conditions})}')

    # Causality check the example enforces: no output-direction pin may
    # appear in any guard.
    out_pins = {p.name for p in kg.get_fsm_output_ports()}
    offending = [t.guard_expression for t in transitions
                 if any(op in t.guard_expression for op in out_pins)]
    if offending:
        print(f'FAIL: output pins leaked into guards: {offending}')
        return 1
    print(f'   output pins {sorted(out_pins)} absent from all guards ✓')
    if fsm['output_signatures']:
        print(f'   output signatures recorded for '
              f'{len(fsm["output_signatures"])} states ✓')

    # ── 4. Completeness + customer gap report ──────────────────────────────
    print('== 4. Completeness (Capability B) + gap report ==')
    sm = SignalMap.from_spec_json(args.signal_map_json)
    registry = CurrentRegistry(kg, sm)
    runs = load_all_runs(blut_path, None, ['$flow'], signal_map=sm)
    sc = fsm['signal_capture']
    seq = fsm['state_sequence']
    bounds = list(sc.run_boundaries) + [len(seq)]
    state_sequences = {}
    for k, rid in enumerate(sc.run_ids):
        state_sequences[f'{rid}@{sc.run_corners[k]}'] = seq[bounds[k]:bounds[k + 1]]
    views = build_run_views(runs, registry, state_sequences=state_sequences,
                            state_defs=detector.state_defs)
    from types import SimpleNamespace
    fsm_result = SimpleNamespace(state_defs=detector.state_defs,
                                 transitions=transitions, spec_kg=kg,
                                 output_signatures=fsm['output_signatures'])
    coverage, ref, profile = evaluate('LDO', fsm_result, views,
                                      registry=registry)
    gap = build_gap_report(coverage, ref, profile, registry=registry)
    md_path = os.path.join(args.output_dir, 'gap_report_cli.md')
    gap.to_markdown(md_path)
    gap.to_json(os.path.join(args.output_dir, 'gap_report_cli.json'))
    for k, v in coverage.scorecard().items():
        print(f'   {k:26s} {v}')
    print(f'   gap report: {md_path} (+ .json)')

    print('\n== artifacts ==')
    for label, path in output_files:
        print(f'   {label:24s} {path}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
