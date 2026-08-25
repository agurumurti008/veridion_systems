"""
core/spec_kg/knowledge_graph.py
Specification Knowledge Graph (SpecKG) backed by NetworkX.
"""
import json
import math
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum

try:
    import networkx as nx
except ImportError:
    nx = None


# ─── Enums ──────────────────────────────────────────────────────────────────

class PortType(str, Enum):
    input = "input"
    output = "output"
    inout = "inout"
    supply = "supply"
    ground = "ground"
    reference = "reference"
    control = "control"
    clock = "clock"
    enable = "enable"


class PortDomain(str, Enum):
    analog = "analog"
    digital = "digital"
    mixed = "mixed"
    power = "power"


class SpecType(str, Enum):
    dc = "dc"
    ac = "ac"
    transient = "transient"
    noise = "noise"
    psrr = "psrr"
    cmrr = "cmrr"
    snr = "snr"
    thd = "thd"
    settling = "settling"
    slew = "slew"
    stability = "stability"


class RuleType(str, Enum):
    KCL = "KCL"
    KVL = "KVL"
    energy = "energy"
    passivity = "passivity"
    stability = "stability"
    feedback = "feedback"


# ─── Dataclasses ─────────────────────────────────────────────────────────────

@dataclass
class Port:
    name: str
    port_type: str  # PortType value
    domain: str     # PortDomain value
    voltage_range: Tuple[float, float] = (0.0, 5.0)
    current_range: Tuple[float, float] = (0.0, 1.0)
    is_state_signal: bool = False
    fsm_role: Optional[str] = None  # 'enable','ready','fault','startup','mode'
    direction: Optional[str] = None  # 'input'|'output'|'inout'; None → derived
                                     # from port_type (see port_direction)


def port_direction(port) -> str:
    """Signal direction of a port at the DUT boundary: 'input', 'output'
    or 'inout'. An explicit Port.direction wins; otherwise derived from
    port_type — output/status pins are DUT-driven indicators, supply/
    ground/bulk rails are bidirectional, everything else is externally
    driven. This is the single source of FSM causality: only non-output
    ports may become state variables or guard features."""
    d = getattr(port, 'direction', None)
    if d in ('input', 'output', 'inout'):
        return d
    pt = port.port_type
    if pt in (PortType.output.value, 'status'):
        return 'output'
    if pt in (PortType.inout.value, PortType.supply.value,
              PortType.ground.value, 'bulk'):
        return 'inout'
    return 'input'


@dataclass
class SpecConstraint:
    spec_type: str        # SpecType value
    name: str
    min_val: float
    max_val: float
    nominal: float
    unit: str
    frequency: float = 0.0
    condition: str = ""
    transient_weight: float = 0.5


@dataclass
class PhysicsRule:
    rule_type: str   # RuleType value
    nodes: List[str]
    equation: str
    tolerance: float = 1e-6


# ─── Analysis-to-Transient Bridge Map ────────────────────────────────────────

ANALYSIS_BRIDGE_MAP = {
    "AC.phase_margin": {
        "transient_effect": "overshoot_percent",
        "formula": "exp(-pi*zeta/sqrt(1-zeta**2))*100  where zeta=PM/100",
        "enabled": True,
        "transient_weight": 0.8,
    },
    "AC.gain_bandwidth": {
        "transient_effect": "settling_time",
        "formula": "-ln(0.02)/(zeta*wn)",
        "enabled": True,
        "transient_weight": 0.7,
    },
    "AC.unity_gain_freq": {
        "transient_effect": "rise_time",
        "formula": "0.35/BW_3dB",
        "enabled": True,
        "transient_weight": 0.6,
    },
    "PSRR.psrr_dc": {
        "transient_effect": "supply_ripple_at_output",
        "formula": "V_ripple_in / 10^(PSRR_dB/20)",
        "enabled": True,
        "transient_weight": 0.5,
    },
    "NOISE.thermal_noise": {
        "transient_effect": "wideband_noise_floor",
        "formula": "sigma_v = sqrt(kT/C)",
        "enabled": True,
        "transient_weight": 0.4,
    },
    "DC.operating_point": {
        "transient_effect": "initial_condition",
        "formula": "x0 = DC_OP(params)",
        "enabled": True,
        "transient_weight": 0.9,
    },
    "CMRR.cmrr_dc": {
        "transient_effect": "cm_disturbance_rejection",
        "formula": "V_cm_out = V_cm_in / 10^(CMRR/20)",
        "enabled": False,
        "transient_weight": 0.3,
    },
}

BRIDGE_PREFIX_MAP = {
    "AC": ["AC.phase_margin", "AC.gain_bandwidth", "AC.unity_gain_freq"],
    "PSRR": ["PSRR.psrr_dc"],
    "NOISE": ["NOISE.thermal_noise"],
    "DC": ["DC.operating_point"],
    "CMRR": ["CMRR.cmrr_dc"],
}


class SpecKG:
    """Specification Knowledge Graph backed by NetworkX."""

    def __init__(self, ip_type: str = "LDO"):
        self.ip_type = ip_type
        self.ports: List[Port] = []
        self.specs: List[SpecConstraint] = []
        self.physics_rules: List[PhysicsRule] = []
        self.fsm_states: List[str] = []
        self.bridges: Dict[str, Dict] = {k: dict(v) for k, v in ANALYSIS_BRIDGE_MAP.items()}
        self.signal_map = None  # Optional[digitwin.spec_signal_map.SignalMap]
        if nx:
            self.graph = nx.DiGraph()
        else:
            self.graph = None

    def apply_signal_map(self, signal_map) -> None:
        """Attach a digitwin.spec_signal_map.SignalMap to this SpecKG so
        downstream FSM/Phase2 BLUT ingestion can resolve Port/SpecConstraint
        names to BLUT signal names. Does not validate coverage — call
        signal_map.print_unmapped_warning(self) separately if desired."""
        self.signal_map = signal_map

    def add_port(self, port: Port):
        self.ports.append(port)
        if self.graph is not None:
            self.graph.add_node(f"port:{port.name}", kind="port", data=port)
            for spec in self.specs:
                self.graph.add_edge(f"spec:{spec.name}", f"port:{port.name}", rel="constrains")

    def add_spec(self, spec: SpecConstraint):
        self.specs.append(spec)
        if self.graph is not None:
            self.graph.add_node(f"spec:{spec.name}", kind="spec", data=spec)
            for port in self.ports:
                self.graph.add_edge(f"spec:{spec.name}", f"port:{port.name}", rel="constrains")

    def add_physics_rule(self, rule: PhysicsRule):
        self.physics_rules.append(rule)

    def get_fsm_relevant_ports(self) -> List[Port]:
        result = []
        for p in self.ports:
            if p.is_state_signal:
                result.append(p)
            elif p.port_type in (PortType.enable.value, PortType.clock.value, PortType.control.value):
                result.append(p)
        return result

    def get_fsm_input_ports(self) -> List[Port]:
        """FSM-relevant ports that may legally drive state identification
        and transition guards (direction input/inout). Output-direction
        indicator pins are excluded — a DUT-driven status pin is an effect
        of the state, never a cause."""
        return [p for p in self.get_fsm_relevant_ports()
                if port_direction(p) != 'output']

    def get_fsm_output_ports(self) -> List[Port]:
        """FSM-relevant output-direction ports (status/ready/fault
        indicators). Observed per detected state as output signatures and
        checked for consistency — never state variables or guard features."""
        return [p for p in self.get_fsm_relevant_ports()
                if port_direction(p) == 'output']

    def get_physics_loss_terms(self) -> List[Dict]:
        terms = []
        for rule in self.physics_rules:
            terms.append({
                "type": rule.rule_type,
                "nodes": rule.nodes,
                "equation": rule.equation,
                "tolerance": rule.tolerance,
                "weight": 1.0,
            })
        return terms

    def get_active_analysis_bridges(self, user_selections: Dict[str, bool]) -> Dict[str, Dict]:
        active = {}
        for key, bridge in self.bridges.items():
            if user_selections.get(key, bridge.get("enabled", False)):
                active[key] = bridge
        return active

    def get_bridges_for_keys(self, keys: List[str]) -> Dict[str, Dict]:
        """Get bridges matching a list of prefix keys like ['AC','PSRR','DC']."""
        active = {}
        for prefix in keys:
            if prefix == "all":
                return dict(self.bridges)
            bridge_keys = BRIDGE_PREFIX_MAP.get(prefix, [])
            for bk in bridge_keys:
                if bk in self.bridges:
                    active[bk] = self.bridges[bk]
        return active

    def export_to_json(self, path: str):
        def _port_to_dict(p: Port) -> dict:
            return {
                "name": p.name,
                "port_type": p.port_type,
                "domain": p.domain,
                "voltage_range": list(p.voltage_range),
                "current_range": list(p.current_range),
                "is_state_signal": p.is_state_signal,
                "fsm_role": p.fsm_role,
                "direction": p.direction,
            }

        def _spec_to_dict(s: SpecConstraint) -> dict:
            return {
                "spec_type": s.spec_type,
                "name": s.name,
                "min_val": s.min_val,
                "max_val": s.max_val,
                "nominal": s.nominal,
                "unit": s.unit,
                "frequency": s.frequency,
                "condition": s.condition,
                "transient_weight": s.transient_weight,
            }

        def _rule_to_dict(r: PhysicsRule) -> dict:
            return {
                "rule_type": r.rule_type,
                "nodes": r.nodes,
                "equation": r.equation,
                "tolerance": r.tolerance,
            }

        data = {
            "ip_type": self.ip_type,
            "ports": [_port_to_dict(p) for p in self.ports],
            "specs": [_spec_to_dict(s) for s in self.specs],
            "physics_rules": [_rule_to_dict(r) for r in self.physics_rules],
            "fsm_states": self.fsm_states,
            "bridges": self.bridges,
        }
        if self.signal_map is not None and getattr(self.signal_map, "entries", None):
            data["signal_map"] = self.signal_map.to_json_list()
        with open(path, "w", encoding='utf-8') as f:
            json.dump(data, f, indent=2)

    @classmethod
    def from_json(cls, path: str) -> "SpecKG":
        with open(path, encoding='utf-8') as f:
            data = json.load(f)
        kg = cls(ip_type=data["ip_type"])
        for pd in data["ports"]:
            kg.add_port(Port(
                name=pd["name"],
                port_type=pd["port_type"],
                domain=pd["domain"],
                voltage_range=tuple(pd["voltage_range"]),
                current_range=tuple(pd["current_range"]),
                is_state_signal=pd["is_state_signal"],
                fsm_role=pd.get("fsm_role"),
                direction=pd.get("direction"),
            ))
        for sd in data["specs"]:
            kg.add_spec(SpecConstraint(
                spec_type=sd["spec_type"],
                name=sd["name"],
                min_val=sd["min_val"],
                max_val=sd["max_val"],
                nominal=sd["nominal"],
                unit=sd["unit"],
                frequency=sd.get("frequency", 0.0),
                condition=sd.get("condition", ""),
                transient_weight=sd.get("transient_weight", 0.5),
            ))
        for rd in data.get("physics_rules", []):
            kg.add_physics_rule(PhysicsRule(
                rule_type=rd["rule_type"],
                nodes=rd["nodes"],
                equation=rd["equation"],
                tolerance=rd.get("tolerance", 1e-6),
            ))
        kg.fsm_states = data.get("fsm_states", [])
        if "bridges" in data:
            kg.bridges = data["bridges"]

        if "signal_map" in data:
            # Lazy import: core/spec_kg must not hard-depend on digitwin/ at
            # module load time (digitwin/spec_signal_map has no reverse
            # dependency on core/, but keeping this import lazy avoids any
            # import-order fragility for callers that only need core/).
            from digitwin.spec_signal_map import SignalMap, SignalMapEntry
            entries = [
                SignalMapEntry(
                    speckg_name=e["speckg_name"],
                    blut_signal=e["blut_signal"],
                    kind=e.get("kind", "voltage"),
                    run_scope=e.get("run_scope"),
                )
                for e in data["signal_map"]
            ]
            kg.signal_map = SignalMap(entries)

        return kg

    def summary(self):
        print(f"\n{'='*60}")
        print(f"SpecKG Summary — IP Type: {self.ip_type}")
        print(f"{'='*60}")
        print(f"\nPORTS ({len(self.ports)}):")
        print(f"  {'Name':<20} {'Type':<12} {'Domain':<10} {'FSM Role':<12} {'State?'}")
        print(f"  {'-'*70}")
        for p in self.ports:
            print(f"  {p.name:<20} {p.port_type:<12} {p.domain:<10} "
                  f"{str(p.fsm_role):<12} {p.is_state_signal}")

        print(f"\nSPECS ({len(self.specs)}):")
        print(f"  {'Name':<25} {'Type':<12} {'Min':<10} {'Nom':<10} {'Max':<10} {'Unit'}")
        print(f"  {'-'*80}")
        for s in self.specs:
            print(f"  {s.name:<25} {s.spec_type:<12} {s.min_val:<10.3g} "
                  f"{s.nominal:<10.3g} {s.max_val:<10.3g} {s.unit}")

        print(f"\nPHYSICS RULES ({len(self.physics_rules)}):")
        for r in self.physics_rules:
            print(f"  [{r.rule_type}] {r.equation}")

        print(f"\nFSM STATES ({len(self.fsm_states)}): {self.fsm_states}")

        active_bridges = [k for k, v in self.bridges.items() if v.get("enabled", False)]
        print(f"\nACTIVE BRIDGES ({len(active_bridges)}): {active_bridges}")
        print()


# ─── Built-in IP Builders ─────────────────────────────────────────────────────

def build_ldo_kg() -> SpecKG:
    kg = SpecKG(ip_type="LDO")

    # Ports
    kg.add_port(Port("VIN", "supply", "power", (1.5, 6.0), (0.0, 2.0), False, None))
    kg.add_port(Port("VOUT", "output", "analog", (0.5, 5.0), (0.0, 1.5), False, None))
    kg.add_port(Port("GND", "ground", "power", (0.0, 0.0), (0.0, 5.0), False, None))
    kg.add_port(Port("EN", "enable", "digital", (0.0, 1.8), (0.0, 1e-3), True, "enable"))
    kg.add_port(Port("POK", "output", "digital", (0.0, 1.8), (0.0, 1e-3), True, "ready"))
    kg.add_port(Port("FAULT", "output", "digital", (0.0, 1.8), (0.0, 1e-3), True, "fault"))

    # Specs
    kg.add_spec(SpecConstraint("dc", "Output_Voltage", 1.75, 1.85, 1.80, "V", 0, "Iload=100mA", 0.9))
    kg.add_spec(SpecConstraint("dc", "Dropout_Voltage", 0.0, 0.35, 0.20, "V", 0, "Iload=500mA", 0.7))
    kg.add_spec(SpecConstraint("dc", "Quiescent_Current", 0.0, 0.10, 0.05, "mA", 0, "no load", 0.3))
    kg.add_spec(SpecConstraint("psrr", "PSRR_1kHz", 60.0, 120.0, 80.0, "dB", 1e3, "", 0.6))
    kg.add_spec(SpecConstraint("psrr", "PSRR_1MHz", 30.0, 80.0, 50.0, "dB", 1e6, "", 0.5))
    kg.add_spec(SpecConstraint("stability", "Phase_Margin", 45.0, 90.0, 60.0, "deg", 0, "", 0.8))
    kg.add_spec(SpecConstraint("noise", "Output_Noise", 0.0, 50.0, 20.0, "uVrms", 0, "10Hz-100kHz", 0.4))
    kg.add_spec(SpecConstraint("dc", "Load_Regulation", 0.0, 5.0, 2.0, "mV/A", 0, "", 0.5))
    kg.add_spec(SpecConstraint("transient", "Load_Transient_Peak", 0.0, 100.0, 50.0, "mV", 0, "0-500mA step", 0.9))
    kg.add_spec(SpecConstraint("transient", "Settling_Time", 0.0, 10.0, 5.0, "us", 0, "to 1%", 0.8))

    # Physics rules
    kg.add_physics_rule(PhysicsRule("KCL", ["VOUT", "GND"], "I_pass - I_load - I_feedback = 0", 1e-6))
    kg.add_physics_rule(PhysicsRule("KVL", ["VIN", "VOUT"], "V_vin - V_dropout - V_vout = 0", 1e-3))
    kg.add_physics_rule(PhysicsRule("energy", ["VIN", "VOUT"], "P_in >= P_out", 1e-6))
    kg.add_physics_rule(PhysicsRule("feedback", ["VOUT"], "V_vout = V_vref*(1 + Rf1/Rf2)", 1e-3))

    kg.fsm_states = ["DISABLED", "STARTUP", "REGULATION", "DROPOUT", "FAULT", "SHUTDOWN"]
    return kg


def build_ota_kg() -> SpecKG:
    kg = SpecKG(ip_type="OTA")

    kg.add_port(Port("VINP", "input", "analog", (0.0, 3.3), (0.0, 1e-6), False, None))
    kg.add_port(Port("VINN", "input", "analog", (0.0, 3.3), (0.0, 1e-6), False, None))
    kg.add_port(Port("VOUT", "output", "analog", (0.0, 3.3), (-1e-2, 1e-2), False, None))
    kg.add_port(Port("VDD", "supply", "power", (1.8, 3.6), (0.0, 5e-3), False, None))
    kg.add_port(Port("VSS", "ground", "power", (0.0, 0.0), (0.0, 5e-3), False, None))
    kg.add_port(Port("EN", "enable", "digital", (0.0, 1.8), (0.0, 1e-4), True, "enable"))

    kg.add_spec(SpecConstraint("ac", "GBW", 10.0, 200.0, 50.0, "MHz", 0, "", 0.7))
    kg.add_spec(SpecConstraint("stability", "Phase_Margin", 45.0, 90.0, 65.0, "deg", 0, "", 0.8))
    kg.add_spec(SpecConstraint("cmrr", "CMRR", 60.0, 120.0, 80.0, "dB", 0, "", 0.5))
    kg.add_spec(SpecConstraint("psrr", "PSRR", 50.0, 100.0, 70.0, "dB", 0, "", 0.5))
    kg.add_spec(SpecConstraint("slew", "Slew_Rate", 10.0, 500.0, 50.0, "V/us", 0, "", 0.6))
    kg.add_spec(SpecConstraint("dc", "Offset_Voltage", 0.0, 5.0, 1.0, "mV", 0, "", 0.4))
    kg.add_spec(SpecConstraint("dc", "Gm", 0.5, 20.0, 5.0, "mA/V", 0, "", 0.6))
    kg.add_spec(SpecConstraint("dc", "Output_Resistance", 10.0, 10000.0, 1000.0, "kOhm", 0, "", 0.5))

    kg.add_physics_rule(PhysicsRule("KCL", ["VOUT"], "I_out = Gm*V_diff - V_out/R_out", 1e-6))
    kg.add_physics_rule(PhysicsRule("stability", ["VOUT"], "GBW = Gm/(2*pi*C_L)", 1e6))
    kg.add_physics_rule(PhysicsRule("slew", ["VOUT"], "SR = I_tail/C_L", 1e6))
    kg.add_physics_rule(PhysicsRule("KCL", ["VINP", "VINN"], "CMRR = 20*log10(A_diff/A_cm)", 1.0))

    kg.fsm_states = ["DISABLED", "STARTUP", "ACTIVE", "SLEWING", "SETTLED"]
    return kg


def build_dcdc_kg() -> SpecKG:
    kg = SpecKG(ip_type="DCDC")

    kg.add_port(Port("VIN", "supply", "power", (3.0, 15.0), (0.0, 5.0), False, None))
    kg.add_port(Port("VOUT", "output", "analog", (0.5, 5.0), (0.0, 3.0), False, None))
    kg.add_port(Port("SW", "output", "mixed", (0.0, 15.0), (-5.0, 5.0), True, "mode"))
    kg.add_port(Port("EN", "enable", "digital", (0.0, 5.0), (0.0, 1e-3), True, "enable"))
    kg.add_port(Port("PG", "output", "digital", (0.0, 5.0), (0.0, 1e-3), True, "ready"))
    kg.add_port(Port("GND", "ground", "power", (0.0, 0.0), (0.0, 10.0), False, None))

    kg.add_spec(SpecConstraint("dc", "Output_Voltage", 1.75, 1.85, 1.80, "V", 0, "", 0.9))
    kg.add_spec(SpecConstraint("dc", "Efficiency", 80.0, 99.0, 92.0, "%", 0, "full load", 0.5))
    kg.add_spec(SpecConstraint("transient", "Output_Ripple", 0.0, 50.0, 20.0, "mV", 0, "", 0.8))
    kg.add_spec(SpecConstraint("stability", "Phase_Margin", 45.0, 90.0, 60.0, "deg", 0, "", 0.7))
    kg.add_spec(SpecConstraint("ac", "Crossover_Frequency", 10.0, 200.0, 80.0, "kHz", 0, "", 0.6))

    kg.add_physics_rule(PhysicsRule("energy", ["VIN", "VOUT"], "V_out/V_in = D (buck CCM)", 1e-3))
    kg.add_physics_rule(PhysicsRule("KVL", ["SW", "VIN", "VOUT"], "V_L = V_in - V_out (during ton)", 1e-3))
    kg.add_physics_rule(PhysicsRule("KCL", ["VOUT"], "I_L_min > 0 implies CCM", 1e-3))

    kg.fsm_states = ["DISABLED", "SOFT_START", "CCM", "DCM", "FAULT", "HICCUP"]
    return kg
