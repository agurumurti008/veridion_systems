"""
core/templates/pin_taxonomy.py — SREF pin-category mapping.

Maps the SREF_LDO1V2_LP pin list onto the categories
{supply, ground, enable, mode, trim, bias, sense, analog_io, scan}
and onto LdoPmosTemplate mode/parameter hooks. Pins whose template hook
cannot be inferred from the pin name/spec alone carry hook=None +
questionnaire=True and are enumerated in
configs/sref_architecture_questionnaire.yaml with the safe default in
use. Never silently invent SREF internals (delivery contract).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class PinInfo:
    name: str
    category: str            # supply|ground|enable|mode|trim|bias|sense|analog_io|scan
    hook: Optional[str]      # template hook name, None if deferred
    questionnaire: bool      # True -> semantics deferred to the questionnaire
    safe_default: str        # behavior used while the questionnaire is open
    note: str


PIN_TAXONOMY: Dict[str, PinInfo] = {p.name: p for p in [
    # ── Control pins with inferable template hooks ──────────────────────────
    PinInfo('EN_LDO', 'enable', 'enable', False,
            'gates the error amp; 0 -> DISABLED',
            'Primary enable (spec fsm_role=enable)'),
    PinInfo('HIGH_POWER_MODE', 'mode', 'hp_lp', False,
            'scales {Gm_ea, I_ea_max} by hp_gm_scale, I_lim by hp_ilim_scale',
            'HP/LP mode select (spec fsm_role=mode_select)'),
    PinInfo('UVLO_GD_OR_OVERRIDE_MPOS', 'mode', 'uvlo_override', True,
            'treated as observed UVLO-good status; override polarity/priority '
            'deferred', 'Named "GD OR OVERRIDE" — whether 1 forces uvlo_ok=1 '
            'regardless of V_in, or merely reports it, is not inferable'),
    PinInfo('EN_UVLO_1V2', 'mode', 'uvlo_enable', True,
            'observed as a ready/status bit (spec fsm_role=ready); not fed '
            'back into the analog core',
            'Spec marks it status/ready; whether it enables the UVLO '
            'comparator or reports its output is not inferable'),

    # ── Mux/select pins — semantics deferred ────────────────────────────────
    PinInfo('VPWR_SEL', 'mode', None, True,
            'ignored by the analog core (V_SUPPLY assumed the active source)',
            'Supply mux select between VPWR and V_SUPPLY — mux semantics '
            'deferred to questionnaire'),
    PinInfo('PAD_VDD1V2_SEL', 'mode', None, True,
            'ignored by the analog core (internal VDD_1V2 assumed the '
            'regulated node)',
            'Output/pad mux select — which node the pad follows is deferred'),
    PinInfo('FS_V_SUPPLY_TO_MOST_POS', 'scan', None, True,
            'ignored (assumed test-only domain crossing)',
            'Force/sense of V_SUPPLY onto MOST_POS — test-mode semantics '
            'deferred'),

    # ── Scan pins ────────────────────────────────────────────────────────────
    PinInfo('SCAN_MODE_VSUPPLY', 'scan', 'scan', True,
            'scan=1 treated as a DISABLED-class switch state (zero analog '
            'deltas)', 'Scan-mode supply behavior deferred'),
    PinInfo('EN_SCAN_MODE_MPOS', 'scan', 'scan', True,
            'scan=1 treated as a DISABLED-class switch state (zero analog '
            'deltas)', 'Scan enable for the MOST_POS domain — deferred'),

    # ── Test-load / sense pins ───────────────────────────────────────────────
    PinInfo('SREF_ADD_LDO1V2_LOAD_MPOS', 'mode', 'test_load', True,
            'adds no load (0 A) until the questionnaire supplies the value',
            'Switchable test load; magnitude not inferable'),
    PinInfo('SREF_EN_ISENSE_LDO1V2_MPOS', 'sense', 'isense', True,
            'isense path modeled as ideal (no burden) when enabled',
            'Current-sense architecture (series/mirror, burden) deferred'),
    PinInfo('SREF_LDO_ISNS_DIS_MPOS', 'sense', 'isense', True,
            'isense disable observed only', 'Complement of isense enable'),

    # ── Bias pins ────────────────────────────────────────────────────────────
    PinInfo('IBIAS_SNK_25nA_0', 'bias', 'bias', False,
            '25 nA sink expected; window check only (no analog dependence '
            'until trim map arrives)', 'Bias sink bit 0'),
    PinInfo('IBIAS_SNK_25nA_1', 'bias', 'bias', False,
            '25 nA sink expected; window check only', 'Bias sink bit 1'),
    PinInfo('IBIAS_SNK_25nA_2', 'bias', 'bias', False,
            '25 nA sink expected; window check only', 'Bias sink bit 2'),
    PinInfo('ICONST_75A', 'bias', 'bias', False,
            'constant-current bias; window check only', 'Constant bias input'),

    # ── Analog I/O ───────────────────────────────────────────────────────────
    PinInfo('VFB', 'analog_io', 'feedback', False,
            'template feedback node (v_fb)', 'External feedback sense'),
    PinInfo('VREF', 'analog_io', 'reference', False,
            'template V_ref input', 'Bandgap reference input'),
    PinInfo('floop_in', 'analog_io', 'feedback', True,
            'observed only (loop-probe input assumed shorted to floop_out '
            'in mission mode)', 'STB loop-probe pin pair — mission-mode '
            'strapping deferred'),
    PinInfo('floop_out', 'analog_io', None, True,
            'observed only', 'STB loop-probe output side'),

    # ── Supplies / grounds ───────────────────────────────────────────────────
    PinInfo('V_SUPPLY', 'supply', 'vin', False,
            'template V_in (active source per VPWR_SEL safe default)',
            'Primary 5 V supply'),
    PinInfo('VPWR', 'supply', None, True,
            'window-checked only; not the active source under the safe '
            'default', 'Alternate supply behind VPWR_SEL'),
    PinInfo('MOST_POS', 'supply', None, True,
            'window-checked only', 'Most-positive rail (test crossing)'),
    PinInfo('FUN_DC', 'supply', None, True,
            'window-checked only', 'Function/DC test supply'),
    PinInfo('ISO', 'supply', None, True,
            'window-checked only', 'Isolation rail'),
    PinInfo('VDD_1V2', 'supply', 'vout', False,
            'template v_out (regulated node)', 'Regulated 1.2 V output'),
    PinInfo('VDD_1V2_EXT', 'supply', None, True,
            'window-checked only', 'External 1.2 V behind PAD_VDD1V2_SEL'),
    PinInfo('AVSS', 'ground', 'gnd', False,
            'template ground reference', 'Analog ground'),
    PinInfo('GND', 'ground', 'gnd', False,
            'template ground reference (tied to AVSS)', 'Global ground'),
    PinInfo('PBKG', 'ground', None, False,
            'window-checked only (bulk tie)', 'P-substrate/bulk'),
]}


def categorize_pin(name: str) -> str:
    """Category for a pin; unknown pins fall back by name heuristics so a
    renamed testbench net still lands somewhere sensible."""
    if name in PIN_TAXONOMY:
        return PIN_TAXONOMY[name].category
    u = name.upper()
    if 'SCAN' in u:
        return 'scan'
    if u.startswith('IBIAS') or u.startswith('ICONST'):
        return 'bias'
    if 'VSS' in u or u in ('GND', 'PBKG'):
        return 'ground'
    if u.startswith('V') or 'SUPPLY' in u or 'PWR' in u:
        return 'supply'
    if u.startswith('EN'):
        return 'enable'
    return 'analog_io'


def hook_for_pin(name: str) -> Optional[str]:
    info = PIN_TAXONOMY.get(name)
    return info.hook if info else None


def questionnaire_pins() -> List[PinInfo]:
    """Every pin whose semantics are deferred to the questionnaire."""
    return [p for p in PIN_TAXONOMY.values() if p.questionnaire]
