"""
core/fsm_completeness — Capability B: quantified FSM state/transition
coverage against a masked (not 2^n) reference space, with a customer-facing
gap report that drives a proceed-or-provide-more-data decision.
"""
from .ip_profiles import IPProfile, get_profile, evaluate
from .state_space import ReferenceStateSpace, build_reference_space
from .coverage import CoverageResult, evaluate_coverage
from .gap_report import GapReport, GapRow, build_gap_report

__all__ = [
    'IPProfile', 'get_profile', 'evaluate',
    'ReferenceStateSpace', 'build_reference_space',
    'CoverageResult', 'evaluate_coverage',
    'GapReport', 'GapRow', 'build_gap_report',
]
