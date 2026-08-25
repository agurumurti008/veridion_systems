# example17 Run Manifest — Pipeline Structure

```
1. Load per_corner_correlation.json -> filter good corners
2. Global FSM (SignalCapture + FSMStateDetector + TransitionLearner + FSMValidator) -> state_defs, transitions
3. Validate requested signal names against the actually-resolved signal set (fast-fail on a typo); gray-box aux signals (VFB/VFB_I/VREF/iload) checked softly
4. Phase2SimAugmented.build_dataset_from_blut(run_ids=good_qids) -> corner-and-state-labeled X, Y (+ gray-box aux columns), feature_names + target_encode_categorical_meta
5. NEW (item 6): per-corner gray-box fit of LdoPmosTemplate via SingleCornerFitter, with Rf1/Rf2 identified from VFB/VFB_I (falls back tier-by-tier — see module docstring)
6. Derivative (+ optional integral) features per input signal, per-run/run-boundary-safe
7. Per state: GPR/SMT/PINN/NODE (informational; GPR/SMT/PySR sub-capped) + degree-2 polynomial + differential equation, ddt()/idt() token rewrite
8. FSMCodeGenerator.generate_veriloga(output_equations=...) -> final .vams/.sv
```

BLUT: `blut_files/regression_multi_corner_sref_ldo.bin`
Correlation source: `output_fsm_correlation_2/per_corner_correlation.json`
Good corners: 126/135
FSM strategy: `hybrid`
States: ['DISABLED', 'REGULATION', 'REGULATION_2', 'REGULATION_3', 'REGULATION_4', 'REGULATION_5', 'DISABLED_2', 'REGULATION_6', 'REGULATION_7', 'REGULATION_8', 'REGULATION_9', 'REGULATION_10', 'REGULATION_11', 'REGULATION_12']
Transitions: 23
Models requested: ['gpr', 'smt', 'pinn', 'node']
Equation source: degree-2 polynomial + differential

## Gray-box fit (item 6 — new this pass)

Rf1/Rf2 identification tier: 1
Corners fitted: 27
Full report: `output_new/ex17_graybox_1/graybox_fit_report.md` (+ .json)

## Categorical corner codes (set meta_<key> to this value per simulated process)

- `meta_corner`: nn=0.1207, ss=-0.09835, ww=-0.3877

**Analog skeleton output-driving equations: EMBEDDED**
  states with equations: 14
  outputs: ['VDD_1V2', 'VPWR_I', 'V_SUPPLY_I', 'FUN_DC_I', 'MOST_POS_I']
  ddt() present: True   idt() present: False

## Output files

- `output_new/ex17_graybox_1/ldo_fsm_skeleton.vams` — final Verilog-A (FSM + self-checks + differential output equations)
- `output_new/ex17_graybox_1/ldo_fsm_skeleton.sv` — final SystemVerilog control skeleton
- `output_new/ex17_graybox_1/model_comparison.md` (+ .json)
- `output_new/ex17_graybox_1/graybox_fit_report.md` (+ .json)
