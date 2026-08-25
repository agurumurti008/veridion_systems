#!/bin/bash
# ============================================================================
# VERA — Verification Engine for Runtime & Autonomous Checking
# FILE: scripts/regression/vera_regression.sh
# DESC: Regression runner with VERA hooks.
#       Runs simulation tests, collects VERA reports, generates summary.
# VERSION: 1.0
# USAGE: ./vera_regression.sh --sim xcelium --test_list tests.list
#                             --vera_cfg cfg/vera_config.yaml
# ============================================================================

set -euo pipefail

# --- Defaults ---
SIM_TOOL="xcelium"
TEST_LIST=""
VERA_CFG=""
OUTPUT_DIR="vera_regression_results"
MAX_PARALLEL=4
VERA_REPORT_DIR="vera_reports"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
RUN_ID="vera_run_${TIMESTAMP}"

# --- Colors ---
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; NC='\033[0m'

# --- Banner ---
vera_banner() {
cat << 'EOF'
  ╔══════════════════════════════════════════════════════════╗
  ║                                                          ║
  ║   VERA — Verification Engine for Runtime &              ║
  ║           Autonomous Checking                           ║
  ║   Regression Runner v1.0                                ║
  ║                                                          ║
  ╚══════════════════════════════════════════════════════════╝
EOF
}

# --- Parse Arguments ---
parse_args() {
  while [[ $# -gt 0 ]]; do
    case $1 in
      --sim)        SIM_TOOL="$2";    shift 2;;
      --test_list)  TEST_LIST="$2";   shift 2;;
      --vera_cfg)   VERA_CFG="$2";    shift 2;;
      --output)     OUTPUT_DIR="$2";  shift 2;;
      --parallel)   MAX_PARALLEL="$2";shift 2;;
      *) echo "Unknown option: $1"; exit 1;;
    esac
  done
}

# --- Setup ---
setup_dirs() {
  mkdir -p "${OUTPUT_DIR}/${RUN_ID}/"{logs,reports,waveforms,vera_json}
  echo -e "${CYAN}  Run ID: ${RUN_ID}${NC}"
  echo -e "${CYAN}  Output: ${OUTPUT_DIR}/${RUN_ID}${NC}"
}

# --- Run Single Test ---
run_test() {
  local test_name="$1"
  local test_dir="${OUTPUT_DIR}/${RUN_ID}/logs/${test_name}"
  local vera_out="${OUTPUT_DIR}/${RUN_ID}/vera_json/${test_name}_vera.json"
  local log_file="${test_dir}/sim.log"
  
  mkdir -p "${test_dir}"
  
  echo -e "  ${BLUE}[RUN]${NC} ${test_name}"

  # Build simulation command based on tool
  case "${SIM_TOOL}" in
    xcelium)
      SIM_CMD="xrun -access +r \
        +vera_report_path=${vera_out} \
        +vera_ip_name=${test_name} \
        -vera_sva vera_sva_library.sv \
        -top tb \
        -define VERA_ENABLE=1 \
        ${test_name}.sv 2>&1"
      ;;
    vcs)
      SIM_CMD="vcs +vcs+dumparrays \
        +define+VERA_ENABLE=1 \
        -vera_out ${vera_out} \
        tb.sv ${test_name}.sv \
        -o simv && ./simv 2>&1"
      ;;
    questa)
      SIM_CMD="vsim -c -do \"
        vlog +define+VERA_ENABLE=1 vera_sva_library.sv ${test_name}.sv;
        vsim tb;
        run -all;
        quit -code 0
      \" 2>&1"
      ;;
    *)
      echo -e "  ${YELLOW}[WARN]${NC} Unknown sim tool: ${SIM_TOOL}, using echo"
      SIM_CMD="echo 'VERA_PASS | IP=${test_name} | CHECK=sim_placeholder'"
      ;;
  esac

  # Run simulation
  if eval "${SIM_CMD}" > "${log_file}" 2>&1; then
    local status="PASS"
    echo -e "  ${GREEN}[PASS]${NC} ${test_name}"
  else
    local status="FAIL"
    echo -e "  ${RED}[FAIL]${NC} ${test_name} — see ${log_file}"
  fi

  # Run post-sim Python checkers if VERA config exists
  if [[ -f "${VERA_CFG}" ]]; then
    local spec_yaml
    spec_yaml=$(python3 -c "
import yaml
with open('${VERA_CFG}') as f:
  cfg = yaml.safe_load(f)
tests = cfg.get('tests', {})
print(tests.get('${test_name}', {}).get('spec', ''))
" 2>/dev/null || echo "")

    if [[ -n "${spec_yaml}" && -f "${spec_yaml}" ]]; then
      local csv_data="${test_dir}/sim_data.csv"
      if [[ -f "${csv_data}" ]]; then
        echo -e "  ${CYAN}[VERA]${NC} Running post-sim Python checkers..."
        python3 core/python/vera_postsim_engine.py \
          --spec "${spec_yaml}" \
          --data "${csv_data}" \
          --report "${vera_out/.json/_postsim.json}" || true
      fi
    fi
  fi

  echo "${test_name},${status},${vera_out}" >> \
    "${OUTPUT_DIR}/${RUN_ID}/test_results.csv"
}

# --- Aggregate Reports ---
aggregate_reports() {
  local agg_path="${OUTPUT_DIR}/${RUN_ID}/vera_aggregate_report.json"
  
  echo -e "\n  ${CYAN}Aggregating VERA reports...${NC}"
  
  python3 - <<PYEOF
import json, os, glob
from datetime import datetime

run_dir = "${OUTPUT_DIR}/${RUN_ID}"
json_files = glob.glob(f"{run_dir}/vera_json/*.json")
all_results = []
total_pass = total_fail = total_warn = 0

for jf in sorted(json_files):
    try:
        with open(jf) as f:
            rpt = json.load(f)
        summary = rpt.get("vera_report", {}).get("summary", {})
        total_pass += summary.get("pass", 0)
        total_fail += summary.get("fail", 0)
        total_warn += summary.get("warning", 0)
        results = rpt.get("vera_report", {}).get("results", [])
        all_results.extend(results)
    except Exception as e:
        print(f"  [VERA] Warning: Could not parse {jf}: {e}")

agg = {
    "vera_aggregate_report": {
        "run_id": "${RUN_ID}",
        "timestamp": datetime.now().isoformat(),
        "summary": {
            "total_checks": len(all_results),
            "pass": total_pass,
            "fail": total_fail,
            "warning": total_warn,
            "pass_rate": f"{100*total_pass/max(len(all_results),1):.1f}%"
        },
        "failures": [r for r in all_results if r.get("status") == "FAIL"],
        "all_results": all_results
    }
}

with open("${agg_path}", "w") as f:
    json.dump(agg, f, indent=2)

print(f"  Aggregate report: ${agg_path}")
print(f"\n  {'='*50}")
print(f"  VERA REGRESSION SUMMARY")
print(f"  Total Checks : {len(all_results)}")
print(f"  PASS         : {total_pass}")
print(f"  FAIL         : {total_fail}")
print(f"  WARNING      : {total_warn}")
print(f"  Pass Rate    : {100*total_pass/max(len(all_results),1):.1f}%")
print(f"  {'='*50}\n")

if total_fail > 0:
    print(f"  FAILURES:")
    for f in [r for r in all_results if r.get("status") == "FAIL"]:
        print(f"  ✗ {f.get('ip_name')} | {f.get('checker_name')}")
        print(f"    EXP: {f.get('expected')}  ACT: {f.get('actual')}")
PYEOF

  # Generate waveform loaders for failures
  if [[ -f "${agg_path}" ]]; then
    echo -e "  ${CYAN}Generating waveform loaders for failures...${NC}"
    python3 automation/waveform_loader/vera_waveload.py \
      --report "${agg_path}" \
      --fsdb_dir "${OUTPUT_DIR}/${RUN_ID}/waveforms" \
      --tool all \
      --output "${OUTPUT_DIR}/${RUN_ID}/debug_scripts" || true
  fi
}

# --- Main ---
main() {
  vera_banner
  parse_args "$@"
  setup_dirs

  echo -e "\n  ${CYAN}VERA Regression: ${SIM_TOOL^^} | Run: ${RUN_ID}${NC}\n"

  if [[ -z "${TEST_LIST}" ]]; then
    echo "ERROR: --test_list is required"
    exit 1
  fi

  # Initialize results CSV
  echo "test_name,status,vera_report" > "${OUTPUT_DIR}/${RUN_ID}/test_results.csv"

  # Run tests
  local pass_count=0
  local fail_count=0
  
  while IFS= read -r test || [[ -n "${test}" ]]; do
    [[ "${test}" =~ ^#.*$ || -z "${test}" ]] && continue
    run_test "${test}"
    [[ "$?" == "0" ]] && ((pass_count++)) || ((fail_count++))
  done < "${TEST_LIST}"

  aggregate_reports

  # Exit code based on failures
  local total_fail
  total_fail=$(grep -c ",FAIL," "${OUTPUT_DIR}/${RUN_ID}/test_results.csv" 2>/dev/null || echo 0)
  [[ "${total_fail}" -eq 0 ]] && exit 0 || exit 1
}

main "$@"
