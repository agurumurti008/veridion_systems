# Final FSM — Included/Excluded Corner Manifest

BLUT source: `blut_files/regression_multi_corner_sref_ldo.bin`  |  strategy: `hybrid`

Included: 126/135 corners  |  Excluded: 9/135 corners

Final validation: reachability=True, completeness=True, determinism=True, speckg_coverage=25.0%

Final states (14): DISABLED, REGULATION, REGULATION_2, REGULATION_3, REGULATION_4, REGULATION_5, DISABLED_2, REGULATION_6, REGULATION_7, REGULATION_8, REGULATION_9, REGULATION_10, REGULATION_11, REGULATION_12

Final transitions: 23

## Included corners

| run_id | corner_id |
|---|---|
| TC_001_LDO_VPWR_FUNDC_Load_HPM_AddLoad_Static | proc_nn_temp_125_vsup_maxproc_4.5 |
| TC_001_LDO_VPWR_FUNDC_Load_HPM_AddLoad_Static | proc_nn_temp_125_vsup_maxproc_5 |
| TC_001_LDO_VPWR_FUNDC_Load_HPM_AddLoad_Static | proc_nn_temp_125_vsup_maxproc_5.5 |
| TC_001_LDO_VPWR_FUNDC_Load_HPM_AddLoad_Static | proc_nn_temp_27_vsup_maxproc_4.5 |
| TC_001_LDO_VPWR_FUNDC_Load_HPM_AddLoad_Static | proc_nn_temp_27_vsup_maxproc_5 |
| TC_001_LDO_VPWR_FUNDC_Load_HPM_AddLoad_Static | proc_nn_temp_27_vsup_maxproc_5.5 |
| TC_001_LDO_VPWR_FUNDC_Load_HPM_AddLoad_Static | proc_nn_temp_n40_vsup_maxproc_4.5 |
| TC_001_LDO_VPWR_FUNDC_Load_HPM_AddLoad_Static | proc_nn_temp_n40_vsup_maxproc_5 |
| TC_001_LDO_VPWR_FUNDC_Load_HPM_AddLoad_Static | proc_nn_temp_n40_vsup_maxproc_5.5 |
| TC_001_LDO_VPWR_FUNDC_Load_HPM_AddLoad_Static | proc_ss_temp_125_vsup_maxproc_4.5 |
| TC_001_LDO_VPWR_FUNDC_Load_HPM_AddLoad_Static | proc_ss_temp_125_vsup_maxproc_5 |
| TC_001_LDO_VPWR_FUNDC_Load_HPM_AddLoad_Static | proc_ss_temp_125_vsup_maxproc_5.5 |
| TC_001_LDO_VPWR_FUNDC_Load_HPM_AddLoad_Static | proc_ss_temp_27_vsup_maxproc_4.5 |
| TC_001_LDO_VPWR_FUNDC_Load_HPM_AddLoad_Static | proc_ss_temp_27_vsup_maxproc_5 |
| TC_001_LDO_VPWR_FUNDC_Load_HPM_AddLoad_Static | proc_ss_temp_27_vsup_maxproc_5.5 |
| TC_001_LDO_VPWR_FUNDC_Load_HPM_AddLoad_Static | proc_ss_temp_n40_vsup_maxproc_4.5 |
| TC_001_LDO_VPWR_FUNDC_Load_HPM_AddLoad_Static | proc_ss_temp_n40_vsup_maxproc_5 |
| TC_001_LDO_VPWR_FUNDC_Load_HPM_AddLoad_Static | proc_ss_temp_n40_vsup_maxproc_5.5 |
| TC_001_LDO_VPWR_FUNDC_Load_HPM_AddLoad_Static | proc_ww_temp_125_vsup_maxproc_4.5 |
| TC_001_LDO_VPWR_FUNDC_Load_HPM_AddLoad_Static | proc_ww_temp_125_vsup_maxproc_5 |
| TC_001_LDO_VPWR_FUNDC_Load_HPM_AddLoad_Static | proc_ww_temp_125_vsup_maxproc_5.5 |
| TC_001_LDO_VPWR_FUNDC_Load_HPM_AddLoad_Static | proc_ww_temp_27_vsup_maxproc_4.5 |
| TC_001_LDO_VPWR_FUNDC_Load_HPM_AddLoad_Static | proc_ww_temp_27_vsup_maxproc_5 |
| TC_001_LDO_VPWR_FUNDC_Load_HPM_AddLoad_Static | proc_ww_temp_27_vsup_maxproc_5.5 |
| TC_001_LDO_VPWR_FUNDC_Load_HPM_AddLoad_Static | proc_ww_temp_n40_vsup_maxproc_4.5 |
| TC_001_LDO_VPWR_FUNDC_Load_HPM_AddLoad_Static | proc_ww_temp_n40_vsup_maxproc_5 |
| TC_001_LDO_VPWR_FUNDC_Load_HPM_AddLoad_Static | proc_ww_temp_n40_vsup_maxproc_5.5 |
| TC_002_LDO_LoadLine_Transients_VPWR_FUNDC_HPM | proc_nn_temp_125_vsup_maxproc_4.5 |
| TC_002_LDO_LoadLine_Transients_VPWR_FUNDC_HPM | proc_nn_temp_125_vsup_maxproc_5 |
| TC_002_LDO_LoadLine_Transients_VPWR_FUNDC_HPM | proc_nn_temp_125_vsup_maxproc_5.5 |
| TC_002_LDO_LoadLine_Transients_VPWR_FUNDC_HPM | proc_nn_temp_27_vsup_maxproc_4.5 |
| TC_002_LDO_LoadLine_Transients_VPWR_FUNDC_HPM | proc_nn_temp_27_vsup_maxproc_5 |
| TC_002_LDO_LoadLine_Transients_VPWR_FUNDC_HPM | proc_nn_temp_27_vsup_maxproc_5.5 |
| TC_002_LDO_LoadLine_Transients_VPWR_FUNDC_HPM | proc_nn_temp_n40_vsup_maxproc_4.5 |
| TC_002_LDO_LoadLine_Transients_VPWR_FUNDC_HPM | proc_nn_temp_n40_vsup_maxproc_5 |
| TC_002_LDO_LoadLine_Transients_VPWR_FUNDC_HPM | proc_nn_temp_n40_vsup_maxproc_5.5 |
| TC_002_LDO_LoadLine_Transients_VPWR_FUNDC_HPM | proc_ss_temp_125_vsup_maxproc_4.5 |
| TC_002_LDO_LoadLine_Transients_VPWR_FUNDC_HPM | proc_ss_temp_125_vsup_maxproc_5 |
| TC_002_LDO_LoadLine_Transients_VPWR_FUNDC_HPM | proc_ss_temp_125_vsup_maxproc_5.5 |
| TC_002_LDO_LoadLine_Transients_VPWR_FUNDC_HPM | proc_ss_temp_27_vsup_maxproc_4.5 |
| TC_002_LDO_LoadLine_Transients_VPWR_FUNDC_HPM | proc_ss_temp_27_vsup_maxproc_5 |
| TC_002_LDO_LoadLine_Transients_VPWR_FUNDC_HPM | proc_ss_temp_27_vsup_maxproc_5.5 |
| TC_002_LDO_LoadLine_Transients_VPWR_FUNDC_HPM | proc_ss_temp_n40_vsup_maxproc_4.5 |
| TC_002_LDO_LoadLine_Transients_VPWR_FUNDC_HPM | proc_ss_temp_n40_vsup_maxproc_5 |
| TC_002_LDO_LoadLine_Transients_VPWR_FUNDC_HPM | proc_ss_temp_n40_vsup_maxproc_5.5 |
| TC_002_LDO_LoadLine_Transients_VPWR_FUNDC_HPM | proc_ww_temp_125_vsup_maxproc_4.5 |
| TC_002_LDO_LoadLine_Transients_VPWR_FUNDC_HPM | proc_ww_temp_125_vsup_maxproc_5 |
| TC_002_LDO_LoadLine_Transients_VPWR_FUNDC_HPM | proc_ww_temp_125_vsup_maxproc_5.5 |
| TC_002_LDO_LoadLine_Transients_VPWR_FUNDC_HPM | proc_ww_temp_27_vsup_maxproc_4.5 |
| TC_002_LDO_LoadLine_Transients_VPWR_FUNDC_HPM | proc_ww_temp_27_vsup_maxproc_5 |
| TC_002_LDO_LoadLine_Transients_VPWR_FUNDC_HPM | proc_ww_temp_27_vsup_maxproc_5.5 |
| TC_002_LDO_LoadLine_Transients_VPWR_FUNDC_HPM | proc_ww_temp_n40_vsup_maxproc_4.5 |
| TC_002_LDO_LoadLine_Transients_VPWR_FUNDC_HPM | proc_ww_temp_n40_vsup_maxproc_5 |
| TC_002_LDO_LoadLine_Transients_VPWR_FUNDC_HPM | proc_ww_temp_n40_vsup_maxproc_5.5 |
| TC_003_LDO_Bypass_Entry_Exit_HPM_AddLoad_Priority | proc_nn_temp_125_vsup_maxproc_4.5 |
| TC_003_LDO_Bypass_Entry_Exit_HPM_AddLoad_Priority | proc_nn_temp_125_vsup_maxproc_5 |
| TC_003_LDO_Bypass_Entry_Exit_HPM_AddLoad_Priority | proc_nn_temp_125_vsup_maxproc_5.5 |
| TC_003_LDO_Bypass_Entry_Exit_HPM_AddLoad_Priority | proc_nn_temp_27_vsup_maxproc_4.5 |
| TC_003_LDO_Bypass_Entry_Exit_HPM_AddLoad_Priority | proc_nn_temp_27_vsup_maxproc_5 |
| TC_003_LDO_Bypass_Entry_Exit_HPM_AddLoad_Priority | proc_nn_temp_27_vsup_maxproc_5.5 |
| TC_003_LDO_Bypass_Entry_Exit_HPM_AddLoad_Priority | proc_nn_temp_n40_vsup_maxproc_4.5 |
| TC_003_LDO_Bypass_Entry_Exit_HPM_AddLoad_Priority | proc_nn_temp_n40_vsup_maxproc_5 |
| TC_003_LDO_Bypass_Entry_Exit_HPM_AddLoad_Priority | proc_nn_temp_n40_vsup_maxproc_5.5 |
| TC_003_LDO_Bypass_Entry_Exit_HPM_AddLoad_Priority | proc_ss_temp_125_vsup_maxproc_4.5 |
| TC_003_LDO_Bypass_Entry_Exit_HPM_AddLoad_Priority | proc_ss_temp_125_vsup_maxproc_5 |
| TC_003_LDO_Bypass_Entry_Exit_HPM_AddLoad_Priority | proc_ss_temp_125_vsup_maxproc_5.5 |
| TC_003_LDO_Bypass_Entry_Exit_HPM_AddLoad_Priority | proc_ss_temp_27_vsup_maxproc_4.5 |
| TC_003_LDO_Bypass_Entry_Exit_HPM_AddLoad_Priority | proc_ss_temp_27_vsup_maxproc_5 |
| TC_003_LDO_Bypass_Entry_Exit_HPM_AddLoad_Priority | proc_ss_temp_27_vsup_maxproc_5.5 |
| TC_003_LDO_Bypass_Entry_Exit_HPM_AddLoad_Priority | proc_ss_temp_n40_vsup_maxproc_4.5 |
| TC_003_LDO_Bypass_Entry_Exit_HPM_AddLoad_Priority | proc_ss_temp_n40_vsup_maxproc_5 |
| TC_003_LDO_Bypass_Entry_Exit_HPM_AddLoad_Priority | proc_ss_temp_n40_vsup_maxproc_5.5 |
| TC_003_LDO_Bypass_Entry_Exit_HPM_AddLoad_Priority | proc_ww_temp_125_vsup_maxproc_4.5 |
| TC_003_LDO_Bypass_Entry_Exit_HPM_AddLoad_Priority | proc_ww_temp_125_vsup_maxproc_5 |
| TC_003_LDO_Bypass_Entry_Exit_HPM_AddLoad_Priority | proc_ww_temp_125_vsup_maxproc_5.5 |
| TC_003_LDO_Bypass_Entry_Exit_HPM_AddLoad_Priority | proc_ww_temp_27_vsup_maxproc_4.5 |
| TC_003_LDO_Bypass_Entry_Exit_HPM_AddLoad_Priority | proc_ww_temp_27_vsup_maxproc_5 |
| TC_003_LDO_Bypass_Entry_Exit_HPM_AddLoad_Priority | proc_ww_temp_27_vsup_maxproc_5.5 |
| TC_003_LDO_Bypass_Entry_Exit_HPM_AddLoad_Priority | proc_ww_temp_n40_vsup_maxproc_4.5 |
| TC_003_LDO_Bypass_Entry_Exit_HPM_AddLoad_Priority | proc_ww_temp_n40_vsup_maxproc_5 |
| TC_003_LDO_Bypass_Entry_Exit_HPM_AddLoad_Priority | proc_ww_temp_n40_vsup_maxproc_5.5 |
| TC_004_LDO_MuxSwitch_HPMToggle_EnLDO_Cycling | proc_ss_temp_125_vsup_maxproc_4.5 |
| TC_004_LDO_MuxSwitch_HPMToggle_EnLDO_Cycling | proc_ss_temp_125_vsup_maxproc_5 |
| TC_004_LDO_MuxSwitch_HPMToggle_EnLDO_Cycling | proc_ss_temp_125_vsup_maxproc_5.5 |
| TC_004_LDO_MuxSwitch_HPMToggle_EnLDO_Cycling | proc_ss_temp_27_vsup_maxproc_4.5 |
| TC_004_LDO_MuxSwitch_HPMToggle_EnLDO_Cycling | proc_ss_temp_27_vsup_maxproc_5 |
| TC_004_LDO_MuxSwitch_HPMToggle_EnLDO_Cycling | proc_ss_temp_27_vsup_maxproc_5.5 |
| TC_004_LDO_MuxSwitch_HPMToggle_EnLDO_Cycling | proc_ss_temp_n40_vsup_maxproc_4.5 |
| TC_004_LDO_MuxSwitch_HPMToggle_EnLDO_Cycling | proc_ss_temp_n40_vsup_maxproc_5 |
| TC_004_LDO_MuxSwitch_HPMToggle_EnLDO_Cycling | proc_ss_temp_n40_vsup_maxproc_5.5 |
| TC_004_LDO_MuxSwitch_HPMToggle_EnLDO_Cycling | proc_ww_temp_125_vsup_maxproc_4.5 |
| TC_004_LDO_MuxSwitch_HPMToggle_EnLDO_Cycling | proc_ww_temp_125_vsup_maxproc_5 |
| TC_004_LDO_MuxSwitch_HPMToggle_EnLDO_Cycling | proc_ww_temp_125_vsup_maxproc_5.5 |
| TC_004_LDO_MuxSwitch_HPMToggle_EnLDO_Cycling | proc_ww_temp_27_vsup_maxproc_4.5 |
| TC_004_LDO_MuxSwitch_HPMToggle_EnLDO_Cycling | proc_ww_temp_27_vsup_maxproc_5 |
| TC_004_LDO_MuxSwitch_HPMToggle_EnLDO_Cycling | proc_ww_temp_27_vsup_maxproc_5.5 |
| TC_004_LDO_MuxSwitch_HPMToggle_EnLDO_Cycling | proc_ww_temp_n40_vsup_maxproc_4.5 |
| TC_004_LDO_MuxSwitch_HPMToggle_EnLDO_Cycling | proc_ww_temp_n40_vsup_maxproc_5 |
| TC_004_LDO_MuxSwitch_HPMToggle_EnLDO_Cycling | proc_ww_temp_n40_vsup_maxproc_5.5 |
| TC_005_LDO_ScanPins_AddLoad_Toggle_VPWR_FUNDC | proc_nn_temp_125_vsup_maxproc_4.5 |
| TC_005_LDO_ScanPins_AddLoad_Toggle_VPWR_FUNDC | proc_nn_temp_125_vsup_maxproc_5 |
| TC_005_LDO_ScanPins_AddLoad_Toggle_VPWR_FUNDC | proc_nn_temp_125_vsup_maxproc_5.5 |
| TC_005_LDO_ScanPins_AddLoad_Toggle_VPWR_FUNDC | proc_nn_temp_27_vsup_maxproc_4.5 |
| TC_005_LDO_ScanPins_AddLoad_Toggle_VPWR_FUNDC | proc_nn_temp_27_vsup_maxproc_5 |
| TC_005_LDO_ScanPins_AddLoad_Toggle_VPWR_FUNDC | proc_nn_temp_27_vsup_maxproc_5.5 |
| TC_005_LDO_ScanPins_AddLoad_Toggle_VPWR_FUNDC | proc_nn_temp_n40_vsup_maxproc_4.5 |
| TC_005_LDO_ScanPins_AddLoad_Toggle_VPWR_FUNDC | proc_nn_temp_n40_vsup_maxproc_5 |
| TC_005_LDO_ScanPins_AddLoad_Toggle_VPWR_FUNDC | proc_nn_temp_n40_vsup_maxproc_5.5 |
| TC_005_LDO_ScanPins_AddLoad_Toggle_VPWR_FUNDC | proc_ss_temp_125_vsup_maxproc_4.5 |
| TC_005_LDO_ScanPins_AddLoad_Toggle_VPWR_FUNDC | proc_ss_temp_125_vsup_maxproc_5 |
| TC_005_LDO_ScanPins_AddLoad_Toggle_VPWR_FUNDC | proc_ss_temp_125_vsup_maxproc_5.5 |
| TC_005_LDO_ScanPins_AddLoad_Toggle_VPWR_FUNDC | proc_ss_temp_27_vsup_maxproc_4.5 |
| TC_005_LDO_ScanPins_AddLoad_Toggle_VPWR_FUNDC | proc_ss_temp_27_vsup_maxproc_5 |
| TC_005_LDO_ScanPins_AddLoad_Toggle_VPWR_FUNDC | proc_ss_temp_27_vsup_maxproc_5.5 |
| TC_005_LDO_ScanPins_AddLoad_Toggle_VPWR_FUNDC | proc_ss_temp_n40_vsup_maxproc_4.5 |
| TC_005_LDO_ScanPins_AddLoad_Toggle_VPWR_FUNDC | proc_ss_temp_n40_vsup_maxproc_5 |
| TC_005_LDO_ScanPins_AddLoad_Toggle_VPWR_FUNDC | proc_ss_temp_n40_vsup_maxproc_5.5 |
| TC_005_LDO_ScanPins_AddLoad_Toggle_VPWR_FUNDC | proc_ww_temp_125_vsup_maxproc_4.5 |
| TC_005_LDO_ScanPins_AddLoad_Toggle_VPWR_FUNDC | proc_ww_temp_125_vsup_maxproc_5 |
| TC_005_LDO_ScanPins_AddLoad_Toggle_VPWR_FUNDC | proc_ww_temp_125_vsup_maxproc_5.5 |
| TC_005_LDO_ScanPins_AddLoad_Toggle_VPWR_FUNDC | proc_ww_temp_27_vsup_maxproc_4.5 |
| TC_005_LDO_ScanPins_AddLoad_Toggle_VPWR_FUNDC | proc_ww_temp_27_vsup_maxproc_5 |
| TC_005_LDO_ScanPins_AddLoad_Toggle_VPWR_FUNDC | proc_ww_temp_27_vsup_maxproc_5.5 |
| TC_005_LDO_ScanPins_AddLoad_Toggle_VPWR_FUNDC | proc_ww_temp_n40_vsup_maxproc_4.5 |
| TC_005_LDO_ScanPins_AddLoad_Toggle_VPWR_FUNDC | proc_ww_temp_n40_vsup_maxproc_5 |
| TC_005_LDO_ScanPins_AddLoad_Toggle_VPWR_FUNDC | proc_ww_temp_n40_vsup_maxproc_5.5 |

## Excluded corners

| run_id | corner_id | reasons |
|---|---|---|
| TC_004_LDO_MuxSwitch_HPMToggle_EnLDO_Cycling | proc_nn_temp_125_vsup_maxproc_4.5 | n_states_detected=6 differs from this test case's majority pattern (3, 20/27 corners); completeness=True differs from this test case's majority pattern (False, 18/27 corners) |
| TC_004_LDO_MuxSwitch_HPMToggle_EnLDO_Cycling | proc_nn_temp_125_vsup_maxproc_5 | n_states_detected=6 differs from this test case's majority pattern (3, 20/27 corners); completeness=True differs from this test case's majority pattern (False, 18/27 corners) |
| TC_004_LDO_MuxSwitch_HPMToggle_EnLDO_Cycling | proc_nn_temp_125_vsup_maxproc_5.5 | n_states_detected=6 differs from this test case's majority pattern (3, 20/27 corners); completeness=True differs from this test case's majority pattern (False, 18/27 corners) |
| TC_004_LDO_MuxSwitch_HPMToggle_EnLDO_Cycling | proc_nn_temp_27_vsup_maxproc_4.5 | n_states_detected=6 differs from this test case's majority pattern (3, 20/27 corners); completeness=True differs from this test case's majority pattern (False, 18/27 corners) |
| TC_004_LDO_MuxSwitch_HPMToggle_EnLDO_Cycling | proc_nn_temp_27_vsup_maxproc_5 | n_states_detected=6 differs from this test case's majority pattern (3, 20/27 corners); completeness=True differs from this test case's majority pattern (False, 18/27 corners) |
| TC_004_LDO_MuxSwitch_HPMToggle_EnLDO_Cycling | proc_nn_temp_27_vsup_maxproc_5.5 | n_states_detected=6 differs from this test case's majority pattern (3, 20/27 corners); completeness=True differs from this test case's majority pattern (False, 18/27 corners) |
| TC_004_LDO_MuxSwitch_HPMToggle_EnLDO_Cycling | proc_nn_temp_n40_vsup_maxproc_4.5 | n_states_detected=5 differs from this test case's majority pattern (3, 20/27 corners); completeness=True differs from this test case's majority pattern (False, 18/27 corners) |
| TC_004_LDO_MuxSwitch_HPMToggle_EnLDO_Cycling | proc_nn_temp_n40_vsup_maxproc_5 | completeness=True differs from this test case's majority pattern (False, 18/27 corners) |
| TC_004_LDO_MuxSwitch_HPMToggle_EnLDO_Cycling | proc_nn_temp_n40_vsup_maxproc_5.5 | completeness=True differs from this test case's majority pattern (False, 18/27 corners); n_signals is a low IQR outlier within this test case |
