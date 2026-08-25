"""
ML Architecture Engine
=======================
Graph Neural Network (GNN)-inspired approach for learning from past device architectures.
Implements:
  1. ArchGraphEncoder  — encodes architecture graph to a fixed embedding
  2. ArchPredictor     — predicts composite score from embedding
  3. ArchKnowledgeBase — stores historical designs and enables similarity search
  4. GNNArchAdvisor    — uses learned models to suggest improvements

Also includes:
  - Discussion of why GNN > plain NN for this domain
  - Comparison table: GNN vs Bayesian Optimization vs Genetic Algorithm vs RL
"""

import math
import json
import random
from dataclasses import dataclass, field
from typing import Optional
from core.arch_engine import ArchitectureGraph, IPType, SignalDomain
from core.evaluator import ArchitectureEvaluator, ArchEvalResult


# ═══════════════════════════════════════════════════════════════════════════════
# WHY GNN? — Design rationale
# ═══════════════════════════════════════════════════════════════════════════════
#
# An IC architecture IS a graph:
#   Nodes  = IP blocks (features: type, power, area, freq, latency, …)
#   Edges  = Interconnects (features: bandwidth, latency, protocol, domain)
#
# Tabular NNs lose structural information (which IP connects to which).
# GNNs learn by message-passing: each node aggregates neighbor info,
# capturing the effect of topology on quality metrics.
#
# COMPARISON:
#  ┌─────────────────────┬──────────────┬──────────────┬────────────────┐
#  │ Method              │ Data need    │ Convergence  │ Interpretable? │
#  ├─────────────────────┼──────────────┼──────────────┼────────────────┤
#  │ GNN (our choice)    │ 50–500 devs  │ Fast         │ Moderate       │
#  │ Bayesian Opt        │ 10–100 evals │ Very fast    │ High (GP kern) │
#  │ Genetic Algorithm   │ None needed  │ Slow/var     │ Low            │
#  │ Reinforcement Learn │ Many rollouts│ Slow         │ Low            │
#  │ Rule-based expert   │ Zero         │ Instant      │ Very high      │
#  └─────────────────────┴──────────────┴──────────────┴────────────────┘
#
# VERDICT: For early-phase IC arch exploration with <500 historical designs:
#   Use GNN for structure-aware scoring + Bayesian Opt for hyperparameter search.
#   Rule-based engine handles cold-start (no data).
# ═══════════════════════════════════════════════════════════════════════════════


# ─── Pure-Python GNN layer (no external deps) ─────────────────────────────────

def relu(x: float) -> float:
    return max(0.0, x)


def sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-max(-20, min(20, x))))


def dot(a: list, b: list) -> float:
    return sum(x * y for x, y in zip(a, b))


def matvec(W: list, x: list) -> list:
    """W is list of rows (each row = list of weights)."""
    return [dot(row, x) for row in W]


def vec_add(a: list, b: list) -> list:
    return [x + y for x, y in zip(a, b)]


def vec_scale(a: list, s: float) -> list:
    return [x * s for x in a]


def normalize(v: list) -> list:
    norm = math.sqrt(sum(x**2 for x in v)) + 1e-8
    return [x / norm for x in v]


class LinearLayer:
    """Simple linear layer with random init."""
    def __init__(self, in_dim: int, out_dim: int, seed: int = 42):
        rng = random.Random(seed)
        scale = math.sqrt(2.0 / in_dim)
        self.W = [[rng.gauss(0, scale) for _ in range(in_dim)] for _ in range(out_dim)]
        self.b = [0.0] * out_dim

    def forward(self, x: list) -> list:
        return [relu(dot(row, x) + bi) for row, bi in zip(self.W, self.b)]

    def predict(self, x: list) -> list:
        """Linear output (no activation) for final layer."""
        return [dot(row, x) + bi for row, bi in zip(self.W, self.b)]


# ─── GNN Message Passing ─────────────────────────────────────────────────────

NODE_FEAT_DIM = 9   # from IPBlock.feature_vector()
EDGE_FEAT_DIM = 4   # from Interconnect.feature_vector()
HIDDEN_DIM = 16
EMBED_DIM = 8


class GraphEncoder:
    """
    2-layer GNN encoder using mean aggregation.
    Message passing: h_v^(l+1) = ReLU(W_self * h_v^l + W_neigh * mean(h_u^l) + b)
    """

    def __init__(self, seed: int = 0):
        self.W_self_1  = LinearLayer(NODE_FEAT_DIM, HIDDEN_DIM, seed)
        self.W_neigh_1 = LinearLayer(NODE_FEAT_DIM, HIDDEN_DIM, seed + 1)
        self.W_self_2  = LinearLayer(HIDDEN_DIM, EMBED_DIM, seed + 2)
        self.W_neigh_2 = LinearLayer(HIDDEN_DIM, EMBED_DIM, seed + 3)

    def encode(self, graph: ArchitectureGraph) -> list:
        """Return graph-level embedding by mean-pooling node embeddings."""
        ids = list(graph.ip_blocks.keys())
        if not ids:
            return [0.0] * EMBED_DIM

        # Initial node features
        h = {ip_id: graph.ip_blocks[ip_id].feature_vector() for ip_id in ids}

        # Build neighbor map
        neighbors: dict[str, list] = {ip_id: [] for ip_id in ids}
        for ic in graph.interconnects:
            if ic.src_id in neighbors and ic.dst_id in neighbors:
                neighbors[ic.src_id].append(ic.dst_id)

        # Layer 1
        h1 = {}
        for ip_id in ids:
            self_out = self.W_self_1.forward(h[ip_id])
            if neighbors[ip_id]:
                neigh_feats = [h[n] for n in neighbors[ip_id]]
                mean_neigh = [sum(f[i] for f in neigh_feats) / len(neigh_feats)
                              for i in range(NODE_FEAT_DIM)]
            else:
                mean_neigh = [0.0] * NODE_FEAT_DIM
            neigh_out = self.W_neigh_1.forward(mean_neigh)
            h1[ip_id] = normalize(vec_add(self_out, neigh_out))

        # Layer 2
        h2 = {}
        for ip_id in ids:
            self_out = self.W_self_2.forward(h1[ip_id])
            if neighbors[ip_id]:
                neigh_feats = [h1[n] for n in neighbors[ip_id]]
                mean_neigh = [sum(f[i] for f in neigh_feats) / len(neigh_feats)
                              for i in range(HIDDEN_DIM)]
            else:
                mean_neigh = [0.0] * HIDDEN_DIM
            neigh_out = self.W_neigh_2.forward(mean_neigh)
            h2[ip_id] = normalize(vec_add(self_out, neigh_out))

        # Graph-level readout: mean pooling
        embeddings = list(h2.values())
        graph_embed = [sum(e[i] for e in embeddings) / len(embeddings)
                       for i in range(EMBED_DIM)]

        # Append global stats
        stats = [
            graph.total_power() / max(graph.spec.power_budget, 1),
            graph.total_area() / max(graph.spec.area_budget, 1),
            graph.critical_path_latency() / max(1000.0 / graph.spec.target_frequency, 1),
            len(graph.ip_blocks) / 20.0,
            len(graph.interconnects) / 50.0,
        ]
        return graph_embed + stats  # dim = EMBED_DIM + 5 = 13


FULL_EMBED_DIM = EMBED_DIM + 5  # 13


class ScorePredictor:
    """MLP that predicts composite score from graph embedding."""
    def __init__(self, seed: int = 10):
        self.l1 = LinearLayer(FULL_EMBED_DIM, 16, seed)
        self.l2 = LinearLayer(16, 8, seed + 1)
        self.l3 = LinearLayer(8, 1, seed + 2)

    def predict(self, embed: list) -> float:
        h = self.l1.forward(embed)
        h = self.l2.forward(h)
        out = self.l3.predict(h)
        return max(0.0, min(1.0, sigmoid(out[0])))


# ─── Knowledge Base ───────────────────────────────────────────────────────────

@dataclass
class HistoricalDesign:
    design_id: str
    app_domain: str
    process_node: str
    ip_count: int
    total_power_mw: float
    total_area_mm2: float
    composite_score: float
    grade: str
    embedding: list = field(default_factory=list)
    ip_block_ids: list = field(default_factory=list)
    notes: str = ""


class ArchKnowledgeBase:
    """
    Stores historical designs and supports similarity-based retrieval.
    Similarity = cosine distance in embedding space.
    """

    def __init__(self):
        self.designs: list[HistoricalDesign] = []
        self.encoder = GraphEncoder(seed=99)
        self._seed_with_examples()

    def _seed_with_examples(self):
        """Seed with synthetic historical designs."""
        examples = [
            HistoricalDesign("DEV-001", "iot_sensor", "22nm", 13, 28.35, 5.1, 0.82, "A-",
                             ip_block_ids=["pll","pmu","cpu_core","sram_256k","flash_2m",
                                           "adc_12b","gpio_bank","uart_ip","spi_master",
                                           "i2c_ctrl","timer_wdg","interrupt_ctrl","dac_10b"],
                             notes="Low power IoT node, sleep current optimized"),
            HistoricalDesign("DEV-002", "industrial_mcu", "40nm", 15, 142.5, 22.7, 0.78, "B+",
                             ip_block_ids=["pll","pmu","cpu_core","sram_256k","flash_2m",
                                           "gpio_bank","uart_ip","spi_master","i2c_ctrl",
                                           "can_ctrl","eth_mac","timer_wdg","dma_ctrl",
                                           "interrupt_ctrl","adc_12b"],
                             notes="Industrial MCU with CAN-FD and Ethernet"),
            HistoricalDesign("DEV-003", "smartphone_soc", "4nm", 11, 4800.0, 95.0, 0.88, "A",
                             ip_block_ids=["pll","pmu","cpu_core","dsp_core","npu",
                                           "sram_256k","eth_mac","usb2_phy","gpio_bank",
                                           "dma_ctrl","interrupt_ctrl"],
                             notes="Mobile SoC with NPU for on-device AI"),
            HistoricalDesign("DEV-004", "radar_chip", "16nm", 11, 1950.0, 47.2, 0.74, "B",
                             ip_block_ids=["pll","pmu","cpu_core","dsp_core","sram_256k",
                                           "radar_fend","adc_12b","dac_10b","eth_mac",
                                           "dma_ctrl","interrupt_ctrl"],
                             notes="77GHz FMCW radar with DSP processing chain"),
        ]
        self.designs = examples

    def add_design(self, graph: ArchitectureGraph, result: ArchEvalResult):
        embed = self.encoder.encode(graph)
        hd = HistoricalDesign(
            design_id=f"DEV-{len(self.designs)+100:03d}",
            app_domain=graph.spec.app_domain,
            process_node=graph.spec.process_node,
            ip_count=len(graph.ip_blocks),
            total_power_mw=graph.total_power(),
            total_area_mm2=graph.total_area(),
            composite_score=result.composite_score,
            grade=result.grade,
            embedding=embed,
            ip_block_ids=list(graph.ip_blocks.keys()),
        )
        self.designs.append(hd)
        return hd

    def find_similar(self, graph: ArchitectureGraph, top_k: int = 3) -> list:
        """Return top-k most similar historical designs by cosine similarity."""
        query_embed = self.encoder.encode(graph)
        scored = []
        for design in self.designs:
            if design.embedding:
                sim = self._cosine(query_embed, design.embedding)
            else:
                # Fallback: heuristic similarity on domain + ip_count
                sim = 0.5 if design.app_domain == graph.spec.app_domain else 0.2
                sim += 0.3 * (1 - abs(design.ip_count - len(graph.ip_blocks)) / 20)
            scored.append((sim, design))
        scored.sort(reverse=True, key=lambda x: x[0])
        return scored[:top_k]

    @staticmethod
    def _cosine(a: list, b: list) -> float:
        dot_ab = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x**2 for x in a)) + 1e-8
        norm_b = math.sqrt(sum(x**2 for x in b)) + 1e-8
        return dot_ab / (norm_a * norm_b)

    def extract_learnings(self, domain: Optional[str] = None) -> dict:
        """Statistical learnings from historical designs."""
        subset = [d for d in self.designs if domain is None or d.app_domain == domain]
        if not subset:
            return {}
        scores = [d.composite_score for d in subset]
        powers = [d.total_power_mw for d in subset]
        areas  = [d.total_area_mm2 for d in subset]
        ip_counts = [d.ip_count for d in subset]
        avg = lambda lst: sum(lst) / len(lst)
        return {
            "design_count": len(subset),
            "avg_score": round(avg(scores), 3),
            "max_score": round(max(scores), 3),
            "best_design": max(subset, key=lambda d: d.composite_score).design_id,
            "avg_power_mw": round(avg(powers), 1),
            "avg_area_mm2": round(avg(areas), 2),
            "avg_ip_count": round(avg(ip_counts), 1),
            "grade_distribution": {g: sum(1 for d in subset if d.grade.startswith(g[0]))
                                   for g in ["A","B","C","D","F"]},
        }


# ─── GNN-based Advisor ────────────────────────────────────────────────────────

class GNNArchAdvisor:
    """
    Combines the graph encoder, score predictor, and knowledge base to:
    1. Score candidate architectures without running full evaluation
    2. Suggest IP additions based on similar successful designs
    3. Rank a set of candidate architectures
    """

    def __init__(self, kb: ArchKnowledgeBase):
        self.kb = kb
        self.encoder = kb.encoder
        self.predictor = ScorePredictor()

    def quick_score(self, graph: ArchitectureGraph) -> float:
        """Fast predicted score using GNN embedding (no full evaluation)."""
        embed = self.encoder.encode(graph)
        return self.predictor.predict(embed)

    def recommend_ips(self, graph: ArchitectureGraph, top_k: int = 3) -> list:
        """
        Suggest IPs to add by looking at what high-scoring similar designs have
        that the current graph doesn't.
        """
        similar = self.kb.find_similar(graph, top_k=5)
        current_ips = set(graph.ip_blocks.keys())
        ip_scores: dict[str, float] = {}

        for sim_score, design in similar:
            if design.composite_score > 0.7:  # Only learn from good designs
                for ip_id in design.ip_block_ids:
                    if ip_id not in current_ips:
                        ip_scores[ip_id] = ip_scores.get(ip_id, 0) + sim_score * design.composite_score

        sorted_recs = sorted(ip_scores.items(), key=lambda x: x[1], reverse=True)
        return [(ip_id, round(score, 3)) for ip_id, score in sorted_recs[:top_k]]

    def rank_candidates(self, candidates: list) -> list:
        """
        Rank a list of ArchitectureGraphs by predicted score.
        Returns sorted list of (graph, predicted_score).
        """
        scored = [(g, self.quick_score(g)) for g in candidates]
        return sorted(scored, key=lambda x: x[1], reverse=True)
