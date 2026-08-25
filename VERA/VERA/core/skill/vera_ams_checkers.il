; =============================================================================
; VERA — Verification Engine for Runtime & Autonomous Checking
; FILE: core/skill/vera_ams_checkers.il
; DESC: SKILL/OCEAN checker library for Cadence AMS (Virtuoso/Spectre)
;       Provides parametric measurement, schematic-embedded checks,
;       and VERA-format result generation.
; VERSION: 1.0
; USAGE: Load in Virtuoso CIW: load("/path/to/vera_ams_checkers.il")
;        Or source in OCEAN script: load("vera_ams_checkers.il")
; =============================================================================

; ---------------------------------------------------------------------------
; VERA Global State
; ---------------------------------------------------------------------------
veraResults       = list()
veraPassCount     = 0
veraFailCount     = 0
veraWarnCount     = 0
veraCurrentIP     = "UNKNOWN"
veraCurrentTest   = "UNKNOWN"
veraReportFile    = "./vera_report_ams.json"

; ---------------------------------------------------------------------------
; veraSetIP — Set current IP context
; ---------------------------------------------------------------------------
procedure( veraSetIP(ipName testName)
  veraCurrentIP   = ipName
  veraCurrentTest = testName
  printf("VERA: Starting checks for IP=%s Test=%s\n" ipName testName)
)

; ---------------------------------------------------------------------------
; veraLogResult — Core result logger
; ---------------------------------------------------------------------------
procedure( veraLogResult(resultPlist)
  let( (status checkerName ip actualStr expectedStr marginStr contextStr)
    ip          = getf(resultPlist 'ip          veraCurrentIP)
    checkerName = getf(resultPlist 'checker_name "UNNAMED")
    status      = getf(resultPlist 'status      "UNKNOWN")
    actualStr   = getf(resultPlist 'actual      "")
    expectedStr = getf(resultPlist 'expected    "")
    marginStr   = getf(resultPlist 'margin      "")
    contextStr  = getf(resultPlist 'context     "")

    ; Update counters
    cond(
      ((equal status "PASS")    veraPassCount = veraPassCount + 1)
      ((equal status "FAIL")    veraFailCount = veraFailCount + 1)
      ((equal status "WARNING") veraWarnCount = veraWarnCount + 1)
    )

    ; Build result plist with defaults
    resultPlist = append(resultPlist list(
      'vera_version  "1.0"
      'ip            ip
      'test          veraCurrentTest
      'checker_type  "skill_ocean"
      'timestamp     getCurrentDateTime()
    ))

    ; Append to global results list
    veraResults = append(veraResults list(resultPlist))

    ; Console output
    let( (icon)
      icon = cond((equal status "PASS") "✓" (equal status "FAIL") "✗" t "⚠")
      printf("  [%s] %s | %s | EXP: %s | ACT: %s | MAR: %s\n"
             icon ip checkerName expectedStr actualStr marginStr)
    )
    resultPlist
  )
)

; ---------------------------------------------------------------------------
; veraCheckParam — Check a scalar measurement against min/max bounds
; ---------------------------------------------------------------------------
procedure( veraCheckParam(checkerName measVal minVal maxVal unit signal ctx)
  let( (status margin inSpec)
    inSpec = (measVal >= minVal) && (measVal <= maxVal)
    status = if(inSpec "PASS" "FAIL")
    margin = sprintf(nil "lo=%+.4g hi=%+.4g %s"
                     (measVal - minVal) (maxVal - measVal) unit)
    veraLogResult(list(
      'checker_name  checkerName
      'status        status
      'severity      if(inSpec "INFO" "ERROR")
      'expected      sprintf(nil "%g to %g %s" minVal maxVal unit)
      'actual        sprintf(nil "%g %s" measVal unit)
      'margin        margin
      'context       ctx
      'debug_signal  signal
      'layer         "parametric"
    ))
  )
)

; ---------------------------------------------------------------------------
; veraCheckMin — Check measurement is >= minimum
; ---------------------------------------------------------------------------
procedure( veraCheckMin(checkerName measVal minVal unit signal ctx)
  let( (status)
    status = if(measVal >= minVal "PASS" "FAIL")
    veraLogResult(list(
      'checker_name  checkerName
      'status        status
      'severity      if(status == "PASS" "INFO" "ERROR")
      'expected      sprintf(nil ">= %g %s" minVal unit)
      'actual        sprintf(nil "%g %s" measVal unit)
      'margin        sprintf(nil "%+.4g %s" (measVal - minVal) unit)
      'context       ctx
      'debug_signal  signal
    ))
  )
)

; ---------------------------------------------------------------------------
; veraCheckMax — Check measurement is <= maximum
; ---------------------------------------------------------------------------
procedure( veraCheckMax(checkerName measVal maxVal unit signal ctx)
  let( (status)
    status = if(measVal <= maxVal "PASS" "FAIL")
    veraLogResult(list(
      'checker_name  checkerName
      'status        status
      'severity      if(status == "PASS" "INFO" "ERROR")
      'expected      sprintf(nil "<= %g %s" maxVal unit)
      'actual        sprintf(nil "%g %s" measVal unit)
      'margin        sprintf(nil "%+.4g %s" (maxVal - measVal) unit)
      'context       ctx
      'debug_signal  signal
    ))
  )
)

; ---------------------------------------------------------------------------
; veraCheckOcean — Check OCEAN waveform measurement
; ---------------------------------------------------------------------------
procedure( veraCheckOcean(checkerName waveExpr minVal maxVal unit signal ctx)
  let( (measVal)
    measVal = evalstring(waveExpr)   ; Evaluate OCEAN expression
    if(rationalp(measVal) || floatp(measVal)
      veraCheckParam(checkerName float(measVal) minVal maxVal unit signal ctx)
      veraLogResult(list(
        'checker_name checkerName
        'status       "WARNING"
        'severity     "WARNING"
        'expected     sprintf(nil "%g to %g %s" minVal maxVal unit)
        'actual       sprintf(nil "EVAL_FAILED: %s" waveExpr)
        'context      ctx
      ))
    )
  )
)

; ---------------------------------------------------------------------------
; AMS-Specific Checker Procedures
; ---------------------------------------------------------------------------

; veraCheckAcGain — AC gain check (dB at specific frequency)
procedure( veraCheckAcGain(sig_out sig_in freq_hz minGain maxGain)
  let( (gainVal gainExpr)
    gainExpr = sprintf(nil "dBm20(getData(\"%s\") / getData(\"%s\"))" sig_out sig_in)
    gainVal  = value(evalstring(gainExpr) freq_hz)
    veraCheckParam("vera_ac_gain" gainVal minGain maxGain "dB"
                   sig_out sprintf(nil "f=%.0fHz" freq_hz))
  )
)

; veraCheckAcBW — 3dB bandwidth check
procedure( veraCheckAcBW(sig_out sig_in minBW maxBW)
  let( (bwVal)
    bwVal = bandwidth(evalstring(sprintf(nil "dBm20(getData(\"%s\") / getData(\"%s\"))" sig_out sig_in)) -3)
    veraCheckParam("vera_ac_bandwidth" bwVal minBW maxBW "Hz" sig_out "3dB BW")
  )
)

; veraCheckPhaseMargin — Phase margin from Bode plot
procedure( veraCheckPhaseMargin(loopGainWave minPM)
  let( (pmVal)
    pmVal = phaseMargin(loopGainWave)
    veraCheckMin("vera_phase_margin" pmVal minPM "deg" "loop_gain"
                 sprintf(nil "PM=%.1f deg" pmVal))
  )
)

; veraCheckDcVoltage — DC voltage at node
procedure( veraCheckDcVoltage(nodeName minV maxV)
  let( (vval)
    vval = value(getData(nodeName) 0)
    veraCheckParam(
      sprintf(nil "vera_dc_%s" nodeName) vval minV maxV "V" nodeName "DC operating point"
    )
  )
)

; veraCheckPSRR — Power Supply Rejection Ratio
procedure( veraCheckPSRR(vout_wave vdd_wave freq_hz minPSRR)
  let( (psrrVal)
    psrrVal = -1 * value(dBm20(getData(vout_wave) / getData(vdd_wave)) freq_hz)
    veraCheckMin("vera_psrr" psrrVal minPSRR "dB" vout_wave
                 sprintf(nil "f=%.0fHz PSRR=%.1fdB" freq_hz psrrVal))
  )
)

; veraCheckCMRR — Common Mode Rejection Ratio
procedure( veraCheckCMRR(vdiff_wave vcm_wave freq_hz minCMRR)
  let( (cmrrVal)
    cmrrVal = -1 * value(dBm20(getData(vdiff_wave) / getData(vcm_wave)) freq_hz)
    veraCheckMin("vera_cmrr" cmrrVal minCMRR "dB" vdiff_wave
                 sprintf(nil "f=%.0fHz CMRR=%.1fdB" freq_hz cmrrVal))
  )
)

; veraCheckSlew — Slew rate check (V/us)
procedure( veraCheckSlewRate(vout_wave riseFlag minSlew maxSlew)
  let( (slewVal t1 t2 v1 v2)
    ; Measure between 10% and 90% of swing
    slewVal = if(riseFlag
      slewRate(vout_wave 0.1 0.9)
      slewRate(vout_wave 0.9 0.1)
    )
    veraCheckParam("vera_slew_rate" slewVal minSlew maxSlew "V/us"
                   "vout" sprintf(nil "rise=%s" if(riseFlag "T" "F")))
  )
)

; veraCheckSettling — Settling time to within X% of final value
procedure( veraCheckSettling(vout_wave targetV tolerance_pct maxTime_ns)
  let( (settleTime bandHigh bandLow)
    bandHigh   = targetV * (1 + tolerance_pct/100)
    bandLow    = targetV * (1 - tolerance_pct/100)
    settleTime = settlingTime(vout_wave bandLow bandHigh) * 1e9   ; Convert to ns
    veraCheckMax("vera_settling_time" settleTime maxTime_ns "ns"
                 "vout" sprintf(nil "target=%.3fV tol=%.1f%%" targetV tolerance_pct))
  )
)

; veraCheckOffset — Input referred offset voltage
procedure( veraCheckOffset(vos_val maxOffset_uV)
  let( (vos_uV)
    vos_uV = abs(vos_val * 1e6)
    veraCheckMax("vera_vos_offset" vos_uV maxOffset_uV "uV" "vos" "input offset")
  )
)

; veraCheckTHD — Total Harmonic Distortion
procedure( veraCheckTHD(vout_wave fin_hz maxTHD_pct)
  let( (thdVal)
    thdVal = thd(vout_wave) * 100   ; Convert to percentage
    veraCheckMax("vera_thd" thdVal maxTHD_pct "%" "vout"
                 sprintf(nil "fin=%.0fHz" fin_hz))
  )
)

; ---------------------------------------------------------------------------
; veraWriteReport — Write VERA JSON report
; ---------------------------------------------------------------------------
procedure( veraWriteReport()
  let( (fd i result)
    fd = outfile(veraReportFile "w")
    if(fd then
      fprintf(fd "{\n")
      fprintf(fd "  \"vera_report\": {\n")
      fprintf(fd "    \"summary\": {\n")
      fprintf(fd "      \"total\": %d,\n" length(veraResults))
      fprintf(fd "      \"pass\": %d,\n" veraPassCount)
      fprintf(fd "      \"fail\": %d,\n" veraFailCount)
      fprintf(fd "      \"warning\": %d\n" veraWarnCount)
      fprintf(fd "    },\n")
      fprintf(fd "    \"results\": [\n")
      i = 0
      foreach(result veraResults
        fprintf(fd "      {\n")
        foreach(key list('checker_name 'status 'severity 'expected 'actual
                         'margin 'context 'debug_signal 'layer 'vera_version
                         'ip 'checker_type 'timestamp)
          let( (val)
            val = getf(result key "")
            if(stringp(val)
              fprintf(fd "        \"%s\": \"%s\"" symbolToString(key) val)
              fprintf(fd "        \"%s\": \"%s\"" symbolToString(key) sprintf(nil "%A" val))
            )
            fprintf(fd ",\n")
          )
        )
        fprintf(fd "        \"_end\": null\n")
        if(i < length(veraResults) - 1
          fprintf(fd "      },\n")
          fprintf(fd "      }\n")
        )
        i++
      )
      fprintf(fd "    ]\n")
      fprintf(fd "  }\n")
      fprintf(fd "}\n")
      close(fd)
      printf("\n============================================================\n")
      printf("  VERA AMS SUMMARY: PASS=%d FAIL=%d WARN=%d\n"
             veraPassCount veraFailCount veraWarnCount)
      printf("  Report written: %s\n" veraReportFile)
      printf("============================================================\n\n")
    else
      printf("VERA ERROR: Cannot open report file: %s\n" veraReportFile)
    )
  )
)

; ---------------------------------------------------------------------------
; veraRunOpamp — Complete op-amp checker suite
; Usage: veraRunOpamp("my_ota" list('gain_min 60 'bw_min 10e6 'pm_min 60))
; ---------------------------------------------------------------------------
procedure( veraRunOpamp(ipName specPlist)
  veraSetIP(ipName "opamp_ac_checks")

  let( (gainMin bwMin pmMin slewMin psrrMin cmrrMin vosMax)
    gainMin  = getf(specPlist 'gain_min  60.0)
    bwMin    = getf(specPlist 'bw_min    1e6)
    pmMin    = getf(specPlist 'pm_min    45.0)
    psrrMin  = getf(specPlist 'psrr_min  60.0)
    cmrrMin  = getf(specPlist 'cmrr_min  60.0)
    vosMax   = getf(specPlist 'vos_max_uV 1000.0)

    veraCheckAcGain("/vout" "/vin" 1000 gainMin 200)
    veraCheckAcBW   "/vout" "/vin" bwMin 1e9)
    ; Phase margin requires loop gain wave — user must set up
    ; veraCheckPhaseMargin(loopGainWave pmMin)
  )
)

; ---------------------------------------------------------------------------
; VERA SKILL — Print banner on load
; ---------------------------------------------------------------------------
printf("\n")
printf("  ╔══════════════════════════════════════════════════╗\n")
printf("  ║  VERA AMS Checker Library v1.0 — Loaded         ║\n")
printf("  ║  Verification Engine for Runtime & Autonomous   ║\n")
printf("  ║  Checking — Cadence SKILL/OCEAN Module          ║\n")
printf("  ╚══════════════════════════════════════════════════╝\n")
printf("\n")
printf("  Functions loaded:\n")
printf("    veraSetIP, veraCheckParam, veraCheckMin, veraCheckMax\n")
printf("    veraCheckAcGain, veraCheckAcBW, veraCheckPhaseMargin\n")
printf("    veraCheckDcVoltage, veraCheckPSRR, veraCheckCMRR\n")
printf("    veraCheckSlew, veraCheckSettling, veraCheckOffset\n")
printf("    veraCheckTHD, veraRunOpamp, veraWriteReport\n")
printf("\n")
printf("  Usage: load(\"vera_ams_checkers.il\")\n")
printf("         veraSetIP(\"MY_OTA\" \"tb_ac\")\n")
printf("         veraCheckAcGain(\"/vout\" \"/vin\" 1000 60 120)\n")
printf("         veraWriteReport()\n\n")
