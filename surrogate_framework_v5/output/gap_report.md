# FSM Completeness — Gap Report

## Scorecard

| metric | value |
|---|---|
| state coverage | 42.9% |
| transition coverage | 14.3% |
| transient richness | 100.0% |
| missing states | 4 |
| missing transitions | 12 |
| clipped (counted as gaps) | 0 |
| current-informed gaps | 1 |
| output contradictions | 0 |
| corners exercised | 3 |

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
| 9 | transition REGULATION_HP->DISABLED never observed | expected edge missing; guard unverified | drive REGULATION_HP->DISABLED event @ any, >=2.5e-05s | transition guard unvalidated by data |
| 10 | transition REGULATION_HP->DROPOUT never observed | expected edge missing; guard unverified | drive REGULATION_HP->DROPOUT event @ any, >=2.5e-05s | transition guard unvalidated by data |
| 11 | transition REGULATION_HP->FAULT never observed | expected edge missing; guard unverified | drive REGULATION_HP->FAULT event @ any, >=2.5e-05s | transition guard unvalidated by data |
| 12 | transition REGULATION_LP->DISABLED never observed | expected edge missing; guard unverified | drive REGULATION_LP->DISABLED event @ any, >=2.5e-05s | transition guard unvalidated by data |
| 13 | transition REGULATION_LP->DROPOUT never observed | expected edge missing; guard unverified | drive REGULATION_LP->DROPOUT event @ any, >=2.5e-05s | transition guard unvalidated by data |
| 14 | transition REGULATION_LP->FAULT never observed | expected edge missing; guard unverified | drive REGULATION_LP->FAULT event @ any, >=2.5e-05s | transition guard unvalidated by data |
| 15 | transition STARTUP->REGULATION_HP never observed | expected edge missing; guard unverified | drive STARTUP->REGULATION_HP event @ any, >=2.5e-05s | transition guard unvalidated by data |
| 16 | transition STARTUP->REGULATION_LP never observed | expected edge missing; guard unverified | drive STARTUP->REGULATION_LP event @ any, >=2.5e-05s | transition guard unvalidated by data |
| 17 | state DISABLED dwell insufficient | dwell < 3x settling; analog response not captured | hold DISABLED longer @ any, >=2.5e-05s | DISABLED steady-state params under-constrained |
| 18 | mux path VPWR_SEL,VPWR,FUN_DC,ISO,MOST_POS,V_SUPPLY not current-verified | SEL path never current-verified (functional gap even if voltage-covered) | SEL toggle, all candidate supplies live @ any, >=2.5e-05s | selected supply path unproven; possible untested-mux bug |

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
| R9 | REGULATION_HP->DISABLED event | EN_LDO=0 | any | 2.5e-05s |
| R10 | REGULATION_HP->DROPOUT event | EN_LDO=1,V_SUPPLY->dropout | any | 2.5e-05s |
| R11 | REGULATION_HP->FAULT event | fault-inject | any | 2.5e-05s |
| R12 | REGULATION_LP->DISABLED event | EN_LDO=0 | any | 2.5e-05s |
| R13 | REGULATION_LP->DROPOUT event | EN_LDO=1,V_SUPPLY->dropout | any | 2.5e-05s |
| R14 | REGULATION_LP->FAULT event | fault-inject | any | 2.5e-05s |
| R15 | STARTUP->REGULATION_HP event | EN_LDO=1,HIGH_POWER_MODE=1 | any | 2.5e-05s |
| R16 | STARTUP->REGULATION_LP event | EN_LDO=1,HIGH_POWER_MODE=0 | any | 2.5e-05s |
| R17 | SEL toggle w/ candidates live | VPWR_SEL,VPWR,FUN_DC,ISO,MOST_POS,V_SUPPLY | any | 2.5e-05s |

**Option 2 — proceed now** (these limitations are stamped into the emitted Verilog-A `LIMITATIONS:` header):

- `LIMITATIONS: state STARTUP not characterized (no run enters it)`
- `LIMITATIONS: state DROPOUT not characterized (no run enters it)`
- `LIMITATIONS: state FAULT not characterized (no run enters it)`
- `LIMITATIONS: state SCAN not characterized (no run enters it)`
- `LIMITATIONS: transition DISABLED->STARTUP unverified`
- `LIMITATIONS: transition DROPOUT->REGULATION_HP unverified`
- `LIMITATIONS: transition DROPOUT->REGULATION_LP unverified`
- `LIMITATIONS: transition FAULT->DISABLED unverified`
- `LIMITATIONS: transition REGULATION_HP->DISABLED unverified`
- `LIMITATIONS: transition REGULATION_HP->DROPOUT unverified`
- `LIMITATIONS: transition REGULATION_HP->FAULT unverified`
- `LIMITATIONS: transition REGULATION_LP->DISABLED unverified`
- `LIMITATIONS: transition REGULATION_LP->DROPOUT unverified`
- `LIMITATIONS: transition REGULATION_LP->FAULT unverified`
- `LIMITATIONS: transition STARTUP->REGULATION_HP unverified`
- `LIMITATIONS: transition STARTUP->REGULATION_LP unverified`
- `LIMITATIONS: DISABLED dwell too short for steady-state fit`
- `LIMITATIONS: mux VPWR_SEL,VPWR,FUN_DC,ISO,MOST_POS,V_SUPPLY path not current-verified`
