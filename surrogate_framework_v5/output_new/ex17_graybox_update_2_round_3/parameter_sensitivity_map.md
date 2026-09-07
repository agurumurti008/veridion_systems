# Parameter -> Behavior Sensitivity Map (item 4a)

Elasticity = (% change in behavior) / (% change in parameter), centered finite difference at +-1% around each process's FITTED parameter vector. |elasticity| >> 0 means that parameter dominates that behavior; ~0 means it barely matters for it (a real, computed result — not asserted).

## Process: nn

**dropout_margin** (base=0.6787): Kp=+2.52, V_ref=-1.39, I_lim=+0.882, k_load=-0.0601, lambda_p=+0.0103, Vth_p=+0.000771
**iq** (base=5e-06): I_q=+1, lp_iq_scale=+1
**phase_margin_deg** (base=63.57): R_esr=+0.438, C_out=+0.438, Cgs=-0.233, Cc=+0.214, C_ea=-0.0233, R_ea=-0.0221
**psrr_1kHz_dB** (base=65.3): Gm_ea=+0.133, R_ea=+0.114, Cc=-0.0188, C_ea=-0.00116, Rz=-0.000802, lambda_p=-0.000261
**vout_dc** (base=0.9003): V_ref=+1, Kp=+0.00095, Vth_p=-0.000555, I_lim=+0.000333, R_ea=-0.000322, Gm_ea=-0.000322
**zout_1kHz** (base=0.02724): Gm_ea=-1, I_lim=-0.943, R_ea=-0.699, Kp=-0.5, Cc=+0.181, Cgs=+0.114

## Process: ss

**dropout_margin** (base=0.7591): Kp=+2.2, V_ref=-1.42, Rf2=+0.2, k_load=-0.0354, lambda_p=+0.00898, I_lim=+0.00226
**iq** (base=5e-06): I_q=+1, lp_iq_scale=+1
**phase_margin_deg** (base=63.69): R_esr=+0.438, C_out=+0.435, Cgs=-0.233, Cc=+0.214, C_ea=-0.0233, R_ea=-0.022
**psrr_1kHz_dB** (base=65.3): Gm_ea=+0.133, R_ea=+0.114, Cc=-0.0188, C_ea=-0.00115, Rz=-0.000796, lambda_p=-0.000233
**vout_dc** (base=0.9003): V_ref=+1, Kp=+0.000928, Vth_p=-0.000555, R_ea=-0.000366, Gm_ea=-0.000366, Rf2=+8.45e-05
**zout_1kHz** (base=0.01793): Gm_ea=-1, R_ea=-0.699, Kp=-0.5, Cc=+0.181, Cgs=+0.114, V_ref=-0.0529

## Process: ww

**dropout_margin** (base=3.872): V_ref=-0.233, Kp=+0.0291, k_load=-0.000515, R_ea=+0.000488, Gm_ea=+0.000488, Rf2=+0.000137
**iq** (base=5e-06): I_q=+1, lp_iq_scale=+1
**phase_margin_deg** (base=87.88): R_esr=+0.0727, C_out=+0.0726, Rz=-0.046, Cgs=-0.0443, C_ea=-0.00443, R_ea=-0.00234
**psrr_1kHz_dB** (base=65.32): Gm_ea=+0.133, R_ea=+0.114, Cc=-0.0187, C_ea=-0.00114, Rz=-0.000796, Kp=+1.35e-05
**vout_dc** (base=0.9019): V_ref=+0.998, R_ea=-0.00209, Gm_ea=-0.00209, Vth_p=-0.000554, Kp=+6.26e-05, k_load=-1.11e-06
**zout_1kHz** (base=0.001328): Gm_ea=-1, R_ea=-0.699, Kp=-0.5, Cc=+0.181, Cgs=+0.114, C_ea=+0.0114

