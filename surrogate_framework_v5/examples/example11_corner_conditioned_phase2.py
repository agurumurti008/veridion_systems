#!/usr/bin/env python3
"""
examples/example11_corner_conditioned_phase2.py — corner-conditioned,
per-state Phase 2 modeling with current/voltage-backed physics insights.

Builds on example9/example10 (both left unmodified — this script is
fully self-contained, re-deriving what it needs inline) to produce, from
the SAME clean/good corner set:

  1. A corner-and-state-labeled Phase 2 training dataset: process/temp/
     vsup (and any other regression sweep variables) ride as explicit
     input features — continuous ones (temp, vsup: already their true
     numeric value) left as-is for future interpolation work, categorical
     ones (process corner "nn"/"ss"/"ww") one-hot expanded rather than
     given a misleading ordinal scale (see
     Phase2SimAugmented.expand_categorical_meta).
  2. ONE authoritative global FSM (state_defs/transitions), derived the
     same way example10 does (single global detection over the
     concatenated good-corner capture, boundary-mask-aware) — this is
     the "control-logic skeleton" the per-state models below are sliced
     against, and what the final generated .vams/.sv control-logic
     skeleton embeds.
  3. Per-state model comparison (GPR, SMT — Surrogate Modeling Toolbox
     via `smt` if installed, else a regularized scipy RBFInterpolator
     fallback; PINN optionally via `--models gpr,smt,pinn`, reusing
     Phase2SimAugmented.initialize_models/incremental_train per state
     with n_fsm_states=1 — this sidesteps the multi-state soft-gate
     machinery that makes whole-capture PINN unreliable, since with one
     sub-network the gate is trivial. NODE is not offered: it needs
     transient trajectory data, structurally different from a per-state
     tabular slice.)
  4. A fitted input->output EQUATION per (state, output) — always a fast,
     robust linear regression by default; a PySR symbolic-regression
     equation instead when --include_symbolic is passed (PySR bootstraps
     a Julia environment on first use and is meaningfully slower, hence
     opt-in). This equation is what actually DRIVES the output in the
     generated .vams (see item 6) — GPR/SMT/PINN remain informational
     (how good COULD a black-box model be), since none of them reduces
     to a compact closed-form expression a Verilog-A simulator can run.
  5. Current/voltage-backed insights reusing core/current_insights/
     as-is (no template/fit_result needed): MuxVerification (e.g.
     VPWR_SEL's effect showing up as current redistribution between
     VPWR/FUN_DC), SupplyAttribution (per-state supply current ranking),
     TransitionHealth (per-transition shoot-through/inrush), and
     EfficiencySequencing (per-state P_out/P_in efficiency).
  6. A regenerated FSM Verilog-A/SV control-logic skeleton using the
     updated FSMCodeGenerator: supply-sensitive `logic` pins for pure-
     digital control signals, $strobe range self-checks for supply/
     ground/bulk/bias pins, AND (new) a per-state case(current_state)
     block that actually drives every requested output from its fitted
     equation (item 4) — V(<port>) <+ eq; for a voltage output, I(<base>,
     <gnd>) <+ eq; for a "<base>_I" current output. Corner/meta terms an
     equation references (temp, vsup, one-hot process flags) have no
     physical pin, so they're declared as overridable `parameter real`s
     instead — settable per simulated corner, the same pattern
     core/ab_integration/ab_codegen.py already uses for PVT tables.

Explicit non-goal this pass: actually validating interpolation accuracy
at unseen/intermittent corners — only the continuous-vs-categorical
feature-encoding groundwork is built now (see module docstring above).

Run:  uv run examples/example11_corner_conditioned_phase2.py \\
          [--correlation_json output/per_corner_correlation.json] \\
          [--blut_path PATH] [--spec_json PATH] [--signal_map_json PATH] \\
          [--fsm_strategy hybrid] [--fsm_tree_depth 4] [--ip_type LDO] \\
          [--blut_input_signals VPWR,EN_LDO,VPWR_SEL,HIGH_POWER_MODE] \\
          [--blut_output_signals VDD_1V2,VPWR_I,FUN_DC_I] \\
          [--models gpr,smt] [--include_symbolic] \\
          [--min_state_samples 30] [--max_state_samples 3000] \\
          [--pinn_epochs 30] [--output_dir output/phase2_corner_model]

Example command:
uv run examples/example11_corner_conditioned_phase2.py --correlation_json output_fsm_correlation_2/per_corner_correlation.json --blut_path blut_files/regression_multi_corner_sref_ldo.bin --signal_map_json configs/signal_map_ldo.json --fsm_strategy hybrid --fsm_tree_depth 4 --ip_type LDO --blut_input_signals VPWR,VREF,FUN_DC,VDD_1V2_EXT,V_SUPPLY --blut_output_signals VDD_1V2,VPWR_I,FUN_DC_I,V_SUPPLY_I,VDD_1V2_EXT_I --models pinn --include_symbolic --min_state_sample 30 --max_state_samples 3000 --output_dir output_phase2_pinn_3000
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

ROOT = os.path.join(os.path.dirname(__file__), "..")
CFG = os.path.join(ROOT, "configs")

IMPLEMENTED_MODELS = ("gpr", "smt", "pinn")


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
    ap.add_argument(
        "--blut_input_signals", default="VPWR,EN_LDO,VPWR_SEL,HIGH_POWER_MODE"
    )
    ap.add_argument("--blut_output_signals", default="VDD_1V2,VPWR_I,FUN_DC_I")
    ap.add_argument(
        "--models",
        default="gpr,smt",
        help="comma list from gpr, smt, pinn (node is not "
        "offered — needs transient trajectory data, not "
        "a tabular per-state slice)",
    )
    ap.add_argument(
        "--pinn_epochs",
        type=int,
        default=30,
        help="Epochs for per-state PINN training (runs once "
        "per state — kept small by default)",
    )
    ap.add_argument(
        "--include_symbolic",
        action="store_true",
        help="Use PySR symbolic regression (falls back to "
        "linear internally on failure) for the embedded "
        "per-state output equations instead of the "
        "default fast linear fit. Off by default — PySR "
        "bootstraps a Julia environment on first use "
        "(minutes) and each (state, output) pair adds a "
        "full search on top.",
    )
    ap.add_argument("--min_state_samples", type=int, default=30)
    ap.add_argument(
        "--max_state_samples",
        type=int,
        default=3000,
        help="Uniform subsample cap per state before model "
        "fitting — GPR/Kriging are O(n^2) memory / O(n^3) "
        "time, infeasible on a dense multi-corner transient "
        "capture without this.",
    )
    ap.add_argument(
        "--output_dir", default=os.path.join(ROOT, "output", "phase2_corner_model")
    )
    return ap


def _write_json(path, obj):
    with open(path, "w") as f:
        json.dump(obj, f, indent=2, default=str)


def _linear_equation(X: np.ndarray, y: np.ndarray, feature_names: list):
    """Local duplicate of CircuitSymbolicExtractor._linear_fallback's
    logic (core/interpretability/symbolic_regression.py) — NOT imported
    from there because importing that module pulls in pysr/juliacall at
    IMPORT TIME whenever pysr is installed, even if .extract() is never
    called; pysr's own wrapper warns that importing juliacall after torch
    (torch/torch_shim is always imported at module load here) risks a
    segfault. Duplicating this ~15-line fit keeps the default (non-
    --include_symbolic) path free of that import entirely. Returns
    (equation_string, r2)."""
    X_b = np.hstack([X, np.ones((len(X), 1))])
    try:
        sol, _, _, _ = np.linalg.lstsq(X_b, y, rcond=None)
    except Exception:
        sol = np.zeros(X.shape[1] + 1)
    coeffs, intercept = sol[:-1], sol[-1]
    terms = [
        f"{c:.6g}*{name}" for c, name in zip(coeffs, feature_names) if abs(c) > 1e-10
    ]
    if abs(intercept) > 1e-10:
        terms.append(f"{intercept:.6g}")
    equation = " + ".join(terms) if terms else "0"
    y_pred = X_b @ sol
    ss_res = float(np.sum((y - y_pred) ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    r2 = 1.0 if ss_tot < 1e-30 else 1 - ss_res / ss_tot
    return equation, r2


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
    from core.tensor_utils import to_np
    from digitwin.blut_reader_ext import (
        open_blut,
        get_run,
        load_run_matrix,
        DEFAULT_CURRENT_SUFFIXES,
    )
    from core.current_insights import CurrentRegistry, build_run_views, run_analyzers
    from core.current_insights.findings import EfficiencySequencing

    kg = framework_main._build_kg(args)
    sm = framework_main._resolve_signal_map(args)
    requested_models = [m.strip().lower() for m in args.models.split(",")]
    for m in requested_models:
        if m not in IMPLEMENTED_MODELS:
            print(
                f"  [example11] '{m}' is not an implemented model option "
                f"(implemented: {IMPLEMENTED_MODELS}) — ignored."
            )

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

    # Keep only the (tiny) run_boundaries index list needed in step 4 —
    # sc's decoded per-sample signal/current arrays for many corners are
    # no longer needed once seq/transitions are derived, and step 2 below
    # does a second full independent load of the same corners; freeing
    # this first caps peak memory instead of holding two full copies
    # concurrently.
    run_boundaries = list(sc.run_boundaries)
    sc.signals = {}
    sc.current_signals = {}

    print(f"\n{'=' * 60}\n  2. Corner-and-state-labeled Phase 2 dataset\n{'=' * 60}")
    input_names = [s.strip() for s in args.blut_input_signals.split(",")]
    output_names_req = [s.strip() for s in args.blut_output_signals.split(",")]
    phase2 = Phase2SimAugmented(kg)
    # Fresh detector instance for build_dataset_from_blut's own (discarded)
    # per-run state_sequence — the authoritative labels are `seq` above.
    fsm_detector_for_blut = FSMStateDetector(strategy=args.fsm_strategy, spec_kg=kg)
    data = phase2.build_dataset_from_blut(
        blut_path,
        sm,
        input_names,
        output_names_req,
        fsm_detector=fsm_detector_for_blut,
        run_ids=good_qids,
    )
    if len(data["X"]) != len(seq):
        print(
            f"FAIL: row-count mismatch between build_dataset_from_blut "
            f"({len(data['X'])} rows) and the global FSM capture "
            f"({len(seq)} samples) — the two SignalCapture loads over "
            f"the same good_qids diverged; cannot trust per-row state "
            f"labels. This should not happen — check for BLUT signals "
            f"present in one path's decode but not the other's."
        )
        return 1
    data = phase2.expand_categorical_meta(data)
    print(f"  X: {tuple(to_np(data['X']).shape)}  features: {data['feature_names']}")
    print(f"  Y: {tuple(to_np(data['Y']).shape)}  outputs: {data['output_names']}")
    print(f"  meta_key_kind: {data.get('meta_key_kind', {})}")

    X_np = to_np(data["X"]).astype(np.float64)
    Y_np = to_np(data["Y"]).astype(np.float64)
    output_names = data["output_names"]
    # Sanitized feature names: also what the equation TEXT embeds as
    # tokens, so they must already be legal Verilog-A identifiers (a raw
    # one-hot name like "meta_corner=nn" is not — _vid() -> "meta_corner_nn").
    # generate_veriloga's equation_parameters dict (built below with the
    # same sanitized names) then declares each as a real parameter.
    feature_names = [_vid(n) for n in data["feature_names"]]
    equation_parameters = {
        name: float(X_np[:, i].mean())
        for i, name in enumerate(feature_names)
        if name.startswith("meta_")
    }

    print(
        f"\n{'=' * 60}\n  3. Per-state model comparison + output equations\n{'=' * 60}"
    )
    if args.include_symbolic:
        print(
            "  equation source: PySR (--include_symbolic) — first call "
            "bootstraps a Julia environment, this can take a while"
        )
    else:
        print("  equation source: linear (pass --include_symbolic for PySR)")

    rng = np.random.RandomState(42)
    state_metrics = {}
    state_n_samples = {}
    output_equations = {}  # {state_id: {output_name: equation_text}}
    equation_info = {}  # {state_id: {output_name: {equation, r2, source}}}
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
        # GPR/Kriging-family models are O(n^2) memory / O(n^3) time in the
        # kernel matrix — states here can carry hundreds of thousands of
        # transient samples across many corners, which is both infeasible
        # to fit and unnecessary (dense oversampling of a smooth transient
        # doesn't add real information). Subsample once, uniformly,
        # BEFORE the train/test split.
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
        if "gpr" in requested_models:
            gpr = CircuitGPR(X_tr.shape[1], Y_tr.shape[1])
            gpr.fit(X_tr, Y_tr)
            metrics["GPR"] = gpr.evaluate(X_te, Y_te)
        if "smt" in requested_models:
            smt_model = CircuitSMT(X_tr.shape[1], Y_tr.shape[1])
            smt_model.fit(X_tr, Y_tr)
            metrics["SMT"] = smt_model.evaluate(X_te, Y_te)
        if "pinn" in requested_models:
            # Reuse the existing, tested Phase2 training pipeline rather
            # than writing a new trainer: n_fsm_states=1 collapses PINN's
            # internal multi-state soft-gate to a single sub-network
            # (trivial gate), sidestepping the hardcoded-state-0-at-eval
            # issue that makes whole-capture PINN unreliable.
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
                from core.tensor_utils import make_float_tensor, assign_col

                X_te_t = make_float_tensor(X_te.astype(np.float32))
                S_te = make_float_tensor(np.zeros((len(X_te), 1), dtype=np.float32))
                assign_col(S_te, 0, 1.0)
                out_te = pinn(X_te_t, S_te)
                pred_np = to_np(out_te["predictions"]).astype(np.float64)
                metrics["PINN"] = float(np.mean((pred_np - Y_te) ** 2))
            except Exception as e:
                print(f"  state {sid} ({sname}): PINN training failed — {e}")

        # Fitted output equation(s) — always computed (this is what the
        # final .vams actually gets driven by); GPR/SMT/PINN above are
        # informational, since none reduces to a compact closed-form
        # expression a Verilog-A simulator can evaluate.
        state_eq_info = {}
        for out_idx, out_name in enumerate(output_names):
            try:
                if args.include_symbolic:
                    from core.interpretability.symbolic_regression import (
                        CircuitSymbolicExtractor,
                    )

                    extractor = CircuitSymbolicExtractor(feature_names, output_names)
                    res = extractor.extract(X_tr, Y_tr, output_idx=out_idx)
                    eq_text, r2 = res.get("equation"), res.get("r2")
                    # extract() tries PySR then silently falls back to the
                    # same linear fit internally on failure — it doesn't
                    # report which path was actually taken, so this is
                    # "requested PySR" rather than a confirmed PySR hit.
                    source = "pysr_requested"
                else:
                    eq_text, r2 = _linear_equation(
                        X_tr, Y_tr[:, out_idx], feature_names
                    )
                    source = "linear"
                state_eq_info[out_name] = {
                    "equation": eq_text,
                    "r2": r2,
                    "source": source,
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

    print(f"\n{'=' * 60}\n  4. Current/voltage-backed insights\n{'=' * 60}")
    blut = open_blut(blut_path)
    runs = []
    for qid in good_qids:
        rid, _, cid = qid.partition("@")
        run = get_run(blut, rid, cid if cid else None)
        runs.append(
            load_run_matrix(
                blut_path, run, None, DEFAULT_CURRENT_SUFFIXES, signal_map=sm
            )
        )

    bounds = run_boundaries + [len(seq)]
    state_sequences = {
        qid: seq[bounds[k] : bounds[k + 1]] for k, qid in enumerate(good_qids)
    }

    registry = CurrentRegistry(kg, sm)
    views = build_run_views(
        runs, registry, state_sequences=state_sequences, state_defs=detector.state_defs
    )
    findings, _analyzers = run_analyzers(views, registry, fsm_result=fsm_report)

    mux_findings = [
        f for f in findings if f.category in ("mux-verified", "untested-mux")
    ]
    supply_findings = [f for f in findings if f.category == "supply-dominance"]
    transition_findings = [
        f for f in findings if f.analyzer == "3.11 transition-health"
    ]
    print(f"  mux-verification findings: {len(mux_findings)}")
    for f in mux_findings[:5]:
        print(f"    {f.severity:8s} {f.summary[:100]}")
    print(f"  supply-attribution findings: {len(supply_findings)}")
    print(f"  transition-health findings: {len(transition_findings)}")

    eff_az = EfficiencySequencing()
    efficiency_by_state = {}
    for v in views:
        if v.state_sequence is None:
            continue
        eff = eff_az._efficiency(v, registry.input_supplies(), registry.output_rails())
        for sname, val in eff.items():
            if val is not None:
                efficiency_by_state.setdefault(sname, []).append(val)
    efficiency_summary = {
        sname: {"mean": float(np.mean(vals)), "n": len(vals)}
        for sname, vals in efficiency_by_state.items()
    }
    print(f"  per-state efficiency (mean P_out/P_in): {efficiency_summary}")

    print(f"\n{'=' * 60}\n  5. Final control-logic-skeleton codegen\n{'=' * 60}")
    codegen = FSMCodeGenerator(spec_kg=kg, ip_type=args.ip_type)
    va_code = codegen.generate_veriloga(
        detector.state_defs,
        transitions,
        kg.ports,
        output_equations=output_equations,
        equation_parameters=equation_parameters,
    )
    sv_code = codegen.generate_systemverilog(detector.state_defs, transitions)
    ip = args.ip_type.lower()
    va_path = os.path.join(args.output_dir, f"{ip}_fsm_skeleton.vams")
    sv_path = os.path.join(args.output_dir, f"{ip}_fsm_skeleton.sv")
    with open(va_path, "w") as f:
        f.write(va_code)
    with open(sv_path, "w") as f:
        f.write(sv_code)

    # Confirm — don't assume — that the equations actually landed in the
    # generated text, and report exactly what's there.
    n_states_with_eq = len(output_equations)
    embedded_ok = (
        n_states_with_eq > 0 and "Fitted per-state output equations" in va_code
    )
    print(
        f"\n  Analog skeleton output-driving equations: "
        f"{'EMBEDDED' if embedded_ok else 'NOT EMBEDDED'}"
    )
    print(f"    states: {n_states_with_eq}   outputs: {output_names}")
    print(
        f"    equation source: {'PySR (--include_symbolic)' if args.include_symbolic else 'linear'}"
    )

    # ── Reports ──────────────────────────────────────────────────────────
    model_comparison = {
        "blut_path": blut_path,
        "good_corners": len(good_qids),
        "total_corners": len(corners),
        "meta_key_kind": data.get("meta_key_kind", {}),
        "feature_names": feature_names,
        "output_names": output_names,
        "equation_source": "pysr" if args.include_symbolic else "linear",
        "equation_parameters": equation_parameters,
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
    }
    _write_json(
        os.path.join(args.output_dir, "model_comparison.json"), model_comparison
    )
    with open(os.path.join(args.output_dir, "model_comparison.md"), "w") as f:
        model_cols = sorted({m for v in state_metrics.values() for m in v})
        L = [
            "# Phase 2 Per-State Model Comparison",
            "",
            f"BLUT: `{blut_path}`  |  good corners: {len(good_qids)}/{len(corners)}  "
            f"|  equation source: `{'pysr' if args.include_symbolic else 'linear'}`",
            "",
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
            "| state | output | R2 | equation |",
            "|---|---|---|---|",
        ]
        for sid, eqs in equation_info.items():
            sname = detector.state_defs[sid]["name"]
            for out_name, info in eqs.items():
                r2_str = f"{info['r2']:.3f}" if info["r2"] is not None else "n/a"
                eq_str = (info["equation"] or "FAILED")[:120]
                L.append(f"| {sname} | {out_name} | {r2_str} | `{eq_str}` |")
        f.write("\n".join(L) + "\n")

    current_insights = {
        "mux_findings": [f.as_row() for f in mux_findings],
        "supply_findings": [f.as_row() for f in supply_findings],
        "transition_findings": [f.as_row() for f in transition_findings],
        "efficiency_by_state": efficiency_summary,
    }
    _write_json(
        os.path.join(args.output_dir, "current_insights_report.json"), current_insights
    )
    with open(os.path.join(args.output_dir, "current_insights_report.md"), "w") as f:
        L = [
            "# Current/Voltage-Backed Insights",
            "",
            "## Mux / supply-select verification",
            "",
        ]
        for fnd in mux_findings:
            L.append(f"- **{fnd.severity}** {fnd.summary}")
        L += ["", "## Per-state supply attribution", ""]
        for fnd in supply_findings:
            L.append(f"- {fnd.summary}")
        L += ["", "## Transition health (shoot-through / inrush)", ""]
        for fnd in transition_findings:
            L.append(f"- {fnd.summary}")
        L += [
            "",
            "## Per-state efficiency (mean P_out/P_in)",
            "",
            "| state | efficiency | n |",
            "|---|---|---|",
        ]
        for sname, s in efficiency_summary.items():
            L.append(f"| {sname} | {s['mean']:.3f} | {s['n']} |")
        f.write("\n".join(L) + "\n")

    # ── Pipeline structure summary — what ran, in what order, feeding what ──
    manifest_path = os.path.join(args.output_dir, "manifest.md")
    with open(manifest_path, "w") as f:
        L = [
            "# example11 Run Manifest — Pipeline Structure",
            "",
            "```",
            "1. Load per_corner_correlation.json -> filter good corners",
            "2. Global FSM (SignalCapture + FSMStateDetector + "
            "TransitionLearner + FSMValidator) -> state_defs, transitions",
            "3. Phase2SimAugmented.build_dataset_from_blut(run_ids=good_qids)",
            "   -> corner-and-state-labeled X, Y, feature_names",
            "4. Per state: GPR/SMT"
            + ("/PINN" if "pinn" in requested_models else "")
            + " (informational) + linear"
            + ("/PySR" if args.include_symbolic else "")
            + " equation (embedded)",
            "5. core/current_insights: mux/supply/transition/efficiency findings",
            "6. FSMCodeGenerator.generate_veriloga(output_equations=...) "
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
            f"Equation source: {'pysr' if args.include_symbolic else 'linear'}",
            "",
            f"**Analog skeleton output-driving equations: "
            f"{'EMBEDDED' if embedded_ok else 'NOT EMBEDDED'}**",
            f"  states with equations: {n_states_with_eq}",
            f"  outputs: {output_names}",
            "",
            "## Output files",
            "",
            f"- `{va_path}` — final Verilog-A (FSM + self-checks + output equations)",
            f"- `{sv_path}` — final SystemVerilog control skeleton",
            f"- `{os.path.join(args.output_dir, 'model_comparison.md')}` (+ .json)",
            f"- `{os.path.join(args.output_dir, 'current_insights_report.md')}` (+ .json)",
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
        f"  Current insights      {os.path.join(args.output_dir, 'current_insights_report.md')} (+ .json)"
    )
    print(f"  Manifest / structure  {manifest_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
