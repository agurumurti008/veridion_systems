#!/usr/bin/env python3
"""
digitwin/blut_reader_ext.py — NEW capability layer on top of the vendored
digiTwin BLUT reader (blut_reader_core.py / blut_format.py).

Implements everything surrogate_framework needs that the original reader
does not expose: bulk per-run matrix decoding, $flow-suffix current/voltage
classification, and multi-run iteration. All functions raise
bf.BlutFormatError on structural problems, matching the vendored module's
exception convention.
"""
from __future__ import annotations

import logging
from typing import Dict, List, Literal, Optional

import numpy as np

from . import blut_format as bf
from .blut_reader_core import BlutFile, open_blut, decode


def iter_runs(blut: BlutFile):
    """Yield every RunMeta in file order, flattening the v8 nested
    runs[run_id][corner_id] shape. For files that never used corner_id
    (v7 reads, or v8 written without --corner-id), every run sits under
    corner_id="" and this degenerates to the old per-run_id iteration."""
    for corner_map in blut.runs.values():
        for run in corner_map.values():
            yield run


def get_run(blut: BlutFile, run_id: str, corner_id: str = None):
    """Fetch one RunMeta by (run_id, corner_id). corner_id=None resolves
    to the run's single corner when unambiguous, else raises listing the
    available corners — the same disambiguation contract as
    resolve_requests' 'name@run_id' rule."""
    if run_id not in blut.runs:
        raise KeyError(
            f"{blut.path}: run_id '{run_id}' not found. "
            f"Available runs: {list(blut.runs.keys())}"
        )
    corner_map = blut.runs[run_id]
    if corner_id is not None:
        if corner_id not in corner_map:
            raise KeyError(
                f"{blut.path}: corner_id '{corner_id}' not found for run_id "
                f"'{run_id}'. Available corners: {sorted(corner_map.keys())}"
            )
        return corner_map[corner_id]
    if len(corner_map) == 1:
        return next(iter(corner_map.values()))
    raise KeyError(
        f"{blut.path}: run_id '{run_id}' has {len(corner_map)} corners "
        f"({sorted(corner_map.keys())}) — pass corner_id to disambiguate."
    )

log = logging.getLogger("digitwin.blut_reader_ext")

DEFAULT_CURRENT_SUFFIXES = ["$flow"]


# ---------------------------------------------------------------------------
# $flow suffix classification (naming convention, not a BLUT format feature)
# ---------------------------------------------------------------------------

def classify_signal_kind(
    name: str, current_suffixes: List[str] = None
) -> Literal["current", "voltage"]:
    """Exact-suffix match against current_suffixes (default ["$flow"]) ->
    "current"; otherwise "voltage". Case-sensitive, matching Cadence's own
    $flow probe-naming convention."""
    suffixes = current_suffixes if current_suffixes is not None else DEFAULT_CURRENT_SUFFIXES
    for suf in suffixes:
        if suf and name.endswith(suf):
            return "current"
    return "voltage"


def strip_kind_suffix(name: str, current_suffixes: List[str] = None) -> str:
    """Strip a matched current suffix, returning the base signal name used
    for spec-mapping purposes. No-op if no suffix matches."""
    suffixes = current_suffixes if current_suffixes is not None else DEFAULT_CURRENT_SUFFIXES
    for suf in suffixes:
        if suf and name.endswith(suf):
            return name[: -len(suf)]
    return name


# ---------------------------------------------------------------------------
# Discovery: union of signal base names across all runs
# ---------------------------------------------------------------------------

def list_all_signal_base_names(
    blut: BlutFile, current_suffixes: List[str] = None
) -> Dict[str, dict]:
    """Union of signal base names across all runs in the file. Each entry:
        {"kind": "voltage"|"current", "base_name": str, "present_in_runs": [run_id,...]}
    If the same base name appears as both a voltage and a $flow current in
    different runs (or the same run), both kinds are tracked distinctly
    under composite key f"{base_name}::{kind}" to avoid collapsing them."""
    suffixes = current_suffixes if current_suffixes is not None else DEFAULT_CURRENT_SUFFIXES
    discovered: Dict[str, dict] = {}

    for run in iter_runs(blut):
        run_id = run.run_id
        for raw_name in run.signals.keys():
            kind = classify_signal_kind(raw_name, suffixes)
            base = strip_kind_suffix(raw_name, suffixes)
            key = f"{base}::{kind}"
            if key not in discovered:
                discovered[key] = {
                    "kind": kind,
                    "base_name": base,
                    "present_in_runs": [],
                }
            discovered[key]["present_in_runs"].append(run_id)

    return discovered


def print_signal_discovery_table(discovered: Dict[str, dict]) -> None:
    """Pretty-print the output of list_all_signal_base_names."""
    print(f"\n{'='*70}")
    print(f"  BLUT Signal Discovery")
    print(f"  {'Base Name':<30} {'Kind':<10} {'Present In Runs'}")
    print(f"  {'-'*66}")
    for key in sorted(discovered.keys()):
        info = discovered[key]
        runs_str = ", ".join(info["present_in_runs"][:4])
        if len(info["present_in_runs"]) > 4:
            runs_str += f" (+{len(info['present_in_runs']) - 4} more)"
        print(f"  {info['base_name']:<30} {info['kind']:<10} {runs_str}")
    print()


# ---------------------------------------------------------------------------
# Bulk per-run matrix decode
# ---------------------------------------------------------------------------

def load_run_matrix(
    path: str,
    run: "bf.RunMeta",
    signal_names: Optional[List[str]] = None,
    current_suffixes: List[str] = None,
    signal_map=None,
) -> dict:
    """Decode every requested signal (default: every signal in the run) and
    return a dict of aligned voltage/current matrices.

    Missing signals (when signal_names is explicitly given and a name is
    absent from this run) are logged via log.warning and filled with a
    NaN column rather than silently dropped, so column counts stay
    consistent across heterogeneous runs when the caller requested a
    fixed explicit signal list.

    signal_map : optional digitwin.spec_signal_map.SignalMap. When given,
    decoded BLUT base names are renamed to their speckg_name (kind-aware,
    via SignalMap.reverse_resolve) before being placed into
    voltage_names/current_names — this keeps load_run_matrix/load_all_runs
    consistent with SignalCapture.load_from_blut's renaming behavior, so
    callers like core.phases.blut_reference.fill_missing_state_transient
    can search by SpecKG-native name regardless of which reader_ext
    function produced the run dict. Names with no mapping keep their raw
    BLUT base name (same fallback as SignalCapture).
    """
    suffixes = current_suffixes if current_suffixes is not None else DEFAULT_CURRENT_SUFFIXES
    ntime = run.ntime

    if signal_names is None:
        raw_names = list(run.signals.keys())
    else:
        raw_names = list(signal_names)

    voltage_cols: List[np.ndarray] = []
    voltage_names: List[str] = []
    current_cols: List[np.ndarray] = []
    current_names: List[str] = []

    for raw_name in raw_names:
        kind = classify_signal_kind(raw_name, suffixes)
        base = strip_kind_suffix(raw_name, suffixes)

        if raw_name in run.signals:
            arr = decode(path, run, raw_name)
        else:
            log.warning(
                "%s: signal '%s' not present in run '%s' (ntime=%d) — "
                "filling with NaN column to preserve requested column order.",
                path, raw_name, run.run_id, ntime,
            )
            arr = np.full(ntime, np.nan, dtype=np.float64)

        renamed = base
        if signal_map is not None:
            mapped = signal_map.reverse_resolve(base, run_id=run.run_id, kind=kind)
            if mapped is not None:
                renamed = mapped

        if kind == "current":
            current_cols.append(arr)
            current_names.append(renamed)
        else:
            voltage_cols.append(arr)
            voltage_names.append(renamed)

    voltage_matrix = (
        np.column_stack(voltage_cols) if voltage_cols else np.zeros((ntime, 0))
    )
    current_matrix = (
        np.column_stack(current_cols) if current_cols else np.zeros((ntime, 0))
    )

    return {
        "time": run.times,
        "voltage_names": voltage_names,
        "voltage_matrix": voltage_matrix,
        "current_names": current_names,
        "current_matrix": current_matrix,
        "run_id": run.run_id,
        "corner_id": getattr(run, "corner_id", ""),
        "meta": run.meta,
    }


def load_all_runs(
    path: str,
    signal_names: Optional[List[str]] = None,
    current_suffixes: List[str] = None,
    signal_map=None,
) -> List[dict]:
    """Call load_run_matrix for every run in the file, in run order (the
    order runs were read from the file, i.e. BlutFile.runs dict order).
    signal_map, if given, is forwarded to load_run_matrix for consistent
    SpecKG-name renaming across every run."""
    blut = open_blut(path)
    suffixes = current_suffixes if current_suffixes is not None else DEFAULT_CURRENT_SUFFIXES
    results = []
    for run in iter_runs(blut):
        results.append(load_run_matrix(path, run, signal_names, suffixes, signal_map=signal_map))
    return results


# ---------------------------------------------------------------------------
# Digital/logic classification of decoded run signals (reuses
# signal_capture._is_bimodal rather than duplicating the algorithm)
# ---------------------------------------------------------------------------

def iter_run_transitions(
    run_dict: dict, digital_names: Optional[List[str]] = None
) -> np.ndarray:
    """Classify which of run_dict['voltage_names'] behave as digital/logic
    signals purely from decoded waveform shape (BLUT stores everything as
    float regardless of digital/analog origin). Returns a boolean array,
    True at index i if voltage_names[i] is digital-like.

    If digital_names is given, only those names are checked (others forced
    False); otherwise every voltage column is tested.
    """
    # Import lazily to avoid a hard import-time dependency cycle between
    # digitwin/ and core/fsm/ (core/fsm imports digitwin, not vice versa,
    # in the normal flow, but this keeps blut_reader_ext usable standalone).
    from core.fsm.signal_capture import SignalCapture

    names = run_dict["voltage_names"]
    matrix = run_dict["voltage_matrix"]
    is_digital = np.zeros(len(names), dtype=bool)

    sc = SignalCapture()  # only used for its _is_bimodal classifier method
    for i, name in enumerate(names):
        if digital_names is not None and name not in digital_names:
            continue
        col = matrix[:, i]
        valid = col[~np.isnan(col)]
        if valid.size == 0:
            continue
        is_digital[i] = sc._is_bimodal(valid)

    return is_digital


# ---------------------------------------------------------------------------
# Run metadata parsing helper (used by Phase 2 stimulus-column extraction)
# ---------------------------------------------------------------------------

def parse_meta_string(meta: str) -> Dict[str, str]:
    """Parse a RunMeta.meta string of the form "corner=ff,temp=125" into a
    dict {"corner": "ff", "temp": "125"}. Malformed tokens (no '=') are
    skipped with a debug log rather than raising, since meta is free-form
    by the builder's own contract ("Free-form metadata string...")."""
    result: Dict[str, str] = {}
    if not meta:
        return result
    for token in meta.split(","):
        token = token.strip()
        if not token:
            continue
        if "=" not in token:
            log.debug("parse_meta_string: skipping malformed token %r in meta=%r", token, meta)
            continue
        key, _, val = token.partition("=")
        result[key.strip()] = val.strip()
    return result
