"""
data/__init__.py  —  Dataset management for AnalogML

Provides:
  - SyntheticCircuitDataset : generates physics-consistent synthetic data
    for OTAs, LDOs, OpAmps without needing a real simulator
  - CircuitDataset          : loads real simulation CSV results
  - MultiFidelityDataset    : pairs of (schematic, post-layout) results
"""

from __future__ import annotations

import csv
import math
import random
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np


# ─────────────────────────────────────────────────────────────────────────────
# Physics-consistent synthetic data generators
# ─────────────────────────────────────────────────────────────────────────────

class SyntheticCircuitDataset:
    """
    Generates (X, Y) pairs using analytic hand-analysis equations for
    common analog building blocks.  Good for bootstrapping / unit testing.

    Supported topologies:
      'ota_5t'       — 5-transistor OTA
      'ota_folded'   — Folded-cascode OTA
      'ldo'          — LDO regulator
      'current_mirror' — Simple current mirror
    """

    TOPOLOGIES = ["ota_5t", "ota_folded", "ldo", "current_mirror"]

    def __init__(self, seed: int = 42):
        self.rng = np.random.default_rng(seed)

    def generate(self, topology: str, n_samples: int = 200,
                 technology: str = "180nm") -> Tuple[np.ndarray, np.ndarray,
                                                      List[str], List[str]]:
        """
        Returns (X, Y, x_names, y_names).

        X columns: [W1, L1, W3, L3, W5, L5, Ibias, Cload, Cc, Rc, VDD]
        Y columns: depends on topology
        """
        generators = {
            "ota_5t"       : self._ota_5t,
            "ota_folded"   : self._ota_folded,
            "ldo"          : self._ldo,
            "current_mirror": self._current_mirror,
        }
        if topology not in generators:
            raise ValueError(f"Unknown topology: {topology}. "
                             f"Choose from {self.TOPOLOGIES}")
        return generators[topology](n_samples, technology)

    # ── 5-transistor OTA ─────────────────────────────────────────────────────

    def _ota_5t(self, n: int, tech: str
                ) -> Tuple[np.ndarray, np.ndarray, List[str], List[str]]:
        from analogml.core import TECH_DB
        tp   = TECH_DB.get(tech, TECH_DB["180nm"])
        lmin = tp["lmin"]
        vdd  = tp["vdd"]
        vth  = tp["vth_n"]

        x_names = ["W1_um","L1_um","W3_um","L3_um","W5_um","L5_um",
                   "Ibias_uA","Cload_fF","Cc_fF","VDD_V"]
        y_names = ["gain_dB","ugf_MHz","phase_margin_deg",
                   "power_uW","noise_nV_sqrtHz","cmrr_dB",
                   "slew_rate_V_us","output_swing_V"]

        X, Y = [], []
        for _ in range(n):
            # sample sizes (in meters)
            W1  = self.rng.uniform(1, 20)  * lmin * 1e6   # μm
            L1  = self.rng.uniform(1, 4)   * lmin * 1e6
            W3  = self.rng.uniform(2, 40)  * lmin * 1e6
            L3  = self.rng.uniform(1, 4)   * lmin * 1e6
            W5  = self.rng.uniform(1, 20)  * lmin * 1e6
            L5  = self.rng.uniform(1, 4)   * lmin * 1e6
            Ib  = self.rng.uniform(1, 50)               # μA
            Cl  = self.rng.uniform(100, 2000)            # fF
            Cc  = self.rng.uniform(50,  500)             # fF
            Vdd = vdd + self.rng.uniform(-0.05, 0.05)

            # ── analytic hand equations ──
            mu_n   = 0.04   # m²/Vs  (rough 180nm)
            mu_p   = 0.015
            Cox    = 8.6e-3 / tp["tox"]  # F/m² approx

            # W/L ratios
            WL1 = W1 / L1
            WL3 = W3 / L3
            WL5 = W5 / L5

            Id     = Ib * 1e-6 / 2          # drain current each input pair
            gm1    = math.sqrt(2 * mu_n * Cox * WL1 * 1e-6 * Id)
            gm3    = math.sqrt(2 * mu_p * Cox * WL3 * 1e-6 * Id)
            gds1   = 0.05 * gm1
            gds3   = 0.05 * gm3
            Ro     = 1 / (gds1 + gds3)
            Av     = gm1 * Ro
            gain   = 20 * math.log10(max(Av, 1))

            Cl_F   = Cl * 1e-15
            Cc_F   = Cc * 1e-15
            ugf    = gm1 / (2 * math.pi * Cc_F) / 1e6   # MHz
            # phase margin using two-pole approximation
            fp2    = gm3 / (2 * math.pi * Cl_F) / 1e6
            pm     = 90 - math.degrees(math.atan(ugf / max(fp2, 0.01)))
            pm     = max(0, min(90, pm))

            Ptot   = Ib * 1e-6 * Vdd * 1e6   # μW
            # input-referred noise (thermal dominant)
            k      = 1.38e-23
            T      = 300
            noise  = math.sqrt(8 * k * T / (3 * gm1)) * 1e9  # nV/√Hz

            cmrr   = gain + 20 * math.log10(max(gm1 / (2*gds1+1e-12), 1))
            SR     = Ib * 1e-6 / Cc_F / 1e6   # V/μs
            swing  = Vdd - 2 * 0.2            # headroom estimate

            # add noise
            def jitter(v, pct=0.03):
                return v * (1 + self.rng.normal(0, pct))

            X.append([W1, L1, W3, L3, W5, L5, Ib, Cl, Cc, Vdd])
            Y.append([jitter(gain), jitter(ugf), jitter(pm),
                      jitter(Ptot), jitter(noise), jitter(cmrr),
                      jitter(SR), jitter(swing)])

        return np.array(X, dtype=np.float32), np.array(Y, dtype=np.float32), \
               x_names, y_names

    # ── folded-cascode OTA (simplified) ──────────────────────────────────────

    def _ota_folded(self, n: int, tech: str
                    ) -> Tuple[np.ndarray, np.ndarray, List[str], List[str]]:
        # Use 5T as base but apply ~1.5× gain boost factor
        X, Y, xn, yn = self._ota_5t(n, tech)
        Y[:, 0] += self.rng.uniform(6, 12, n).astype(np.float32)  # +gain
        Y[:, 1] *= self.rng.uniform(0.7, 1.1, n).astype(np.float32)
        Y[:, 3] *= self.rng.uniform(1.5, 2.0, n).astype(np.float32)  # +power
        return X, Y, xn, yn

    # ── LDO regulator ────────────────────────────────────────────────────────

    def _ldo(self, n: int, tech: str
             ) -> Tuple[np.ndarray, np.ndarray, List[str], List[str]]:
        from analogml.core import TECH_DB
        tp   = TECH_DB.get(tech, TECH_DB["180nm"])
        vdd  = tp["vdd"]

        x_names = ["Wp_um","Lp_um","Wn_um","Ln_um","Ibias_uA",
                   "Rfb1_kohm","Rfb2_kohm","Cout_pF","VDD_V"]
        y_names = ["Vout_V","line_reg_mV_V","load_reg_mV_A",
                   "psrr_dB","quiescent_uA","dropout_mV",
                   "phase_margin_deg","power_uW"]

        X, Y = [], []
        for _ in range(n):
            Wp   = self.rng.uniform(20, 200)   # μm
            Lp   = self.rng.uniform(0.3, 2)
            Wn   = self.rng.uniform(2, 20)
            Ln   = self.rng.uniform(0.2, 1)
            Ib   = self.rng.uniform(5, 100)
            Rf1  = self.rng.uniform(10, 200)
            Rf2  = self.rng.uniform(10, 200)
            Co   = self.rng.uniform(1, 100)    # pF
            Vdd  = vdd + self.rng.uniform(0, 0.3)

            Vref = vdd * 0.4
            Vout = Vref * (1 + Rf1/Rf2)
            Vout = min(Vout, Vdd - 0.1)

            gm_ea = 0.5e-3 * (Wn/Ln)
            Ro    = 50e3
            Av    = gm_ea * Ro
            Co_F  = Co * 1e-12
            ugf   = gm_ea / (2*math.pi*Co_F) / 1e3   # kHz

            line_reg = 1000 / max(Av, 1)     # mV/V
            load_reg = 1 / max(gm_ea, 1e-6)  # mV/A approx
            psrr     = 20 * math.log10(max(Av/10, 1))
            Iq       = Ib
            dropout  = 200 * (1 / max(Wp, 1))   # rough
            pm       = 55 + self.rng.uniform(-5, 10)

            def j(v): return v * (1 + self.rng.normal(0, 0.03))
            X.append([Wp, Lp, Wn, Ln, Ib, Rf1, Rf2, Co, Vdd])
            Y.append([j(Vout), j(line_reg), j(load_reg),
                      j(psrr), j(Iq), j(dropout), j(pm),
                      j(Iq*Vdd)])

        return np.array(X, dtype=np.float32), np.array(Y, dtype=np.float32), \
               x_names, y_names

    # ── Current mirror ────────────────────────────────────────────────────────

    def _current_mirror(self, n: int, tech: str
                        ) -> Tuple[np.ndarray, np.ndarray, List[str], List[str]]:
        x_names = ["W_ref_um","L_ref_um","W_out_um","L_out_um","Iref_uA"]
        y_names = ["Iout_Iref_ratio","Vmin_out_mV","output_impedance_kohm",
                   "bandwidth_MHz","mismatch_pct"]

        X, Y = [], []
        for _ in range(n):
            Wr  = self.rng.uniform(1, 10)
            Lr  = self.rng.uniform(0.2, 2)
            Wo  = self.rng.uniform(1, 10)
            Lo  = self.rng.uniform(0.2, 2)
            Ir  = self.rng.uniform(1, 50)

            ratio  = (Wo/Lo) / (Wr/Lr)
            Vdsat  = 150 * (Lr**0.5)   # mV rough
            Rout   = 100 * Lo / Wo      # kΩ
            BW     = 1 / (2*math.pi * 1e-15 * Wo * 1e-6 * Rout*1e3) / 1e6
            mismatch = 0.5 / math.sqrt(Wr*Lr + Wo*Lo)

            def j(v): return v * (1 + self.rng.normal(0, 0.02))
            X.append([Wr, Lr, Wo, Lo, Ir])
            Y.append([j(ratio), j(Vdsat), j(Rout), j(BW), j(mismatch)])

        return np.array(X, dtype=np.float32), np.array(Y, dtype=np.float32), \
               x_names, y_names


# ─────────────────────────────────────────────────────────────────────────────
# CSV-based real-simulation dataset loader
# ─────────────────────────────────────────────────────────────────────────────

class CircuitDataset:
    """
    Loads circuit simulation results from CSV files.

    Expected CSV format:
      - One row per simulation run
      - Columns starting with 'x_' → input features
      - Columns starting with 'y_' → output specs
      - Column 'technology'        → optional tech node label
    """

    def __init__(self, csv_path: str):
        self.path = Path(csv_path)
        self.X: Optional[np.ndarray] = None
        self.Y: Optional[np.ndarray] = None
        self.x_names: List[str] = []
        self.y_names: List[str] = []
        self.technology: str    = "unknown"
        self._load()

    def _load(self):
        rows = []
        with open(self.path, newline="") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                rows.append(row)

        if not rows:
            raise ValueError(f"Empty CSV: {self.path}")

        first = rows[0]
        self.x_names = sorted(k for k in first if k.startswith("x_"))
        self.y_names = sorted(k for k in first if k.startswith("y_"))

        if "technology" in first:
            self.technology = rows[0]["technology"]

        X, Y = [], []
        for row in rows:
            X.append([float(row[k]) for k in self.x_names])
            Y.append([float(row[k]) for k in self.y_names])

        self.X = np.array(X, dtype=np.float32)
        self.Y = np.array(Y, dtype=np.float32)

    def train_test_split(self, test_ratio: float = 0.2
                          ) -> Tuple[np.ndarray, np.ndarray,
                                     np.ndarray, np.ndarray]:
        n     = len(self.X)
        idx   = np.random.permutation(n)
        split = int(n * (1 - test_ratio))
        tr, te = idx[:split], idx[split:]
        return self.X[tr], self.Y[tr], self.X[te], self.Y[te]


# ─────────────────────────────────────────────────────────────────────────────
# Multi-fidelity dataset
# ─────────────────────────────────────────────────────────────────────────────

class MultiFidelityDataset:
    """
    Holds paired low-fidelity (schematic) and high-fidelity (post-layout)
    simulation results for the same circuits.
    """

    def __init__(self):
        self.X_low  : Optional[np.ndarray] = None
        self.Y_low  : Optional[np.ndarray] = None
        self.X_high : Optional[np.ndarray] = None
        self.Y_high : Optional[np.ndarray] = None
        self.x_names: List[str] = []
        self.y_names: List[str] = []

    def from_csv(self, low_csv: str, high_csv: str) -> "MultiFidelityDataset":
        ds_low  = CircuitDataset(low_csv)
        ds_high = CircuitDataset(high_csv)
        self.X_low   = ds_low.X
        self.Y_low   = ds_low.Y
        self.X_high  = ds_high.X
        self.Y_high  = ds_high.Y
        self.x_names = ds_low.x_names
        self.y_names = ds_low.y_names
        return self

    def from_synthetic(self, topology: str = "ota_5t",
                       n_low: int = 500, n_high: int = 100,
                       tech: str = "180nm") -> "MultiFidelityDataset":
        """
        Generates synthetic multi-fidelity data.
        High-fidelity adds realistic layout parasitics (+cap, -bandwidth).
        """
        ds = SyntheticCircuitDataset()
        Xl, Yl, xn, yn = ds.generate(topology, n_low, tech)
        Xh, Yh, _,  _  = ds.generate(topology, n_high, tech)
        # Simulate layout parasitics: gain -2dB, UGF -20%, PM -5deg
        Yh[:, 0] -= np.random.uniform(1, 3, n_high)    # gain dip
        Yh[:, 1] *= np.random.uniform(0.7, 0.9, n_high) # UGF drop
        Yh[:, 2] -= np.random.uniform(2, 8, n_high)    # PM drop
        self.X_low   = Xl;  self.Y_low  = Yl
        self.X_high  = Xh;  self.Y_high = Yh
        self.x_names = xn;  self.y_names = yn
        return self
