# FCovForge YAML Format Specification
**Version 1.0**

---

## Why YAML?

FCovForge uses YAML as its primary format because:
- **Human-readable**: Verification engineers can write and review it without tooling
- **Version-control friendly**: Diffs are clean and meaningful
- **Hierarchical**: Maps naturally to the Feature → CG → CP → Bin hierarchy
- **Widely supported**: Parseable in Python, Ruby, C++, and most CI systems
- **Comment-friendly**: Unlike JSON, YAML supports inline documentation

Excel is also supported (see `excel_parser.py`) for teams preferring spreadsheet-based workflows and existing register maps.

---

## Top-Level Structure

```yaml
project: "my_soc"             # Project name (required)

metadata:                      # Optional metadata block
  version: "1.0"
  author: "Verification Team"
  date: "2025-01-01"

features:                      # List of Feature definitions
  - ...

feature_crosses:               # List of Feature-level crosses
  - ...
```

---

## Feature Definition

```yaml
features:
  - name: feature_name          # snake_case, required
    description: "..."          # Human-readable (optional)
    tags: [tag1, tag2]          # Searchable tags (optional)
    source_doc: "spec.pdf"      # Traceability link (optional)
    covergroups:
      - ...
```

---

## CoverGroup Definition

```yaml
covergroups:
  - name: cg_name               # snake_case, required
    clock: "posedge clk"        # Sampling event (optional)
    condition: "reset_n"        # Global iff condition (optional)
    per_instance: true          # option.per_instance (default: false)
    auto_bin_max: 64            # option.auto_bin_max (optional)
    goal: 100                   # option.goal in % (default: 100)
    comment: "What this measures"

    args:                       # Parameterized CG arguments (optional)
      - type: int
        name: channel_id
      - type: "logic [7:0]"
        name: addr_base

    coverpoints:
      - ...

    crosses:                    # CG-internal crosses (optional)
      - ...
```

---

## CoverPoint Definition

```yaml
coverpoints:
  - name: cp_name               # snake_case, required
    variable: "dut.signal"      # SV expression being sampled (required)
    condition: "valid"          # Per-coverpoint iff (optional)
    comment: "What this measures"
    bins:
      - ...
```

---

## Bin Types Reference

### VALUES bin (default)
Covers specific enumerated values.
```yaml
- name: BIN_RESET
  values: [0]

- name: BIN_MULTI
  values: [1, 2, 3, 7]
```
→ SV: `bins BIN_RESET = {0};`

---

### RANGE bin
Covers a contiguous range of values. Multiple ranges can be combined.
```yaml
- name: BIN_LOW
  ranges: [[0, 15]]

- name: BIN_MIXED
  values: [64, 128]
  ranges: [[0, 15], [32, 47]]
```
→ SV: `bins BIN_LOW = {[0:15]};`

---

### TRANSITION bin
Covers state/value sequences.
- Each entry in `transitions` is one sequence
- Multiple sequences in one bin are OR'd
```yaml
- name: BIN_IDLE_TO_DONE
  type: transition
  transitions:
    - [IDLE, ACTIVE, DONE]        # sequence 1
    - [IDLE, ACTIVE, ACTIVE, DONE] # sequence 2 (with wait state)
```
→ SV: `bins BIN_IDLE_TO_DONE = (IDLE => ACTIVE => DONE), (IDLE => ACTIVE => ACTIVE => DONE);`

---

### WILDCARD bin
Uses `?` as don't-care bits.
```yaml
- name: BIN_UPPER_ADDR
  type: wildcard
  pattern: "8'b1???????"
```
→ SV: `wildcard bins BIN_UPPER_ADDR = {8'b1???????};`

---

### AUTO bin
SystemVerilog automatic partitioning.
```yaml
- name: BIN_AUTO_ALL
  type: auto
  auto_bin_max: 16
```
→ SV: `bins[] BIN_AUTO_ALL = {};  // auto`

---

### DEFAULT bin
Catches all values not covered by other bins.
```yaml
- name: BIN_OTHER
  type: default
```
→ SV: `bins BIN_OTHER = default;`

---

### IGNORE bin
Excludes values from coverage measurement.
```yaml
- name: BIN_RSVD
  type: ignore
  values: [255]
  ranges: [[256, 511]]
```
→ SV: `ignore_bins BIN_RSVD = {255, [256:511]};`

---

### ILLEGAL bin
Marks values as illegal (simulator may error on hit).
```yaml
- name: BIN_ILLEGAL
  type: illegal
  ranges: [[512, 1023]]
```
→ SV: `illegal_bins BIN_ILLEGAL = {[512:1023]};`

---

## Bin Advanced Options

```yaml
- name: BIN_CRITICAL
  values: [0]
  min_hits: 10       # Must be hit at least 10 times (default: 1)
  weight: 5          # Weighted for coverage calculation
  comment: "Reset must be seen at least 10 times"
```

---

## CG-Internal Cross Definition

Within a covergroup, you can define standard SV crosses between coverpoints:

```yaml
crosses:
  - name: width_x_direction
    coverpoints: [width_cp, direction_cp]
    comment: "Width vs direction cross"
    exclude_bins:
      - width_cp.BIN_8BIT       # Exclude 8-bit from cross
```

---

## Feature Cross Definition

This is the novel abstraction — crossing across covergroup/feature boundaries:

```yaml
feature_crosses:

  # CP-level cross (most specific)
  - name: uart_baud_x_spi_mode
    targets:
      - uart_tx.baud_rate_cg.baud_cp        # feature.cg.cp
      - spi_master.spi_mode_cg.mode_cp
    comment: "UART baud rate when SPI mode changes"
    goal: 100

  # CG-level cross (expands to all CPs in each CG)
  - name: dma_mode_x_irq_nesting
    targets:
      - dma_transfer.transfer_mode_cg       # feature.cg
      - interrupt_handling.nesting_cg
    goal: 90

  # Feature-level cross (expands to ALL CGs and CPs in each feature)
  - name: full_dma_x_power
    targets:
      - dma_transfer                         # feature only
      - power_management
    goal: 80

  # Three-way cross
  - name: dma_x_irq_x_power
    targets:
      - dma_transfer.transfer_mode_cg.direction_cp
      - interrupt_handling.priority_cg.source_cp
      - power_management.power_state_cg.pstate_cp
    goal: 75

  # With exclusions
  - name: power_x_dma_filtered
    targets:
      - power_management.power_state_cg.pstate_cp
      - dma_transfer.data_width_cg.width_cp
    goal: 85
    exclude_combinations:
      - power_management.power_state_cg.pstate_cp.BIN_OFF: true
        dma_transfer.data_width_cg.width_cp.BIN_64BIT: true
```

---

## Addressability Scheme

Every element has a unique dotted address:

| Address | Resolves To |
|---------|-------------|
| `feature_name` | Entire Feature |
| `feature_name.cg_name` | One CoverGroup |
| `feature_name.cg_name.cp_name` | One CoverPoint |
| `feature_name.cg_name.cp_name.BIN_NAME` | One CoverBin |

This addressing is used in:
- `feature_crosses[].targets[]`
- `feature_crosses[].exclude_combinations`
- CLI `--targets` arguments
- API `model.resolve_address()`

---

## Complete Minimal Example

```yaml
project: my_uart

features:
  - name: uart_config
    description: "UART configuration coverage"
    covergroups:
      - name: baud_cg
        clock: "posedge clk"
        coverpoints:
          - name: baud_cp
            variable: baud_rate
            bins:
              - {name: BIN_9600,   values: [9600]}
              - {name: BIN_115200, values: [115200]}
              - {name: BIN_1M,     values: [1000000]}

  - name: uart_error
    description: "UART error conditions"
    covergroups:
      - name: error_cg
        coverpoints:
          - name: error_cp
            variable: uart_error
            bins:
              - {name: BIN_NO_ERR,    values: [0]}
              - {name: BIN_PARITY,    values: [1]}
              - {name: BIN_FRAMING,   values: [2]}
              - {name: BIN_OVERFLOW,  values: [4]}
              - {name: BIN_ILLEGAL,   type: illegal, values: [8, 16]}

feature_crosses:
  - name: baud_x_error
    targets:
      - uart_config.baud_cg.baud_cp
      - uart_error.error_cg.error_cp
    comment: "Error types at different baud rates"
    goal: 100
```
