# INSTRUCTIONS — Surrogate Framework

## 1. Project Structure

```
surrogate_framework/
├── main.py                            # CLI orchestrator — single entry point
├── torch_shim.py                      # NumPy-based torch-compatible shim
├── requirements.txt                   # pip dependencies
├── README.md                          # Quick-start overview
├── INSTRUCTIONS.md                    # This file
├── digitwin/                          # Vendored digiTwin BLUT (v7) support
│   ├── blut_format.py                 # Vendored verbatim: binary format (source of truth)
│   ├── blut_reader_core.py            # Vendored core read API (open_blut, decode, resolve_requests)
│   ├── blut_reader_ext.py             # NEW: bulk matrix access, $flow classification, multi-run iteration
│   └── spec_signal_map.py             # SpecKG <-> BLUT signal-name resolver (SignalMap)
├── configs/
│   ├── ldo_spec.json                  # Editable LDO spec (no Python needed)
│   ├── LDO_1V2.json                   # 1.2V LDO spec matching the blut_files/regression*.bin testbench
│   ├── signal_map_ldo.json            # SpecKG <-> SREF_LDO1V2_LP_TB.* map for regression*.bin
│   └── ota_spec.json                  # Editable OTA spec
│                                       #   (specs may optionally carry a "signal_map" block)
├── core/
│   ├── spec_kg/
│   │   └── knowledge_graph.py         # SpecKG class + IP builders + signal_map field
│   ├── fsm/
│   │   ├── signal_capture.py          # Waveform loader + classifier + load_from_blut()
│   │   ├── state_detector.py          # Three-strategy FSM detector
│   │   ├── transition_learner.py      # Decision-tree guard learning + boundary_mask
│   │   └── fsm_codegen.py             # Verilog-A + SV emitter + FSMValidator
│   ├── models/
│   │   ├── pinn.py                    # CircuitPINN
│   │   ├── neural_ode.py              # CircuitNeuralODE
│   │   └── gpr_surrogate.py           # CircuitGPR + ModelSelector
│   ├── interpretability/
│   │   └── symbolic_regression.py     # PySR wrapper + pole-zero + SHAP
│   └── phases/
│       ├── phase1_spec_based.py       # Spec-only Verilog-A/SV generator
│       ├── phase2_sim_augmented.py    # PINN/NODE/GPR trainer + build_dataset_from_blut()
│       ├── phase3_silicon.py          # Silicon calibration + GapODE
│       └── blut_reference.py          # digiTwin as state-transition reference/filler
├── data/
│   └── pipeline.py                    # LHS generator + SPICE CSV parser
├── examples/
│   ├── example1_ldo_full.py           # LDO Phase1 + FSM + Phase2
│   ├── example2_ota_csv.py            # OTA CSV + model comparison
│   ├── example3_silicon.py            # Phase3 silicon calibration
│   └── example4_blut_pipeline.py      # Full BLUT -> FSM -> Phase2 -> Verilog-A walkthrough
├── tests/
│   └── test_framework.py              # ≥41 tests (29 original + ≥12 BLUT ingestion tests)
└── output/                            # All generated files land here
```

---

## 2. Installation

### Minimum (NumPy shim mode — no PyTorch needed)

```bash
uv pip install numpy scipy pandas scikit-learn networkx matplotlib
```

### Full (with all optional libraries)

```bash
uv pip install numpy scipy pandas scikit-learn networkx matplotlib torch pysr shap wandb
```

### Optional extras

| Library     | Purpose                            | Fallback behaviour                    |
|-------------|------------------------------------|---------------------------------------|
| `torch`     | PINN / Neural ODE training         | NumPy shim — models run as NumPy MLP  |
| `pysr`      | Symbolic regression                | Linear regression (`numpy.linalg.lstsq`) |
| `shap`      | Feature attribution                | Numerical Jacobian                    |
| `torchdiffeq` | ODE integration               | Euler integration in `CircuitNeuralODE` |
| `wandb`     | Experiment logging                 | Logging skipped silently              |

### Verify installation

```bash
python tests/test_framework.py
```

Expected: `Results: 41/41 passed`

---

## 3. Quick Start

Three commands that produce visible output within 60 seconds:

```bash
# 1. Generate synthetic LDO data CSV
python main.py --ip_type LDO --export_data --n_samples 200

# 2. Run Phase 1 code generation
python main.py --ip_type LDO --phase 1

# 3. Run full pipeline with FSM + training
python main.py --ip_type LDO --phase 1,fsm,2 --epochs 50 --n_samples 150
```

---

## 4. CLI Switches Reference

| Switch              | Type    | Default      | Description                                                     |
|---------------------|---------|--------------|-----------------------------------------------------------------|
| `--ip_type`         | str     | **required** | `LDO` \| `OTA` \| `DCDC` — selects built-in KG builder         |
| `--phase`           | str     | `1`          | `1` \| `fsm` \| `2` \| `3` \| `all` \| comma-list             |
| `--model`           | str     | `PINN,GPR`   | `PINN` \| `NODE` \| `GPR` \| `all` \| comma-list              |
| `--bridges`         | str     | `AC,PSRR,DC` | Bridge keys; `all` enables all 7; `none` disables all           |
| `--fsm_strategy`    | str     | `hybrid`     | `logic` \| `cluster` \| `hybrid`                               |
| `--fsm_tree_depth`  | int     | `4`          | Max depth of transition guard decision tree                     |
| `--data_csv`        | str     | `None`       | Path to SPICE training CSV; if None → synthetic                 |
| `--sim_csv`         | str     | `None`       | Path to transient waveform CSV for FSM; if None → synthetic     |
| `--silicon_csv`     | str     | `None`       | Path to silicon measurements CSV; if None → demo data           |
| `--spec_json`       | str     | `None`       | Load specKG from JSON; if None → built-in builder               |
| `--blut_path`       | str     | `None`       | Path to digiTwin `.blut` file; if given, Phase 2/FSM read from it instead of synthetic/CSV data |
| `--blut_run_id`     | str     | `None`       | Restrict BLUT ingestion to one run; if None → ALL runs used      |
| `--signal_map_json` | str     | `None`       | Standalone JSON with `"signal_map"` array; falls back to `--spec_json`'s embedded map, then raw BLUT names |
| `--blut_input_signals` | str  | `None`       | Comma-separated SpecKG input names for BLUT Phase 2 (e.g. `VIN,EN`); required with `--blut_path` for Phase 2 |
| `--blut_output_signals` | str | `None`      | Comma-separated SpecKG output names for BLUT Phase 2 (e.g. `VOUT,IOUT`); required with `--blut_path` for Phase 2 |
| `--export_data`     | flag    | off          | Generate synthetic CSV and exit immediately                     |
| `--n_samples`       | int     | `300`        | LHS sample count for synthetic data                             |
| `--include_transient` | flag  | off          | Add transient trajectories for NODE training                    |
| `--n_points`        | int     | `1000`       | Time points in synthetic signal capture                         |
| `--t_end`           | float   | `100e-6`     | Simulation end time for signal capture (seconds)                |
| `--epochs`          | int     | `150`        | Training epochs for PINN and NODE                               |
| `--silicon_epochs`  | int     | `200`        | Epochs for gap correction ODE fitting                           |
| `--seed`            | int     | `42`         | Random seed                                                     |
| `--save_kg`         | flag    | off          | Export specKG JSON to output directory                          |
| `--use_wandb`       | flag    | off          | Enable W&B logging (gracefully skipped if wandb not installed)  |
| `--output_dir`      | str     | `output`     | Root output directory                                           |

---

## 5. Input Formats

### Data CSV (`--data_csv`)

Training data from SPICE simulator. Must have named columns matching the IP feature list.

**LDO columns:**

| Column        | Unit   | Description              |
|---------------|--------|--------------------------|
| `Vin`         | V      | Input voltage            |
| `Iload`       | A      | Load current             |
| `Temp`        | °C     | Temperature              |
| `Process`     | int    | Process corner (encoded) |
| `W_pass`      | m      | Pass transistor width    |
| `Cc`          | F      | Compensation capacitor   |
| `Rf1`         | Ω      | Feedback resistor 1      |
| `Rf2`         | Ω      | Feedback resistor 2      |
| `Vout`        | V      | Output voltage (target)  |
| `PSRR_1kHz`   | dB     | PSRR at 1 kHz            |
| `PSRR_1MHz`   | dB     | PSRR at 1 MHz            |
| `Phase_Margin`| deg    | Phase margin             |
| `Quiescent_I` | mA     | Quiescent current        |
| `Noise_uVrms` | µVrms  | Output noise             |
| `Dropout_V`   | V      | Dropout voltage          |
| `Load_Reg_mV` | mV     | Load regulation          |

**Example rows:**
```
Vin,Iload,Temp,Process,W_pass,Cc,Rf1,Rf2,Vout,PSRR_1kHz,...
3.3,0.1,27,2,500e-6,10e-12,100e3,100e3,1.800,80.2,...
5.0,0.3,-40,0,800e-6,22e-12,120e3,80e3,1.798,74.1,...
```

**Process Encoding:**

| Corner | Code |
|--------|------|
| SS     | 0    |
| SF     | 1    |
| TT     | 2    |
| FS     | 3    |
| FF     | 4    |

### Sim CSV (`--sim_csv`)

Transient waveform CSV for FSM derivation. Must have a `time` column plus any signal columns matching specKG port names.

```
time,VOUT,ILOAD,EN,POK,FAULT
0.0,0.0,0.1,0,0,0
1e-7,0.05,0.1,1,0,0
...
```

### Silicon CSV (`--silicon_csv`)

Silicon measurement data for Phase 3 calibration.

```
chip_id,pvt_corner,temperature,vdd,Output_Voltage,PSRR_1kHz,Phase_Margin
chip_000_TT,TT,27,1.8,1.802,78.5,61.2
chip_001_SS,SS,-40,1.62,1.795,72.1,58.9
```

---

## 6. Phase-by-Phase Guide

### Phase 1 — Spec-based code generation

```bash
# LDO Phase 1 only
python main.py --ip_type LDO --phase 1

# OTA with custom spec JSON
python main.py --ip_type OTA --phase 1 --spec_json configs/ota_spec.json


# Save specKG JSON as well
python main.py --ip_type LDO --phase 1 --save_kg
```

Outputs: `output/ldo_phase1.vams`, `output/ldo_phase1.sv`

### FSM Auto-Derivation

```bash
# FSM only with synthetic signals
python main.py --ip_type LDO --phase fsm

# FSM with custom waveform CSV
python main.py --ip_type LDO --phase fsm --sim_csv my_waveforms.csv

# Change strategy and tree depth
python main.py --ip_type LDO --phase fsm --fsm_strategy logic --fsm_tree_depth 3

# Increase signal resolution
python main.py --ip_type LDO --phase fsm --n_points 5000 --t_end 200e-6
```

Outputs: `output/ldo_fsm.vams`, `output/ldo_fsm.sv`

### Phase 2 — Sim-augmented training

```bash
# PINN + GPR with default bridges
python main.py --ip_type LDO --phase 2 --epochs 200

# GPR only, all bridges
python main.py --ip_type LDO --phase 2 --model GPR --bridges all

# NODE training with transient data
python main.py --ip_type LDO --phase 2 --model NODE --include_transient

# Load SPICE CSV, train PINN only
python main.py --ip_type LDO --phase 2 --data_csv my_spice.csv --model PINN

# All models
python main.py --ip_type LDO --phase 2 --model all --epochs 300
```

Outputs: `output/ldo_phase2.vams`, model MSE comparison table

### Section 6b — BLUT-Sourced Training

Phase 2 (and FSM auto-derivation) can train directly from a digiTwin BLUT
(`.blut`) file instead of synthetic data or a single CSV. A `.blut` file
may contain multiple runs (corners, seeds, line/load-transient sweeps);
by default **all runs are used** — omit `--blut_run_id` to train across
every run in the file.

**Signal mapping.** Real BLUT signal names use full hierarchy paths
(`top.u1.vout`), not SpecKG's short port names (`VOUT`). A `signal_map`
bridges the two — either as a standalone JSON file (`--signal_map_json`)
or embedded in `--spec_json` under a top-level `"signal_map"` key:

```json
"signal_map": [
  {"speckg_name": "VIN",  "blut_signal": "top.u1.vin",  "kind": "voltage"},
  {"speckg_name": "VOUT", "blut_signal": "top.u1.vout", "kind": "voltage"},
  {"speckg_name": "EN",   "blut_signal": "top.u1.en",   "kind": "voltage"},
  {"speckg_name": "IOUT", "blut_signal": "top.u1.vout", "kind": "current"}
]
```

Note `VOUT`/`IOUT` above: the same BLUT base name can map twice under
different `kind`s when the design exports both a voltage node and its
`$flow`-suffixed current probe (e.g. `top.u1.vout` and
`top.u1.vout$flow`) — `kind` disambiguates which is which.

**FSM auto-derivation from BLUT:**

```bash
# FSM across ALL runs in the file
python main.py --ip_type LDO --phase fsm \
    --blut_path regression.blut --spec_json configs/ldo_spec_with_map.json

# FSM restricted to one run
python main.py --ip_type LDO --phase fsm \
    --blut_path regression.blut --blut_run_id corner_ff_125c \
    --spec_json configs/ldo_spec_with_map.json

# Bundled 1.2V LDO regression example (spec + signal map included)
python main.py --ip_type LDO --phase fsm --fsm_strategy logic \
    --spec_json configs/LDO_1V2.json \
    --signal_map_json configs/signal_map_ldo.json \
    --blut_path blut_files/regression1.bin
```

The signal map matters for FSM quality: mapped SpecKG port names carry
`domain`/`fsm_role` metadata, which (a) pins digital-vs-analog
classification for the mapped nets, (b) restricts the FSM state space to
the spec's FSM-relevant ports instead of every rail-to-rail testbench
net, and (c) names the detected states (DISABLED/STARTUP/REGULATION/...)
from the enable/ready/fault roles. Unmapped captures still work, but
fall back to waveform heuristics and generic STATE_N names.

**Port directions (causality).** Each port's direction comes from an
explicit `"direction"` field in the spec JSON (`input`/`output`/`inout`)
or, when absent, is derived from `port_type`: `output`/`status` ⇒
output; `supply`/`ground`/`bulk`/`inout` ⇒ inout; everything else ⇒
input. Only digital **input/inout** ports can become state variables and
guard features. Digital **output/status** ports (e.g. a ready or fault
indicator like `EN_UVLO_1V2`) are summarized per detected state as
**output signatures** (printed as a table by the fsm phase), refine the
state naming (an enabled state with an asserted ready indicator is
REGULATION-family), are emitted as driven `output` pins in the
Verilog-A, and feed the completeness gap report's output-consistency
check — they never appear in guards.

#### FSM from BLUT via CLI (example7)

`examples/example7_fsm_blut_cli.py` runs the exact bundled command above
through `main.build_parser()` + `main.run_fsm_phase()` (imported, not
shelled out — the example and the CLI cannot drift), then verifies that
no output-direction pin appears in any guard, and finishes with the
Capability-B completeness evaluation and customer gap report
(including output-consistency rows):

```bash
uv run examples/example7_fsm_blut_cli.py
# options: --blut PATH (default blut_files/regression1.bin; a v8
#          stand-in covering every signal_map entry is generated if the
#          file is missing), --output_dir DIR
```

Artifacts: `output/ldo_fsm.vams`, `output/ldo_fsm.sv`,
`output/gap_report_cli.md` (+ `.json`).

**Phase 2 training from BLUT** (requires `--blut_input_signals` and
`--blut_output_signals`, comma-separated SpecKG-native names; either
voltage or current names, mixed freely):

```bash
# Train PINN+GPR on every run in the file, joint voltage+current output
python main.py --ip_type LDO --phase 2 \
    --blut_path regression.blut \
    --blut_input_signals VIN,EN \
    --blut_output_signals VOUT,IOUT \
    --signal_map_json configs/ldo_signal_map.json \
    --epochs 200

# Combine with FSM in one run
python main.py --ip_type LDO --phase fsm,2 \
    --blut_path regression.blut \
    --blut_input_signals VIN,EN \
    --blut_output_signals VOUT,IOUT \
    --spec_json configs/ldo_spec_with_map.json
```

`--signal_map_json` takes priority over a `signal_map` embedded in
`--spec_json`; if neither is given, BLUT ingestion falls back to raw BLUT
signal names and prints an unmapped-name warning (once) rather than
silently mismatching.

**Stimulus-conditioning.** Each run's `RunMeta.meta` string (e.g.
`"corner=ff,temp=125"`) is automatically parsed and appended as extra
input columns (`meta_corner`, `meta_temp`, ...) so the trained surrogate
is conditioned on which stimulus/corner produced each row, rather than
corner-blind.

**Physics loss activation.** When `--blut_output_signals` includes
voltage/current names that match the IP's physics rules (e.g. `VIN`,
`Dropout_Voltage`, `VOUT` for an LDO's KVL rule), the existing KCL/KVL
physics loss terms activate automatically — no extra flag needed.

**Using digiTwin as a state-transition reference.** See
`examples/example4_blut_pipeline.py` for a full demonstration of pulling a
BLUT ground-truth waveform segment for a thinly-trained FSM state
(`core.phases.blut_reference.fill_missing_state_transient`) and comparing
it against the trained surrogate's output for that state.

Outputs: same as Phase 1/FSM/Phase 2 above, plus per-run provenance
(`run_ids`, `run_meta`) available on the returned dataset dict for
debugging which run contributed which training row.

### Phase 3 — Silicon calibration

```bash
# Demo silicon data (auto-generated)
python main.py --ip_type LDO --phase 3

# Custom silicon CSV
python main.py --ip_type LDO --phase 3 --silicon_csv silicon_measurements.csv

# More training epochs for gap ODE
python main.py --ip_type LDO --phase 3 --silicon_epochs 500
```

Outputs: `output/ldo_phase3.vams`, `output/gap_report.json`, `output/device_insights.json`

### Full Pipeline

```bash
# All phases, all models
python main.py --ip_type LDO --phase all --model all --epochs 200

# All phases, production run
python main.py --ip_type LDO --phase all \
    --model PINN,GPR \
    --bridges AC,PSRR,DC \
    --fsm_strategy hybrid \
    --n_samples 500 \
    --epochs 300 \
    --silicon_epochs 300 \
    --seed 42 \
    --save_kg \
    --output_dir output/ldo_production
```

---

## 7. Customisation Guide

### Adding a New IP Type (4 steps)

**Step 1 — Add to `PARAM_SPACES` in `data/pipeline.py`:**

```python
PARAM_SPACES["MYIP"] = {
    "features": ["Vin", "Iload", "Temp", "Process", "W1", "C1"],
    "outputs": ["Vout", "Efficiency", "Phase_Margin"],
    "bounds": {
        "Vin": (1.8, 5.5),
        "Iload": (0.01, 1.0),
        "Temp": (-40.0, 125.0),
        "Process": (0.0, 4.0),
        "W1": (10e-6, 500e-6),
        "C1": (1e-12, 100e-12),
    },
}
```

**Step 2 — Add `_compute_myip` method to `SyntheticDataGenerator`:**

```python
def _compute_myip(self, X, col, n):
    Vin = col("Vin")
    # Physics-realistic equations
    Vout = Vin * 0.9 + np.random.randn(n) * 0.01
    Eff = 90 - 0.1 * col("Temp") + np.random.randn(n) * 1
    PM = 55 + np.random.randn(n) * 3
    return np.column_stack([Vout, Eff, PM])
```

**Step 3 — Add `build_myip_kg()` to `core/spec_kg/knowledge_graph.py`:**

```python
def build_myip_kg() -> SpecKG:
    kg = SpecKG(ip_type="MYIP")
    kg.add_port(Port("VIN", "supply", "power", (1.8, 5.5), (0, 2)))
    kg.add_port(Port("VOUT", "output", "analog", (0.5, 5.0), (0, 1)))
    kg.add_spec(SpecConstraint("dc", "Output_Voltage", 1.75, 1.85, 1.80, "V"))
    kg.add_physics_rule(PhysicsRule("KVL", ["VIN", "VOUT"], "V_vin - V_vout = 0"))
    kg.fsm_states = ["DISABLED", "STARTUP", "ACTIVE", "FAULT"]
    return kg
```

**Step 4 — Register in `main.py` builder dict:**

```python
# In _build_kg():
from core.spec_kg.knowledge_graph import build_myip_kg

builders = {
    "LDO": build_ldo_kg,
    "OTA": build_ota_kg,
    "DCDC": build_dcdc_kg,
    "MYIP": build_myip_kg,  # ← add this line
}
```

Then add `'MYIP'` to the `choices` list in `build_parser()`:
```python
p.add_argument('--ip_type', choices=['LDO','OTA','DCDC','MYIP'], ...)
```

---

## 8. Output Files Reference

```
output/
├── ldo_phase1.vams              # Phase 1 Verilog-A behavioural model
├── ldo_phase1.sv                # Phase 1 SystemVerilog FSM
├── ldo_fsm.vams                 # Auto-derived FSM Verilog-A
├── ldo_fsm.sv                   # Auto-derived FSM SystemVerilog
├── ldo_phase2.vams              # Phase 2 calibrated Verilog-A
│                                #   (includes symbolic equation comments)
├── ldo_phase3.vams              # Phase 3 silicon-calibrated Verilog-A
│                                #   (includes Gm/Ro/C correction factors)
├── ldo_speckg.json              # SpecKG export (with --save_kg)
├── ldo_synthetic.csv            # Synthetic training data (with --export_data)
├── gap_report.json              # Per-chip, per-spec gap analysis
└── device_insights.json         # PDK parameter suggestions (u0, lambda, CGDO)
```

Each `.vams` file is a self-contained Verilog-A module importable into Cadence Virtuoso,  
Spectre, or any VerilogAMS simulator. The `.sv` files target any IEEE 1800 compliant simulator.

---

## 9. Troubleshooting

| Problem | Likely Cause | Fix |
|---------|-------------|-----|
| `ModuleNotFoundError: torch` | PyTorch not installed | Run `import torch_shim` before other imports, or `uv pip install torch` |
| `[torch_shim] running with NumPy shim` | PyTorch absent (expected) | Normal behaviour — shim covers all functionality |
| `AssertionError: Expected ≥4 ports` in tests | specKG builder import error | Run `python -c "from core.spec_kg.knowledge_graph import build_ldo_kg; print(build_ldo_kg())"` |
| GPR fit very slow | Large dataset + many restarts | Reduce `--n_samples` or add `--model GPR` (skip PINN) |
| FSM detects only 1 state | All logic signals constant | Use `--fsm_strategy cluster` or check CSV signal ranges |
| Phase 2 MSE = 0.0 (NODE) | No transient data | Add `--include_transient` flag |
| `KeyError: 'X'` in Phase 2 | CSV column mismatch | Check that CSV headers match `PARAM_SPACES` feature list exactly |
| Verilog-A simulation fails | Missing `disciplines.vams` | Add `include_path` in simulator pointing to VerilogAMS library |
| `silicon_csv` columns not found | Non-standard column names | Ensure columns match spec names from `--spec_json` |
| `[SignalMap] WARNING: N SpecKG name(s) have no BLUT signal mapping` | No `signal_map` provided, or names don't match | Add a `"signal_map"` block (see Section 6b) mapping each `Port`/`SpecConstraint` name to its real BLUT signal name; check `kind` ("voltage"/"current") matches how the signal was exported ($flow suffix = current) |
| BLUT Phase 2 raises `ValueError: --blut_path requires ...` | `--blut_input_signals`/`--blut_output_signals` omitted | Supply both as comma-separated SpecKG-native names, e.g. `--blut_input_signals VIN,EN --blut_output_signals VOUT,IOUT` |
| FSM finds a transition exactly at a run boundary that looks wrong | `boundary_mask` not applied (only auto-applied when `--blut_path` is used) | Confirm you're loading via `SignalCapture.load_from_blut` / `--blut_path`, not `--sim_csv`, so `get_boundary_mask()` is populated and passed to `TransitionLearner.learn` |
| `Results: N/41 passed` < 41 | Dependency or import error, or a digiTwin BLUT test failure | Run `uv pip install scikit-learn networkx`; if a `test_blut_*` or `test_signal_map_*` test fails, confirm `digitwin/blut_format.py` imports cleanly (`python -c "import digitwin.blut_format"`) |

## 10. Commands used
<<<<<<< HEAD
uv run examples/example11_corner_conditioned_phase2.py --correlation_json output_fsm_correlation_2/per_corner_correlation.json --blut_path blut_files/regression_multi_corner_sref_ldo.bin --signal_map_json configs/signal_map_ldo.json --fsm_strategy hybrid --fsm_tree_depth 4 --ip_type LDO --blut_input_signals VPWR,VREF,FUN_DC,VDD_1V2_EXT,V_SUPPLY --blut_output_signals VDD_1V2,VPWR_I,FUN_DC_I,V_SUPPLY_I,VDD_1V2_EXT_I --models gpr,smt --min_state_sample 30 --output_dir output_phase2_1
=======
uv run examples/example11_corner_conditioned_phase2.py --correlation_json output_fsm_correlation_2/per_corner_correlation.json --blut_path blut_files/regression_multi_corner_sref_ldo.bin --signal_map_json configs/signal_map_ldo.json --fsm_strategy hybrid --fsm_tree_depth 4 --ip_type LDO --blut_input_signals VPWR,VREF,FUN_DC,VDD_1V2_EXT,V_SUPPLY --blut_output_signals VDD_1V2,VPWR_I,FUN_DC_I,V_SUPPLY_I,VDD_1V2_EXT_I --models gpr,smt --min_state_sample 30 --output_dir output_phase2_1
>>>>>>> 7928143 (updated code to add pinn, pysr and slowness)
