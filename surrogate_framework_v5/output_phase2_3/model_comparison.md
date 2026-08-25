# Phase 2 Per-State Model Comparison

BLUT: `blut_files/regression_multi_corner_sref_ldo.bin`  |  good corners: 126/135  |  equation source: `pysr`

| state | n_samples | PINN | best black-box |
|---|---|---|---|
| DISABLED | 1500 | 0.1806 | PINN |
| REGULATION | 1500 | 0.297 | PINN |
| REGULATION_2 | 1500 | 0.4779 | PINN |
| REGULATION_3 | 1500 | 0.399 | PINN |
| REGULATION_4 | 1500 | 0.1414 | PINN |
| REGULATION_5 | 1500 | 0.3709 | PINN |
| DISABLED_2 | 1500 | 0.5362 | PINN |
| REGULATION_6 | 1500 | 0.1508 | PINN |
| REGULATION_7 | 1500 | 0.6475 | PINN |
| REGULATION_8 | 1500 | 0.5039 | PINN |
| REGULATION_9 | 1500 | 0.2626 | PINN |
| REGULATION_10 | 1500 | 0.564 | PINN |
| REGULATION_11 | 1500 | 0.5687 | PINN |
| REGULATION_12 | 1500 | 0.4301 | PINN |

## Fitted output equations (embedded in the .vams)

| state | output | R2 | equation |
|---|---|---|---|
| DISABLED | VDD_1V2 | 0.086 | `VREF * -0.41224968` |
| DISABLED | VPWR_I | 0.074 | `VREF * 0.04285335` |
| DISABLED | FUN_DC_I | 0.034 | `exp(V_SUPPLY ^ meta_corner_nn) * -1.5463762e-6` |
| DISABLED | V_SUPPLY_I | 0.457 | `VREF * 0.00023058376` |
| DISABLED | VDD_1V2_EXT_I | 0.092 | `-5.8776254e-7 / exp(FUN_DC)` |
| REGULATION | VDD_1V2 | 0.478 | `meta_corner_nn - VDD_1V2_EXT` |
| REGULATION | VPWR_I | 0.085 | `0.030304013 / exp(meta_corner_nn)` |
| REGULATION | FUN_DC_I | 0.309 | `3.7972353e-7 / (((meta_corner_nn / 0.2009204) - FUN_DC) * -3.0858405)` |
| REGULATION | V_SUPPLY_I | 0.071 | `VDD_1V2_EXT * 0.00019922618` |
| REGULATION | VDD_1V2_EXT_I | 0.598 | `(VDD_1V2_EXT / meta_temp) / (exp(FUN_DC) * (meta_temp / VDD_1V2_EXT))` |
| REGULATION_2 | VDD_1V2 | 0.350 | `sqrt(meta_corner_nn)` |
| REGULATION_2 | VPWR_I | 0.059 | `(V_SUPPLY - VPWR) ^ 0.7166998` |
| REGULATION_2 | FUN_DC_I | 0.011 | `(0.051744476 / VPWR) - ((0.051744476 / meta_temp) * meta_corner_nn)` |
| REGULATION_2 | V_SUPPLY_I | 0.159 | `9.680527e-5 / exp(meta_corner_nn)` |
| REGULATION_2 | VDD_1V2_EXT_I | 0.023 | `((meta_corner_ss * 2.058426e-6) / meta_temp) - -2.3587877e-8` |
| REGULATION_3 | VDD_1V2 | 0.124 | `(3.8084342 / meta_temp) + (VREF ^ meta_corner_ss)` |
| REGULATION_3 | VPWR_I | 0.846 | `(meta_vsup_max - VPWR) / (0.019320931 + meta_corner_nn)` |
| REGULATION_3 | FUN_DC_I | 0.268 | `(1.050073 / meta_temp) - -0.105446234` |
| REGULATION_3 | V_SUPPLY_I | 0.138 | `meta_temp * (meta_temp * 2.900725e-9)` |
| REGULATION_3 | VDD_1V2_EXT_I | 0.042 | `(1.2717535e-6 / meta_temp) + -3.2684923e-8` |
| REGULATION_4 | VDD_1V2 | 0.532 | `0.67552704 ^ meta_corner_ss` |
| REGULATION_4 | VPWR_I | 0.470 | `(0.00010239825 / meta_temp) / (meta_corner_ww + -0.458579)` |
| REGULATION_4 | FUN_DC_I | 0.624 | `(0.085075125 - (-1.7163142 / meta_temp)) / exp(meta_corner_ww)` |
| REGULATION_4 | V_SUPPLY_I | 0.967 | `((sqrt(V_SUPPLY ^ V_SUPPLY) + meta_temp) * meta_corner_ss) * 3.740488e-9` |
| REGULATION_4 | VDD_1V2_EXT_I | 0.024 | `meta_corner_ww * -5.7159923e-8` |
| REGULATION_5 | VDD_1V2 | 0.083 | `17.110502 / meta_temp` |
| REGULATION_5 | VPWR_I | 0.381 | `exp(-2.0314393 - meta_corner_nn)` |
| REGULATION_5 | FUN_DC_I | 0.410 | `(exp(FUN_DC) * -3.4677324e-8) * meta_corner_ss` |
| REGULATION_5 | V_SUPPLY_I | 0.050 | `(VPWR ^ meta_corner_nn) * 3.880861e-6` |
| REGULATION_5 | VDD_1V2_EXT_I | 0.041 | `((meta_temp * 1.4662929e-9) * meta_corner_ss) + -3.572575e-8` |
| DISABLED_2 | VDD_1V2 | 0.522 | `meta_corner_nn + -1.2776865` |
| DISABLED_2 | VPWR_I | 0.034 | `0.059661802 / exp(meta_corner_nn)` |
| DISABLED_2 | FUN_DC_I | 0.008 | `(meta_corner_nn * -0.00034742052) - -0.00016552207` |
| DISABLED_2 | V_SUPPLY_I | 0.251 | `((FUN_DC + -3.7091808) + meta_corner_ss) * 0.00011522634` |
| DISABLED_2 | VDD_1V2_EXT_I | 0.233 | `(meta_temp * 8.09544e-9) * meta_corner_ss` |
| REGULATION_6 | VDD_1V2 | 0.990 | `(meta_corner_nn * (VPWR ^ 0.5603452)) - 1.4479212` |
| REGULATION_6 | VPWR_I | 0.460 | `0.018341439 - (meta_temp * -0.00012256035)` |
| REGULATION_6 | FUN_DC_I | 0.812 | `meta_corner_nn * ((exp(meta_vsup_max) * -5.527408e-8) - -1.195265e-5)` |
| REGULATION_6 | V_SUPPLY_I | 0.862 | `((meta_temp * 7.715769e-9) * (V_SUPPLY - 4.643847)) * meta_corner_ss` |
| REGULATION_6 | VDD_1V2_EXT_I | 0.520 | `(meta_temp ^ meta_corner_ss) * 3.675849e-9` |
| REGULATION_7 | VDD_1V2 | 0.990 | `(meta_corner_nn * sqrt(VPWR * 1.2005093)) + -1.4649365` |
| REGULATION_7 | VPWR_I | 0.267 | `exp(meta_corner_ss) * 0.013303139` |
| REGULATION_7 | FUN_DC_I | 0.869 | `meta_corner_nn * ((VPWR * -1.3230053e-5) + 7.070293e-5)` |
| REGULATION_7 | V_SUPPLY_I | 0.922 | `(meta_temp * exp(meta_vsup_max * (3.4147522 ^ meta_corner_ss))) * VDD_1V2_EXT` |
| REGULATION_7 | VDD_1V2_EXT_I | 0.506 | `(meta_temp ^ meta_corner_ss) * 3.8705137e-9` |
| REGULATION_8 | VDD_1V2 | 0.923 | `(VPWR * (meta_corner_nn * 0.47635186)) - 1.5138838` |
| REGULATION_8 | VPWR_I | 0.242 | `(0.1250386 / meta_vsup_max) - (meta_corner_nn * 0.010277628)` |
| REGULATION_8 | FUN_DC_I | 0.902 | `((V_SUPPLY * -1.312765e-5) + 7.011761e-5) * meta_corner_nn` |
| REGULATION_8 | V_SUPPLY_I | 0.417 | `(meta_temp * meta_corner_ss) * 3.1467497e-9` |
| REGULATION_8 | VDD_1V2_EXT_I | 0.139 | `(meta_temp ^ meta_corner_ss) * 3.3101366e-9` |
| REGULATION_9 | VDD_1V2 | 0.959 | `-1.4636978 - (meta_corner_nn * -2.3684993)` |
| REGULATION_9 | VPWR_I | 0.770 | `0.04513471 / (meta_corner_nn + ((0.9907082 ^ meta_temp) + 0.90785295))` |
| REGULATION_9 | FUN_DC_I | 0.270 | `((VPWR * -4.5726897e-6) - -2.2971828e-5) * meta_corner_nn` |
| REGULATION_9 | V_SUPPLY_I | 0.858 | `(meta_temp * (VDD_1V2_EXT * meta_vsup_max)) * exp((meta_corner_ss + FUN_DC) * 2.6012487)` |
| REGULATION_9 | VDD_1V2_EXT_I | 0.883 | `((meta_temp + 35.992157) ^ meta_corner_ss) * 3.0419103e-9` |
| REGULATION_10 | VDD_1V2 | 0.967 | `((meta_corner_nn + -0.6742253) + ((meta_corner_nn * 8.489523) / meta_temp)) / 0.46207693` |
| REGULATION_10 | VPWR_I | 0.296 | `(0.988548 ^ meta_corner_nn) + -0.97341245` |
| REGULATION_10 | FUN_DC_I | 0.176 | `0.00011330891 / (exp(meta_corner_ww + ((meta_corner_ss + meta_vsup_max) / 1.0744958)) - meta_temp)` |
| REGULATION_10 | V_SUPPLY_I | 0.910 | `meta_temp * (exp(meta_vsup_max * (sqrt(exp(1.7557207)) + meta_corner_ss)) * VDD_1V2_EXT)` |
| REGULATION_10 | VDD_1V2_EXT_I | 0.956 | `((meta_temp * 2.8948328e-9) + 1.1579452e-7) * meta_corner_ss` |
| REGULATION_11 | VDD_1V2 | 0.970 | `(meta_corner_nn * sqrt(meta_vsup_max + (101.6483 / meta_temp))) + -1.4786524` |
| REGULATION_11 | VPWR_I | 0.018 | `meta_temp * 3.7178746e-5` |
| REGULATION_11 | FUN_DC_I | 0.038 | `(meta_corner_ss + 1.3892263) * 0.007253301` |
| REGULATION_11 | V_SUPPLY_I | 0.059 | `(V_SUPPLY - meta_corner_ww) * 1.7632417e-5` |
| REGULATION_11 | VDD_1V2_EXT_I | 0.685 | `((meta_temp * 3.567271e-9) - -1.8040652e-7) * meta_corner_ss` |
| REGULATION_12 | VDD_1V2 | 0.964 | `(((-12.966423 / meta_temp) + -0.46688893) ^ meta_corner_nn) / -0.6842628` |
| REGULATION_12 | VPWR_I | 0.311 | `exp(meta_vsup_max) / (meta_temp / -1.3613019e-6)` |
| REGULATION_12 | FUN_DC_I | 0.821 | `0.019284869 - ((meta_temp * -7.683105e-5) * exp(meta_corner_ss - meta_corner_nn))` |
| REGULATION_12 | V_SUPPLY_I | 0.556 | `(meta_corner_ss * (61.524567 ^ FUN_DC)) * VDD_1V2_EXT` |
| REGULATION_12 | VDD_1V2_EXT_I | 0.954 | `((meta_temp * 2.8327183e-9) + 1.1340427e-7) * meta_corner_ss` |
