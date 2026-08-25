#!/usr/bin/env python3
"""
examples/example15_curated_inputs_full_data_modeling.py — incremental
update over example14_differential_autoselect_modeling.py (kept exactly
as-is, for reference — this script is fully self-contained, reusing
example14's UNCHANGED equation-fitting/ddt-idt-rewrite/transition-
sensitivity helpers by import), addressing four observations from
running example14 against real data with --models gpr,pinn,node
--include_symbolic:

  1. PINN/NODE MSE not improving, GPR always winning. Two DIFFERENT
     root causes, not one — and PINN's turned out to be deeper than
     first suspected:
       - PINN: TWO real bugs, now FIXED, both directly in
         core/models/pinn.py and core/phases/phase2_sim_augmented.py's
         _train_pinn (this file needs no change to see either fix — it
         calls the same methods). The PRIMARY one: CircuitPINN.forward()
         and compute_loss() round-tripped every intermediate value
         (each state sub-net's output, the gate, the final prediction,
         the data loss) through to_np()/float()/torch.tensor(...)
         before returning — under real PyTorch that SILENTLY SEVERS the
         autograd graph between the returned loss and every learnable
         parameter, so _train_pinn's total_loss.backward() either raised
         (caught by its own bare `except Exception: pass`) or produced a
         zero gradient — no parameter EVER updated, epochs or data
         volume notwithstanding (verified: loss was flat/noisy across
         epochs before this fix, and drops ~200x on a synthetic check
         after it — see the fix's comments in core/models/pinn.py for
         exactly which lines broke the graph). Fixed by keeping every
         step from the state-gate onward as genuine tensor ops
         (torch.cat/torch.stack/broadcasted multiply-and-sum instead of
         a numpy accumulation loop) and returning compute_loss()'s
         'total' as the SAME connected tensor instead of re-wrapping it
         in torch.tensor(total) (which silently re-detaches it too — the
         same gotcha, one level up). The SECONDARY bug: unlike
         CircuitGPR/CircuitSMT, which StandardScaler their inputs
         internally, _train_pinn was feeding RAW, unscaled feature
         columns straight into the network — example14's expanded
         feature set (uA-scale currents alongside V-scale voltages
         alongside a dV/dt derivative feature whose scale depends on
         the sampling dt) is exactly the kind of wildly-mixed-magnitude
         input that further slows gradient-based training even once the
         graph itself is intact. Fixed via CircuitPINN.set_input_scaler
         (z-scores X internally on every forward() call, fit once from
         train-set statistics) — stored ON THE MODEL rather than only
         inside the trainer's local scope, so a caller evaluating the
         trained network later on a raw held-out split (this script's
         own separate PINN eval block below, same pattern as example14)
         still gets the identical transform automatically. A third,
         smaller fix while in the area: _train_pinn/this script now call
         pinn.eval() before the final test-set forward pass, so Dropout
         (0.05 in every hidden layer) doesn't inject noise into the
         reported MSE. Y is deliberately left in native units throughout
         (the physics KCL/KVL loss terms need real magnitudes, and it
         keeps PINN's reported MSE directly comparable to GPR/SMT's
         already-original-units evaluate()).
       - NODE: confirmed (again) genuinely dead training code under
         real PyTorch — Phase2SimAugmented._train_node's update rule
         unconditionally checks `hasattr(p, '_d')`, an attribute that
         only exists on torch_shim's numpy-backed parameters; real
         torch.nn.Parameter never has it, so no parameter update EVER
         happens, epochs or data volume notwithstanding. This is a
         different, larger fix (a real backward()/optimizer.step()
         path), explicitly out of scope per the same decision made for
         example14 — NODE stays informational-only, its high/flat MSE
         is expected, not a bug to chase further here.
  2. "Treating all the ports as inputs will not make sense in analog
     modeling" — agreed, and addressed: --input_mode now defaults to
     "reference" (a curated --blut_input_signals list, e.g. example12's
     original default, IS the candidate pool — nothing further is
     auto-discovered from the full port list), with automatic
     supply/ground/output-rail current force-inclusion kept (a
     different, independently-justified axis — see example14's
     docstring point 3). A per-signal, per-OUTPUT mutual-information
     dependency table is still computed and reported for the reference
     inputs (this is the "find the output signal dependency" half of
     the request) without silently dropping anything the user
     explicitly asked for. example14's full "every resolvable port is a
     candidate, mRMR-narrow it" behavior is still available via
     --input_mode all_ports, for exploration/comparison.
  3. max_state_samples' significance: it bounds EVERY model uniformly,
     but only GPR and SMT actually need a small bound (both are
     O(n^2)/O(n^3) kernel-matrix methods — see core/models/
     gpr_surrogate.py's drop_degenerate_columns docstring and
     core/models/smt_surrogate.py's n_start comment for the same cost
     argument). The polynomial/differential equation fit (plain
     np.linalg.lstsq — O(n * k^2) in the design-matrix column count k,
     typically a few dozen) and PINN (full-batch gradient descent
     through a small [64,64,32] MLP) both scale comfortably to tens of
     thousands of rows. So: --max_state_samples now defaults to 200000
     (effectively "use everything" for a 50k-sample capture, per the
     request), and GPR/SMT get their OWN, separate, still-conservative
     --max_gpr_smt_samples (default 3000, drawn from the larger set) —
     the equation fit and PINN train on the full (up to
     --max_state_samples) data, only GPR/SMT sub-sample further, and
     the held-out test split stays the larger set for every model so
     the comparison table stays apples-to-apples. --include_symbolic
     gets its own --max_pysr_samples (default 5000) for the same
     reason, since PySR's search cost also scales with row count.
  4. Denoising before differentiating: real, measured signals carry
     noise, and a raw finite-difference derivative (np.gradient)
     amplifies high-frequency noise rather than averaging it out — a
     well-known numerical-differentiation issue, plausible here too.
     --smoothing_window (Savitzky-Golay, scipy.signal.savgol_filter,
     applied per-run/run-boundary-safe, BEFORE computing the derivative/
     integral feature only — never to the raw polynomial-term features,
     so the directly-measured input/output relationship those terms
     already capture stays untouched) is now a pipeline option, and
     --evaluate_denoising runs a small, self-contained side-by-side
     comparison (smoothed vs unsmoothed differential-term R² on one
     representative state/output) so the actual measured impact on your
     data is visible rather than assumed.

"uv run examples/example15_curated_inputs_full_data_modeling.py --correlation_json output_fsm_correlation_2/per_corner_correlation.json --blut_path blut_files/regression_multi_corner_sref_ldo.bin --signal_map_json configs/signal_map_ldo.json --fsm_strategy hybrid --fsm_tree_depth 4 --ip_type LDO --blut_input_signals VPWR,VREF,FUN_DC,V_SUPPLY,MOST_POS --blut_output_signals VDD_1V2,VPWR_I --models gpr,smt --min_state_sample 30 --max_state_samples 200000 --max_gpr_smt_samples 3000 --max_pysr_samples 5000 --max_auto_inputs 5 --relevance_min_score 0.05 --redunda
ncy_corr_threshold 0.95 --smoothing_window 0 --evaluate_denoising --auto_transition_time --output_dir output_new/ex15_2

Run:  uv run examples/example15_curated_inputs_full_data_modeling.py \\
          [--correlation_json output/per_corner_correlation.json] \\
          [--blut_path PATH] [--spec_json PATH] [--signal_map_json PATH] \\
          [--fsm_strategy hybrid] [--fsm_tree_depth 4] [--ip_type LDO] \\
          [--blut_output_signals VDD_1V2,VPWR_I,FUN_DC_I] \\
          [--input_mode reference] \\
          [--blut_input_signals VPWR,EN_LDO,VPWR_SEL,HIGH_POWER_MODE] \\
          [--max_auto_inputs 8] [--relevance_min_score 0.0] \\
          [--redundancy_corr_threshold 0.95] \\
          [--include_integral_features] \\
          [--smoothing_window 0] [--evaluate_denoising] \\
          [--t_transition 1e-6] [--auto_transition_time] \\
          [--equation_degree 2] [--include_symbolic] \\
          [--models gpr,smt] [--pinn_epochs 30] [--node_epochs 20] \\
          [--min_state_samples 30] [--max_state_samples 200000] \\
          [--max_gpr_smt_samples 3000] [--max_pysr_samples 5000] \\
          [--output_dir output/phase2_curated_full_data_v1]
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

try:
    import torch  # noqa: F401
except ImportError:
    import torch_shim  # noqa: F401

import numpy as np

from example12_phase2_refined_modeling import _longest_same_state_segment
from example14_differential_autoselect_modeling import (
    _differential_polynomial_equation,
    _rewrite_ddt_idt_tokens,
    _estimate_transition_time,
    _transition_sensitivity,
)

ROOT = os.path.join(os.path.dirname(__file__), "..")
CFG = os.path.join(ROOT, "configs")

IMPLEMENTED_MODELS = ("gpr", "smt", "pinn", "node")


def build_parser():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--correlation_json",
        default=os.path.join(ROOT, "output", "per_corner_correlation.json"),
    )
    ap.add_argument(
        "--blut_path",
        default=None,
        help="Defaults to the blut_path recorded in --correlation_json",
    )
    ap.add_argument("--spec_json", default=os.path.join(CFG, "LDO_1V2.json"))
    ap.add_argument(
        "--signal_map_json", default=os.path.join(CFG, "signal_map_ldo.json")
    )
    ap.add_argument(
        "--fsm_strategy", default="hybrid", choices=["logic", "cluster", "hybrid"]
    )
    ap.add_argument("--fsm_tree_depth", type=int, default=4)
    ap.add_argument("--ip_type", default="LDO")
    ap.add_argument("--blut_output_signals", default="VDD_1V2,VPWR_I,FUN_DC_I")
    ap.add_argument(
        "--input_mode",
        default="reference",
        choices=["reference", "all_ports"],
        help='"reference" (default): --blut_input_signals IS '
        "the candidate pool — nothing else is auto-"
        "discovered, nothing in it is auto-dropped (a "
        "per-output relevance table is still reported). "
        '"all_ports": example14\'s original behavior — '
        "every resolvable port is a candidate, narrowed "
        "via mRMR selection to --max_auto_inputs.",
    )
    ap.add_argument(
        "--blut_input_signals",
        default="VPWR,EN_LDO,VPWR_SEL,HIGH_POWER_MODE",
        help="In --input_mode reference: the candidate input "
        "pool itself. In --input_mode all_ports: force-"
        "included signals, same as example14.",
    )
    ap.add_argument(
        "--max_auto_inputs",
        type=int,
        default=8,
        help="Only used in --input_mode all_ports.",
    )
    ap.add_argument(
        "--relevance_min_score",
        type=float,
        default=0.0,
        help="Only used in --input_mode all_ports.",
    )
    ap.add_argument(
        "--redundancy_corr_threshold",
        type=float,
        default=0.95,
        help="Only used in --input_mode all_ports.",
    )
    ap.add_argument("--include_integral_features", action="store_true")
    ap.add_argument(
        "--smoothing_window",
        type=int,
        default=0,
        help="Savitzky-Golay smoothing window (samples, odd; "
        "even values are bumped up by 1) applied per-run "
        "to a candidate signal BEFORE computing its "
        "derivative/integral feature — 0 disables "
        "(matches example14). Never applied to the raw "
        "polynomial-term features.",
    )
    ap.add_argument(
        "--evaluate_denoising",
        action="store_true",
        help="Run a small, self-contained comparison of "
        "differential-term R2 with vs without "
        "--smoothing_window (falls back to an 11-sample "
        'window for the "with" side if --smoothing_window '
        "is 0) on one representative state/output, and "
        "report the measured difference.",
    )
    ap.add_argument("--t_transition", type=float, default=1e-6)
    ap.add_argument("--auto_transition_time", action="store_true")
    ap.add_argument("--equation_degree", type=int, default=2)
    ap.add_argument("--include_symbolic", action="store_true")
    ap.add_argument(
        "--models", default="gpr,smt", help="comma list from gpr, smt, pinn, node"
    )
    ap.add_argument("--pinn_epochs", type=int, default=30)
    ap.add_argument("--node_epochs", type=int, default=20)
    ap.add_argument("--min_state_samples", type=int, default=30)
    ap.add_argument(
        "--max_state_samples",
        type=int,
        default=200000,
        help="Per-state cap BEFORE any model-specific sub-cap "
        "— shared by the equation fit and PINN. Default "
        'is effectively "use everything" for a ~50k-'
        "sample capture; lower it only if you are memory-"
        "constrained.",
    )
    ap.add_argument(
        "--max_gpr_smt_samples",
        type=int,
        default=3000,
        help="GPR/SMT-specific training sub-cap, drawn from "
        "the (already --max_state_samples-capped) "
        "training split — both are O(n^2)/O(n^3) kernel-"
        "matrix methods and need this regardless of how "
        "much data the cheaper methods can use.",
    )
    ap.add_argument(
        "--max_pysr_samples",
        type=int,
        default=5000,
        help="PySR-specific training sub-cap (--include_symbolic "
        "only) — its search cost also scales with row count.",
    )
    ap.add_argument(
        "--output_dir",
        default=os.path.join(ROOT, "output", "phase2_curated_full_data_v1"),
    )
    return ap


def _write_json(path, obj):
    with open(path, "w") as f:
        json.dump(obj, f, indent=2, default=str)


def _subcap(X: np.ndarray, Y: np.ndarray, cap: int, rng: np.random.RandomState):
    """Uniform sub-sample down to `cap` rows — used to give GPR/SMT/PySR
    their own, smaller training set independent of the larger set the
    equation fit and PINN use, without touching the shared X/Y arrays."""
    if len(X) <= cap:
        return X, Y
    idx = rng.choice(len(X), size=cap, replace=False)
    return X[idx], Y[idx]


def _smooth_column(col: np.ndarray, window: int) -> np.ndarray:
    """Savitzky-Golay smoothing for one signal segment (already sliced to
    a single run — never smoothed across a run boundary by the caller).
    window<=1 is a no-op. Falls back to the input unchanged if the
    segment is too short for the requested window (rather than raising —
    matches this codebase's "degrade gracefully on small segments"
    convention elsewhere, e.g. _longest_same_state_segment's min-length
    checks)."""
    if window <= 1 or len(col) < 5:
        return col
    from scipy.signal import savgol_filter

    w = window if window % 2 == 1 else window + 1
    w = min(w, len(col) - 1 if len(col) % 2 == 0 else len(col))
    if w < 5:
        return col
    polyorder = min(3, w - 1)
    return savgol_filter(col, window_length=w, polyorder=polyorder)


def _add_derivative_integral_features(
    X_np: np.ndarray,
    feature_names: list,
    run_boundaries: list,
    sc_time: np.ndarray,
    target_names: list,
    include_integral: bool = False,
    smoothing_window: int = 0,
):
    """Same contract as example14's version (kept import-free/local here
    since it gains a new smoothing_window parameter — example14's own
    copy is intentionally left unchanged for reference): appends a per-
    run, run-boundary-safe derivative column (np.gradient against real
    time, never crossing a run seam) for each name in target_names, and
    optionally a running-integral column too. When smoothing_window > 0,
    each run's signal segment is Savitzky-Golay smoothed BEFORE either
    is computed — never applied to X_np itself, only to the temporary
    segment used to build the derivative/integral. Returns (X_augmented,
    augmented_feature_names, deriv_token_to_base, integral_token_to_base)."""
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
            c_seg = _smooth_column(col[s:e], smoothing_window)
            d[s:e] = np.gradient(c_seg, t_seg)
            if include_integral:
                acc[s:e] = integral_fn(c_seg, t_seg, initial=0.0)
        token = f"d{name}_dt"
        deriv_cols.append(d)
        deriv_tokens.append(token)
        deriv_token_to_base[token] = name
        if include_integral:
            itoken = f"{name}_idt"
            integral_cols.append(acc)
            integral_tokens.append(itoken)
            integral_token_to_base[itoken] = name

    extra_cols = deriv_cols + integral_cols
    extra_names = deriv_tokens + integral_tokens
    X_aug = np.column_stack([X_np] + extra_cols) if extra_cols else X_np
    return (
        X_aug,
        feature_names + extra_names,
        deriv_token_to_base,
        integral_token_to_base,
    )


def _per_output_relevance(
    X: np.ndarray,
    Y: np.ndarray,
    names: list,
    output_names: list,
    max_samples: int = 5000,
    rng: np.random.RandomState = None,
) -> dict:
    """{input_name: {output_name: mutual_info_score}} — the "find the
    output signal dependency" half of the reference-input request: even
    though nothing in a curated reference list gets dropped, this makes
    each reference input's actual per-output relevance visible.

    mutual_info_regression is a k-NN-based estimator (Kraskov et al.) —
    its cost scales with row count well beyond what a "quick relevance
    read-out" needs. Every OTHER expensive step in this pipeline (GPR/
    SMT/PySR fitting, the equation fit) is already bounded by one of the
    --max_*_samples flags; this one was NOT, and on a full multi-corner
    capture (order 10^5-10^6 rows total, well beyond the "50k+" figure
    that motivated --max_state_samples' large default) that omission
    alone can make this single step take many minutes with zero
    progress output in between — easy to mistake for a hang. A uniform
    subsample of a few thousand rows gives a statistically comparable MI
    estimate at a small fraction of the cost, consistent with how every
    other model in this script already treats "enough data for a
    reliable estimate" vs. "use literally every row"."""
    table = {name: {} for name in names}
    try:
        from sklearn.feature_selection import mutual_info_regression
    except ImportError:
        print(
            "[example15] sklearn not available — skipping per-output relevance table."
        )
        return table
    if rng is None:
        rng = np.random.RandomState(42)
    X_mi, Y_mi = _subcap(X, Y, max_samples, rng)
    print(
        f"  computing per-output relevance on {len(X_mi)}/{len(X)} rows "
        f"(subsampled for mutual_info_regression's k-NN cost) for "
        f"{len(names)} input(s) x {len(output_names)} output(s)..."
    )
    for j, name in enumerate(names):
        col = X_mi[:, j : j + 1]
        for k, out in enumerate(output_names):
            try:
                mi = mutual_info_regression(col, Y_mi[:, k], random_state=42)[0]
            except Exception:
                mi = 0.0
            table[name][out] = float(mi)
    return table


def main() -> int:
    args = build_parser().parse_args()

    with open(args.correlation_json) as f:
        correlation = json.load(f)
    blut_path = args.blut_path or correlation["blut_path"]
    corners = correlation["corners"]
    good = [r for r in corners if not r["outlier"] and not r["fsm_generation_failed"]]
    good_qids = [r["qid"] for r in good]
    if not good_qids:
        print(
            "FAIL: no non-outlier corners available in "
            f"{args.correlation_json} — run example9 first."
        )
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
    requested_models = [m.strip().lower() for m in args.models.split(",")]
    for m in requested_models:
        if m not in IMPLEMENTED_MODELS:
            print(
                f"  [example15] '{m}' is not an implemented model option "
                f"(implemented: {IMPLEMENTED_MODELS}) — ignored."
            )

    output_names_req = [
        s.strip() for s in args.blut_output_signals.split(",") if s.strip()
    ]
    user_signals = [s.strip() for s in args.blut_input_signals.split(",") if s.strip()]

    print(
        f"\n{'=' * 60}\n  1. Authoritative global FSM (control-logic skeleton)"
        f"\n{'=' * 60}"
    )
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
    transitions = learner.learn(
        seq, lm, ln, detector.state_defs, boundary_mask=sc.get_boundary_mask()
    )
    learner.print_summary()
    validator = FSMValidator(spec_kg=kg)
    fsm_report = validator.validate(
        detector.state_defs, transitions, ip_type=args.ip_type
    )
    print(f"  Validation: {fsm_report}")

    run_boundaries = list(sc.run_boundaries)
    sc_time = np.array(sc.time, dtype=np.float64)
    resolvable_names = set(sc.signals.keys()) | set(sc.current_signals.keys())
    sc.signals = {}
    sc.current_signals = {}

    print(f"\n{'=' * 60}\n  1.5 Signal-name validation\n{'=' * 60}")
    requested_to_check = output_names_req + user_signals
    bad_names = [n for n in requested_to_check if n not in resolvable_names]
    if bad_names:
        print(
            f"FAIL: the following requested signal name(s) did not "
            f"resolve against this BLUT/signal_map: {bad_names}"
        )
        print(
            f"  Known resolvable names ({len(resolvable_names)}): "
            f"{sorted(resolvable_names)}"
        )
        return 1
    print(
        f"  {len(requested_to_check)} requested name(s) OK against "
        f"{len(resolvable_names)} resolvable signal(s)"
    )

    print(
        f"\n{'=' * 60}\n  2. Input selection (--input_mode {args.input_mode})"
        f"\n{'=' * 60}"
    )
    output_set = set(output_names_req)
    registry = CurrentRegistry(kg, sm)
    auto_force = [
        ch.i_name
        for ch in (
            registry.input_supplies() + registry.output_rails() + registry.grounds()
        )
        if ch.has_current and ch.i_name in resolvable_names
    ]

    if args.input_mode == "reference":
        candidate_names = sorted(set(user_signals) | set(auto_force))
        candidate_names = [
            n for n in candidate_names if n in resolvable_names and n not in output_set
        ]
        force_include = candidate_names  # nothing in the reference pool is dropped
        print(f"  reference pool: {user_signals}")
        print(f"  + auto-forced supply/ground/output-rail currents: {auto_force}")
        print(f"  candidate/kept signal(s) ({len(candidate_names)}): {candidate_names}")
    else:
        candidate_names = sorted(n for n in resolvable_names if n not in output_set)
        force_include = sorted(set(auto_force) | set(user_signals))
        print(
            f"  {len(candidate_names)} candidate signal(s) considered (all_ports mode)"
        )
        print(f"  force-included: {force_include}")

    print(
        f"  loading dataset for {len(candidate_names)} candidate signal(s) "
        f"across {len(good_qids)} corners (re-decodes the BLUT — no "
        f"progress output until this completes, can take a while on a "
        f"large multi-corner capture)..."
    )
    phase2 = Phase2SimAugmented(kg)
    fsm_detector_for_blut = FSMStateDetector(strategy=args.fsm_strategy, spec_kg=kg)
    data = phase2.build_dataset_from_blut(
        blut_path,
        sm,
        candidate_names,
        output_names_req,
        fsm_detector=fsm_detector_for_blut,
        run_ids=good_qids,
    )
    print(f"  dataset loaded: {len(data['X'])} rows")
    if len(data["X"]) != len(seq):
        print(
            f"FAIL: row-count mismatch between build_dataset_from_blut "
            f"({len(data['X'])} rows) and the global FSM capture "
            f"({len(seq)} samples) — cannot trust per-row state labels."
        )
        return 1
    data = phase2.target_encode_categorical_meta(data)

    feature_names_vid = [_vid(n) for n in data["feature_names"]]
    force_include_vid = [_vid(n) for n in force_include]
    is_meta = [n.startswith("meta_") for n in feature_names_vid]
    meta_idx = [i for i, m in enumerate(is_meta) if m]
    cand_idx = [i for i, m in enumerate(is_meta) if not m]
    cand_names_vid = [feature_names_vid[i] for i in cand_idx]

    X_np_full = to_np(data["X"]).astype(np.float64)
    Y_np = to_np(data["Y"]).astype(np.float64)
    output_names = data["output_names"]

    if args.input_mode == "reference":
        # Nothing gets dropped — the whole (small, curated) reference
        # pool is kept as-is; relevance is reported, not enforced.
        selected_global_idx = sorted(cand_idx)
        relevance_scores = {}
    else:
        selected_local_idx, relevance_scores = select_relevant_inputs(
            X_np_full[:, cand_idx],
            Y_np,
            cand_names_vid,
            force_include=force_include_vid,
            max_features=args.max_auto_inputs,
            relevance_min_score=args.relevance_min_score,
            redundancy_corr_threshold=args.redundancy_corr_threshold,
        )
        selected_global_idx = sorted(cand_idx[i] for i in selected_local_idx)

    final_idx = sorted(selected_global_idx + meta_idx)
    X_np = X_np_full[:, final_idx]
    feature_names = [feature_names_vid[i] for i in final_idx]
    selected_names = [feature_names_vid[i] for i in selected_global_idx]

    dependency_table = _per_output_relevance(
        X_np_full[:, selected_global_idx], Y_np, selected_names, output_names
    )
    print(
        f"  {len(selected_names)} input(s) used — per-output mutual-"
        f"information dependency:"
    )
    for name in selected_names:
        row = dependency_table.get(name, {})
        row_str = "  ".join(f"{out}={v:.4g}" for out, v in row.items())
        print(f"    {name}: {row_str}")

    categorical_codes = data.get("categorical_codes", {})
    if categorical_codes:
        print("  categorical corner codes:")
        for key, mapping in categorical_codes.items():
            print(
                f"    meta_{key}: "
                + "  ".join(f"{v}={c:.4g}" for v, c in mapping.items())
            )

    print(f"\n{'=' * 60}\n  3. Differential (ddt/idt) features\n{'=' * 60}")
    deriv_targets = [n for n in feature_names if not n.startswith("meta_")]
    X_np, feature_names, deriv_token_to_base, integral_token_to_base = (
        _add_derivative_integral_features(
            X_np,
            feature_names,
            run_boundaries,
            sc_time,
            deriv_targets,
            include_integral=args.include_integral_features,
            smoothing_window=args.smoothing_window,
        )
    )
    poly_mask = np.array(
        [
            n not in deriv_token_to_base and n not in integral_token_to_base
            for n in feature_names
        ]
    )
    print(
        f"  added {len(deriv_token_to_base)} derivative feature(s)"
        + (
            f" + {len(integral_token_to_base)} integral feature(s)"
            if args.include_integral_features
            else ""
        )
        + f"  (X now {X_np.shape[1]} columns, smoothing_window="
        f"{args.smoothing_window})"
    )

    denoising_eval = None
    if args.evaluate_denoising:
        print(f"\n{'=' * 60}\n  3.5 Denoising impact evaluation\n{'=' * 60}")
        biggest_sid = max(
            detector.state_defs.keys(), key=lambda s: int((seq == s).sum())
        )
        mask = seq == biggest_sid
        n_eval = int(mask.sum())
        if n_eval >= max(30, args.min_state_samples):
            # _add_derivative_integral_features indexes by GLOBAL
            # run_boundaries/sc_time, so it must run on the FULL-length,
            # pre-derivative capture (X_np_full[:, final_idx]) — never on
            # an already state-masked slice, which would misalign those
            # global offsets against a much shorter array. Masking down
            # to just this state's rows happens AFTER, same as everywhere
            # else in this script.
            eval_base_names = feature_names[: len(final_idx)]
            eval_targets = [n for n in eval_base_names if not n.startswith("meta_")]
            eval_window = args.smoothing_window if args.smoothing_window > 1 else 11
            comparisons = {}
            for label, w in (
                ("unsmoothed", 0),
                (f"smoothed(w={eval_window})", eval_window),
            ):
                Xd, names_d, dtb, itb = _add_derivative_integral_features(
                    X_np_full[:, final_idx],
                    eval_base_names,
                    run_boundaries,
                    sc_time,
                    eval_targets,
                    include_integral=False,
                    smoothing_window=w,
                )
                pm = np.array([n not in dtb for n in names_d])
                X_state, Y_state = Xd[mask], Y_np[mask]
                eq_text, r2 = _differential_polynomial_equation(
                    X_state[:, pm],
                    [n for n, m in zip(names_d, pm) if m],
                    X_state[:, ~pm],
                    [n for n, m in zip(names_d, pm) if not m],
                    Y_state[:, 0],
                    degree=args.equation_degree,
                )
                comparisons[label] = r2
                print(f"  {label}: R2={r2:.4f}")
            denoising_eval = {
                "state": detector.state_defs[biggest_sid]["name"],
                "output": output_names[0],
                "n_samples": n_eval,
                "r2_by_variant": comparisons,
            }
            delta = comparisons.get(
                f"smoothed(w={eval_window})", 0.0
            ) - comparisons.get("unsmoothed", 0.0)
            print(
                f"  measured impact on this state/output: "
                f"{'+' if delta >= 0 else ''}{delta:.4f} R2"
            )
        else:
            print(
                f"  state {biggest_sid} too small (n={n_eval}) for a "
                f"denoising comparison, skipped"
            )

    ground_ports = [p for p in kg.ports if p.port_type == "ground"]
    gnd_ident = _vid(ground_ports[0].name) if ground_ports else "0"

    if args.auto_transition_time:
        t_transition = _estimate_transition_time(
            seq, run_boundaries, sc_time, default=args.t_transition
        )
        print(
            f"\n  auto-estimated t_transition = {t_transition:.4g} s "
            f"(--t_transition default was {args.t_transition:.4g} s)"
        )
    else:
        t_transition = args.t_transition

    equation_parameters = {
        name: float(X_np[:, i].mean())
        for i, name in enumerate(feature_names)
        if name.startswith("meta_")
    }
    equation_parameters["t_transition"] = t_transition

    print(
        f"\n{'=' * 60}\n  4. Per-state model comparison + output equations\n{'=' * 60}"
    )
    print(
        f"  sample caps: general(equation/PINN)={args.max_state_samples}  "
        f"GPR/SMT={args.max_gpr_smt_samples}"
        + (f"  PySR={args.max_pysr_samples}" if args.include_symbolic else "")
    )

    rng = np.random.RandomState(42)
    state_metrics = {}
    state_n_samples = {}
    output_equations = {}
    equation_info = {}
    ddt_idt_placeholder_map = {}
    for sid in sorted(detector.state_defs.keys()):
        sname = detector.state_defs[sid]["name"]
        mask = seq == sid
        n_state = int(mask.sum())
        if n_state < args.min_state_samples:
            print(
                f"  state {sid} ({sname}): n={n_state} < "
                f"--min_state_samples={args.min_state_samples}, skipped"
            )
            continue

        X_s, Y_s = X_np[mask], Y_np[mask]
        if n_state > args.max_state_samples:
            sub_idx = rng.choice(n_state, size=args.max_state_samples, replace=False)
            X_s, Y_s = X_s[sub_idx], Y_s[sub_idx]
            n_state = args.max_state_samples

        idx = rng.permutation(n_state)
        n_test = max(1, int(0.2 * n_state))
        if n_state - n_test < 2:
            print(
                f"  state {sid} ({sname}): n={n_state} too small for a "
                f"train/test split, skipped"
            )
            continue
        test_idx, train_idx = idx[:n_test], idx[n_test:]
        X_tr, Y_tr = X_s[train_idx], Y_s[train_idx]
        X_te, Y_te = X_s[test_idx], Y_s[test_idx]

        metrics = {}
        # GPR/SMT prediction cost scales with the EVAL set size too (a
        # 15000-row test set alone measured ~9s for one GPR.evaluate()
        # call — confirmed directly), not just the training set —
        # X_te/Y_te are sized off --max_state_samples (deliberately left
        # large for the cheap methods), so a big state's held-out split
        # can dwarf --max_gpr_smt_samples on its own. Sub-capped the same
        # way as training, independently per model call.
        X_te_kernel, Y_te_kernel = _subcap(X_te, Y_te, args.max_gpr_smt_samples, rng)
        if "gpr" in requested_models:
            Xg, Yg = _subcap(X_tr, Y_tr, args.max_gpr_smt_samples, rng)
            gpr = CircuitGPR(Xg.shape[1], Yg.shape[1])
            gpr.fit(Xg, Yg)
            metrics["GPR"] = gpr.evaluate(X_te_kernel, Y_te_kernel)
        if "smt" in requested_models:
            Xs_, Ys_ = _subcap(X_tr, Y_tr, args.max_gpr_smt_samples, rng)
            smt_model = CircuitSMT(Xs_.shape[1], Ys_.shape[1])
            smt_model.fit(Xs_, Ys_)
            metrics["SMT"] = smt_model.evaluate(X_te_kernel, Y_te_kernel)
        if "pinn" in requested_models:
            try:
                p2_pinn = Phase2SimAugmented(kg)
                p2_pinn.initialize_models(
                    input_dim=X_tr.shape[1],
                    output_dim=Y_tr.shape[1],
                    n_fsm_states=1,
                    model_names=["PINN"],
                )
                pinn_data = {
                    "X": X_tr,
                    "Y": Y_tr,
                    "state_sequence": np.zeros(len(X_tr), dtype=np.int64),
                    "output_names": output_names,
                }
                p2_pinn.incremental_train(pinn_data, epochs=args.pinn_epochs)
                pinn = p2_pinn.models["PINN"]
                pinn.eval()  # Dropout off for a deterministic eval MSE
                from core.tensor_utils import make_float_tensor, assign_col

                X_te_t = make_float_tensor(X_te.astype(np.float32))
                S_te = make_float_tensor(np.zeros((len(X_te), 1), dtype=np.float32))
                assign_col(S_te, 0, 1.0)
                out_te = pinn(X_te_t, S_te)
                pred_np = to_np(out_te["predictions"]).astype(np.float64)
                metrics["PINN"] = float(np.mean((pred_np - Y_te) ** 2))
            except Exception as e:
                print(f"  state {sid} ({sname}): PINN training failed — {e}")
        if "node" in requested_models:
            # NODE stays informational-only by explicit decision — see
            # module docstring. Reuses example12's exact trajectory-
            # reconstruction helper unchanged.
            try:
                seg_start, seg_end = _longest_same_state_segment(
                    seq, run_boundaries, sid
                )
                if seg_start is not None and (seg_end - seg_start) >= 5:
                    t_seg = sc_time[seg_start:seg_end]
                    X_seg = X_np[seg_start:seg_end]
                    Y_seg = Y_np[seg_start:seg_end]
                    p2_node = Phase2SimAugmented(kg)
                    p2_node.initialize_models(
                        input_dim=X_seg.shape[1],
                        output_dim=Y_seg.shape[1],
                        n_fsm_states=1,
                        state_dim=Y_seg.shape[1],
                        model_names=["NODE"],
                    )
                    node_data = {
                        "X": X_seg,
                        "Y": Y_seg,
                        "t_span": t_seg,
                        "trajectories": Y_seg,
                    }
                    node_metrics = p2_node.incremental_train(
                        node_data, epochs=args.node_epochs
                    )
                    metrics["NODE"] = node_metrics.get("NODE", {}).get(
                        "test_mse", float("nan")
                    )
                else:
                    print(
                        f"  state {sid} ({sname}): no single-corner "
                        f"contiguous stretch long enough for NODE, skipped"
                    )
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
                    from core.interpretability.symbolic_regression import (
                        CircuitSymbolicExtractor,
                    )

                    X_pysr, Y_pysr = _subcap(X_tr, Y_tr, args.max_pysr_samples, rng)
                    print(
                        f"    fitting PySR for state {sid} ({sname}) "
                        f"output {out_name} (n={len(X_pysr)}) — the FIRST "
                        f"PySR call in this process bootstraps a Julia "
                        f"environment with near-zero console output "
                        f"(PySRRegressor(verbosity=0)) and can take "
                        f"several minutes; this is expected, not a hang."
                    )
                    extractor = CircuitSymbolicExtractor(feature_names, output_names)
                    res = extractor.extract(X_pysr, Y_pysr, output_idx=out_idx)
                    eq_text, r2 = res.get("equation"), res.get("r2")
                    source = "pysr_requested"
                else:
                    eq_text, r2 = _differential_polynomial_equation(
                        X_poly_tr,
                        poly_names,
                        X_lin_tr,
                        lin_names,
                        Y_tr[:, out_idx],
                        degree=args.equation_degree,
                    )
                    source = f"polynomial_deg{args.equation_degree}+differential"
                eq_rewritten = _rewrite_ddt_idt_tokens(
                    eq_text,
                    deriv_token_to_base,
                    integral_token_to_base,
                    gnd_ident,
                    ddt_idt_placeholder_map,
                )
                eq_final = f"transition({eq_rewritten}, 0, t_transition, t_transition)"
                state_eq_info[out_name] = {
                    "equation": eq_final,
                    "raw_equation": eq_text,
                    "r2": r2,
                    "source": source,
                    "has_differential_term": eq_rewritten != eq_text,
                }
            except Exception as e:
                state_eq_info[out_name] = {
                    "equation": None,
                    "r2": None,
                    "source": "failed",
                    "error": str(e),
                }

        equation_info[sid] = state_eq_info
        output_equations[sid] = {
            name: info["equation"]
            for name, info in state_eq_info.items()
            if info["equation"]
        }

        state_metrics[sid] = metrics
        state_n_samples[sid] = n_state
        metric_str = "  ".join(f"{k}={v:.4g}" for k, v in metrics.items())
        eq_r2_str = "  ".join(
            f"{n}_R2={i['r2']:.3f}"
            for n, i in state_eq_info.items()
            if i["r2"] is not None
        )
        print(f"  state {sid} ({sname}): n={n_state}  {metric_str}  {eq_r2_str}")

    print()
    best_by_state = (
        ModelSelector.select_best_per_state(state_metrics) if state_metrics else {}
    )

    print(f"\n{'=' * 60}\n  5. Transition sensitivity (informational)\n{'=' * 60}")
    transition_sensitivity = _transition_sensitivity(
        seq, run_boundaries, Y_np, output_names, transitions, detector.state_defs
    )
    for row in transition_sensitivity[:5]:
        top_out = max(
            row["mean_abs_output_delta"], key=row["mean_abs_output_delta"].get
        )
        print(
            f"  {row['from_state']} -> {row['to_state']}  guard: {row['guard']}  "
            f"n={row['n_occurrences']}  largest delta: {top_out}="
            f"{row['mean_abs_output_delta'][top_out]:.4g}"
        )

    print(f"\n{'=' * 60}\n  6. Final control-logic-skeleton codegen\n{'=' * 60}")
    codegen = FSMCodeGenerator(spec_kg=kg, ip_type=args.ip_type)
    va_code = codegen.generate_veriloga(
        detector.state_defs,
        transitions,
        kg.ports,
        output_equations=output_equations,
        equation_parameters=equation_parameters,
    )
    for placeholder, real in ddt_idt_placeholder_map.items():
        va_code = va_code.replace(placeholder, real)
    sv_code = codegen.generate_systemverilog(detector.state_defs, transitions)
    ip = args.ip_type.lower()
    va_path = os.path.join(args.output_dir, f"{ip}_fsm_skeleton.vams")
    sv_path = os.path.join(args.output_dir, f"{ip}_fsm_skeleton.sv")
    with open(va_path, "w") as f:
        f.write(va_code)
    with open(sv_path, "w") as f:
        f.write(sv_code)

    n_states_with_eq = len(output_equations)
    embedded_ok = (
        n_states_with_eq > 0 and "Fitted per-state output equations" in va_code
    )
    has_ddt = "ddt(" in va_code
    has_idt = "idt(" in va_code
    has_transition = "transition(" in va_code
    eq_source_label = (
        "PySR (--include_symbolic)"
        if args.include_symbolic
        else f"degree-{args.equation_degree} polynomial + differential"
    )
    print(
        f"\n  Analog skeleton output-driving equations: "
        f"{'EMBEDDED' if embedded_ok else 'NOT EMBEDDED'}"
    )
    print(f"    states: {n_states_with_eq}   outputs: {output_names}")
    print(f"    equation source: {eq_source_label}")
    print(
        f"    ddt() present: {has_ddt}   idt() present: {has_idt}   "
        f"transition() present: {has_transition}"
    )

    # ── Reports ──────────────────────────────────────────────────────────
    model_comparison = {
        "blut_path": blut_path,
        "good_corners": len(good_qids),
        "total_corners": len(corners),
        "input_mode": args.input_mode,
        "meta_key_kind": data.get("meta_key_kind", {}),
        "categorical_codes": categorical_codes,
        "candidate_inputs": candidate_names,
        "selected_inputs": selected_names,
        "dependency_table": dependency_table,
        "feature_names": feature_names,
        "output_names": output_names,
        "equation_source": eq_source_label,
        "equation_parameters": equation_parameters,
        "t_transition": t_transition,
        "sample_caps": {
            "max_state_samples": args.max_state_samples,
            "max_gpr_smt_samples": args.max_gpr_smt_samples,
            "max_pysr_samples": args.max_pysr_samples
            if args.include_symbolic
            else None,
        },
        "denoising_evaluation": denoising_eval,
        "states": {
            str(sid): {
                "name": detector.state_defs[sid]["name"],
                "n_samples": state_n_samples[sid],
                "metrics": state_metrics[sid],
                "best_black_box_model": best_by_state.get(sid),
                "equations": equation_info.get(sid, {}),
            }
            for sid in state_metrics
        },
        "fsm_validation": {
            "reachability": fsm_report.reachability,
            "completeness": fsm_report.completeness,
            "determinism": fsm_report.determinism,
            "speckg_coverage": fsm_report.speckg_coverage,
        },
        "analog_skeleton_equations_embedded": embedded_ok,
        "has_ddt": has_ddt,
        "has_idt": has_idt,
        "has_transition": has_transition,
    }
    _write_json(
        os.path.join(args.output_dir, "model_comparison.json"), model_comparison
    )
    _write_json(
        os.path.join(args.output_dir, "transition_sensitivity.json"),
        transition_sensitivity,
    )

    with open(os.path.join(args.output_dir, "model_comparison.md"), "w") as f:
        model_cols = sorted({m for v in state_metrics.values() for m in v})
        L = [
            "# Phase 2 Curated-Input Full-Data Model Comparison",
            "",
            f"BLUT: `{blut_path}`  |  good corners: {len(good_qids)}/{len(corners)}  "
            f"|  input mode: `{args.input_mode}`  "
            f"|  equation source: `{eq_source_label}`",
            "",
        ]
        L += [
            "## Selected inputs + per-output dependency (mutual information)",
            "",
            "| input | " + " | ".join(output_names) + " |",
            "|---|" + "---|" * len(output_names),
        ]
        for name in selected_names:
            row = dependency_table.get(name, {})
            L.append(
                f"| {name} | "
                + " | ".join(f"{row.get(o, 0.0):.4g}" for o in output_names)
                + " |"
            )
        L.append("")
        if categorical_codes:
            L += ["## Categorical corner codes", ""]
            for key, mapping in categorical_codes.items():
                L.append(
                    f"- `meta_{key}`: "
                    + ", ".join(f"{v}={c:.4g}" for v, c in mapping.items())
                )
            L.append("")
        L += [
            "## Sample caps used",
            "",
            f"- general (equation fit + PINN): {args.max_state_samples}",
            f"- GPR/SMT: {args.max_gpr_smt_samples}",
        ]
        if args.include_symbolic:
            L.append(f"- PySR: {args.max_pysr_samples}")
        L.append("")
        if denoising_eval:
            L += [
                "## Denoising impact evaluation",
                "",
                f"State: {denoising_eval['state']}  Output: "
                f"{denoising_eval['output']}  n={denoising_eval['n_samples']}",
                "",
            ]
            for label, r2 in denoising_eval["r2_by_variant"].items():
                L.append(f"- {label}: R2={r2:.4f}")
            L.append("")
        L += [
            "| state | n_samples | " + " | ".join(model_cols) + " | best black-box |",
            "|---|---|" + "---|" * len(model_cols) + "---|",
        ]
        for sid, metrics in state_metrics.items():
            sname = detector.state_defs[sid]["name"]
            row = (
                f"| {sname} | {state_n_samples[sid]} | "
                + " | ".join(f"{metrics.get(m, float('nan')):.4g}" for m in model_cols)
                + f" | {best_by_state.get(sid)} |"
            )
            L.append(row)
        L += [
            "",
            "## Fitted output equations (embedded in the .vams)",
            "",
            "| state | output | R2 | has ddt/idt | equation |",
            "|---|---|---|---|---|",
        ]
        for sid, eqs in equation_info.items():
            sname = detector.state_defs[sid]["name"]
            for out_name, info in eqs.items():
                r2_str = f"{info['r2']:.3f}" if info.get("r2") is not None else "n/a"
                has_diff = info.get("has_differential_term", False)
                eq_str = (info.get("equation") or "FAILED")[:200]
                L.append(
                    f"| {sname} | {out_name} | {r2_str} | {has_diff} | `{eq_str}` |"
                )
        L += [
            "",
            "## Transition sensitivity (informational)",
            "",
            "| from | to | guard | n | largest output delta |",
            "|---|---|---|---|---|",
        ]
        for row in transition_sensitivity:
            top_out = max(
                row["mean_abs_output_delta"], key=row["mean_abs_output_delta"].get
            )
            L.append(
                f"| {row['from_state']} | {row['to_state']} | `{row['guard']}` | "
                f"{row['n_occurrences']} | {top_out}="
                f"{row['mean_abs_output_delta'][top_out]:.4g} |"
            )
        f.write("\n".join(L) + "\n")

    manifest_path = os.path.join(args.output_dir, "manifest.md")
    with open(manifest_path, "w") as f:
        L = [
            "# example15 Run Manifest — Pipeline Structure",
            "",
            "```",
            "1. Load per_corner_correlation.json -> filter good corners",
            "2. Global FSM (SignalCapture + FSMStateDetector + "
            "TransitionLearner + FSMValidator) -> state_defs, transitions",
            "3. Validate requested signal names against the actually-"
            "resolved signal set (fast-fail on a typo)",
            f"4. Input selection (--input_mode {args.input_mode}): "
            + (
                "curated --blut_input_signals pool kept as-is + auto-forced "
                "supply/ground/output-rail currents, per-output MI "
                "dependency reported (nothing dropped)"
                if args.input_mode == "reference"
                else "every resolvable port a candidate, mRMR-narrowed to "
                "--max_auto_inputs"
            ),
            "5. Derivative (+ optional integral) features per selected "
            "input, per-run/run-boundary-safe"
            + (
                f", Savitzky-Golay smoothed (window={args.smoothing_window})"
                if args.smoothing_window > 1
                else ""
            ),
            "6. Per state: "
            + "/".join(m.upper() for m in requested_models if m in IMPLEMENTED_MODELS)
            + " (informational; GPR/SMT/PySR sub-capped, equation fit + PINN "
            "use the full --max_state_samples-capped set) + "
            + eq_source_label
            + " equation, ddt()/idt() token rewrite, "
            "transition()-wrapped",
            "7. Transition-sensitivity report (informational)",
            "8. FSMCodeGenerator.generate_veriloga(output_equations=...) "
            "-> final .vams/.sv",
            "```",
            "",
            f"BLUT: `{blut_path}`",
            f"Correlation source: `{args.correlation_json}`",
            f"Good corners: {len(good_qids)}/{len(corners)}",
            f"FSM strategy: `{args.fsm_strategy}`",
            f"States: {[d['name'] for d in detector.state_defs.values()]}",
            f"Transitions: {len(transitions)}",
            f"Models requested: {requested_models}",
            f"Equation source: {eq_source_label}",
            f"t_transition: {t_transition:.4g} s "
            f"({'auto-estimated' if args.auto_transition_time else 'fixed default'})",
            "",
            "## PINN/NODE convergence (see module docstring for full detail)",
            "",
            "- PINN: two real bugs, now fixed directly in "
            "core/models/pinn.py and core/phases/phase2_sim_augmented.py "
            "`_train_pinn`. Primary: CircuitPINN.forward()/compute_loss() "
            "silently severed the autograd graph via to_np()/float()/"
            "torch.tensor(...) round-tripping, so no parameter EVER "
            "updated under real PyTorch regardless of epochs (verified: "
            "loss now drops ~200x on a synthetic check that was flat "
            "before). Secondary: missing input feature scaling — fixed "
            "via CircuitPINN.set_input_scaler, stored on the model so any "
            "later eval call (including this script's own) stays "
            "consistent. No change needed in this script to get either "
            "fix; it calls the same methods example14 does.",
            "- NODE: confirmed genuinely dead training code under real "
            "PyTorch (`_train_node`'s update rule only mutates a numpy-"
            "shim-only attribute) — informational-only, unchanged, out of "
            "scope by explicit decision (same as example14).",
            "",
            "## Sample caps",
            "",
            f"- general (equation fit + PINN): {args.max_state_samples}",
            f"- GPR/SMT: {args.max_gpr_smt_samples}",
        ]
        if args.include_symbolic:
            L.append(f"- PySR: {args.max_pysr_samples}")
        L += [
            "",
            f"**Analog skeleton output-driving equations: "
            f"{'EMBEDDED' if embedded_ok else 'NOT EMBEDDED'}**",
            f"  states with equations: {n_states_with_eq}",
            f"  outputs: {output_names}",
            f"  ddt() present: {has_ddt}   idt() present: {has_idt}   "
            f"transition() present: {has_transition}",
            "",
            "## Output files",
            "",
            f"- `{va_path}` — final Verilog-A",
            f"- `{sv_path}` — final SystemVerilog control skeleton",
            f"- `{os.path.join(args.output_dir, 'model_comparison.md')}` (+ .json)",
            f"- `{os.path.join(args.output_dir, 'transition_sensitivity.json')}`",
            "",
        ]
        f.write("\n".join(L))

    print(f"\n{'=' * 60}\n  OUTPUT FILES")
    print(f"{'=' * 60}")
    print(f"  Final Verilog-A       {va_path}")
    print(f"  Final SystemVerilog   {sv_path}")
    print(
        f"  Model comparison      {os.path.join(args.output_dir, 'model_comparison.md')} (+ .json)"
    )
    print(
        f"  Transition sensitivity {os.path.join(args.output_dir, 'transition_sensitivity.json')}"
    )
    print(f"  Manifest / structure  {manifest_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
