# AnalogML — Physics-Backed Multi-Fidelity Neural Models for Analog IC Design

## Overview

AnalogML is a grey-box, physics-informed machine learning framework that learns
the relationship **Y = f(X)** for analog circuits:

| Symbol | Meaning |
|--------|---------|
| **X** | Technology node (180nm, 90nm…), circuit topology (graph), component sizes (W/L, R, C), pin specifications |
| **Y** | AC/DC/Noise/Transient/Thermal/Reliability/Power simulation results |
| **f** | Multi-fidelity, interpretable, physics-backed grey model |

---

## Architecture

```
analogml/
├── parsers/          # Netlist/SPICE/Spectre parsers → graph representation
├── core/             # Graph encoder, feature engineering, physics constraints
├── models/           # NN-ODE, PINN, HamiltonianNN, PySR symbolic regression
├── data/             # Dataset management, multi-fidelity data loaders
├── ui/               # Streamlit dashboard
├── examples/         # OTA, LDO, OpAmp example circuits
├── notebooks/        # Jupyter walkthrough notebooks
└── tests/            # Unit + integration tests
```

---

## Installation

```bash
# 1. Create environment
conda create -n analogml python=3.10
conda activate analogml

# 2. Install dependencies
pip install -r requirements.txt

# 3. (Optional) GPU support
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118
```

---

## Quick Start

### 1. Parse a netlist
```python
from analogml.parsers import SpiceParser
from analogml.core import CircuitGraph

parser = SpiceParser()
netlist = parser.parse("examples/ota_180nm.sp")
graph   = CircuitGraph.from_netlist(netlist, technology="180nm")
```

### 2. Build feature tensor
```python
from analogml.core import FeatureExtractor

fe = FeatureExtractor()
X  = fe.extract(graph)   # topology + sizes + tech + pin specs
```

### 3. Train multi-fidelity model
```python
from analogml.models import AnalogMLModel

model = AnalogMLModel(fidelity_levels=["schematic", "post_layout"])
model.fit(X_train, Y_train, epochs=500)
```

### 4. Predict without simulation
```python
Y_pred = model.predict(X_new)          # full spec vector
model.recommend_sizes(target_specs={   # inverse design
    "gain_db": 60,
    "ugf_hz": 10e6,
    "phase_margin_deg": 60
})
```

### 5. Technology transfer
```python
from analogml.models import TechTransferAgent

agent = TechTransferAgent(source_tech="180nm", target_tech="90nm")
agent.fit(circuits_180nm, circuits_90nm)
X_90nm = agent.transfer(graph_180nm)
```

---

## Running the Dashboard

```bash
streamlit run analogml/ui/dashboard.py
```

---

## Running Examples

```bash
python examples/run_ota_example.py
python examples/run_ldo_example.py
python examples/run_opamp_example.py
```

---

## Running Tests

```bash
pytest tests/ -v
```

---

## Key Design Decisions

| Choice | Rationale |
|--------|-----------|
| **Graph Neural Network** topology encoder | Captures structural connectivity independent of instance/net names |
| **Neural ODE** for transient/AC | Embeds ODE physics structure into dynamics model |
| **PINN** for DC operating point | Enforces KCL/KVL as soft constraints during training |
| **HamiltonianNN** for power/energy | Conserves energy by construction |
| **PySR symbolic regression** | Extracts human-readable equations from learned representations |
| **Multi-fidelity GP meta-learner** | Bridges schematic-level (fast) to post-layout (slow) fidelity |

---

## Citation / License

MIT License. See LICENSE.
