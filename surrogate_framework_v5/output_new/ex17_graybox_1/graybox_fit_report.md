# Gray-Box Analog-Template Fitting (item 6)

**Rf1/Rf2 identification: Tier 1** — Rf1=2.21e-06 Ohm, Rf2=26.99 Ohm (63111/896342 samples)

## Assumptions actually used

- **A1_feedback_node_no_bias_current**: The feedback divider branch current equals the full v_out/(Rf1+Rf2) divider current — i.e. the error amplifier input draws negligible bias current at that node. Used whenever ANY tier of Rf1/Rf2 identification ran (always the case if VFB_I resolved).
- **tier2_closed_loop_v_fb_eq_v_ref**: not used (Tier 1 ran, or no gray-box fit at all)
- **tier3_nominal_rf2_vref**: not used (VFB_I resolved)
- **iload_assumed_zero**: not used (--iload_current_signal given)

## Per-corner fitted parameters

| corner | dc_rms | transient_rms | frozen | spec pass |
|---|---|---|---|---|
| TC_002_LDO_LoadLine_Transients_VPWR_FUNDC_HPM@proc_nn_temp_125_vsup_maxproc_5.5 | 0.678 | 0.5 | ['C_ea', 'Cgd', 'I_q', 'hp_gm_scale', 'hp_ilim_scale', 'lambda_p', 'lp_iq_scale'] | 3/6 |
| TC_002_LDO_LoadLine_Transients_VPWR_FUNDC_HPM@proc_ss_temp_n40_vsup_maxproc_4.5 | 0.781 | 0.546 | ['C_ea', 'Cgd', 'Cgs', 'I_ea_max', 'I_q', 'hp_gm_scale', 'hp_ilim_scale', 'lp_iq_scale'] | 3/6 |
| TC_002_LDO_LoadLine_Transients_VPWR_FUNDC_HPM@proc_ss_temp_27_vsup_maxproc_4.5 | 0.682 | 1.26 | ['I_q', 'Rz', 'hp_gm_scale', 'hp_ilim_scale', 'lp_iq_scale'] | 3/6 |
| TC_002_LDO_LoadLine_Transients_VPWR_FUNDC_HPM@proc_ss_temp_125_vsup_maxproc_4.5 | 0.699 | 0.515 | ['C_ea', 'Cgd', 'Gm_ea', 'I_q', 'hp_gm_scale', 'hp_ilim_scale', 'lambda_p', 'lp_iq_scale'] | 3/6 |
| TC_002_LDO_LoadLine_Transients_VPWR_FUNDC_HPM@proc_ss_temp_n40_vsup_maxproc_5 | 0.775 | 0.416 | ['C_ea', 'Cgd', 'Cgs', 'I_q', 'R_ea', 'hp_gm_scale', 'hp_ilim_scale', 'lambda_p', 'lp_iq_scale'] | 3/6 |
| TC_002_LDO_LoadLine_Transients_VPWR_FUNDC_HPM@proc_ss_temp_27_vsup_maxproc_5 | 0.676 | 1.92 | ['I_q', 'hp_gm_scale', 'hp_ilim_scale', 'lp_iq_scale'] | 3/6 |
| TC_002_LDO_LoadLine_Transients_VPWR_FUNDC_HPM@proc_ss_temp_125_vsup_maxproc_5 | 0.695 | 0.515 | ['C_ea', 'Cc', 'Cgd', 'I_q', 'hp_gm_scale', 'hp_ilim_scale', 'lp_iq_scale'] | 3/6 |
| TC_002_LDO_LoadLine_Transients_VPWR_FUNDC_HPM@proc_ss_temp_n40_vsup_maxproc_5.5 | 0.765 | 0.418 | ['C_ea', 'Cc', 'Cgd', 'I_q', 'hp_gm_scale', 'hp_ilim_scale', 'lambda_p', 'lp_iq_scale'] | 3/6 |
| TC_002_LDO_LoadLine_Transients_VPWR_FUNDC_HPM@proc_ss_temp_27_vsup_maxproc_5.5 | 0.673 | 2.66 | ['I_q', 'hp_gm_scale', 'hp_ilim_scale', 'lp_iq_scale'] | 3/6 |
| TC_002_LDO_LoadLine_Transients_VPWR_FUNDC_HPM@proc_ss_temp_125_vsup_maxproc_5.5 | 0.698 | 0.519 | ['C_ea', 'Cgd', 'I_q', 'hp_gm_scale', 'hp_ilim_scale', 'lambda_p', 'lp_iq_scale'] | 3/6 |
| TC_002_LDO_LoadLine_Transients_VPWR_FUNDC_HPM@proc_ww_temp_n40_vsup_maxproc_4.5 | 0.569 | 0.496 | ['C_ea', 'Cgd', 'Gm_ea', 'I_q', 'Rz', 'hp_gm_scale', 'hp_ilim_scale', 'lambda_p', 'lp_iq_scale'] | 3/6 |
| TC_002_LDO_LoadLine_Transients_VPWR_FUNDC_HPM@proc_ww_temp_27_vsup_maxproc_4.5 | 0.528 | 0.651 | ['C_ea', 'Cgd', 'Cgs', 'Gm_ea', 'I_ea_max', 'I_q', 'Rz', 'hp_gm_scale', 'hp_ilim_scale', 'lp_iq_scale'] | 3/6 |
| TC_002_LDO_LoadLine_Transients_VPWR_FUNDC_HPM@proc_ww_temp_125_vsup_maxproc_4.5 | 0.661 | 0.519 | ['C_ea', 'Cgd', 'I_q', 'hp_gm_scale', 'hp_ilim_scale', 'lambda_p', 'lp_iq_scale'] | 3/6 |
| TC_002_LDO_LoadLine_Transients_VPWR_FUNDC_HPM@proc_ww_temp_n40_vsup_maxproc_5 | 0.569 | 0.51 | ['Cgd', 'I_q', 'hp_gm_scale', 'hp_ilim_scale', 'lambda_p', 'lp_iq_scale'] | 3/6 |
| TC_002_LDO_LoadLine_Transients_VPWR_FUNDC_HPM@proc_ww_temp_27_vsup_maxproc_5 | 0.53 | 0.759 | ['C_ea', 'Cgd', 'I_q', 'Rz', 'hp_gm_scale', 'hp_ilim_scale', 'lambda_p', 'lp_iq_scale'] | 3/6 |
| TC_002_LDO_LoadLine_Transients_VPWR_FUNDC_HPM@proc_ww_temp_125_vsup_maxproc_5 | 0.662 | 0.506 | ['C_ea', 'Gm_ea', 'I_q', 'hp_gm_scale', 'hp_ilim_scale', 'lambda_p', 'lp_iq_scale'] | 3/6 |
| TC_002_LDO_LoadLine_Transients_VPWR_FUNDC_HPM@proc_ww_temp_n40_vsup_maxproc_5.5 | 0.568 | 0.53 | ['Cgd', 'I_q', 'hp_gm_scale', 'hp_ilim_scale', 'lp_iq_scale'] | 3/6 |
| TC_002_LDO_LoadLine_Transients_VPWR_FUNDC_HPM@proc_ww_temp_27_vsup_maxproc_5.5 | 0.528 | 1.08 | ['C_ea', 'Cgd', 'I_ea_max', 'I_q', 'R_ea', 'hp_gm_scale', 'hp_ilim_scale', 'lambda_p', 'lp_iq_scale'] | 3/6 |
| TC_002_LDO_LoadLine_Transients_VPWR_FUNDC_HPM@proc_ww_temp_125_vsup_maxproc_5.5 | 0.664 | 0.508 | ['Cgd', 'I_q', 'Rz', 'hp_gm_scale', 'hp_ilim_scale', 'lp_iq_scale'] | 3/6 |
| TC_002_LDO_LoadLine_Transients_VPWR_FUNDC_HPM@proc_nn_temp_n40_vsup_maxproc_4.5 | 0.309 | 0.148 | ['I_q', 'hp_gm_scale', 'hp_ilim_scale', 'lp_iq_scale'] | 3/6 |
| TC_002_LDO_LoadLine_Transients_VPWR_FUNDC_HPM@proc_nn_temp_27_vsup_maxproc_4.5 | 0.598 | 2.52 | ['I_q', 'hp_gm_scale', 'hp_ilim_scale', 'lp_iq_scale'] | 3/6 |
| TC_002_LDO_LoadLine_Transients_VPWR_FUNDC_HPM@proc_nn_temp_125_vsup_maxproc_4.5 | 0.679 | 0.509 | ['C_ea', 'Cgd', 'I_q', 'hp_gm_scale', 'hp_ilim_scale', 'lp_iq_scale'] | 3/6 |
| TC_002_LDO_LoadLine_Transients_VPWR_FUNDC_HPM@proc_nn_temp_n40_vsup_maxproc_5 | 0.279 | 0.146 | ['I_q', 'hp_gm_scale', 'hp_ilim_scale', 'lp_iq_scale'] | 3/6 |
| TC_002_LDO_LoadLine_Transients_VPWR_FUNDC_HPM@proc_nn_temp_27_vsup_maxproc_5 | 0.594 | 0.56 | ['C_ea', 'Cgd', 'I_q', 'Rz', 'hp_gm_scale', 'hp_ilim_scale', 'lp_iq_scale'] | 3/5 |
| TC_002_LDO_LoadLine_Transients_VPWR_FUNDC_HPM@proc_nn_temp_125_vsup_maxproc_5 | 0.679 | 0.509 | ['C_ea', 'Gm_ea', 'I_q', 'hp_gm_scale', 'hp_ilim_scale', 'lp_iq_scale'] | 3/6 |
| TC_002_LDO_LoadLine_Transients_VPWR_FUNDC_HPM@proc_nn_temp_n40_vsup_maxproc_5.5 | 0.347 | 0.221 | ['I_q', 'hp_gm_scale', 'hp_ilim_scale', 'lp_iq_scale'] | 2/5 |
| TC_002_LDO_LoadLine_Transients_VPWR_FUNDC_HPM@proc_nn_temp_27_vsup_maxproc_5.5 | 0.593 | 0.563 | ['C_ea', 'Cgd', 'Cgs', 'I_q', 'hp_gm_scale', 'hp_ilim_scale', 'lp_iq_scale'] | 3/6 |

### TC_002_LDO_LoadLine_Transients_VPWR_FUNDC_HPM@proc_nn_temp_125_vsup_maxproc_5.5 — fitted component values

| parameter | value |
|---|---|
| C_ea | 2e-12 |
| C_out | 4.7e-06 |
| Cc | 3e-11 |
| Cgd | 1e-11 |
| Cgs | 2e-11 |
| Gm_ea | 0.001 |
| I_ea_max | 3.76293e-06 |
| I_lim | 0.0502135 |
| I_q | 2e-05 |
| Kp | 0.01 |
| R_ea | 2e+06 |
| R_esr | 0.3 |
| Rf1 | 2.20984e-06 |
| Rf2 | 26.9914 |
| Rz | 100000 |
| V_ref | 0.9 |
| V_uvlo_f | 3.4 |
| V_uvlo_r | 3.6 |
| Vth_p | 1 |
| hp_gm_scale | 3 |
| hp_ilim_scale | 2 |
| k_load | 0.001 |
| lambda_p | 0.03 |
| lp_iq_scale | 0.25 |

### TC_002_LDO_LoadLine_Transients_VPWR_FUNDC_HPM@proc_ss_temp_n40_vsup_maxproc_4.5 — fitted component values

| parameter | value |
|---|---|
| C_ea | 2e-12 |
| C_out | 4.7e-06 |
| Cc | 3e-11 |
| Cgd | 1e-11 |
| Cgs | 2e-11 |
| Gm_ea | 0.001 |
| I_ea_max | 0.0001 |
| I_lim | 0.0501672 |
| I_q | 2e-05 |
| Kp | 0.01 |
| R_ea | 2e+06 |
| R_esr | 0.3 |
| Rf1 | 2.20984e-06 |
| Rf2 | 26.9914 |
| Rz | 100000 |
| V_ref | 0.9 |
| V_uvlo_f | 3.4 |
| V_uvlo_r | 3.6 |
| Vth_p | 0.999999 |
| hp_gm_scale | 3 |
| hp_ilim_scale | 2 |
| k_load | 0.000999963 |
| lambda_p | 0.00100071 |
| lp_iq_scale | 0.25 |

### TC_002_LDO_LoadLine_Transients_VPWR_FUNDC_HPM@proc_ss_temp_27_vsup_maxproc_4.5 — fitted component values

| parameter | value |
|---|---|
| C_ea | 2e-12 |
| C_out | 4.7e-06 |
| Cc | 3e-11 |
| Cgd | 1e-11 |
| Cgs | 2e-11 |
| Gm_ea | 0.001 |
| I_ea_max | 9.79652e-05 |
| I_lim | 0.0500717 |
| I_q | 2e-05 |
| Kp | 0.01 |
| R_ea | 2e+06 |
| R_esr | 0.3 |
| Rf1 | 2.20984e-06 |
| Rf2 | 26.9914 |
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

### TC_002_LDO_LoadLine_Transients_VPWR_FUNDC_HPM@proc_ss_temp_125_vsup_maxproc_4.5 — fitted component values

| parameter | value |
|---|---|
| C_ea | 2e-12 |
| C_out | 4.7e-06 |
| Cc | 3e-11 |
| Cgd | 1e-11 |
| Cgs | 2e-11 |
| Gm_ea | 0.001 |
| I_ea_max | 1.78332e-06 |
| I_lim | 0.0505915 |
| I_q | 2e-05 |
| Kp | 0.01 |
| R_ea | 2e+06 |
| R_esr | 0.3 |
| Rf1 | 2.20984e-06 |
| Rf2 | 26.9914 |
| Rz | 100000 |
| V_ref | 0.9 |
| V_uvlo_f | 3.4 |
| V_uvlo_r | 3.6 |
| Vth_p | 1 |
| hp_gm_scale | 3 |
| hp_ilim_scale | 2 |
| k_load | 0.000999963 |
| lambda_p | 0.03 |
| lp_iq_scale | 0.25 |

### TC_002_LDO_LoadLine_Transients_VPWR_FUNDC_HPM@proc_ss_temp_n40_vsup_maxproc_5 — fitted component values

| parameter | value |
|---|---|
| C_ea | 2e-12 |
| C_out | 4.7e-06 |
| Cc | 3e-11 |
| Cgd | 1e-11 |
| Cgs | 2e-11 |
| Gm_ea | 0.001 |
| I_ea_max | 0.000204493 |
| I_lim | 0.0500216 |
| I_q | 2e-05 |
| Kp | 0.01 |
| R_ea | 2e+06 |
| R_esr | 0.3 |
| Rf1 | 2.20984e-06 |
| Rf2 | 26.9914 |
| Rz | 100000 |
| V_ref | 0.9 |
| V_uvlo_f | 3.4 |
| V_uvlo_r | 3.6 |
| Vth_p | 1 |
| hp_gm_scale | 3 |
| hp_ilim_scale | 2 |
| k_load | 0.001 |
| lambda_p | 0.03 |
| lp_iq_scale | 0.25 |

### TC_002_LDO_LoadLine_Transients_VPWR_FUNDC_HPM@proc_ss_temp_27_vsup_maxproc_5 — fitted component values

| parameter | value |
|---|---|
| C_ea | 2e-12 |
| C_out | 4.7e-06 |
| Cc | 3e-11 |
| Cgd | 1e-11 |
| Cgs | 2e-11 |
| Gm_ea | 0.001 |
| I_ea_max | 3.47633e-05 |
| I_lim | 0.0502939 |
| I_q | 2e-05 |
| Kp | 0.01 |
| R_ea | 2e+06 |
| R_esr | 0.3 |
| Rf1 | 2.20984e-06 |
| Rf2 | 26.9914 |
| Rz | 100000 |
| V_ref | 0.9 |
| V_uvlo_f | 3.4 |
| V_uvlo_r | 3.6 |
| Vth_p | 0.999997 |
| hp_gm_scale | 3 |
| hp_ilim_scale | 2 |
| k_load | 0.000999898 |
| lambda_p | 0.00100031 |
| lp_iq_scale | 0.25 |

### TC_002_LDO_LoadLine_Transients_VPWR_FUNDC_HPM@proc_ss_temp_125_vsup_maxproc_5 — fitted component values

| parameter | value |
|---|---|
| C_ea | 2e-12 |
| C_out | 4.7e-06 |
| Cc | 3e-11 |
| Cgd | 1e-11 |
| Cgs | 2e-11 |
| Gm_ea | 0.001 |
| I_ea_max | 2.18239e-06 |
| I_lim | 0.0500554 |
| I_q | 2e-05 |
| Kp | 0.01 |
| R_ea | 2e+06 |
| R_esr | 0.3 |
| Rf1 | 2.20984e-06 |
| Rf2 | 26.9914 |
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

### TC_002_LDO_LoadLine_Transients_VPWR_FUNDC_HPM@proc_ss_temp_n40_vsup_maxproc_5.5 — fitted component values

| parameter | value |
|---|---|
| C_ea | 2e-12 |
| C_out | 4.7e-06 |
| Cc | 3e-11 |
| Cgd | 1e-11 |
| Cgs | 2e-11 |
| Gm_ea | 0.001 |
| I_ea_max | 0.000247267 |
| I_lim | 0.0500156 |
| I_q | 2e-05 |
| Kp | 0.01 |
| R_ea | 2e+06 |
| R_esr | 0.3 |
| Rf1 | 2.20984e-06 |
| Rf2 | 26.9914 |
| Rz | 100000 |
| V_ref | 0.9 |
| V_uvlo_f | 3.4 |
| V_uvlo_r | 3.6 |
| Vth_p | 0.999999 |
| hp_gm_scale | 3 |
| hp_ilim_scale | 2 |
| k_load | 0.000999927 |
| lambda_p | 0.03 |
| lp_iq_scale | 0.25 |

### TC_002_LDO_LoadLine_Transients_VPWR_FUNDC_HPM@proc_ss_temp_27_vsup_maxproc_5.5 — fitted component values

| parameter | value |
|---|---|
| C_ea | 2e-12 |
| C_out | 4.7e-06 |
| Cc | 3e-11 |
| Cgd | 1e-11 |
| Cgs | 2e-11 |
| Gm_ea | 0.001 |
| I_ea_max | 0.000197327 |
| I_lim | 0.0501699 |
| I_q | 2e-05 |
| Kp | 0.01 |
| R_ea | 2e+06 |
| R_esr | 0.3 |
| Rf1 | 2.20984e-06 |
| Rf2 | 26.9914 |
| Rz | 100000 |
| V_ref | 0.9 |
| V_uvlo_f | 3.4 |
| V_uvlo_r | 3.6 |
| Vth_p | 0.999998 |
| hp_gm_scale | 3 |
| hp_ilim_scale | 2 |
| k_load | 0.000999897 |
| lambda_p | 0.00100046 |
| lp_iq_scale | 0.25 |

### TC_002_LDO_LoadLine_Transients_VPWR_FUNDC_HPM@proc_ss_temp_125_vsup_maxproc_5.5 — fitted component values

| parameter | value |
|---|---|
| C_ea | 2e-12 |
| C_out | 4.7e-06 |
| Cc | 3e-11 |
| Cgd | 1e-11 |
| Cgs | 2e-11 |
| Gm_ea | 0.001 |
| I_ea_max | 3.35102e-06 |
| I_lim | 0.0504169 |
| I_q | 2e-05 |
| Kp | 0.01 |
| R_ea | 2e+06 |
| R_esr | 0.3 |
| Rf1 | 2.20984e-06 |
| Rf2 | 26.9914 |
| Rz | 100000 |
| V_ref | 0.9 |
| V_uvlo_f | 3.4 |
| V_uvlo_r | 3.6 |
| Vth_p | 0.999995 |
| hp_gm_scale | 3 |
| hp_ilim_scale | 2 |
| k_load | 0.000999936 |
| lambda_p | 0.03 |
| lp_iq_scale | 0.25 |

### TC_002_LDO_LoadLine_Transients_VPWR_FUNDC_HPM@proc_ww_temp_n40_vsup_maxproc_4.5 — fitted component values

| parameter | value |
|---|---|
| C_ea | 2e-12 |
| C_out | 4.7e-06 |
| Cc | 3e-11 |
| Cgd | 1e-11 |
| Cgs | 2e-11 |
| Gm_ea | 0.001 |
| I_ea_max | 0.000817045 |
| I_lim | 0.0500001 |
| I_q | 2e-05 |
| Kp | 0.01 |
| R_ea | 2e+06 |
| R_esr | 0.3 |
| Rf1 | 2.20984e-06 |
| Rf2 | 26.9914 |
| Rz | 100000 |
| V_ref | 0.9 |
| V_uvlo_f | 3.4 |
| V_uvlo_r | 3.6 |
| Vth_p | 0.999998 |
| hp_gm_scale | 3 |
| hp_ilim_scale | 2 |
| k_load | 0.000999875 |
| lambda_p | 0.03 |
| lp_iq_scale | 0.25 |

### TC_002_LDO_LoadLine_Transients_VPWR_FUNDC_HPM@proc_ww_temp_27_vsup_maxproc_4.5 — fitted component values

| parameter | value |
|---|---|
| C_ea | 2e-12 |
| C_out | 4.7e-06 |
| Cc | 3e-11 |
| Cgd | 1e-11 |
| Cgs | 2e-11 |
| Gm_ea | 0.001 |
| I_ea_max | 0.0001 |
| I_lim | 0.0503962 |
| I_q | 2e-05 |
| Kp | 0.01 |
| R_ea | 2e+06 |
| R_esr | 0.3 |
| Rf1 | 2.20984e-06 |
| Rf2 | 26.9914 |
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

### TC_002_LDO_LoadLine_Transients_VPWR_FUNDC_HPM@proc_ww_temp_125_vsup_maxproc_4.5 — fitted component values

| parameter | value |
|---|---|
| C_ea | 2e-12 |
| C_out | 4.7e-06 |
| Cc | 3e-11 |
| Cgd | 1e-11 |
| Cgs | 2e-11 |
| Gm_ea | 0.001 |
| I_ea_max | 1.85599e-06 |
| I_lim | 0.0511887 |
| I_q | 2e-05 |
| Kp | 0.01 |
| R_ea | 2e+06 |
| R_esr | 0.3 |
| Rf1 | 2.20984e-06 |
| Rf2 | 26.9914 |
| Rz | 100000 |
| V_ref | 0.9 |
| V_uvlo_f | 3.4 |
| V_uvlo_r | 3.6 |
| Vth_p | 0.999998 |
| hp_gm_scale | 3 |
| hp_ilim_scale | 2 |
| k_load | 0.000999975 |
| lambda_p | 0.03 |
| lp_iq_scale | 0.25 |

### TC_002_LDO_LoadLine_Transients_VPWR_FUNDC_HPM@proc_ww_temp_n40_vsup_maxproc_5 — fitted component values

| parameter | value |
|---|---|
| C_ea | 2e-12 |
| C_out | 4.7e-06 |
| Cc | 3e-11 |
| Cgd | 1e-11 |
| Cgs | 2e-11 |
| Gm_ea | 0.001 |
| I_ea_max | 0.000106761 |
| I_lim | 0.0508118 |
| I_q | 2e-05 |
| Kp | 0.01 |
| R_ea | 2e+06 |
| R_esr | 0.3 |
| Rf1 | 2.20984e-06 |
| Rf2 | 26.9914 |
| Rz | 100000 |
| V_ref | 0.9 |
| V_uvlo_f | 3.4 |
| V_uvlo_r | 3.6 |
| Vth_p | 0.999997 |
| hp_gm_scale | 3 |
| hp_ilim_scale | 2 |
| k_load | 0.000999869 |
| lambda_p | 0.03 |
| lp_iq_scale | 0.25 |

### TC_002_LDO_LoadLine_Transients_VPWR_FUNDC_HPM@proc_ww_temp_27_vsup_maxproc_5 — fitted component values

| parameter | value |
|---|---|
| C_ea | 2e-12 |
| C_out | 4.7e-06 |
| Cc | 3e-11 |
| Cgd | 1e-11 |
| Cgs | 2e-11 |
| Gm_ea | 0.001 |
| I_ea_max | 0.000148082 |
| I_lim | 0.0502108 |
| I_q | 2e-05 |
| Kp | 0.01 |
| R_ea | 2e+06 |
| R_esr | 0.3 |
| Rf1 | 2.20984e-06 |
| Rf2 | 26.9914 |
| Rz | 100000 |
| V_ref | 0.9 |
| V_uvlo_f | 3.4 |
| V_uvlo_r | 3.6 |
| Vth_p | 1 |
| hp_gm_scale | 3 |
| hp_ilim_scale | 2 |
| k_load | 0.001 |
| lambda_p | 0.03 |
| lp_iq_scale | 0.25 |

### TC_002_LDO_LoadLine_Transients_VPWR_FUNDC_HPM@proc_ww_temp_125_vsup_maxproc_5 — fitted component values

| parameter | value |
|---|---|
| C_ea | 2e-12 |
| C_out | 4.7e-06 |
| Cc | 3e-11 |
| Cgd | 1e-11 |
| Cgs | 2e-11 |
| Gm_ea | 0.001 |
| I_ea_max | 2.60986e-06 |
| I_lim | 0.0501426 |
| I_q | 2e-05 |
| Kp | 0.01 |
| R_ea | 2e+06 |
| R_esr | 0.3 |
| Rf1 | 2.20984e-06 |
| Rf2 | 26.9914 |
| Rz | 100000 |
| V_ref | 0.9 |
| V_uvlo_f | 3.4 |
| V_uvlo_r | 3.6 |
| Vth_p | 1 |
| hp_gm_scale | 3 |
| hp_ilim_scale | 2 |
| k_load | 0.000999998 |
| lambda_p | 0.03 |
| lp_iq_scale | 0.25 |

### TC_002_LDO_LoadLine_Transients_VPWR_FUNDC_HPM@proc_ww_temp_n40_vsup_maxproc_5.5 — fitted component values

| parameter | value |
|---|---|
| C_ea | 2e-12 |
| C_out | 4.7e-06 |
| Cc | 3e-11 |
| Cgd | 1e-11 |
| Cgs | 2e-11 |
| Gm_ea | 0.001 |
| I_ea_max | 0.000443294 |
| I_lim | 0.0500248 |
| I_q | 2e-05 |
| Kp | 0.01 |
| R_ea | 2e+06 |
| R_esr | 0.3 |
| Rf1 | 2.20984e-06 |
| Rf2 | 26.9914 |
| Rz | 100000 |
| V_ref | 0.9 |
| V_uvlo_f | 3.4 |
| V_uvlo_r | 3.6 |
| Vth_p | 1 |
| hp_gm_scale | 3 |
| hp_ilim_scale | 2 |
| k_load | 0.000999997 |
| lambda_p | 0.001 |
| lp_iq_scale | 0.25 |

### TC_002_LDO_LoadLine_Transients_VPWR_FUNDC_HPM@proc_ww_temp_27_vsup_maxproc_5.5 — fitted component values

| parameter | value |
|---|---|
| C_ea | 2e-12 |
| C_out | 4.7e-06 |
| Cc | 3e-11 |
| Cgd | 1e-11 |
| Cgs | 2e-11 |
| Gm_ea | 0.001 |
| I_ea_max | 0.0001 |
| I_lim | 0.050221 |
| I_q | 2e-05 |
| Kp | 0.01 |
| R_ea | 2e+06 |
| R_esr | 0.3 |
| Rf1 | 2.20984e-06 |
| Rf2 | 26.9914 |
| Rz | 100000 |
| V_ref | 0.9 |
| V_uvlo_f | 3.4 |
| V_uvlo_r | 3.6 |
| Vth_p | 0.999996 |
| hp_gm_scale | 3 |
| hp_ilim_scale | 2 |
| k_load | 0.000999996 |
| lambda_p | 0.03 |
| lp_iq_scale | 0.25 |

### TC_002_LDO_LoadLine_Transients_VPWR_FUNDC_HPM@proc_ww_temp_125_vsup_maxproc_5.5 — fitted component values

| parameter | value |
|---|---|
| C_ea | 2e-12 |
| C_out | 4.7e-06 |
| Cc | 3e-11 |
| Cgd | 1e-11 |
| Cgs | 2e-11 |
| Gm_ea | 0.001 |
| I_ea_max | 2.48838e-06 |
| I_lim | 0.0523322 |
| I_q | 2e-05 |
| Kp | 0.01 |
| R_ea | 2e+06 |
| R_esr | 0.3 |
| Rf1 | 2.20984e-06 |
| Rf2 | 26.9914 |
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

### TC_002_LDO_LoadLine_Transients_VPWR_FUNDC_HPM@proc_nn_temp_n40_vsup_maxproc_4.5 — fitted component values

| parameter | value |
|---|---|
| C_ea | 2e-12 |
| C_out | 4.7e-06 |
| Cc | 3e-11 |
| Cgd | 1e-11 |
| Cgs | 2e-11 |
| Gm_ea | 0.001 |
| I_ea_max | 0.000447876 |
| I_lim | 0.0500402 |
| I_q | 2e-05 |
| Kp | 0.01 |
| R_ea | 2e+06 |
| R_esr | 0.3 |
| Rf1 | 2.20984e-06 |
| Rf2 | 26.9914 |
| Rz | 100000 |
| V_ref | 0.9 |
| V_uvlo_f | 3.4 |
| V_uvlo_r | 3.6 |
| Vth_p | 0.99999 |
| hp_gm_scale | 3 |
| hp_ilim_scale | 2 |
| k_load | 0.001 |
| lambda_p | 0.00100481 |
| lp_iq_scale | 0.25 |

### TC_002_LDO_LoadLine_Transients_VPWR_FUNDC_HPM@proc_nn_temp_27_vsup_maxproc_4.5 — fitted component values

| parameter | value |
|---|---|
| C_ea | 2e-12 |
| C_out | 4.7e-06 |
| Cc | 3e-11 |
| Cgd | 1e-11 |
| Cgs | 2e-11 |
| Gm_ea | 0.001 |
| I_ea_max | 1.85188e-06 |
| I_lim | 0.0502687 |
| I_q | 2e-05 |
| Kp | 0.01 |
| R_ea | 2e+06 |
| R_esr | 0.3 |
| Rf1 | 2.20984e-06 |
| Rf2 | 26.9914 |
| Rz | 100000 |
| V_ref | 0.9 |
| V_uvlo_f | 3.4 |
| V_uvlo_r | 3.6 |
| Vth_p | 0.999997 |
| hp_gm_scale | 3 |
| hp_ilim_scale | 2 |
| k_load | 0.000999976 |
| lambda_p | 0.001 |
| lp_iq_scale | 0.25 |

### TC_002_LDO_LoadLine_Transients_VPWR_FUNDC_HPM@proc_nn_temp_125_vsup_maxproc_4.5 — fitted component values

| parameter | value |
|---|---|
| C_ea | 2e-12 |
| C_out | 4.7e-06 |
| Cc | 3e-11 |
| Cgd | 1e-11 |
| Cgs | 2e-11 |
| Gm_ea | 0.001 |
| I_ea_max | 1.84073e-06 |
| I_lim | 0.0507631 |
| I_q | 2e-05 |
| Kp | 0.01 |
| R_ea | 2e+06 |
| R_esr | 0.3 |
| Rf1 | 2.20984e-06 |
| Rf2 | 26.9914 |
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

### TC_002_LDO_LoadLine_Transients_VPWR_FUNDC_HPM@proc_nn_temp_n40_vsup_maxproc_5 — fitted component values

| parameter | value |
|---|---|
| C_ea | 2e-12 |
| C_out | 4.7e-06 |
| Cc | 3e-11 |
| Cgd | 1e-11 |
| Cgs | 2e-11 |
| Gm_ea | 0.001 |
| I_ea_max | 8.70285e-07 |
| I_lim | 0.0512366 |
| I_q | 2e-05 |
| Kp | 0.01 |
| R_ea | 2e+06 |
| R_esr | 0.3 |
| Rf1 | 2.20984e-06 |
| Rf2 | 26.9914 |
| Rz | 100000 |
| V_ref | 0.9 |
| V_uvlo_f | 3.4 |
| V_uvlo_r | 3.6 |
| Vth_p | 0.680527 |
| hp_gm_scale | 3 |
| hp_ilim_scale | 2 |
| k_load | 0.001 |
| lambda_p | 0.001 |
| lp_iq_scale | 0.25 |

### TC_002_LDO_LoadLine_Transients_VPWR_FUNDC_HPM@proc_nn_temp_27_vsup_maxproc_5 — fitted component values

| parameter | value |
|---|---|
| C_ea | 2e-12 |
| C_out | 4.7e-06 |
| Cc | 3e-11 |
| Cgd | 1e-11 |
| Cgs | 2e-11 |
| Gm_ea | 0.001 |
| I_ea_max | 3.31935e-06 |
| I_lim | 0.0568066 |
| I_q | 2e-05 |
| Kp | 0.01 |
| R_ea | 2e+06 |
| R_esr | 0.3 |
| Rf1 | 2.20984e-06 |
| Rf2 | 26.9914 |
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

### TC_002_LDO_LoadLine_Transients_VPWR_FUNDC_HPM@proc_nn_temp_125_vsup_maxproc_5 — fitted component values

| parameter | value |
|---|---|
| C_ea | 2e-12 |
| C_out | 4.7e-06 |
| Cc | 3e-11 |
| Cgd | 1e-11 |
| Cgs | 2e-11 |
| Gm_ea | 0.001 |
| I_ea_max | 2.95931e-06 |
| I_lim | 0.0501966 |
| I_q | 2e-05 |
| Kp | 0.01 |
| R_ea | 2e+06 |
| R_esr | 0.3 |
| Rf1 | 2.20984e-06 |
| Rf2 | 26.9914 |
| Rz | 100000 |
| V_ref | 0.9 |
| V_uvlo_f | 3.4 |
| V_uvlo_r | 3.6 |
| Vth_p | 0.999995 |
| hp_gm_scale | 3 |
| hp_ilim_scale | 2 |
| k_load | 0.000999976 |
| lambda_p | 0.00100025 |
| lp_iq_scale | 0.25 |

### TC_002_LDO_LoadLine_Transients_VPWR_FUNDC_HPM@proc_nn_temp_n40_vsup_maxproc_5.5 — fitted component values

| parameter | value |
|---|---|
| C_ea | 2e-12 |
| C_out | 4.7e-06 |
| Cc | 3e-11 |
| Cgd | 1e-11 |
| Cgs | 2e-11 |
| Gm_ea | 0.001 |
| I_ea_max | 6.27993e-06 |
| I_lim | 0.0500485 |
| I_q | 2e-05 |
| Kp | 19.0095 |
| R_ea | 2e+06 |
| R_esr | 0.3 |
| Rf1 | 2.20984e-06 |
| Rf2 | 26.9914 |
| Rz | 100000 |
| V_ref | 0.9 |
| V_uvlo_f | 3.4 |
| V_uvlo_r | 3.6 |
| Vth_p | 0.3 |
| hp_gm_scale | 3 |
| hp_ilim_scale | 2 |
| k_load | 1e-09 |
| lambda_p | 0.469069 |
| lp_iq_scale | 0.25 |

### TC_002_LDO_LoadLine_Transients_VPWR_FUNDC_HPM@proc_nn_temp_27_vsup_maxproc_5.5 — fitted component values

| parameter | value |
|---|---|
| C_ea | 2e-12 |
| C_out | 4.7e-06 |
| Cc | 3e-11 |
| Cgd | 1e-11 |
| Cgs | 2e-11 |
| Gm_ea | 0.001 |
| I_ea_max | 3.69933e-06 |
| I_lim | 0.0500087 |
| I_q | 2e-05 |
| Kp | 0.01 |
| R_ea | 2e+06 |
| R_esr | 0.3 |
| Rf1 | 2.20984e-06 |
| Rf2 | 26.9914 |
| Rz | 100000 |
| V_ref | 0.9 |
| V_uvlo_f | 3.4 |
| V_uvlo_r | 3.6 |
| Vth_p | 1 |
| hp_gm_scale | 3 |
| hp_ilim_scale | 2 |
| k_load | 0.000999966 |
| lambda_p | 0.001 |
| lp_iq_scale | 0.25 |
