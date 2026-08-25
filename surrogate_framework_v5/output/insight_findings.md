# Current-Insight Findings

| severity | count |
|---|---|
| high | 4 |
| medium | 5 |
| info | 17 |

| # | analyzer | severity | summary | pins | states | action |
|---|---|---|---|---|---|---|
| 1 | 3.1 supply-attribution | high | REGULATION_2 powered mainly from VPWR, not primary V_SUPPLY | VPWR,V_SUPPLY | REGULATION_2 | confirm intended supply for this state; possible mux/routing bug |
| 2 | 3.4 mux-verification | high | VPWR_SEL toggled but no candidate supply current redistributed — mux path unverified | VPWR_SEL,VPWR,FUN_DC,ISO,MOST_POS,V_SUPPLY | - | provide a SEL-toggle run with all candidate supplies live to prove the selected path |
| 3 | 3.3/3.7 drive-strength | high | VDD_1V2 sustains only 0.0825 mA in reg (spec 200 mA) | VDD_1V2 | - | provide a load-sweep run to full spec current; if real, raise pass-device drive |
| 4 | 3.3/3.7 drive-strength | high | VDD_1V2 collapses below reg when demand exceeds capacity | VDD_1V2 | - | downstream loads on this rail see the sag; confirm current-limit/foldback intent |
| 5 | 3.11 transition-health | medium | REGULATION inrush -> C_out estimate 0.00 uF | VDD_1V2 | DISABLED,REGULATION | inrush-derived C_out disagrees with fit; reconcile |
| 6 | 3.11 transition-health | medium | REGULATION inrush -> C_out estimate 0.00 uF | VDD_1V2 | DISABLED,REGULATION | inrush-derived C_out disagrees with fit; reconcile |
| 7 | 3.11 transition-health | medium | REGULATION inrush -> C_out estimate 0.00 uF | VDD_1V2 | DISABLED,REGULATION | inrush-derived C_out disagrees with fit; reconcile |
| 8 | 3.11 transition-health | medium | REGULATION inrush -> C_out estimate 0.00 uF | VDD_1V2 | DISABLED,REGULATION | inrush-derived C_out disagrees with fit; reconcile |
| 9 | 3.11 transition-health | medium | REGULATION inrush -> C_out estimate 0.00 uF | VDD_1V2 | DISABLED,REGULATION | inrush-derived C_out disagrees with fit; reconcile |
| 10 | 3.1 supply-attribution | info | DISABLED: dominant supply V_SUPPLY (3.8 uA) | - | DISABLED |  |
| 11 | 3.1 supply-attribution | info | REGULATION: dominant supply V_SUPPLY (49.5 uA) | - | REGULATION |  |
| 12 | 3.1 supply-attribution | info | REGULATION_2: dominant supply VPWR (39.8 uA) | - | REGULATION_2 |  |
| 13 | 3.1 supply-attribution | info | DISABLED: dominant supply V_SUPPLY (3.7 uA) | - | DISABLED |  |
| 14 | 3.1 supply-attribution | info | REGULATION: dominant supply V_SUPPLY (49.7 uA) | - | REGULATION |  |
| 15 | 3.1 supply-attribution | info | REGULATION_2: dominant supply V_SUPPLY (50.0 uA) | - | REGULATION_2 |  |
| 16 | 3.1 supply-attribution | info | DISABLED: dominant supply V_SUPPLY (3.8 uA) | - | DISABLED |  |
| 17 | 3.1 supply-attribution | info | REGULATION: dominant supply V_SUPPLY (49.8 uA) | - | REGULATION |  |
| 18 | 3.1 supply-attribution | info | REGULATION_3: dominant supply V_SUPPLY (50.0 uA) | - | REGULATION_3 |  |
| 19 | 3.1 supply-attribution | info | DISABLED: dominant supply V_SUPPLY (3.7 uA) | - | DISABLED |  |
| 20 | 3.1 supply-attribution | info | REGULATION: dominant supply V_SUPPLY (49.9 uA) | - | REGULATION |  |
| 21 | 3.1 supply-attribution | info | DISABLED: dominant supply V_SUPPLY (3.8 uA) | - | DISABLED |  |
| 22 | 3.1 supply-attribution | info | REGULATION: dominant supply V_SUPPLY (49.9 uA) | - | REGULATION |  |
| 23 | 3.4 mux-verification | info | VPWR_SEL toggle: current shifted to VPWR from V_SUPPLY | VPWR_SEL,VPWR,V_SUPPLY | - |  |
| 24 | 3.3/3.7 drive-strength | info | fitted capacity -> tighten I_lim upper bound to 8.25e-05 A | VDD_1V2 | - | apply as a bound in the manifest, not an overwrite; refit within [lo, capacity] |
| 25 | 3.5/3.9 vi-consistency | info | VDD_1V2 Zout extracted | VDD_1V2 | - |  |
| 26 | 3.8 dummy-load-detect | info | SREF_ADD_LDO1V2_LOAD_MPOS classified internal load (+25.7 uA on assertion) | SREF_ADD_LDO1V2_LOAD_MPOS | - | accept taxonomy enrichment: SREF_ADD_LDO1V2_LOAD_MPOS -> internal_load (25.7 uA) |

## Current-probe coverage by role

| role | with_current / total |
|---|---|
| bias | 4/4 |
| control | 6/6 |
| enable | 1/1 |
| ground | 2/3 |
| input_supply | 5/5 |
| load_control | 1/1 |
| output_rail | 3/3 |
| select | 2/2 |
| sense | 3/5 |
