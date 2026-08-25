# Per-Corner FSM Correlation Report

BLUT source: `blut_files/regression_multi_corner_ldo.bin`  |  strategy: `hybrid`  |  corners: 27

## Findings

| severity | category | summary |
|---|---|---|
| medium | corner-outlier | corner_nn_27c_vsup_4p5: FSM validation: completeness=False |
| medium | corner-outlier | corner_ss_27c_vsup_4p5: FSM validation: completeness=False |
| medium | corner-outlier | corner_ss_n40c_vsup_5: FSM validation: completeness=False |
| high | meta-run_id-mismatch | RunMeta.meta disagrees with the run_id-encoded corner for 25/27 runs — meta is not a trustworthy per-run corner source for this file |

## Outlier corners (3/27)

- **corner_nn_27c_vsup_4p5**: FSM validation: completeness=False
- **corner_ss_27c_vsup_4p5**: FSM validation: completeness=False
- **corner_ss_n40c_vsup_5**: FSM validation: completeness=False

## Per-corner table

| run_id | process | temp | vsup | n_signals | completeness% | ntime | n_states | determinism | speckg_coverage | meta_ok | outlier |
|---|---|---|---|---|---|---|---|---|---|---|---|
| corner_nn_125c_vsup_4p5 | nn | 125 | 4p5 | 35 | 68.6 | 1597 | 5 | True | 62% | False |  |
| corner_nn_125c_vsup_5 | nn | 125 | 5 | 27 | 52.9 | 2418 | 4 | True | 25% | False |  |
| corner_nn_125c_vsup_5p5 | nn | 125 | 5p5 | 43 | 84.3 | 2579 | 4 | True | 25% | False |  |
| corner_nn_27c_vsup_4p5 | nn | 27 | 4p5 | 32 | 62.7 | 1657 | 2 | True | 25% | False | YES |
| corner_nn_27c_vsup_5 | nn | 27 | 5 | 35 | 68.6 | 3897 | 3 | True | 25% | False |  |
| corner_nn_27c_vsup_5p5 | nn | 27 | 5p5 | 35 | 68.6 | 3918 | 7 | True | 50% | False |  |
| corner_nn_n40c_vsup_4p5 | nn | n40 | 4p5 | 59 | 115.7 | 32916 | 5 | True | 25% | False |  |
| corner_nn_n40c_vsup_5 | nn | n40 | 5 | 27 | 52.9 | 125599 | 2 | True | 25% | False |  |
| corner_nn_n40c_vsup_5p5 | nn | n40 | 5p5 | 19 | 37.3 | 2938 | 2 | True | 25% | False |  |
| corner_ss_125c_vsup_4p5 | ss | 125 | 4p5 | 27 | 52.9 | 3198 | 3 | True | 25% | False |  |
| corner_ss_125c_vsup_5 | ss | 125 | 5 | 35 | 68.6 | 3042 | 4 | True | 25% | False |  |
| corner_ss_125c_vsup_5p5 | ss | 125 | 5p5 | 27 | 52.9 | 2472 | 6 | True | 12% | False |  |
| corner_ss_27c_vsup_4p5 | ss | 27 | 4p5 | 19 | 37.3 | 2357 | 5 | True | 25% | False | YES |
| corner_ss_27c_vsup_5 | ss | 27 | 5 | 35 | 68.6 | 3934 | 3 | True | 38% | False |  |
| corner_ss_27c_vsup_5p5 | ss | 27 | 5p5 | 35 | 68.6 | 2326 | 4 | True | 50% | False |  |
| corner_ss_n40c_vsup_4p5 | ss | n40 | 4p5 | 19 | 37.3 | 3954 | 2 | True | 25% | False |  |
| corner_ss_n40c_vsup_5 | ss | n40 | 5 | 19 | 37.3 | 1030 | 2 | True | 25% | False | YES |
| corner_ss_n40c_vsup_5p5 | ss | n40 | 5p5 | 19 | 37.3 | 3860 | 3 | True | 25% | False |  |
| corner_ww_125c_vsup_4p5 | ww | 125 | 4p5 | 43 | 84.3 | 2307 | 6 | True | 12% | True |  |
| corner_ww_125c_vsup_5 | ww | 125 | 5 | 19 | 37.3 | 3203 | 3 | True | 25% | True |  |
| corner_ww_125c_vsup_5p5 | ww | 125 | 5p5 | 27 | 52.9 | 1516 | 2 | True | 12% | False |  |
| corner_ww_27c_vsup_4p5 | ww | 27 | 4p5 | 24 | 47.1 | 1839 | 4 | True | 25% | False |  |
| corner_ww_27c_vsup_5 | ww | 27 | 5 | 27 | 52.9 | 2419 | 5 | True | 25% | False |  |
| corner_ww_27c_vsup_5p5 | ww | 27 | 5p5 | 35 | 68.6 | 2008 | 5 | True | 25% | False |  |
| corner_ww_n40c_vsup_4p5 | ww | n40 | 4p5 | 40 | 78.4 | 1965 | 3 | True | 12% | False |  |
| corner_ww_n40c_vsup_5 | ww | n40 | 5 | 24 | 47.1 | 4068 | 2 | True | 12% | False |  |
| corner_ww_n40c_vsup_5p5 | ww | n40 | 5p5 | 32 | 62.7 | 4212 | 4 | True | 25% | False |  |
