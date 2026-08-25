"""
core/fsm/transition_learner.py
Decision-tree guard learning for FSM transitions.
"""
import numpy as np
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple

try:
    from sklearn.tree import DecisionTreeClassifier, export_text
    _SKLEARN = True
except ImportError:
    _SKLEARN = False


@dataclass
class Transition:
    from_state: int
    to_state: int
    from_name: str
    to_name: str
    conditions: List[str]
    guard_expression: str
    probability: float
    feature_importances: Dict[str, float]


class TransitionLearner:
    """Learn transition guards from state sequences using decision trees."""

    def __init__(self, fsm_tree_depth: int = 4):
        self.fsm_tree_depth = fsm_tree_depth
        self.transitions: List[Transition] = []

    def learn(self, state_sequence: np.ndarray, feature_matrix: np.ndarray,
              feature_names: List[str], state_defs: Dict,
              boundary_mask: Optional[np.ndarray] = None) -> List[Transition]:
        """
        Learn transitions from (state_sequence, feature_matrix).

        boundary_mask: optional bool array, same length as state_sequence.
        boundary_mask[i] == True means "sample i+1 is the start of a new
        run" — the (i, i+1) pair is an artificial concatenation seam, not
        an observed transition, and must be excluded from both the
        possible_next discovery scan and the per-transition training set.

        Returns list of Transition objects.
        """
        seq = np.array(state_sequence, dtype=int)
        n = min(len(seq), len(feature_matrix))
        seq = seq[:n]
        feat = feature_matrix[:n]

        if boundary_mask is not None:
            bmask = np.asarray(boundary_mask, dtype=bool)[:n]
        else:
            bmask = np.zeros(n, dtype=bool)

        states = sorted(state_defs.keys())
        transitions = []

        for from_sid in states:
            # Find all unique next states, skipping boundary-masked pairs
            possible_next = set()
            for i in range(n - 1):
                if bmask[i]:
                    continue  # artificial run seam — not a real transition
                if seq[i] == from_sid and seq[i + 1] != from_sid:
                    possible_next.add(int(seq[i + 1]))

            for to_sid in possible_next:
                trans = self._learn_single_transition(
                    seq, feat, feature_names, state_defs,
                    from_sid, to_sid, n, bmask
                )
                if trans is not None:
                    transitions.append(trans)

        self.transitions = transitions
        return transitions

    def _learn_single_transition(
        self, seq: np.ndarray, feat: np.ndarray, feature_names: List[str],
        state_defs: Dict, from_sid: int, to_sid: int, n: int,
        bmask: Optional[np.ndarray] = None
    ) -> Optional[Transition]:

        # Align arrays
        n_safe = min(n - 1, len(seq) - 1, len(feat) - 1)

        if bmask is not None:
            bmask_safe = bmask[:n_safe]
        else:
            bmask_safe = np.zeros(n_safe, dtype=bool)

        # Build classification dataset
        in_from_mask = (seq[:n_safe] == from_sid) & (~bmask_safe)
        labels = np.zeros(n_safe, dtype=int)
        for i in range(n_safe):
            if bmask_safe[i]:
                continue  # artificial run seam — never label as observed transition
            if seq[i] == from_sid and seq[i + 1] == to_sid:
                labels[i] = 1

        # The guard fires on the inputs that DRIVE the state change, i.e.
        # the values at sample i+1 (the destination sample). Features at
        # sample i are constant within a logic-derived from_state (they are
        # exactly what defines it), so a tree trained on them can never
        # split and every guard degenerates to "(1)".
        from_idx = np.where(in_from_mask)[0]
        X = feat[from_idx + 1]
        y = labels[from_idx]

        # Require ≥3 samples, ≥1 positive
        if len(X) < 3 or y.sum() < 1:
            return None

        from_name = state_defs.get(from_sid, {}).get('name', f'STATE_{from_sid}')
        to_name = state_defs.get(to_sid, {}).get('name', f'STATE_{to_sid}')

        probability = float(y.mean())

        # Logic-derived states carry the exact bit pattern that defines
        # them — the transition guard is simply the destination values of
        # the bits that changed. This is exact; no learning needed.
        from_pat = state_defs.get(from_sid, {}).get('pattern') or {}
        to_pat = state_defs.get(to_sid, {}).get('pattern') or {}
        if from_pat and to_pat:
            changed = [k for k in to_pat
                       if k in from_pat and int(from_pat[k]) != int(to_pat[k])]
            if changed:
                conditions = [f"{k} == {int(to_pat[k])}" for k in changed]
                guard = "(" + " && ".join(conditions) + ")"
                importances = {name: (1.0 / len(changed) if name in changed else 0.0)
                               for name in feature_names}
                return Transition(
                    from_state=from_sid, to_state=to_sid,
                    from_name=from_name, to_name=to_name,
                    conditions=conditions, guard_expression=guard,
                    probability=probability, feature_importances=importances
                )

        if not _SKLEARN:
            # Fallback: simple threshold on mean feature
            conditions = [f"{feature_names[0]} > threshold"]
            guard = f"({feature_names[0]} > threshold)"
            importances = {name: 1.0 / len(feature_names) for name in feature_names}
            return Transition(
                from_state=from_sid, to_state=to_sid,
                from_name=from_name, to_name=to_name,
                conditions=conditions, guard_expression=guard,
                probability=probability, feature_importances=importances
            )

        try:
            clf = DecisionTreeClassifier(
                max_depth=self.fsm_tree_depth,
                random_state=42,
                min_samples_leaf=1,
            )
            clf.fit(X, y)

            importances = {
                feature_names[i]: float(clf.feature_importances_[i])
                for i in range(len(feature_names))
            }

            conditions = self._extract_conditions(clf, feature_names)
            guard = self._conditions_to_guard(conditions, feature_names)

            return Transition(
                from_state=from_sid, to_state=to_sid,
                from_name=from_name, to_name=to_name,
                conditions=conditions, guard_expression=guard,
                probability=probability, feature_importances=importances
            )
        except Exception as e:
            # Return a fallback transition
            return Transition(
                from_state=from_sid, to_state=to_sid,
                from_name=from_name, to_name=to_name,
                conditions=[f"probability={probability:.3f}"],
                guard_expression=f"(prob_{from_sid}_to_{to_sid})",
                probability=probability,
                feature_importances={n: 0.0 for n in feature_names}
            )

    def _extract_conditions(self, clf, feature_names: List[str]) -> List[str]:
        """Extract highest-probability leaf path as human-readable conditions."""
        tree = clf.tree_
        conditions = []

        # Walk tree to find best leaf
        def walk(node, path):
            if tree.children_left[node] == -1:
                # Leaf node
                total = tree.value[node].sum()
                if total > 0:
                    prob = tree.value[node][0][1] / total
                else:
                    prob = 0.0
                return prob, path
            feat = tree.feature[node]
            thresh = tree.threshold[node]
            name = feature_names[feat] if feat < len(feature_names) else f'f{feat}'

            left_prob, left_path = walk(
                tree.children_left[node],
                path + [f"{name} <= {thresh:.4g}"]
            )
            right_prob, right_path = walk(
                tree.children_right[node],
                path + [f"{name} > {thresh:.4g}"]
            )
            if right_prob >= left_prob:
                return right_prob, right_path
            return left_prob, left_path

        try:
            _, conditions = walk(0, [])
        except Exception:
            conditions = ["true"]

        return conditions if conditions else ["true"]

    def _conditions_to_guard(self, conditions: List[str],
                              feature_names: List[str]) -> str:
        """Convert conditions to Verilog-A guard expression."""
        parts = []
        for cond in conditions:
            if not cond or cond == 'true':
                continue
            # Identify signal type from name
            for name in feature_names:
                if name in cond:
                    name_upper = name.upper()
                    if name_upper.startswith('V') or 'VOLT' in name_upper:
                        # Voltage signal
                        cond_va = cond.replace(name, f'V({name})')
                    elif name_upper.startswith('I') or 'CURR' in name_upper:
                        cond_va = cond.replace(name, f'I({name})')
                    else:
                        cond_va = cond
                    parts.append(cond_va)
                    break
            else:
                parts.append(cond)

        if not parts:
            return "(1)"
        return "(" + " && ".join(parts) + ")"

    def print_summary(self):
        print(f"\nTransitions found: {len(self.transitions)}")
        for t in self.transitions:
            print(f"  {t.from_name} -> {t.to_name}  (p={t.probability:.3f})  "
                  f"guard: {t.guard_expression[:60]}")
