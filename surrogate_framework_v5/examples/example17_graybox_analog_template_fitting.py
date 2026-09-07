#!/usr/bin/env python3
"""
examples/example17_graybox_analog_template_fitting.py — same pipeline as
example16_node_gradient_fix_modeling.py (kept exactly as-is, for
reference — every step below through the differential/black-box
modeling and codegen is unchanged from it, reusing its imports), adding
ONE new step: item 6's gray-box question, implemented (not just
assessed).

── Round-2 fixes, from observations running this script for real ──────
  1. EN_LDO is no longer a MANDATORY literal --blut_input_signals entry
     for the gray-box step. It is a digital control signal that decides
     WHICH FSM STATE the device is in; it has no graded influence on the
     analog dynamics WITHIN a state, so hard-requiring a specific pin
     mapping for it was the wrong rigidity. The enable trace the
     template actually needs is now DERIVED from the already-detected
     FSM state sequence (any state whose name matches
     --disabled_state_names, default 'DISABLED,SHUTDOWN', is en=0,
     everything else en=1) — see _infer_activity_masks. --en_signal is
     now optional (default '') and, if given, is only cross-checked
     against the derived trace, never required.
  2. Per-corner independent fits were wasteful and less accurate when
     process genuinely doesn't vary run-to-run in the loaded capture —
     and wrong in spirit even when it does, since Kp/Vth_p/lambda_p
     etc. are process properties, not per-run ones. Runs are now GROUPED
     by their real process label (parsed straight from each run's BLUT
     meta string, the same 'corner' key target_encode_categorical_meta
     already classifies as categorical — see _group_qids_by_process),
     and ONE pooled SingleCornerFitter.fit() call runs PER PROCESS,
     combining every grouped run's DC points and transient records into
     a single, better-conditioned fit (more data, one parameter vector).
     When only one process is present, this collapses to exactly one
     fit for the whole capture, per the request ("process doesn't vary
     ... simplify"). Voltage and temperature are deliberately NOT
     separate LUT axes: the template already models vin continuously
     through its own ODEs/dc_solve (that's what "common modeling
     strategy" means here), so a run at 4.5V and one at 5.5V of the SAME
     process are pooled into the SAME fit rather than split further.
     Each process's fitted vector becomes a genuine LUT entry — persisted
     via THIS REPO's own PVT parameter store (core.pvt.save_param_store/
     StateParamSet, core/pvt/param_blut_store.py — the same mechanism
     core/pvt/param_lut.py's LutParamProvider and
     test_param_providers_roundtrip_and_agree_at_training_corners
     already exercise), plus a plain JSON mirror for human inspection.
  3. The fitted analog structure is now an actual OUTPUT ARTIFACT, not
     just a report: each process's fitted parameters are rendered via
     LdoPmosTemplate.emit_veriloga_core() (already existed, unused by
     example16/its ancestors) into its own .vams file — real ODEs
     (immediate output-drop feedback, real transient dynamics), not a
     per-state static polynomial. Two more structural realities are now
     accounted for rather than assumed away:
       - Bypass mode (EXT_VDD_1V2 switched straight to VDD_1V2, mux'd
         with the internal LDO): any state matching --bypass_state_names
         (default 'BYPASS') is EXCLUDED from the gray-box fit entirely —
         during bypass the output is driven by the external switch, not
         by this template's ODEs, so including those samples would
         corrupt the fit. Excluding rows can't simply drop them from a
         transient array (that would silently splice two disjoint time
         windows together and integrate across the gap) — each corner's
         segment is split into its maximal BYPASS-free contiguous
         stretches (_contiguous_true_runs) and each stretch becomes its
         own transient record.
       - "Wherever output is active the LDO circuit would be active":
         when no --disabled_state_names pattern matches ANY detected
         state name (a real possibility if this IP's states are named
         differently), the enable trace falls back to observed VDD_1V2
         activity (--vout_active_frac of the corner's own peak |vout|)
         instead of guessing.
     Supply muxing (which rail actually feeds the LDO, decided by FSM +
     current consumption) is a REAL, separate mechanism this script does
     not yet auto-select per state — core/current_insights already has
     the mux-verification/supply-attribution analyzers example12 used
     (CurrentRegistry, build_run_views, run_analyzers); wiring their
     findings into a per-state --vin_signal choice is a natural next
     step, flagged here rather than guessed at without data to validate
     against (same "state, don't guess" discipline as the rest of this
     script's assumption-flagging).

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

uv run examples/example17_graybox_analog_template_fitting.py --correlation_json output_fsm_correlation_2/per_corner_correlation.json --blut_path blut_files/regression_multi_corner_sref_ldo.bin --signal_map_json configs/signal_map_ldo.json --fsm_strategy hybrid --fsm_tree_depth 4 --ip_type LDO --blut_input_signals VPWR,VREF,FUN_DC,V_SUPPLY,MOST_POS --blut_output_signals VDD_1V2 --models gpr,smt --vin_signal VPWR --hp_signal HIGH_POWER_MODE --vout_signal VDD_1V2 --vfb_voltage_signal VFB --vfb_current_signal VFB_I --vref_signal VREF --iload_current_signal VDD_1V2_I --regulation_state_name REGULATION --max_graybox_corners 8 --graybox_max_dc_points 6 --graybox_max_transient_samples 2000 --graybox_de_maxiter 12 --graybox_de_popsize 8 --enable_nn_residual --include_integral_features --smoothing_window 0 --evaluate_denoising --equation_degree 2 --include_symbolic --models gpr,smt,pinn,node --pinn_epochs 30 --node_epochs 20 --min_state_samples 30 --max_state_samples 200000 --max_gpr_smt_samples 3000 --max_pysr_samples 5000 --output_dir output_new/ex17_graybox_update_1
uv run examples/example17_graybox_analog_template_fitting.py --correlation_json output_fsm_correlation_2/per_corner_correlation.json --blut_path blut_files/regression_multi_corner_sref_ldo.bin --signal_map_json configs/signal_map_ldo.json --fsm_strategy hybrid --fsm_tree_depth 4 --ip_type LDO --blut_input_signals VPWR,VREF,FUN_DC,V_SUPPLY,MOST_POS --blut_output_signals VDD_1V2 --models gpr,smt --vin_signal VPWR --hp_signal HIGH_POWER_MODE --vout_signal VDD_1V2 --vfb_voltage_signal VFB --vfb_current_signal VFB_I --vref_signal VREF --iload_current_signal VDD_1V2_I --regulation_state_name REGULATION --max_graybox_corners 8 --graybox_max_dc_points 6 --graybox_max_transient_samples 2000 --graybox_de_maxiter 12 --graybox_de_popsize 8 --enable_nn_residual --include_integral_features --smoothing_window 0 --evaluate_denoising --equation_degree 2 --include_symbolic --models gpr,smt,pinn,node --pinn_epochs 30 --node_epochs 20 --min_state_samples 30 --max_state_samples 200000 --max_gpr_smt_samples 3000 --max_pysr_samples 5000 --output_dir output_new/ex17_graybox_update_2_round_3
uv run examples/example17_graybox_analog_template_fitting.py --blut_path blut_files/regression_multi_corner_sref_ldo.bin --signal_map_json configs/signal_map_ldo.json --fsm_strategy hybrid --fsm_tree_depth 4 --ip_type LDO --blut_input_signals VPWR,VREF,FUN_DC,V_SUPPLY,MOST_POS --blut_output_signals VDD_1V2 --vin_signal VPWR --hp_signal HIGH_POWER_MODE --vout_signal VDD_1V2 --vfb_voltage_signal VFB --vfb_current_signal VFB_I --vref_signal VREF --iload_current_signal VDD_1V2_I --regulation_state_name REGULATION --max_graybox_corners 8 --graybox_max_dc_points 6 --graybox_max_transient_samples 2000 --graybox_de_maxiter 12 --graybox_de_popsize 8 --enable_nn_residual --include_integral_features --smoothing_window 0 --evaluate_denoising --equation_degree 2 --include_symbolic --models gpr,smt,pinn,node --pinn_epochs 30 --node_epochs 20 --min_state_samples 30 --max_state_samples 200000 --max_gpr_smt_samples 3000 --max_pysr_samples 5000 --output_dir output_new/ex17_graybox_new_bin_round_3

"""

import argparse
import dataclasses
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
)
from example15_curated_inputs_full_data_modeling import (
    _subcap,
    _add_derivative_integral_features,
)

ROOT = os.path.join(os.path.dirname(__file__), "..")
CFG = os.path.join(ROOT, "configs")

IMPLEMENTED_MODELS = ("gpr", "smt", "pinn", "node")


def build_parser():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--correlation_json",
        default="",
        help="OPTIONAL (round-3 fix, item 2): if given and the file "
        "exists, it is reused as-is (avoids recomputing an expensive "
        "per-corner FSM pass against an unchanged BLUT). Leave empty "
        "(default) and the per-corner correlation is computed "
        "internally from --blut_path/--signal_map_json/--spec_json — "
        "no external example9 pre-step required — and cached to "
        "<output_dir>/per_corner_correlation.json for inspection/reuse.",
    )
    ap.add_argument(
        "--blut_path",
        default=None,
        help="Required unless --correlation_json is given (see above).",
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

    # ── Gray-box (item 6) ───────────────────────────────────────────────
    ap.add_argument(
        "--vin_signal",
        default="VPWR",
        help="Which --blut_input_signals entry is the "
        "template's vin (pass-device source).",
    )
    ap.add_argument(
        "--en_signal",
        default="",
        help="OPTIONAL cross-check only (round-2 fix — see "
        "module docstring point 1): the enable trace the "
        "template actually uses is DERIVED from the FSM "
        "state sequence via --disabled_state_names, not "
        "from a literal pin. If given and present in "
        "--blut_input_signals, its disagreement rate "
        "against the derived trace is reported, nothing "
        "more.",
    )
    ap.add_argument(
        "--disabled_state_names",
        default="DISABLED,SHUTDOWN",
        help="Comma list of FSM state-name substrings (case-"
        'insensitive) treated as "LDO analog core off" '
        "for the derived enable trace.",
    )
    ap.add_argument(
        "--bypass_state_names",
        default="BYPASS",
        help="Comma list of FSM state-name substrings marking "
        "bypass mode (EXT_VDD_1V2 switched straight to "
        "the output) — those samples are excluded from "
        "the gray-box fit entirely, never spliced across.",
    )
    ap.add_argument(
        "--vout_active_frac",
        type=float,
        default=0.1,
        help="Fallback enable heuristic ONLY used when no "
        "--disabled_state_names pattern matches any "
        "detected state name: a sample counts as "
        '"active" when |vout| exceeds this fraction of '
        "the corner's own observed peak |vout|.",
    )
    ap.add_argument(
        "--max_graybox_processes",
        type=int,
        default=8,
        help="Cap on how many distinct processes get a pooled gray-box fit.",
    )
    ap.add_argument(
        "--hp_signal",
        default="HIGH_POWER_MODE",
        help="Which --blut_input_signals entry is the "
        "template's HIGH_POWER_MODE hp hook (optional "
        "— ignored if not present in --blut_input_signals).",
    )
    ap.add_argument(
        "--vout_signal",
        default="",
        help="Which --blut_output_signals entry is the "
        "regulated output (vout). Defaults to the FIRST "
        "entry in --blut_output_signals.",
    )
    ap.add_argument(
        "--vfb_voltage_signal",
        default="VFB",
        help="Feedback-divider-tap VOLTAGE signal (Tier 1). "
        "Empty disables; falls back to Tier 2/3 if this "
        "name does not resolve against the BLUT/signal_map.",
    )
    ap.add_argument(
        "--vfb_current_signal",
        default="VFB_I",
        help='Feedback-divider-branch CURRENT signal — "the '
        'current flowing through the VFB pin" from the '
        "request. Empty disables (falls back to Tier 3).",
    )
    ap.add_argument(
        "--vref_signal",
        default="VREF",
        help="Directly-measured bandgap reference (Tier 2 "
        "only, used when --vfb_voltage_signal does not "
        "resolve). Empty falls back to --v_ref_nominal.",
    )
    ap.add_argument(
        "--v_ref_nominal",
        type=float,
        default=0.9,
        help="Assumed V_ref (Tier 2 fallback, or Tier 3) when "
        "neither --vfb_voltage_signal nor --vref_signal "
        "resolves — matches LDO_PMOS_MANIFEST's own "
        "nominal default.",
    )
    ap.add_argument(
        "--iload_current_signal",
        default="",
        help="Load-current signal for the gray-box DC/"
        "transient records. Empty ASSUMES iload=0 "
        "(unloaded/light-load corner) — stated here "
        "since it is a real added assumption when unset.",
    )
    ap.add_argument(
        "--regulation_state_name",
        default="",
        help="FSM state name substring marking settled closed-"
        "loop regulation (Tier 2's v_fb~=V_ref window, and "
        "one of the two DC-point sources — round-3 fix, "
        "item 1). Empty auto-matches any state name "
        'containing "REGULATION".',
    )
    ap.add_argument(
        "--dropout_state_name",
        default="",
        help="Round-3 fix, item 1: FSM state name substring "
        "marking dropout (vin close to vout, pass device in "
        "triode). Regulation-only DC points cannot identify "
        "Kp/Vth_p/lambda_p (the loop compensates for pass-"
        "device changes almost perfectly in regulation — "
        "confirmed on a synthetic check where these stayed "
        "pinned at their manifest defaults with regulation-"
        "only data); DC points are now ALSO drawn from this "
        "state when present, which is where those parameters "
        "actually show up in vout. Empty auto-matches any "
        'state name containing "DROPOUT".',
    )
    ap.add_argument(
        "--max_graybox_corners",
        type=int,
        default=8,
        help="Cap on how many runs get POOLED into each "
        "process's single gray-box fit (round-2: fitting "
        "moved from per-run to per-process — see module "
        "docstring point 2). Each process's pooled fit "
        "still runs one differential-evolution + LSODA-"
        "integrated transient search — not cheap.",
    )
    ap.add_argument(
        "--graybox_max_dc_points",
        type=int,
        default=6,
        help="Quasi-DC points sampled per corner from its "
        "regulation-state dwell (evenly spaced) for the "
        "DC fitting stage.",
    )
    ap.add_argument(
        "--graybox_max_transient_samples",
        type=int,
        default=2000,
        help="Uniform-stride decimation cap on each corner's "
        "transient record before handing it to the "
        "fitter — LSODA-integrating the full capture "
        "every DE iteration is not needed for a good fit "
        "and is not free either.",
    )
    ap.add_argument("--graybox_de_maxiter", type=int, default=12)
    ap.add_argument("--graybox_de_popsize", type=int, default=8)
    ap.add_argument(
        "--enable_nn_residual",
        action="store_true",
        help="Passthrough to SingleCornerFitter — an opt-in "
        "small residual net on top of the physical fit, "
        "capped at <=10%% of the RHS magnitude.",
    )
    ap.add_argument(
        "--skip_graybox",
        action="store_true",
        help="Skip Step 3 entirely and behave exactly like "
        "example16 (useful if you only want the black-"
        "box/differential-equation pipeline).",
    )

    ap.add_argument("--include_integral_features", action="store_true")
    ap.add_argument("--smoothing_window", type=int, default=0)
    ap.add_argument("--evaluate_denoising", action="store_true")
    ap.add_argument("--equation_degree", type=int, default=2)
    ap.add_argument("--include_symbolic", action="store_true")
    ap.add_argument(
        "--models",
        default="gpr,smt,pinn,node",
        help="comma list from gpr, smt, pinn, node",
    )
    ap.add_argument("--pinn_epochs", type=int, default=30)
    ap.add_argument("--node_epochs", type=int, default=20)
    ap.add_argument("--min_state_samples", type=int, default=30)
    ap.add_argument("--max_state_samples", type=int, default=200000)
    ap.add_argument("--max_gpr_smt_samples", type=int, default=3000)
    ap.add_argument("--max_pysr_samples", type=int, default=5000)
    ap.add_argument(
        "--output_dir", default=os.path.join(ROOT, "output", "phase2_graybox_v1")
    )
    return ap


def _write_json(path, obj):
    with open(path, "w") as f:
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
    return {
        "Rf1": float(np.median(rf1[ok])),
        "Rf2": float(np.median(rf2[ok])),
        "n_samples": int(ok.sum()),
        "n_total": int(len(vout)),
        "tier": 1,
    }


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
    return {
        "Rf1": float(np.median(rf1[ok])),
        "Rf2": float(np.median(rf2[ok])),
        "n_samples": int(ok.sum()),
        "n_total": int(len(vout)),
        "tier": 2,
    }


def _identify_rf_for_rows(
    row_mask,
    Y_np_full,
    vout_idx,
    vfb_idx,
    ifb_idx,
    vref_idx,
    have_vfb_v,
    have_vfb_i,
    have_vref,
    reg_sid,
    seq,
    args,
):
    """Tier-1/2/3 Rf1/Rf2 identification RESTRICTED to `row_mask` — round-
    3 fix, item 1: previously computed ONCE globally (pooled across every
    process), which silently forced identical Rf1/Rf2 onto every
    process's fit regardless of whether the real resistors actually
    shift with process corner. Called once per process now (with that
    process's own row mask), so a genuine per-process difference (or
    genuine absence of one — resistor sheet-rho often has its OWN,
    separate PDK corner axis from the ff/ss/tt transistor corners, so
    identical Rf1/Rf2 across process CAN be the physically correct
    answer) is something the data shows, not something this script
    imposes by sharing one fit across every process."""
    rf_result = None
    if have_vfb_v and have_vfb_i:
        rf_result = _identify_rf_tier1(
            Y_np_full[row_mask, vout_idx],
            Y_np_full[row_mask, vfb_idx],
            Y_np_full[row_mask, ifb_idx],
        )
    if rf_result is None and have_vfb_i and reg_sid is not None:
        reg_mask = row_mask & (seq == reg_sid)
        if reg_mask.any():
            v_ref_used = args.v_ref_nominal
            v_ref_source = f"--v_ref_nominal={args.v_ref_nominal:g} (assumed)"
            if have_vref:
                v_ref_used = float(np.median(Y_np_full[reg_mask, vref_idx]))
                v_ref_source = (
                    f"measured {args.vref_signal} median over regulation-state samples"
                )
            rf_result = _identify_rf_tier2(
                Y_np_full[reg_mask, vout_idx], Y_np_full[reg_mask, ifb_idx], v_ref_used
            )
            if rf_result:
                rf_result["v_ref_used"] = v_ref_used
                rf_result["v_ref_source"] = v_ref_source
    return rf_result


def _parameter_sensitivity_map(
    template, params, vin_nom=5.0, iload_nom=0.05, rel_step=0.01
):
    """Round-3 fix, item 4a: WHICH fitted parameter drives WHICH
    observable behavior — a genuine, data-grounded "engineering insight"
    mechanism (computed, not asserted), reusing the template's own
    dc_solve/small_signal (the same views spec_compliance_table already
    uses) plus a centered finite-difference ELASTICITY (%behavior change
    per %parameter change), which keeps parameters of very different
    natural units/scales (Ohms, Farads, Amps, dimensionless) comparable
    in one table without ad-hoc normalization.

    Behaviors tracked: DC output voltage, dropout margin, quiescent
    current, PSRR@1kHz, output impedance@1kHz, phase margin — every one
    already computable from the template as-is. Returns
    {'base_behaviors': {...}, 'elasticities': {param: {behavior: value}}}."""

    def _behaviors(p):
        op = template.dc_solve(p, vin_nom, iload_nom)
        ss = template.small_signal(p, op)
        f = ss["freqs"]
        psrr_1k = float(ss["psrr_db"][np.argmin(np.abs(f - 1e3))])
        zout_1k = float(ss["zout"][np.argmin(np.abs(f - 1e3))])
        T = ss["loop_gain"]
        idx = np.where(np.abs(T) < 1.0)[0]
        pm = float(180 + np.angle(T[idx[0]], deg=True)) if len(idx) else float("nan")
        return {
            "vout_dc": op["vout"],
            "dropout_margin": op["dropout_margin"],
            "iq": op["iq"],
            "psrr_1kHz_dB": psrr_1k,
            "zout_1kHz": zout_1k,
            "phase_margin_deg": pm,
        }

    try:
        base = _behaviors(params)
    except Exception:
        return {"base_behaviors": {}, "elasticities": {}}

    elasticities = {}
    for name, val in params.items():
        if abs(val) < 1e-30:
            continue
        p_hi = dict(params)
        p_hi[name] = val * (1 + rel_step)
        p_lo = dict(params)
        p_lo[name] = val * (1 - rel_step)
        try:
            hi = _behaviors(p_hi)
            lo = _behaviors(p_lo)
        except Exception:
            continue
        row = {}
        for beh, b0 in base.items():
            if not np.isfinite(b0) or abs(b0) < 1e-30:
                continue
            dbeh = hi.get(beh, np.nan) - lo.get(beh, np.nan)
            if not np.isfinite(dbeh):
                continue
            row[beh] = float((dbeh / (2 * rel_step)) / b0)
        if row:
            elasticities[name] = row
    return {"base_behaviors": base, "elasticities": elasticities}


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
        if spec.name == "Rf1":
            new_specs.append(
                dataclasses.replace(
                    spec,
                    default=rf1,
                    fit_stage="fixed",
                    lo=min(spec.lo, rf1 * 0.5),
                    hi=max(spec.hi, rf1 * 2.0),
                )
            )
        elif spec.name == "Rf2":
            new_specs.append(
                dataclasses.replace(
                    spec,
                    default=rf2,
                    fit_stage="fixed",
                    lo=min(spec.lo, rf2 * 0.5),
                    hi=max(spec.hi, rf2 * 2.0),
                )
            )
        elif spec.name == "V_ref" and v_ref is not None:
            new_specs.append(
                dataclasses.replace(
                    spec, default=float(np.clip(v_ref, spec.lo, spec.hi))
                )
            )
        else:
            new_specs.append(spec)
    manifest = ParamManifest(new_specs)

    class _AnchoredLdoTemplate(LdoPmosTemplate):
        def manifest(self):
            return manifest

    return _AnchoredLdoTemplate()


def _infer_activity_masks(
    seq, state_defs, vout_full, disabled_names, bypass_names, active_frac
):
    """(en_eff, bypass_mask) over the GLOBAL row axis — round-2 fix,
    items 1+3. en_eff: 1.0 where the analog core should be treated as
    enabled. Authoritative source is the already-detected FSM state
    name (never a raw EN_LDO pin, which only matters at the state-
    transition boundary, not continuously inside a state); a state-name-
    activity fallback ("wherever output is active the LDO would be
    active") kicks in ONLY when --disabled_state_names matches nothing
    at all in this capture, so a differently-named IP's states don't
    silently read as permanently-enabled. bypass_mask marks rows to
    EXCLUDE from the gray-box fit outright (see _contiguous_true_runs —
    exclusion must split transient records, not delete-and-splice)."""
    state_names = {sid: d["name"].upper() for sid, d in state_defs.items()}
    disabled_pats = [s.strip().upper() for s in disabled_names.split(",") if s.strip()]
    bypass_pats = [s.strip().upper() for s in bypass_names.split(",") if s.strip()]

    is_disabled_state = np.array(
        [any(p in state_names.get(sid, "") for p in disabled_pats) for sid in seq]
    )
    bypass_mask = np.array(
        [any(p in state_names.get(sid, "") for p in bypass_pats) for sid in seq]
    )

    if disabled_pats and is_disabled_state.any():
        en_eff = (~is_disabled_state).astype(float)
        source = f"FSM state name (matched {disabled_pats})"
    else:
        peak = float(np.max(np.abs(vout_full))) if len(vout_full) else 0.0
        en_eff = (np.abs(vout_full) > active_frac * peak).astype(float)
        source = (
            f"VDD_1V2 output activity fallback (no "
            f"--disabled_state_names pattern matched any detected "
            f"state — peak |vout|={peak:.4g}, threshold="
            f"{active_frac * peak:.4g})"
        )
    return en_eff, bypass_mask, source


def _contiguous_true_runs(mask):
    """[(start, end), ...] half-open index ranges where `mask` is True,
    contiguously — the bypass-exclusion-safe way to carve a corner's
    segment into its BYPASS-free stretches without ever splicing two
    disjoint time windows together (which would integrate across the
    excised gap as if it were continuous)."""
    runs = []
    n = len(mask)
    i = 0
    while i < n:
        if not mask[i]:
            i += 1
            continue
        j = i
        while j < n and mask[j]:
            j += 1
        runs.append((i, j))
        i = j
    return runs


def _group_qids_by_process(data, good_qids, run_boundaries, seq):
    """{process_label: [qid, ...]} — round-2 fix, item 2. Reads the real
    process straight from each run's own BLUT meta string
    (build_dataset_from_blut already returns 'run_meta', one raw meta
    string per ROW, constant within a run — see that method's
    docstring), via the SAME parse_meta_string + 'corner' key
    target_encode_categorical_meta already treats as the categorical
    process axis. No BLUT re-open needed. A capture with no 'corner' key
    at all (process genuinely doesn't vary) collapses to one group,
    'ALL' — exactly the "simplify" outcome requested."""
    from digitwin.blut_reader_ext import parse_meta_string

    bounds = list(run_boundaries) + [len(seq)]
    run_meta = data["run_meta"]
    groups = {}
    for k, qid in enumerate(good_qids):
        meta_str = run_meta[bounds[k]]
        process = parse_meta_string(meta_str).get("corner", "ALL")
        groups.setdefault(process, []).append(qid)
    return groups


def _build_graybox_records_for_run(
    s,
    e,
    sc_time,
    X_np,
    Y_np_full,
    vin_idx,
    hp_idx,
    vout_idx,
    iload_idx,
    seq,
    reg_sid,
    dropout_sid,
    en_eff,
    bypass_mask,
    args,
):
    """(dc_points, transient_records) for ONE run's global rows [s, e) —
    bypass-state rows are excluded by splitting into their maximal
    BYPASS-free contiguous stretches (_contiguous_true_runs), each
    becoming its OWN transient record (never spliced together).

    Round-3 fix, item 1: DC points are now drawn from BOTH the
    regulation state AND (if present) the dropout state. Regulation-only
    DC points were confirmed (synthetic check, tight loop-gain
    compensation) to leave Kp/Vth_p/lambda_p pinned at their manifest
    defaults regardless of their true value — a well-regulated loop
    adjusts the gate to hit v_fb=V_ref almost independently of the pass
    device's exact I-V curve, so vout barely moves when Kp/Vth_p change
    IN REGULATION. Dropout data (vin close to vout, pass device in
    triode) is where those parameters actually show up in vout, so
    omitting it — as the previous version did — was the direct cause of
    those three parameters looking artificially process-invariant."""
    n = e - s
    vin_seg = X_np[s:e, vin_idx]
    hp_seg = X_np[s:e, hp_idx] if hp_idx is not None else np.zeros(n)
    en_seg = en_eff[s:e]
    vout_seg = Y_np_full[s:e, vout_idx]
    iload_seg = Y_np_full[s:e, iload_idx] if iload_idx is not None else np.zeros(n)
    seq_seg = seq[s:e]
    bypass_seg = bypass_mask[s:e]
    t_seg = sc_time[s:e]

    dc_points = []
    transient_records = []
    for a, b in _contiguous_true_runs(~bypass_seg):
        if b - a < 5:
            continue
        t_local = t_seg[a:b] - t_seg[a]
        dc_state_masks = []
        if reg_sid is not None:
            dc_state_masks.append(seq_seg[a:b] == reg_sid)
        if dropout_sid is not None:
            dc_state_masks.append(seq_seg[a:b] == dropout_sid)
        for state_local in dc_state_masks:
            state_idx = np.where(state_local)[0]
            if len(state_idx) == 0:
                continue
            n_pick = min(args.graybox_max_dc_points, len(state_idx))
            picks = state_idx[np.linspace(0, len(state_idx) - 1, n_pick).astype(int)]
            for i in picks:
                dc_points.append(
                    {
                        "vin": float(vin_seg[a:b][i]),
                        "iload": float(iload_seg[a:b][i]),
                        "vout": float(vout_seg[a:b][i]),
                    }
                )

        stride = max(1, (b - a) // max(args.graybox_max_transient_samples, 1))
        sl = slice(0, b - a, stride)
        transient_records.append(
            {
                "t": t_local[sl],
                "inputs": {
                    "vin": vin_seg[a:b][sl],
                    "iload": iload_seg[a:b][sl],
                    "en": en_seg[a:b][sl],
                    "hp": hp_seg[a:b][sl],
                },
                "vout_ref": vout_seg[a:b][sl],
            }
        )
    return dc_points, transient_records


def _ensure_correlation(args, kg, sm):
    """Round-3 fix, item 2 — self-sufficiency: no external example9
    pre-step required. If --correlation_json is given and exists, reuse
    it verbatim (cheap re-runs against an UNCHANGED BLUT shouldn't repeat
    an expensive per-corner FSM pass — favors the long-term iterative-
    agent-loop goal over blind recomputation). Otherwise compute it here,
    reusing example9_per_corner_fsm_correlate's own resolve_corner_dims/
    group_outliers (not reimplemented) against the SAME per-(run_id,
    corner_id) loop that script uses, and cache the result to
    <output_dir>/per_corner_correlation.json so it's inspectable and
    reusable on the next run. The meta-trustworthiness Finding
    diagnostics in example9's own report are intentionally NOT
    duplicated here — this is the internal, load-bearing subset
    (outlier/fsm_generation_failed per qid) this script actually
    consumes, not a replacement for example9's own standalone report."""
    if args.correlation_json and os.path.exists(args.correlation_json):
        with open(args.correlation_json) as f:
            return json.load(f)

    if not args.blut_path:
        raise ValueError(
            "--blut_path is required when --correlation_json is not "
            "given (correlation is now computed internally — see "
            "module docstring item 2)."
        )

    print(
        f"\n{'=' * 60}\n  0. Per-corner FSM correlation (self-sufficient — "
        f"no --correlation_json given)\n{'=' * 60}"
    )
    from example9_per_corner_fsm_correlate import resolve_corner_dims, group_outliers
    from digitwin.blut_reader_ext import open_blut
    from core.fsm.signal_capture import SignalCapture
    from core.fsm.state_detector import FSMStateDetector
    from core.fsm.transition_learner import TransitionLearner
    from core.fsm.fsm_codegen import FSMValidator

    blut = open_blut(args.blut_path)
    run_pairs = [(rid, cid) for rid, cmap in blut.runs.items() for cid in cmap.keys()]
    if not run_pairs:
        raise ValueError(f"{args.blut_path}: no runs found")

    signal_map_size = len(sm.entries) if sm is not None else 0
    rows = []
    for rid, cid in run_pairs:
        qid = rid if not cid else f"{rid}@{cid}"
        run_meta_obj = blut.runs[rid][cid]
        sc = SignalCapture(spec_kg=kg)
        sc.load_from_blut(args.blut_path, run_id=qid, signal_map=sm)
        n_t = len(sc.time)
        lm, ln, _ = sc.get_logic_signal_matrix()
        om, on, _ = sc.get_output_signal_matrix()
        af = sc.get_analog_features(n_windows=min(10, max(2, n_t // 5)))
        detector = FSMStateDetector(strategy=args.fsm_strategy, spec_kg=kg)
        try:
            seq = detector.detect(lm, ln, af, output_matrix=om, output_names=on)
            learner = TransitionLearner(fsm_tree_depth=args.fsm_tree_depth)
            transitions = learner.learn(
                seq, lm, ln, detector.state_defs, boundary_mask=None
            )
            validator = FSMValidator(spec_kg=kg)
            report = validator.validate(
                detector.state_defs, transitions, ip_type=args.ip_type
            )
            failed = False
        except Exception as e:
            print(f"  {qid}: FSM generation failed — {e}")
            report = None
            failed = True

        dims, dims_source, meta_dict, cid_dict = resolve_corner_dims(
            run_meta_obj.meta, cid
        )
        row = {
            "run_id": rid,
            "corner_id": cid,
            "qid": qid,
            "dims": dims,
            "dims_source": dims_source,
            "n_signals": run_meta_obj.n_signals,
            "signal_completeness_pct": (
                round(100.0 * run_meta_obj.n_signals / signal_map_size, 1)
                if signal_map_size
                else None
            ),
            "ntime": run_meta_obj.ntime,
            "meta_raw": run_meta_obj.meta,
            "fsm_generation_failed": failed,
            "n_states_detected": len(detector.state_defs) if not failed else 0,
            "state_names": (
                [d["name"] for d in detector.state_defs.values()] if not failed else []
            ),
            "reachability": report.reachability if report else False,
            "completeness": report.completeness if report else False,
            "determinism": report.determinism if report else False,
            "speckg_coverage": round(report.speckg_coverage, 4) if report else 0.0,
            "missing_states": list(report.missing_states) if report else [],
        }
        rows.append(row)
        print(
            f"  {qid:50s} n_signals={row['n_signals']:3d} "
            f"states={row['n_states_detected']:2d}"
        )

    group_outliers(rows)
    correlation = {
        "blut_path": args.blut_path,
        "fsm_strategy": args.fsm_strategy,
        "corners": rows,
    }
    os.makedirs(args.output_dir, exist_ok=True)
    corr_path = os.path.join(args.output_dir, "per_corner_correlation.json")
    with open(corr_path, "w") as f:
        json.dump(correlation, f, indent=2, default=str)
    n_outliers = sum(1 for r in rows if r["outlier"])
    print(
        f"  computed correlation for {len(rows)} corner(s), "
        f"{n_outliers} flagged outlier(s) — cached to {corr_path}"
    )
    return correlation


def _generate_top_level_wrapper(
    ip,
    process,
    va_path,
    core_path,
    vin_ident,
    vout_ident,
    gnd_ident,
    en_ident,
    hp_ident,
    embedded_ok,
    output_dir,
):
    """Item 3: instantiate BOTH the FSM control skeleton and the fitted
    gray-box analog core in one top-level module — the "complete analog
    model" integration the request asked for (with the usage also
    described in comments below, per the request's own offered
    alternative).

    Net names on the FSM-skeleton side are the SAME sanitized (_vid)
    identifiers this pipeline already used to REQUEST vin/vout/gnd/en/hp
    — not re-parsed from the generated .vams text, since
    FSMCodeGenerator.generate_veriloga's own port list is built from
    exactly these names. If a real run's skeleton ends up NOT exposing
    one of them as a port (possible depending on which kg.ports/guard
    signals were actually detected), that one wrapper connection is
    simply a dangling net — verify against the skeleton's own port list
    before simulating (noted in the header comment). This wrapper also
    only connects the 5 shared analog nets explicitly, by named
    association — the FSM skeleton's other ports (additional guard
    signals, ready/fault status) are left unconnected here; extend the
    instantiation with them as needed for a specific testbench.

    DRIVER-CONFLICT AVOIDANCE: when the FSM skeleton's own fitted per-
    state equations are embedded (embedded_ok=True), it may ALSO drive
    V(vout_ident) — wiring the analog core's real-ODE vout to the SAME
    node would be two drivers on one net. Instead the analog core's vout
    connects to a SEPARATE probe net, `<vout>_analog_core`, so the real-
    ODE prediction and the black-box per-state equation's prediction are
    BOTH observable in the same simulation — a free model cross-check —
    rather than conflicting."""
    from core.fsm.fsm_codegen import _vid

    fsm_module = f"{ip.lower()}_fsm_model"
    core_module = "ldo_pmos_core"
    vout_core_net = f"{vout_ident}_analog_core" if embedded_ok else vout_ident

    L = [
        f"// Auto-generated top-level wrapper — {ip} ({process})",
        f"// Instantiates BOTH the digital/FSM control skeleton",
        f"// ({fsm_module}, from {os.path.basename(va_path)}) and the",
        f"// fitted gray-box analog core ({core_module}, from",
        f"// {os.path.basename(core_path)}) — item 3's requested",
        f"// integration.",
        f"//",
        f"// `include both source files ahead of this one when compiling.",
    ]
    if embedded_ok:
        L += [
            f"//",
            f"// NOTE: {fsm_module} may ALSO drive V({vout_ident}) via its own",
            f"// fitted per-state equations (black-box). To avoid two drivers",
            f"// on one node, the analog core's real-ODE output connects to a",
            f"// SEPARATE probe net, {vout_core_net} — compare the two in",
            f"// simulation as a model cross-check.",
        ]
    L += [
        f"//",
        f"// Net names below are the SAME sanitized identifiers this",
        f"// pipeline requested for vin/vout/gnd/en/hp — verify they match",
        f"// {os.path.basename(va_path)}'s actual port list before",
        f"// simulating (a skeleton that doesn't expose one of these as a",
        f"// port leaves that one wrapper net dangling, not a wiring error",
        f"// elsewhere). Only these 5 shared nets are connected below — the",
        f"// skeleton's other ports (further guard signals, ready/fault",
        f"// status) are left unconnected; extend as needed.",
        "",
        '`include "disciplines.vams"',
        "",
        f"module {ip.lower()}_top_{_vid(process)};",
        f"    electrical {vin_ident}, {vout_ident}, {gnd_ident}, {en_ident}, {hp_ident};",
    ]
    if embedded_ok:
        L.append(f"    electrical {vout_core_net};")
    L += [
        "",
        f"    {fsm_module} u_fsm_skeleton (",
        f"        .{vin_ident}({vin_ident}), .{vout_ident}({vout_ident}), "
        f".{gnd_ident}({gnd_ident}),",
        f"        .{en_ident}({en_ident}), .{hp_ident}({hp_ident})",
        f"        /* extend with this module's remaining ports as needed */",
        f"    );",
        "",
        f"    {core_module} u_analog_core (",
        f"        .vin({vin_ident}), .vout({vout_core_net}), .gnd({gnd_ident}),",
        f"        .en({en_ident}), .hp({hp_ident})",
        f"    );",
        "",
        "endmodule",
    ]
    path = os.path.join(output_dir, f"{ip.lower()}_top_{_vid(process)}.vams")
    with open(path, "w") as f:
        f.write("\n".join(L) + "\n")
    return path


def main() -> int:
    args = build_parser().parse_args()

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

    try:
        correlation = _ensure_correlation(args, kg, sm)
    except ValueError as e:
        print(f"FAIL: {e}")
        return 1
    blut_path = args.blut_path or correlation["blut_path"]
    corners = correlation["corners"]
    good = [r for r in corners if not r["outlier"] and not r["fsm_generation_failed"]]
    good_qids = [r["qid"] for r in good]
    if not good_qids:
        print(
            "FAIL: no non-outlier corners available — every corner was "
            "flagged as an outlier or failed FSM generation."
        )
        return 1

    os.makedirs(args.output_dir, exist_ok=True)

    requested_models = [m.strip().lower() for m in args.models.split(",")]
    for m in requested_models:
        if m not in IMPLEMENTED_MODELS:
            print(
                f"  [example17] '{m}' is not an implemented model option "
                f"(implemented: {IMPLEMENTED_MODELS}) — ignored."
            )

    input_names = [s.strip() for s in args.blut_input_signals.split(",") if s.strip()]
    output_names_req = [
        s.strip() for s in args.blut_output_signals.split(",") if s.strip()
    ]
    vout_signal = args.vout_signal or (output_names_req[0] if output_names_req else "")

    if not args.skip_graybox:
        if args.vin_signal not in input_names:
            print(
                f"FAIL: --vin_signal {args.vin_signal!r} must be one of "
                f"--blut_input_signals {input_names}."
            )
            return 1
        # --en_signal is now OPTIONAL (round-2 fix, item 1) — the enable
        # trace the template actually uses is derived from the FSM state
        # sequence (see _infer_activity_masks), never required as a
        # literal input-signal mapping.
        if vout_signal not in output_names_req:
            print(
                f"FAIL: --vout_signal {vout_signal!r} must be one of "
                f"--blut_output_signals {output_names_req}."
            )
            return 1

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
    requested_to_check = input_names + output_names_req
    bad_names = [n for n in requested_to_check if n not in resolvable_names]
    if bad_names:
        print(
            f"FAIL: the following --blut_input_signals/--blut_output_signals "
            f"name(s) did not resolve against this BLUT/signal_map: {bad_names}"
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

    # Gray-box auxiliary signals are OPTIONAL/auto-degrading (unlike the
    # mandatory names above) — checked here, softly, against the same
    # resolved set, never a hard failure: a wrong/absent name just moves
    # to the next tier (see module docstring).
    graybox_aux = []
    have_vfb_v = (
        bool(args.vfb_voltage_signal) and args.vfb_voltage_signal in resolvable_names
    )
    have_vfb_i = (
        bool(args.vfb_current_signal) and args.vfb_current_signal in resolvable_names
    )
    have_vref = bool(args.vref_signal) and args.vref_signal in resolvable_names
    have_iload = (
        bool(args.iload_current_signal)
        and args.iload_current_signal in resolvable_names
    )
    for flag, name in (
        (have_vfb_v, args.vfb_voltage_signal),
        (have_vfb_i, args.vfb_current_signal),
        (have_vref, args.vref_signal),
        (have_iload, args.iload_current_signal),
    ):
        if flag:
            graybox_aux.append(name)
    print(
        f"\n  Gray-box auxiliary signals: VFB(voltage)={have_vfb_v}  "
        f"VFB_I(current)={have_vfb_i}  VREF={have_vref}  "
        f"iload={have_iload}"
    )

    print(f"\n{'=' * 60}\n  2. Corner-and-state-labeled Phase 2 dataset\n{'=' * 60}")
    output_names_full = output_names_req + [
        n for n in graybox_aux if n not in output_names_req
    ]
    phase2 = Phase2SimAugmented(kg)
    fsm_detector_for_blut = FSMStateDetector(strategy=args.fsm_strategy, spec_kg=kg)
    data = phase2.build_dataset_from_blut(
        blut_path,
        sm,
        input_names,
        output_names_full,
        fsm_detector=fsm_detector_for_blut,
        run_ids=good_qids,
    )
    if len(data["X"]) != len(seq):
        print(
            f"FAIL: row-count mismatch between build_dataset_from_blut "
            f"({len(data['X'])} rows) and the global FSM capture "
            f"({len(seq)} samples) — cannot trust per-row state labels."
        )
        return 1
    data = phase2.target_encode_categorical_meta(data)
    print(f"  X: {tuple(to_np(data['X']).shape)}  features: {data['feature_names']}")
    print(
        f"  Y: {tuple(to_np(data['Y']).shape)}  outputs (incl. gray-box "
        f"aux): {data['output_names']}"
    )

    categorical_codes = data.get("categorical_codes", {})
    if categorical_codes:
        print("  categorical corner codes:")
        for key, mapping in categorical_codes.items():
            print(
                f"    meta_{key}: "
                + "  ".join(f"{v}={c:.4g}" for v, c in mapping.items())
            )

    X_np = to_np(data["X"]).astype(np.float64)
    Y_np_full = to_np(data["Y"]).astype(np.float64)
    output_names_full = data["output_names"]
    feature_names = [_vid(n) for n in data["feature_names"]]
    # Everything from Step 4 on sees ONLY the originally-requested outputs
    # (gray-box aux columns never leak into the black-box/equation fit).
    Y_np = Y_np_full[:, : len(output_names_req)]
    output_names = output_names_req

    # ── Step 3 (NEW — item 6): gray-box analog-template fitting ────────
    graybox_report = None
    analog_core_paths = {}
    if not args.skip_graybox:
        print(
            f"\n{'=' * 60}\n  3. Gray-box analog-template fitting (item 6)\n{'=' * 60}"
        )
        vin_idx = input_names.index(args.vin_signal)
        hp_idx = (
            input_names.index(args.hp_signal) if args.hp_signal in input_names else None
        )
        vout_idx = output_names_full.index(vout_signal)
        iload_idx = (
            output_names_full.index(args.iload_current_signal) if have_iload else None
        )

        reg_sid = next(
            (
                sid
                for sid, d in detector.state_defs.items()
                if (args.regulation_state_name or "REGULATION") in d["name"]
            ),
            None,
        )
        if reg_sid is None:
            print(
                "  no REGULATION-like state found — Tier 2 (i_fb + "
                "V_ref) will have no settled window to use; falling "
                "back further if Tier 1 is also unavailable."
            )
        dropout_sid = next(
            (
                sid
                for sid, d in detector.state_defs.items()
                if (args.dropout_state_name or "DROPOUT") in d["name"]
            ),
            None,
        )
        print(
            f"  DC-point sources (round-3 fix, item 1): "
            f"regulation={'state ' + str(reg_sid) if reg_sid is not None else 'NONE'}  "
            f"dropout={'state ' + str(dropout_sid) if dropout_sid is not None else 'NONE (Kp/Vth_p/lambda_p likely stay pinned at manifest defaults)'}"
        )

        # Round-2 fix, items 1+3: enable/bypass derived from the FSM
        # state sequence (+ VDD_1V2 activity fallback), never a
        # mandatory literal EN_LDO column. See _infer_activity_masks.
        en_eff, bypass_mask, en_source = _infer_activity_masks(
            seq,
            detector.state_defs,
            Y_np_full[:, vout_idx],
            args.disabled_state_names,
            args.bypass_state_names,
            args.vout_active_frac,
        )
        print(f"  enable trace source: {en_source}")
        if bypass_mask.any():
            print(
                f"  bypass-state samples excluded from gray-box fit: "
                f"{int(bypass_mask.sum())}/{len(bypass_mask)} "
                f"({100.0 * bypass_mask.mean():.1f}%) — matched "
                f"--bypass_state_names={args.bypass_state_names!r}"
            )
        if args.en_signal and args.en_signal in input_names:
            en_lit = (X_np[:, input_names.index(args.en_signal)] >= 0.5).astype(float)
            disagree = float(np.mean(en_lit != en_eff))
            print(
                f"  --en_signal {args.en_signal!r} cross-check: "
                f"{disagree * 100:.2f}% disagreement with the derived "
                f"FSM-state enable trace (informational only — the "
                f"derived trace is what the fit actually uses)"
            )

        vfb_idx = (
            output_names_full.index(args.vfb_voltage_signal) if have_vfb_v else None
        )
        ifb_idx = (
            output_names_full.index(args.vfb_current_signal) if have_vfb_i else None
        )
        vref_idx = output_names_full.index(args.vref_signal) if have_vref else None

        from core.templates import LdoPmosTemplate
        from core.fitting import SingleCornerFitter
        from core.fitting.state_delta_fitter import StateParamSet
        from core.pvt import save_param_store

        bounds = run_boundaries + [len(seq)]
        process_groups = _group_qids_by_process(data, good_qids, run_boundaries, seq)
        if len(process_groups) == 1:
            print(
                f"  process does not vary across the loaded corners "
                f"(round-2 fix, item 2) — pooling ALL "
                f"{len(good_qids)} run(s) into a single gray-box fit"
            )
        else:
            print(
                f"  {len(process_groups)} distinct process(es) detected "
                f"— one pooled gray-box fit per process (item 2): "
                f"{sorted(process_groups)}"
            )
        processes_to_fit = sorted(process_groups)[: args.max_graybox_processes]

        graybox_by_process = {}
        param_sets_for_lut = {}
        analog_core_paths = {}
        rf_results_by_process = {}
        for process in processes_to_fit:
            qids_pooled = process_groups[process][: args.max_graybox_corners]

            # Round-3 fix, item 1: Rf1/Rf2 identified from THIS process's
            # own rows only (was pooled globally before, which forced
            # identical Rf1/Rf2 onto every process's fit regardless of
            # whether that's physically true).
            process_row_mask = np.zeros(len(seq), dtype=bool)
            for qid in qids_pooled:
                k = good_qids.index(qid)
                process_row_mask[bounds[k] : bounds[k + 1]] = True
            rf_result = _identify_rf_for_rows(
                process_row_mask,
                Y_np_full,
                vout_idx,
                vfb_idx,
                ifb_idx,
                vref_idx,
                have_vfb_v,
                have_vfb_i,
                have_vref,
                reg_sid,
                seq,
                args,
            )
            rf_results_by_process[process] = rf_result
            if rf_result:
                print(
                    f"  process {process}: Rf identification Tier "
                    f"{rf_result['tier']} — Rf1={rf_result['Rf1']:.4g} Ohm  "
                    f"Rf2={rf_result['Rf2']:.4g} Ohm  "
                    f"({rf_result['n_samples']}/{rf_result['n_total']} samples)"
                )
                process_template = _anchored_ldo_template(
                    rf_result["Rf1"],
                    rf_result["Rf2"],
                    v_ref=rf_result.get("v_ref_used"),
                )
            else:
                print(
                    f"  process {process}: Tier 3 fallback — no usable "
                    f"VFB_I data for this process, Rf2/V_ref stay at "
                    f"manifest nominal defaults, Rf1 floats via DC-stage fit"
                )
                process_template = LdoPmosTemplate()

            dc_points, transient_records = [], []
            for qid in qids_pooled:
                k = good_qids.index(qid)
                s, e = bounds[k], bounds[k + 1]
                if e - s < args.min_state_samples:
                    continue
                dc, trs = _build_graybox_records_for_run(
                    s,
                    e,
                    sc_time,
                    X_np,
                    Y_np_full,
                    vin_idx,
                    hp_idx,
                    vout_idx,
                    iload_idx,
                    seq,
                    reg_sid,
                    dropout_sid,
                    en_eff,
                    bypass_mask,
                    args,
                )
                dc_points.extend(dc)
                transient_records.extend(trs)
            if not transient_records:
                print(
                    f"  process {process}: no usable (non-bypass) data "
                    f"across {len(qids_pooled)} pooled run(s), skipped"
                )
                continue

            fitter = SingleCornerFitter(
                process_template,
                spec_kg=kg,
                de_maxiter=args.graybox_de_maxiter,
                de_popsize=args.graybox_de_popsize,
                enable_nn_residual=args.enable_nn_residual,
            )
            try:
                result = fitter.fit(
                    {"dc": dc_points, "transient": transient_records}, corner=process
                )
                n_pass = sum(
                    1
                    for r in result.spec_compliance
                    if r.get("evaluated") and r.get("passes")
                )
                n_eval = sum(1 for r in result.spec_compliance if r.get("evaluated"))
                print(
                    f"  process {process}: pooled {len(qids_pooled)} run(s), "
                    f"{len(transient_records)} transient record(s), "
                    f"{len(dc_points)} DC point(s) — "
                    f"dc_rms={result.per_stage_residuals['dc']:.3g}  "
                    f"transient_rms={result.per_stage_residuals['transient']:.3g}  "
                    f"frozen={result.frozen_params}  "
                    f"spec_compliance={n_pass}/{n_eval}"
                )
                # Item 4a: which of THIS process's fitted parameters
                # actually drives which observable behavior — computed
                # from the fitted template itself (dc_solve/small_signal),
                # not asserted. See _parameter_sensitivity_map docstring.
                sensitivity = _parameter_sensitivity_map(
                    process_template, result.params
                )

                graybox_by_process[process] = {
                    "params": result.params,
                    "rf_identification": rf_result,
                    "n_runs_pooled": len(qids_pooled),
                    "n_transient_records": len(transient_records),
                    "n_dc_points": len(dc_points),
                    "per_stage_residuals": result.per_stage_residuals,
                    "frozen_params": result.frozen_params,
                    "identifiability": result.identifiability,
                    "spec_compliance": result.spec_compliance,
                    "notes": result.notes,
                    "sensitivity": sensitivity,
                }
                param_sets_for_lut[process] = StateParamSet(baseline=result.params)

                # Item 3: the fitted analog structure becomes a REAL
                # output artifact (real ODEs — immediate output-drop
                # feedback, real transient dynamics), not just a report.
                ip = args.ip_type.lower()
                core_path = os.path.join(
                    args.output_dir, f"{ip}_analog_core_{_vid(process)}.vams"
                )
                with open(core_path, "w") as f:
                    f.write(process_template.emit_veriloga_core(result.params))
                analog_core_paths[process] = core_path
            except Exception as ex:
                print(f"  process {process}: gray-box fit failed — {ex}")

        # Item 2's LUT: persisted via this repo's OWN PVT parameter store
        # (core/pvt/param_blut_store.py — the same mechanism
        # LutParamProvider/BlutStoreParamProvider already consume), keyed
        # by process label directly (no '<P>_<vdd>V_<temp>C' naming
        # constraint needed for save_param_store itself) — plus a plain
        # JSON mirror for quick human inspection.
        param_store_path = os.path.join(args.output_dir, "graybox_process_lut.blut")
        if param_sets_for_lut:
            try:
                save_param_store(param_store_path, param_sets_for_lut)
            except Exception as ex:
                print(
                    f"  process-LUT BLUT store write failed — {ex} "
                    f"(the JSON mirror below is still authoritative)"
                )
                param_store_path = None
        else:
            param_store_path = None

        any_tier2 = any(
            r and r.get("tier") == 2 for r in rf_results_by_process.values()
        )
        any_tier3 = any(r is None for r in rf_results_by_process.values())
        graybox_report = {
            "rf_identification_by_process": rf_results_by_process,
            "enable_trace_source": en_source,
            "bypass_fraction_excluded": float(bypass_mask.mean())
            if len(bypass_mask)
            else 0.0,
            "process_lut": {p: r["params"] for p, r in graybox_by_process.items()},
            "assumptions": {
                "A1_feedback_node_no_bias_current": (
                    "The feedback divider branch current equals the full "
                    "v_out/(Rf1+Rf2) divider current — i.e. the error "
                    "amplifier input draws negligible bias current at that "
                    "node. Used whenever ANY tier of Rf1/Rf2 identification "
                    "ran (always the case if VFB_I resolved)."
                ),
                "tier2_closed_loop_v_fb_eq_v_ref": (
                    "Used for at least one process (VFB_I but no VFB "
                    "voltage): in a settled REGULATION-state sample, the "
                    "closed loop holds v_fb approximately equal to V_ref."
                    if any_tier2
                    else "not used (every process either ran Tier 1 or had "
                    "no gray-box fit at all)"
                ),
                "tier3_nominal_rf2_vref": (
                    "At least one process fell back to Rf2/V_ref held at "
                    "LDO_PMOS_MANIFEST's own nominal defaults (never "
                    "measured for that process) — only the ORIGINAL, "
                    "already-shipped assumption, unchanged. Rf1/Rf2 are "
                    "now identified PER PROCESS (round-3 fix, item 1), so "
                    "other processes may still have resolved VFB_I."
                    if any_tier3
                    else "not used (every process resolved VFB_I)"
                ),
                "iload_assumed_zero": (
                    "iload assumed 0 in every gray-box DC/transient record "
                    "(no --iload_current_signal given) — the fit then "
                    "calibrates an effectively unloaded/light-load corner."
                    if not have_iload
                    else "not used (--iload_current_signal given)"
                ),
                "enable_trace": (
                    f"Derived from {en_source} (round-2 fix, item 1) — "
                    f"never a mandatory literal EN_LDO pin mapping."
                ),
                "bypass_excluded": (
                    f"{100.0 * bypass_mask.mean():.1f}% of samples matched "
                    f"--bypass_state_names={args.bypass_state_names!r} and "
                    f"were excluded from the gray-box fit entirely (item 3) "
                    if bypass_mask.any()
                    else "no --bypass_state_names pattern matched any detected "
                    "state — nothing excluded."
                ),
                "voltage_temperature_not_separate_lut_axes": (
                    "Runs of the SAME process but different vin/temp are "
                    "POOLED into one fit, not split into separate LUT "
                    "entries — the template already models vin "
                    "continuously through its own ODEs/dc_solve (item 2)."
                ),
            },
            "processes": graybox_by_process,
            "analog_core_files": analog_core_paths,
            "param_store_path": param_store_path,
        }
        _write_json(
            os.path.join(args.output_dir, "graybox_fit_report.json"), graybox_report
        )
        with open(os.path.join(args.output_dir, "graybox_fit_report.md"), "w") as f:
            L = ["# Gray-Box Analog-Template Fitting (item 6 + round-3 fixes)", ""]
            L.append("## Rf1/Rf2 identification, PER PROCESS (round-3 fix, item 1)")
            L.append("")
            L.append("| process | tier | Rf1 (Ohm) | Rf2 (Ohm) | samples |")
            L.append("|---|---|---|---|---|")
            for process, rf in rf_results_by_process.items():
                if rf:
                    L.append(
                        f"| {process} | {rf['tier']} | {rf['Rf1']:.4g} | "
                        f"{rf['Rf2']:.4g} | {rf['n_samples']}/{rf['n_total']} |"
                    )
                else:
                    L.append(
                        f"| {process} | 3 (fallback) | manifest default | "
                        "manifest default | n/a |"
                    )
            L += ["", "## Assumptions actually used", ""]
            for key, text in graybox_report["assumptions"].items():
                L.append(f"- **{key}**: {text}")
            L += [
                "",
                "## Per-process pooled fit (LUT entries)",
                "",
                "| process | runs pooled | dc_rms | transient_rms | frozen | spec pass |",
                "|---|---|---|---|---|---|",
            ]
            for process, r in graybox_by_process.items():
                n_pass = sum(
                    1
                    for c in r["spec_compliance"]
                    if c.get("evaluated") and c.get("passes")
                )
                n_eval = sum(1 for c in r["spec_compliance"] if c.get("evaluated"))
                L.append(
                    f"| {process} | {r['n_runs_pooled']} | "
                    f"{r['per_stage_residuals']['dc']:.3g} | "
                    f"{r['per_stage_residuals']['transient']:.3g} | "
                    f"{r['frozen_params']} | {n_pass}/{n_eval} |"
                )
            for process, r in graybox_by_process.items():
                L += [
                    "",
                    f"### {process} — fitted component values",
                    "",
                    "| parameter | value |",
                    "|---|---|",
                ]
                for name, val in sorted(r["params"].items()):
                    L.append(f"| {name} | {val:.6g} |")
                if process in analog_core_paths:
                    L.append(f"\nAnalog core: `{analog_core_paths[process]}`")
            if param_store_path:
                L += [
                    "",
                    f"LUT param store (core.pvt-compatible): `{param_store_path}`",
                ]
            f.write("\n".join(L) + "\n")
        print(
            f"  Gray-box report: "
            f"{os.path.join(args.output_dir, 'graybox_fit_report.md')} (+ .json)"
        )
        if param_store_path:
            print(f"  Process-LUT param store: {param_store_path}")
        for process, p in analog_core_paths.items():
            print(f"  Analog core ({process}): {p}")

        # Item 4a: consolidated "which parameter drives which behavior"
        # report, ranked per behavior by |elasticity| — the engineering-
        # insight mechanism the request asked to be BUILT (computed from
        # the fitted templates, not asserted).
        sens_json = {
            p: r["sensitivity"]
            for p, r in graybox_by_process.items()
            if r.get("sensitivity")
        }
        if sens_json:
            _write_json(
                os.path.join(args.output_dir, "parameter_sensitivity_map.json"),
                sens_json,
            )
            with open(
                os.path.join(args.output_dir, "parameter_sensitivity_map.md"), "w"
            ) as f:
                L = [
                    "# Parameter -> Behavior Sensitivity Map (item 4a)",
                    "",
                    "Elasticity = (% change in behavior) / (% change in "
                    "parameter), centered finite difference at +-1% around "
                    "each process's FITTED parameter vector. |elasticity| "
                    ">> 0 means that parameter dominates that behavior; "
                    "~0 means it barely matters for it (a real, computed "
                    "result — not asserted).",
                    "",
                ]
                for process, r in graybox_by_process.items():
                    sens = r.get("sensitivity")
                    if not sens or not sens.get("elasticities"):
                        continue
                    L += [f"## Process: {process}", ""]
                    behaviors = sorted(sens["base_behaviors"].keys())
                    for beh in behaviors:
                        ranked = sorted(
                            (
                                (name, row.get(beh, 0.0))
                                for name, row in sens["elasticities"].items()
                            ),
                            key=lambda kv: -abs(kv[1]),
                        )
                        top = [(n, v) for n, v in ranked if abs(v) > 1e-6][:6]
                        if not top:
                            continue
                        L.append(
                            f"**{beh}** (base={sens['base_behaviors'][beh]:.4g}): "
                            + ", ".join(f"{n}={v:+.3g}" for n, v in top)
                        )
                    L.append("")
                f.write("\n".join(L) + "\n")
            print(
                f"  Parameter sensitivity map: "
                f"{os.path.join(args.output_dir, 'parameter_sensitivity_map.md')} (+ .json)"
            )

    print(f"\n{'=' * 60}\n  4. Differential (ddt/idt) features\n{'=' * 60}")
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
        print(f"\n{'=' * 60}\n  4.5 Denoising impact evaluation\n{'=' * 60}")
        biggest_sid = max(
            detector.state_defs.keys(), key=lambda s: int((seq == s).sum())
        )
        mask_eval = seq == biggest_sid
        n_eval = int(mask_eval.sum())
        if n_eval >= max(30, args.min_state_samples):
            base_names = feature_names[
                : X_np.shape[1] - len(deriv_token_to_base) - len(integral_token_to_base)
            ]
            X_base = X_np[:, : len(base_names)]
            eval_targets = [n for n in base_names if not n.startswith("meta_")]
            eval_window = args.smoothing_window if args.smoothing_window > 1 else 11
            comparisons = {}
            for label, w in (
                ("unsmoothed", 0),
                (f"smoothed(w={eval_window})", eval_window),
            ):
                Xd, names_d, dtb, itb = _add_derivative_integral_features(
                    X_base,
                    base_names,
                    run_boundaries,
                    sc_time,
                    eval_targets,
                    include_integral=False,
                    smoothing_window=w,
                )
                pm = np.array([n not in dtb for n in names_d])
                X_state, Y_state = Xd[mask_eval], Y_np[mask_eval]
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

    equation_parameters = {
        name: float(X_np[:, i].mean())
        for i, name in enumerate(feature_names)
        if name.startswith("meta_")
    }

    print(
        f"\n{'=' * 60}\n  5. Per-state model comparison + output equations\n{'=' * 60}"
    )
    print(
        f"  sample caps: general(equation/PINN/NODE)={args.max_state_samples}  "
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
                pinn.eval()
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
                eq_final = _rewrite_ddt_idt_tokens(
                    eq_text,
                    deriv_token_to_base,
                    integral_token_to_base,
                    gnd_ident,
                    ddt_idt_placeholder_map,
                )
                state_eq_info[out_name] = {
                    "equation": eq_final,
                    "raw_equation": eq_text,
                    "r2": r2,
                    "source": source,
                    "has_differential_term": eq_final != eq_text,
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
    print(f"    ddt() present: {has_ddt}   idt() present: {has_idt}")
    if graybox_report:
        tiers = {
            p: (rf["tier"] if rf else "3 (fallback)")
            for p, rf in graybox_report["rf_identification_by_process"].items()
        }
        print(
            f"    gray-box Rf1/Rf2 tier by process: {tiers}  "
            f"processes fitted: {len(graybox_report['processes'])}"
        )

    # Item 3: wire the fitted analog core(s) and the FSM control skeleton
    # into one top-level module per process — a real, simulatable
    # "complete analog model" integration (usage documented in each
    # wrapper's header comments).
    top_wrapper_paths = {}
    for process, core_path in analog_core_paths.items():
        top_wrapper_paths[process] = _generate_top_level_wrapper(
            args.ip_type,
            process,
            va_path,
            core_path,
            _vid(args.vin_signal),
            _vid(vout_signal),
            gnd_ident,
            _vid(args.en_signal or "EN_LDO"),
            _vid(args.hp_signal),
            embedded_ok,
            args.output_dir,
        )
    if top_wrapper_paths:
        print(f"\n  Top-level analog-core + FSM-skeleton wrapper(s):")
        for process, p in top_wrapper_paths.items():
            print(f"    {process}: {p}")

    # ── Reports ──────────────────────────────────────────────────────────
    model_comparison = {
        "blut_path": blut_path,
        "good_corners": len(good_qids),
        "total_corners": len(corners),
        "meta_key_kind": data.get("meta_key_kind", {}),
        "categorical_codes": categorical_codes,
        "feature_names": feature_names,
        "output_names": output_names,
        "equation_source": eq_source_label,
        "equation_parameters": equation_parameters,
        "sample_caps": {
            "max_state_samples": args.max_state_samples,
            "max_gpr_smt_samples": args.max_gpr_smt_samples,
            "max_pysr_samples": args.max_pysr_samples
            if args.include_symbolic
            else None,
        },
        "denoising_evaluation": denoising_eval,
        "graybox_fit": ("see graybox_fit_report.json" if graybox_report else None),
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
    }
    _write_json(
        os.path.join(args.output_dir, "model_comparison.json"), model_comparison
    )

    with open(os.path.join(args.output_dir, "model_comparison.md"), "w") as f:
        model_cols = sorted({m for v in state_metrics.values() for m in v})
        L = [
            "# Phase 2 Model Comparison — Gray-Box Analog-Template Fitting",
            "",
            f"BLUT: `{blut_path}`  |  good corners: {len(good_qids)}/{len(corners)}  "
            f"|  equation source: `{eq_source_label}`",
            "",
        ]
        if graybox_report:
            L += ["## Gray-box fit — see `graybox_fit_report.md`", ""]
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
            f"- general (equation fit + PINN + NODE): {args.max_state_samples}",
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
        f.write("\n".join(L) + "\n")

    manifest_path = os.path.join(args.output_dir, "manifest.md")
    with open(manifest_path, "w") as f:
        L = [
            "# example17 Run Manifest — Pipeline Structure",
            "",
            "```",
            "1. Load per_corner_correlation.json -> filter good corners",
            "2. Global FSM (SignalCapture + FSMStateDetector + "
            "TransitionLearner + FSMValidator) -> state_defs, transitions",
            "3. Validate requested signal names against the actually-"
            "resolved signal set (fast-fail on a typo); gray-box aux "
            "signals (VFB/VFB_I/VREF/iload) checked softly",
            "4. Phase2SimAugmented.build_dataset_from_blut(run_ids=good_qids) "
            "-> corner-and-state-labeled X, Y (+ gray-box aux columns), "
            "feature_names + target_encode_categorical_meta",
            "5. NEW (item 6): per-corner gray-box fit of LdoPmosTemplate "
            "via SingleCornerFitter, with Rf1/Rf2 identified from VFB/"
            "VFB_I (falls back tier-by-tier — see module docstring)",
            "6. Derivative (+ optional integral) features per input signal, "
            "per-run/run-boundary-safe"
            + (
                f", Savitzky-Golay smoothed (window={args.smoothing_window})"
                if args.smoothing_window > 1
                else ""
            ),
            "7. Per state: "
            + "/".join(m.upper() for m in requested_models if m in IMPLEMENTED_MODELS)
            + " (informational; GPR/SMT/PySR sub-capped) + "
            + eq_source_label
            + " equation, ddt()/idt() token rewrite",
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
            "",
        ]
        if graybox_report:
            tiers = {
                p: (rf["tier"] if rf else "3 (fallback)")
                for p, rf in graybox_report["rf_identification_by_process"].items()
            }
            L += [
                "## Gray-box fit (item 6 + round-3 fixes)",
                "",
                f"Rf1/Rf2 identification tier BY PROCESS: {tiers}",
                f"Processes fitted (pooled LUT entries): "
                f"{len(graybox_report['processes'])}",
                f"Enable trace source: {graybox_report['enable_trace_source']}",
                f"Bypass fraction excluded: "
                f"{graybox_report['bypass_fraction_excluded'] * 100:.1f}%",
                f"Full report: `{os.path.join(args.output_dir, 'graybox_fit_report.md')}` (+ .json)",
                "",
            ]
        if categorical_codes:
            L += [
                "## Categorical corner codes (set meta_<key> to this "
                "value per simulated process)",
                "",
            ]
            for key, mapping in categorical_codes.items():
                L.append(
                    f"- `meta_{key}`: "
                    + ", ".join(f"{v}={c:.4g}" for v, c in mapping.items())
                )
        L += [
            "",
            f"**Analog skeleton output-driving equations: "
            f"{'EMBEDDED' if embedded_ok else 'NOT EMBEDDED'}**",
            f"  states with equations: {n_states_with_eq}",
            f"  outputs: {output_names}",
            f"  ddt() present: {has_ddt}   idt() present: {has_idt}",
            "",
            "## Output files",
            "",
            f"- `{va_path}` — final Verilog-A (FSM + self-checks + "
            f"differential output equations)",
            f"- `{sv_path}` — final SystemVerilog control skeleton",
            f"- `{os.path.join(args.output_dir, 'model_comparison.md')}` (+ .json)",
        ]
        if graybox_report:
            L.append(
                f"- `{os.path.join(args.output_dir, 'graybox_fit_report.md')}` (+ .json)"
            )
            L.append(
                f"- `{os.path.join(args.output_dir, 'parameter_sensitivity_map.md')}` "
                f"(+ .json) — item 4a engineering-insight mechanism"
            )
            for process, p in analog_core_paths.items():
                L.append(f"- `{p}` — fitted analog core ({process})")
            for process, p in top_wrapper_paths.items():
                L.append(f"- `{p}` — top-level wrapper ({process}, item 3)")
            if param_store_path:
                L.append(f"- `{param_store_path}` — process LUT param store")
        L.append("")
        f.write("\n".join(L))

    print(f"\n{'=' * 60}\n  OUTPUT FILES")
    print(f"{'=' * 60}")
    print(f"  Final Verilog-A       {va_path}")
    print(f"  Final SystemVerilog   {sv_path}")
    print(
        f"  Model comparison      {os.path.join(args.output_dir, 'model_comparison.md')} (+ .json)"
    )
    if graybox_report:
        print(
            f"  Gray-box fit          {os.path.join(args.output_dir, 'graybox_fit_report.md')} (+ .json)"
        )
        print(
            f"  Sensitivity map       {os.path.join(args.output_dir, 'parameter_sensitivity_map.md')} (+ .json)"
        )
    print(f"  Manifest / structure  {manifest_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
