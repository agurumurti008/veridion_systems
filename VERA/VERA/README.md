# VERA — Verification Engine for Runtime & Autonomous Checking
## Complete Checker Network Intelligence Ecosystem

> *"No waveform should ever need to be eyeballed. Every failure should explain itself."*

---

## What is VERA?

**VERA** is a comprehensive, layered checker network intelligence ecosystem designed for Digital, Mixed-Signal, and Analog (DMS/AMS) verification environments. It unifies every major checker paradigm available in the IC design and verification industry into a single, portable, auto-buildable framework.

VERA transforms raw simulation data into actionable, pinpointed failure intelligence — replacing manual waveform inspection with automated checking, structured reporting, and guided debug navigation.

---

## Ecosystem Architecture (7 Layers)

```
┌─────────────────────────────────────────────────────────────────┐
│  LAYER 7 │ VERA Dashboard — Unified Reporting & Debug Navigator │
├─────────────────────────────────────────────────────────────────┤
│  LAYER 6 │ Waveform Loader & Debug Accelerator (VCD/FSDB/SHM)  │
├─────────────────────────────────────────────────────────────────┤
│  LAYER 5 │ Post-Sim Intelligence (Python/MATLAB/Pandas)        │
├─────────────────────────────────────────────────────────────────┤
│  LAYER 4 │ AMS Checkers (SKILL-embedded, Spectre callbacks)     │
├─────────────────────────────────────────────────────────────────┤
│  LAYER 3 │ Runtime Checkers (SVA, UVM Scoreboards, OVM)        │
├─────────────────────────────────────────────────────────────────┤
│  LAYER 2 │ Auto-Builder (Datasheet Parser + Param Generator)   │
├─────────────────────────────────────────────────────────────────┤
│  LAYER 1 │ Checker Library (Templates per IP/Block type)        │
└─────────────────────────────────────────────────────────────────┘
```

---

## Directory Structure

```
VERA/
├── README.md                          ← This file
├── VERA_MASTER_GUIDE.md               ← Complete knowledge base
├── docs/
│   ├── checker_taxonomy.md            ← All checker types & when to use
│   ├── industry_reference.md          ← Standards, papers, methodologies
│   ├── integration_guide.md           ← EDA tool integration (Cadence/Synopsys/Mentor)
│   └── roadmap.md                     ← Phased implementation plan
├── core/
│   ├── sv/                            ← SystemVerilog interface checkers
│   ├── uvm/                           ← UVM Scoreboards, monitors, predictor
│   ├── sva/                           ← SVA assertion library
│   ├── python/                        ← Post-sim Python checkers
│   ├── matlab/                        ← MATLAB/Simulink-based checkers
│   └── skill/                         ← SKILL/OCEAN AMS checkers
├── automation/
│   ├── builder/                       ← Auto-checker generation from datasheets
│   ├── reporter/                       ← Standardized VERA report engine
│   ├── waveform_loader/               ← Automated waveform loader for failures
│   └── tb_gen/                        ← IP-level TB generation hooks
├── templates/
│   ├── digital/                       ← Digital IP checker templates
│   ├── analog/                        ← Analog block checker templates
│   └── mixed_signal/                  ← Mixed-signal checker templates
├── examples/
│   ├── adc/                           ← ADC checker example (ENOB, DNL, INL)
│   ├── pll/                           ← PLL checker (lock time, jitter, frequency)
│   ├── uart/                          ← UART protocol checker
│   └── sar_adc/                       ← SAR ADC full checker suite
└── scripts/
    ├── integration/                   ← EDA integration scripts
    └── regression/                    ← Regression runner with VERA hooks
```

---

## Quick Start

### 1. Auto-Build Checkers from a Datasheet Parameter File
```bash
python3 automation/builder/vera_builder.py \
  --spec examples/adc/adc_spec.yaml \
  --ip_type adc \
  --env ams \
  --output_dir output/adc_checkers/
```

### 2. Run Regression with VERA Hooks
```bash
./scripts/regression/vera_regression.sh \
  --sim xcelium \
  --test_list tests/adc_tests.list \
  --vera_cfg cfg/vera_config.yaml
```

### 3. Launch VERA Dashboard
```bash
python3 automation/reporter/vera_dashboard.py \
  --results_dir results/ \
  --port 8080
```

### 4. Generate Waveform Loader for Failures
```bash
python3 automation/waveform_loader/vera_waveload.py \
  --report results/vera_report.json \
  --tool simvision \
  --fsdb_dir sim_outputs/
```

---

## Supported Environments

| Environment | Checker Types Supported |
|-------------|------------------------|
| Xcelium (Cadence) | SVA, SV, UVM, SKILL callbacks |
| VCS (Synopsys) | SVA, SV, UVM, Python co-sim |
| Questa (Siemens) | SVA, SV, UVM, do-file automation |
| Spectre (Cadence) | OCEAN/SKILL, Verilog-A monitors |
| HSPICE (Synopsys) | Measure statements, Python post |
| MATLAB/Simulink | Post-sim, reference model compare |
| Custom Python | Universal post-processing |

---

## Naming & Versioning
- Ecosystem Name: **VERA** (Verification Engine for Runtime & Autonomous checking)
- Version: 1.0.0
- License: Internal / Proprietary
- Contact: Your Verification Team
