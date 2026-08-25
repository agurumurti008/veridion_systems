"""
core/fitting — staged single-corner system identification + per-state
deltas for the A+B composition.
"""
from .objectives import (
    dc_residuals, transient_residual, transient_features,
    spec_weights, spec_compliance_table,
)
from .vector_fitting import vector_fit, era, RationalFit
from .single_corner_fitter import SingleCornerFitter, FitResult
from .state_delta_fitter import (
    StateDeltaFitter, StateParamSet, extract_state_records,
)

__all__ = [
    'dc_residuals', 'transient_residual', 'transient_features',
    'spec_weights', 'spec_compliance_table',
    'vector_fit', 'era', 'RationalFit',
    'SingleCornerFitter', 'FitResult',
    'StateDeltaFitter', 'StateParamSet', 'extract_state_records',
]
