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
| FUN_DC | 1.135 | no |
| GND | 0.0008028 | no |
| HIGH_POWER_MODE | 0.75 | no |
| HIGH_POWER_MODE_I | 3.265 | no |
| ISO | 0.001673 | no |
| ISO_I | 3.674 | force |
| MOST_POS | 1.136 | no |
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
| VFB | 9.286 | yes |
| VFB_I | 4.186 | no |
| VPWR | 1.2 | no |
| VPWR_SEL | 1.53 | no |
| VPWR_SEL_I | 3.338 | no |
| VREF | 0.1416 | no |
| VREF_I | 3.325 | no |
| V_SUPPLY | 1.136 | no |
| floop_in | 4.468 | no |
| floop_in_I | 3.414 | no |
| floop_out | 4.468 | no |
| floop_out_I | 3.413 | force |

## Categorical corner codes

- `meta_corner`: nn=-0.03632, ss=0.2227, ww=-0.2295

| state | n_samples | GPR | NODE | PINN | best black-box |
|---|---|---|---|---|---|
| DISABLED | 3000 | 6.462e-05 | 4.57e+09 | 0.2704 | GPR |
| REGULATION | 3000 | 0.008275 | 5.637e+10 | 0.4793 | GPR |
| REGULATION_2 | 3000 | 0.0002217 | 1.858e+10 | 0.4223 | GPR |
| REGULATION_3 | 3000 | 1.842e-05 | 3.231e+09 | 0.2239 | GPR |
| REGULATION_4 | 3000 | 1.461e-05 | 1.322e+10 | 0.2035 | GPR |
| REGULATION_5 | 3000 | 5.891e-05 | 4.539e+09 | 0.4472 | GPR |
| DISABLED_2 | 3000 | 0.0001806 | 4.822e+09 | 0.4714 | GPR |
| REGULATION_6 | 3000 | 9.919e-05 | 4.722e+09 | 0.445 | GPR |
| REGULATION_7 | 3000 | 1.46e-05 | 3.869e+09 | 0.3149 | GPR |
| REGULATION_8 | 3000 | 1.908e-06 | 3.92e+09 | 0.2593 | GPR |
| REGULATION_9 | 3000 | 0.001729 | 4.796e+09 | 0.4402 | GPR |
| REGULATION_10 | 3000 | 3.207e-05 | 4.571e+09 | 0.6549 | GPR |
| REGULATION_11 | 3000 | 5.383e-05 | 4.405e+09 | 0.576 | GPR |
| REGULATION_12 | 3000 | 2.711e-05 | 4.583e+09 | 0.5346 | GPR |

## Fitted output equations (embedded in the .vams)

| state | output | R2 | has ddt/idt | equation |
|---|---|---|---|---|
| DISABLED | VDD_1V2 | 1.000 | True | `transition(VFB - (zzzDdtPh11zzz * 0.017136196), 0, t_transition, t_transition)` |
| DISABLED | VPWR_I | 0.998 | True | `transition((((zzzDdtPh24zzz - VDD_1V2_I) / 0.8704175) - (AVSS_I + MOST_POS_I)) - PBKG_I, 0, t_transition, t_transition)` |
| DISABLED | FUN_DC_I | 0.920 | False | `transition(PBKG_I * 0.4028349, 0, t_transition, t_transition)` |
| DISABLED | V_SUPPLY_I | 0.137 | False | `transition((((-0.42297634 * AVSS_I) - VDD_1V2_I) * 0.0015900381) + 7.5745214e-5, 0, t_transition, t_transition)` |
| REGULATION | VDD_1V2 | 1.000 | False | `transition(VFB + -1.1297981e-8, 0, t_transition, t_transition)` |
| REGULATION | VPWR_I | 0.999 | False | `transition(((AVSS_I * -0.8027296) - VDD_1V2_I) - (PBKG_I / 0.049315475), 0, t_transition, t_transition)` |
| REGULATION | FUN_DC_I | 0.223 | True | `transition(zzzDdtPh111zzz / 4.3430577e-5, 0, t_transition, t_transition)` |
| REGULATION | V_SUPPLY_I | 0.187 | False | `transition(VDD_1V2_I * -0.00038813206, 0, t_transition, t_transition)` |
| REGULATION_2 | VDD_1V2 | 1.000 | False | `transition(VFB + -4.307104e-9, 0, t_transition, t_transition)` |
| REGULATION_2 | VPWR_I | 0.134 | False | `transition(VDD_1V2_I * VDD_1V2_I, 0, t_transition, t_transition)` |
| REGULATION_2 | FUN_DC_I | 0.446 | False | `transition((VDD_1V2_I + AVSS_I) * -0.67262954, 0, t_transition, t_transition)` |
| REGULATION_2 | V_SUPPLY_I | 0.102 | False | `transition((MOST_POS_I * 0.003064618) + 4.8849266e-5, 0, t_transition, t_transition)` |
| REGULATION_3 | VDD_1V2 | 1.000 | True | `transition(VFB - ((zzzDdtPh201zzz * zzzDdtPh201zzz) * 0.24271438), 0, t_transition, t_transition)` |
| REGULATION_3 | VPWR_I | 0.989 | True | `transition(zzzDdtPh217zzz * (VDD_1V2_I * -2716.511), 0, t_transition, t_transition)` |
| REGULATION_3 | FUN_DC_I | 0.998 | True | `transition(zzzDdtPh237zzz - (exp(zzzDdtPh232zzz / -0.00012479122) * VDD_1V2_I), 0, t_transition, t_transition)` |
| REGULATION_3 | V_SUPPLY_I | 0.358 | True | `transition(zzzDdtPh248zzz * 0.33909696, 0, t_transition, t_transition)` |
| REGULATION_4 | VDD_1V2 | 1.000 | True | `transition(VFB + ((PBKG_I * PBKG_I) / ((zzzDdtPh259zzz * zzzDdtPh270zzz) - 0.3030057)), 0, t_transition, t_transition)` |
| REGULATION_4 | VPWR_I | 0.344 | True | `transition(zzzDdtPh286zzz * -0.00031338894, 0, t_transition, t_transition)` |
| REGULATION_4 | FUN_DC_I | 1.000 | False | `transition(0.00021562823 - (VDD_1V2_I - (ISO_I * -0.6882507)), 0, t_transition, t_transition)` |
| REGULATION_4 | V_SUPPLY_I | 0.395 | True | `transition(zzzDdtPh319zzz * exp((meta_vsup_max + meta_vsup_max) * VFB), 0, t_transition, t_transition)` |
| REGULATION_5 | VDD_1V2 | 1.000 | False | `transition(VFB + -2.3957293e-8, 0, t_transition, t_transition)` |
| REGULATION_5 | VPWR_I | 1.000 | False | `transition((AVSS_I / ((AVSS_I / -0.20200954) + -0.7047099)) - VDD_1V2_I, 0, t_transition, t_transition)` |
| REGULATION_5 | FUN_DC_I | 0.232 | True | `transition(zzzDdtPh362zzz * -33.81346, 0, t_transition, t_transition)` |
| REGULATION_5 | V_SUPPLY_I | 0.110 | False | `transition((2.456354e-6 - ((VFB * VDD_1V2_I) * -1.9561021e-5)) * meta_vsup_max, 0, t_transition, t_transition)` |
| DISABLED_2 | VDD_1V2 | 1.000 | True | `transition(VFB + ((VDD_1V2_EXT_I * (meta_corner + -0.1910172)) / (zzzDdtPh389zzz + -0.17658988)), 0, t_transition, t_transition)` |
| DISABLED_2 | VPWR_I | 0.995 | False | `transition(((ISO_I * 0.24811971) - ((VDD_1V2_I + AVSS_I) + MOST_POS_I)) - PBKG_I, 0, t_transition, t_transition)` |
| DISABLED_2 | FUN_DC_I | 0.616 | False | `transition(PBKG_I * 0.45148864, 0, t_transition, t_transition)` |
| DISABLED_2 | V_SUPPLY_I | 0.163 | False | `transition(exp(meta_corner - VDD_1V2_I) * 0.00017446004, 0, t_transition, t_transition)` |
| REGULATION_6 | VDD_1V2 | 1.000 | True | `transition(VFB - ((PBKG_I * 0.4969576) * zzzDdtPh456zzz), 0, t_transition, t_transition)` |
| REGULATION_6 | VPWR_I | 0.921 | False | `transition((VDD_1V2_I * -1.1355114) + (-0.00196049 - AVSS_I), 0, t_transition, t_transition)` |
| REGULATION_6 | FUN_DC_I | 0.555 | False | `transition((0.00017670373 / meta_vsup_max) - 3.2582488e-5, 0, t_transition, t_transition)` |
| REGULATION_6 | V_SUPPLY_I | 0.904 | True | `transition((exp(meta_vsup_max * meta_vsup_max) * zzzDdtPh508zzz) * 2.8230106e-11, 0, t_transition, t_transition)` |
| REGULATION_7 | VDD_1V2 | 1.000 | False | `transition(VFB - (((meta_corner * 0.01577519) + AVSS_I) * 6.5698987e-7), 0, t_transition, t_transition)` |
| REGULATION_7 | VPWR_I | 0.772 | True | `transition(sqrt(((zzzDdtPh541zzz - VDD_1V2_I) * 0.013886548) - zzzDdtPh536zzz), 0, t_transition, t_transition)` |
| REGULATION_7 | FUN_DC_I | 0.843 | True | `transition(((zzzDdtPh555zzz * -2.9281387) + (zzzDdtPh554zzz * -66.68577)) + 7.774343e-6, 0, t_transition, t_transition)` |
| REGULATION_7 | V_SUPPLY_I | 0.953 | True | `transition(exp(meta_vsup_max * meta_vsup_max) * (zzzDdtPh572zzz * 2.72089e-11), 0, t_transition, t_transition)` |
| REGULATION_8 | VDD_1V2 | 1.000 | True | `transition(VFB - (zzzDdtPh584zzz * (PBKG_I * 0.27811757)), 0, t_transition, t_transition)` |
| REGULATION_8 | VPWR_I | 0.992 | False | `transition(((AVSS_I * 8.941733) * VDD_1V2_I) - VDD_1V2_I, 0, t_transition, t_transition)` |
| REGULATION_8 | FUN_DC_I | 0.797 | False | `transition((meta_vsup_max * -1.20147415e-5) + 6.427437e-5, 0, t_transition, t_transition)` |
| REGULATION_8 | V_SUPPLY_I | 0.645 | True | `transition((zzzDdtPh636zzz / (VDD_1V2_I + (VDD_1V2_I + 0.21092561))) * 0.5165726, 0, t_transition, t_transition)` |
| REGULATION_9 | VDD_1V2 | 1.000 | False | `transition(VFB - ((0.17274351 ^ VFB) * floop_out_I), 0, t_transition, t_transition)` |
| REGULATION_9 | VPWR_I | 0.947 | True | `transition(((zzzDdtPh664zzz * -33.48179) - (VDD_1V2_I * 0.73200613)) + 0.003918482, 0, t_transition, t_transition)` |
| REGULATION_9 | FUN_DC_I | 0.198 | True | `transition(zzzDdtPh682zzz * -10.570317, 0, t_transition, t_transition)` |
| REGULATION_9 | V_SUPPLY_I | 0.754 | True | `transition(((exp(meta_vsup_max) * 0.0925021) - meta_vsup_max) * (meta_vsup_max * zzzDdtPh700zzz), 0, t_transition, t_transition)` |
| REGULATION_10 | VDD_1V2 | 1.000 | False | `transition(VFB + (-1.9876415e-8 - (AVSS_I * 4.954097e-7)), 0, t_transition, t_transition)` |
| REGULATION_10 | VPWR_I | 0.973 | True | `transition(VDD_1V2_I * ((zzzDdtPh728zzz / (zzzDdtPh733zzz / -0.70151025)) + -0.8635841), 0, t_transition, t_transition)` |
| REGULATION_10 | FUN_DC_I | 0.100 | True | `transition(zzzDdtPh751zzz * -27898.295, 0, t_transition, t_transition)` |
| REGULATION_10 | V_SUPPLY_I | 0.844 | True | `transition(((meta_vsup_max ^ meta_vsup_max) * 0.011032492) * zzzDdtPh764zzz, 0, t_transition, t_transition)` |
| REGULATION_11 | VDD_1V2 | 1.000 | True | `transition(VFB - (zzzDdtPh776zzz * (zzzDdtPh779zzz / 0.2200517)), 0, t_transition, t_transition)` |
| REGULATION_11 | VPWR_I | 0.278 | False | `transition(MOST_POS_I * -0.44996876, 0, t_transition, t_transition)` |
| REGULATION_11 | FUN_DC_I | 0.452 | False | `transition((VDD_1V2_I + AVSS_I) * -0.7555813, 0, t_transition, t_transition)` |
| REGULATION_11 | V_SUPPLY_I | 0.232 | True | `transition(((-6.0067437e-6 / (0.03566902 - zzzDdtPh819zzz)) * 0.4065019) + 0.0001248202, 0, t_transition, t_transition)` |
| REGULATION_12 | VDD_1V2 | 1.000 | False | `transition((VFB + -0.22990982) - -0.22990982, 0, t_transition, t_transition)` |
| REGULATION_12 | VPWR_I | 0.379 | False | `transition((-0.00021562983 / meta_temp) - ((meta_vsup_max / VFB) * -2.3255157e-7), 0, t_transition, t_transition)` |
| REGULATION_12 | FUN_DC_I | 0.954 | True | `transition((zzzDdtPh873zzz * -28.996588) - (((ISO_I / AVSS_I) * -0.09622708) + -0.015027411), 0, t_transition, t_transition)` |
| REGULATION_12 | V_SUPPLY_I | 0.896 | True | `transition((1.2917763 * zzzDdtPh895zzz) / ((zzzDdtPh895zzz / zzzDdtPh892zzz) + 0.0047646975), 0, t_transition, t_transition)` |

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
