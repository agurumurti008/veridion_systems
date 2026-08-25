"""
torch_shim.py — NumPy-based torch-compatible shim.
Injected into sys.modules when PyTorch is not installed.
"""
import sys
import numpy as np
import math

print("[torch_shim] PyTorch not found — running with NumPy shim.")


class _Tensor:
    def __init__(self, data, dtype=None):
        if isinstance(data, _Tensor):
            self._d = np.array(data._d, dtype=dtype)
        elif isinstance(data, np.ndarray):
            self._d = data.astype(dtype) if dtype else data.copy()
        else:
            self._d = np.array(data, dtype=dtype)
        self.grad = None
        self.requires_grad = False

    @property
    def shape(self):
        return self._d.shape

    @property
    def data(self):
        return self

    def __repr__(self):
        return f"Tensor({self._d})"

    def __len__(self):
        return len(self._d)

    def __iter__(self):
        for i in range(len(self._d)):
            yield _Tensor(self._d[i])

    def __getitem__(self, idx):
        r = self._d[idx]
        if isinstance(r, np.ndarray):
            return _Tensor(r)
        return r

    def __setitem__(self, idx, val):
        if isinstance(val, _Tensor):
            self._d[idx] = val._d
        else:
            self._d[idx] = val

    def _unwrap(self, other):
        if isinstance(other, _Tensor):
            return other._d
        return other

    def __add__(self, o): return _Tensor(self._d + self._unwrap(o))
    def __radd__(self, o): return _Tensor(self._unwrap(o) + self._d)
    def __sub__(self, o): return _Tensor(self._d - self._unwrap(o))
    def __rsub__(self, o): return _Tensor(self._unwrap(o) - self._d)
    def __mul__(self, o): return _Tensor(self._d * self._unwrap(o))
    def __rmul__(self, o): return _Tensor(self._unwrap(o) * self._d)
    def __truediv__(self, o): return _Tensor(self._d / self._unwrap(o))
    def __rtruediv__(self, o): return _Tensor(self._unwrap(o) / self._d)
    def __neg__(self): return _Tensor(-self._d)
    def __pow__(self, o): return _Tensor(self._d ** self._unwrap(o))
    def __lt__(self, o): return _Tensor(self._d < self._unwrap(o))
    def __le__(self, o): return _Tensor(self._d <= self._unwrap(o))
    def __gt__(self, o): return _Tensor(self._d > self._unwrap(o))
    def __ge__(self, o): return _Tensor(self._d >= self._unwrap(o))
    def __eq__(self, o): return _Tensor(self._d == self._unwrap(o))
    def __float__(self): return float(self._d.flat[0])
    def __int__(self): return int(self._d.flat[0])
    def __index__(self): return int(self._d.flat[0])

    def item(self):
        return self._d.flat[0]

    def numpy(self):
        return self._d

    def float(self):
        return _Tensor(self._d.astype(np.float32))

    def long(self):
        return _Tensor(self._d.astype(np.int64))

    def clone(self):
        return _Tensor(self._d.copy())

    def detach(self):
        return _Tensor(self._d.copy())

    def backward(self, *a, **kw):
        pass

    def mean(self, dim=None):
        if dim is None:
            return _Tensor(np.array(self._d.mean()))
        return _Tensor(self._d.mean(axis=dim))

    def sum(self, dim=None):
        if dim is None:
            return _Tensor(np.array(self._d.sum()))
        return _Tensor(self._d.sum(axis=dim))

    def unsqueeze(self, dim):
        return _Tensor(np.expand_dims(self._d, axis=dim))

    def squeeze(self, dim=None):
        if dim is None:
            return _Tensor(self._d.squeeze())
        return _Tensor(self._d.squeeze(axis=dim))

    def view(self, *shape):
        return _Tensor(self._d.reshape(shape))

    def reshape(self, *s):
        if len(s) == 1 and hasattr(s[0], '__iter__'):
            s = tuple(s[0])
        return _Tensor(self._d.reshape(s))

    def expand(self, *s):
        return _Tensor(np.broadcast_to(self._d, s).copy())

    def dim(self):
        return self._d.ndim

    def size(self, d=None):
        if d is None:
            return self._d.shape
        return self._d.shape[d]

    def t(self):
        return _Tensor(self._d.T)

    def max(self, dim=None):
        if dim is None:
            return _Tensor(np.array(self._d.max()))
        vals = self._d.max(axis=dim)
        idxs = self._d.argmax(axis=dim)
        return _Tensor(vals), _Tensor(idxs)

    def min(self, dim=None):
        if dim is None:
            return _Tensor(np.array(self._d.min()))
        vals = self._d.min(axis=dim)
        idxs = self._d.argmin(axis=dim)
        return _Tensor(vals), _Tensor(idxs)

    def abs(self):
        return _Tensor(np.abs(self._d))

    def sqrt(self):
        return _Tensor(np.sqrt(np.abs(self._d)))

    def exp(self):
        return _Tensor(np.exp(np.clip(self._d, -500, 500)))

    def log(self):
        return _Tensor(np.log(np.abs(self._d) + 1e-30))

    def clamp(self, min=None, max=None):
        return _Tensor(np.clip(self._d, min, max))

    def softmax(self, dim=-1):
        x = self._d - self._d.max(axis=dim, keepdims=True)
        e = np.exp(x)
        return _Tensor(e / (e.sum(axis=dim, keepdims=True) + 1e-30))

    def cat_with(self, other, dim=0):
        return _Tensor(np.concatenate([self._d, self._unwrap(other)], axis=dim))

    @property
    def T(self):
        return _Tensor(self._d.T)

    def tolist(self):
        return self._d.tolist()


class _Parameter(_Tensor):
    def __init__(self, data):
        super().__init__(data if isinstance(data, np.ndarray)
                         else (data._d if isinstance(data, _Tensor) else np.array(data)))
        self.requires_grad = True


class _Module:
    def __init__(self):
        self._params = {}
        self._modules = {}
        self.training = True

    def __setattr__(self, name, val):
        object.__setattr__(self, name, val)
        if isinstance(val, _Parameter):
            if not hasattr(self, '_params'):
                object.__setattr__(self, '_params', {})
            self._params[name] = val
        elif isinstance(val, _Module):
            if not hasattr(self, '_modules'):
                object.__setattr__(self, '_modules', {})
            self._modules[name] = val

    def parameters(self):
        params = list(self._params.values())
        for m in self._modules.values():
            params.extend(m.parameters())
        return params

    def __call__(self, *a, **kw):
        return self.forward(*a, **kw)

    def forward(self, *a, **kw):
        return a[0] if a else None

    def train(self, mode=True):
        self.training = mode
        return self

    def eval(self):
        self.training = False
        return self

    def zero_grad(self):
        pass

    def state_dict(self):
        return {}

    def load_state_dict(self, d, strict=False):
        pass

    def to(self, *a, **kw):
        return self


class _Linear(_Module):
    def __init__(self, in_f, out_f, bias=True):
        super().__init__()
        scale = math.sqrt(2.0 / in_f)
        self.weight = _Parameter(np.random.randn(out_f, in_f).astype(np.float32) * scale)
        self.bias_flag = bias
        if bias:
            self.bias = _Parameter(np.zeros(out_f, dtype=np.float32))

    def forward(self, x):
        d = x._d if isinstance(x, _Tensor) else np.array(x)
        out = d @ self.weight._d.T
        if self.bias_flag:
            out = out + self.bias._d
        return _Tensor(out)


class _LayerNorm(_Module):
    def __init__(self, normalized_shape):
        super().__init__()
        if isinstance(normalized_shape, int):
            normalized_shape = (normalized_shape,)
        self.weight = _Parameter(np.ones(normalized_shape, dtype=np.float32))
        self.bias = _Parameter(np.zeros(normalized_shape, dtype=np.float32))

    def forward(self, x):
        d = x._d if isinstance(x, _Tensor) else np.array(x)
        mu = d.mean(axis=-1, keepdims=True)
        std = d.std(axis=-1, keepdims=True) + 1e-5
        return _Tensor((d - mu) / std * self.weight._d + self.bias._d)


class _SiLU(_Module):
    def forward(self, x):
        d = x._d if isinstance(x, _Tensor) else np.array(x)
        return _Tensor(d * (1 / (1 + np.exp(-np.clip(d, -500, 500)))))


class _Tanh(_Module):
    def forward(self, x):
        d = x._d if isinstance(x, _Tensor) else np.array(x)
        return _Tensor(np.tanh(d))


class _ReLU(_Module):
    def forward(self, x):
        d = x._d if isinstance(x, _Tensor) else np.array(x)
        return _Tensor(np.maximum(0, d))


class _Dropout(_Module):
    def __init__(self, p=0.5):
        super().__init__()
        self.p = p

    def forward(self, x):
        return x  # no dropout in shim (eval-like)


class _Softmax(_Module):
    def __init__(self, dim=-1):
        super().__init__()
        self.dim = dim

    def forward(self, x):
        d = x._d if isinstance(x, _Tensor) else np.array(x)
        e = np.exp(d - d.max(axis=self.dim, keepdims=True))
        return _Tensor(e / (e.sum(axis=self.dim, keepdims=True) + 1e-30))


class _Sequential(_Module):
    def __init__(self, *layers):
        super().__init__()
        self._layers = list(layers)
        for i, l in enumerate(layers):
            self._modules[str(i)] = l

    def forward(self, x):
        for l in self._layers:
            x = l(x)
        return x

    def parameters(self):
        params = []
        for l in self._layers:
            if hasattr(l, 'parameters'):
                params.extend(l.parameters())
        return params


class _ModuleList(_Module):
    def __init__(self, modules=None):
        super().__init__()
        self._list = list(modules) if modules else []
        for i, m in enumerate(self._list):
            self._modules[str(i)] = m

    def __iter__(self):
        return iter(self._list)

    def __len__(self):
        return len(self._list)

    def __getitem__(self, i):
        return self._list[i]

    def append(self, m):
        self._list.append(m)
        self._modules[str(len(self._list) - 1)] = m

    def parameters(self):
        params = []
        for m in self._list:
            if hasattr(m, 'parameters'):
                params.extend(m.parameters())
        return params


class _ParameterDict(_Module):
    def __init__(self, d=None):
        super().__init__()
        self._dict = {}
        if d:
            for k, v in d.items():
                self[k] = v

    def __setitem__(self, k, v):
        self._dict[k] = v
        self._params[k] = v

    def __getitem__(self, k):
        return self._dict[k]

    def __contains__(self, k):
        return k in self._dict

    def keys(self):
        return self._dict.keys()

    def items(self):
        return self._dict.items()

    def parameters(self):
        return list(self._dict.values())


class _functional:
    @staticmethod
    def mse_loss(pred, target, reduction='mean'):
        p = pred._d if isinstance(pred, _Tensor) else np.array(pred)
        t = target._d if isinstance(target, _Tensor) else np.array(target)
        diff = (p - t) ** 2
        if reduction == 'mean':
            return _Tensor(np.array(diff.mean()))
        return _Tensor(diff)

    @staticmethod
    def relu(x):
        d = x._d if isinstance(x, _Tensor) else np.array(x)
        return _Tensor(np.maximum(0, d))

    @staticmethod
    def softmax(x, dim=-1):
        d = x._d if isinstance(x, _Tensor) else np.array(x)
        e = np.exp(d - d.max(axis=dim, keepdims=True))
        return _Tensor(e / (e.sum(axis=dim, keepdims=True) + 1e-30))

    @staticmethod
    def cross_entropy(input, target):
        d = input._d if isinstance(input, _Tensor) else np.array(input)
        t = target._d if isinstance(target, _Tensor) else np.array(target)
        e = np.exp(d - d.max(axis=-1, keepdims=True))
        probs = e / e.sum(axis=-1, keepdims=True)
        n = len(t)
        loss = -np.log(probs[np.arange(n), t.astype(int)] + 1e-30).mean()
        return _Tensor(np.array(loss))


class _Adam:
    def __init__(self, params, lr=1e-3, **kw):
        self.params = list(params)
        self.lr = lr
        self.t = 0
        self.m = [np.zeros_like(p._d) for p in self.params]
        self.v = [np.zeros_like(p._d) for p in self.params]
        self.beta1 = kw.get('betas', (0.9, 0.999))[0]
        self.beta2 = kw.get('betas', (0.9, 0.999))[1]
        self.eps = kw.get('eps', 1e-8)

    def zero_grad(self):
        pass

    def step(self):
        self.t += 1
        for i, p in enumerate(self.params):
            if p.grad is not None:
                g = p.grad._d if isinstance(p.grad, _Tensor) else np.array(p.grad)
                self.m[i] = self.beta1 * self.m[i] + (1 - self.beta1) * g
                self.v[i] = self.beta2 * self.v[i] + (1 - self.beta2) * g ** 2
                m_hat = self.m[i] / (1 - self.beta1 ** self.t)
                v_hat = self.v[i] / (1 - self.beta2 ** self.t)
                p._d -= self.lr * m_hat / (np.sqrt(v_hat) + self.eps)


class _CosineAnnealingLR:
    def __init__(self, optimizer, T_max, eta_min=0):
        self.optimizer = optimizer
        self.T_max = T_max
        self.eta_min = eta_min
        self.t = 0

    def step(self):
        self.t += 1


class _optim:
    Adam = _Adam

    class lr_scheduler:
        CosineAnnealingLR = _CosineAnnealingLR


class _TensorDataset:
    def __init__(self, *tensors):
        self.tensors = tensors

    def __len__(self):
        return len(self.tensors[0])

    def __getitem__(self, i):
        return tuple(t[i] for t in self.tensors)


class _DataLoader:
    def __init__(self, dataset, batch_size=32, shuffle=False, **kw):
        self.dataset = dataset
        self.batch_size = batch_size
        self.shuffle = shuffle

    def __iter__(self):
        n = len(self.dataset)
        indices = np.random.permutation(n) if self.shuffle else np.arange(n)
        for start in range(0, n, self.batch_size):
            batch_idx = indices[start:start + self.batch_size]
            batch = [self.dataset[int(i)] for i in batch_idx]
            if isinstance(batch[0], tuple):
                yield tuple(_stack([b[j] for b in batch]) for j in range(len(batch[0])))
            else:
                yield _stack(batch)

    def __len__(self):
        return max(1, math.ceil(len(self.dataset) / self.batch_size))


class _data:
    TensorDataset = _TensorDataset
    DataLoader = _DataLoader


# Top-level functions
def _FloatTensor(data):
    if isinstance(data, _Tensor):
        return _Tensor(data._d.astype(np.float32))
    return _Tensor(np.array(data, dtype=np.float32))


def _LongTensor(data):
    if isinstance(data, _Tensor):
        return _Tensor(data._d.astype(np.int64))
    return _Tensor(np.array(data, dtype=np.int64))


def _tensor(data, dtype=None):
    if isinstance(data, _Tensor):
        d = data._d
    elif isinstance(data, np.ndarray):
        d = data
    else:
        d = np.array(data)
    if dtype is not None:
        dtype_map = {
            'torch.float32': np.float32,
            'torch.float': np.float32,
            'torch.long': np.int64,
            'torch.int64': np.int64,
        }
        np_dtype = dtype_map.get(str(dtype), np.float32)
        d = d.astype(np_dtype)
    return _Tensor(d.astype(np.float32) if d.dtype.kind == 'f' else d)


def _zeros(*shape, **kw):
    if len(shape) == 1 and hasattr(shape[0], '__iter__'):
        shape = tuple(shape[0])
    return _Tensor(np.zeros(shape, dtype=np.float32))


def _ones(*shape, **kw):
    if len(shape) == 1 and hasattr(shape[0], '__iter__'):
        shape = tuple(shape[0])
    return _Tensor(np.ones(shape, dtype=np.float32))


def _randn(*shape, **kw):
    if len(shape) == 1 and hasattr(shape[0], '__iter__'):
        shape = tuple(shape[0])
    return _Tensor(np.random.randn(*shape).astype(np.float32))


def _stack(tensors, dim=0):
    arrays = [t._d if isinstance(t, _Tensor) else np.array(t) for t in tensors]
    return _Tensor(np.stack(arrays, axis=dim))


def _cat(tensors, dim=0):
    arrays = [t._d if isinstance(t, _Tensor) else np.array(t) for t in tensors]
    return _Tensor(np.concatenate(arrays, axis=dim))


def _exp(x):
    d = x._d if isinstance(x, _Tensor) else np.array(x)
    return _Tensor(np.exp(np.clip(d, -500, 500)))


def _log(x):
    d = x._d if isinstance(x, _Tensor) else np.array(x)
    return _Tensor(np.log(np.abs(d) + 1e-30))


def _abs(x):
    d = x._d if isinstance(x, _Tensor) else np.array(x)
    return _Tensor(np.abs(d))


def _sqrt(x):
    d = x._d if isinstance(x, _Tensor) else np.array(x)
    return _Tensor(np.sqrt(np.abs(d)))


def _clamp(x, min=None, max=None):
    d = x._d if isinstance(x, _Tensor) else np.array(x)
    return _Tensor(np.clip(d, min, max))


def _relu(x):
    d = x._d if isinstance(x, _Tensor) else np.array(x)
    return _Tensor(np.maximum(0, d))


def _linspace(start, end, steps):
    return _Tensor(np.linspace(start, end, steps).astype(np.float32))


def _manual_seed(seed):
    np.random.seed(seed)


class _no_grad:
    def __enter__(self): return self
    def __exit__(self, *a): pass
    def __call__(self, fn):
        def wrapper(*a, **kw): return fn(*a, **kw)
        return wrapper


# Build shim module
class _torch_shim:
    Tensor = _Tensor
    Parameter = _Parameter
    FloatTensor = staticmethod(_FloatTensor)
    LongTensor = staticmethod(_LongTensor)
    tensor = staticmethod(_tensor)
    zeros = staticmethod(_zeros)
    ones = staticmethod(_ones)
    randn = staticmethod(_randn)
    stack = staticmethod(_stack)
    cat = staticmethod(_cat)
    exp = staticmethod(_exp)
    log = staticmethod(_log)
    abs = staticmethod(_abs)
    sqrt = staticmethod(_sqrt)
    clamp = staticmethod(_clamp)
    relu = staticmethod(_relu)
    linspace = staticmethod(_linspace)
    manual_seed = staticmethod(_manual_seed)
    no_grad = _no_grad
    float32 = np.float32
    float64 = np.float64
    int64 = np.int64
    long = np.int64
    nn = None  # set below
    optim = _optim
    utils = None  # set below


class _nn:
    Module = _Module
    Linear = _Linear
    LayerNorm = _LayerNorm
    SiLU = _SiLU
    Tanh = _Tanh
    ReLU = _ReLU
    Dropout = _Dropout
    Softmax = _Softmax
    Sequential = _Sequential
    ModuleList = _ModuleList
    ParameterDict = _ParameterDict
    Parameter = _Parameter
    functional = _functional

    class init:
        @staticmethod
        def xavier_uniform_(tensor):
            d = tensor._d if isinstance(tensor, _Tensor) else tensor
            fan_in = d.shape[-1] if d.ndim > 1 else d.shape[0]
            std = math.sqrt(2.0 / fan_in)
            tensor._d[:] = np.random.randn(*d.shape) * std
            return tensor

        @staticmethod
        def zeros_(tensor):
            tensor._d[:] = 0
            return tensor


class _utils_wrapper:
    data = _data


_torch_shim.nn = _nn
_torch_shim.utils = _utils_wrapper

# Inject into sys.modules
_shim_instance = _torch_shim()

# Make it behave like a module
import types as _types

_torch_mod = _types.ModuleType('torch')
for _k in dir(_torch_shim):
    if not _k.startswith('__'):
        setattr(_torch_mod, _k, getattr(_torch_shim, _k))

_nn_mod = _types.ModuleType('torch.nn')
for _k in dir(_nn):
    if not _k.startswith('__'):
        setattr(_nn_mod, _k, getattr(_nn, _k))

_fn_mod = _types.ModuleType('torch.nn.functional')
for _k in dir(_functional):
    if not _k.startswith('__'):
        setattr(_fn_mod, _k, getattr(_functional, _k))

_optim_mod = _types.ModuleType('torch.optim')
_optim_mod.Adam = _Adam
_lr_mod = _types.ModuleType('torch.optim.lr_scheduler')
_lr_mod.CosineAnnealingLR = _CosineAnnealingLR
_optim_mod.lr_scheduler = _lr_mod

_utils_mod = _types.ModuleType('torch.utils')
_data_mod = _types.ModuleType('torch.utils.data')
_data_mod.TensorDataset = _TensorDataset
_data_mod.DataLoader = _DataLoader
_utils_mod.data = _data_mod

_torch_mod.nn = _nn_mod
_torch_mod.optim = _optim_mod
_torch_mod.utils = _utils_mod
_torch_mod.no_grad = _no_grad

sys.modules['torch'] = _torch_mod
sys.modules['torch.nn'] = _nn_mod
sys.modules['torch.nn.functional'] = _fn_mod
sys.modules['torch.optim'] = _optim_mod
sys.modules['torch.optim.lr_scheduler'] = _lr_mod
sys.modules['torch.utils'] = _utils_mod
sys.modules['torch.utils.data'] = _data_mod
