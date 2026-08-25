# Phase 2 Per-State Model Comparison

BLUT: `blut_files/regression_multi_corner_sref_ldo.bin`  |  good corners: 126/135  |  equation source: `degree-2 polynomial`

## Categorical corner codes

- `meta_corner`: nn=0.4417, ss=-0.519, ww=-1.134

| state | n_samples | PINN | best black-box |
|---|---|---|---|
| DISABLED | 3000 | 0.3918 | PINN |
| REGULATION | 3000 | 0.5663 | PINN |
| REGULATION_2 | 3000 | 1.625 | PINN |
| REGULATION_3 | 3000 | 0.2348 | PINN |
| REGULATION_4 | 3000 | 0.7919 | PINN |
| REGULATION_5 | 3000 | 1.411 | PINN |
| DISABLED_2 | 3000 | 1.734 | PINN |
| REGULATION_6 | 3000 | 0.7967 | PINN |
| REGULATION_7 | 3000 | 2.123 | PINN |
| REGULATION_8 | 3000 | 1.158 | PINN |
| REGULATION_9 | 3000 | 1.822 | PINN |
| REGULATION_10 | 3000 | 1.453 | PINN |
| REGULATION_11 | 3000 | 1.445 | PINN |
| REGULATION_12 | 3000 | 1.411 | PINN |

## Fitted output equations (embedded in the .vams)

| state | output | R2 | equation |
|---|---|---|---|
| DISABLED | VDD_1V2 | 0.198 | `-0.00547834*VPWR + 1.14309*VREF + -0.00547834*FUN_DC + -0.00547834*V_SUPPLY + 0.206063*meta_corner + -0.000924674*meta_temp + 0.0317382*meta_vsup_max + 0.002298` |
| REGULATION | VDD_1V2 | 0.558 | `-0.242475*VPWR + -0.188868*VREF + 0.114826*FUN_DC + -5.32943*VDD_1V2_EXT + 0.114826*V_SUPPLY + 0.810819*meta_corner + 0.000946263*meta_temp + 0.114826*meta_vsup` |
| REGULATION_2 | VDD_1V2 | 0.414 | `-18.0678*VPWR + -0.0797521*VREF + 0.217019*FUN_DC + 0.001497*VDD_1V2_EXT + 8.97692*V_SUPPLY + 0.468348*meta_corner + 0.00156447*meta_temp + 8.97695*meta_vsup_ma` |
| REGULATION_3 | VDD_1V2 | 0.252 | `267.321*VPWR + 0.14345*VREF + -89.0599*FUN_DC + 0.000202342*VDD_1V2_EXT + -89.0611*V_SUPPLY + 0.0565745*meta_corner + 0.00325058*meta_temp + -89.0609*meta_vsup_` |
| REGULATION_4 | VDD_1V2 | 0.657 | `-0.168959*VPWR + 0.910838*VREF + 0.0642021*FUN_DC + 27066*VDD_1V2_EXT + -0.131035*V_SUPPLY + 1.06443*meta_corner + 0.0805602*meta_temp + -0.134159*meta_vsup_max` |
| REGULATION_5 | VDD_1V2 | 0.238 | `-1.25204*VPWR + -0.202616*VREF + 0.460221*FUN_DC + 0.460221*V_SUPPLY + 0.460065*meta_corner + 0.00319633*meta_temp + 0.460221*meta_vsup_max + -0.861659*VPWR*VPW` |
| DISABLED_2 | VDD_1V2 | 0.587 | `0.169296*VPWR + -1.35135*VREF + 0.169296*FUN_DC + 0.169296*V_SUPPLY + 0.597741*meta_corner + 0.00537797*meta_temp + 0.169296*meta_vsup_max + -0.0101481*VPWR*VPW` |
| REGULATION_6 | VDD_1V2 | 0.991 | `0.303427*VPWR + -2.17094*VREF + 0.303427*FUN_DC + 0.303427*V_SUPPLY + 1.48857*meta_corner + 0.00486614*meta_temp + 0.303427*meta_vsup_max + -0.0164483*VPWR*VPWR` |
| REGULATION_7 | VDD_1V2 | 0.990 | `0.417133*VPWR + -2.95025*VREF + 0.417133*FUN_DC + 0.417133*V_SUPPLY + 1.12184*meta_corner + 0.00638081*meta_temp + 0.417133*meta_vsup_max + -0.0222914*VPWR*VPWR` |
| REGULATION_8 | VDD_1V2 | 0.960 | `0.789413*VPWR + -5.37215*VREF + 0.789413*FUN_DC + 0.789413*V_SUPPLY + 0.562028*meta_corner + 0.0139785*meta_temp + 0.789413*meta_vsup_max + -0.0426014*VPWR*VPWR` |
| REGULATION_9 | VDD_1V2 | 0.975 | `0.157741*VPWR + -1.72784*VREF + 0.157741*FUN_DC + 0.157741*V_SUPPLY + 0.259482*meta_corner + 0.0154*meta_temp + 0.157741*meta_vsup_max + -0.00407501*VPWR*VPWR +` |
| REGULATION_10 | VDD_1V2 | 0.971 | `0.0176347*VPWR + -0.628573*VREF + 0.0176347*FUN_DC + 0.0176347*V_SUPPLY + 0.8358*meta_corner + 0.0104936*meta_temp + 0.0176347*meta_vsup_max + 0.00165369*VPWR*V` |
| REGULATION_11 | VDD_1V2 | 0.962 | `0.110869*VPWR + -1.32188*VREF + 0.110869*FUN_DC + 0.110869*V_SUPPLY + 0.504752*meta_corner + 0.01339*meta_temp + 0.110869*meta_vsup_max + -0.00276129*VPWR*VPWR ` |
| REGULATION_12 | VDD_1V2 | 0.968 | `-0.0730259*VPWR + -0.111003*VREF + -0.0730259*FUN_DC + -0.0730259*V_SUPPLY + 0.846319*meta_corner + 0.0111659*meta_temp + -0.0730259*meta_vsup_max + 0.00724598*` |
