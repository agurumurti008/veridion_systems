"""
core/fsm_completeness/ip_profiles.py — 4.4 multi-IP generalization.

An IP-class profile declares the dominance hierarchy, canonical states,
minimum transition set, and required transient captures for a class, so the
same completeness machinery serves every IP. Built-in profiles are the
source of truth; configs/ip_profiles.yaml (if present + pyyaml available)
overrides/extends them. Unknown IP -> generic profile + a notice, never a
crash.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

try:
    import yaml
    _YAML = True
except ImportError:                       # pragma: no cover
    _YAML = False


@dataclass
class IPProfile:
    ip_type: str
    dominance_hierarchy: List[str]        # fsm_role tiers, high -> low
    canonical_states: List[str]
    min_transitions: List[Tuple[str, str]]
    required_transients: List[str]        # e.g. load_step, line_step, inrush
    mode_split_roles: List[str] = field(default_factory=list)
    settling_role: str = 'load_step'
    is_generic: bool = False
    complete: bool = True                 # is the class knowledge filled in?


_LDO = IPProfile(
    ip_type='LDO',
    dominance_hierarchy=['supply_ok', 'enable', 'fault', 'override', 'ready',
                         'mode_select', 'supply_select', 'output_select',
                         'scan_mode', 'trim'],
    canonical_states=['DISABLED', 'STARTUP', 'REGULATION', 'DROPOUT',
                      'FAULT', 'SCAN'],
    min_transitions=[('DISABLED', 'STARTUP'), ('STARTUP', 'REGULATION'),
                     ('REGULATION', 'DROPOUT'), ('DROPOUT', 'REGULATION'),
                     ('REGULATION', 'FAULT'), ('FAULT', 'DISABLED'),
                     ('REGULATION', 'DISABLED')],
    required_transients=['line_step', 'load_step', 'enable_inrush'],
    mode_split_roles=['mode_select'], settling_role='load_step', complete=True)

# DCDC / PLL skeletons: declared fields complete, class knowledge minimal
# but honest (marked complete=False so the gap report flags the profile).
_DCDC = IPProfile(
    ip_type='DCDC',
    dominance_hierarchy=['supply_ok', 'enable', 'fault', 'mode_select',
                         'scan_mode'],
    canonical_states=['DISABLED', 'SOFT_START', 'CCM', 'DCM', 'FAULT',
                      'HICCUP'],
    min_transitions=[('DISABLED', 'SOFT_START'), ('SOFT_START', 'CCM'),
                     ('CCM', 'DCM'), ('DCM', 'CCM'), ('CCM', 'FAULT'),
                     ('FAULT', 'HICCUP')],
    required_transients=['line_step', 'load_step', 'soft_start'],
    mode_split_roles=['mode_select'], settling_role='load_step',
    complete=False)

_PLL = IPProfile(
    ip_type='PLL',
    dominance_hierarchy=['supply_ok', 'enable', 'reset', 'lock', 'mode_select'],
    canonical_states=['DISABLED', 'RESET', 'ACQUIRE', 'LOCKED', 'UNLOCKED'],
    min_transitions=[('DISABLED', 'RESET'), ('RESET', 'ACQUIRE'),
                     ('ACQUIRE', 'LOCKED'), ('LOCKED', 'UNLOCKED'),
                     ('UNLOCKED', 'ACQUIRE')],
    required_transients=['reference_step', 'lock_acquire'],
    mode_split_roles=[], settling_role='lock_acquire', complete=False)

_BUILTIN: Dict[str, IPProfile] = {'LDO': _LDO, 'DCDC': _DCDC, 'PLL': _PLL}

_YAML_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'configs',
                          'ip_profiles.yaml')


def _load_yaml(path: str) -> Dict[str, IPProfile]:
    if not (_YAML and path and os.path.exists(path)):
        return {}
    with open(path, encoding='utf-8') as f:
        raw = yaml.safe_load(f) or {}
    out = {}
    for ip, d in (raw.get('profiles', {}) or {}).items():
        out[ip.upper()] = IPProfile(
            ip_type=ip.upper(),
            dominance_hierarchy=list(d.get('dominance_hierarchy', [])),
            canonical_states=list(d.get('canonical_states', [])),
            min_transitions=[tuple(t) for t in d.get('min_transitions', [])],
            required_transients=list(d.get('required_transients', [])),
            mode_split_roles=list(d.get('mode_split_roles', [])),
            settling_role=d.get('settling_role', 'load_step'),
            complete=bool(d.get('complete', True)))
    return out


def get_profile(ip_type: str,
                yaml_path: Optional[str] = None) -> Tuple[IPProfile, str]:
    """Return (profile, notice). YAML overrides built-ins; an unknown IP
    yields a generic single-state profile with a notice string (never
    raises)."""
    ip = (ip_type or '').upper()
    profiles = dict(_BUILTIN)
    profiles.update(_load_yaml(yaml_path or _YAML_PATH))
    if ip in profiles:
        p = profiles[ip]
        notice = '' if p.complete else \
            f'{ip} profile is a skeleton (class knowledge minimal)'
        return p, notice
    generic = IPProfile(
        ip_type=ip or 'UNKNOWN',
        dominance_hierarchy=['supply_ok', 'enable', 'mode_select'],
        canonical_states=['DISABLED', 'ACTIVE'],
        min_transitions=[('DISABLED', 'ACTIVE'), ('ACTIVE', 'DISABLED')],
        required_transients=['enable_inrush'], is_generic=True, complete=False)
    return generic, f'no profile for IP type {ip!r}; using generic profile'


def evaluate(ip_type: str, fsm_result, runs, registry=None,
             insight_findings=None, yaml_path: Optional[str] = None,
             **coverage_kw):
    """Dispatch completeness evaluation through the IP profile. fsm_result:
    object/dict with state_defs + transitions; runs: list of RunView (or run
    dicts). Returns a CoverageResult (see coverage.py)."""
    from .state_space import build_reference_space
    from .coverage import evaluate_coverage
    profile, notice = get_profile(ip_type, yaml_path)
    ref = build_reference_space(fsm_result, profile, registry=registry)
    result = evaluate_coverage(ref, fsm_result, runs, profile,
                               registry=registry,
                               insight_findings=insight_findings,
                               **coverage_kw)
    if notice:
        result.notices.append(notice)
    return result, ref, profile
