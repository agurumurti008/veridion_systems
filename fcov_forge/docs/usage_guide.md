# FCovForge Usage Guide & Tutorial

---

## Installation

```bash
# Clone the repository
git clone https://github.com/your-org/fcov_forge
cd fcov_forge

# Install dependencies
pip install -r requirements.txt

# Verify installation
python -m fcov_forge --help
```

---

## Tutorial 1: Your First Feature Definition

Create `my_uart.yaml`:

```yaml
project: my_uart_chip

features:
  - name: uart_transmit
    description: "UART TX configuration and behavior"
    covergroups:
      - name: baud_rate_cg
        clock: "posedge clk"
        condition: "uart_enable"
        coverpoints:
          - name: baud_cp
            variable: uart_baud_rate
            bins:
              - {name: BIN_9600,   values: [9600]}
              - {name: BIN_38400,  values: [38400]}
              - {name: BIN_115200, values: [115200]}
              - {name: BIN_1M,     values: [1000000]}
```

Generate SystemVerilog:
```bash
python -m fcov_forge generate --input my_uart.yaml --output sv_out/
```

Output:
```
[FCovForge] Parsing YAML: my_uart.yaml
[FCovForge] Model: 1 feature(s), 0 cross(es)
[FCovForge] Generated 3 file(s):
  ✓ [feature:uart_transmit] uart_transmit_coverage.sv
  ✓ [package] my_uart_chip_fcov_pkg.sv
  ✓ [uvm_collector] my_uart_chip_coverage.sv
```

---

## Tutorial 2: Adding All Bin Types

```yaml
features:
  - name: memory_controller
    covergroups:
      - name: access_cg
        clock: "posedge clk"
        coverpoints:

          # VALUES: specific values
          - name: access_size_cp
            variable: mem_access_size
            bins:
              - {name: BIN_BYTE,  values: [1]}
              - {name: BIN_WORD,  values: [4]}
              - {name: BIN_DWORD, values: [8]}

          # RANGE: contiguous ranges
          - name: address_cp
            variable: mem_addr
            bins:
              - {name: BIN_LOW_MEM,  ranges: [[0x0000, 0x7FFF]]}
              - {name: BIN_HIGH_MEM, ranges: [[0x8000, 0xFFFF]]}
              - {name: BIN_IGNORE_IO, type: ignore, ranges: [[0xF000, 0xFFFF]]}

          # TRANSITION: state sequences
          - name: state_cp
            variable: mem_state
            bins:
              - name: BIN_READ_CYCLE
                type: transition
                transitions:
                  - [IDLE, READ_REQ, READ_DATA, IDLE]

              - name: BIN_WRITE_CYCLE
                type: transition
                transitions:
                  - [IDLE, WRITE_REQ, WRITE_DATA, WRITE_ACK, IDLE]

              - name: BIN_RMW_CYCLE
                type: transition
                transitions:
                  - [IDLE, READ_REQ, READ_DATA, WRITE_REQ, WRITE_DATA, WRITE_ACK, IDLE]

          # WILDCARD: don't-care bits
          - name: addr_pattern_cp
            variable: "mem_addr[7:0]"
            bins:
              - {name: BIN_ALIGNED_4B,  type: wildcard, pattern: "8'b??????00"}
              - {name: BIN_UNALIGNED,   type: wildcard, pattern: "8'b??????11"}

          # AUTO: automatic partitioning
          - name: data_cp
            variable: mem_data
            bins:
              - {name: BIN_AUTO_VALS, type: auto, auto_bin_max: 32}

          # DEFAULT: catch-all
          - name: opcode_cp
            variable: mem_opcode
            bins:
              - {name: BIN_READ,  values: [1]}
              - {name: BIN_WRITE, values: [2]}
              - {name: BIN_FLUSH, values: [3]}
              - {name: BIN_OTHER, type: default}
              - {name: BIN_RSV,   type: illegal, values: [0, 255]}
```

---

## Tutorial 3: Feature Crosses

The power of FCovForge — crossing between features.

```yaml
project: soc_chip

features:
  - name: dma_engine
    covergroups:
      - name: channel_cg
        coverpoints:
          - name: ch_width_cp
            variable: dma_width
            bins:
              - {name: BIN_32BIT, values: [32]}
              - {name: BIN_64BIT, values: [64]}

  - name: cache_controller
    covergroups:
      - name: cache_state_cg
        coverpoints:
          - name: hit_miss_cp
            variable: cache_result
            bins:
              - {name: BIN_HIT,  values: [0]}
              - {name: BIN_MISS, values: [1]}

feature_crosses:

  # Cross specific coverpoints
  - name: dma_width_x_cache_result
    targets:
      - dma_engine.channel_cg.ch_width_cp
      - cache_controller.cache_state_cg.hit_miss_cp
    comment: "DMA width behavior on cache hit vs miss"
    goal: 100

  # Cross at covergroup level (all CPs in each CG are crossed)
  - name: dma_cg_x_cache_cg
    targets:
      - dma_engine.channel_cg
      - cache_controller.cache_state_cg
    goal: 90
```

Generate:
```bash
python -m fcov_forge generate --input soc_chip.yaml --output sv_out/
```

---

## Tutorial 4: CLI Cross Command (Ad-hoc)

You can add a cross without modifying the YAML:

```bash
# Cross two specific coverpoints
python -m fcov_forge cross \
  --input features.yaml \
  --targets dma_engine.channel_cg.ch_width_cp cache_controller.cache_state_cg.hit_miss_cp \
  --name dma_cache_cross \
  --output sv_out/adhoc_cross.sv

# Three-way cross
python -m fcov_forge cross \
  --input features.yaml \
  --targets dma_engine.channel_cg power_management.power_cg interrupt_handling.priority_cg \
  --output sv_out/three_way.sv
```

---

## Tutorial 5: AI Extraction from Spec Document

```bash
# Set API key
export ANTHROPIC_API_KEY=sk-ant-...

# Extract from PDF spec
python -m fcov_forge extract \
  --doc specs/dma_spec.pdf \
  --output features/extracted_dma.yaml \
  --focus "DMA transfer modes, burst lengths, address alignment"

# Extract from text document
python -m fcov_forge extract \
  --doc specs/interrupt_spec.txt \
  --output features/extracted_interrupt.yaml \
  --suggest-crosses     # Also suggest feature crosses

# Then generate SV from extracted features
python -m fcov_forge generate \
  --input features/extracted_dma.yaml \
  --output sv_out/
```

**Tips for better extraction:**
- Use `--focus` to narrow what the AI looks for
- Run extraction on sections of the spec separately for better quality
- Always review the extracted YAML before generating SV
- Use `python -m fcov_forge validate --input extracted.yaml` to catch issues

---

## Tutorial 6: Validation

```bash
python -m fcov_forge validate --input features.yaml
```

Output:
```
[FCovForge] Validation Report
  Features    : 3
  CoverGroups : 7
  CoverPoints : 18
  Bins        : 63
  Feat Crosses: 4

  ✓ No errors found
```

Error example:
```
  ✗ 2 error(s) found:
    - [CrossEngine] Feature 'nonexistent_feat' not found
    - FeatureCross 'bad_cross' needs at least 2 targets
```

---

## Tutorial 7: HTML Coverage Plan

```bash
python -m fcov_forge report \
  --input features.yaml \
  --output coverage_plan.html
```

Open `coverage_plan.html` in a browser for an interactive coverage plan showing:
- Feature hierarchy with collapsible covergroups
- All bins with type badges and value visualization
- Feature cross definitions
- Statistics (total features, CGs, CPs, bins)

---

## Tutorial 8: Excel Workflow

### Generate blank Excel template
```python
from generators.excel_template import generate_blank_template
from pathlib import Path

generate_blank_template(Path("my_coverage_template.xlsx"))
```

Fill in the Excel sheets, then:
```bash
python -m fcov_forge generate \
  --input my_coverage_plan.xlsx \
  --output sv_out/
```

### Export existing YAML to Excel
```python
import sys
sys.path.insert(0, ".")
from parsers.yaml_parser import parse_yaml
from generators.excel_template import export_to_excel
from pathlib import Path

model = parse_yaml("features.yaml")
export_to_excel(model, Path("coverage_plan.xlsx"))
```

---

## Tutorial 9: Python API

Use FCovForge programmatically in your verification infrastructure:

```python
import sys
sys.path.insert(0, "/path/to/fcov_forge")

from parsers.yaml_parser import parse_yaml
from core.model import FeatureCross, FeatureCrossTarget
from core.cross_engine import CrossEngine
from generators.sv_generator import generate_all
from generators.yaml_export import export_to_yaml, merge_models
from pathlib import Path

# Load model
model = parse_yaml("features.yaml")

# Add cross programmatically
model.feature_crosses.append(FeatureCross(
    name="runtime_cross",
    targets=[
        FeatureCrossTarget("dma_transfer.data_width_cg.width_cp"),
        FeatureCrossTarget("interrupt_handling.priority_cg.priority_cp"),
    ],
    goal=100,
    comment="Added by automation script",
))

# Validate
engine = CrossEngine(model)
errors = engine.validate()
if errors:
    for e in errors:
        print(f"ERROR: {e}")
    exit(1)

# Generate SV
generated = generate_all(model, Path("sv_out/"))

# Export normalized YAML
export_to_yaml(model, Path("features_normalized.yaml"))

# Resolve any address
cp = model.resolve_address("dma_transfer.data_width_cg.width_cp")
print(f"Bins in {cp.name}: {[b.name for b in cp.bins]}")

# Merge multiple feature files
from parsers.yaml_parser import parse_yaml
models = [parse_yaml(f) for f in ["dma.yaml", "interrupt.yaml", "power.yaml"]]
merged = merge_models(models, "full_soc")
generate_all(merged, Path("full_sv_out/"))
```

---

## UVM Testbench Integration

After generation, integrate into your UVM testbench:

```systemverilog
// tb_top.sv
`include "example_soc_fcov_pkg.sv"

import example_soc_fcov_pkg::*;

module tb_top;
  // ...
  
  // Instantiate coverage
  example_soc_coverage cov_collector;
  
  initial begin
    cov_collector = example_soc_coverage::type_id::create("cov_collector", null);
    // ...
  end
endmodule
```

Or use the generated UVM subscriber directly:

```systemverilog
// In your env build_phase
example_soc_coverage cov;
cov = example_soc_coverage::type_id::create("cov", this);
// Connect to the agent monitor port:
my_agent.monitor.ap.connect(cov.analysis_export);
```

---

## Addressing Cheat Sheet

```
# Full hierarchy:
feature_name.covergroup_name.coverpoint_name.BIN_NAME

# Examples:
dma_transfer                                    # entire feature
dma_transfer.data_width_cg                      # one covergroup
dma_transfer.data_width_cg.width_cp             # one coverpoint
dma_transfer.data_width_cg.width_cp.BIN_32BIT   # one bin

# Use in feature_crosses.targets:
targets:
  - dma_transfer.data_width_cg.width_cp    # CP-level
  - interrupt_handling.priority_cg         # CG-level
  - power_management                       # Feature-level
```
