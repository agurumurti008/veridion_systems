# FCovForge Architecture Document

## 1. Design Philosophy

FCovForge is built on three principles:

1. **Representation before generation** — The internal model (FeatureModel) is the source of truth. All parsers produce it; all generators consume it. This means YAML and Excel are interchangeable input formats, and SV and HTML are interchangeable outputs.

2. **Dotted-path addressability everywhere** — Every element (Feature, CoverGroup, CoverPoint, Bin) has a unique, stable dotted address. This enables surgical cross definitions and clean CLI UX.

3. **Synthesize, don't simulate** — FCovForge generates standard SystemVerilog. It doesn't require a simulator, doesn't hook into coverage databases, and doesn't need EDA licenses. It is a pre-simulation code generation tool.

---

## 2. Layer Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    CLI / API Layer                       │
│  __main__.py — generate, cross, extract, validate,       │
│                report commands                           │
└─────────────────────┬───────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────┐
│                   Parser Layer                           │
│  yaml_parser.py   — YAML → FeatureModel                  │
│  excel_parser.py  — Excel → FeatureModel                 │
│  (future: json_parser.py, pss_parser.py)                │
└─────────────────────┬───────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────┐
│                  Core Model Layer                        │
│  model.py                                               │
│  ┌─────────────┐                                        │
│  │FeatureModel │                                        │
│  │  ├ Feature  │                                        │
│  │  │  ├ CoverGroup                                     │
│  │  │  │  ├ CoverPoint                                  │
│  │  │  │  │  └ CoverBin (8 types)                      │
│  │  │  │  └ CrossDef (intra-CG)                        │
│  │  └ FeatureCross (inter-feature)                      │
│  └─────────────┘                                        │
└───────────┬─────────────────────┬───────────────────────┘
            │                     │
┌───────────▼──────────┐ ┌────────▼───────────────────────┐
│   Cross Engine Layer │ │       Generator Layer           │
│  cross_engine.py     │ │  sv_generator.py — → .sv       │
│  - resolve targets   │ │  html_report.py  — → .html     │
│  - synthesize cross  │ │  (future: excel_export.py)     │
│    covergroups       │ └────────────────────────────────┘
└──────────────────────┘
            │
┌───────────▼──────────────────────────────────────────────┐
│                   AI Extractor Layer                      │
│  extractor.py                                            │
│  - Document loading (PDF, TXT, MD)                       │
│  - Chunking + LLM prompting                              │
│  - JSON → FeatureModel merge                             │
│  - RegisterMapExtractor (CSV → features)                 │
└──────────────────────────────────────────────────────────┘
```

---

## 3. Core Model Design Decisions

### BinType Enum
All 8 SystemVerilog bin types are first-class citizens in the model. This is important because:
- `ignore_bins` and `illegal_bins` use different SV keywords
- `wildcard bins` requires the `wildcard` qualifier before `bins`
- `default` bins have no value specification
- Each requires different SV rendering logic

### FeatureCrossTarget Granularity
Targets can be at 4 levels of granularity:
```
feature                    → all CGs, all CPs
feature.cg                 → one CG, all its CPs  
feature.cg.cp              → one CP only
feature.cg.cp.bin          → (reserved for future bin-level filtering)
```

The CrossEngine `resolve_target()` method handles all cases and produces a flat list of CoverPoints to be shadowed in the synthesized covergroup.

### Shadow Coverpoint Strategy
When synthesizing a feature cross, FCovForge creates "shadow" coverpoints that mirror the bins of the source coverpoints, using the same DUT signals. This is the key synthesis strategy:

```
Source (in feature A):          Synthesized (in cross CG):
  covergroup cg_A                 covergroup fcov_cross_X
    cp_1: coverpoint sig_1          shadow_A_cg_A_cp_1: coverpoint sig_1
      bins B1 = {1,2}               bins B1 = {1,2}
    cp_2: coverpoint sig_2          shadow_A_cg_A_cp_2: coverpoint sig_2
      bins B2 = {3,4}               bins B2 = {3,4}
  endgroup                        // cross them:
                                    X : cross shadow_A_cg_A_cp_1, 
                                            shadow_A_cg_A_cp_2
                                  endgroup
```

This is legal SystemVerilog. The shadow CG samples the same signals as the source CGs, so no new signal infrastructure is needed in the testbench.

---

## 4. AI Extraction Architecture

### Chunking Strategy
Large documents are split into overlapping chunks. Overlap (500 chars) ensures that features described across page boundaries aren't split.

### Prompt Engineering
The system prompt is carefully designed to:
1. Constrain output to pure JSON (no markdown fences)
2. Specify the exact schema expected
3. Provide examples of each bin type
4. Instruct the LLM to use snake_case names and UPPER_CASE bin names
5. Instruct realistic value ranges from the actual spec

### Merge Strategy
Multiple chunks may produce the same feature (partial descriptions across pages). The merge algorithm:
- Deduplicates by `feature.name`
- For duplicate features, merges covergroups (union, no duplicate CG names)
- First-wins for field-level conflicts (description, tags)

### Register Map Extractor
A specialized extractor for structured register maps (CSV/Excel) that doesn't need LLM:
- Parses register name, field name, bit range, access type
- Auto-generates value bins based on field width
- 1-bit fields → BIN_CLEAR/BIN_SET
- 8-bit fields → BIN_ZERO/BIN_LOW/BIN_MID/BIN_HIGH/BIN_ONES
- Read-only fields get an `ignore_bins` for write attempts

---

## 5. Future Extensions (Roadmap)

### Phase 2: Coverage Database Integration
```
[Simulator Coverage DB] → [FCovForge Coverage Analyzer] → [Gap Report]
                                                         → [Suggested Tests]
```
- Parse Questa UCDB, VCS VDIF, Xcelium CCDB
- Map coverage hits back to Feature → CoverGroup → CoverBin
- Produce "which features are uncovered" report
- Suggest directed test scenarios for uncovered bins

### Phase 3: PSS (Portable Stimulus Standard) Output
FCovForge YAML features can be translated to Accellera PSS:
- Feature → `component`
- CoverGroup → `covergroup`
- FeatureCross → PSS `cross` inside a `scenario`

### Phase 4: AI Test Suggestion
Given uncovered feature crosses, use LLM to suggest:
- UVM sequence configurations
- Constrained-random constraint additions
- Directed test cases in pseudocode

### Phase 5: Formal Verification Integration
Feature definitions can drive formal property generation:
- `BIN_ILLEGAL` → SVA assertion that value never occurs
- `BIN_TRANSITION` → SVA sequence property
- Feature cross → Formal cover property

---

## 6. Integration Points

### UVM Integration
Generated files integrate into UVM as follows:
```
my_tb/
  coverage/
    dma_transfer_coverage.sv          ← FCovForge generated
    interrupt_handling_coverage.sv    ← FCovForge generated
    example_soc_feature_crosses.sv    ← FCovForge generated
    example_soc_fcov_pkg.sv           ← FCovForge generated
    example_soc_coverage.sv           ← FCovForge generated (UVM subscriber)
  agents/
    ...
  tb_top.sv  ← includes fcov_pkg; instantiates coverage object
```

### CI/CD Integration
```yaml
# .github/workflows/coverage_plan.yml
- name: Generate Coverage Plan
  run: |
    python -m fcov_forge validate --input coverage/features.yaml
    python -m fcov_forge generate --input coverage/features.yaml --output coverage/sv/
    python -m fcov_forge report --input coverage/features.yaml --output coverage/plan.html
- name: Upload Coverage Plan
  uses: actions/upload-artifact@v3
  with:
    name: coverage-plan
    path: coverage/plan.html
```

### Makefile Integration
```makefile
coverage_plan:
	python -m fcov_forge generate --input features.yaml --output sv_out/
	
coverage_report:
	python -m fcov_forge report --input features.yaml --output plan.html

.PHONY: coverage_plan coverage_report
```
