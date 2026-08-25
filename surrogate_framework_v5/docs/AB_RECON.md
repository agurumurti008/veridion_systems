# A+B Strategy Build — Gate 1 Recon Report

Base branch: `claude/fsm-ldo-output-fix-hphkez` (commit `2998b43`).
Feature branch: `claude/ab-strategy-sref-poc`.
digiTwin v8 (authoritative): `origin/experiment1:DigiTwin_v8/` — checked out at repo
root and **re-vendored into `surrogate_framework_v5/digitwin/` (commit `e0c30f0`)**;
see Section 4 for the sync report.
LDO spec reference: `configs/LDO_1V2.json` — replaced by the authoritative
`experiment1` version (29 SREF ports; commit `9679210`).

## 1. Actual state of `surrogate_framework_v5/`

```
surrogate_framework_v5/
├── main.py                      # CLI orchestrator (--phase 1|fsm|2|3, --fsm_strategy, --blut_path, --signal_map_json)
├── torch_shim.py                # NumPy torch-compatible shim (nn.Sequential/Linear/Tanh/Adam/DataLoader...)
├── requirements.txt             # numpy/scipy/pandas/scikit-learn/networkx/matplotlib (torch optional)
├── INSTRUCTIONS.md, README.md
├── blut_files/
│   ├── regression1.bin          # SREF_LDO1V2_LP_TB multi-run BLUT (59 runs TC_001..TC_060, 71 183 samples)
│   └── regression2.bin          # second SREF regression BLUT (reaches REGULATION w/ UVLO_OK=1)
├── configs/
│   ├── ldo_spec.json, ota_spec.json
│   ├── LDO_1V2.json             # 1.2V LDO SpecKG matching the SREF testbench
│   └── signal_map_ldo.json      # SpecKG <-> SREF_LDO1V2_LP_TB.* map (9 entries)
├── core/
│   ├── tensor_utils.py          # to_np / to_f32 / scalar / make_float_tensor / assign_col / get_shape
│   ├── spec_kg/knowledge_graph.py
│   ├── fsm/{signal_capture,state_detector,transition_learner,fsm_codegen}.py
│   ├── models/{pinn,neural_ode,gpr_surrogate}.py
│   ├── interpretability/symbolic_regression.py
│   └── phases/{phase1_spec_based,phase2_sim_augmented,phase3_silicon,blut_reference}.py
├── data/pipeline.py             # LHS synthetic generator + CSV parser
├── digitwin/                    # vendored BLUT support — v8 after sync (see §4)
│   ├── blut_format.py           # VERSION = 8, byte-for-byte from DigiTwin_v8 (v6/v7 reads kept)
│   ├── blut_reader_core.py      # open_blut / decode / resolve_requests
│   ├── blut_reader_ext.py       # load_run_matrix / load_all_runs / iter_run_transitions / parse_meta_string
│   └── spec_signal_map.py       # SignalMap (kind-aware, run-scoped)
├── examples/example{1..4}_*.py
├── output/ldo_fsm.{vams,sv}     # committed outputs of the documented regression1 FSM run
└── tests/test_framework.py      # self-contained runner, 48 tests, @test decorator + TESTS list
```

### Version markers found

| Marker | Value found | Where |
|---|---|---|
| BLUT format version (vendored, after sync) | **v8** — `VERSION = 8`, `RunMeta.corner_id` first-class, `(run_id, corner_id)` uniqueness key, v6/v7 backward-compat reads (`corner_id=""`). Byte-for-byte copy of `experiment1:DigiTwin_v8/blut_format.py`. Pre-sync the vendored copy was v7 — see Section 4. | `digitwin/blut_format.py:38,141` |
| FSM detector strategy set | `{'logic', 'cluster', 'hybrid'}` (assert in ctor); GMM+BIC in `_detect_cluster` (n_components 2..8, `GaussianMixture(...).bic`), KMeans sub-split in `_detect_hybrid` | `core/fsm/state_detector.py` |
| Boundary-mask support | present end-to-end: `SignalCapture.get_boundary_mask()` → `TransitionLearner.learn(..., boundary_mask=)` | `core/fsm/{signal_capture,transition_learner}.py` |
| Verilog-A codegen entry | `FSMCodeGenerator.generate_veriloga(state_defs, transitions, ports)` — emits SpecKG-derived ports, `VTH_*` threshold params, priority `if/else-if` state updates **inside a plain `analog begin` case** (no `@(cross)` anywhere; no `$bound_step` yet) | `core/fsm/fsm_codegen.py` |
| SV codegen entry | `FSMCodeGenerator.generate_systemverilog(state_defs, transitions)` | `core/fsm/fsm_codegen.py` |
| Test runner | `python tests/test_framework.py`; `@test` decorator appends to `TESTS`; **48/48 passing** at branch point; append-only numbering convention documented in-file | `tests/test_framework.py` |
| Torch presence | optional; `torch_shim` auto-installed via `try: import torch / except: import torch_shim` bootstrap in `main.py`, models, tests | `main.py:11`, `torch_shim.py` |

## 2. Integration-point table

| Capability | Module | Exact symbol / signature as found | A+B usage |
|---|---|---|---|
| FSM state detection | `core/fsm/state_detector.py` | `FSMStateDetector(strategy='hybrid', spec_kg=None)`; `.detect(logic_matrix, logic_names, analog_features=None) -> np.ndarray`; results in `.state_defs: Dict[int, dict]` (`name`, `pattern`, `count`), `.state_sequence` | **reused as-is** (mode/control layer of A+B) |
| Transition learning | `core/fsm/transition_learner.py` | `TransitionLearner(fsm_tree_depth=4)`; `.learn(state_sequence, feature_matrix, feature_names, state_defs, boundary_mask=None) -> List[Transition]`; `Transition(from_state, to_state, from_name, to_name, conditions: List[str], guard_expression: str, probability, feature_importances)` | **reused as-is** (guards drive ABModel + codegen) |
| BLUT open/decode | `digitwin/blut_reader_core.py` | `open_blut(path) -> BlutFile` (`.runs: Dict[run_id, Dict[corner_id, RunMeta]]` — v8 nested shape); `decode(path, run, sig_name) -> np.ndarray`; `parse_signal_token` supports `name@run_id@corner_id`; `resolve_requests(blut, tokens, requested_runs, requested_corners=None)` | **re-vendored from v8** (verbatim bodies) |
| BLUT multi-run load | `digitwin/blut_reader_ext.py` | `load_all_runs(path, signal_names=None, current_suffixes=None) -> List[dict]` (keys `run_id, corner_id, meta, time, voltage_names, voltage_matrix, current_names, current_matrix`); `load_run_matrix(path, run, signal_names=None, current_suffixes=None, signal_map=None) -> dict`; new `iter_runs(blut)` / `get_run(blut, run_id, corner_id=None)` helpers; `parse_meta_string(meta) -> Dict[str,str]` | **extended** for the v8 nested runs shape |
| BLUT writing | `digitwin/blut_format.py` | `write_file_header(f, n_runs, flags=0)`; `write_run_header(f, run_number, run_id, meta, times)`; `write_signal_block(f, name, idxs, vals, encoding, offset, qstep, compress, hold_mode=HOLD_ZOH)`; `patch_run_n_signals(f, off, n)`; `patch_file_header_counts(f, n_runs)` — same pattern as tests' `_write_synthetic_blut` | **reused as-is** by `param_blut_store` + example5 synthetic-BLUT builder |
| Signal capture / classification | `core/fsm/signal_capture.py` | `SignalCapture(spec_kg=None)`; `.load_from_blut(blut_path, run_id=None, signal_map=None, current_suffixes=None)`; `.get_logic_signal_matrix() -> (matrix, names, time)`; `.get_analog_features(n_windows)`; `.get_boundary_mask()`; `.run_boundaries/.run_ids/.run_meta` | **reused as-is** |
| SignalMap resolution | `digitwin/spec_signal_map.py` | `SignalMap.from_spec_json(path)`; `.resolve(speckg_name, run_id=None)`; `.resolve_with_kind(name, kind, run_id=None)`; `.reverse_resolve(blut_signal, run_id=None, kind=None)`; `.auto_suggest(kg, blut_names)` | **reused as-is** |
| SpecKG load | `core/spec_kg/knowledge_graph.py` | `SpecKG.from_json(path)`; `Port(name, port_type, domain, voltage_range, current_range, is_state_signal, fsm_role)`; `.get_fsm_relevant_ports()`; `.specs: List[SpecConstraint]` (has `transient_weight` — used as the loss weight; there is **no field literally named `loss_weight`**) | **reused as-is**; `objectives.py` maps `SpecConstraint.transient_weight` → loss weights |
| Phase-2 dataset builder | `core/phases/phase2_sim_augmented.py` | `Phase2SimAugmented(spec_kg, use_wandb=False)`; `.build_dataset_from_blut(blut_path, signal_map, input_signal_names, output_signal_names, fsm_detector, current_suffixes=None) -> dict` | **bypassed** for the POC backbone; available for optional NN residual training data |
| Thin-state reference filler | `core/phases/blut_reference.py` | `fill_missing_state_transient(state_defs, transitions, run_dicts, state_name, ...)`; `count_samples_per_state`; `find_thin_states`; `StateReferenceNotFoundError` | **reused** by `state_delta_fitter` for thin states |
| NODE residual pattern | `core/models/neural_ode.py` | `ODEFunc.residual_net = nn.Sequential(...)`, residual added to physics RHS in `.forward(t, state)`; shim-compatible via `to_np` | **pattern copied** for the optional ≤10% RHS residual (off by default) |
| Verilog-A emitter | `core/fsm/fsm_codegen.py` | `FSMCodeGenerator(spec_kg=None, ip_type='LDO')`; `.generate_veriloga(state_defs, transitions, ports=None) -> str`; helpers `_vid(name)`, `_sv_guard(expr, signal_names)`, `_guard_signal_names`, `_digital_thresholds`, `_va_guard` | **wrapped/extended** by `ab_codegen` (adds `$bound_step` sampling, per-state param `case` overrides, `$table_model` PVT tables, structural analog core) |
| Test runner | `tests/test_framework.py` | `@test` decorator → `TESTS` list; `run_all()`; plain asserts; run `python tests/test_framework.py`; currently **48 tests** | **extended, append-only** (≥14 new) |
| Tensor/shim utilities | `core/tensor_utils.py`, `torch_shim.py` | `to_np(x)`, `to_f32(x)`, `scalar(x)`, `make_float_tensor(arr)`; shim provides `nn.Sequential/Linear/Tanh`, `optim.Adam`, `DataLoader` | **reused as-is** by `param_nn` and optional residual |
| Numerics stack | `requirements.txt` | `scipy>=1.9` guaranteed → `scipy.optimize.least_squares`, `differential_evolution`, `scipy.integrate.solve_ivp` all available | **used directly** by templates + fitting |
| `configs/LDO_1V2.json` schema (Section 7 consumer) | `configs/LDO_1V2.json` (authoritative, from `experiment1`) | Top level: `ip_type, ports[], specs[], physics_rules[], fsm_states[], bridges{}`. Each port: `name, port_type, domain, voltage_range:[lo,hi], current_range:[lo,hi], is_state_signal, fsm_role`. `port_type` vocabulary as found: `supply, ground, bulk, output, feedback, enable, status, select, control, bias_current_sink, bias_current_source, feedback_input, reference_input` (SpecKG stores it as a plain str — the extended vocabulary loads without enum validation). `domain` ∈ `digital / analog / power`. **There is no separate named-voltage-domain table**: each pin carries its own `voltage_range`, and digital pins' logic domain is `[0, 5.5]` (V_SUPPLY-referenced) in this spec — so connect-module grouping (Section 7) is derived by grouping logic pins on identical `voltage_range` and referencing the supply pin whose range upper bound matches (here `V_SUPPLY`/`VPWR`, ground `AVSS`); `_ok` windows come from each supply/ground/bias pin's own `voltage_range`/`current_range` | **consumed** by `ab_codegen` connect-module + `_ok` emission; **flag:** the JSON does not name each logic pin's supply net explicitly — the supply-net association rule above goes into the questionnaire with the `V_SUPPLY`/`AVSS` default |

## 3. Merge plan — what powers A+B unchanged vs. bypassed

**Reused unchanged (Strategy A machinery):**
- Full FSM auto-derivation pipeline: `SignalCapture.load_from_blut` (multi-run, boundary-mask) → `FSMStateDetector` (logic/cluster/hybrid, GMM+BIC) → `TransitionLearner` (pattern-diff guards) → `FSMValidator`. This is the **mode/control layer** of every ABModel.
- BLUT ingestion (`blut_reader_core/ext`) and BLUT writing (`blut_format` writer functions) — the latter is what `param_blut_store` persists fitted vectors through.
- `SignalMap` + SpecKG (`configs/LDO_1V2.json` extended into `configs/sref_ldo1v2_lp_spec.json`).
- `tests/test_framework.py` runner and the `torch`/`torch_shim` bootstrap convention.

**Bypassed for the POC (available, not the backbone):**
- Per-state PINN/NODE/GPR training (`Phase2SimAugmented.initialize_models/incremental_train`): the analog backbone is the **physical template** (Section 3 of the build prompt). The NODE residual pattern is reused only for the optional, default-off ≤10% RHS residual.
- `phase1_spec_based` / `phase3_silicon` / `interpretability`: untouched.
- `FSMCodeGenerator.generate_veriloga` continues to serve the standalone `--phase fsm` flow; `ab_codegen` emits the combined structural model and is the only emitter for ABModel (it reuses `_vid`/guard-translation helpers rather than duplicating them).

**New modules (all under `surrogate_framework_v5/`):**
`core/templates/` (Section 3), `core/fitting/` (Sections 4–5, incl. vendored minimal Vector Fitting), `core/pvt/` (Section 6), `core/ab_integration/` (Section 7), plus `configs/sref_ldo1v2_lp_spec.json`, `configs/sref_architecture_questionnaire.yaml`, `examples/example5_sref_ab_poc.py`.

## 4. digiTwin v8 sync report

The in-tree copy was **older (v7)**; v8 is authoritative, so it was re-vendored
(dedicated commit `e0c30f0`):

- `digitwin/blut_format.py` ← `experiment1:DigiTwin_v8/blut_format.py` **byte-for-byte**
  (verified with `diff`): `VERSION = 8`, `RunMeta.corner_id` first-class,
  `write_run_header(..., corner_id="")` backward-compatible, v6/v7 reads return
  `corner_id=""`, `read_run_meta` now takes `version`.
- `digitwin/blut_reader_core.py` ← re-trimmed from `DigiTwin_v8/digitwin_blut_reader.py`
  with **function bodies verbatim** (same CLI/plot trim as the original vendoring;
  only the module docstring and the package-relative `from . import blut_format as bf`
  differ). Brings the nested `BlutFile.runs: run_id -> {corner_id -> RunMeta}` shape,
  3-segment signal tokens, and corner-aware `resolve_requests`.
- `DigiTwin_v8/` (builder, reader, corner_id tests) checked out at repo root as the
  authoritative reference.

**Downstream call sites affected by the sync (all updated, suite 48/48 green):**

| Call site | What changed |
|---|---|
| `digitwin/blut_reader_ext.py` — `list_all_signal_base_names`, `load_all_runs` | iterate via new `iter_runs(blut)` (flattens corner maps in file order); run dicts gain a `"corner_id"` key |
| `digitwin/blut_reader_ext.py` — new `iter_runs` / `get_run` | added as the sanctioned nested-shape accessors so no consumer re-implements corner disambiguation |
| `core/fsm/signal_capture.py` — `load_from_blut(run_id=...)` | accepts plain `run_id` (resolved when unambiguous) or `run_id@corner_id`; new `self.run_corners` list parallel to `run_ids` |
| `core/phases/phase2_sim_augmented.py` — `build_dataset_from_blut` | iterates the full `(run_id, corner_id)` matrix; per-row run ids are corner-qualified |
| `tests/test_framework.py` — `test_blut_roundtrip_2run_4signal`, `test_load_run_matrix_shapes` | use `iter_runs`/`get_run`; roundtrip additionally asserts `corner_id == ""` for corner-less writes |
| `examples/example4_blut_pipeline.py` — step-6 per-run loop | iterates corner-qualified run ids |
| `core/phases/blut_reference.py`, `main.py` | **no change needed** — consume `load_all_runs` run dicts / `SignalCapture` only |

**`param_blut_store` (Section 6) therefore keys on real `(run_id, corner_id)`**:
fitted vectors are written with `write_run_header(..., corner_id=<corner>)` and read
back through `blut.runs[run_id][corner_id]` — no run_id-encoding convention needed.

## 4b. Authoritative LDO spec adoption (commit `9679210`)

`configs/LDO_1V2.json` was replaced by the `experiment1` version: 29 SREF ports with
real pin names, per-pin ranges, and extended `port_type`/`fsm_role` vocabulary
(loads cleanly — `SpecKG.from_json` stores `port_type` as plain str).
`configs/signal_map_ldo.json` was regenerated so every spec port maps onto its
`SREF_LDO1V2_LP_TB.*` BLUT net (the two isense pins named in the pin taxonomy do not
exist in the regression BLUTs and stay unmapped/reported). The documented FSM command
re-verified: 20 named states / 37 transitions with guards over the real control pins
(`EN_LDO`, `EN_UVLO_1V2`, `VPWR_SEL`, `PAD_VDD1V2_SEL`, `SCAN_MODE_VSUPPLY`, ...).
Note for Sections 5/8: this spec marks 10 digital pins `is_state_signal`, so the raw
logic state space is wide; per-state delta fitting will use the `mode_affected`
manifest gate plus the ≤40-floated-dimensions cap to keep identifiability honest.

## 5. Existing-data reality check (affects Sections 4–5 fidelity, flagged early)

`blut_files/regression*.bin` contain **testbench control/supply nets only** (EN_LDO, EN_UVLO_1V2, HIGH_POWER_MODE, UVLO_GD_OR_OVERRIDE_MPOS, V_SUPPLY, VDD_1V2, VFB, VREF, IBIAS/ICONST nets...) — no AC/PSRR sweeps, no per-corner labeling in `meta` (meta strings are empty), and VDD_1V2 rarely sits in regulation. Consequences already anticipated by the build prompt:
- Stage LINEAR will use the **transient-derived path** (ERA on load/EN-step ring-down) unless AC data is supplied; the fit report will say so.
- example5 therefore builds a **synthetic 3-corner SREF-like BLUT** (template-generated with known ground-truth params per corner, written as v8 with real `corner_id`s) as its default data source, and accepts a real BLUT path as an override.
