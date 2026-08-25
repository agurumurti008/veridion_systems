"""
core/phases/blut_reference.py
Using digiTwin BLUT data as a state-transition reference/filler for states
with thin or no training coverage in the primary Phase 2 dataset.

This closes the loop described by the user: "digiTwin can be used as
filler for state transitions reference as well" — when the surrogate needs
a transient reference for a rare state (e.g. FAULT), pull the actual
decoded BLUT waveform segment for that state's sample range from whichever
run's state_sequence contains it, and return it as ground truth to compare
against / augment the trained model's output for that state.
"""
from __future__ import annotations

import logging
from typing import Dict, List, Optional

import numpy as np

log = logging.getLogger("surrogate_framework.blut_reference")


class StateReferenceNotFoundError(Exception):
    """Raised when fill_missing_state_transient finds the target state in
    none of the supplied BLUT runs — this is a loud, actionable failure,
    never a silent empty array, per Section 7/Section 8 test 12."""


def count_samples_per_state(state_sequence: np.ndarray, state_defs: Dict) -> Dict[str, int]:
    """Convenience: per-state sample counts using state_defs' human-readable
    names, for deciding which state(s) are "thin" (< N samples) in the
    primary Phase 2 training dataset."""
    seq = np.asarray(state_sequence, dtype=int)
    counts: Dict[str, int] = {}
    for sid, sdef in state_defs.items():
        name = sdef.get('name', f'STATE_{sid}')
        counts[name] = int(np.sum(seq == sid))
    return counts


def find_thin_states(state_sequence: np.ndarray, state_defs: Dict,
                     min_samples: int = 20) -> List[str]:
    """Return the list of state names with fewer than min_samples samples
    in state_sequence — candidates for BLUT reference filling."""
    counts = count_samples_per_state(state_sequence, state_defs)
    return [name for name, c in counts.items() if c < min_samples]


def fill_missing_state_transient(
    fsm_state_defs: Dict,
    transitions: list,
    blut_runs: List[dict],
    target_state_name: str,
    signal_names: Optional[List[str]] = None,
    fsm_detector=None,
) -> np.ndarray:
    """
    Pull a ground-truth transient waveform segment for `target_state_name`
    from whichever BLUT run actually contains that state, for use as a
    Phase-2-model-vs-BLUT-reference comparison (or as an augmentation
    source) when the primary training dataset has thin/no coverage for it.

    Parameters
    ----------
    fsm_state_defs : dict
        The state_defs dict produced by FSMStateDetector (sid -> {'name': ...}).
        Used only to resolve target_state_name -> sid for matching against
        each run's own re-detected state_sequence (Section 7 requires this
        function to work from the BLUT runs' OWN dynamics, not assume the
        primary dataset's state numbering applies unchanged to each run).
    transitions : list
        Learned Transition objects (currently unused for the pull itself,
        accepted for API symmetry with the FSM pipeline and so a future
        transition-aware windowing strategy can be added without breaking
        callers — the present implementation pulls the full contiguous
        sample range for the state, not a single transition edge).
    blut_runs : list[dict]
        A list of run dicts as produced by
        digitwin.blut_reader_ext.load_run_matrix / load_all_runs — each
        must carry 'voltage_matrix', 'voltage_names', 'current_matrix',
        'current_names', 'time', 'run_id'.
    target_state_name : str
        The human-readable state name to search for (e.g. "FAULT").
    signal_names : list[str], optional
        If given, restrict the returned reference to these columns (order
        preserved); default returns every voltage+current column
        concatenated (voltage columns first, then current columns).
    fsm_detector : FSMStateDetector, optional
        If given, used to re-detect states independently in each BLUT run
        (matching the per-run detection philosophy from
        Phase2SimAugmented.build_dataset_from_blut) so the state search
        reflects that run's own dynamics rather than a state_sequence
        computed elsewhere. If omitted, this function falls back to
        assuming each run dict already carries a 'state_sequence' key
        (as attached by the caller, e.g. from a prior detection pass).

    Returns
    -------
    np.ndarray, shape (n_samples_in_state, n_signal_columns)
        The concatenated (across all matching contiguous ranges, across all
        runs that contain the state) reference waveform segment.

    Raises
    ------
    StateReferenceNotFoundError
        If target_state_name is absent from every supplied run — this is
        always a loud, explicit failure (never a silently-empty array),
        so a missing reference can't be mistaken for "the state doesn't
        transition anywhere interesting".
    """
    from core.fsm.signal_capture import SignalCapture  # local import: avoid cycle

    if not blut_runs:
        raise StateReferenceNotFoundError(
            f"fill_missing_state_transient: no BLUT runs supplied to search "
            f"for state '{target_state_name}'."
        )

    segments = []
    matched_any_run = False

    for run_dict in blut_runs:
        voltage_names = run_dict.get('voltage_names', [])
        voltage_matrix = run_dict.get('voltage_matrix', np.zeros((0, 0)))
        current_names = run_dict.get('current_names', [])
        current_matrix = run_dict.get('current_matrix', np.zeros((0, 0)))
        run_id = run_dict.get('run_id', '<unknown>')

        n_t = voltage_matrix.shape[0] if voltage_matrix.size else (
            current_matrix.shape[0] if current_matrix.size else 0
        )
        if n_t == 0:
            continue

        # Resolve this run's own state_sequence.
        if 'state_sequence' in run_dict and run_dict['state_sequence'] is not None:
            run_state_seq = np.asarray(run_dict['state_sequence'], dtype=int)
            run_state_defs = run_dict.get('state_defs', fsm_state_defs)
        elif fsm_detector is not None:
            sc = SignalCapture()
            sc.time = run_dict['time']
            sc.signals = {name: voltage_matrix[:, j] for j, name in enumerate(voltage_names)}
            sc.current_signals = {name: current_matrix[:, j] for j, name in enumerate(current_names)}
            sc._classify_signals()
            lm, ln, lt = sc.get_logic_signal_matrix()
            af = sc.get_analog_features(n_windows=min(10, max(2, n_t // 5)))
            run_state_seq = fsm_detector.detect(lm, ln, af)
            run_state_defs = fsm_detector.state_defs
        else:
            log.debug(
                "fill_missing_state_transient: run '%s' has no 'state_sequence' "
                "and no fsm_detector was given — skipping this run.", run_id,
            )
            continue

        if len(run_state_seq) != n_t:
            m = min(len(run_state_seq), n_t)
            run_state_seq = run_state_seq[:m]

        # Find sid(s) in THIS run's state_defs whose name matches target.
        matching_sids = [
            sid for sid, sdef in run_state_defs.items()
            if sdef.get('name') == target_state_name
        ]
        if not matching_sids:
            continue

        mask = np.isin(run_state_seq, matching_sids)
        if not mask.any():
            continue

        matched_any_run = True

        # Build the requested column set for this run.
        if signal_names is not None:
            cols = []
            for name in signal_names:
                if name in voltage_names:
                    cols.append(voltage_matrix[:len(run_state_seq), voltage_names.index(name)])
                elif name in current_names:
                    cols.append(current_matrix[:len(run_state_seq), current_names.index(name)])
                else:
                    cols.append(np.full(len(run_state_seq), np.nan))
            run_matrix = np.column_stack(cols) if cols else np.zeros((len(run_state_seq), 0))
        else:
            v_part = voltage_matrix[:len(run_state_seq)]
            c_part = current_matrix[:len(run_state_seq)]
            run_matrix = np.hstack([v_part, c_part])

        segments.append(run_matrix[mask])
        log.info(
            "fill_missing_state_transient: found %d sample(s) of state '%s' "
            "in run '%s'.", int(mask.sum()), target_state_name, run_id,
        )

    if not matched_any_run or not segments:
        raise StateReferenceNotFoundError(
            f"fill_missing_state_transient: state '{target_state_name}' was not "
            f"found in any of the {len(blut_runs)} supplied BLUT run(s). "
            f"Checked run_id(s): {[r.get('run_id', '<unknown>') for r in blut_runs]}. "
            f"Confirm the state name matches what FSMStateDetector actually "
            f"produced (case-sensitive), and that fsm_detector or a "
            f"precomputed 'state_sequence' was supplied for each run."
        )

    return np.concatenate(segments, axis=0)


def compare_model_to_blut_reference(
    model_predictions: np.ndarray, blut_reference: np.ndarray,
) -> dict:
    """Compare a trained surrogate's output for a given state against the
    BLUT ground-truth reference pulled via fill_missing_state_transient.
    Returns {'mse', 'mae', 'max_abs_error', 'n_compared'} using the
    shorter of the two arrays' lengths (predictions and reference are not
    guaranteed to be sampled at the same rate)."""
    pred = np.asarray(model_predictions, dtype=np.float64)
    ref = np.asarray(blut_reference, dtype=np.float64)

    if pred.ndim == 1:
        pred = pred.reshape(-1, 1)
    if ref.ndim == 1:
        ref = ref.reshape(-1, 1)

    n = min(len(pred), len(ref))
    if n == 0:
        return {'mse': float('nan'), 'mae': float('nan'), 'max_abs_error': float('nan'), 'n_compared': 0}

    p = pred[:n]
    r = ref[:n, :pred.shape[1]] if ref.shape[1] >= pred.shape[1] else np.pad(
        ref[:n], ((0, 0), (0, pred.shape[1] - ref.shape[1])), constant_values=np.nan
    )

    diff = p - r
    valid = ~np.isnan(diff)
    if not valid.any():
        return {'mse': float('nan'), 'mae': float('nan'), 'max_abs_error': float('nan'), 'n_compared': 0}

    return {
        'mse': float(np.mean(diff[valid] ** 2)),
        'mae': float(np.mean(np.abs(diff[valid]))),
        'max_abs_error': float(np.max(np.abs(diff[valid]))),
        'n_compared': int(valid.sum()),
    }
