# Phase 2 Differential/Auto-Select Model Comparison

BLUT: `blut_files/regression_multi_corner_sref_ldo.bin`  |  good corners: 126/135  |  equation source: `PySR (--include_symbolic)`

## Auto-selected inputs

Candidates considered: 55

| input | relevance | selected |
|---|---|---|
| AVSS | 2.397 | no |
| AVSS_I | 3.343 | force |
| EN_LDO | 0.6581 | no |
| EN_LDO_I | 3.233 | no |
| EN_SCAN_MODE_MPOS | 0.2537 | no |
| EN_SCAN_MODE_MPOS_I | 3.336 | no |
| EN_UVLO_1V2 | 2.19 | no |
| EN_UVLO_1V2_I | 0.0004914 | no |
| FS_V_SUPPLY_TO_MOST_POS | 2.396 | no |
| FS_V_SUPPLY_TO_MOST_POS_I | 3.464 | no |
| FUN_DC | 1.135 | force |
| GND | 0.0008028 | no |
| HIGH_POWER_MODE | 0.75 | no |
| HIGH_POWER_MODE_I | 3.265 | no |
| ISO | 0.001673 | no |
| ISO_I | 3.674 | force |
| MOST_POS | 1.136 | force |
| MOST_POS_I | 3.214 | force |
| PAD_VDD1V2_SEL | 0.02019 | no |
| PAD_VDD1V2_SEL_I | 3.246 | no |
| PBKG | 2.396 | no |
| PBKG_I | 3.504 | force |
| SCAN_MODE_VSUPPLY | 0.2595 | no |
| SCAN_MODE_VSUPPLY_I | 3.357 | no |
| SREF_ADD_LDO1V2_LOAD_MPOS | 0.3904 | no |
| SREF_ADD_LDO1V2_LOAD_MPOS_I | 4.783 | no |
| SREF_LDO1V2_LP_TB.IBIAS_SNK_25nA_[0] | 7.202 | no |
| SREF_LDO1V2_LP_TB.IBIAS_SNK_25nA_[1] | 7.237 | no |
| SREF_LDO1V2_LP_TB.IBIAS_SNK_25nA_[2] | 6.727 | no |
| SREF_LDO1V2_LP_TB.ICONST_75A[0] | 3.617 | no |
| SREF_LDO1V2_LP_TB.SREF_EN_ISENSE_LDO1V2_MPOS | 0.2447 | no |
| SREF_LDO1V2_LP_TB.SREF_LDO_ISNS_DIS_MPOS | 0.3157 | no |
| SREF_LDO1V2_LP_TB.X_DUT.IBIAS_SNK_25nA_[0] | 7.202 | no |
| SREF_LDO1V2_LP_TB.X_DUT.IBIAS_SNK_25nA_[1] | 7.237 | no |
| SREF_LDO1V2_LP_TB.X_DUT.IBIAS_SNK_25nA_[2] | 6.727 | no |
| SREF_LDO1V2_LP_TB.X_DUT.ICONST_75A[0] | 3.618 | no |
| SREF_LDO1V2_LP_TB.X_DUT.SREF_EN_ISENSE_LDO1V2_MPOS_ | 3.274 | no |
| SREF_LDO1V2_LP_TB.X_DUT.SREF_LDO_ISNS_DIS_MPOS_ | 3.224 | no |
| UVLO_GD_OR_OVERRIDE_MPOS | 2.396 | no |
| UVLO_GD_OR_OVERRIDE_MPOS_I | 3.365 | no |
| VDD_1V2_EXT | 0.02502 | no |
| VDD_1V2_EXT_I | 4.718 | force |
| VDD_1V2_I | 5.5 | force |
| VFB | 9.286 | no |
| VFB_I | 4.186 | no |
| VPWR | 1.2 | force |
| VPWR_SEL | 1.53 | no |
| VPWR_SEL_I | 3.338 | no |
| VREF | 0.1416 | no |
| VREF_I | 3.325 | no |
| V_SUPPLY | 1.136 | force |
| floop_in | 4.468 | no |
| floop_in_I | 3.414 | no |
| floop_out | 4.468 | no |
| floop_out_I | 3.413 | force |

## Categorical corner codes

- `meta_corner`: nn=-0.03632, ss=0.2227, ww=-0.2295

| state | n_samples | GPR | NODE | PINN | best black-box |
|---|---|---|---|---|---|
| DISABLED | 3000 | 0.005513 | 4.596e+09 | 0.2046 | GPR |
| REGULATION | 3000 | 0.02531 | 5.378e+10 | 0.5706 | GPR |
| REGULATION_2 | 3000 | 0.01274 | 1.965e+10 | 0.4198 | GPR |
| REGULATION_3 | 3000 | 0.006074 | 3.304e+09 | 0.2459 | GPR |
| REGULATION_4 | 3000 | 0.001913 | 1.828e+10 | 0.2978 | GPR |
| REGULATION_5 | 3000 | 0.009772 | 4.595e+09 | 0.3548 | GPR |
| DISABLED_2 | 3000 | 0.008245 | 4.676e+09 | 0.4846 | GPR |
| REGULATION_6 | 3000 | 0.002035 | 4.585e+09 | 0.3662 | GPR |
| REGULATION_7 | 3000 | 0.0002132 | 4.583e+09 | 0.3602 | GPR |
| REGULATION_8 | 3000 | 7.137e-05 | 4.538e+09 | 0.3437 | GPR |
| REGULATION_9 | 3000 | 0.003661 | 4.564e+09 | 0.3853 | GPR |
| REGULATION_10 | 3000 | 0.0002005 | 4.666e+09 | 0.4291 | GPR |
| REGULATION_11 | 3000 | 0.0004931 | 4.159e+09 | 0.5768 | GPR |
| REGULATION_12 | 3000 | 0.001455 | 4.502e+09 | 0.6281 | GPR |

## Fitted output equations (embedded in the .vams)

| state | output | R2 | has ddt/idt | equation |
|---|---|---|---|---|
| DISABLED | VDD_1V2 | 0.884 | False | `transition((exp(ISO_I * -92.316734) - 0.9154745) * 1.6992617, 0, t_transition, t_transition)` |
| DISABLED | VPWR_I | 0.998 | False | `transition(((VDD_1V2_I / -0.85714936) - PBKG_I) - (AVSS_I + MOST_POS_I), 0, t_transition, t_transition)` |
| DISABLED | FUN_DC_I | 0.920 | False | `transition(PBKG_I * 0.40281367, 0, t_transition, t_transition)` |
| DISABLED | V_SUPPLY_I | 0.350 | False | `transition(FUN_DC * 2.8801762e-5, 0, t_transition, t_transition)` |
| REGULATION | VDD_1V2 | 0.637 | False | `transition((ISO_I * -58.325542) + 0.87574404, 0, t_transition, t_transition)` |
| REGULATION | VPWR_I | 0.999 | False | `transition((VDD_1V2_I * -0.9937707) - (AVSS_I / exp(AVSS_I + AVSS_I)), 0, t_transition, t_transition)` |
| REGULATION | FUN_DC_I | 0.223 | True | `transition(zzzDdtPh153zzz * 23089.334, 0, t_transition, t_transition)` |
| REGULATION | V_SUPPLY_I | 0.187 | False | `transition(VDD_1V2_I * -0.00038813215, 0, t_transition, t_transition)` |
| REGULATION_2 | VDD_1V2 | 0.860 | False | `transition((ISO_I * -65.526985) - -1.0123514, 0, t_transition, t_transition)` |
| REGULATION_2 | VPWR_I | 0.341 | True | `transition(zzzDdtPh212zzz * ((VDD_1V2_I + AVSS_I) / -0.3152533), 0, t_transition, t_transition)` |
| REGULATION_2 | FUN_DC_I | 0.446 | False | `transition((AVSS_I + VDD_1V2_I) * -0.6725917, 0, t_transition, t_transition)` |
| REGULATION_2 | V_SUPPLY_I | 0.200 | False | `transition(((-5.7626266e-7 / meta_corner) / -0.20209794) - (log(meta_vsup_max) * -6.6513e-5), 0, t_transition, t_transition)` |
| REGULATION_3 | VDD_1V2 | 0.418 | False | `transition((ISO_I * -286.98157) + 0.8796061, 0, t_transition, t_transition)` |
| REGULATION_3 | VPWR_I | 0.996 | True | `transition(VDD_1V2_I * ((zzzDdtPh305zzz - zzzDdtPh306zzz) * 112.315346), 0, t_transition, t_transition)` |
| REGULATION_3 | FUN_DC_I | 0.992 | True | `transition(zzzDdtPh326zzz - (VDD_1V2_I * exp(zzzDdtPh319zzz / (zzzDdtPh326zzz / 4.6620555))), 0, t_transition, t_transition)` |
| REGULATION_3 | V_SUPPLY_I | 0.358 | True | `transition(zzzDdtPh341zzz * 0.3393371, 0, t_transition, t_transition)` |
| REGULATION_4 | VDD_1V2 | 0.818 | False | `transition(((8.234361 / V_SUPPLY) + -0.80329573) + (ISO_I * -300.20877), 0, t_transition, t_transition)` |
| REGULATION_4 | VPWR_I | 0.428 | True | `transition((VDD_1V2_I * 817.28345) * zzzDdtPh389zzz, 0, t_transition, t_transition)` |
| REGULATION_4 | FUN_DC_I | 1.000 | False | `transition((0.00021563028 - VDD_1V2_I) + (ISO_I * -0.6881471), 0, t_transition, t_transition)` |
| REGULATION_4 | V_SUPPLY_I | 0.521 | True | `transition((1.1258842 * ((-0.6003273 * floop_out_I) / (-0.15424047 + zzzDdtPh432zzz))) / zzzDdtPh432zzz, 0, t_transition, t_transition)` |
| REGULATION_5 | VDD_1V2 | 0.801 | False | `transition((2.2370858 / exp(ISO_I * 182.62665)) + -1.485869, 0, t_transition, t_transition)` |
| REGULATION_5 | VPWR_I | 1.000 | False | `transition((VDD_1V2_I / -1.0022407) - (AVSS_I / (AVSS_I + exp(AVSS_I))), 0, t_transition, t_transition)` |
| REGULATION_5 | FUN_DC_I | 0.584 | True | `transition((((zzzDdtPh499zzz * V_SUPPLY) / zzzDdtPh504zzz) / (meta_corner + -0.788054)) - -4.3131868e-6, 0, t_transition, t_transition)` |
| REGULATION_5 | V_SUPPLY_I | 0.071 | False | `transition(4.6029795e-6 - (PBKG_I * VDD_1V2_I), 0, t_transition, t_transition)` |
| DISABLED_2 | VDD_1V2 | 0.906 | True | `transition((((ISO_I - 0.01481444) * -0.0026508651) / zzzDdtPh539zzz) + -1.3438823, 0, t_transition, t_transition)` |
| DISABLED_2 | VPWR_I | 0.991 | True | `transition((MOST_POS_I * -1.2247722) - ((VDD_1V2_I + AVSS_I) - (V_SUPPLY * zzzDdtPh561zzz)), 0, t_transition, t_transition)` |
| DISABLED_2 | FUN_DC_I | 0.616 | False | `transition(PBKG_I * 0.45149, 0, t_transition, t_transition)` |
| DISABLED_2 | V_SUPPLY_I | 0.181 | False | `transition((exp(meta_corner) * 3.8215534e-5) * V_SUPPLY, 0, t_transition, t_transition)` |
| REGULATION_6 | VDD_1V2 | 0.976 | False | `transition((meta_vsup_max / 4.9021754) + (ISO_I * -57.871166), 0, t_transition, t_transition)` |
| REGULATION_6 | VPWR_I | 0.972 | False | `transition((AVSS_I * 0.15525495) - (AVSS_I + VDD_1V2_I), 0, t_transition, t_transition)` |
| REGULATION_6 | FUN_DC_I | 0.817 | True | `transition(((zzzDdtPh675zzz * V_SUPPLY) + -4.921449e-7) / (meta_corner * 1.5008647), 0, t_transition, t_transition)` |
| REGULATION_6 | V_SUPPLY_I | 0.938 | True | `transition((zzzDdtPh695zzz * (VDD_1V2_EXT_I * exp(V_SUPPLY * V_SUPPLY))) * 6.4329797e-10, 0, t_transition, t_transition)` |
| REGULATION_7 | VDD_1V2 | 0.975 | False | `transition((ISO_I - 0.017328277) * (VPWR / -0.08719268), 0, t_transition, t_transition)` |
| REGULATION_7 | VPWR_I | 0.770 | True | `transition(sqrt((VDD_1V2_I * -0.014013443) - zzzDdtPh737zzz), 0, t_transition, t_transition)` |
| REGULATION_7 | FUN_DC_I | 0.848 | True | `transition(2.2512965 * (((6.2314035e-7 - (MOST_POS * zzzDdtPh763zzz)) * V_SUPPLY) - zzzDdtPh764zzz), 0, t_transition, t_transition)` |
| REGULATION_7 | V_SUPPLY_I | 0.834 | True | `transition(exp(V_SUPPLY * ((V_SUPPLY * 0.034123894) * V_SUPPLY)) * zzzDdtPh787zzz, 0, t_transition, t_transition)` |
| REGULATION_8 | VDD_1V2 | 0.927 | False | `transition(((AVSS_I * -28.876953) + (V_SUPPLY * 0.45814657)) + -1.4223986, 0, t_transition, t_transition)` |
| REGULATION_8 | VPWR_I | 0.739 | False | `transition(0.024844825 + (0.00014386806 / VDD_1V2_I), 0, t_transition, t_transition)` |
| REGULATION_8 | FUN_DC_I | 0.846 | False | `transition((exp(FUN_DC) * -6.453324e-8) - -1.3888155e-5, 0, t_transition, t_transition)` |
| REGULATION_8 | V_SUPPLY_I | 0.743 | True | `transition((exp(FUN_DC) - 92.63703) * zzzDdtPh875zzz, 0, t_transition, t_transition)` |
| REGULATION_9 | VDD_1V2 | 0.950 | True | `transition((-0.0006559592 / zzzDdtPh898zzz) + -1.8343569, 0, t_transition, t_transition)` |
| REGULATION_9 | VPWR_I | 0.690 | False | `transition((PBKG_I * meta_temp) + 0.015498941, 0, t_transition, t_transition)` |
| REGULATION_9 | FUN_DC_I | 0.198 | True | `transition(zzzDdtPh939zzz * -10.5617485, 0, t_transition, t_transition)` |
| REGULATION_9 | V_SUPPLY_I | 0.839 | True | `transition(((zzzDdtPh963zzz * 5.3763216e-11) * zzzDdtPh965zzz) * exp(meta_vsup_max * meta_vsup_max), 0, t_transition, t_transition)` |
| REGULATION_10 | VDD_1V2 | 0.913 | False | `transition((-0.040777314 / VDD_1V2_I) + -1.886805, 0, t_transition, t_transition)` |
| REGULATION_10 | VPWR_I | 0.905 | True | `transition((zzzDdtPh1001zzz + (((zzzDdtPh1006zzz * meta_temp) / 0.13117203) + 0.0027573549)) * VPWR, 0, t_transition, t_transition)` |
| REGULATION_10 | FUN_DC_I | 0.101 | True | `transition(zzzDdtPh1033zzz * -25274.809, 0, t_transition, t_transition)` |
| REGULATION_10 | V_SUPPLY_I | 0.955 | True | `transition(zzzDdtPh1051zzz * (exp(meta_vsup_max * meta_vsup_max) * 1.0971181e-11), 0, t_transition, t_transition)` |
| REGULATION_11 | VDD_1V2 | 0.925 | False | `transition(0.5943706 - ((meta_temp * -0.0045121037) + (ISO_I * 52.151623)), 0, t_transition, t_transition)` |
| REGULATION_11 | VPWR_I | 0.278 | False | `transition(MOST_POS_I * -0.44996902, 0, t_transition, t_transition)` |
| REGULATION_11 | FUN_DC_I | 0.097 | True | `transition((zzzDdtPh1120zzz * 2.8841445) ^ MOST_POS, 0, t_transition, t_transition)` |
| REGULATION_11 | V_SUPPLY_I | 0.447 | True | `transition(((FUN_DC * 2.9791503e-5) / zzzDdtPh1136zzz) - 0.0009558587, 0, t_transition, t_transition)` |
| REGULATION_12 | VDD_1V2 | 0.899 | False | `transition(0.04416584 / (VDD_1V2_I + 0.0642903), 0, t_transition, t_transition)` |
| REGULATION_12 | VPWR_I | 0.169 | False | `transition(-0.0001821667 / meta_temp, 0, t_transition, t_transition)` |
| REGULATION_12 | FUN_DC_I | 0.996 | False | `transition((((0.13109495 - AVSS_I) * VDD_1V2_I) * -7.9331098) - (ISO_I * 0.2852467), 0, t_transition, t_transition)` |
| REGULATION_12 | V_SUPPLY_I | 0.812 | True | `transition(zzzDdtPh1229zzz * (exp(zzzDdtPh1229zzz * (MOST_POS * FUN_DC)) * zzzDdtPh1227zzz), 0, t_transition, t_transition)` |

## Transition sensitivity (informational)

| from | to | guard | n | largest output delta |
|---|---|---|---|---|
| REGULATION | DISABLED_2 | `(EN_LDO == 0 && HIGH_POWER_MODE == 1)` | 27 | VDD_1V2=0.1492 |
| REGULATION | REGULATION_5 | `(HIGH_POWER_MODE == 1)` | 27 | VDD_1V2=0.1479 |
| REGULATION_3 | REGULATION_5 | `(VPWR_SEL == 1)` | 36 | VDD_1V2=0.1201 |
| REGULATION_2 | REGULATION_3 | `(HIGH_POWER_MODE == 1)` | 63 | VDD_1V2=0.09899 |
| REGULATION_2 | REGULATION_5 | `(HIGH_POWER_MODE == 1 && VPWR_SEL == 1)` | 18 | VDD_1V2=0.04824 |
| REGULATION_2 | REGULATION | `(VPWR_SEL == 1)` | 27 | VDD_1V2=0.013 |
| REGULATION_5 | REGULATION | `(HIGH_POWER_MODE == 0)` | 81 | VPWR_I=0.006125 |
| REGULATION | REGULATION_2 | `(VPWR_SEL == 0)` | 123 | VDD_1V2=0.002057 |
