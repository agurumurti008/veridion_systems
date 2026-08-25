# Silicon Architecture Platform — Complete Technical Breakdown
**Document Type:** Implementation Strategy, AI Plan, I/O Definitions, POC Timeline  
**Artifact:** `ic-arch-platform.jsx`  
**Date:** May 2026

---

## 1. WHAT THE JSX FILE IS — STRUCTURE EXPLAINED

The file is a **single-file React application** (928 lines) that runs entirely in the browser. It is a UI prototype and interactive specification tool — not yet connected to a real backend. Every component, style, data model, and the one live AI call are self-contained inside this file.

### 1.1 File Architecture Map

```
ic-arch-platform.jsx
│
├── CONSTANTS (lines 1–226)
│   ├── C{}              — Color design system (17 semantic tokens)
│   ├── PHASES[]         — 6 architecture phases, each with: id, label, icon,
│   │                      color, aiRole, steps[], outputs[]
│   └── IP_DOMAINS[]     — 4 domain cards: Digital, Analog, Mixed-Signal, RF
│                          each with: ips[], intentFields[]
│
├── GLOBAL CSS (lines 147–226)
│   ├── Google Fonts: Space Mono (monospace) + Syne (display)
│   ├── CSS keyframes: pulse-ring, scan, blink, fadeSlideIn, shimmer
│   └── Utility classes: .mono, .tag, .fade-in, .grid-bg, .shimmer-text,
│                         .progress-bar-inner
│
├── PRIMITIVE COMPONENTS (lines 228–300)
│   ├── AIBadge({label})       — Violet pill showing AI engine name per phase
│   ├── StatusDot({active})    — Animated green/grey pulse dot
│   └── OutputPill({label})    — Colored tag for phase output artifacts
│
├── PHASE COMPONENTS (lines 302–450)
│   ├── PhaseCard              — Sidebar list item (click → select phase)
│   │   Props: phase, index, isActive, onClick, isCompleted
│   │   State: none (controlled)
│   │
│   └── PhaseDetail            — Main content panel for selected phase
│       Props: phase, onComplete, isCompleted
│       State: stepsDone (int), running (bool)
│       Logic: runAutomation() — setTimeout chain fires every 700ms,
│              increments stepsDone, calls onComplete() at last step
│
├── IP DOMAIN COMPONENTS (lines 452–570)
│   ├── IPDomainPanel          — Domain selector sidebar card
│   └── IPIntentDetail         — Full AID view: IP list, intent fields,
│                                interdependency matrix (static mock data)
│
├── AI COMPONENT (lines 572–727)
│   └── SpecInput              — ONLY component making a real API call
│       State: spec (string), loading, result, error
│       API: POST https://api.anthropic.com/v1/messages
│       Model: claude-sonnet-4-20250514
│       Returns: JSON {domain, functionalBlocks[], recommendedIPs{},
│                      architectureDecisions[], intentStatement}
│
└── ROOT APP (lines 729–927)
    State: activeTab, activePhase, completedPhases (Set), activeDomain,
           generatedArch
    Layout: sticky header + 3 tab panels
    Tabs:   "workflow" | "ip" | "ai"
```

### 1.2 What Is Real vs. Simulated in Current JSX

| Feature | Status | Notes |
|---|---|---|
| Phase step animation | **Simulated** | setTimeout chain, no real processing |
| Phase output artifacts | **Simulated** | Labels only, no file generation |
| IP interdependency matrix | **Static mock** | Hardcoded strings |
| AI Spec Analyzer | **REAL** | Live Claude API call, real JSON response |
| Phase progress tracking | **Real UI state** | completedPhases Set persists within session |
| Overall progress % | **Real** | Derived from completedPhases.size / 6 |

---

## 2. IMPLEMENTATION STRATEGY — FROM POC TO PRODUCTION

The platform needs three layers built on top of the current JSX shell.

### 2.1 Three-Layer Architecture

```
┌─────────────────────────────────────────────┐
│  LAYER 3 — Frontend (current JSX)           │
│  React UI · Tab navigation · Phase runner   │
│  State machine · AI result display          │
├─────────────────────────────────────────────┤
│  LAYER 2 — Orchestration Backend            │
│  FastAPI/Node server · Agent controller     │
│  Phase pipeline manager · File store        │
│  Traceability engine · Conflict detector    │
├─────────────────────────────────────────────┤
│  LAYER 1 — Data & AI Services               │
│  IP Library (PostgreSQL/JSON) · Vector DB   │
│  Claude API (agents) · PPA models           │
│  Standards DB · Dependency graph (Neo4j)    │
└─────────────────────────────────────────────┘
```

### 2.2 Technology Stack per Layer

**Frontend (Layer 3)**
- React 18 + Vite
- State: Zustand (replace useState chains with a global store)
- API client: Axios with interceptors for auth + error handling
- File export: jsPDF / docx.js for AID document download
- Real-time updates: WebSocket or SSE for streaming phase progress

**Orchestration Backend (Layer 2)**
- Python FastAPI (recommended for IC/EDA community familiarity)
- Phase pipeline: Celery + Redis for async task queues
- File store: S3-compatible (MinIO for on-prem, AWS S3 for cloud)
- Traceability DB: PostgreSQL with JSONB columns
- Dependency graph: Neo4j (IP-to-IP relationships as graph nodes/edges)

**AI & Data Services (Layer 1)**
- LLM: Anthropic Claude claude-sonnet-4-20250514 (already used)
- Embeddings: claude-sonnet-4-20250514 or `text-embedding-3-small` for IP library semantic search
- Vector DB: Pinecone or pgvector (IP library RAG)
- PPA models: Python analytical models (sklearn) or regression models trained on historical data
- Standards DB: Structured JSON files for ISO 26262, IEC 61508, DO-254 rule sets

---

## 3. AUTOMATION SCRIPTS — WHAT NEEDS TO BE BUILT

Each phase in the UI maps to a real automation script on the backend.

### Script P01 — Spec Parser (`spec_parser.py`)
```
Input:  Raw text string (natural language or structured)
Tools:  Claude API (NLP extraction), regex validators
Output: spec.json — formalized spec with traceability IDs
        domain_report.json — application domain classification
        traceability_matrix_v0.csv — requirement ID ↔ spec field mapping
```

### Script P02 — Architecture Explorer (`arch_explorer.py`)
```
Input:  spec.json from P01, IP library (PostgreSQL), prior arch DB
Tools:  Embedding search (semantic IP matching),
        Claude API (candidate generation),
        PPA scoring models (Python)
Output: candidate_matrix.json — N candidate architectures ranked
        ppa_scorecards.json — Power/Performance/Area per candidate
        reuse_analysis.json — reuse flag per IP with cost estimate
```

### Script P03 — Partitioner (`domain_partitioner.py`)
```
Input:  candidate_matrix.json (top-ranked candidate from P02)
Tools:  Constraint solver (OR-Tools / Z3),
        Clock domain rule engine,
        Floorplan heuristic checker
Output: partition_map.json — IP→domain assignments
        clock_power_spec.json — domain clocks, voltages, isolation cells
        interface_protocol_list.json — all inter-domain interface types
```

### Script P04 — IP Selector & Dependency Mapper (`ip_dep_mapper.py`)
```
Input:  partition_map.json, IP library
Tools:  Rule-based matcher + Claude re-ranking,
        Port compatibility checker,
        Latency budget calculator,
        Neo4j graph writer
Output: ip_selection_register.json — final selected IPs with versions
        dependency_graph.json (+ Neo4j graph) — full I/O dependency map
        integration_checklist.csv — per-interface pass/fail criteria
```

### Script P05 — Intent Propagator (`intent_propagator.py`)
```
Input:  ip_selection_register.json, dependency_graph.json, spec.json
Tools:  Claude API (document generation, one call per IP),
        Traceability linker (PostgreSQL queries),
        Change impact analyzer (graph traversal)
Output: intent_statement.txt — top-level architecture philosophy
        aid_pack/ — folder of per-IP Architecture Intent Documents (PDF/MD)
        change_impact_matrix.json — what changes if any requirement shifts
```

### Script P06 — Spec Closer (`spec_closure.py`)
```
Input:  All outputs from P01–P05
Tools:  Formal completeness checker (rule engine),
        Anti-pattern detector (Claude + rules),
        PPA feasibility verifier
Output: spec_closure_report.pdf
        architecture_review_package.zip — all artifacts bundled
        frozen_baseline.json — version-locked, signed-off state
```

---

## 4. AI IMPLEMENTATION PLAN — AGENT VS. PIPELINE DECISION

### 4.1 Decision: Hybrid — Pipeline + Selective Agentic Calls

The system is **NOT a single autonomous agent**. That would be unreliable for IC design where every decision has downstream cost consequences. Instead, the design is:

```
Deterministic Pipeline (automation scripts P01–P06)
        +
Selective Claude Agent Calls at defined decision points
        +
Human-in-the-loop gates between phases
```

This is the correct architecture because:
- IC design errors compound — a wrong domain classification in P01 propagates to P06
- Engineers need auditability — every AI decision must show its reasoning and be overridable
- PPA trade-offs require human sign-off — AI ranks candidates, human selects
- Safety-critical domains (Automotive, Medical) require human approval at every gate

### 4.2 Where Claude Acts as an Agent (Tool-Using)

Three phases use Claude with tool_use enabled — meaning Claude can decide to call functions, read its results, and reason further before responding.

**Agent Call 1 — Spec Enrichment (P01)**
```
Tools given to Claude:
  - search_standards_db(standard_id)   → returns rule text
  - lookup_domain_profile(domain_name) → returns typical IP set
  - flag_ambiguity(field, reason)      → marks unclear spec fields

Claude's job: Read raw spec → call tools to resolve ambiguities →
              return enriched, validated spec JSON

Why agentic: Spec ambiguity resolution requires multi-step reasoning.
             Claude may call search_standards_db 3–4 times before
             arriving at the right safety standard classification.
```

**Agent Call 2 — Architecture Candidate Generation (P02)**
```
Tools given to Claude:
  - query_ip_library(domain, function) → returns matching IPs
  - get_prior_arch(domain, ppa_target) → returns similar past designs
  - run_ppa_model(ip_list, config)     → returns PPA estimate

Claude's job: Generate 3–5 candidate architectures, for each one
              call query_ip_library and run_ppa_model to score it,
              rank by PPA and risk, return candidate_matrix.json

Why agentic: Exploration space is large. Claude iteratively refines
             candidates based on PPA feedback from tool calls.
             This is classic ReAct (Reason + Act) loop behavior.
```

**Agent Call 3 — Per-IP AID Generation (P05)**
```
Tools given to Claude:
  - get_ip_spec(ip_id)                 → detailed IP spec from library
  - get_dependencies(ip_id)            → upstream + downstream IPs
  - get_requirement_trace(req_id)      → requirement text by ID

Claude's job: For each IP in ip_selection_register.json:
              1. Call get_ip_spec → understand what this IP does
              2. Call get_dependencies → understand its connections
              3. Call get_requirement_trace → link to top-level reqs
              4. Generate AID document in Markdown

Why agentic: Each AID must be grounded in real data. Claude cannot
             hallucinate dependency details — tool calls enforce grounding.
             This runs N times (once per IP, parallelizable).
```

### 4.3 Where Claude is Non-Agentic (Single-Shot Inference)

These calls are deterministic prompts with structured output — no tool use, no multi-step:

| Phase | Claude Role | Prompt Style |
|---|---|---|
| P01 domain classification | Classifier | System prompt with domain taxonomy → JSON output |
| P03 interface naming | Naming assistant | IP pair list → protocol name suggestions |
| P06 anti-pattern detection | Reviewer | Architecture JSON → list of detected patterns |
| All phases — error messages | Explainer | Error context → human-readable explanation |

### 4.4 System Prompt Strategy

Each Claude call uses a specialized system prompt. The core principle: **Claude is always told it is a senior IC architect, never a general assistant.**

```
Base system prompt (all calls):
"You are a senior IC architecture engineer with 20 years of experience
in digital, analog, and mixed-signal SoC design. You have deep knowledge
of IP integration, PPA optimization, and functional safety standards.
All your responses must be precise, technically accurate, and directly
applicable to silicon design. Never guess — use the tools provided to
ground your answers in real data."
```

Each phase appends domain-specific context on top of this base.

### 4.5 Structured Output Enforcement

All Claude responses that feed into automation scripts return JSON, enforced by:
1. System prompt: "Respond ONLY in JSON. No markdown, no preamble."
2. Response validation: Python `pydantic` models validate schema before passing downstream
3. Retry logic: If JSON parse fails, re-call with error context (max 3 retries)

---

## 5. INPUTS AND OUTPUTS — EVERY STAGE

### Stage P01 — Application Spec Ingestion

**INPUT**
```
Type: Free text (natural language) OR structured YAML/JSON
Min fields: Application description (required)
Optional:   Target process node, package type, known standards
Example:
  "Ultra-low-power BLE SoC for continuous glucose monitoring.
   Cortex-M0+ at 32MHz, 10-bit ADC, BLE 5.2, coin cell battery,
   3-year shelf life, FDA Class II device."
```

**OUTPUT**
```json
// spec.json
{
  "spec_id": "SPEC-2026-0047",
  "domain": "Medical",
  "safety_standard": "IEC 62304",
  "functional_blocks": ["MCU Core", "RF Block", "AFE", "PMU"],
  "requirements": [
    { "req_id": "REQ-001", "text": "BLE 5.2 compliant", "priority": "SHALL" },
    { "req_id": "REQ-002", "text": "ADC resolution ≥ 10-bit", "priority": "SHALL" }
  ],
  "power_envelope_mw": 2.5,
  "frequency_target_mhz": 32,
  "ambiguities": ["Process node not specified — assumed 40nm ULP"]
}

// traceability_matrix_v0.csv
REQ-001, "BLE 5.2 compliant", P01, spec.json
REQ-002, "ADC resolution ≥ 10-bit", P01, spec.json
```

---

### Stage P02 — Architecture Exploration & Benchmarking

**INPUT**
```
spec.json (from P01)
IP library (PostgreSQL table: ip_id, name, domain, function, ppa_data)
Prior architecture DB (historical designs with PPA outcomes)
```

**OUTPUT**
```json
// candidate_matrix.json
{
  "candidates": [
    {
      "candidate_id": "ARCH-A",
      "topology": "single-core AHB bus",
      "ip_set": ["CM0+", "BLE-PHY-40nm", "SAR-ADC-10b", "LDO"],
      "ppa": { "power_mw": 2.1, "performance_score": 87, "area_mm2": 0.9 },
      "risk": "low",
      "reuse_pct": 85
    },
    {
      "candidate_id": "ARCH-B",
      "topology": "dual-bus AHB/APB",
      "ip_set": ["CM0+", "BLE-PHY-40nm", "Delta-Sigma-ADC", "LDO", "DCDC"],
      "ppa": { "power_mw": 1.8, "performance_score": 91, "area_mm2": 1.1 },
      "risk": "medium",
      "reuse_pct": 70
    }
  ],
  "recommended": "ARCH-A",
  "reasoning": "ARCH-A meets power envelope with lower risk and 85% IP reuse"
}
```

---

### Stage P03 — System Partitioning & Domain Assignment

**INPUT**
```
candidate_matrix.json → top candidate (ARCH-A)
Clock domain rules (JSON rule file)
Voltage domain rules (process-specific)
Floorplan feasibility model (area/aspect ratio constraints)
```

**OUTPUT**
```json
// partition_map.json
{
  "domains": {
    "digital": { "ips": ["CM0+", "DMA"], "clock_mhz": 32, "voltage_v": 1.0 },
    "analog":  { "ips": ["SAR-ADC", "LDO", "Bandgap"], "clock_mhz": 1, "voltage_v": 1.8 },
    "mixed_signal": { "ips": ["BLE-PHY"], "clock_mhz": 16, "voltage_v": 1.2 }
  },
  "isolation_cells": ["ISO-D2A-01", "ISO-A2D-01"],
  "level_shifters": ["LS-1V0-to-1V8"],
  "clock_crossings": [
    { "from": "digital/32MHz", "to": "mixed_signal/16MHz", "type": "CDC_sync_2ff" }
  ]
}

// clock_power_spec.json
// interface_protocol_list.json — ["AHB", "APB", "SPI", "UART", "I2C"]
```

---

### Stage P04 — IP Selection & Dependency Mapping

**INPUT**
```
partition_map.json
IP library (filtered by domain from P03)
Latency budget (derived from spec.json performance requirements)
Protocol compatibility rules
```

**OUTPUT**
```json
// ip_selection_register.json
{
  "selected_ips": [
    {
      "ip_id": "CM0PLUS-40NM-V3",
      "name": "Cortex-M0+",
      "domain": "digital",
      "version": "r0p1",
      "source": "hard_macro",
      "ports": { "in": ["HCLK", "HRESETn", "HADDR[31:0]"], "out": ["HRDATA[31:0]"] },
      "perf_bounds": { "max_freq_mhz": 50, "power_mw_active": 0.8 }
    }
  ]
}

// dependency_graph.json
{
  "nodes": [{"id": "CM0PLUS"}, {"id": "DMA"}, {"id": "AHB-BUS"}],
  "edges": [
    {"from": "CM0PLUS", "to": "AHB-BUS", "type": "master", "protocol": "AHB-Lite"},
    {"from": "DMA", "to": "AHB-BUS", "type": "master", "protocol": "AHB-Lite"}
  ]
}

// integration_checklist.csv
IP_pair, Interface, Protocol_match, Width_match, Timing_met, CDC_handled
CM0PLUS↔AHB, AHB-Lite, PASS, PASS, PASS, N/A
DMA↔SAR-ADC, APB, PASS, PASS, REVIEW, N/A
```

---

### Stage P05 — Architecture Intent Propagation

**INPUT**
```
ip_selection_register.json
dependency_graph.json
spec.json (traceability source)
Per-IP template (Markdown AID template)
```

**OUTPUT**
```
// intent_statement.txt
"A medical-grade, ultra-low-power BLE SoC designed to sustain continuous
glucose monitoring for 3 years on a coin cell, prioritizing power
integrity and analog signal chain quality above all other trade-offs."

// aid_pack/ (one file per IP)
  CM0PLUS_AID.md
  SAR_ADC_AID.md
  BLE_PHY_AID.md
  LDO_AID.md
  ...

// Each AID file contains:
  ## Objective
  ## Performance Specifications (traced to REQ-IDs)
  ## Input Ports & Expected Signals
  ## Output Ports & Signal Contracts
  ## Clock Domain & Power Domain Assignment
  ## Upstream Dependencies (what this IP consumes)
  ## Downstream Dependents (what consumes this IP)
  ## Known Constraints & Risks
  ## Open Items for IP Owner

// change_impact_matrix.json
{
  "if_changed": "REQ-002 (ADC resolution)",
  "impacts": ["SAR_ADC selection", "AFE gain chain", "digital post-processing IP"]
}
```

---

### Stage P06 — Spec Closure & Architecture Sign-Off

**INPUT**
```
All outputs P01–P05 (entire pipeline state)
Anti-pattern rule library (JSON)
PPA feasibility model
Reviewer identity + approval workflow config
```

**OUTPUT**
```
// spec_closure_report.pdf
  - Completeness score: X/Y fields defined
  - Open items list (blocking vs. non-blocking)
  - PPA feasibility: PASS / WARN / FAIL per target
  - Anti-patterns detected: [list]

// architecture_review_package.zip
  Contains: spec.json, partition_map.json, ip_selection_register.json,
            dependency_graph.json, all AIDs, closure report

// frozen_baseline.json
{
  "baseline_id": "ARCH-BL-001",
  "frozen_at": "2026-05-19T14:32:00Z",
  "approved_by": "john.smith@company.com",
  "hash": "sha256:a3f9...",
  "phase_outputs": { ... all artifact paths and hashes ... }
}
```

---

## 6. POC TIMELINE — 8 WEEKS TO WORKING PROTOTYPE

### Week 1 — Foundation & Data
**Goal:** Backend skeleton + IP library populated

| Task | Owner | Details |
|---|---|---|
| Set up FastAPI server | Backend | 3 endpoints: POST /spec, GET /phase/{id}/status, GET /artifacts |
| PostgreSQL schema | Backend | Tables: specs, ips, architectures, artifacts, traceability |
| Seed IP library | Domain Eng | Import 20–30 representative IPs across 4 domains |
| Connect JSX → backend | Frontend | Replace setTimeout simulation with real API calls |
| Anthropic API key setup | All | Rate limits, cost budget, error handling |

**POC Milestone:** Frontend calls real backend. Phase runner shows real server responses.

---

### Week 2 — P01 Spec Parser (Real)
**Goal:** Real NLP spec ingestion running end-to-end

| Task | Details |
|---|---|
| `spec_parser.py` | Claude single-shot call, pydantic validation, write to DB |
| Domain classifier | System prompt + 10-class domain taxonomy |
| Standards rule engine | JSON rules for ISO 26262, IEC 61508, DO-254 |
| Traceability matrix generator | Python script: spec fields → REQ-IDs → CSV |
| UI: spec upload | JSX: file upload + text input, real loading state, real output display |

**POC Milestone:** Paste a spec → get real spec.json + traceability matrix displayed in UI.

---

### Week 3 — P02 Architecture Explorer (AI Agent)
**Goal:** Claude agent generates real candidate architectures

| Task | Details |
|---|---|
| IP library search endpoint | FastAPI + pgvector semantic search |
| PPA scoring model | Simple Python regression (train on 50 historical data points) |
| Claude tool-use integration | query_ip_library + run_ppa_model tools registered |
| Agent loop | ReAct: Claude calls tools 2–4 times per candidate, returns candidate_matrix.json |
| UI: candidate comparison | JSX: show 2–3 candidates with PPA bars, let user pick preferred |

**POC Milestone:** AI generates 2–3 real architecture candidates for any spec input.

---

### Week 4 — P03 & P04 Partitioner + Dependency Mapper
**Goal:** Automated domain partitioning and dependency graph

| Task | Details |
|---|---|
| `domain_partitioner.py` | Rule-based + Claude validation of clock/power domain assignments |
| Constraint checker | Python: validate CDC crossings, isolation cell requirements |
| `ip_dep_mapper.py` | Port matching rules + protocol compatibility check |
| Neo4j setup | Graph DB: nodes=IPs, edges=dependencies with protocol labels |
| Conflict detector | Rule engine: flag width mismatches, protocol mismatches |
| UI: dependency graph viz | JSX: basic D3 or react-force-graph node/edge visualization |

**POC Milestone:** Auto-generated partition map + clickable dependency graph in UI.

---

### Week 5 — P05 Intent Propagation (AI Agent)
**Goal:** Auto-generate real AIDs for all selected IPs

| Task | Details |
|---|---|
| AID template (Markdown) | Define all sections with placeholder tokens |
| `intent_propagator.py` | Claude agent: per-IP tool calls → AID generation (parallelized) |
| Top-level intent distillation | Single Claude call: all phase outputs → one Intent Statement |
| Traceability linker | Python: embed REQ-IDs into every AID section |
| Change impact engine | Graph traversal: if node X changes, return all downstream nodes |
| UI: AID viewer | JSX: per-IP document viewer with download button |

**POC Milestone:** All IPs have downloadable AIDs linked to requirements.

---

### Week 6 — P06 Spec Closure + Overall Pipeline Integration
**Goal:** Full pipeline P01→P06 runs without manual steps

| Task | Details |
|---|---|
| `spec_closure.py` | Completeness checker + anti-pattern detector + PPA verifier |
| Architecture Review Package | ZIP bundler: all artifacts + checksums |
| Frozen baseline + hash | SHA-256 sign-off with timestamp and approver ID |
| Pipeline orchestrator | Celery chain: P01 → P02 → P03 → P04 → P05 → P06 |
| Human gate UI | JSX: "Approve and proceed" buttons between phases |
| UI: overall dashboard | JSX: all 6 phases on one view, real % progress, artifact download links |

**POC Milestone:** Full end-to-end run from raw spec to frozen architecture baseline.

---

### Week 7 — Testing & Validation with Real IC Specs
**Goal:** Validate against 3 real device specs from different domains

| Test Case | Domain | Validation Criteria |
|---|---|---|
| BLE wearable SoC | Medical/IoT | AID accuracy verified by domain engineer |
| ADAS vision processor | Automotive | ISO 26262 requirements correctly identified |
| Industrial HART sensor | Industrial | Mixed-signal partitioning matches expert judgment |

| Task | Details |
|---|---|
| Expert review | Have 1–2 IC architects review generated AIDs for accuracy |
| Hallucination audit | Check all AI-generated specs against known IP data |
| Latency profiling | Measure end-to-end pipeline runtime, optimize slow steps |
| Error handling | All failure modes tested: bad spec input, API timeouts, DB errors |

---

### Week 8 — POC Demo Hardening & Documentation
**Goal:** Clean, demonstrable POC ready for stakeholder review

| Task | Details |
|---|---|
| Demo script | 3 recorded runs: simple IoT → complex ADAS → edge ML chip |
| UI polish | Finalize JSX: real data everywhere, no mock fallbacks |
| Cost analysis | Actual Claude API token usage per full pipeline run |
| Limitations doc | What POC does NOT do (layout, timing closure, DRC, LVS) |
| Roadmap to v1.0 | What needs to be added for production use |

---

## 7. KEY LIMITATIONS OF CURRENT JSX (TO FIX IN WEEKS 1–8)

| Current Limitation | Fix Required |
|---|---|
| Phase steps are pure animation (setTimeout) | Replace with real backend polling |
| IP interdependency matrix is hardcoded | Pull from Neo4j graph DB |
| No data persists between sessions | Backend DB + session tokens |
| AID documents not generated | P05 agent + file download endpoint |
| No human gate between phases | Approval workflow API + UI confirmation |
| AI Spec Analyzer result not fed into phases | Wire generatedArch state into P01 kickoff |
| No error recovery | Retry logic + partial state save |

---

## 8. COST & RESOURCE ESTIMATES

### Claude API Cost per Full Pipeline Run
| Call | Model | Est. Tokens In | Est. Tokens Out | Est. Cost |
|---|---|---|---|---|
| P01 Spec enrichment (agent) | Sonnet | ~2,000 | ~1,000 | ~$0.015 |
| P02 Arch exploration (agent, 3 iterations) | Sonnet | ~6,000 | ~3,000 | ~$0.045 |
| P03 Validation | Sonnet | ~1,500 | ~800 | ~$0.010 |
| P05 AID generation (10 IPs × 1 call each) | Sonnet | ~20,000 | ~15,000 | ~$0.175 |
| P06 Anti-pattern review | Sonnet | ~3,000 | ~1,500 | ~$0.022 |
| **Total per full pipeline run** | | | | **~$0.27** |

At 100 runs/month during POC: ~$27/month in API costs.

### Engineering Effort (POC)
| Role | Weeks | FTE |
|---|---|---|
| Frontend (React/JSX evolution) | 8 | 0.5 |
| Backend (FastAPI + pipeline) | 8 | 1.0 |
| AI/Prompt Engineer | 8 | 0.5 |
| Domain Expert (IC Architect) | Weeks 5–7 | 0.3 |
| **Total** | | **~2.3 FTE for 8 weeks** |

---

*Document generated from ic-arch-platform.jsx analysis — Silicon Architecture Platform POC*
