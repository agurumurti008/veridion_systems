# Phase 2 Model Comparison — Gray-Box Analog-Template Fitting

BLUT: `blut_files/regression_multi_corner_sref_ldo.bin`  |  good corners: 126/135  |  equation source: `PySR (--include_symbolic)`

## Gray-box fit — see `graybox_fit_report.md`

## Categorical corner codes

- `meta_corner`: nn=0.3461, ss=-0.4769, ww=-0.7629

## Sample caps used

- general (equation fit + PINN + NODE): 200000
- GPR/SMT: 3000
- PySR: 5000

## Denoising impact evaluation

State: REGULATION  Output: VDD_1V2  n=332735

- unsmoothed: R2=0.5122
- smoothed(w=11): R2=0.5122

| state | n_samples | GPR | NODE | PINN | SMT | best black-box |
|---|---|---|---|---|---|---|
| DISABLED | 75704 | 0.1615 | 1.8e+10 | 0.0675 | 0.3737 | PINN |
| REGULATION | 200000 | 0.2582 | 2.203e+11 | 0.2189 | 0.5131 | PINN |
| REGULATION_2 | 180379 | 0.4915 | 7.203e+10 | 0.4317 | 0.7988 | PINN |
| REGULATION_3 | 25338 | 0.06742 | 1.796e+10 | 0.07787 | 0.08867 | GPR |
| REGULATION_4 | 59280 | 0.02663 | 7.223e+10 | 0.02251 | 0.0618 | PINN |
| REGULATION_5 | 55918 | 0.445 | 1.809e+10 | 0.2909 | 0.5189 | PINN |
| DISABLED_2 | 15387 | 0.2024 | 1.821e+10 | 0.1071 | 0.7644 | PINN |
| REGULATION_6 | 45642 | 0.01061 | 1.778e+10 | 0.02067 | 0.3307 | GPR |
| REGULATION_7 | 37555 | 0.007345 | 1.795e+10 | 0.02172 | 0.2736 | GPR |
| REGULATION_8 | 32484 | 0.01055 | 1.792e+10 | 0.02243 | 0.1491 | GPR |
| REGULATION_9 | 13177 | 0.05639 | 1.807e+10 | 0.03969 | 1.029 | PINN |
| REGULATION_10 | 3654 | 0.1514 | 1.818e+10 | 0.07575 | 1.294 | PINN |
| REGULATION_11 | 12995 | 0.1608 | 1.81e+10 | 0.08399 | 1.277 | PINN |
| REGULATION_12 | 6094 | 0.148 | 1.798e+10 | 0.05822 | 1.252 | PINN |

## Fitted output equations (embedded in the .vams)

| state | output | R2 | has ddt/idt | equation |
|---|---|---|---|---|
| DISABLED | VDD_1V2 | n/a | False | `FAILED` |
| REGULATION | VDD_1V2 | n/a | False | `FAILED` |
| REGULATION_2 | VDD_1V2 | n/a | False | `FAILED` |
| REGULATION_3 | VDD_1V2 | n/a | False | `FAILED` |
| REGULATION_4 | VDD_1V2 | n/a | False | `FAILED` |
| REGULATION_5 | VDD_1V2 | n/a | False | `FAILED` |
| DISABLED_2 | VDD_1V2 | n/a | False | `FAILED` |
| REGULATION_6 | VDD_1V2 | n/a | False | `FAILED` |
| REGULATION_7 | VDD_1V2 | n/a | False | `FAILED` |
| REGULATION_8 | VDD_1V2 | n/a | False | `FAILED` |
| REGULATION_9 | VDD_1V2 | n/a | False | `FAILED` |
| REGULATION_10 | VDD_1V2 | n/a | False | `FAILED` |
| REGULATION_11 | VDD_1V2 | n/a | False | `FAILED` |
| REGULATION_12 | VDD_1V2 | n/a | False | `FAILED` |
