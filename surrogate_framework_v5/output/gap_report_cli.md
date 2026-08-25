# FSM Completeness — Gap Report

## Scorecard

| metric | value |
|---|---|
| state coverage | 42.9% |
| transition coverage | 28.6% |
| transient richness | 100.0% |
| missing states | 4 |
| missing transitions | 10 |
| clipped (counted as gaps) | 0 |
| current-informed gaps | 0 |
| output contradictions | 5 |
| corners exercised | 1 |

## Gaps

| # | gap | why it matters | recommended run | impact if left open |
|---|---|---|---|---|
| 1 | state STARTUP never observed | reference state absent from all runs | exercise entry into STARTUP @ any, >=2.5e-05s | STARTUP behavior defaults to nearest state; unmodeled |
| 2 | state DROPOUT never observed | reference state absent from all runs | exercise entry into DROPOUT @ any, >=2.5e-05s | DROPOUT behavior defaults to nearest state; unmodeled |
| 3 | state FAULT never observed | reference state absent from all runs | exercise entry into FAULT @ any, >=2.5e-05s | FAULT behavior defaults to nearest state; unmodeled |
| 4 | state SCAN never observed | reference state absent from all runs | exercise entry into SCAN @ any, >=2.5e-05s | SCAN behavior defaults to nearest state; unmodeled |
| 5 | transition DISABLED->STARTUP never observed | expected edge missing; guard unverified | drive DISABLED->STARTUP event @ any, >=2.5e-05s | transition guard unvalidated by data |
| 6 | transition DROPOUT->REGULATION_HP never observed | expected edge missing; guard unverified | drive DROPOUT->REGULATION_HP event @ any, >=2.5e-05s | transition guard unvalidated by data |
| 7 | transition DROPOUT->REGULATION_LP never observed | expected edge missing; guard unverified | drive DROPOUT->REGULATION_LP event @ any, >=2.5e-05s | transition guard unvalidated by data |
| 8 | transition FAULT->DISABLED never observed | expected edge missing; guard unverified | drive FAULT->DISABLED event @ any, >=2.5e-05s | transition guard unvalidated by data |
| 9 | transition REGULATION_HP->DROPOUT never observed | expected edge missing; guard unverified | drive REGULATION_HP->DROPOUT event @ any, >=2.5e-05s | transition guard unvalidated by data |
| 10 | transition REGULATION_HP->FAULT never observed | expected edge missing; guard unverified | drive REGULATION_HP->FAULT event @ any, >=2.5e-05s | transition guard unvalidated by data |
| 11 | transition REGULATION_LP->DROPOUT never observed | expected edge missing; guard unverified | drive REGULATION_LP->DROPOUT event @ any, >=2.5e-05s | transition guard unvalidated by data |
| 12 | transition REGULATION_LP->FAULT never observed | expected edge missing; guard unverified | drive REGULATION_LP->FAULT event @ any, >=2.5e-05s | transition guard unvalidated by data |
| 13 | transition STARTUP->REGULATION_HP never observed | expected edge missing; guard unverified | drive STARTUP->REGULATION_HP event @ any, >=2.5e-05s | transition guard unvalidated by data |
| 14 | transition STARTUP->REGULATION_LP never observed | expected edge missing; guard unverified | drive STARTUP->REGULATION_LP event @ any, >=2.5e-05s | transition guard unvalidated by data |
| 15 | state REGULATION_3 dwell insufficient | dwell < 3x settling; analog response not captured | hold REGULATION_3 longer @ any, >=2.5e-05s | REGULATION_3 steady-state params under-constrained |
| 16 | state REGULATION_4 dwell insufficient | dwell < 3x settling; analog response not captured | hold REGULATION_4 longer @ any, >=2.5e-05s | REGULATION_4 steady-state params under-constrained |
| 17 | state REGULATION_5 dwell insufficient | dwell < 3x settling; analog response not captured | hold REGULATION_5 longer @ any, >=2.5e-05s | REGULATION_5 steady-state params under-constrained |
| 18 | state DISABLED_5 dwell insufficient | dwell < 3x settling; analog response not captured | hold DISABLED_5 longer @ any, >=2.5e-05s | DISABLED_5 steady-state params under-constrained |
| 19 | state REGULATION_6 dwell insufficient | dwell < 3x settling; analog response not captured | hold REGULATION_6 longer @ any, >=2.5e-05s | REGULATION_6 steady-state params under-constrained |
| 20 | state REGULATION_8 dwell insufficient | dwell < 3x settling; analog response not captured | hold REGULATION_8 longer @ any, >=2.5e-05s | REGULATION_8 steady-state params under-constrained |
| 21 | state REGULATION_10 dwell insufficient | dwell < 3x settling; analog response not captured | hold REGULATION_10 longer @ any, >=2.5e-05s | REGULATION_10 steady-state params under-constrained |
| 22 | output-consistency: EN_UVLO_1V2 in DISABLED_2 | ready-role indicator observed at mean 0.769 but the DISABLED_2 family expects 0 | re-exercise DISABLED_2 and capture EN_UVLO_1V2; confirm the ready role assignment @ any, >=2.5e-05s | emitted status-indicator drive may misrepresent this state |
| 23 | output-consistency: EN_UVLO_1V2 in DISABLED_3 | ready-role indicator observed at mean 0.809 but the DISABLED_3 family expects 0 | re-exercise DISABLED_3 and capture EN_UVLO_1V2; confirm the ready role assignment @ any, >=2.5e-05s | emitted status-indicator drive may misrepresent this state |
| 24 | output-consistency: EN_UVLO_1V2 in DISABLED_4 | ready-role indicator observed at mean 1.0 but the DISABLED_4 family expects 0 | re-exercise DISABLED_4 and capture EN_UVLO_1V2; confirm the ready role assignment @ any, >=2.5e-05s | emitted status-indicator drive may misrepresent this state |
| 25 | output-consistency: EN_UVLO_1V2 in DISABLED_5 | ready-role indicator observed at mean 1.0 but the DISABLED_5 family expects 0 | re-exercise DISABLED_5 and capture EN_UVLO_1V2; confirm the ready role assignment @ any, >=2.5e-05s | emitted status-indicator drive may misrepresent this state |
| 26 | output-consistency: EN_UVLO_1V2 in DISABLED_6 | ready-role indicator observed at mean 1.0 but the DISABLED_6 family expects 0 | re-exercise DISABLED_6 and capture EN_UVLO_1V2; confirm the ready role assignment @ any, >=2.5e-05s | emitted status-indicator drive may misrepresent this state |
| 27 | only 1/3 corners | states/transitions not exercised across PVT | repeat key runs at missing corners @ SS/FF, >=2.5e-05s | PVT parameter grid sparse |

## Decision (choose one)

**Option 1 — provide these runs** (model improves proactively):

| run | stimulus | pins | corner | min duration |
|---|---|---|---|---|
| R1 | enter STARTUP | EN_LDO=1 | any | 2.5e-05s |
| R2 | enter DROPOUT | EN_LDO=1,V_SUPPLY->dropout | any | 2.5e-05s |
| R3 | enter FAULT | fault-inject | any | 2.5e-05s |
| R4 | enter SCAN | SCAN_MODE_VSUPPLY=1 | any | 2.5e-05s |
| R5 | DISABLED->STARTUP event | EN_LDO=1 | any | 2.5e-05s |
| R6 | DROPOUT->REGULATION_HP event | EN_LDO=1,HIGH_POWER_MODE=1 | any | 2.5e-05s |
| R7 | DROPOUT->REGULATION_LP event | EN_LDO=1,HIGH_POWER_MODE=0 | any | 2.5e-05s |
| R8 | FAULT->DISABLED event | EN_LDO=0 | any | 2.5e-05s |
| R9 | REGULATION_HP->DROPOUT event | EN_LDO=1,V_SUPPLY->dropout | any | 2.5e-05s |
| R10 | REGULATION_HP->FAULT event | fault-inject | any | 2.5e-05s |
| R11 | REGULATION_LP->DROPOUT event | EN_LDO=1,V_SUPPLY->dropout | any | 2.5e-05s |
| R12 | REGULATION_LP->FAULT event | fault-inject | any | 2.5e-05s |
| R13 | STARTUP->REGULATION_HP event | EN_LDO=1,HIGH_POWER_MODE=1 | any | 2.5e-05s |
| R14 | STARTUP->REGULATION_LP event | EN_LDO=1,HIGH_POWER_MODE=0 | any | 2.5e-05s |

**Option 2 — proceed now** (these limitations are stamped into the emitted Verilog-A `LIMITATIONS:` header):

- `LIMITATIONS: state STARTUP not characterized (no run enters it)`
- `LIMITATIONS: state DROPOUT not characterized (no run enters it)`
- `LIMITATIONS: state FAULT not characterized (no run enters it)`
- `LIMITATIONS: state SCAN not characterized (no run enters it)`
- `LIMITATIONS: transition DISABLED->STARTUP unverified`
- `LIMITATIONS: transition DROPOUT->REGULATION_HP unverified`
- `LIMITATIONS: transition DROPOUT->REGULATION_LP unverified`
- `LIMITATIONS: transition FAULT->DISABLED unverified`
- `LIMITATIONS: transition REGULATION_HP->DROPOUT unverified`
- `LIMITATIONS: transition REGULATION_HP->FAULT unverified`
- `LIMITATIONS: transition REGULATION_LP->DROPOUT unverified`
- `LIMITATIONS: transition REGULATION_LP->FAULT unverified`
- `LIMITATIONS: transition STARTUP->REGULATION_HP unverified`
- `LIMITATIONS: transition STARTUP->REGULATION_LP unverified`
- `LIMITATIONS: REGULATION_3 dwell too short for steady-state fit`
- `LIMITATIONS: REGULATION_4 dwell too short for steady-state fit`
- `LIMITATIONS: REGULATION_5 dwell too short for steady-state fit`
- `LIMITATIONS: DISABLED_5 dwell too short for steady-state fit`
- `LIMITATIONS: REGULATION_6 dwell too short for steady-state fit`
- `LIMITATIONS: REGULATION_8 dwell too short for steady-state fit`
- `LIMITATIONS: REGULATION_10 dwell too short for steady-state fit`
- `LIMITATIONS: output-consistency: EN_UVLO_1V2 contradicts DISABLED_2 (ready role)`
- `LIMITATIONS: output-consistency: EN_UVLO_1V2 contradicts DISABLED_3 (ready role)`
- `LIMITATIONS: output-consistency: EN_UVLO_1V2 contradicts DISABLED_4 (ready role)`
- `LIMITATIONS: output-consistency: EN_UVLO_1V2 contradicts DISABLED_5 (ready role)`
- `LIMITATIONS: output-consistency: EN_UVLO_1V2 contradicts DISABLED_6 (ready role)`
- `LIMITATIONS: corner coverage 1/3`
