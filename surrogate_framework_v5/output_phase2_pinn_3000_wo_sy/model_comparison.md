# Phase 2 Per-State Model Comparison

BLUT: `blut_files/regression_multi_corner_sref_ldo.bin`  |  good corners: 126/135  |  equation source: `linear`

| state | n_samples | PINN | best black-box |
|---|---|---|---|
| DISABLED | 3000 | 0.4031 | PINN |
| REGULATION | 3000 | 1.305 | PINN |
| REGULATION_2 | 3000 | 0.8717 | PINN |
| REGULATION_3 | 3000 | 0.6604 | PINN |
| REGULATION_4 | 3000 | 0.3182 | PINN |
| REGULATION_5 | 3000 | 0.5527 | PINN |
| DISABLED_2 | 3000 | 1.577 | PINN |
| REGULATION_6 | 3000 | 1.457 | PINN |
| REGULATION_7 | 3000 | 1.335 | PINN |
| REGULATION_8 | 3000 | 0.4547 | PINN |
| REGULATION_9 | 3000 | 1.082 | PINN |
| REGULATION_10 | 3000 | 1.947 | PINN |
| REGULATION_11 | 3000 | 1.523 | PINN |
| REGULATION_12 | 3000 | 2.192 | PINN |

## Fitted output equations (embedded in the .vams)

| state | output | R2 | equation |
|---|---|---|---|
| DISABLED | VDD_1V2 | 0.169 | `-0.000625388*VPWR + -0.539243*VREF + -0.000625388*FUN_DC + -0.000625388*V_SUPPLY + 0.289696*meta_corner_nn + -0.125726*m` |
| REGULATION | VDD_1V2 | 0.520 | `0.347055*VPWR + -0.180099*VREF + -0.0661307*FUN_DC + -2.83789*VDD_1V2_EXT + -0.0661307*V_SUPPLY + 0.603709*meta_corner_n` |
| REGULATION_2 | VDD_1V2 | 0.392 | `240.937*VPWR + -0.061652*VREF + 0.755759*FUN_DC + 3.41813e-09*VDD_1V2_EXT + -120.794*V_SUPPLY + 0.711071*meta_corner_nn ` |
| REGULATION_3 | VDD_1V2 | 0.198 | `271.242*VPWR + 0.342753*VREF + -90.4162*FUN_DC + 6.43415e-09*VDD_1V2_EXT + -90.4162*V_SUPPLY + 0.27985*meta_corner_nn + ` |
| REGULATION_4 | VDD_1V2 | 0.639 | `-2.50272*VPWR + 12.8813*VREF + 1.6383*FUN_DC + 5.28439e+07*VDD_1V2_EXT + 0.825232*V_SUPPLY + -2.50145*meta_corner_nn + -` |
| REGULATION_5 | VDD_1V2 | 0.145 | `-0.505899*VPWR + -0.788833*VREF + 0.323842*FUN_DC + 0.323842*V_SUPPLY + -0.257236*meta_corner_nn + -0.236318*meta_corner` |
| DISABLED_2 | VDD_1V2 | 0.577 | `-0.0234411*VPWR + -0.187962*VREF + -0.0234411*FUN_DC + -0.0234411*V_SUPPLY + 0.843141*meta_corner_nn + -0.522731*meta_co` |
| REGULATION_6 | VDD_1V2 | 0.988 | `0.058592*VPWR + -0.697571*VREF + 0.058592*FUN_DC + 0.058592*V_SUPPLY + 1.37377*meta_corner_nn + -1.15*meta_corner_ss + -` |
| REGULATION_7 | VDD_1V2 | 0.987 | `0.0660861*VPWR + -0.759431*VREF + 0.0660861*FUN_DC + 0.0660861*V_SUPPLY + 1.32837*meta_corner_nn + -1.17738*meta_corner_` |
| REGULATION_8 | VDD_1V2 | 0.950 | `0.122812*VPWR + -1.20735*VREF + 0.122812*FUN_DC + 0.122812*V_SUPPLY + 1.03556*meta_corner_nn + -1.38267*meta_corner_ss +` |
| REGULATION_9 | VDD_1V2 | 0.960 | `0.0734001*VPWR + -0.851329*VREF + 0.0734001*FUN_DC + 0.0734001*V_SUPPLY + 1.18072*meta_corner_nn + -1.18183*meta_corner_` |
| REGULATION_10 | VDD_1V2 | 0.940 | `0.0282429*VPWR + -0.518905*VREF + 0.0282429*FUN_DC + 0.0282429*V_SUPPLY + 1.27838*meta_corner_nn + -0.987734*meta_corner` |
| REGULATION_11 | VDD_1V2 | 0.911 | `0.0473129*VPWR + -0.681833*VREF + 0.0473129*FUN_DC + 0.0473129*V_SUPPLY + 1.14581*meta_corner_nn + -1.04788*meta_corner_` |
| REGULATION_12 | VDD_1V2 | 0.932 | `0.0317925*VPWR + -0.552369*VREF + 0.0317925*FUN_DC + 0.0317925*V_SUPPLY + 1.25026*meta_corner_nn + -1.00131*meta_corner_` |
