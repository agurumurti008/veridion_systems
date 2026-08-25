"""S-parameter-based characterization -- thin wrapper converting S->Y/Z and delegating
to Vector Fitting (the standard practical route: VNA-measured S-parameters are the
cleanest wideband data source for PDN/RLC characterization; see Pozar, Microwave
Engineering, 4th ed., Wiley, 2011 for S<->Y/Z conversion identities).
"""
from __future__ import annotations
import numpy as np
from .vector_fitting import VectorFittingIdentifier
from ..core.base import RLCIdentifier


def s_to_z(S: np.ndarray, z0: float = 50.0) -> np.ndarray:
    """1-port S->Z: Z = z0*(1+S)/(1-S)."""
    return z0 * (1 + S) / (1 - S)


def s_to_y(S: np.ndarray, z0: float = 50.0) -> np.ndarray:
    """1-port S->Y: Y = (1/z0)*(1-S)/(1+S)."""
    return (1.0 / z0) * (1 - S) / (1 + S)


class DeEmbedStub:
    """Pass-through de-embedding interface. Real fixture removal (2x-thru, SOLT,
    TRL) requires measured calibration standards not modeled here -- this stub
    documents the extension point rather than silently no-op-ing without comment."""

    def __init__(self, fixture_model=None):
        self.fixture_model = fixture_model

    def apply(self, S: np.ndarray, w: np.ndarray) -> np.ndarray:
        if self.fixture_model is None:
            return S
        raise NotImplementedError(
            "De-embedding with a real fixture model is not implemented -- this is a "
            "documented extension point, not a silent approximation. Provide "
            "pre-de-embedded S-parameters, or implement de-embedding externally."
        )


class SParameterIdentifier(RLCIdentifier):
    """Frequency-domain fit from raw S-parameters. t_or_f=angular frequency (rad/s),
    y=complex S(jw) (1-port reflection data). kwargs: z0 (reference impedance,
    default 50.0), param_type ('Z'|'Y', default 'Z' -- which the S-data is converted
    to before delegating to VectorFittingIdentifier), de_embed (DeEmbedStub or None),
    plus all VectorFittingIdentifier kwargs (n_poles, n_iterations, etc.)."""

    name = "sparam"

    def fit(self, t_or_f, u, y, order: int | None = None) -> "SParameterIdentifier":
        w = np.asarray(t_or_f, dtype=float)
        S = np.asarray(y, dtype=complex)
        z0 = self.kwargs.get("z0", 50.0)
        param_type = self.kwargs.get("param_type", "Z")
        de_embed = self.kwargs.get("de_embed", None)

        if de_embed is not None:
            S = de_embed.apply(S, w)

        H = s_to_z(S, z0) if param_type == "Z" else s_to_y(S, z0)
        self._param_type = param_type
        self._z0 = z0

        vf_kwargs = {k: v for k, v in self.kwargs.items()
                     if k not in ("z0", "param_type", "de_embed")}
        self._vf = VectorFittingIdentifier(**vf_kwargs)
        self._vf.fit(w, None, H, order=order)

        self._pz = self._vf._pz
        self._ss = self._vf._ss
        self._order_selected = self._vf._order_selected
        return self

    def predict(self, u_new: np.ndarray, t_new: np.ndarray) -> np.ndarray:
        """t_new is the angular-frequency axis; returns the fitted Z (or Y) response,
        not S -- convert back via z_to_s if S-domain comparison is needed."""
        return self._vf.predict(u_new, t_new)

    def is_passive(self) -> bool:
        return self._vf.is_passive()

    def to_spice_netlist(self) -> str:
        return self._vf.to_spice_netlist()
