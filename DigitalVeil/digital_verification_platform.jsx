import { useState, useEffect, useRef } from "react";

// ── DESIGN SYSTEM ─────────────────────────────────────────────────────────────
// Aesthetic: Military-grade industrial. Amber-on-black terminal. Structured warfare.
// Distinct from AnalogVeil's cyan/purple cyberpunk. This is a command center.
const C = {
  bg:       "#080a06",
  surface:  "#0d0f0a",
  card:     "#121508",
  border:   "#1c2012",
  amber:    "#f5a623",
  amberDim: "#a36b10",
  lime:     "#7fff00",
  limeDim:  "#4d9900",
  red:      "#ff3b30",
  redDim:   "#8b1a14",
  blue:     "#4fc3f7",
  blueDim:  "#1565a0",
  gold:     "#ffd700",
  goldDim:  "#9a7d00",
  muted:    "#5a6340",
  dim:      "#2a3018",
  text:     "#d4dbb8",
  textDim:  "#8a9470",
};

const TABS = [
  { id: 0, label: "WAR DOCTRINE",    icon: "⊕" },
  { id: 1, label: "IP TAXONOMY",     icon: "◫" },
  { id: 2, label: "VPLAN ENGINE",    icon: "◧" },
  { id: 3, label: "METHODOLOGY",     icon: "◨" },
  { id: 4, label: "COVERAGE MATRIX", icon: "▦" },
  { id: 5, label: "DFT ARSENAL",     icon: "◩" },
  { id: 6, label: "SPEC KG",         icon: "⊗" },
  { id: 7, label: "SIGN-OFF GATES",  icon: "⊞" },
  { id: 8, label: "UNIFIED VEIL",    icon: "⊛" },
];

// ── REUSABLE COMPONENTS ───────────────────────────────────────────────────────
const SectionTitle = ({ icon, title, sub }) => (
  <div style={{ marginBottom: 24 }}>
    <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 6 }}>
      <span style={{ color: C.amber, fontSize: 20 }}>{icon}</span>
      <h2 style={{ color: C.amber, fontSize: 17, margin: 0, letterSpacing: 3, fontFamily: "'Courier New', monospace", fontWeight: 700 }}>
        {title}
      </h2>
    </div>
    {sub && <p style={{ color: C.muted, fontSize: 12, margin: 0, paddingLeft: 30, lineHeight: 1.8, fontFamily: "'Courier New', monospace" }}>{sub}</p>}
  </div>
);

const Tag = ({ label, color = C.amber }) => (
  <span style={{
    fontSize: 10, color, border: `1px solid ${color}50`, padding: "2px 7px",
    borderRadius: 2, fontFamily: "'Courier New', monospace", letterSpacing: 1,
    background: `${color}0d`,
  }}>{label}</span>
);

const Bar = ({ val, max = 100, color = C.amber }) => (
  <div style={{ background: C.dim, borderRadius: 2, height: 5, overflow: "hidden" }}>
    <div style={{ width: `${(val / max) * 100}%`, height: "100%", background: color, borderRadius: 2 }} />
  </div>
);

const Pill = ({ children, color = C.amber }) => (
  <span style={{
    display: "inline-block", fontSize: 10, color, background: `${color}15`,
    border: `1px solid ${color}30`, padding: "3px 8px", borderRadius: 2,
    fontFamily: "'Courier New', monospace", marginRight: 4, marginBottom: 4,
  }}>{children}</span>
);

// ── TAB 0 — WAR DOCTRINE ──────────────────────────────────────────────────────
function WarDoctrine() {
  const [tick, setTick] = useState(0);
  useEffect(() => { const t = setInterval(() => setTick(x => x + 1), 900); return () => clearInterval(t); }, []);

  const pyramid = [
    { level: "SYSTEM", label: "SoC / Chip-Level Validation", color: C.red,    pct: 15, desc: "Integration, regression, bench — expensive failures surface here" },
    { level: "SUB-SYS", label: "Subsystem / Cluster Sim",     color: C.amber,  pct: 25, desc: "Interface contracts, multi-IP interaction — medium cost to fix" },
    { level: "BLOCK",   label: "IP Block Verification ← WE FIGHT HERE", color: C.lime, pct: 60, desc: "All internal logic, edge cases, corner states — cheapest to fix" },
  ];

  const doctrines = [
    { n: "01", title: "BLOCK IS THE BATTLEFIELD",   body: "Every unverified assumption at block level becomes a system-level bug. Kill bugs where they're cheapest — at the source. A spec-traced block test suite is 10× cheaper than a chip re-spin." },
    { n: "02", title: "COVERAGE IS TRUTH",           body: "Simulation that cannot be measured has not happened. Every block must exit with a quantified, documented coverage closure report — functional, code, assertion, toggle, boundary, and protocol." },
    { n: "03", title: "SPEC ↔ TEST TRACEABILITY",   body: "No test without a spec node. No spec node without a test. The Spec Knowledge Graph enforces bidirectional traceability — gaps are flagged before simulation begins." },
    { n: "04", title: "METHODOLOGY LAYERING",        body: "UVM + SVA + CDC + FPV + Power-Aware + DFT-Aware — each methodology layer attacks a different class of bug. No single method is sufficient. DigitalVeil orchestrates all layers simultaneously." },
    { n: "05", title: "DFT IS FIRST-CLASS CITIZEN",  body: "DFT constraints are functional requirements, not afterthoughts. Scan coverage, BIST, JTAG, boundary scan — verified at block level so they compose correctly at chip level." },
    { n: "06", title: "SIGN-OFF IS A GATE, NOT A CEREMONY", body: "Sign-off means measurable criteria met — not 'no known bugs.' DigitalVeil's sign-off engine tracks 12 coverage dimensions and requires explicit closure or waiver before release." },
  ];

  return (
    <div>
      <SectionTitle icon="⊕" title="WAR DOCTRINE — WIN FIGHTS, WIN BATTLES, WIN WARS"
        sub="Block-level verification is not a task. It is a discipline of controlled, measurable quality warfare. DigitalVeil is the command system." />

      {/* Pyramid */}
      <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 6, padding: 20, marginBottom: 24 }}>
        <div style={{ color: C.amber, fontSize: 11, letterSpacing: 3, marginBottom: 16 }}>▸ VERIFICATION COST PYRAMID — WHERE WE FIGHT</div>
        {pyramid.map((p, i) => (
          <div key={i} style={{ marginBottom: 12 }}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
              <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
                <span style={{ color: p.color, fontSize: 12, fontWeight: 700, minWidth: 60 }}>{p.level}</span>
                <span style={{ color: C.text, fontSize: 12 }}>{p.label}</span>
              </div>
              <span style={{ color: p.color, fontSize: 12, fontWeight: 700 }}>{p.pct}%</span>
            </div>
            <Bar val={p.pct} color={p.color} />
            <div style={{ color: C.muted, fontSize: 11, marginTop: 3, paddingLeft: 70 }}>{p.desc}</div>
          </div>
        ))}
      </div>

      {/* Doctrine cards */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
        {doctrines.map((d, i) => (
          <div key={i} style={{
            background: C.card, border: `1px solid ${C.border}`, borderRadius: 6, padding: 14,
            borderLeft: `3px solid ${C.amber}60`,
          }}>
            <div style={{ display: "flex", gap: 8, marginBottom: 6, alignItems: "center" }}>
              <span style={{ color: C.amber, fontSize: 10, fontWeight: 700 }}>DOC-{d.n}</span>
              <span style={{ color: C.amber, fontSize: 12, fontWeight: 700 }}>{d.title}</span>
            </div>
            <div style={{ color: C.textDim, fontSize: 11, lineHeight: 1.7 }}>{d.body}</div>
          </div>
        ))}
      </div>

      {/* Live ticker */}
      <div style={{ marginTop: 20, background: C.dim, borderRadius: 4, padding: "8px 14px", display: "flex", gap: 20, flexWrap: "wrap" }}>
        {[["Block Coverage Avg", `${72 + (tick % 5)}%`, C.lime],
          ["Open Spec Nodes", `${14 - (tick % 3)}`, C.amber],
          ["Failing Assertions", `${3 + (tick % 2)}`, C.red],
          ["Sign-Off Ready IPs", `${7 + (tick % 2)}`, C.blue]].map(([l, v, c]) => (
          <div key={l} style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <span style={{ color: C.muted, fontSize: 10 }}>{l}:</span>
            <span style={{ color: c, fontSize: 13, fontWeight: 700, fontFamily: "'Courier New', monospace" }}>{v}</span>
          </div>
        ))}
        <span style={{ color: C.muted, fontSize: 10, marginLeft: "auto" }}>● LIVE SIM DASHBOARD</span>
      </div>
    </div>
  );
}

// ── TAB 1 — IP TAXONOMY ───────────────────────────────────────────────────────
function IPTaxonomy() {
  const [sel, setSel] = useState(null);

  const categories = [
    {
      id: "PROC", name: "PROCESSOR CORES", color: C.amber,
      types: ["RISC-V Core", "ARM Cortex-M/A", "DSP Core", "Vector/SIMD", "Custom ISA", "Coprocessor"],
      common: ["Reset sequence & boot vector", "Pipeline stage boundaries", "Exception/interrupt handler", "Clock enable / power gating I/F", "Debug port (JTAG/SWD) connectivity"],
      major: ["ISA compliance (every instruction)", "Pipeline hazard coverage (RAW/WAW/WAR)", "Branch prediction accuracy", "Cache coherency (multi-core)", "Out-of-order execution correctness", "Privilege level transitions", "Vector extension completeness", "MMU/MPU boundary conditions"],
      methodologies: ["ISA-directed constrained-random", "Coverage-driven UVM env", "Formal ISA property checking", "Co-simulation vs golden model (Spike/QEMU)", "Post-silicon correlation hooks"],
      dft: ["Scan chain insertion", "BIST for cache/SRAM", "JTAG TAP controller", "Boundary scan (IEEE 1149.1)", "Logic BIST (LBIST)", "TDR (Test Data Register) access"],
    },
    {
      id: "MEM", name: "MEMORY CONTROLLERS & SUBSYSTEMS", color: C.lime,
      types: ["DDR4/5 Controller", "LPDDR5 Controller", "HBM Controller", "SRAM/ROM Controller", "Flash Controller", "Cache Subsystem"],
      common: ["AXI/AHB interface compliance", "Clock domain crossing (CDC)", "Reset and initialization sequence", "ECC enable/disable modes", "Power management handshake"],
      major: ["JEDEC protocol compliance (all commands)", "Timing parameter margin (tRCD, tCL, tRAS)", "Refresh modes (auto, self, per-bank)", "ECC single-bit correct, double-bit detect", "Bank/rank/row/col address mapping", "ZQ calibration", "Write leveling / read training", "ODT/termination control"],
      methodologies: ["Protocol-specific VIP (Cadence/Synopsys DRAM VIP)", "Formal ECC property verification", "CDC analysis (Meridian/Questa CDC)", "Stress test: simultaneous bank conflict", "Power-aware sim (CPF/UPF)"],
      dft: ["MBIST (Memory BIST)", "Repair fuse interface", "March algorithm coverage", "DRAM training mode BIST", "Scan through memory wrapper"],
    },
    {
      id: "NOC", name: "INTERCONNECT & NoC", color: C.blue,
      types: ["AXI Crossbar", "AHB/APB Bridge", "NoC Mesh/Ring", "PCIe Controller", "USB Controller", "Ethernet MAC"],
      common: ["Bus protocol handshake (valid/ready)", "Backpressure / flow control", "Outstanding transaction limit", "Error response handling", "Arbitration priority"],
      major: ["Protocol spec compliance (every transaction type)", "Deadlock freedom proof", "Livelock detection", "QoS enforcement", "Address decode completeness", "Transaction ordering rules (AXI ID ordering)", "Split / retry transactions", "Coherency protocol (ACE/CHI)"],
      methodologies: ["Protocol VIP-based UVM", "Formal deadlock proof (model checking)", "Traffic generator stress testing", "Boundary condition injection", "Formal address decoder completeness"],
      dft: ["Scan stitching across clock domains", "BIST for embedded FIFOs", "Protocol loopback test mode", "Error injection register access", "Boundary scan at interface pins"],
    },
    {
      id: "CRYPTO", name: "SECURITY & CRYPTOGRAPHY", color: C.red,
      types: ["AES Engine", "SHA/Hash Core", "RSA/ECC Accelerator", "RNG / TRNG", "Secure Boot Controller", "Key Management Unit"],
      common: ["APB/AXI register interface", "Interrupt output", "DMA handshake", "Reset zeroization", "Clock gating compatibility"],
      major: ["NIST vector compliance (every algorithm mode)", "Side-channel resistance (power, timing)", "Key isolation / zeroization on reset", "RNG entropy qualification (NIST SP800-90B)", "Fault injection resilience", "Secure vs non-secure world isolation", "Anti-tamper response", "Known-answer test (KAT) pass"],
      methodologies: ["Formal functional equivalence (golden vs RTL)", "Constraint-random with protocol coverage", "Side-channel simulation (power trace)", "Formal information flow (taint analysis)", "Fault injection simulation (bit-flip)"],
      dft: ["KAT BIST mode (self-test)", "RNG health test register", "Scan disable in secure mode (mandatory)", "Bypass mode for production test", "Fuse access test interface"],
    },
    {
      id: "IO", name: "I/O & PHY DIGITAL", color: C.gold,
      types: ["GPIO Controller", "I2C/SPI/UART Controller", "PCIe PHY Digital", "USB PHY Digital", "MIPI (CSI/DSI) Controller", "SD/eMMC Controller"],
      common: ["APB register interface", "Clock prescaler logic", "Interrupt aggregation", "DMA request interface", "GPIO direction/pull control"],
      major: ["Protocol compliance (all modes/speeds)", "Framing error detection", "Start/stop bit integrity", "FIFO overflow/underflow handling", "Clock stretching (I2C)", "Multi-master arbitration", "Flow control (RTS/CTS)", "Protocol timing margins"],
      methodologies: ["Protocol VIP (all operating modes)", "Fault injection: noise, glitch, framing error", "CDC analysis at async boundaries", "Formal register access completeness", "Power domain crossing checks"],
      dft: ["Loopback test mode", "Internal BIST pattern generator", "Register read-back verification", "Clock divider output test", "Protocol analyzer hook"],
    },
    {
      id: "PWR", name: "POWER MANAGEMENT DIGITAL", color: "#c084fc",
      types: ["PMU Controller", "Clock Gating Logic", "Power Domain Controller", "DVFS Controller", "Retention Logic", "Power Sequencer"],
      common: ["UPF/CPF multi-voltage compliance", "Always-on domain definition", "Isolation cell insertion correctness", "Retention flop coverage", "Power-on reset sequencing"],
      major: ["Power state machine completeness", "Illegal state transition blocking", "Wake/sleep sequencing correctness", "Retention data integrity across power cycle", "Clock gating enable timing", "Supply ramp-up/ramp-down sequencing", "DVFS transition glitch-free", "PMU register lock after boot"],
      methodologies: ["Power-aware simulation (UPF mode)", "Formal power intent verification (PA-FV)", "Structural clock gating analysis", "Low-power CDC (multi-supply)", "Retention simulation: save/restore correctness"],
      dft: ["Power-on BIST trigger", "Clock enable chain test", "Retention flop scan access", "PMU state forced via JTAG", "Power domain boundary scan"],
    },
    {
      id: "ACCEL", name: "AI/ML & DSP ACCELERATORS", color: "#38bdf8",
      types: ["CNN/DNN Accelerator", "FFT Engine", "FIR/IIR Filter", "Matrix Multiply Unit", "Attention Mechanism Core", "Quantization Engine"],
      common: ["AXI-M DMA interface", "Configuration register (APB)", "Done/interrupt output", "Weight/activation memory I/F", "Precision mode config (INT8/FP16/BF16)"],
      major: ["Numerical accuracy vs golden model (Python/numpy)", "Dataflow completeness (all tensor shapes)", "Weight loading integrity", "Accumulator overflow handling", "Quantization rounding correctness", "Sparse computation correctness", "Throughput vs area efficiency metrics", "Stall/backpressure handling"],
      methodologies: ["Golden model co-simulation (Python hook)", "Coverage of all tensor dimension edge cases", "Overflow/saturation formal proof", "Random dataflow stress", "Timing accuracy: latency measurement per op"],
      dft: ["Accumulator BIST", "MAC array test mode", "SRAM/register file MBIST", "Scan through datapath", "Golden vector replay mode"],
    },
    {
      id: "SAFE", name: "FUNCTIONAL SAFETY (ISO 26262 / DO-254)", color: C.red,
      types: ["ECC Controller", "Watchdog Timer", "Lockstep Core", "Safety Island", "Error Logger", "CRC Engine"],
      common: ["ASIL-B/D requirement decomposition", "Safety mechanism activation time", "Diagnostic coverage metric", "Safe state output", "Error signaling interface (ERR_OUT)"],
      major: ["Fault detection coverage (FDC ≥ 99% for ASIL-D)", "Latent fault metric (LFM)", "Dual-core lockstep comparison", "Watchdog kick protocol completeness", "Safe state reachability (formal proof)", "No-common-cause failures isolation", "FMEA-linked test cases", "ISO 26262 Part 5 compliance per element"],
      methodologies: ["Formal safety property verification", "Fault injection (FI) simulation framework", "Mutation testing for diagnostic coverage", "FMEA-to-test traceability matrix", "DO-254 DAL-A evidence generation"],
      dft: ["Safety mechanism self-test (LBIST/MBIST)", "Error injection register", "Lockstep comparator test", "WDT open/closed loop test", "Diagnostic test library (DTL)"],
    },
  ];

  return (
    <div>
      <SectionTitle icon="◫" title="DIGITAL IP TAXONOMY — 8 BATTLE DOMAINS"
        sub="Every domain has: common setup reqs (universal) + major/specific reqs + verification methodologies + DFT strategy. Click to deploy." />

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
        {categories.map((cat, i) => {
          const isOpen = sel === i;
          return (
            <div key={i} onClick={() => setSel(isOpen ? null : i)} style={{
              background: C.card, border: `1px solid ${isOpen ? cat.color : C.border}`,
              borderLeft: `3px solid ${cat.color}`, borderRadius: 6, padding: 14,
              cursor: "pointer", transition: "all 0.18s",
            }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 8 }}>
                <div>
                  <div style={{ color: cat.color, fontSize: 10, letterSpacing: 2, marginBottom: 3 }}>{cat.id}</div>
                  <div style={{ color: C.text, fontSize: 13, fontWeight: 700 }}>{cat.name}</div>
                </div>
                <span style={{ color: cat.color, fontSize: 16 }}>{isOpen ? "▾" : "▸"}</span>
              </div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 3, marginBottom: isOpen ? 14 : 0 }}>
                {cat.types.map((t, j) => <Pill key={j} color={cat.color}>{t}</Pill>)}
              </div>

              {isOpen && (
                <div onClick={e => e.stopPropagation()}>
                  {[
                    ["COMMON SETUP REQUIREMENTS", cat.common, C.lime],
                    ["MAJOR / BLOCK-SPECIFIC REQUIREMENTS", cat.major, cat.color],
                    ["VERIFICATION METHODOLOGIES", cat.methodologies, C.blue],
                    ["DFT STRATEGY", cat.dft, C.red],
                  ].map(([label, items, col]) => (
                    <div key={label} style={{ marginBottom: 12 }}>
                      <div style={{ color: col, fontSize: 10, letterSpacing: 2, marginBottom: 6, borderBottom: `1px solid ${col}20`, paddingBottom: 3 }}>{label}</div>
                      {items.map((item, k) => (
                        <div key={k} style={{ fontSize: 11, color: C.textDim, paddingLeft: 10, borderLeft: `2px solid ${col}25`, marginBottom: 3, lineHeight: 1.6 }}>
                          → {item}
                        </div>
                      ))}
                    </div>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── TAB 2 — VPLAN ENGINE ─────────────────────────────────────────────────────
function VPlanEngine() {
  const phases = [
    {
      ph: "P0", name: "SPEC INTAKE & KG BINDING", color: C.amber, dur: "Days 1–3",
      tasks: [
        "Ingest specification (PDF/DOCX/Confluence) → KG extraction",
        "Auto-identify: parameters, modes, interfaces, constraints, exceptions",
        "Classify IP into taxonomy category → load domain template",
        "User declares: dependencies, adjacent blocks, system context, design concerns",
        "Flag under-specified nodes (missing limits, ambiguous modes)",
        "Generate structured VPlan skeleton from KG nodes",
      ]
    },
    {
      ph: "P1", name: "PLAN CONSTRUCTION", color: C.lime, dur: "Days 3–7",
      tasks: [
        "Test intent mapping: every spec node → ≥1 test intent",
        "Methodology assignment: UVM / FPV / CDC / PA-SIM / DFT per test class",
        "Coverage goal definition: functional, code, assertion, toggle, protocol, power",
        "DFT constraint extraction: scan mode, BIST enable, JTAG TAP setup",
        "Corner/mode matrix construction (reset modes × power states × operating modes)",
        "Dependency-aware sequencing: interface IPs verified before NoC, etc.",
        "Risk-weighted test priority (P0/P1/P2/P3) assignment",
        "Regression tier structure: smoke / nightly / full / sign-off",
      ]
    },
    {
      ph: "P2", name: "ENVIRONMENT BUILD", color: C.blue, dur: "Weeks 1–3",
      tasks: [
        "UVM testbench scaffold generation (Agent, Env, Scoreboard, Coverage)",
        "Protocol VIP instantiation (AXI/AHB/APB/custom protocol)",
        "Assertion (SVA) library: auto-generated from KG spec nodes",
        "Coverage group auto-generation: coverpoints, cross-coverage",
        "Clock domain map → CDC checker configuration",
        "UPF/CPF power intent import → power-aware sim setup",
        "JTAG TAP model + DFT mode controller",
        "Golden model hook (C/Python co-simulation interface)",
      ]
    },
    {
      ph: "P3", name: "EXECUTION & ANALYSIS", color: C.gold, dur: "Weeks 2–6",
      tasks: [
        "Regression dispatch: smoke → nightly → full (cloud or LSF)",
        "Real-time coverage dashboard: all 12 coverage dimensions",
        "Failure triage: waveform tag, assertion message, UVM phase, spec node",
        "Formal proof runs: FPV properties, CDC formal, power-intent formal",
        "CDC arc analysis: all domain crossings reported, waived, or fixed",
        "Power-aware: X-propagation, isolation check, retention correctness",
        "DFT regression: scan, BIST, JTAG TAP, boundary scan coverage",
        "Mutation testing: bug injection → diagnostic coverage measurement",
      ]
    },
    {
      ph: "P4", name: "CLOSURE & SIGN-OFF", color: C.red, dur: "Weeks 5–8",
      tasks: [
        "12-dimension coverage closure report",
        "Spec-to-test gap analysis: uncovered spec nodes listed",
        "Waiver management: formal approval, root-cause, risk classification",
        "Regression first-pass yield trend (target: >95% FPY)",
        "CDC sign-off report: all arcs synchronous, waived, or architected safe",
        "Power intent compliance: UPF vs implementation vs simulation consistent",
        "DFT completeness: scan, BIST, JTAG coverage ≥ target %",
        "Digital sign-off with engineer, lead, manager approval chain",
      ]
    },
  ];

  const [active, setActive] = useState(0);

  return (
    <div>
      <SectionTitle icon="◧" title="VPLAN ENGINE — AUTOMATED VERIFICATION PLANNING"
        sub="From spec ingestion to sign-off: a 5-phase automated planning pipeline. Every plan is spec-traced, methodology-assigned, and coverage-gated." />

      <div style={{ display: "flex", gap: 6, marginBottom: 20, flexWrap: "wrap" }}>
        {phases.map((p, i) => (
          <button key={i} onClick={() => setActive(i)} style={{
            padding: "8px 14px", borderRadius: 3, cursor: "pointer",
            fontFamily: "'Courier New', monospace", fontSize: 11, letterSpacing: 2,
            fontWeight: 700, background: active === i ? p.color : "transparent",
            color: active === i ? "#000" : p.color, border: `1.5px solid ${p.color}`,
          }}>
            {p.ph} {p.name.split(" ")[0]}
          </button>
        ))}
      </div>

      {(() => {
        const p = phases[active];
        return (
          <div style={{ border: `1px solid ${p.color}40`, borderRadius: 6, padding: 20, background: `${p.color}06` }}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 16, flexWrap: "wrap", gap: 8 }}>
              <div style={{ color: p.color, fontSize: 14, letterSpacing: 3 }}>{p.ph} — {p.name}</div>
              <Tag label={p.dur} color={p.color} />
            </div>
            {p.tasks.map((task, i) => (
              <div key={i} style={{ display: "flex", gap: 12, marginBottom: 10, alignItems: "flex-start" }}>
                <div style={{
                  minWidth: 22, height: 22, borderRadius: "50%", background: `${p.color}15`,
                  border: `1px solid ${p.color}`, color: p.color, fontSize: 10,
                  display: "flex", alignItems: "center", justifyContent: "center", fontWeight: 700
                }}>{i + 1}</div>
                <div style={{ color: C.text, fontSize: 12, paddingTop: 3, lineHeight: 1.7 }}>{task}</div>
              </div>
            ))}
          </div>
        );
      })()}

      {/* Auto-gen outputs */}
      <div style={{ marginTop: 20, background: C.card, border: `1px solid ${C.border}`, borderRadius: 6, padding: 16 }}>
        <div style={{ color: C.amber, fontSize: 11, letterSpacing: 2, marginBottom: 12 }}>▸ VPLAN ENGINE AUTO-GENERATES</div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 8 }}>
          {[
            ["VPlan Document", "Structured plan with all test intents, methodology, coverage goals"],
            ["UVM Scaffold", "Top-level TB, Env, Agents, Scoreboards, Coverage groups"],
            ["SVA Library", "Assertions auto-derived from spec KG nodes"],
            ["CDC Report Template", "Pre-populated with all identified clock domains"],
            ["Regression Makefile", "Tiered suite: smoke/nightly/full/signoff targets"],
            ["Sign-Off Checklist", "12-dimension closure tracker, waiver log template"],
          ].map(([t, d], i) => (
            <div key={i} style={{ background: C.surface, border: `1px solid ${C.dim}`, borderRadius: 4, padding: 10 }}>
              <div style={{ color: C.amber, fontSize: 11, marginBottom: 4 }}>{t}</div>
              <div style={{ color: C.muted, fontSize: 10, lineHeight: 1.6 }}>{d}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ── TAB 3 — METHODOLOGY ───────────────────────────────────────────────────────
function Methodology() {
  const [selMethod, setSelMethod] = useState(0);

  const methods = [
    {
      id: "UVM", name: "UVM / CONSTRAINED RANDOM", color: C.amber, icon: "◈",
      tagline: "Industry-standard structured testbench for functional coverage-driven verification",
      what: "Universal Verification Methodology: layered TB architecture with reusable agents, scoreboards, coverage, and sequences.",
      components: ["UVM Agent (Driver, Monitor, Sequencer)", "Reference Model / Scoreboard", "Functional Coverage Groups", "Constrained Random Stimulus", "Phase Control (build/connect/run/check/final)", "RAL (Register Abstraction Layer)", "Factory overrides for reuse"],
      blockApply: ["All digital IPs — primary methodology", "Register interface verification (RAL)", "Protocol compliance (AXI/APB/custom)", "Datapath stress testing"],
      coverage: ["Functional coverpoints per spec feature", "Cross-coverage (mode × stimulus)", "Protocol state machine coverage", "Transition coverage between modes"],
      tools: ["Synopsys VCS + Verdi", "Cadence Xcelium + Simvision", "Mentor Questa", "Aldec Riviera-PRO"],
    },
    {
      id: "FPV", name: "FORMAL PROPERTY VERIFICATION", color: C.lime, icon: "◉",
      tagline: "Mathematical proof of correctness — no simulation needed, exhaustive by nature",
      what: "FPV uses model checking to prove SVA properties hold for ALL possible inputs — not just simulated ones. Finds corner cases simulation misses.",
      components: ["SVA Property Library (from spec KG)", "Assume/Guarantee contracts", "Cover properties (reachability)", "Proof-bounded (k-steps) vs unbounded", "Counterexample witness analysis", "Abstraction / cut-points for scalability"],
      blockApply: ["Deadlock/livelock freedom (NoC, arbiters)", "Safety-critical properties (FSM completeness)", "Protocol ordering rules (AXI ID, CHI)", "Reset correctness (all regs to reset value)", "Arithmetic overflow / underflow"],
      coverage: ["Proof status: proven / bounded / falsified", "Cover reachability %", "Vacuity check (antecedent fires?)", "Witness depth (complexity measure)"],
      tools: ["Cadence JasperGold", "Synopsys VC Formal", "OneSpin 360", "Mentor/Siemens Questa Formal"],
    },
    {
      id: "CDC", name: "CLOCK DOMAIN CROSSING (CDC)", color: C.blue, icon: "◑",
      tagline: "Every signal crossing a clock boundary is a potential metastability failure — all must be verified",
      what: "CDC analysis identifies all multi-clock crossings, verifies synchronizer correctness, checks protocol safety (gray code, handshake, async FIFO).",
      components: ["Structural CDC extraction (all crossing arcs)", "Synchronizer topology verification", "Protocol analysis (2FF, MCP, bus, async FIFO)", "False path qualification", "Metastability window analysis", "Reconvergence (glitch) detection"],
      blockApply: ["ALL IPs with >1 clock domain", "SoC interfaces (HCLK/PCLK crossings)", "Memory controllers (core vs PHY clock)", "USB/PCIe (ref_clk vs core_clk)"],
      coverage: ["Arc count: total / analyzed / waived", "Protocol coverage: each type verified", "False path ratio", "Synchronizer depth per arc"],
      tools: ["Synopsys SpyGlass CDC", "Cadence Meridian CDC", "Mentor Questa CDC", "Real Intent Meridian"],
    },
    {
      id: "PAWM", name: "POWER-AWARE VERIFICATION (UPF/CPF)", color: "#c084fc", icon: "◐",
      tagline: "Verify power intent correctness: isolation, retention, X-propagation, supply sequencing",
      what: "Power-aware simulation applies UPF/CPF to insert and verify isolation cells, retention flops, level shifters — catching power bugs that functional sim misses.",
      components: ["UPF/CPF intent import & consistency check", "Isolation cell verification (enable timing)", "Retention flop: save/restore correctness", "Level-shifter X-propagation blocking", "Power state machine completeness", "Supply ramp X-propagation analysis"],
      blockApply: ["All IPs with power gating", "DVFS controllers", "PMU / power sequencers", "Always-on retention domains"],
      coverage: ["Power state coverage: all legal states hit", "Transition coverage: all valid transitions", "Retention coverage: save/restore per mode", "X-coverage: no X propagation at outputs"],
      tools: ["Cadence Xcelium + Voltus-FI", "Synopsys VCS + MVRC", "Mentor Questa Power Aware", "Synopsys VC LP"],
    },
    {
      id: "SVA", name: "ASSERTION-BASED VERIFICATION (ABV)", color: C.gold, icon: "◆",
      tagline: "Encode design intent as machine-checkable properties — the spec made executable",
      what: "SVA assertions embedded in RTL or bound externally. Checked every clock cycle. Violation = immediate, traceable failure with spec reference.",
      components: ["Concurrent assertions (temporal properties)", "Immediate assertions (combinatorial checks)", "Cover properties (feature reachability)", "Assume statements (environment constraints)", "Sequence operators (##, |=>, |->)", "Clocking blocks + default disable iff"],
      blockApply: ["Protocol handshake (valid→ready sequencing)", "FSM: no illegal state, no deadlock", "Register field access rules (RO, WO, W1C)", "FIFO: overflow/underflow never asserted", "Reset: all registers to reset value"],
      coverage: ["Assertion hit count per property", "Vacuity check (did antecedent fire?)", "Cover hit count (feature exercised?)", "Assertion failure spectral analysis"],
      tools: ["Native sim: VCS/Xcelium/Questa", "Formal: JasperGold / VC Formal", "SpecIF (spec-to-SVA automation)", "DVCon standard libraries"],
    },
    {
      id: "LINT", name: "LINT / STATIC ANALYSIS", color: C.red, icon: "◌",
      tagline: "Catch RTL quality issues before simulation: latches, CDC, reset issues, naming, synthesis issues",
      what: "Static RTL analysis for coding style violations, inferred latches, incomplete sensitivity lists, unintentional clock gating, and synthesis-simulation mismatch.",
      components: ["Latch inference detection", "Incomplete case statement check", "Undriven / multi-driven net detection", "Clock gating inferred (not intended)", "Naming convention enforcement", "Async reset synchronization check", "X-assignment analysis"],
      blockApply: ["Every IP, every RTL commit (CI/CD gate)", "Pre-simulation quality gate", "Synthesis readiness check", "Foundry rule compliance"],
      coverage: ["Violation count by severity (Fatal/Error/Warn/Info)", "Waiver ratio (target: <5% of errors waived)", "Rule coverage: all lint rules active", "CI gate: 0 fatal violations to proceed"],
      tools: ["Synopsys SpyGlass", "Cadence HAL", "Mentor Questa Lint", "Aldec ALINT-PRO"],
    },
    {
      id: "MUTTEST", name: "MUTATION TESTING", color: "#fb923c", icon: "◎",
      tagline: "Prove your testbench can actually catch bugs by injecting them deliberately",
      what: "Automated RTL mutation: flip operators, toggle conditions, delete statements. Measure what % of mutations are caught by your regression — this is your true diagnostic coverage.",
      components: ["RTL mutation operators (AOR, LOR, ROR, SDL...)", "Mutation-per-spec-node mapping", "Equivalent mutation detection", "Mutation kill rate per test", "Coverage-gap → mutation alive correlation", "Regression diagnostic score"],
      blockApply: ["Safety-critical IP (ISO 26262 FDC requirement)", "Crypto IP (correctness-critical)", "Arbiter / priority logic", "Error detection & correction logic"],
      coverage: ["Mutation kill rate (target: >95%)", "Alive mutations with root-cause", "Per-operator kill rates", "Spec-node diagnostic coverage mapping"],
      tools: ["Synopsys Certitude", "Cadence vManager Mutation", "Aldec Spec-TRACER", "Open-source: mull (LLVM)"],
    },
    {
      id: "EMUL", name: "EMULATION & PROTOTYPING", color: "#22d3ee", icon: "◻",
      tagline: "Hardware-speed verification for software bring-up, long-duration tests, and real-world stimulus",
      what: "FPGA/emulator-based acceleration for scenarios that take weeks in simulation: OS boot, protocol stacks, real-world traffic. Block-level: used for compliance and stress.",
      components: ["RTL-to-emulator compile flow", "In-circuit emulation (ICE) probing", "Transaction-accurate bus models", "Hardware/software co-verification", "Real-world stimulus injection", "Logic analyzer integration"],
      blockApply: ["CPU cores (OS boot, software stack)", "Memory controllers (real DRAM training)", "USB/PCIe (protocol stack bring-up)", "AI accelerators (full inference workload)"],
      coverage: ["Software test coverage (code coverage from SW)", "Protocol soak coverage (hours of traffic)", "Stress: memory error injection rate", "Performance: throughput vs spec"],
      tools: ["Cadence Palladium Z2", "Synopsys ZeBu Server-4", "Mentor Veloce Strato", "FPGA: Xilinx VCU118 / Intel Stratix"],
    },
  ];

  return (
    <div>
      <SectionTitle icon="◨" title="VERIFICATION METHODOLOGY ARSENAL — 8 WEAPONS"
        sub="Each methodology targets a different class of bugs. DigitalVeil orchestrates all layers simultaneously, guided by IP type and risk profile." />

      <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 20 }}>
        {methods.map((m, i) => (
          <button key={i} onClick={() => setSelMethod(i)} style={{
            padding: "7px 12px", borderRadius: 3, cursor: "pointer",
            fontFamily: "'Courier New', monospace", fontSize: 10, letterSpacing: 2,
            background: selMethod === i ? m.color : "transparent",
            color: selMethod === i ? "#000" : m.color, border: `1.5px solid ${m.color}`,
          }}>{m.id}</button>
        ))}
      </div>

      {(() => {
        const m = methods[selMethod];
        return (
          <div style={{ border: `1px solid ${m.color}40`, borderRadius: 6, padding: 20, background: `${m.color}05` }}>
            <div style={{ display: "flex", gap: 10, alignItems: "center", marginBottom: 6 }}>
              <span style={{ color: m.color, fontSize: 22 }}>{m.icon}</span>
              <div>
                <div style={{ color: m.color, fontSize: 15, fontWeight: 700 }}>{m.name}</div>
                <div style={{ color: C.muted, fontSize: 11, fontStyle: "italic" }}>{m.tagline}</div>
              </div>
            </div>
            <div style={{ color: C.textDim, fontSize: 12, marginBottom: 16, lineHeight: 1.7, paddingLeft: 32 }}>{m.what}</div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
              {[
                ["KEY COMPONENTS", m.components, m.color],
                ["BLOCK-LEVEL APPLICATION", m.blockApply, C.lime],
                ["COVERAGE METRICS", m.coverage, C.gold],
                ["TOOL ECOSYSTEM", m.tools, C.blue],
              ].map(([label, items, col]) => (
                <div key={label} style={{ background: C.card, border: `1px solid ${col}20`, borderRadius: 4, padding: 12 }}>
                  <div style={{ color: col, fontSize: 10, letterSpacing: 2, marginBottom: 8 }}>{label}</div>
                  {items.map((item, k) => (
                    <div key={k} style={{ fontSize: 11, color: C.textDim, marginBottom: 4, paddingLeft: 8, borderLeft: `2px solid ${col}30` }}>→ {item}</div>
                  ))}
                </div>
              ))}
            </div>
          </div>
        );
      })()}
    </div>
  );
}

// ── TAB 4 — COVERAGE MATRIX ───────────────────────────────────────────────────
function CoverageMatrix() {
  const dims = [
    {
      dim: "01", name: "CODE COVERAGE", color: C.amber, target: "95%",
      metrics: [
        ["Line Coverage", "Every RTL line executed at least once", "Sim", "% lines hit"],
        ["Branch Coverage", "Both taken/not-taken for every if/case", "Sim", "% branches hit"],
        ["Condition Coverage", "Every boolean sub-expression T and F", "Sim", "% conditions hit"],
        ["Toggle Coverage", "Every net toggled 0→1 and 1→0", "Sim", "% nets toggled"],
        ["Expression Coverage", "All operand combinations in expressions", "Sim", "% expressions hit"],
        ["FSM State Coverage", "Every state reached", "Sim", "% states hit"],
        ["FSM Transition Coverage", "Every valid arc traversed", "Sim", "% arcs hit"],
      ]
    },
    {
      dim: "02", name: "FUNCTIONAL COVERAGE", color: C.lime, target: "100%",
      metrics: [
        ["Feature Coverpoints", "Spec feature exercised (derived from KG nodes)", "UVM/Sim", "% features hit"],
        ["Cross Coverage", "Mode × stimulus × configuration combinations", "UVM", "% cross bins hit"],
        ["Protocol State Machine", "All protocol states and transitions", "VIP/Sim", "% states hit"],
        ["Register Field Coverage", "All R/W/access-type fields read and written", "RAL/Sim", "% fields accessed"],
        ["Boundary Conditions", "Min, max, overflow, underflow values exercised", "CDR", "% boundaries hit"],
        ["Mode Combinations", "Every operating mode exercised", "Directed", "% modes hit"],
        ["Error Injection Coverage", "Each error type injected and detected", "Directed", "% error types"],
      ]
    },
    {
      dim: "03", name: "ASSERTION COVERAGE", color: C.blue, target: "100% (0 failures)",
      metrics: [
        ["Assertion Hit Count", "Antecedent fires ≥N times", "SVA/Sim+Formal", "count per property"],
        ["Vacuity Rate", "Antecedent never fires (dead assertion)", "SVA", "% non-vacuous"],
        ["Cover Property Hit", "Feature reachable (cover fires)", "SVA/FPV", "% covers hit"],
        ["Proof Status (FPV)", "Property proven / bounded / falsified", "FPV", "proven/bounded/%"],
        ["Assertion Failure Rate", "Target: 0 unexpected failures", "Sim", "failure count"],
        ["Counterexample Length", "Witness depth for FPV", "FPV", "clock cycles"],
      ]
    },
    {
      dim: "04", name: "CDC COVERAGE", color: "#c084fc", target: "100% analyzed",
      metrics: [
        ["Total Crossing Arcs", "All multi-domain crossings identified", "CDC Tool", "arc count"],
        ["Synchronizer Verified", "Synchronizer topology proven correct", "CDC Formal", "% arcs verified"],
        ["Protocol Coverage", "2FF/MCP/Handshake/AsyncFIFO analyzed", "CDC Tool", "protocol type count"],
        ["Reconvergence Check", "Glitch-prone reconvergence paths analyzed", "CDC Tool", "path count"],
        ["False Path Justified", "Each waiver has formal justification", "CDC Tool", "waiver count"],
        ["Gray Code Monotonic", "FIFO pointer encoding verified", "FPV", "pass/fail"],
      ]
    },
    {
      dim: "05", name: "POWER-AWARE COVERAGE", color: "#fb923c", target: "All states covered",
      metrics: [
        ["Power State Coverage", "All legal power states exercised in sim", "PA-Sim", "% states hit"],
        ["Retention Save/Restore", "Data integrity across power cycle", "PA-Sim", "% retention paths"],
        ["Isolation Cell Active", "Isolation fires when domain off", "PA-Sim", "pass/fail per cell"],
        ["X-Propagation Clean", "No X at primary outputs from supply ramps", "PA-Sim", "X count"],
        ["UPF Consistency", "Intent matches RTL power structure", "PA-FV", "pass/fail"],
        ["Sequencing Correctness", "Supply ramp order verified", "PA-Sim", "sequence count"],
      ]
    },
    {
      dim: "06", name: "DFT COVERAGE", color: C.red, target: "≥98% scan, ≥95% BIST",
      metrics: [
        ["Scan Coverage", "% faults detected by scan patterns", "ATPG", "% fault coverage"],
        ["BIST Coverage", "MBIST/LBIST autonomous test coverage", "BIST", "% coverage"],
        ["JTAG TAP Coverage", "All TAP instructions exercised", "Sim/ATE", "% instructions hit"],
        ["DFT Pin Controllability", "Each DFT pin driven to all values", "Sim", "pass/fail per pin"],
        ["DFT Pin Observability", "DFT outputs observable at scan-out", "Sim", "pass/fail per pin"],
        ["Boundary Scan Coverage", "IEEE 1149.1 instructions verified", "BScan tool", "% instructions"],
        ["Pattern Count Efficiency", "ATPG patterns / fault coverage ratio", "ATPG", "patterns/% coverage"],
      ]
    },
    {
      dim: "07", name: "PROTOCOL COVERAGE", color: C.gold, target: "100% of spec transactions",
      metrics: [
        ["Transaction Type Coverage", "All defined transaction types issued", "VIP", "% types hit"],
        ["Response Coverage", "All legal responses received and checked", "VIP/SB", "% responses hit"],
        ["Error Response Coverage", "All error/fault responses tested", "VIP/Directed", "% error resps hit"],
        ["Outstanding Txn Coverage", "Max outstanding depth exercised", "CDR", "depth buckets"],
        ["Burst Length Coverage", "All legal burst lengths tested", "VIP/CDR", "length bins"],
        ["Atomic Operation Coverage", "Read-Modify-Write atomic combos", "Directed", "operation count"],
      ]
    },
    {
      dim: "08", name: "RESET COVERAGE", color: C.lime, target: "All reset scenarios",
      metrics: [
        ["Cold Reset", "Full power-on reset from defined state", "Directed", "pass/fail"],
        ["Warm Reset", "Reset during active operation", "Directed", "pass/fail"],
        ["Domain-specific Reset", "Per-domain async reset independence", "Directed", "domain count"],
        ["Register Reset Value", "All regs return to spec reset value", "RAL/Directed", "% regs verified"],
        ["Mid-Transaction Reset", "Reset asserted during outstanding txn", "CDR/Directed", "scenario count"],
        ["Reset Synchronizer", "Async assert / sync deassert verified", "SVA/CDC", "pass/fail"],
      ]
    },
    {
      dim: "09", name: "PERFORMANCE COVERAGE", color: C.amber, target: "All throughput/latency bins",
      metrics: [
        ["Throughput", "Peak and sustained bandwidth vs spec", "Perf Model", "MB/s or ops/s"],
        ["Latency", "Avg/max/P99 latency per operation type", "Perf Monitor", "cycles"],
        ["Backpressure Behavior", "Throughput under sustained backpressure", "Stress Sim", "% of peak"],
        ["Queue/FIFO Depth", "All fill-level bins exercised", "CDR", "depth bins"],
        ["Arbitration Fairness", "All requestors get service within deadline", "Coverage", "starvation count"],
      ]
    },
    {
      dim: "10", name: "FAULT/SAFETY COVERAGE", color: C.red, target: "FDC ≥99% (ASIL-D)",
      metrics: [
        ["Fault Detection Coverage (FDC)", "% permanent faults detected by safety mechanism", "FI-Sim", "% FDC"],
        ["Latent Fault Metric (LFM)", "Latent faults per hour (target ≤ threshold)", "FI-Sim", "failures/hr"],
        ["Mutation Kill Rate", "% injected mutations caught by regression", "Mutation", "% kill rate"],
        ["Diagnostic Coverage", "Safety mechanism detects fault within exposure time", "FI-Sim", "% DC"],
        ["Safe State Reachability", "IP reaches safe state on any single fault", "FPV", "proven/bounded"],
      ]
    },
    {
      dim: "11", name: "INTERFACE CONTRACT COVERAGE", color: C.blue, target: "100% contract terms",
      metrics: [
        ["Handshake Protocol", "Valid/ready contract never violated", "SVA", "violation count"],
        ["Data Integrity", "No data corruption across interface", "Scoreboard", "mismatch count"],
        ["Timing Contract", "Setup/hold on synchronous interfaces", "SVA/STA", "violations"],
        ["Backpressure Propagation", "Ready de-assertion propagated correctly", "SVA/Sim", "pass/fail"],
        ["Out-of-Sequence Detection", "Protocol ordering rules enforced", "VIP/SVA", "OOS count"],
      ]
    },
    {
      dim: "12", name: "STRUCTURAL / LINT COVERAGE", color: C.gold, target: "0 Fatal / 0 Error",
      metrics: [
        ["Latch Count", "Target: 0 unintended latches", "Lint", "latch count"],
        ["Multi-driven Nets", "Target: 0 multi-drive conflicts", "Lint", "net count"],
        ["Undriven Inputs", "Target: 0 floating primary inputs", "Lint", "input count"],
        ["Naming Violations", "Coding style compliance", "Lint", "violation count"],
        ["Synthesis/Sim Mismatch Risk", "Constructs that differ pre/post-synthesis", "Lint", "risk count"],
      ]
    },
  ];

  const [selDim, setSelDim] = useState(0);

  return (
    <div>
      <SectionTitle icon="▦" title="12-DIMENSION COVERAGE MATRIX"
        sub="Digital verification measured across 12 orthogonal dimensions. Sign-off requires closure on ALL dimensions. No dimension can be omitted." />

      <div style={{ display: "flex", gap: 5, flexWrap: "wrap", marginBottom: 20 }}>
        {dims.map((d, i) => (
          <button key={i} onClick={() => setSelDim(i)} style={{
            padding: "6px 10px", borderRadius: 3, cursor: "pointer",
            fontFamily: "'Courier New', monospace", fontSize: 9, letterSpacing: 1,
            background: selDim === i ? d.color : "transparent",
            color: selDim === i ? "#000" : d.color, border: `1px solid ${d.color}60`,
          }}>D{d.dim}</button>
        ))}
      </div>

      {(() => {
        const d = dims[selDim];
        return (
          <div style={{ border: `1px solid ${d.color}40`, borderRadius: 6, padding: 18, background: `${d.color}05` }}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 16, alignItems: "center" }}>
              <div style={{ color: d.color, fontSize: 14, fontWeight: 700, letterSpacing: 2 }}>D{d.dim} — {d.name}</div>
              <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                <span style={{ color: C.muted, fontSize: 10 }}>TARGET:</span>
                <Tag label={d.target} color={d.color} />
              </div>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1.4fr 2fr 0.8fr 1fr", gap: 2, marginBottom: 4 }}>
              {["METRIC", "DESCRIPTION", "METHOD", "UNIT/MEASURE"].map(h => (
                <div key={h} style={{ fontSize: 9, color: C.muted, letterSpacing: 1, padding: "4px 8px" }}>{h}</div>
              ))}
              {d.metrics.map(([name, desc, method, unit], i) => [
                <div key={`n${i}`} style={{ fontSize: 11, color: C.text, padding: "8px 8px", background: C.card, borderRadius: 3 }}>{name}</div>,
                <div key={`d${i}`} style={{ fontSize: 10, color: C.muted, padding: "8px 8px", background: C.card, borderRadius: 3 }}>{desc}</div>,
                <div key={`m${i}`} style={{ fontSize: 10, color: d.color, padding: "8px 8px", background: C.card, borderRadius: 3 }}>{method}</div>,
                <div key={`u${i}`} style={{ fontSize: 10, color: C.gold, padding: "8px 8px", background: C.card, borderRadius: 3, fontStyle: "italic" }}>{unit}</div>,
              ])}
            </div>
          </div>
        );
      })()}

      <div style={{ marginTop: 16, background: C.card, border: `1px solid ${C.dim}`, borderRadius: 6, padding: 14 }}>
        <div style={{ color: C.amber, fontSize: 11, letterSpacing: 2, marginBottom: 10 }}>▸ COVERAGE CLOSURE DASHBOARD (ALL 12 DIMS)</div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 6 }}>
          {dims.map((d, i) => {
            const fakeVal = [88, 94, 97, 91, 86, 93, 99, 100, 82, 89, 96, 100][i];
            const col = fakeVal >= 95 ? C.lime : fakeVal >= 85 ? C.amber : C.red;
            return (
              <div key={i} onClick={() => setSelDim(i)} style={{
                background: C.surface, border: `1px solid ${col}30`, borderRadius: 4, padding: 8, cursor: "pointer"
              }}>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 5 }}>
                  <span style={{ color: C.muted, fontSize: 9 }}>D{d.dim}</span>
                  <span style={{ color: col, fontSize: 11, fontWeight: 700 }}>{fakeVal}%</span>
                </div>
                <Bar val={fakeVal} color={col} />
                <div style={{ color: C.textDim, fontSize: 9, marginTop: 4 }}>{d.name.split(" ").slice(0, 2).join(" ")}</div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

// ── TAB 5 — DFT ARSENAL ───────────────────────────────────────────────────────
function DFTArsenal() {
  const weapons = [
    {
      name: "SCAN INSERTION & ATPG", color: C.red,
      what: "Scan chains make every flip-flop controllable and observable. ATPG generates minimum patterns for maximum fault coverage.",
      reqs: ["Scan enable (SE) pin fully controlled", "All flip-flops in scan chain", "No asynchronous reset/set during scan", "Clock gating bypassed in scan mode", "Scan-safe multiplexers"],
      coverage: ["Stuck-at fault coverage ≥ 98%", "Transition fault coverage ≥ 95%", "Path delay fault coverage ≥ 90%", "IDDQ test patterns generated", "Scan chain continuity verified"],
      blockTest: ["SE force high → all clocks running → shift patterns", "Compare capture vs expected at scan_out", "Chain length verification", "Scan shift frequency tolerance"],
    },
    {
      name: "MEMORY BIST (MBIST)", color: C.amber,
      what: "Autonomous hardware self-test for all embedded memories: SRAMs, ROMs, register files, FIFOs.",
      reqs: ["MBIST controller instantiated per memory bank", "March algorithms: March-C, March-LR, March-SS", "Repair interface (fuse/eFuse) connected", "MBIST GO/DONE/FAIL signals observable", "Redundancy analysis (row/col repair)"],
      coverage: ["All memory cells written and read", "Adjacent cell coupling (March-C−)", "Address decoder faults", "Stuck-at cell faults", "Repair yield improvement measurement"],
      blockTest: ["Assert MBIST_EN → run algorithm → check MBIST_PASS", "Inject known bit-flip → verify MBIST_FAIL", "Repair: inject fault → repair → re-test → MBIST_PASS"],
    },
    {
      name: "LOGIC BIST (LBIST)", color: C.lime,
      what: "On-chip pseudo-random test pattern generation + MISR signature compression for autonomous logic testing at functional speed.",
      reqs: ["PRPG (pattern generator) seeded and verified", "MISR signature matches golden", "LBIST clock separate from functional", "LBIST mode disables normal I/O", "Safety: LBIST activated at power-on or via JTAG"],
      coverage: ["Random pattern fault coverage ≥ 90%", "MISR signature match vs golden", "LBIST duration per mode", "Clock frequency stress during LBIST"],
      blockTest: ["Trigger LBIST via JTAG → compare MISR to golden signature", "Inject RTL fault → verify signature changes (sensitivity)"],
    },
    {
      name: "JTAG / IEEE 1149.1", color: C.blue,
      what: "Standard debug and test access port. TAP controller, instruction register, data registers. Gateway for all internal DFT access.",
      reqs: ["TAP controller FSM (16 states) fully verified", "All mandatory instructions: BYPASS, IDCODE, SAMPLE/PRELOAD, EXTEST", "User-defined instructions for internal access", "TDI/TDO chain verified", "TCK independent from functional clock"],
      coverage: ["All 16 TAP FSM states reachable", "All instructions exercised", "IDCODE correct device identification", "Boundary scan cell capture/update verified", "Chain scan: TDI→TDO integrity"],
      blockTest: ["Drive TMS sequence → verify TAP state machine", "Issue each instruction → verify TDO response", "Read IDCODE → verify against device register"],
    },
    {
      name: "BOUNDARY SCAN (IEEE 1149.1 BScan)", color: C.gold,
      what: "External pin test via boundary scan register. Enables board-level test, interconnect test, and cluster-level IP testing without probing.",
      reqs: ["BSR cell at every I/O pin", "EXTEST, SAMPLE/PRELOAD, INTEST support", "Interconnect test mode enabled", "BSR cell capture reflects real pin state", "Safe values loaded during functional mode"],
      coverage: ["All I/O pins in BSR chain", "EXTEST: drive/sense all pin combinations", "SAMPLE: capture functional values", "INTEST: verify internal logic via BSR"],
      blockTest: ["EXTEST: force pin values via BSR → verify adjacent block sees expected values", "SAMPLE: capture known output pattern"],
    },
    {
      name: "DFT STRUCTURAL CHECKS", color: "#c084fc",
      what: "Static DFT rules: clock gating, asynchronous resets, glitch-free muxes, test isolation — all checked before ATPG.",
      reqs: ["No combinatorial feedback loops in scan mode", "All async resets deasserted in scan shift", "Clock enable bypassed by scan enable", "Test mode isolation from functional outputs", "No glitches on test clock during shift"],
      coverage: ["DRC rule count: 0 violations", "Clock domain count verified", "Async reset synchronizer DFT-safe", "Isolation rule: outputs gated in test mode"],
      blockTest: ["Run EDA DFT DRC → 0 violations before ATPG", "Verify SE→scan shift: no glitch on functional outputs"],
    },
  ];

  const [sel, setSel] = useState(0);

  return (
    <div>
      <SectionTitle icon="◩" title="DFT ARSENAL — DESIGN FOR TEST AT BLOCK LEVEL"
        sub="DFT is a first-class verification requirement. Every pin, every memory, every flop must be testable. These are the weapons." />

      <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 18 }}>
        {weapons.map((w, i) => (
          <button key={i} onClick={() => setSel(i)} style={{
            padding: "7px 12px", borderRadius: 3, cursor: "pointer",
            fontFamily: "'Courier New', monospace", fontSize: 10, letterSpacing: 1,
            background: sel === i ? w.color : "transparent",
            color: sel === i ? "#000" : w.color, border: `1.5px solid ${w.color}60`,
          }}>{w.name.split(" ")[0]}{w.name.split(" ").length > 2 ? "..." : ""}</button>
        ))}
      </div>

      {(() => {
        const w = weapons[sel];
        return (
          <div style={{ border: `1px solid ${w.color}40`, borderRadius: 6, padding: 18, background: `${w.color}05` }}>
            <div style={{ color: w.color, fontSize: 14, fontWeight: 700, marginBottom: 6 }}>{w.name}</div>
            <div style={{ color: C.textDim, fontSize: 12, marginBottom: 16, lineHeight: 1.7 }}>{w.what}</div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12 }}>
              {[["DFT REQUIREMENTS", w.reqs, w.color], ["COVERAGE METRICS", w.coverage, C.gold], ["BLOCK-LEVEL TESTS", w.blockTest, C.lime]].map(([label, items, col]) => (
                <div key={label} style={{ background: C.card, border: `1px solid ${col}20`, borderRadius: 4, padding: 12 }}>
                  <div style={{ color: col, fontSize: 10, letterSpacing: 2, marginBottom: 8 }}>{label}</div>
                  {items.map((item, k) => (
                    <div key={k} style={{ fontSize: 11, color: C.textDim, marginBottom: 5, paddingLeft: 8, borderLeft: `2px solid ${col}30`, lineHeight: 1.6 }}>→ {item}</div>
                  ))}
                </div>
              ))}
            </div>
          </div>
        );
      })()}

      <div style={{ marginTop: 18, background: C.card, border: `1px solid ${C.border}`, borderRadius: 6, padding: 14 }}>
        <div style={{ color: C.red, fontSize: 11, letterSpacing: 2, marginBottom: 10 }}>▸ DFT SIGN-OFF CHECKLIST (ALL ITEMS REQUIRED)</div>
        {[
          ["Scan Chain Closure", "All flip-flops scanned, chain continuity verified, no broken chains"],
          ["ATPG Patterns Generated", "Stuck-at ≥98%, Transition ≥95%, patterns validated in simulation"],
          ["MBIST Pass", "All memories: GO/DONE/FAIL verified, repair flow tested"],
          ["LBIST Signature Match", "MISR signature matches golden, sensitivity verified"],
          ["JTAG TAP Compliance", "All 16 states, all instructions, IDCODE correct"],
          ["Boundary Scan Complete", "All I/O pins in BSR, EXTEST/SAMPLE/INTEST verified"],
          ["DFT DRC Clean", "Zero violations, clock gating DFT-safe, async reset safe"],
          ["DFT Mode Isolation", "Functional outputs gated in all test modes"],
        ].map(([item, desc], i) => (
          <div key={i} style={{ display: "flex", gap: 12, marginBottom: 7, alignItems: "flex-start" }}>
            <div style={{ color: C.lime, fontSize: 12, minWidth: 16 }}>□</div>
            <div>
              <span style={{ color: C.text, fontSize: 12, fontWeight: 700 }}>{item}: </span>
              <span style={{ color: C.muted, fontSize: 11 }}>{desc}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── TAB 6 — SPEC KG ───────────────────────────────────────────────────────────
function SpecKG() {
  const entities = [
    { type: "FEATURE NODE", color: C.amber, example: "AXI4 Read Transaction", relations: ["hasSubFeature", "hasConstraint", "generatesTest", "hasCoverage"] },
    { type: "PARAMETER NODE", color: C.lime, example: "MAX_OUTSTANDING = 256", relations: ["hasLimit", "hasUnit", "constrainsTest", "inCoverpoint"] },
    { type: "MODE NODE", color: C.blue, example: "DDR5_SELF_REFRESH", relations: ["enabledBySignal", "requiresSetup", "hasExitCondition", "generatesScenario"] },
    { type: "INTERFACE NODE", color: C.gold, example: "AXI4-M Port", relations: ["hasProtocol", "hasVIP", "hasAssertion", "hasCDCCrossing"] },
    { type: "EXCEPTION NODE", color: C.red, example: "BUS_ERROR Response", relations: ["triggeredBy", "hasHandling", "hasSafetyAction", "generatesTest"] },
    { type: "DFT NODE", color: "#c084fc", example: "SCAN_EN Pin", relations: ["controlsMode", "requiredSetup", "hasControllability", "hasObservability"] },
    { type: "DEPENDENCY NODE", color: "#38bdf8", example: "Requires REF_CLK stable before RST_N", relations: ["dependsOnBlock", "hasTimingRelation", "isVerifiedBy", "generatesSequence"] },
    { type: "SAFETY NODE", color: C.red, example: "ASIL-D FDC ≥99%", relations: ["mapsFMEA", "hasDiagnosticMechanism", "requiresFITest", "hasLFM"] },
  ];

  const workflows = [
    { step: "01", action: "INGEST", desc: "Parse spec (PDF/DOCX/Markdown/Confluence) → extract all entities via NLP + rule-based extraction", color: C.amber },
    { step: "02", action: "STRUCTURE", desc: "Build KG ontology: nodes = features/params/modes/interfaces. Edges = relations between nodes", color: C.lime },
    { step: "03", action: "VALIDATE", desc: "Engineer reviews KG: confirm extracted params, flag missing/ambiguous nodes, approve before activation", color: C.blue },
    { step: "04", action: "REASON", desc: "KG engine derives: missing test intents, conflicting params, coverage gaps, dependency ordering", color: C.gold },
    { step: "05", action: "GENERATE", desc: "Auto-generate: VPlan, SVA library, UVM coverage groups, RAL model, regression test list", color: "#c084fc" },
    { step: "06", action: "TRACE", desc: "Every test links back to ≥1 KG node. Every KG node links forward to ≥1 test. Bidirectional traceability enforced", color: C.red },
    { step: "07", action: "CLOSE", desc: "As tests pass, KG nodes marked covered. Uncovered nodes = open sign-off items. Gap report auto-generated", color: C.lime },
  ];

  return (
    <div>
      <SectionTitle icon="⊗" title="SPEC KNOWLEDGE GRAPH — THE INTELLIGENCE CORE"
        sub="Every verification decision traces to a KG node. Every KG node traces to a spec. This is the foundation of measurable, auditable digital verification." />

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginBottom: 24 }}>
        {entities.map((e, i) => (
          <div key={i} style={{ background: C.card, border: `1px solid ${e.color}30`, borderLeft: `3px solid ${e.color}`, borderRadius: 6, padding: 12 }}>
            <div style={{ color: e.color, fontSize: 10, letterSpacing: 2, marginBottom: 4 }}>{e.type}</div>
            <div style={{ color: C.text, fontSize: 12, marginBottom: 8, fontStyle: "italic" }}>e.g. "{e.example}"</div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
              {e.relations.map((r, j) => <Pill key={j} color={e.color}>{r}</Pill>)}
            </div>
          </div>
        ))}
      </div>

      <div style={{ marginBottom: 20 }}>
        <div style={{ color: C.amber, fontSize: 11, letterSpacing: 2, marginBottom: 12 }}>▸ KG WORKFLOW — SPEC TO SIGN-OFF</div>
        {workflows.map((w, i) => (
          <div key={i} style={{
            display: "flex", gap: 14, marginBottom: 8, padding: "10px 14px",
            background: C.card, borderRadius: 5, borderLeft: `2px solid ${w.color}`,
          }}>
            <div style={{ color: w.color, fontSize: 13, fontWeight: 700, minWidth: 90 }}>{w.step} {w.action}</div>
            <div style={{ color: C.textDim, fontSize: 12, lineHeight: 1.6 }}>{w.desc}</div>
          </div>
        ))}
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
        <div style={{ background: C.card, border: `1px solid ${C.amber}20`, borderRadius: 6, padding: 14 }}>
          <div style={{ color: C.amber, fontSize: 11, letterSpacing: 2, marginBottom: 10 }}>KG CATCHES THESE ISSUES</div>
          {["Under-specified parameters (no limit defined)",
            "Contradicting limits across spec sections",
            "Modes with no associated test intent",
            "Interface signals with no functional definition",
            "Dependencies not sequenced in VPlan",
            "DFT pins not mapped to any test",
            "Safety requirements without FMEA linkage",
          ].map((item, i) => (
            <div key={i} style={{ fontSize: 11, color: C.textDim, marginBottom: 5, paddingLeft: 8, borderLeft: `2px solid ${C.amber}40` }}>→ {item}</div>
          ))}
        </div>
        <div style={{ background: C.card, border: `1px solid ${C.lime}20`, borderRadius: 6, padding: 14 }}>
          <div style={{ color: C.lime, fontSize: 11, letterSpacing: 2, marginBottom: 10 }}>KG AUTO-GENERATES</div>
          {["Structured VPlan (feature × test matrix)",
            "SVA assertions from protocol/constraint nodes",
            "UVM coverage groups from functional nodes",
            "RAL model from register-map nodes",
            "CDC checker config from clock-domain nodes",
            "UPF power domain map from power nodes",
            "ISO 26262 FMEA-test traceability table",
          ].map((item, i) => (
            <div key={i} style={{ fontSize: 11, color: C.textDim, marginBottom: 5, paddingLeft: 8, borderLeft: `2px solid ${C.lime}40` }}>→ {item}</div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ── TAB 7 — SIGN-OFF GATES ────────────────────────────────────────────────────
function SignOffGates() {
  const [checks, setChecks] = useState(Array(20).fill(false));
  const toggle = i => setChecks(c => c.map((v, j) => j === i ? !v : v));
  const done = checks.filter(Boolean).length;

  const items = [
    ["CODE COVERAGE", "Line ≥95%, Branch ≥95%, Toggle ≥90%, FSM state ≥100%", C.amber],
    ["FUNCTIONAL COVERAGE", "All spec features 100% covered, all cross-coverage bins hit", C.amber],
    ["ASSERTION COVERAGE", "0 unexpected SVA failures, all cover properties hit, vacuity <5%", C.blue],
    ["FPV PROPERTIES", "All formal properties: proven or bounded with justified depth", C.lime],
    ["CDC SIGN-OFF", "All crossing arcs analyzed, synchronized, or waived with formal justification", "#c084fc"],
    ["POWER-AWARE SIM", "All power states covered, 0 X-propagation, UPF consistent with RTL", "#fb923c"],
    ["DFT: SCAN", "Stuck-at ≥98%, transition ≥95%, chain continuity verified, ATPG validated in sim", C.red],
    ["DFT: MBIST", "All memories: MBIST_PASS verified, repair flow tested, March algorithm complete", C.red],
    ["DFT: JTAG", "All TAP states, all instructions verified, IDCODE correct, boundary scan complete", C.red],
    ["PROTOCOL COMPLIANCE", "100% of spec transaction types exercised, all responses checked", C.gold],
    ["RESET COVERAGE", "Cold/warm/domain-specific reset, all reg reset values, mid-txn reset", C.lime],
    ["PERFORMANCE", "Throughput/latency within spec, backpressure, queue depth bins exercised", C.amber],
    ["FAULT/SAFETY", "FDC ≥99% (ASIL-D), mutation kill rate ≥95%, safe state reachability proven", C.red],
    ["INTERFACE CONTRACTS", "0 handshake violations, 0 data corruption, ordering rules enforced", C.blue],
    ["LINT CLEAN", "0 fatal, 0 error violations. Waiver log approved by design lead", C.gold],
    ["REGRESSION FPY", "First-pass yield ≥95% on final regression run", C.lime],
    ["WAIVER LOG", "All waivers: root cause documented, risk classified, manager approved", C.amber],
    ["SPEC TRACEABILITY", "Every KG spec node has ≥1 test. Every test links to ≥1 KG node", C.lime],
    ["DEPENDENCY VERIFIED", "All declared inter-block dependencies resolved and tested", C.blue],
    ["IP RELEASE NOTE", "Verification report generated, delta from last tape-out documented", C.gold],
  ];

  return (
    <div>
      <SectionTitle icon="⊞" title="SIGN-OFF GATES — 20-POINT IP RELEASE CHECKLIST"
        sub="Sign-off is a gate, not a ceremony. All 20 items must be closed or formally waived before IP release. No exceptions." />

      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <div style={{ color: C.text, fontSize: 14 }}>
          Progress: <span style={{ color: done === 20 ? C.lime : done > 10 ? C.amber : C.red, fontWeight: 700 }}>{done}/20</span>
        </div>
        <div style={{ background: C.dim, borderRadius: 4, height: 8, width: 300 }}>
          <div style={{ background: done === 20 ? C.lime : C.amber, width: `${(done / 20) * 100}%`, height: "100%", borderRadius: 4, transition: "width 0.3s" }} />
        </div>
        <Tag label={done === 20 ? "✓ READY TO RELEASE" : "IN PROGRESS"} color={done === 20 ? C.lime : C.amber} />
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr", gap: 5 }}>
        {items.map(([title, desc, color], i) => (
          <div key={i} onClick={() => toggle(i)} style={{
            display: "flex", gap: 12, padding: "10px 14px", cursor: "pointer",
            background: checks[i] ? `${color}10` : C.card,
            border: `1px solid ${checks[i] ? color : C.border}`,
            borderLeft: `3px solid ${checks[i] ? color : C.dim}`,
            borderRadius: 5, alignItems: "flex-start", transition: "all 0.15s",
          }}>
            <div style={{
              minWidth: 18, height: 18, borderRadius: 3, border: `1.5px solid ${color}`,
              background: checks[i] ? color : "transparent",
              display: "flex", alignItems: "center", justifyContent: "center",
              color: "#000", fontSize: 10, fontWeight: 700, marginTop: 1, flexShrink: 0,
            }}>{checks[i] ? "✓" : ""}</div>
            <div>
              <div style={{ color: checks[i] ? color : C.text, fontSize: 12, fontWeight: 700, marginBottom: 2 }}>{title}</div>
              <div style={{ color: C.muted, fontSize: 10, lineHeight: 1.6 }}>{desc}</div>
            </div>
          </div>
        ))}
      </div>

      {done === 20 && (
        <div style={{ marginTop: 20, background: `${C.lime}15`, border: `2px solid ${C.lime}`, borderRadius: 6, padding: 16, textAlign: "center" }}>
          <div style={{ color: C.lime, fontSize: 18, fontWeight: 700, letterSpacing: 3 }}>✓ IP BLOCK CLEARED FOR RELEASE</div>
          <div style={{ color: C.textDim, fontSize: 12, marginTop: 6 }}>All 20 sign-off gates closed. Proceed to chip-level integration with confidence.</div>
        </div>
      )}
    </div>
  );
}

// ── TAB 8 — UNIFIED VEIL ─────────────────────────────────────────────────────
function UnifiedVeil() {
  const layers = [
    {
      layer: "BLOCK",
      label: "FIGHT — IP Block Verification (DigitalVeil + AnalogVeil)",
      color: C.lime, pct: 100,
      digital: ["UVM", "FPV", "CDC", "PA-SIM", "ABV", "Lint", "Mutation", "DFT"],
      analog:  ["DC/AC/Tran", "Stability", "Noise MC", "FloatingNode", "StaticNode", "DFT-A"],
      outcome: "Bugs killed at source. 12-dim digital + 8-dim analog coverage closed. IP sign-off issued.",
    },
    {
      layer: "SUB-SYSTEM",
      label: "BATTLE — Subsystem Integration Verification",
      color: C.amber, pct: 65,
      digital: ["Interface contract tests", "Cross-IP CDC", "Power domain boundaries", "Protocol interop"],
      analog:  ["Mixed-signal co-sim", "Supply interaction", "Load coupling"],
      outcome: "Integration bugs caught early. Verified IPs plug together cleanly. Subsystem sign-off issued.",
    },
    {
      layer: "SoC / CHIP",
      label: "WAR — Top-Level Chip Validation",
      color: C.red, pct: 25,
      digital: ["Chip-level regression", "Boot/OS bring-up", "System performance", "Formal chip-level"],
      analog:  ["Board-level power", "Bench measurements", "Datasheet correlation"],
      outcome: "Tape-out confidence earned from below. Top-level finds integration issues only — not block bugs.",
    },
  ];

  const comparison = [
    ["Verification Start", "Block-level (VPlan day 1)", "Late RTL or post-integration"],
    ["Test Traceability", "Spec KG → 100% traced", "Informal checklists, often untraceable"],
    ["Coverage Dimensions", "12 digital + 8 analog (measurable)", "Typically 2–3, often subjective"],
    ["DFT Integration", "Block-level, first-class", "Late, often an afterthought"],
    ["CDC Analysis", "Block-level, per IP", "Chip-level, expensive to fix"],
    ["Power-Aware Sim", "Block-level from UPF day 1", "Often skipped until tape-out"],
    ["Safety/ISO 26262", "FDC traced to block requirements", "Last-minute, hard to prove"],
    ["Sign-Off", "20-gate quantitative checklist", "Email from lead: 'looks good'"],
    ["Bug Escape Rate", "Target: <2% to chip level", "Industry avg: 15–40% escape rate"],
    ["Re-spin Risk", "Dramatically reduced", "High — block bugs found at silicon"],
  ];

  return (
    <div>
      <SectionTitle icon="⊛" title="UNIFIED VEIL — DIGITAL + ANALOG LAYERED STRATEGY"
        sub="Win fights (block) → win battles (subsystem) → win wars (chip/product). Both DigitalVeil and AnalogVeil feed the same layered quality fortress." />

      {layers.map((l, i) => (
        <div key={i} style={{
          border: `1px solid ${l.color}40`, borderLeft: `4px solid ${l.color}`,
          borderRadius: 6, padding: 18, marginBottom: 14, background: `${l.color}06`,
        }}>
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 10, alignItems: "center" }}>
            <div>
              <Tag label={l.layer} color={l.color} />
              <span style={{ color: C.text, fontSize: 13, marginLeft: 10 }}>{l.label}</span>
            </div>
            <span style={{ color: l.color, fontSize: 16, fontWeight: 700 }}>{l.pct}% BUG KILL</span>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginBottom: 10 }}>
            <div style={{ background: C.card, borderRadius: 4, padding: 10 }}>
              <div style={{ color: C.blue, fontSize: 10, letterSpacing: 1, marginBottom: 6 }}>DIGITAL VERIFICATION</div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>{l.digital.map((d, j) => <Pill key={j} color={C.blue}>{d}</Pill>)}</div>
            </div>
            <div style={{ background: C.card, borderRadius: 4, padding: 10 }}>
              <div style={{ color: "#00d4ff", fontSize: 10, letterSpacing: 1, marginBottom: 6 }}>ANALOG VERIFICATION (AnalogVeil)</div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>{l.analog.map((a, j) => <Pill key={j} color="#00d4ff">{a}</Pill>)}</div>
            </div>
          </div>
          <div style={{ color: C.muted, fontSize: 11, borderLeft: `2px solid ${l.color}40`, paddingLeft: 10 }}>◎ {l.outcome}</div>
        </div>
      ))}

      <div style={{ marginTop: 20, marginBottom: 16 }}>
        <div style={{ color: C.amber, fontSize: 11, letterSpacing: 2, marginBottom: 12 }}>▸ DIGITALVEIL + ANALOGVEIL vs. TRADITIONAL APPROACH</div>
        <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr 1fr", gap: 2 }}>
          {["DIMENSION", "UNIFIED VEIL", "TRADITIONAL"].map(h => (
            <div key={h} style={{ fontSize: 9, color: C.muted, letterSpacing: 1, padding: "4px 8px" }}>{h}</div>
          ))}
          {comparison.map(([dim, veil, trad], i) => [
            <div key={`d${i}`} style={{ padding: "8px 8px", background: C.card, borderRadius: 3, fontSize: 11, color: C.text }}>{dim}</div>,
            <div key={`v${i}`} style={{ padding: "8px 8px", background: C.card, borderRadius: 3, fontSize: 11, color: C.lime }}>{veil}</div>,
            <div key={`t${i}`} style={{ padding: "8px 8px", background: C.card, borderRadius: 3, fontSize: 11, color: C.red }}>{trad}</div>,
          ])}
        </div>
      </div>

      <div style={{ background: `${C.amber}10`, border: `1px solid ${C.amber}40`, borderRadius: 6, padding: 16 }}>
        <div style={{ color: C.amber, fontSize: 12, letterSpacing: 2, marginBottom: 10 }}>◎ THE FOUNDER'S DOCTRINE — IN SYSTEM TERMS</div>
        <div style={{ color: C.text, fontSize: 13, lineHeight: 2 }}>
          <div>◈ <strong style={{ color: C.amber }}>Win Fights</strong> — Every IP block fully verified (DigitalVeil + AnalogVeil). Zero unresolved spec nodes. 20-gate sign-off. DFT complete.</div>
          <div>◈ <strong style={{ color: C.amber }}>Win Battles</strong> — Verified blocks integrate cleanly. Interface contracts honored. Power domains correct. No integration surprises.</div>
          <div>◈ <strong style={{ color: C.amber }}>Win Wars</strong> — Top-level validation finds zero block-origin bugs. First silicon boots. Tape-out confidence is mathematically earned, not hoped for.</div>
          <div style={{ color: C.muted, fontSize: 11, marginTop: 8 }}>
            This is not a philosophy — it is an engineering discipline enforced by tooling. DigitalVeil + AnalogVeil = Unified Veil = the quantitative foundation of high-quality silicon.
          </div>
        </div>
      </div>
    </div>
  );
}

// ── APP SHELL ─────────────────────────────────────────────────────────────────
export default function App() {
  const [activeTab, setActiveTab] = useState(0);

  const components = [
    WarDoctrine, IPTaxonomy, VPlanEngine, Methodology,
    CoverageMatrix, DFTArsenal, SpecKG, SignOffGates, UnifiedVeil,
  ];
  const ActiveComponent = components[activeTab];

  return (
    <div style={{ background: C.bg, minHeight: "100vh", color: C.text, fontFamily: "'Courier New', monospace" }}>
      {/* Header */}
      <div style={{
        background: C.surface, borderBottom: `1px solid ${C.border}`,
        padding: "14px 24px", position: "sticky", top: 0, zIndex: 100,
        display: "flex", alignItems: "center", gap: 16,
      }}>
        <div style={{
          width: 36, height: 36, background: `${C.amber}20`, border: `1.5px solid ${C.amber}`,
          borderRadius: 4, display: "flex", alignItems: "center", justifyContent: "center",
          fontSize: 18, color: C.amber, flexShrink: 0,
        }}>⊛</div>
        <div>
          <div style={{ color: C.amber, fontSize: 17, fontWeight: 700, letterSpacing: 3 }}>DIGITALVEIL</div>
          <div style={{ color: C.muted, fontSize: 9, letterSpacing: 4 }}>DIGITAL IP BLOCK-LEVEL VERIFICATION COMMAND SYSTEM</div>
        </div>
        <div style={{ marginLeft: "auto", display: "flex", gap: 16 }}>
          {[["UNIFIED VEIL", C.lime], ["v2.0", C.amber], ["DIGITAL", C.blue]].map(([l, c]) => (
            <Tag key={l} label={l} color={c} />
          ))}
        </div>
      </div>

      {/* Tab bar */}
      <div style={{
        background: C.surface, borderBottom: `1px solid ${C.border}`,
        padding: "0 24px", display: "flex", overflowX: "auto", gap: 0,
      }}>
        {TABS.map((tab, i) => (
          <button key={i} onClick={() => setActiveTab(i)} style={{
            padding: "11px 14px", background: "transparent", border: "none",
            borderBottom: activeTab === i ? `2px solid ${C.amber}` : "2px solid transparent",
            color: activeTab === i ? C.amber : C.muted,
            cursor: "pointer", fontSize: 10, letterSpacing: 1, whiteSpace: "nowrap",
            fontFamily: "'Courier New', monospace", fontWeight: activeTab === i ? 700 : 400,
            transition: "all 0.15s",
          }}>
            {tab.icon} {tab.label}
          </button>
        ))}
      </div>

      {/* Content */}
      <div style={{ maxWidth: 980, margin: "0 auto", padding: "28px 24px" }}>
        <ActiveComponent />
      </div>

      {/* Footer */}
      <div style={{
        borderTop: `1px solid ${C.border}`, padding: "12px 24px",
        display: "flex", justifyContent: "space-between",
        background: C.surface, marginTop: 40,
      }}>
        <span style={{ color: C.muted, fontSize: 10 }}>DIGITALVEIL — Win Fights. Win Battles. Win Wars.</span>
        <span style={{ color: C.muted, fontSize: 10 }}>Spec KG → VPlan → 12-Dim Coverage → 20-Gate Sign-Off</span>
      </div>
    </div>
  );
}