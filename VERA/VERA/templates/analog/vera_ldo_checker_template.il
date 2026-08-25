// ============================================================================
// VERA — Verification Engine for Runtime & Autonomous Checking
// FILE: templates/analog/vera_ldo_checker_template.il
// DESC: LDO / Power Management checker template (SKILL/OCEAN)
//       Covers: line regulation, load regulation, PSRR, transient response,
//       dropout voltage, quiescent current, output noise.
// VERSION: 1.0
// ============================================================================

; ---------------------------------------------------------------------------
; VERA LDO Checker — Complete Template
; Usage: load the file then call veraRunLdo("LDO_1V8" ldoSpec)
; ---------------------------------------------------------------------------

load(strcat(getShellEnvVar("VERA_HOME") "/core/skill/vera_ams_checkers.il"))

; ---------------------------------------------------------------------------
; veraRunLdo — Full LDO checker suite
; ldoSpec example:
;   list('vout_nom 1.8 'vout_tol 0.02 'dropout_max 0.3
;        'iq_max_ua 50 'psrr_min_db 40 'load_reg_max_mv 10
;        'line_reg_max_mv 5 'transient_max_mv 100 'settle_ns 5000)
; ---------------------------------------------------------------------------
procedure( veraRunLdo(ipName ldoSpec)
  let( (voutNom voutTol voutMin voutMax
        dropoutMax iqMax psrrMin
        loadRegMax lineRegMax transMax settleNs
        voutDc voutAcLoad voutAcLine iqVal dropoutVal)

    ; Extract spec parameters
    voutNom    = getf(ldoSpec 'vout_nom    1.8)
    voutTol    = getf(ldoSpec 'vout_tol    0.02)
    dropoutMax = getf(ldoSpec 'dropout_max 0.3)
    iqMax      = getf(ldoSpec 'iq_max_ua   100)
    psrrMin    = getf(ldoSpec 'psrr_min_db 40)
    loadRegMax = getf(ldoSpec 'load_reg_max_mv 20)
    lineRegMax = getf(ldoSpec 'line_reg_max_mv 10)
    transMax   = getf(ldoSpec 'transient_max_mv 200)
    settleNs   = getf(ldoSpec 'settle_ns   10000)

    voutMin    = voutNom * (1 - voutTol)
    voutMax    = voutNom * (1 + voutTol)

    veraSetIP(ipName "ldo_full_check")

    ; ---- DC Output Voltage ----
    selectResults('dc)
    voutDc = value(getData("/vout") 0)
    veraCheckParam("vera_ldo_vout_dc" voutDc voutMin voutMax "V" "/vout" "DC output voltage")

    ; ---- Dropout Voltage ----
    ; Dropout = Vin_min - Vout at Vin_min
    let( (vinMin vout_at_vin_min dropoutVal)
      vinMin          = getf(ldoSpec 'vin_min 1.9)
      vout_at_vin_min = value(getData("/vout") 0)   ; from dropout DC sweep
      dropoutVal      = vinMin - vout_at_vin_min
      veraCheckMax("vera_ldo_dropout" dropoutVal dropoutMax "V" "/vout"
                   sprintf(nil "Vin=%.2fV" vinMin))
    )

    ; ---- Quiescent Current ----
    let( (iqUa)
      iqUa = abs(value(getData("/iin") 0) * 1e6)
      veraCheckMax("vera_ldo_iq" iqUa iqMax "uA" "/iin" "quiescent current at no load")
    )

    ; ---- AC: PSRR at multiple frequencies ----
    selectResults('ac)
    foreach( freq list(100 1000 10000 100000)
      let( (psrrVal label)
        ; PSRR = -|Vout/Vripple| in dB
        psrrVal = -1 * value(dBm20(getData("/vout") / getData("/vdd_ac")) freq)
        label   = sprintf(nil "f=%dHz" freq)
        veraCheckMin(sprintf(nil "vera_ldo_psrr_%dHz" freq) psrrVal psrrMin "dB" "/vout" label)
      )
    )

    ; ---- Load Regulation ----
    ; Load reg = (Vout_noload - Vout_fullload) in mV
    ; Requires DC sweep over load current
    selectResults('dc)
    let( (vNoLoad vFullLoad loadRegMv)
      vNoLoad    = value(getData("/vout") 0)
      vFullLoad  = value(getData("/vout") 1)   ; assumes 2-point DC sweep
      loadRegMv  = abs(vNoLoad - vFullLoad) * 1000
      veraCheckMax("vera_ldo_load_reg" loadRegMv loadRegMax "mV" "/vout"
                   "load regulation noload→fullload")
    )

    ; ---- Line Regulation ----
    ; Line reg = ΔVout / ΔVin in mV/V
    let( (lineRegMv)
      lineRegMv = abs(deriv(getData("/vout")) * 1000)
      veraCheckMax("vera_ldo_line_reg" ymax(lineRegMv) lineRegMax "mV/V" "/vout"
                   "line regulation")
    )

    ; ---- Transient Response ----
    ; Load transient — check peak deviation and settling
    selectResults('tran)
    let( (voutTran peakDev peakDevMv settleTime)
      voutTran   = getData("/vout")
      peakDevMv  = abs(ymax(voutTran) - voutNom) * 1000
      veraCheckMax("vera_ldo_transient_peak" peakDevMv transMax "mV" "/vout"
                   sprintf(nil "peak deviation from %.3fV" voutNom))
      settleTime = settlingTime(voutTran
                    voutMin * 1000   ; band in mV not V here — adjust
                    voutMax * 1000) * 1e9
      veraCheckMax("vera_ldo_transient_settle" settleTime settleNs "ns" "/vout"
                   "settling to within spec band after load step")
    )

    ; ---- Output Noise (if available) ----
    selectResults('noise)
    let( (noiseMax noiseSpec intNoiseUv)
      noiseSpec   = getf(ldoSpec 'noise_max_uv_rms 50)
      ; Integrated noise 10Hz–100kHz
      intNoiseUv  = integ(sqrt(getData("out"))) * 1e6
      veraCheckMax("vera_ldo_output_noise" intNoiseUv noiseSpec "uV_rms" "/vout"
                   "integrated output noise 10Hz-100kHz")
    )

    ; Write report
    veraWriteReport()
  )
)


; ---------------------------------------------------------------------------
; veraRunBandgap — Bandgap reference checker
; ---------------------------------------------------------------------------
procedure( veraRunBandgap(ipName bgSpec)
  let( (vbgNom vbgTol vbgMin vbgMax tcMax psrrMin vbgDc tcCoeff)

    vbgNom  = getf(bgSpec 'vbg_nom    1.2)
    vbgTol  = getf(bgSpec 'vbg_tol    0.01)
    tcMax   = getf(bgSpec 'tc_max_ppm 20)   ; ppm/°C
    psrrMin = getf(bgSpec 'psrr_min_db 60)

    vbgMin  = vbgNom * (1 - vbgTol)
    vbgMax  = vbgNom * (1 + vbgTol)

    veraSetIP(ipName "bandgap_checks")

    ; DC at nominal
    selectResults('dc)
    vbgDc = value(getData("/vbg") 0)
    veraCheckParam("vera_bg_vbg_dc" vbgDc vbgMin vbgMax "V" "/vbg" "nominal Vbg")

    ; Temperature coefficient (from temp sweep)
    ; TC = (Vbg_max - Vbg_min) / (Vbg_nom * temp_range) * 1e6 ppm/C
    let( (vbgMax_t vbgMin_t tempRange tcPpm)
      tempRange = getf(bgSpec 'temp_range 150)   ; e.g. -40 to 125C
      vbgMax_t  = ymax(getData("/vbg"))
      vbgMin_t  = ymin(getData("/vbg"))
      tcPpm     = (vbgMax_t - vbgMin_t) / (vbgNom * tempRange) * 1e6
      veraCheckMax("vera_bg_temp_coeff" tcPpm tcMax "ppm/C" "/vbg"
                   sprintf(nil "range=%dC tcPpm=%.1f" tempRange tcPpm))
    )

    ; PSRR
    selectResults('ac)
    let( (psrrVal)
      psrrVal = -1 * value(dBm20(getData("/vbg") / getData("/vdd")) 1000)
      veraCheckMin("vera_bg_psrr_1kHz" psrrVal psrrMin "dB" "/vbg" "PSRR at 1kHz")
    )

    veraWriteReport()
  )
)


; ---------------------------------------------------------------------------
; veraRunComparator — Comparator checker suite
; ---------------------------------------------------------------------------
procedure( veraRunComparator(ipName cmpSpec)
  let( (propDelMax offsetMax hystMin vosMax)

    propDelMax = getf(cmpSpec 'prop_delay_max_ns 10)
    offsetMax  = getf(cmpSpec 'offset_max_mv     5)
    hystMin    = getf(cmpSpec 'hysteresis_min_mv 0)
    vosMax     = getf(cmpSpec 'vos_max_uv        1000)

    veraSetIP(ipName "comparator_checks")

    selectResults('tran)

    ; Propagation delay (rising)
    let( (tpd_rise tpd_fall)
      tpd_rise = delay(getData("/vout") 0.9 getData("/vdiff") 0.0 1) * 1e9
      tpd_fall = delay(getData("/vout") 0.1 getData("/vdiff") 0.0 -1) * 1e9
      veraCheckMax("vera_cmp_tpd_rise" tpd_rise propDelMax "ns" "/vout" "rising propagation delay")
      veraCheckMax("vera_cmp_tpd_fall" tpd_fall propDelMax "ns" "/vout" "falling propagation delay")
    )

    ; Input offset voltage (from DC transfer sweep)
    selectResults('dc)
    let( (vos_uv)
      vos_uv = abs(cross(getData("/vout") 0.9 1)) * 1e6
      veraCheckMax("vera_cmp_offset" vos_uv vosMax "uV" "/vout" "input offset voltage")
    )

    veraWriteReport()
  )
)
