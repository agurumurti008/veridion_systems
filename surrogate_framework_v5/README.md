 # Surrogate Behavioural Model Development Platform

A production-ready, end-to-end platform for developing surrogate behavioural models of analog, mixed-signal, and digital-mixed-signal semiconductor IPs — backed by a Specification Knowledge Graph (SpecKG).

## Features

- **SpecKG Engine** — NetworkX-backed knowledge graph encoding ports, specs, physics rules, and FSM states
- **FSM Auto-Derivation** — Three-strategy (logic / cluster / hybrid) automatic FSM extraction from waveform data
- **Physics-Informed Neural Network (PINN)** — Differentiable KCL/KVL/energy constraints as loss terms
- **Neural ODE** — Averaged-model physics + residual network for transient simulation
- **Gaussian Process Regression (GPR)** — Matérn kernel surrogate with active learning
- **Symbolic Regression** — PySR-based equation extraction with SHAP attribution
- **Three-Phase Workflow** — Spec-only → Sim-augmented → Silicon-calibrated
- **digiTwin BLUT Ingestion** — Train directly from multi-run BLUT files (corners/seeds/transients), with automatic run-boundary-aware FSM detection, `$flow`-suffix current classification, and SpecKG signal-name mapping
- **Code Generation** — Syntactically valid Verilog-A (.vams) and SystemVerilog (.sv)
- **Zero hard dependencies on PyTorch** — Full NumPy shim fallback

## Quick Start

```bash
# Install dependencies
uv pip install numpy scipy pandas scikit-learn networkx matplotlib

# Phase 1: Generate spec-based Verilog-A/SV
python main.py --ip_type LDO --phase 1

# Phase 1 + FSM + Phase 2
python main.py --ip_type LDO --phase 1,fsm,2 --epochs 100

# Full pipeline
python main.py --ip_type LDO --phase all
```

## Supported IP Types

| IP   | Physics Rules | FSM States | Features | Outputs |
|------|--------------|------------|----------|---------|
| LDO  | KCL, KVL, energy, feedback | 6 | 8 | 8 |
| OTA  | KCL, GBW, SR, CMRR | 5 | 8 | 8 |
| DCDC | Energy, KVL, CCM/DCM | 6 | 7 | 5 |

## Project Structure

```
surrogate_framework/
├── main.py                  # CLI orchestrator
├── torch_shim.py            # NumPy-based PyTorch fallback
├── requirements.txt
├── README.md
├── INSTRUCTIONS.md
├── configs/
│   ├── ldo_spec.json        # Editable LDO specification
│   └── ota_spec.json        # Editable OTA specification
├── core/
│   ├── spec_kg/             # SpecKG knowledge graph engine
│   ├── fsm/                 # FSM auto-derivation
│   ├── models/              # PINN, Neural ODE, GPR
│   ├── interpretability/    # Symbolic regression + SHAP
│   └── phases/              # Phase 1/2/3 generators
├── data/
│   └── pipeline.py          # LHS data generator
├── examples/                # Three worked examples
└── tests/
    └── test_framework.py    # ≥28 tests
```

## See INSTRUCTIONS.md for full CLI reference and customisation guide.
