import { useState, useEffect, useRef } from "react";

// ── Color system ──────────────────────────────────────────────
const C = {
  bg: "#06080f",
  surface: "#0d1117",
  panel: "#111827",
  border: "#1e2d40",
  accent: "#00d4ff",
  accentDim: "#0891b2",
  gold: "#f59e0b",
  green: "#10b981",
  violet: "#8b5cf6",
  red: "#ef4444",
  text: "#e2e8f0",
  muted: "#64748b",
  dim: "#334155",
};

// ── Architecture phases ────────────────────────────────────────
const PHASES = [
  {
    id: "spec",
    label: "Application Spec Ingestion",
    icon: "◈",
    color: C.accent,
    aiRole: "NLP + Classifier",
    steps: [
      "Parse natural-language or structured spec input",
      "Classify application domain (IoT, HPC, RF, ML, Automotive, Medical…)",
      "Extract functional requirements, power envelope, frequency targets",
      "Identify safety/reliability standards (ISO 26262, IEC 61508, DO-254)",
      "Auto-generate a formalized Spec Document with traceability IDs",
    ],
    outputs: ["Formalized Spec (JSON/YAML)", "Domain Classification Report", "Traceability Matrix v0"],
  },
  {
    id: "explore",
    label: "Architecture Exploration & Benchmarking",
    icon: "⬡",
    color: C.gold,
    aiRole: "Generative Search + Ranking",
    steps: [
      "Query internal IP library and prior architecture database",
      "Generate candidate top-level architectures (bus topology, memory hierarchy, power domains)",
      "Benchmark candidates against spec KPIs using analytical models",
      "Apply PPA (Power-Performance-Area) trade-off scoring",
      "Flag reuse opportunities vs. new development cost",
    ],
    outputs: ["Candidate Architecture Matrix", "PPA Score Cards", "Reuse vs. New Analysis"],
  },
  {
    id: "partition",
    label: "System Partitioning & Domain Assignment",
    icon: "⬢",
    color: C.violet,
    aiRole: "Graph Partitioning + Constraint Solver",
    steps: [
      "Partition system into Digital / Analog / Mixed-Signal / RF domains",
      "Assign clock domains, voltage domains, isolation strategies",
      "Define inter-domain interfaces (clock crossings, level shifters, ESD)",
      "Establish power management architecture (DVFS, power gating trees)",
      "Validate partitioning against floorplan feasibility heuristics",
    ],
    outputs: ["Domain Partition Map", "Clock/Power Domain Spec", "Interface Protocol List"],
  },
  {
    id: "ip",
    label: "IP Selection & Dependency Mapping",
    icon: "◉",
    color: C.green,
    aiRole: "Recommendation Engine + Conflict Detection",
    steps: [
      "Select IPs per domain from validated library (hard / soft / configurable)",
      "Define per-IP: function, input/output ports, performance bounds, QoS requirements",
      "Map all IP-to-IP dependencies: data flow, control flow, power, timing",
      "Detect interface mismatches, protocol conflicts, latency budget violations",
      "Generate IP Integration Checklist with pass/fail criteria",
    ],
    outputs: ["IP Selection Register", "Dependency Graph", "Integration Checklist"],
  },
  {
    id: "intent",
    label: "Architecture Intent Propagation",
    icon: "⟁",
    color: "#f97316",
    aiRole: "LLM Documentation Generator",
    steps: [
      "Distill top-level architecture philosophy into a single Intent Statement",
      "Auto-generate per-IP Architecture Intent Documents (AIDs)",
      "Embed traceability: each IP spec traces to top-level requirement IDs",
      "Propagate interdependency context to each IP team (what they depend on, what depends on them)",
      "Lock intent baseline — any change triggers impact analysis across all IPs",
    ],
    outputs: ["Architecture Intent Statement", "Per-IP AID Pack", "Change Impact Matrix"],
  },
  {
    id: "verify",
    label: "Spec Closure & Architecture Sign-Off",
    icon: "◎",
    color: C.red,
    aiRole: "Formal Checker + Coverage Analyzer",
    steps: [
      "Run automated spec completeness check (no undefined interfaces, clocks, resets)",
      "Verify PPA targets are achievable with selected IP set",
      "Check for architectural anti-patterns (dead logic, unresolved X-states, unclocked flops)",
      "Generate Architecture Review Package (ARP) for sign-off",
      "Freeze Architecture Baseline — feeds into RTL/schematic kickoff",
    ],
    outputs: ["Spec Closure Report", "Architecture Review Package", "Frozen Architecture Baseline"],
  },
];

// ── IP Domain Cards ────────────────────────────────────────────
const IP_DOMAINS = [
  {
    domain: "Digital",
    icon: "▣",
    color: C.accent,
    ips: ["CPU/DSP Core", "DMA Engine", "Crypto Accelerator", "Interconnect Fabric", "Memory Controller"],
    intentFields: ["Latency budget", "Clock frequency", "Reset strategy", "Pipeline depth", "DFT hooks"],
  },
  {
    domain: "Analog",
    icon: "◌",
    color: C.gold,
    ips: ["PLL/FRAC-N", "LDO Regulator", "Bandgap Reference", "ADC/DAC", "Temp Sensor"],
    intentFields: ["Supply voltage", "Noise budget", "Trim strategy", "Process corner coverage", "PSRR target"],
  },
  {
    domain: "Mixed-Signal",
    icon: "◑",
    color: C.violet,
    ips: ["SerDes PHY", "MIPI D-PHY", "USB PHY", "PMIC Interface", "Sensor AFE"],
    intentFields: ["Jitter budget", "Eye diagram target", "ESD level", "Power sequence", "Calibration flow"],
  },
  {
    domain: "RF/Wireless",
    icon: "⌾",
    color: C.green,
    ips: ["RF Transceiver", "PA/LNA", "VCO", "Balun/Filter", "Antenna Switch"],
    intentFields: ["Noise figure", "Output power", "Linearity (IIP3)", "Frequency plan", "Matching network"],
  },
];

// ── Styles ─────────────────────────────────────────────────────
const gStyles = `
  @import url('https://fonts.googleapis.com/css2?family=Space+Mono:ital,wght@0,400;0,700;1,400&family=Syne:wght@400;600;700;800&display=swap');

  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  body {
    background: ${C.bg};
    color: ${C.text};
    font-family: 'Syne', sans-serif;
    min-height: 100vh;
  }

  ::-webkit-scrollbar { width: 6px; }
  ::-webkit-scrollbar-track { background: ${C.surface}; }
  ::-webkit-scrollbar-thumb { background: ${C.dim}; border-radius: 3px; }

  .mono { font-family: 'Space Mono', monospace; }

  @keyframes pulse-ring {
    0% { box-shadow: 0 0 0 0 rgba(0,212,255,0.4); }
    70% { box-shadow: 0 0 0 12px rgba(0,212,255,0); }
    100% { box-shadow: 0 0 0 0 rgba(0,212,255,0); }
  }

  @keyframes scan {
    0% { transform: translateY(-100%); opacity: 0; }
    10% { opacity: 1; }
    90% { opacity: 1; }
    100% { transform: translateY(100vh); opacity: 0; }
  }

  @keyframes blink {
    0%,100% { opacity: 1; } 50% { opacity: 0; }
  }

  @keyframes fadeSlideIn {
    from { opacity: 0; transform: translateY(16px); }
    to { opacity: 1; transform: translateY(0); }
  }

  @keyframes shimmer {
    0% { background-position: -200% center; }
    100% { background-position: 200% center; }
  }

  .fade-in { animation: fadeSlideIn 0.4s ease forwards; }

  .tag {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 3px;
    font-size: 10px;
    font-family: 'Space Mono', monospace;
    letter-spacing: 0.05em;
    text-transform: uppercase;
  }

  .progress-bar-inner {
    height: 100%;
    border-radius: 4px;
    background: linear-gradient(90deg, ${C.accent}, ${C.violet});
    transition: width 0.8s ease;
  }

  .grid-bg {
    background-image:
      linear-gradient(rgba(0,212,255,0.03) 1px, transparent 1px),
      linear-gradient(90deg, rgba(0,212,255,0.03) 1px, transparent 1px);
    background-size: 32px 32px;
  }

  .shimmer-text {
    background: linear-gradient(90deg, ${C.accent}, ${C.violet}, ${C.gold}, ${C.accent});
    background-size: 200% auto;
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    animation: shimmer 4s linear infinite;
  }
`;

// ── Sub-components ─────────────────────────────────────────────

function AIBadge({ label }) {
  return (
    <span className="tag" style={{ background: "rgba(139,92,246,0.15)", color: C.violet, border: `1px solid ${C.violet}33` }}>
      ✦ AI: {label}
    </span>
  );
}

function StatusDot({ active }) {
  return (
    <span style={{
      display: "inline-block",
      width: 8, height: 8,
      borderRadius: "50%",
      background: active ? C.green : C.dim,
      animation: active ? "pulse-ring 2s infinite" : "none",
      flexShrink: 0,
    }} />
  );
}

function PhaseCard({ phase, index, isActive, onClick, isCompleted }) {
  return (
    <div
      onClick={onClick}
      style={{
        border: `1px solid ${isActive ? phase.color : C.border}`,
        borderRadius: 8,
        padding: "14px 16px",
        cursor: "pointer",
        background: isActive ? `${phase.color}10` : C.surface,
        transition: "all 0.25s",
        position: "relative",
        overflow: "hidden",
      }}
    >
      {isActive && (
        <div style={{
          position: "absolute", top: 0, left: 0, right: 0, height: 2,
          background: `linear-gradient(90deg, ${phase.color}, transparent)`,
        }} />
      )}
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <span style={{ color: phase.color, fontSize: 18 }}>{phase.icon}</span>
        <div style={{ flex: 1 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span className="mono" style={{ fontSize: 10, color: C.muted }}>P{String(index + 1).padStart(2, "0")}</span>
            {isCompleted && <span className="tag" style={{ background: `${C.green}20`, color: C.green, fontSize: 9 }}>✓ DONE</span>}
          </div>
          <div style={{ fontSize: 13, fontWeight: 600, color: isActive ? phase.color : C.text, lineHeight: 1.3, marginTop: 2 }}>
            {phase.label}
          </div>
        </div>
      </div>
    </div>
  );
}

function OutputPill({ label, color }) {
  return (
    <span className="tag mono" style={{
      background: `${color}15`,
      color: color,
      border: `1px solid ${color}40`,
      fontSize: 10,
      padding: "3px 10px",
    }}>
      ↗ {label}
    </span>
  );
}

function PhaseDetail({ phase, onComplete, isCompleted }) {
  const [stepsDone, setStepsDone] = useState(isCompleted ? phase.steps.length : 0);
  const [running, setRunning] = useState(false);

  const runAutomation = () => {
    if (running || isCompleted) return;
    setRunning(true);
    setStepsDone(0);
    phase.steps.forEach((_, i) => {
      setTimeout(() => {
        setStepsDone(i + 1);
        if (i === phase.steps.length - 1) {
          setRunning(false);
          onComplete();
        }
      }, (i + 1) * 700);
    });
  };

  const pct = Math.round((stepsDone / phase.steps.length) * 100);

  return (
    <div className="fade-in" style={{ height: "100%", display: "flex", flexDirection: "column", gap: 20 }}>
      {/* Header */}
      <div style={{
        background: C.panel,
        border: `1px solid ${phase.color}40`,
        borderRadius: 10,
        padding: 20,
      }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: 12 }}>
          <div>
            <div style={{ display: "flex", align: "center", gap: 10, flexWrap: "wrap" }}>
              <span style={{ fontSize: 32, color: phase.color }}>{phase.icon}</span>
              <div>
                <div className="mono" style={{ fontSize: 10, color: C.muted, marginBottom: 4 }}>ARCHITECTURE PHASE</div>
                <h2 style={{ fontSize: 20, fontWeight: 800, color: phase.color }}>{phase.label}</h2>
              </div>
            </div>
            <div style={{ marginTop: 12 }}>
              <AIBadge label={phase.aiRole} />
            </div>
          </div>
          <button
            onClick={runAutomation}
            disabled={running || isCompleted}
            style={{
              padding: "10px 24px",
              borderRadius: 6,
              border: "none",
              background: isCompleted ? `${C.green}20` : running ? `${phase.color}30` : phase.color,
              color: isCompleted ? C.green : running ? phase.color : C.bg,
              fontFamily: "'Space Mono', monospace",
              fontSize: 12,
              fontWeight: 700,
              cursor: isCompleted || running ? "not-allowed" : "pointer",
              letterSpacing: "0.05em",
              transition: "all 0.2s",
            }}
          >
            {isCompleted ? "✓ COMPLETE" : running ? "▶ RUNNING…" : "▶ RUN PHASE"}
          </button>
        </div>

        {/* Progress */}
        <div style={{ marginTop: 16 }}>
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
            <span className="mono" style={{ fontSize: 11, color: C.muted }}>PHASE PROGRESS</span>
            <span className="mono" style={{ fontSize: 11, color: phase.color }}>{pct}%</span>
          </div>
          <div style={{ height: 6, background: C.dim, borderRadius: 4, overflow: "hidden" }}>
            <div className="progress-bar-inner" style={{
              width: `${pct}%`,
              background: `linear-gradient(90deg, ${phase.color}, ${phase.color}90)`,
            }} />
          </div>
        </div>
      </div>

      {/* Steps */}
      <div style={{
        background: C.panel,
        border: `1px solid ${C.border}`,
        borderRadius: 10,
        padding: 20,
        flex: 1,
        overflowY: "auto",
      }}>
        <div className="mono" style={{ fontSize: 10, color: C.muted, marginBottom: 14, letterSpacing: "0.1em" }}>
          AUTOMATION STEPS
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {phase.steps.map((step, i) => {
            const done = i < stepsDone;
            const active = i === stepsDone && running;
            return (
              <div key={i} style={{
                display: "flex",
                gap: 12,
                alignItems: "flex-start",
                padding: "10px 14px",
                borderRadius: 6,
                background: done ? `${phase.color}0a` : active ? `${phase.color}15` : "transparent",
                border: `1px solid ${done ? phase.color + "40" : active ? phase.color + "60" : C.border}`,
                transition: "all 0.3s",
              }}>
                <div style={{
                  width: 22, height: 22,
                  borderRadius: "50%",
                  border: `2px solid ${done ? phase.color : active ? phase.color : C.dim}`,
                  background: done ? phase.color : "transparent",
                  display: "flex", alignItems: "center", justifyContent: "center",
                  flexShrink: 0,
                  fontSize: 11,
                  color: done ? C.bg : phase.color,
                  fontWeight: 700,
                  animation: active ? "pulse-ring 1s infinite" : "none",
                  fontFamily: "'Space Mono', monospace",
                }}>
                  {done ? "✓" : active ? "●" : String(i + 1).padStart(2, "0")}
                </div>
                <span style={{ fontSize: 13, color: done ? C.text : active ? C.text : C.muted, lineHeight: 1.6 }}>
                  {step}
                </span>
              </div>
            );
          })}
        </div>
      </div>

      {/* Outputs */}
      {isCompleted && (
        <div className="fade-in" style={{
          background: C.panel,
          border: `1px solid ${C.green}30`,
          borderRadius: 10,
          padding: 16,
        }}>
          <div className="mono" style={{ fontSize: 10, color: C.muted, marginBottom: 10 }}>GENERATED OUTPUTS</div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
            {phase.outputs.map((o, i) => (
              <OutputPill key={i} label={o} color={phase.color} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function IPDomainPanel({ domain, isSelected, onClick }) {
  return (
    <div
      onClick={onClick}
      style={{
        border: `1px solid ${isSelected ? domain.color : C.border}`,
        borderRadius: 8,
        padding: "14px 16px",
        cursor: "pointer",
        background: isSelected ? `${domain.color}12` : C.surface,
        transition: "all 0.2s",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <span style={{ fontSize: 22, color: domain.color }}>{domain.icon}</span>
        <div>
          <div style={{ fontSize: 15, fontWeight: 700, color: isSelected ? domain.color : C.text }}>
            {domain.domain}
          </div>
          <div className="mono" style={{ fontSize: 10, color: C.muted }}>{domain.ips.length} IPs</div>
        </div>
      </div>
    </div>
  );
}

function IPIntentDetail({ domain }) {
  return (
    <div className="fade-in" style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <div style={{
        background: C.panel,
        border: `1px solid ${domain.color}40`,
        borderRadius: 10,
        padding: 20,
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 16 }}>
          <span style={{ fontSize: 28, color: domain.color }}>{domain.icon}</span>
          <div>
            <div className="mono" style={{ fontSize: 10, color: C.muted }}>DOMAIN</div>
            <div style={{ fontSize: 20, fontWeight: 800, color: domain.color }}>{domain.domain} IPs</div>
          </div>
        </div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
          {domain.ips.map((ip, i) => (
            <span key={i} className="tag" style={{
              background: `${domain.color}15`,
              color: domain.color,
              border: `1px solid ${domain.color}40`,
              fontSize: 11,
            }}>
              {ip}
            </span>
          ))}
        </div>
      </div>

      <div style={{
        background: C.panel,
        border: `1px solid ${C.border}`,
        borderRadius: 10,
        padding: 20,
      }}>
        <div className="mono" style={{ fontSize: 10, color: C.muted, marginBottom: 14 }}>
          ARCHITECTURE INTENT DOCUMENT FIELDS
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {domain.intentFields.map((field, i) => (
            <div key={i} style={{
              display: "flex",
              alignItems: "center",
              gap: 14,
              padding: "10px 14px",
              borderRadius: 6,
              border: `1px solid ${C.border}`,
              background: C.surface,
            }}>
              <span style={{ color: domain.color, fontSize: 16, flexShrink: 0 }}>◈</span>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 13, fontWeight: 600, color: C.text }}>{field}</div>
                <div className="mono" style={{ fontSize: 10, color: C.muted, marginTop: 2 }}>
                  Propagated from top-level architecture intent — traceable to requirement
                </div>
              </div>
              <span className="tag" style={{ background: "rgba(16,185,129,0.1)", color: C.green, fontSize: 9 }}>
                LINKED
              </span>
            </div>
          ))}
        </div>
      </div>

      <div style={{
        background: C.panel,
        border: `1px solid ${C.border}`,
        borderRadius: 10,
        padding: 20,
      }}>
        <div className="mono" style={{ fontSize: 10, color: C.muted, marginBottom: 12 }}>
          INTERDEPENDENCY MATRIX
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
          {["Depends ON", "Depended BY", "Shared Clocks", "Shared Power Rails"].map((label, i) => (
            <div key={i} style={{
              padding: "10px 14px",
              borderRadius: 6,
              border: `1px solid ${C.border}`,
              background: C.surface,
            }}>
              <div className="mono" style={{ fontSize: 9, color: C.muted, marginBottom: 4 }}>{label}</div>
              <div style={{ fontSize: 12, color: C.text }}>
                {["Interconnect Fabric, PMU", "CPU Core, DMA", "25/100/200 MHz", "VDD_CORE, VDD_IO"][i]}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function SpecInput({ onGenerate }) {
  const [spec, setSpec] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  const handleGenerate = async () => {
    if (!spec.trim()) return;
    setLoading(true);
    setResult(null);
    setError(null);
    try {
      const res = await fetch("https://api.anthropic.com/v1/messages", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          model: "claude-sonnet-4-20250514",
          max_tokens: 1000,
          system: `You are an expert IC architecture engineer. When given a product spec or description, you:
1. Identify the application domain
2. List the top-level functional blocks needed
3. Recommend key IPs for Digital, Analog, Mixed-Signal domains
4. State the top 3 architecture decisions and trade-offs
5. Provide a one-sentence Architecture Intent Statement

Respond ONLY in JSON format with keys: domain, functionalBlocks (array), recommendedIPs (object with digital/analog/mixedSignal arrays), architectureDecisions (array of {decision, tradeoff}), intentStatement. No markdown, no backticks, pure JSON only.`,
          messages: [{ role: "user", content: `IC Spec: ${spec}` }],
        }),
      });
      const data = await res.json();
      const text = data.content.map(c => c.text || "").join("");
      const parsed = JSON.parse(text.replace(/```json|```/g, "").trim());
      setResult(parsed);
      onGenerate(parsed);
    } catch (e) {
      setError("Failed to analyze spec. Check API connectivity.");
    }
    setLoading(false);
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <div style={{
        background: C.panel,
        border: `1px solid ${C.border}`,
        borderRadius: 10,
        padding: 20,
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 14 }}>
          <AIBadge label="NLP + Classifier" />
          <span className="mono" style={{ fontSize: 10, color: C.muted }}>LIVE ARCHITECTURE INTELLIGENCE</span>
        </div>
        <div className="mono" style={{ fontSize: 10, color: C.muted, marginBottom: 8 }}>ENTER APPLICATION SPEC</div>
        <textarea
          value={spec}
          onChange={e => setSpec(e.target.value)}
          placeholder="e.g. A wearable health monitor SoC with BLE 5.3, 12-bit biometric ADC, Cortex-M33 @ 64MHz, 10-day battery life, medical grade accuracy, ultra-low power sleep at 2µA..."
          style={{
            width: "100%",
            height: 120,
            background: C.surface,
            border: `1px solid ${C.border}`,
            borderRadius: 6,
            padding: 12,
            color: C.text,
            fontFamily: "'Space Mono', monospace",
            fontSize: 12,
            lineHeight: 1.6,
            resize: "vertical",
            outline: "none",
          }}
        />
        <button
          onClick={handleGenerate}
          disabled={loading || !spec.trim()}
          style={{
            marginTop: 12,
            padding: "10px 28px",
            borderRadius: 6,
            border: "none",
            background: loading ? `${C.accent}30` : C.accent,
            color: loading ? C.accent : C.bg,
            fontFamily: "'Space Mono', monospace",
            fontSize: 12,
            fontWeight: 700,
            cursor: loading || !spec.trim() ? "not-allowed" : "pointer",
            letterSpacing: "0.05em",
          }}
        >
          {loading ? "◈ ANALYZING SPEC…" : "◈ GENERATE ARCHITECTURE"}
        </button>
        {error && <div style={{ marginTop: 10, color: C.red, fontSize: 12 }}>{error}</div>}
      </div>

      {result && (
        <div className="fade-in" style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <div style={{
            background: `${C.accent}10`,
            border: `1px solid ${C.accent}40`,
            borderRadius: 10,
            padding: 20,
          }}>
            <div className="mono" style={{ fontSize: 10, color: C.muted, marginBottom: 8 }}>ARCHITECTURE INTENT STATEMENT</div>
            <div style={{ fontSize: 15, fontWeight: 700, color: C.accent, lineHeight: 1.5, fontStyle: "italic" }}>
              "{result.intentStatement}"
            </div>
            <div style={{ marginTop: 10 }}>
              <span className="tag" style={{ background: `${C.gold}20`, color: C.gold, border: `1px solid ${C.gold}40` }}>
                Domain: {result.domain}
              </span>
            </div>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
            <div style={{ background: C.panel, border: `1px solid ${C.border}`, borderRadius: 10, padding: 16 }}>
              <div className="mono" style={{ fontSize: 10, color: C.muted, marginBottom: 10 }}>FUNCTIONAL BLOCKS</div>
              {result.functionalBlocks?.map((b, i) => (
                <div key={i} style={{ fontSize: 12, color: C.text, padding: "4px 0", borderBottom: `1px solid ${C.border}`, display: "flex", gap: 8 }}>
                  <span style={{ color: C.accent }}>▸</span> {b}
                </div>
              ))}
            </div>
            <div style={{ background: C.panel, border: `1px solid ${C.border}`, borderRadius: 10, padding: 16 }}>
              <div className="mono" style={{ fontSize: 10, color: C.muted, marginBottom: 10 }}>IP RECOMMENDATIONS</div>
              {["digital", "analog", "mixedSignal"].map(k => (
                result.recommendedIPs?.[k]?.map((ip, i) => (
                  <div key={`${k}-${i}`} style={{ fontSize: 12, color: C.text, padding: "4px 0", borderBottom: `1px solid ${C.border}`, display: "flex", gap: 8 }}>
                    <span style={{ color: { digital: C.accent, analog: C.gold, mixedSignal: C.violet }[k] }}>
                      {k === "digital" ? "▣" : k === "analog" ? "◌" : "◑"}
                    </span> {ip}
                  </div>
                ))
              ))}
            </div>
          </div>

          <div style={{ background: C.panel, border: `1px solid ${C.border}`, borderRadius: 10, padding: 16 }}>
            <div className="mono" style={{ fontSize: 10, color: C.muted, marginBottom: 10 }}>ARCHITECTURE DECISIONS & TRADE-OFFS</div>
            {result.architectureDecisions?.map((d, i) => (
              <div key={i} style={{
                padding: "10px 14px",
                borderRadius: 6,
                border: `1px solid ${C.border}`,
                background: C.surface,
                marginBottom: 8,
              }}>
                <div style={{ fontSize: 13, fontWeight: 600, color: C.text }}>{d.decision}</div>
                <div className="mono" style={{ fontSize: 11, color: C.muted, marginTop: 4 }}>↳ {d.tradeoff}</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Main App ───────────────────────────────────────────────────
export default function App() {
  const [activeTab, setActiveTab] = useState("workflow");
  const [activePhase, setActivePhase] = useState(0);
  const [completedPhases, setCompletedPhases] = useState(new Set());
  const [activeDomain, setActiveDomain] = useState(0);
  const [generatedArch, setGeneratedArch] = useState(null);

  const tabs = [
    { id: "workflow", label: "Architecture Workflow" },
    { id: "ip", label: "IP Intent Propagation" },
    { id: "ai", label: "AI Spec Analyzer" },
  ];

  const totalDone = completedPhases.size;
  const overallPct = Math.round((totalDone / PHASES.length) * 100);

  return (
    <>
      <style>{gStyles}</style>
      <div className="grid-bg" style={{ minHeight: "100vh", padding: "0 0 40px 0" }}>

        {/* Header */}
        <div style={{
          borderBottom: `1px solid ${C.border}`,
          background: `${C.surface}e0`,
          backdropFilter: "blur(12px)",
          position: "sticky",
          top: 0,
          zIndex: 100,
        }}>
          <div style={{ maxWidth: 1400, margin: "0 auto", padding: "16px 28px" }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 12 }}>
              <div>
                <div className="mono" style={{ fontSize: 10, color: C.muted, letterSpacing: "0.15em", marginBottom: 4 }}>
                  ◈ ANTHROPIC-POWERED — IC DESIGN INTELLIGENCE
                </div>
                <h1 className="shimmer-text" style={{ fontSize: 22, fontWeight: 800, letterSpacing: "-0.02em" }}>
                  Silicon Architecture Platform
                </h1>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
                <div style={{ textAlign: "right" }}>
                  <div className="mono" style={{ fontSize: 10, color: C.muted }}>OVERALL PROGRESS</div>
                  <div className="mono" style={{ fontSize: 16, color: C.accent, fontWeight: 700 }}>{overallPct}%</div>
                </div>
                <div style={{ width: 80, height: 6, background: C.dim, borderRadius: 4, overflow: "hidden" }}>
                  <div className="progress-bar-inner" style={{ width: `${overallPct}%` }} />
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  <StatusDot active={true} />
                  <span className="mono" style={{ fontSize: 10, color: C.green }}>SYSTEM ONLINE</span>
                </div>
              </div>
            </div>

            {/* Tabs */}
            <div style={{ display: "flex", gap: 4, marginTop: 16 }}>
              {tabs.map(tab => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  style={{
                    padding: "7px 18px",
                    borderRadius: 6,
                    border: `1px solid ${activeTab === tab.id ? C.accent : C.border}`,
                    background: activeTab === tab.id ? `${C.accent}15` : "transparent",
                    color: activeTab === tab.id ? C.accent : C.muted,
                    fontFamily: "'Space Mono', monospace",
                    fontSize: 11,
                    cursor: "pointer",
                    letterSpacing: "0.05em",
                    transition: "all 0.2s",
                  }}
                >
                  {tab.label}
                </button>
              ))}
            </div>
          </div>
        </div>

        <div style={{ maxWidth: 1400, margin: "0 auto", padding: "28px 28px 0" }}>

          {/* ── TAB: Workflow ── */}
          {activeTab === "workflow" && (
            <div style={{ display: "grid", gridTemplateColumns: "320px 1fr", gap: 20, alignItems: "start" }}>
              {/* Phase list */}
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                <div className="mono" style={{ fontSize: 10, color: C.muted, letterSpacing: "0.1em", marginBottom: 4 }}>
                  DEVELOPMENT PHASES
                </div>
                {PHASES.map((phase, i) => (
                  <PhaseCard
                    key={phase.id}
                    phase={phase}
                    index={i}
                    isActive={activePhase === i}
                    isCompleted={completedPhases.has(i)}
                    onClick={() => setActivePhase(i)}
                  />
                ))}

                {/* Legend */}
                <div style={{
                  marginTop: 8,
                  background: C.panel,
                  border: `1px solid ${C.border}`,
                  borderRadius: 8,
                  padding: 14,
                }}>
                  <div className="mono" style={{ fontSize: 9, color: C.muted, marginBottom: 8 }}>AUTOMATION LEGEND</div>
                  {[["✦", C.violet, "AI-driven step"], ["▶", C.accent, "Automated execution"], ["✓", C.green, "Phase complete"]].map(([sym, col, lbl]) => (
                    <div key={lbl} style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 6 }}>
                      <span style={{ color: col, fontSize: 14, width: 16 }}>{sym}</span>
                      <span style={{ fontSize: 11, color: C.muted }}>{lbl}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Phase detail */}
              <div style={{ minHeight: 600 }}>
                <PhaseDetail
                  key={activePhase}
                  phase={PHASES[activePhase]}
                  isCompleted={completedPhases.has(activePhase)}
                  onComplete={() => setCompletedPhases(prev => new Set([...prev, activePhase]))}
                />
              </div>
            </div>
          )}

          {/* ── TAB: IP Intent ── */}
          {activeTab === "ip" && (
            <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
              {/* Philosophy banner */}
              <div style={{
                background: `${C.violet}10`,
                border: `1px solid ${C.violet}40`,
                borderRadius: 10,
                padding: 20,
              }}>
                <div className="mono" style={{ fontSize: 10, color: C.muted, marginBottom: 8 }}>ARCHITECTURE INTENT PROPAGATION PHILOSOPHY</div>
                <p style={{ fontSize: 14, color: C.text, lineHeight: 1.7, maxWidth: 900 }}>
                  Every IP in the device receives a complete <strong style={{ color: C.violet }}>Architecture Intent Document (AID)</strong> derived
                  from the top-level architecture statement. The AID carries: the IP's functional objective,
                  performance specifications, input/output contracts, power/clock domain assignment, and a
                  full map of its upstream/downstream interdependencies. No IP team operates in isolation —
                  architectural intent propagates with full traceability.
                </p>
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "220px 1fr", gap: 16 }}>
                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  <div className="mono" style={{ fontSize: 10, color: C.muted, marginBottom: 4 }}>SELECT DOMAIN</div>
                  {IP_DOMAINS.map((d, i) => (
                    <IPDomainPanel
                      key={d.domain}
                      domain={d}
                      isSelected={activeDomain === i}
                      onClick={() => setActiveDomain(i)}
                    />
                  ))}
                </div>
                <div style={{ overflowY: "auto" }}>
                  <IPIntentDetail domain={IP_DOMAINS[activeDomain]} />
                </div>
              </div>
            </div>
          )}

          {/* ── TAB: AI Analyzer ── */}
          {activeTab === "ai" && (
            <div style={{ maxWidth: 900 }}>
              <div style={{
                background: `${C.gold}10`,
                border: `1px solid ${C.gold}40`,
                borderRadius: 10,
                padding: 20,
                marginBottom: 20,
              }}>
                <div className="mono" style={{ fontSize: 10, color: C.muted, marginBottom: 6 }}>
                  ✦ AI-POWERED — LIVE ARCHITECTURE INTELLIGENCE
                </div>
                <p style={{ fontSize: 14, color: C.text, lineHeight: 1.7 }}>
                  Describe your device in plain language — from a simple IoT sensor to a complex SoC.
                  Claude will classify the application domain, recommend a top-level IP set, identify key
                  architecture decisions, and generate your <strong style={{ color: C.gold }}>Architecture Intent Statement</strong>.
                </p>
              </div>
              <SpecInput onGenerate={setGeneratedArch} />
            </div>
          )}
        </div>
      </div>
    </>
  );
}
