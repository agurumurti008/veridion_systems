# example17 Run Manifest — Pipeline Structure

```
1. Load per_corner_correlation.json -> filter good corners
2. Global FSM (SignalCapture + FSMStateDetector + TransitionLearner + FSMValidator) -> state_defs, transitions
3. Validate requested signal names against the actually-resolved signal set (fast-fail on a typo); gray-box aux signals (VFB/VFB_I/VREF/iload) checked softly
4. Phase2SimAugmented.build_dataset_from_blut(run_ids=good_qids) -> corner-and-state-labeled X, Y (+ gray-box aux columns), feature_names + target_encode_categorical_meta
5. NEW (item 6): per-corner gray-box fit of LdoPmosTemplate via SingleCornerFitter, with Rf1/Rf2 identified from VFB/VFB_I (falls back tier-by-tier — see module docstring)
6. Derivative (+ optional integral) features per input signal, per-run/run-boundary-safe
7. Per state: GPR/SMT/PINN/NODE (informational; GPR/SMT/PySR sub-capped) + PySR (--include_symbolic) equation, ddt()/idt() token rewrite
8. FSMCodeGenerator.generate_veriloga(output_equations=...) -> final .vams/.sv
```

BLUT: `blut_files/regression_multi_corner_sref_ldo.bin`
Correlation source: ``
Good corners: 126/135
FSM strategy: `hybrid`
States: ['DISABLED', 'REGULATION', 'REGULATION_2', 'REGULATION_3', 'REGULATION_4', 'REGULATION_5', 'DISABLED_2', 'REGULATION_6', 'REGULATION_7', 'REGULATION_8', 'REGULATION_9', 'REGULATION_10', 'REGULATION_11', 'REGULATION_12']
Transitions: 23
Models requested: ['gpr', 'smt', 'pinn', 'node']
Equation source: PySR (--include_symbolic)

## Gray-box fit (item 6 + round-3 fixes)

Rf1/Rf2 identification tier BY PROCESS: {'nn': 1, 'ss': 1, 'ww': 1}
Processes fitted (pooled LUT entries): 3
Enable trace source: FSM state name (matched ['DISABLED', 'SHUTDOWN'])
Bypass fraction excluded: 0.0%
Full report: `output_new/ex17_graybox_new_bin_round_3/graybox_fit_report.md` (+ .json)

## Categorical corner codes (set meta_<key> to this value per simulated process)

- `meta_corner`: nn=0.3461, ss=-0.4769, ww=-0.7629

**Analog skeleton output-driving equations: EMBEDDED**
  states with equations: 14
  outputs: ['VDD_1V2']
  ddt() present: False   idt() present: False

## Output files

- `output_new/ex17_graybox_new_bin_round_3/ldo_fsm_skeleton.vams` — final Verilog-A (FSM + self-checks + differential output equations)
- `output_new/ex17_graybox_new_bin_round_3/ldo_fsm_skeleton.sv` — final SystemVerilog control skeleton
- `output_new/ex17_graybox_new_bin_round_3/model_comparison.md` (+ .json)
- `output_new/ex17_graybox_new_bin_round_3/graybox_fit_report.md` (+ .json)
- `output_new/ex17_graybox_new_bin_round_3/parameter_sensitivity_map.md` (+ .json) — item 4a engineering-insight mechanism
- `output_new/ex17_graybox_new_bin_round_3/ldo_analog_core_nn.vams` — fitted analog core (nn)
- `output_new/ex17_graybox_new_bin_round_3/ldo_analog_core_ss.vams` — fitted analog core (ss)
- `output_new/ex17_graybox_new_bin_round_3/ldo_analog_core_ww.vams` — fitted analog core (ww)
- `output_new/ex17_graybox_new_bin_round_3/ldo_top_nn.vams` — top-level wrapper (nn, item 3)
- `output_new/ex17_graybox_new_bin_round_3/ldo_top_ss.vams` — top-level wrapper (ss, item 3)
- `output_new/ex17_graybox_new_bin_round_3/ldo_top_ww.vams` — top-level wrapper (ww, item 3)
- `output_new/ex17_graybox_new_bin_round_3/graybox_process_lut.blut` — process LUT param store
