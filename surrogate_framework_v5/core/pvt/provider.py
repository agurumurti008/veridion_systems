"""
core/pvt/provider.py — ParamProvider ABC + corner parsing.

A ParamProvider answers: "what is the template parameter vector at
(process, vdd, temp), optionally specialized to FSM state `state`?"
Three backends implement it (param_lut, param_blut_store, param_nn);
selection is a constructor argument at the ABModel level.

Corner naming convention (SREF corner list): '<P>_<vdd>V_<temp>C', e.g.
TT_1p8V_27C, SS_1p5V_125C, FF_2p0V_N40C — 'p' is the decimal point and a
leading N on temp means negative.
"""
from __future__ import annotations

import re
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple

_CORNER_RE = re.compile(
    r'^(?P<p>[A-Z]{2})_(?P<v>[0-9]+(?:p[0-9]+)?)V_(?P<t>N?[0-9]+(?:p[0-9]+)?)C$')


def parse_corner(corner: str) -> Tuple[str, float, float]:
    """'SS_1p5V_125C' -> ('SS', 1.5, 125.0); 'FF_2p0V_N40C' -> ('FF', 2.0,
    -40.0). Raises ValueError on anything that doesn't match the SREF
    corner naming convention."""
    m = _CORNER_RE.match(corner.strip())
    if not m:
        raise ValueError(
            f"corner {corner!r} does not match '<P>_<vdd>V_<temp>C' "
            f"(e.g. TT_1p8V_27C, FF_2p0V_N40C)")
    vdd = float(m.group('v').replace('p', '.'))
    t_raw = m.group('t')
    neg = t_raw.startswith('N')
    temp = float(t_raw.lstrip('N').replace('p', '.'))
    return m.group('p'), vdd, (-temp if neg else temp)


def format_corner(process: str, vdd: float, temp: float) -> str:
    v = f"{vdd:g}".replace('.', 'p')
    t = f"{abs(temp):g}".replace('.', 'p')
    sign = 'N' if temp < 0 else ''
    return f"{process}_{v}V_{sign}{t}C"


class ParamProvider(ABC):
    """Uniform PVT parameter backend interface."""

    @abstractmethod
    def get_params(self, process: str, vdd: float, temp: float,
                   state: Optional[str] = None) -> Dict[str, float]:
        """Baseline parameter dict at (process, vdd, temp); when `state`
        is given and a per-state delta is known, the delta is applied on
        top of the baseline."""

    @abstractmethod
    def corners(self) -> List[str]:
        """Training/storage corners this provider was built from."""

    def get_params_for_corner(self, corner: str,
                              state: Optional[str] = None) -> Dict[str, float]:
        p, v, t = parse_corner(corner)
        return self.get_params(p, v, t, state=state)
