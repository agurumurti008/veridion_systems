"""
IC Architecture Engine
======================
Translates application specs into structured architecture graphs.
Supports digital, analog, and mixed-signal IP classification.
"""

import json
import math
import itertools
from dataclasses import dataclass, field, asdict
from typing import Optional
from enum import Enum


class IPType(Enum):
    DIGITAL = "digital"
    ANALOG = "analog"
    MIXED_SIGNAL = "mixed_signal"
    MEMORY = "memory"
    IO = "io"
    POWER = "power"
    CLOCK = "clock"


class SignalDomain(Enum):
    DIGITAL = "digital"
    ANALOG = "analog"
    POWER = "power"
    CLOCK = "clock"
    RF = "rf"


@dataclass
class ArchSpec:
    """Top-level architecture specification derived from application requirements."""
    app_domain: str
    process_node: str
    supply_voltage: float
    target_frequency: float  # MHz
    power_budget: float      # mW
    area_budget: float       # mm²
    performance_targets: dict = field(default_factory=dict)
    reliability_targets: dict = field(default_factory=dict)
    interface_standards: list = field(default_factory=list)
    operating_temp_range: tuple = field(default_factory=lambda: (-40, 125))

    def to_dict(self):
        d = asdict(self)
        d['operating_temp_range'] = list(self.operating_temp_range)
        return d


@dataclass
class IPBlock:
    """Represents a single IP block in the architecture."""
    ip_id: str
    name: str
    ip_type: IPType
    signal_domain: SignalDomain
    power_mw: float
    area_mm2: float
    frequency_mhz: float
    latency_ns: float
    interfaces: list = field(default_factory=list)
    dependencies: list = field(default_factory=list)
    specs: dict = field(default_factory=dict)
    verified: bool = False
    reuse_from: Optional[str] = None  # Prior device reference

    def feature_vector(self):
        """Return numerical feature vector for ML use."""
        type_enc = list(IPType).index(self.ip_type)
        dom_enc = list(SignalDomain).index(self.signal_domain)
        return [
            type_enc, dom_enc,
            self.power_mw, self.area_mm2,
            self.frequency_mhz, self.latency_ns,
            len(self.interfaces), len(self.dependencies),
            1.0 if self.verified else 0.0
        ]


@dataclass
class Interconnect:
    """Directed edge between two IP blocks."""
    src_id: str
    dst_id: str
    signal_domain: SignalDomain
    bandwidth_gbps: float
    latency_ns: float
    protocol: str = "proprietary"
    power_mw: float = 0.0

    def feature_vector(self):
        dom_enc = list(SignalDomain).index(self.signal_domain)
        return [dom_enc, self.bandwidth_gbps, self.latency_ns, self.power_mw]


class ArchitectureGraph:
    """
    Graph representation of an IC architecture.
    Nodes = IP blocks, Edges = Interconnects.
    Provides adjacency matrix and feature matrices for ML consumption.
    """

    def __init__(self, spec: ArchSpec):
        self.spec = spec
        self.ip_blocks: dict[str, IPBlock] = {}
        self.interconnects: list[Interconnect] = []
        self._id_to_idx: dict[str, int] = {}

    def add_ip(self, ip: IPBlock):
        self.ip_blocks[ip.ip_id] = ip
        self._rebuild_index()

    def add_interconnect(self, ic: Interconnect):
        if ic.src_id not in self.ip_blocks or ic.dst_id not in self.ip_blocks:
            raise ValueError(f"Unknown IP in interconnect: {ic.src_id} -> {ic.dst_id}")
        self.interconnects.append(ic)

    def _rebuild_index(self):
        self._id_to_idx = {k: i for i, k in enumerate(self.ip_blocks)}

    def adjacency_matrix(self):
        """Weighted adjacency matrix (bandwidth)."""
        n = len(self.ip_blocks)
        A = [[0.0] * n for _ in range(n)]
        for ic in self.interconnects:
            i = self._id_to_idx[ic.src_id]
            j = self._id_to_idx[ic.dst_id]
            A[i][j] = ic.bandwidth_gbps
        return A

    def node_feature_matrix(self):
        """Feature matrix X where each row = IP feature vector."""
        return [ip.feature_vector() for ip in self.ip_blocks.values()]

    def edge_feature_list(self):
        """List of (src_idx, dst_idx, features) for GNN use."""
        edges = []
        for ic in self.interconnects:
            i = self._id_to_idx[ic.src_id]
            j = self._id_to_idx[ic.dst_id]
            edges.append((i, j, ic.feature_vector()))
        return edges

    def total_power(self):
        return sum(ip.power_mw for ip in self.ip_blocks.values()) + \
               sum(ic.power_mw for ic in self.interconnects)

    def total_area(self):
        return sum(ip.area_mm2 for ip in self.ip_blocks.values())

    def critical_path_latency(self):
        """Longest path latency via topological sort (simple DAG)."""
        dist = {k: ip.latency_ns for k, ip in self.ip_blocks.items()}
        # Relax edges
        for _ in range(len(self.ip_blocks)):
            for ic in self.interconnects:
                new_d = dist[ic.src_id] + ic.latency_ns + self.ip_blocks[ic.dst_id].latency_ns
                if new_d > dist[ic.dst_id]:
                    dist[ic.dst_id] = new_d
        return max(dist.values()) if dist else 0.0

    def summary(self):
        return {
            "n_ips": len(self.ip_blocks),
            "n_interconnects": len(self.interconnects),
            "total_power_mw": round(self.total_power(), 3),
            "total_area_mm2": round(self.total_area(), 4),
            "critical_path_ns": round(self.critical_path_latency(), 2),
            "power_budget_mw": self.spec.power_budget,
            "area_budget_mm2": self.spec.area_budget,
        }

    def to_dict(self):
        return {
            "spec": self.spec.to_dict(),
            "ip_blocks": {k: asdict(v) for k, v in self.ip_blocks.items()},
            "interconnects": [asdict(ic) for ic in self.interconnects],
        }


# ─── Spec Parser ────────────────────────────────────────────────────────────────

DOMAIN_TEMPLATES = {
    "iot_sensor": {
        "process_node": "22nm",
        "supply_voltage": 1.8,
        "target_frequency": 48.0,
        "power_budget": 5.0,
        "area_budget": 4.0,
        "interface_standards": ["I2C", "SPI", "UART"],
        "performance_targets": {"adc_resolution": 12, "sleep_current_ua": 1},
    },
    "smartphone_soc": {
        "process_node": "4nm",
        "supply_voltage": 0.75,
        "target_frequency": 3200.0,
        "power_budget": 5000.0,
        "area_budget": 100.0,
        "interface_standards": ["PCIe5", "USB4", "MIPI-CSI", "LPDDR5"],
        "performance_targets": {"cpu_dmips": 100000, "gpu_tops": 20},
    },
    "industrial_mcu": {
        "process_node": "40nm",
        "supply_voltage": 3.3,
        "target_frequency": 200.0,
        "power_budget": 150.0,
        "area_budget": 25.0,
        "interface_standards": ["CAN", "RS485", "Ethernet", "USB2"],
        "performance_targets": {"flash_mb": 2, "ram_kb": 512},
    },
    "radar_chip": {
        "process_node": "16nm",
        "supply_voltage": 1.0,
        "target_frequency": 1000.0,
        "power_budget": 2000.0,
        "area_budget": 50.0,
        "interface_standards": ["PCIe4", "Ethernet"],
        "performance_targets": {"range_m": 250, "velocity_mps": 60, "angular_res_deg": 1.5},
    },
}


def parse_spec_from_dict(raw: dict) -> ArchSpec:
    """Build an ArchSpec from a raw user dictionary, applying domain defaults."""
    domain = raw.get("app_domain", "generic")
    defaults = DOMAIN_TEMPLATES.get(domain, {})
    merged = {**defaults, **raw}
    return ArchSpec(
        app_domain=domain,
        process_node=merged.get("process_node", "28nm"),
        supply_voltage=float(merged.get("supply_voltage", 1.8)),
        target_frequency=float(merged.get("target_frequency", 100.0)),
        power_budget=float(merged.get("power_budget", 100.0)),
        area_budget=float(merged.get("area_budget", 10.0)),
        performance_targets=merged.get("performance_targets", {}),
        reliability_targets=merged.get("reliability_targets", {}),
        interface_standards=merged.get("interface_standards", []),
        operating_temp_range=tuple(merged.get("operating_temp_range", [-40, 125])),
    )


# ─── Architecture Builder ───────────────────────────────────────────────────────

class ArchitectureBuilder:
    """
    Rule-based + heuristic architecture generator.
    Takes a spec and produces a candidate ArchitectureGraph with
    appropriate IP blocks and interconnects.
    """

    IP_LIBRARY = {
        "cpu_core": IPBlock("cpu_core", "CPU Core", IPType.DIGITAL, SignalDomain.DIGITAL,
                             power_mw=200, area_mm2=2.0, frequency_mhz=1000,
                             latency_ns=1.0, interfaces=["AXI4", "AHB"],
                             specs={"isa": "RISC-V", "pipeline": 5}),
        "dsp_core": IPBlock("dsp_core", "DSP Core", IPType.DIGITAL, SignalDomain.DIGITAL,
                             power_mw=120, area_mm2=1.2, frequency_mhz=500,
                             latency_ns=2.0, interfaces=["AXI4"],
                             specs={"macs": 64, "simd_width": 256}),
        "adc_12b": IPBlock("adc_12b", "12-bit ADC", IPType.MIXED_SIGNAL, SignalDomain.ANALOG,
                            power_mw=1.5, area_mm2=0.05, frequency_mhz=1,
                            latency_ns=1000, interfaces=["SPI", "parallel"],
                            specs={"resolution": 12, "snr_db": 72}),
        "dac_10b": IPBlock("dac_10b", "10-bit DAC", IPType.MIXED_SIGNAL, SignalDomain.ANALOG,
                            power_mw=0.8, area_mm2=0.03, frequency_mhz=0.5,
                            latency_ns=500, interfaces=["SPI"],
                            specs={"resolution": 10, "thd_db": -65}),
        "sram_256k": IPBlock("sram_256k", "256KB SRAM", IPType.MEMORY, SignalDomain.DIGITAL,
                              power_mw=5.0, area_mm2=0.8, frequency_mhz=800,
                              latency_ns=0.5, interfaces=["AHB", "SRAM-IF"],
                              specs={"capacity_kb": 256}),
        "flash_2m": IPBlock("flash_2m", "2MB Flash", IPType.MEMORY, SignalDomain.DIGITAL,
                             power_mw=8.0, area_mm2=3.0, frequency_mhz=100,
                             latency_ns=50, interfaces=["QSPI"],
                             specs={"capacity_mb": 2, "endurance_cycles": 100000}),
        "pll": IPBlock("pll", "PLL", IPType.CLOCK, SignalDomain.CLOCK,
                        power_mw=2.0, area_mm2=0.02, frequency_mhz=2000,
                        latency_ns=500, interfaces=["clock"],
                        specs={"jitter_ps": 1, "lock_time_us": 100}),
        "pmu": IPBlock("pmu", "Power Management Unit", IPType.POWER, SignalDomain.POWER,
                        power_mw=3.0, area_mm2=0.5, frequency_mhz=10,
                        latency_ns=1000, interfaces=["APB", "power"],
                        specs={"vreg_count": 4, "efficiency_pct": 92}),
        "gpio_bank": IPBlock("gpio_bank", "GPIO Bank", IPType.IO, SignalDomain.DIGITAL,
                              power_mw=0.5, area_mm2=0.1, frequency_mhz=100,
                              latency_ns=5, interfaces=["APB"],
                              specs={"pins": 32}),
        "uart_ip": IPBlock("uart_ip", "UART Controller", IPType.DIGITAL, SignalDomain.DIGITAL,
                            power_mw=0.2, area_mm2=0.02, frequency_mhz=48,
                            latency_ns=20, interfaces=["APB"],
                            specs={"baud_max": 3000000}),
        "spi_master": IPBlock("spi_master", "SPI Master", IPType.DIGITAL, SignalDomain.DIGITAL,
                               power_mw=0.3, area_mm2=0.02, frequency_mhz=48,
                               latency_ns=10, interfaces=["APB"],
                               specs={"max_clk_mhz": 50}),
        "i2c_ctrl": IPBlock("i2c_ctrl", "I2C Controller", IPType.DIGITAL, SignalDomain.DIGITAL,
                             power_mw=0.1, area_mm2=0.01, frequency_mhz=1,
                             latency_ns=50, interfaces=["APB"],
                             specs={"max_speed": "Fast-mode+"}),
        "can_ctrl": IPBlock("can_ctrl", "CAN Controller", IPType.DIGITAL, SignalDomain.DIGITAL,
                             power_mw=1.0, area_mm2=0.05, frequency_mhz=80,
                             latency_ns=25, interfaces=["AHB"],
                             specs={"can_fd": True, "max_mbps": 8}),
        "eth_mac": IPBlock("eth_mac", "Ethernet MAC", IPType.DIGITAL, SignalDomain.DIGITAL,
                            power_mw=15.0, area_mm2=0.3, frequency_mhz=250,
                            latency_ns=40, interfaces=["AXI4", "RGMII"],
                            specs={"speed_mbps": 1000}),
        "npu": IPBlock("npu", "Neural Processing Unit", IPType.DIGITAL, SignalDomain.DIGITAL,
                        power_mw=500, area_mm2=4.0, frequency_mhz=1000,
                        latency_ns=5, interfaces=["AXI4"],
                        specs={"tops": 8, "precision": "INT8"}),
        "radar_fend": IPBlock("radar_fend", "Radar Frontend", IPType.ANALOG, SignalDomain.RF,
                               power_mw=300, area_mm2=2.0, frequency_mhz=77000,
                               latency_ns=100, interfaces=["LVDS"],
                               specs={"tx_channels": 3, "rx_channels": 4}),
        "usb2_phy": IPBlock("usb2_phy", "USB2 PHY", IPType.MIXED_SIGNAL, SignalDomain.ANALOG,
                             power_mw=20, area_mm2=0.2, frequency_mhz=480,
                             latency_ns=10, interfaces=["UTMI"],
                             specs={"speed": "HS"}),
        "timer_wdg": IPBlock("timer_wdg", "Timer/Watchdog", IPType.DIGITAL, SignalDomain.DIGITAL,
                              power_mw=0.05, area_mm2=0.005, frequency_mhz=48,
                              latency_ns=5, interfaces=["APB"],
                              specs={"channels": 6}),
        "dma_ctrl": IPBlock("dma_ctrl", "DMA Controller", IPType.DIGITAL, SignalDomain.DIGITAL,
                             power_mw=5.0, area_mm2=0.1, frequency_mhz=200,
                             latency_ns=3, interfaces=["AXI4", "AHB"],
                             specs={"channels": 16}),
        "interrupt_ctrl": IPBlock("interrupt_ctrl", "Interrupt Controller", IPType.DIGITAL, SignalDomain.DIGITAL,
                                   power_mw=0.1, area_mm2=0.01, frequency_mhz=200,
                                   latency_ns=2, interfaces=["APB"],
                                   specs={"irq_lines": 64}),
    }

    DOMAIN_IP_MAP = {
        "iot_sensor":    ["pll", "pmu", "cpu_core", "sram_256k", "flash_2m",
                           "adc_12b", "dac_10b", "gpio_bank", "uart_ip",
                           "spi_master", "i2c_ctrl", "timer_wdg", "interrupt_ctrl"],
        "smartphone_soc": ["pll", "pmu", "cpu_core", "dsp_core", "npu",
                            "sram_256k", "eth_mac", "usb2_phy", "gpio_bank",
                            "dma_ctrl", "interrupt_ctrl"],
        "industrial_mcu": ["pll", "pmu", "cpu_core", "sram_256k", "flash_2m",
                            "gpio_bank", "uart_ip", "spi_master", "i2c_ctrl",
                            "can_ctrl", "eth_mac", "timer_wdg", "dma_ctrl",
                            "interrupt_ctrl", "adc_12b"],
        "radar_chip":    ["pll", "pmu", "cpu_core", "dsp_core", "sram_256k",
                           "radar_fend", "adc_12b", "dac_10b", "eth_mac",
                           "dma_ctrl", "interrupt_ctrl"],
        "generic":       ["pll", "pmu", "cpu_core", "sram_256k", "gpio_bank",
                           "uart_ip", "interrupt_ctrl"],
    }

    def build(self, spec: ArchSpec) -> ArchitectureGraph:
        import copy
        graph = ArchitectureGraph(spec)
        domain = spec.app_domain if spec.app_domain in self.DOMAIN_IP_MAP else "generic"
        ip_ids = self.DOMAIN_IP_MAP[domain]

        # Scale IP parameters to match spec frequency/power
        freq_scale = spec.target_frequency / 1000.0

        for ip_id in ip_ids:
            if ip_id not in self.IP_LIBRARY:
                continue
            ip = copy.deepcopy(self.IP_LIBRARY[ip_id])
            # Scale digital IPs by frequency ratio
            if ip.ip_type == IPType.DIGITAL and ip.frequency_mhz > 0:
                ratio = min(spec.target_frequency / max(ip.frequency_mhz, 1), 3.0)
                ip.power_mw *= ratio ** 1.3
                ip.frequency_mhz = min(ip.frequency_mhz * ratio, spec.target_frequency)
            graph.add_ip(ip)

        # Add interconnects based on standard bus topology
        self._wire_interconnects(graph, ip_ids)
        return graph

    def _wire_interconnects(self, graph: ArchitectureGraph, ip_ids: list):
        """Wire up standard bus connections."""
        has = lambda x: x in ip_ids and x in graph.ip_blocks

        # PLL → everything digital
        if has("pll"):
            for ip_id in ip_ids:
                if ip_id != "pll" and ip_id in graph.ip_blocks:
                    ip = graph.ip_blocks[ip_id]
                    if ip.signal_domain in (SignalDomain.DIGITAL, SignalDomain.CLOCK):
                        graph.add_interconnect(Interconnect(
                            "pll", ip_id, SignalDomain.CLOCK, 0.001, 0.1, "clock", 0.0))

        # CPU ↔ SRAM (high bandwidth)
        if has("cpu_core") and has("sram_256k"):
            graph.add_interconnect(Interconnect("cpu_core", "sram_256k",
                SignalDomain.DIGITAL, 32.0, 1.0, "AXI4", 0.5))
            graph.add_interconnect(Interconnect("sram_256k", "cpu_core",
                SignalDomain.DIGITAL, 32.0, 1.0, "AXI4", 0.5))

        # CPU → Flash
        if has("cpu_core") and has("flash_2m"):
            graph.add_interconnect(Interconnect("cpu_core", "flash_2m",
                SignalDomain.DIGITAL, 4.0, 50.0, "QSPI", 0.2))

        # DMA ↔ SRAM
        if has("dma_ctrl") and has("sram_256k"):
            graph.add_interconnect(Interconnect("dma_ctrl", "sram_256k",
                SignalDomain.DIGITAL, 16.0, 2.0, "AXI4", 0.3))

        # ADC → DMA or CPU
        if has("adc_12b"):
            target = "dma_ctrl" if has("dma_ctrl") else "cpu_core"
            if has(target):
                graph.add_interconnect(Interconnect("adc_12b", target,
                    SignalDomain.ANALOG, 0.1, 1000.0, "SPI", 0.05))

        # CPU → Peripheral bus
        for peri in ["uart_ip", "spi_master", "i2c_ctrl", "can_ctrl",
                     "gpio_bank", "timer_wdg", "interrupt_ctrl"]:
            if has("cpu_core") and has(peri):
                graph.add_interconnect(Interconnect("cpu_core", peri,
                    SignalDomain.DIGITAL, 0.5, 5.0, "APB", 0.02))

        # NPU ↔ SRAM
        if has("npu") and has("sram_256k"):
            graph.add_interconnect(Interconnect("npu", "sram_256k",
                SignalDomain.DIGITAL, 64.0, 2.0, "AXI4", 1.0))

        # Radar frontend → ADC
        if has("radar_fend") and has("adc_12b"):
            graph.add_interconnect(Interconnect("radar_fend", "adc_12b",
                SignalDomain.ANALOG, 1.0, 10.0, "LVDS", 0.5))

        # DSP ↔ SRAM
        if has("dsp_core") and has("sram_256k"):
            graph.add_interconnect(Interconnect("dsp_core", "sram_256k",
                SignalDomain.DIGITAL, 16.0, 2.0, "AXI4", 0.3))

        # PMU → everything (power rails)
        if has("pmu"):
            for ip_id in list(graph.ip_blocks.keys()):
                if ip_id != "pmu":
                    graph.add_interconnect(Interconnect("pmu", ip_id,
                        SignalDomain.POWER, 0.0, 0.0, "power_rail", 0.0))
