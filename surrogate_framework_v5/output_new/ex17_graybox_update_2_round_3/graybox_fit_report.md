# Gray-Box Analog-Template Fitting (item 6 + round-3 fixes)

## Rf1/Rf2 identification, PER PROCESS (round-3 fix, item 1)

| process | tier | Rf1 (Ohm) | Rf2 (Ohm) | samples |
|---|---|---|---|---|
| nn | 1 | 0.1046 | 3.771e+05 | 11/120385 |
| ss | 1 | 1.091e-05 | 176.6 | 181/79220 |
| ww | 1 | 0.0002795 | 3765 | 8/14716 |

## Assumptions actually used

- **A1_feedback_node_no_bias_current**: The feedback divider branch current equals the full v_out/(Rf1+Rf2) divider current — i.e. the error amplifier input draws negligible bias current at that node. Used whenever ANY tier of Rf1/Rf2 identification ran (always the case if VFB_I resolved).
- **tier2_closed_loop_v_fb_eq_v_ref**: not used (every process either ran Tier 1 or had no gray-box fit at all)
- **tier3_nominal_rf2_vref**: not used (every process resolved VFB_I)
- **iload_assumed_zero**: not used (--iload_current_signal given)
- **enable_trace**: Derived from FSM state name (matched ['DISABLED', 'SHUTDOWN']) (round-2 fix, item 1) — never a mandatory literal EN_LDO pin mapping.
- **bypass_excluded**: no --bypass_state_names pattern matched any detected state — nothing excluded.
- **voltage_temperature_not_separate_lut_axes**: Runs of the SAME process but different vin/temp are POOLED into one fit, not split into separate LUT entries — the template already models vin continuously through its own ODEs/dc_solve (item 2).

## Per-process pooled fit (LUT entries)

| process | runs pooled | dc_rms | transient_rms | frozen | spec pass |
|---|---|---|---|---|---|
| nn | 8 | 2.62 | 43.3 | ['I_q', 'hp_gm_scale', 'hp_ilim_scale', 'lp_iq_scale'] | 3/5 |
| ss | 8 | 1.05 | 7 | ['C_ea', 'Cc', 'Cgd', 'Gm_ea', 'I_q', 'R_ea', 'Rz', 'hp_gm_scale', 'hp_ilim_scale', 'lp_iq_scale'] | 4/5 |
| ww | 8 | 1.63 | 22.4 | ['C_ea', 'Cc', 'Cgd', 'Gm_ea', 'I_q', 'Kp', 'R_ea', 'hp_gm_scale', 'hp_ilim_scale', 'lp_iq_scale'] | 4/6 |

### nn — fitted component values

| parameter | value |
|---|---|
| C_ea | 2e-12 |
| C_out | 4.7e-06 |
| Cc | 3e-11 |
| Cgd | 1e-11 |
| Cgs | 2e-11 |
| Gm_ea | 0.001 |
| I_ea_max | 0.000521163 |
| I_lim | 0.0850397 |
| I_q | 2e-05 |
| Kp | 0.01 |
| R_ea | 2e+06 |
| R_esr | 0.3 |
| Rf1 | 0.104612 |
| Rf2 | 377114 |
| Rz | 100000 |
| V_ref | 0.9 |
| V_uvlo_f | 3.4 |
| V_uvlo_r | 3.6 |
| Vth_p | 1 |
| hp_gm_scale | 3 |
| hp_ilim_scale | 2 |
| k_load | 0.001 |
| lambda_p | 0.001 |
| lp_iq_scale | 0.25 |

Analog core: `output_new/ex17_graybox_update_2_round_3/ldo_analog_core_nn.vams`

### ss — fitted component values

| parameter | value |
|---|---|
| C_ea | 2e-12 |
| C_out | 4.7e-06 |
| Cc | 3e-11 |
| Cgd | 1e-11 |
| Cgs | 2e-11 |
| Gm_ea | 0.001 |
| I_ea_max | 5.17092e-05 |
| I_lim | 1.42761 |
| I_q | 2e-05 |
| Kp | 0.01 |
| R_ea | 2e+06 |
| R_esr | 0.3 |
| Rf1 | 1.09075e-05 |
| Rf2 | 176.619 |
| Rz | 100000 |
| V_ref | 0.9 |
| V_uvlo_f | 3.4 |
| V_uvlo_r | 3.6 |
| Vth_p | 1 |
| hp_gm_scale | 3 |
| hp_ilim_scale | 2 |
| k_load | 0.001 |
| lambda_p | 0.001 |
| lp_iq_scale | 0.25 |

Analog core: `output_new/ex17_graybox_update_2_round_3/ldo_analog_core_ss.vams`

### ww — fitted component values

| parameter | value |
|---|---|
| C_ea | 2e-12 |
| C_out | 4.7e-06 |
| Cc | 3e-11 |
| Cgd | 1e-11 |
| Cgs | 2e-11 |
| Gm_ea | 0.001 |
| I_ea_max | 0.000345346 |
| I_lim | 0.861688 |
| I_q | 2e-05 |
| Kp | 2 |
| R_ea | 2e+06 |
| R_esr | 0.3 |
| Rf1 | 0.000279485 |
| Rf2 | 3764.61 |
| Rz | 100000 |
| V_ref | 0.9 |
| V_uvlo_f | 3.4 |
| V_uvlo_r | 3.6 |
| Vth_p | 1 |
| hp_gm_scale | 3 |
| hp_ilim_scale | 2 |
| k_load | 0.000999993 |
| lambda_p | 0.00100464 |
| lp_iq_scale | 0.25 |

Analog core: `output_new/ex17_graybox_update_2_round_3/ldo_analog_core_ww.vams`

LUT param store (core.pvt-compatible): `output_new/ex17_graybox_update_2_round_3/graybox_process_lut.blut`
