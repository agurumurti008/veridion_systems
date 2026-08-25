"""
core/gnn_trainer.py
Graph-level property prediction trainer using CircuitGNN.
Works standalone (no PyG needed) — uses our custom message-passing layers.
"""
from __future__ import annotations
from typing import Dict, List, Optional, Tuple
import numpy as np

try:
    import torch
    import torch.nn as nn
    import torch.optim as optim
    TORCH_OK = True
except ImportError:
    TORCH_OK = False


class GraphDataset:
    """
    Holds a list of (node_feat, edge_index, graph_label) tuples.
    Built from CircuitGraph objects.
    """
    def __init__(self):
        self.items: List[Tuple] = []   # (X_nodes, E, y_global)

    def add(self, node_feat: np.ndarray, edge_index: np.ndarray,
            y: np.ndarray):
        self.items.append((node_feat, edge_index, y))

    def __len__(self): return len(self.items)

    @classmethod
    def from_circuit_graphs(cls, graphs, Y: np.ndarray) -> "GraphDataset":
        ds = cls()
        for g, y in zip(graphs, Y):
            X_n, E = g.to_feature_matrix()
            ds.add(X_n, E, y)
        return ds


if TORCH_OK:
    class GNNTrainer:
        """
        Trains CircuitGNN on a GraphDataset.
        Outputs a graph-level embedding that is concatenated with the flat
        feature vector before passing to AnalogMLModel.
        """
        def __init__(self, node_feat_dim: int = 15,
                     embed_dim: int = 32,
                     hidden: int = 64,
                     n_layers: int = 3,
                     lr: float = 1e-3):
            from analogml.models import CircuitGNN
            self.gnn  = CircuitGNN(node_feat_dim, hidden, embed_dim, n_layers)
            # regression head on top of GNN embedding
            self.head = nn.Sequential(
                nn.Linear(embed_dim, hidden), nn.SiLU(),
                nn.Linear(hidden, 1)
            )
            self.opt  = optim.Adam(
                list(self.gnn.parameters()) + list(self.head.parameters()),
                lr=lr)
            self.history: List[float] = []

        def fit(self, dataset: GraphDataset, epochs: int = 100,
                target_idx: int = 0):
            """Train to predict dataset Y[:, target_idx]."""
            criterion = nn.MSELoss()
            for ep in range(epochs):
                ep_loss = 0.0
                for (X_n, E, y) in dataset.items:
                    self.opt.zero_grad()
                    Xt = torch.tensor(X_n, dtype=torch.float32)
                    Et = torch.tensor(E,   dtype=torch.long)
                    g  = self.gnn(Xt, Et)
                    yp = self.head(g.unsqueeze(0)).squeeze()
                    yt = torch.tensor(y[target_idx], dtype=torch.float32)
                    loss = criterion(yp, yt)
                    loss.backward(); self.opt.step()
                    ep_loss += loss.item()
                self.history.append(ep_loss / max(len(dataset), 1))

        def embed(self, node_feat: np.ndarray,
                  edge_index: np.ndarray) -> np.ndarray:
            self.gnn.eval()
            with torch.no_grad():
                Xt = torch.tensor(node_feat, dtype=torch.float32)
                Et = torch.tensor(edge_index, dtype=torch.long)
                return self.gnn(Xt, Et).numpy()

else:
    class GNNTrainer:          # type: ignore
        def __init__(self, **kw): pass
        def fit(self, *a, **kw): pass
        def embed(self, X, E):  return np.zeros(32)
