# AnalogML — Complete User Instructions

## What Is AnalogML?

AnalogML is a **physics-backed, multi-fidelity machine learning framework** for analog IC design.
It learns the relationship **Y = f(X)** where:

- **X** = technology node + circuit topology (graph) + component sizes + pin specifications  
- **Y** = all simulation results: AC, DC, Noise, Transient, Thermal, Reliability, Power  
- **f** = grey-box model (PINN + Neural ODE + Hamiltonian NN + Symbolic Regression + GP)

The goal: **predict simulation results in milliseconds** instead of hours, and **recommend component sizes** to meet target specifications.

---

## Directory Structure

```
analogml/
├── __init__.py               # Top-level imports
├── parsers/__init__.py        # SPICE & Spectre netlist parsers
├── core/
│   ├── __init__.py            # CircuitGraph, FeatureExtractor, build_dataset
│   ├── physics.py             # KCL/KVL, MOSFET models, noise, thermal, reliability
│   └── gnn_trainer.py         # Graph Neural Network trainer
├── models/
│   ├── __init__.py            # AnalogMLModel, TechTransferAgent, PINN, NeuralODE, HamiltonianNN
│   └── analysis_models.py     # AC / DC / Noise / Transient / Thermal / Reliability / Power sub-models
├── data/
│   ├── __init__.py            # SyntheticCircuitDataset, CircuitDataset, MultiFidelityDataset
│   └── export.py              # CSV/JSON export utilities
├── ui/
│   └── dashboard.py           # Streamlit web dashboard
├── examples/
│   ├── ota_180nm.sp           # Example SPICE netlist
│   ├── run_ota_example.py     # Full OTA pipeline
│   ├── run_ldo_example.py     # LDO + multi-fidelity
│   ├── run_opamp_example.py   # OpAmp + multi-analysis
│   └── run_tech_transfer_example.py
├── notebooks/
│   ├── analogml_walkthrough.ipynb
│   └── tech_transfer.ipynb
├── tests/
│   ├── test_analogml.py       # Core unit tests
│   └── test_extended.py       # Physics, analysis, export tests
├── requirements.txt
└── setup.py
```

---

## Installation

### Option A — Minimal (no GPU, no symbolic regression)
```bash
conda create -n analogml python=3.10 -y
conda activate analogml
pip install -r requirements.txt
```

### Option B — Full (with PyTorch PINN + PySR symbolic regression)
```bash
conda create -n analogml python=3.10 -y
conda activate analogml
pip install -r requirements.txt
pip install torch>=2.0.0
pip install pysr>=0.17.0
```

### Option C — GPU (CUDA 11.8)
```bash
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118
```

### Option D — Install as package
```bash
pip install -e .
pip install -e ".[symbolic,gnn]"    # with PySR and PyG
```

---

## Running Examples

```bash
# Activate environment first
conda activate analogml

# 1. OTA — full pipeline (recommended starting point)
python examples/run_ota_example.py

# 2. LDO + multi-fidelity
python examples/run_ldo_example.py

# 3. Two-stage OpAmp — all analysis types
python examples/run_opamp_example.py

# 4. Technology transfer 180nm → 90nm → 65nm
python examples/run_tech_transfer_example.py
```

---

## Running the Dashboard

```bash
streamlit run analogml/ui/dashboard.py
```

Then open **http://localhost:8501** in your browser.

Dashboard features:
- **Model Performance** tab — parity plots, R², training loss curves
- **Predict Specs** tab — slider-based input → instant spec prediction with uncertainty
- **Inverse Design** tab — enter target specs → get recommended component sizes
- **Tech Transfer** tab — Dennard scaling rules + ML-based transfer

---

## Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run only physics tests
pytest tests/test_extended.py::TestPhysics -v

# Run only model tests
pytest tests/test_analogml.py::TestAnalogMLModel -v

# With coverage
pip install pytest-cov
pytest tests/ --cov=analogml --cov-report=term-missing
```

---

## Jupyter Notebooks

```bash
pip install jupyter
jupyter notebook notebooks/
```

Available notebooks:
1. `analogml_walkthrough.ipynb` — end-to-end OTA example with visualizations
2. `tech_transfer.ipynb` — multi-technology knowledge transfer

---

## Using Your Own Netlists

### SPICE format (.sp, .spi, .cir)
```python
from analogml.parsers import SpiceParser
from analogml.core    import CircuitGraph, FeatureExtractor

parser  = SpiceParser()
netlist = parser.parse("your_circuit.sp", technology="180nm")
graph   = CircuitGraph.from_netlist(netlist)
fe      = FeatureExtractor()
X       = fe.extract(graph)   # 117-dim feature vector
```

### Spectre format (.scs)
```python
from analogml.parsers import SpectreParser
parser  = SpectreParser()
netlist = parser.parse("your_circuit.scs", technology="90nm")
```

### CSV from your simulator
Format: columns prefixed `x_` for inputs, `y_` for outputs, optional `technology`.
```python
from analogml.data import CircuitDataset
ds = CircuitDataset("sim_results.csv")
X_tr, Y_tr, X_te, Y_te = ds.train_test_split(test_ratio=0.2)
```

---

## Training a Model

```python
from analogml.models import AnalogMLModel

model = AnalogMLModel(
    mode="fast",          # 'fast' = GBM (no GPU needed) | 'nn' = PINN | 'full' = PINN+symbolic
    output_names=yn       # list of output spec names
)
model.fit(X_train, Y_train,
          X_val=X_val, Y_val=Y_val,
          epochs=300, lr=1e-3, batch_size=32)
```

### Prediction
```python
Y_pred = model.predict(X_new)                              # point estimate
Y_mean, Y_std = model.predict_with_uncertainty(X_new)      # with GP uncertainty
```

### Inverse Design
```python
x_best = model.recommend_sizes(
    target_specs={"gain_dB": 65, "ugf_MHz": 15, "phase_margin_deg": 60},
    X_candidates=X_train    # search over training space
)
```

### Save / Load
```python
model.save("saved_model/")
model = AnalogMLModel.load("saved_model/")
```

---

## Multi-Analysis Models

```python
from analogml.models.analysis_models import MultiAnalysisPredictor

pred = MultiAnalysisPredictor(
    analysis_types=["ac", "dc", "noise", "transient", "thermal", "reliability", "power"]
)
pred.fit_all(X_train, {
    "ac"          : Y_ac_train,
    "noise"       : Y_noise_train,
    "thermal"     : Y_thermal_train,
    "reliability" : Y_rel_train,
})
results = pred.predict_all(X_new)
# results["ac"], results["noise"], results["thermal"] …
```

---

## Technology Transfer

```python
from analogml.models import TechTransferAgent

# Fit on paired circuit data (same topologies, different tech)
agent = TechTransferAgent(source_tech="180nm", target_tech="90nm")
agent.fit(X_180nm_circuits, X_90nm_circuits)

# Map a 180nm circuit to its 90nm equivalent feature vector
X_90nm_estimate = agent.transfer(X_new_180nm)

# Get rough Dennard scaling ratios
rules = agent.tech_scaling_rules()
# {'L_ratio': 0.5, 'W_ratio': 0.5, 'C_ratio': 0.25, ...}
```

---

## Physics Utilities

```python
from analogml.core.physics import (
    mosfet_region,              # classify MOSFET operating region
    ids_saturation,             # square-law drain current
    gm_saturation,              # transconductance
    input_referred_noise_voltage,  # thermal noise floor
    junction_temperature,       # Tj = Ta + P*Rth
    hot_carrier_stress,         # HCI risk metric
    nbti_degradation_factor,    # NBTI Vth shift
    validate_spec,              # physics plausibility check
)

# Example
region = mosfet_region(vgs=0.9, vds=1.2, vth=0.5, device="nmos")
# → 'saturation'

ok, msg = validate_spec("gain_dB", 180.0)
# → (False, 'gain_dB=180.000 outside [0, 120]')
```

---

## Export Results

```python
from analogml.data.export import (
    export_predictions_csv,
    export_training_data_csv,
    model_report, print_report
)

# Export predictions with true values and error %
export_predictions_csv(X_test, Y_pred, Y_true,
                        x_names=xn, y_names=yn,
                        path="results.csv")

# Generate JSON performance report
report = model_report(model, X_test, Y_test,
                       output_names=yn, path="report.json")
print_report(report)
```

---

## Model Modes Comparison

| Mode    | Speed     | Accuracy | GPU Needed | Interpretability |
|---------|-----------|----------|------------|------------------|
| `fast`  | < 30s     | Good     | No         | Medium (SHAP-ready) |
| `nn`    | 2–10 min  | Better   | Optional   | Low–Medium |
| `full`  | 10–60 min | Best     | Recommended| High (PySR equations) |

---

## Supported Topologies (Synthetic Data)

| Topology          | Key Metrics |
|-------------------|-------------|
| `ota_5t`          | Gain, UGF, PM, Power, Noise, CMRR, SR |
| `ota_folded`      | Same + higher gain |
| `ldo`             | Vout, Line/Load Reg, PSRR, Dropout, Iq |
| `current_mirror`  | Accuracy, Vmin, Rout, BW, Mismatch |

For real circuits: use your own SPICE/Spectre netlists + simulator CSV outputs.

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `ModuleNotFoundError: torch` | Install PyTorch; model falls back to `fast` mode automatically |
| `ModuleNotFoundError: pysr` | `pip install pysr` or use `mode='fast'` |
| R² < 0.5 | Increase `n_samples`, add more training data, or use `mode='nn'` |
| Parser misses components | Check netlist format matches SPICE 2g6/3f5 syntax |
| Dashboard blank | Run `streamlit run analogml/ui/dashboard.py` and train model in sidebar first |

---

## Extending AnalogML

### Add a new topology to synthetic data
In `data/__init__.py`, add a method `_your_topology` to `SyntheticCircuitDataset`
following the `_ota_5t` pattern.

### Add a new analysis type
In `models/analysis_models.py`, create a class inheriting `BaseAnalysisModel`,
set `name` and `out_names`, add to `MultiAnalysisPredictor.MODELS`.

### Add a new physics constraint to PINN
In `models/__init__.py`, extend `AnalogPINN.physics_loss()` with your constraint.
