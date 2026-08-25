# example16 Run Manifest — Pipeline Structure

```
1. Load per_corner_correlation.json -> filter good corners
2. Global FSM (SignalCapture + FSMStateDetector + TransitionLearner + FSMValidator) -> state_defs, transitions
3. Validate requested signal names against the actually-resolved signal set (fast-fail on a typo)
4. Phase2SimAugmented.build_dataset_from_blut(run_ids=good_qids) -> corner-and-state-labeled X, Y, feature_names + target_encode_categorical_meta
5. Derivative (+ optional integral) features per input signal, per-run/run-boundary-safe
6. Per state: GPR/SMT/PINN/NODE (informational; GPR/SMT/PySR sub-capped, equation fit + PINN + NODE use the full --max_state_samples-capped set) + degree-2 polynomial + differential equation, ddt()/idt() token rewrite
7. FSMCodeGenerator.generate_veriloga(output_equations=...) -> final .vams/.sv
```

BLUT: `blut_files/regression_multi_corner_sref_ldo.bin`
Correlation source: `output_fsm_correlation_2/per_corner_correlation.json`
Good corners: 126/135
FSM strategy: `hybrid`
States: ['DISABLED', 'REGULATION', 'REGULATION_2', 'REGULATION_3', 'REGULATION_4', 'REGULATION_5', 'DISABLED_2', 'REGULATION_6', 'REGULATION_7', 'REGULATION_8', 'REGULATION_9', 'REGULATION_10', 'REGULATION_11', 'REGULATION_12']
Transitions: 23
Models requested: ['gpr', 'smt', 'pinn', 'node']
Equation source: degree-2 polynomial + differential

## NODE training (this script's new fix)

core/models/neural_ode.py's CircuitODEFunction.forward and CircuitNeuralODE._euler_integrate/forward now keep the entire Euler rollout (state, physics coefficients, ic_net/state_clf outputs) as genuine tensor ops instead of round-tripping through to_np()/make_float_tensor() every step — the same class of graph-severing bug already fixed in CircuitPINN. Phase2SimAugmented._train_node now builds a real torch.optim.Adam over node.parameters() and calls backward()/step() on the real loss tensor, falling back to the original numpy-perturbation update only under torch_shim. NODE remains informational-only in the final .vams (same as every prior example in this series) — closed-form output equations still come from the polynomial+differential fit (or PySR).

## Sample caps

- general (equation fit + PINN + NODE): 200000
- GPR/SMT: 3000

## Categorical corner codes (set meta_<key> to this value per simulated process)

- `meta_corner`: nn=-0.04055, ss=0.196, ww=-0.1619

**Analog skeleton output-driving equations: EMBEDDED**
  states with equations: 14
  outputs: ['VDD_1V2', 'VPWR_I', 'V_SUPPLY_I', 'FUN_DC_I', 'MOST_POS_I']
  ddt() present: True   idt() present: False

## Output files

- `output_new/ex16_gpr_smt_pinn_node/ldo_fsm_skeleton.vams` — final Verilog-A (FSM + self-checks + differential output equations)
- `output_new/ex16_gpr_smt_pinn_node/ldo_fsm_skeleton.sv` — final SystemVerilog control skeleton
- `output_new/ex16_gpr_smt_pinn_node/model_comparison.md` (+ .json)
