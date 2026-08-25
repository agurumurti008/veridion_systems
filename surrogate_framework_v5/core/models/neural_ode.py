"""
core/models/neural_ode.py
Neural ODE for circuit transient simulation.
Compatible with real PyTorch AND the NumPy shim (no ._d references).
"""
import numpy as np
import math

try:
    import torch
    import torch.nn as nn
except ImportError:
    import torch_shim  # noqa
    import torch
    import torch.nn as nn

from core.tensor_utils import to_np, scalar, make_float_tensor


def _as_tensor0(v):
    """Wrap a plain python/numpy scalar as a 0-d tensor; pass a tensor
    (real torch or shim `_Tensor`, either may already carry a gradient
    path back to a learnable parameter) through unchanged. Needed because
    `s[i]` on a 1-D tensor returns a genuine 0-d (grad-connected) tensor
    under real PyTorch but a bare python/numpy scalar under torch_shim's
    `_Tensor.__getitem__` — see that class for why (shim tensors don't
    track gradients at all, so this is only a shape-uniformity concern
    there, not a correctness one)."""
    if hasattr(v, 'reshape'):
        return v
    return torch.tensor(float(v))


class CircuitODEFunction(nn.Module):
    def __init__(self, state_dim: int, param_dim: int, ip_type: str = 'LDO'):
        super().__init__()
        self.state_dim = state_dim
        self.param_dim = param_dim
        self.ip_type   = ip_type.upper()

        self.log_gm = nn.Parameter(torch.tensor(math.log(5e-3)))
        self.log_ro = nn.Parameter(torch.tensor(math.log(1e4)))
        self.log_cl = nn.Parameter(torch.tensor(math.log(1e-11)))

        self.residual_net = nn.Sequential(
            nn.Linear(state_dim + param_dim + 1, 64), nn.Tanh(),
            nn.Linear(64, 64), nn.Tanh(),
            nn.Linear(64, state_dim),
        )

    @property
    def gm(self): return math.exp(scalar(self.log_gm))
    @property
    def ro(self): return math.exp(scalar(self.log_ro))
    @property
    def cl(self): return math.exp(scalar(self.log_cl))

    def _physics_t(self, t_f, s):
        """Tensor-native right-hand side — replaces the old _ldo/_ota/
        _dcdc numpy helpers, which ran self.gm/ro/cl (both already
        detached via `scalar()`) through plain float arithmetic and
        returned a bare np.ndarray: a real ODE surrogate needs THIS
        function's output connected all the way back to log_gm/log_ro/
        log_cl AND to `s` (itself the previous integration step's output,
        for backprop-through-time across the Euler rollout in
        CircuitNeuralODE._euler_integrate) — building it with to_np()
        anywhere severs both, the same class of bug fixed in
        core/models/pinn.py's CircuitPINN.forward(). `s` is a 1-D tensor
        of length state_dim; `t_f` is a plain python float (time is an
        independent variable here, never a learnable parameter, so
        detaching it costs nothing)."""
        gm = torch.exp(self.log_gm)
        ro = torch.exp(self.log_ro)
        cl = torch.exp(self.log_cl)
        vout = s[0]

        if self.ip_type == 'LDO':
            dvdt = (gm * 0.9 - vout / ro) / cl
            second = -vout * 0.01
        elif self.ip_type == 'OTA':
            vdiff = s[1] if self.state_dim > 1 else \
                0.1 * math.sin(2 * math.pi * 1e6 * t_f)
            dvdt = (gm * vdiff - vout / ro) / cl
            second = -vdiff * 0.001
        elif self.ip_type == 'DCDC':
            d, vin = 0.36, 5.0
            dvdt = (d * vin - vout) / (ro * cl)
            second = (d * vin - vout) / 1e-6
        else:
            return torch.zeros(self.state_dim)

        parts = [dvdt.reshape(1)]
        if self.state_dim > 1:
            parts.append(_as_tensor0(second).reshape(1))
        if self.state_dim > 2:
            parts.append(torch.zeros(self.state_dim - 2))
        return torch.cat(parts)

    def forward(self, t, state):
        t_f = scalar(t)
        if hasattr(state, 'reshape'):
            s = state.reshape(-1)
        else:
            s = make_float_tensor(np.asarray(state, dtype=np.float32)).reshape(-1)
        if s.shape[0] < self.state_dim:
            s = torch.cat([s, torch.zeros(self.state_dim - s.shape[0])])
        s = s[:self.state_dim]

        phys = self._physics_t(t_f, s)

        param_zeros = torch.zeros(self.param_dim)
        t_tensor = torch.tensor([t_f])
        res_in = torch.cat([s, param_zeros, t_tensor]).reshape(1, -1)
        res_out = self.residual_net(res_in).reshape(-1)[:self.state_dim]

        dstate = phys + 0.1 * res_out
        return dstate


class CircuitNeuralODE(nn.Module):
    def __init__(self, state_dim, param_dim, n_fsm_states=4, ip_type='LDO'):
        super().__init__()
        self.state_dim    = state_dim
        self.param_dim    = param_dim
        self.n_fsm_states = max(n_fsm_states, 1)
        self.ip_type      = ip_type

        self.ode_funcs = nn.ModuleList([
            CircuitODEFunction(state_dim, param_dim, ip_type)
            for _ in range(self.n_fsm_states)
        ])
        self.state_clf = nn.Sequential(
            nn.Linear(state_dim + param_dim, 32), nn.ReLU(),
            nn.Linear(32, self.n_fsm_states), nn.Softmax(dim=-1),
        )
        self.ic_net = nn.Sequential(
            nn.Linear(param_dim, 64), nn.ReLU(),
            nn.Linear(64, state_dim),
        )

    def _euler_integrate(self, params_t, t_span_np, x0_t, n_steps=200):
        """Real-gradient Euler rollout — the previous version pulled `x`
        back to numpy (`to_np(...)`) on every single step to feed
        state_clf/ode_fn and then re-wrapped the result via
        make_float_tensor(), which under real PyTorch creates a fresh
        LEAF tensor with no grad_fn: the returned 'trajectory' was
        therefore never connected to ode_funcs'/state_clf's parameters no
        matter how it was later used in a loss — the NODE analogue of the
        exact bug already fixed in core/models/pinn.py's
        CircuitPINN.forward(). Kept entirely as tensor ops here (`x`
        itself carries the graph forward from one Euler step to the
        next — genuine backprop-through-time), so
        Phase2SimAugmented._train_node's loss.backward() now has a real
        path back to every ode_fn's log_gm/log_ro/log_cl/residual_net and
        to state_clf's weights."""
        t_start = float(t_span_np[0])
        t_end   = float(t_span_np[-1])
        t_lin   = np.linspace(t_start, t_end, n_steps)

        x = x0_t
        if x.shape[0] < self.state_dim:
            x = torch.cat([x, torch.zeros(self.state_dim - x.shape[0])])
        x = x[:self.state_dim]

        trajectory   = [x]
        fsm_sequence = []

        for i in range(1, n_steps):
            dt  = float(t_lin[i] - t_lin[i-1])
            t_i = float(t_lin[i])

            clf_in = torch.cat([x, params_t]).reshape(1, -1)
            sw = self.state_clf(clf_in).reshape(-1)
            fsm_sequence.append(int(np.argmax(to_np(sw))))

            dxdt = torch.zeros(self.state_dim)
            for j, ode_fn in enumerate(self.ode_funcs):
                dx_j = ode_fn(t_i, x)
                dxdt = dxdt + sw[j] * dx_j

            dxdt = torch.clamp(dxdt, -1e10, 1e10)
            x    = x + dt * dxdt
            trajectory.append(x)

        return {
            'trajectory':   torch.stack(trajectory, dim=0),
            'fsm_sequence': np.array(fsm_sequence),
        }

    def forward(self, params, t_span, initial_state=None) -> dict:
        params_np  = to_np(params).reshape(-1).astype(np.float64)
        if len(params_np) < self.param_dim:
            params_np = np.pad(params_np, (0, self.param_dim - len(params_np)))
        params_np = params_np[:self.param_dim]
        params_t = make_float_tensor(params_np.astype(np.float32))

        t_span_np = to_np(t_span).reshape(-1)

        if initial_state is None:
            p_t = params_t.reshape(1, -1)
            x0  = self.ic_net(p_t).reshape(-1)  # tensor — keeps grad path to ic_net
        else:
            x0  = make_float_tensor(to_np(initial_state).reshape(-1).astype(np.float32))

        result = self._euler_integrate(params_t, t_span_np, x0)
        result['initial_conditions'] = to_np(x0)
        return result
