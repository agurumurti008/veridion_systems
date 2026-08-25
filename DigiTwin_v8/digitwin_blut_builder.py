#!/usr/bin/env python3
"""
digitwin_blut_builder.py — digiTwin BLUT (v7) builder.

Converts Cadence simulation results (PSF data exported to CSV via SKILL
scripts) into a compact, run-aware binary lookup table (BLUT) used for:
  1. Offline plotting / analysis / debug (via digitwin_blut_reader.py).
  2. DPI-C replay of analog/mixed-signal behavior inside digital/UVM
     simulation (see BLUT_FORMAT.md sec 9 for DPI-C compatibility notes).

v7 adds multi-run consolidation: many CSV result sets (corners, seeds,
regression iterations) that share signal names can be combined into one
BLUT container, each tagged with an explicit run_id / run_number, with its
own independent time grid. See BLUT_FORMAT.md for the full format spec.

USAGE
-----
Create a new multi-run BLUT, one run per CSV:

  python3 digitwin_blut_builder.py create \\
      --out regression.blut \\
      --csv corner_ff.csv  --run-id corner_ff_125c  --run-meta "corner=ff,temp=125" \\
      --csv corner_ss.csv  --run-id corner_ss_m40c  --run-meta "corner=ss,temp=-40" \\
      --workers 12 --mode int32 --qstep-rel 1e-4 --compress yes

Append one more run to an existing BLUT:

  python3 digitwin_blut_builder.py append-run \\
      --out regression.blut \\
      --csv corner_tt.csv --run-id corner_tt_25c --run-meta "corner=tt,temp=25"

Inspect a BLUT without loading signal data:

  python3 digitwin_blut_builder.py validate --out regression.blut

Migrate an old v6 single-run file to a v8 single-run container:

  python3 digitwin_blut_builder.py migrate-v6 --csv-equiv-blut old_psf.bin \\
      --out regression.blut --run-id legacy_run

Migrate an old v7 multi-run file to v8, optionally backfilling corner_id
from each run's meta string (see corner_id_from_meta convention):

  python3 digitwin_blut_builder.py migrate-v7 --blut-v7 old_regression.blut \\
      --out regression_v8.blut --corner-from-meta

Export one run back out as a standalone v6 file (for an unmodified DPI-C
consumer that only understands v6):

  python3 digitwin_blut_builder.py export-v6 \\
      --out regression.blut --run-id corner_ff_125c --export-path corner_ff_v6.bin

3x3 REGRESSION MATRIX: run_id x corner_id
------------------------------------------
v8 adds --corner-id as a second organizational axis orthogonal to
--run-id: the same run_id can repeat under different corner_id values
(the same stimulus swept across PVT corners), and the same corner_id can
repeat under different run_id values (different stimuli at one corner).
The uniqueness key for a run within a container is the PAIR
(run_id, corner_id), not run_id alone.

  # 3 stimuli x 3 corners = 9 runs, all in one container, each queryable
  # by run_id alone, corner_id alone, or the explicit pair.
  python3 digitwin_blut_builder.py create --out regression.blut \\
      --csv startup_ff.csv  --run-id startup_test    --corner-id ff_125c_1p98v \\
      --csv startup_tt.csv  --run-id startup_test    --corner-id tt_25c_1p8v \\
      --csv startup_ss.csv  --run-id startup_test    --corner-id ss_m40c_1p62v \\
      --csv load_ff.csv     --run-id load_transient  --corner-id ff_125c_1p98v \\
      --csv load_tt.csv     --run-id load_transient  --corner-id tt_25c_1p8v \\
      --csv load_ss.csv     --run-id load_transient  --corner-id ss_m40c_1p62v \\
      --csv psrr_ff.csv     --run-id psrr_sweep      --corner-id ff_125c_1p98v \\
      --csv psrr_tt.csv     --run-id psrr_sweep      --corner-id tt_25c_1p8v \\
      --csv psrr_ss.csv     --run-id psrr_sweep      --corner-id ss_m40c_1p62v \\
      --workers 8

  # Reader can then select "all corners for psrr_sweep" or "all run_ids at
  # tt_25c_1p8v" — see digitwin_blut_reader.py --runs / --corners.

NOTES
-----
- CSV format: first column is time (any header name accepted), remaining
  columns are signal names. Same CSV column-naming convention as before.
- Multiple CSVs with the *same* signal names are expected and supported —
  that's the whole point of multi-run consolidation. Signals are scoped
  per-run; identical names across runs do not collide.
- corner_id defaults to "" (empty string) when --corner-id is never used,
  which is fully backward compatible: uniqueness then reduces to run_id
  alone, identical to pre-v8 behavior.
- See "Part 1 bug fixes" below for what changed vs. the original
  parallel_blut_builder.py; see BLUT_FORMAT.md sec 2 for the full diff.
"""

from __future__ import annotations

import argparse
import glob as globmod
import logging
import multiprocessing as mp
import os
import sys
import zlib
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

import blut_format as bf

log = logging.getLogger("digitwin.builder")


# ---------------------------------------------------------------------------
# Transition finding (Part 1 fix: working tolerance, explicit qstep modes)
# ---------------------------------------------------------------------------

def find_transitions(vals: np.ndarray, tol: float) -> np.ndarray:
    """Greedy running-baseline transition finder.

    Keeps index i whenever |vals[i] - vals[last_kept]| > tol. This bounds
    the zero-order-hold reconstruction error to `tol` (in signal units)
    for every sample, and always keeps the first and last sample.

    tol <= 0 means "exact mode": every sample is kept (equivalent to the
    original script's `preserve_all=True`, but now reachable deliberately
    via tol=0 rather than being the only code path that worked).

    This is an intentionally sequential greedy scan (the kept baseline
    resets every time a point is kept), so it's expressed as a Python loop
    rather than a vectorized numpy op — RDP-style sequential delta
    encoding doesn't vectorize without losing the greedy property. At
    ~2M samples/signal this costs well under half a second per signal,
    and signals are already processed in parallel across worker
    processes, so this has not been a bottleneck in practice. The tol<=0
    fast path below avoids the loop entirely for exact-mode signals
    (e.g. digital/discrete nets where every sample matters).
    """
    n = vals.size
    if n == 0:
        return np.array([], dtype=np.int64)
    if n <= 2 or tol <= 0.0:
        return np.arange(n, dtype=np.int64)

    keep = [0]
    last = 0
    last_val = vals[0]
    for i in range(1, n - 1):
        vi = vals[i]
        if abs(vi - last_val) > tol:
            keep.append(i)
            last = i
            last_val = vi
    if keep[-1] != n - 1:
        keep.append(n - 1)
    return np.asarray(keep, dtype=np.int64)


def resolve_tolerance(
    vals: np.ndarray, tol_abs: float, tol_rel: float
) -> float:
    """Combine absolute and range-relative tolerance into one effective
    tolerance in signal units. tol_rel is a fraction of (max-min)."""
    if tol_abs <= 0.0 and tol_rel <= 0.0:
        return 0.0
    rng = float(vals.max() - vals.min()) if vals.size else 0.0
    rel = tol_rel * rng if (tol_rel > 0.0 and rng > 0.0) else 0.0
    return max(tol_abs, rel)


def resolve_qstep(vals: np.ndarray, qstep_abs: Optional[float], qstep_rel: Optional[float]) -> float:
    """Resolve the quantization step in absolute signal units.

    Part 1 fix: the original script silently reinterpreted --qstep as
    range-relative whenever max != min, even though it was documented and
    used as an absolute value. v7 requires the caller to pick one
    explicitly (--qstep-abs or --qstep-rel, mutually exclusive at the CLI
    level), and this function only does the range->absolute conversion
    when --qstep-rel was actually requested.
    """
    rng = float(vals.max() - vals.min()) if vals.size else 0.0

    if qstep_rel is not None:
        if rng <= 0.0:
            # constant signal: relative step is meaningless, fall back to
            # a small absolute floor so quantization still has *a* step.
            return 1e-9
        return rng * qstep_rel

    if qstep_abs is not None:
        return qstep_abs

    # Neither given (shouldn't happen if CLI enforces one) — safe fallback.
    return max(1e-9, rng * 1e-6)


# ---------------------------------------------------------------------------
# Worker (one signal per task)
# ---------------------------------------------------------------------------

@dataclass
class BuildConfig:
    mode: str               # 'int32' | 'float32' | 'float64'
    qstep_abs: Optional[float]
    qstep_rel: Optional[float]
    compress: bool
    tol_abs: float
    tol_rel: float
    on_signal_collision: str = "error"   # 'error' | 'last-wins', see merge_csv_group()
    allow_time_mismatch: bool = False    # see merge_csv_group()


@dataclass
class RunSpec:
    """One run-to-be-written: one or more source CSVs that will be merged
    into a single run_id. This generalizes the old (csv, run_id, run_meta)
    tuple contract to support --csv-group and --csv-pattern, while a plain
    --csv still produces a RunSpec with csv_paths=[single_path] so the rest
    of the pipeline (load + merge + write) doesn't need to special-case the
    single-CSV case at all.

    corner_id (v8): a second organizational axis, orthogonal to run_id.
    The uniqueness key for a run within a container is the PAIR
    (run_id, corner_id) — the same run_id may repeat under different
    corner_id values (the same stimulus at different PVT corners), and
    the same corner_id may repeat under different run_id values (different
    stimuli at the same corner). Defaults to "" (no corner context),
    preserving the original run_id-only uniqueness behavior when
    --corner-id is never used.
    """
    csv_paths: list[str]
    run_id: str
    run_meta: str
    corner_id: str = ""


_WORKER_TIMES: Optional[np.ndarray] = None  # set once per worker via initializer


def _worker_init(times: np.ndarray) -> None:
    """Pool initializer: stash the (shared, identical-for-every-task) time
    array once per worker process instead of pickling it on every task.
    Part 1 perf fix for the original script's per-task `times` duplication."""
    global _WORKER_TIMES
    _WORKER_TIMES = times


def worker_make_block(sig_name: str, vals: np.ndarray, cfg: BuildConfig) -> tuple[str, dict]:
    """Build one signal's encoded block payload (in memory, not yet written
    to any file — the parent process owns all file I/O so blocks for a run
    can be streamed straight into the final container in order)."""
    v = np.asarray(vals, dtype=np.float64)
    if v.size == 0:
        return sig_name, {"empty": True, "reason": "zero samples"}

    finite_mask = np.isfinite(v)
    if not finite_mask.any():
        # entirely NaN/Inf (e.g. an unconnected/unmeasured net in the CSV
        # export) — treat as empty rather than silently quantizing NaN
        # into int32 (which numpy will do with a RuntimeWarning and a
        # meaningless result).
        return sig_name, {"empty": True, "reason": "all NaN/Inf"}
    if not finite_mask.all():
        n_bad = int((~finite_mask).sum())
        log.warning(
            "Signal '%s' has %d non-finite sample(s) out of %d; this is not "
            "currently handled (no interpolation/masking is applied) and "
            "will likely produce a quantization range/overflow error below. "
            "Clean non-finite values out of the source CSV/PSF export.",
            sig_name, n_bad, v.size,
        )

    encoding = bf.ENC_BY_NAME[cfg.mode]
    offset = float(v.min())
    qstep = resolve_qstep(v, cfg.qstep_abs, cfg.qstep_rel)
    tol = resolve_tolerance(v, cfg.tol_abs, cfg.tol_rel)

    idxs = find_transitions(v, tol)
    vals_sel = v[idxs]

    payload, raw_bytes = bf.build_signal_payload(idxs, vals_sel, encoding, offset, qstep)

    return sig_name, {
        "empty": False,
        "idxs": idxs,
        "vals_sel": vals_sel,
        "encoding": encoding,
        "offset": offset,
        "qstep": qstep,
        "raw_bytes": raw_bytes,
        "nchange": idxs.size,
    }


# ---------------------------------------------------------------------------
# CSV -> per-run signal dict (parallel across signals within one run)
# ---------------------------------------------------------------------------

def load_csv(csv_path: str) -> tuple[np.ndarray, list[str], pd.DataFrame]:
    log.info("Loading CSV: %s", csv_path)
    df = pd.read_csv(csv_path, dtype=np.float64)
    col_names = list(dict.fromkeys(df.columns))  # de-dup, preserve order
    if len(col_names) < 2:
        raise ValueError(f"{csv_path}: expected a time column plus at least one signal column")
    times = df[col_names[0]].to_numpy(dtype=np.float64)
    signals = col_names[1:]
    log.info("Found %d signals, %d samples in %s", len(signals), len(times), csv_path)
    return times, signals, df


def build_run_blocks(
    times: np.ndarray, signals: list[str], df: pd.DataFrame, cfg: BuildConfig, workers: int
) -> dict[str, dict]:
    """Run the worker pool across all signals for one CSV/run. Returns
    {signal_name: block_dict} as produced by worker_make_block."""
    n_time = times.size
    mismatched = [s for s in signals if len(df[s]) != n_time]
    if mismatched:
        raise ValueError(
            f"Signal column length mismatch against the run's time grid "
            f"({n_time} samples): {mismatched[:5]}{'...' if len(mismatched) > 5 else ''}. "
            f"Every signal column must have exactly one value per time-grid sample; a "
            f"mismatch here would otherwise produce transition indices out of range for "
            f"the stored time grid, which fails (or silently misreads) at decode time "
            f"instead of at build time."
        )

    tasks = [(sig, df[sig].to_numpy(dtype=np.float64), cfg) for sig in signals]
    nworkers = max(1, min(workers, len(tasks)))
    log.info("Starting pool with %d workers for %d signals ...", nworkers, len(tasks))

    results: dict[str, dict] = {}
    if nworkers == 1:
        # avoid pool overhead entirely for small/serial cases
        _worker_init(times)
        for sig, vals, c in tasks:
            name, block = worker_make_block(sig, vals, c)
            results[name] = block
    else:
        with mp.Pool(nworkers, initializer=_worker_init, initargs=(times,)) as pool:
            for name, block in pool.starmap(worker_make_block, tasks):
                results[name] = block

    n_empty = sum(1 for b in results.values() if b.get("empty"))
    if n_empty:
        log.warning("%d of %d signals were empty and will be skipped", n_empty, len(results))
    return results


def merge_csv_group(
    csv_paths: list[str], cfg: BuildConfig, workers: int
) -> tuple[np.ndarray, dict[str, dict]]:
    """Load and merge multiple CSVs into one run's worth of (times, blocks).

    Contract (see CHANGELOG / BLUT_FORMAT.md companion notes for the v7.1
    CLI extension):
      - Time grid: the FIRST csv_path's time grid is authoritative for the
        merged run. Every other CSV in the group must have an identical
        time grid (same length, same values) or this is a hard error,
        UNLESS cfg.allow_time_mismatch is True, in which case the mismatch
        is logged as a warning and the first CSV's grid is still used
        (later CSVs' rows are still consumed positionally by index, NOT
        resampled — if their grids genuinely differ in length/spacing this
        will silently misalign samples, which is why this is opt-in only).
      - Signal name collisions across CSVs in the group:
          cfg.on_signal_collision == "error" (default): hard error listing
            every colliding signal name and which CSVs they came from.
          cfg.on_signal_collision == "last-wins": the signal from the
            LAST csv_path (in the order given) wins; a warning is logged
            per collision naming the discarded source file.
      - Each CSV is still processed through the existing build_run_blocks
        (so the worker pool / quantization / transition-finding code path
        is reused verbatim, not reimplemented).
    """
    if not csv_paths:
        raise ValueError("merge_csv_group: csv_paths is empty")

    if cfg.on_signal_collision not in ("error", "last-wins"):
        raise ValueError(
            f"on_signal_collision must be 'error' or 'last-wins', got {cfg.on_signal_collision!r}"
        )

    merged_blocks: dict[str, dict] = {}
    signal_source: dict[str, str] = {}  # signal name -> csv_path that produced it (for error/warn messages)
    authoritative_times: Optional[np.ndarray] = None
    collisions: list[tuple[str, str, str]] = []  # (signal, old_source, new_source)

    for csv_path in csv_paths:
        times, signals, df = load_csv(csv_path)

        if authoritative_times is None:
            authoritative_times = times
        else:
            same_len = times.shape == authoritative_times.shape
            same_vals = same_len and np.array_equal(times, authoritative_times)
            if not same_vals:
                msg = (
                    f"Time grid mismatch in CSV group: '{csv_path}' has a different "
                    f"time grid ({times.size} samples) than the group's first CSV "
                    f"'{csv_paths[0]}' ({authoritative_times.size} samples). BLUT does "
                    f"not resample — grouped CSVs sharing one run_id must share one "
                    f"time grid."
                )
                if not cfg.allow_time_mismatch:
                    raise ValueError(msg + " Pass --allow-time-mismatch to override (unsafe).")
                n_auth = authoritative_times.size
                if times.size < n_auth:
                    raise ValueError(
                        msg + f" Cannot proceed even with --allow-time-mismatch: '{csv_path}' "
                        f"has FEWER samples ({times.size}) than the group's authoritative grid "
                        f"({n_auth}), which would leave transition indices pointing past the "
                        f"end of its own data."
                    )
                log.warning(
                    "%s Proceeding because --allow-time-mismatch was given: '%s' will be "
                    "truncated to the first %d row(s) and consumed positionally against the "
                    "FIRST CSV's time grid — this silently drops any rows beyond that and is "
                    "unsafe unless you know the grids are positionally equivalent.",
                    msg, csv_path, n_auth,
                )
                df = df.iloc[:n_auth].reset_index(drop=True)

        blocks = build_run_blocks(authoritative_times, signals, df, cfg, workers)

        for name, block in blocks.items():
            if name in merged_blocks:
                collisions.append((name, signal_source[name], csv_path))
                if cfg.on_signal_collision == "error":
                    continue  # keep scanning to report ALL collisions at once, not just the first
                # last-wins: fall through and overwrite below
            merged_blocks[name] = block
            signal_source[name] = csv_path

    if collisions and cfg.on_signal_collision == "error":
        detail = "; ".join(
            f"'{name}' in both '{old}' and '{new}'" for name, old, new in collisions
        )
        raise ValueError(
            f"Signal name collision(s) across grouped CSVs (on_signal_collision=error): "
            f"{detail}. Use --on-signal-collision last-wins to allow this (last CSV in "
            f"the group order wins), or rename signals upstream."
        )
    if collisions:  # last-wins: already overwritten above, just log
        for name, old, new in collisions:
            log.warning(
                "Signal '%s' present in multiple grouped CSVs; '%s' overrides value "
                "from '%s' (on_signal_collision=last-wins).",
                name, new, old,
            )

    assert authoritative_times is not None
    return authoritative_times, merged_blocks


def load_and_build_for_spec(
    spec: RunSpec, cfg: BuildConfig, workers: int
) -> tuple[np.ndarray, dict[str, dict]]:
    """Resolve one RunSpec (1 or more CSVs) to (times, blocks) ready for
    write_run(). Single-CSV RunSpecs go through the original load_csv +
    build_run_blocks path unchanged (zero behavior change for existing
    --csv usage); multi-CSV RunSpecs go through merge_csv_group()."""
    if len(spec.csv_paths) == 1:
        times, signals, df = load_csv(spec.csv_paths[0])
        blocks = build_run_blocks(times, signals, df, cfg, workers)
        return times, blocks
    return merge_csv_group(spec.csv_paths, cfg, workers)


def write_run(
    f, run_number: int, run_id: str, run_meta: str, times: np.ndarray,
    blocks: dict[str, dict], compress: bool, hold_mode: int = bf.HOLD_ZOH,
    corner_id: str = "",
) -> int:
    """Write one full run section (header + all non-empty signal blocks).
    Returns the number of signals actually written."""
    run_header_offset = f.tell()
    bf.write_run_header(f, run_number, run_id, run_meta, times, corner_id=corner_id)

    n_written = 0
    for name in sorted(blocks.keys()):
        block = blocks[name]
        if block.get("empty"):
            log.warning("Skipping signal '%s' in run '%s' (corner '%s'): %s",
                        name, run_id, corner_id, block.get("reason", "empty"))
            continue
        bf.write_signal_block(
            f, name, block["idxs"], block["vals_sel"], block["encoding"],
            block["offset"], block["qstep"], compress, hold_mode,
        )
        n_written += 1

    bf.patch_run_n_signals(f, run_header_offset, n_written)
    return n_written


# ---------------------------------------------------------------------------
# High-level commands
# ---------------------------------------------------------------------------

def cmd_create(args: argparse.Namespace) -> int:
    cfg = _cfg_from_args(args)
    run_specs = _resolve_run_specs(args)

    if os.path.exists(args.out) and not args.force:
        log.error("%s already exists. Use 'append-run' to add to it, or pass --force to overwrite.", args.out)
        return 2

    # Build into a temp file and only replace --out on full success. A
    # mid-build failure (e.g. a --csv-group time-mismatch or signal
    # collision on a later run) must not leave a partial/misleading file
    # at --out — this matters more now that merge_csv_group() can fail
    # partway through a multi-run create.
    tmp_path = args.out + ".tmp"
    try:
        with open(tmp_path, "wb") as f:
            bf.write_file_header(f, n_runs=0)  # patched at the end
            n_runs_written = 0
            for run_number, spec in enumerate(run_specs):
                times, blocks = load_and_build_for_spec(spec, cfg, args.workers)
                n_sig = write_run(f, run_number, spec.run_id, spec.run_meta, times, blocks,
                                   cfg.compress, corner_id=spec.corner_id)
                log.info(
                    "Wrote run '%s' corner '%s' (run_number=%d, %d source CSV(s)): %d signals",
                    spec.run_id, spec.corner_id, run_number, len(spec.csv_paths), n_sig,
                )
                n_runs_written += 1
            bf.patch_file_header_counts(f, n_runs_written)
    except BaseException:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        raise

    os.replace(tmp_path, args.out)
    log.info("Created %s with %d run(s)", args.out, n_runs_written)
    return 0


def cmd_append_run(args: argparse.Namespace) -> int:
    cfg = _cfg_from_args(args)
    run_specs = _resolve_run_specs(args)

    if not os.path.exists(args.out):
        log.error("%s does not exist. Use 'create' first.", args.out)
        return 2

    existing_run_keys, next_run_number, file_version = _scan_existing_runs(args.out)
    if file_version != bf.VERSION:
        log.error(
            "%s is BLUT v%d, not v%d. Use 'migrate-v6' or 'migrate-v7' first to upgrade.",
            args.out, file_version, bf.VERSION,
        )
        return 2

    # Uniqueness key is the (run_id, corner_id) PAIR, not run_id alone: the
    # same run_id is expected and allowed to repeat under different
    # corner_id values (same stimulus, different PVT corner).
    new_run_key_set = {(spec.run_id, spec.corner_id) for spec in run_specs}
    collisions = new_run_key_set & existing_run_keys
    if collisions and not args.force:
        log.error(
            "(run_id, corner_id) pair(s) already present in %s: %s. Choose a "
            "different --run-id or --corner-id, or pass --force to add them "
            "anyway ((run_id, corner_id) is not required to be unique, but "
            "duplicates make run/corner-qualified lookups ambiguous).",
            args.out, sorted(collisions),
        )
        return 2

    with open(args.out, "r+b") as f:
        f.seek(0, os.SEEK_END)
        append_start_offset = f.tell()
        n_runs_added = 0
        run_number = next_run_number
        try:
            for spec in run_specs:
                times, blocks = load_and_build_for_spec(spec, cfg, args.workers)
                n_sig = write_run(f, run_number, spec.run_id, spec.run_meta, times, blocks,
                                   cfg.compress, corner_id=spec.corner_id)
                log.info(
                    "Appended run '%s' corner '%s' (run_number=%d, %d source CSV(s)): %d signals",
                    spec.run_id, spec.corner_id, run_number, len(spec.csv_paths), n_sig,
                )
                run_number += 1
                n_runs_added += 1
        except BaseException:
            # n_runs in the file header has NOT been patched yet at this
            # point, so the existing file is still structurally valid and
            # readable as-is — but truncate back to drop the orphaned
            # partial-run bytes already written for this failed attempt,
            # rather than leaving dead space appended to the file.
            f.truncate(append_start_offset)
            raise

        f.seek(0)
        fh = bf.read_file_header(f, args.out)
        f.seek(0, os.SEEK_END)
        # patch n_runs in place at offset 8
        f.seek(8)
        f.write((fh.n_runs + n_runs_added).to_bytes(4, "little"))

    log.info("Appended %d run(s) to %s", n_runs_added, args.out)
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    """--dry-run / --validate: report BLUT contents without loading signal data."""
    path = args.out
    try:
        with open(path, "rb") as f:
            fh = bf.read_file_header(f, path)
            print(f"File:    {path}")
            print(f"Version: {fh.version}")

            if fh.version == bf.VERSION_V6:
                run = bf.read_v6_as_run(f, path, load_signals=False)
                _print_run_summary(run)
                return 0

            print(f"Runs:    {fh.n_runs}")
            for _ in range(fh.n_runs):
                run = bf.read_run_meta(f, path, version=fh.version, load_signals=False)
                _print_run_summary(run)
        return 0
    except bf.BlutFormatError as e:
        log.error("Validation failed: %s", e)
        return 1
    except FileNotFoundError:
        log.error("File not found: %s", path)
        return 2


def _print_run_summary(run: bf.RunMeta) -> None:
    span = f"[{run.times[0]:.6g}, {run.times[-1]:.6g}]" if run.ntime else "[]"
    corner_str = f" corner_id={run.corner_id!r}" if run.corner_id else ""
    print(f"  - run_id={run.run_id!r}{corner_str} run_number={run.run_number} "
          f"ntime={run.ntime} time_span={span} meta={run.meta!r} "
          f"n_signals={run.n_signals}")
    total_enc = sum(s.enc_bytes for s in run.signals.values())
    total_raw = sum(s.raw_bytes for s in run.signals.values())
    ratio = (total_raw / total_enc) if total_enc else float("nan")
    print(f"    encoded_bytes={total_enc:,} raw_bytes={total_raw:,} "
          f"compression_ratio={ratio:.2f}x")
    for name in sorted(run.signals):
        s = run.signals[name]
        print(f"    - {name}: enc={s.encoding_name} comp={'zlib' if s.compressed else 'none'} "
              f"nchange={s.nchange} ({100*s.nchange/max(run.ntime,1):.1f}% of samples) "
              f"enc_bytes={s.enc_bytes:,}")


def _decode_signal_raw(sig: bf.SignalBlockMeta) -> tuple[np.ndarray, np.ndarray]:
    """Decode a SignalBlockMeta back to (transition_idxs, values) exactly as
    originally stored, so migration can re-pack them verbatim into a new
    signal block without re-deriving transitions or touching quantization.
    Returns empty arrays for empty signals.

    Works identically regardless of which container version (v6/v7/v8) the
    signal block was read from — the signal block binary layout has never
    changed across BLUT format versions; only the run header (which wraps
    signal blocks) gained the corner_id field in v8. This is used by both
    migrate-v6 and migrate-v7.
    """
    if sig.nchange == 0:
        return np.array([], dtype=np.int64), np.array([], dtype=np.float64)

    payload = zlib.decompress(sig.blob) if sig.compressed == bf.COMP_ZLIB else sig.blob
    delta_bytes = 4 * sig.nchange
    deltas = np.frombuffer(payload[:delta_bytes], dtype=np.uint32)
    raw_vals = np.frombuffer(payload[delta_bytes:], dtype=bf.ENC_DTYPE[sig.encoding])
    idxs = np.cumsum(deltas.astype(np.int64))
    vals = bf.dequantize(raw_vals, sig.encoding, sig.offset, sig.qstep)
    return idxs, vals


def cmd_migrate_v6(args: argparse.Namespace) -> int:
    """Convert a v6 single-run BLUT into a v8 single-run container (the
    module always writes the current VERSION via write_file_header(), so
    this targets v8, not v7, despite the subcommand's historical name).
    corner_id defaults to "" since v6 files have no corner concept at all."""
    src = args.csv_equiv_blut  # the existing v6 .bin file
    with open(src, "rb") as f:
        fh = bf.read_file_header(f, src)
        if fh.version != bf.VERSION_V6:
            log.error("%s is not a v6 BLUT file (version=%d)", src, fh.version)
            return 2
        run = bf.read_v6_as_run(f, src, load_signals=True)

    run_id = args.run_id or bf.LEGACY_V6_RUN_ID
    with open(args.out, "wb") as f:
        bf.write_file_header(f, n_runs=1)
        run_header_offset = f.tell()
        bf.write_run_header(f, run_number=0, run_id=run_id, meta=run.meta, times=run.times,
                             corner_id="")
        n_written = 0
        for name, sig in sorted(run.signals.items()):
            idxs, vals = _decode_signal_raw(sig)
            bf.write_signal_block(
                f, name, idxs, vals, sig.encoding, sig.offset, sig.qstep, compress=True,
            )
            n_written += 1
        bf.patch_run_n_signals(f, run_header_offset, n_written)

    log.info("Migrated %s (v6) -> %s (v%d, run_id=%r, %d signals)",
              src, args.out, bf.VERSION, run_id, n_written)
    return 0


def cmd_migrate_v7(args: argparse.Namespace) -> int:
    """Convert a v7 multi-run BLUT into a v8 multi-run container.

    If --corner-from-meta is given, each migrated run's corner_id is
    extracted from its run_meta string via bf.corner_id_from_meta() (using
    the 'corner=X' key convention already shown in the builder's
    --run-meta examples). Without --corner-from-meta, every migrated run
    gets corner_id="" — i.e. the file becomes a valid v8 file with no
    corner axis populated, identical in query behavior to how it read as
    a v7 file (every run_id remains globally unique unless the source v7
    file itself already had duplicate run_ids, which was never possible
    under the v7 single-axis uniqueness rule).
    """
    src = args.blut_v7
    with open(src, "rb") as f:
        fh = bf.read_file_header(f, src)
        if fh.version != bf.VERSION_V7:
            log.error("%s is not a v7 BLUT file (version=%d)", src, fh.version)
            return 2
        runs = []
        for _ in range(fh.n_runs):
            run = bf.read_run_meta(f, src, version=fh.version, load_signals=True)
            runs.append(run)

    tmp_path = args.out + ".tmp"
    try:
        with open(tmp_path, "wb") as f:
            bf.write_file_header(f, n_runs=0)  # patched at the end
            n_runs_written = 0
            for run in runs:
                corner_id = bf.corner_id_from_meta(run.meta) if args.corner_from_meta else ""
                run_header_offset = f.tell()
                bf.write_run_header(
                    f, run_number=run.run_number, run_id=run.run_id, meta=run.meta,
                    times=run.times, corner_id=corner_id,
                )
                n_written = 0
                for name, sig in sorted(run.signals.items()):
                    idxs, vals = _decode_signal_raw(sig)
                    bf.write_signal_block(
                        f, name, idxs, vals, sig.encoding, sig.offset, sig.qstep,
                        compress=(sig.compressed == bf.COMP_ZLIB), hold_mode=sig.hold_mode,
                    )
                    n_written += 1
                bf.patch_run_n_signals(f, run_header_offset, n_written)
                n_runs_written += 1
            bf.patch_file_header_counts(f, n_runs_written)
    except BaseException:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        raise

    os.replace(tmp_path, args.out)
    log.info(
        "Migrated %s (v7) -> %s (v%d, %d run(s), corner_from_meta=%s)",
        src, args.out, bf.VERSION, n_runs_written, args.corner_from_meta,
    )
    return 0


def cmd_export_v6(args: argparse.Namespace) -> int:
    """Export a single run from a v7/v8 container as a standalone v6 file,
    for replay through an unmodified v6 DPI-C consumer (see BLUT_FORMAT.md
    sec 9, option 2).

    Since v8 allows the same run_id to appear under multiple corner_id
    values, --run-id alone may be ambiguous. --corner-id disambiguates;
    if omitted and the run_id is ambiguous, this errors out listing the
    available corners rather than guessing which one was meant.
    """
    with open(args.out, "rb") as f:
        fh = bf.read_file_header(f, args.out)
        if fh.version not in (bf.VERSION_V7, bf.VERSION):
            log.error("%s is not a v7 or v8 BLUT file", args.out)
            return 2
        matches = []
        for _ in range(fh.n_runs):
            run = bf.read_run_meta(f, args.out, version=fh.version, load_signals=True)
            if run.run_id == args.run_id:
                matches.append(run)

        if not matches:
            log.error("run_id %r not found in %s", args.run_id, args.out)
            return 2

        if len(matches) > 1:
            if args.corner_id is None:
                available = [m.corner_id for m in matches]
                log.error(
                    "run_id %r is ambiguous in %s: %d runs share this run_id across "
                    "corner_id values %s. Pass --corner-id to disambiguate.",
                    args.run_id, args.out, len(matches), available,
                )
                return 2
            filtered = [m for m in matches if m.corner_id == args.corner_id]
            if not filtered:
                log.error(
                    "No run with run_id=%r and corner_id=%r found in %s. "
                    "Available corner_id values for this run_id: %s",
                    args.run_id, args.corner_id, args.out, [m.corner_id for m in matches],
                )
                return 2
            target = filtered[0]
        else:
            target = matches[0]
            if args.corner_id is not None and target.corner_id != args.corner_id:
                log.error(
                    "run_id %r exists in %s but with corner_id=%r, not %r.",
                    args.run_id, args.out, target.corner_id, args.corner_id,
                )
                return 2

    with open(args.export_path, "wb") as out:
        out.write(bf.MAGIC)
        out.write(bf.VERSION_V6.to_bytes(4, "little"))
        out.write(len(target.signals).to_bytes(4, "little"))
        out.write(target.ntime.to_bytes(4, "little"))
        out.write(target.times.astype(np.float64).tobytes())
        bf.write_pad8(out)
        for name in sorted(target.signals):
            sig = target.signals[name]
            out.write(len(name.encode("utf-8")).to_bytes(2, "little"))
            out.write(name.encode("utf-8"))
            bf.write_pad8(out)
            import struct as _struct
            out.write(_struct.pack("<2d", sig.offset, sig.qstep))
            out.write(_struct.pack("<BBH", sig.encoding, sig.compressed, 0))
            out.write(_struct.pack("<III", sig.nchange, sig.enc_bytes, sig.raw_bytes))
            out.write(sig.blob)
            bf.write_pad8(out)

    log.info("Exported run_id=%r corner_id=%r from %s -> %s (v6)",
              args.run_id, target.corner_id, args.out, args.export_path)
    return 0


# ---------------------------------------------------------------------------
# CLI plumbing
# ---------------------------------------------------------------------------

def _cfg_from_args(args: argparse.Namespace) -> BuildConfig:
    return BuildConfig(
        mode=args.mode,
        qstep_abs=args.qstep_abs,
        qstep_rel=args.qstep_rel,
        compress=(args.compress == "yes"),
        tol_abs=args.tol_abs,
        tol_rel=args.tol_rel,
        on_signal_collision=args.on_signal_collision,
        allow_time_mismatch=args.allow_time_mismatch,
    )


def _expand_pattern(pattern: str) -> list[str]:
    """Expand a glob pattern to a sorted, deterministic file list.
    Hard error on zero matches (never a silent no-op)."""
    matches = sorted(globmod.glob(pattern))
    if not matches:
        raise ValueError(
            f"--csv-pattern {pattern!r} matched zero files. This is treated as an "
            f"error rather than a silent no-op — check the pattern and working directory."
        )
    return matches


def _resolve_run_specs(args: argparse.Namespace) -> list[RunSpec]:
    """Resolve --csv / --csv-group / --csv-pattern (any combination, each
    repeatable) into an ordered list of RunSpec(csv_paths, run_id, run_meta,
    corner_id).

    Contract:
      --csv FILE            -> one RunSpec with csv_paths=[FILE] (unchanged
                                from the original 1:1 behavior).
      --csv-group "a,b,c"   -> one RunSpec with csv_paths=[a, b, c], merged
                                into a single run via merge_csv_group().
      --csv-pattern GLOB    -> glob-expanded to N files.
                                - If this --csv-pattern has its own paired
                                  --run-id, all N matched files collapse
                                  into ONE RunSpec (same merge path as
                                  --csv-group) under that run_id.
                                - If no --run-id is paired with it, each
                                  matched file becomes its OWN RunSpec
                                  (auto-numbered run_id, consistent with
                                  the original --csv auto-naming).

    --run-id / --run-meta / --corner-id are consumed positionally across
    the combined, in-order sequence of --csv / --csv-group / --csv-pattern
    occurrences (one slot per occurrence of any of the three flags — NOT
    one per individual file), exactly mirroring how the original code
    paired --run-id against --csv. This keeps a single, consistent
    resolution rule instead of separate branches per source flag.

    Uniqueness within one invocation is enforced on the (run_id, corner_id)
    PAIR, not on run_id alone: the same run_id may legitimately repeat
    under different corner_id values (the same stimulus swept across PVT
    corners), and the same corner_id may legitimately repeat under
    different run_id values (different stimuli at the same corner).
    """
    csv_singles = args.csv or []
    csv_groups = args.csv_group or []
    csv_patterns = args.csv_pattern or []

    # Reconstruct the original interleaving order from argparse, since
    # argparse gives us three separate lists with no record of how the
    # user interleaved --csv/--csv-group/--csv-pattern on the command
    # line. We use the order each flag-type's values were supplied in,
    # concatenated as: all --csv, then all --csv-group, then all
    # --csv-pattern. This is a deliberate, documented simplification
    # (order across *different* flag types is not preserved; order
    # *within* one flag type is). --run-id/--run-meta/--corner-id must be
    # supplied in that same concatenated order.
    n_occurrences = len(csv_singles) + len(csv_groups) + len(csv_patterns)
    run_ids = args.run_id or []
    run_metas = args.run_meta or []
    corner_ids = args.corner_id or []

    if run_ids and len(run_ids) > n_occurrences:
        raise ValueError(
            f"--run-id given {len(run_ids)} time(s) but only {n_occurrences} CSV "
            f"source(s) given across --csv/--csv-group/--csv-pattern; supply at most "
            f"one --run-id per CSV source occurrence."
        )
    if run_metas and len(run_metas) > n_occurrences:
        raise ValueError(
            f"--run-meta given {len(run_metas)} time(s) but only {n_occurrences} CSV "
            f"source(s) given across --csv/--csv-group/--csv-pattern."
        )
    if corner_ids and len(corner_ids) > n_occurrences:
        raise ValueError(
            f"--corner-id given {len(corner_ids)} time(s) but only {n_occurrences} CSV "
            f"source(s) given across --csv/--csv-group/--csv-pattern; supply at most "
            f"one --corner-id per CSV source occurrence."
        )

    specs: list[RunSpec] = []
    occurrence_idx = 0  # indexes into run_ids/run_metas/corner_ids, one slot per --csv/--csv-group/--csv-pattern occurrence

    def _next_run_id() -> Optional[str]:
        nonlocal occurrence_idx
        rid = run_ids[occurrence_idx] if occurrence_idx < len(run_ids) else None
        return rid

    def _next_run_meta() -> str:
        return run_metas[occurrence_idx] if occurrence_idx < len(run_metas) else ""

    def _next_corner_id() -> str:
        return corner_ids[occurrence_idx] if occurrence_idx < len(corner_ids) else ""

    # --csv: unchanged 1:1 behavior.
    for csv_path in csv_singles:
        rid = _next_run_id() or f"run{len(specs)}"
        meta = _next_run_meta()
        cid = _next_corner_id()
        specs.append(RunSpec(csv_paths=[csv_path], run_id=rid, run_meta=meta, corner_id=cid))
        occurrence_idx += 1

    # --csv-group "a,b,c": always one merged RunSpec.
    for group_str in csv_groups:
        paths = [p.strip() for p in group_str.split(",") if p.strip()]
        if len(paths) < 2:
            raise ValueError(
                f"--csv-group {group_str!r} must list at least 2 comma-separated CSV "
                f"paths (use --csv for a single file)."
            )
        rid = _next_run_id() or f"run{len(specs)}"
        meta = _next_run_meta()
        cid = _next_corner_id()
        specs.append(RunSpec(csv_paths=paths, run_id=rid, run_meta=meta, corner_id=cid))
        occurrence_idx += 1

    # --csv-pattern GLOB: paired --run-id -> one merged RunSpec; no
    # --run-id -> one RunSpec per matched file, auto-numbered.
    for pattern in csv_patterns:
        matched = _expand_pattern(pattern)
        paired_run_id = _next_run_id()
        meta = _next_run_meta()
        cid = _next_corner_id()
        if paired_run_id is not None:
            specs.append(RunSpec(csv_paths=matched, run_id=paired_run_id, run_meta=meta, corner_id=cid))
        else:
            for csv_path in matched:
                specs.append(RunSpec(csv_paths=[csv_path], run_id=f"run{len(specs)}", run_meta=meta, corner_id=cid))
        occurrence_idx += 1

    seen = set()
    for spec in specs:
        key = (spec.run_id, spec.corner_id)
        if key in seen:
            raise ValueError(
                f"Duplicate (run_id, corner_id) pair {key!r} within this command "
                f"invocation. run_id may repeat across different corner_id values "
                f"(and vice versa), but the same (run_id, corner_id) pair must be "
                f"unique."
            )
        seen.add(key)

    if not specs:
        raise ValueError("No CSV sources given (use --csv, --csv-group, and/or --csv-pattern).")

    return specs


def _scan_existing_runs(path: str) -> tuple[set, int, int]:
    """Scan an existing BLUT file's run headers (no signal data) and return
    ((run_id, corner_id) key set, next available run_number, file version).
    The key set is used by cmd_append_run to detect (run_id, corner_id)
    pair collisions — run_id alone is no longer the uniqueness key."""
    with open(path, "rb") as f:
        fh = bf.read_file_header(f, path)
        if fh.version != bf.VERSION:
            return set(), 0, fh.version
        run_keys = set()
        max_run_number = -1
        for _ in range(fh.n_runs):
            run = bf.read_run_meta(f, path, version=fh.version, load_signals=False)
            run_keys.add((run.run_id, run.corner_id))
            max_run_number = max(max_run_number, run.run_number)
    return run_keys, max_run_number + 1, fh.version


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="digitwin_blut_builder.py",
        description="digiTwin BLUT (v7) builder: CSV -> multi-run BLUT container.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("-v", "--verbose", action="store_true", help="Enable debug logging.")
    sub = p.add_subparsers(dest="command", required=True)

    def add_common_build_args(sp: argparse.ArgumentParser) -> None:
        sp.add_argument("--csv", action="append", default=[],
                         help="CSV file to ingest as one run. Repeat for multiple runs "
                              "(e.g. --csv a.csv --csv b.csv). May be combined with "
                              "--csv-group and --csv-pattern in the same invocation.")
        sp.add_argument("--csv-group", action="append", default=[],
                         help="Comma-separated list of >=2 CSV files to merge into ONE "
                              "run (e.g. --csv-group 'a.csv,b.csv,c.csv' --run-id merged). "
                              "All CSVs in a group must share an identical time grid "
                              "(see --allow-time-mismatch) and must not have colliding "
                              "signal names (see --on-signal-collision).")
        sp.add_argument("--csv-pattern", action="append", default=[],
                         help="Glob pattern matching one or more CSV files (e.g. "
                              "'corners/*.csv'). Zero matches is an error. If paired "
                              "with a --run-id, all matched files merge into ONE run "
                              "(same rules as --csv-group). If no --run-id is paired, "
                              "each matched file becomes its own auto-numbered run.")
        sp.add_argument("--run-id", action="append",
                         help="Run identifier, one per --csv/--csv-group/--csv-pattern "
                              "occurrence, in that concatenated order (all --csv first, "
                              "then all --csv-group, then all --csv-pattern). If omitted "
                              "entirely, run0/run1/... are auto-generated.")
        sp.add_argument("--run-meta", action="append",
                         help="Free-form metadata string, one per --csv/--csv-group/"
                              "--csv-pattern occurrence in the same concatenated order "
                              "(e.g. 'corner=ff,temp=125').")
        sp.add_argument("--corner-id", action="append",
                         help="PVT corner identifier (e.g. 'ff_125c_1p98v'), one per "
                              "--csv/--csv-group/--csv-pattern occurrence in the same "
                              "concatenated order as --run-id/--run-meta. This is a "
                              "second organizational axis orthogonal to --run-id: the "
                              "same run_id may repeat under different --corner-id "
                              "values (same stimulus swept across PVT corners), and the "
                              "same --corner-id may repeat under different run_id "
                              "values (different stimuli at the same corner). The "
                              "uniqueness key for a run within a container is the pair "
                              "(run_id, corner_id). If omitted entirely, corner_id='' "
                              "for all runs (identical to pre-v8 behavior).")
        sp.add_argument("--on-signal-collision", choices=["error", "last-wins"], default="error",
                         help="When merging multiple CSVs into one run (--csv-group or "
                              "a --run-id-paired --csv-pattern), how to handle the same "
                              "signal name appearing in more than one CSV. 'error' "
                              "(default): fail with the full list of collisions. "
                              "'last-wins': the last CSV (in group order) wins, with a "
                              "warning logged per collision.")
        sp.add_argument("--allow-time-mismatch", action="store_true",
                         help="When merging multiple CSVs into one run, allow CSVs whose "
                              "time grids differ from the group's first CSV (default: "
                              "hard error). If set, the first CSV's time grid is used "
                              "and later CSVs' rows are consumed positionally — this is "
                              "unsafe unless you know the grids are equivalent, since no "
                              "resampling is performed.")
        sp.add_argument("--workers", type=int, default=8,
                         help="Worker processes per run (parallelized across signals). Default: 8.")
        sp.add_argument("--mode", choices=["int32", "float32", "float64"], default="int32",
                         help="Storage encoding for quantized values. Default: int32.")
        qgroup = sp.add_mutually_exclusive_group()
        qgroup.add_argument("--qstep-abs", type=float, default=None,
                             help="Quantization step in absolute signal units (e.g. volts). "
                                  "Mutually exclusive with --qstep-rel.")
        qgroup.add_argument("--qstep-rel", type=float, default=None,
                             help="Quantization step as a fraction of each signal's "
                                  "(max-min) range (e.g. 1e-4). Mutually exclusive with --qstep-abs.")
        sp.add_argument("--compress", choices=["yes", "no"], default="yes",
                         help="zlib-compress each signal block. Default: yes.")
        sp.add_argument("--tol-abs", type=float, default=0.0,
                         help="Absolute transition tolerance (signal units) for delta/run-length "
                              "compression. 0 (default) stores every sample (exact mode).")
        sp.add_argument("--tol-rel", type=float, default=0.0,
                         help="Relative transition tolerance, as a fraction of each signal's "
                              "range. Combined with --tol-abs via max(). 0 (default) = exact mode.")

    p_create = sub.add_parser("create", help="Create a new multi-run BLUT from one or more CSVs.")
    add_common_build_args(p_create)
    p_create.add_argument("--out", required=True, help="Output BLUT path.")
    p_create.add_argument("--force", action="store_true", help="Overwrite --out if it already exists.")
    p_create.set_defaults(func=cmd_create)

    p_append = sub.add_parser("append-run", help="Append one or more new runs to an existing BLUT.")
    add_common_build_args(p_append)
    p_append.add_argument("--out", required=True, help="Existing BLUT path to append to.")
    p_append.add_argument("--force", action="store_true",
                           help="Allow appending a run_id that already exists in the file.")
    p_append.set_defaults(func=cmd_append_run)

    p_validate = sub.add_parser("validate", help="Report BLUT contents without loading signal data.")
    p_validate.add_argument("--out", required=True, help="BLUT path to inspect.")
    p_validate.set_defaults(func=cmd_validate)

    p_migrate = sub.add_parser("migrate-v6", help="Convert a v6 single-run BLUT into a v8 single-run container.")
    p_migrate.add_argument("--csv-equiv-blut", required=True, dest="csv_equiv_blut",
                            help="Path to the existing v6 BLUT (.bin) file to migrate.")
    p_migrate.add_argument("--out", required=True, help="Output v8 BLUT path.")
    p_migrate.add_argument("--run-id", default=None,
                            help="run_id to assign to the migrated run. Default: 'legacy_v6'.")
    p_migrate.set_defaults(func=cmd_migrate_v6)

    p_migrate_v7 = sub.add_parser(
        "migrate-v7",
        help="Convert a v7 multi-run BLUT into a v8 multi-run container, "
             "optionally extracting corner_id from each run's meta string.",
    )
    p_migrate_v7.add_argument("--blut-v7", required=True, dest="blut_v7",
                               help="Path to the existing v7 BLUT file to migrate.")
    p_migrate_v7.add_argument("--out", required=True, help="Output v8 BLUT path.")
    p_migrate_v7.add_argument(
        "--corner-from-meta", action="store_true",
        help="Extract corner_id from each run's meta string using the 'corner=X' "
             "key convention (see blut_format.corner_id_from_meta). Without this "
             "flag, all migrated runs get corner_id=''.",
    )
    p_migrate_v7.set_defaults(func=cmd_migrate_v7)

    p_export = sub.add_parser("export-v6", help="Export one run from a v7/v8 BLUT as a standalone v6 file.")
    p_export.add_argument("--out", required=True, help="Source v7/v8 BLUT path.")
    p_export.add_argument("--run-id", required=True, help="run_id of the run to export.")
    p_export.add_argument("--corner-id", default=None,
                           help="corner_id to disambiguate if run_id is not unique "
                                "(i.e. the same run_id appears under multiple corners). "
                                "Not required if the run_id is unique in the file.")
    p_export.add_argument("--export-path", required=True, help="Output v6 file path.")
    p_export.set_defaults(func=cmd_export_v6)

    return p


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    try:
        return args.func(args)
    except bf.BlutFormatError as e:
        log.error("BLUT format error: %s", e)
        return 1
    except (ValueError, FileNotFoundError) as e:
        log.error("%s", e)
        return 2
    except BrokenPipeError:
        # Output was piped to something like `head` that closed early.
        # Avoid a noisy traceback; suppress further writes to stdout.
        try:
            sys.stdout.close()
        except Exception:
            pass
        return 0
    except KeyboardInterrupt:
        log.warning("Interrupted.")
        return 130


if __name__ == "__main__":
    sys.exit(main())
