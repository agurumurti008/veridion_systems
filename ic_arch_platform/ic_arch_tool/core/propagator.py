"""
Architecture Philosophy Propagation Engine
==========================================
Takes the top-level architecture intent and propagates clear objectives,
specs, and interdependencies to every IP in the design.
Generates a structured IP Design Brief for each block.
"""

from dataclasses import dataclass, field
from typing import Optional
from core.arch_engine import ArchitectureGraph, IPBlock, IPType, SignalDomain


@dataclass
class IPDesignBrief:
    """
    Structured design brief for a single IP block.
    Propagated from architecture-level intent.
    """
    ip_id: str
    ip_name: str
    ip_type: str
    signal_domain: str

    # Architecture context
    arch_intent: str
    app_domain: str
    process_node: str

    # Electrical specs
    supply_voltage_v: float
    max_power_mw: float
    max_area_mm2: float
    operating_freq_mhz: float
    max_latency_ns: float
    temp_range: tuple

    # Functional specs
    functional_objectives: list = field(default_factory=list)
    interface_requirements: list = field(default_factory=list)
    protocol_compliance: list = field(default_factory=list)

    # Interdependencies
    drives: list = field(default_factory=list)       # IPs this IP provides output to
    driven_by: list = field(default_factory=list)    # IPs this IP receives input from
    shared_resources: list = field(default_factory=list)
    critical_paths_through: list = field(default_factory=list)

    # Verification targets
    coverage_goals: list = field(default_factory=list)
    corner_cases: list = field(default_factory=list)

    # Additional guidance
    analog_notes: Optional[str] = None
    power_domain_notes: Optional[str] = None
    cdc_notes: Optional[str] = None
    reuse_guidance: Optional[str] = None

    def render_text(self) -> str:
        """Render a human-readable design brief."""
        lines = [
            f"╔══════════════════════════════════════════════════════════════╗",
            f"║  IP DESIGN BRIEF: {self.ip_name:<44}║",
            f"╚══════════════════════════════════════════════════════════════╝",
            f"",
            f"IP ID         : {self.ip_id}",
            f"Type          : {self.ip_type}  |  Domain: {self.signal_domain}",
            f"App Domain    : {self.app_domain}  |  Process: {self.process_node}",
            f"",
            f"── ARCHITECTURE INTENT ──",
            f"  {self.arch_intent}",
            f"",
            f"── ELECTRICAL SPECS ──",
            f"  Supply Voltage : {self.supply_voltage_v}V",
            f"  Power Budget   : {self.max_power_mw:.2f} mW",
            f"  Area Budget    : {self.max_area_mm2:.4f} mm²",
            f"  Operating Freq : {self.operating_freq_mhz:.1f} MHz",
            f"  Max Latency    : {self.max_latency_ns:.1f} ns",
            f"  Temp Range     : {self.temp_range[0]}°C to {self.temp_range[1]}°C",
            f"",
            f"── FUNCTIONAL OBJECTIVES ──",
        ]
        for obj in self.functional_objectives:
            lines.append(f"  • {obj}")
        lines += ["", "── INTERFACES ──"]
        for iface in self.interface_requirements:
            lines.append(f"  ↔ {iface}")
        if self.protocol_compliance:
            lines += ["", "── PROTOCOL COMPLIANCE ──"]
            for p in self.protocol_compliance:
                lines.append(f"  ✓ {p}")
        lines += ["", "── INTERDEPENDENCIES ──"]
        if self.drives:
            lines.append(f"  Drives      → {', '.join(self.drives)}")
        if self.driven_by:
            lines.append(f"  Driven by   ← {', '.join(self.driven_by)}")
        if self.shared_resources:
            lines.append(f"  Shared with = {', '.join(self.shared_resources)}")
        if self.critical_paths_through:
            lines.append(f"  Critical paths: {', '.join(self.critical_paths_through)}")
        if self.coverage_goals:
            lines += ["", "── VERIFICATION TARGETS ──"]
            for goal in self.coverage_goals:
                lines.append(f"  ☑ {goal}")
        if self.corner_cases:
            lines += ["", "── CORNER CASES ──"]
            for cc in self.corner_cases:
                lines.append(f"  ⚠ {cc}")
        if self.analog_notes:
            lines += ["", f"── ANALOG NOTES ──", f"  {self.analog_notes}"]
        if self.power_domain_notes:
            lines += ["", f"── POWER DOMAIN NOTES ──", f"  {self.power_domain_notes}"]
        if self.cdc_notes:
            lines += ["", f"── CDC NOTES ──", f"  {self.cdc_notes}"]
        if self.reuse_guidance:
            lines += ["", f"── REUSE GUIDANCE ──", f"  {self.reuse_guidance}"]
        lines.append("")
        return "\n".join(lines)


# ─── Intent Templates ─────────────────────────────────────────────────────────

ARCH_INTENT_TEMPLATES = {
    "iot_sensor": (
        "Ultra-low-power always-on sensing platform. Every IP must prioritize "
        "sleep-mode current minimization. Wake latency < 100µs. Analog signal "
        "chain accuracy is paramount; digital noise must be isolated."
    ),
    "smartphone_soc": (
        "High-performance mobile compute with aggressive power-performance scaling. "
        "Thermal envelope is critical; per-IP DVFS is expected. Latency-sensitive "
        "user-facing paths must meet sub-5ms end-to-end targets."
    ),
    "industrial_mcu": (
        "Deterministic real-time control with field-hardened reliability. "
        "Fault containment and ECC are mandatory for safety-critical paths. "
        "Wide temperature operation (-40 to 125°C) must be validated at all corners."
    ),
    "radar_chip": (
        "High-dynamic-range RF signal chain with real-time DSP processing. "
        "Analog frontend noise figure and linearity dominate performance. "
        "Digital backend must sustain continuous 1Gbps throughput without data loss."
    ),
    "generic": (
        "General-purpose embedded platform. Balance power, area, and performance "
        "to meet mid-range application requirements. Prioritize IP reuse and "
        "standard interface compliance."
    ),
}

VERIFICATION_GOALS = {
    IPType.DIGITAL: [
        "100% functional coverage of all FSM states",
        "Code coverage ≥ 95% (line + branch)",
        "Formal verification of control logic",
        "Timing closure at worst-case PVT corner",
    ],
    IPType.ANALOG: [
        "Monte Carlo mismatch analysis (1000 runs)",
        "Corner simulation: TT/FF/SS/SF/FS × nominal/hot/cold",
        "Noise figure and linearity across supply range",
        "ESD protection verification to 2kV HBM",
    ],
    IPType.MIXED_SIGNAL: [
        "INL/DNL within ±0.5 LSB across temp range",
        "SFDR > 70dBc at full-scale input",
        "Digital switching noise impact on analog ground",
        "Supply rejection ratio > 60dB",
    ],
    IPType.MEMORY: [
        "Bit-cell retention at min VDD and max temperature",
        "Read/write margin characterization vs PVT",
        "ECC bit flip detection and correction verified",
        "Wordline/bitline timing margin > 20%",
    ],
    IPType.CLOCK: [
        "Phase noise < -120dBc/Hz at 1MHz offset",
        "Lock time and false-lock immunity",
        "Spread-spectrum profile compliance",
        "Jitter accumulation over 1M cycles",
    ],
    IPType.POWER: [
        "Load regulation < 0.5% across full current range",
        "Line regulation < 0.1% across supply range",
        "Soft-start and inrush current limits",
        "Thermal shutdown and OVP/UVP trip points",
    ],
    IPType.IO: [
        "Signal integrity at max speed",
        "ESD stress to 2kV HBM / 200V MM",
        "Latch-up immunity at 100mA injection",
        "Drive strength programmability verified",
    ],
}

CORNER_CASES = {
    IPType.DIGITAL: ["Clock glitch on power-up", "Back-to-back max-bandwidth transfers",
                     "Reset during active transaction"],
    IPType.ANALOG: ["Input overdrive > 10%", "Supply bounce during high slew event",
                    "Process corner cross-talk from adjacent digital IP"],
    IPType.MIXED_SIGNAL: ["DC offset drift over temperature", "Full-scale step response",
                          "Adjacent channel interference"],
    IPType.MEMORY: ["Single-bit upset from alpha particle", "Simultaneous read/write collision",
                    "Retention at min VDD and 125°C"],
    IPType.CLOCK: ["Cold start lock at -40°C", "Reference clock loss recovery",
                   "Simultaneous PLL and divider switching"],
    IPType.POWER: ["Hot-plug inrush > 10× steady state", "Short-circuit at output",
                   "Thermal runaway prevention"],
    IPType.IO: ["Bus contention from external driver", "Cable ESD event during operation",
                "Hot-plug with live system"],
}


class ArchitecturePropagator:
    """
    Propagates architecture philosophy to each IP block,
    generating a complete set of IP Design Briefs.
    """

    def propagate(self, graph: ArchitectureGraph) -> dict[str, IPDesignBrief]:
        """Returns a dict of ip_id → IPDesignBrief."""
        briefs = {}
        domain = graph.spec.app_domain
        arch_intent = ARCH_INTENT_TEMPLATES.get(domain, ARCH_INTENT_TEMPLATES["generic"])

        # Build connectivity maps
        drives: dict[str, list] = {k: [] for k in graph.ip_blocks}
        driven_by: dict[str, list] = {k: [] for k in graph.ip_blocks}
        for ic in graph.interconnects:
            if ic.src_id in drives and ic.dst_id in drives:
                if ic.signal_domain != SignalDomain.POWER:  # Power is implicit
                    drives[ic.src_id].append(ic.dst_id)
                    driven_by[ic.dst_id].append(ic.src_id)

        for ip_id, ip in graph.ip_blocks.items():
            brief = IPDesignBrief(
                ip_id=ip_id,
                ip_name=ip.name,
                ip_type=ip.ip_type.value,
                signal_domain=ip.signal_domain.value,
                arch_intent=arch_intent,
                app_domain=domain,
                process_node=graph.spec.process_node,
                supply_voltage_v=graph.spec.supply_voltage,
                max_power_mw=ip.power_mw * 1.15,  # 15% margin
                max_area_mm2=ip.area_mm2 * 1.10,
                operating_freq_mhz=min(ip.frequency_mhz, graph.spec.target_frequency),
                max_latency_ns=ip.latency_ns,
                temp_range=graph.spec.operating_temp_range,
                drives=drives[ip_id],
                driven_by=driven_by[ip_id],
                interface_requirements=self._interface_reqs(ip, graph),
                protocol_compliance=ip.interfaces,
                coverage_goals=VERIFICATION_GOALS.get(ip.ip_type, []),
                corner_cases=CORNER_CASES.get(ip.ip_type, []),
                functional_objectives=self._functional_objectives(ip, graph),
                analog_notes=self._analog_notes(ip) if ip.ip_type in (IPType.ANALOG, IPType.MIXED_SIGNAL) else None,
                power_domain_notes=self._power_notes(ip_id, ip, graph),
                cdc_notes=self._cdc_notes(ip_id, ip, graph),
                reuse_guidance=f"Based on: {ip.reuse_from}" if ip.reuse_from else
                               "New implementation required — no prior reuse source identified",
            )
            briefs[ip_id] = brief

        return briefs

    def _interface_reqs(self, ip: IPBlock, graph: ArchitectureGraph) -> list:
        reqs = []
        for iface in ip.interfaces:
            reqs.append(f"{iface} compliance per specification")
        for std in graph.spec.interface_standards:
            if std in ip.interfaces:
                reqs.append(f"{std} certified silicon characterization required")
        return reqs

    def _functional_objectives(self, ip: IPBlock, graph: ArchitectureGraph) -> list:
        objs = [f"Achieve {ip.frequency_mhz:.0f} MHz operation at {graph.spec.supply_voltage}V nominal"]
        objs.append(f"Maintain ≤ {ip.power_mw:.1f} mW at typical corner")
        if ip.ip_type == IPType.DIGITAL:
            objs.append("Implement clock gating on all idle datapath registers")
            objs.append("Ensure scan test coverage ≥ 98%")
        elif ip.ip_type == IPType.ANALOG:
            objs.append(f"Achieve SNR ≥ {ip.specs.get('snr_db', 60)} dB")
            objs.append("Characterize across all process corners (TT/FF/SS/FS/SF)")
        elif ip.ip_type == IPType.MIXED_SIGNAL:
            objs.append(f"Resolution: {ip.specs.get('resolution', 'N/A')} bits with full INL/DNL spec")
            objs.append("Implement digital calibration for offset and gain error")
        elif ip.ip_type == IPType.MEMORY:
            objs.append("Enable low-power retention mode with VDDQ scaling")
            objs.append(f"Capacity: {ip.specs.get('capacity_kb', ip.specs.get('capacity_mb', 'N/A'))} with error correction")
        elif ip.ip_type == IPType.CLOCK:
            objs.append("Sub-1ps RMS jitter in locked state")
            objs.append("Spread-spectrum modulation capability if required by EMI spec")
        elif ip.ip_type == IPType.POWER:
            objs.append("Implement independent power sequencing for all voltage domains")
            objs.append("On-chip voltage monitoring with ±2% accuracy")
        return objs

    def _analog_notes(self, ip: IPBlock) -> str:
        return (
            f"Signal domain isolation critical. Ensure dedicated analog ground (AGND) "
            f"separated from digital ground with single-point star connection. "
            f"Route analog signals on dedicated metal layer away from digital clocks. "
            f"Guard-ring all sensitive nodes. Validate substrate coupling from digital "
            f"switching activity through layout extraction + post-layout simulation."
        )

    def _power_notes(self, ip_id: str, ip: IPBlock, graph: ArchitectureGraph) -> str:
        pwr_src = [ic.src_id for ic in graph.interconnects
                   if ic.dst_id == ip_id and ic.signal_domain == SignalDomain.POWER]
        if pwr_src:
            return f"Powered by: {', '.join(pwr_src)}. Ensure sequencing compliance per PMU spec."
        return "No explicit power connection defined — verify power domain assignment with PMU."

    def _cdc_notes(self, ip_id: str, ip: IPBlock, graph: ArchitectureGraph) -> str:
        cdc_crossings = []
        for ic in graph.interconnects:
            if ic.signal_domain == SignalDomain.DIGITAL:
                other_id = ic.dst_id if ic.src_id == ip_id else (ic.src_id if ic.dst_id == ip_id else None)
                if other_id and other_id in graph.ip_blocks:
                    other_f = graph.ip_blocks[other_id].frequency_mhz
                    if max(ip.frequency_mhz, other_f) / max(min(ip.frequency_mhz, other_f), 0.01) > 2.0:
                        cdc_crossings.append(f"{other_id} ({other_f:.0f}MHz)")
        if cdc_crossings:
            return (f"CDC crossings detected to: {', '.join(cdc_crossings)}. "
                    f"Insert 2-FF synchronizers or async FIFO handshake as appropriate. "
                    f"Verify with CDC tool (Questa CDC / Cadence JasperGold).")
        return "No significant CDC crossings detected at this IP boundary."
