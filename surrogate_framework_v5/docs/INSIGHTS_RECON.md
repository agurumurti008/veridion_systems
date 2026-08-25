# Insights + FSM-Completeness Increment — Gate 1 Recon

Branch `claude/insights-fsm-completeness`, forked from `claude/ab-strategy-sref-poc`
(`f80effc`). POC branch untouched.

## 1. Post-POC tree (new code lands under the two new package dirs)

```
core/
├── fsm/{signal_capture,state_detector,transition_learner,fsm_codegen}.py
├── templates/{param_manifest,base_template,ldo_pmos_template,pin_taxonomy}.py
├── fitting/{objectives,vector_fitting,single_corner_fitter,state_delta_fitter}.py
├── pvt/{provider,param_lut,param_blut_store,param_nn}.py
├── ab_integration/{ab_model_builder,ab_codegen}.py
├── numpy_mlp.py
├── current_insights/     ← NEW (Capability A)
└── fsm_completeness/     ← NEW (Capability B)
digitwin/{blut_format,blut_reader_core,blut_reader_ext,spec_signal_map}.py
configs/{LDO_1V2,signal_map_ldo,sref_ldo1v2_lp_spec,sref_architecture_questionnaire}.*
examples/example{1..5}_*.py   ← add example6_insights_gaps.py
tests/test_framework.py       ← 65 tests, append-only
```

## 2. Integration-point table (exact API as found)

| Capability | Symbol / signature | Insights use |
|---|---|---|
| Current signals | `SignalCapture.current_signals: dict[speckg_name→ndarray]`; `get_current_features(n_windows=10)→DataFrame` (mean/std/slope per window, run-boundary-clipped); `run_boundaries`/`run_ids`/`run_corners`/`get_boundary_mask()` | analyzers consume `current_signals` + per-run slices; never touch the logic matrix |
| Kind resolution | `classify_signal_kind(name, suffixes=["$flow"])`, `strip_kind_suffix`, `SignalMap.resolve_with_kind(name, kind, run_id)`, `reverse_resolve(blut_signal, run_id, kind)` | registry maps pin↔`$flow` path↔domain |
| Multi-run/corner load | `load_all_runs(path, names=None, suffixes=None)→[{run_id, corner_id, time, voltage_names/matrix, current_names/matrix, meta}]`; `open_blut().runs[run_id][corner_id]`; `get_run(blut,run_id,corner_id=None)`, `iter_runs(blut)` | analyzers + coverage iterate the run×corner matrix |
| Spec-JSON pin schema | port: `name, port_type, domain∈{digital,analog,power}, voltage_range[lo,hi], current_range[lo,hi], is_state_signal, fsm_role`; `SpecKG.from_json`, `.ports`, `.specs` (`min_val/max_val/nominal/unit/frequency/transient_weight`) | registry domain + expected-range source; attribution cross-check |
| Template load model | `dc_solve(params,vin,iload,mode)→{vout,iq,i_pass,dropout_margin,in_dropout,...}`; `simulate(...)→{...,i_vin,i_pass}`; `small_signal(...)→{...,zout,psrr_db,poles}`. Node: `i_c = i_pass − iload − vout/(Rf1+Rf2) − k_load·vout`; soft limit `I_lim·tanh(i_pass/I_lim)` | 3.3 capacity→`I_lim`/`k_load` bounds; 3.9 impedance vs `zout`; 3.11 vs fitted `C_out` |
| Pin taxonomy | `PinInfo(name,category,hook,questionnaire,safe_default,note)`; `categorize_pin`, `hook_for_pin`, `questionnaire_pins`. SEL pins `VPWR_SEL`/`PAD_VDD1V2_SEL` (cat=mode, hook=None); `SREF_ADD_LDO1V2_LOAD_MPOS` (hook=`test_load`); isense pins | 3.4 SEL-class enumeration; 3.8 emits enrichment proposal back here |
| FSM detector | `FSMStateDetector.detect(logic_matrix, logic_names, analog_features=None)→seq`; `.state_defs[sid]={name,pattern,count}` | **inputs are logic+analog only; currents MUST NOT be added** (contract row 2). 3.10 relabels `state_defs` post-detection |
| Transition learner | `TransitionLearner.learn(seq, feat, names, state_defs, boundary_mask=None)→[Transition{from/to_state,conditions,guard_expression,probability}]` | B expected-transition matrix |
| Fit result | `FitResult{params, per_stage_residuals, frozen_params, spec_compliance, identifiability}` | 3.3/3.9/3.11 reconcile + log agreement |
| Codegen | `emit(ab_model, corner, table_dir=None, fsm_ts=1e-7)→str` (header via `A(...)`, `ok_windows()`, `guard_pins`, per-state `case` override, `I(vin,gnd)` draw); `emit_pvt_tables` | add `LIMITATIONS:` header lines, per-state Iq `I(vin)` currents, dummy-load load-model comment |
| ABModel build | `build_ab_model(template, state_defs, transitions, provider, spec_kg, state_param_set=None, pin_map=None, fsm_ts=1e-7)`; `.simulate(stimulus, corner)` | Section 5 optional `insights` phase after detection |

## 3. Signal inventory — SREF `$flow` currents in real BLUT (`regression1.bin`)

23 of 30 pins carry a `$flow` probe at the DUT boundary. **Convention delta (important):** currents live at `SREF_LDO1V2_LP_TB.X_DUT.<PIN>_$flow` → base `…X_DUT.<PIN>_` (trailing `_` is the DUT-internal net; probe adds `$flow`). Existing `signal_map_ldo.json` maps *voltages* at `SREF_LDO1V2_LP_TB.<PIN>` (TB level, no `X_DUT`, no trailing `_`) — so the current registry needs its own `kind:"current"` entries with the `X_DUT.<PIN>_` path. Measured magnitudes are µA-scale (filtering-relevant).

| pin | blut base path (kind=current) | domain | expected \|I\| (spec current_range) | measured max (TC_001) |
|---|---|---|---|---|
| V_SUPPLY | X_DUT.V_SUPPLY_ | power/supply | 0–0.25 A | 400 µA |
| VDD_1V2 (out) | X_DUT.VDD_1V2_ | power/supply | 0–0.20 A | 145 µA |
| VDD_1V2_EXT | X_DUT.VDD_1V2_EXT_ | power/supply | 0–0.20 A | 9.4 mA |
| VPWR | X_DUT.VPWR_ | power/supply | 0–0.25 A | — |
| MOST_POS / ISO / FUN_DC | X_DUT.{MOST_POS,ISO,FUN_DC}_ | power/supply | 0–0.25 A | — |
| SREF_ADD_LDO1V2_LOAD_MPOS | X_DUT.SREF_ADD_LDO1V2_LOAD_MPOS_ | digital/load_control | 0–1 mA | 4.5 µA |
| VPWR_SEL / PAD_VDD1V2_SEL | X_DUT.{VPWR_SEL,PAD_VDD1V2_SEL}_ | digital/select | 0–1 mA | — |
| AVSS / PBKG (returns) | X_DUT.{AVSS,PBKG}_ | power/ground | 0–0.25 A | — |
| VFB / VREF / floop_* | X_DUT.{VFB,VREF,floop_in,floop_out}_ | analog | 0–0.1 mA | — |

No `$flow` probe for: `GND`, `IBIAS_SNK_25nA_[0..2]`, `ICONST_75A`, `SREF_EN_ISENSE…`, `SREF_LDO_ISNS_DIS…` → those insights fall back to synthetic/spec-declared, flagged by the registry.

## 4. B — evaluable now vs needs new runs

| Check | From data present | Needs new run |
|---|---|---|
| State coverage vs reference space | ✅ 59 runs in `regression1.bin` | — |
| Transition coverage | ✅ observed edges | — |
| Transient richness (undershoot+recovery-to-band) | ⚠️ only where a capture holds full settling | **load-step runs with ≥k×settling dwell** |
| Corner×state | ⚠️ real BLUT `corner_id=""` (v7-origin), meta empty | **corner-tagged v8 runs** (POC synth already v8-tagged) |
| Mux current-verification (3.4) | ⚠️ probes exist, but stimulus must toggle SEL with the alt supply live | **VPWR_SEL-toggle run, both supplies high** |
| Dummy-load auto-detect (3.8) | ✅ `SREF_ADD…_$flow` present; needs an assertion edge at constant ext. stimulus | edge present in a mode run |

**Demonstration plan (Section 6):** the bundled BLUTs have empty meta / uncertain SEL-toggle stimulus, so `example6` builds synthetic v8 runs with *controlled* current redistribution (mux pass + a constructed no-shift bug), a dummy-load assertion, a load-step-to-capacity, plus one omitted and one clipped-settling transition — giving every analyzer and the gap report real evidence. `--blut` accepts real SREF data (registry auto-maps the `X_DUT.<PIN>_` currents).

## 5. Contract enforcement points (code structure)

- Currents-are-evidence: `current_insights/*` import `SignalCapture.current_signals` / run dicts and `FSMStateDetector.state_defs` (read-only); none write the logic matrix passed to `detect()`. Only `state_signatures.py` (3.10) returns relabel *proposals* applied post-detection.
- Filtering-before-inference: every analyzer takes signals through `filtering.py` first; filter choice/params logged per signal in the report.
- Actionable: all analyzers return `list[Finding]` (`severity, evidence, affected pins/states, recommended_action`).
- Regression guard: insights phase is opt-in; with it disabled, `example5` and `emit()` produce byte-identical output paths (Section 5.4 test).
