"""
core/pvt — PVT parameter capture behind one ParamProvider interface.

Backends: LutParamProvider (grid + multilinear interpolation +
nearest-corner fallback), BlutStoreParamProvider (BLUT v8 persistence,
keyed (run_id, corner_id)), NNParamProvider (corner-features -> vector
regression, torch-or-shim). evaluate_providers() makes the LUT-vs-NN
choice data-driven via a holdout interpolation-error table.
"""
from typing import Dict, List

import numpy as np

from .provider import ParamProvider, parse_corner, format_corner
from .param_lut import LutParamProvider
from .param_blut_store import (
    save_param_store, load_param_store, BlutStoreParamProvider,
)
from .param_nn import NNParamProvider


def evaluate_providers(providers: Dict[str, ParamProvider],
                       holdout_corner: str,
                       true_params: Dict[str, float],
                       template=None,
                       vin: float = 5.0, iload: float = 0.05) -> List[dict]:
    """Interpolation-error table at a corner none of the providers
    trained on: per-param % error per provider, plus the resulting spec
    drift (DC vout / iq deltas via template.dc_solve) so the LUT-vs-NN
    choice is data-driven, not asserted.

    Returns one row per parameter plus one '_spec_drift' row per
    provider."""
    rows = []
    preds = {name: prov.get_params_for_corner(holdout_corner)
             for name, prov in providers.items()}
    for pname, true_v in sorted(true_params.items()):
        row = {'param': pname, 'true': float(true_v)}
        for prov_name, pred in preds.items():
            pv = pred.get(pname)
            if pv is None or abs(true_v) < 1e-30:
                row[f'{prov_name}_pct_err'] = None
            else:
                row[f'{prov_name}_pct_err'] = float(
                    100.0 * abs(pv - true_v) / abs(true_v))
        rows.append(row)

    if template is not None:
        op_true = template.dc_solve(true_params, vin, iload)
        for prov_name, pred in preds.items():
            op_p = template.dc_solve(pred, vin, iload)
            rows.append({
                'param': f'_spec_drift[{prov_name}]',
                'true': op_true['vout'],
                f'{prov_name}_vout_drift_mV': float(
                    1e3 * (op_p['vout'] - op_true['vout'])),
                f'{prov_name}_iq_drift_pct': float(
                    100.0 * (op_p['iq'] - op_true['iq'])
                    / max(op_true['iq'], 1e-12)),
            })
    return rows


__all__ = [
    'ParamProvider', 'parse_corner', 'format_corner',
    'LutParamProvider', 'BlutStoreParamProvider', 'NNParamProvider',
    'save_param_store', 'load_param_store', 'evaluate_providers',
]
