"""
core/models/pinn.py
Physics-Informed Neural Network for circuit surrogate modelling.
Compatible with real PyTorch AND the NumPy shim (no ._d references).
"""
import numpy as np
import math

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
except ImportError:
    import torch_shim  # noqa
    import torch
    import torch.nn as nn
    import torch.nn.functional as F

from core.tensor_utils import to_np, scalar, make_float_tensor


class PhysicsConstraintLayer(nn.Module):
    def __init__(self, physics_rules: list):
        super().__init__()
        self.physics_rules = physics_rules
        n = max(len(physics_rules), 1)
        self.rule_weights = nn.Parameter(torch.ones(n) * 0.1)

    def _unwrap(self, v):
        """Always return numpy scalar from any tensor type."""
        return float(scalar(v)) if v is not None else 0.0

    def kcl_loss(self, predictions: dict) -> float:
        keys = ['I_pass', 'I_load', 'I_feedback', 'I_out', 'I_tail']
        available = [k for k in keys if k in predictions]
        if len(available) < 2:
            return 0.0
        vals = [to_np(predictions[k]).ravel() for k in available]
        total = vals[0].copy()
        for v in vals[1:]:
            n = min(len(total), len(v))
            total[:n] -= v[:n]
        return float(np.mean(total ** 2))

    def kvl_loss(self, predictions: dict) -> float:
        if all(k in predictions for k in ('V_vin', 'V_dropout', 'V_vout')):
            diff = (to_np(predictions['V_vin']) -
                    to_np(predictions['V_dropout']) -
                    to_np(predictions['V_vout']))
            return float(np.mean(diff ** 2))
        return 0.0

    def energy_conservation_loss(self, predictions: dict) -> float:
        if 'P_in' in predictions and 'P_out' in predictions:
            violation = to_np(predictions['P_out']) - to_np(predictions['P_in'])
            return float(np.mean(np.maximum(0, violation) ** 2))
        return 0.0

    def compute_all_losses(self, predictions_dict: dict, inputs) -> torch.Tensor:
        total = 0.0
        weights = to_np(self.rule_weights).ravel()
        for i, rule in enumerate(self.physics_rules):
            w = float(weights[i]) if i < len(weights) else 1.0
            rtype = rule.get('type', '')
            if rtype == 'KCL':
                loss = self.kcl_loss(predictions_dict)
            elif rtype == 'KVL':
                loss = self.kvl_loss(predictions_dict)
            elif rtype == 'energy':
                loss = self.energy_conservation_loss(predictions_dict)
            else:
                loss = 0.0
            total += w * loss
        return torch.tensor(float(total))


class SpecAwareLossLayer(nn.Module):
    def __init__(self, spec_constraints: list, active_specs: list = None):
        super().__init__()
        self.spec_constraints = spec_constraints
        self.active_specs = active_specs or [s.name for s in spec_constraints]

    def forward(self, predictions, output_names: list = None) -> torch.Tensor:
        if output_names is None:
            return torch.tensor(0.0)
        pred_np = to_np(predictions)
        total = 0.0
        for spec in self.spec_constraints:
            if spec.name not in self.active_specs:
                continue
            if spec.name not in output_names:
                continue
            idx = output_names.index(spec.name)
            if idx >= pred_np.shape[-1]:
                continue
            col = pred_np[:, idx] if pred_np.ndim > 1 else pred_np
            lo  = np.maximum(0, spec.min_val - col)
            hi  = np.maximum(0, col - spec.max_val)
            total += spec.transient_weight * float(np.mean(lo ** 2 + hi ** 2))
        return torch.tensor(total)


class AnalysisBridgeLayer(nn.Module):
    def __init__(self, active_bridges: dict):
        super().__init__()
        self.active_bridges = active_bridges
        self.scale_factors = nn.ParameterDict({
            k.replace('.', '_'): nn.Parameter(torch.ones(1))
            for k in active_bridges.keys()
        })

    def forward(self, analysis_results: dict) -> dict:
        outputs = {}
        pi = math.pi
        for bridge_key, bridge_info in self.active_bridges.items():
            safe = bridge_key.replace('.', '_')
            if bridge_key == 'AC.phase_margin':
                pm = float(analysis_results.get('phase_margin', 60.0))
                zeta = max(0.01, min(0.99, pm / 100.0))
                val = math.exp(-pi * zeta / math.sqrt(max(1e-9, 1 - zeta**2))) * 100
            elif bridge_key == 'AC.gain_bandwidth':
                gbw  = float(analysis_results.get('gain_bandwidth', 1e6))
                pm   = float(analysis_results.get('phase_margin', 60.0))
                zeta = max(0.01, pm / 100.0)
                wn   = 2 * pi * gbw
                val  = -math.log(0.02) / (zeta * wn + 1e-30)
            elif bridge_key == 'AC.unity_gain_freq':
                bw  = float(analysis_results.get('unity_gain_freq', 1e6))
                val = 0.35 / (bw + 1e-30)
            elif bridge_key == 'PSRR.psrr_dc':
                psrr = float(analysis_results.get('psrr_dc', 60.0))
                vin  = float(analysis_results.get('v_ripple_in', 0.1))
                val  = vin / (10 ** (psrr / 20.0))
            elif bridge_key == 'NOISE.thermal_noise':
                k   = 1.38e-23
                T   = float(analysis_results.get('temperature', 300.0))
                C   = float(analysis_results.get('capacitance', 1e-12))
                val = math.sqrt(k * T / (C + 1e-30))
            elif bridge_key == 'DC.operating_point':
                val = float(analysis_results.get('dc_op', 0.0))
            elif bridge_key == 'CMRR.cmrr_dc':
                cmrr = float(analysis_results.get('cmrr_dc', 80.0))
                vcm  = float(analysis_results.get('v_cm_in', 0.1))
                val  = vcm / (10 ** (cmrr / 20.0))
            else:
                val = 0.0
            if safe in self.scale_factors:
                val *= scalar(self.scale_factors[safe])
            outputs[bridge_key] = torch.tensor(float(val))
        return outputs


def _build_mlp(in_d, out_d, hidden):
    layers = []
    cur = in_d
    for h in hidden:
        layers += [nn.Linear(cur, h), nn.LayerNorm(h), nn.SiLU(), nn.Dropout(0.05)]
        cur = h
    layers.append(nn.Linear(cur, out_d))
    return nn.Sequential(*layers)


class CircuitPINN(nn.Module):
    def __init__(self, input_dim, output_dim, hidden_dims=None, n_states=4,
                 physics_rules=None, spec_constraints=None, active_bridges=None):
        super().__init__()
        self.input_dim  = input_dim
        self.output_dim = output_dim
        self.n_states   = max(n_states, 1)
        hd = hidden_dims or [64, 64, 32]

        self.state_nets = nn.ModuleList([
            _build_mlp(input_dim, output_dim, hd) for _ in range(self.n_states)
        ])
        self.feature_extractor = _build_mlp(input_dim, hd[-1], hd[:-1])
        self.state_gate = nn.Sequential(
            nn.Linear(input_dim + self.n_states, self.n_states),
            nn.Softmax(dim=-1),
        )
        self.pole_zero_head = nn.Linear(hd[-1], 6)
        # Input normalization stats — identity (mean 0, std 1) until
        # set_input_scaler() is called, so forward() is a safe no-op
        # transform for any caller that never trains this instance (e.g.
        # the shape-only unit tests). Stored on the model itself, not
        # just inside the trainer's local scope, so EVERY subsequent
        # forward() call — this trainer's own eval, or any OTHER caller's
        # separate eval pass on a held-out split — applies the identical
        # transform the network was actually trained on; without this, a
        # caller evaluating on raw/unscaled inputs after training would
        # silently feed the network out-of-distribution values.
        self._x_mean = np.zeros(input_dim, dtype=np.float32)
        self._x_std = np.ones(input_dim, dtype=np.float32)
        self.physics_layer  = PhysicsConstraintLayer(physics_rules or [])
        self.spec_layer     = SpecAwareLossLayer(
            spec_constraints or [],
            [s.name for s in (spec_constraints or [])]
        )
        self.bridge_layer   = AnalysisBridgeLayer(active_bridges or {})

    def set_input_scaler(self, x_mean: np.ndarray, x_std: np.ndarray):
        """Store train-set input z-score stats — see the __init__
        docstring note on _x_mean/_x_std for why this lives on the model
        rather than only inside the trainer's local scope."""
        x_std = np.asarray(x_std, dtype=np.float32)
        x_std = np.where(x_std < 1e-8, 1.0, x_std)
        self._x_mean = np.asarray(x_mean, dtype=np.float32)
        self._x_std = x_std

    def forward(self, x, state_onehot=None, analysis_results=None) -> dict:
        # x/state_onehot are DATA (never require grad themselves), so
        # round-tripping them through numpy here is harmless — unlike
        # everything computed from them below. Confirmed (2026-08-18)
        # via test_pinn_forward_shape et al still passing plus a direct
        # loss-decrease check: the PREVIOUS version of this method
        # rebuilt every intermediate (gate, each state sub-net's output,
        # the final weighted sum) through to_np()/plain-numpy arithmetic
        # before wrapping the result back in make_float_tensor() — under
        # real PyTorch that silently severs the autograd graph between
        # `predictions` and state_nets'/state_gate's parameters, so
        # `_train_pinn`'s total_loss.backward() either raised (caught by
        # its bare `except Exception: pass`) or produced zero gradient —
        # no parameter EVER updated, regardless of epoch count or input
        # scaling (a second, independent PINN bug from the missing-
        # feature-scaling one already fixed in Phase2SimAugmented.
        # _train_pinn). Fixed by keeping every step from `gate` onward
        # as a genuine tensor op (torch.cat/torch.stack/broadcasted
        # multiply-and-sum), never round-tripped through numpy/float().
        x_np = to_np(x).astype(np.float32)
        x_np = (x_np - self._x_mean) / self._x_std
        batch = x_np.shape[0]
        x_t = make_float_tensor(x_np)

        if state_onehot is None:
            soh_np = np.zeros((batch, self.n_states), dtype=np.float32)
            soh_np[:, 0] = 1.0
            soh_t = make_float_tensor(soh_np)
        else:
            soh_np = to_np(state_onehot).astype(np.float32)
            if soh_np.shape[-1] != self.n_states:
                tmp = np.zeros((batch, self.n_states), dtype=np.float32)
                tmp[:, 0] = 1.0
                soh_np = tmp
            soh_t = make_float_tensor(soh_np)

        gate_in = torch.cat([x_t, soh_t], dim=-1)
        gate = self.state_gate(gate_in)  # (batch, n_states) — gradient-tracked

        # Per-sample weighted sum across state sub-nets, entirely in
        # tensor ops so the gradient path back to every state sub-net's
        # (and state_gate's) parameters stays intact.
        state_outs = torch.stack([net(x_t) for net in self.state_nets], dim=1)
        pred = (gate.unsqueeze(-1) * state_outs).sum(dim=1)

        feat = self.feature_extractor(x_t)
        pz = self.pole_zero_head(feat)

        bridge_feats = {}
        if analysis_results:
            bridge_feats = self.bridge_layer(analysis_results)

        return {
            'predictions':    pred,
            'pole_zero':      pz,
            'bridge_features': bridge_feats,
            'state_gates':    gate,
        }

    def compute_loss(self, outputs: dict, targets, circuit_state=None) -> dict:
        # data_loss MUST stay a genuine tensor op on outputs['predictions']
        # (not float(np.mean(...)), which discards the graph the same way
        # forward()'s old numpy round-tripping did) — this is the term
        # that actually needs to backprop into the network; physics/spec/
        # bridge below are already numpy-evaluated "soft" side terms (a
        # deliberate, separate design choice, not touched here) and stay
        # plain floats/detached tensors, which is fine: tensor + float
        # arithmetic preserves data_loss's graph in both real PyTorch and
        # the torch_shim.
        pred = outputs['predictions']
        target_t = targets if hasattr(targets, 'shape') else \
            make_float_tensor(np.asarray(targets, dtype=np.float32))
        data_loss = ((pred - target_t) ** 2).mean()

        phys_loss = scalar(self.physics_layer.compute_all_losses(
            circuit_state or {}, outputs['predictions']))
        spec_loss  = 0.0
        bridge_val = sum(float(scalar(v))
                         for v in outputs.get('bridge_features', {}).values())
        bridge_loss = bridge_val * 0.001

        # total = data_loss (tensor) + plain-float terms -> stays a
        # tensor, still connected to data_loss's graph. Returned AS-IS
        # (never re-wrapped via torch.tensor(total), which would create a
        # detached leaf copy exactly like forward()'s old bug) so
        # _train_pinn's total_loss.backward() has a real graph to walk.
        total = data_loss + 0.1 * phys_loss + 0.01 * spec_loss + bridge_loss

        return {
            'total':   total,
            'data':    torch.tensor(float(scalar(data_loss))),
            'physics': torch.tensor(phys_loss),
            'spec':    torch.tensor(spec_loss),
            'bridge':  torch.tensor(bridge_loss),
        }


# ---------------------------------------------------------------------------
# BLUT-derived output -> physics-variable-key mapping
# ---------------------------------------------------------------------------
# PhysicsConstraintLayer.kcl_loss / kvl_loss (above) expect predictions_dict
# keys drawn from the physics rules' own free-text equations (e.g. I_pass,
# I_load, I_feedback, V_vin, V_dropout, V_vout — see build_ldo_kg's
# PhysicsRule.equation strings in core/spec_kg/knowledge_graph.py). Real
# BLUT-derived voltage/current outputs are keyed by SpecKG names instead
# (VOUT, IOUT, Dropout_Voltage, ...), so without this mapping step the KCL/
# KVL loss terms silently see an empty/mismatched dict and contribute zero
# physics loss regardless of how physically correct or incorrect the data
# actually is.

import re as _re

_PHYSICS_VAR_ALIASES = {
    # physics-variable suffix (the part after I_/V_/P_) -> list of
    # normalized (lowercase, alnum-only) SpecKG-name patterns that should
    # resolve to it. Extend this table when adding new IP types/physics
    # rules whose equations introduce new variable name conventions.
    "vout":     ["vout", "outputvoltage"],
    "vin":      ["vin", "inputvoltage"],
    "vref":     ["vref", "referencevoltage"],
    "dropout":  ["dropoutvoltage", "vdropout", "dropout"],
    "load":     ["iload", "loadcurrent", "outputcurrent", "iout"],
    "pass":     ["ipass", "passcurrent"],
    "feedback": ["ifeedback", "feedbackcurrent"],
    "tail":     ["itail", "tailcurrent", "slewrate"],
    "out":      ["iout", "outputcurrent"],
    "in":       ["pin", "inputpower"],
    "diff":     ["vdiff", "differentialvoltage"],
}


def _normalize_name(name: str) -> str:
    return _re.sub(r"[^a-z0-9]", "", name.lower())


def _extract_physics_var_names(spec_kg) -> list:
    """Parse every PhysicsRule.equation string for this SpecKG and return
    the set of I_*/V_*/P_* variable-like tokens referenced anywhere in
    them (physics rules have no separate structured variable-name field —
    the equation string is the only source of truth for these names)."""
    var_names = set()
    for rule in spec_kg.physics_rules:
        tokens = _re.findall(r"[A-Za-z_][A-Za-z0-9_]*", rule.equation)
        for t in tokens:
            if t.startswith(("I_", "V_", "P_")):
                var_names.add(t)
    return sorted(var_names)


def _map_predictions_to_physics_keys(spec_kg, output_signal_names: list, Y_row) -> dict:
    """Build a predictions_dict keyed with the physics variable names that
    PhysicsConstraintLayer.kcl_loss/kvl_loss already expect, from one row
    (or a column-batch) of BLUT-derived voltage/current outputs whose
    columns are named by output_signal_names (SpecKG-native names, e.g.
    'VOUT', 'IOUT', 'Dropout_Voltage').

    Y_row may be a 1D array (single sample) or a 2D array (batch, one
    column per output_signal_names entry) — either way, each physics key
    maps to the corresponding column (kept as an array if 2D, so
    PhysicsConstraintLayer's to_np()-based losses average over the batch).

    Matching is done via _PHYSICS_VAR_ALIASES: for every physics variable
    name found in this SpecKG's physics_rules equations (e.g. 'I_load'),
    its suffix ('load') is looked up in the alias table, and every
    output_signal_names entry whose normalized form matches one of that
    suffix's aliases is bound to that physics key. An output name may bind
    to more than one physics key (e.g. IOUT binding to both I_load and
    I_out is intentional when a rule's equation uses either name for the
    same physical current), and a physics key with no matching output is
    simply absent from the returned dict (that rule then contributes zero
    loss for this batch, same as if the data were missing entirely — this
    is a graceful degradation, not a silent corruption of the loss value).
    """
    Y_arr = np.asarray(Y_row)
    is_2d = Y_arr.ndim == 2

    physics_var_names = _extract_physics_var_names(spec_kg)
    result = {}
    unmatched_physics_vars = []

    for var_name in physics_var_names:
        prefix, _, suffix = var_name.partition("_")
        aliases = _PHYSICS_VAR_ALIASES.get(suffix, [suffix])
        norm_aliases = [_normalize_name(a) for a in aliases]

        matched_col = None
        for j, out_name in enumerate(output_signal_names):
            norm_out = _normalize_name(out_name)
            if norm_out in norm_aliases or any(
                a in norm_out or norm_out in a for a in norm_aliases
            ):
                matched_col = j
                break

        if matched_col is None:
            unmatched_physics_vars.append(var_name)
            continue

        col = Y_arr[:, matched_col] if is_2d else Y_arr[matched_col]
        result[var_name] = make_float_tensor(np.asarray(col, dtype=np.float32))

    return result

