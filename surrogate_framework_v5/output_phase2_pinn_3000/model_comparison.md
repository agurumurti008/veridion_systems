# Phase 2 Per-State Model Comparison

BLUT: `blut_files/regression_multi_corner_sref_ldo.bin`  |  good corners: 126/135  |  equation source: `pysr`

| state | n_samples | PINN | best black-box |
|---|---|---|---|
| DISABLED | 3000 | 0.1667 | PINN |
| REGULATION | 3000 | 0.1884 | PINN |
| REGULATION_2 | 3000 | 0.3488 | PINN |
| REGULATION_3 | 3000 | 0.4269 | PINN |
| REGULATION_4 | 3000 | 0.2756 | PINN |
| REGULATION_5 | 3000 | 0.306 | PINN |
| DISABLED_2 | 3000 | 0.51 | PINN |
| REGULATION_6 | 3000 | 0.2631 | PINN |
| REGULATION_7 | 3000 | 0.329 | PINN |
| REGULATION_8 | 3000 | 0.2725 | PINN |
| REGULATION_9 | 3000 | 0.3361 | PINN |
| REGULATION_10 | 3000 | 0.5669 | PINN |
| REGULATION_11 | 3000 | 0.5996 | PINN |
| REGULATION_12 | 3000 | 0.4601 | PINN |

## Fitted output equations (embedded in the .vams)

| state | output | R2 | equation |
|---|---|---|---|
| DISABLED | VDD_1V2 | 0.177 | `VREF * (meta_corner_nn - VREF)` |
| DISABLED | VPWR_I | 0.072 | `VREF * 0.041126303` |
| DISABLED | FUN_DC_I | 0.008 | `VREF * -0.00021940703` |
| DISABLED | V_SUPPLY_I | 0.438 | `VREF * 0.00022542111` |
| DISABLED | VDD_1V2_EXT_I | 0.095 | `-6.367229e-7 / exp(FUN_DC)` |
| REGULATION | VDD_1V2 | 0.482 | `meta_corner_nn - VDD_1V2_EXT` |
| REGULATION | VPWR_I | 0.095 | `0.03181064 / exp(meta_corner_nn)` |
| REGULATION | FUN_DC_I | 0.220 | `4.568297e-8 / log((meta_temp / (meta_vsup_max * meta_vsup_max)) + 2.615638)` |
| REGULATION | V_SUPPLY_I | 0.069 | `VDD_1V2_EXT * 0.0002555359` |
| REGULATION | VDD_1V2_EXT_I | 0.731 | `(((VDD_1V2_EXT * VDD_1V2_EXT) ^ V_SUPPLY) / meta_temp) * 0.688966` |
| REGULATION_2 | VDD_1V2 | 0.358 | `(V_SUPPLY * 0.22579277) * (meta_corner_nn + -0.056087445)` |
| REGULATION_2 | VPWR_I | 0.071 | `(V_SUPPLY - VPWR) ^ 0.720334` |
| REGULATION_2 | FUN_DC_I | 0.021 | `(meta_corner_nn * (meta_temp * -5.9344922e-5)) + 0.010260841` |
| REGULATION_2 | V_SUPPLY_I | 0.152 | `exp(meta_corner_ss) * 4.379155e-5` |
| REGULATION_2 | VDD_1V2_EXT_I | 0.035 | `(meta_temp ^ meta_corner_ss) * 1.2072884e-9` |
| REGULATION_3 | VDD_1V2 | 0.103 | `(meta_temp * 0.0037617045) + 0.7619099` |
| REGULATION_3 | VPWR_I | 0.757 | `(0.08269327 ^ meta_corner_nn) * sqrt(sqrt(V_SUPPLY - VPWR))` |
| REGULATION_3 | FUN_DC_I | 0.179 | `0.11225313 + (meta_corner_ss / meta_temp)` |
| REGULATION_3 | V_SUPPLY_I | 0.235 | `(meta_vsup_max - VPWR) * 0.044849403` |
| REGULATION_3 | VDD_1V2_EXT_I | 0.197 | `(VPWR - meta_vsup_max) * 0.00026777387` |
| REGULATION_4 | VDD_1V2 | 0.407 | `0.6751047 ^ meta_corner_ss` |
| REGULATION_4 | VPWR_I | 0.621 | `((-0.00053570955 / (0.46590176 - meta_corner_ww)) / VPWR) / meta_temp` |
| REGULATION_4 | FUN_DC_I | 0.458 | `((1.7480526 - meta_corner_ww) / meta_temp) - -0.08249684` |
| REGULATION_4 | V_SUPPLY_I | 0.121 | `((meta_temp * meta_temp) * 7.703445e-15) * exp(VPWR * 2.23792)` |
| REGULATION_4 | VDD_1V2_EXT_I | 0.040 | `meta_corner_nn * 2.0900178e-8` |
| REGULATION_5 | VDD_1V2 | 0.129 | `17.734138 / meta_temp` |
| REGULATION_5 | VPWR_I | 0.322 | `0.13061732 / exp(meta_corner_nn)` |
| REGULATION_5 | FUN_DC_I | 0.386 | `(meta_corner_ss * exp(VPWR)) * -3.3502623e-8` |
| REGULATION_5 | V_SUPPLY_I | 0.025 | `5.3910544e-6 * exp(meta_corner_nn)` |
| REGULATION_5 | VDD_1V2_EXT_I | 0.043 | `((meta_corner_ss * meta_temp) * 1.5518733e-9) + -4.061973e-8` |
| DISABLED_2 | VDD_1V2 | 0.523 | `meta_corner_nn + -1.250111` |
| DISABLED_2 | VPWR_I | 0.043 | `0.059411786 / exp(meta_corner_nn)` |
| DISABLED_2 | FUN_DC_I | 0.008 | `(0.17897764 / exp(meta_corner_nn)) ^ V_SUPPLY` |
| DISABLED_2 | V_SUPPLY_I | 0.223 | `((FUN_DC + meta_corner_ss) * 0.00010283004) + -0.00036073063` |
| DISABLED_2 | VDD_1V2_EXT_I | 0.164 | `meta_corner_ss * (meta_temp * 6.581933e-9)` |
| REGULATION_6 | VDD_1V2 | 0.988 | `((meta_corner_nn * V_SUPPLY) ^ 0.5620598) - 1.4522998` |
| REGULATION_6 | VPWR_I | 0.372 | `exp(meta_corner_nn * -0.64951396) * 0.025591683` |
| REGULATION_6 | FUN_DC_I | 0.844 | `((-3.6089457e-7 - (-1.9431536e-6 / FUN_DC)) * exp(FUN_DC)) * meta_corner_nn` |
| REGULATION_6 | V_SUPPLY_I | 0.790 | `(exp(exp(meta_corner_ss) * (FUN_DC + 1.3460444)) * meta_temp) * VDD_1V2_EXT` |
| REGULATION_6 | VDD_1V2_EXT_I | 0.414 | `(meta_temp ^ meta_corner_ss) * 3.5509602e-9` |
| REGULATION_7 | VDD_1V2 | 0.986 | `((VPWR * meta_corner_nn) ^ 0.55619794) + -1.4658281` |
| REGULATION_7 | VPWR_I | 0.409 | `(meta_temp * 0.00011692523) + 0.018108726` |
| REGULATION_7 | FUN_DC_I | 0.863 | `(6.9905305e-5 - (V_SUPPLY * 1.3089e-5)) * meta_corner_nn` |
| REGULATION_7 | V_SUPPLY_I | 0.616 | `(meta_corner_ss * ((-0.26126868 / (meta_vsup_max / 7.4889266e-7)) + 4.20248e-8)) * meta_temp` |
| REGULATION_7 | VDD_1V2_EXT_I | 0.486 | `3.6008738e-9 * (meta_temp ^ meta_corner_ss)` |
| REGULATION_8 | VDD_1V2 | 0.950 | `(meta_corner_nn * (V_SUPPLY * 0.47110522)) - 1.4850253` |
| REGULATION_8 | VPWR_I | 0.237 | `(meta_corner_nn * -0.012240114) - -0.026069034` |
| REGULATION_8 | FUN_DC_I | 0.904 | `meta_corner_nn * ((-1.32276455e-5 * FUN_DC) - -7.067309e-5)` |
| REGULATION_8 | V_SUPPLY_I | 0.813 | `(meta_temp * (exp(V_SUPPLY ^ meta_corner_ss) ^ V_SUPPLY)) * 5.27201e-22` |
| REGULATION_8 | VDD_1V2_EXT_I | 0.327 | `(meta_temp ^ meta_corner_ss) * 3.5547838e-9` |
| REGULATION_9 | VDD_1V2 | 0.949 | `(meta_corner_nn * 2.3558123) + -1.4595004` |
| REGULATION_9 | VPWR_I | 0.761 | `0.02440375 / ((meta_corner_nn + exp(meta_temp * -0.0041323197)) ^ 0.7441618)` |
| REGULATION_9 | FUN_DC_I | 0.264 | `((FUN_DC * -4.785515e-6) + 2.4134313e-5) * meta_corner_nn` |
| REGULATION_9 | V_SUPPLY_I | 0.550 | `(60.451424 ^ FUN_DC) * (VDD_1V2_EXT * meta_corner_ss)` |
| REGULATION_9 | VDD_1V2_EXT_I | 0.876 | `((meta_temp * 2.8055336e-9) + 1.1374171e-7) * meta_corner_ss` |
| REGULATION_10 | VDD_1V2 | 0.980 | `-0.6587072 / (exp(-0.6587072 * (meta_temp * meta_corner_nn)) + -0.5488256)` |
| REGULATION_10 | VPWR_I | 0.874 | `((((meta_corner_nn - exp(meta_corner_ss)) * -1.5564194e-5) * meta_temp) - -0.0039018576) * meta_vsup_max` |
| REGULATION_10 | FUN_DC_I | 0.068 | `3.411023e-7 / (exp(16.321095 / meta_temp) - meta_corner_ss)` |
| REGULATION_10 | V_SUPPLY_I | 0.712 | `VDD_1V2_EXT * (meta_temp * (exp(exp(exp(meta_corner_ss / VPWR))) ^ VPWR))` |
| REGULATION_10 | VDD_1V2_EXT_I | 0.997 | `meta_corner_ss * (exp(meta_temp * 0.014108653) * (4.2882135e-7 / VPWR))` |
| REGULATION_11 | VDD_1V2 | 0.954 | `((2.0746186 - (-21.56122 / meta_temp)) * meta_corner_nn) + -1.45847` |
| REGULATION_11 | VPWR_I | 0.028 | `(1.2161636 - meta_corner_nn) * ((meta_temp * 2.5709234e-5) - -0.0014921804)` |
| REGULATION_11 | FUN_DC_I | 0.034 | `((meta_corner_ss - (meta_temp * -0.016176477)) + FUN_DC) * 0.0020654406` |
| REGULATION_11 | V_SUPPLY_I | 0.099 | `((FUN_DC - meta_corner_ww) * 3.4537352e-5) - 7.763184e-5` |
| REGULATION_11 | VDD_1V2_EXT_I | 0.708 | `(meta_corner_ss * 1.7228783e-7) / ((VREF + 0.28931525) ^ meta_temp)` |
| REGULATION_12 | VDD_1V2 | 0.964 | `(((18.486307 / meta_temp) - -2.1427417) * meta_corner_nn) + -1.4583693` |
| REGULATION_12 | VPWR_I | 0.495 | `(meta_vsup_max ^ meta_vsup_max) * (-4.0752557e-8 / meta_temp)` |
| REGULATION_12 | FUN_DC_I | 0.847 | `(V_SUPPLY - (meta_corner_nn + (meta_corner_nn - meta_corner_ss))) / (266.6043 - meta_temp)` |
| REGULATION_12 | V_SUPPLY_I | 0.538 | `(exp(FUN_DC / 0.27316576) * (meta_corner_ss * VDD_1V2_EXT)) / 0.083093986` |
| REGULATION_12 | VDD_1V2_EXT_I | 0.958 | `meta_corner_ss * ((meta_temp * 2.9044709e-9) + 1.1409774e-7)` |
