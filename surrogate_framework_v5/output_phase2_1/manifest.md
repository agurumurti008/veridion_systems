<<<<<<< HEAD
# example11 Run Manifest

BLUT: `blut_files/regression_multi_corner_sref_ldo.bin`
Correlation source: `output_fsm_correlation_2/per_corner_correlation.json`
=======
# example11 Run Manifest — Pipeline Structure

```
1. Load per_corner_correlation.json -> filter good corners
2. Global FSM (SignalCapture + FSMStateDetector + TransitionLearner + FSMValidator) -> state_defs, transitions
3. Phase2SimAugmented.build_dataset_from_blut(run_ids=good_qids)
   -> corner-and-state-labeled X, Y, feature_names
4. Per state: GPR/SMT (informational) + linear equation (embedded)
5. core/current_insights: mux/supply/transition/efficiency findings
6. FSMCodeGenerator.generate_veriloga(output_equations=...) -> final .vams/.sv
```

BLUT: `blut_files/regression_multi_corner_sref_ldo.bin`
Correlation source: `output/per_corner_correlation.json`
>>>>>>> 7928143 (updated code to add pinn, pysr and slowness)
Good corners: 126/135
FSM strategy: `hybrid`
States: ['DISABLED', 'REGULATION', 'REGULATION_2', 'REGULATION_3', 'REGULATION_4', 'REGULATION_5', 'DISABLED_2', 'REGULATION_6', 'REGULATION_7', 'REGULATION_8', 'REGULATION_9', 'REGULATION_10', 'REGULATION_11', 'REGULATION_12']
Transitions: 23
<<<<<<< HEAD
Models requested: ['gpr', 'smt']
=======
Models requested: ['gpr']
Equation source: linear

**Analog skeleton output-driving equations: EMBEDDED**
  states with equations: 14
  outputs: ['VDD_1V2', 'VPWR_I', 'FUN_DC_I', 'V_SUPPLY_I', 'VDD_1V2_EXT_I']

## Output files

- `output_phase2_1/ldo_fsm_skeleton.vams` — final Verilog-A (FSM + self-checks + output equations)
- `output_phase2_1/ldo_fsm_skeleton.sv` — final SystemVerilog control skeleton
- `output_phase2_1/model_comparison.md` (+ .json)
- `output_phase2_1/current_insights_report.md` (+ .json)
>>>>>>> 7928143 (updated code to add pinn, pysr and slowness)
