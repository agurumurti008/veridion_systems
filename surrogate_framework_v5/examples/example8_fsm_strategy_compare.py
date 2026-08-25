#!/usr/bin/env python3
"""
examples/example8_fsm_strategy_compare.py — run FSM auto-derivation with
every --fsm_strategy option (logic / cluster / hybrid) against the same
BLUT source and compare the results side by side.

Imports main.build_parser + main._build_kg + main.run_fsm_phase (no
shell-out), the same reuse pattern as example7_fsm_blut_cli.py, so this
can never drift from the CLI. Each strategy's .vams/.sv is written to its
own subdirectory under --output_dir so the three runs never clobber each
other.

Run:  uv run examples/example8_fsm_strategy_compare.py \\
          [--blut_path PATH] [--spec_json PATH] [--signal_map_json PATH] \\
          [--ip_type LDO] [--output_dir output/fsm_compare]
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

try:
    import torch  # noqa: F401
except ImportError:
    import torch_shim  # noqa: F401

ROOT = os.path.join(os.path.dirname(__file__), '..')
CFG = os.path.join(ROOT, 'configs')

STRATEGIES = ('logic', 'cluster', 'hybrid')


def _report_to_dict(report) -> dict:
    """ValidationReport has no built-in dict conversion; only this
    comparison script needs one, so it lives here rather than in
    core/fsm/fsm_codegen.py."""
    return {
        'reachability': report.reachability,
        'completeness': report.completeness,
        'determinism': report.determinism,
        'speckg_coverage': round(report.speckg_coverage, 4),
        'missing_states': list(report.missing_states),
        'missing_transitions': [list(t) for t in report.missing_transitions],
        'warnings': list(report.warnings),
        'errors': list(report.errors),
    }


def run_strategy(framework_main, strategy: str, base_args) -> dict:
    argv = [
        '--ip_type', base_args.ip_type,
        '--phase', 'fsm',
        '--fsm_strategy', strategy,
        '--fsm_tree_depth', str(base_args.fsm_tree_depth),
        '--blut_path', base_args.blut_path,
        '--output_dir', os.path.join(base_args.output_dir, strategy),
    ]
    if base_args.spec_json:
        argv += ['--spec_json', base_args.spec_json]
    if base_args.signal_map_json:
        argv += ['--signal_map_json', base_args.signal_map_json]

    parsed = framework_main.build_parser().parse_args(argv)
    kg = framework_main._build_kg(parsed)
    os.makedirs(parsed.output_dir, exist_ok=True)
    fsm = framework_main.run_fsm_phase(parsed, kg, [])

    state_names = [d['name'] for d in fsm['state_defs'].values()]
    return {
        'strategy': strategy,
        'n_states': len(fsm['state_defs']),
        'state_names': state_names,
        'n_transitions': len(fsm['transitions']),
        'validation': _report_to_dict(fsm['validation']),
        'output_dir': parsed.output_dir,
    }


def to_markdown(results: list, blut_path: str) -> str:
    L = ['# FSM Strategy Comparison', '',
         f'BLUT source: `{blut_path}`', '']
    L.append('| strategy | n_states | state_names | n_transitions | '
             'reachability | completeness | determinism | speckg_coverage | '
             'missing_states | warnings | errors |')
    L.append('|---|---|---|---|---|---|---|---|---|---|---|')
    for r in results:
        v = r['validation']
        L.append(
            f"| {r['strategy']} | {r['n_states']} | "
            f"{', '.join(r['state_names'])} | {r['n_transitions']} | "
            f"{v['reachability']} | {v['completeness']} | {v['determinism']} | "
            f"{v['speckg_coverage']:.1%} | {', '.join(v['missing_states']) or '-'} | "
            f"{len(v['warnings'])} | {len(v['errors'])} |"
        )
    L.append('')
    return '\n'.join(L) + '\n'


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--blut_path', default=os.path.join(
        ROOT, 'blut_files', 'regression_multi_corner_ldo.bin'))
    ap.add_argument('--spec_json', default=os.path.join(CFG, 'LDO_1V2.json'))
    ap.add_argument('--signal_map_json',
                    default=os.path.join(CFG, 'signal_map_ldo.json'))
    ap.add_argument('--ip_type', default='LDO')
    ap.add_argument('--fsm_tree_depth', type=int, default=4)
    ap.add_argument('--output_dir',
                    default=os.path.join(ROOT, 'output', 'fsm_compare'))
    args = ap.parse_args()

    import main as framework_main

    os.makedirs(args.output_dir, exist_ok=True)
    results = []
    for strategy in STRATEGIES:
        print(f"\n{'='*60}\n  Strategy: {strategy}\n{'='*60}")
        results.append(run_strategy(framework_main, strategy, args))

    md_path = os.path.join(args.output_dir, 'fsm_strategy_compare.md')
    json_path = os.path.join(args.output_dir, 'fsm_strategy_compare.json')
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(to_markdown(results, args.blut_path))
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump({'blut_path': args.blut_path,
                   'strategies': {r['strategy']: r for r in results}},
                  f, indent=2)

    print(f"\n{'='*60}\n  COMPARISON")
    print(f"{'='*60}")
    for r in results:
        v = r['validation']
        print(f"  {r['strategy']:8s} states={r['n_states']:2d} "
              f"transitions={r['n_transitions']:2d} "
              f"reach={v['reachability']!s:5s} complete={v['completeness']!s:5s} "
              f"determ={v['determinism']!s:5s} coverage={v['speckg_coverage']:.0%}")
    print(f"\n  report: {md_path} (+ .json)")
    return 0


if __name__ == '__main__':
    sys.exit(main())
