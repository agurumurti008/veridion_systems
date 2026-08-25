# IC Architecture Automation Tool
## Automated Quality Assessment, GNN-Based Learning & IP Design Brief Propagation

---

## Overview

This tool implements a full automated flow for IC architecture development:

```
Simple Spec → Architecture Graph → Quality Evaluation → Optimization → IP Design Briefs
                                         ↕
                               GNN Knowledge Base
                             (learns from past designs)
```

### Architecture Development Steps (Application-Driven)

1. **Application Profiling** — Map use-case to domain template (IoT/MCU/SoC/Radar)
2. **Constraint Capture** — Power, area, frequency, temperature, interface standards
3. **IP Inventory** — Select IPs from library; classify: digital, analog, mixed-signal
4. **Topology Definition** — Define bus hierarchy (AXI/AHB/APB); clock domains; power domains
5. **Interdependency Mapping** — Signal flows, clock distribution, power sequencing
6. **Quality Assessment** — Multi-dimensional scoring with loss functions
7. **Optimization Loop** — Iterative refinement guided by loss gradient direction
8. **Philosophy Propagation** — Architecture intent → per-IP design briefs
9. **Historical Learning** — GNN encodes past designs; informs future decisions

---

## Installation

```bash
# Python 3.8+ required, no external dependencies for core engine
git clone <repo>
cd ic_arch_tool
python tests/test_all.py   # Verify installation
```

---

## Usage

### Built-in Examples

```bash
# Run full flow with IoT sensor example
python arch_tool.py --example iot --full

# Industrial MCU with optimization only
python arch_tool.py --example mcu --optimize

# Radar chip — evaluate only
python arch_tool.py --example radar

# Smartphone SoC — full analysis + IP briefs
python arch_tool.py --example smartphone --full
```

### Custom Specification

```bash
# Provide your own JSON spec
python arch_tool.py --spec examples/wearable_spec.json --full
python arch_tool.py --spec examples/adas_radar_spec.json --optimize
```

### Spec JSON Format

```json
{
  "app_domain": "iot_sensor",          // iot_sensor | industrial_mcu | smartphone_soc | radar_chip | generic
  "process_node": "22nm",              // Technology node string
  "supply_voltage": 1.8,              // Volts
  "target_frequency": 48.0,           // MHz
  "power_budget": 5.0,               // mW
  "area_budget": 4.0,                // mm²
  "interface_standards": ["I2C", "SPI", "UART"],
  "performance_targets": {
    "adc_resolution": 12,
    "sleep_current_ua": 1
  },
  "reliability_targets": {
    "mtbf_hours": 100000
  },
  "operating_temp_range": [-40, 125]  // Celsius
}
```

---

## Architecture Quality Assessment

### Loss Functions

| Loss | Formula | What It Measures |
|------|---------|-----------------|
| `L_power` | total_power / budget | Power over-budget ratio |
| `L_area` | total_area / budget | Area over-budget ratio |
| `L_timing` | critical_path / clock_period | Timing violation risk |
| `L_connectivity` | missing_connections / expected | Bus topology completeness |
| `L_ip_coverage` | missing_interfaces / required | Protocol compliance |
| `L_cdc` | risky_crossings / digital_ics | Clock domain crossing risk |
| `L_analog_isolation` | digital→analog paths / analog_IPs | Noise coupling risk |
| `L_redundancy` | excess_IP_instances / total_IPs | Over-provisioning |
| `L_power_domain` | unpowered_IPs / total_IPs | PMU coverage |

### Composite Loss

```
L_composite = Σ(wᵢ × Lᵢ) / Σ(wᵢ)
Score = max(0, 1 - L_composite/2)
```

Default weights: connectivity=3.0, ip_coverage=2.5, power=2.0, timing=2.0, power_domain=2.0

### Grading

| Score | Grade | | Score | Grade |
|-------|-------|-|-------|-------|
| ≥0.90 | A+   | | ≥0.50 | C+   |
| ≥0.85 | A    | | ≥0.42 | C    |
| ≥0.78 | A-   | | ≥0.35 | C-   |
| ≥0.72 | B+   | | ≥0.25 | D    |
| ≥0.65 | B    | | <0.25 | F    |
| ≥0.58 | B-   | | | |

---

## Graph Representation for ML

The architecture is expressed as a graph G = (V, E):

- **V (Nodes)** = IP blocks, feature vector ∈ ℝ⁹:
  `[ip_type, signal_domain, power, area, frequency, latency, #interfaces, #deps, verified]`

- **E (Edges)** = Interconnects, feature vector ∈ ℝ⁴:
  `[signal_domain, bandwidth_gbps, latency_ns, power_mw]`

- **Adjacency Matrix** A ∈ ℝⁿˣⁿ: Aᵢⱼ = bandwidth of interconnect i→j

- **Node Feature Matrix** X ∈ ℝⁿˣ⁹

This graph is consumed by the **GraphEncoder** (2-layer GNN with mean aggregation):

```
h_v^(l+1) = ReLU(W_self · h_v^l + W_neigh · mean({h_u^l : u ∈ N(v)}) + b)
```

Graph-level embedding = mean pooling of node embeddings + 5 global stats → ℝ¹³

---

## Why GNN vs Alternatives?

| Method | Data Need | Speed | Structural Aware | Interpretable |
|--------|-----------|-------|-----------------|---------------|
| **GNN** (our choice) | 50–500 designs | Fast | ✓ Yes | Moderate |
| Bayesian Optimization | 10–100 evals | Very fast | ✗ No | High (GP) |
| Genetic Algorithm | None | Slow | ✗ No | Low |
| Reinforcement Learning | 1000s rollouts | Very slow | Partial | Low |
| Rule-based Expert | Zero | Instant | ✓ Yes | Very high |

**Justification**: IC architectures are inherently graph-structured. A plain NN treating IP counts as scalars loses the topology (which IP connects to which). GNNs propagate neighbor information via message passing, capturing how an analog IP's position relative to noisy digital clocks affects quality. For cold-start (few historical designs), the rule-based engine covers; as designs accumulate, GNN takes over similarity search and IP recommendation.

---

## IP Design Brief Propagation

Each IP receives:
- **Architecture Intent** — The top-level design philosophy
- **Electrical Specs** — Power/area/frequency budgets with margins
- **Functional Objectives** — What this IP must achieve
- **Interface Requirements** — Protocol compliance checklist
- **Interdependencies** — What drives it, what it drives, shared resources
- **Verification Targets** — Coverage goals per IP type
- **Corner Cases** — Domain-specific failure scenarios
- **CDC Notes** — Clock domain crossing risks at this boundary
- **Analog Notes** — Isolation and noise guidance (analog/mixed-signal IPs)

---

## Project Structure

```
ic_arch_tool/
├── arch_tool.py          # Main CLI entry point
├── core/
│   ├── arch_engine.py    # Spec parsing, IP library, graph builder
│   ├── evaluator.py      # Loss functions, quality assessment, optimizer
│   ├── ml_engine.py      # GNN encoder, knowledge base, advisor
│   └── propagator.py     # Architecture → IP design brief propagation
├── examples/
│   ├── wearable_spec.json
│   └── adas_radar_spec.json
├── tests/
│   └── test_all.py       # Full test suite (8 tests)
└── README.md
```

---

## Test Examples

```bash
# Run all 8 tests
python tests/test_all.py

# Tests cover:
# 1. IoT Sensor — Build & Evaluate
# 2. Industrial MCU — Build, Evaluate, Optimize
# 3. Radar Chip — Analog + Mixed-Signal
# 4. Graph → Adjacency + Feature Matrices
# 5. GNN Encoder + Knowledge Base + Advisor
# 6. IP Design Brief Propagation
# 7. Custom Spec (Wearable Health Monitor)
# 8. Loss Function Sensitivity (over-budget scenario)
```

---

## Extending the Tool

**Add a new IP to the library** (`core/arch_engine.py`):
```python
ArchitectureBuilder.IP_LIBRARY["my_ip"] = IPBlock(
    ip_id="my_ip", name="My Custom IP",
    ip_type=IPType.DIGITAL, signal_domain=SignalDomain.DIGITAL,
    power_mw=10.0, area_mm2=0.1, frequency_mhz=200,
    latency_ns=5.0, interfaces=["AXI4"],
    specs={"my_param": 42}
)
```

**Add a new application domain** (`core/arch_engine.py`):
```python
DOMAIN_TEMPLATES["medical_device"] = { ... }
ArchitectureBuilder.DOMAIN_IP_MAP["medical_device"] = ["pll", "pmu", ...]
```

**Add a new loss function** (`core/evaluator.py`):
```python
def loss_my_metric(graph: ArchitectureGraph) -> float:
    return ...  # Return value in [0, ∞); 0 = perfect

# Register in ArchitectureEvaluator.evaluate()
losses["my_metric"] = loss_my_metric(graph)
```
