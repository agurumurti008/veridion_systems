"""
Architecture Quality Assessment Engine
=======================================
Quantified evaluation with multi-objective loss functions.
Each metric maps to a normalized score in [0, 1].
Composite loss enables gradient-free optimization loops.
"""

import math
from dataclasses import dataclass, field
from typing import Optional
from core.arch_engine import ArchitectureGraph, IPType, SignalDomain


# ─── Individual Loss Functions ────────────────────────────────────────────────

def loss_power(graph: ArchitectureGraph) -> float:
    """L_power: how much power budget is consumed (0=under, 1=at limit, >1=over)."""
    total = graph.total_power()
    budget = graph.spec.power_budget
    return total / budget if budget > 0 else 1.0


def loss_area(graph: ArchitectureGraph) -> float:
    """L_area: area utilization relative to budget."""
    total = graph.total_area()
    budget = graph.spec.area_budget
    return total / budget if budget > 0 else 1.0


def loss_timing(graph: ArchitectureGraph) -> float:
    """
    L_timing: measures timing risk based on IP operating frequencies vs spec target.
    Returns ratio of IPs operating below target frequency, weighted by severity.
    0 = all IPs meet timing, 1 = all IPs significantly miss timing.
    """
    from core.arch_engine import IPType
    digital_ips = [ip for ip in graph.ip_blocks.values()
                   if ip.ip_type in (IPType.DIGITAL, IPType.MIXED_SIGNAL)]
    if not digital_ips:
        return 0.0
    target_f = graph.spec.target_frequency
    violations = 0.0
    for ip in digital_ips:
        if ip.frequency_mhz < target_f:
            # Soft violation: proportional to gap
            violations += min((target_f - ip.frequency_mhz) / target_f, 1.0)
    return violations / len(digital_ips)


def loss_connectivity(graph: ArchitectureGraph) -> float:
    """
    L_connectivity: penalizes missing critical connections.
    For each expected IP pair, checks if interconnect exists.
    Returns fraction of missing connections [0=perfect, 1=all missing].
    """
    expected_pairs = [
        ("cpu_core", "sram_256k"), ("cpu_core", "flash_2m"),
        ("pll", "cpu_core"), ("pmu", "cpu_core"),
        ("interrupt_ctrl", "cpu_core"),
    ]
    present_ids = set(graph.ip_blocks.keys())
    connected_pairs = set(
        (ic.src_id, ic.dst_id) for ic in graph.interconnects
    )
    missing = 0
    total = 0
    for src, dst in expected_pairs:
        if src in present_ids and dst in present_ids:
            total += 1
            if (src, dst) not in connected_pairs:
                missing += 1
    return missing / total if total > 0 else 0.0


def loss_ip_coverage(graph: ArchitectureGraph) -> float:
    """
    L_coverage: fraction of required interface standards not satisfied.
    If no interface standards are specified, returns 0 (no penalty).
    """
    required = set(graph.spec.interface_standards)
    if not required:
        return 0.0
    all_interfaces = set()
    for ip in graph.ip_blocks.values():
        all_interfaces.update(ip.interfaces)
    # Also check interface names case-insensitively with partial match
    # e.g., "CAN" matches "CAN-FD" in ip specs
    satisfied = set()
    for req in required:
        for iface in all_interfaces:
            if req.lower() in iface.lower() or iface.lower() in req.lower():
                satisfied.add(req)
                break
    missing = required - satisfied
    return len(missing) / len(required)


def loss_clock_domain_crossings(graph: ArchitectureGraph) -> float:
    """
    L_cdc: penalizes uncontrolled clock domain crossings.
    Proxy: count digital interconnects between IPs running at very different frequencies.
    Normalizes by total digital interconnects.
    """
    digital_ics = [ic for ic in graph.interconnects
                   if ic.signal_domain == SignalDomain.DIGITAL]
    if not digital_ics:
        return 0.0
    risky = 0
    for ic in digital_ics:
        src_f = graph.ip_blocks[ic.src_id].frequency_mhz
        dst_f = graph.ip_blocks[ic.dst_id].frequency_mhz
        if max(src_f, dst_f) / max(min(src_f, dst_f), 0.001) > 4.0:
            risky += 1
    return risky / len(digital_ics)


def loss_analog_isolation(graph: ArchitectureGraph) -> float:
    """
    L_isolation: penalizes analog IPs with high fan-in from digital neighbors.
    Noisy digital signals coupling into analog = bad.
    """
    analog_ids = {k for k, ip in graph.ip_blocks.items()
                  if ip.ip_type in (IPType.ANALOG, IPType.MIXED_SIGNAL)}
    if not analog_ids:
        return 0.0
    total_violations = 0
    for ic in graph.interconnects:
        if ic.dst_id in analog_ids and ic.signal_domain == SignalDomain.DIGITAL:
            total_violations += 1
    return min(total_violations / max(len(analog_ids), 1), 1.0)


def loss_ip_redundancy(graph: ArchitectureGraph) -> float:
    """
    L_redundancy: detect duplicate IP types (over-provisioning).
    Penalty per redundant IP beyond 1.
    """
    from collections import Counter
    type_counts = Counter(ip.ip_type for ip in graph.ip_blocks.values()
                          if ip.ip_type not in (IPType.IO, IPType.MEMORY))
    excess = sum(max(v - 2, 0) for v in type_counts.values())
    return min(excess / max(len(graph.ip_blocks), 1), 1.0)


def loss_power_domain_integrity(graph: ArchitectureGraph) -> float:
    """
    L_pdi: checks that PMU exists and connects to all IPs.
    If PMU missing, maximum penalty.
    """
    if "pmu" not in graph.ip_blocks:
        return 1.0
    powered_ids = {ic.dst_id for ic in graph.interconnects
                   if ic.src_id == "pmu" and ic.signal_domain == SignalDomain.POWER}
    all_ids = set(graph.ip_blocks.keys()) - {"pmu"}
    unpowered = all_ids - powered_ids
    return len(unpowered) / max(len(all_ids), 1)


# ─── Composite Evaluator ──────────────────────────────────────────────────────

@dataclass
class EvalWeights:
    """Weights for composite loss. Sum need not be 1; normalized internally."""
    power: float = 2.0
    area: float = 1.5
    timing: float = 2.0
    connectivity: float = 3.0
    ip_coverage: float = 2.5
    cdc: float = 1.5
    analog_isolation: float = 1.0
    redundancy: float = 0.5
    power_domain: float = 2.0


@dataclass
class ArchEvalResult:
    """Full evaluation result for one architecture."""
    scores: dict = field(default_factory=dict)
    losses: dict = field(default_factory=dict)
    composite_loss: float = 0.0
    composite_score: float = 0.0
    grade: str = "F"
    violations: list = field(default_factory=list)
    suggestions: list = field(default_factory=list)
    summary: dict = field(default_factory=dict)


GRADE_THRESHOLDS = [
    (0.90, "A+"), (0.85, "A"), (0.78, "A-"),
    (0.72, "B+"), (0.65, "B"), (0.58, "B-"),
    (0.50, "C+"), (0.42, "C"), (0.35, "C-"),
    (0.25, "D"),  (0.0,  "F"),
]


def _score_from_loss(loss: float, ideal: float = 0.85) -> float:
    """Convert raw loss to a 0-1 score. Loss=0 → 1.0, Loss>=2 → 0.0."""
    return max(0.0, 1.0 - loss / 2.0)


class ArchitectureEvaluator:
    """
    Runs all loss functions, computes composite loss and score,
    assigns grade, and generates actionable suggestions.
    """

    def __init__(self, weights: Optional[EvalWeights] = None):
        self.weights = weights or EvalWeights()

    def evaluate(self, graph: ArchitectureGraph) -> ArchEvalResult:
        result = ArchEvalResult()

        # Compute raw losses
        losses = {
            "power":           loss_power(graph),
            "area":            loss_area(graph),
            "timing":          loss_timing(graph),
            "connectivity":    loss_connectivity(graph),
            "ip_coverage":     loss_ip_coverage(graph),
            "cdc":             loss_clock_domain_crossings(graph),
            "analog_isolation":loss_analog_isolation(graph),
            "redundancy":      loss_ip_redundancy(graph),
            "power_domain":    loss_power_domain_integrity(graph),
        }
        result.losses = {k: round(v, 4) for k, v in losses.items()}

        # Convert to scores
        result.scores = {k: round(_score_from_loss(v), 4) for k, v in losses.items()}

        # Weighted composite
        w = self.weights
        weight_map = {
            "power": w.power, "area": w.area, "timing": w.timing,
            "connectivity": w.connectivity, "ip_coverage": w.ip_coverage,
            "cdc": w.cdc, "analog_isolation": w.analog_isolation,
            "redundancy": w.redundancy, "power_domain": w.power_domain,
        }
        total_w = sum(weight_map.values())
        composite_loss = sum(losses[k] * weight_map[k] for k in losses) / total_w
        result.composite_loss = round(composite_loss, 4)
        result.composite_score = round(_score_from_loss(composite_loss), 4)

        # Grade
        for threshold, grade in GRADE_THRESHOLDS:
            if result.composite_score >= threshold:
                result.grade = grade
                break

        # Violations
        result.violations = self._detect_violations(graph, losses)

        # Suggestions
        result.suggestions = self._generate_suggestions(graph, losses)

        # Summary
        result.summary = {
            **graph.summary(),
            "composite_score": result.composite_score,
            "composite_loss": result.composite_loss,
            "grade": result.grade,
        }

        return result

    def _detect_violations(self, graph: ArchitectureGraph, losses: dict) -> list:
        viol = []
        if losses["power"] > 1.0:
            over = (losses["power"] - 1.0) * graph.spec.power_budget
            viol.append(f"POWER_OVER_BUDGET: {over:.1f}mW over limit")
        if losses["area"] > 1.0:
            over = (losses["area"] - 1.0) * graph.spec.area_budget
            viol.append(f"AREA_OVER_BUDGET: {over:.3f}mm² over limit")
        if losses["timing"] > 1.0:
            viol.append(f"TIMING_VIOLATION: critical path exceeds clock period by {(losses['timing']-1)*100:.0f}%")
        if losses["connectivity"] > 0.3:
            viol.append(f"CONNECTIVITY: {losses['connectivity']*100:.0f}% of critical connections missing")
        if losses["ip_coverage"] > 0.0:
            missing = [s for s in graph.spec.interface_standards
                       if not any(s in ip.interfaces for ip in graph.ip_blocks.values())]
            viol.append(f"INTERFACE_MISSING: {missing}")
        if losses["power_domain"] > 0.5:
            viol.append("POWER_DOMAIN: PMU not connected to all IPs")
        if losses["analog_isolation"] > 0.5:
            viol.append("ANALOG_ISOLATION: digital noise paths into analog IPs detected")
        return viol

    def _generate_suggestions(self, graph: ArchitectureGraph, losses: dict) -> list:
        sug = []
        if losses["power"] > 0.9:
            sug.append("Consider power gating low-utilization IPs or reducing core voltage")
        if losses["area"] > 0.9:
            sug.append("Review IP sizes; consider memory macros or smaller process node")
        if losses["timing"] > 0.8:
            sug.append("Pipeline deep logic paths; verify clock constraints with STA")
        if losses["cdc"] > 0.3:
            sug.append("Insert synchronizer flops or handshake bridges at CDC crossings")
        if losses["analog_isolation"] > 0.3:
            sug.append("Add guard rings and shielding; route analog signals away from digital switching")
        if losses["ip_coverage"] > 0.2:
            sug.append("Add missing interface IPs to satisfy protocol requirements")
        if losses["redundancy"] > 0.2:
            sug.append("Consolidate redundant IP instances; share via bus arbitration")
        if losses["connectivity"] > 0.1:
            sug.append("Review bus topology; add missing interconnects for uncovered IPs")
        if not sug:
            sug.append("Architecture meets all major quality criteria — proceed to detailed spec")
        return sug


# ─── Optimization Loop ────────────────────────────────────────────────────────

class ArchitectureOptimizer:
    """
    Iterative optimization using greedy hill-climbing on composite loss.
    Explores IP addition/removal and interconnect restructuring.
    Acts as the outer loop calling the evaluator as a loss oracle.
    """

    def __init__(self, evaluator: ArchitectureEvaluator, max_iterations: int = 20):
        self.evaluator = evaluator
        self.max_iterations = max_iterations

    def optimize(self, graph: ArchitectureGraph, verbose: bool = True) -> tuple:
        """Returns (best_graph, best_result, history)."""
        from core.arch_engine import ArchitectureBuilder, Interconnect
        import copy

        best_graph = copy.deepcopy(graph)
        best_result = self.evaluator.evaluate(best_graph)
        history = [{"iter": 0, "loss": best_result.composite_loss,
                    "score": best_result.composite_score, "grade": best_result.grade}]

        for i in range(1, self.max_iterations + 1):
            candidate = copy.deepcopy(best_graph)
            improved = False

            # Strategy: address worst scoring dimension
            worst_dim = max(best_result.losses, key=best_result.losses.get)

            if worst_dim == "power_domain" and "pmu" not in candidate.ip_blocks:
                from core.arch_engine import ArchitectureBuilder
                pmu = copy.deepcopy(ArchitectureBuilder.IP_LIBRARY.get("pmu"))
                if pmu:
                    candidate.add_ip(pmu)
                    for ip_id in list(candidate.ip_blocks.keys()):
                        if ip_id != "pmu":
                            try:
                                candidate.add_interconnect(Interconnect(
                                    "pmu", ip_id, SignalDomain.POWER, 0, 0, "power_rail", 0))
                            except Exception:
                                pass
                    improved = True

            elif worst_dim == "connectivity":
                # Try adding missing critical connections
                for src, dst in [("cpu_core","sram_256k"),("cpu_core","flash_2m"),("pll","cpu_core")]:
                    if src in candidate.ip_blocks and dst in candidate.ip_blocks:
                        existing = any(ic.src_id==src and ic.dst_id==dst for ic in candidate.interconnects)
                        if not existing:
                            try:
                                candidate.add_interconnect(Interconnect(
                                    src, dst, SignalDomain.DIGITAL, 8.0, 2.0, "AXI4", 0.2))
                                improved = True
                                break
                            except Exception:
                                pass

            elif worst_dim == "ip_coverage":
                # Try adding a missing interface IP
                missing_ifaces = [s for s in candidate.spec.interface_standards
                                  if not any(s in ip.interfaces for ip in candidate.ip_blocks.values())]
                iface_to_ip = {
                    "CAN": "can_ctrl", "Ethernet": "eth_mac", "I2C": "i2c_ctrl",
                    "SPI": "spi_master", "UART": "uart_ip", "USB2": "usb2_phy",
                }
                for iface in missing_ifaces:
                    ip_key = iface_to_ip.get(iface)
                    if ip_key and ip_key in ArchitectureBuilder.IP_LIBRARY and ip_key not in candidate.ip_blocks:
                        candidate.add_ip(copy.deepcopy(ArchitectureBuilder.IP_LIBRARY[ip_key]))
                        if "cpu_core" in candidate.ip_blocks:
                            try:
                                candidate.add_interconnect(Interconnect(
                                    "cpu_core", ip_key, SignalDomain.DIGITAL, 0.5, 5.0, "APB", 0.02))
                            except Exception:
                                pass
                        improved = True
                        break

            elif worst_dim == "power" and best_result.losses["power"] > 1.0:
                # Trim highest power non-essential IP
                non_essential = [k for k in candidate.ip_blocks
                                 if k not in ("cpu_core","pmu","pll","sram_256k")]
                if non_essential:
                    worst_ip = max(non_essential, key=lambda k: candidate.ip_blocks[k].power_mw)
                    del candidate.ip_blocks[worst_ip]
                    candidate.interconnects = [ic for ic in candidate.interconnects
                                               if ic.src_id != worst_ip and ic.dst_id != worst_ip]
                    candidate._rebuild_index()
                    improved = True

            if improved:
                result = self.evaluator.evaluate(candidate)
                if result.composite_loss < best_result.composite_loss:
                    best_graph = candidate
                    best_result = result

            history.append({
                "iter": i,
                "loss": best_result.composite_loss,
                "score": best_result.composite_score,
                "grade": best_result.grade
            })

            if verbose:
                print(f"  Iter {i:2d}: loss={best_result.composite_loss:.4f}  "
                      f"score={best_result.composite_score:.4f}  grade={best_result.grade}")

            if best_result.composite_loss < 0.15:  # Early exit if excellent
                break

        return best_graph, best_result, history
