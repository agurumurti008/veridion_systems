# Phase 2 Per-State Model Comparison

BLUT: `blut_files/regression_multi_corner_sref_ldo.bin`  |  good corners: 126/135  |  equation source: `pysr`

| state | n_samples | GPR | best black-box |
|---|---|---|---|
| DISABLED | 3000 | 0.05129 | GPR |
| REGULATION | 3000 | 0.04539 | GPR |
| REGULATION_2 | 3000 | 0.08439 | GPR |
| REGULATION_3 | 3000 | 0.01211 | GPR |
| REGULATION_4 | 3000 | 0.00344 | GPR |
| REGULATION_5 | 3000 | 0.02151 | GPR |
| DISABLED_2 | 3000 | 0.03986 | GPR |
| REGULATION_6 | 3000 | 0.0006352 | GPR |
| REGULATION_7 | 3000 | 0.000253 | GPR |
| REGULATION_8 | 3000 | 0.00131 | GPR |
| REGULATION_9 | 3000 | 0.0007502 | GPR |
| REGULATION_10 | 3000 | 0.0008168 | GPR |
| REGULATION_11 | 3000 | 0.0001535 | GPR |
| REGULATION_12 | 3000 | 1.83e-06 | GPR |

## Fitted output equations (embedded in the .vams)

| state | output | R2 | equation |
|---|---|---|---|
| DISABLED | VDD_1V2 | 0.177 | `VREF * (meta_corner_nn - VREF)` |
| DISABLED | VPWR_I | 0.072 | `VREF * 0.041126497` |
| DISABLED | FUN_DC_I | 0.008 | `VREF * -0.00021942465` |
| DISABLED | V_SUPPLY_I | 0.438 | `VREF * 0.00022544723` |
| DISABLED | VDD_1V2_EXT_I | 0.095 | `-6.364355e-7 / exp(VPWR)` |
| REGULATION | VDD_1V2 | 0.509 | `(meta_corner_nn - ((V_SUPPLY / meta_temp) + VDD_1V2_EXT)) - 0.1248706` |
| REGULATION | VPWR_I | 0.095 | `0.03181063 / exp(meta_corner_nn)` |
| REGULATION | FUN_DC_I | -0.003 | `(((meta_vsup_max * -1.023022) + (meta_vsup_max * 1.0230219)) * FUN_DC) / -1.2538127` |
| REGULATION | V_SUPPLY_I | 0.069 | `VDD_1V2_EXT * 0.00025553588` |
| REGULATION | VDD_1V2_EXT_I | 0.621 | `meta_corner_ss * (VDD_1V2_EXT * (0.1878143 ^ meta_vsup_max))` |
| REGULATION_2 | VDD_1V2 | 0.364 | `(VDD_1V2_EXT / 1.3543456e-12) + meta_corner_nn` |
| REGULATION_2 | VPWR_I | 0.070 | `(V_SUPPLY - VPWR) ^ VREF` |
| REGULATION_2 | FUN_DC_I | 0.021 | `0.010260521 - ((meta_corner_nn * meta_temp) * 5.9347847e-5)` |
| REGULATION_2 | V_SUPPLY_I | 0.163 | `0.00010063949 / exp(meta_corner_nn)` |
| REGULATION_2 | VDD_1V2_EXT_I | 0.035 | `(meta_temp ^ meta_corner_ss) * 1.1903831e-9` |
| REGULATION_3 | VDD_1V2 | 0.147 | `(meta_temp * 0.0033589804) + (0.7354823 ^ meta_corner_ss)` |
| REGULATION_3 | VPWR_I | 0.718 | `sqrt(sqrt(FUN_DC - VPWR)) / exp(meta_corner_nn)` |
| REGULATION_3 | FUN_DC_I | 0.181 | `(meta_corner_ss / meta_temp) - -0.11064038` |
| REGULATION_3 | V_SUPPLY_I | 0.235 | `(V_SUPPLY - VPWR) * 0.044856936` |
| REGULATION_3 | VDD_1V2_EXT_I | 0.210 | `((meta_vsup_max - VPWR) ^ 0.0058348337) * -8.2952283e-7` |
| REGULATION_4 | VDD_1V2 | 0.407 | `0.6750668 ^ meta_corner_ss` |
| REGULATION_4 | VPWR_I | -16.041 | `((-0.7931885 ^ meta_corner_ww) / (meta_temp * FUN_DC)) * -0.0011562345` |
| REGULATION_4 | FUN_DC_I | 0.362 | `(1.6288927 / meta_temp) + 0.086470686` |
| REGULATION_4 | V_SUPPLY_I | 0.072 | `exp(meta_temp * 0.21126595) * VDD_1V2_EXT` |
| REGULATION_4 | VDD_1V2_EXT_I | 0.040 | `meta_corner_nn * 2.0927114e-8` |
| REGULATION_5 | VDD_1V2 | 0.129 | `17.734211 / meta_temp` |
| REGULATION_5 | VPWR_I | 0.321 | `0.13132995 / exp(meta_corner_nn)` |
| REGULATION_5 | FUN_DC_I | 0.386 | `(meta_corner_ss * exp(VPWR)) * -3.349362e-8` |
| REGULATION_5 | V_SUPPLY_I | 0.025 | `exp(meta_corner_nn) * 5.3895974e-6` |
| REGULATION_5 | VDD_1V2_EXT_I | 0.043 | `(meta_temp * (1.5592729e-9 * meta_corner_ss)) - 4.0980222e-8` |
| DISABLED_2 | VDD_1V2 | 0.523 | `meta_corner_nn - 1.2501094` |
| DISABLED_2 | VPWR_I | 0.043 | `0.059411358 / exp(meta_corner_nn)` |
| DISABLED_2 | FUN_DC_I | -0.041 | `(-0.46269885 ^ meta_corner_nn) * (1.9374716e-5 / (V_SUPPLY / meta_temp))` |
| DISABLED_2 | V_SUPPLY_I | 0.122 | `(meta_corner_ss + V_SUPPLY) * 3.786347e-5` |
| DISABLED_2 | VDD_1V2_EXT_I | 0.164 | `meta_temp * (meta_corner_ss * 6.5788965e-9)` |
| REGULATION_6 | VDD_1V2 | 0.988 | `(meta_corner_nn * (VPWR ^ 0.56206447)) + -1.4522996` |
| REGULATION_6 | VPWR_I | 0.372 | `0.028002143 / (meta_corner_nn + 1.0943004)` |
| REGULATION_6 | FUN_DC_I | 0.818 | `(((3.8794441 ^ V_SUPPLY) * -6.6813555e-9) + 9.786783e-6) * meta_corner_nn` |
| REGULATION_6 | V_SUPPLY_I | 0.813 | `(exp(sqrt(exp(FUN_DC ^ meta_corner_ss))) * meta_temp) * 1.2306385e-15` |
| REGULATION_6 | VDD_1V2_EXT_I | 0.414 | `(meta_temp ^ meta_corner_ss) * 3.5509453e-9` |
| REGULATION_7 | VDD_1V2 | 0.986 | `((meta_corner_nn * V_SUPPLY) ^ 0.5561609) - 1.4656484` |
| REGULATION_7 | VPWR_I | 0.409 | `0.01810873 - (meta_temp * -0.00011692533)` |
| REGULATION_7 | FUN_DC_I | 0.845 | `meta_corner_nn * (-6.5588174e-5 - (-0.00034985054 / meta_vsup_max))` |
| REGULATION_7 | V_SUPPLY_I | 0.909 | `meta_temp * (VDD_1V2_EXT * (meta_corner_ss / exp(V_SUPPLY / (VREF * -0.4162371))))` |
| REGULATION_7 | VDD_1V2_EXT_I | 0.486 | `(meta_temp ^ meta_corner_ss) * 3.7002321e-9` |
| REGULATION_8 | VDD_1V2 | 0.950 | `((meta_corner_nn * 0.47112486) * V_SUPPLY) - 1.4851253` |
| REGULATION_8 | VPWR_I | 0.237 | `(meta_corner_nn * -0.012240113) + 0.026069034` |
| REGULATION_8 | FUN_DC_I | 0.927 | `((meta_corner_nn * 2.721065) ^ V_SUPPLY) * ((2.1131052e-6 / meta_vsup_max) + -3.924735e-7)` |
| REGULATION_8 | V_SUPPLY_I | 0.896 | `VDD_1V2_EXT * (meta_temp * (((FUN_DC ^ meta_corner_ss) * VPWR) ^ FUN_DC))` |
| REGULATION_8 | VDD_1V2_EXT_I | 0.327 | `(meta_temp ^ meta_corner_ss) * 3.5985344e-9` |
| REGULATION_9 | VDD_1V2 | 0.949 | `(meta_corner_nn * 2.3558204) - 1.4595085` |
| REGULATION_9 | VPWR_I | 0.815 | `(0.023959162 - (meta_temp * (meta_corner_ss * -0.00018170338))) + (meta_corner_nn * -0.009569389)` |
| REGULATION_9 | FUN_DC_I | 0.264 | `meta_corner_nn * ((V_SUPPLY * -4.873445e-6) - -2.4617542e-5)` |
| REGULATION_9 | V_SUPPLY_I | 0.774 | `(9.669508e-14 * (meta_temp * exp(meta_vsup_max))) * exp(meta_vsup_max ^ meta_corner_ss)` |
| REGULATION_9 | VDD_1V2_EXT_I | 0.879 | `((meta_temp - -37.626545) ^ meta_corner_ss) * 2.8657816e-9` |
| REGULATION_10 | VDD_1V2 | 0.974 | `log((meta_corner_nn + 1.2348759) - ((-45.265182 / meta_temp) ^ meta_corner_nn))` |
| REGULATION_10 | VPWR_I | 0.911 | `0.015244789 - (((meta_temp * -6.907349e-5) - 0.003192626) / exp(meta_corner_nn - meta_corner_ss))` |
| REGULATION_10 | FUN_DC_I | 0.143 | `1.0075229e-6 / (V_SUPPLY - ((meta_corner_ss * 0.17950268) * meta_temp))` |
| REGULATION_10 | V_SUPPLY_I | 0.935 | `(meta_temp * (exp(log(VPWR) ^ VPWR) * VDD_1V2_EXT)) * meta_corner_ss` |
| REGULATION_10 | VDD_1V2_EXT_I | 0.957 | `((meta_temp * 2.8660658e-9) + 1.16080074e-7) * meta_corner_ss` |
| REGULATION_11 | VDD_1V2 | 0.905 | `exp(meta_corner_nn + (6.3129 / meta_temp)) + -2.383977` |
| REGULATION_11 | VPWR_I | 0.029 | `((meta_temp * 8.5312466e-5) + 0.00505587) / exp(V_SUPPLY ^ meta_corner_nn)` |
| REGULATION_11 | FUN_DC_I | 0.035 | `((meta_corner_ss * meta_temp) * 7.709605e-5) + 0.011035271` |
| REGULATION_11 | V_SUPPLY_I | 0.107 | `((FUN_DC + meta_corner_ss) * 3.6029058e-5) - 0.000108637265` |
| REGULATION_11 | VDD_1V2_EXT_I | 0.698 | `meta_corner_ss * (1.8781276e-7 - (meta_temp * -3.5796812e-9))` |
| REGULATION_12 | VDD_1V2 | 0.976 | `(sqrt(V_SUPPLY + (91.38168 / meta_temp)) * meta_corner_nn) + -1.4729534` |
| REGULATION_12 | VPWR_I | 0.337 | `(exp(FUN_DC) / meta_temp) * -1.4070043e-6` |
| REGULATION_12 | FUN_DC_I | 0.825 | `0.022221725 / sqrt((0.9911508 ^ meta_temp) + meta_corner_nn)` |
| REGULATION_12 | V_SUPPLY_I | 0.922 | `(meta_temp * (exp(VPWR ^ meta_corner_ss) * VDD_1V2_EXT)) / (0.09454076 ^ VPWR)` |
| REGULATION_12 | VDD_1V2_EXT_I | 0.958 | `((meta_temp * 2.904899e-9) + 1.1423748e-7) * meta_corner_ss` |
