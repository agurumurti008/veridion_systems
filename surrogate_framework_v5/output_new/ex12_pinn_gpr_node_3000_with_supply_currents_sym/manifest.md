# example12 Run Manifest — Pipeline Structure

```
1. Load per_corner_correlation.json -> filter good corners
2. Global FSM (SignalCapture + FSMStateDetector + TransitionLearner + FSMValidator) -> state_defs, transitions
3. Phase2SimAugmented.build_dataset_from_blut(run_ids=good_qids)
   -> corner-and-state-labeled X, Y, feature_names
   -> target_encode_categorical_meta (single meta_corner variable)
4. Per state: PINN/GPR/NODE (informational) + PySR (--include_symbolic) equation (embedded)
5. core/current_insights: mux/supply/transition/efficiency findings
6. FSMCodeGenerator.generate_veriloga(output_equations=...) -> final .vams/.sv
```

BLUT: `blut_files/regression_multi_corner_sref_ldo.bin`
Correlation source: `output_fsm_correlation_2/per_corner_correlation.json`
Good corners: 126/135
FSM strategy: `hybrid`
States: ['DISABLED', 'REGULATION', 'REGULATION_2', 'REGULATION_3', 'REGULATION_4', 'REGULATION_5', 'DISABLED_2', 'REGULATION_6', 'REGULATION_7', 'REGULATION_8', 'REGULATION_9', 'REGULATION_10', 'REGULATION_11', 'REGULATION_12']
Transitions: 23
Models requested: ['pinn', 'gpr', 'node']
Equation source: PySR (--include_symbolic)

## Categorical corner codes (set meta_<key> to this value per simulated process)

- `meta_corner`: nn=nan, ss=nan, ww=nan

**Analog skeleton output-driving equations: EMBEDDED**
  states with equations: 14
  outputs: ['VDD_1V2', 'VDD_1V2_I', 'VPWR_I', 'FUN_DC_I', 'V_SUPPY_I']

## Output files

- `output_new/ex12_pinn_gpr_node_3000_with_supply_currents_sym/ldo_fsm_skeleton.vams` — final Verilog-A (FSM + self-checks + output equations)
- `output_new/ex12_pinn_gpr_node_3000_with_supply_currents_sym/ldo_fsm_skeleton.sv` — final SystemVerilog control skeleton
- `output_new/ex12_pinn_gpr_node_3000_with_supply_currents_sym/model_comparison.md` (+ .json)
- `output_new/ex12_pinn_gpr_node_3000_with_supply_currents_sym/current_insights_report.md` (+ .json)
