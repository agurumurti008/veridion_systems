#!/usr/bin/env python3
"""
examples/example17_graybox_analog_template_fitting.py — same pipeline as
example16_node_gradient_fix_modeling.py (kept exactly as-is, for
reference — every step below through the differential/black-box
modeling and codegen is unchanged from it, reusing its imports), adding
ONE new step: item 6's gray-box question, implemented (not just
assessed).

Item 6 recap: the LDO schematic already has a known physical blueprint —
feedback resistors (Rf1/Rf2), a PID-like compensator (Gm_ea/R_ea/C_ea
integrator + Rz-Cc lead/lag zero), and a pass-FET whose effective
impedance varies with the compensator's output node (gate drive). Can
that blueprint BE the model, with component values identified from
observed I/O signals? Yes — and this repo already has the machinery:
core/templates/ldo_pmos_template.py (LdoPmosTemplate/LDO_PMOS_MANIFEST)
IS that exact blueprint, and core/fitting/single_corner_fitter.py
(SingleCornerFitter) already does staged (DC -> AC/linear ->
transient -> identifiability-gated) gray-box system identification
against it from I/O waveforms alone. Nothing in either file needed to
change — this script only adds the piece that WAS missing: a way to
resolve the one structurally-underdetermined part of that manifest.

── The identifiability gap this script closes ──────────────────────────
LDO_PMOS_MANIFEST's own docstring already states it: from vout data
alone, only the PRODUCT V_ref*(1+Rf1/Rf2) is identifiable — floating
both Rf1 and Rf2 (or Rf2 and V_ref) is structurally degenerate, so the
manifest anchors Rf2 and V_ref at fixed nominal defaults and only floats
Rf1 via nonlinear least-squares. That anchor is itself an ASSUMPTION
(the nominal Rf2/V_ref are trusted, not measured).

The request's insight — "the current flowing through the VFB pin can be
used" — breaks that degeneracy with an extra, independently measured
observable. The feedback divider is a purely resistive tap (the
template carries no capacitance at that node), so at every instant:
    i_fb  = v_out / (Rf1 + Rf2)                    [Ohm's law, ASSUMING
                                                     the EA input draws
                                                     no bias current at
                                                     that node — A1]
    v_fb  = v_out * Rf2 / (Rf1 + Rf2)
This script uses THREE tiers, each closing the gap with progressively
fewer assumptions, falling back automatically to the next when a signal
isn't resolvable (never a hard failure):

  Tier 1 (best): VFB (voltage) AND VFB_I (current) both measured.
    Rf1 = (v_out - v_fb) / i_fb ; Rf2 = v_fb / i_fb — solved PER SAMPLE,
    at every timestamp, no steady-state/closed-loop assumption needed at
    all (only A1 above). This is the "no added assumption beyond A1"
    path this script prefers whenever both signals resolve.
  Tier 2: only VFB_I (current) measured, not VFB (voltage) itself (a
    real possibility — VFB is an internal divider-tap node that a real
    test setup may not always break out, while its branch current can
    still be sensed). Then v_fb itself isn't directly known, so this
    tier ADDS the assumption that in a settled REGULATION-state sample,
    the closed loop holds v_fb ~= V_ref (the error amp's own reference)
    — v_out/(Rf1+Rf2) still gives Rf1+Rf2 for free from i_fb, but the
    SPLIT into Rf1 vs Rf2 individually now needs V_ref, taken from a
    directly measured VREF signal if resolvable, else from
    --v_ref_nominal (the manifest's own nominal default) — an EXTRA,
    clearly-flagged assumption on top of A1.
  Tier 3 (fallback, unchanged from today): neither VFB_I nor a usable
    substitute resolves. Rf2 and V_ref stay at the manifest's own
    nominal defaults (fit_stage='fixed', exactly as already shipped),
    and Rf1 floats via the existing DC-stage nonlinear least-squares —
    this is the SingleCornerFitter/LDO_PMOS_MANIFEST's stock behavior,
    completely untouched.

Whichever tier resolves, Rf1/Rf2 (and V_ref if used) are injected into a
NEW ParamManifest instance (built here, in this script — LDO_PMOS_MANIFEST
itself is never mutated) with those two names' fit_stage forced to
'fixed' at the data-derived value, via a thin LdoPmosTemplate subclass
that returns this manifest instead of the module-level one. Every other
component (Gm_ea, R_ea, C_ea, Rz, Cc, Kp, Vth_p, lambda_p, Cgd, Cgs,
C_out, R_esr, I_lim, I_q, ...) is fitted PER CORNER exactly as
SingleCornerFitter.fit() already does, unmodified — the DC/AC/transient
staging, the identifiability freeze-then-repolish gate, and the spec-
compliance table are all reused as-is.

Assumption A1 in one line, since the request asked to state additions
clearly: the feedback node's branch current is assumed to equal the full
divider current, i.e. the error amplifier's input draws negligible bias
current at that node (standard high-impedance opamp-input assumption;
the template itself has no alternate current path modeled there, so this
is also the model's own implicit assumption, not something this script
adds on top of it).

Everything from example16 (FSM, step 1.5 signal validation, corner-and-
state-labeled dataset, differential ddt/idt features + denoising eval,
per-state GPR/SMT/PINN/NODE + polynomial/differential equation fit +
codegen) is UNCHANGED below and still runs — this script is a strict
superset, inserting the gray-box step as a new Step 3.

Run:  uv run examples/example17_graybox_analog_template_fitting.py \\
          [--correlation_json output/per_corner_correlation.json] \\
          [--blut_path PATH] [--spec_json PATH] [--signal_map_json PATH] \\
          [--fsm_strategy hybrid] [--fsm_tree_depth 4] [--ip_type LDO] \\
          [--blut_input_signals VPWR,EN_LDO,VPWR_SEL,HIGH_POWER_MODE] \\
          [--blut_output_signals VDD_1V2,VPWR_I,FUN_DC_I] \\
          [--vin_signal VPWR] [--en_signal EN_LDO] [--hp_signal HIGH_POWER_MODE] \\
          [--vout_signal VDD_1V2] \\
          [--vfb_voltage_signal VFB] [--vfb_current_signal VFB_I] \\
          [--vref_signal VREF] [--v_ref_nominal 0.9] \\
          [--iload_current_signal ""] [--regulation_state_name ""] \\
          [--max_graybox_corners 8] [--graybox_max_dc_points 6] \\
          [--graybox_max_transient_samples 2000] \\
          [--graybox_de_maxiter 12] [--graybox_de_popsize 8] \\
          [--enable_nn_residual] [--skip_graybox] \\
          [--include_integral_features] \\
          [--smoothing_window 0] [--evaluate_denoising] \\
          [--equation_degree 2] [--include_symbolic] \\
          [--models gpr,smt,pinn,node] [--pinn_epochs 30] [--node_epochs 20] \\
          [--min_state_samples 30] [--max_state_samples 200000] \\
          [--max_gpr_smt_samples 3000] [--max_pysr_samples 5000] \\
          [--output_dir output/phase2_graybox_v1]
"""
import argparse
import dataclasses
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

try:
    import torch  # noqa: F401
except ImportError:
    import torch_shim  # noqa: F401

import numpy as np

from example12_phase2_refined_modeling import _longest_same_state_segment
from example14_differential_autoselect_modeling import (
    _differential_polynomial_equation,
    _rewrite_ddt_idt_tokens,
)
from example15_curated_inputs_full_data_modeling import (
    _subcap,
    _add_derivative_integral_features,
)

ROOT = os.path.join(os.path.dirname(__file__), '..')
CFG = os.path.join(ROOT, 'configs')

IMPLEMENTED_MODELS = ('gpr', 'smt', 'pinn', 'node')


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
    ap.add_argument('--blut_output_signals',
                    default='VDD_1V2,VPWR_I,FUN_DC_I')

    # ── Gray-box (item 6) ───────────────────────────────────────────────
    ap.add_argument('--vin_signal', default='VPWR',
                    help='Which --blut_input_signals entry is the '
                         'template\'s vin (pass-device source).')
    ap.add_argument('--en_signal', default='EN_LDO',
                    help='Which --blut_input_signals entry is the '
                         'template\'s enable.')
    ap.add_argument('--hp_signal', default='HIGH_POWER_MODE',
                    help='Which --blut_input_signals entry is the '
                         'template\'s HIGH_POWER_MODE hp hook (optional '
                         '— ignored if not present in --blut_input_signals).')
    ap.add_argument('--vout_signal', default='',
                    help='Which --blut_output_signals entry is the '
                         'regulated output (vout). Defaults to the FIRST '
                         'entry in --blut_output_signals.')
    ap.add_argument('--vfb_voltage_signal', default='VFB',
                    help='Feedback-divider-tap VOLTAGE signal (Tier 1). '
                         'Empty disables; falls back to Tier 2/3 if this '
                         'name does not resolve against the BLUT/signal_map.')
    ap.add_argument('--vfb_current_signal', default='VFB_I',
                    help='Feedback-divider-branch CURRENT signal — "the '
                         'current flowing through the VFB pin" from the '
                         'request. Empty disables (falls back to Tier 3).')
    ap.add_argument('--vref_signal', default='VREF',
                    help='Directly-measured bandgap reference (Tier 2 '
                         'only, used when --vfb_voltage_signal does not '
                         'resolve). Empty falls back to --v_ref_nominal.')
    ap.add_argument('--v_ref_nominal', type=float, default=0.9,
                    help='Assumed V_ref (Tier 2 fallback, or Tier 3) when '
                         'neither --vfb_voltage_signal nor --vref_signal '
                         'resolves — matches LDO_PMOS_MANIFEST\'s own '
                         'nominal default.')
    ap.add_argument('--iload_current_signal', default='',
                    help='Load-current signal for the gray-box DC/'
                         'transient records. Empty ASSUMES iload=0 '
                         '(unloaded/light-load corner) — stated here '
                         'since it is a real added assumption when unset.')
    ap.add_argument('--regulation_state_name', default='',
                    help='FSM state name substring marking settled closed-'
                         'loop regulation (Tier 2\'s v_fb~=V_ref window). '
                         'Empty auto-matches any state name containing '
                         '"REGULATION".')
    ap.add_argument('--max_graybox_corners', type=int, default=8,
                    help='Cap on how many good corners get a full staged '
                         'gray-box fit (each one runs a differential-'
                         'evolution + LSODA-integrated transient search — '
                         'not cheap).')
    ap.add_argument('--graybox_max_dc_points', type=int, default=6,
                    help='Quasi-DC points sampled per corner from its '
                         'regulation-state dwell (evenly spaced) for the '
                         'DC fitting stage.')
    ap.add_argument('--graybox_max_transient_samples', type=int, default=2000,
                    help='Uniform-stride decimation cap on each corner\'s '
                         'transient record before handing it to the '
                         'fitter — LSODA-integrating the full capture '
                         'every DE iteration is not needed for a good fit '
                         'and is not free either.')
    ap.add_argument('--graybox_de_maxiter', type=int, default=12)
    ap.add_argument('--graybox_de_popsize', type=int, default=8)
    ap.add_argument('--enable_nn_residual', action='store_true',
                    help='Passthrough to SingleCornerFitter — an opt-in '
                         'small residual net on top of the physical fit, '
                         'capped at <=10%% of the RHS magnitude.')
    ap.add_argument('--skip_graybox', action='store_true',
                    help='Skip Step 3 entirely and behave exactly like '
                         'example16 (useful if you only want the black-'
                         'box/differential-equation pipeline).')

    ap.add_argument('--include_integral_features', action='store_true')
    ap.add_argument('--smoothing_window', type=int, default=0)
    ap.add_argument('--evaluate_denoising', action='store_true')
    ap.add_argument('--equation_degree', type=int, default=2)
    ap.add_argument('--include_symbolic', action='store_true')
    ap.add_argument('--models', default='gpr,smt,pinn,node',
                    help='comma list from gpr, smt, pinn, node')
    ap.add_argument('--pinn_epochs', type=int, default=30)
    ap.add_argument('--node_epochs', type=int, default=20)
    ap.add_argument('--min_state_samples', type=int, default=30)
    ap.add_argument('--max_state_samples', type=int, default=200000)
    ap.add_argument('--max_gpr_smt_samples', type=int, default=3000)
    ap.add_argument('--max_pysr_samples', type=int, default=5000)
    ap.add_argument('--output_dir',
                    default=os.path.join(ROOT, 'output', 'phase2_graybox_v1'))
    return ap


def _write_json(path, obj):
    with open(path, 'w') as f:
        json.dump(obj, f, indent=2, default=str)


# ─── Gray-box helpers (new — item 6) ─────────────────────────────────────────

def _identify_rf_tier1(vout, vfb, ifb, min_ifb=1e-9):
    """Per-sample, assumption-A1-only split: Rf1=(vout-vfb)/ifb,
    Rf2=vfb/ifb. No steady-state/closed-loop assumption needed — the
    feedback tap is a purely resistive node (no capacitance on it in the
    template), so this holds at every instant, not just in regulation."""
    valid = np.abs(ifb) > min_ifb
    v, f, i = vout[valid], vfb[valid], ifb[valid]
    rf2 = f / i
    rf1 = (v - f) / i
    ok = np.isfinite(rf1) & np.isfinite(rf2) & (rf1 > 0) & (rf2 > 0)
    if not ok.any():
        return None
    return {'Rf1': float(np.median(rf1[ok])), 'Rf2': float(np.median(rf2[ok])),
            'n_samples': int(ok.sum()), 'n_total': int(len(vout)), 'tier': 1}


def _identify_rf_tier2(vout, ifb, v_ref, min_ifb=1e-9):
    """Regulation-state-only split using i_fb + an assumed/measured V_ref
    in place of directly-measured v_fb: Rf1+Rf2 = vout/ifb (assumption A1
    only), Rf2 = V_ref/ifb, Rf1 = sum - Rf2 (ADDS the v_fb~=V_ref
    closed-loop assumption — caller must restrict `vout`/`ifb` to
    regulation-state samples first)."""
    valid = np.abs(ifb) > min_ifb
    v, i = vout[valid], ifb[valid]
    r_sum = v / i
    rf2 = v_ref / i
    rf1 = r_sum - rf2
    ok = np.isfinite(rf1) & np.isfinite(rf2) & (rf1 > 0) & (rf2 > 0)
    if not ok.any():
        return None
    return {'Rf1': float(np.median(rf1[ok])), 'Rf2': float(np.median(rf2[ok])),
            'n_samples': int(ok.sum()), 'n_total': int(len(vout)), 'tier': 2}


def _anchored_ldo_template(rf1, rf2, v_ref=None):
    """A NEW ParamManifest (LDO_PMOS_MANIFEST itself is never mutated)
    with Rf1/Rf2 (and V_ref, if independently known) pinned to
    data-derived values at fit_stage='fixed' — SingleCornerFitter's
    _stage_dc/_stage_linear/_stage_transient/_identifiability all already
    skip fit_stage=='fixed' names, so this is the minimal, non-invasive
    way to "repurpose the existing pieces": no core file changes, just a
    manifest built here and a thin template subclass returning it instead
    of the module-level default."""
    from core.templates import LdoPmosTemplate, ParamManifest

    base_manifest = LdoPmosTemplate().manifest()
    new_specs = []
    for spec in base_manifest.specs:
        if spec.name == 'Rf1':
            new_specs.append(dataclasses.replace(
                spec, default=rf1, fit_stage='fixed',
                lo=min(spec.lo, rf1 * 0.5), hi=max(spec.hi, rf1 * 2.0)))
        elif spec.name == 'Rf2':
            new_specs.append(dataclasses.replace(
                spec, default=rf2, fit_stage='fixed',
                lo=min(spec.lo, rf2 * 0.5), hi=max(spec.hi, rf2 * 2.0)))
        elif spec.name == 'V_ref' and v_ref is not None:
            new_specs.append(dataclasses.replace(
                spec, default=float(np.clip(v_ref, spec.lo, spec.hi))))
        else:
            new_specs.append(spec)
    manifest = ParamManifest(new_specs)

    class _AnchoredLdoTemplate(LdoPmosTemplate):
        def manifest(self):
            return manifest

    return _AnchoredLdoTemplate()


def _build_graybox_corner_data(s, e, sc_time, X_np, Y_np_full, input_names,
                               output_names_full, seq, reg_sid, args,
                               vin_idx, en_idx, hp_idx, vout_idx, iload_idx):
    """One SingleCornerFitter-shaped {'dc': [...], 'transient': [...]}
    dict for the corner occupying global rows [s, e) — reuses the same
    run_boundaries-derived slicing already used elsewhere in this script
    for NODE trajectory reconstruction."""
    t_full = sc_time[s:e] - sc_time[s]
    n = e - s
    vin_full = X_np[s:e, vin_idx]
    en_full = X_np[s:e, en_idx]
    hp_full = X_np[s:e, hp_idx] if hp_idx is not None else np.zeros(n)
    vout_full = Y_np_full[s:e, vout_idx]
    iload_full = Y_np_full[s:e, iload_idx] if iload_idx is not None else np.zeros(n)

    seq_seg = seq[s:e]
    reg_mask = (seq_seg == reg_sid) if reg_sid is not None else np.zeros(n, dtype=bool)
    reg_idx = np.where(reg_mask)[0]

    dc_points = []
    if len(reg_idx) > 0:
        n_pick = min(args.graybox_max_dc_points, len(reg_idx))
        picks = reg_idx[np.linspace(0, len(reg_idx) - 1, n_pick).astype(int)]
        for i in picks:
            dc_points.append({'vin': float(vin_full[i]),
                              'iload': float(iload_full[i]),
                              'vout': float(vout_full[i])})

    stride = max(1, n // max(args.graybox_max_transient_samples, 1))
    sl = slice(0, n, stride)
    tr = {'t': t_full[sl],
          'inputs': {'vin': vin_full[sl], 'iload': iload_full[sl],
                    'en': en_full[sl], 'hp': hp_full[sl]},
          'vout_ref': vout_full[sl]}

    return {'dc': dc_points, 'transient': [tr]}, reg_mask


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

    import main as framework_main
    from core.fsm.signal_capture import SignalCapture
    from core.fsm.state_detector import FSMStateDetector
    from core.fsm.transition_learner import TransitionLearner
    from core.fsm.fsm_codegen import FSMValidator, FSMCodeGenerator, _vid
    from core.phases.phase2_sim_augmented import Phase2SimAugmented
    from core.models.gpr_surrogate import CircuitGPR, ModelSelector
    from core.models.smt_surrogate import CircuitSMT
    from core.tensor_utils import to_np

    kg = framework_main._build_kg(args)
    sm = framework_main._resolve_signal_map(args)
    requested_models = [m.strip().lower() for m in args.models.split(',')]
    for m in requested_models:
        if m not in IMPLEMENTED_MODELS:
            print(f"  [example17] '{m}' is not an implemented model option "
                  f"(implemented: {IMPLEMENTED_MODELS}) — ignored.")

    input_names = [s.strip() for s in args.blut_input_signals.split(',') if s.strip()]
    output_names_req = [s.strip() for s in args.blut_output_signals.split(',') if s.strip()]
    vout_signal = args.vout_signal or (output_names_req[0] if output_names_req else '')

    if not args.skip_graybox:
        if args.vin_signal not in input_names:
            print(f"FAIL: --vin_signal {args.vin_signal!r} must be one of "
                  f"--blut_input_signals {input_names}.")
            return 1
        if args.en_signal not in input_names:
            print(f"FAIL: --en_signal {args.en_signal!r} must be one of "
                  f"--blut_input_signals {input_names}.")
            return 1
        if vout_signal not in output_names_req:
            print(f"FAIL: --vout_signal {vout_signal!r} must be one of "
                  f"--blut_output_signals {output_names_req}.")
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

    run_boundaries = list(sc.run_boundaries)
    sc_time = np.array(sc.time, dtype=np.float64)
    resolvable_names = set(sc.signals.keys()) | set(sc.current_signals.keys())
    sc.signals = {}
    sc.current_signals = {}

    print(f"\n{'='*60}\n  1.5 Signal-name validation\n{'='*60}")
    requested_to_check = input_names + output_names_req
    bad_names = [n for n in requested_to_check if n not in resolvable_names]
    if bad_names:
        print(f"FAIL: the following --blut_input_signals/--blut_output_signals "
              f"name(s) did not resolve against this BLUT/signal_map: {bad_names}")
        print(f"  Known resolvable names ({len(resolvable_names)}): "
              f"{sorted(resolvable_names)}")
        return 1
    print(f"  {len(requested_to_check)} requested name(s) OK against "
          f"{len(resolvable_names)} resolvable signal(s)")

    # Gray-box auxiliary signals are OPTIONAL/auto-degrading (unlike the
    # mandatory names above) — checked here, softly, against the same
    # resolved set, never a hard failure: a wrong/absent name just moves
    # to the next tier (see module docstring).
    graybox_aux = []
    have_vfb_v = bool(args.vfb_voltage_signal) and args.vfb_voltage_signal in resolvable_names
    have_vfb_i = bool(args.vfb_current_signal) and args.vfb_current_signal in resolvable_names
    have_vref = bool(args.vref_signal) and args.vref_signal in resolvable_names
    have_iload = bool(args.iload_current_signal) and args.iload_current_signal in resolvable_names
    for flag, name in ((have_vfb_v, args.vfb_voltage_signal),
                       (have_vfb_i, args.vfb_current_signal),
                       (have_vref, args.vref_signal),
                       (have_iload, args.iload_current_signal)):
        if flag:
            graybox_aux.append(name)
    print(f"\n  Gray-box auxiliary signals: VFB(voltage)={have_vfb_v}  "
          f"VFB_I(current)={have_vfb_i}  VREF={have_vref}  "
          f"iload={have_iload}")

    print(f"\n{'='*60}\n  2. Corner-and-state-labeled Phase 2 dataset"
          f"\n{'='*60}")
    output_names_full = output_names_req + [n for n in graybox_aux
                                            if n not in output_names_req]
    phase2 = Phase2SimAugmented(kg)
    fsm_detector_for_blut = FSMStateDetector(strategy=args.fsm_strategy, spec_kg=kg)
    data = phase2.build_dataset_from_blut(
        blut_path, sm, input_names, output_names_full,
        fsm_detector=fsm_detector_for_blut, run_ids=good_qids,
    )
    if len(data['X']) != len(seq):
        print(f"FAIL: row-count mismatch between build_dataset_from_blut "
              f"({len(data['X'])} rows) and the global FSM capture "
              f"({len(seq)} samples) — cannot trust per-row state labels.")
        return 1
    data = phase2.target_encode_categorical_meta(data)
    print(f"  X: {tuple(to_np(data['X']).shape)}  features: "
          f"{data['feature_names']}")
    print(f"  Y: {tuple(to_np(data['Y']).shape)}  outputs (incl. gray-box "
          f"aux): {data['output_names']}")

    categorical_codes = data.get('categorical_codes', {})
    if categorical_codes:
        print("  categorical corner codes:")
        for key, mapping in categorical_codes.items():
            print(f"    meta_{key}: " +
                  '  '.join(f"{v}={c:.4g}" for v, c in mapping.items()))

    X_np = to_np(data['X']).astype(np.float64)
    Y_np_full = to_np(data['Y']).astype(np.float64)
    output_names_full = data['output_names']
    feature_names = [_vid(n) for n in data['feature_names']]
    # Everything from Step 4 on sees ONLY the originally-requested outputs
    # (gray-box aux columns never leak into the black-box/equation fit).
    Y_np = Y_np_full[:, :len(output_names_req)]
    output_names = output_names_req

    # ── Step 3 (NEW — item 6): gray-box analog-template fitting ────────
    graybox_report = None
    if not args.skip_graybox:
        print(f"\n{'='*60}\n  3. Gray-box analog-template fitting (item 6)"
              f"\n{'='*60}")
        vin_idx = input_names.index(args.vin_signal)
        en_idx = input_names.index(args.en_signal)
        hp_idx = input_names.index(args.hp_signal) if args.hp_signal in input_names else None
        vout_idx = output_names_full.index(vout_signal)
        iload_idx = output_names_full.index(args.iload_current_signal) if have_iload else None

        reg_sid = next(
            (sid for sid, d in detector.state_defs.items()
             if (args.regulation_state_name or 'REGULATION') in d['name']),
            None)
        if reg_sid is None:
            print("  no REGULATION-like state found — Tier 2 (i_fb + "
                  "V_ref) will have no settled window to use; falling "
                  "back further if Tier 1 is also unavailable.")

        rf_result = None
        if have_vfb_v and have_vfb_i:
            vfb_idx = output_names_full.index(args.vfb_voltage_signal)
            ifb_idx = output_names_full.index(args.vfb_current_signal)
            rf_result = _identify_rf_tier1(
                Y_np_full[:, vout_idx], Y_np_full[:, vfb_idx], Y_np_full[:, ifb_idx])
            if rf_result:
                print(f"  Tier 1 identification (VFB voltage + VFB_I current, "
                      f"assumption A1 only — no closed-loop assumption): "
                      f"Rf1={rf_result['Rf1']:.4g} Ohm  "
                      f"Rf2={rf_result['Rf2']:.4g} Ohm  "
                      f"({rf_result['n_samples']}/{rf_result['n_total']} "
                      f"samples used)")
        if rf_result is None and have_vfb_i and reg_sid is not None:
            ifb_idx = output_names_full.index(args.vfb_current_signal)
            v_ref_used = args.v_ref_nominal
            v_ref_source = f'--v_ref_nominal={args.v_ref_nominal:g} (assumed)'
            if have_vref:
                vref_idx = output_names_full.index(args.vref_signal)
                reg_mask_all = (seq == reg_sid)
                if reg_mask_all.any():
                    v_ref_used = float(np.median(Y_np_full[reg_mask_all, vref_idx]))
                    v_ref_source = (f'measured {args.vref_signal} median over '
                                    f'regulation-state samples')
            reg_mask_all = (seq == reg_sid)
            rf_result = _identify_rf_tier2(
                Y_np_full[reg_mask_all, vout_idx],
                Y_np_full[reg_mask_all, ifb_idx], v_ref_used)
            if rf_result:
                rf_result['v_ref_used'] = v_ref_used
                rf_result['v_ref_source'] = v_ref_source
                print(f"  Tier 2 identification (VFB_I current only — ADDS "
                      f"the v_fb~=V_ref closed-loop assumption, restricted "
                      f"to REGULATION-state samples, V_ref from "
                      f"{v_ref_source}): Rf1={rf_result['Rf1']:.4g} Ohm  "
                      f"Rf2={rf_result['Rf2']:.4g} Ohm  "
                      f"({rf_result['n_samples']}/{rf_result['n_total']} "
                      f"regulation samples used)")
        if rf_result is None:
            print("  Tier 3 fallback (unchanged template default): no usable "
                  "VFB_I data — Rf2/V_ref stay at LDO_PMOS_MANIFEST's "
                  "nominal defaults (ASSUMED, trusted, not measured) and "
                  "Rf1 floats via the existing nonlinear DC-stage fit.")

        if rf_result:
            template = _anchored_ldo_template(
                rf_result['Rf1'], rf_result['Rf2'],
                v_ref=rf_result.get('v_ref_used'))
        else:
            from core.templates import LdoPmosTemplate
            template = LdoPmosTemplate()

        from core.fitting import SingleCornerFitter

        bounds = run_boundaries + [len(seq)]
        corners_to_fit = good_qids[:args.max_graybox_corners]
        if len(good_qids) > args.max_graybox_corners:
            print(f"  fitting {args.max_graybox_corners}/{len(good_qids)} "
                  f"corners (--max_graybox_corners) — each runs a full "
                  f"differential-evolution + LSODA transient search")

        graybox_by_corner = {}
        for k, qid in enumerate(corners_to_fit):
            s, e = bounds[k], bounds[k + 1]
            if e - s < args.min_state_samples:
                print(f"  corner {qid}: n={e - s} too small, skipped")
                continue
            corner_data, reg_mask = _build_graybox_corner_data(
                s, e, sc_time, X_np, Y_np_full, input_names, output_names_full,
                seq, reg_sid, args, vin_idx, en_idx, hp_idx, vout_idx, iload_idx)
            fitter = SingleCornerFitter(
                template, spec_kg=kg,
                de_maxiter=args.graybox_de_maxiter,
                de_popsize=args.graybox_de_popsize,
                enable_nn_residual=args.enable_nn_residual)
            try:
                result = fitter.fit(corner_data, corner=qid)
                n_pass = sum(1 for r in result.spec_compliance
                            if r.get('evaluated') and r.get('passes'))
                n_eval = sum(1 for r in result.spec_compliance if r.get('evaluated'))
                print(f"  corner {qid}: dc_rms={result.per_stage_residuals['dc']:.3g}  "
                      f"transient_rms={result.per_stage_residuals['transient']:.3g}  "
                      f"frozen={result.frozen_params}  "
                      f"spec_compliance={n_pass}/{n_eval}")
                graybox_by_corner[qid] = {
                    'params': result.params,
                    'per_stage_residuals': result.per_stage_residuals,
                    'frozen_params': result.frozen_params,
                    'identifiability': result.identifiability,
                    'spec_compliance': result.spec_compliance,
                    'notes': result.notes,
                }
            except Exception as ex:
                print(f"  corner {qid}: gray-box fit failed — {ex}")

        graybox_report = {
            'rf_identification': rf_result,
            'assumptions': {
                'A1_feedback_node_no_bias_current': (
                    'The feedback divider branch current equals the full '
                    'v_out/(Rf1+Rf2) divider current — i.e. the error '
                    'amplifier input draws negligible bias current at that '
                    'node. Used whenever ANY tier of Rf1/Rf2 identification '
                    'ran (always the case if VFB_I resolved).'),
                'tier2_closed_loop_v_fb_eq_v_ref': (
                    'Only added when Tier 2 ran (VFB_I but no VFB voltage): '
                    'in a settled REGULATION-state sample, the closed loop '
                    'holds v_fb approximately equal to V_ref.'
                    if rf_result and rf_result.get('tier') == 2 else
                    'not used (Tier 1 ran, or no gray-box fit at all)'),
                'tier3_nominal_rf2_vref': (
                    'Rf2 and V_ref held at LDO_PMOS_MANIFEST\'s own nominal '
                    'defaults (never measured) — only the ORIGINAL, already-'
                    'shipped assumption, unchanged.'
                    if rf_result is None else 'not used (VFB_I resolved)'),
                'iload_assumed_zero': (
                    'iload assumed 0 in every gray-box DC/transient record '
                    '(no --iload_current_signal given) — the fit then '
                    'calibrates an effectively unloaded/light-load corner.'
                    if not have_iload else 'not used (--iload_current_signal given)'),
            },
            'corners': graybox_by_corner,
        }
        _write_json(os.path.join(args.output_dir, 'graybox_fit_report.json'),
                   graybox_report)
        with open(os.path.join(args.output_dir, 'graybox_fit_report.md'), 'w') as f:
            L = ['# Gray-Box Analog-Template Fitting (item 6)', '']
            if rf_result:
                L.append(f"**Rf1/Rf2 identification: Tier {rf_result['tier']}** "
                         f"— Rf1={rf_result['Rf1']:.4g} Ohm, "
                         f"Rf2={rf_result['Rf2']:.4g} Ohm "
                         f"({rf_result['n_samples']}/{rf_result['n_total']} "
                         f"samples)")
            else:
                L.append('**Rf1/Rf2 identification: Tier 3 fallback** — '
                        'manifest nominal defaults, Rf1 floats via DC-stage fit')
            L += ['', '## Assumptions actually used', '']
            for key, text in graybox_report['assumptions'].items():
                L.append(f"- **{key}**: {text}")
            L += ['', '## Per-corner fitted parameters', '',
                 '| corner | dc_rms | transient_rms | frozen | spec pass |',
                 '|---|---|---|---|---|']
            for qid, r in graybox_by_corner.items():
                n_pass = sum(1 for c in r['spec_compliance']
                            if c.get('evaluated') and c.get('passes'))
                n_eval = sum(1 for c in r['spec_compliance'] if c.get('evaluated'))
                L.append(f"| {qid} | {r['per_stage_residuals']['dc']:.3g} | "
                        f"{r['per_stage_residuals']['transient']:.3g} | "
                        f"{r['frozen_params']} | {n_pass}/{n_eval} |")
            for qid, r in graybox_by_corner.items():
                L += ['', f'### {qid} — fitted component values', '',
                     '| parameter | value |', '|---|---|']
                for name, val in sorted(r['params'].items()):
                    L.append(f"| {name} | {val:.6g} |")
            f.write('\n'.join(L) + '\n')
        print(f"  Gray-box report: "
              f"{os.path.join(args.output_dir, 'graybox_fit_report.md')} (+ .json)")

    print(f"\n{'='*60}\n  4. Differential (ddt/idt) features\n{'='*60}")
    deriv_targets = [n for n in feature_names if not n.startswith('meta_')]
    X_np, feature_names, deriv_token_to_base, integral_token_to_base = \
        _add_derivative_integral_features(
            X_np, feature_names, run_boundaries, sc_time, deriv_targets,
            include_integral=args.include_integral_features,
            smoothing_window=args.smoothing_window)
    poly_mask = np.array([n not in deriv_token_to_base and n not in integral_token_to_base
                          for n in feature_names])
    print(f"  added {len(deriv_token_to_base)} derivative feature(s)"
          + (f" + {len(integral_token_to_base)} integral feature(s)"
             if args.include_integral_features else "")
          + f"  (X now {X_np.shape[1]} columns, smoothing_window="
            f"{args.smoothing_window})")

    denoising_eval = None
    if args.evaluate_denoising:
        print(f"\n{'='*60}\n  4.5 Denoising impact evaluation\n{'='*60}")
        biggest_sid = max(detector.state_defs.keys(), key=lambda s: int((seq == s).sum()))
        mask_eval = (seq == biggest_sid)
        n_eval = int(mask_eval.sum())
        if n_eval >= max(30, args.min_state_samples):
            base_names = feature_names[:X_np.shape[1] - len(deriv_token_to_base)
                                        - len(integral_token_to_base)]
            X_base = X_np[:, :len(base_names)]
            eval_targets = [n for n in base_names if not n.startswith('meta_')]
            eval_window = args.smoothing_window if args.smoothing_window > 1 else 11
            comparisons = {}
            for label, w in (('unsmoothed', 0), (f'smoothed(w={eval_window})', eval_window)):
                Xd, names_d, dtb, itb = _add_derivative_integral_features(
                    X_base, base_names, run_boundaries, sc_time, eval_targets,
                    include_integral=False, smoothing_window=w)
                pm = np.array([n not in dtb for n in names_d])
                X_state, Y_state = Xd[mask_eval], Y_np[mask_eval]
                eq_text, r2 = _differential_polynomial_equation(
                    X_state[:, pm], [n for n, m in zip(names_d, pm) if m],
                    X_state[:, ~pm], [n for n, m in zip(names_d, pm) if not m],
                    Y_state[:, 0], degree=args.equation_degree)
                comparisons[label] = r2
                print(f"  {label}: R2={r2:.4f}")
            denoising_eval = {
                'state': detector.state_defs[biggest_sid]['name'],
                'output': output_names[0], 'n_samples': n_eval,
                'r2_by_variant': comparisons,
            }
            delta = comparisons.get(f'smoothed(w={eval_window})', 0.0) - \
                comparisons.get('unsmoothed', 0.0)
            print(f"  measured impact on this state/output: "
                  f"{'+' if delta >= 0 else ''}{delta:.4f} R2")
        else:
            print(f"  state {biggest_sid} too small (n={n_eval}) for a "
                  f"denoising comparison, skipped")

    ground_ports = [p for p in kg.ports if p.port_type == 'ground']
    gnd_ident = _vid(ground_ports[0].name) if ground_ports else '0'

    equation_parameters = {
        name: float(X_np[:, i].mean())
        for i, name in enumerate(feature_names) if name.startswith('meta_')
    }

    print(f"\n{'='*60}\n  5. Per-state model comparison + output equations"
          f"\n{'='*60}")
    print(f"  sample caps: general(equation/PINN/NODE)={args.max_state_samples}  "
          f"GPR/SMT={args.max_gpr_smt_samples}"
          + (f"  PySR={args.max_pysr_samples}" if args.include_symbolic else ""))

    rng = np.random.RandomState(42)
    state_metrics = {}
    state_n_samples = {}
    output_equations = {}
    equation_info = {}
    ddt_idt_placeholder_map = {}
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

        idx = rng.permutation(n_state)
        n_test = max(1, int(0.2 * n_state))
        if n_state - n_test < 2:
            print(f"  state {sid} ({sname}): n={n_state} too small for a "
                  f"train/test split, skipped")
            continue
        test_idx, train_idx = idx[:n_test], idx[n_test:]
        X_tr, Y_tr = X_s[train_idx], Y_s[train_idx]
        X_te, Y_te = X_s[test_idx], Y_s[test_idx]

        metrics = {}
        X_te_kernel, Y_te_kernel = _subcap(X_te, Y_te, args.max_gpr_smt_samples, rng)
        if 'gpr' in requested_models:
            Xg, Yg = _subcap(X_tr, Y_tr, args.max_gpr_smt_samples, rng)
            gpr = CircuitGPR(Xg.shape[1], Yg.shape[1])
            gpr.fit(Xg, Yg)
            metrics['GPR'] = gpr.evaluate(X_te_kernel, Y_te_kernel)
        if 'smt' in requested_models:
            Xs_, Ys_ = _subcap(X_tr, Y_tr, args.max_gpr_smt_samples, rng)
            smt_model = CircuitSMT(Xs_.shape[1], Ys_.shape[1])
            smt_model.fit(Xs_, Ys_)
            metrics['SMT'] = smt_model.evaluate(X_te_kernel, Y_te_kernel)
        if 'pinn' in requested_models:
            try:
                p2_pinn = Phase2SimAugmented(kg)
                p2_pinn.initialize_models(
                    input_dim=X_tr.shape[1], output_dim=Y_tr.shape[1],
                    n_fsm_states=1, model_names=['PINN'])
                pinn_data = {
                    'X': X_tr, 'Y': Y_tr,
                    'state_sequence': np.zeros(len(X_tr), dtype=np.int64),
                    'output_names': output_names,
                }
                p2_pinn.incremental_train(pinn_data, epochs=args.pinn_epochs)
                pinn = p2_pinn.models['PINN']
                pinn.eval()
                from core.tensor_utils import make_float_tensor, assign_col
                X_te_t = make_float_tensor(X_te.astype(np.float32))
                S_te = make_float_tensor(np.zeros((len(X_te), 1), dtype=np.float32))
                assign_col(S_te, 0, 1.0)
                out_te = pinn(X_te_t, S_te)
                pred_np = to_np(out_te['predictions']).astype(np.float64)
                metrics['PINN'] = float(np.mean((pred_np - Y_te) ** 2))
            except Exception as e:
                print(f"  state {sid} ({sname}): PINN training failed — {e}")
        if 'node' in requested_models:
            try:
                seg_start, seg_end = _longest_same_state_segment(
                    seq, run_boundaries, sid)
                if seg_start is not None and (seg_end - seg_start) >= 5:
                    t_seg = sc_time[seg_start:seg_end]
                    X_seg = X_np[seg_start:seg_end]
                    Y_seg = Y_np[seg_start:seg_end]
                    p2_node = Phase2SimAugmented(kg)
                    p2_node.initialize_models(
                        input_dim=X_seg.shape[1], output_dim=Y_seg.shape[1],
                        n_fsm_states=1, state_dim=Y_seg.shape[1],
                        model_names=['NODE'])
                    node_data = {'X': X_seg, 'Y': Y_seg,
                                't_span': t_seg, 'trajectories': Y_seg}
                    node_metrics = p2_node.incremental_train(
                        node_data, epochs=args.node_epochs)
                    metrics['NODE'] = node_metrics.get('NODE', {}).get(
                        'test_mse', float('nan'))
                else:
                    print(f"  state {sid} ({sname}): no single-corner "
                          f"contiguous stretch long enough for NODE, skipped")
            except Exception as e:
                print(f"  state {sid} ({sname}): NODE training failed — {e}")

        X_poly_tr = X_tr[:, poly_mask]
        X_lin_tr = X_tr[:, ~poly_mask]
        poly_names = [n for n, m in zip(feature_names, poly_mask) if m]
        lin_names = [n for n, m in zip(feature_names, poly_mask) if not m]

        state_eq_info = {}
        for out_idx, out_name in enumerate(output_names):
            try:
                if args.include_symbolic:
                    from core.interpretability.symbolic_regression import \
                        CircuitSymbolicExtractor
                    X_pysr, Y_pysr = _subcap(X_tr, Y_tr, args.max_pysr_samples, rng)
                    extractor = CircuitSymbolicExtractor(feature_names, output_names)
                    res = extractor.extract(X_pysr, Y_pysr, output_idx=out_idx)
                    eq_text, r2 = res.get('equation'), res.get('r2')
                    source = 'pysr_requested'
                else:
                    eq_text, r2 = _differential_polynomial_equation(
                        X_poly_tr, poly_names, X_lin_tr, lin_names,
                        Y_tr[:, out_idx], degree=args.equation_degree)
                    source = f'polynomial_deg{args.equation_degree}+differential'
                eq_final = _rewrite_ddt_idt_tokens(
                    eq_text, deriv_token_to_base, integral_token_to_base,
                    gnd_ident, ddt_idt_placeholder_map)
                state_eq_info[out_name] = {
                    'equation': eq_final, 'raw_equation': eq_text, 'r2': r2,
                    'source': source,
                    'has_differential_term': eq_final != eq_text,
                }
            except Exception as e:
                state_eq_info[out_name] = {'equation': None, 'r2': None,
                                           'source': 'failed', 'error': str(e)}

        equation_info[sid] = state_eq_info
        output_equations[sid] = {name: info['equation']
                                 for name, info in state_eq_info.items()
                                 if info['equation']}

        state_metrics[sid] = metrics
        state_n_samples[sid] = n_state
        metric_str = '  '.join(f'{k}={v:.4g}' for k, v in metrics.items())
        eq_r2_str = '  '.join(f"{n}_R2={i['r2']:.3f}" for n, i in state_eq_info.items()
                              if i['r2'] is not None)
        print(f"  state {sid} ({sname}): n={n_state}  {metric_str}  {eq_r2_str}")

    print()
    best_by_state = ModelSelector.select_best_per_state(state_metrics) if state_metrics else {}

    print(f"\n{'='*60}\n  6. Final control-logic-skeleton codegen"
          f"\n{'='*60}")
    codegen = FSMCodeGenerator(spec_kg=kg, ip_type=args.ip_type)
    va_code = codegen.generate_veriloga(
        detector.state_defs, transitions, kg.ports,
        output_equations=output_equations,
        equation_parameters=equation_parameters,
    )
    for placeholder, real in ddt_idt_placeholder_map.items():
        va_code = va_code.replace(placeholder, real)
    sv_code = codegen.generate_systemverilog(detector.state_defs, transitions)
    ip = args.ip_type.lower()
    va_path = os.path.join(args.output_dir, f'{ip}_fsm_skeleton.vams')
    sv_path = os.path.join(args.output_dir, f'{ip}_fsm_skeleton.sv')
    with open(va_path, 'w') as f:
        f.write(va_code)
    with open(sv_path, 'w') as f:
        f.write(sv_code)

    n_states_with_eq = len(output_equations)
    embedded_ok = n_states_with_eq > 0 and 'Fitted per-state output equations' in va_code
    has_ddt = ('ddt(' in va_code)
    has_idt = ('idt(' in va_code)
    eq_source_label = ('PySR (--include_symbolic)' if args.include_symbolic
                       else f'degree-{args.equation_degree} polynomial + differential')
    print(f"\n  Analog skeleton output-driving equations: "
          f"{'EMBEDDED' if embedded_ok else 'NOT EMBEDDED'}")
    print(f"    states: {n_states_with_eq}   outputs: {output_names}")
    print(f"    equation source: {eq_source_label}")
    print(f"    ddt() present: {has_ddt}   idt() present: {has_idt}")
    if graybox_report:
        rf = graybox_report['rf_identification']
        print(f"    gray-box Rf1/Rf2: "
              f"{'Tier ' + str(rf['tier']) if rf else 'Tier 3 fallback'}  "
              f"corners fitted: {len(graybox_report['corners'])}")

    # ── Reports ──────────────────────────────────────────────────────────
    model_comparison = {
        'blut_path': blut_path,
        'good_corners': len(good_qids),
        'total_corners': len(corners),
        'meta_key_kind': data.get('meta_key_kind', {}),
        'categorical_codes': categorical_codes,
        'feature_names': feature_names,
        'output_names': output_names,
        'equation_source': eq_source_label,
        'equation_parameters': equation_parameters,
        'sample_caps': {
            'max_state_samples': args.max_state_samples,
            'max_gpr_smt_samples': args.max_gpr_smt_samples,
            'max_pysr_samples': args.max_pysr_samples if args.include_symbolic else None,
        },
        'denoising_evaluation': denoising_eval,
        'graybox_fit': ('see graybox_fit_report.json' if graybox_report else None),
        'states': {
            str(sid): {
                'name': detector.state_defs[sid]['name'],
                'n_samples': state_n_samples[sid],
                'metrics': state_metrics[sid],
                'best_black_box_model': best_by_state.get(sid),
                'equations': equation_info.get(sid, {}),
            } for sid in state_metrics
        },
        'fsm_validation': {
            'reachability': fsm_report.reachability,
            'completeness': fsm_report.completeness,
            'determinism': fsm_report.determinism,
            'speckg_coverage': fsm_report.speckg_coverage,
        },
        'analog_skeleton_equations_embedded': embedded_ok,
        'has_ddt': has_ddt, 'has_idt': has_idt,
    }
    _write_json(os.path.join(args.output_dir, 'model_comparison.json'), model_comparison)

    with open(os.path.join(args.output_dir, 'model_comparison.md'), 'w') as f:
        model_cols = sorted({m for v in state_metrics.values() for m in v})
        L = ['# Phase 2 Model Comparison — Gray-Box Analog-Template Fitting', '',
             f'BLUT: `{blut_path}`  |  good corners: {len(good_qids)}/{len(corners)}  '
             f'|  equation source: `{eq_source_label}`',
             '']
        if graybox_report:
            L += ['## Gray-box fit — see `graybox_fit_report.md`', '']
        if categorical_codes:
            L += ['## Categorical corner codes', '']
            for key, mapping in categorical_codes.items():
                L.append(f"- `meta_{key}`: " +
                        ', '.join(f"{v}={c:.4g}" for v, c in mapping.items()))
            L.append('')
        L += ['## Sample caps used', '',
              f'- general (equation fit + PINN + NODE): {args.max_state_samples}',
              f'- GPR/SMT: {args.max_gpr_smt_samples}']
        if args.include_symbolic:
            L.append(f'- PySR: {args.max_pysr_samples}')
        L.append('')
        if denoising_eval:
            L += ['## Denoising impact evaluation', '',
                  f"State: {denoising_eval['state']}  Output: "
                  f"{denoising_eval['output']}  n={denoising_eval['n_samples']}",
                  '']
            for label, r2 in denoising_eval['r2_by_variant'].items():
                L.append(f"- {label}: R2={r2:.4f}")
            L.append('')
        L += ['| state | n_samples | ' + ' | '.join(model_cols) +
             ' | best black-box |', '|---|---|' + '---|' * len(model_cols) + '---|']
        for sid, metrics in state_metrics.items():
            sname = detector.state_defs[sid]['name']
            row = f"| {sname} | {state_n_samples[sid]} | " + \
                ' | '.join(f"{metrics.get(m, float('nan')):.4g}" for m in model_cols) + \
                f" | {best_by_state.get(sid)} |"
            L.append(row)
        L += ['', '## Fitted output equations (embedded in the .vams)', '',
              '| state | output | R2 | has ddt/idt | equation |',
              '|---|---|---|---|---|']
        for sid, eqs in equation_info.items():
            sname = detector.state_defs[sid]['name']
            for out_name, info in eqs.items():
                r2_str = f"{info['r2']:.3f}" if info.get('r2') is not None else 'n/a'
                has_diff = info.get('has_differential_term', False)
                eq_str = (info.get('equation') or 'FAILED')[:200]
                L.append(f"| {sname} | {out_name} | {r2_str} | {has_diff} | `{eq_str}` |")
        f.write('\n'.join(L) + '\n')

    manifest_path = os.path.join(args.output_dir, 'manifest.md')
    with open(manifest_path, 'w') as f:
        L = ['# example17 Run Manifest — Pipeline Structure', '',
             '```',
             '1. Load per_corner_correlation.json -> filter good corners',
             '2. Global FSM (SignalCapture + FSMStateDetector + '
             'TransitionLearner + FSMValidator) -> state_defs, transitions',
             '3. Validate requested signal names against the actually-'
             'resolved signal set (fast-fail on a typo); gray-box aux '
             'signals (VFB/VFB_I/VREF/iload) checked softly',
             '4. Phase2SimAugmented.build_dataset_from_blut(run_ids=good_qids) '
             '-> corner-and-state-labeled X, Y (+ gray-box aux columns), '
             'feature_names + target_encode_categorical_meta',
             '5. NEW (item 6): per-corner gray-box fit of LdoPmosTemplate '
             'via SingleCornerFitter, with Rf1/Rf2 identified from VFB/'
             'VFB_I (falls back tier-by-tier — see module docstring)',
             '6. Derivative (+ optional integral) features per input signal, '
             'per-run/run-boundary-safe'
             + (f', Savitzky-Golay smoothed (window={args.smoothing_window})'
                if args.smoothing_window > 1 else ''),
             '7. Per state: ' + '/'.join(m.upper() for m in requested_models if
                                        m in IMPLEMENTED_MODELS) +
             ' (informational; GPR/SMT/PySR sub-capped) + '
             + eq_source_label + ' equation, ddt()/idt() token rewrite',
             '8. FSMCodeGenerator.generate_veriloga(output_equations=...) '
             '-> final .vams/.sv',
             '```', '',
             f'BLUT: `{blut_path}`',
             f'Correlation source: `{args.correlation_json}`',
             f'Good corners: {len(good_qids)}/{len(corners)}',
             f'FSM strategy: `{args.fsm_strategy}`',
             f'States: {[d["name"] for d in detector.state_defs.values()]}',
             f'Transitions: {len(transitions)}',
             f'Models requested: {requested_models}',
             f'Equation source: {eq_source_label}',
             '']
        if graybox_report:
            rf = graybox_report['rf_identification']
            L += ['## Gray-box fit (item 6 — new this pass)', '',
                 f"Rf1/Rf2 identification tier: {rf['tier'] if rf else '3 (fallback)'}",
                 f"Corners fitted: {len(graybox_report['corners'])}",
                 f"Full report: `{os.path.join(args.output_dir, 'graybox_fit_report.md')}` (+ .json)",
                 '']
        if categorical_codes:
            L += ['## Categorical corner codes (set meta_<key> to this '
                 'value per simulated process)', '']
            for key, mapping in categorical_codes.items():
                L.append(f"- `meta_{key}`: " +
                        ', '.join(f"{v}={c:.4g}" for v, c in mapping.items()))
        L += ['',
             f'**Analog skeleton output-driving equations: '
             f'{"EMBEDDED" if embedded_ok else "NOT EMBEDDED"}**',
             f'  states with equations: {n_states_with_eq}',
             f'  outputs: {output_names}',
             f'  ddt() present: {has_ddt}   idt() present: {has_idt}',
             '',
             '## Output files', '',
             f'- `{va_path}` — final Verilog-A (FSM + self-checks + '
             f'differential output equations)',
             f'- `{sv_path}` — final SystemVerilog control skeleton',
             f'- `{os.path.join(args.output_dir, "model_comparison.md")}` (+ .json)']
        if graybox_report:
            L.append(f'- `{os.path.join(args.output_dir, "graybox_fit_report.md")}` (+ .json)')
        L.append('')
        f.write('\n'.join(L))

    print(f"\n{'='*60}\n  OUTPUT FILES")
    print(f"{'='*60}")
    print(f"  Final Verilog-A       {va_path}")
    print(f"  Final SystemVerilog   {sv_path}")
    print(f"  Model comparison      {os.path.join(args.output_dir, 'model_comparison.md')} (+ .json)")
    if graybox_report:
        print(f"  Gray-box fit          {os.path.join(args.output_dir, 'graybox_fit_report.md')} (+ .json)")
    print(f"  Manifest / structure  {manifest_path}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
