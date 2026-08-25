"""
core/models/feature_selection.py
Automatic, mRMR-style ("max relevance, min redundancy") narrowing of a
candidate input-signal list down to the subset worth modeling against a
set of outputs — same family/style as gpr_surrogate.py's
drop_degenerate_columns (plain numpy function, sklearn behind the same
optional-dependency guard pattern used there and in
core/fsm/state_detector.py), but scores relevance to a TARGET rather
than pruning for numerical stability among already-chosen columns.

Motivation: an analog circuit's ports are all electrically coupled to
some degree (shared rails, ground-return paths), so "use every port as
an input" is defensible in principle but expensive in practice (a
degree-2 polynomial fit blows up combinatorially in feature count, and
GPR/Kriging are O(n^2)/O(n^3) in the column count too). This module
picks a small, defensible subset automatically instead of requiring a
hand-picked --blut_input_signals list, while still letting a caller
force-include specific signals that must never be dropped (the
counter-argument to pure automatic narrowing: a real small-signal
coupling can sit below any statistical threshold, so a hard cutoff
alone is not safe — force_include is the escape hatch, and callers are
expected to force-include every supply/ground/output-rail current by
default, not just leave selection fully automatic).
"""
from typing import Dict, List, Sequence, Tuple

import numpy as np

try:
    from sklearn.feature_selection import mutual_info_regression
    _SKLEARN = True
except ImportError:
    _SKLEARN = False


def select_relevant_inputs(
    X_candidates: np.ndarray,
    Y: np.ndarray,
    candidate_names: Sequence[str],
    force_include: Sequence[str] = (),
    max_features: int = 8,
    relevance_min_score: float = 0.0,
    redundancy_corr_threshold: float = 0.95,
    random_state: int = 42,
) -> Tuple[List[int], Dict[str, float]]:
    """Select which columns of X_candidates to keep as model inputs.

    Two-stage mRMR selection:
      1. Relevance: mutual_info_regression(X_candidates, Y[:, k]) per
         output k, combined via max-across-outputs into one relevance
         score per candidate — nonlinearity-aware (unlike a Pearson
         correlation), appropriate for analog V-I relationships, and
         needs no dependency beyond the sklearn already used elsewhere
         in this codebase (state_detector.py's KMeans/GaussianMixture,
         gpr_surrogate.py's GaussianProcessRegressor).
      2. Redundancy pruning: walk candidates by descending relevance,
         greedily skipping one whose |corr| with an ALREADY-selected
         column exceeds redundancy_corr_threshold — the same
         collinearity idea as drop_degenerate_columns, applied by
         relevance rank instead of arbitrary column order, so two
         near-identical supply rails don't both consume a feature slot.

    force_include names are always kept (never scored, never dropped,
    never counted against max_features's remaining budget beyond their
    own slots). Falls back to "keep everything up to max_features" (no
    scoring) if sklearn isn't installed, matching this codebase's
    optional-dependency convention elsewhere.

    Returns (selected_indices into candidate_names/X_candidates columns,
    {candidate_name: relevance_score}) — the score dict is returned in
    full (including non-selected candidates) so a caller can report
    what was considered and why something was dropped.
    """
    n_candidates = X_candidates.shape[1]
    name_to_idx = {n: i for i, n in enumerate(candidate_names)}
    force_idx = [name_to_idx[n] for n in force_include if n in name_to_idx]

    if not _SKLEARN:
        print("[feature_selection] sklearn not available — skipping "
              "relevance/redundancy scoring, keeping the first "
              f"{max_features} candidates plus all force_include names.")
        remaining_budget = max(0, max_features - len(force_idx))
        rest = [i for i in range(n_candidates) if i not in force_idx][:remaining_budget]
        selected = sorted(set(force_idx) | set(rest))
        return selected, {name: 0.0 for name in candidate_names}

    Y2 = Y if Y.ndim > 1 else Y.reshape(-1, 1)
    scores = np.zeros(n_candidates)
    for k in range(Y2.shape[1]):
        try:
            mi = mutual_info_regression(X_candidates, Y2[:, k],
                                        random_state=random_state)
        except Exception as e:
            print(f"[feature_selection] mutual_info_regression failed for "
                  f"output index {k}: {e} — treating that output's "
                  f"relevance contribution as 0.")
            mi = np.zeros(n_candidates)
        scores = np.maximum(scores, mi)
    relevance_scores = {name: float(scores[i]) for i, name in enumerate(candidate_names)}

    # Redundancy pruning needs pairwise correlation among candidates —
    # computed once, reused for every greedy-add check below.
    with np.errstate(invalid='ignore'):
        corr = np.corrcoef(X_candidates, rowvar=False)
    corr = np.nan_to_num(corr, nan=0.0)

    selected: List[int] = list(dict.fromkeys(force_idx))  # de-dup, keep order
    ranked = sorted((i for i in range(n_candidates) if i not in selected),
                    key=lambda i: -scores[i])
    for i in ranked:
        if len(selected) >= max_features:
            break
        if scores[i] < relevance_min_score:
            continue
        redundant = any(abs(corr[i, j]) > redundancy_corr_threshold for j in selected)
        if redundant:
            continue
        selected.append(i)

    return sorted(selected), relevance_scores
