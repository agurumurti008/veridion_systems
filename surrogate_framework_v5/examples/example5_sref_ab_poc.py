#!/usr/bin/env python3
"""
examples/example5_sref_ab_poc.py — SREF_LDO1V2_LP A+B proof of concept.

End-to-end (Section 8 of the A+B build):
  1. Build (or load, via --blut) a 3-corner SREF-like BLUT v8: per corner
     {line step, load step 10->200 mA at 1 A/us, EN/HP-LP/UVLO exercise},
     written with corner_id and template-generated ground-truth params.
  2. FSM auto-derivation across ALL runs (SignalCapture boundary-mask ->
     logic detector -> pattern-diff transition learner -> validator).
  3. Baseline + state-delta fit per corner (staged fitter, Section 4-5).
  4. Store fits via the BLUT v8 param store; build all three ParamProviders
     and print the holdout comparison table (Section 6).
  5. ABModel reference simulation vs ground-truth waveforms per corner.
  6. Verilog-A emission (+ $table_model .tbl files) into output/.
  7. POC scorecard against the bars.

Run:  uv run examples/example5_sref_ab_poc.py            (from
      surrogate_framework_v5/, after `uv pip install -r requirements.txt`)
Fast: uv run examples/example5_sref_ab_poc.py --fast
"""
import argparse
import os
import sys
import tempfile

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
from core.fsm.fsm_codegen import FSMValidator
from core.fitting import (SingleCornerFitter, StateDeltaFitter,
                          extract_state_records, transient_features)
from core.pvt import (LutParamProvider, BlutStoreParamProvider,
                      NNParamProvider, save_param_store, evaluate_providers,
                      parse_corner)
from core.ab_integration import build_ab_model, emit, emit_pvt_tables
from digitwin import blut_format as bf
from digitwin.spec_signal_map import SignalMap, SignalMapEntry

HIER = 'SREF_SYN_TB'
SPEC = os.path.join(os.path.dirname(__file__), '..', 'configs',
                    'sref_ldo1v2_lp_spec.json')
OUTDIR = os.path.join(os.path.dirname(__file__), '..', 'output')

CORNERS = ['TT_1p8V_27C', 'SS_1p5V_125C', 'FF_2p0V_N40C']
HOLDOUT = 'TT_1p8V_85C'

GT_SCALES = {  # per-corner ground-truth deviations from template defaults
    # (SS chosen so the true device still meets the dropout/PSRR bars —
    # the scorecard measures the fitted model, not an impossible corner)
    'TT_1p8V_27C':  dict(Kp=1.00, dVth=0.00,  I_q=1.00, Gm=1.00, Resr=1.00),
    'SS_1p5V_125C': dict(Kp=0.88, dVth=0.03,  I_q=1.40, Gm=0.90, Resr=1.10),
    'FF_2p0V_N40C': dict(Kp=1.25, dVth=-0.04, I_q=0.75, Gm=1.12, Resr=0.90),
    'TT_1p8V_85C':  dict(Kp=0.96, dVth=0.012, I_q=1.16, Gm=0.96, Resr=1.04),
}


def gt_params(tpl, corner):
    s = GT_SCALES[corner]
    p = tpl.default_params()
    p['Kp'] *= s['Kp']
    p['Vth_p'] += s['dVth']
    p['I_q'] *= s['I_q']
    p['Gm_ea'] *= s['Gm']
    p['R_esr'] *= s['Resr']
    return p


def stimulus_runs(n_pts):
    """Three stimulus runs (t, pin waveforms, iload). Times in seconds."""
    runs = {}
    # 1) line step: V_SUPPLY 5.0 -> 4.5 at 20us
    t = np.linspace(0, 60e-6, n_pts)
    runs['line_step'] = {
        't': t, 'vsup': np.where(t < 20e-6, 5.0, 4.5),
        'en': np.full(len(t), 5.0), 'hp': np.zeros(len(t)),
        'iload': np.full(len(t), 0.05)}
    # 2) load step 10 -> 200 mA at 1 A/us (190 ns ramp) at 20us
    t = np.linspace(0, 60e-6, n_pts)
    ramp = np.clip((t - 20e-6) / 190e-9, 0.0, 1.0)
    runs['load_step'] = {
        't': t, 'vsup': np.full(len(t), 5.0),
        'en': np.full(len(t), 5.0), 'hp': np.zeros(len(t)),
        'iload': 0.01 + 0.19 * ramp}
    # 3) EN / HP-LP / UVLO exercise
    t = np.linspace(0, 100e-6, int(n_pts * 5 // 3))
    en = np.where(t > 5e-6, 5.0, 0.0)
    hp = np.where((t > 35e-6) & (t < 55e-6), 5.0, 0.0)
    vsup = np.where((t > 70e-6) & (t < 82e-6), 3.0, 5.0)  # below UVLO fall
    runs['mode_exercise'] = {
        't': t, 'vsup': vsup, 'en': en, 'hp': hp,
        'iload': np.full(len(t), 0.02)}
    return runs


def build_synthetic_blut(path, tpl, n_pts):
    """Simulate ground truth per corner and write a v8 BLUT: run_id x
    corner_id matrix, SREF-style hierarchical names, ready bit derived
    from regulation (vout > 1.1)."""
    refs = {}
    with open(path, 'wb') as f:
        bf.write_file_header(f, n_runs=0)
        n_runs = 0
        for corner in CORNERS:
            p_gt = gt_params(tpl, corner)
            for rname, stim in stimulus_runs(n_pts).items():
                t = stim['t']
                w = tpl.simulate(p_gt, t, {'vin': stim['vsup'],
                                           'iload': stim['iload'],
                                           'en': (stim['en'] > 2.5),
                                           'hp': (stim['hp'] > 2.5)})
                ready = np.where(w['vout'] > 1.1, 5.0, 0.0)
                refs[(corner, rname)] = {'t': t, 'stim': stim, 'gt': w}
                run_off = f.tell()
                bf.write_run_header(f, n_runs, rname,
                                    f'corner={corner},stim={rname}', t,
                                    corner_id=corner)
                idxs = np.arange(len(t), dtype=np.int64)
                sigs = {
                    f'{HIER}.V_SUPPLY': stim['vsup'],
                    f'{HIER}.EN_LDO': stim['en'],
                    f'{HIER}.HIGH_POWER_MODE': stim['hp'],
                    f'{HIER}.EN_UVLO_1V2': ready,
                    f'{HIER}.VDD_1V2': w['vout'],
                    f'{HIER}.VFB': w['vout'] * 0.75,
                    f'{HIER}.VDD_1V2$flow': np.asarray(stim['iload']),
                    f'{HIER}.V_SUPPLY$flow': w['i_vin'],
                }
                for name, vals in sigs.items():
                    arr = np.full(len(t), float(vals)) if np.isscalar(vals) \
                        else np.asarray(vals, dtype=float)
                    bf.write_signal_block(f, name, idxs, arr, bf.ENC_FLOAT64,
                                          0.0, 1.0, compress=False)
                bf.patch_run_n_signals(f, run_off, len(sigs))
                n_runs += 1
        bf.patch_file_header_counts(f, n_runs)
    return refs


def signal_map():
    return SignalMap([SignalMapEntry(n, f'{HIER}.{n}', 'voltage')
                      for n in ('V_SUPPLY', 'EN_LDO', 'HIGH_POWER_MODE',
                                'EN_UVLO_1V2', 'VDD_1V2', 'VFB')]
                     + [SignalMapEntry('IOUT', f'{HIER}.VDD_1V2', 'current'),
                        SignalMapEntry('IIN', f'{HIER}.V_SUPPLY', 'current')])


def fit_data_for_corner(tpl, corner, refs):
    """DC sweeps synthesized from ground truth (bench-style measurements;
    the BLUT carries no DC sweeps — recon Section 5) + the BLUT transient
    runs as fit records."""
    p_gt = gt_params(tpl, corner)
    dc = []
    for vin in (4.5, 5.0, 5.5):
        for il in (0.001, 0.01, 0.05, 0.1, 0.2):
            op = tpl.dc_solve(p_gt, vin, il)
            dc.append({'vin': vin, 'iload': il, 'vout': op['vout'],
                       'iq': op['iq']})
    for vin in np.arange(1.30, 1.75, 0.05):
        op = tpl.dc_solve(p_gt, float(vin), 0.2, mode={'uvlo_ok': 1})
        dc.append({'vin': float(vin), 'iload': 0.2,
                   'mode': {'uvlo_ok': 1}, 'vout': op['vout']})
    trs = []
    for rname, t_event in (('load_step', 20e-6), ('line_step', 20e-6)):
        r = refs[(corner, rname)]
        trs.append({'t': r['t'],
                    'inputs': {'vin': r['stim']['vsup'],
                               'iload': r['stim']['iload']},
                    'vout_ref': r['gt']['vout'],
                    'ivin_ref': r['gt']['i_vin'],
                    't_event': t_event})
    # AC-derived data (bench PSRR/Zout characterization of the ground
    # truth) — drives Stage LINEAR through the Vector Fitting path
    op = tpl.dc_solve(p_gt, 5.0, 0.05)
    ss = tpl.small_signal(p_gt, op)
    ac = {'freqs': ss['freqs'], 'psrr_db': ss['psrr_db'],
          'zout': ss['zout'], 'op': {'vin': 5.0, 'iload': 0.05}}
    return {'dc': dc, 'ac': ac, 'transient': trs}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--blut', default=None,
                    help='real SREF BLUT to use instead of synthetic')
    ap.add_argument('--fast', action='store_true',
                    help='reduced DE budget / point counts')
    ap.add_argument('--smoke', action='store_true',
                    help='minimum budget (test-suite smoke run)')
    args = ap.parse_args()
    if args.smoke:
        args.fast = True

    os.makedirs(OUTDIR, exist_ok=True)
    n_pts = 480 if args.smoke else (600 if args.fast else 900)
    kg = SpecKG.from_json(SPEC)
    tpl = LdoPmosTemplate()

    print('\n══ 1. SREF BLUT (synthetic v8 with corner_id) ══')
    if args.blut:
        blut_path = args.blut
        refs = None
        print(f'  using real BLUT: {blut_path}')
    else:
        blut_path = os.path.join(OUTDIR, 'sref_ab_poc_synth.blut')
        refs = build_synthetic_blut(blut_path, tpl, n_pts)
        print(f'  wrote {blut_path} ({len(CORNERS)} corners x 3 runs)')

    print('\n══ 2. FSM auto-derivation (Strategy A, unchanged pipeline) ══')
    sc = SignalCapture(spec_kg=kg)
    sc.load_from_blut(blut_path, signal_map=signal_map())
    lm, ln, _ = sc.get_logic_signal_matrix()
    om, on, _ = sc.get_output_signal_matrix()
    detector = FSMStateDetector(strategy='logic', spec_kg=kg)
    seq = detector.detect(lm, ln, sc.get_analog_features(n_windows=10),
                          output_matrix=om, output_names=on)
    detector.print_summary()
    learner = TransitionLearner(fsm_tree_depth=4)
    transitions = learner.learn(seq, lm, ln, detector.state_defs,
                                boundary_mask=sc.get_boundary_mask())
    learner.print_summary()
    report = FSMValidator(spec_kg=kg).validate(detector.state_defs,
                                               transitions, ip_type='LDO')
    print(f'  Validation: {report}')

    print('\n══ 3. Per-corner staged fits + state deltas ══')
    if refs is None:
        raise SystemExit('real-BLUT fitting requires corner-labeled DC data;'
                         ' rerun without --blut for the synthetic POC')
    fitter = SingleCornerFitter(tpl, kg,
                                de_maxiter=3 if args.smoke else
                                (4 if args.fast else 8),
                                de_popsize=5 if args.smoke else
                                (5 if args.fast else 6))
    sd_fitter = StateDeltaFitter(tpl, kg)
    fits = {}
    for corner in CORNERS:
        res = fitter.fit(fit_data_for_corner(tpl, corner, refs),
                         corner=corner)
        # state deltas from the mode exercise run of this corner
        r = refs[(corner, 'mode_exercise')]
        # state_sequence for THIS run: re-detect on the run's own bits
        sc_run = SignalCapture(spec_kg=kg)
        sc_run.load_from_blut(blut_path, run_id=f'mode_exercise@{corner}',
                              signal_map=signal_map())
        lm_r, ln_r, _ = sc_run.get_logic_signal_matrix()
        om_r, on_r, _ = sc_run.get_output_signal_matrix()
        det_r = FSMStateDetector(strategy='logic', spec_kg=kg)
        seq_r = det_r.detect(lm_r, ln_r, None,
                             output_matrix=om_r, output_names=on_r)
        recs = extract_state_records(
            r['t'], {'vin': r['stim']['vsup'], 'iload': r['stim']['iload'],
                     'en': (r['stim']['en'] > 2.5).astype(float),
                     'hp': (r['stim']['hp'] > 2.5).astype(float)},
            r['gt']['vout'], seq_r, det_r.state_defs)
        sps = sd_fitter.fit(res.params, recs, det_r.state_defs,
                            state_sequence=seq_r)
        fits[corner] = sps
        n_frozen = len(res.frozen_params)
        print(f'  {corner}: stage rms={ {k: (round(v, 5) if v == v else None) for k, v in res.per_stage_residuals.items()} } '
              f'frozen={n_frozen} deltas={ {k: len(v) for k, v in sps.deltas.items() if v} }')

    print('\n══ 4. PVT providers (BLUT v8 store / LUT / NN) + holdout table ══')
    store_path = os.path.join(OUTDIR, 'sref_ab_param_store.blut')
    save_param_store(store_path, fits)
    prov_blut = BlutStoreParamProvider(store_path)
    prov_lut = LutParamProvider()
    for c, s in fits.items():
        prov_lut.add_corner(c, s)
    prov_nn = NNParamProvider().fit(fits)
    providers = {'lut': prov_lut, 'nn': prov_nn, 'blut': prov_blut}
    table = evaluate_providers(providers, HOLDOUT, gt_params(tpl, HOLDOUT),
                               template=tpl)
    key_params = ('Kp', 'Vth_p', 'I_q', 'Gm_ea', 'R_esr')
    print(f'  holdout corner {HOLDOUT} (per-param % error; full table has '
          f'{len(table)} rows):')
    print(f'    {"param":10s} {"lut":>8s} {"nn":>8s} {"blut":>8s}')
    for row in table:
        if row['param'] in key_params:
            print(f'    {row["param"]:10s} '
                  f'{row.get("lut_pct_err", float("nan")):8.2f} '
                  f'{row.get("nn_pct_err", float("nan")):8.2f} '
                  f'{row.get("blut_pct_err", float("nan")):8.2f}')
        if row['param'].startswith('_spec_drift'):
            print(f'    {row["param"]}: '
                  + ', '.join(f'{k}={v:.3g}' for k, v in row.items()
                              if k.endswith(('_mV', '_pct'))))

    print('\n══ 5. ABModel reference simulation vs ground truth ══')
    ab = build_ab_model(tpl, detector.state_defs, transitions, prov_lut, kg,
                        state_param_set=fits['TT_1p8V_27C'])
    sim_errs = {}
    fsm_checks = {}
    for corner in CORNERS:
        errs = []
        for rname in ('line_step', 'load_step', 'mode_exercise'):
            r = refs[(corner, rname)]
            stim = {'t': r['t'],
                    'pins': {'V_SUPPLY': r['stim']['vsup'], 'AVSS': 0.0,
                             'EN_LDO': r['stim']['en'],
                             'HIGH_POWER_MODE': r['stim']['hp'],
                             'EN_UVLO_1V2': np.where(
                                 r['gt']['vout'] > 1.1, 5.0, 0.0)},
                    'iload': r['stim']['iload']}
            w = ab.simulate(stim, corner)
            mask = r['gt']['vout'] > 0.05  # compare where the GT is alive
            err = float(np.sqrt(np.mean(
                (w['vout'][mask] - r['gt']['vout'][mask]) ** 2)))
            errs.append(err)
            if rname == 'mode_exercise':
                names = w['state_names']
                trace = [names[int(s)] for s in w['state_trace']]
                t = r['t']
                def state_at(tq):
                    return trace[int(np.argmin(np.abs(t - tq)))]
                fsm_checks[corner] = {
                    'EN off -> DISABLED-class': state_at(2e-6).startswith('DISABLED'),
                    'EN on -> running': not state_at(25e-6).startswith('DISABLED'),
                    'HP window changes state': state_at(45e-6) != state_at(25e-6),
                    'UVLO/_ok dip -> DISABLED': state_at(76e-6).startswith('DISABLED'),
                    'recovers after dip': not state_at(95e-6).startswith('DISABLED'),
                }
        sim_errs[corner] = errs
        print(f'  {corner}: vout rms err per run (mV) = '
              + ', '.join(f'{e*1e3:.2f}' for e in errs)
              + f' | FSM: {fsm_checks[corner]}')

    print('\n══ 6. Verilog-A emission ══')
    va = emit(ab, corner='TT_1p8V_27C', table_dir=os.path.join(OUTDIR, 'pvt_tables'))
    va_path = os.path.join(OUTDIR, 'sref_ldo1v2_lp_ab.vams')
    with open(va_path, 'w', encoding='utf-8') as f:
        f.write(va)
    n_tbl = len(os.listdir(os.path.join(OUTDIR, 'pvt_tables')))
    print(f'  wrote {va_path} ({len(va.splitlines())} lines) '
          f'+ {n_tbl} $table_model .tbl files')

    print('\n══ 7. POC SCORECARD ══')
    rows = []
    for corner in CORNERS:
        p_fit = prov_lut.get_params_for_corner(corner)
        p_gt = gt_params(tpl, corner)
        op = tpl.dc_solve(p_fit, 5.0, 0.05)
        op_gt = tpl.dc_solve(p_gt, 5.0, 0.05)
        ss = tpl.small_signal(p_fit, op)
        ss_gt = tpl.small_signal(p_gt, op_gt)
        f = ss['freqs']
        p1k = float(ss['psrr_db'][np.argmin(np.abs(f - 1e3))])
        p1M = float(ss['psrr_db'][np.argmin(np.abs(f - 1e6))])
        p1k_ref = float(ss_gt['psrr_db'][np.argmin(np.abs(f - 1e3))])
        p1M_ref = float(ss_gt['psrr_db'][np.argmin(np.abs(f - 1e6))])
        dropout = None
        for vin in np.arange(1.25, 2.2, 0.01):
            o = tpl.dc_solve(p_fit, float(vin), 0.2, mode={'uvlo_ok': 1})
            if o['vout'] >= 0.98 * op['vout']:
                dropout = float(vin) - o['vout']
                break
        r = refs[(corner, 'load_step')]
        w_fit = tpl.simulate(p_fit, r['t'], {'vin': 5.0,
                                             'iload': r['stim']['iload']})
        ft_fit = transient_features(r['t'], w_fit['vout'], 20e-6)
        ft_ref = transient_features(r['t'], r['gt']['vout'], 20e-6)
        iq = op['iq']
        rows.append({
            'corner': corner,
            'DC in [1.176,1.224]': bool(1.176 <= op['vout'] <= 1.224),
            'DC (V)': round(op['vout'], 4),
            'dropout<=0.2 @200mA': (bool(dropout is not None
                                         and dropout <= 0.2 + 1e-3),
                                    round(dropout, 3) if dropout else None),
            'PSRR1k>=60 & |d|<=3': (bool(p1k >= 60
                                         and abs(p1k - p1k_ref) <= 3),
                                    round(p1k, 1)),
            'PSRR1M>=30 & |d|<=3': (bool(p1M >= 30
                                         and abs(p1M - p1M_ref) <= 3),
                                    round(p1M, 1)),
            'under<=0.1 & +-10%': (bool(
                ft_fit['undershoot'] <= 0.1
                and abs(ft_fit['undershoot'] - ft_ref['undershoot'])
                <= 0.1 * max(ft_ref['undershoot'], 1e-3) + 2e-3),
                round(ft_fit['undershoot'] * 1e3, 1)),
            'settle<=5us & +-10%': (bool(
                ft_fit['settling_time'] <= 5e-6
                and abs(ft_fit['settling_time'] - ft_ref['settling_time'])
                <= 0.1 * max(ft_ref['settling_time'], 1e-7) + 3e-7),
                round(ft_fit['settling_time'] * 1e6, 2)),
            'Iq<=80uA': (bool(iq <= 80e-6), round(iq * 1e6, 1)),
            'FSM transitions ok': all(fsm_checks[corner].values()),
        })
    all_pass = True
    for row in rows:
        verdicts = []
        for k, v in row.items():
            if k == 'corner':
                continue
            ok = v[0] if isinstance(v, tuple) else (v if isinstance(v, bool) else True)
            if isinstance(v, (bool, tuple)):
                all_pass &= bool(ok)
            verdicts.append(f'{k}={"PASS" if ok else "FAIL"}'
                            + (f'({v[1]})' if isinstance(v, tuple) else
                               (f'({v})' if not isinstance(v, bool) else '')))
        print(f'  {row["corner"]}:')
        for v in verdicts:
            print(f'      {v}')
    print(f'\n  POC RESULT: {"ALL BARS MET" if all_pass else "SOME BARS FAILED"}')
    return 0 if all_pass else 1


if __name__ == '__main__':
    sys.exit(main())
