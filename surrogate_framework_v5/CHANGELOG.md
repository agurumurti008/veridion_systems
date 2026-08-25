# Changelog — surrogate_framework_v5

Entries are per-commit, newest first. "Bugs found" lists real defects
discovered and fixed while building that commit, per the delivery contract.

---
# Increment: current-insights (A) + FSM-completeness (B)
Branch `claude/insights-fsm-completeness` (forked from `claude/ab-strategy-sref-poc`).

## branch audit Phase B — direction-aware port roles, output signatures, example7
- Root cause (docs/AUDIT_INSIGHTS_FSM.md): `get_fsm_relevant_ports`'s
  `is_state_signal` short-circuit (knowledge_graph.py, audit line 194)
  dropped input-vs-output semantics, so output/status indicator pins
  (EN_UVLO_1V2) became state variables AND guard features, the `output`
  port_type additionally produced a .vams that drove and sampled the
  same pin (combinational loop), and the user's port_type flip was a
  behavioral no-op.
- Fix: Port.direction (explicit or derived via port_direction);
  get_fsm_input_ports/get_fsm_output_ports; the logic matrix is
  input-only (outputs excluded even in the waveform fallback, logged);
  get_output_signal_matrix + per-state output signatures; signature-
  driven REGULATION/FAULT naming (hardcoded EN/FAULT/POK fallbacks
  removed); codegen directions + status drive via port_direction; new
  output-consistency section in coverage/gap report; role/taxonomy-
  driven replacements for every remaining hardcoded pin-name decision
  (primary_input_supply, switch/hp-state roles, domain supply nets,
  derive_pin_map, gap-report stimulus pins).
- main.py fsm phase extracted as run_fsm_phase();
  examples/example7_fsm_blut_cli.py drives the exact documented CLI
  through it (import, no shell-out) + completeness/gap report;
  INSTRUCTIONS.md "FSM from BLUT via CLI". Suite 79 -> 86 (7 appended
  tests), example5 FULL rerun still ALL BARS MET.
- Real-data result (regression1.bin): 20 -> 17 states, 37 -> 33
  transitions, guards over 8 input pins only; EN_UVLO_1V2 emitted as a
  driven `output` and reported per state; 5 output-consistency
  contradictions surfaced (UVLO-good indicator high in DISABLED-family
  states — role semantics flagged for review, not silently renamed).
- Bugs found while testing: (1) the first refinement test assumed a
  STARTUP state would survive when the ready indicator covered >=50% of
  the enabled state's dwell — wrong expectation, the whole input-pattern
  state legitimately becomes REGULATION; the fixture now pulses the mode
  pin before ready asserts so a genuine STARTUP-family state exists.
  (2) example7's first completeness call passed the detector object as
  fsm_result, silently dropping transitions (transition coverage read
  0) — it now passes a namespace carrying state_defs + transitions +
  output_signatures.

## tests + CHANGELOG — insights/completeness test block (14 tests)
- Appended 14 tests (suite 65 -> 79, never renumbered): filtering floor/
  spike/derivative; registry `$flow` current resolution; supply-attribution
  ranking; edge->threshold localization; mux verify pass+bug; V/I
  total-supply consistency; capacity vs ground truth; dummy-load
  classification; impedance extraction + template reconciliation; Iq
  advisory-only (detector inputs unchanged); 2^n->masked containment
  arithmetic (EN>-SEL); coverage richness clipped-as-gap; Option-2
  limitations reaching the Verilog-A header; disabled-insights regression
  guard.
- Bugs found: two analyzers were fragile on the constructed traces and were
  hardened (not the tests): 3.2 edge localization read the current
  DERIVATIVE peak (offset from the crossing) -> now reads the current
  MAGNITUDE peak; 3.9 impedance thresholded per-sample dV/dI (destroyed by
  SG smoothing) -> now a regression slope of V(out) on I(out).

## configs + example6 — ip_profiles.yaml, insights/gaps demo, false-positive fixes
- configs/ip_profiles.yaml (LDO complete + DCDC/PLL skeletons);
  examples/example6_insights_gaps.py (synthetic v8 SREF BLUT: mux pass+bug,
  dummy-load, capacity, missing states; real FSM auto-derivation sliced per
  run; insight report + gap report + Option-2 Verilog-A).
- Bugs found: (1) the authoritative experiment1 map stores current paths
  WITH `$flow` but the reader strips it before matching -> all currents
  unresolved; SignalMap.from_spec_json now normalizes current blut_signals
  to the base name. (2) 3.11 shoot-through flagged the intended
  make-before-break mux handover -> now requires EXCESS total supply
  current. (3) 3.5 vi-consistency compared only the primary supply ->
  compares TOTAL input-supply current. (4) coverage richness gate only
  scrutinized REGULATION entries -> all analog-settling destinations.

## Section 5 — insights phase + codegen integration
- insights_pipeline.run_insights_phase() (opt-in A+B phase after detection);
  emit() gains iq_signatures / limitations / load_enrichment (additive,
  byte-identical when disabled).
- Bug found: dummy-load detection used a fixed 4 nA floor -> SEL/mode
  toggles false-classified as loads; threshold is now k x the output
  current's own noise floor.

## Section 4 — FSM completeness (Capability B)
- state_space (2^n->masked containment), coverage (state/transition/
  richness/corner + current-informed gaps), gap_report (.md+.json,
  Option 1/2), ip_profiles (LDO + DCDC/PLL, pyyaml via uv).
- Bug found: Transient_Settling spec is in us but was read as seconds ->
  every transition looked clipped; added time-unit conversion.

## Section 3 — current-insight analyzers (Capability A, 3.1-3.11)
- filtering, registry, findings (+3.12), and the eight analyzers.
- Bugs found: output-rail selection picked the tiny STB floop_out probe ->
  data-driven pick_output_rail; np.trapz removed in numpy 2.x -> trapezoid;
  Max_Load_Current spec in mA read as Amps -> unit-convert; vi-consistency
  keyed by op-point flagged legit STARTUP-vs-REGULATION -> same-state-
  across-paths.

## Insights Gate 1 — recon (docs/INSIGHTS_RECON.md)
- Recon of the current API surface; key finding: 23 `$flow` probes at the
  X_DUT boundary make Capability A evaluable on real data.

---
# A+B strategy build
Branch `claude/ab-strategy-sref-poc`.

## tests + CHANGELOG — A+B test block (17 appended tests) and this file
- Appended 17 tests (suite 48 -> 65, never renumbered) covering Sections
  3–7: manifest round-trip, DC-solve sanity (Vout = Vref·(1+Rf1/Rf2)),
  dropout-from-triode (structural, clamp-free), PSRR structural response,
  Vector-Fitting and ERA known-pole recovery, DC-stage and transient-stage
  ground-truth recovery, identifiability freeze on a constructed
  degenerate case (DC-only data must freeze transient-stage params),
  state-delta switch-state sparsity, three-provider round-trip/agreement
  at training corners, holdout-table shape, ABModel state-switch
  continuity, `$bound_step`-and-no-`@(cross` emission, connect-module +
  `_ok` blocks matching the spec JSON, supplies_ok inertness gating in the
  reference sim, and an end-to-end example5 `--smoke` scorecard execution.
- Bugs found: the "PSRR responds to lambda_p" assertion was first written
  against 1 kHz where the loop hides the CLM path — the structural effect
  lives at HF (1.2–2.4 dB above 1 MHz); assertion moved to the full grid.

## configs + example5 — SREF POC configs, questionnaire, end-to-end example
- `configs/sref_ldo1v2_lp_spec.json`: transformed SREF spec (target
  schema, all 30 ports incl. bias/VFB/VREF/AVSS) + placeholder
  `signal_map` skeleton marked for user substitution.
- `configs/sref_architecture_questionnaire.yaml`: 14 deferred
  SREF-specific decisions (UVLO thresholds/override, HP-LP deltas, supply/
  output mux semantics, isense architecture, scan topology, trim map, bias
  and ground-bounce `_ok` windows, logic-domain supply association, floop
  strapping), each with the safe default currently in use.
- `examples/example5_sref_ab_poc.py`: synthetic 3-corner SREF BLUT v8
  (corner_id-keyed, per-corner ground truth; line step, 1 A/us load step,
  EN/HP/UVLO exercise) -> FSM auto-derivation -> per-corner staged fits +
  state deltas -> BLUT-store/LUT/NN providers + holdout table -> ABModel
  reference sim vs ground truth -> Verilog-A + $table_model emission ->
  POC scorecard. Scorecard: ALL BARS MET at TT/SS/FF.
- Bugs found: (1) ABModel's Python supplies_ok hold zeroed V(vout)
  instantly while the emitted Verilog-A bleeds it through 1 kOhm — the
  reference sim now mirrors the emitted contract (k_load += 1 mS during
  !supplies_ok segments); mode-exercise rms vs ground truth dropped from
  ~425 mV to ~5 mV at TT. (2) The first SS ground-truth corner violated
  the dropout bar by construction (no fit could pass); SS deviations
  retuned so the true device meets the bars the scorecard checks.

## Add A+B integration: ABModel reference simulation + structural Verilog-A codegen
- `core/ab_integration/`: ABModel (FSM x template x deltas x provider,
  per-timestep guard evaluation, spec-JSON `_ok`/supplies_ok gating,
  segment-wise ODE integration with x0 continuity) and ab_codegen
  (spec-JSON pin interface, per-domain supply-sensitive connect modules,
  `<pin>_ok` self-checks with JSON-cited windows, `$bound_step` FSM
  sampling, per-state case overrides, V(vout)+I(vin), $table_model .tbl
  export with the NN-deployment note).

## Add PVT parameter capture: provider ABC, LUT, BLUT v8 store, NN regression
- `core/pvt/` + `core/numpy_mlp.py`; `evaluate_providers()` holdout table.
- Bugs found: torch_shim has NO autograd — `backward()` is a no-op and its
  Adam only consumes externally-set grads, so shim-path training silently
  performed zero updates (NN provider plateaued at mse 0.85 regardless of
  lr/epochs). Added an analytic-gradient NumPy MLP used whenever real
  torch is absent (shim-path mse 1.7e-7, training corners exact).

## Add staged fitting module: objectives, Vector Fitting/ERA, corner fitter, state deltas
- `core/fitting/`: SpecKG-weighted objectives, vendored Vector Fitting
  (Gustavsen & Semlyen 1999) + ERA, staged DC/LINEAR/TRANSIENT fitter with
  identifiability gate, per-state delta fitter (mode_affected-only, L2 to
  zero, thin-state skip, 40-dim cap).
- Bugs found: (1) freezing unidentifiable params to defaults WITHOUT
  re-fitting left identifiable partners holding stale compensations
  (railed V_ref compensated by Rf1 became a plain vout error after the
  freeze) — the gate now re-polishes every stage with the frozen set
  pinned. (2) V_ref is structurally unidentifiable from vout data (only
  V_ref·(1+Rf1/Rf2) is observable) — manifest anchors V_ref as fixed and
  floats the divider ratio.

## Add Strategy B template module: PMOS-pass LDO backbone + manifest + pin taxonomy
- `core/templates/`: ParamSpec/ParamManifest, AnalogTemplate ABC with
  shared numerical linearization, LdoPmosTemplate (normative 3-state
  physics, tuned defaults meeting every POC bar), SREF pin taxonomy with
  questionnaire flags.
- Bugs found: (1) the literal normative EA sign i_ea = Gm·(V_ref − v_fb)
  closes the loop with POSITIVE feedback for a PMOS pass device (DC solves
  landed on a spurious root at vout ~= vin) — gate drive made inverting.
  (2) a static-input linearization dropped the Cgs/Cgd input-derivative
  feedthrough, so PSRR(f) came from an incomplete model — small_signal now
  uses the descriptor form H(s) = C(sI−A)^-1(B + sE) + D.

## Update Gate 1 recon to revised contract: v8 authoritative sync + spec schema row
- AB_RECON.md: executed v8 re-vendor report with the affected-call-site
  table, real (run_id, corner_id) keying for param_blut_store, adopted
  authoritative LDO_1V2.json, spec-JSON schema row for the Section 7
  connect-module/`_ok` emission (+ the missing logic-pin supply-net
  association flagged to the questionnaire).

## Adopt authoritative SREF LDO_1V2 spec from experiment1; regenerate map and outputs
- `configs/LDO_1V2.json` replaced by the experiment1 reference (29 SREF
  ports); `configs/signal_map_ldo.json` regenerated; documented FSM
  command re-verified (20 states / 37 transitions over real control pins).

## Re-vendor digiTwin BLUT support from authoritative v8 source
- `digitwin/blut_format.py` byte-for-byte from `experiment1:DigiTwin_v8/`;
  `blut_reader_core.py` re-trimmed with verbatim v8 bodies (nested
  runs[run_id][corner_id], 3-segment tokens, corner-aware resolution);
  `iter_runs`/`get_run` helpers; SignalCapture/Phase2/tests/example4
  updated for the nested shape. Suite green (48/48) after sync.

## Add A+B Gate 1 recon report and merge plan
- `docs/AB_RECON.md`: repo-as-found inventory, integration-point
  signature table, merge plan, data reality checks (no AC data in the
  bundled BLUTs -> ERA path; empty meta strings).
