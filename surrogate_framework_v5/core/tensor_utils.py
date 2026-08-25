"""
core/tensor_utils.py
Unified tensor ↔ numpy conversion that works with both real PyTorch
and the NumPy shim.  Import _to_np / _to_tensor everywhere instead
of checking ._d directly.
"""
import numpy as np


def to_np(x) -> np.ndarray:
    """Convert any tensor/array to numpy float64 array."""
    if x is None:
        return None
    if isinstance(x, np.ndarray):
        return x.astype(np.float64)
    # Shim tensor
    if hasattr(x, '_d'):
        return np.array(x._d, dtype=np.float64)
    # Real PyTorch tensor
    try:
        return x.detach().cpu().numpy().astype(np.float64)
    except Exception:
        pass
    return np.array(x, dtype=np.float64)


def to_f32(x) -> np.ndarray:
    """Convert to float32 numpy (for feeding back into torch)."""
    return to_np(x).astype(np.float32)


def scalar(x) -> float:
    """Extract a Python float from any scalar tensor/array."""
    if isinstance(x, (int, float)):
        return float(x)
    if isinstance(x, np.ndarray):
        return float(x.flat[0])
    if hasattr(x, '_d'):
        return float(x._d.flat[0])
    try:
        return float(x.item())
    except Exception:
        return float(x)


def make_float_tensor(arr):
    """Make a FloatTensor from a numpy array, works with shim or real torch."""
    import torch
    arr = np.array(arr, dtype=np.float32)
    return torch.FloatTensor(arr)


def assign_col(tensor, col_idx: int, value: float):
    """Set tensor[:, col_idx] = value — works shim or real."""
    if hasattr(tensor, '_d'):
        tensor._d[:, col_idx] = value
    else:
        tensor[:, col_idx] = value


def get_shape(tensor):
    """Return shape tuple."""
    if hasattr(tensor, '_d'):
        return tensor._d.shape
    return tuple(tensor.shape)
