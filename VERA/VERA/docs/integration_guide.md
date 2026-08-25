# VERA Integration Guide
## EDA Tool Setup, Environment Configuration & Verification Flow

---

## 1. Quick Setup Checklist

```bash
# 1. Source environment
source vera_env.sh

# 2. Install Python dependencies
pip3 install numpy scipy pyyaml pandas vcdvcd

# 3. Run EDA integration setup
chmod +x scripts/integration/vera_eda_setup.sh
./scripts/integration/vera_eda_setup.sh

# 4. Build checkers for your IP
python3 automation/builder/vera_builder.py \
  --spec examples/sar_adc/sar_adc_spec.yaml \
  --output output/sar_adc/

# 5. Generate TB skeleton
python3 automation/tb_gen/vera_tb_gen.py \
  --spec examples/sar_adc/sar_adc_spec.yaml \
  --output tb/sar_adc/

# 6. Run regression
./scripts/regression/vera_regression.sh \
  --sim xcelium \
  --test_list tests/adc_tests.list \
  --vera_cfg cfg/vera_config.yaml

# 7. View dashboard
python3 automation/reporter/vera_dashboard.py \
  --results_dir vera_reports/ \
  --output vera_dashboard.html \
  --serve
```

---

## 2. Xcelium (Cadence) Integration

### Compile Command
```bash
xrun \
  -64bit -sv -uvm \
  -f ${VERA_HOME}/scripts/integration/vera_xcelium.f \
  -f your_dut.f \
  -top vera_<ip>_tb_top \
  +UVM_TESTNAME=vera_<ip>_base_test \
  +UVM_VERBOSITY=UVM_MEDIUM \
  +vera_report_path=./vera_reports/vera_report.json \
  -end_run_cmd "${VERA_HOME}/scripts/integration/vera_xcelium_posthook.sh" \
  -define VERA_ENABLE=1
```

### AMS Mode (Xcelium AMS / SimVision)
```bash
xrun \
  -64bit -ams \
  -f ${VERA_HOME}/scripts/integration/vera_xcelium.f \
  -amscell verilog_dut=./netlists/dut.scs \
  -iereport \
  +UVM_TESTNAME=vera_adc_base_test
```

---

## 3. VCS (Synopsys) Integration

```bash
vcs \
  -full64 -sverilog -ntb_opts uvm-1.2 \
  -f ${VERA_HOME}/scripts/integration/vera_vcs.f \
  -f your_dut.f \
  -top vera_<ip>_tb_top \
  -o simv

./simv \
  +UVM_TESTNAME=vera_<ip>_base_test \
  +ntb_random_seed_automatic \
  +vera_report=./vera_reports/vera_report.json
```

---

## 4. Questa (Siemens) Integration

```tcl
# In Questa shell or .do file
do ${VERA_HOME}/scripts/integration/vera_questa.do
vera_run vera_<ip>_base_test
```

---

## 5. Spectre/APS (Cadence AMS) Integration

### .cdsinit Setup
```lisp
; Add to ~/.cdsinit or project .cdsinit
load("/path/to/VERA/core/skill/vera_ams_checkers.il")
```

### OCEAN Post-Sim Script
```bash
ocean -nograph -replay ${VERA_HOME}/scripts/integration/vera_ocean_template.ocn
```

### Verilog-AMS Monitor Instantiation
```spice
// In your AMS testbench netlist
vera_voltage_monitor #(
  .vmin(1.71), .vmax(1.89),
  .ip_name("LDO_1V8"), .node_name("vout")
) u_vera_vout_mon (
  .monitor_node(vout),
  .gnd(gnd)
);
```

---

## 6. New IP Onboarding — Step by Step

### Step 1: Create IP Spec YAML
Copy `examples/sar_adc/sar_adc_spec.yaml` and customize:
```yaml
ip_name:     MY_NEW_IP
ip_type:     adc           # adc|dac|pll|ldo|opamp|uart|spi|fifo|sram|generic
environment: mixed         # dms|ams|mixed

# Add your specs...
adc:
  n_bits: 14
  fs_hz:  5_000_000
  dynamic:
    enob_min: 12.0
```

### Step 2: Auto-Build Checkers
```bash
python3 automation/builder/vera_builder.py \
  --spec my_ip_spec.yaml \
  --output output/my_ip/
```
This generates: `sva/`, `python/`, `skill/` — all checker files.

### Step 3: Auto-Generate TB Skeleton
```bash
python3 automation/tb_gen/vera_tb_gen.py \
  --spec my_ip_spec.yaml \
  --output tb/my_ip/
```
Fill in protocol-specific driver/monitor logic.

### Step 4: Integrate SVA (non-invasive bind)
```systemverilog
// In tb_top or separate bind file
bind my_dut vera_my_ip_param_chk i_vera_bind (
  .clk   (clk),
  .rst_n (rst_n),
  .data_out (data_out)
);
```

### Step 5: Run Simulation + Post-Sim
```bash
# Simulation with VERA SVA + UVM hooks
xrun -f output/my_ip/sva/vera_filelist.f ...

# Post-sim Python checks
python3 core/python/vera_postsim_engine.py \
  --spec my_ip_spec.yaml \
  --data sim_outputs/my_ip_data.csv \
  --report vera_reports/my_ip_report.json
```

### Step 6: View Dashboard
```bash
python3 automation/reporter/vera_dashboard.py \
  --report vera_reports/my_ip_report.json \
  --output vera_reports/my_ip_dashboard.html \
  --serve
```

### Step 7: Debug Failures
```bash
python3 automation/waveform_loader/vera_waveload.py \
  --report vera_reports/my_ip_report.json \
  --tool simvision \
  --output debug_scripts/

# In SimVision:
# source debug_scripts/vera_waveload_simvision.tcl
```

---

## 7. VERA Checker Naming Convention

```
vera_<ip>_<category>_<signal>_<condition>
      │         │          │         │
      │         │          │         └── brief condition (e.g. max, min, valid, stable)
      │         │          └──────────── signal or parameter name
      │         └─────────────────────── category (protocol, parametric, dynamic, static)
      └───────────────────────────────── IP name (lowercase)

Examples:
  vera_uart_protocol_tx_stop_bit
  vera_adc_dynamic_enob_min
  vera_pll_parametric_jitter_rms
  vera_fifo_structural_overflow
  vera_axi4_protocol_aw_deadlock
```

---

## 8. VERA Severity Levels

| Severity | Meaning | Simulation Action |
|----------|---------|-------------------|
| ERROR | Spec violation — test must fail | `$error()` / UVM_ERROR |
| WARNING | Potential issue — degraded margin | `$warning()` / UVM_WARNING |
| INFO | Informational — passed check | `$info()` / UVM_INFO |

---

## 9. Extending VERA

### Add a New IP Type
1. Add entry to `IP_CHECKER_MAP` in `vera_builder.py`
2. Create template in `templates/<type>/`
3. Add generator method to `VERASVAGenerator` or `VERASKILLGenerator`
4. Add spec example in `examples/<type>/<type>_spec.yaml`

### Add a New Checker Type
1. Write checker in `core/sv/` (SVA), `core/python/` (post-sim), or `core/skill/` (AMS)
2. Register in VERA builder for auto-generation
3. Ensure it emits `VERAResultItem`-compatible output

### Custom Reference Models
Extend `vera_transform_scoreboard` in UVM:
```systemverilog
class my_adc_sb extends vera_transform_scoreboard #(.T_IN(analog_item), .T_OUT(code_item));
  virtual function real reference_transform(analog_item in);
    return $floor(in.voltage / vref * (2**n_bits));
  endfunction
endclass
```

---

## 10. Troubleshooting

| Issue | Solution |
|-------|----------|
| `vera_sva_library.sv` not found | Set `VERA_SV_INCDIR` or use `-f vera_xcelium.f` |
| SKILL checkers not loading | Source `vera_cdsinit_snippet.il` in `.cdsinit` |
| Python import error | `pip3 install numpy scipy pyyaml vcdvcd` |
| JSON report empty | Check `VERA_REPORT_DIR` is writable |
| Dashboard not opening | `pip3 install` and check port 8080 is free |
| VCD parsing slow | Use CSV export from simulator instead |

---

*VERA Integration Guide v1.0*
