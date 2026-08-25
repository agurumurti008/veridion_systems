#!/bin/bash
# ============================================================================
# VERA — Verification Engine for Runtime & Autonomous Checking
# FILE: scripts/integration/vera_eda_setup.sh
# DESC: EDA tool integration setup script.
#       Configures Xcelium, VCS, Questa, and Spectre/APS for VERA.
#       Sources environment variables and patches simulation run scripts.
# VERSION: 1.0
# ============================================================================

set -euo pipefail

VERA_HOME="${VERA_HOME:-$(pwd)}"
CYAN='\033[0;36m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'

vera_log() { echo -e "  ${CYAN}[VERA]${NC} $1"; }
vera_ok()  { echo -e "  ${GREEN}[OK]${NC} $1"; }
vera_warn(){ echo -e "  ${YELLOW}[WARN]${NC} $1"; }

echo ""
echo "  ╔══════════════════════════════════════════════════════════╗"
echo "  ║  VERA EDA Integration Setup v1.0                        ║"
echo "  ╚══════════════════════════════════════════════════════════╝"
echo ""

# ============================================================================
# Detect available EDA tools
# ============================================================================
detect_tools() {
  vera_log "Detecting EDA tools..."
  HAS_XCELIUM=0; HAS_VCS=0; HAS_QUESTA=0; HAS_SPECTRE=0

  command -v xrun     &>/dev/null && HAS_XCELIUM=1 && vera_ok "Cadence Xcelium found"
  command -v vcs      &>/dev/null && HAS_VCS=1      && vera_ok "Synopsys VCS found"
  command -v vsim     &>/dev/null && HAS_QUESTA=1   && vera_ok "Siemens Questa found"
  command -v spectre  &>/dev/null && HAS_SPECTRE=1  && vera_ok "Cadence Spectre found"

  [[ $HAS_XCELIUM -eq 0 && $HAS_VCS -eq 0 && $HAS_QUESTA -eq 0 ]] && \
    vera_warn "No digital simulator detected. VERA will run in post-sim only mode."
}

# ============================================================================
# Write VERA environment file
# ============================================================================
write_vera_env() {
  cat > "${VERA_HOME}/vera_env.sh" << EOF
# VERA Environment — source this in your shell or simulation scripts
# Generated: $(date)

export VERA_HOME="${VERA_HOME}"
export VERA_VERSION="1.0"

# Add VERA Python tools to PATH
export PATH="\${VERA_HOME}/automation/builder:\${VERA_HOME}/automation/reporter:\${VERA_HOME}/automation/waveform_loader:\${VERA_HOME}/automation/tb_gen:\$PATH"
export PYTHONPATH="\${VERA_HOME}/core/python:\$PYTHONPATH"

# VERA SV include paths
export VERA_SV_INCDIR="\${VERA_HOME}/core/sv"
export VERA_UVM_INCDIR="\${VERA_HOME}/core/uvm"

# VERA SKILL library (Cadence)
export VERA_SKILL_LIB="\${VERA_HOME}/core/skill/vera_ams_checkers.il"

# VERA Report defaults
export VERA_REPORT_DIR="\${PWD}/vera_reports"
export VERA_REPORT_FORMAT="json"

echo "  [VERA] Environment loaded: VERA_HOME=\${VERA_HOME}"
EOF
  vera_ok "Created vera_env.sh"
}

# ============================================================================
# Xcelium integration — .xcelium_prj and xrun wrapper
# ============================================================================
setup_xcelium() {
  [[ $HAS_XCELIUM -eq 0 ]] && return
  vera_log "Setting up Xcelium integration..."

  cat > "${VERA_HOME}/scripts/integration/vera_xcelium.f" << 'EOF'
# VERA Xcelium File List
# Include in your xrun command: xrun -f $VERA_HOME/scripts/integration/vera_xcelium.f

# VERA SVA Library
-sv ${VERA_HOME}/core/sv/vera_sva_library.sv

# VERA UVM Scoreboard Base
-uvm
${VERA_HOME}/core/uvm/vera_scoreboard_base.sv

# VERA defines
+define+VERA_ENABLE=1
+define+VERA_REPORT_JSON=1

# UVM verbosity
+UVM_VERBOSITY=UVM_MEDIUM

# VERA report output path (override with +vera_report_path)
+vera_report_path=./vera_reports/vera_sim_report.json
EOF

  # Xcelium post-sim hook — runs Python checkers after simulation
  cat > "${VERA_HOME}/scripts/integration/vera_xcelium_posthook.sh" << 'EOF'
#!/bin/bash
# VERA Xcelium Post-Sim Hook
# Add to xrun: -end_run_cmd "$VERA_HOME/scripts/integration/vera_xcelium_posthook.sh"
source "${VERA_HOME}/vera_env.sh"

SPEC_YAML="${VERA_SPEC_YAML:-}"
SIM_DATA="${VERA_SIM_DATA:-}"
REPORT_DIR="${VERA_REPORT_DIR:-./vera_reports}"

mkdir -p "${REPORT_DIR}"

if [[ -n "${SPEC_YAML}" && -f "${SPEC_YAML}" && -n "${SIM_DATA}" && -f "${SIM_DATA}" ]]; then
  echo "  [VERA] Running post-sim Python checkers..."
  python3 "${VERA_HOME}/core/python/vera_postsim_engine.py" \
    --spec "${SPEC_YAML}" \
    --data "${SIM_DATA}" \
    --report "${REPORT_DIR}/vera_postsim_report.json"
fi

# Generate HTML dashboard
if ls "${REPORT_DIR}"/*.json 1>/dev/null 2>&1; then
  echo "  [VERA] Generating HTML dashboard..."
  python3 "${VERA_HOME}/automation/reporter/vera_dashboard.py" \
    --results_dir "${REPORT_DIR}" \
    --output "${REPORT_DIR}/vera_dashboard.html"
fi

# Generate waveform loaders
if [[ -f "${REPORT_DIR}/vera_postsim_report.json" ]]; then
  python3 "${VERA_HOME}/automation/waveform_loader/vera_waveload.py" \
    --report "${REPORT_DIR}/vera_postsim_report.json" \
    --tool all \
    --output "${REPORT_DIR}/debug_scripts/"
fi
EOF
  chmod +x "${VERA_HOME}/scripts/integration/vera_xcelium_posthook.sh"
  vera_ok "Xcelium integration files created"
}

# ============================================================================
# VCS integration
# ============================================================================
setup_vcs() {
  [[ $HAS_VCS -eq 0 ]] && return
  vera_log "Setting up VCS integration..."

  cat > "${VERA_HOME}/scripts/integration/vera_vcs.f" << 'EOF'
# VERA VCS File List
# Include: vcs -f $VERA_HOME/scripts/integration/vera_vcs.f

-sverilog
-ntb_opts uvm-1.2
+define+VERA_ENABLE=1
+define+VERA_REPORT_JSON=1
${VERA_HOME}/core/sv/vera_sva_library.sv
${VERA_HOME}/core/uvm/vera_scoreboard_base.sv
EOF
  vera_ok "VCS integration files created"
}

# ============================================================================
# Questa integration
# ============================================================================
setup_questa() {
  [[ $HAS_QUESTA -eq 0 ]] && return
  vera_log "Setting up Questa integration..."

  cat > "${VERA_HOME}/scripts/integration/vera_questa.do" << 'EOF'
# VERA Questa Do File
# Source in Questa: do $VERA_HOME/scripts/integration/vera_questa.do

quietly set VERA_HOME [getenv VERA_HOME]

# Compile VERA libraries
vlog -sv +define+VERA_ENABLE=1 \
  ${VERA_HOME}/core/sv/vera_sva_library.sv \
  ${VERA_HOME}/core/uvm/vera_scoreboard_base.sv

# Run simulation with VERA hooks
proc vera_run {test_name {verbosity UVM_MEDIUM}} {
  vsim -c tb_top +UVM_TESTNAME=${test_name} +UVM_VERBOSITY=${verbosity} \
    -do "
      log -r /*;
      run -all;
      vera_post_sim;
      quit -code [coverage attribute -name TOTALUNCOVERED -strip]
    "
}

proc vera_post_sim {} {
  global VERA_HOME
  set report_dir "./vera_reports"
  file mkdir $report_dir
  exec python3 ${VERA_HOME}/automation/reporter/vera_dashboard.py \
    --results_dir $report_dir --output ${report_dir}/vera_dashboard.html
}
EOF
  vera_ok "Questa integration files created"
}

# ============================================================================
# Spectre/APS integration (SKILL auto-load)
# ============================================================================
setup_spectre() {
  [[ $HAS_SPECTRE -eq 0 ]] && return
  vera_log "Setting up Spectre/APS integration..."

  # .cdsinit snippet to auto-load VERA SKILL library
  cat > "${VERA_HOME}/scripts/integration/vera_cdsinit_snippet.il" << EOF
; Add to your .cdsinit to auto-load VERA SKILL library
; -------------------------------------------------------
when( isFile( getShellEnvVar("VERA_HOME") + "/core/skill/vera_ams_checkers.il" )
  load( getShellEnvVar("VERA_HOME") + "/core/skill/vera_ams_checkers.il" )
  printf("VERA: AMS Checker Library loaded\n")
)
EOF

  # Template OCEAN post-sim script
  cat > "${VERA_HOME}/scripts/integration/vera_ocean_template.ocn" << 'OCNEOF'
; VERA OCEAN Post-Sim Template
; Run in Cadence ADE or as: ocean -nograph -replay vera_ocean_template.ocn

; Load VERA library
load(getShellEnvVar("VERA_HOME") + "/core/skill/vera_ams_checkers.il")

; Set current IP
veraSetIP("MY_IP" "ocean_postsim")

; Open results
openResults(strcat(getShellEnvVar("PWD") "/simulation/MY_IP/spectre/schematic/psf"))

; Run checks (customize for your IP)
selectResults('dc)
veraCheckDcVoltage("/vout" 1.75 1.85)

selectResults('ac)
veraCheckAcGain("/vout" "/vin" 1000 60 120)
veraCheckAcBW("/vout" "/vin" 1e6 1e9)

; Write VERA report
veraReportFile = strcat(getShellEnvVar("PWD") "/vera_reports/vera_ocean_report.json")
veraWriteReport()
OCNEOF

  vera_ok "Spectre/APS integration files created"
}

# ============================================================================
# Install Python dependencies
# ============================================================================
install_python_deps() {
  vera_log "Checking Python dependencies..."
  local deps=("numpy" "scipy" "pyyaml" "pandas")
  local missing=()

  for dep in "${deps[@]}"; do
    python3 -c "import $dep" 2>/dev/null || missing+=("$dep")
  done

  if [[ ${#missing[@]} -gt 0 ]]; then
    vera_warn "Missing Python packages: ${missing[*]}"
    vera_log "Installing: pip3 install ${missing[*]}"
    pip3 install "${missing[@]}" --quiet 2>/dev/null || \
      vera_warn "Could not auto-install. Run: pip3 install ${missing[*]}"
  else
    vera_ok "All Python dependencies satisfied"
  fi

  # Optional: vcdvcd for VCD parsing
  python3 -c "import vcdvcd" 2>/dev/null || \
    vera_warn "Optional: pip3 install vcdvcd (for VCD parsing)"
}

# ============================================================================
# Write VERA config template
# ============================================================================
write_vera_config() {
  cat > "${VERA_HOME}/cfg/vera_config.yaml" << 'EOF'
# VERA Configuration File
# Used by vera_regression.sh and VERA tools

vera_version: "1.0"

# Default simulator
sim_tool: xcelium   # xcelium | vcs | questa

# Report settings
report:
  format:    json
  html:      true
  dir:       ./vera_reports/

# Waveform loader
waveform:
  tool:     simvision   # simvision | nwave | gtkwave | dve
  fsdb_dir: ./sim_runs/

# Post-sim Python engine
postsim:
  enabled: true
  engine:  vera_postsim_engine.py

# AMS checks (SKILL/OCEAN)
ams:
  enabled:   true
  tool:      spectre
  skill_lib: ${VERA_HOME}/core/skill/vera_ams_checkers.il

# Tests (map test names to spec YAMLs)
tests:
  adc_basic_test:
    spec: examples/sar_adc/sar_adc_spec.yaml
  pll_lock_test:
    spec: examples/pll/pll_spec.yaml
  uart_protocol_test:
    spec: examples/uart/uart_spec.yaml
EOF
  mkdir -p "${VERA_HOME}/cfg"
  vera_ok "Created cfg/vera_config.yaml"
}

# ============================================================================
# Main
# ============================================================================
main() {
  detect_tools
  write_vera_env
  setup_xcelium
  setup_vcs
  setup_questa
  setup_spectre
  install_python_deps
  write_vera_config

  echo ""
  echo "  ============================================================"
  echo "  VERA EDA Integration Setup Complete"
  echo ""
  echo "  Next steps:"
  echo "    1. source ${VERA_HOME}/vera_env.sh"
  echo "    2. Add to xrun: -f \${VERA_HOME}/scripts/integration/vera_xcelium.f"
  echo "    3. Add to .cdsinit: vera_cdsinit_snippet.il content"
  echo "    4. python3 automation/builder/vera_builder.py --spec <ip>.yaml --output out/"
  echo "    5. ./scripts/regression/vera_regression.sh --sim xcelium --test_list tests.list"
  echo "  ============================================================"
  echo ""
}

main "$@"
