# example13 Run Manifest — PDN-Aware Port Model (exploratory)

```
1. Load per_corner_correlation.json -> filter good corners
2. Global FSM (SignalCapture + FSMStateDetector + TransitionLearner + FSMValidator) -> state_defs, transitions
3. Phase2SimAugmented.build_dataset_from_blut(output=[VDD_1V2])
   -> target_encode_categorical_meta (single meta_corner variable)
4. Per state: degree-2 polynomial equation for VDD_1V2_ideal (intrinsic/set-point target, embedded)
5. FSMCodeGenerator.generate_veriloga(output_equations={<port>_ideal: eq})
   -> new diagnostic port <port>_ideal, driven per-state
6. Hand-spliced PDN RLC branch (this script, not fsm_codegen.py):
   V(VDD_1V2_ideal, VDD_1V2) <+ R_pdn*I(...) + L_pdn*ddt(I(...));
   I(VDD_1V2, GND) <+ C_pdn*ddt(V(VDD_1V2, GND));
```

BLUT: `blut_files/regression_multi_corner_sref_ldo.bin`
Correlation source: `output_fsm_correlation_2/per_corner_correlation.json`
Good corners: 126/135
FSM strategy: `hybrid`
PDN port: `VDD_1V2`  (ideal/intrinsic node: `VDD_1V2_ideal`)
PDN variant: `decap_1uF_tight`  R_pdn=0.05  L_pdn=1e-09  C_pdn=1e-06
Available PDN variants: ['decap_1uF_tight', 'decap_100nF_loose', 'decap_10uF_bulk']

## Categorical corner codes

- `meta_corner`: nn=0.4417, ss=-0.519, ww=-1.134

## Per-state intrinsic/ideal equation

| state | n_samples | R2 | equation |
|---|---|---|---|
| DISABLED | 3000 | 0.196 | `-0.00378953*VPWR + 1.08034*VREF + -0.00378953*FUN_DC + -0.00378953*V_SUPPLY + 0.23157*meta_corner + -0.000576153*meta_temp + -0.0541548*meta_vsup_max + 0.002140` |
| REGULATION | 3000 | 0.555 | `0.405208*VPWR + 0.525208*VREF + -0.242365*FUN_DC + -2.70451*VDD_1V2_EXT + -0.242365*V_SUPPLY + 0.57181*meta_corner + -0.00259392*meta_temp + -0.242365*meta_vsup` |
| REGULATION_2 | 3000 | 0.423 | `-93.4803*VPWR + 3.32744*VREF + 2.60746*FUN_DC + -59146.9*VDD_1V2_EXT + 49.8756*V_SUPPLY + 0.839395*meta_corner + -2.19713*meta_temp + 49.7931*meta_vsup_max + 13` |
| REGULATION_3 | 3000 | 0.225 | `-588.871*VPWR + -1.64418*VREF + 196.723*FUN_DC + 0.0456214*VDD_1V2_EXT + 196.728*V_SUPPLY + 0.361407*meta_corner + 0.00340757*meta_temp + 196.727*meta_vsup_max ` |
| REGULATION_4 | 3000 | 0.625 | `-0.728621*VPWR + 4.61614*VREF + -0.728621*FUN_DC + 1.30671e-10*VDD_1V2_EXT + -0.728621*V_SUPPLY + 1.21988*meta_corner + 0.0104803*meta_temp + -0.728621*meta_vsu` |
| REGULATION_5 | 3000 | 0.197 | `-1.26968*VPWR + 2.76725*VREF + -0.187857*FUN_DC + -0.187857*V_SUPPLY + -0.118016*meta_corner + 0.00793297*meta_temp + -0.187857*meta_vsup_max + -0.523425*VPWR*V` |
| DISABLED_2 | 3000 | 0.587 | `0.091508*VPWR + -0.80655*VREF + 0.091508*FUN_DC + 0.091508*V_SUPPLY + 0.636814*meta_corner + 0.00115366*meta_temp + 0.091508*meta_vsup_max + -0.00623915*VPWR*VP` |
| REGULATION_6 | 3000 | 0.991 | `0.281098*VPWR + -2.03737*VREF + 0.281098*FUN_DC + 0.281098*V_SUPPLY + 1.55469*meta_corner + 0.00498081*meta_temp + 0.281098*meta_vsup_max + -0.0150686*VPWR*VPWR` |
| REGULATION_7 | 3000 | 0.992 | `0.415861*VPWR + -2.94417*VREF + 0.415861*FUN_DC + 0.415861*V_SUPPLY + 1.31755*meta_corner + 0.0080388*meta_temp + 0.415861*meta_vsup_max + -0.0222134*VPWR*VPWR ` |
| REGULATION_8 | 3000 | 0.961 | `1.45713*VPWR + -9.53022*VREF + 1.45713*FUN_DC + 1.45713*V_SUPPLY + 0.311475*meta_corner + 0.0151943*meta_temp + 1.45713*meta_vsup_max + -0.0808907*VPWR*VPWR + 1` |
| REGULATION_9 | 3000 | 0.973 | `0.0562128*VPWR + -1.12218*VREF + 0.0562128*FUN_DC + 0.0562128*V_SUPPLY + 0.0600977*meta_corner + 0.0154202*meta_temp + 0.0562128*meta_vsup_max + 0.00201971*VPWR` |
| REGULATION_10 | 3000 | 0.970 | `0.0575197*VPWR + -0.890013*VREF + 0.0575197*FUN_DC + 0.0575197*V_SUPPLY + 0.785487*meta_corner + 0.0110495*meta_temp + 0.0575197*meta_vsup_max + -0.000508427*VP` |
| REGULATION_11 | 3000 | 0.961 | `-0.122375*VPWR + 0.153871*VREF + -0.122375*FUN_DC + -0.122375*V_SUPPLY + 0.678511*meta_corner + 0.0121236*meta_temp + -0.122375*meta_vsup_max + 0.01049*VPWR*VPW` |
| REGULATION_12 | 3000 | 0.967 | `-0.00865123*VPWR + -0.514273*VREF + -0.00865123*FUN_DC + -0.00865123*V_SUPPLY + 0.744479*meta_corner + 0.0111291*meta_temp + -0.00865123*meta_vsup_max + 0.00352` |

## Known simplifications (first version)

- One RLC network per port; no cross-port/rail coupling.
- R/L/C are linear and fixed for the run (no temp/aging dependence).
- The intrinsic/ideal node only updates on FSM state change (a per-state set-point, not a continuously-varying source).
- Only `--pdn_port` gets PDN-aware treatment; other ports are left exactly as the plain FSM control skeleton drives them.

**PDN-aware port loading: EMBEDDED**

## Output files

- `output_new/ex13_3000/ldo_pdn_aware_decap_1uF_tight.vams` — Verilog-A (FSM + intrinsic equation + PDN RLC branch)
- `output_new/ex13_3000/ldo_pdn_aware_decap_1uF_tight.sv` — SystemVerilog control skeleton
- `output_new/ex13_3000/model_decap_1uF_tight.json`
