#!/usr/bin/env python3
"""
examples/example10_final_fsm_from_good_corners.py — the next pipeline step
after examples/example9_per_corner_fsm_correlate.py: take only the corners
example9 did NOT flag as outliers, combine them into one FSM-derivation
dataset, and run the normal (global, boundary-mask-aware) FSM auto-
derivation over that clean subset to produce the final, trustworthy
output/fsm_final/<ip>_fsm.vams / .sv.

Excluded (outlier-flagged) corners are never silently dropped — this
script always writes a manifest of what went in and what was left out
(and why), so exclusion is auditable rather than a black box.

Depends on example9's JSON report (per_corner_correlation.json) for the
outlier/good judgment per (run_id, corner_id) — run example9 first. This
script does not re-derive outliers itself; it only consumes the verdict.

Uses SignalCapture.load_from_blut's list-of-run_ids form (added
alongside this script) to load exactly the good corners' data,
concatenated with the same NaN-safe cross-run alignment and
get_boundary_mask() seam-avoidance as any other multi-run BLUT load — so
the excluded corners never contribute a single sample, and the included
corners' concatenation seams are never misread as real FSM transitions.

Run:  uv run examples/example10_final_fsm_from_good_corners.py \\
          [--correlation_json output/per_corner_correlation.json] \\
          [--blut_path PATH] [--spec_json PATH] [--signal_map_json PATH] \\
          [--fsm_strategy hybrid] [--fsm_tree_depth 4] \\
          [--ip_type LDO] [--output_dir output/fsm_final]
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

ROOT = os.path.join(os.path.dirname(__file__), "..")
CFG = os.path.join(ROOT, "configs")


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
    ap.add_argument("--output_dir", default=os.path.join(ROOT, "output", "fsm_final"))
    return ap


def main() -> int:
    args = build_parser().parse_args()

    with open(args.correlation_json, encoding='utf-8') as f:
        correlation = json.load(f)

    blut_path = args.blut_path or correlation["blut_path"]
    corners = correlation["corners"]
    good = [r for r in corners if not r["outlier"] and not r["fsm_generation_failed"]]
    excluded = [r for r in corners if r["outlier"] or r["fsm_generation_failed"]]

    print(f"\n{'=' * 60}\n  Final FSM from good corners\n{'=' * 60}")
    print(f"  correlation source: {args.correlation_json}")
    print(f"  blut source:        {blut_path}")
    print(
        f"  corners: {len(corners)} total, {len(good)} good, {len(excluded)} excluded"
    )

    if not good:
        print(
            "  FAIL: no non-outlier corners available — cannot build a "
            "final FSM. Check the correlation report; every corner was "
            "flagged."
        )
        return 1

    import main as framework_main
    from core.fsm.signal_capture import SignalCapture
    from core.fsm.state_detector import FSMStateDetector
    from core.fsm.transition_learner import TransitionLearner
    from core.fsm.fsm_codegen import FSMValidator, FSMCodeGenerator

    kg = framework_main._build_kg(args)
    sm = framework_main._resolve_signal_map(args)

    good_qids = [r["qid"] for r in good]
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
    report = validator.validate(detector.state_defs, transitions, ip_type=args.ip_type)
    print(f"\n  [Final FSM] Validation: {report}")

    codegen = FSMCodeGenerator(spec_kg=kg, ip_type=args.ip_type)
    va_code = codegen.generate_veriloga(detector.state_defs, transitions, kg.ports)
    sv_code = codegen.generate_systemverilog(detector.state_defs, transitions)

    os.makedirs(args.output_dir, exist_ok=True)
    ip = args.ip_type.lower()
    va_path = os.path.join(args.output_dir, f"{ip}_fsm_final.vams")
    sv_path = os.path.join(args.output_dir, f"{ip}_fsm_final.sv")
    with open(va_path, "w", encoding='utf-8') as f:
        f.write(va_code)
    with open(sv_path, "w", encoding='utf-8') as f:
        f.write(sv_code)

    # ── Manifest: what went in, what was left out and why ──────────────
    manifest_path = os.path.join(args.output_dir, "fsm_final_manifest.md")
    L = [
        "# Final FSM — Included/Excluded Corner Manifest",
        "",
        f"BLUT source: `{blut_path}`  |  strategy: `{args.fsm_strategy}`",
        "",
        f"Included: {len(good)}/{len(corners)} corners  |  "
        f"Excluded: {len(excluded)}/{len(corners)} corners",
        "",
        f"Final validation: reachability={report.reachability}, "
        f"completeness={report.completeness}, "
        f"determinism={report.determinism}, "
        f"speckg_coverage={report.speckg_coverage:.1%}",
        "",
        f"Final states ({len(detector.state_defs)}): "
        f"{', '.join(d['name'] for d in detector.state_defs.values())}",
        "",
        f"Final transitions: {len(transitions)}",
        "",
    ]
    L += ["## Included corners", "", "| run_id | corner_id |", "|---|---|"]
    for r in sorted(good, key=lambda x: (x["run_id"], x["corner_id"])):
        L.append(f"| {r['run_id']} | {r['corner_id'] or '-'} |")
    L += [
        "",
        "## Excluded corners",
        "",
        "| run_id | corner_id | reasons |",
        "|---|---|---|",
    ]
    for r in sorted(excluded, key=lambda x: (x["run_id"], x["corner_id"])):
        reasons = "; ".join(r.get("outlier_reasons", [])) or (
            "FSM generation failed" if r["fsm_generation_failed"] else "-"
        )
        L.append(f"| {r['run_id']} | {r['corner_id'] or '-'} | {reasons} |")
    L.append("")
    with open(manifest_path, "w", encoding='utf-8') as f:
        f.write("\n".join(L))

    print(f"\n{'=' * 60}\n  OUTPUT FILES")
    print(f"{'=' * 60}")
    print(f"  Final Verilog-A       {va_path}")
    print(f"  Final SystemVerilog   {sv_path}")
    print(f"  Manifest              {manifest_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
