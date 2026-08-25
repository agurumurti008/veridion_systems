# FCovForge — Feature-Level Functional Coverage Automation

> **Higher-order abstraction for SystemVerilog functional coverage: Features, not just covergroups.**

---

## 1. Problem Statement

Modern SoC verification faces a structural gap in coverage methodology:

| Layer | Standard SV Support | Real Verification Need |
|-------|---------------------|------------------------|
| Coverbin | ✅ Native | Individual value/transition bins |
| Covergroup | ✅ Native | Related coverpoints grouped |
| **Feature** | ❌ Missing | Multi-condition device behavior |
| **Feature Cross** | ❌ Missing | Interaction between features |

SystemVerilog's `cross` is **bin-level only** — it cannot cross two covergroups, and certainly cannot cross *features* (which may each span multiple covergroups). This forces teams to:
- Hand-write thousands of lines of duplicated cross coverage
- Use ad-hoc scripts with no standardization
- Miss feature interaction coverage entirely
- Have zero traceability from spec to coverage

FCovForge solves this with a **YAML-first feature abstraction layer** that compiles down to synthesized SystemVerilog, with AI-assisted extraction from spec documents.

---

## 2. Industry Landscape Analysis

### Existing Solutions

| Tool | Vendor | Approach | Limitations |
|------|--------|----------|-------------|
| **Questa Coverage** | Siemens EDA | GUI-based coverage merge/analyze | No feature abstraction; bin-level only |
| **VCS/URG** | Synopsys | Coverage report + exclusion files | No cross-feature support |
| **Incisive/IMC** | Cadence | Coverage database queries | Proprietary; no feature layer |
| **Breker Trek** | Breker | Graph-based scenario coverage | High cost; scenario-not-feature focused |
| **OneSpin** | Siemens | Formal assertion coverage | Formal only, not simulation |
| **Portable Stimulus (PSS)** | Accellera | Scenario abstraction | Generates tests, not coverage collectors |
| **Custom YAML scripts** | In-house | Various | Not reusable; no AI; no cross-feature |

### Gap Analysis

None of the above tools provide:
1. A **named Feature abstraction** above covergroup
2. **Cross between features** (not just bins)
3. **Addressable sub-selection** (`feature.covergroup.coverbin`)
4. **AI extraction** from spec/register documents
5. **Portable, human-readable format** (YAML/Excel) as source of truth

**FCovForge is a greenfield innovation** in this space.

---

## 3. Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        FCovForge Pipeline                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  [Spec/RegMap/uArch Docs]  [YAML/Excel Feature Defs]           │
│           │                          │                           │
│           ▼                          ▼                           │
│   ┌──────────────┐          ┌────────────────┐                  │
│   │  AI Extractor│          │  Format Parser  │                  │
│   │  (LLM-based) │          │  (YAML/Excel)   │                  │
│   └──────┬───────┘          └───────┬────────┘                  │
│          │                          │                            │
│          └──────────┬───────────────┘                           │
│                     ▼                                            │
│            ┌─────────────────┐                                   │
│            │  Feature Model  │  (Python dataclasses)             │
│            │  - Feature      │                                   │
│            │  - CoverGroup   │                                   │
│            │  - CoverPoint   │                                   │
│            │  - CoverBin     │                                   │
│            └────────┬────────┘                                   │
│                     │                                            │
│          ┌──────────┴──────────┐                                 │
│          ▼                     ▼                                 │
│  ┌──────────────┐    ┌──────────────────┐                       │
│  │  Cross Engine│    │  SV Code Generator│                      │
│  │  (resolves   │    │  (synthesizes SV) │                      │
│  │   feature    │    │                  │                        │
│  │   crosses)   │    └──────────────────┘                       │
│  └──────┬───────┘                                               │
│         │                                                        │
│         ▼                                                        │
│  ┌──────────────────────────────────────┐                       │
│  │        Output Artifacts               │                       │
│  │  - .sv  (synthesized covergroups)    │                       │
│  │  - .sv  (feature cross wrappers)     │                       │
│  │  - .html (coverage plan report)      │                       │
│  │  - .yaml (normalized feature model)  │                       │
│  └──────────────────────────────────────┘                       │
└─────────────────────────────────────────────────────────────────┘
```

### Addressability Scheme

Every element is addressable via dotted path:

```
<feature>.<covergroup>.<coverpoint>.<bin>

# Examples:
dma_transfer.data_width_cg.width_cp.BIN_32BIT
dma_transfer.burst_mode_cg                     # entire covergroup
interrupt_handling                              # entire feature
```

---

## 4. YAML Format Specification

See `docs/yaml_format_spec.md` for full spec.

Quick example:

```yaml
features:
  - name: dma_transfer
    description: "DMA channel transfer feature"
    covergroups:
      - name: data_width_cg
        coverpoints:
          - name: width_cp
            variable: dma_width
            bins:
              - {name: BIN_8BIT,  values: [8]}
              - {name: BIN_16BIT, values: [16]}
              - {name: BIN_32BIT, values: [32]}
              - {name: BIN_64BIT, values: [64]}
```

---

## 5. Quick Start

```bash
# Install
pip install -r requirements.txt

# Parse YAML and generate SV
python -m fcov_forge generate --input examples/dma_feature.yaml --output out/

# Cross two features
python -m fcov_forge cross \
  --feature1 dma_transfer \
  --feature2 interrupt_handling \
  --output out/

# Selective cross (specific covergroups)
python -m fcov_forge cross \
  --feature1 dma_transfer.data_width_cg \
  --feature2 interrupt_handling.priority_cg \
  --output out/

# AI extraction from spec document
python -m fcov_forge extract \
  --doc specs/dma_spec.pdf \
  --output features/extracted.yaml \
  --api-key $ANTHROPIC_API_KEY
```

---

## 6. SaaS Viability Assessment

See `docs/saas_analysis.md` for full analysis.

**TL;DR**: Viable as a B2B SaaS for IC verification teams, with strong competitive moat due to the AI-extraction capability and the feature-level abstraction which is genuinely absent from existing toolchains.

---

## 7. License

MIT License. Commercial SaaS deployment allowed.
