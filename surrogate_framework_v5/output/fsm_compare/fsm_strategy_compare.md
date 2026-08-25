# FSM Strategy Comparison

BLUT source: `/workspaces/Veridion_Systems/surrogate_framework_v5/examples/../blut_files/regression_multi_corner_ldo.bin`

| strategy | n_states | state_names | n_transitions | reachability | completeness | determinism | speckg_coverage | missing_states | warnings | errors |
|---|---|---|---|---|---|---|---|---|---|---|
| logic | 10 | DISABLED, REGULATION, REGULATION_2, REGULATION_3, STARTUP, DISABLED_2, DISABLED_3, DISABLED_4, REGULATION_4, DISABLED_5 | 22 | False | True | True | 37.5% | UVLO, HIGH_POWER_MODE, SCAN_MODE, OVERRIDE, SHUTDOWN | 2 | 0 |
| cluster | 7 | DISABLED, REGULATION, REGULATION_2, REGULATION_3, HIGH_POWER_MODE, SCAN_MODE, REGULATION_4 | 12 | False | True | True | 50.0% | UVLO, STARTUP, OVERRIDE, SHUTDOWN | 2 | 0 |
| hybrid | 10 | DISABLED, REGULATION, REGULATION_2, REGULATION_3, STARTUP, DISABLED_2, DISABLED_3, DISABLED_4, REGULATION_4, DISABLED_5 | 22 | False | True | True | 37.5% | UVLO, HIGH_POWER_MODE, SCAN_MODE, OVERRIDE, SHUTDOWN | 2 | 0 |

