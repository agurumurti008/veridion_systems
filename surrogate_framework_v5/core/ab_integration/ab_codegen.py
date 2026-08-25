"""
core/ab_integration/ab_codegen.py — Verilog-A emission of the A+B model.

Contract (Section 7 of the build prompt):
- Pin interface generated from the IP's spec JSON (port list, order,
  directions, domains) — never hardcoded.
- Supply-sensitive connect modules: one declaration block per distinct
  logic voltage domain, referencing that domain's supply/ground nets as
  named in the spec JSON, pins grouped under it.
- <pin>_ok self-checks for every supply/ground/bulk/bias pin (voltage or
  current windows from the JSON ranges), ANDed into supplies_ok which
  forces the FSM to DISABLED and holds analog contributions safe.
- FSM state-register updates via the $bound_step timestep-sampling
  pattern; no @(cross) inside case arms (illegal Verilog-A).
- Analog core as contribution statements; per-state parameter overrides
  through case(current_state) on the delta'd subset.
- PVT: LUT provider exported as $table_model-compatible 3-D tables
  (P index, V, T); NN deployment requires table export (no NN inference
  in Verilog-A) — documented in the header.
- Both V(vout) regulation and I(vin) draw are emitted.
"""
from __future__ import annotations

import os
from typing import Dict, List, Optional

import numpy as np

from core.fsm.fsm_codegen import _vid
from core.pvt.provider import parse_corner
from .ab_model_builder import ABModel, _parse_guard

def _direction(port) -> str:
    # Single source of truth for pin direction (explicit Port.direction
    # wins; output/status -> output, supply/ground/bulk/inout -> inout,
    # else input). Status indicators are DUT-driven and emit as outputs.
    from core.spec_kg.knowledge_graph import port_direction
    return port_direction(port)


def _logic_domains(spec_kg) -> Dict[tuple, List]:
    """Group digital-domain pins by their (lo, hi) voltage range — the spec
    JSON's per-pin voltage domain entry."""
    groups: Dict[tuple, List] = {}
    for p in spec_kg.ports:
        if p.domain == 'digital':
            key = (float(p.voltage_range[0]), float(p.voltage_range[1]))
            groups.setdefault(key, []).append(p)
    return groups


def _domain_supply_nets(spec_kg, dom_range: tuple) -> tuple:
    """(supply_net, ground_net) a logic domain converts against. The spec
    JSON does not name each logic pin's supply explicitly (recon flag /
    questionnaire item): candidates are supply-typed pins whose range
    upper bound covers the domain's upper bound; among them the primary is
    the taxonomy 'vin'-hook pin, else the one with the largest declared
    current capability (spec order breaks ties). No pin-name literals —
    if the spec declares no supply/ground at all, an explicit UNRESOLVED
    placeholder is emitted rather than a guessed name. Resolution itself
    lives in core.spec_kg.port_bounds.resolve_supply_ground, shared with
    core.fsm.fsm_codegen's per-pin supplySensitivity/groundSensitivity
    attributes — this just adapts the (lo, hi) domain-range group form to
    that per-port-object helper via a lightweight stand-in."""
    from types import SimpleNamespace
    from core.spec_kg.port_bounds import resolve_supply_ground
    return resolve_supply_ground(SimpleNamespace(voltage_range=dom_range),
                                 spec_kg.ports)


def emit_pvt_tables(ab_model: ABModel, outdir: str,
                    basename: str = 'ldo_ab') -> List[str]:
    """$table_model-compatible 3-D tables (P index, vdd, temp -> value),
    one .tbl per baseline parameter, from the model's provider corners.
    Process letters map to integer indices in sorted order (documented in
    each file header). Returns the written paths."""
    os.makedirs(outdir, exist_ok=True)
    corners = ab_model.provider.corners()
    meta = {c: parse_corner(c) for c in corners}
    procs = sorted({m[0] for m in meta.values()})
    proc_idx = {p: i for i, p in enumerate(procs)}
    vecs = {c: ab_model.provider.get_params_for_corner(c) for c in corners}
    names = sorted(vecs[corners[0]].keys())
    paths = []
    for name in names:
        path = os.path.join(outdir, f'{basename}_{_vid(name)}.tbl')
        with open(path, 'w', encoding='utf-8') as f:
            f.write(f'# $table_model data for parameter {name}\n')
            f.write('# columns: p_idx vdd temp value\n')
            f.write('# p_idx: ' + ', '.join(
                f'{i}={p}' for p, i in sorted(proc_idx.items(),
                                              key=lambda kv: kv[1])) + '\n')
            for c in sorted(corners):
                p, v, t = meta[c]
                f.write(f'{proc_idx[p]} {v:g} {t:g} {vecs[c][name]:.9g}\n')
        paths.append(path)
    return paths


def emit(ab_model: ABModel, corner: str = 'TT_1p8V_27C',
         table_dir: Optional[str] = None, fsm_ts: float = 1e-7,
         iq_signatures: Optional[dict] = None,
         limitations: Optional[list] = None,
         load_enrichment: Optional[list] = None) -> str:
    """Emit the composed A+B Verilog-A module. `corner` selects the
    baseline parameter values inlined as parameter defaults (PVT tables
    carry the full grid).

    Insights integration (Section 5) — all optional and purely additive;
    with all three None the output is byte-identical to the POC emitter
    (regression guard):
      iq_signatures  : {state_name: (Iq_mean_A, Iq_std_A)} from 3.10 -> per-
                       state I(vin) currents where fitting lacked direct data.
      limitations    : accepted Option-2 gap-report limitations -> `LIMITATIONS:`
                       header lines.
      load_enrichment: 3.8 dummy-load proposals -> load-model comment."""
    kg = ab_model.spec_kg
    tpl = ab_model.template
    man = tpl.manifest()
    ports = list(kg.ports)
    baseline = ab_model.provider.get_params_for_corner(corner)
    sps = ab_model.state_param_set

    state_ids = sorted(ab_model.state_defs.keys())
    state_names = {sid: _vid(ab_model.state_defs[sid]['name'])
                   for sid in state_ids}
    disabled_sid = ab_model._state_id_by_name('DISABLED')

    guard_pins: List[str] = []
    for tr in ab_model.transitions:
        for nm, _ in _parse_guard(tr.conditions):
            if nm not in guard_pins:
                guard_pins.append(nm)

    ok_windows = ab_model.ok_windows()
    delta_names = sorted({n for d in (sps.deltas.values() if sps else [])
                          for n in d.keys()})

    L: List[str] = []
    A = L.append
    A(f'// Auto-generated A+B Verilog-A model — {kg.ip_type} '
      f'(FSM layer: learned; analog core: LdoPmosTemplate)')
    A('// Generated by surrogate_framework ab_codegen')
    A('//')
    A(f'// Baseline parameter values inlined for corner {corner}.')
    A('// PVT: baseline parameters are exported as $table_model-compatible')
    A('// 3-D tables (P index, vdd, temp) from the LUT provider — see the')
    A("// companion .tbl files (emit_pvt_tables). Example per-parameter use:")
    A('//   Gm_ea_pvt = $table_model(p_idx, vdd, temp,'
      ' "ldo_ab_Gm_ea.tbl", "1L,1L,1L");')
    A('// NOTE: the NN provider cannot deploy to Verilog-A (no NN inference')
    A('// in VA) — NN-provider deployment requires exporting its predictions')
    A('// through emit_pvt_tables to the same .tbl form.')
    if limitations:
        A('//')
        A('// LIMITATIONS (Option-2 gap-report: model proceeds with these '
          'uncharacterized):')
        for lim in limitations:
            A(f'// LIMITATIONS: {lim}')
    if load_enrichment:
        A('//')
        A('// Load model — auto-detected internal loads (3.8 dummy-load):')
        for e in load_enrichment:
            A(f'//   {e.get("pin")}: internal_load '
              f'+{e.get("added_load_A", 0.0)*1e6:.1f} uA on assertion')
    A('')
    A('`include "disciplines.vams"')
    A('`include "constants.vams"')
    A('')

    # ── Supply-sensitive connect modules, one block per logic domain ──────
    A('// ─── Supply-sensitive connect modules (logic pins, per spec-JSON')
    A('//     voltage domain). L2E/E2L conversion tracks the named domain')
    A('//     supply/ground nets, not a global default. ───')
    for dom, pins in sorted(_logic_domains(kg).items()):
        sup, gnd = _domain_supply_nets(kg, dom)
        nominal = (dom[0] + dom[1]) / 2.0
        dom_tag = _vid(f'{sup}_{dom[1]:g}V'.replace('.', 'p'))
        A(f'// domain {sup}/{gnd}: logic range [{dom[0]:g}, {dom[1]:g}] V '
          f'(nominal {nominal:g} V) — from spec JSON voltage_range of:')
        A('//   pins: ' + ', '.join(p.name for p in pins))
        A(f'connectmodule ab_e2l_{dom_tag}(a, d);')
        A(f'    input a;  electrical a;   // analog side, {sup}-referenced')
        A('    output d; ddiscrete d;    // logic side')
        A(f'    parameter real vth = {nominal:g};  '
          f'// midpoint of [{dom[0]:g}, {dom[1]:g}] from spec JSON')
        A('    logic dval;')
        A('    assign d = dval;')
        A('    always @(above(V(a) - vth)) dval = 1;')
        A('    always @(above(vth - V(a))) dval = 0;')
        A('endconnectmodule')
        A(f'connectmodule ab_l2e_{dom_tag}(d, a);')
        A('    input d;  ddiscrete d;')
        A(f'    output a; electrical a;   // drives V({sup})/V({gnd}) levels')
        A('    analog V(a) <+ transition((d !== 0) ? '
          f'V({sup}, {gnd}) : 0.0, 0, 1n, 1n);')
        A('endconnectmodule')
        A('')

    # ── Module + port list straight from the spec JSON, JSON order ────────
    port_ids = [_vid(p.name) for p in ports]
    A(f'module {kg.ip_type.lower()}_ab_model(')
    A('    ' + ', '.join(port_ids))
    A(');')
    A('')
    for d in ('input', 'output', 'inout'):
        grp = [_vid(p.name) for p in ports if _direction(p) == d]
        if grp:
            A(f'    {d} {", ".join(grp)};')
    A(f'    electrical {", ".join(port_ids)};')
    A('    electrical n_vg, n_vc;  // EA output node, compensator node')
    A('')

    # ── Parameters: baseline (corner-inlined) + logic thresholds ──────────
    A(f'    // Baseline template parameters @ {corner} (PVT via .tbl files)')
    for name in man.names:
        val = baseline.get(name, man.spec(name).default)
        A(f'    parameter real {name} = {val:.6g};  // {man.spec(name).unit}')
    A('')
    A('    // Logic thresholds per guard pin (midpoint of spec-JSON range)')
    for pin in guard_pins:
        A(f'    parameter real VTH_{_vid(pin)} = '
          f'{ab_model.logic_threshold(pin):g};')
    A(f'    parameter real fsm_ts = {fsm_ts:g};  '
      '// FSM sampling bound for $bound_step')
    A('')

    # ── State encoding ─────────────────────────────────────────────────────
    for sid in state_ids:
        A(f'    parameter integer {state_names[sid]} = {sid};')
    A('')
    A('    integer current_state;')
    A('    integer supplies_ok;')
    for pin in ok_windows:
        A(f'    integer {_vid(pin)}_ok;')
    for pin in guard_pins:
        A(f'    integer {_vid(pin)}_b;')
    A('    real Gm_ea_eff, I_ea_max_eff, I_lim_eff, I_q_eff;')
    A('    real v_fb, i_ea, i_comp, v_sg, vov, v_sd, i_sq, i_pass, en_gate;')
    A('')

    vin_id = _vid(ab_model.pin_map['vin'])
    vout_id = _vid(ab_model.pin_map['vout'])
    gnd_id = _vid(ab_model.pin_map['gnd'])
    hp_id = _vid(ab_model.pin_map['hp'])
    en_id = _vid(ab_model.pin_map['enable'])

    A('    analog begin')
    A('        // FSM sampling: bound the solver timestep so state-register')
    A('        // updates are re-evaluated at least every fsm_ts (the')
    A("        // repo's corrected pattern; cross-event controls inside case")
    A('        // arms are illegal Verilog-A and are never emitted).')
    A('        $bound_step(fsm_ts);')
    A('')
    A('        @(initial_step) begin')
    A(f'            current_state = {state_names[disabled_sid]};')
    A('        end')
    A('')

    # ── _ok self-checks from spec JSON windows ─────────────────────────────
    A('        // ── Pin self-checks (windows from the spec JSON) ──')
    for pin, win in ok_windows.items():
        pid = _vid(pin)
        if win['kind'] == 'voltage':
            A(f'        {pid}_ok = ((V({pid}, {gnd_id}) >= {win["lo"]:g}) &&'
              f' (V({pid}, {gnd_id}) <= {win["hi"]:g})) ? 1 : 0;'
              f'  // {pin}.{win["source"]}')
        else:
            A(f'        {pid}_ok = ((I({pid}) >= {win["lo"]:g}) &&'
              f' (I({pid}) <= {win["hi"]:g})) ? 1 : 0;'
              f'  // {pin}.{win["source"]}')
    A('        supplies_ok = ' + ' && '.join(
        f'{_vid(pin)}_ok' for pin in ok_windows) + ';')
    A('')

    # ── guard pin binarization ─────────────────────────────────────────────
    A('        // ── Control-pin logic levels ──')
    for pin in guard_pins:
        pid = _vid(pin)
        A(f'        {pid}_b = (V({pid}, {gnd_id}) > VTH_{pid}) ? 1 : 0;')
    A('')

    # ── FSM next-state (sampled every bounded timestep) ────────────────────
    A('        // ── FSM: supplies_ok gate outranks every learned guard ──')
    A('        if (!supplies_ok)')
    A(f'            current_state = {state_names[disabled_sid]};')
    A('        else case (current_state)')
    for sid in state_ids:
        outs = sorted((tr for tr in ab_model.transitions
                       if tr.from_state == sid),
                      key=lambda tr: -len(tr.conditions))
        A(f'            {state_names[sid]}: begin')
        for k, tr in enumerate(outs):
            terms = _parse_guard(tr.conditions)
            if not terms:
                continue
            guard = ' && '.join(f'({_vid(nm)}_b == {val})'
                                for nm, val in terms)
            kw = 'if' if k == 0 else 'else if'
            A(f'                // learned: {tr.from_name} -> {tr.to_name} '
              f'(p={tr.probability:.3f})')
            A(f'                {kw} ({guard})')
            A(f'                    current_state = '
              f'{state_names.get(tr.to_state, state_names[disabled_sid])};')
        if not outs:
            A('                // no learned outgoing transitions')
        A('            end')
    A('        endcase')
    A('')

    # ── Per-state parameter overrides on the delta'd subset ───────────────
    A('        // ── Per-state parameter overrides (fitted deltas) ──')
    A(f'        Gm_ea_eff = Gm_ea * ((V({hp_id}, {gnd_id}) > '
      f'VTH_{hp_id}) ? hp_gm_scale : 1.0);'
      if ab_model.pin_map['hp'] in guard_pins else
      '        Gm_ea_eff = Gm_ea;')
    A('        I_ea_max_eff = I_ea_max;')
    A('        I_lim_eff = I_lim;')
    A('        I_q_eff = I_q * lp_iq_scale;')
    # Per-state override lines: fitted deltas, plus (3.10) a measured-Iq
    # I_q_eff where fitting lacked direct current data. Building the lines
    # first keeps the delta-only output byte-identical when iq_signatures is
    # absent (regression guard).
    per_state_lines: dict = {}
    if sps and delta_names:
        for sid in state_ids:
            nm = ab_model.state_defs[sid]['name']
            deltas = sps.deltas.get(nm, {})
            if not deltas:
                continue
            lines = []
            for pname, dv in sorted(deltas.items()):
                eff = f'{pname}_eff' if pname in (
                    'Gm_ea', 'I_ea_max', 'I_lim', 'I_q') else pname
                base_v = baseline.get(pname, man.spec(pname).default)
                lines.append(f'                {eff} = {base_v + dv:.6g};'
                             f'  // baseline {base_v:.6g} + delta {dv:+.3g}')
            per_state_lines[sid] = lines
    if iq_signatures:
        for sid in state_ids:
            nm = ab_model.state_defs[sid]['name']
            sig = iq_signatures.get(nm)
            if sig is None:
                continue
            per_state_lines.setdefault(sid, []).append(
                f'                I_q_eff = {abs(sig[0]):.6g};'
                f'  // 3.10 measured Iq (sigma {sig[1]:.2g} A)')
    if per_state_lines:
        A('        case (current_state)')
        for sid in state_ids:
            if sid not in per_state_lines:
                continue
            A(f'            {state_names[sid]}: begin')
            for line in per_state_lines[sid]:
                A(line)
            A('            end')
        A('            default: ;')
        A('        endcase')
    A('')

    # ── Analog core (template equations, gated by supplies_ok) ────────────
    A('        // ── Analog core (LdoPmosTemplate equations) ──')
    A(f'        en_gate = ((current_state != {state_names[disabled_sid]}) &&'
      f' supplies_ok && (V({en_id}, {gnd_id}) > VTH_{en_id})) ? 1.0 : 0.0;'
      if ab_model.pin_map['enable'] in guard_pins else
      f'        en_gate = ((current_state != {state_names[disabled_sid]})'
      ' && supplies_ok) ? 1.0 : 0.0;')
    A(f'        v_fb = V({vout_id}, {gnd_id}) * Rf2 / (Rf1 + Rf2);')
    A('        // inverting gate drive (negative feedback, PMOS pass)')
    A('        i_ea = en_gate * I_ea_max_eff *'
      ' tanh(Gm_ea_eff * (v_fb - V_ref) / I_ea_max_eff);')
    A('        i_comp = (V(n_vg) - V(n_vc)) / Rz;')
    A('        I(n_vg) <+ (C_ea + Cgs) * ddt(V(n_vg));')
    A('        I(n_vg) <+ -i_ea + i_comp;')
    A(f'        I(n_vg) <+ (en_gate > 0.5) ? V(n_vg) / R_ea'
      f' : (V(n_vg) - V({vin_id}, {gnd_id})) / R_ea;')
    A(f'        I(n_vg) <+ -Cgs * ddt(V({vin_id}, {gnd_id}));')
    A('        I(n_vc) <+ Cc * ddt(V(n_vc) - V(' + vout_id + f', {gnd_id}));')
    A('        I(n_vc) <+ -i_comp;')
    A(f'        v_sg = V({vin_id}, {gnd_id}) - V(n_vg);')
    A('        vov  = v_sg - Vth_p;')
    A(f'        v_sd = V({vin_id}, {vout_id});')
    A('        if ((vov > 0) && (v_sd > 0)) begin')
    A('            if (v_sd >= vov)')
    A('                i_sq = 0.5 * Kp * vov * vov * (1 + lambda_p * v_sd);')
    A('            else  // triode branch IS dropout')
    A('                i_sq = Kp * (vov * v_sd - 0.5 * v_sd * v_sd)'
      ' * (1 + lambda_p * v_sd);')
    A('        end else')
    A('            i_sq = 0.0;')
    A('        i_pass = en_gate * I_lim_eff * tanh(i_sq / I_lim_eff);')
    A('        // both behaviors emitted: V(vout) regulation AND I(vin) draw')
    A(f'        I({vin_id}, {vout_id}) <+ i_pass;')
    A(f'        I({vin_id}, {gnd_id})  <+ (en_gate > 0.5)'
      ' ? I_q_eff : 0.05 * I_q_eff;')
    A(f'        I({vout_id}, {gnd_id}) <+ V({vout_id}, {gnd_id})'
      ' / (Rf1 + Rf2);')
    A(f'        I({vout_id}, {gnd_id}) <+ k_load * V({vout_id}, {gnd_id});')
    A(f'        I({vout_id}, {gnd_id}) <+ -Cgd *'
      f' ddt(V({vin_id}, {gnd_id}) - V(n_vg));')
    A(f'        I({vout_id}, {gnd_id}) <+ C_out *'
      f' ddt(V({vout_id}, {gnd_id}));')
    A('        // supplies_ok low -> held safe: pass device off (en_gate=0),')
    A(f'        // V({vout_id}) bleeds to the ground reference')
    A(f'        I({vout_id}, {gnd_id}) <+ (supplies_ok ? 0.0'
      f' : V({vout_id}, {gnd_id}) / 1k);')
    A('    end')
    A('')
    A(f'endmodule  // {kg.ip_type.lower()}_ab_model')

    text = '\n'.join(L)
    if table_dir is not None:
        emit_pvt_tables(ab_model, table_dir)
    return text
