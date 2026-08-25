import { useState, useEffect, useRef } from "react";

// ─── DESIGN TOKENS ───────────────────────────────────────────────────────────
const T = {
  bg:       "#0a0c10",
  ink:      "#0f1318",
  card:     "#141920",
  border:   "#1c2530",
  borderHi: "#2a3a4a",
  cyan:     "#00e5ff",
  amber:    "#ffb300",
  rose:     "#ff4d6d",
  sage:     "#4ade80",
  indigo:   "#818cf8",
  sand:     "#e2c98a",
  text:     "#dde3ed",
  muted:    "#5a6a7e",
  dim:      "#232f3e",
};

// ─── DATA ────────────────────────────────────────────────────────────────────

const STEPS = [
  {
    id: "s1",
    num: "01",
    title: "Application Domain Classification",
    tag: "UNIVERSAL",
    color: T.cyan,
    scale: "common",
    summary: "Classify the device by application family before touching any topology.",
    details: [
      {
        heading: "Why this comes first",
        body: "Every architectural decision — bus width, clock strategy, power domains, safety standards — flows downstream from domain classification. Getting it wrong here means rework at every subsequent step. Domain determines: regulatory requirements, operating temperature range, reliability targets, and which IP libraries are even licensed to you."
      },
      {
        heading: "How to classify",
        body: "Map against seven primary IC domains: (1) IoT/Wearable — ultra-low power, BLE/802.15.4, coin cell. (2) Mobile/Consumer — power efficiency, high integration, cost-optimized. (3) Automotive — ISO 26262 ASIL, wide temperature, EMC. (4) Industrial — IEC 61508 SIL, harsh environment, deterministic RT. (5) High-Performance Computing — bandwidth-first, DDR5/HBM, PCIe Gen5. (6) Medical — IEC 60601, IEC 62304, ultra-reliable analog front-ends. (7) RF/Communications — NF, linearity, jitter, spectrum mask."
      },
      {
        heading: "Outputs of this step",
        body: "Domain classification card, applicable safety/quality standard list, temperature grade (Commercial / Industrial / Automotive / Military), target process technology node range (e.g., 40nm ULP, 16nm FinFET, 5nm), and a constraint priority ordering: for Automotive it's Reliability > Safety > Performance > Cost; for Consumer it's Cost > Power > Performance > Area."
      }
    ],
    scaleNote: null,
    influences: []
  },
  {
    id: "s2",
    num: "02",
    title: "Requirements Formalization & Traceability Setup",
    tag: "UNIVERSAL",
    color: T.cyan,
    scale: "common",
    summary: "Convert all customer specs into traceable, measurable engineering requirements with unique IDs.",
    details: [
      {
        heading: "The traceability imperative",
        body: "In IC design, an untraced requirement is a requirement that will be forgotten. Every feature in silicon costs area and power. Traceability ensures that every block of logic has a named customer requirement justifying its existence — and that if the requirement changes, you can find every circuit element that must change with it."
      },
      {
        heading: "Shall / Should / May classification",
        body: "Use RFC 2119 severity levels for all requirements. SHALL requirements are non-negotiable — failing them means the device is non-functional or non-compliant. SHOULD requirements define target performance — missing them degrades the product but does not make it non-functional. MAY requirements are optional enhancements. This classification directly drives PPA trade-off decisions later."
      },
      {
        heading: "Formalization template per requirement",
        body: "Each requirement gets: REQ-ID, plain-language text, measurable acceptance criterion, priority (SHALL/SHOULD/MAY), source document and section, traceability to parent system requirement, and the IP(s) that will implement it. Build this as a living spreadsheet or database from day one — not a PDF that will go stale."
      }
    ],
    scaleNote: null,
    influences: []
  },
  {
    id: "s3",
    num: "03",
    title: "Functional Decomposition — Top-Level Block Diagram",
    tag: "UNIVERSAL",
    color: T.cyan,
    scale: "common",
    summary: "Decompose the device into named functional blocks before assigning any specific IP.",
    details: [
      {
        heading: "Functional blocks vs. IP — critical distinction",
        body: "A functional block is a named capability: 'memory controller', 'security engine', 'clock generation'. An IP is a specific implementation of that capability from a specific vendor or internal library. This step creates functional blocks only. Premature IP selection is one of the most common architectural mistakes — it locks you into a specific implementation before you understand the full system interaction."
      },
      {
        heading: "The block diagram hierarchy",
        body: "Draw three levels: (L1) System context — what is outside the chip (host processor, sensors, power rails, external memory). (L2) Top-level functional partitioning — 6–15 named blocks with arrows showing data flow. (L3) Block internals — major sub-blocks within each L2 block. Stop at L3 during architecture. Going deeper during architecture phase leads to premature microarchitecture decisions."
      },
      {
        heading: "Naming conventions matter",
        body: "Name blocks by function, not by component. Write 'Analog Front End' not 'ADC'. Write 'Wireless Subsystem' not 'BLE PHY'. This keeps the architecture agnostic to implementation choices during the exploration phase and prevents anchoring bias toward any particular IP."
      }
    ],
    scaleNote: null,
    influences: []
  },
  {
    id: "s4",
    num: "04",
    title: "Power Architecture — Domains, Sequencing, Budget",
    tag: "UNIVERSAL",
    color: T.cyan,
    scale: "common",
    summary: "Define all power domains and establish power budgets before any other architecture decision.",
    details: [
      {
        heading: "Why power architecture precedes everything else",
        body: "Power domains dictate physical floorplan feasibility, isolation cell requirements, level-shifter placement, and chip area. If you define them after interconnect topology, you will be forced to change your interconnect. Power architecture is the skeleton upon which everything else is built. Define it second only to domain classification."
      },
      {
        heading: "Power domain taxonomy",
        body: "Identify: (1) Always-on domain — holds state during all power modes, contains PMU, RTC, tamper detection. (2) Retention domains — can gate clock but hold register state via retention flops. (3) Switchable domains — full power gating, lose state, must be reloaded on wakeup. (4) Analog supply domains — often separate voltage regulators, noise-sensitive, must be isolated from digital noise."
      },
      {
        heading: "Power sequencing specification",
        body: "For every wakeup and sleep transition, define the exact sequence of domain enable/disable, including timing relationships. An incorrectly specified power sequence causes one of the hardest classes of silicon bugs to debug — intermittent failures that only appear at specific supply ramp rates or temperatures. Document every transition as a timing diagram, not prose."
      }
    ],
    scaleNote: "Scale impact: Simple devices may have 2–3 power domains. Complex SoCs (mobile, HPC) may have 20–30 independently controlled power domains with DVFS (Dynamic Voltage and Frequency Scaling) on multiple domains simultaneously. The complexity of the PMU firmware and hardware handshake protocol scales directly with domain count.",
    influences: ["domain_count", "power_modes", "standby_current_target"]
  },
  {
    id: "s5",
    num: "05",
    title: "Clock Architecture — Domains, Distribution, CDCs",
    tag: "UNIVERSAL",
    color: T.cyan,
    scale: "common",
    summary: "Define all clock sources, domains, frequencies, and all Clock Domain Crossings (CDCs).",
    details: [
      {
        heading: "Clock architecture as a constraint graph",
        body: "Think of clock architecture as a directed graph where nodes are clock domains and edges are clock domain crossings. Every edge is a potential metastability failure if not properly handled. Draw this graph completely before RTL begins. Every CDC must have a named synchronization strategy: 2-FF synchronizer, handshake protocol, async FIFO, or MUX-controlled."
      },
      {
        heading: "Clock source hierarchy",
        body: "Define the source of every clock: external crystal, internal RC oscillator, PLL output, divided PLL output, recovered clock from serial interface. For each PLL: define lock time, frequency range, jitter specification (RMS and peak), power, and startup sequence. The PLL architecture (integer-N vs. fractional-N) is an architecture-level decision, not a circuit-level one."
      },
      {
        heading: "Clock gating strategy",
        body: "Document where clock gating will be applied: at what level of hierarchy (block-level, sub-block, register-file), the enable signal source, and the minimum enable pulse width. Clock gating is your primary dynamic power lever in digital logic — it typically reduces active power by 20–40%. Define the strategy at architecture time so RTL engineers implement it consistently."
      }
    ],
    scaleNote: "Scale impact: Simple microcontrollers may have 1 PLL and 3 clock domains. Complex SoCs have 5–10 PLLs, 50+ clock domains, and hundreds of CDC crossings. The CDC verification burden scales quadratically — each new domain creates potential crossings with all existing domains. This is where CDC verification tools (Meridian, Questa CDC) become mandatory.",
    influences: ["pll_count", "clock_domain_count", "cdc_complexity"]
  },
  {
    id: "s6",
    num: "06",
    title: "Interconnect Topology Selection",
    tag: "SCALE-SENSITIVE",
    color: T.amber,
    scale: "scale",
    summary: "Choose the on-chip communication backbone — the most scale-sensitive architectural decision.",
    details: [
      {
        heading: "Interconnect topology options and their regimes",
        body: "Single shared bus (APB, AHB): correct for ≤8 masters, low bandwidth, simple arbitration. Multi-layer AHB / AXI crossbar: correct for 8–20 masters, moderate bandwidth, parallel transactions. Network-on-Chip (NoC) mesh/ring: correct for >20 masters, high bandwidth, distributed routing, flit-based flow control. Dedicated point-to-point links: correct for chiplets and die-to-die (UCIe, BoW). Choosing below your complexity tier costs performance. Choosing above it wastes area and power."
      },
      {
        heading: "Bandwidth requirement analysis",
        body: "For every interface in your block diagram, calculate peak bandwidth (bytes/second) and average bandwidth. Sum all master bandwidths. If the total exceeds 60% of your bus bandwidth at target frequency, a single shared bus will not meet latency requirements and you need a crossbar or NoC. Use this calculation to justify the topology choice, not intuition."
      },
      {
        heading: "Latency budget allocation",
        body: "Define an end-to-end latency budget for each critical data path: sensor → DSP → memory → output. Allocate portions of the budget to each interconnect segment. For real-time systems, worst-case latency (not average) is the binding constraint. Prioritization, Quality-of-Service (QoS), and traffic shaping are interconnect-level mechanisms that enforce latency budgets under contention."
      }
    ],
    scaleNote: "Scale defines topology: ≤8 masters → AHB bus. 8–20 → AXI crossbar. 20+ → NoC. Chiplets → die-to-die protocol. Each step up in topology complexity adds: routing area overhead, verification complexity, power for the interconnect fabric itself, and firmware complexity for traffic management.",
    influences: ["master_count", "bandwidth_gbps", "latency_budget_ns", "die_count"]
  },
  {
    id: "s7",
    num: "07",
    title: "Memory Architecture — Hierarchy, Sizing, Coherency",
    tag: "SCALE-SENSITIVE",
    color: T.amber,
    scale: "scale",
    summary: "Define the full memory hierarchy from registers to external DRAM, with coherency strategy.",
    details: [
      {
        heading: "Memory hierarchy levels",
        body: "Level 0 — Register files inside compute blocks (cycle-accurate access). Level 1 — Tightly Coupled Memory (TCM), SRAM, no cache misses, deterministic latency — essential for real-time and safety-critical code. Level 2 — Shared on-chip SRAM (L2 cache or scratchpad). Level 3 — External DRAM (DDR4/DDR5/LPDDR5) — high latency, high bandwidth. Level 4 — External NVM (Flash, eMMC, UFS). Define access latency and bandwidth at every level."
      },
      {
        heading: "Cache coherency — the hard architectural question",
        body: "Does your design require hardware cache coherency? Answer: if you have multiple processor cores sharing data, and you want to use standard OS software, you need hardware coherency (ACE, CHI protocol). If you have a single core or explicitly-managed shared memory (DMA copies), you can avoid hardware coherency entirely. Hardware coherency (AMBA CHI, CCI-500) costs 15–25% area overhead on the interconnect and dramatically increases verification complexity. It should only be chosen when the software model genuinely requires it."
      },
      {
        heading: "SRAM sizing methodology",
        body: "Size each on-chip SRAM by the working set of data it must hold for the worst-case use case, not the average. Add 20% margin. Then sanity check against area budget. On advanced nodes, SRAM is 40–60% of chip area for many designs. If SRAM area dominates, consider moving data off-chip or restructuring the algorithm to require less working set. Do not accept an 'optimistic' SRAM size that will be revised after tapeout constraints are felt."
      }
    ],
    scaleNote: "Scale impact: Simple MCU — 64–256KB SRAM, no cache, no DRAM. Complex SoC — multi-MB L2 cache, LPDDR5 controller with PHY, hardware coherency fabric (CCI/CMN). Memory architecture complexity scales with core count and OS requirements. Multi-core + Linux → mandatory coherency. Bare-metal single-core → no coherency needed.",
    influences: ["core_count", "os_requirement", "working_set_size", "bandwidth_gbps"]
  },
  {
    id: "s8",
    num: "08",
    title: "IP Selection, Characterization & Integration Contracts",
    tag: "UNIVERSAL",
    color: T.cyan,
    scale: "common",
    summary: "Select specific IPs for each functional block and formally define every integration boundary.",
    details: [
      {
        heading: "IP selection criteria hierarchy",
        body: "Evaluate IPs in this order: (1) Process compatibility — is this IP validated on your process node? (2) Interface compatibility — does it speak the protocol your interconnect uses? (3) Performance — does it meet your requirement with margin? (4) Power — does it fit in your domain budget? (5) Area — does it fit your floorplan? (6) Delivery — is the IP ready when you need it? (7) Cost — license fee vs. development cost. Never start with cost — it leads to choosing the cheapest IP that technically meets spec but fails on process or interface compatibility."
      },
      {
        heading: "Integration contracts — the architect's primary tool",
        body: "For every IP, write an Integration Contract that specifies: all input and output signals with width, direction, and timing requirements; clock domain assignment and synchronization requirements at all ports; reset strategy (synchronous/asynchronous, active-high/low, sequencing); power domain and supply voltage; boundary conditions and undefined states; what the IP guarantees to its consumers and what it requires from its producers."
      },
      {
        heading: "Hard macro vs. soft IP — the re-use decision",
        body: "Hard macros (GDSII) are pre-characterized at a specific process node — faster, more predictable PPA, less flexibility. Soft IPs (RTL) are portable across nodes but require full synthesis and implementation — more risk, more control. The rule: use hard macros for analog, memory compilers, PHYs, and any IP where analog performance is the differentiator. Use soft IP for digital logic where you need frequency/power flexibility or where you expect future port changes."
      }
    ],
    scaleNote: null,
    influences: []
  },
  {
    id: "s9",
    num: "09",
    title: "Domain Partitioning — Digital / Analog / Mixed-Signal",
    tag: "UNIVERSAL",
    color: T.cyan,
    scale: "common",
    summary: "Physically and electrically separate domains with formal interface specifications between them.",
    details: [
      {
        heading: "Why domain separation is an architectural decision",
        body: "The boundary between digital and analog logic is not just a circuit detail — it determines substrate isolation requirements, power ring layout, guard ring placement, ESD protection topology, noise coupling budget, and package selection. These all have first-order impact on chip area and yield. The digital/analog boundary must be defined at architecture phase, not left to layout engineers."
      },
      {
        heading: "The noise budget allocation",
        body: "The analog supply noise specification (e.g., 'ADC AVDD ripple < 1mV at 100kHz') must be formally allocated at architecture time. Then trace backwards: how much digital switching noise couples through the substrate and package? What LDO rejection ratio is needed? How much decoupling capacitance? These calculations determine whether a single-supply or multi-supply architecture is required — and that is an architecture decision, not a circuit decision."
      },
      {
        heading: "Mixed-signal interface specification",
        body: "Every signal crossing the digital-analog boundary needs: signal type (differential/single-ended), voltage levels and swing, frequency and slew rate, ESD protection level (HBM/CDM), common-mode specification for differential signals, and any calibration or trim requirements. The SAR ADC input, the DAC output, the PLL reference — every one of these crossings is an architectural contract."
      }
    ],
    scaleNote: null,
    influences: []
  },
  {
    id: "s10",
    num: "10",
    title: "Security Architecture — Trust Boundaries & Threat Model",
    tag: "SCALE-SENSITIVE",
    color: T.rose,
    scale: "scale",
    summary: "Define the hardware security boundary, trust zones, and threat model before RTL begins.",
    details: [
      {
        heading: "Security is an architecture-time decision",
        body: "Security cannot be added to silicon after tapeout. The hardware root of trust, secure boot chain, memory isolation, cryptographic key storage, and side-channel attack countermeasures must all be defined at architecture phase. A design that reaches RTL without a threat model will have security vulnerabilities baked into its fundamental topology."
      },
      {
        heading: "TrustZone, RISC-V PMP, and hardware firewalls",
        body: "For any device handling sensitive data, define: (1) the hardware root of trust (PUF or eFuse-based), (2) secure vs. non-secure memory regions and their enforcement mechanism, (3) cryptographic accelerator access control, (4) debug port security (JTAG lockdown, authenticated debug), (5) secure boot chain with chain-of-trust verification."
      },
      {
        heading: "Side-channel attack threat model",
        body: "For devices handling secrets (keys, biometrics, payment credentials), the threat model must include power analysis (SPA/DPA), timing attacks, and EM emissions. Countermeasures (constant-time execution, power noise injection, masking) are determined by the threat model and must be specified before the cryptographic IP is selected — not all crypto IPs include these protections."
      }
    ],
    scaleNote: "Scale and application define security depth: Consumer toy — minimal security. IoT device with cloud keys — secure boot + key storage. Payment terminal — EAL4+ certified security enclave. Automotive ECU with OTA — EVITA HSM. The certification level drives the IP selection and verification cost nonlinearly.",
    influences: ["security_certification", "key_storage", "threat_model_level"]
  },
  {
    id: "s11",
    num: "11",
    title: "DFT Architecture — Testability at Architecture Time",
    tag: "UNIVERSAL",
    color: T.cyan,
    scale: "common",
    summary: "Plan Design for Test (DFT) hooks, scan chains, BIST, and JTAG before RTL to avoid untestable silicon.",
    details: [
      {
        heading: "DFT is not an afterthought",
        body: "The single most expensive mistake in IC design is finding that a block is untestable after RTL is written. Re-architecting for testability at RTL stage requires redesigning the block, re-verifying it, and re-integrating it. DFT architecture must define: test access mechanism (JTAG / TAP), scan chain topology and expected coverage target (>95% fault coverage is typical), memory BIST (MBIST) for all SRAMs, and boundary scan for package-level interconnect testing."
      },
      {
        heading: "Analog test access architecture",
        body: "For mixed-signal IPs, define the test mux architecture that routes analog signals to dedicated test pins. Specify: which internal analog nodes need observability, what test modes the analog blocks must support (DC trim, AC characterization, loopback), and the multiplexer hierarchy. Analog DFT is frequently under-specified at architecture time and leads to expensive ATE time at production test."
      },
      {
        heading: "Scan chain partitioning",
        body: "Divide scan chains based on clock domain — different clock domains cannot share a scan chain. Also consider power domains — scan must be wrappable around power-gated regions. Define the target chain length (typically 500–2000 flops per chain) based on test time budget and DFT compression ratio requirements."
      }
    ],
    scaleNote: "Scale impact: Simple MCU — single JTAG TAP, 2–4 scan chains, basic MBIST. Complex SoC — hierarchical DFT with multiple test compression ratios, die-level and system-level test access, embedded tester (eSelfTest), IEEE 1687 IJTAG for instrument-level access. Test cost is 15–30% of chip manufacturing cost — DFT quality directly impacts production economics.",
    influences: ["scan_chain_count", "memory_count", "test_coverage_target", "ate_test_time_budget"]
  },
  {
    id: "s12",
    num: "12",
    title: "Architecture Verification — Completeness & Consistency Checks",
    tag: "UNIVERSAL",
    color: T.sage,
    scale: "common",
    summary: "Formally verify the architecture is complete, consistent, and achievable before RTL kickoff.",
    details: [
      {
        heading: "Architecture verification checklist",
        body: "Every interface has a defined protocol, width, and timing. Every clock has a defined source and all CDCs are identified and named. Every power domain is bounded, with all isolation cells and level shifters specified. Every requirement traces to at least one block. Every block traces to at least one requirement. No orphan blocks. No orphan requirements. No undefined reset states."
      },
      {
        heading: "Feasibility validation",
        body: "Before signing off, validate feasibility with three numbers: (1) Area feasibility — sum of known hard macro areas vs. target die area at target density. (2) Power feasibility — sum of IP power budgets vs. total power envelope. (3) Timing feasibility — critical paths estimated from IP timing through interconnect vs. target frequency. If any of these are within 10% of budget, the architecture is at high risk and must be revised."
      },
      {
        heading: "The architecture review package",
        body: "Produce a formal Architecture Review Package containing: top-level block diagram, power domain map, clock architecture diagram, interconnect topology with bandwidth analysis, IP selection register, all integration contracts, DFT plan, and an open items list with owner and due date for each item. This package is the contract between architecture and implementation."
      }
    ],
    scaleNote: null,
    influences: []
  }
];

const LOSS_FUNCTIONS = [
  {
    id: "lf1",
    name: "PPA Loss",
    formula: "L_PPA = w_p·(P/P_target) + w_a·(A/A_target) + w_f·(f_target/f_achieved)",
    color: T.cyan,
    icon: "⊕",
    description: "The foundational three-way trade-off. Every architectural decision moves points between power, area, and frequency. The weights (w_p, w_a, w_f) are set by domain: IoT sets w_p very high; HPC sets w_f very high. A good architecture minimizes L_PPA for its domain's weight vector.",
    examples: [
      "Adding pipeline stages reduces area-delay product but increases flop count (area) and power",
      "Choosing LPDDR5 over DDR5 saves power but costs bandwidth — changes w_f and w_p balance",
      "Increasing cache size cuts DRAM access (frequency gain) but increases area and leakage"
    ]
  },
  {
    id: "lf2",
    name: "Interconnect Contention Loss",
    formula: "L_IC = Σ (bandwidth_requested_i / bandwidth_available) × latency_penalty_i",
    color: T.amber,
    icon: "⊗",
    description: "Measures how much performance is lost to bus contention and arbitration delay. A bus that is 80%+ utilized introduces nonlinear latency spikes. A good architecture keeps worst-case utilization below 60% on any shared resource.",
    examples: [
      "Two high-BW DMA masters sharing one AHB bus — one always waits",
      "NoC with hot-spot nodes due to unbalanced traffic — routing bottleneck",
      "Single memory port serving both instruction fetch and data access — stall cycles"
    ]
  },
  {
    id: "lf3",
    name: "Clock Domain Entropy",
    formula: "L_CDC = N_crossings × complexity_per_crossing × verification_cost_factor",
    color: T.rose,
    icon: "⊘",
    description: "CDC crossings are the primary source of silicon bugs that escape simulation. Each crossing costs area (synchronizer flops, async FIFOs), power, and verification effort. A good architecture minimizes unnecessary crossings and groups logic into coherent clock domains.",
    examples: [
      "Placing data path logic in two separate clock domains for no functional reason — doubles CDC burden",
      "Using 10 clock domains when 4 would suffice — O(n²) CDC verification problem",
      "An async FIFO where a sync FIFO with clock enable would suffice — unnecessary complexity"
    ]
  },
  {
    id: "lf4",
    name: "Power Domain Isolation Cost",
    formula: "L_PD = N_domains × (iso_cell_area + level_shifter_area + sequencing_logic) + verification_cost",
    color: T.indigo,
    icon: "⊙",
    description: "Every power domain boundary costs area for isolation cells, level shifters, and retention cells. It also costs verification effort for power-aware simulation. An architecture with more domains than functionally necessary wastes area and creates complex power sequencing bugs.",
    examples: [
      "Splitting one logical block across two power domains to save 5% power — costs 8% area in isolation cells",
      "A domain that is never actually power-gated in the real product — pure overhead",
      "Missing isolation cell on a signal — output floats to unpredictable voltage during power-down"
    ]
  },
  {
    id: "lf5",
    name: "Integration Complexity Loss",
    formula: "L_INT = Σ_ip [protocol_mismatch_count × adapter_cost + timing_margin_violation_risk]",
    color: T.sage,
    icon: "⊛",
    description: "Protocol adapters, width converters, clock bridge FIFOs, and level shifters inserted to make incompatible IPs work together are all symptoms of integration complexity loss. Each adapter is a potential point of failure and a source of timing closure difficulty.",
    examples: [
      "APB IP connected to AHB bus — needs AHB-to-APB bridge (area, latency, power overhead)",
      "32-bit wide IP feeding 64-bit bus — needs packing logic and changes burst behavior",
      "AXI IP with 64-bit data width connected to 128-bit crossbar — bandwidth halved at boundary"
    ]
  },
  {
    id: "lf6",
    name: "Verification Completeness Loss",
    formula: "L_VER = (1 - coverage_achieved) × P_escape × cost_of_silicon_bug",
    color: T.sand,
    icon: "◈",
    description: "An architecture that is difficult to verify — too many states, too many CDCs, too many undefined corner cases — increases the probability that a bug escapes to silicon. Silicon bug cost is 100–1000× RTL bug cost. Good architectures are designed for verifiability, not just functionality.",
    examples: [
      "Shared mutable state between two independent subsystems — exponential state space",
      "An async handshake protocol without formal coverage model — unverifiable in simulation alone",
      "Power-on reset sequence with 12 interdependent signals — combinatorial explosion of valid orders"
    ]
  },
  {
    id: "lf7",
    name: "Reuse & Portability Loss",
    formula: "L_REUSE = (1 - reuse_fraction) × NRE_cost + (1 - portability_score) × future_redesign_cost",
    color: T.rose,
    icon: "◉",
    description: "An architecture that cannot reuse existing validated IPs, or that cannot be ported to a future process node, forces complete redesign in the next generation. Good architectures maximize validated IP reuse and isolate process-dependent blocks (analog, memory, PHY) from process-independent blocks (digital logic).",
    examples: [
      "Choosing a hard macro PLL from 40nm — entire analog subsystem must be redesigned for 28nm",
      "Bus protocol tightly coupled to a specific interconnect IP — switching vendors requires RTL changes",
      "SRAM compiler interface exposed in RTL — not portable to different foundry without RTL edit"
    ]
  }
];

const RESOURCES = [
  {
    category: "Foundational Textbooks",
    color: T.cyan,
    icon: "◈",
    items: [
      {
        title: "CMOS VLSI Design: A Circuits and Systems Perspective",
        author: "Weste & Harris",
        url: "https://www.amazon.com/CMOS-VLSI-Design-Circuits-Perspective/dp/0321547748",
        note: "The definitive reference for digital IC design — covers logic design through physical implementation. Read Chapters 1–4 for architecture fundamentals."
      },
      {
        title: "Digital Integrated Circuits — A Design Perspective",
        author: "Rabaey, Chandrakasan, Nikolic",
        url: "https://www.pearson.com/en-us/subject-catalog/p/digital-integrated-circuits/P200000003482",
        note: "Deep dive into circuit-level understanding that every architect must have — covers power, delay, and interconnect at the physics level."
      },
      {
        title: "System-on-Chip Design with Arm Cortex-M Processors",
        author: "ARM / Joseph Yiu",
        url: "https://www.arm.com/resources/book/system-on-chip-design",
        note: "Practical SoC architecture guide from ARM — covers bus systems, memory maps, interrupt architecture, debug infrastructure."
      },
      {
        title: "The Art of Hardware Architecture",
        author: "Miloš Milovanović",
        url: "https://link.springer.com/book/10.1007/978-1-4614-0397-2",
        note: "Bridges the gap between algorithm requirements and hardware implementation — excellent on design trade-offs."
      }
    ]
  },
  {
    category: "ARM / AMBA Architecture Specifications (Free)",
    color: T.amber,
    icon: "⬡",
    items: [
      {
        title: "AMBA AXI Protocol Specification",
        author: "ARM",
        url: "https://developer.arm.com/documentation/ihi0022/latest",
        note: "Free. The most-used on-chip interconnect protocol in commercial SoCs. Master this thoroughly — it is the language of SoC integration."
      },
      {
        title: "AMBA APB Protocol Specification",
        author: "ARM",
        url: "https://developer.arm.com/documentation/ihi0024/latest",
        note: "Free. Simple peripheral bus — every SoC has APB peripherals. Essential for understanding bus hierarchies."
      },
      {
        title: "AMBA CHI Architecture Specification",
        author: "ARM",
        url: "https://developer.arm.com/documentation/ihi0050/latest",
        note: "Free. Cache coherent interconnect for multi-core systems — critical for understanding coherency architecture."
      },
      {
        title: "CoreLink CMN-700 Technical Reference",
        author: "ARM",
        url: "https://developer.arm.com/documentation/101754/latest",
        note: "Free. Real-world mesh NoC implementation — see how ARM architects a production coherent interconnect."
      }
    ]
  },
  {
    category: "Online Courses & Video Learning",
    color: T.indigo,
    icon: "⬢",
    items: [
      {
        title: "MIT 6.004 Computation Structures",
        author: "MIT OpenCourseWare",
        url: "https://ocw.mit.edu/courses/6-004-computation-structures-spring-2017/",
        note: "Free. Builds understanding of digital systems from logic gates to processor architecture. Essential conceptual foundation."
      },
      {
        title: "VLSI CAD: Logic to Layout",
        author: "University of Illinois / Coursera",
        url: "https://www.coursera.org/learn/vlsi-cad-logic",
        note: "Covers the full RTL-to-GDSII flow — critical for understanding how architecture decisions impact implementation."
      },
      {
        title: "Hardware Security: Cryptographic Design",
        author: "University of Maryland / Coursera",
        url: "https://www.coursera.org/learn/hardware-security",
        note: "Security architecture in hardware — trust zones, side-channel attacks, cryptographic IP integration."
      },
      {
        title: "Computer Architecture — ETH Zurich (Onur Mutlu)",
        author: "ETH Zurich / YouTube",
        url: "https://www.youtube.com/c/OnurMutluLectures",
        note: "Free. World-class computer architecture lectures — covers memory hierarchy, coherency, and modern processor architecture in depth."
      }
    ]
  },
  {
    category: "Free EDA Tools & Simulators (Hands-On)",
    color: T.sage,
    icon: "◉",
    items: [
      {
        title: "Icarus Verilog + GTKWave",
        author: "Open Source",
        url: "https://bleyer.org/icarus/",
        note: "Free. RTL simulation and waveform viewing. Write Verilog, simulate bus interfaces, observe CDC behavior — essential hands-on tool."
      },
      {
        title: "OpenROAD — Open-Source RTL-to-GDS Flow",
        author: "OpenROAD Project",
        url: "https://openroad.readthedocs.io/en/latest/",
        note: "Free. Complete open-source physical implementation flow — synthesize RTL, place and route, generate GDSII. See how architecture affects timing closure."
      },
      {
        title: "Skywater 130nm PDK + OpenLane",
        author: "Google / SkyWater Technology",
        url: "https://github.com/google/skywater-pdk",
        note: "Free. Real open-source process design kit. Design actual silicon layouts. Pairs with OpenLane for full chip implementation."
      },
      {
        title: "ChipIgnite / Efabless — Tapeout Platform",
        author: "Efabless",
        url: "https://efabless.com/chipignite",
        note: "Low-cost real chip fabrication on SKY130. Design, submit, and receive fabricated silicon. The ultimate architecture validation."
      },
      {
        title: "Verilator",
        author: "Open Source",
        url: "https://www.veripool.org/verilator/",
        note: "Free. High-speed RTL-to-C++ compiler for fast simulation. Excellent for verifying system-level architectural behavior at speed."
      },
      {
        title: "RISC-V Formal Verification Framework",
        author: "RISC-V Foundation / Symbiotic EDA",
        url: "https://github.com/SymbioticEDA/riscv-formal",
        note: "Free. Formal verification of RISC-V processor implementations — learn how formal methods apply to architecture verification."
      }
    ]
  },
  {
    category: "Interactive Playgrounds & Design Exercises",
    color: T.rose,
    icon: "⟁",
    items: [
      {
        title: "EDA Playground",
        author: "Doulos",
        url: "https://www.edaplayground.com/",
        note: "Free browser-based RTL simulation. Run Verilog/VHDL/SystemVerilog instantly. Ideal for experimenting with bus interfaces, CDC synchronizers, arbiters."
      },
      {
        title: "Makerchip — TL-Verilog Playground",
        author: "Redwood EDA",
        url: "https://makerchip.com/",
        note: "Free. Browser-based IDE for TL-Verilog. Has pre-built RISC-V CPU starter templates — experiment with pipeline architecture, memory hierarchy, and NoC concepts interactively."
      },
      {
        title: "OpenHW Group CVA6 RISC-V",
        author: "OpenHW Group",
        url: "https://github.com/openhwgroup/cva6",
        note: "Free. Full 6-stage RISC-V processor with cache, MMU, and debug — study real production-quality architecture. Excellent reference for pipeline and memory subsystem design."
      },
      {
        title: "Caravel Harness — Pre-built SoC Template",
        author: "Efabless",
        url: "https://github.com/efabless/caravel",
        note: "Free. Pre-designed SoC harness with RISC-V core, wishbone bus, GPIOs, and user project area. Add your own logic and submit for fabrication — architecture through silicon."
      },
      {
        title: "nMigen / Amaranth HDL",
        author: "Open Source",
        url: "https://amaranth-hdl.readthedocs.io/",
        note: "Free. Python-based hardware description language — rapid architecture prototyping. Model bus systems, state machines, and memory hierarchies in Python before committing to RTL."
      }
    ]
  },
  {
    category: "Standards & Reference Documents",
    color: T.sand,
    icon: "◎",
    items: [
      {
        title: "RISC-V ISA Specifications",
        author: "RISC-V International",
        url: "https://riscv.org/technical/specifications/",
        note: "Free. Open processor ISA — study the instruction set architecture spec as a model for how architectural documents should be written."
      },
      {
        title: "IEEE 1500 — Embedded Core Test Standard",
        author: "IEEE",
        url: "https://standards.ieee.org/ieee/1500/1450/",
        note: "DFT architecture for IP cores — defines the standard wrapper that makes IP cores independently testable."
      },
      {
        title: "ISO 26262 Functional Safety — Overview",
        author: "ISO",
        url: "https://www.iso.org/standard/68383.html",
        note: "The automotive functional safety standard. Free overview available — understand ASIL levels and what hardware requirements they impose."
      },
      {
        title: "JEDEC LPDDR5/5X Specification",
        author: "JEDEC",
        url: "https://www.jedec.org/standards-documents/docs/jesd209-5b",
        note: "Free with registration. Memory interface standard — understanding the protocol is essential for mobile SoC memory architecture."
      }
    ]
  }
];

// ─── COMPONENTS ────────────────────────────────────────────────────────────────

const css = `
  @import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=IBM+Plex+Mono:wght@400;500;600&family=DM+Sans:wght@300;400;500;600&display=swap');

  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  html { scroll-behavior: smooth; }

  body {
    background: ${T.bg};
    color: ${T.text};
    font-family: 'DM Sans', sans-serif;
    font-size: 15px;
    line-height: 1.7;
    min-height: 100vh;
  }

  ::-webkit-scrollbar { width: 5px; }
  ::-webkit-scrollbar-track { background: ${T.ink}; }
  ::-webkit-scrollbar-thumb { background: ${T.borderHi}; border-radius: 2px; }

  .serif { font-family: 'DM Serif Display', serif; }
  .mono  { font-family: 'IBM Plex Mono', monospace; }

  .label {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 10px;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: ${T.muted};
  }

  @keyframes fadeUp {
    from { opacity: 0; transform: translateY(20px); }
    to   { opacity: 1; transform: translateY(0); }
  }
  @keyframes glow {
    0%, 100% { opacity: 0.5; }
    50% { opacity: 1; }
  }
  @keyframes spin {
    to { transform: rotate(360deg); }
  }

  .fade-up { animation: fadeUp 0.5s ease both; }

  .nav-pill {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 11px;
    letter-spacing: 0.08em;
    padding: 7px 16px;
    border-radius: 2px;
    border: 1px solid ${T.border};
    background: transparent;
    color: ${T.muted};
    cursor: pointer;
    transition: all 0.2s;
    text-transform: uppercase;
  }
  .nav-pill:hover { border-color: ${T.borderHi}; color: ${T.text}; }
  .nav-pill.active { border-color: currentColor; color: ${T.cyan}; background: rgba(0,229,255,0.05); }

  .step-card {
    border: 1px solid ${T.border};
    border-radius: 3px;
    padding: 22px 24px;
    cursor: pointer;
    transition: all 0.25s;
    position: relative;
    overflow: hidden;
  }
  .step-card:hover { border-color: ${T.borderHi}; background: ${T.ink}; }
  .step-card.active { background: ${T.card}; }

  .detail-panel {
    border: 1px solid ${T.border};
    border-radius: 3px;
    background: ${T.card};
    padding: 32px;
  }

  .lf-card {
    border: 1px solid ${T.border};
    border-radius: 3px;
    padding: 24px;
    transition: border-color 0.2s;
    cursor: pointer;
  }
  .lf-card:hover { border-color: ${T.borderHi}; }
  .lf-card.active { background: ${T.card}; }

  .res-item {
    padding: 14px 0;
    border-bottom: 1px solid ${T.border};
    display: flex;
    gap: 16px;
    align-items: flex-start;
  }
  .res-item:last-child { border-bottom: none; }

  .link-btn {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 10px;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: inherit;
    border: 1px solid currentColor;
    border-radius: 2px;
    padding: 4px 10px;
    text-decoration: none;
    opacity: 0.7;
    transition: opacity 0.2s;
  }
  .link-btn:hover { opacity: 1; }

  .tag-badge {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 9px;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    padding: 3px 8px;
    border-radius: 2px;
    display: inline-block;
  }

  .formula-box {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 12px;
    padding: 14px 18px;
    border-radius: 3px;
    line-height: 1.5;
    letter-spacing: 0.02em;
    overflow-x: auto;
    white-space: nowrap;
  }

  .section-divider {
    height: 1px;
    background: linear-gradient(90deg, transparent, ${T.borderHi}, transparent);
    margin: 48px 0;
  }

  .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
  @media (max-width: 860px) {
    .grid-2 { grid-template-columns: 1fr; }
  }
`;

function ScaleBadge({ scale }) {
  if (scale === "common") return (
    <span className="tag-badge" style={{ background: "rgba(0,229,255,0.1)", color: T.cyan, border: `1px solid rgba(0,229,255,0.2)` }}>
      ● Universal
    </span>
  );
  if (scale === "scale") return (
    <span className="tag-badge" style={{ background: "rgba(255,179,0,0.1)", color: T.amber, border: `1px solid rgba(255,179,0,0.2)` }}>
      ◆ Scale-Sensitive
    </span>
  );
  return null;
}

function StepsTab() {
  const [active, setActive] = useState(0);
  const step = STEPS[active];

  return (
    <div style={{ display: "grid", gridTemplateColumns: "300px 1fr", gap: 20, alignItems: "start" }}>
      {/* Step list */}
      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
        <div className="label" style={{ marginBottom: 10, paddingLeft: 4 }}>12 Architecture Steps</div>
        {STEPS.map((s, i) => (
          <div
            key={s.id}
            className={`step-card ${active === i ? "active" : ""}`}
            onClick={() => setActive(i)}
            style={{ borderLeftColor: active === i ? s.color : T.border, borderLeftWidth: active === i ? 3 : 1 }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <span className="mono" style={{ fontSize: 11, color: T.muted, minWidth: 22 }}>{s.num}</span>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 12, fontWeight: 500, color: active === i ? T.text : T.muted, lineHeight: 1.4 }}>
                  {s.title}
                </div>
                <div style={{ marginTop: 4 }}>
                  <ScaleBadge scale={s.scale} />
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Step detail */}
      <div key={active} className="detail-panel fade-up">
        <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", flexWrap: "wrap", gap: 12, marginBottom: 24 }}>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 8 }}>
              <span className="mono" style={{ fontSize: 13, color: T.muted }}>STEP {step.num}</span>
              <ScaleBadge scale={step.scale} />
            </div>
            <h2 className="serif" style={{ fontSize: 26, color: step.color, lineHeight: 1.2 }}>
              {step.title}
            </h2>
          </div>
        </div>

        <p style={{ color: T.muted, fontSize: 14, marginBottom: 28, borderLeft: `2px solid ${step.color}`, paddingLeft: 16 }}>
          {step.summary}
        </p>

        <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
          {step.details.map((d, i) => (
            <div key={i}>
              <div className="label" style={{ color: step.color, marginBottom: 8 }}>{d.heading}</div>
              <p style={{ fontSize: 14, lineHeight: 1.75, color: T.text }}>{d.body}</p>
            </div>
          ))}
        </div>

        {step.scaleNote && (
          <div style={{
            marginTop: 28,
            padding: "16px 20px",
            borderRadius: 3,
            background: "rgba(255,179,0,0.06)",
            border: `1px solid rgba(255,179,0,0.2)`,
          }}>
            <div className="label" style={{ color: T.amber, marginBottom: 8 }}>◆ Scale & Complexity Influence</div>
            <p style={{ fontSize: 13, color: T.text, lineHeight: 1.7 }}>{step.scaleNote}</p>
          </div>
        )}

        {/* Navigation */}
        <div style={{ display: "flex", justifyContent: "space-between", marginTop: 36, paddingTop: 20, borderTop: `1px solid ${T.border}` }}>
          <button
            onClick={() => setActive(Math.max(0, active - 1))}
            disabled={active === 0}
            style={{
              fontFamily: "'IBM Plex Mono', monospace", fontSize: 11, letterSpacing: "0.08em",
              textTransform: "uppercase", padding: "8px 18px", borderRadius: 2,
              border: `1px solid ${T.border}`, background: "transparent",
              color: active === 0 ? T.dim : T.muted, cursor: active === 0 ? "not-allowed" : "pointer",
            }}
          >← Prev Step</button>
          <span className="mono" style={{ fontSize: 11, color: T.muted, alignSelf: "center" }}>
            {active + 1} / {STEPS.length}
          </span>
          <button
            onClick={() => setActive(Math.min(STEPS.length - 1, active + 1))}
            disabled={active === STEPS.length - 1}
            style={{
              fontFamily: "'IBM Plex Mono', monospace", fontSize: 11, letterSpacing: "0.08em",
              textTransform: "uppercase", padding: "8px 18px", borderRadius: 2,
              border: `1px solid ${active === STEPS.length - 1 ? T.border : step.color}`,
              background: "transparent",
              color: active === STEPS.length - 1 ? T.dim : step.color,
              cursor: active === STEPS.length - 1 ? "not-allowed" : "pointer",
            }}
          >Next Step →</button>
        </div>
      </div>
    </div>
  );
}

function LossTab() {
  const [active, setActive] = useState(0);
  const lf = LOSS_FUNCTIONS[active];

  return (
    <div>
      {/* Header explanation */}
      <div style={{
        padding: "24px 28px",
        borderRadius: 3,
        border: `1px solid ${T.border}`,
        background: T.card,
        marginBottom: 28,
      }}>
        <div className="label" style={{ marginBottom: 10 }}>Architecture Optimization Framework</div>
        <p className="serif" style={{ fontSize: 20, color: T.text, lineHeight: 1.5, marginBottom: 14 }}>
          When two architectures both satisfy the spec, how do you choose the better one?
        </p>
        <p style={{ fontSize: 14, color: T.muted, lineHeight: 1.7 }}>
          The answer is loss functions — mathematical expressions of what each architecture sacrifices.
          The best architecture is the one that minimizes total weighted loss for your specific application domain.
          These are not abstract metrics — each one corresponds to real silicon cost: area, power, yield, re-spin risk, or verification time.
          The weights applied to each loss function are determined by your domain classification from Step 01.
        </p>
      </div>

      {/* Domain weight table */}
      <div style={{ marginBottom: 28, overflowX: "auto" }}>
        <div className="label" style={{ marginBottom: 12 }}>Domain Weight Vectors — How Each Domain Prioritizes the Loss Functions</div>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12, fontFamily: "'IBM Plex Mono', monospace" }}>
          <thead>
            <tr style={{ borderBottom: `1px solid ${T.borderHi}` }}>
              {["Domain", "PPA", "Interconnect", "CDC", "Power Domains", "Integration", "Verification", "Reuse"].map(h => (
                <th key={h} style={{ padding: "8px 12px", textAlign: "left", color: T.muted, fontWeight: 500, letterSpacing: "0.06em", fontSize: 10 }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {[
              ["IoT/Wearable",    "Power↑↑↑", "Low",   "Medium", "High",   "Medium", "Medium", "High"],
              ["Automotive",      "Reliability↑↑↑", "Medium","High","High","High","High↑↑","High"],
              ["HPC/Datacenter",  "Perf↑↑↑", "High↑↑","High","Medium","High","High","Medium"],
              ["Mobile SoC",      "Balanced", "High",  "High",   "High↑↑","High","High","High"],
              ["Industrial RT",   "Latency↑", "Low",   "High↑↑","Medium","Medium","High","Medium"],
              ["Medical",         "Analog↑↑↑","Low",   "Medium", "Medium","High","High↑↑↑","High"],
            ].map((row, i) => (
              <tr key={i} style={{ borderBottom: `1px solid ${T.border}` }}>
                {row.map((cell, j) => (
                  <td key={j} style={{
                    padding: "8px 12px",
                    color: j === 0 ? T.text : cell.includes("↑↑↑") ? T.rose : cell.includes("↑↑") ? T.amber : cell.includes("↑") ? T.cyan : T.muted,
                    fontWeight: cell.includes("↑↑") ? 600 : 400,
                    fontSize: 11,
                  }}>{cell}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Loss function cards */}
      <div className="label" style={{ marginBottom: 12 }}>The Seven Architecture Loss Functions</div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))", gap: 10, marginBottom: 24 }}>
        {LOSS_FUNCTIONS.map((lf_, i) => (
          <div
            key={lf_.id}
            className={`lf-card ${active === i ? "active" : ""}`}
            onClick={() => setActive(i)}
            style={{ borderLeftColor: active === i ? lf_.color : T.border, borderLeftWidth: active === i ? 3 : 1 }}
          >
            <div style={{ fontSize: 18, marginBottom: 6 }}>{lf_.icon}</div>
            <div style={{ fontSize: 13, fontWeight: 600, color: active === i ? lf_.color : T.text, marginBottom: 4 }}>{lf_.name}</div>
          </div>
        ))}
      </div>

      {/* Selected loss function detail */}
      <div key={active} className="detail-panel fade-up">
        <div style={{ display: "flex", alignItems: "center", gap: 14, marginBottom: 20 }}>
          <span style={{ fontSize: 28, color: lf.color }}>{lf.icon}</span>
          <h3 className="serif" style={{ fontSize: 24, color: lf.color }}>{lf.name}</h3>
        </div>

        <div className="formula-box" style={{ background: T.ink, color: lf.color, marginBottom: 20 }}>
          {lf.formula}
        </div>

        <p style={{ fontSize: 14, color: T.text, lineHeight: 1.75, marginBottom: 24 }}>{lf.description}</p>

        <div className="label" style={{ marginBottom: 12 }}>Real Architecture Examples of This Loss</div>
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {lf.examples.map((ex, i) => (
            <div key={i} style={{
              padding: "12px 16px",
              borderRadius: 3,
              border: `1px solid ${T.border}`,
              background: T.ink,
              display: "flex",
              gap: 12,
              alignItems: "flex-start",
            }}>
              <span style={{ color: lf.color, fontSize: 16, flexShrink: 0, marginTop: 1 }}>▸</span>
              <span style={{ fontSize: 13, color: T.muted, lineHeight: 1.6 }}>{ex}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Total loss synthesis */}
      <div style={{ marginTop: 24, padding: "20px 24px", borderRadius: 3, border: `1px solid ${T.borderHi}`, background: T.card }}>
        <div className="label" style={{ marginBottom: 10 }}>Total Architecture Loss — The Optimization Target</div>
        <div className="formula-box" style={{ background: T.ink, color: T.text, fontSize: 11 }}>
          L_total = w1·L_PPA + w2·L_IC + w3·L_CDC + w4·L_PD + w5·L_INT + w6·L_VER + w7·L_REUSE
        </div>
        <p style={{ fontSize: 13, color: T.muted, marginTop: 14, lineHeight: 1.7 }}>
          The optimal architecture is the one that minimizes L_total for your domain's weight vector.
          When two architectures both pass spec verification, compute their individual loss function values,
          apply your domain weights, and sum them. The lower total loss architecture is the better choice —
          even if neither obviously dominates the other on any single dimension.
          This framework transforms a subjective design review argument into an objective, measurable decision.
        </p>
      </div>
    </div>
  );
}

function ResourcesTab() {
  const [activeCategory, setActiveCategory] = useState(0);
  const cat = RESOURCES[activeCategory];

  return (
    <div>
      <div style={{ marginBottom: 24, padding: "20px 24px", borderRadius: 3, border: `1px solid ${T.border}`, background: T.card }}>
        <p style={{ fontSize: 14, color: T.muted, lineHeight: 1.7 }}>
          Curated references for every stage of IC architecture learning — from conceptual foundations through hands-on silicon.
          Items marked as <strong style={{ color: T.sage }}>Free</strong> are openly accessible.
          Playgrounds and simulators are highlighted — these are where real learning happens, not just reading.
        </p>
      </div>

      {/* Category tabs */}
      <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginBottom: 24 }}>
        {RESOURCES.map((r, i) => (
          <button
            key={i}
            onClick={() => setActiveCategory(i)}
            style={{
              fontFamily: "'IBM Plex Mono', monospace",
              fontSize: 10,
              letterSpacing: "0.08em",
              textTransform: "uppercase",
              padding: "7px 14px",
              borderRadius: 2,
              border: `1px solid ${activeCategory === i ? r.color : T.border}`,
              background: activeCategory === i ? `${r.color}10` : "transparent",
              color: activeCategory === i ? r.color : T.muted,
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              gap: 6,
              transition: "all 0.2s",
            }}
          >
            <span>{r.icon}</span>
            {r.category}
          </button>
        ))}
      </div>

      {/* Items */}
      <div key={activeCategory} className="detail-panel fade-up">
        <div className="label" style={{ color: cat.color, marginBottom: 20 }}>{cat.category}</div>
        {cat.items.map((item, i) => (
          <div key={i} className="res-item">
            <div style={{
              width: 28, height: 28, borderRadius: "50%",
              border: `1px solid ${cat.color}40`,
              display: "flex", alignItems: "center", justifyContent: "center",
              flexShrink: 0, color: cat.color, fontSize: 12, fontFamily: "'IBM Plex Mono', monospace",
              fontWeight: 600,
            }}>
              {String(i + 1).padStart(2, "0")}
            </div>
            <div style={{ flex: 1 }}>
              <div style={{ display: "flex", alignItems: "flex-start", gap: 12, flexWrap: "wrap", marginBottom: 6 }}>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 14, fontWeight: 600, color: T.text, marginBottom: 2 }}>{item.title}</div>
                  <div className="mono" style={{ fontSize: 10, color: T.muted }}>{item.author}</div>
                </div>
                <a href={item.url} target="_blank" rel="noopener noreferrer" className="link-btn" style={{ color: cat.color, flexShrink: 0 }}>
                  Open ↗
                </a>
              </div>
              <p style={{ fontSize: 13, color: T.muted, lineHeight: 1.6 }}>{item.note}</p>
            </div>
          </div>
        ))}
      </div>

      {/* Learning path suggestion */}
      <div style={{ marginTop: 24, padding: "20px 24px", borderRadius: 3, border: `1px solid ${T.border}`, background: T.card }}>
        <div className="label" style={{ marginBottom: 12, color: T.sage }}>◉ Recommended Learning Path — Architecture to Silicon</div>
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {[
            ["Week 1–2",   "MIT 6.004 + Weste & Harris Ch.1–4",        "Build foundational understanding of digital systems"],
            ["Week 3–4",   "ARM AMBA AXI Spec + EDA Playground",        "Master the most common on-chip bus protocol hands-on"],
            ["Week 5–6",   "OpenROAD + SKY130 PDK setup",               "Run RTL through physical implementation, see PPA impact"],
            ["Week 7–8",   "Makerchip RISC-V template + CVA6 study",    "Study a real production architecture, modify it, simulate"],
            ["Week 9–12",  "Caravel harness, design a block, submit",   "Design a real functional block for chip fabrication"],
            ["Ongoing",    "IEEE papers, ISSCC, Hot Chips conference",   "Stay current with production architecture innovations"],
          ].map(([period, resource, goal], i) => (
            <div key={i} style={{ display: "flex", gap: 16, alignItems: "flex-start", padding: "10px 0", borderBottom: i < 5 ? `1px solid ${T.border}` : "none" }}>
              <span className="mono" style={{ fontSize: 11, color: T.sage, minWidth: 90, flexShrink: 0 }}>{period}</span>
              <div>
                <div style={{ fontSize: 13, fontWeight: 500, color: T.text, marginBottom: 2 }}>{resource}</div>
                <div style={{ fontSize: 12, color: T.muted }}>{goal}</div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function CriteriaTab() {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      {/* Good vs Bad architecture */}
      <div className="grid-2">
        {/* Good */}
        <div style={{ padding: "24px", borderRadius: 3, border: `1px solid rgba(74,222,128,0.3)`, background: "rgba(74,222,128,0.04)" }}>
          <div className="label" style={{ color: T.sage, marginBottom: 16 }}>◉ Characteristics of a Good Architecture</div>
          {[
            ["Minimal necessary complexity", "Every block, domain, and interface exists because a requirement mandates it. Nothing extra."],
            ["Verifiable by construction", "Every interface is formally specified. Every CDC is named and has a verified synchronization strategy."],
            ["Monotonic PPA improvement", "Adding a feature improves one PPA dimension without disproportionately degrading others."],
            ["Clear intent propagation", "Every IP engineer can state in one sentence why their block exists and what it feeds."],
            ["Graceful degradation", "If one subsystem fails, the architecture defines how the rest of the system behaves."],
            ["Process portability", "Process-specific IP (analog, memory, PHY) is isolated behind stable digital interfaces."],
            ["Maximum IP reuse", "≥70% of IP area comes from previously validated blocks. New development is minimal and isolated."],
            ["Deterministic worst-case behavior", "Latency, power, and timing are bounded — not just described by average-case analysis."],
          ].map(([title, desc], i) => (
            <div key={i} style={{ marginBottom: 14 }}>
              <div style={{ display: "flex", gap: 8, alignItems: "flex-start" }}>
                <span style={{ color: T.sage, flexShrink: 0, marginTop: 2 }}>✓</span>
                <div>
                  <div style={{ fontSize: 13, fontWeight: 600, color: T.text, marginBottom: 2 }}>{title}</div>
                  <div style={{ fontSize: 12, color: T.muted, lineHeight: 1.6 }}>{desc}</div>
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Bad */}
        <div style={{ padding: "24px", borderRadius: 3, border: `1px solid rgba(255,77,109,0.3)`, background: "rgba(255,77,109,0.04)" }}>
          <div className="label" style={{ color: T.rose, marginBottom: 16 }}>✕ Characteristics of a Poor Architecture</div>
          {[
            ["Premature IP binding", "Specific IP chosen before functional decomposition is complete. Topology built around one IP's constraints."],
            ["Undocumented CDCs", "Clock crossings exist in RTL that were not planned at architecture stage — guaranteed metastability risk."],
            ["Orphan requirements", "Requirements exist that no block implements. Or blocks exist that no requirement justifies."],
            ["Shared mutable state", "Multiple independent subsystems write to the same register or memory without a defined arbitration protocol."],
            ["Topology overkill", "NoC chosen for a 6-master system. Hardware coherency added when a single-core bare-metal design would suffice."],
            ["Power domain proliferation", "More power domains than the power saving analysis justifies — all overhead, no benefit."],
            ["Average-case sizing", "Memory, bandwidth, and timing margins computed for average case, not worst case."],
            ["Undefined reset states", "No documentation of what every signal and register holds immediately after reset in every domain."],
          ].map(([title, desc], i) => (
            <div key={i} style={{ marginBottom: 14 }}>
              <div style={{ display: "flex", gap: 8, alignItems: "flex-start" }}>
                <span style={{ color: T.rose, flexShrink: 0, marginTop: 2 }}>✕</span>
                <div>
                  <div style={{ fontSize: 13, fontWeight: 600, color: T.text, marginBottom: 2 }}>{title}</div>
                  <div style={{ fontSize: 12, color: T.muted, lineHeight: 1.6 }}>{desc}</div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Critical evaluation criteria matrix */}
      <div style={{ padding: "24px", borderRadius: 3, border: `1px solid ${T.border}`, background: T.card }}>
        <div className="label" style={{ marginBottom: 16 }}>Architecture Evaluation Criteria Matrix</div>
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
            <thead>
              <tr style={{ borderBottom: `1px solid ${T.borderHi}` }}>
                {["Criterion", "Question to Ask", "Good Signal", "Bad Signal", "Weight by Domain"].map(h => (
                  <th key={h} style={{ padding: "8px 12px", textAlign: "left", fontFamily: "'IBM Plex Mono', monospace", fontSize: 10, color: T.muted, letterSpacing: "0.06em", fontWeight: 500 }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {[
                ["Requirement Coverage", "Does every REQ-ID map to exactly one owner block?", "1:1 mapping, no gaps", "Orphan REQs or blocks", "Universal — all domains"],
                ["Interface Completeness", "Is every signal at every IP boundary formally specified?", "All ports contracted", "Undocumented ports exist", "Universal — all domains"],
                ["CDC Safety", "Is every clock domain crossing named and synchronized?", "All CDCs in CDC plan", "RTL-discovered CDCs", "High: Automotive, Medical"],
                ["Power Budget Margin", "Is worst-case power ≤80% of target at max temperature?", ">20% margin", "<5% margin", "Critical: IoT, Wearable"],
                ["Interconnect Utilization", "Is worst-case bus utilization <60%?", "<60% utilized", ">80% → latency spikes", "High: HPC, Mobile"],
                ["IP Reuse Fraction", "What % of area is proven silicon?", ">70% reused IP", "<40% reused", "High: Cost-sensitive"],
                ["Floorplan Feasibility", "Can all hard macros fit in target die at target density?", "Confirmed by sanity calc", "No area analysis done", "Universal — all domains"],
                ["Verification Closure Path", "Can 95% functional coverage be achieved in simulation budget?", "Coverage model exists", "No coverage plan", "Critical: Automotive, Medical"],
              ].map((row, i) => (
                <tr key={i} style={{ borderBottom: `1px solid ${T.border}` }}>
                  <td style={{ padding: "10px 12px", fontWeight: 600, color: T.text, fontSize: 13 }}>{row[0]}</td>
                  <td style={{ padding: "10px 12px", color: T.muted, fontSize: 12, lineHeight: 1.5 }}>{row[1]}</td>
                  <td style={{ padding: "10px 12px", color: T.sage, fontSize: 12 }}>{row[2]}</td>
                  <td style={{ padding: "10px 12px", color: T.rose, fontSize: 12 }}>{row[3]}</td>
                  <td style={{ padding: "10px 12px", color: T.cyan, fontSize: 11, fontFamily: "'IBM Plex Mono', monospace" }}>{row[4]}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* The three questions */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 14 }}>
        {[
          {
            q: "Is it correct?",
            c: T.cyan,
            body: "Does the architecture implement every SHALL requirement with no gaps and no extra logic? Correctness is binary — the architecture either covers the spec or it doesn't. No partial credit."
          },
          {
            q: "Is it minimal?",
            c: T.amber,
            body: "Can any block, domain, interface, or clock be removed without violating a requirement? If yes, the architecture is over-designed. Complexity beyond what requirements demand is a liability."
          },
          {
            q: "Is it robust?",
            c: T.rose,
            body: "What happens when an IP delivers 10% less performance, a clock locks 20ms late, or a power domain fails to sequence? A robust architecture specifies its degraded behavior before tapeout."
          },
        ].map(({ q, c, body }) => (
          <div key={q} style={{ padding: "20px", borderRadius: 3, border: `1px solid ${c}30`, background: `${c}05` }}>
            <div className="serif" style={{ fontSize: 18, color: c, marginBottom: 12 }}>{q}</div>
            <p style={{ fontSize: 13, color: T.muted, lineHeight: 1.7 }}>{body}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── ROOT APP ─────────────────────────────────────────────────────────────────
export default function App() {
  const [tab, setTab] = useState("steps");

  const tabs = [
    { id: "steps",    label: "12-Step Guide" },
    { id: "loss",     label: "Loss Functions" },
    { id: "criteria", label: "Good vs Bad" },
    { id: "resources",label: "References & Playgrounds" },
  ];

  return (
    <>
      <style>{css}</style>
      <div style={{ minHeight: "100vh" }}>

        {/* Header */}
        <div style={{
          borderBottom: `1px solid ${T.border}`,
          position: "sticky", top: 0, zIndex: 100,
          background: `${T.bg}f0`,
          backdropFilter: "blur(16px)",
        }}>
          <div style={{ maxWidth: 1280, margin: "0 auto", padding: "0 32px" }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", height: 64, flexWrap: "wrap", gap: 12 }}>
              <div style={{ display: "flex", alignItems: "baseline", gap: 16 }}>
                <h1 className="serif" style={{ fontSize: 20, color: T.text, letterSpacing: "-0.01em" }}>
                  IC Architecture <span style={{ color: T.cyan }}>Mastery</span>
                </h1>
                <span className="mono" style={{ fontSize: 10, color: T.muted }}>System Design Reference</span>
              </div>
              <nav style={{ display: "flex", gap: 6 }}>
                {tabs.map(t => (
                  <button
                    key={t.id}
                    className={`nav-pill ${tab === t.id ? "active" : ""}`}
                    onClick={() => setTab(t.id)}
                  >
                    {t.label}
                  </button>
                ))}
              </nav>
            </div>
          </div>
        </div>

        {/* Page header */}
        <div style={{
          borderBottom: `1px solid ${T.border}`,
          background: T.ink,
          padding: "40px 32px 36px",
        }}>
          <div style={{ maxWidth: 1280, margin: "0 auto" }}>
            {{
              steps: (
                <>
                  <div className="label" style={{ marginBottom: 12 }}>12-Step Architecture Development Guide</div>
                  <h2 className="serif" style={{ fontSize: 36, color: T.text, lineHeight: 1.2, marginBottom: 14 }}>
                    From Specification to<br /><span style={{ color: T.cyan }}>Frozen Architecture Baseline</span>
                  </h2>
                  <p style={{ color: T.muted, maxWidth: 680, fontSize: 14, lineHeight: 1.7 }}>
                    Steps marked <strong style={{ color: T.cyan }}>Universal</strong> apply identically across all device types and scales.
                    Steps marked <strong style={{ color: T.amber }}>Scale-Sensitive</strong> have methodology that changes significantly
                    based on design complexity — the approach for a simple MCU is fundamentally different from a multi-core SoC.
                  </p>
                </>
              ),
              loss: (
                <>
                  <div className="label" style={{ marginBottom: 12 }}>Architecture Comparison Framework</div>
                  <h2 className="serif" style={{ fontSize: 36, color: T.text, lineHeight: 1.2, marginBottom: 14 }}>
                    Seven Loss Functions for<br /><span style={{ color: T.amber }}>Choosing the Better Architecture</span>
                  </h2>
                  <p style={{ color: T.muted, maxWidth: 680, fontSize: 14, lineHeight: 1.7 }}>
                    When multiple architectures satisfy the same spec, use loss functions to make the choice objective and measurable.
                    Each function quantifies a real cost — in area, power, risk, or schedule — that the architecture imposes on the project.
                  </p>
                </>
              ),
              criteria: (
                <>
                  <div className="label" style={{ marginBottom: 12 }}>Architecture Quality Assessment</div>
                  <h2 className="serif" style={{ fontSize: 36, color: T.text, lineHeight: 1.2, marginBottom: 14 }}>
                    Defining Good and Bad<br /><span style={{ color: T.rose }}>Architecture Criteria</span>
                  </h2>
                  <p style={{ color: T.muted, maxWidth: 680, fontSize: 14, lineHeight: 1.7 }}>
                    Good architecture is not subjective. There are measurable, objective criteria that separate robust architecture
                    from brittle architecture — and they can all be evaluated before a single line of RTL is written.
                  </p>
                </>
              ),
              resources: (
                <>
                  <div className="label" style={{ marginBottom: 12 }}>Curated Learning Resources</div>
                  <h2 className="serif" style={{ fontSize: 36, color: T.text, lineHeight: 1.2, marginBottom: 14 }}>
                    References, Playgrounds<br /><span style={{ color: T.sage }}>& Hands-On Tools</span>
                  </h2>
                  <p style={{ color: T.muted, maxWidth: 680, fontSize: 14, lineHeight: 1.7 }}>
                    From free open-source simulators to real chip fabrication platforms — every resource here is actionable.
                    Reading builds knowledge. Simulating and implementing builds judgment. Both are required.
                  </p>
                </>
              ),
            }[tab]}
          </div>
        </div>

        {/* Content */}
        <div style={{ maxWidth: 1280, margin: "0 auto", padding: "36px 32px 64px" }}>
          {tab === "steps"     && <StepsTab />}
          {tab === "loss"      && <LossTab />}
          {tab === "criteria"  && <CriteriaTab />}
          {tab === "resources" && <ResourcesTab />}
        </div>
      </div>
    </>
  );
}
