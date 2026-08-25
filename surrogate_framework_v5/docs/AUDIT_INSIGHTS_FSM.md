# Audit — `claude/insights-fsm-completeness`: Insights Compliance + Port-Role Forensics

Branch head at audit time: `950ffda`. Real `blut_files/regression1.bin` present on the branch
(3.3 MB, 59 runs) — **no stand-in was generated**; the user's exact CLI was run as-is.

**Compliance baseline location:** the "Modeling Insights Increment" instruction set is **not
committed as a document**. It is reconstructable from `docs/INSIGHTS_RECON.md` (quotes the
contract rows + requirement map), the branch commit messages (`f3873ab` "Capability A, 3.1-3.11",
`437f86f` "Capability B", `fa6df25` "Section 5", `869e704` "Section 6", `950ffda` tests), and
`CHANGELOG.md`. This report treats those as the baseline and flags the missing doc as a gap.

## Part 1 — Insights-Increment compliance

| Requirement | Impl? | Evidence (file:line) | Gap |
|---|---|---|---|
| 3.6 filtering before inference (floor/median/SG, logged) | ✓ | `core/current_insights/filtering.py:83-151` (`filter_current`), `FilterLog` :25-40; logs surfaced `insights_pipeline.py:60-64` | — |
| registry pin↔`$flow`-path↔domain (spec+SignalMap) | ✓ | `registry.py:64-100` (`CurrentRegistry.__init__`), `resolve_current` :131-140 | — |
| 3.1 supply attribution + domain mismatch | ✓ | `supply_attribution.py:16-90` | — |
| 3.2 edge↔threshold localization w/ confidence | ✓ | `edge_correlation.py:17-77` | — |
| 3.3/3.7 drive strength, collapse, capacity vs spec, bound feed-back | ✓ | `drive_strength.py:17-119` (bound is a Finding, never a silent overwrite :104-116) | — |
| 3.4 mux verification (shift = proof; no-shift = high) | ✓ | `supply_attribution.py:93-171` (`MuxVerification`) | — |
| 3.5 V/I consistency (same state+op-point across paths) | ✓ | `vi_correlation.py:47-108` (total-supply keying) | — |
| 3.8 dummy-load auto-detect + taxonomy enrichment | ✓ | `load_detection.py:26-93` (`enrichment_proposals`) | — |
| 3.9 impedance (Welch + secants) + template reconcile/refit trigger | ✓ | `vi_correlation.py:110-160` | — |
| 3.10 Iq signatures, advisory-only | ✓ | `state_signatures.py:20-108`; boundary test `tests/test_framework.py::test_iq_signature_advisory_only` | — |
| 3.11 transition health (crowbar, inrush C_out, cross-check) | ✓ | `transition_health.py:17-115` | charge-balance is partial (crowbar+inrush only; no explicit ∫I_in−∫I_out row) |
| 3.12 efficiency + sequencing (top severity) | ✓ | `findings.py:169-262` (`EfficiencySequencing`) | — |
| Currents never feed the state detector | ✓ | `state_detector.py:30-38` (`detect(logic_matrix, logic_names, analog_features)` — no current input); RunView split `findings.py:47-58` | — |
| **$flow currents in state characterization** | ✓* | by contract row 2 they must NOT create states; they refine post-detection only (3.10) and feed codegen Iq (`ab_codegen.py` `iq_signatures`) | *as designed — cite when reading "participation in state characterization" |
| 4.1 containment (2^n → masked, arithmetic shown) | ✓ | `state_space.py:36-107`; regression spec: 2^12=4096 → 7 (585×) | — |
| 4.2 coverage: states/dwell/transitions/richness/corner + current-informed gaps | ✓ | `coverage.py:61-160`; clipped-as-gap `coverage.py:125-135` | — |
| unreachable/missing-state detection | ✓ | `coverage.py:80-87` (`missing_states`) + `FSMValidator.validate` reachability `fsm_codegen.py:71-91` | — |
| 4.3 gap report .md+.json, Option-1 runs / Option-2 limitations | ✓ | `gap_report.py:28-100` + builder :119-207 | — |
| 4.4 IP profiles + generic fallback | ✓ | `ip_profiles.py:26-124` | — |
| Insights phase opt-in; disabled = byte-identical | ✓ | `insights_pipeline.py:41-115`; guard test `test_disabled_insights_regression_guard` | — |
| Instruction set retrievable in-repo | ✗ | — | **gap**: baseline only via RECON/commits/CHANGELOG (this report records it) |
| Insights phase reachable from `main.py` CLI | ✗ | `main.py` fsm phase :227-292 never calls `run_insights_phase` | **gap**: API/example6 only (Phase B example wires completeness into the CLI flow) |
| Output-indicator consistency vs state | ✗ | nowhere | **gap** — created by Part 2 verdict; fixed in Section 3 |

## Part 2 — `EN_UVLO_1V2` port-role trace

### Experiment (user's exact CLI, 3 variants of `port_type`)

| Variant | states/transitions/guards (console) | `ldo_fsm.sv` | `ldo_fsm.vams` |
|---|---|---|---|
| `status` (committed) | 20 states, 37 transitions; `EN_UVLO_1V2` in guards (e.g. `DISABLED_2->DISABLED_3 (EN_UVLO_1V2 == 1)`) | baseline | baseline (pin in `inout` group) |
| `control` (input role) | **identical** | **identical** | pin moves to `input` group — only diff |
| `output` (user's edit) | **identical** | **identical** | pin moves to `output` group **and** gains a state-driven contribution `V(EN_UVLO_1V2) <+ (state==REGULATION…) ? 5.5 : 0.0` (fsm_codegen.py:326-339) **while the same pin is still sampled in guards** `V(EN_UVLO_1V2) > VTH_…` — the emitted model drives and reads its own status pin (combinational loop) |

So: **the flip changed nothing in FSM behavior** — only the emitted port-direction cosmetics,
plus, in the `output` case, an internally inconsistent .vams.

### Call chain (does the spec's port semantics survive each hop?)

| # | Hop | Code | Port direction/role consumed? |
|---|---|---|---|
| 1 | `--spec_json` → `Port` | `knowledge_graph.py:278-291` (`from_json`), `Port` :64-71 | `port_type`/`is_state_signal`/`fsm_role` stored. **No `direction` field exists** |
| 2 | SignalMap → `SignalCapture.signals` | `signal_capture.py:126-247` | name/kind only — direction n/a |
| 3 | digital/analog classification | `signal_capture.py:415-431` (`_classify_signals` → `_speckg_domain` :402-409) | **`domain` only** ('digital' forces digital); port_type ignored |
| 4 | state-signal selection | `signal_capture.py:433-461` (`get_logic_signal_matrix`) → **`knowledge_graph.py:191-198`** (`get_fsm_relevant_ports`) | **DECISIVE: line 194 `if p.is_state_signal` short-circuits** — status/output port_types included identically; `port_type` consulted only at :196 for the *else* branch (`enable/clock/control`) |
| 5 | state detection | `state_detector.py:30-38`; `main.py:251-254` | consumes the matrix from hop 4 — outputs are state bits |
| 6 | guard learning | `main.py:261-264` (`feat_mat = lm`), `transition_learner.py:129-133` (guard = changed pattern bits) | outputs become guard conditions (`EN_UVLO_1V2 == 1` observed) |
| 7 | naming | `state_detector.py:238-290` (`_apply_speckg_naming`, role_ports :249) | `fsm_role` consumed (spec-driven) — plus hardcoded fallbacks :263-265 |
| 8 | codegen | `fsm_codegen.py:245-249` (direction groups), :326-339 (ready-role drive when `port_type == 'output'`) | port_type consumed **only for cosmetic direction emission** and the output-drive block — after guards were already built from the pin |

### Verdict

**(b)-partial, with a causality hole — not (a), not (c).** FSM signal-role handling IS
spec-driven for *inclusion* (`is_state_signal` at `knowledge_graph.py:194`, `domain` at
`signal_capture.py:423-426`, `fsm_role` at `state_detector.py:249-265` all demonstrably control
behavior — deleting `is_state_signal` removes a pin from the state space). But the spec's
**input-vs-output semantics are dropped at `knowledge_graph.py:194`**: any `is_state_signal`
digital pin becomes a state variable and a guard feature regardless of `port_type =
status/output`, so the user's flip is a no-op for FSM behavior. Waveform-driven (c) exists only
as the fallback for signals with no matching port (`signal_capture.py:427` `_is_bimodal`) and
when the fsm-port∩digital intersection is empty (`signal_capture.py:449-450`) — it is not the
primary mechanism.

### Target semantics (for the record)
Digital **input/inout** ports drive state identification and are the only legal guard features
(causality). Digital **output/status** ports are excluded from guard causality but retained as
per-state **output signatures** (observed indicator value per state) and feed
completeness/gap reporting (a state whose observed `EN_UVLO_1V2` contradicts its `ready` role is
a reportable gap). Current behavior violates this: outputs are guards (hop 6) and no signature
or consistency artifact exists anywhere.

## Part 3 — hardcoded pin/signal names in the FSM path (non-test, non-example)

| Location | Names | Disposition |
|---|---|---|
| `state_detector.py:263-265` | `['EN'] ['FAULT'] ['POK']` role fallbacks | **REMOVE** (role-only; built-in specs declare roles) |
| `state_delta_fitter.py:67-69` | `'EN_LDO'`, `== 'EN'`, `'SCAN'` | **REMOVE** → fsm_role via spec_kg |
| `vi_correlation.py:35`, `state_signatures.py:28` | `== 'V_SUPPLY'` primary-supply pick | **REMOVE** → taxonomy hook/role |
| `ab_codegen.py:67,78` | `('V_SUPPLY','VPWR')` domain-supply pref | **REMOVE** → role/range rule (questionnaire item already flags it) |
| `gap_report.py:105-116` | `EN_LDO=…`, `SCAN_MODE_VSUPPLY=1`, `HIGH_POWER_MODE=…`, `V_SUPPLY->dropout` | **REMOVE** → derive stimulus pins from spec fsm_roles |
| `ab_model_builder.py:28-33` `DEFAULT_PIN_MAP` | `V_SUPPLY/VDD_1V2/AVSS/EN_LDO/HIGH_POWER_MODE` | justified (explicit, caller-overridable default) — Phase B derives it from taxonomy hooks with this map as last resort |
| `pin_taxonomy.py` (whole) | SREF pin table | justified: SREF data table by design |
| `ip_profiles.py`, `coverage.py:127`, `fsm_codegen.py:10-32` + name heuristics | `DISABLED/REGULATION/FAULT/CCM/…` | justified: **state-name** vocabulary (IP-class knowledge), not pin names |
| `signal_capture.py:59-123` (`load_synthetic`) | `EN/POK/FAULT/VOUT/…` | justified: synthetic demo generator, not decision logic |
| `phase1_spec_based.py:351` | `'FAULT' in sname` | justified: state-name heuristic, phase-1 legacy path (outside audited FSM flow) |
| `state_space.py:6` | `EN_LDO=0` | justified: docstring illustration |

## Section 3 preconditions
Verdict ≠ clean (b) ⇒ the Section-3 fix applies (spec-driven direction resolution, output
signatures, guard causality, output-consistency gap section, removals above). Executed only on
"Continue". Push target will be this same branch (linear continuation, no history rewrite).

## Phase B — executed (post-"Continue")

Implemented in the commits following this report (see CHANGELOG "branch audit Phase B"):

| Target semantics item | Now | Evidence |
|---|---|---|
| direction is spec property | `Port.direction` explicit or derived (`port_direction`: output/status→output, supply/ground/bulk/inout→inout, else input) | `core/spec_kg/knowledge_graph.py` |
| inputs only in states/guards | logic matrix = `get_fsm_input_ports()`; declared outputs excluded even in the waveform fallback | `core/fsm/signal_capture.py` (`get_logic_signal_matrix`) |
| outputs → per-state signatures | `get_output_signal_matrix()` + `compute_output_signatures()`; printed by the fsm phase; REGULATION/FAULT naming from `refine_names_with_outputs()` (hardcoded `EN`/`FAULT`/`POK` fallbacks removed) | `core/fsm/state_detector.py` |
| consistency reporting | `CoverageResult.output_consistency` + gap rows + Option-2 limitations | `core/fsm_completeness/coverage.py`, `gap_report.py` |
| combinational loop impossible | status pins emit as `output` and are driven from state; they can no longer be guard features by construction | `core/fsm/fsm_codegen.py` |
| hardcoded-name removals | `primary_input_supply` (taxonomy hook/capability), role-driven switch/hp-state checks, role/hook-driven domain supply nets, `derive_pin_map`, role-derived gap-report stimulus pins | registry/vi_correlation/state_signatures/state_delta_fitter/ab_codegen/ab_model_builder/gap_report |
| CLI example | `examples/example7_fsm_blut_cli.py` imports `main.build_parser`+`main.run_fsm_phase`, enforces the no-output-in-guards check, writes `gap_report_cli.*` | + INSTRUCTIONS.md subsection |

Re-run of the user's exact CLI on `regression1.bin`: 17 states / 33 transitions (was 20/37);
guards use only the 8 input pins; `EN_UVLO_1V2` appears solely in the signature table and as a
driven `output` in the .vams; 5 output-consistency contradictions reported (ready-role
indicator high in DISABLED-family states — consistent with the pin being UVLO-good rather than
regulation-ready; flagged for role review, not silently renamed). The flip experiment is now
behavioral: `port_type=control` puts the pin in the state space, `status`/`output` (or explicit
`direction`) makes it signature-only (regression-tested in
`test_spec_direction_flip_changes_fsm_semantics`). Suite 86/86.
