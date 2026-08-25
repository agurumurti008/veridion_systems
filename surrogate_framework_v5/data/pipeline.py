"""
data/pipeline.py
LHS synthetic data generator + SPICE CSV parser.
"""
import os
import math
import numpy as np

try:
    from scipy.stats.qmc import LatinHypercube
    _QMC = True
except ImportError:
    _QMC = False

try:
    import pandas as pd
    _PANDAS = True
except ImportError:
    _PANDAS = False

try:
    import torch
    _TORCH = True
except ImportError:
    _TORCH = False


# ─── Data contracts: exact column names per IP type ──────────────────────────

PARAM_SPACES = {
    'LDO': {
        'features': ['Vin', 'Iload', 'Temp', 'Process', 'W_pass', 'Cc', 'Rf1', 'Rf2'],
        'outputs':  ['Vout', 'PSRR_1kHz', 'PSRR_1MHz', 'Phase_Margin',
                     'Quiescent_I', 'Noise_uVrms', 'Dropout_V', 'Load_Reg_mV'],
        'bounds': {
            'Vin':    (1.8, 5.5),
            'Iload':  (1e-3, 0.5),
            'Temp':   (-40.0, 125.0),
            'Process': (0.0, 4.0),
            'W_pass': (100e-6, 2000e-6),
            'Cc':     (1e-12, 100e-12),
            'Rf1':    (10e3, 500e3),
            'Rf2':    (10e3, 500e3),
        },
    },
    'OTA': {
        'features': ['Ibias', 'Vcm', 'CL', 'Temp', 'Process', 'W_diff', 'W_load', 'Cc'],
        'outputs':  ['GBW', 'Phase_Margin', 'CMRR', 'PSRR',
                     'Slew_Rate', 'Offset_mV', 'Gm', 'Ro'],
        'bounds': {
            'Ibias':   (10e-6, 500e-6),
            'Vcm':     (0.5, 2.5),
            'CL':      (0.5e-12, 20e-12),
            'Temp':    (-40.0, 125.0),
            'Process': (0.0, 4.0),
            'W_diff':  (10e-6, 500e-6),
            'W_load':  (10e-6, 500e-6),
            'Cc':      (0.1e-12, 10e-12),
        },
    },
    'DCDC': {
        'features': ['Vin', 'D', 'Iload', 'Temp', 'L', 'C', 'Fsw'],
        'outputs':  ['Vout', 'Efficiency', 'Ripple_mV', 'Phase_Margin', 'CrossFreq'],
        'bounds': {
            'Vin':   (3.0, 15.0),
            'D':     (0.1, 0.9),
            'Iload': (0.1, 3.0),
            'Temp':  (-40.0, 125.0),
            'L':     (1e-6, 100e-6),
            'C':     (1e-6, 100e-6),
            'Fsw':   (100e3, 5e6),
        },
    },
}

# Process encoding
PROCESS_ENCODING = {'TT': 2, 'SS': 0, 'FF': 4, 'SF': 1, 'FS': 3}
PROCESS_LIST = ['SS', 'SF', 'TT', 'FS', 'FF']


class SyntheticDataGenerator:
    """Generate physics-realistic synthetic training data."""

    def __init__(self, ip_type: str = 'LDO', seed: int = 42):
        self.ip_type = ip_type.upper()
        self.seed = seed
        np.random.seed(seed)

        if self.ip_type not in PARAM_SPACES:
            raise ValueError(f"Unknown IP type: {self.ip_type}. "
                             f"Choose from {list(PARAM_SPACES.keys())}")

        self.space = PARAM_SPACES[self.ip_type]
        self.feature_names = self.space['features']
        self.output_names  = self.space['outputs']
        self.bounds        = self.space['bounds']

    # ─── LHS sampling ─────────────────────────────────────────────────────────

    def generate_lhs(self, n_samples: int = 300) -> np.ndarray:
        """Latin Hypercube Sampling scaled to parameter bounds."""
        n_dims = len(self.feature_names)

        if _QMC:
            sampler = LatinHypercube(d=n_dims, seed=self.seed)
            unit = sampler.random(n=n_samples)
        else:
            # Fallback: stratified random
            unit = np.zeros((n_samples, n_dims))
            for d in range(n_dims):
                perm = np.random.permutation(n_samples)
                unit[:, d] = (perm + np.random.uniform(size=n_samples)) / n_samples

        # Scale to bounds
        X = np.zeros_like(unit)
        for j, fname in enumerate(self.feature_names):
            lo, hi = self.bounds[fname]
            X[:, j] = lo + (hi - lo) * unit[:, j]

        # Round Process to integer
        if 'Process' in self.feature_names:
            pidx = self.feature_names.index('Process')
            X[:, pidx] = np.round(X[:, pidx]).clip(0, 4)

        Y = self._compute_outputs(X)
        return X, Y

    def _compute_outputs(self, X: np.ndarray) -> np.ndarray:
        ip = self.ip_type
        n = len(X)

        def col(name):
            if name in self.feature_names:
                return X[:, self.feature_names.index(name)]
            return np.zeros(n)

        if ip == 'LDO':
            return self._compute_ldo(X, col, n)
        elif ip == 'OTA':
            return self._compute_ota(X, col, n)
        elif ip == 'DCDC':
            return self._compute_dcdc(X, col, n)
        else:
            return np.zeros((n, len(self.output_names)))

    def _compute_ldo(self, X, col, n):
        Vin     = col('Vin')
        Iload   = col('Iload')
        Temp    = col('Temp')
        Process = col('Process')
        W_pass  = col('W_pass')
        Cc      = col('Cc')
        Rf1     = col('Rf1')
        Rf2     = col('Rf2')

        Vref = 0.9
        # Vout = Vref*(1+Rf1/Rf2) - Iload*0.05 + noise
        Vout = Vref * (1 + Rf1 / (Rf2 + 1e-12)) - Iload * 0.05
        Vout += np.random.randn(n) * 0.002

        # PSRR at 1kHz
        PSRR_1kHz = (60 + 10 * np.log10(W_pass / 200e-6 + 1e-9)
                     - 5 * (Process - 2))
        PSRR_1kHz = np.clip(PSRR_1kHz + np.random.randn(n) * 2, 40, 120)

        # PSRR at 1MHz (rolls off)
        PSRR_1MHz = PSRR_1kHz - 20 + np.random.randn(n) * 2
        PSRR_1MHz = np.clip(PSRR_1MHz, 20, 90)

        # Phase Margin
        PM = (55 + 10 * np.log10(Cc / 10e-12 + 1e-9)
              - 0.03 * (Temp - 27))
        PM = np.clip(PM + np.random.randn(n) * 3, 30, 90)

        # Quiescent current (mA)
        Iq = 0.05 + 0.01 * (Process - 2) + np.random.randn(n) * 0.005
        Iq = np.clip(Iq, 0.01, 0.2)

        # Noise (uVrms)
        Noise = 20 - 5 * (W_pass / 500e-6) + np.random.randn(n) * 2
        Noise = np.clip(Noise, 5, 80)

        # Dropout voltage
        Vdrop = 0.2 + 0.1 * Iload / 0.5 + np.random.randn(n) * 0.01
        Vdrop = np.clip(Vdrop, 0.05, 0.6)

        # Load regulation (mV)
        Load_Reg = Iload * 5.0 + np.random.randn(n) * 0.5
        Load_Reg = np.clip(Load_Reg, 0.1, 30)

        return np.column_stack([Vout, PSRR_1kHz, PSRR_1MHz, PM,
                                 Iq, Noise, Vdrop, Load_Reg])

    def _compute_ota(self, X, col, n):
        Ibias   = col('Ibias')
        Vcm     = col('Vcm')
        CL      = col('CL')
        Temp    = col('Temp')
        Process = col('Process')
        W_diff  = col('W_diff')
        W_load  = col('W_load')
        Cc      = col('Cc')

        # Gm: physics-realistic
        Gm = (2e-3 * np.sqrt(np.abs(Ibias / 100e-6) * np.abs(W_diff / 100e-6))
              * (1 - 0.003 * (Temp - 27)))
        Gm = np.clip(Gm, 0.1e-3, 20e-3)

        # GBW = Gm / (2*pi*CL)
        GBW = Gm / (2 * math.pi * np.abs(CL) + 1e-20)
        GBW /= 1e6  # convert to MHz
        GBW = np.clip(GBW + np.random.randn(n) * 1, 1, 500)

        # fp2 (non-dominant pole) — affects PM
        fp2 = GBW * (5 + 2 * Process) * 1e6
        # PM = 90 - arctan(GBW/fp2 * 2pi)
        PM = 90 - np.degrees(np.arctan(GBW * 1e6 / (fp2 + 1e-9)))
        PM = np.clip(PM + np.random.randn(n) * 3, 20, 89)

        # CMRR
        CMRR = (80 + 5 * (W_diff / 100e-6)
                - 2 * (Process - 2) + np.random.randn(n) * 3)
        CMRR = np.clip(CMRR, 50, 120)

        # PSRR
        PSRR = (70 + 3 * (Cc / 1e-12)
                + np.random.randn(n) * 3)
        PSRR = np.clip(PSRR, 40, 100)

        # Slew Rate = Ibias / CL (V/us)
        SR = Ibias / (np.abs(CL) + 1e-20) / 1e6
        SR = np.clip(SR + np.random.randn(n) * 2, 1, 500)

        # Offset voltage (mV)
        Vos = (1.0 + 0.5 * (Process - 2)
               + 0.01 * (Temp - 27) + np.random.randn(n) * 0.3)
        Vos = np.clip(np.abs(Vos), 0.01, 10)

        # Output resistance (kOhm)
        Ro = (1000 / (Ibias / 100e-6 + 1e-9)
              + np.random.randn(n) * 50)
        Ro = np.clip(Ro, 10, 10000)

        return np.column_stack([GBW, PM, CMRR, PSRR, SR, Vos, Gm * 1e3, Ro])

    def _compute_dcdc(self, X, col, n):
        Vin   = col('Vin')
        D     = col('D')
        Iload = col('Iload')
        Temp  = col('Temp')
        L     = col('L')
        C     = col('C')
        Fsw   = col('Fsw')

        # Vout = Vin * D
        Vout = Vin * D + np.random.randn(n) * 0.01
        Vout = np.clip(Vout, 0.5, 15)

        # Efficiency (%)
        Eff = (92 - 0.02 * (Temp - 27)
               - 5 * Iload / 3.0 + np.random.randn(n) * 1)
        Eff = np.clip(Eff, 60, 99)

        # Ripple (mV): Iload*(1-D)/(Fsw*C)*1000
        Ripple = Iload * (1 - D) / (Fsw * np.abs(C) + 1e-20) * 1000
        Ripple = np.clip(Ripple + np.random.randn(n) * 2, 0.1, 200)

        # Phase Margin (approximate)
        fc = 1.0 / (2 * math.pi * np.sqrt(np.abs(L * C)) + 1e-20)
        PM = 60 - 10 * np.log10(fc / (Fsw / 5) + 1)
        PM = np.clip(PM + np.random.randn(n) * 3, 20, 90)

        # Crossover frequency (kHz)
        CrossFreq = fc / 1e3
        CrossFreq = np.clip(CrossFreq + np.random.randn(n) * 5, 1, 500)

        return np.column_stack([Vout, Eff, Ripple, PM, CrossFreq])

    # ─── PVT corners ──────────────────────────────────────────────────────────

    def generate_pvt_corners(self) -> np.ndarray:
        """5 processes × 3 temps × 3 vdds = 45 rows."""
        processes = [0.0, 1.0, 2.0, 3.0, 4.0]  # SS SF TT FS FF
        temps     = [-40.0, 27.0, 125.0]

        if self.ip_type == 'LDO':
            vdds = [1.8, 2.5, 5.0]
        elif self.ip_type == 'DCDC':
            vdds = [5.0, 9.0, 12.0]
        else:
            vdds = [1.8, 2.5, 3.3]

        rows = []
        for proc in processes:
            for temp in temps:
                for vdd in vdds:
                    row = np.zeros(len(self.feature_names))
                    for j, fname in enumerate(self.feature_names):
                        lo, hi = self.bounds[fname]
                        row[j] = (lo + hi) / 2  # nominal

                    # Override specific params
                    for j, fname in enumerate(self.feature_names):
                        if fname == 'Process':
                            row[j] = proc
                        elif fname == 'Temp':
                            row[j] = temp
                        elif fname in ('Vin', 'Vdd', 'Vdd'):
                            row[j] = vdd

                    rows.append(row)

        X_pvt = np.array(rows)
        Y_pvt = self._compute_outputs(X_pvt)
        return X_pvt, Y_pvt

    # ─── Transient data ───────────────────────────────────────────────────────

    def generate_transient_data(self, params: np.ndarray,
                                 n_timepoints: int = 200,
                                 t_end: float = 100e-6) -> dict:
        """Generate physically realistic transient waveforms."""
        t = np.linspace(0, t_end, n_timepoints)
        n_params = len(params)

        if self.ip_type == 'LDO':
            Vout_nom = 1.8
            tau = t_end * 0.15
            Vout_traj = Vout_nom * (1 - np.exp(-t / tau))
            traj = Vout_traj.reshape(-1, 1)

        elif self.ip_type == 'OTA':
            freq = 1e6
            Vout_traj = 1.0 * np.sin(2 * math.pi * freq * t)
            traj = Vout_traj.reshape(-1, 1)

        elif self.ip_type == 'DCDC':
            D = 0.36
            Vin = 5.0
            Vout_nom = Vin * D
            ripple_f = 1e6
            Vout_traj = Vout_nom + 0.02 * np.sin(2 * math.pi * ripple_f * t)
            traj = Vout_traj.reshape(-1, 1)
        else:
            traj = np.zeros((n_timepoints, 1))

        return {
            't_span': t,
            'trajectories': traj,  # (n_timepoints, state_dim)
        }

    # ─── PyTorch dataset ──────────────────────────────────────────────────────

    def to_torch_dataset(self, n_samples: int = 300,
                          include_transient: bool = False) -> dict:
        """Return dict with FloatTensor X, Y, optional t_span and trajectories."""
        X_np, Y_np = self.generate_lhs(n_samples)

        if _TORCH:
            X_t = torch.FloatTensor(X_np.astype(np.float32))
            Y_t = torch.FloatTensor(Y_np.astype(np.float32))
        else:
            try:
                X_t = torch.FloatTensor(X_np.astype(np.float32))
                Y_t = torch.FloatTensor(Y_np.astype(np.float32))
            except Exception:
                X_t = X_np.astype(np.float32)
                Y_t = Y_np.astype(np.float32)

        result = {'X': X_t, 'Y': Y_t}

        if include_transient:
            td = self.generate_transient_data(X_np[0], n_timepoints=100)
            t_np = td['t_span'].astype(np.float32)
            traj_np = td['trajectories'].astype(np.float32)
            try:
                result['t_span']      = torch.FloatTensor(t_np)
                result['trajectories'] = torch.FloatTensor(traj_np)
            except Exception:
                result['t_span']      = t_np
                result['trajectories'] = traj_np

        return result

    # ─── CSV export ───────────────────────────────────────────────────────────

    def export_csv(self, n_samples: int = 300,
                   filepath: str = 'output/data.csv') -> str:
        os.makedirs(os.path.dirname(filepath) if os.path.dirname(filepath) else '.', exist_ok=True)
        X_np, Y_np = self.generate_lhs(n_samples)

        all_cols = self.feature_names + self.output_names
        data = np.hstack([X_np, Y_np])

        if _PANDAS:
            import pandas as pd
            df = pd.DataFrame(data, columns=all_cols)
            df.to_csv(filepath, index=False)
        else:
            import csv
            with open(filepath, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(all_cols)
                writer.writerows(data.tolist())

        print(f"[DataPipeline] Exported {n_samples} samples → {filepath}")
        print(f"  Features: {self.feature_names}")
        print(f"  Outputs:  {self.output_names}")
        return filepath

    def load_from_csv(self, filepath: str) -> dict:
        """Load training data from CSV file."""
        if _PANDAS:
            import pandas as pd
            df = pd.read_csv(filepath)
            cols = list(df.columns)
            feat_cols = [c for c in cols if c in self.feature_names]
            out_cols  = [c for c in cols if c in self.output_names]
            X_np = df[feat_cols].values.astype(np.float32)
            Y_np = df[out_cols].values.astype(np.float32)
        else:
            import csv
            with open(filepath, encoding='utf-8') as f:
                reader = csv.DictReader(f)
                rows = list(reader)
            if not rows:
                return {}
            cols = list(rows[0].keys())
            feat_cols = [c for c in cols if c in self.feature_names]
            out_cols  = [c for c in cols if c in self.output_names]
            X_np = np.array([[float(r[c]) for c in feat_cols] for r in rows], dtype=np.float32)
            Y_np = np.array([[float(r[c]) for c in out_cols] for r in rows], dtype=np.float32)

        try:
            X_t = torch.FloatTensor(X_np)
            Y_t = torch.FloatTensor(Y_np)
        except Exception:
            X_t = X_np
            Y_t = Y_np

        return {
            'X': X_t,
            'Y': Y_t,
            'feature_names': feat_cols,
            'output_names':  out_cols,
        }
