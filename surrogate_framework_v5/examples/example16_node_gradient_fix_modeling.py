#!/usr/bin/env python3
"""
examples/example16_node_gradient_fix_modeling.py — same overall pipeline
as example12_phase2_refined_modeling.py (kept exactly as-is, for
reference — the FSM/dataset/target-encoding steps below are unchanged
from it), reusing example14/example15's already-validated differential-
feature/denoising machinery by import (same "don't re-solve a solved
problem" convention example15 already established over example14)
rather than duplicating it, so this script can focus its own new work on
the two things that were still open after example14/15:

  1. --include_symbolic produced all-zero equations. Root cause (fixed
     upstream, not worked around here): a --blut_output_signals typo
     silently NaN-filled one output column
     (core/phases/phase2_sim_augmented.py's _column_for), which poisoned
     target_encode_categorical_meta's shared meta_corner feature for
     EVERY output (that method now uses nanmean, bounding the blast
     radius to just the bad column — see that method's docstring), and
     CircuitSymbolicExtractor.extract() now raises a clear, actionable
     error on NaN input instead of silently degrading to the literal
     equation "0" (core/interpretability/symbolic_regression.py). This
     script ALSO validates every requested signal name against the
     actually-resolved signal set up front (step 1.5 below), so a typo
     like that is caught in seconds, not after a full run.
  2. Why fitted equations never contain ddt()/idt(): confirmed
     structural — build_dataset_from_blut's X is purely same-timestamp
     instantaneous values, so no fitter can ever produce a differential
     term from it. This script adds real per-run, run-boundary-safe
     derivative (and optional integral) FEATURES of each selected input
     signal (example15's _add_derivative_integral_features, which also
     supports --smoothing_window), lets the equation fitter
     (example14's _differential_polynomial_equation) put a genuine
     coefficient on them, and rewrites that term's token into an actual
     ddt()/idt() Verilog-A call (example14's _rewrite_ddt_idt_tokens)
     before embedding — a deterministic, verifiable path to a
     differential relation in the final .vams.
  3. PINN/NODE MSE not improving, GPR always winning. Two DIFFERENT root
     causes — and this pass finally closes BOTH, not just PINN's:
       - PINN: already fixed (core/models/pinn.py + core/phases/
         phase2_sim_augmented.py's _train_pinn) — this script needs no
         change to see it, it calls the same methods example12/14/15 do.
         Two real bugs: CircuitPINN.forward()/compute_loss() used to
         round-trip every intermediate value through to_np()/float()/
         torch.tensor(...), silently severing the autograd graph so
         total_loss.backward() never updated a single parameter; fixed
         by keeping every step a genuine tensor op and returning
         compute_loss()'s 'total' unwrapped. Second: _train_pinn now
         feeds z-scored (not raw, wildly-mixed-magnitude) inputs via
         CircuitPINN.set_input_scaler, stored on the model so any later
         eval call stays consistent.
       - NODE: THIS is the new fix in this pass. Previously confirmed
         (example14/15) genuinely dead training code even under real
         PyTorch: CircuitNeuralODE._euler_integrate rebuilt its state
         `x` through to_np()/make_float_tensor() on every single Euler
         step, and Phase2SimAugmented._train_node's update rule only
         ever mutated a numpy-shim-only `p._d` attribute — exactly the
         same "round-trip through numpy severs the graph" bug already
         fixed in PINN, just not yet fixed here. Now fixed the same way:
         core/models/neural_ode.py's CircuitODEFunction.forward/
         CircuitNeuralODE._euler_integrate/forward keep `x` (and the
         physics coefficients log_gm/log_ro/log_cl, and ic_net's/
         state_clf's outputs) as genuine tensor ops for the ENTIRE Euler
         rollout — real backprop-through-time — and _train_node now
         builds a real torch.optim.Adam over node.parameters() and
         calls sample_loss.backward()/optimizer.step() when a real
         (non-shim) loss tensor comes back, falling back to the
         original numpy-perturbation update only under torch_shim
         (mirrors _train_pinn's exact real-vs-shim dispatch pattern).
         Verified on a synthetic single-state settling trajectory: loss
         drops noticeably across 60 epochs under real PyTorch, where it
         was flat/unchanged before this fix regardless of epoch count.
         NODE's role in this script is UNCHANGED beyond that: still
         informational-only (never embedded in the .vams) — it was
         never producing a compact closed-form expression a Verilog-A
         simulator can evaluate, closed-form equations are still the
         degree-N polynomial+differential fit (or PySR) — this fix only
         makes NODE's reported MSE an honest number instead of a frozen
         one.
  4. max_state_samples' significance: it bounds EVERY model uniformly,
     but only GPR and SMT actually need a small bound (both are
     O(n^2)/O(n^3) kernel-matrix methods). --max_state_samples now
     defaults to 200000 (effectively "use everything" for a 50k-sample
     capture), and GPR/SMT get their own --max_gpr_smt_samples (default
     3000, drawn from the larger set) — the equation fit, PINN, and NODE
     train on the full (up to --max_state_samples) data, only GPR/SMT
     sub-sample further, and the held-out test split stays the larger
     set for every model so the comparison table stays apples-to-apples.
     --include_symbolic gets its own --max_pysr_samples (default 5000).
  5. Denoising before differentiating: --smoothing_window (Savitzky-
     Golay, applied per-run/run-boundary-safe, BEFORE computing the
     derivative/integral feature only — never the raw polynomial-term
     features) and --evaluate_denoising (a small side-by-side smoothed-
     vs-unsmoothed differential-term R2 comparison on one representative
     state/output) are both available here, same as example15.

Item 6 of the request that produced this script (an LDO-schematic-as-
component-parameter-identification feasibility question) is answered
directly in conversation, not as code — no implementation was asked for
there.

Run:  uv run examples/example16_node_gradient_fix_modeling.py \\
          [--correlation_json output/per_corner_correlation.json] \\
          [--blut_path PATH] [--spec_json PATH] [--signal_map_json PATH] \\
          [--fsm_strategy hybrid] [--fsm_tree_depth 4] [--ip_type LDO] \\
          [--blut_input_signals VPWR,EN_LDO,VPWR_SEL,HIGH_POWER_MODE] \\
          [--blut_output_signals VDD_1V2,VPWR_I,FUN_DC_I] \\
          [--include_integral_features] \\
          [--smoothing_window 0] [--evaluate_denoising] \\
          [--equation_degree 2] [--include_symbolic] \\
          [--models gpr,smt,pinn,node] [--pinn_epochs 30] [--node_epochs 20] \\
          [--min_state_samples 30] [--max_state_samples 200000] \\
          [--max_gpr_smt_samples 3000] [--max_pysr_samples 5000] \\
          [--output_dir output/phase2_node_gradient_fix_v1]
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
    ap.add_argument('--include_integral_features', action='store_true',
                    help='Also add a running-integral feature per input '
                         'signal (idt()-embeddable) — off by default: a '
                         'cumulative integral drifts with an arbitrary '
                         'start-of-window offset.')
    ap.add_argument('--smoothing_window', type=int, default=0,
                    help='Savitzky-Golay smoothing window (samples, odd; '
                         'even values are bumped up by 1) applied per-run '
                         'to a signal BEFORE computing its derivative/'
                         'integral feature — 0 disables. Never applied to '
                         'the raw polynomial-term features.')
    ap.add_argument('--evaluate_denoising', action='store_true',
                    help='Run a small, self-contained comparison of '
                         'differential-term R2 with vs without '
                         '--smoothing_window (falls back to an 11-sample '
                         'window for the "with" side if --smoothing_window '
                         'is 0) on one representative state/output.')
    ap.add_argument('--equation_degree', type=int, default=2)
    ap.add_argument('--include_symbolic', action='store_true',
                    help='Use PySR symbolic regression for the embedded '
                         'per-state output equations instead of the '
                         'default --equation_degree polynomial+'
                         'differential fit.')
    ap.add_argument('--models', default='gpr,smt,pinn,node',
                    help='comma list from gpr, smt, pinn, node')
    ap.add_argument('--pinn_epochs', type=int, default=30)
    ap.add_argument('--node_epochs', type=int, default=20)
    ap.add_argument('--min_state_samples', type=int, default=30)
    ap.add_argument('--max_state_samples', type=int, default=200000,
                    help='Per-state cap shared by the equation fit, PINN, '
                         'and NODE — default is effectively "use '
                         'everything" for a ~50k-sample capture.')
    ap.add_argument('--max_gpr_smt_samples', type=int, default=3000,
                    help='GPR/SMT-specific training+eval sub-cap, drawn '
                         'from the (already --max_state_samples-capped) '
                         'split — both are O(n^2)/O(n^3) kernel-matrix '
                         'methods and need this regardless of how much '
                         'data the cheaper methods can use.')
    ap.add_argument('--max_pysr_samples', type=int, default=5000,
                    help='PySR-specific training sub-cap (--include_symbolic '
                         'only) — its search cost also scales with row count.')
    ap.add_argument('--output_dir',
                    default=os.path.join(ROOT, 'output', 'phase2_node_gradient_fix_v1'))
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
            print(f"  [example16] '{m}' is not an implemented model option "
                  f"(implemented: {IMPLEMENTED_MODELS}) — ignored.")

    input_names = [s.strip() for s in args.blut_input_signals.split(',') if s.strip()]
    output_names_req = [s.strip() for s in args.blut_output_signals.split(',') if s.strip()]

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
        print("  (A silently-NaN-filled column previously produced an "
              "all-zero embedded equation instead of this fast, explicit "
              "failure — check for a typo against the list above.)")
        return 1
    print(f"  {len(requested_to_check)} requested name(s) OK against "
          f"{len(resolvable_names)} resolvable signal(s)")

    print(f"\n{'='*60}\n  2. Corner-and-state-labeled Phase 2 dataset"
          f"\n{'='*60}")
    phase2 = Phase2SimAugmented(kg)
    fsm_detector_for_blut = FSMStateDetector(strategy=args.fsm_strategy, spec_kg=kg)
    data = phase2.build_dataset_from_blut(
        blut_path, sm, input_names, output_names_req,
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
    print(f"  Y: {tuple(to_np(data['Y']).shape)}  outputs: {data['output_names']}")

    categorical_codes = data.get('categorical_codes', {})
    if categorical_codes:
        print("  categorical corner codes:")
        for key, mapping in categorical_codes.items():
            print(f"    meta_{key}: " +
                  '  '.join(f"{v}={c:.4g}" for v, c in mapping.items()))

    X_np = to_np(data['X']).astype(np.float64)
    Y_np = to_np(data['Y']).astype(np.float64)
    output_names = data['output_names']
    feature_names = [_vid(n) for n in data['feature_names']]

    print(f"\n{'='*60}\n  3. Differential (ddt/idt) features\n{'='*60}")
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
        print(f"\n{'='*60}\n  3.5 Denoising impact evaluation\n{'='*60}")
        biggest_sid = max(detector.state_defs.keys(), key=lambda s: int((seq == s).sum()))
        mask_eval = (seq == biggest_sid)
        n_eval = int(mask_eval.sum())
        if n_eval >= max(30, args.min_state_samples):
            # Rebuild derivative features from the PRE-derivative X (its
            # column layout matches feature_names[:len(deriv_targets)+
            # n_meta] before the ddt/idt columns were appended above), on
            # the FULL-length capture — _add_derivative_integral_features
            # indexes by global run_boundaries/sc_time, never on an
            # already state-masked slice.
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

    print(f"\n{'='*60}\n  4. Per-state model comparison + output equations"
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
                pinn.eval()  # Dropout off for a deterministic eval MSE
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
            # NODE needs real (t, trajectory) data, reconstructed from the
            # longest single-corner contiguous same-state stretch (never
            # spliced across corners/runs) — same helper example12/14/15
            # use unchanged. What's different THIS time: the training
            # loop it feeds into (Phase2SimAugmented._train_node +
            # core/models/neural_ode.py) now does real gradient descent
            # instead of a numpy perturbation — see module docstring.
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

    print(f"\n{'='*60}\n  5. Final control-logic-skeleton codegen"
          f"\n{'='*60}")
    codegen = FSMCodeGenerator(spec_kg=kg, ip_type=args.ip_type)
    va_code = codegen.generate_veriloga(
        detector.state_defs, transitions, kg.ports,
        output_equations=output_equations,
        equation_parameters=equation_parameters,
    )
    # Swap in the real ddt()/idt() call text now that generate_veriloga's
    # own port-name V()-wrapping pass has already run — see
    # _rewrite_ddt_idt_tokens's docstring for why this can't happen before
    # that pass instead.
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
        'node_training': 'real gradient descent (fixed this pass — see '
                         'module docstring point 3)',
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
        L = ['# Phase 2 Model Comparison — NODE Gradient Fix', '',
             f'BLUT: `{blut_path}`  |  good corners: {len(good_qids)}/{len(corners)}  '
             f'|  equation source: `{eq_source_label}`',
             '']
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
        L = ['# example16 Run Manifest — Pipeline Structure', '',
             '```',
             '1. Load per_corner_correlation.json -> filter good corners',
             '2. Global FSM (SignalCapture + FSMStateDetector + '
             'TransitionLearner + FSMValidator) -> state_defs, transitions',
             '3. Validate requested signal names against the actually-'
             'resolved signal set (fast-fail on a typo)',
             '4. Phase2SimAugmented.build_dataset_from_blut(run_ids=good_qids) '
             '-> corner-and-state-labeled X, Y, feature_names + '
             'target_encode_categorical_meta',
             '5. Derivative (+ optional integral) features per input signal, '
             'per-run/run-boundary-safe'
             + (f', Savitzky-Golay smoothed (window={args.smoothing_window})'
                if args.smoothing_window > 1 else ''),
             '6. Per state: ' + '/'.join(m.upper() for m in requested_models if
                                        m in IMPLEMENTED_MODELS) +
             ' (informational; GPR/SMT/PySR sub-capped, equation fit + PINN '
             '+ NODE use the full --max_state_samples-capped set) + '
             + eq_source_label + ' equation, ddt()/idt() token rewrite',
             '7. FSMCodeGenerator.generate_veriloga(output_equations=...) '
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
             '',
             '## NODE training (this script\'s new fix)', '',
             'core/models/neural_ode.py\'s CircuitODEFunction.forward and '
             'CircuitNeuralODE._euler_integrate/forward now keep the entire '
             'Euler rollout (state, physics coefficients, ic_net/state_clf '
             'outputs) as genuine tensor ops instead of round-tripping '
             'through to_np()/make_float_tensor() every step — the same '
             'class of graph-severing bug already fixed in CircuitPINN. '
             'Phase2SimAugmented._train_node now builds a real '
             'torch.optim.Adam over node.parameters() and calls '
             'backward()/step() on the real loss tensor, falling back to '
             'the original numpy-perturbation update only under '
             'torch_shim. NODE remains informational-only in the final '
             '.vams (same as every prior example in this series) — closed-'
             'form output equations still come from the polynomial+'
             'differential fit (or PySR).',
             '',
             '## Sample caps', '',
             f'- general (equation fit + PINN + NODE): {args.max_state_samples}',
             f'- GPR/SMT: {args.max_gpr_smt_samples}']
        if args.include_symbolic:
            L.append(f'- PySR: {args.max_pysr_samples}')
        if categorical_codes:
            L += ['', '## Categorical corner codes (set meta_<key> to this '
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
             f'- `{os.path.join(args.output_dir, "model_comparison.md")}` (+ .json)',
             '']
        f.write('\n'.join(L))

    print(f"\n{'='*60}\n  OUTPUT FILES")
    print(f"{'='*60}")
    print(f"  Final Verilog-A       {va_path}")
    print(f"  Final SystemVerilog   {sv_path}")
    print(f"  Model comparison      {os.path.join(args.output_dir, 'model_comparison.md')} (+ .json)")
    print(f"  Manifest / structure  {manifest_path}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
