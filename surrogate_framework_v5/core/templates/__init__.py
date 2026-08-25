"""
core/templates — Strategy B analog-architecture backbones.

A template is a parameterized physical circuit architecture (ODEs +
DC/small-signal views + Verilog-A core emission). Parameters live in a
ParamManifest; fitted values come from core/fitting; PVT variation comes
from core/pvt providers; the FSM mode layer wraps a template instance in
core/ab_integration.
"""
from .param_manifest import ParamSpec, ParamManifest
from .base_template import AnalogTemplate
from .ldo_pmos_template import LdoPmosTemplate
from .pin_taxonomy import (
    PIN_TAXONOMY, categorize_pin, hook_for_pin, questionnaire_pins,
)

__all__ = [
    'ParamSpec', 'ParamManifest', 'AnalogTemplate', 'LdoPmosTemplate',
    'PIN_TAXONOMY', 'categorize_pin', 'hook_for_pin', 'questionnaire_pins',
]
