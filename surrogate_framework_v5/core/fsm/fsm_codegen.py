"""
core/fsm/fsm_codegen.py
FSM Validator + Verilog-A / SystemVerilog code generator.
"""
import re
from typing import Dict, List, Optional
from collections import deque


def _vid(name: str) -> str:
    """Sanitize a signal/state name into a legal Verilog identifier
    (hierarchical BLUT names contain '.', '!', '[', ']')."""
    ident = re.sub(r'[^A-Za-z0-9_$]', '_', str(name))
    if ident and ident[0].isdigit():
        ident = '_' + ident
    return ident


# Expected states/transitions per IP type
IP_EXPECTED_STATES = {
    'LDO': ['DISABLED', 'STARTUP', 'REGULATION', 'DROPOUT', 'FAULT', 'SHUTDOWN'],
    'OTA': ['DISABLED', 'STARTUP', 'ACTIVE', 'SLEWING', 'SETTLED'],
    'DCDC': ['DISABLED', 'SOFT_START', 'CCM', 'DCM', 'FAULT', 'HICCUP'],
}

IP_EXPECTED_TRANSITIONS = {
    'LDO': [
        ('DISABLED', 'STARTUP'), ('STARTUP', 'REGULATION'),
        ('REGULATION', 'DROPOUT'), ('REGULATION', 'FAULT'),
        ('DROPOUT', 'REGULATION'), ('FAULT', 'DISABLED'),
    ],
    'OTA': [
        ('DISABLED', 'STARTUP'), ('STARTUP', 'ACTIVE'),
        ('ACTIVE', 'SLEWING'), ('SLEWING', 'ACTIVE'),
        ('ACTIVE', 'SETTLED'),
    ],
    'DCDC': [
        ('DISABLED', 'SOFT_START'), ('SOFT_START', 'CCM'),
        ('CCM', 'DCM'), ('DCM', 'CCM'), ('CCM', 'FAULT'),
        ('FAULT', 'HICCUP'),
    ],
}


class ValidationReport:
    def __init__(self):
        self.reachability: bool = False
        self.completeness: bool = False
        self.determinism: bool = False
        self.speckg_coverage: float = 0.0
        self.missing_states: List[str] = []
        self.missing_transitions: List[tuple] = []
        self.warnings: List[str] = []
        self.errors: List[str] = []

    def __repr__(self):
        return (f"ValidationReport(reachability={self.reachability}, "
                f"completeness={self.completeness}, "
                f"determinism={self.determinism}, "
                f"coverage={self.speckg_coverage:.1%})")


class FSMValidator:
    """Validate detected FSM for correctness and completeness."""

    def __init__(self, spec_kg=None):
        self.spec_kg = spec_kg

    def validate(self, state_defs: Dict, transitions: list,
                 ip_type: str = 'LDO') -> ValidationReport:
        report = ValidationReport()

        state_ids = set(state_defs.keys())
        state_names = {s['name'] for s in state_defs.values()}

        # Build adjacency
        adj: Dict[int, List[int]] = {s: [] for s in state_ids}
        for t in transitions:
            adj[t.from_state].append(t.to_state)

        # 1. Reachability (BFS from state 0)
        if state_ids:
            start = 0
            visited = set()
            queue = deque([start])
            while queue:
                node = queue.popleft()
                if node in visited:
                    continue
                visited.add(node)
                for nb in adj.get(node, []):
                    if nb not in visited:
                        queue.append(nb)
            report.reachability = len(visited) == len(state_ids)
            if not report.reachability:
                unreachable = state_ids - visited
                report.warnings.append(
                    f"Unreachable states: {[state_defs[s]['name'] for s in unreachable]}"
                )
        else:
            report.reachability = True

        # 2. Completeness: every non-terminal state has ≥1 outgoing transition
        non_terminal = [s for s in state_ids if s in adj and len(adj[s]) > 0]
        no_outgoing = [s for s in state_ids
                       if not adj.get(s) and state_defs[s]['name'] not in
                       ['SHUTDOWN', 'FAULT', 'DISABLED']]
        report.completeness = len(no_outgoing) == 0
        if no_outgoing:
            report.warnings.append(
                f"States with no outgoing transitions: "
                f"{[state_defs[s]['name'] for s in no_outgoing]}"
            )

        # 3. Determinism: no duplicate guards from same state
        guard_seen: Dict[int, set] = {}
        is_deterministic = True
        for t in transitions:
            if t.from_state not in guard_seen:
                guard_seen[t.from_state] = set()
            if t.guard_expression in guard_seen[t.from_state]:
                is_deterministic = False
                report.errors.append(
                    f"Duplicate guard '{t.guard_expression}' from state "
                    f"'{state_defs.get(t.from_state, {}).get('name', t.from_state)}'"
                )
            guard_seen[t.from_state].add(t.guard_expression)
        report.determinism = is_deterministic

        # 4. specKG coverage — prefer the loaded KG's own fsm_states (e.g. a
        # custom spec JSON's state list) over the generic per-ip_type
        # reference list, so a custom design isn't scored against states it
        # was never meant to have. Falls back to IP_EXPECTED_STATES when no
        # spec_kg is attached or its fsm_states is empty (matches
        # build_ldo_kg()'s default list exactly, so this is a no-op for the
        # built-in/no-spec-json path).
        kg_states = getattr(self.spec_kg, 'fsm_states', None) if self.spec_kg else None
        using_kg_states = bool(kg_states)
        expected_states = list(kg_states) if using_kg_states else \
            IP_EXPECTED_STATES.get(ip_type.upper(), [])
        if expected_states:
            matched = len(state_names & set(expected_states))
            report.speckg_coverage = matched / len(expected_states)
            report.missing_states = [s for s in expected_states if s not in state_names]
        else:
            report.speckg_coverage = 1.0

        # 5. Missing transitions — the generic IP_EXPECTED_TRANSITIONS list
        # is only meaningful against the generic per-ip_type state list; a
        # custom KG state list (e.g. extra UVLO/HIGH_POWER_MODE/SCAN_MODE/
        # OVERRIDE states) has no generic transition equivalent, so scoring
        # against it would just report a permanently "incomplete" transition
        # set for reasons unrelated to the detected FSM's actual quality.
        if using_kg_states:
            report.missing_transitions = []
            report.warnings.append(
                "missing_transitions not evaluated: spec_kg.fsm_states is a "
                "custom state list, not the generic per-ip_type reference"
            )
        else:
            expected_trans = IP_EXPECTED_TRANSITIONS.get(ip_type.upper(), [])
            detected_trans = {(state_defs.get(t.from_state, {}).get('name', ''),
                               state_defs.get(t.to_state, {}).get('name', ''))
                              for t in transitions}
            report.missing_transitions = [
                tr for tr in expected_trans if tr not in detected_trans
            ]

        return report


class FSMCodeGenerator:
    """Generate Verilog-A and SystemVerilog FSM code."""

    def __init__(self, spec_kg=None, ip_type: str = 'LDO'):
        self.spec_kg = spec_kg
        self.ip_type = ip_type

    # ─── Shared helpers ───────────────────────────────────────────────────────

    def _guard_signal_names(self, state_defs: Dict, transitions: list) -> List[str]:
        """Every signal name referenced by state patterns or guards, in
        stable (first-seen) order."""
        names: List[str] = []
        for sid in sorted(state_defs.keys()):
            for k in (state_defs[sid].get('pattern') or {}):
                if k not in names:
                    names.append(k)
        for t in transitions:
            for m in re.finditer(r'([A-Za-z_][\w.\[\]!]*)\s*(?:==|<=|>=|<|>)', t.guard_expression):
                nm = m.group(1)
                if nm not in ('V', 'I') and nm not in names:
                    names.append(nm)
            # Guards already in access-function form (decision-tree path
            # wraps voltage-ish feature names as V(name)) still reference
            # nodes that must be declared.
            for m in re.finditer(r'\b[VI]\(([^)]+)\)', t.guard_expression):
                nm = m.group(1)
                if nm not in names:
                    names.append(nm)
        return names

    def _digital_thresholds(self, names: List[str]) -> Dict[str, float]:
        """Logic threshold per guard signal: midpoint of the SpecKG port's
        voltage range when known, else a 0.5 V default."""
        thresholds = {}
        port_by_name = {}
        if self.spec_kg is not None:
            port_by_name = {p.name: p for p in getattr(self.spec_kg, 'ports', [])}
        for nm in names:
            p = port_by_name.get(nm)
            if p is not None:
                lo, hi = p.voltage_range
                thresholds[nm] = (float(lo) + float(hi)) / 2.0 if hi > lo else 0.5
            else:
                thresholds[nm] = 0.5
        return thresholds

    def _is_pure_digital(self, port) -> bool:
        """True for a digital-domain port that is neither a supply/ground/
        bulk rail nor itself treated as an analog state node — i.e. a
        control/status pin that can be declared `logic` (with
        supplySensitivity/groundSensitivity attributes) instead of
        `electrical` + V()-threshold. vin/vout/gnd/feedback-loop nodes
        (domain=='analog', or port_type in supply/ground/bulk) always stay
        on the existing electrical path — as do ready/fault-role status
        outputs, since those are driven via an analog V() <+ contribution
        further down in generate_veriloga() and need to stay electrical."""
        return (getattr(port, 'domain', None) == 'digital'
                and getattr(port, 'port_type', None) not in
                ('supply', 'ground', 'bulk')
                and getattr(port, 'fsm_role', None) not in ('ready', 'fault'))

    def _va_guard(self, guard: str, names: List[str],
                  logic_names: Optional[set] = None) -> str:
        """Translate an abstract guard ("EN == 1 && POK == 0") into
        Verilog-A. Names in `logic_names` (pure-digital ports declared
        `logic`, see _is_pure_digital) render as a plain digital
        comparison — no V()/threshold wrap, since the pin is already a
        logic value. Every other name (electrical ports, and guard
        signals with no matching Port at all) keeps the existing
        V()-vs-threshold treatment. Longer names are substituted first so
        a name that is a prefix of another is never clobbered."""
        logic_names = logic_names or set()
        out = guard
        for nm in sorted(names, key=len, reverse=True):
            ident = _vid(nm)
            if nm in logic_names:
                out = out.replace(f'{nm} == 1', f'{ident}')
                out = out.replace(f'{nm} == 0', f'!{ident}')
                out = re.sub(rf'(?<![\w(]){re.escape(nm)}(?=\s*(?:<=|>=|<|>))',
                             ident, out)
            else:
                out = out.replace(f'{nm} == 1', f'V({ident}) > VTH_{ident}')
                out = out.replace(f'{nm} == 0', f'V({ident}) < VTH_{ident}')
                # decision-tree numeric splits, e.g. "EN <= 0.5" / "EN > 0.5"
                out = re.sub(rf'(?<![\w(]){re.escape(nm)}(?=\s*(?:<=|>=|<|>))',
                             f'V({ident})', out)
        return out

    def _wrap_equation_port_terms(self, equation: str, port_names: List[str]) -> str:
        """Wrap each standalone occurrence of a real port name in an
        equation string with V(<ident>) — a fitted equation (linear/PySR)
        references bare feature-name tokens like "1.02*VPWR + ...", but a
        bare port name is not a valid Verilog-A operand; it must read
        that node's voltage. Names NOT in port_names (equation_parameters
        keys — corner/meta terms with no physical pin) are left bare, on
        purpose. Longest names substituted first so a name that is a
        prefix of another is never partially clobbered."""
        out = equation
        for nm in sorted(port_names, key=len, reverse=True):
            ident = _vid(nm)
            out = re.sub(rf'(?<![\w.]){re.escape(nm)}(?![\w])', f'V({ident})', out)
        return out

    def generate_veriloga(self, state_defs: Dict, transitions: list,
                          ports=None, output_equations: Optional[Dict[int, Dict[str, str]]] = None,
                          equation_parameters: Optional[Dict[str, float]] = None) -> str:
        """Generate Verilog-A FSM code.

        output_equations (optional): {state_id: {output_name: equation}} —
        when given, a SECOND case(current_state) block is emitted driving
        each output_name from its per-state fitted equation (e.g. a
        per-state linear regression or PySR expression over the model's
        input features). This is what turns the FSM control skeleton
        into a model that actually computes its outputs, rather than one
        that only sequences states. output_name is resolved against
        `ports`: an exact Port.name match drives it as a voltage
        (`V(ident) <+ eq;`); an unmatched name ending in "_I" whose base
        (name[:-2]) IS a Port drives that base pin's current
        (`I(base_ident, gnd_ident) <+ eq;` — the signal_map "_I"-suffix
        convention for a current probe); anything else is added as a new
        voltage-type output port. equation strings must reference only
        identifiers already valid in the generated module: real (already
        `_vid`-sanitized) port names, or names declared via
        equation_parameters.

        equation_parameters (optional): {name: nominal_value} — corner/
        meta features an equation references that are NOT observable DUT
        pins (e.g. "meta_temp", one-hot "meta_corner_nn") are declared as
        `parameter real <name> = <nominal_value>;`, overridable per
        simulation corner via instance/`.param` overrides — the
        idiomatic Verilog-A way to expose corner-conditioning that has no
        physical pin, matching the PVT-table pattern used elsewhere in
        this codebase (core/ab_integration/ab_codegen.py)."""
        lines = []
        ip = self.ip_type

        guard_names = self._guard_signal_names(state_defs, transitions)
        thresholds = self._digital_thresholds(guard_names)

        port_objs = list(ports) if ports else []
        port_names = [p.name for p in port_objs]

        # Resolve output_equations targets against the existing port list:
        # exact match -> voltage drive on that port; "<base>_I" whose base
        # is a port -> current drive on that base pin; neither -> a brand
        # new voltage-type output port. Must happen BEFORE the port-list/
        # direction declarations below so new ports flow through the same
        # declaration logic as everything else.
        output_target_names = sorted({n for d in (output_equations or {}).values()
                                      for n in d})
        output_current_bases: Dict[str, str] = {}   # output_name -> base pin name
        output_new_names: List[str] = []             # needs a brand-new port
        drive_target_names = set()                   # ports that MUST stay electrical
        for name in output_target_names:
            if name in port_names:
                drive_target_names.add(name)
            elif name.endswith('_I') and name[:-2] in port_names:
                output_current_bases[name] = name[:-2]
                drive_target_names.add(name[:-2])
            else:
                output_new_names.append(name)

        # Guard-referenced signals that aren't SpecKG ports still need to be
        # observable nodes — expose them as ports too (existing behavior,
        # these are INPUTS). New output-equation targets with no matching
        # port are OUTPUTS — kept in a separate list so direction
        # declarations below route them correctly.
        extra_names = [n for n in guard_names if n not in port_names]
        output_extra_names = [n for n in output_new_names
                              if n not in extra_names and n not in port_names]
        all_port_ids = [_vid(n) for n in port_names + extra_names + output_extra_names]

        lines.append(f'// Auto-generated Verilog-A FSM — {ip}')
        lines.append('// Generated by surrogate_framework FSMCodeGenerator')
        lines.append('')
        lines.append('`include "disciplines.vams"')
        lines.append('`include "constants.vams"')
        lines.append('')
        lines.append(f'module {ip.lower()}_fsm_model(')
        if all_port_ids:
            lines.append('    ' + ', '.join(all_port_ids))
        else:
            lines.append('    vin, vout, gnd, en, pok, fault')
            all_port_ids = ['vin', 'vout', 'gnd', 'en', 'pok', 'fault']
        lines.append(');')
        lines.append('')

        # Split ports: pure-digital control/status pins (_is_pure_digital)
        # become `logic` nets with supplySensitivity/groundSensitivity
        # attributes, usable directly in guard expressions without a
        # V()/threshold wrap; everything else (vin/vout/gnd/feedback,
        # supply/ground/bulk rails, and unmapped extra guard names) keeps
        # the existing `electrical` + V()-threshold treatment.
        from core.spec_kg.knowledge_graph import port_direction
        from core.spec_kg.port_bounds import resolve_supply_ground, range_check_lines
        # Ports being driven by an output equation MUST stay electrical
        # (need V()/I() access) even if they'd otherwise qualify as pure
        # digital — drive_target_names, resolved above, overrides that.
        logic_ports = [p for p in port_objs
                       if self._is_pure_digital(p) and p.name not in drive_target_names]
        logic_names = {p.name for p in logic_ports}
        electrical_ports = [p for p in port_objs if p.name not in logic_names]
        electrical_ids = [_vid(p.name) for p in electrical_ports] + \
            [_vid(n) for n in extra_names] + [_vid(n) for n in output_extra_names]

        # Direction + discipline declarations for electrical ports, from
        # SpecKG port metadata (port_direction: explicit Port.direction
        # wins, else derived — output/status ⇒ output, supply/ground/
        # bulk/inout ⇒ inout).
        dir_in, dir_out, dir_inout = [], [], []
        for p in electrical_ports:
            ident = _vid(p.name)
            d = port_direction(p)
            if d == 'output':
                dir_out.append(ident)
            elif d == 'inout':
                dir_inout.append(ident)
            else:
                dir_in.append(ident)
        dir_in += [_vid(n) for n in extra_names]
        dir_out += [_vid(n) for n in output_extra_names]
        if dir_in:
            lines.append(f'    input {", ".join(dir_in)};')
        if dir_out:
            lines.append(f'    output {", ".join(dir_out)};')
        if dir_inout:
            lines.append(f'    inout {", ".join(dir_inout)};')
        if electrical_ids:
            lines.append(f'    electrical {", ".join(electrical_ids)};')
        lines.append('')

        # Corner/meta parameters an output equation references that aren't
        # observable DUT pins (temp, vsup, one-hot process-corner flags) —
        # declared as overridable parameters, not ports (see docstring).
        if equation_parameters:
            lines.append('    // Corner/meta parameters (equation inputs with')
            lines.append('    // no physical pin — override per simulated corner)')
            for name, value in equation_parameters.items():
                lines.append(f'    parameter real {_vid(name)} = {value:g};')
            lines.append('')

        # Pure-digital ports: one supplySensitivity/groundSensitivity-
        # annotated declaration per pin (direction + attributes on one
        # line, matching the mixed-signal boundary convention this
        # generator targets), plus an explicit `logic` net declaration —
        # usable directly in guard expressions, never wrapped in V()/I().
        if logic_ports:
            lines.append('    // Supply-sensitive logic pins (mixed-signal')
            lines.append('    // boundary via attribute annotation, no V()')
            lines.append('    // threshold needed — see _va_guard).')
            for p in logic_ports:
                ident = _vid(p.name)
                d = port_direction(p)
                sup, gnd = resolve_supply_ground(p, port_objs)
                lines.append(
                    f'    {d} (* integer supplySensitivity = "{_vid(sup)}"; '
                    f'integer groundSensitivity = "{_vid(gnd)}"; *) {ident};')
                lines.append(f'    logic {ident};')
            lines.append('')

        # Logic thresholds for guard comparisons — only for signals still
        # on the electrical/V() path (logic ports compare directly).
        electrical_guard_names = [nm for nm in guard_names if nm not in logic_names]
        for nm in electrical_guard_names:
            lines.append(f'    parameter real VTH_{_vid(nm)} = {thresholds[nm]:g};'
                         f'  // logic threshold for {nm}')
        if electrical_guard_names:
            lines.append('')

        # State parameter declarations
        for sid in sorted(state_defs.keys()):
            sname = _vid(state_defs[sid]['name'])
            lines.append(f'    parameter integer {sname} = {sid};')
        lines.append('')

        # Variables
        # current_state is digital-domain-computed (see the labeled
        # transition case-block below) and only READ, never written, by
        # the analog-domain output-equations case-block further down —
        # the two are kept as clearly separated case(current_state)
        # blocks for exactly this reason, even though both currently
        # execute inside the same `analog begin...end` (a full digital/
        # analog module split was evaluated and deferred; see project
        # notes — this is the same-file structural clarification instead).
        lines.append('    integer current_state;  // digital-domain FSM state')
        lines.append('')

        # Reset into the DISABLED-like state when one exists
        reset_sid = 0
        for sid in sorted(state_defs.keys()):
            if state_defs[sid]['name'].startswith('DISABLED'):
                reset_sid = sid
                break

        # Analog block
        lines.append('    analog begin')
        lines.append('')
        lines.append('        @(initial_step) begin')
        lines.append(f'            current_state = {reset_sid};')
        lines.append('        end')
        lines.append('')

        # Non-fatal runtime self-checks: $strobe when a supply/ground/
        # bulk/bias-current electrical pin's V()/I() falls outside its
        # spec-declared operating window (Port.voltage_range/
        # current_range). Diagnostic only — no simulation-altering
        # behavior, unlike the AB-model's silent supplies_ok gating.
        check_lines = []
        for p in electrical_ports:
            check_lines += range_check_lines(p, _vid(p.name))
        if check_lines:
            lines.append('        // ── Pin operating-range self-checks ──')
            lines += check_lines
            lines.append('')
        lines.append('        // ── Digital-domain state-transition logic ──')
        lines.append('        case (current_state)')

        for sid in sorted(state_defs.keys()):
            sname = _vid(state_defs[sid]['name'])
            # Most specific guard first, so a broad condition never shadows
            # a stricter one later in the priority if/else-if chain.
            out_trans = sorted((t for t in transitions if t.from_state == sid),
                               key=lambda t: -len(t.conditions))
            lines.append(f'            {sname}: begin')

            for k, t in enumerate(out_trans):
                tname = _vid(state_defs.get(t.to_state, {}).get('name', f'STATE_{t.to_state}'))
                guard = self._va_guard(t.guard_expression, guard_names, logic_names)
                for cond in t.conditions:
                    lines.append(f'                // condition: {cond}')
                kw = 'if' if k == 0 else 'else if'
                if not guard.startswith('('):
                    guard = f'({guard})'
                lines.append(f'                {kw} {guard}')
                lines.append(f'                    current_state = {tname};')

            if not out_trans:
                lines.append('                // terminal state — no transitions')

            lines.append('            end')

        lines.append('        endcase')
        lines.append('')

        # Fitted per-state output equations (Phase 2 modeling result) —
        # this is what makes the FSM skeleton actually COMPUTE its
        # outputs instead of only sequencing states. A second, independent
        # case(current_state) block (valid Verilog-A — multiple case
        # statements over the same selector are just separate procedural
        # blocks) drives each requested output from its per-state
        # equation, resolved above into either a voltage drive on a
        # matching port or a current drive on a "<base>_I" port's base pin.
        if output_equations:
            ground_ports = [p for p in port_objs if p.port_type == 'ground']
            gnd_ident = _vid(ground_ports[0].name) if ground_ports else '0'
            # Equation strings (from a per-state linear/PySR fit) reference
            # bare feature-name tokens ("1.02*VPWR + 0.01*meta_temp - 0.3").
            # A bare port name is not valid Verilog-A — it must read that
            # node's voltage via V(). equation_parameters keys (corner/meta
            # terms with no physical pin) are the one class of token that's
            # correctly left bare, since they're plain `parameter real`s.
            eq_port_names = [p.name for p in electrical_ports] + list(logic_names)
            lines.append('        // ── Fitted per-state output equations '
                         '(Phase 2 modeling) ──')
            lines.append('        case (current_state)')
            for sid in sorted(state_defs.keys()):
                eqs = output_equations.get(sid)
                if not eqs:
                    continue
                sname = _vid(state_defs[sid]['name'])
                lines.append(f'            {sname}: begin')
                for out_name in sorted(eqs.keys()):
                    eq = self._wrap_equation_port_terms(eqs[out_name], eq_port_names)
                    if out_name in output_current_bases:
                        base_ident = _vid(output_current_bases[out_name])
                        lines.append(f'                I({base_ident}, {gnd_ident}) '
                                     f'<+ {eq};  // {out_name}')
                    else:
                        lines.append(f'                V({_vid(out_name)}) <+ {eq};')
                lines.append('            end')
            lines.append('            default: ;')
            lines.append('        endcase')
            lines.append('')

        # Drive status outputs (ready/fault roles) from the current state
        ready_states = [_vid(s['name']) for s in state_defs.values()
                        if any(tag in s['name'] for tag in
                               ('REGULATION', 'ACTIVE', 'SETTLED', 'CCM'))]
        fault_states = [_vid(s['name']) for s in state_defs.values()
                        if 'FAULT' in s['name']]
        for p in port_objs:
            if p.fsm_role not in ('ready', 'fault') or \
                    port_direction(p) != 'output':
                continue
            driven = ready_states if p.fsm_role == 'ready' else fault_states
            if not driven:
                continue
            vhi = float(p.voltage_range[1]) if p.voltage_range[1] > 0 else 1.0
            expr = ' || '.join(f'(current_state == {s})' for s in driven)
            lines.append(f'        V({_vid(p.name)}) <+ ({expr}) ? {vhi:g} : 0.0;')

        lines.append('')
        lines.append('    end  // analog begin')
        lines.append('')
        lines.append('endmodule')

        return '\n'.join(lines)

    def generate_systemverilog(self, state_defs: Dict,
                                transitions: list) -> str:
        """Generate SystemVerilog FSM code."""
        lines = []
        ip = self.ip_type

        # Inputs are the signals the detected states/guards actually
        # observe (SpecKG names when a signal_map was applied); fall back
        # to the legacy fixed port list when none are known.
        guard_names = self._guard_signal_names(state_defs, transitions)
        input_ids = [_vid(n) for n in guard_names]

        lines.append(f'// Auto-generated SystemVerilog FSM — {ip}')
        lines.append('// Generated by surrogate_framework FSMCodeGenerator')
        lines.append('')
        lines.append(f'module {ip.lower()}_fsm (')
        lines.append('    input  logic clk,')
        lines.append('    input  logic rst_n,')
        if input_ids:
            for ident in input_ids:
                lines.append(f'    input  logic {ident},')
        else:
            lines.append('    input  logic en,')
            lines.append('    input  logic fault_det,')
            lines.append('    input  logic pok_det,')
        lines.append('    output logic ready,')
        lines.append('    output logic fault_out')
        lines.append(');')
        lines.append('')

        # Enum declaration
        state_names = [_vid(state_defs[s]['name']) for s in sorted(state_defs.keys())]
        reset_name = next((n for n in state_names if n.startswith('DISABLED')),
                          state_names[0] if state_names else 'RESET')
        n_bits = max(4, len(state_names).bit_length())
        lines.append(f'    typedef enum logic [{n_bits-1}:0] {{')
        for i, name in enumerate(state_names):
            comma = ',' if i < len(state_names) - 1 else ''
            lines.append(f'        {name}{comma}')
        lines.append('    } state_t;')
        lines.append('')
        lines.append('    state_t current_state, next_state;')
        lines.append('')

        # Localparams from specs
        if self.spec_kg:
            for spec in self.spec_kg.specs:
                safe_name = spec.name.replace(' ', '_').replace('.', '_')
                lines.append(f'    localparam real {safe_name}_nom = {spec.nominal};'
                              f'  // {spec.unit}')
        lines.append('')

        # always_ff (sequential)
        lines.append('    always_ff @(posedge clk or negedge rst_n) begin')
        lines.append('        if (!rst_n)')
        lines.append(f'            current_state <= {reset_name};')
        lines.append('        else')
        lines.append('            current_state <= next_state;')
        lines.append('    end')
        lines.append('')

        # always_comb (next-state + output)
        lines.append('    always_comb begin')
        lines.append('        next_state = current_state;')
        lines.append('        ready     = 1\'b0;')
        lines.append('        fault_out = 1\'b0;')
        lines.append('')
        lines.append('        case (current_state)')

        for sid in sorted(state_defs.keys()):
            sname = _vid(state_defs[sid]['name'])
            # Most specific guard first (see generate_veriloga)
            out_trans = sorted((t for t in transitions if t.from_state == sid),
                               key=lambda t: -len(t.conditions))
            lines.append(f'            {sname}: begin')

            # Output logic
            if 'REGULATION' in sname or 'ACTIVE' in sname or 'SETTLED' in sname or 'CCM' in sname:
                lines.append('                ready = 1\'b1;')
            if 'FAULT' in sname:
                lines.append('                fault_out = 1\'b1;')

            # Next-state logic (priority if/else-if — deterministic)
            for k, t in enumerate(out_trans):
                tname = _vid(state_defs.get(t.to_state, {}).get('name', f'STATE_{t.to_state}'))
                kw = 'if' if k == 0 else 'else if'
                lines.append(f'                {kw} ({_sv_guard(t.guard_expression, guard_names)})')
                lines.append(f'                    next_state = {tname};')

            lines.append('            end')

        lines.append('            default: next_state = ' + reset_name + ';')
        lines.append('        endcase')
        lines.append('    end')
        lines.append('')
        lines.append(f'endmodule  // {ip.lower()}_fsm')

        return '\n'.join(lines)


def _sv_guard(guard_expr: str, signal_names: Optional[List[str]] = None) -> str:
    """Convert an abstract/Verilog-A guard to a SystemVerilog expression:
    V(x)/I(x) unwrap to the logic signal, bit tests "x == 1"/"x == 0"
    become "x"/"!x", and decision-tree splits against 0.5 collapse to the
    logic value ("x > 0.5" -> "x", "x <= 0.5" -> "!x")."""
    sv = guard_expr
    # Substitute raw names by sanitized identifiers, longest first
    for nm in sorted(signal_names or [], key=len, reverse=True):
        sv = sv.replace(nm, _vid(nm))
    sv = re.sub(r'V\((\w+)\)', r'\1', sv)
    sv = re.sub(r'I\((\w+)\)', r'\1_cur', sv)
    sv = re.sub(r'(\w+)\s*==\s*1\b', r'\1', sv)
    sv = re.sub(r'(\w+)\s*==\s*0\b', r'!\1', sv)
    sv = re.sub(r'(\w+)\s*>\s*0\.5\b', r'\1', sv)
    sv = re.sub(r'(\w+)\s*<=\s*0\.5\b', r'!\1', sv)
    if sv.strip() == '(1)':
        return "1'b1"
    return sv
