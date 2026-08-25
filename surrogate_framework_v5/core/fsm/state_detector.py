"""
core/fsm/state_detector.py
Three-strategy FSM state detector: logic | cluster | hybrid
"""
import numpy as np
from typing import Optional, List, Dict, Tuple

try:
    from sklearn.mixture import GaussianMixture
    from sklearn.cluster import KMeans
    _SKLEARN = True
except ImportError:
    _SKLEARN = False


def compute_output_signatures(state_sequence: np.ndarray,
                              output_matrix: Optional[np.ndarray],
                              output_names: List[str],
                              state_defs: Dict[int, dict]) -> Dict[str, dict]:
    """Per-state output signatures: {state_name: {output_signal: mean
    binarized value observed while in that state}}. Output/status indicator
    pins are effects of the state — they are summarized here (and later
    consistency-checked) instead of ever becoming state variables or guard
    features."""
    if output_matrix is None or not output_names or state_sequence is None:
        return {}
    seq = np.asarray(state_sequence)
    n = min(len(seq), len(output_matrix))
    if n == 0:
        return {}
    sig: Dict[str, dict] = {}
    for sid, sdef in state_defs.items():
        mask = seq[:n] == sid
        if not mask.any():
            continue
        sig[sdef['name']] = {
            output_names[j]: float(np.mean(output_matrix[:n][mask, j]))
            for j in range(len(output_names))}
    return sig


class FSMStateDetector:
    """Detect FSM states from waveform data."""

    def __init__(self, strategy: str = 'hybrid', spec_kg=None):
        assert strategy in ('logic', 'cluster', 'hybrid'), \
            f"Unknown strategy: {strategy}"
        self.strategy = strategy
        self.spec_kg = spec_kg
        self.state_sequence: np.ndarray = None
        self.state_defs: Dict[int, dict] = {}
        self.n_states: int = 0
        self.output_signatures: Dict[str, dict] = {}

    # ─── Public interface ─────────────────────────────────────────────────────

    def detect(self, logic_matrix: np.ndarray, logic_names: List[str],
               analog_features=None, output_matrix=None,
               output_names: Optional[List[str]] = None) -> np.ndarray:
        """Run detection and return state_sequence (int array).

        logic_matrix/logic_names must contain only input/inout-direction
        signals (causality). output_matrix/output_names, when given, carry
        the digital output/status indicators: they are summarized into
        per-state output signatures and used to refine state names (a
        ready-asserted enabled state is REGULATION-family), never to
        define states."""
        if self.strategy == 'logic':
            seq, defs = self._detect_logic(logic_matrix, logic_names)
        elif self.strategy == 'cluster':
            seq, defs = self._detect_cluster(logic_matrix, logic_names, analog_features)
        else:
            seq, defs = self._detect_hybrid(logic_matrix, logic_names, analog_features)

        self.state_sequence = seq
        self.state_defs = self._apply_speckg_naming(defs)
        self.n_states = len(self.state_defs)
        self.output_signatures = {}
        if output_matrix is not None and output_names:
            sigs = compute_output_signatures(seq, output_matrix,
                                             output_names, self.state_defs)
            self.output_signatures = self.refine_names_with_outputs(sigs)
        return seq

    # ─── Logic strategy ───────────────────────────────────────────────────────

    def _detect_logic(self, matrix: np.ndarray,
                      names: List[str]) -> Tuple[np.ndarray, Dict]:
        n = len(matrix)
        # Map unique rows → state id
        state_map: Dict[tuple, int] = {}
        seq = np.zeros(n, dtype=int)
        for i in range(n):
            key = tuple(matrix[i].tolist())
            if key not in state_map:
                state_map[key] = len(state_map)
            seq[i] = state_map[key]

        seq, state_map = self._merge_rare_patterns(seq, state_map, n)

        defs = {}
        for pattern, sid in state_map.items():
            defs[sid] = {
                'id': sid,
                'name': f'STATE_{sid}',
                'method': 'logic',
                'pattern': {names[j]: int(pattern[j]) for j in range(len(names))},
                'count': int(np.sum(seq == sid)),
            }
        return seq, defs

    def _merge_rare_patterns(self, seq: np.ndarray, state_map: Dict[tuple, int],
                             n: int) -> Tuple[np.ndarray, Dict[tuple, int]]:
        """Fold glitch patterns into their nearest frequent pattern.

        Real waveform captures produce transient bit patterns while several
        controls settle within a few solver timesteps of each other; each
        such pattern otherwise becomes its own FSM state. Any pattern seen
        in fewer than max(3, 0.2%) of samples is reassigned to the frequent
        pattern at minimum Hamming distance, and state ids are re-packed."""
        min_count = max(3, int(round(0.002 * n)))
        counts = {pat: int(np.sum(seq == sid)) for pat, sid in state_map.items()}
        frequent = {pat for pat, c in counts.items() if c >= min_count}
        if not frequent or len(frequent) == len(state_map):
            return seq, state_map

        def hamming(a: tuple, b: tuple) -> int:
            return sum(1 for x, y in zip(a, b) if x != y)

        remap: Dict[int, int] = {}
        new_map: Dict[tuple, int] = {}
        for pat, sid in state_map.items():
            target_pat = pat if pat in frequent else \
                min(frequent, key=lambda f: hamming(f, pat))
            if target_pat not in new_map:
                new_map[target_pat] = len(new_map)
            remap[sid] = new_map[target_pat]

        new_seq = np.array([remap[s] for s in seq], dtype=int)
        return new_seq, new_map

    # ─── Cluster strategy ─────────────────────────────────────────────────────

    def _detect_cluster(self, matrix: np.ndarray, names: List[str],
                        analog_features=None) -> Tuple[np.ndarray, Dict]:
        if analog_features is not None:
            if hasattr(analog_features, 'values'):
                af = analog_features.values
            elif isinstance(analog_features, list):
                # list of dicts — expand per sample
                af = None
            else:
                af = np.array(analog_features)
        else:
            af = None

        n = len(matrix)
        if af is not None and len(af) != n:
            af = None

        features = matrix.copy()
        if af is not None:
            # Standardize
            std = af.std(axis=0)
            std[std < 1e-10] = 1.0
            af_norm = (af - af.mean(axis=0)) / std
            features = np.hstack([features, af_norm])

        if not _SKLEARN:
            # Fallback: simple thresholding
            return self._detect_logic(matrix, names)

        best_bic = np.inf
        best_gm = None
        best_n = 2
        for n_comp in range(2, min(9, n // 5 + 2)):
            try:
                gm = GaussianMixture(n_components=n_comp, random_state=42, n_init=3)
                gm.fit(features)
                bic = gm.bic(features)
                if bic < best_bic:
                    best_bic = bic
                    best_gm = gm
                    best_n = n_comp
            except Exception:
                pass

        if best_gm is None:
            return self._detect_logic(matrix, names)

        seq = best_gm.predict(features)
        defs = {}
        for sid in range(best_n):
            mask = seq == sid
            defs[sid] = {
                'id': sid,
                'name': f'STATE_{sid}',
                'method': 'cluster',
                'pattern': {},
                'count': int(mask.sum()),
                'probs': float(best_gm.weights_[sid]),
            }
        return seq, defs

    # ─── Hybrid strategy ──────────────────────────────────────────────────────

    def _detect_hybrid(self, matrix: np.ndarray, names: List[str],
                       analog_features=None) -> Tuple[np.ndarray, Dict]:
        # Step 1: coarse logic states
        coarse_seq, coarse_defs = self._detect_logic(matrix, names)
        seq = coarse_seq.copy()
        defs = {k: dict(v) for k, v in coarse_defs.items()}
        next_id = max(defs.keys()) + 1

        if analog_features is None or not _SKLEARN:
            return seq, defs

        # Compute per-sample analog feature vector
        if hasattr(analog_features, 'values'):
            af = analog_features.values
        elif isinstance(analog_features, list) and len(analog_features) > 0:
            if isinstance(analog_features[0], dict):
                # window-based features — skip per-sample expansion
                return seq, defs
            af = np.array(analog_features)
        else:
            return seq, defs

        if len(af) != len(seq):
            return seq, defs

        # Step 2: within each coarse state, split on analog variance
        for sid in sorted(coarse_defs.keys()):
            mask = seq == sid
            count = mask.sum()
            if count < 10:
                continue
            sub_feats = af[mask]
            variance = sub_feats.var()
            if variance < 0.01:
                continue

            # KMeans(k=2) split
            try:
                km = KMeans(n_clusters=2, random_state=42, n_init=5)
                labels = km.fit_predict(sub_feats)
            except Exception:
                continue

            # Temporal coherence: accept only if transition count < 10% of samples
            transitions = int(np.sum(np.diff(labels) != 0))
            if transitions >= 0.1 * count:
                continue

            # Accept split
            sub_ids = np.where(mask)[0]
            for j, orig_idx in enumerate(sub_ids):
                if labels[j] == 0:
                    seq[orig_idx] = sid
                else:
                    seq[orig_idx] = next_id

            defs[next_id] = {
                'id': next_id,
                'name': f'STATE_{sid}b',
                'method': 'hybrid',
                'pattern': coarse_defs[sid]['pattern'],
                'count': int((labels == 1).sum()),
            }
            defs[sid]['count'] = int((labels == 0).sum())
            defs[sid]['name'] = f'STATE_{sid}a'
            next_id += 1

        return seq, defs

    # ─── SpecKG naming ────────────────────────────────────────────────────────

    def _apply_speckg_naming(self, state_defs: Dict) -> Dict:
        if self.spec_kg is None:
            return state_defs

        named = {k: dict(v) for k, v in state_defs.items()}

        # Map FSM port roles to state names: role -> [port names]
        fsm_ports = self.spec_kg.get_fsm_relevant_ports()
        role_ports: Dict[str, List[str]] = {}
        for p in fsm_ports:
            if p.fsm_role:
                role_ports.setdefault(p.fsm_role, []).append(p.name)

        def _pattern_val(pattern: dict, port_names: List[str]) -> Optional[int]:
            for pn in port_names:
                if pn in pattern:
                    return int(pattern[pn])
                if pn.lower() in pattern:
                    return int(pattern[pn.lower()])
            return None

        # Role-driven naming only: the spec declares which ports carry the
        # enable/fault/ready roles (no hardcoded pin-name fallbacks — a spec
        # without a role simply contributes nothing to that check). With
        # output-direction indicators excluded from patterns, fault/ready
        # bits are normally absent here; enabled states start as STARTUP
        # and are refined to REGULATION/FAULT families by
        # refine_names_with_outputs from the observed output signatures.
        for sid, sdef in named.items():
            pattern = sdef.get('pattern', {})
            if not pattern:
                continue
            en_val = _pattern_val(pattern, role_ports.get('enable', []))
            fault_val = _pattern_val(pattern, role_ports.get('fault', []))
            pok_val = _pattern_val(pattern, role_ports.get('ready', []))
            if en_val is None:
                continue
            if en_val == 0:
                named[sid]['name'] = 'DISABLED'
            elif fault_val == 1:
                named[sid]['name'] = 'FAULT'
            elif pok_val == 1:
                named[sid]['name'] = 'REGULATION'
            else:
                named[sid]['name'] = 'STARTUP'

        # Also apply specKG FSM state list if available
        if hasattr(self.spec_kg, 'fsm_states') and self.spec_kg.fsm_states:
            unnamed = [s for s in named.values()
                       if s['name'].startswith('STATE_')]
            known = [n for n in self.spec_kg.fsm_states
                     if n not in [s['name'] for s in named.values()]]
            for i, sdef in enumerate(unnamed):
                if i < len(known):
                    sdef['name'] = known[i]

        for sid in named:
            named[sid]['base_name'] = named[sid]['name']
        self._dedupe_names(named)
        return named

    @staticmethod
    def _dedupe_names(named: Dict) -> None:
        """De-duplicate in place from each state's base_name: several bit
        patterns can map onto the same role name (e.g. two REGULATION
        patterns differing only in a mode bit). Duplicate names would emit
        illegal Verilog (duplicate parameters/enum literals), so repeats
        are suffixed deterministically by state id."""
        seen: Dict[str, int] = {}
        for sid in sorted(named.keys()):
            base = named[sid].get('base_name', named[sid]['name'])
            if base in seen:
                seen[base] += 1
                named[sid]['name'] = f'{base}_{seen[base]}'
            else:
                seen[base] = 1
                named[sid]['name'] = base

    def refine_names_with_outputs(self, signatures: Dict[str, dict],
                                  spec_kg=None) -> Dict[str, dict]:
        """Refine state names from observed output signatures: an enabled
        state whose ready-role indicator is asserted (mean ≥ 0.5) is
        REGULATION-family; one whose fault-role indicator is asserted is
        FAULT-family. DISABLED-family states are never renamed — a ready
        indicator asserted while disabled is a consistency gap (reported by
        fsm_completeness), not a naming decision. Renames self.state_defs
        in place (re-deduplicated) and returns the signatures re-keyed by
        the final names."""
        kg = spec_kg or self.spec_kg
        if kg is None or not signatures or not self.state_defs:
            return signatures
        try:
            out_ports = kg.get_fsm_output_ports()
            in_ports = kg.get_fsm_input_ports()
        except AttributeError:
            return signatures
        role_of = {p.name: p.fsm_role for p in out_ports if p.fsm_role}
        en_ports = [p.name for p in in_ports if p.fsm_role == 'enable']

        sig_by_sid = {sid: signatures.get(sdef['name'], {})
                      for sid, sdef in self.state_defs.items()}
        for sid in sorted(self.state_defs.keys()):
            sdef = self.state_defs[sid]
            pattern = sdef.get('pattern', {}) or {}
            en_val = next((int(pattern[p]) for p in en_ports if p in pattern),
                          None)
            if en_val == 0:
                continue
            sig = sig_by_sid[sid]
            fault_vals = [v for s, v in sig.items()
                          if role_of.get(s) == 'fault']
            ready_vals = [v for s, v in sig.items()
                          if role_of.get(s) == 'ready']
            if fault_vals and max(fault_vals) >= 0.5:
                sdef['base_name'] = 'FAULT'
            elif ready_vals and max(ready_vals) >= 0.5:
                sdef['base_name'] = 'REGULATION'
        self._dedupe_names(self.state_defs)
        return {self.state_defs[sid]['name']: sig
                for sid, sig in sig_by_sid.items() if sig}

    def print_summary(self):
        print(f"\n{'='*55}")
        print(f"FSM States — Strategy: {self.strategy}")
        print(f"{'='*55}")
        print(f"  {'ID':<5} {'Name':<20} {'Count':<10} {'Method'}")
        print(f"  {'-'*50}")
        for sid in sorted(self.state_defs.keys()):
            s = self.state_defs[sid]
            print(f"  {sid:<5} {s['name']:<20} {s['count']:<10} {s.get('method','?')}")
        print(f"\n  Total samples: {len(self.state_sequence) if self.state_sequence is not None else 0}")
        print()
