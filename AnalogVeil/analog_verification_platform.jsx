import { useState } from "react";

const COLORS = {
  bg: "#0a0c10",
  surface: "#111318",
  card: "#161b24",
  border: "#1e2535",
  accent: "#00d4ff",
  accent2: "#7c3aed",
  accent3: "#f59e0b",
  accent4: "#10b981",
  danger: "#ef4444",
  warn: "#f59e0b",
  text: "#e2e8f0",
  muted: "#64748b",
  dim: "#334155",
};

const tabs = [
  "Platform Architecture",
  "Verification Framework",
  "Coverage Matrix",
  "IP Categories",
  "Spec Knowledge Graph",
  "Roadmap",
  "Business Case",
  "Feasibility & Moat",
];

// ─── Platform Architecture ──────────────────────────────────────────────────
function PlatformArchitecture() {
  const layers = [
    {
      label: "USER INTERFACE LAYER",
      color: COLORS.accent,
      items: ["SaaS Web Dashboard", "IP Plan Studio", "Coverage Cockpit", "Sign-off Portal", "DFT Pin Mapper"],
    },
    {
      label: "ORCHESTRATION ENGINE",
      color: COLORS.accent2,
      items: ["Verification Plan Generator", "Spec KG Reasoning Engine", "Dependency Resolver", "Test Sequencer", "Coverage Aggregator"],
    },
    {
      label: "VERIFICATION MODULES",
      color: COLORS.accent4,
      items: ["DC / Operating Point", "AC / Frequency Domain", "Transient / Stability", "Noise & Mismatch", "DFT / Testability", "Floating Node Detector", "Static Node Analyzer", "Corner & Monte Carlo", "System-Level Co-sim"],
    },
    {
      label: "KNOWLEDGE & DATA LAYER",
      color: COLORS.accent3,
      items: ["Spec Knowledge Graph (KG)", "IP Template Library", "Design Rule DB", "Foundry PDK Adaptor", "Historical Coverage DB"],
    },
    {
      label: "INTEGRATION LAYER",
      color: COLORS.muted,
      items: ["Cadence Virtuoso", "Synopsys CustomSim/HSPICE", "Mentor/Siemens AMS", "Git/Perforce VCS", "JIRA / Polarion ALM", "Slack / Webhook Notifiers"],
    },
  ];

  return (
    <div style={{ fontFamily: "'JetBrains Mono', monospace" }}>
      <h2 style={{ color: COLORS.accent, fontSize: 18, marginBottom: 24, letterSpacing: 2 }}>
        ◈ PLATFORM ARCHITECTURE — 5-LAYER STACK
      </h2>
      <p style={{ color: COLORS.muted, fontSize: 13, marginBottom: 28, lineHeight: 1.7 }}>
        A design-agnostic, IP-type-aware verification operating system. Every layer is independently scalable and integrates via open APIs.
      </p>
      {layers.map((layer, i) => (
        <div key={i} style={{
          border: `1px solid ${layer.color}40`,
          borderLeft: `3px solid ${layer.color}`,
          borderRadius: 8,
          padding: "16px 20px",
          marginBottom: 14,
          background: `${layer.color}08`,
        }}>
          <div style={{ color: layer.color, fontSize: 11, letterSpacing: 3, marginBottom: 10, fontWeight: 700 }}>
            {`LAYER ${layers.length - i} — ${layer.label}`}
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
            {layer.items.map((item, j) => (
              <span key={j} style={{
                background: `${layer.color}15`,
                border: `1px solid ${layer.color}30`,
                color: COLORS.text,
                borderRadius: 4,
                padding: "4px 10px",
                fontSize: 12,
              }}>{item}</span>
            ))}
          </div>
        </div>
      ))}

      <div style={{ marginTop: 28, background: COLORS.card, border: `1px solid ${COLORS.border}`, borderRadius: 10, padding: 20 }}>
        <div style={{ color: COLORS.accent3, fontSize: 12, letterSpacing: 2, marginBottom: 14 }}>◈ KEY DESIGN PRINCIPLES</div>
        {[
          ["IP-Type Aware", "Each verification plan is auto-customized based on detected IP category (LDO, ADC, PLL, etc.)"],
          ["Spec-Driven", "All test parameters trace back to specification nodes in the Knowledge Graph"],
          ["Coverage-First", "Every test maps to at least one coverage metric; no orphan tests"],
          ["Dependency-Aware", "Users declare inter-block and system dependencies; engine adjusts sequencing"],
          ["Sign-Off Ready", "Built-in audit trail, waiver management, and formal sign-off workflows"],
        ].map(([title, desc], i) => (
          <div key={i} style={{ display: "flex", gap: 14, marginBottom: 12, alignItems: "flex-start" }}>
            <div style={{ color: COLORS.accent, fontSize: 18, lineHeight: 1 }}>→</div>
            <div>
              <span style={{ color: COLORS.accent3, fontSize: 13, fontWeight: 700 }}>{title}: </span>
              <span style={{ color: COLORS.muted, fontSize: 13 }}>{desc}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── Verification Framework ─────────────────────────────────────────────────
function VerificationFramework() {
  const [activePhase, setActivePhase] = useState(0);
  const phases = [
    {
      name: "PLAN", icon: "◐",
      color: COLORS.accent,
      steps: [
        "Ingest IP spec → KG extraction & structuring",
        "Auto-classify IP category (broad + specialized)",
        "Identify common setup requirements (supply, ground, bias, temperature, PVT corners)",
        "Identify major/IP-specific setup requirements",
        "User-declared design dependencies ingested",
        "Generate Verification Plan (VPlan) document",
        "Map all pins (signal, power, DFT, substrate) to test intents",
        "Assign coverage goals per parameter group",
      ]
    },
    {
      name: "IMPLEMENT", icon: "◑",
      color: COLORS.accent2,
      steps: [
        "Auto-generate testbench templates per IP type",
        "Parameterized stimulus generation (DC sweep, AC, tran, noise)",
        "Corner matrix builder (PVT × mismatch × aging)",
        "Floating node identification & forced-bias injection",
        "Static node leakage / latch-up risk checklist",
        "DFT pin mode switching automation",
        "System co-simulation harness scaffolding",
        "Regression suite builder with priority tiers",
      ]
    },
    {
      name: "EXECUTE", icon: "◕",
      color: COLORS.accent4,
      steps: [
        "Distributed simulation dispatch (cloud or on-prem)",
        "Real-time job monitoring with ETA and failure triage",
        "Automatic retry on infrastructure failures",
        "Intermediate coverage reporting per test completion",
        "Spec KG parameter binding verification",
        "Stability analysis: phase margin, gain margin, PSRR, CMRR",
        "Efficiency measurement across load/line conditions",
        "Monte Carlo convergence tracking",
      ]
    },
    {
      name: "ANALYZE", icon: "●",
      color: COLORS.accent3,
      steps: [
        "Coverage matrix population and gap detection",
        "Parameter vs. spec limit comparison with margin",
        "Statistical summary (μ, σ, Cpk, worst-case)",
        "Failure root-cause classification via AI triage",
        "Floating / static node report",
        "Spec KG traceability matrix auto-generation",
        "Cross-IP system-level consistency check",
        "Regression trend analysis (first-pass yield over time)",
      ]
    },
    {
      name: "SIGN-OFF", icon: "◈",
      color: "#f43f5e",
      steps: [
        "Coverage closure checklist (all metrics ≥ target)",
        "Waiver management with formal approval workflow",
        "Datasheet correlation (measured vs. specified)",
        "PVT boundary confirmation across all corners",
        "DFT controllability / observability sign-off",
        "System-level dependency resolution sign-off",
        "Final verification report auto-generation (PDF/HTML)",
        "Digital sign-off with timestamped audit trail",
      ]
    },
  ];

  return (
    <div style={{ fontFamily: "'JetBrains Mono', monospace" }}>
      <h2 style={{ color: COLORS.accent, fontSize: 18, marginBottom: 8, letterSpacing: 2 }}>◈ VERIFICATION FRAMEWORK — 5-PHASE LIFECYCLE</h2>
      <p style={{ color: COLORS.muted, fontSize: 13, marginBottom: 24 }}>Click a phase to expand its workflow steps.</p>

      <div style={{ display: "flex", gap: 8, marginBottom: 24, flexWrap: "wrap" }}>
        {phases.map((p, i) => (
          <button key={i} onClick={() => setActivePhase(i)} style={{
            padding: "10px 18px", borderRadius: 6, cursor: "pointer", fontFamily: "'JetBrains Mono', monospace",
            fontSize: 12, letterSpacing: 2, fontWeight: 700, transition: "all 0.2s",
            background: activePhase === i ? p.color : "transparent",
            color: activePhase === i ? "#000" : p.color,
            border: `1.5px solid ${p.color}`,
          }}>
            {p.icon} {p.name}
          </button>
        ))}
      </div>

      {(() => {
        const p = phases[activePhase];
        return (
          <div style={{ border: `1px solid ${p.color}50`, borderRadius: 10, padding: 24, background: `${p.color}08` }}>
            <div style={{ color: p.color, fontSize: 14, letterSpacing: 3, marginBottom: 18 }}>
              {p.icon} PHASE: {p.name}
            </div>
            {p.steps.map((step, i) => (
              <div key={i} style={{ display: "flex", gap: 14, marginBottom: 11, alignItems: "flex-start" }}>
                <div style={{
                  minWidth: 24, height: 24, borderRadius: "50%", background: `${p.color}20`,
                  border: `1px solid ${p.color}`, color: p.color, fontSize: 10, display: "flex",
                  alignItems: "center", justifyContent: "center", fontWeight: 700
                }}>{i + 1}</div>
                <div style={{ color: COLORS.text, fontSize: 13, paddingTop: 4, lineHeight: 1.6 }}>{step}</div>
              </div>
            ))}
          </div>
        );
      })()}

      {/* Verification Checks Table */}
      <div style={{ marginTop: 28 }}>
        <div style={{ color: COLORS.accent2, fontSize: 12, letterSpacing: 2, marginBottom: 14 }}>◈ UNIVERSAL VERIFICATION CHECKS</div>
        {[
          ["Internal Functionality", "Transfer function, gain, bandwidth, linearity, offset, CMRR, PSRR"],
          ["Performance Parameters", "THD, SNR, ENOB, settling time, slew rate, output swing, phase noise"],
          ["Stability", "Phase margin ≥45°, gain margin ≥10dB, step load response, oscillation-free"],
          ["Floating Node Analysis", "All high-impedance nodes identified, forced or terminated, leakage checked"],
          ["Static Node Analysis", "DC operating points verified, quiescent current, node voltages vs spec"],
          ["Efficiency / Power", "η vs. load curve, quiescent current, dropout voltage, power-down leakage"],
          ["Corner Compliance", "SS/FF/TT/SF/FS × −40/27/125°C × 0.9V/1.0V/1.1V VDD grid"],
          ["DFT Coverage", "All DFT pins: controllability, observability, BIST self-test, scan coverage"],
          ["System Dependencies", "Interface timing with adjacent blocks, supply sequencing, load interaction"],
          ["Aging / Reliability", "NBTI/PBTI guard-band, EM rule check, ESD compliance, latch-up immunity"],
        ].map(([name, desc], i) => (
          <div key={i} style={{
            display: "flex", gap: 14, padding: "10px 14px", marginBottom: 4,
            background: i % 2 === 0 ? COLORS.card : COLORS.surface,
            borderRadius: 6, borderLeft: `2px solid ${COLORS.accent2}50`
          }}>
            <div style={{ color: COLORS.accent2, fontSize: 13, minWidth: 200, fontWeight: 700 }}>{name}</div>
            <div style={{ color: COLORS.muted, fontSize: 12 }}>{desc}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── Coverage Matrix ─────────────────────────────────────────────────────────
function CoverageMatrix() {
  const groups = [
    {
      name: "DC / Static", color: COLORS.accent,
      metrics: [
        ["Operating Point", "All node voltages vs spec", "✓ Auto", "Node voltage, Current"],
        ["Quiescent Current", "IQ across PVT", "✓ Auto", "μA/mA"],
        ["Leakage (Power-Down)", "Off-state leakage", "✓ Auto", "nA"],
        ["Static Node Check", "No floating high-Z dc nodes", "✓ Auto", "Pass/Fail per node"],
      ]
    },
    {
      name: "AC / Frequency", color: COLORS.accent2,
      metrics: [
        ["Open-Loop Gain", "Gain vs freq", "✓ Auto", "dB"],
        ["Bandwidth", "−3dB, GBW", "✓ Auto", "Hz"],
        ["Phase Margin", "Loop stability", "✓ Auto", "°"],
        ["PSRR", "Supply rejection vs freq", "✓ Auto", "dB"],
        ["CMRR", "Common-mode rejection", "✓ Auto", "dB"],
      ]
    },
    {
      name: "Transient", color: COLORS.accent4,
      metrics: [
        ["Settling Time", "To ε% of final value", "✓ Auto", "ns/μs"],
        ["Slew Rate", "Rising & falling", "✓ Auto", "V/μs"],
        ["Overshoot/Undershoot", "Step response", "✓ Auto", "%"],
        ["Load Transient", "ΔVOUT vs ΔI_load", "✓ Auto", "mV/A"],
      ]
    },
    {
      name: "Noise", color: COLORS.accent3,
      metrics: [
        ["Input-Referred Noise", "Spot noise & integrated", "✓ Auto", "nV/√Hz, μVrms"],
        ["Phase Noise (PLLs)", "dBc/Hz vs offset", "✓ Auto", "dBc/Hz"],
        ["THD", "At rated output", "✓ Auto", "dB/%"],
        ["Mismatch (MC)", "Offset, gain variation", "✓ MC", "mV, %"],
      ]
    },
    {
      name: "DFT / Testability", color: "#f43f5e",
      metrics: [
        ["Pin Controllability", "Each DFT pin driven to 0/1", "✓ Auto", "Pass/Fail"],
        ["Pin Observability", "Output observable at ATE", "✓ Auto", "Pass/Fail"],
        ["BIST Coverage", "Built-in self-test coverage", "Semi-Auto", "%"],
        ["Scan Coverage", "Digital portion coverage", "Semi-Auto", "%"],
      ]
    },
    {
      name: "Reliability", color: COLORS.muted,
      metrics: [
        ["Aging Guard-band", "5yr drift margin", "Semi-Auto", "% margin"],
        ["ESD", "HBM/CDM compliance", "Manual/DRC", "kV"],
        ["Latch-up", "Trigger current immunity", "Manual", "mA"],
        ["EM / IR Drop", "Via foundry rules", "DRC link", "mA/μm"],
      ]
    },
  ];

  return (
    <div style={{ fontFamily: "'JetBrains Mono', monospace" }}>
      <h2 style={{ color: COLORS.accent, fontSize: 18, marginBottom: 8, letterSpacing: 2 }}>◈ MEASURABLE COVERAGE MATRIX</h2>
      <p style={{ color: COLORS.muted, fontSize: 13, marginBottom: 4 }}>
        Every coverage metric has: a measurable quantity, an automation status, and a unit of measure.
        Coverage gates sign-off — 100% required unless formally waived.
      </p>

      <div style={{ display: "flex", gap: 10, marginBottom: 20, flexWrap: "wrap", marginTop: 16 }}>
        {[["✓ Auto", COLORS.accent4, "Fully automated"], ["Semi-Auto", COLORS.accent3, "Guided automation"], ["Manual/DRC", COLORS.muted, "Manual or EDA-linked"]].map(([l, c, d]) => (
          <div key={l} style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12, color: COLORS.text }}>
            <div style={{ width: 10, height: 10, borderRadius: "50%", background: c }} />
            <span style={{ color: c }}>{l}</span> — <span style={{ color: COLORS.muted }}>{d}</span>
          </div>
        ))}
      </div>

      {groups.map((g, gi) => (
        <div key={gi} style={{ marginBottom: 20 }}>
          <div style={{ color: g.color, fontSize: 12, letterSpacing: 2, marginBottom: 8, borderBottom: `1px solid ${g.color}30`, paddingBottom: 6 }}>
            ▸ {g.name.toUpperCase()} METRICS
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1.4fr 100px 120px", gap: 2 }}>
            {["METRIC", "DESCRIPTION", "AUTOMATION", "UNIT"].map(h => (
              <div key={h} style={{ fontSize: 10, color: COLORS.muted, letterSpacing: 1, padding: "4px 8px" }}>{h}</div>
            ))}
            {g.metrics.map(([name, desc, auto, unit], i) => {
              const autoColor = auto === "✓ Auto" ? COLORS.accent4 : auto === "Semi-Auto" ? COLORS.accent3 : COLORS.muted;
              return [
                <div key={`n${i}`} style={{ fontSize: 12, color: COLORS.text, padding: "7px 8px", background: COLORS.card, borderRadius: 4 }}>{name}</div>,
                <div key={`d${i}`} style={{ fontSize: 11, color: COLORS.muted, padding: "7px 8px", background: COLORS.card, borderRadius: 4 }}>{desc}</div>,
                <div key={`a${i}`} style={{ fontSize: 11, color: autoColor, padding: "7px 8px", background: COLORS.card, borderRadius: 4 }}>{auto}</div>,
                <div key={`u${i}`} style={{ fontSize: 11, color: COLORS.accent3, padding: "7px 8px", background: COLORS.card, borderRadius: 4, fontStyle: "italic" }}>{unit}</div>,
              ];
            })}
          </div>
        </div>
      ))}
    </div>
  );
}

// ─── IP Categories ───────────────────────────────────────────────────────────
function IPCategories() {
  const [sel, setSel] = useState(null);

  const broad = [
    {
      name: "POWER MANAGEMENT", color: "#22d3ee", abbr: "PMU",
      ips: ["LDO Regulator", "Buck/Boost DC-DC", "Charge Pump", "Power MUX", "PMU Controller"],
      common: ["Line/load regulation", "Dropout voltage", "Efficiency vs load", "Transient response", "PSRR"],
      major: ["Output capacitor stability range", "Current limit foldback", "Soft-start", "Enable/disable sequencing", "Thermal shutdown"],
      dft: ["Force enable/disable", "Current sense output", "Overcurrent flag observability"],
    },
    {
      name: "DATA CONVERTERS", color: "#a78bfa", abbr: "ADC/DAC",
      ips: ["SAR ADC", "Sigma-Delta ADC", "Pipeline ADC", "Nyquist DAC", "Current Steering DAC"],
      common: ["ENOB, SNDR, SFDR, THD", "DNL/INL", "Full-scale range", "Supply current"],
      major: ["Reference dependency", "Clock jitter sensitivity", "Settling time per code", "Calibration convergence", "Gain/offset trim"],
      dft: ["BIST tone injection", "Ramp linearity test", "Reference force mode", "Trim register access"],
    },
    {
      name: "FREQUENCY SYNTHESIS", color: "#34d399", abbr: "PLL/DLL",
      ips: ["Integer-N PLL", "Fractional-N PLL", "DLL", "Clock Multiplier", "Spread-Spectrum CLK"],
      common: ["Phase noise", "Lock time", "Jitter (RMS/peak-peak)", "VCO tuning range"],
      major: ["Loop filter stability", "Reference spur", "Fractional spur", "Phase detector gain", "Divider ratio range"],
      dft: ["VCO open-loop test", "Divider test mode", "Lock detect observability", "Bypass path"],
    },
    {
      name: "INTERFACE / IO", color: "#fb923c", abbr: "IO",
      ips: ["LVDS Driver/Receiver", "SerDes", "USB PHY", "I2C/SPI PHY", "Comparator"],
      common: ["Common-mode range", "Output swing", "Propagation delay", "Hysteresis (comparators)"],
      major: ["Eye diagram margin", "Pre-emphasis / EQ", "Return loss", "Protocol compliance", "ESD robustness"],
      dft: ["Loop-back mode", "Eye monitor BIST", "Serializer pattern gen", "Receiver margin test"],
    },
    {
      name: "AMPLIFIERS / FILTERS", color: "#f472b6", abbr: "AMP",
      ips: ["Op-Amp", "Instrumentation Amp", "Transimpedance Amp", "Active Filter", "PGA"],
      common: ["Gain accuracy", "Bandwidth", "Offset voltage", "Input bias current"],
      major: ["Noise figure", "Gain-bandwidth product", "Input/output impedance", "Rail-to-rail operation", "Filter corner frequency"],
      dft: ["Gain program test", "Input short/offset measure", "Bandwidth spot test", "Open-loop gain test"],
    },
    {
      name: "REFERENCES", color: "#fbbf24", abbr: "REF",
      ips: ["Bandgap Reference", "Current Reference", "Resistor String DAC", "Trimmed Reference"],
      common: ["Output voltage accuracy", "Temperature coefficient", "Line regulation", "Startup behavior"],
      major: ["PTAT/CTAT balance", "Trim DAC resolution", "Noise spectral density", "Reference curvature"],
      dft: ["Force supply extremes", "Trim register r/w", "Temp coefficient probe point", "Startup force mode"],
    },
  ];

  const specialized = [
    "Crystal Oscillator / XTAL Interface", "MEMS Sensor Interface", "Hall Effect Sensor Front-End",
    "Neural Recording Amplifier", "Optical Detector TIA", "RF LNA / PA", "Wireless TX/RX Front-End",
    "Battery Charger IC", "Motor Driver", "Gate Driver", "Isolated Interface (Galvanic)",
    "High-Voltage Level Shifter (>5V)", "Mixed-Signal Subsystem", "Analog Compute / AI Accelerator",
  ];

  return (
    <div style={{ fontFamily: "'JetBrains Mono', monospace" }}>
      <h2 style={{ color: COLORS.accent, fontSize: 18, marginBottom: 8, letterSpacing: 2 }}>◈ ANALOG IP TAXONOMY</h2>
      <p style={{ color: COLORS.muted, fontSize: 13, marginBottom: 24 }}>
        Each IP category has: common setup reqs (apply to ALL), major/specific reqs, and DFT pin test strategy.
        Click a category to expand.
      </p>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 28 }}>
        {broad.map((cat, i) => (
          <div key={i} onClick={() => setSel(sel === i ? null : i)} style={{
            border: `1px solid ${sel === i ? cat.color : cat.color + "30"}`,
            borderRadius: 8, padding: 16, cursor: "pointer",
            background: sel === i ? `${cat.color}10` : COLORS.card,
            transition: "all 0.2s",
          }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div style={{ color: cat.color, fontSize: 13, fontWeight: 700 }}>{cat.name}</div>
              <div style={{ color: cat.color, fontSize: 11, background: `${cat.color}20`, padding: "2px 8px", borderRadius: 3 }}>{cat.abbr}</div>
            </div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 4, marginTop: 8 }}>
              {cat.ips.map((ip, j) => (
                <span key={j} style={{ fontSize: 10, color: COLORS.muted, background: COLORS.surface, padding: "2px 6px", borderRadius: 3 }}>{ip}</span>
              ))}
            </div>

            {sel === i && (
              <div style={{ marginTop: 14 }}>
                {[["COMMON SETUP", cat.common, COLORS.accent4], ["IP-SPECIFIC / MAJOR", cat.major, cat.color], ["DFT PIN TESTS", cat.dft, "#f43f5e"]].map(([label, items, color]) => (
                  <div key={label} style={{ marginBottom: 10 }}>
                    <div style={{ color, fontSize: 10, letterSpacing: 2, marginBottom: 6 }}>{label}</div>
                    {items.map((item, k) => (
                      <div key={k} style={{ fontSize: 11, color: COLORS.muted, paddingLeft: 10, borderLeft: `2px solid ${color}30`, marginBottom: 3 }}>• {item}</div>
                    ))}
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>

      <div style={{ background: COLORS.card, border: `1px solid ${COLORS.accent3}30`, borderRadius: 8, padding: 16 }}>
        <div style={{ color: COLORS.accent3, fontSize: 12, letterSpacing: 2, marginBottom: 12 }}>◈ SPECIALIZED / DOMAIN-SPECIFIC IPs</div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
          {specialized.map((s, i) => (
            <span key={i} style={{ fontSize: 11, color: COLORS.text, background: COLORS.surface, border: `1px solid ${COLORS.border}`, padding: "5px 10px", borderRadius: 4 }}>{s}</span>
          ))}
        </div>
        <div style={{ color: COLORS.muted, fontSize: 11, marginTop: 12 }}>
          Each specialized IP inherits common setup reqs + auto-loads a domain-specific checklist from the IP Template Library.
        </div>
      </div>
    </div>
  );
}

// ─── Spec Knowledge Graph ────────────────────────────────────────────────────
function SpecKnowledgeGraph() {
  const nodes = [
    { id: "SPEC", label: "IP Specification\n(Datasheet / Doc)", x: 45, y: 10, color: COLORS.accent },
    { id: "KG", label: "Spec KG\n(Ontology)", x: 45, y: 35, color: COLORS.accent2 },
    { id: "PARAM", label: "Parameters\n& Limits", x: 15, y: 60, color: COLORS.accent4 },
    { id: "TEST", label: "Test Cases\n(auto-gen)", x: 45, y: 60, color: COLORS.accent3 },
    { id: "COV", label: "Coverage\nMetrics", x: 75, y: 60, color: "#f43f5e" },
    { id: "TRACE", label: "Traceability\nMatrix", x: 45, y: 85, color: COLORS.muted },
  ];

  const edges = [
    ["SPEC", "KG"], ["KG", "PARAM"], ["KG", "TEST"], ["KG", "COV"],
    ["PARAM", "TEST"], ["TEST", "TRACE"], ["COV", "TRACE"],
  ];

  const entities = [
    ["Spec Entity", "Example", "KG Relation"],
    ["Parameter", "VOUT = 1.8V ±2%", "hasNominal, hasTolerance, hasUnit"],
    ["Condition", "TJ = −40 to 125°C", "validOverRange, hasCorner"],
    ["Limit", "IQ < 50μA", "hasMaxLimit, hasUnit, triggersTest"],
    ["Mode", "LDO_ENABLE = HIGH", "controlledByPin, enablesFunction"],
    ["Dependency", "REF_IN from Bandgap", "requiresBlock, hasTimingRelation"],
    ["DFT Pin", "TEST_EN", "controlsDFTMode, observesOutput"],
  ];

  return (
    <div style={{ fontFamily: "'JetBrains Mono', monospace" }}>
      <h2 style={{ color: COLORS.accent, fontSize: 18, marginBottom: 8, letterSpacing: 2 }}>◈ SPEC KNOWLEDGE GRAPH ENGINE</h2>
      <p style={{ color: COLORS.muted, fontSize: 13, marginBottom: 24, lineHeight: 1.7 }}>
        The Spec KG is the intelligence core. It parses IP specifications (PDF, DOCX, structured DB) into a formal ontology.
        Every verification test traces back to a KG node, providing full spec-to-silicon traceability.
      </p>

      {/* SVG Diagram */}
      <div style={{ background: COLORS.card, borderRadius: 10, padding: 20, marginBottom: 24, position: "relative" }}>
        <div style={{ color: COLORS.accent2, fontSize: 11, letterSpacing: 2, marginBottom: 14 }}>◈ KG DATA FLOW GRAPH</div>
        <svg viewBox="0 0 100 100" style={{ width: "100%", maxWidth: 500, display: "block" }}>
          {edges.map(([from, to], i) => {
            const f = nodes.find(n => n.id === from);
            const t = nodes.find(n => n.id === to);
            return <line key={i} x1={f.x} y1={f.y + 5} x2={t.x} y2={t.y - 3}
              stroke={COLORS.dim} strokeWidth="0.5" strokeDasharray="1.5,1" />;
          })}
          {nodes.map(n => (
            <g key={n.id}>
              <rect x={n.x - 12} y={n.y - 4} width={24} height={11} rx={2}
                fill={`${n.color}20`} stroke={n.color} strokeWidth="0.5" />
              {n.label.split("\n").map((line, li) => (
                <text key={li} x={n.x} y={n.y + 1 + li * 3.5} textAnchor="middle"
                  fontSize="2.5" fill={n.color} fontFamily="monospace">{line}</text>
              ))}
            </g>
          ))}
        </svg>
      </div>

      {/* Entity table */}
      <div style={{ marginBottom: 24 }}>
        <div style={{ color: COLORS.accent2, fontSize: 11, letterSpacing: 2, marginBottom: 10 }}>◈ KG ENTITY TYPES & RELATIONS</div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1.5fr 2fr", gap: 2 }}>
          {entities.map((row, i) => row.map((cell, j) => (
            <div key={`${i}${j}`} style={{
              padding: "8px 10px", fontSize: i === 0 ? 10 : 12, borderRadius: 4,
              background: i === 0 ? COLORS.surface : COLORS.card,
              color: i === 0 ? COLORS.muted : j === 0 ? COLORS.accent2 : j === 1 ? COLORS.accent4 : COLORS.muted,
              letterSpacing: i === 0 ? 1 : 0, fontWeight: i === 0 ? 700 : 400,
            }}>{cell}</div>
          )))}
        </div>
      </div>

      {/* KG capabilities */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
        {[
          ["Spec Ingestion", ["PDF/DOCX NLP parsing", "Table extraction", "Limit auto-detection", "Unit normalization"]],
          ["Reasoning", ["Derive test from spec node", "Identify under-specified params", "Flag conflicting limits", "Propagate dependencies"]],
          ["Traceability", ["Spec-to-test bidirectional links", "Gap analysis (spec node → no test)", "Coverage closure per spec section", "Audit-ready export"]],
          ["Collaboration", ["Multi-engineer annotation", "Spec version diff", "Review workflow", "Change impact analysis"]],
        ].map(([title, items]) => (
          <div key={title} style={{ background: COLORS.card, border: `1px solid ${COLORS.accent2}20`, borderRadius: 8, padding: 14 }}>
            <div style={{ color: COLORS.accent2, fontSize: 11, letterSpacing: 2, marginBottom: 8 }}>{title.toUpperCase()}</div>
            {items.map((item, i) => (
              <div key={i} style={{ fontSize: 12, color: COLORS.muted, marginBottom: 4 }}>→ {item}</div>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── Roadmap ─────────────────────────────────────────────────────────────────
function Roadmap() {
  const phases = [
    {
      phase: "Phase 0", title: "Foundation", duration: "Months 1–4", color: COLORS.accent,
      deliverables: [
        "Core IP taxonomy & KG ontology schema design",
        "Spec ingestion pipeline (PDF/DOCX → KG) — MVP",
        "Verification plan template engine (3 IP types: LDO, ADC, PLL)",
        "Coverage matrix schema & database",
        "Basic web UI: plan creation, pin mapping, coverage dashboard",
        "First enterprise pilot customer signed (1 IP type, 3 IPs)",
      ],
      team: "4 Eng (2 AMS EE, 1 NLP/ML, 1 FE), 1 PM",
      kpi: "1 pilot, KG parses 80% of spec params without manual correction",
    },
    {
      phase: "Phase 1", title: "Core Platform", duration: "Months 5–10", color: COLORS.accent2,
      deliverables: [
        "All 6 broad IP categories + templates",
        "Full coverage matrix engine with gap detection",
        "Testbench scaffolding generator (SPICE / AMS netlists)",
        "Simulator adaptor: Spectre, HSPICE, Eldo",
        "Sign-off workflow: waiver management, audit trail",
        "Floating node & static node automated checkers",
        "DFT pin controllability/observability automated tests",
        "3 paying enterprise customers, SaaS billing live",
      ],
      team: "+2 AMS EE, +1 DevOps/Cloud, +1 Sales/BD",
      kpi: "ARR >$500K, plan-to-sign-off cycle cut 40% vs manual",
    },
    {
      phase: "Phase 2", title: "Intelligence Layer", duration: "Months 11–18", color: COLORS.accent4,
      deliverables: [
        "AI-driven failure triage & root-cause classification",
        "Monte Carlo convergence advisor",
        "System-level co-simulation harness (mixed-signal)",
        "Specialized IP templates: RF, Motor Driver, Sensor Front-End",
        "User-declared design dependency engine (graph-based)",
        "Spec KG: reasoning + conflicting-spec detection",
        "10+ customers, foundry PDK adaptors (TSMC, Samsung, GF)",
        "ISO 26262 / DO-254 compliance mode (automotive/aero)",
      ],
      team: "+3 AMS EE (domain experts), +1 ML Engineer, +2 Sales",
      kpi: "ARR >$3M, NPS >50, 1 automotive customer signed",
    },
    {
      phase: "Phase 3", title: "Platform & Ecosystem", duration: "Months 19–30", color: COLORS.accent3,
      deliverables: [
        "Open API + partner SDK for EDA vendor integration",
        "Cadence / Synopsys plugin (marketplace listing)",
        "IP reuse intelligence: cross-project coverage mining",
        "Collaborative multi-site verification (distributed teams)",
        "Parametric yield prediction (ML on historical coverage data)",
        "Custom enterprise on-prem deployment option",
        "30+ customers, Series A fundraise",
        "Marketplace: community IP templates & checks",
      ],
      team: "25–35 total headcount",
      kpi: "ARR >$10M, platform moat established",
    },
  ];

  return (
    <div style={{ fontFamily: "'JetBrains Mono', monospace" }}>
      <h2 style={{ color: COLORS.accent, fontSize: 18, marginBottom: 8, letterSpacing: 2 }}>◈ PRODUCT ROADMAP — 30 MONTHS</h2>
      <p style={{ color: COLORS.muted, fontSize: 13, marginBottom: 24 }}>From MVP to ecosystem platform. Each phase gate-checked by KPI before funding next phase.</p>
      {phases.map((p, i) => (
        <div key={i} style={{ border: `1px solid ${p.color}40`, borderLeft: `4px solid ${p.color}`, borderRadius: 8, padding: 20, marginBottom: 16, background: `${p.color}06` }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
            <div>
              <span style={{ color: p.color, fontSize: 11, letterSpacing: 3, fontWeight: 700 }}>{p.phase} — </span>
              <span style={{ color: COLORS.text, fontSize: 15, fontWeight: 700 }}>{p.title}</span>
            </div>
            <span style={{ color: COLORS.muted, fontSize: 11, background: COLORS.surface, padding: "4px 10px", borderRadius: 4 }}>{p.duration}</span>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr", gap: 4, marginBottom: 12 }}>
            {p.deliverables.map((d, j) => (
              <div key={j} style={{ fontSize: 12, color: COLORS.text, paddingLeft: 10, borderLeft: `2px solid ${p.color}40`, lineHeight: 1.6 }}>• {d}</div>
            ))}
          </div>
          <div style={{ display: "flex", gap: 20, flexWrap: "wrap" }}>
            <div style={{ fontSize: 11 }}><span style={{ color: p.color }}>TEAM: </span><span style={{ color: COLORS.muted }}>{p.team}</span></div>
            <div style={{ fontSize: 11 }}><span style={{ color: p.color }}>KPI: </span><span style={{ color: COLORS.muted }}>{p.kpi}</span></div>
          </div>
        </div>
      ))}
    </div>
  );
}

// ─── Business Case ────────────────────────────────────────────────────────────
function BusinessCase() {
  const metrics = [
    { label: "Global Analog IP Market", val: "$8.4B", note: "2025, growing 9% CAGR" },
    { label: "Verification TAM", val: "$2.1B", note: "~25% of analog design spend" },
    { label: "Target SAM (tools/SaaS)", val: "$600M", note: "Mid-large IC design teams" },
    { label: "Yr1 Revenue Target", val: "$500K", note: "3–5 enterprise pilots" },
    { label: "Yr3 Revenue Target", val: "$10M ARR", note: "30+ customers" },
    { label: "Yr5 Revenue Target", val: "$50M ARR", note: "Platform + marketplace" },
  ];

  const segments = [
    ["Primary", "Fabless IC design companies", "$150K–$500K/yr per customer", "High"],
    ["Secondary", "IDMs (Intel, TI, NXP, Renesas)", "$300K–$1M/yr enterprise deal", "Medium (long sales cycle)"],
    ["Tertiary", "IP vendor companies (Arm, Synopsys IP)", "$100K–$300K/yr", "High — validates every IP release"],
    ["Vertical", "Automotive tier-1 (ISO 26262 demand)", "Premium pricing +50%", "High after compliance module"],
    ["SMB", "ASIC design services, startups", "$20K–$80K/yr SaaS tier", "Volume play, Phase 3"],
  ];

  const costs = [
    ["Seed (Pre-Phase 1)", "$2M", "Team of 8, 12 months runway, cloud infra, pilot"],
    ["Series A (Phase 2)", "$8–12M", "Scale to 25 people, sales, foundry integrations"],
    ["Series B (Phase 3)", "$25–35M", "Platform, global expansion, 35+ headcount"],
  ];

  return (
    <div style={{ fontFamily: "'JetBrains Mono', monospace" }}>
      <h2 style={{ color: COLORS.accent, fontSize: 18, marginBottom: 8, letterSpacing: 2 }}>◈ BUSINESS CASE & FINANCIAL MODEL</h2>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 10, marginBottom: 24 }}>
        {metrics.map((m, i) => (
          <div key={i} style={{ background: COLORS.card, border: `1px solid ${COLORS.border}`, borderRadius: 8, padding: 14 }}>
            <div style={{ color: COLORS.muted, fontSize: 10, letterSpacing: 1, marginBottom: 4 }}>{m.label.toUpperCase()}</div>
            <div style={{ color: COLORS.accent, fontSize: 20, fontWeight: 700, marginBottom: 4 }}>{m.val}</div>
            <div style={{ color: COLORS.dim, fontSize: 11 }}>{m.note}</div>
          </div>
        ))}
      </div>

      <div style={{ marginBottom: 24 }}>
        <div style={{ color: COLORS.accent2, fontSize: 12, letterSpacing: 2, marginBottom: 12 }}>◈ PRICING STRATEGY</div>
        <div style={{ background: COLORS.card, border: `1px solid ${COLORS.accent2}20`, borderRadius: 8, padding: 16 }}>
          {[
            ["Starter", "$15K/yr", "Up to 5 IPs, 3 IP types, standard templates"],
            ["Professional", "$60K/yr", "Up to 30 IPs, all IP types, KG + sign-off module"],
            ["Enterprise", "$150K–500K/yr", "Unlimited IPs, on-prem option, custom integrations, SLA"],
            ["Platform Fee", "$250K/yr", "IDMs/large fabless — full team, foundry adaptors, ISO mode"],
          ].map(([tier, price, desc], i) => (
            <div key={i} style={{ display: "flex", gap: 16, padding: "10px 0", borderBottom: `1px solid ${COLORS.border}`, alignItems: "center" }}>
              <div style={{ color: COLORS.accent2, fontSize: 13, minWidth: 120, fontWeight: 700 }}>{tier}</div>
              <div style={{ color: COLORS.accent, fontSize: 14, minWidth: 120, fontWeight: 700 }}>{price}</div>
              <div style={{ color: COLORS.muted, fontSize: 12 }}>{desc}</div>
            </div>
          ))}
        </div>
      </div>

      <div style={{ marginBottom: 24 }}>
        <div style={{ color: COLORS.accent3, fontSize: 12, letterSpacing: 2, marginBottom: 12 }}>◈ CUSTOMER SEGMENTS & GTM</div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr 80px", gap: 2 }}>
          {["SEGMENT", "TARGET", "ACV", "PRIORITY"].map(h => (
            <div key={h} style={{ fontSize: 10, color: COLORS.muted, letterSpacing: 1, padding: "4px 8px" }}>{h}</div>
          ))}
          {segments.map((row, i) => row.map((cell, j) => (
            <div key={`${i}${j}`} style={{
              padding: "9px 10px", fontSize: 11, borderRadius: 4,
              background: COLORS.card, color: j === 0 ? COLORS.accent3 : j === 3 ? COLORS.accent4 : COLORS.muted,
            }}>{cell}</div>
          )))}
        </div>
      </div>

      <div>
        <div style={{ color: "#f43f5e", fontSize: 12, letterSpacing: 2, marginBottom: 12 }}>◈ FUNDING REQUIREMENTS</div>
        {costs.map(([round, amt, use], i) => (
          <div key={i} style={{ display: "flex", gap: 14, marginBottom: 8, padding: 12, background: COLORS.card, borderRadius: 6, borderLeft: `3px solid #f43f5e50` }}>
            <div style={{ color: "#f43f5e", minWidth: 150, fontSize: 13, fontWeight: 700 }}>{round}</div>
            <div style={{ color: COLORS.accent, minWidth: 80, fontSize: 14, fontWeight: 700 }}>{amt}</div>
            <div style={{ color: COLORS.muted, fontSize: 12 }}>{use}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── Feasibility & Moat ───────────────────────────────────────────────────────
function FeasibilityMoat() {
  const strengths = [
    ["Acute Pain, No Good Solution", "Analog verification is predominantly manual, checklist-driven, expert-dependent. No SaaS tool addresses the full lifecycle with coverage metrics. This is a genuine white space.", "HIGH"],
    ["Spec KG is a Compounding Moat", "The KG accumulates structured knowledge per IP type over time. The more IPs ingested, the smarter the system. Competitors must replicate years of structured analog domain knowledge.", "VERY HIGH"],
    ["Coverage-First Discipline", "Measurable coverage closes a cultural gap in analog — most teams can't answer 'what percentage of your spec is tested?' This resonates immediately with managers and sign-off owners.", "HIGH"],
    ["Regulatory Tailwinds", "ISO 26262 (automotive), DO-254 (aerospace), IEC 62443 (industrial) all demand formal verification traceability. The market is being pushed toward exactly what this platform provides.", "HIGH"],
    ["Switching Cost", "Once a team's spec library, waiver history, coverage baselines, and IP templates are in the platform, switching is prohibitively expensive. CAC recovered quickly, LTV is long.", "VERY HIGH"],
  ];

  const risks = [
    ["Sales Cycle", "Enterprise EDA/IC tool sales are 6–18 months. Mitigation: pilot programs, land-and-expand, target VP Engineering/Design Verification leads directly.", "MED"],
    ["EDA Incumbent Response", "Cadence/Synopsys could build this. Reality: their incentive is simulator hours, not reducing verification effort. They also move slowly. Mitigation: integrate with them, don't fight.", "MED"],
    ["Talent Scarcity", "Need rare combination: AMS circuit expertise + software engineering. Mitigation: hire PhDs from top analog groups, build structured onboarding.", "MED-HIGH"],
    ["IP Confidentiality", "Customers won't share schematics on public cloud. Mitigation: on-prem option in Phase 2, local KG processing, no schematic ingestion required for plan layer.", "MED"],
    ["AI Hallucination in KG", "Wrong spec extraction → wrong tests → false sign-off. Mitigation: human-in-loop validation, confidence scores, engineer sign-off on KG nodes before activation.", "HIGH — must solve"],
  ];

  const moatScores = [
    ["Domain Knowledge Depth", 95], ["Switching Costs", 88], ["Data Network Effects", 82],
    ["Regulatory Alignment", 78], ["Integration Ecosystem", 65], ["Brand / Reputation", 40],
  ];

  return (
    <div style={{ fontFamily: "'JetBrains Mono', monospace" }}>
      <h2 style={{ color: COLORS.accent, fontSize: 18, marginBottom: 8, letterSpacing: 2 }}>◈ EXPERT FEASIBILITY ASSESSMENT & MOAT ANALYSIS</h2>
      <div style={{ background: `${COLORS.accent4}10`, border: `1px solid ${COLORS.accent4}40`, borderRadius: 8, padding: 16, marginBottom: 24 }}>
        <div style={{ color: COLORS.accent4, fontSize: 12, letterSpacing: 2, marginBottom: 8 }}>EXPERT VERDICT</div>
        <div style={{ color: COLORS.text, fontSize: 13, lineHeight: 1.8 }}>
          This is a <strong style={{ color: COLORS.accent4 }}>high-feasibility, defensible opportunity</strong> with a genuine moat if executed with deep domain expertise.
          The analog verification market has been systematically underserved by EDA vendors who optimized for simulator revenue,
          not verification productivity. A spec-KG-anchored, coverage-first SaaS platform solves a real, expensive, recurring pain
          for every analog IP team globally. The risk is execution: you need credibility-first (hire PhDs, get a Tier-1 reference customer)
          before the sales motion scales.
        </div>
      </div>

      <div style={{ marginBottom: 24 }}>
        <div style={{ color: COLORS.accent4, fontSize: 12, letterSpacing: 2, marginBottom: 12 }}>◈ MOAT STRENGTH SCORES</div>
        {moatScores.map(([name, score], i) => (
          <div key={i} style={{ marginBottom: 8 }}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 3 }}>
              <span style={{ color: COLORS.text, fontSize: 12 }}>{name}</span>
              <span style={{ color: score > 80 ? COLORS.accent4 : score > 60 ? COLORS.accent3 : COLORS.muted, fontSize: 12, fontWeight: 700 }}>{score}/100</span>
            </div>
            <div style={{ background: COLORS.surface, borderRadius: 4, height: 6 }}>
              <div style={{ background: score > 80 ? COLORS.accent4 : score > 60 ? COLORS.accent3 : COLORS.muted, width: `${score}%`, height: "100%", borderRadius: 4, transition: "width 1s" }} />
            </div>
          </div>
        ))}
      </div>

      <div style={{ marginBottom: 24 }}>
        <div style={{ color: COLORS.accent4, fontSize: 12, letterSpacing: 2, marginBottom: 12 }}>◈ COMPETITIVE STRENGTHS</div>
        {strengths.map(([title, desc, rating], i) => (
          <div key={i} style={{ background: COLORS.card, borderRadius: 8, padding: 14, marginBottom: 8, borderLeft: `3px solid ${COLORS.accent4}` }}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
              <span style={{ color: COLORS.accent4, fontSize: 13, fontWeight: 700 }}>{title}</span>
              <span style={{ fontSize: 10, color: rating.includes("VERY") ? COLORS.accent : COLORS.accent4, background: `${COLORS.accent4}20`, padding: "2px 8px", borderRadius: 3 }}>{rating}</span>
            </div>
            <div style={{ color: COLORS.muted, fontSize: 12, lineHeight: 1.6 }}>{desc}</div>
          </div>
        ))}
      </div>

      <div>
        <div style={{ color: COLORS.danger, fontSize: 12, letterSpacing: 2, marginBottom: 12 }}>◈ RISKS & MITIGATIONS</div>
        {risks.map(([title, desc, severity], i) => (
          <div key={i} style={{ background: COLORS.card, borderRadius: 8, padding: 14, marginBottom: 8, borderLeft: `3px solid ${COLORS.danger}60` }}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
              <span style={{ color: "#f87171", fontSize: 13, fontWeight: 700 }}>{title}</span>
              <span style={{ fontSize: 10, color: severity.includes("HIGH") ? COLORS.danger : COLORS.accent3, background: `${COLORS.danger}15`, padding: "2px 8px", borderRadius: 3 }}>{severity}</span>
            </div>
            <div style={{ color: COLORS.muted, fontSize: 12, lineHeight: 1.6 }}>{desc}</div>
          </div>
        ))}
      </div>

      <div style={{ marginTop: 24, background: `${COLORS.accent2}10`, border: `1px solid ${COLORS.accent2}30`, borderRadius: 8, padding: 16 }}>
        <div style={{ color: COLORS.accent2, fontSize: 12, letterSpacing: 2, marginBottom: 10 }}>◈ FIRST 90 DAYS — CRITICAL PATH</div>
        {["Hire 2 AMS circuit PhDs with mixed-signal IC experience (credibility foundation)",
          "Define KG ontology schema for 2 IP types (LDO + PLL) with a design partner",
          "Build spec ingestion parser for structured PDFs → validate with real datasheets",
          "Sign 1 paid pilot ($25–50K) with a fabless company or IP house",
          "File provisional patent on KG-driven analog verification coverage methodology",
          "Begin seed fundraise with pilot data as proof"].map((step, i) => (
          <div key={i} style={{ display: "flex", gap: 12, marginBottom: 8 }}>
            <div style={{ color: COLORS.accent2, minWidth: 20, fontSize: 13 }}>{i + 1}.</div>
            <div style={{ color: COLORS.muted, fontSize: 12, lineHeight: 1.6 }}>{step}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── App Shell ───────────────────────────────────────────────────────────────
export default function App() {
  const [activeTab, setActiveTab] = useState(0);

  const components = [
    PlatformArchitecture,
    VerificationFramework,
    CoverageMatrix,
    IPCategories,
    SpecKnowledgeGraph,
    Roadmap,
    BusinessCase,
    FeasibilityMoat,
  ];

  const ActiveComponent = components[activeTab];

  return (
    <div style={{
      background: COLORS.bg, minHeight: "100vh", color: COLORS.text,
      fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
    }}>
      {/* Header */}
      <div style={{
        background: COLORS.surface, borderBottom: `1px solid ${COLORS.border}`,
        padding: "18px 28px", position: "sticky", top: 0, zIndex: 100,
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 14, marginBottom: 4 }}>
          <div style={{
            width: 32, height: 32, borderRadius: 6, background: `linear-gradient(135deg, ${COLORS.accent}, ${COLORS.accent2})`,
            display: "flex", alignItems: "center", justifyContent: "center", fontSize: 16, flexShrink: 0
          }}>◈</div>
          <div>
            <div style={{ color: COLORS.text, fontSize: 16, fontWeight: 700, letterSpacing: 1 }}>ANALOGVEIL</div>
            <div style={{ color: COLORS.muted, fontSize: 10, letterSpacing: 3 }}>ANALOG IP VERIFICATION PLATFORM — SAAS</div>
          </div>
        </div>
      </div>

      {/* Tab Bar */}
      <div style={{
        background: COLORS.surface, borderBottom: `1px solid ${COLORS.border}`,
        padding: "0 28px", display: "flex", gap: 0, overflowX: "auto",
      }}>
        {tabs.map((tab, i) => (
          <button key={i} onClick={() => setActiveTab(i)} style={{
            padding: "12px 16px", background: "transparent", border: "none",
            borderBottom: activeTab === i ? `2px solid ${COLORS.accent}` : "2px solid transparent",
            color: activeTab === i ? COLORS.accent : COLORS.muted,
            cursor: "pointer", fontSize: 11, letterSpacing: 1, whiteSpace: "nowrap",
            fontFamily: "'JetBrains Mono', monospace", fontWeight: activeTab === i ? 700 : 400,
            transition: "all 0.15s",
          }}>{tab.toUpperCase()}</button>
        ))}
      </div>

      {/* Content */}
      <div style={{ maxWidth: 960, margin: "0 auto", padding: "32px 28px" }}>
        <ActiveComponent />
      </div>

      {/* Footer */}
      <div style={{
        borderTop: `1px solid ${COLORS.border}`, padding: "16px 28px",
        display: "flex", justifyContent: "space-between", alignItems: "center",
        background: COLORS.surface, marginTop: 40,
      }}>
        <span style={{ color: COLORS.dim, fontSize: 11 }}>ANALOGVEIL v0.1 — Design-Agnostic Analog Verification OS</span>
        <span style={{ color: COLORS.dim, fontSize: 11 }}>Spec → KG → Tests → Coverage → Sign-Off</span>
      </div>
    </div>
  );
}
