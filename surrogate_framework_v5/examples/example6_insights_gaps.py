#!/usr/bin/env python3
"""
examples/example6_insights_gaps.py — Capability A + B demonstration on
SREF_LDO1V2_LP.

Builds a synthetic v8 BLUT (real SREF hierarchy names, $flow currents at the
X_DUT boundary) exercising:
  - supply mux toggle WITH current redistribution (3.4 pass) + a constructed
    no-shift bug run (3.4 untested-mux, high)
  - SREF_ADD_LDO1V2_LOAD_MPOS dummy-load assertion (3.8 auto-detected)
  - a load step to capacity (3.3/3.7 shortfall)
  - FAULT/SCAN/DROPOUT never exercised + a short-dwell REGULATION capture,
    so the gap report has real gaps.
Runs the real FSM auto-derivation, then the insights phase, and prints the
findings table, the coverage scorecard, the gap-report path, and the
Option-1 run list exactly as a customer would receive it.

Run:  uv run examples/example6_insights_gaps.py            [--blut PATH]
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

from core.spec_kg.knowledge_graph import SpecKG
from core.templates import LdoPmosTemplate
from core.fsm.signal_capture import SignalCapture
from core.fsm.state_detector import FSMStateDetector
from core.fsm.transition_learner import TransitionLearner
from core.ab_integration import run_insights_phase, emit, build_ab_model
from core.fitting.state_delta_fitter import StateParamSet
from core.pvt import LutParamProvider
from digitwin import blut_format as bf
from digitwin.spec_signal_map import SignalMap
from digitwin.blut_reader_ext import load_all_runs
from types import SimpleNamespace

HIER = 'SREF_LDO1V2_LP_TB'
CFG = os.path.join(os.path.dirname(__file__), '..', 'configs')
OUT = os.path.join(os.path.dirname(__file__), '..', 'output')

# voltage pins written (TB level) and current probes (X_DUT.<pin>_$flow)
V_PINS = ['V_SUPPLY', 'VDD_1V2', 'EN_LDO', 'EN_UVLO_1V2', 'HIGH_POWER_MODE',
          'VPWR', 'VPWR_SEL', 'SREF_ADD_LDO1V2_LOAD_MPOS']
I_PINS = ['V_SUPPLY', 'VDD_1V2', 'VPWR']


def _run_signals(kind):
    """Return (t, {volt_pin: trace}, {cur_pin: trace}) for a demo scenario."""
    n = 1400
    t = np.linspace(0, 140e-6, n)
    rng = np.random.RandomState(len(kind))
    V = {p: np.zeros(n) for p in V_PINS}
    I = {p: 1e-6 * rng.randn(n) for p in I_PINS}
    V['V_SUPPLY'][:] = 5.0
    V['VPWR'][:] = 5.0
    # baseline enable + ready
    en = t > 8e-6
    ready = t > 18e-6
    V['EN_LDO'][:] = np.where(en, 5.0, 0.0)
    V['EN_UVLO_1V2'][:] = np.where(ready, 5.0, 0.0)
    V['VDD_1V2'][:] = np.where(ready, 1.2, np.where(en, 0.6, 0.0))
    I['V_SUPPLY'][:] = np.where(en, 5e-5, 1e-6) + 3e-7 * rng.randn(n)
    I['VDD_1V2'][:] = np.where(ready, 5e-5, 0.0) + 3e-7 * rng.randn(n)

    if kind == 'mux_good':
        sel = t > 70e-6
        V['VPWR_SEL'][:] = np.where(sel, 5.0, 0.0)
        I['V_SUPPLY'][t > 70e-6] -= 4e-5      # current moves V_SUPPLY -> VPWR
        I['VPWR'][t > 70e-6] += 4e-5
    elif kind == 'mux_bug':
        sel = t > 70e-6
        V['VPWR_SEL'][:] = np.where(sel, 5.0, 0.0)
        # BUG: SEL toggles but NO current redistributes (mux stuck / untested)
    elif kind == 'dummy_load':
        add = (t > 95e-6) & (t < 120e-6)
        V['SREF_ADD_LDO1V2_LOAD_MPOS'][:] = np.where(add, 5.0, 0.0)
        I['VDD_1V2'][add] += 3e-5             # +30 uA internal load
    elif kind == 'load_capacity':
        # load ramps output current toward a high demand; vout droops out of
        # regulation past capacity (only ~90 uA sustained here << 200 mA spec)
        ramp = np.clip((t - 60e-6) / 40e-6, 0, 1)
        I['VDD_1V2'][:] = np.where(ready, 5e-5 + 4e-5 * ramp, 0.0)
        V['VDD_1V2'][:] = np.where(ready, 1.2 - 0.1 * ramp, V['VDD_1V2'])
    elif kind == 'short_reg':
        # REGULATION entered only briefly at the very end (dwell insufficient)
        V['EN_UVLO_1V2'][:] = np.where(t > 132e-6, 5.0, 0.0)
        V['VDD_1V2'][:] = np.where(t > 132e-6, 1.2, np.where(en, 0.6, 0.0))
        I['VDD_1V2'][:] = np.where(t > 132e-6, 5e-5, 0.0)
    return t, V, I


def build_blut(path):
    runs = [('mux_good', 'TT_1p8V_27C'), ('mux_bug', 'FF_2p0V_N40C'),
            ('dummy_load', 'TT_1p8V_27C'), ('load_capacity', 'TT_1p8V_27C'),
            ('short_reg', 'SS_1p5V_125C')]
    with open(path, 'wb') as f:
        bf.write_file_header(f, n_runs=0)
        for k, (kind, corner) in enumerate(runs):
            t, V, I = _run_signals(kind)
            off = f.tell()
            bf.write_run_header(f, k, kind, f'corner={corner},demo={kind}', t,
                                corner_id=corner)
            idxs = np.arange(len(t), dtype=np.int64)
            n_sig = 0
            for p in V_PINS:
                bf.write_signal_block(f, f'{HIER}.{p}', idxs, V[p],
                                      bf.ENC_FLOAT64, 0.0, 1.0, compress=False)
                n_sig += 1
            for p in I_PINS:
                bf.write_signal_block(f, f'{HIER}.X_DUT.{p}_$flow', idxs, I[p],
                                      bf.ENC_FLOAT64, 0.0, 1.0, compress=False)
                n_sig += 1
            bf.patch_run_n_signals(f, off, n_sig)
        bf.patch_file_header_counts(f, len(runs))
    return runs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--blut', default=None, help='real SREF BLUT override')
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)

    kg = SpecKG.from_json(os.path.join(CFG, 'LDO_1V2.json'))
    sm = SignalMap.from_spec_json(os.path.join(CFG, 'signal_map_ldo.json'))
    tpl = LdoPmosTemplate()

    print('\n== 1. SREF BLUT (synthetic v8 with $flow currents) ==')
    blut_path = args.blut or os.path.join(OUT, 'sref_insights_demo.blut')
    if not args.blut:
        runs_meta = build_blut(blut_path)
        print(f'   wrote {blut_path} ({len(runs_meta)} runs)')

    print('\n== 2. FSM auto-derivation (currents never feed the detector) ==')
    sc = SignalCapture(spec_kg=kg)
    sc.load_from_blut(blut_path, signal_map=sm)
    lm, ln, _ = sc.get_logic_signal_matrix()
    om, on, _ = sc.get_output_signal_matrix()
    det = FSMStateDetector(strategy='logic', spec_kg=kg)
    seq = det.detect(lm, ln, sc.get_analog_features(n_windows=10),
                     output_matrix=om, output_names=on)
    learner = TransitionLearner(fsm_tree_depth=4)
    transitions = learner.learn(seq, lm, ln, det.state_defs,
                                boundary_mask=sc.get_boundary_mask())
    fsm = SimpleNamespace(state_defs=det.state_defs, transitions=transitions,
                          spec_kg=kg, output_signatures=det.output_signatures)
    print(f'   states: {[d["name"] for d in det.state_defs.values()]}')
    print(f'   transitions: {len(transitions)}')

    # Per-run state sequences: SLICE the single global detection at the run
    # boundaries (sc.run_boundaries) so every run's labels share the global
    # state_defs ids/names — re-detecting per run would produce inconsistent
    # ids that don't align with fsm.state_defs.
    runs = load_all_runs(blut_path, None, ['$flow'], signal_map=sm)
    bounds = list(sc.run_boundaries) + [len(seq)]
    state_sequences = {}
    for k, rid in enumerate(sc.run_ids):
        corner = sc.run_corners[k]
        state_sequences[f'{rid}@{corner}'] = seq[bounds[k]:bounds[k + 1]]

    print('\n== 3. Insights phase (Capability A) + completeness (B) ==')
    fit = SimpleNamespace(params=dict(tpl.default_params()))
    res = run_insights_phase(kg, sm, runs, fsm, state_sequences=state_sequences,
                             ip_type='LDO', template=tpl,
                             params=tpl.default_params(), fit_result=fit,
                             output_dir=OUT, corners_expected=3)

    print('\n-- FINDINGS (Capability A) --')
    print(f'   {"severity":9s} {"analyzer":24s} {"summary"}')
    for f in res.findings:
        if f.severity in ('high', 'critical') or f.category in (
                'mux-verified', 'dummy-load-detected', 'capacity-shortfall',
                'untested-mux'):
            print(f'   {f.severity:9s} {f.analyzer:24s} {f.summary[:64]}')
    print(f'   ... {len(res.findings)} findings total '
          f'({res.insight_report.counts()})')
    print(f'   dummy-load enrichment: '
          f'{[(e["pin"], round(e["added_load_A"]*1e6,1)) for e in res.load_enrichment]}')

    print('\n-- COVERAGE SCORECARD (Capability B) --')
    sc_card = res.coverage.scorecard()
    for k, v in sc_card.items():
        print(f'   {k:24s} {v}')
    print(f'   reference space: {res.reference_space.arithmetic}')

    print('\n-- GAP REPORT: Option-1 runs the customer can provide --')
    for r in res.gap_report.option1_runs[:8]:
        print(f'   {r["id"]}: {r["stimulus"]} | pins={",".join(r.get("pins",[]))}'
              f' | {r.get("corner","any")} | >={r.get("min_duration_s")}s')
    n_more = len(res.gap_report.option1_runs) - 8
    if n_more > 0:
        print(f'   ... +{n_more} more runs')
    print(f'\n   reports written: {os.path.join(OUT,"gap_report.md")} (+ .json),'
          f' {os.path.join(OUT,"insight_findings.md")} (+ .json)')

    print('\n== 4. Option-2: proceed now -> LIMITATIONS stamped in Verilog-A ==')
    sps = StateParamSet(baseline=tpl.default_params(), deltas={})
    lut = LutParamProvider()
    for c in ('TT_1p8V_27C', 'SS_1p5V_125C', 'FF_2p0V_N40C'):
        lut.add_corner(c, sps)
    ab = build_ab_model(tpl, det.state_defs, transitions, lut, kg,
                        state_param_set=sps)
    va = emit(ab, corner='TT_1p8V_27C', iq_signatures=res.iq_signatures,
              limitations=res.limitations, load_enrichment=res.load_enrichment)
    va_path = os.path.join(OUT, 'sref_ldo1v2_lp_ab_insights.vams')
    with open(va_path, 'w', encoding='utf-8') as f:
        f.write(va)
    print(f'   wrote {va_path}: {va.count("LIMITATIONS:")} LIMITATIONS lines, '
          f'{len(res.iq_signatures)} per-state Iq entries')
    print('   sample LIMITATIONS lines:')
    for line in va.splitlines():
        if line.strip().startswith('// LIMITATIONS:'):
            print(f'     {line.strip()}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
