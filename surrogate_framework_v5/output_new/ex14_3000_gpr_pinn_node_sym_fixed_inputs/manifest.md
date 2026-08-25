# example14 Run Manifest — Pipeline Structure

```
1. Load per_corner_correlation.json -> filter good corners
2. Global FSM (SignalCapture + FSMStateDetector + TransitionLearner + FSMValidator) -> state_defs, transitions
3. Validate requested signal names against the actually-resolved signal set (fast-fail on a typo)
4. Candidate inputs = every resolvable non-output signal; select_relevant_inputs (mutual-info relevance + collinearity redundancy pruning) narrows to --max_auto_inputs, always force-including supply/ground/output-rail currents
5. Derivative (+ optional integral) features per selected input, per-run/run-boundary-safe
6. Per state: GPR/PINN/NODE (informational) + PySR (--include_symbolic) equation, ddt()/idt() token rewrite, transition()-wrapped
7. Transition-sensitivity report (informational)
8. FSMCodeGenerator.generate_veriloga(output_equations=...) -> final .vams/.sv
```

BLUT: `blut_files/regression_multi_corner_sref_ldo.bin`
Correlation source: `output_fsm_correlation_2/per_corner_correlation.json`
Good corners: 126/135
FSM strategy: `hybrid`
States: ['DISABLED', 'REGULATION', 'REGULATION_2', 'REGULATION_3', 'REGULATION_4', 'REGULATION_5', 'DISABLED_2', 'REGULATION_6', 'REGULATION_7', 'REGULATION_8', 'REGULATION_9', 'REGULATION_10', 'REGULATION_11', 'REGULATION_12']
Transitions: 23
Models requested: ['gpr', 'pinn', 'node']
Equation source: PySR (--include_symbolic)
t_transition: 0.0002 s (auto-estimated)

## Counter-argument to automatic input narrowing (addressed, not ignored)

Analog circuits couple through shared rails/ground-return paths, so a real small-signal influence can sit below any statistical relevance threshold — a purely automatic hard cutoff risks silently dropping a physically-real coupling. Resolved by always force-including every supply/ground/output-rail current signal by default (matching the stated plan to standardize on including all supply and output port currents), plus any --blut_input_signals the user names explicitly — automatic narrowing only ever applies to the remaining control/select/bias/sense pin pool.

## NODE (informational only — unchanged from example12)

Phase2SimAugmented._train_node's update loop is confirmed dead code under real PyTorch (it only mutates a numpy-shim-only attribute, never calls backward()/optimizer.step()) — a known, separate, pre-existing limitation, out of scope for this pass by explicit decision. The differential-relation ask is instead satisfied deterministically by the ddt()/idt() feature-and-token-rewrite mechanism above.

## Categorical corner codes (set meta_<key> to this value per simulated process)

- `meta_corner`: nn=-0.03632, ss=0.2227, ww=-0.2295

**Analog skeleton output-driving equations: EMBEDDED**
  states with equations: 14
  outputs: ['VDD_1V2', 'VPWR_I', 'FUN_DC_I', 'V_SUPPLY_I']
  ddt() present: False   idt() present: True   transition() present: True

## Output files

- `output_new/ex14_3000_gpr_pinn_node_sym_fixed_inputs/ldo_fsm_skeleton.vams` — final Verilog-A (FSM + self-checks + differential, transition()-smoothed output equations)
- `output_new/ex14_3000_gpr_pinn_node_sym_fixed_inputs/ldo_fsm_skeleton.sv` — final SystemVerilog control skeleton
- `output_new/ex14_3000_gpr_pinn_node_sym_fixed_inputs/model_comparison.md` (+ .json)
- `output_new/ex14_3000_gpr_pinn_node_sym_fixed_inputs/transition_sensitivity.json`
