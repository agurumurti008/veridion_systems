#!/usr/bin/env python3
"""
examples/example14_differential_autoselect_modeling.py — same overall
pipeline as example12_phase2_refined_modeling.py (kept exactly as-is,
for reference — this script is fully self-contained), addressing a data-
integrity bug plus four deeper modeling-architecture questions raised
after running example12 against real data with --include_symbolic:

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
     term from it (PySR only combines the features it's given; it can't
     invent a ddt() of something never supplied). NODE genuinely fits a
     dY/dt right-hand side internally, but its own training loop is
     confirmed dead code even under real PyTorch (Phase2SimAugmented.
     _train_node's update path only mutates a numpy-shim-only
     attribute) — fixing that is a separate, larger piece of work, out
     of scope here; NODE stays informational-only, same footing as
     example12. Instead, this script adds real per-run, run-boundary-
     safe derivative (and optional integral) FEATURES of each selected
     input signal, lets the equation fitter put a genuine coefficient on
     them, and rewrites that term's token into an actual ddt()/idt()
     Verilog-A call before embedding — a deterministic, verifiable path
     to a differential relation in the final .vams.
  3. All ports as candidate inputs, narrowed automatically. Every
     resolvable port/current signal (voltage AND "<port>_I" current,
     confirmed against this run's actually-decoded SignalCapture, not
     just SpecKG's port list) becomes a CANDIDATE input; an mRMR-style
     selector (core/models/feature_selection.py: mutual-information
     relevance + collinearity-redundancy pruning) narrows it to
     --max_auto_inputs. Counter-argument, addressed rather than ignored:
     analog circuits couple through shared rails/ground-return paths, so
     a real small coupling can sit below any statistical cutoff — a
     purely automatic drop is not safe on its own. Resolved by always
     force-including (a) every supply/ground/output-rail current signal
     (via CurrentRegistry's role taxonomy — matches the plan to include
     "all the supply and output ports in currents"), and (b) anything
     the user explicitly names via --blut_input_signals.
  4. Digital vs analog FSM structure: generate_systemverilog() already
     emits a correct, independent always_ff/always_comb FSM, and
     ab_codegen.py already has a proven connectmodule idiom for crossing
     that boundary — but per explicit scope decision, this pass makes
     only a same-file structural/annotation clarification (see
     core/fsm/fsm_codegen.py's new "Digital-domain state-transition
     logic" section comment), not a full wired multi-file split.
  5. Inline power-up/power-down behavior + control-signal sensitivity:
     each state's fitted output equation is wrapped in Verilog-A's
     built-in transition(value, td, tr, tf) filter operator — the exact
     mechanism ab_codegen.py's L2E connect module already uses to turn a
     discontinuous digital-to-analog switch into a smooth ramp — turning
     today's instantaneous case-block equation swap into a continuous
     ramp on every FSM transition. A new, informational-only
     "transition sensitivity" report separately flags which learned
     guard/control-signal transition correlates with the largest
     measured output delta.

Explicit non-goals this pass (by decision, not oversight): fixing
NODE's dead training loop; a fully wired digital-core + analog-wrapper
multi-file split.

Run:  uv run examples/example14_differential_autoselect_modeling.py \\
          [--correlation_json output/per_corner_correlation.json] \\
          [--blut_path PATH] [--spec_json PATH] [--signal_map_json PATH] \\
          [--fsm_strategy hybrid] [--fsm_tree_depth 4] [--ip_type LDO] \\
          [--blut_output_signals VDD_1V2,VPWR_I,FUN_DC_I] \\
          [--blut_input_signals ""] [--max_auto_inputs 8] \\
          [--relevance_min_score 0.0] [--redundancy_corr_threshold 0.95] \\
          [--include_integral_features] \\
          [--t_transition 1e-6] [--auto_transition_time] \\
          [--equation_degree 2] [--include_symbolic] \\
          [--models gpr,smt] [--pinn_epochs 30] [--node_epochs 20] \\
          [--min_state_samples 30] [--max_state_samples 3000] \\
          [--output_dir output/phase2_differential_autoselect_v1]
"""
import argparse
import itertools
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

try:
    import torch  # noqa: F401
except ImportError:
    import torch_shim  # noqa: F401

import numpy as np

from example12_phase2_refined_modeling import _longest_same_state_segment

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
    ap.add_argument('--blut_output_signals',
                    default='VDD_1V2,VPWR_I,FUN_DC_I')
    ap.add_argument('--blut_input_signals', default='',
                    help='Optional comma list of signal names to FORCE-'
                         'INCLUDE as model inputs (never dropped by auto-'
                         'selection). Leave empty to rely entirely on '
                         'automatic candidate selection from every '
                         'resolvable port signal.')
    ap.add_argument('--max_auto_inputs', type=int, default=8,
                    help='Cap on total selected inputs (force-included + '
                         'auto-selected) — bounds polynomial feature '
                         'blow-up and GPR/Kriging column count.')
    ap.add_argument('--relevance_min_score', type=float, default=0.0,
                    help='Minimum mutual-information relevance score for '
                         'a non-force-included candidate to be selected.')
    ap.add_argument('--redundancy_corr_threshold', type=float, default=0.95,
                    help='A candidate is skipped if |corr| with an already-'
                         'selected column exceeds this (mRMR redundancy '
                         'pruning).')
    ap.add_argument('--include_integral_features', action='store_true',
                    help='Also add a running-integral feature per selected '
                         'input (idt()-embeddable) — off by default: a '
                         'cumulative integral drifts with an arbitrary '
                         'start-of-window offset.')
    ap.add_argument('--t_transition', type=float, default=1e-6,
                    help='Rise/fall time constant (seconds) for the '
                         'transition()-wrapped output equations.')
    ap.add_argument('--auto_transition_time', action='store_true',
                    help='Estimate t_transition from the data (a fraction '
                         'of the median observed state-dwell time) instead '
                         'of using the fixed --t_transition default.')
    ap.add_argument('--equation_degree', type=int, default=2)
    ap.add_argument('--include_symbolic', action='store_true')
    ap.add_argument('--models', default='gpr,smt',
                    help='comma list from gpr, smt, pinn, node')
    ap.add_argument('--pinn_epochs', type=int, default=30)
    ap.add_argument('--node_epochs', type=int, default=20)
    ap.add_argument('--min_state_samples', type=int, default=30)
    ap.add_argument('--max_state_samples', type=int, default=3000)
    ap.add_argument('--output_dir', default=os.path.join(
        ROOT, 'output', 'phase2_differential_autoselect_v1'))
    return ap


def _write_json(path, obj):
    with open(path, 'w') as f:
        json.dump(obj, f, indent=2, default=str)


def _differential_polynomial_equation(X_poly: np.ndarray, poly_names: list,
                                      X_linear: np.ndarray, linear_names: list,
                                      y: np.ndarray, degree: int = 2):
    """Degree-N polynomial fit over X_poly (every combination-with-
    replacement of up to `degree` columns — see example12's
    _polynomial_equation for the base rationale), PLUS X_linear's columns
    appended as pure LINEAR terms only — never entered into the
    cross-product/degree expansion. X_linear carries derivative/integral
    features here: a naive product of two first-differences would stand
    in for a physically meaningless second derivative, so they're kept
    strictly additive. Returns (equation_string, r2)."""
    n_samples, n_poly = X_poly.shape
    term_specs = []
    for d in range(1, max(degree, 1) + 1):
        term_specs.extend(itertools.combinations_with_replacement(range(n_poly), d))

    design_cols, design_names = [], []
    for term in term_specs:
        col = np.ones(n_samples)
        for idx in term:
            col = col * X_poly[:, idx]
        design_cols.append(col)
        design_names.append('*'.join(poly_names[idx] for idx in term))

    for j, name in enumerate(linear_names):
        design_cols.append(X_linear[:, j])
        design_names.append(name)

    X_design = np.column_stack(design_cols) if design_cols else np.zeros((n_samples, 0))
    X_b = np.hstack([X_design, np.ones((n_samples, 1))])
    try:
        sol, _, _, _ = np.linalg.lstsq(X_b, y, rcond=None)
    except Exception:
        sol = np.zeros(X_b.shape[1])
    coeffs, intercept = sol[:-1], sol[-1]
    terms = [f"{c:.6g}*{name}" for c, name in zip(coeffs, design_names)
             if abs(c) > 1e-10]
    if abs(intercept) > 1e-10:
        terms.append(f"{intercept:.6g}")
    equation = ' + '.join(terms) if terms else '0'
    y_pred = X_b @ sol
    ss_res = float(np.sum((y - y_pred) ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    r2 = 1.0 if ss_tot < 1e-30 else 1 - ss_res / ss_tot
    return equation, r2


def _add_derivative_integral_features(X_np: np.ndarray, feature_names: list,
                                      run_boundaries: list, sc_time: np.ndarray,
                                      target_names: list, include_integral: bool = False):
    """Appends a per-run, run-boundary-safe derivative column (np.gradient
    against real time, never crossing a run seam) for each name in
    target_names, and optionally a running-integral column too. Returns
    (X_augmented, augmented_feature_names, deriv_token_to_base,
    integral_token_to_base) — the token maps are what
    _rewrite_ddt_idt_tokens uses to turn a fitted term back into a real
    ddt()/idt() Verilog-A call."""
    bounds = list(run_boundaries) + [len(sc_time)]
    n_rows = X_np.shape[0]
    name_to_col = {n: i for i, n in enumerate(feature_names)}
    deriv_cols, deriv_tokens = [], []
    integral_cols, integral_tokens = [], []
    deriv_token_to_base, integral_token_to_base = {}, {}

    integral_fn = None
    if include_integral:
        from scipy.integrate import cumulative_trapezoid
        integral_fn = cumulative_trapezoid

    for name in target_names:
        j = name_to_col[name]
        col = X_np[:, j]
        d = np.zeros(n_rows)
        acc = np.zeros(n_rows) if include_integral else None
        for k in range(len(bounds) - 1):
            s, e = bounds[k], bounds[k + 1]
            if e - s < 2:
                continue
            t_seg = sc_time[s:e]
            c_seg = col[s:e]
            d[s:e] = np.gradient(c_seg, t_seg)
            if include_integral:
                acc[s:e] = integral_fn(c_seg, t_seg, initial=0.0)
        token = f'd{name}_dt'
        deriv_cols.append(d)
        deriv_tokens.append(token)
        deriv_token_to_base[token] = name
        if include_integral:
            itoken = f'{name}_idt'
            integral_cols.append(acc)
            integral_tokens.append(itoken)
            integral_token_to_base[itoken] = name

    extra_cols = deriv_cols + integral_cols
    extra_names = deriv_tokens + integral_tokens
    X_aug = np.column_stack([X_np] + extra_cols) if extra_cols else X_np
    return (X_aug, feature_names + extra_names,
            deriv_token_to_base, integral_token_to_base)


def _rewrite_ddt_idt_tokens(eq_text: str, deriv_token_to_base: dict,
                            integral_token_to_base: dict, gnd_ident: str,
                            placeholder_map: dict) -> str:
    """Word-boundary-anchored substitution of a derivative/integral
    feature token (e.g. 'dVPWR_dt') into a PLACEHOLDER identifier (never
    a real port name — never touched by FSMCodeGenerator's own
    _wrap_equation_port_terms, which blindly V()-wraps every bare
    occurrence of a real port name it recognizes, including AVSS/GND
    INSIDE an already-built ddt(I(AVSS, GND)) call if those were emitted
    directly here — producing invalid double-wrapped text like
    ddt(I(V(AVSS), V(GND)))). The real ddt()/idt() call text (with bare
    node-name arguments, correct for I(node1, node2) branch-access
    syntax) is recorded in `placeholder_map` and substituted into the
    final .vams text only AFTER generate_veriloga has already run its
    port-wrapping pass. A "<base>_I" base (this codebase's current-
    signal naming convention) rewrites to ddt(I(base,gnd)) instead of
    ddt(V(base))."""
    out = eq_text
    for token, base in deriv_token_to_base.items():
        if base.endswith('_I'):
            real = f'ddt(I({base[:-2]}, {gnd_ident}))'
        else:
            real = f'ddt(V({base}))'
        placeholder = f'zzzDdtPh{len(placeholder_map)}zzz'
        placeholder_map[placeholder] = real
        out = re.sub(rf'\b{re.escape(token)}\b', placeholder, out)
    for token, base in integral_token_to_base.items():
        if base.endswith('_I'):
            real = f'idt(I({base[:-2]}, {gnd_ident}))'
        else:
            real = f'idt(V({base}))'
        placeholder = f'zzzDdtPh{len(placeholder_map)}zzz'
        placeholder_map[placeholder] = real
        out = re.sub(rf'\b{re.escape(token)}\b', placeholder, out)
    return out


def _estimate_transition_time(seq: np.ndarray, run_boundaries: list,
                              sc_time: np.ndarray, fraction: float = 0.05,
                              default: float = 1e-6) -> float:
    """A single global t_transition default: `fraction` of the median
    observed state-dwell time (never crossing a run seam) — settling
    should be much faster than a state's own typical duration. Falls
    back to `default` when no usable dwell segment exists."""
    bounds = list(run_boundaries) + [len(seq)]
    dwell_times = []
    for k in range(len(bounds) - 1):
        s, e = bounds[k], bounds[k + 1]
        if e - s < 2:
            continue
        sub_seq = seq[s:e]
        change_idx = [s] + [s + i for i in range(1, len(sub_seq))
                            if sub_seq[i] != sub_seq[i - 1]] + [e - 1]
        for a, b in zip(change_idx[:-1], change_idx[1:]):
            if b > a:
                dwell_times.append(float(sc_time[b] - sc_time[a]))
    if not dwell_times:
        return default
    return max(1e-12, float(np.median(dwell_times)) * fraction)


def _transition_sensitivity(seq: np.ndarray, run_boundaries: list,
                            Y_np: np.ndarray, output_names: list,
                            transitions: list, state_defs: dict,
                            window: int = 3, top_k: int = 8):
    """For each learned FSM transition, the mean |output delta| across
    every occurrence of that transition (never crossing a run seam) —
    an informational, edge-triggered sensitivity metric in the spirit of
    core/current_insights/load_detection.py's delta-consistency idea,
    implemented directly against the flat X/seq arrays this script
    already has rather than that module's RunView plumbing."""
    bounds = list(run_boundaries) + [len(seq)]
    results = []
    for t in transitions:
        deltas = []
        for k in range(len(bounds) - 1):
            s, e = bounds[k], bounds[k + 1]
            for i in range(s + 1, e):
                if seq[i - 1] == t.from_state and seq[i] == t.to_state:
                    pre = max(s, i - window)
                    post = min(e - 1, i + window)
                    if post > pre:
                        deltas.append(Y_np[post] - Y_np[pre])
        if not deltas:
            continue
        deltas = np.array(deltas)
        mean_abs_delta = np.mean(np.abs(deltas), axis=0)
        results.append({
            'from_state': state_defs.get(t.from_state, {}).get('name', str(t.from_state)),
            'to_state': state_defs.get(t.to_state, {}).get('name', str(t.to_state)),
            'guard': t.guard_expression,
            'n_occurrences': len(deltas),
            'mean_abs_output_delta': {out: float(mean_abs_delta[j])
                                      for j, out in enumerate(output_names)},
        })
    results.sort(key=lambda r: -max(r['mean_abs_output_delta'].values()))
    return results[:top_k]


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
    from core.models.feature_selection import select_relevant_inputs
    from core.current_insights import CurrentRegistry
    from core.tensor_utils import to_np

    kg = framework_main._build_kg(args)
    sm = framework_main._resolve_signal_map(args)
    requested_models = [m.strip().lower() for m in args.models.split(',')]
    for m in requested_models:
        if m not in IMPLEMENTED_MODELS:
            print(f"  [example14] '{m}' is not an implemented model option "
                  f"(implemented: {IMPLEMENTED_MODELS}) — ignored.")

    output_names_req = [s.strip() for s in args.blut_output_signals.split(',') if s.strip()]
    user_force_include = [s.strip() for s in args.blut_input_signals.split(',') if s.strip()]

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
    # The definitive "what signal names actually resolved" set for this
    # (blut, signal_map, corner) combination — used BOTH to validate the
    # user's requested names (§1.5) and as the auto-selection candidate
    # pool (§2), rather than guessing from SpecKG's port list.
    resolvable_names = set(sc.signals.keys()) | set(sc.current_signals.keys())
    sc.signals = {}
    sc.current_signals = {}

    print(f"\n{'='*60}\n  1.5 Signal-name validation\n{'='*60}")
    requested_to_check = output_names_req + user_force_include
    bad_names = [n for n in requested_to_check if n not in resolvable_names]
    if bad_names:
        print(f"FAIL: the following requested signal name(s) did not "
              f"resolve against this BLUT/signal_map: {bad_names}")
        print(f"  Known resolvable names ({len(resolvable_names)}): "
              f"{sorted(resolvable_names)}")
        print("  (A silently-NaN-filled column previously produced an "
              "all-zero embedded equation instead of this fast, explicit "
              "failure — check for a typo against the list above.)")
        return 1
    print(f"  {len(requested_to_check)} requested name(s) OK against "
          f"{len(resolvable_names)} resolvable signal(s)")

    print(f"\n{'='*60}\n  2. Auto-selected input signals\n{'='*60}")
    output_set = set(output_names_req)
    candidate_names = sorted(n for n in resolvable_names if n not in output_set)
    registry = CurrentRegistry(kg, sm)
    auto_force = [ch.i_name for ch in
                 (registry.input_supplies() + registry.output_rails() + registry.grounds())
                 if ch.has_current and ch.i_name in resolvable_names]
    force_include = sorted(set(auto_force) | set(user_force_include))
    print(f"  {len(candidate_names)} candidate signal(s) considered")
    print(f"  force-included (supply/ground/output-rail currents + user-"
          f"specified): {force_include}")

    phase2 = Phase2SimAugmented(kg)
    fsm_detector_for_blut = FSMStateDetector(strategy=args.fsm_strategy, spec_kg=kg)
    data = phase2.build_dataset_from_blut(
        blut_path, sm, candidate_names, output_names_req,
        fsm_detector=fsm_detector_for_blut, run_ids=good_qids,
    )
    if len(data['X']) != len(seq):
        print(f"FAIL: row-count mismatch between build_dataset_from_blut "
              f"({len(data['X'])} rows) and the global FSM capture "
              f"({len(seq)} samples) — cannot trust per-row state labels.")
        return 1
    data = phase2.target_encode_categorical_meta(data)

    feature_names_vid = [_vid(n) for n in data['feature_names']]
    force_include_vid = [_vid(n) for n in force_include]
    is_meta = [n.startswith('meta_') for n in feature_names_vid]
    meta_idx = [i for i, m in enumerate(is_meta) if m]
    cand_idx = [i for i, m in enumerate(is_meta) if not m]
    cand_names_vid = [feature_names_vid[i] for i in cand_idx]

    X_np_full = to_np(data['X']).astype(np.float64)
    Y_np = to_np(data['Y']).astype(np.float64)
    output_names = data['output_names']

    selected_local_idx, relevance_scores = select_relevant_inputs(
        X_np_full[:, cand_idx], Y_np, cand_names_vid,
        force_include=force_include_vid, max_features=args.max_auto_inputs,
        relevance_min_score=args.relevance_min_score,
        redundancy_corr_threshold=args.redundancy_corr_threshold,
    )
    selected_global_idx = sorted(cand_idx[i] for i in selected_local_idx)
    final_idx = sorted(selected_global_idx + meta_idx)
    X_np = X_np_full[:, final_idx]
    feature_names = [feature_names_vid[i] for i in final_idx]
    dropped = [n for n in cand_names_vid if n not in
              {feature_names_vid[i] for i in selected_global_idx}]
    print(f"  selected {len(selected_global_idx)}/{len(cand_idx)} candidate "
          f"input(s) (+ {len(meta_idx)} meta/corner column(s)):")
    for n in [feature_names_vid[i] for i in selected_global_idx]:
        print(f"    + {n}  (relevance={relevance_scores.get(n, 0.0):.4g})")
    print(f"  dropped (below relevance/redundancy threshold, not "
          f"force-included): {dropped}")

    categorical_codes = data.get('categorical_codes', {})
    if categorical_codes:
        print("  categorical corner codes:")
        for key, mapping in categorical_codes.items():
            print(f"    meta_{key}: " +
                  '  '.join(f"{v}={c:.4g}" for v, c in mapping.items()))

    print(f"\n{'='*60}\n  3. Differential (ddt/idt) features\n{'='*60}")
    deriv_targets = [n for n in feature_names if not n.startswith('meta_')]
    X_np, feature_names, deriv_token_to_base, integral_token_to_base = \
        _add_derivative_integral_features(
            X_np, feature_names, run_boundaries, sc_time, deriv_targets,
            include_integral=args.include_integral_features)
    poly_mask = np.array([n not in deriv_token_to_base and n not in integral_token_to_base
                          for n in feature_names])
    print(f"  added {len(deriv_token_to_base)} derivative feature(s)"
          + (f" + {len(integral_token_to_base)} integral feature(s)"
             if args.include_integral_features else "")
          + f"  (X now {X_np.shape[1]} columns)")

    ground_ports = [p for p in kg.ports if p.port_type == 'ground']
    gnd_ident = _vid(ground_ports[0].name) if ground_ports else '0'

    if args.auto_transition_time:
        t_transition = _estimate_transition_time(seq, run_boundaries, sc_time,
                                                  default=args.t_transition)
        print(f"  auto-estimated t_transition = {t_transition:.4g} s "
              f"(--t_transition default was {args.t_transition:.4g} s)")
    else:
        t_transition = args.t_transition

    equation_parameters = {
        name: float(X_np[:, i].mean())
        for i, name in enumerate(feature_names) if name.startswith('meta_')
    }
    equation_parameters['t_transition'] = t_transition

    print(f"\n{'='*60}\n  4. Per-state model comparison + output equations"
          f"\n{'='*60}")
    if args.include_symbolic:
        print("  equation source: PySR (--include_symbolic) over the "
              "poly+differential feature set")
    else:
        print(f"  equation source: degree-{args.equation_degree} polynomial "
              f"+ linear differential terms")

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
        if 'gpr' in requested_models:
            gpr = CircuitGPR(X_tr.shape[1], Y_tr.shape[1])
            gpr.fit(X_tr, Y_tr)
            metrics['GPR'] = gpr.evaluate(X_te, Y_te)
        if 'smt' in requested_models:
            smt_model = CircuitSMT(X_tr.shape[1], Y_tr.shape[1])
            smt_model.fit(X_tr, Y_tr)
            metrics['SMT'] = smt_model.evaluate(X_te, Y_te)
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
            # NODE stays informational-only by explicit decision — its
            # training loop is a known, separate, pre-existing weakness
            # (see module docstring); this reuses example12's exact
            # trajectory-reconstruction helper unchanged.
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
                    extractor = CircuitSymbolicExtractor(feature_names, output_names)
                    res = extractor.extract(X_tr, Y_tr, output_idx=out_idx)
                    eq_text, r2 = res.get('equation'), res.get('r2')
                    source = 'pysr_requested'
                else:
                    eq_text, r2 = _differential_polynomial_equation(
                        X_poly_tr, poly_names, X_lin_tr, lin_names,
                        Y_tr[:, out_idx], degree=args.equation_degree)
                    source = f'polynomial_deg{args.equation_degree}+differential'
                eq_rewritten = _rewrite_ddt_idt_tokens(
                    eq_text, deriv_token_to_base, integral_token_to_base,
                    gnd_ident, ddt_idt_placeholder_map)
                eq_final = f'transition({eq_rewritten}, 0, t_transition, t_transition)'
                state_eq_info[out_name] = {
                    'equation': eq_final, 'raw_equation': eq_text, 'r2': r2,
                    'source': source,
                    'has_differential_term': eq_rewritten != eq_text,
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

    print(f"\n{'='*60}\n  5. Transition sensitivity (informational)\n{'='*60}")
    transition_sensitivity = _transition_sensitivity(
        seq, run_boundaries, Y_np, output_names, transitions, detector.state_defs)
    for row in transition_sensitivity[:5]:
        top_out = max(row['mean_abs_output_delta'], key=row['mean_abs_output_delta'].get)
        print(f"  {row['from_state']} -> {row['to_state']}  guard: {row['guard']}  "
              f"n={row['n_occurrences']}  largest delta: {top_out}="
              f"{row['mean_abs_output_delta'][top_out]:.4g}")

    print(f"\n{'='*60}\n  6. Final control-logic-skeleton codegen\n{'='*60}")
    codegen = FSMCodeGenerator(spec_kg=kg, ip_type=args.ip_type)
    va_code = codegen.generate_veriloga(
        detector.state_defs, transitions, kg.ports,
        output_equations=output_equations,
        equation_parameters=equation_parameters,
    )
    # Swap in the real ddt()/idt() call text now that generate_veriloga's
    # own port-name V()-wrapping pass has already run — see
    # _rewrite_ddt_idt_tokens's docstring for why this can't happen
    # before that pass instead.
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
    has_transition = ('transition(' in va_code)
    eq_source_label = ('PySR (--include_symbolic)' if args.include_symbolic
                       else f'degree-{args.equation_degree} polynomial + differential')
    print(f"\n  Analog skeleton output-driving equations: "
          f"{'EMBEDDED' if embedded_ok else 'NOT EMBEDDED'}")
    print(f"    states: {n_states_with_eq}   outputs: {output_names}")
    print(f"    equation source: {eq_source_label}")
    print(f"    ddt() present: {has_ddt}   idt() present: {has_idt}   "
          f"transition() present: {has_transition}")

    # ── Reports ──────────────────────────────────────────────────────────
    model_comparison = {
        'blut_path': blut_path,
        'good_corners': len(good_qids),
        'total_corners': len(corners),
        'meta_key_kind': data.get('meta_key_kind', {}),
        'categorical_codes': categorical_codes,
        'candidate_inputs': candidate_names,
        'selected_inputs': [feature_names_vid[i] for i in selected_global_idx],
        'dropped_inputs': dropped,
        'force_included_inputs': force_include,
        'relevance_scores': relevance_scores,
        'feature_names': feature_names,
        'output_names': output_names,
        'equation_source': eq_source_label,
        'equation_parameters': equation_parameters,
        't_transition': t_transition,
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
        'has_ddt': has_ddt, 'has_idt': has_idt, 'has_transition': has_transition,
    }
    _write_json(os.path.join(args.output_dir, 'model_comparison.json'), model_comparison)
    _write_json(os.path.join(args.output_dir, 'transition_sensitivity.json'),
               transition_sensitivity)

    with open(os.path.join(args.output_dir, 'model_comparison.md'), 'w') as f:
        model_cols = sorted({m for v in state_metrics.values() for m in v})
        L = ['# Phase 2 Differential/Auto-Select Model Comparison', '',
             f'BLUT: `{blut_path}`  |  good corners: {len(good_qids)}/{len(corners)}  '
             f'|  equation source: `{eq_source_label}`',
             '']
        L += ['## Auto-selected inputs', '',
              f'Candidates considered: {len(candidate_names)}', '',
              '| input | relevance | selected |', '|---|---|---|']
        for n in candidate_names:
            vn = _vid(n)
            sel = 'force' if vn in {_vid(x) for x in force_include} else \
                ('yes' if vn in {feature_names_vid[i] for i in selected_global_idx} else 'no')
            L.append(f"| {n} | {relevance_scores.get(vn, 0.0):.4g} | {sel} |")
        L.append('')
        if categorical_codes:
            L += ['## Categorical corner codes', '']
            for key, mapping in categorical_codes.items():
                L.append(f"- `meta_{key}`: " +
                        ', '.join(f"{v}={c:.4g}" for v, c in mapping.items()))
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
        L += ['', '## Transition sensitivity (informational)', '',
              '| from | to | guard | n | largest output delta |',
              '|---|---|---|---|---|']
        for row in transition_sensitivity:
            top_out = max(row['mean_abs_output_delta'], key=row['mean_abs_output_delta'].get)
            L.append(f"| {row['from_state']} | {row['to_state']} | `{row['guard']}` | "
                     f"{row['n_occurrences']} | {top_out}="
                     f"{row['mean_abs_output_delta'][top_out]:.4g} |")
        f.write('\n'.join(L) + '\n')

    manifest_path = os.path.join(args.output_dir, 'manifest.md')
    with open(manifest_path, 'w') as f:
        L = ['# example14 Run Manifest — Pipeline Structure', '',
             '```',
             '1. Load per_corner_correlation.json -> filter good corners',
             '2. Global FSM (SignalCapture + FSMStateDetector + '
             'TransitionLearner + FSMValidator) -> state_defs, transitions',
             '3. Validate requested signal names against the actually-'
             'resolved signal set (fast-fail on a typo)',
             '4. Candidate inputs = every resolvable non-output signal; '
             'select_relevant_inputs (mutual-info relevance + collinearity '
             'redundancy pruning) narrows to --max_auto_inputs, always '
             'force-including supply/ground/output-rail currents',
             '5. Derivative (+ optional integral) features per selected '
             'input, per-run/run-boundary-safe',
             '6. Per state: ' + '/'.join(m.upper() for m in requested_models if
                                        m in IMPLEMENTED_MODELS) +
             ' (informational) + ' + eq_source_label +
             ' equation, ddt()/idt() token rewrite, transition()-wrapped',
             '7. Transition-sensitivity report (informational)',
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
             f't_transition: {t_transition:.4g} s '
             f'({"auto-estimated" if args.auto_transition_time else "fixed default"})',
             '',
             '## Counter-argument to automatic input narrowing (addressed, '
             'not ignored)', '',
             'Analog circuits couple through shared rails/ground-return '
             'paths, so a real small-signal influence can sit below any '
             'statistical relevance threshold — a purely automatic hard '
             'cutoff risks silently dropping a physically-real coupling. '
             'Resolved by always force-including every supply/ground/'
             'output-rail current signal by default (matching the stated '
             'plan to standardize on including all supply and output '
             'port currents), plus any --blut_input_signals the user '
             'names explicitly — automatic narrowing only ever applies to '
             'the remaining control/select/bias/sense pin pool.',
             '',
             '## NODE (informational only — unchanged from example12)', '',
             "Phase2SimAugmented._train_node's update loop is confirmed "
             "dead code under real PyTorch (it only mutates a numpy-shim-"
             "only attribute, never calls backward()/optimizer.step()) — "
             "a known, separate, pre-existing limitation, out of scope for "
             "this pass by explicit decision. The differential-relation "
             "ask is instead satisfied deterministically by the ddt()/"
             "idt() feature-and-token-rewrite mechanism above.",
             '']
        if categorical_codes:
            L += ['## Categorical corner codes (set meta_<key> to this value '
                 'per simulated process)', '']
            for key, mapping in categorical_codes.items():
                L.append(f"- `meta_{key}`: " +
                        ', '.join(f"{v}={c:.4g}" for v, c in mapping.items()))
            L.append('')
        L += [f'**Analog skeleton output-driving equations: '
             f'{"EMBEDDED" if embedded_ok else "NOT EMBEDDED"}**',
             f'  states with equations: {n_states_with_eq}',
             f'  outputs: {output_names}',
             f'  ddt() present: {has_ddt}   idt() present: {has_idt}   '
             f'transition() present: {has_transition}',
             '',
             '## Output files', '',
             f'- `{va_path}` — final Verilog-A (FSM + self-checks + '
             f'differential, transition()-smoothed output equations)',
             f'- `{sv_path}` — final SystemVerilog control skeleton',
             f'- `{os.path.join(args.output_dir, "model_comparison.md")}` (+ .json)',
             f'- `{os.path.join(args.output_dir, "transition_sensitivity.json")}`',
             '']
        f.write('\n'.join(L))

    print(f"\n{'='*60}\n  OUTPUT FILES")
    print(f"{'='*60}")
    print(f"  Final Verilog-A       {va_path}")
    print(f"  Final SystemVerilog   {sv_path}")
    print(f"  Model comparison      {os.path.join(args.output_dir, 'model_comparison.md')} (+ .json)")
    print(f"  Transition sensitivity {os.path.join(args.output_dir, 'transition_sensitivity.json')}")
    print(f"  Manifest / structure  {manifest_path}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
