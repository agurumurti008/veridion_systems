"""
parsers/__init__.py  —  Netlist parsers for SPICE and Spectre formats.

Outputs a canonical ParsedNetlist dataclass that is technology- and
simulator-agnostic, containing:
  - instances  : list of Component objects
  - nets       : list of net names
  - pins       : list of Pin objects (power, ground, signal, control)
  - technology : string label e.g. "180nm"
  - analyses   : dict of requested simulation analyses
"""

from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


# ─────────────────────────────────────────────────────────────────────────────
# Canonical data structures
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class Component:
    """Single circuit component parsed from netlist."""
    instance_name : str               # raw name from netlist (M1, R3 …)
    comp_type     : str               # 'nmos','pmos','resistor','cap','ind','vsrc','isrc','sub'
    model         : str               # model/subckt name
    nets          : List[str]         # ordered net connections
    params        : Dict[str, float]  # w, l, r, c, …
    # derived, filled in by CircuitGraph
    canonical_id  : str = ""          # type + index (e.g. nmos_0)


@dataclass
class Pin:
    """Top-level port of the circuit."""
    name     : str
    net      : str
    pin_type : str   # 'power','ground','signal_in','signal_out','control','bias'


@dataclass
class ParsedNetlist:
    """Simulator-agnostic parsed netlist."""
    title      : str
    technology : str
    components : List[Component]     = field(default_factory=list)
    nets       : List[str]           = field(default_factory=list)
    pins       : List[Pin]           = field(default_factory=list)
    subckt_name: str                 = ""
    analyses   : Dict[str, dict]     = field(default_factory=dict)
    raw_text   : str                 = ""


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

_SI = {"f":1e-15,"p":1e-12,"n":1e-9,"u":1e-6,"m":1e-3,
       "k":1e3,"meg":1e6,"g":1e9,"t":1e12}

def _parse_value(s: str) -> float:
    """Convert SPICE value string ('10k', '2.5u', '1meg') → float."""
    s = s.strip().lower()
    for suffix, mult in sorted(_SI.items(), key=lambda x: -len(x[0])):
        if s.endswith(suffix):
            try:
                return float(s[:-len(suffix)]) * mult
            except ValueError:
                return 0.0
    try:
        return float(s)
    except ValueError:
        return 0.0


def _infer_pin_type(name: str) -> str:
    n = name.lower()
    if any(k in n for k in ["vdd","vcc","supply","pwr","vp"]):  return "power"
    if any(k in n for k in ["vss","gnd","ground","vn"]):        return "ground"
    if any(k in n for k in ["in","inp","inn","vin"]):           return "signal_in"
    if any(k in n for k in ["out","vout","outp","outn"]):       return "signal_out"
    if any(k in n for k in ["bias","ib","vbias"]):              return "bias"
    if any(k in n for k in ["en","ctrl","sel","clk"]):          return "control"
    return "signal_in"


# ─────────────────────────────────────────────────────────────────────────────
# SPICE Parser
# ─────────────────────────────────────────────────────────────────────────────

class SpiceParser:
    """
    Parses SPICE-family netlists (.sp, .spi, .cir).

    Supports:
      M  — MOSFET (NMOS / PMOS detected from model name)
      R  — Resistor
      C  — Capacitor
      L  — Inductor
      V  — Voltage source
      I  — Current source
      X  — Subcircuit call
      .subckt / .ends
      .param
      .op / .ac / .tran / .noise / .dc
    """

    def parse(self, path: str, technology: str = "180nm") -> ParsedNetlist:
        with open(path, "r") as fh:
            raw = fh.read()
        return self.parse_text(raw, technology=technology)

    def parse_text(self, text: str, technology: str = "180nm") -> ParsedNetlist:
        lines   = self._preprocess(text)
        netlist = ParsedNetlist(title="", technology=technology, raw_text=text)

        global_params: Dict[str, float] = {}
        inside_subckt = False
        subckt_ports : List[str] = []

        for line in lines:
            tl = line.strip()
            if not tl or tl.startswith("*"):
                continue

            up = tl.upper()

            # ── title line ──
            if netlist.title == "" and not tl.startswith(".") and not tl[0].isalpha():
                netlist.title = tl
                continue

            # ── .title ──
            if up.startswith(".TITLE"):
                netlist.title = tl[6:].strip()

            # ── .subckt ──
            elif up.startswith(".SUBCKT"):
                parts = tl.split()
                netlist.subckt_name = parts[1]
                subckt_ports = parts[2:]
                inside_subckt = True
                for p in subckt_ports:
                    netlist.pins.append(Pin(
                        name=p, net=p,
                        pin_type=_infer_pin_type(p)
                    ))

            elif up.startswith(".ENDS"):
                inside_subckt = False

            # ── .param ──
            elif up.startswith(".PARAM"):
                for m in re.finditer(r'(\w+)\s*=\s*([\w.]+)', tl[6:]):
                    global_params[m.group(1)] = _parse_value(m.group(2))

            # ── analyses ──
            elif up.startswith(".OP"):
                netlist.analyses["dc_op"] = {}
            elif up.startswith(".AC"):
                netlist.analyses["ac"] = self._parse_ac(tl)
            elif up.startswith(".TRAN"):
                netlist.analyses["transient"] = self._parse_tran(tl)
            elif up.startswith(".NOISE"):
                netlist.analyses["noise"] = {}
            elif up.startswith(".DC"):
                netlist.analyses["dc_sweep"] = {}

            # ── devices ──
            elif tl[0].upper() == "M":
                comp = self._parse_mosfet(tl, global_params)
                if comp: netlist.components.append(comp)

            elif tl[0].upper() == "R":
                comp = self._parse_passive(tl, "resistor", global_params)
                if comp: netlist.components.append(comp)

            elif tl[0].upper() == "C":
                comp = self._parse_passive(tl, "capacitor", global_params)
                if comp: netlist.components.append(comp)

            elif tl[0].upper() == "L":
                comp = self._parse_passive(tl, "inductor", global_params)
                if comp: netlist.components.append(comp)

            elif tl[0].upper() == "V":
                comp = self._parse_vsrc(tl)
                if comp: netlist.components.append(comp)

            elif tl[0].upper() == "I":
                comp = self._parse_isrc(tl)
                if comp: netlist.components.append(comp)

            elif tl[0].upper() == "X":
                comp = self._parse_subcall(tl)
                if comp: netlist.components.append(comp)

        # collect all nets
        all_nets = set()
        for c in netlist.components:
            all_nets.update(c.nets)
        for p in netlist.pins:
            all_nets.add(p.net)
        netlist.nets = sorted(all_nets)

        # assign canonical IDs
        counters: Dict[str, int] = {}
        for c in netlist.components:
            counters[c.comp_type] = counters.get(c.comp_type, 0)
            c.canonical_id = f"{c.comp_type}_{counters[c.comp_type]}"
            counters[c.comp_type] += 1

        return netlist

    # ── internal helpers ──────────────────────────────────────────────────────

    def _preprocess(self, text: str) -> List[str]:
        """Join continuation lines (+), strip comments."""
        lines = text.replace("\r\n", "\n").split("\n")
        joined, buf = [], ""
        for ln in lines:
            if ln.startswith("+"):
                buf += " " + ln[1:]
            else:
                if buf: joined.append(buf)
                buf = ln
        if buf: joined.append(buf)
        return joined

    def _parse_mosfet(self, line: str, gp: dict) -> Optional[Component]:
        parts = line.split()
        if len(parts) < 5: return None
        name  = parts[0]
        nets  = parts[1:5]   # drain gate source body
        model = parts[5] if len(parts) > 5 else "nmos"
        ctype = "pmos" if any(k in model.lower() for k in ["p","pch","pfet"]) else "nmos"
        params = self._extract_kv(parts[6:], gp)
        return Component(instance_name=name, comp_type=ctype, model=model,
                         nets=nets, params=params)

    def _parse_passive(self, line: str, ctype: str, gp: dict) -> Optional[Component]:
        parts = line.split()
        if len(parts) < 4: return None
        name  = parts[0]
        nets  = parts[1:3]
        val   = _parse_value(parts[3])
        key   = {"resistor":"r","capacitor":"c","inductor":"l"}[ctype]
        return Component(instance_name=name, comp_type=ctype, model=ctype,
                         nets=nets, params={key: val})

    def _parse_vsrc(self, line: str) -> Optional[Component]:
        parts = line.split()
        if len(parts) < 3: return None
        return Component(instance_name=parts[0], comp_type="vsrc", model="vsrc",
                         nets=parts[1:3], params={"v": _parse_value(parts[3]) if len(parts)>3 else 0})

    def _parse_isrc(self, line: str) -> Optional[Component]:
        parts = line.split()
        if len(parts) < 3: return None
        return Component(instance_name=parts[0], comp_type="isrc", model="isrc",
                         nets=parts[1:3], params={"i": _parse_value(parts[3]) if len(parts)>3 else 0})

    def _parse_subcall(self, line: str) -> Optional[Component]:
        parts = line.split()
        if len(parts) < 3: return None
        # last part before params is model name
        model = parts[-1] if "=" not in parts[-1] else "unknown"
        return Component(instance_name=parts[0], comp_type="sub", model=model,
                         nets=parts[1:-1], params={})

    def _extract_kv(self, tokens: List[str], gp: dict) -> Dict[str, float]:
        out = {}
        for t in tokens:
            m = re.match(r'(\w+)\s*=\s*([\w.]+)', t)
            if m:
                val = gp.get(m.group(2), _parse_value(m.group(2)))
                out[m.group(1).lower()] = val
        return out

    def _parse_ac(self, line: str) -> dict:
        parts = line.split()
        return {"type": parts[1] if len(parts)>1 else "dec",
                "points": int(parts[2]) if len(parts)>2 else 10,
                "fstart": _parse_value(parts[3]) if len(parts)>3 else 1,
                "fstop":  _parse_value(parts[4]) if len(parts)>4 else 1e9}

    def _parse_tran(self, line: str) -> dict:
        parts = line.split()
        return {"tstep": _parse_value(parts[1]) if len(parts)>1 else 1e-9,
                "tstop": _parse_value(parts[2]) if len(parts)>2 else 1e-6}


# ─────────────────────────────────────────────────────────────────────────────
# Spectre Parser  (thin wrapper — maps Spectre syntax to same dataclass)
# ─────────────────────────────────────────────────────────────────────────────

class SpectreParser:
    """
    Parses Cadence Spectre netlists.
    Key differences from SPICE:
      - instance_name (model) net1 net2 … key=value
      - `parameters` statement
      - `subckt` / `ends`
    """

    def parse(self, path: str, technology: str = "180nm") -> ParsedNetlist:
        with open(path, "r") as fh:
            raw = fh.read()
        return self.parse_text(raw, technology=technology)

    def parse_text(self, text: str, technology: str = "180nm") -> ParsedNetlist:
        lines   = [l.strip() for l in text.split("\n")]
        netlist = ParsedNetlist(title="spectre_netlist",
                                technology=technology, raw_text=text)
        global_params: Dict[str, float] = {}

        for line in lines:
            if not line or line.startswith("//") or line.startswith("*"):
                continue
            up = line.upper()

            if up.startswith("SUBCKT") or up.startswith("MODULE"):
                parts = line.split()
                netlist.subckt_name = parts[1]
                for p in parts[2:]:
                    netlist.pins.append(Pin(name=p, net=p,
                                            pin_type=_infer_pin_type(p)))
            elif up.startswith("PARAMETERS") or up.startswith("PARAMS"):
                for m in re.finditer(r'(\w+)\s*=\s*([\w.]+)', line):
                    global_params[m.group(1)] = _parse_value(m.group(2))
            else:
                comp = self._parse_instance(line, global_params)
                if comp:
                    netlist.components.append(comp)

        all_nets = set()
        for c in netlist.components:
            all_nets.update(c.nets)
        netlist.nets = sorted(all_nets)

        counters: Dict[str, int] = {}
        for c in netlist.components:
            counters[c.comp_type] = counters.get(c.comp_type, 0)
            c.canonical_id = f"{c.comp_type}_{counters[c.comp_type]}"
            counters[c.comp_type] += 1

        return netlist

    def _parse_instance(self, line: str, gp: dict) -> Optional[Component]:
        # Spectre: inst_name (net1 net2 ..) model_name key=val ...
        m = re.match(r'(\S+)\s+\(([^)]*)\)\s+(\S+)(.*)', line)
        if m:
            name  = m.group(1)
            nets  = m.group(2).split()
            model = m.group(3)
            rest  = m.group(4)
            params: Dict[str, float] = {}
            for kv in re.finditer(r'(\w+)\s*=\s*([\w.]+)', rest):
                params[kv.group(1).lower()] = _parse_value(kv.group(2))
            ctype = self._infer_type(model)
            return Component(instance_name=name, comp_type=ctype, model=model,
                             nets=nets, params=params)
        return None

    def _infer_type(self, model: str) -> str:
        ml = model.lower()
        if any(k in ml for k in ["nmos","nfet","nch"]): return "nmos"
        if any(k in ml for k in ["pmos","pfet","pch"]): return "pmos"
        if ml.startswith("r")                         : return "resistor"
        if ml.startswith("c")                         : return "capacitor"
        if ml.startswith("l")                         : return "inductor"
        return "sub"
