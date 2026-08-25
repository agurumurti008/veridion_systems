# VERA Checker Taxonomy & Industry Reference
## Complete Classification, Standards Index & Best Practices

---

## SECTION 1: COMPLETE CHECKER TAXONOMY

### Tier 1 — By Abstraction Level

```
ABSTRACTION LEVEL          CHECKER TYPE              WHEN TO USE
─────────────────────────────────────────────────────────────────
Gate-level (post-synth)    SVA bind modules          CDC, glitch checks
RTL behavioral             SVA + UVM Scoreboard      Functional, protocol
Transaction-level (TLM)    UVM Scoreboard            System-level, perf
AMS schematic/netlist      SKILL/OCEAN, Verilog-AMS  Analog param checks
SPICE/extracted            Spectre measures, OCEAN   Parasitic effects
System / algorithm         Python/MATLAB post-sim    DSP, algorithm quality
```

### Tier 2 — By Check Category

| Category | Description | Primary Method | Example |
|----------|-------------|----------------|---------|
| Protocol | Bus transaction compliance | SVA concurrent | AXI4 handshake |
| Temporal | Timing sequences, ordering | SVA property | Setup/hold sequences |
| Structural | Connectivity, clocking | SVA immediate | Reset active-low |
| Parametric | Value bounds (V, I, f, t) | Python/SKILL | PSRR ≥ 40 dB |
| Functional | Correct behavior | UVM Scoreboard | ADC code accuracy |
| Statistical | Distribution & quality | Python/MATLAB | ENOB, DNL |
| Coverage | Exercise completeness | SVA cover / cg | Code bin coverage |
| Power | Current/energy bounds | Python/SKILL | Iavg < 500 µA |
| Safety | No illegal states | SVA assert | No overflow |
| Formal | Mathematical proof | JasperGold/VC | Deadlock freedom |

### Tier 3 — By Trigger Mechanism

```
TRIGGER TYPE          METHOD              TIMING
──────────────────────────────────────────────────────────────
Clock edge            @(posedge clk)      Every cycle — SVA concurrent
Signal event          @(above/cross)      Threshold crossing — Verilog-AMS
End of simulation     final_phase         After last timestep — UVM/Python
Post-sim batch        External script     After tool exits — Python/MATLAB
Parametric sweep      OCEAN selectResults After each corner — SKILL
Formal exhaustive     Model checker       Unbounded — JasperGold/VC Formal
```

---

## SECTION 2: IP-SPECIFIC CHECKER STRATEGY MATRIX

### Digital IPs

| IP | Key Checks | SVA | UVM SB | Post-Sim | Coverage Focus |
|----|-----------|-----|--------|----------|----------------|
| UART | Framing, baud, parity | ✓✓✓ | ✓ | byte stats | All baud configs |
| SPI | CS/SCLK/MOSI phase | ✓✓✓ | ✓ | packet | CPOL/CPHA combos |
| I2C | START/STOP/ACK | ✓✓✓ | ✓ | speed modes | 7/10-bit addr |
| AXI4 | All 5 channels | ✓✓✓ | ✓✓ | burst stats | burst/size/id |
| APB | SETUP/ACCESS | ✓✓✓ | ✓ | — | R/W/error |
| AHB | HTRANS, wait | ✓✓✓ | ✓ | — | burst types |
| FIFO | OV/UN/count | ✓✓✓ | — | histogram | fill levels |
| SRAM | Read/write/retention | — | ✓✓✓ | patterns | march tests |
| USB | NRZI, bitstuff, CRC | ✓✓ | ✓✓✓ | packet | speeds |
| PCIe | TLP, DLLP, ordered | — | ✓✓✓ | eye | gen/speed |

### Analog / Mixed-Signal IPs

| IP | Key Checks | SKILL | Verilog-AMS | Python | MATLAB |
|----|-----------|-------|-------------|--------|--------|
| ADC | DNL, INL, ENOB, SNR, SFDR | ✓ | ✓ | ✓✓✓ | ✓✓✓ |
| DAC | THD, settling, INL | ✓ | ✓ | ✓✓ | ✓✓ |
| PLL | Lock time, jitter, freq | ✓✓ | ✓✓ | ✓✓ | ✓✓ |
| LDO | PSRR, load/line reg | ✓✓✓ | ✓ | ✓ | — |
| Op-Amp | GBW, PM, CMRR, PSRR | ✓✓✓ | ✓ | ✓ | — |
| Comparator | Offset, tpd, hysteresis | ✓✓✓ | ✓ | ✓ | — |
| Bandgap | TC, PSRR, accuracy | ✓✓✓ | ✓ | ✓ | — |
| SERDES | Eye, BER, jitter | — | ✓✓ | ✓✓ | ✓✓✓ |
| Oscillator | Freq accuracy, PN | ✓✓ | ✓✓ | ✓✓ | ✓✓ |
| BGR/Current | TC, matching | ✓✓✓ | — | ✓ | — |

---

## SECTION 3: INDUSTRY STANDARDS & REFERENCES

### 3.1 IEEE Standards

| Standard | Title | Relevance to VERA |
|----------|-------|-------------------|
| IEEE 1800-2023 | SystemVerilog LRM | SVA syntax, semantics (Chap 16) |
| IEEE 1800.2-2020 | UVM Standard | Scoreboard, monitor, predictor |
| IEEE 1666-2011 | SystemC Standard | TLM-2.0 for mixed abstraction |
| IEEE 1076.1-2007 | VHDL-AMS | Analog extensions |
| IEEE 754-2019 | Floating Point | Post-sim numeric handling |

### 3.2 ARM AMBA Protocol Specifications

| Document | Protocol | Key Sections for Checkers |
|----------|----------|--------------------------|
| IHI0022H | AXI4 | §A3 (handshake), §A4 (bursts), §A8 (exclusive) |
| IHI0033B | AHB-Lite | §3 (transfers), §6 (response) |
| IHI0024C | APB3/4 | §2 (state machine), §3 (PSTRB) |
| IHI0011A | CHI | §4 (transactions), §13 (ordering) |
| IHI0069B | ACE | §5 (coherency), §C (transactions) |

### 3.3 Cadence-Specific References

| Document | Tool | Use in VERA |
|----------|------|-------------|
| CDNSim SV Assert Guide | Xcelium | SVA bind, cover |
| SKILL Language Reference | Virtuoso | SKILL checker syntax |
| OCEAN Reference Manual | ADE | Post-sim measurements |
| Verilog-AMS LRM 2.4 | Spectre/APS | Analog monitors |
| AMS Designer User Guide | Xcelium AMS | Mixed-signal co-sim |

### 3.4 Synopsys References

| Document | Tool | Use in VERA |
|----------|------|-------------|
| VCS SVA User Guide | VCS | SVA simulation |
| VC Formal App Notes | VC Formal | Formal property checking |
| HSPICE User Guide | HSPICE | Measure statement syntax |
| CustomSim User Guide | CustomSim | AMS mixed-signal checks |

### 3.5 Siemens/Mentor References

| Document | Tool | Use in VERA |
|----------|------|-------------|
| Questa SIM User Guide | Questa | SVA, UVM integration |
| Questa Formal User Guide | Questa Formal | Formal assertions |
| UVM Cookbook | Methodology | SB/predictor patterns |
| Verification Academy | Online | UVM patterns |

### 3.6 Open Standards & Methodologies

| Source | Title | Use |
|--------|-------|-----|
| Accellera OVL 2.7 | Open Verification Library | Pre-built assertion library |
| DVCon Proceedings | Mixed-signal verification | AMS methodology papers |
| DAC/DATE Papers | ADC/PLL verification | Academic methods |
| ChipVerify.com | SVA/UVM reference | Quick reference |
| VerificationAcademy.com | UVM Cookbook | Methodology guide |

---

## SECTION 4: SVA BEST PRACTICE REFERENCE CARD

### 4.1 Property Templates

```systemverilog
// Handshake: valid held until ready
property p_valid_stable;
  @(posedge clk) disable iff (!rst_n)
  (valid && !ready) |=> valid;
endproperty

// Response time: must respond within N cycles
property p_response_time;
  @(posedge clk) disable iff (!rst_n)
  $rose(req) |-> ##[1:MAX_LATENCY] ack;
endproperty

// Mutual exclusion: two signals never both high
property p_mutex;
  @(posedge clk) disable iff (!rst_n)
  not (sig_a && sig_b);
endproperty

// Data stability during wait
property p_data_stable_wait;
  @(posedge clk) disable iff (!rst_n)
  (valid && !ready) |=> $stable(data);
endproperty

// One-hot encoding check
property p_one_hot;
  @(posedge clk) disable iff (!rst_n)
  $onehot(grant_vector) || grant_vector == '0;
endproperty

// Gray code counter progression
property p_gray_code;
  @(posedge clk) disable iff (!rst_n)
  $countones(cnt ^ $past(cnt)) <= 1;
endproperty

// Pipeline no-stall: output valid N cycles after input valid
property p_pipeline_latency;
  @(posedge clk) disable iff (!rst_n)
  $rose(data_in_valid) |-> ##LATENCY data_out_valid;
endproperty
```

### 4.2 SVA Operator Quick Reference

| Operator | Meaning | Example |
|----------|---------|---------|
| `\|->` | Overlapping implication | `req \|-> ##[1:4] ack` |
| `\|=>` | Non-overlapping | `valid \|=> $stable(data)` |
| `##N` | N-cycle delay | `##3 done` |
| `##[m:n]` | Delay range | `##[1:8] ack` |
| `[*n]` | Repeat n times | `valid[*4]` |
| `[*m:n]` | Repeat range | `ready[*1:8]` |
| `[->n]` | Goto repeat | `valid[->3]` |
| `$rose()` | Rising edge | `$rose(clk)` |
| `$fell()` | Falling edge | `$fell(rst_n)` |
| `$stable()` | No change | `$stable(addr)` |
| `$past(x,n)` | x delayed n cycles | `$past(data, 2)` |
| `$onehot()` | One-hot check | `$onehot(sel)` |
| `inside` | Set membership | `state inside {S_IDLE, S_WAIT}` |
| `not` | Negate sequence | `not (a && b)` |
| `and` | Both sequences | `s1 and s2` |
| `or` | Either sequence | `s1 or s2` |

---

## SECTION 5: UVM SCOREBOARD PATTERNS

### 5.1 Pattern Selection Guide

| Pattern | When | Class |
|---------|------|-------|
| Simple | 1:1 in-order stimulus→response | `vera_scoreboard_base` |
| Out-of-Order | Responses in any order | Extend SB, use assoc array on ID |
| Pipeline | Fixed N-cycle latency | Add `latency` parameter to SB |
| Transform | Analog→digital, filter | `vera_transform_scoreboard` |
| Statistical | Distribution check | Custom with histogram |
| Functional Model | Golden C/Python ref | `vera_predictor_base` |

### 5.2 TLM Connection Patterns

```
Pattern 1: Direct (simple checker)
  monitor.ap → scoreboard.actual_export

Pattern 2: Predict-then-check (with predictor)
  stim_monitor.ap → predictor.analysis_export
  predictor.predicted_ap → scoreboard.expected_export
  resp_monitor.ap → scoreboard.actual_export

Pattern 3: Pass-through (checker embedded in monitor)
  monitor.ap → coverage.analysis_export
  monitor.vera_ap → reporter.result_export

Pattern 4: Parallel (multiple checkers on same DUT)
  monitor.ap → [sb_functional, sb_timing, sb_power] (3 subscribers)
```

---

## SECTION 6: POST-SIM CHECKER REFERENCE

### 6.1 ADC Performance Metrics Quick Reference

| Metric | Formula | Good 12-bit | VERA Checker |
|--------|---------|-------------|--------------|
| ENOB | `(SINAD-1.76)/6.02` | >10.5 | `vera_adc_enob` |
| SNR | `6.02·N + 1.76 dB` | >74 dB | `vera_adc_snr` |
| SFDR | Max spur free range | >80 dBc | `vera_adc_sfdr` |
| THD | Sum of harmonic power | <-70 dBc | `vera_adc_thd` |
| SINAD | SNR including harmonics | >66 dB | Derived |
| DNL | Code width deviation | <±0.5 LSB | `vera_adc_dnl` |
| INL | Accumulated DNL | <±1.0 LSB | `vera_adc_inl` |
| Missing codes | DNL < -1 LSB | 0 | `vera_adc_missing_codes` |
| Offset | Zero-input code | <±2 LSB | `vera_adc_offset` |
| Gain | Full-scale deviation | <±1% | `vera_adc_gain_err` |

### 6.2 PLL Performance Metrics

| Metric | Definition | Typical Spec | VERA Checker |
|--------|-----------|--------------|--------------|
| Lock time | Time from enable to lock | <10 µs | `vera_pll_lock_time` |
| Freq accuracy | fout vs target | <100 ppm | `vera_pll_freq_accuracy` |
| RMS jitter | σ of period | <5 ps | `vera_pll_jitter_rms` |
| Phase noise | L(f) in dBc/Hz | <-120 dBc/Hz @1MHz | `vera_pll_phase_noise` |
| Lock range | Frequency pull-in | ±2% | `vera_pll_lock_range` |

---

## SECTION 7: VERA NAMING & REPORTING CONVENTIONS

### 7.1 Checker Naming
```
vera_{ip}_{layer}_{parameter}_{condition}
      │       │         │            │
      │       │         │            └── max/min/stable/valid/range
      │       │         └──── signal or measured quantity
      │       └──── parametric/protocol/structural/dynamic/static
      └──── ip name lowercase
```

### 7.2 Status Codes
- `PASS` — Measurement within spec, no action needed
- `FAIL` — Spec violation, test fails, waveform loader triggered
- `WARNING` — Marginal result (within spec but near boundary)
- `INFO` — Informational measurement, no pass/fail criterion

### 7.3 Severity Levels
- `ERROR` → Simulation fails, UVM `uvm_error`, Python `sys.exit(1)`
- `WARNING` → UVM `uvm_warning`, logged but test may pass
- `INFO` → UVM `uvm_info`, always passes

---

*VERA Checker Taxonomy & Industry Reference v1.0*
*Verification Engine for Runtime & Autonomous Checking*
