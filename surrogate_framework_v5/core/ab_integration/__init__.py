"""
core/ab_integration — A+B composition: learned FSM (Strategy A) as the
mode/control layer over a fitted analog template (Strategy B), with
PVT-provided parameters, plus structural Verilog-A emission.
"""
from .ab_model_builder import ABModel, build_ab_model, DEFAULT_PIN_MAP
from .ab_codegen import emit, emit_pvt_tables
from .insights_pipeline import run_insights_phase, InsightsPhaseResult

__all__ = ['ABModel', 'build_ab_model', 'DEFAULT_PIN_MAP',
           'emit', 'emit_pvt_tables',
           'run_insights_phase', 'InsightsPhaseResult']
