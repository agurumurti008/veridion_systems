"""
core/__init__.py  —  CircuitGraph and FeatureExtractor

CircuitGraph
  • Converts ParsedNetlist → NetworkX graph + PyG Data object
  • Nodes  = components  (features: type-one-hot, size params)
  • Edges  = net connections between components
  • Name-independent: uses canonical_id ordering

FeatureExtractor
  • Extracts flat feature vector X from a CircuitGraph
  • Technology encoding
  • Structural fingerprint (degree sequence, component counts)
  • Size parameters normalized per tech node
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import networkx as nx
import numpy as np

from analogml.parsers import ParsedNetlist, Component


# ─────────────────────────────────────────────────────────────────────────────
# Technology parameter database (rough typical values for normalization)
# ─────────────────────────────────────────────────────────────────────────────

TECH_DB: Dict[str, Dict] = {
    "180nm": {"lmin":180e-9, "vdd":1.8,  "tox":4e-9,  "vth_n":0.50, "vth_p":-0.50},
    "90nm":  {"lmin": 90e-9, "vdd":1.2,  "tox":2e-9,  "vth_n":0.35, "vth_p":-0.35},
    "65nm":  {"lmin": 65e-9, "vdd":1.0,  "tox":1.5e-9,"vth_n":0.30, "vth_p":-0.30},
    "45nm":  {"lmin": 45e-9, "vdd":1.0,  "tox":1.2e-9,"vth_n":0.28, "vth_p":-0.28},
    "28nm":  {"lmin": 28e-9, "vdd":0.9,  "tox":1.0e-9,"vth_n":0.25, "vth_p":-0.25},
    "14nm":  {"lmin": 14e-9, "vdd":0.8,  "tox":0.9e-9,"vth_n":0.22, "vth_p":-0.22},
}

COMP_TYPES = ["nmos","pmos","resistor","capacitor","inductor","vsrc","isrc","sub"]
PIN_TYPES  = ["power","ground","signal_in","signal_out","control","bias"]

COMP_TYPE_IDX = {t: i for i, t in enumerate(COMP_TYPES)}
PIN_TYPE_IDX  = {t: i for i, t in enumerate(PIN_TYPES)}

TECH_ORDER = list(TECH_DB.keys())   # for ordinal encoding
TECH_IDX   = {t: i for i, t in enumerate(TECH_ORDER)}


# ─────────────────────────────────────────────────────────────────────────────
# CircuitGraph
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class NodeFeatures:
    """Per-node feature vector for GNN."""
    comp_type_onehot  : np.ndarray   # len = len(COMP_TYPES)
    size_params       : np.ndarray   # [w_norm, l_norm, r_norm, c_norm, wl_ratio]
    degree            : float
    net_count         : int


class CircuitGraph:
    """
    Name-agnostic graph representation of a circuit.

    G nodes  : canonical component IDs  (e.g. "nmos_0", "resistor_2")
    G edges  : share at least one net
    G.graph  : global graph metadata (technology, pin features …)
    """

    def __init__(self):
        self.G            : nx.MultiGraph       = nx.MultiGraph()
        self.technology   : str                 = "180nm"
        self.components   : List[Component]     = []
        self.tech_params  : Dict                = {}
        self.pin_features : np.ndarray          = np.zeros(len(PIN_TYPES)*3)

    # ── constructor ───────────────────────────────────────────────────────────

    @classmethod
    def from_netlist(cls, netlist: ParsedNetlist,
                     technology: Optional[str] = None) -> "CircuitGraph":
        cg = cls()
        cg.technology  = technology or netlist.technology
        cg.tech_params = TECH_DB.get(cg.technology, TECH_DB["180nm"])
        cg.components  = netlist.components

        # ── add nodes ──
        for comp in netlist.components:
            feats = cg._node_features(comp)
            cg.G.add_node(comp.canonical_id,
                          comp_type=comp.comp_type,
                          model=comp.model,
                          params=comp.params,
                          features=feats)

        # ── add edges via shared nets ──
        net_to_comps: Dict[str, List[str]] = {}
        for comp in netlist.components:
            for net in comp.nets:
                net_to_comps.setdefault(net, []).append(comp.canonical_id)

        for net, cids in net_to_comps.items():
            for i in range(len(cids)):
                for j in range(i+1, len(cids)):
                    cg.G.add_edge(cids[i], cids[j], net=net)

        # ── pin aggregate feature vector ──
        pin_feat = np.zeros(len(PIN_TYPES))
        for p in netlist.pins:
            idx = PIN_TYPE_IDX.get(p.pin_type, 0)
            pin_feat[idx] += 1
        # normalize by total pins
        total = pin_feat.sum() or 1
        cg.pin_features = pin_feat / total

        # add degree back to node features
        for cid in cg.G.nodes:
            cg.G.nodes[cid]["features"].degree = float(cg.G.degree(cid))

        return cg

    # ── helpers ───────────────────────────────────────────────────────────────

    def _node_features(self, comp: Component) -> NodeFeatures:
        onehot  = np.zeros(len(COMP_TYPES))
        idx     = COMP_TYPE_IDX.get(comp.comp_type, len(COMP_TYPES)-1)
        onehot[idx] = 1.0

        lmin = self.tech_params.get("lmin", 180e-9)
        vdd  = self.tech_params.get("vdd",  1.8)

        w   = comp.params.get("w", lmin)
        l   = comp.params.get("l", lmin)
        r   = comp.params.get("r", 1e3)
        c   = comp.params.get("c", 1e-15)

        # log-normalize sizes relative to tech minimums
        def lognorm(v, ref):
            if v <= 0 or ref <= 0: return 0.0
            return math.log10(v/ref) / 3   # ±3 decades → ±1

        size = np.array([
            lognorm(w, lmin),
            lognorm(l, lmin),
            lognorm(r, 1e3),
            lognorm(c, 1e-15),
            lognorm(w/l if l>0 else 1, 1.0),  # W/L ratio
        ])
        return NodeFeatures(comp_type_onehot=onehot,
                            size_params=size,
                            degree=0.0,
                            net_count=len(comp.nets))

    def to_feature_matrix(self) -> Tuple[np.ndarray, np.ndarray]:
        """
        Returns (node_features, edge_index) suitable for GNN.
        node_features shape: (N, F)
        edge_index     shape: (2, E)
        """
        nodes = list(self.G.nodes)
        node_idx = {n: i for i, n in enumerate(nodes)}

        rows = []
        for n in nodes:
            nf: NodeFeatures = self.G.nodes[n]["features"]
            row = np.concatenate([
                nf.comp_type_onehot,          # 8
                nf.size_params,               # 5
                [nf.degree, nf.net_count],    # 2
            ])
            rows.append(row)

        X = np.stack(rows) if rows else np.zeros((0, 15))

        edges_src, edges_dst = [], []
        for u, v in self.G.edges():
            edges_src.append(node_idx[u])
            edges_dst.append(node_idx[v])
            edges_src.append(node_idx[v])
            edges_dst.append(node_idx[u])

        E = np.array([edges_src, edges_dst], dtype=np.int64) \
            if edges_src else np.zeros((2,0), dtype=np.int64)

        return X, E

    def structural_fingerprint(self) -> np.ndarray:
        """
        Fixed-size (64-d) structural fingerprint independent of instance names.
        Uses:
          • component type counts (8)
          • degree histogram (10 bins)
          • clustering coefficient stats (4)
          • connected component count (1)
          • diameter estimate (1)
          • total node/edge count (2)
          • WL graph hash fingerprint bits (38 → zeros-padded)
        """
        n = len(self.G.nodes)
        e = len(self.G.edges)

        # component counts
        type_counts = np.zeros(len(COMP_TYPES))
        for _, data in self.G.nodes(data=True):
            t = data.get("comp_type","sub")
            type_counts[COMP_TYPE_IDX.get(t, len(COMP_TYPES)-1)] += 1
        if n > 0: type_counts /= n

        # degree histogram
        degrees = [d for _, d in self.G.degree()]
        deg_hist, _ = np.histogram(degrees, bins=10, range=(0,20))
        deg_hist = deg_hist.astype(float) / (max(deg_hist.sum(),1))

        # clustering
        try:
            cc = nx.clustering(nx.Graph(self.G))
            cc_vals = list(cc.values())
            cc_stats = np.array([np.mean(cc_vals), np.std(cc_vals),
                                  np.min(cc_vals),  np.max(cc_vals)])
        except Exception:
            cc_stats = np.zeros(4)

        # global stats
        gcc = max(nx.connected_components(nx.Graph(self.G)), key=len, default=set())
        try:
            diam = nx.diameter(nx.Graph(self.G).subgraph(gcc)) / 20.0
        except Exception:
            diam = 0.0

        glob = np.array([
            len(list(nx.connected_components(nx.Graph(self.G)))) / max(n,1),
            diam,
            n / 100.0,
            e / 200.0,
        ])

        fp = np.concatenate([type_counts, deg_hist, cc_stats, glob])
        # pad / truncate to 64
        if len(fp) < 64:
            fp = np.concatenate([fp, np.zeros(64 - len(fp))])
        return fp[:64]


# ─────────────────────────────────────────────────────────────────────────────
# FeatureExtractor  — produces the flat X vector for ML models
# ─────────────────────────────────────────────────────────────────────────────

class FeatureExtractor:
    """
    Converts a CircuitGraph → flat feature vector X of fixed dimension.

    X = [tech_encoding (7) | structural_fp (64) | size_statistics (40) | pin_features (6)]
    Total dim = 117
    """

    FEATURE_DIM = 117

    def extract(self, cg: CircuitGraph) -> np.ndarray:
        tech  = self._tech_encoding(cg.technology)          # 7
        struc = cg.structural_fingerprint()                 # 64
        sizes = self._size_statistics(cg)                   # 40
        pins  = cg.pin_features                             # 6
        x = np.concatenate([tech, struc, sizes, pins])
        assert len(x) == self.FEATURE_DIM, f"dim mismatch {len(x)}"
        return x

    def _tech_encoding(self, tech: str) -> np.ndarray:
        """7-d: [ordinal/6, lmin_log, vdd_norm, tox_log, vth_n, |vth_p|, is_finfet]."""
        tp   = TECH_DB.get(tech, TECH_DB["180nm"])
        oidx = TECH_IDX.get(tech, 0) / max(len(TECH_ORDER)-1, 1)
        return np.array([
            oidx,
            math.log10(tp["lmin"] / 180e-9),   # negative = smaller node
            tp["vdd"] / 1.8,
            math.log10(tp["tox"] / 4e-9),
            tp["vth_n"],
            abs(tp["vth_p"]),
            1.0 if int(tech.replace("nm","")) <= 14 else 0.0,  # FinFET flag
        ])

    def _size_statistics(self, cg: CircuitGraph) -> np.ndarray:
        """
        Per-type size statistics: mean/std/min/max of W, L, W/L for
        nmos, pmos, resistor, capacitor, inductor  → 5 types × 8 stats = 40.
        """
        lmin = cg.tech_params.get("lmin", 180e-9)
        types_data: Dict[str, Dict[str, List]] = {
            t: {"w":[], "l":[], "wl":[], "r":[], "c":[], "v":[]}
            for t in ["nmos","pmos","resistor","capacitor","inductor"]
        }

        for _, data in cg.G.nodes(data=True):
            ct = data.get("comp_type", "")
            p  = data.get("params", {})
            if ct in types_data:
                td = types_data[ct]
                w  = p.get("w", lmin)
                l  = p.get("l", lmin)
                td["w"].append(math.log10(max(w/lmin, 1e-3)))
                td["l"].append(math.log10(max(l/lmin, 1e-3)))
                td["wl"].append(math.log10(max(w/l,   1e-3)) if l>0 else 0)
                td["r"].append(math.log10(max(p.get("r",1e3)/1e3, 1e-6)))
                td["c"].append(math.log10(max(p.get("c",1e-15)/1e-15, 1e-6)))

        out = []
        for t in ["nmos","pmos","resistor","capacitor","inductor"]:
            vals_w  = types_data[t]["w"]  or [0.0]
            vals_wl = types_data[t]["wl"] or [0.0]
            # 8 stats: count, mean_w, std_w, mean_wl, std_wl, min_w, max_w, mean_l
            vals_l = types_data[t]["l"] or [0.0]
            out += [
                len(types_data[t]["w"]) / 20.0,
                float(np.mean(vals_w)),
                float(np.std(vals_w)),
                float(np.mean(vals_wl)),
                float(np.std(vals_wl)),
                float(np.min(vals_w)),
                float(np.max(vals_w)),
                float(np.mean(vals_l)),
            ]
        return np.array(out, dtype=np.float32)


# ─────────────────────────────────────────────────────────────────────────────
# Dataset helper
# ─────────────────────────────────────────────────────────────────────────────

def build_dataset(netlists: List[ParsedNetlist],
                  sim_results: List[Dict[str, float]],
                  technology: str = "180nm"):
    """
    Convert a list of parsed netlists + simulation result dicts
    into (X, Y) numpy arrays ready for training.
    """
    fe = FeatureExtractor()
    X_rows, Y_rows, labels = [], [], None

    for netlist, results in zip(netlists, sim_results):
        cg = CircuitGraph.from_netlist(netlist, technology=technology)
        x  = fe.extract(cg)
        X_rows.append(x)

        if labels is None:
            labels = sorted(results.keys())
        y = np.array([results.get(k, float("nan")) for k in labels],
                     dtype=np.float32)
        Y_rows.append(y)

    X = np.stack(X_rows)
    Y = np.stack(Y_rows)
    return X, Y, labels
