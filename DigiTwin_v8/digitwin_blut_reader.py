#!/usr/bin/env python3
"""
digitwin_blut_reader.py — digiTwin BLUT (v7) reader / plotter.

Reads run-aware BLUT containers (and legacy v6 single-run files) and plots
requested signals, with run-qualified signal access for multi-run files.

USAGE
-----
Single-run / single-file, plain signal names (legacy-style, still works):

  python3 digitwin_blut_reader.py --bluts psf_parallel.bin \\
      --signals top.u1.vref top.u2.vout --tmin 1e-6 --tmax 5e-6

Multi-run BLUT, select specific runs:

  python3 digitwin_blut_reader.py --bluts regression.blut \\
      --runs corner_ff_125c corner_ss_m40c \\
      --signals top.u1.vref top.u2.vout

Multi-run BLUT, run-qualified signal shorthand (one signal, one run each):

  python3 digitwin_blut_reader.py --bluts regression.blut \\
      --signals "top.u1.vref@corner_ff_125c" "top.u1.vref@corner_ss_m40c"

v8 run_id x corner_id matrix — explicit pair, run-only, and matrix forms:

  # Fully explicit (run_id, corner_id) pair per signal token:
  python3 digitwin_blut_reader.py --bluts regression.blut \\
      --signals "vout@startup_test@ff_125c" "vout@startup_test@tt_25c"

  # All corners for one run_id (only OK if run_id has exactly one corner,
  # OR --corners is given to disambiguate):
  python3 digitwin_blut_reader.py --bluts regression.blut \\
      --signals "vout@startup_test" --corners ff_125c tt_25c ss_m40c

  # Bare signal name across a run x corner matrix:
  python3 digitwin_blut_reader.py --bluts regression.blut \\
      --signals vout --runs startup_test load_transient --corners ff_125c tt_25c

List runs/signals in a file without plotting:

  python3 digitwin_blut_reader.py --bluts regression.blut --list

NOTES
-----
- If a BLUT has more than one run and a requested signal is not run-
  qualified (`name@run_id`) and `--runs` was not given, this tool errors
  out listing the available runs rather than guessing which one you meant.
  The same applies to corner_id: if a run_id has more than one corner and
  neither `name@run_id@corner_id` nor `--corners` disambiguates, this tool
  errors out listing the available corners for that run_id.
- Legend entries are "<signal> [<run_id>/<corner_id>] (<file basename>)"
  when corner_id is non-empty, or "<signal> [<run_id>] (<file basename>)"
  when corner_id is empty (backward-compatible legend for files that never
  used --corner-id) — so overlays across runs, corners, and files stay
  distinguishable.
- Reconstruction uses zero-order hold (forward-fill) between stored
  transition points, which is correct regardless of compression ratio.
  See BLUT_FORMAT.md sec 2 for why the original implementation's
  zero-fill was a bug.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from dataclasses import dataclass
from typing import Optional

import numpy as np

import blut_format as bf

log = logging.getLogger("digitwin.reader")


# ---------------------------------------------------------------------------
# File-level read API
# ---------------------------------------------------------------------------

@dataclass
class BlutFile:
    path: str
    version: int
    runs: dict  # run_id -> {corner_id -> RunMeta}
    # DESIGN DECISION (v8 corner_id support): nested dict, not a flat
    # dict[(run_id, corner_id)] and not a separate reverse index.
    #
    # The two dominant access patterns are:
    #   (1) "all corners for a given run_id"     -> runs[run_id].values()
    #   (2) "the single run at (run_id, corner)"  -> runs[run_id][corner_id]
    # Both are O(1) dict access with the nested-dict shape. A flat
    # dict[(run_id, corner_id)] key would make (2) equally O(1) but turns
    # (1) into "scan all keys and filter on key[0]" — slower AND less
    # readable than runs[run_id].values().
    #
    # The reverse axis, "all run_ids at a given corner_id", is O(n_runs)
    # under the nested-dict shape (iterate run_ids, check membership in
    # each corner_map) — same asymptotic cost a flat-dict-with-filter or a
    # dedicated reverse index would give for the *forward* pattern, just
    # moved to whichever axis isn't the primary key. Since realistic BLUT
    # containers hold tens to low hundreds of runs (not millions), this
    # O(n_runs) scan is not a real performance concern, so it isn't worth
    # maintaining a second index purely for symmetry.
    #
    # This shape also degenerates cleanly for the common single-corner
    # (or no-corner-context) case: a file with no --corner-id ever used
    # has every run under corner_id="", so runs[run_id][""] is exactly the
    # old runs[run_id] behavior, with no special-casing required anywhere
    # that already assumed one run per run_id.


def open_blut(path: str) -> BlutFile:
    """Read all run/signal *headers* (not blob payloads) for a file. Cheap;
    safe to call before deciding which signals to actually decode."""
    if not os.path.exists(path):
        raise FileNotFoundError(path)

    with open(path, "rb") as f:
        fh = bf.read_file_header(f, path)
        runs: dict = {}

        if fh.version == bf.VERSION_V6:
            run = bf.read_v6_as_run(f, path, load_signals=False)
            runs.setdefault(run.run_id, {})[run.corner_id] = run
            return BlutFile(path=path, version=fh.version, runs=runs)

        for _ in range(fh.n_runs):
            run = bf.read_run_meta(f, path, version=fh.version, load_signals=False)
            corner_map = runs.setdefault(run.run_id, {})
            if run.corner_id in corner_map:
                log.warning(
                    "%s: duplicate (run_id=%r, corner_id=%r) at run_number=%d "
                    "(previous run_number=%d) — both are accessible by "
                    "run_number-qualified lookup, but plain (run_id, corner_id) "
                    "lookup will resolve to the last one read.",
                    path, run.run_id, run.corner_id, run.run_number,
                    corner_map[run.corner_id].run_number,
                )
            corner_map[run.corner_id] = run

    return BlutFile(path=path, version=fh.version, runs=runs)


def load_signal_blob(path: str, run: bf.RunMeta, sig_name: str) -> bytes:
    """Seek directly to one signal's blob and read just that block, using
    the byte offset captured when headers were scanned. O(1) re-read, not
    a re-scan of the whole run."""
    sig = run.signals.get(sig_name)
    if sig is None:
        raise KeyError(f"Signal '{sig_name}' not found in run '{run.run_id}' ({path})")
    if sig.blob is not None:
        return sig.blob

    with open(path, "rb") as f:
        f.seek(sig.file_offset)
        loaded = bf.read_signal_block_meta(f, path, load_blob=True)
    sig.blob = loaded.blob
    return sig.blob


def decode(path: str, run: bf.RunMeta, sig_name: str) -> np.ndarray:
    sig = run.signals.get(sig_name)
    if sig is None:
        raise KeyError(f"Signal '{sig_name}' not found in run '{run.run_id}' ({path})")
    blob = load_signal_blob(path, run, sig_name)
    return bf.decode_signal(sig, run.ntime, blob=blob)


# ---------------------------------------------------------------------------
# Run-qualified signal name resolution
# ---------------------------------------------------------------------------

@dataclass
class ResolvedRequest:
    blut_path: str
    run_id: str
    corner_id: str
    signal_name: str


def parse_signal_token(token: str) -> tuple[str, Optional[str], Optional[str]]:
    """Split a signal token into (name, run_id, corner_id).

    Supported forms:
      'name'                       -> (name, None, None)
      'name@run_id'                -> (name, run_id, None)
      'name@run_id@corner_id'      -> (name, run_id, corner_id)

    Uses rsplit (from the right) rather than a forward split, so that if a
    signal name itself happens to contain '@' (unusual in EDA naming but
    not forbidden), the rightmost one or two '@'-delimited segments are
    still correctly interpreted as (run_id) or (run_id, corner_id) — the
    same principle the original single-'@' design already relied on.
    """
    n_at = token.count("@")
    if n_at == 0:
        return token, None, None
    if n_at == 1:
        name, run_id = token.rsplit("@", 1)
        return name, run_id, None
    if n_at == 2:
        name, run_id, corner_id = token.rsplit("@", 2)
        return name, run_id, corner_id
    raise ValueError(
        f"Signal token {token!r} has too many '@' segments (expected at most "
        f"'name@run_id@corner_id', i.e. 2 '@' characters)."
    )


def resolve_requests(
    blut: BlutFile,
    signal_tokens: list[str],
    requested_runs: Optional[list[str]],
    requested_corners: Optional[list[str]] = None,
) -> list[ResolvedRequest]:
    """Expand (file, signal tokens, --runs, --corners) into concrete
    (run_id, corner_id, signal) triples.

    Resolution rules (v8, run_id x corner_id matrix):
      - 'name@run_id@corner_id' is always fully explicit.
      - 'name@run_id' (no corner_id in the token):
          - if --corners is given, use those corner_id(s) for this run_id.
          - elif run_id has exactly one corner in the file, use it
            (unchanged behavior for files that never used --corner-id).
          - else: error, listing the available corners for that run_id.
      - bare 'name' + --runs given (+ optional --corners): for each run_id
        in --runs, resolve corners the same way as the 'name@run_id' case
        above (using --corners if given, else the single corner or error).
      - bare 'name' + no --runs: only OK if the whole file has exactly one
        (run_id, corner_id) pair; otherwise error listing all pairs.
    """
    available_runs = list(blut.runs.keys())
    resolved: list[ResolvedRequest] = []

    def _corner_map_for(run_id: str, token: str) -> dict:
        if run_id not in blut.runs:
            raise KeyError(
                f"{blut.path}: run_id '{run_id}' not found (requested via '{token}'). "
                f"Available runs: {available_runs}"
            )
        return blut.runs[run_id]

    def _corners_to_use(run_id: str, corner_map: dict, token: str) -> list[str]:
        """Decide which corner_id(s) apply for a run_id-qualified (but not
        corner-qualified) request, per the rules above."""
        if requested_corners:
            return requested_corners
        if len(corner_map) == 1:
            return list(corner_map.keys())
        raise ValueError(
            f"{blut.path}: '{token}' is not corner-qualified and run_id "
            f"'{run_id}' has {len(corner_map)} corners ({sorted(corner_map.keys())}). "
            f"Use 'name@run_id@corner_id', or pass --corners to select which "
            f"corner(s)."
        )

    for token in signal_tokens:
        name, explicit_run, explicit_corner = parse_signal_token(token)

        if explicit_run is not None and explicit_corner is not None:
            # Fully explicit (run_id, corner_id) pair.
            corner_map = _corner_map_for(explicit_run, token)
            if explicit_corner not in corner_map:
                raise KeyError(
                    f"{blut.path}: corner_id '{explicit_corner}' not found for run_id "
                    f"'{explicit_run}' (requested via '{token}'). Available corners "
                    f"for this run_id: {sorted(corner_map.keys())}"
                )
            run = corner_map[explicit_corner]
            if name not in run.signals:
                raise KeyError(
                    f"{blut.path}: signal '{name}' not found in run_id '{explicit_run}' "
                    f"corner_id '{explicit_corner}'. Available signals: "
                    f"{sorted(run.signals.keys())}"
                )
            resolved.append(ResolvedRequest(blut.path, explicit_run, explicit_corner, name))
            continue

        if explicit_run is not None:
            # run_id given, corner_id not -> resolve per _corners_to_use().
            corner_map = _corner_map_for(explicit_run, token)
            for cid in _corners_to_use(explicit_run, corner_map, token):
                if cid not in corner_map:
                    log.warning(
                        "%s: corner_id '%s' not present for run_id '%s' — skipping.",
                        blut.path, cid, explicit_run,
                    )
                    continue
                run = corner_map[cid]
                if name not in run.signals:
                    log.warning(
                        "%s: signal '%s' not present in run '%s'/'%s' — skipping.",
                        blut.path, name, explicit_run, cid,
                    )
                    continue
                resolved.append(ResolvedRequest(blut.path, explicit_run, cid, name))
            continue

        # Bare signal name (no '@' at all in the token).
        if requested_runs:
            for run_id in requested_runs:
                corner_map = _corner_map_for(run_id, token)
                for cid in _corners_to_use(run_id, corner_map, token):
                    if cid not in corner_map:
                        log.warning(
                            "%s: corner_id '%s' not present for run_id '%s' — skipping.",
                            blut.path, cid, run_id,
                        )
                        continue
                    run = corner_map[cid]
                    if name not in run.signals:
                        log.warning(
                            "%s: signal '%s' not present in run '%s'/'%s' — skipping.",
                            blut.path, name, run_id, cid,
                        )
                        continue
                    resolved.append(ResolvedRequest(blut.path, run_id, cid, name))
            continue

        # Bare name, no --runs, no --corners: only OK if the whole file has
        # exactly one (run_id, corner_id) pair.
        all_pairs = [
            (rid, cid) for rid, cmap in blut.runs.items() for cid in cmap.keys()
        ]
        if len(all_pairs) == 1:
            only_run_id, only_corner_id = all_pairs[0]
            run = blut.runs[only_run_id][only_corner_id]
            if name not in run.signals:
                raise KeyError(
                    f"{blut.path}: signal '{name}' not found. "
                    f"Available signals: {sorted(run.signals.keys())}"
                )
            resolved.append(ResolvedRequest(blut.path, only_run_id, only_corner_id, name))
        else:
            raise ValueError(
                f"{blut.path}: signal '{name}' is not run/corner-qualified and this "
                f"file has {len(all_pairs)} (run_id, corner_id) pairs: {all_pairs}. "
                f"Use 'name@run_id@corner_id', or pass --runs/--corners to select "
                f"which run(s)/corner(s) to plot bare signal names from."
            )

    return resolved


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_list(args: argparse.Namespace) -> int:
    for path in args.bluts:
        blut = open_blut(path)
        print(f"File:    {path}")
        print(f"Version: {blut.version}")
        n_total_runs = sum(len(corner_map) for corner_map in blut.runs.values())
        print(f"Runs:    {n_total_runs}")
        for run_id, corner_map in blut.runs.items():
            for corner_id, run in corner_map.items():
                span = f"[{run.times[0]:.6g}, {run.times[-1]:.6g}]" if run.ntime else "[]"
                corner_str = f" corner_id={corner_id!r}" if corner_id else ""
                print(f"  - run_id={run_id!r}{corner_str} run_number={run.run_number} "
                      f"ntime={run.ntime} time_span={span} meta={run.meta!r}")
                for name in sorted(run.signals):
                    print(f"    - {name}")
        print()
    return 0


def cmd_plot(args: argparse.Namespace) -> int:
    import matplotlib.pyplot as plt

    any_plotted = False
    for path in args.bluts:
        blut = open_blut(path)
        try:
            requests = resolve_requests(blut, args.signals, args.runs, args.corners)
        except (KeyError, ValueError) as e:
            log.error("%s", e)
            return 2

        for req in requests:
            run = blut.runs[req.run_id][req.corner_id]
            try:
                full = decode(req.blut_path, run, req.signal_name)
            except bf.BlutFormatError as e:
                log.error("Failed to decode %s@%s@%s in %s: %s",
                          req.signal_name, req.run_id, req.corner_id, path, e)
                continue

            t = run.times
            mask = np.ones(len(t), dtype=bool)
            if args.tmin is not None:
                mask &= t >= args.tmin
            if args.tmax is not None:
                mask &= t <= args.tmax

            if req.corner_id:
                label = f"{req.signal_name} [{req.run_id}/{req.corner_id}] ({os.path.basename(path)})"
            else:
                label = f"{req.signal_name} [{req.run_id}] ({os.path.basename(path)})"
            plt.plot(t[mask], full[mask], label=label)
            any_plotted = True
            log.info("Plotted %s", label)

    if not any_plotted:
        log.error("Nothing was plotted (no matching signals resolved).")
        return 1

    plt.legend()
    plt.xlabel("Time (s)")
    plt.ylabel("Value")
    plt.grid(True)
    if args.save:
        plt.savefig(args.save, dpi=150, bbox_inches="tight")
        log.info("Saved plot to %s", args.save)
    if not args.no_show:
        plt.show()
    return 0


# ---------------------------------------------------------------------------
# CLI plumbing
# ---------------------------------------------------------------------------

def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="digitwin_blut_reader.py",
        description="digiTwin BLUT (v7) reader / plotter, with run-aware multi-run support.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("-v", "--verbose", action="store_true", help="Enable debug logging.")
    p.add_argument("--bluts", nargs="+", required=True,
                    help="One or more BLUT files to read (v7 multi-run or legacy v6).")
    p.add_argument("--signals", nargs="+",
                    help="Signal names to plot. Use 'name@run_id' to qualify which run "
                         "a signal comes from. Required unless --list is given.")
    p.add_argument("--runs", nargs="+", default=None,
                    help="Run id(s) to select for bare (unqualified) signal names, or "
                         "for 'name@run_id' tokens that are ambiguous across corners. "
                         "Required if a file has more than one run_id and --signals "
                         "contains unqualified names.")
    p.add_argument("--corners", nargs="+", default=None,
                    help="Corner id(s) to select when a run_id has multiple corners "
                         "and the signal token does not specify one. Used alongside "
                         "--runs for bare signal names, or with 'name@run_id' tokens "
                         "that are ambiguous across corners. Not needed for "
                         "'name@run_id@corner_id' (fully explicit) or for files where "
                         "every run_id has exactly one corner.")
    p.add_argument("--tmin", type=float, default=None, help="Lower time bound (inclusive).")
    p.add_argument("--tmax", type=float, default=None, help="Upper time bound (inclusive).")
    p.add_argument("--list", action="store_true",
                    help="List runs and signals in each file, then exit (no plotting).")
    p.add_argument("--save", default=None, help="Save the plot to this path instead of/as well as showing it.")
    p.add_argument("--no-show", action="store_true", help="Don't open an interactive plot window.")
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
        if args.list:
            return cmd_list(args)

        if not args.signals:
            parser.error("--signals is required unless --list is given")

        return cmd_plot(args)
    except bf.BlutFormatError as e:
        log.error("BLUT format error: %s", e)
        return 1
    except FileNotFoundError as e:
        log.error("File not found: %s", e)
        return 2
    except BrokenPipeError:
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
