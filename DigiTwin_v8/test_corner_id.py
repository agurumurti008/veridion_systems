#!/usr/bin/env python3
"""
test_corner_id.py — pytest coverage for the v8 corner_id extension:
(run_id, corner_id) pair uniqueness, corner-qualified signal token
resolution, the --corners reader filter, v7 backward-compat reads with
corner_id="" default, and the migrate-v7 subcommand.

Run with:
    uv run pytest test_corner_id.py -v

These tests exercise digitwin_blut_builder.py, digitwin_blut_reader.py,
and blut_format.py both as a black box (CLI subprocess calls) and as a
white box (direct function calls for binary-layout-sensitive checks like
v7 backward compatibility, where hand-constructing a v7-layout file is the
only way to test the legacy read path without a real archived v7 fixture).
"""

from __future__ import annotations

import struct
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import blut_format as bf
import digitwin_blut_builder as builder
import digitwin_blut_reader as reader

BUILDER = str(Path(__file__).parent / "digitwin_blut_builder.py")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def matrix_csv_dir(tmp_path: Path) -> Path:
    """3 stimuli x 3 corners = 9 CSVs, all sharing one time grid, for
    building a full run_id x corner_id regression matrix."""
    t = np.linspace(0, 1e-6, 20)
    stimuli = {"startup": 1.0, "load": 2.0, "psrr": 3.0}
    corners = {"ff_125c": 0.1, "tt_25c": 0.2, "ss_m40c": 0.3}
    for stim, sval in stimuli.items():
        for corner, cval in corners.items():
            pd.DataFrame({"time": t, "vout": np.full_like(t, sval + cval)}).to_csv(
                tmp_path / f"{stim}_{corner}.csv", index=False
            )
    return tmp_path


def run_cli(*args: str, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, BUILDER, *args], cwd=str(cwd), capture_output=True, text=True,
    )


def build_matrix(csv_dir: Path, out: Path) -> subprocess.CompletedProcess:
    """Build the standard 3x3 (run_id, corner_id) matrix via the CLI."""
    return run_cli(
        "create", "--out", str(out),
        "--csv", "startup_ff_125c.csv", "--run-id", "startup_test", "--corner-id", "ff_125c",
        "--csv", "startup_tt_25c.csv", "--run-id", "startup_test", "--corner-id", "tt_25c",
        "--csv", "startup_ss_m40c.csv", "--run-id", "startup_test", "--corner-id", "ss_m40c",
        "--csv", "load_ff_125c.csv", "--run-id", "load_transient", "--corner-id", "ff_125c",
        "--csv", "load_tt_25c.csv", "--run-id", "load_transient", "--corner-id", "tt_25c",
        "--csv", "load_ss_m40c.csv", "--run-id", "load_transient", "--corner-id", "ss_m40c",
        "--csv", "psrr_ff_125c.csv", "--run-id", "psrr_sweep", "--corner-id", "ff_125c",
        "--csv", "psrr_tt_25c.csv", "--run-id", "psrr_sweep", "--corner-id", "tt_25c",
        "--csv", "psrr_ss_m40c.csv", "--run-id", "psrr_sweep", "--corner-id", "ss_m40c",
        "--force", "--workers", "1",
        cwd=csv_dir,
    )


def _write_v7_run_header(f, run_number: int, run_id: str, meta: str, times: np.ndarray) -> None:
    """Hand-construct a v7-layout run header (no corner_id field at all —
    this is the OLD layout, byte-for-byte, used to build a genuine v7
    fixture file so the v7-compat read path in blut_format.py can be
    tested without depending on an archived v7 binary."""
    run_id_b = run_id.encode("utf-8")
    meta_b = meta.encode("utf-8")
    f.write(bf.RUN_MARKER)
    f.write(struct.pack("<I", run_number))
    f.write(struct.pack("<I", 0))  # n_signals placeholder
    f.write(struct.pack("<I", len(times)))
    f.write(struct.pack("<HH", len(run_id_b), len(meta_b)))
    f.write(run_id_b)
    f.write(meta_b)
    bf.write_pad8(f)
    f.write(np.ascontiguousarray(times, dtype=np.float64).tobytes())
    bf.write_pad8(f)


def make_v7_fixture(path: Path, runs: list[tuple[str, str]]) -> None:
    """Write a genuine v7-format BLUT file (magic, version=7, n_runs, flags,
    then v7-layout run headers) with one signal 'vout' per run.

    runs: list of (run_id, meta) tuples.
    """
    t = np.linspace(0, 1e-6, 10)
    idxs = np.array([0, 5, 9])
    vals = np.array([1.0, 2.0, 3.0])

    with open(path, "wb") as f:
        f.write(bf.MAGIC)
        f.write(struct.pack("<I", bf.VERSION_V7))
        f.write(struct.pack("<I", len(runs)))
        f.write(struct.pack("<I", 0))  # flags
        for i, (run_id, meta) in enumerate(runs):
            off = f.tell()
            _write_v7_run_header(f, i, run_id, meta, t)
            bf.write_signal_block(f, "vout", idxs, vals, bf.ENC_FLOAT64, 0.0, 1.0, compress=True)
            bf.patch_run_n_signals(f, off, 1)


# ---------------------------------------------------------------------------
# (a) (run_id, corner_id) pair uniqueness enforcement in builder
# ---------------------------------------------------------------------------

class TestPairUniqueness:
    def test_exact_duplicate_pair_errors(self, matrix_csv_dir: Path):
        out = matrix_csv_dir / "dup.blut"
        r = run_cli(
            "create", "--out", str(out),
            "--csv", "startup_ff_125c.csv", "--run-id", "startup_test", "--corner-id", "ff_125c",
            "--csv", "startup_tt_25c.csv", "--run-id", "startup_test", "--corner-id", "ff_125c",
            "--force", "--workers", "1",
            cwd=matrix_csv_dir,
        )
        assert r.returncode != 0
        assert "Duplicate (run_id, corner_id) pair" in r.stderr
        assert not out.exists()

    def test_same_run_id_different_corner_id_accepted(self, matrix_csv_dir: Path):
        out = matrix_csv_dir / "ok.blut"
        r = run_cli(
            "create", "--out", str(out),
            "--csv", "startup_ff_125c.csv", "--run-id", "startup_test", "--corner-id", "ff_125c",
            "--csv", "startup_tt_25c.csv", "--run-id", "startup_test", "--corner-id", "tt_25c",
            "--force", "--workers", "1",
            cwd=matrix_csv_dir,
        )
        assert r.returncode == 0, r.stderr
        with open(out, "rb") as f:
            fh = bf.read_file_header(f, str(out))
            assert fh.n_runs == 2
            pairs = set()
            for _ in range(fh.n_runs):
                run = bf.read_run_meta(f, str(out), version=fh.version, load_signals=False)
                pairs.add((run.run_id, run.corner_id))
        assert pairs == {("startup_test", "ff_125c"), ("startup_test", "tt_25c")}

    def test_same_corner_id_different_run_id_accepted(self, matrix_csv_dir: Path):
        out = matrix_csv_dir / "ok2.blut"
        r = run_cli(
            "create", "--out", str(out),
            "--csv", "startup_ff_125c.csv", "--run-id", "startup_test", "--corner-id", "ff_125c",
            "--csv", "load_ff_125c.csv", "--run-id", "load_transient", "--corner-id", "ff_125c",
            "--force", "--workers", "1",
            cwd=matrix_csv_dir,
        )
        assert r.returncode == 0, r.stderr

    def test_full_3x3_matrix_builds_9_runs(self, matrix_csv_dir: Path):
        out = matrix_csv_dir / "matrix.blut"
        r = build_matrix(matrix_csv_dir, out)
        assert r.returncode == 0, r.stderr
        with open(out, "rb") as f:
            fh = bf.read_file_header(f, str(out))
            assert fh.version == bf.VERSION
            assert fh.n_runs == 9
            pairs = set()
            for _ in range(fh.n_runs):
                run = bf.read_run_meta(f, str(out), version=fh.version, load_signals=False)
                pairs.add((run.run_id, run.corner_id))
        expected = {
            (rid, cid)
            for rid in ("startup_test", "load_transient", "psrr_sweep")
            for cid in ("ff_125c", "tt_25c", "ss_m40c")
        }
        assert pairs == expected


# ---------------------------------------------------------------------------
# (b) same run_id / different corner_id across append-run
# ---------------------------------------------------------------------------

class TestAppendRunAcrossCorners:
    def test_append_new_corner_for_existing_run_id_succeeds(self, matrix_csv_dir: Path):
        out = matrix_csv_dir / "base.blut"
        r1 = run_cli(
            "create", "--out", str(out),
            "--csv", "startup_ff_125c.csv", "--run-id", "startup_test", "--corner-id", "ff_125c",
            "--force", "--workers", "1",
            cwd=matrix_csv_dir,
        )
        assert r1.returncode == 0, r1.stderr

        r2 = run_cli(
            "append-run", "--out", str(out),
            "--csv", "startup_tt_25c.csv", "--run-id", "startup_test", "--corner-id", "tt_25c",
            "--workers", "1",
            cwd=matrix_csv_dir,
        )
        assert r2.returncode == 0, r2.stderr

        with open(out, "rb") as f:
            fh = bf.read_file_header(f, str(out))
            assert fh.n_runs == 2

    def test_append_existing_pair_blocked(self, matrix_csv_dir: Path):
        out = matrix_csv_dir / "base2.blut"
        r1 = run_cli(
            "create", "--out", str(out),
            "--csv", "startup_ff_125c.csv", "--run-id", "startup_test", "--corner-id", "ff_125c",
            "--force", "--workers", "1",
            cwd=matrix_csv_dir,
        )
        assert r1.returncode == 0, r1.stderr

        r2 = run_cli(
            "append-run", "--out", str(out),
            "--csv", "startup_tt_25c.csv", "--run-id", "startup_test", "--corner-id", "ff_125c",
            "--workers", "1",
            cwd=matrix_csv_dir,
        )
        assert r2.returncode != 0
        assert "already present" in r2.stderr
        with open(out, "rb") as f:
            fh = bf.read_file_header(f, str(out))
            assert fh.n_runs == 1  # unchanged


# ---------------------------------------------------------------------------
# (c) "sig@run_id@corner_id" signal token parsing
# ---------------------------------------------------------------------------

class TestTokenParsing:
    def test_bare_name(self):
        assert reader.parse_signal_token("vout") == ("vout", None, None)

    def test_name_at_run(self):
        assert reader.parse_signal_token("vout@startup_test") == ("vout", "startup_test", None)

    def test_name_at_run_at_corner(self):
        assert reader.parse_signal_token("vout@startup_test@ff_125c") == (
            "vout", "startup_test", "ff_125c",
        )

    def test_too_many_at_segments_raises(self):
        with pytest.raises(ValueError, match="too many '@' segments"):
            reader.parse_signal_token("vout@run@corner@extra")

    def test_resolve_explicit_pair(self, matrix_csv_dir: Path):
        out = matrix_csv_dir / "matrix.blut"
        build_matrix(matrix_csv_dir, out)
        blut = reader.open_blut(str(out))
        resolved = reader.resolve_requests(blut, ["vout@startup_test@ff_125c"], None, None)
        assert len(resolved) == 1
        assert resolved[0].run_id == "startup_test"
        assert resolved[0].corner_id == "ff_125c"

    def test_resolve_ambiguous_run_without_corner_errors(self, matrix_csv_dir: Path):
        out = matrix_csv_dir / "matrix.blut"
        build_matrix(matrix_csv_dir, out)
        blut = reader.open_blut(str(out))
        with pytest.raises(ValueError, match="is not corner-qualified"):
            reader.resolve_requests(blut, ["vout@startup_test"], None, None)


# ---------------------------------------------------------------------------
# (d) --corners filter in reader
# ---------------------------------------------------------------------------

class TestCornersFilter:
    def test_run_qualified_with_corners_filter(self, matrix_csv_dir: Path):
        out = matrix_csv_dir / "matrix.blut"
        build_matrix(matrix_csv_dir, out)
        blut = reader.open_blut(str(out))
        resolved = reader.resolve_requests(
            blut, ["vout@startup_test"], None, ["ff_125c", "tt_25c"]
        )
        pairs = {(r.run_id, r.corner_id) for r in resolved}
        assert pairs == {("startup_test", "ff_125c"), ("startup_test", "tt_25c")}

    def test_bare_name_with_runs_and_corners_matrix(self, matrix_csv_dir: Path):
        out = matrix_csv_dir / "matrix.blut"
        build_matrix(matrix_csv_dir, out)
        blut = reader.open_blut(str(out))
        resolved = reader.resolve_requests(
            blut, ["vout"], ["startup_test", "load_transient"], ["ff_125c", "tt_25c"]
        )
        pairs = {(r.run_id, r.corner_id) for r in resolved}
        assert pairs == {
            ("startup_test", "ff_125c"), ("startup_test", "tt_25c"),
            ("load_transient", "ff_125c"), ("load_transient", "tt_25c"),
        }

    def test_cli_list_shows_all_corners(self, matrix_csv_dir: Path):
        out = matrix_csv_dir / "matrix.blut"
        build_matrix(matrix_csv_dir, out)
        r = subprocess.run(
            [sys.executable, str(Path(__file__).parent / "digitwin_blut_reader.py"),
             "--bluts", str(out), "--list"],
            capture_output=True, text=True,
        )
        assert r.returncode == 0, r.stderr
        assert "corner_id='ff_125c'" in r.stdout
        assert "corner_id='tt_25c'" in r.stdout
        assert "corner_id='ss_m40c'" in r.stdout

    def test_decode_through_nested_structure(self, matrix_csv_dir: Path):
        out = matrix_csv_dir / "matrix.blut"
        build_matrix(matrix_csv_dir, out)
        blut = reader.open_blut(str(out))
        run = blut.runs["startup_test"]["ff_125c"]
        full = reader.decode(str(out), run, "vout")
        assert full.shape == (20,)
        assert np.allclose(full, 1.1)  # startup(1.0) + ff_125c(0.1)


# ---------------------------------------------------------------------------
# (e) v7 file read-back with corner_id="" default
# ---------------------------------------------------------------------------

class TestV7BackwardCompat:
    def test_v7_run_reads_with_empty_corner_id(self, tmp_path: Path):
        v7_path = tmp_path / "legacy.blut"
        make_v7_fixture(v7_path, [("corner_ff_125c", "corner=ff,temp=125")])

        with open(v7_path, "rb") as f:
            fh = bf.read_file_header(f, str(v7_path))
            assert fh.version == bf.VERSION_V7
            run = bf.read_run_meta(f, str(v7_path), version=fh.version, load_signals=True)

        assert run.run_id == "corner_ff_125c"
        assert run.corner_id == ""  # v7 never had this field; must default cleanly
        assert run.meta == "corner=ff,temp=125"
        assert "vout" in run.signals

    def test_v7_file_readable_via_reader_open_blut(self, tmp_path: Path):
        v7_path = tmp_path / "legacy2.blut"
        make_v7_fixture(v7_path, [("run_a", ""), ("run_b", "")])

        blut = reader.open_blut(str(v7_path))
        assert blut.version == bf.VERSION_V7
        assert set(blut.runs.keys()) == {"run_a", "run_b"}
        assert list(blut.runs["run_a"].keys()) == [""]  # single empty-corner entry

    def test_v7_file_via_cli_validate(self, tmp_path: Path):
        v7_path = tmp_path / "legacy3.blut"
        make_v7_fixture(v7_path, [("corner_tt", "corner=tt")])
        r = run_cli("validate", "--out", str(v7_path), cwd=tmp_path)
        assert r.returncode == 0, r.stderr
        assert "Version: 7" in r.stdout
        assert "run_id='corner_tt'" in r.stdout
        # corner_id='' must NOT be printed (empty corner suppressed in summary)
        assert "corner_id=" not in r.stdout

    def test_corner_id_from_meta_extraction(self):
        assert bf.corner_id_from_meta("corner=ff,temp=125") == "ff"
        assert bf.corner_id_from_meta("temp=125,corner=ss") == "ss"
        assert bf.corner_id_from_meta("no_corner_key=here") == ""
        assert bf.corner_id_from_meta("") == ""


# ---------------------------------------------------------------------------
# (f) migrate-v7 subcommand, with and without --corner-from-meta
# ---------------------------------------------------------------------------

class TestMigrateV7:
    def test_migrate_without_corner_from_meta(self, tmp_path: Path):
        v7_path = tmp_path / "src.blut"
        make_v7_fixture(v7_path, [
            ("corner_ff_125c", "corner=ff,temp=125"),
            ("corner_ss_m40c", "corner=ss,temp=-40"),
        ])
        out = tmp_path / "migrated.blut"
        r = run_cli("migrate-v7", "--blut-v7", str(v7_path), "--out", str(out), cwd=tmp_path)
        assert r.returncode == 0, r.stderr

        with open(out, "rb") as f:
            fh = bf.read_file_header(f, str(out))
            assert fh.version == bf.VERSION
            assert fh.n_runs == 2
            for _ in range(fh.n_runs):
                run = bf.read_run_meta(f, str(out), version=fh.version, load_signals=False)
                assert run.corner_id == ""  # no --corner-from-meta -> all empty

    def test_migrate_with_corner_from_meta(self, tmp_path: Path):
        v7_path = tmp_path / "src2.blut"
        make_v7_fixture(v7_path, [
            ("corner_ff_125c", "corner=ff,temp=125"),
            ("corner_ss_m40c", "corner=ss,temp=-40"),
        ])
        out = tmp_path / "migrated2.blut"
        r = run_cli(
            "migrate-v7", "--blut-v7", str(v7_path), "--out", str(out),
            "--corner-from-meta", cwd=tmp_path,
        )
        assert r.returncode == 0, r.stderr

        with open(out, "rb") as f:
            fh = bf.read_file_header(f, str(out))
            assert fh.version == bf.VERSION
            corner_map = {}
            for _ in range(fh.n_runs):
                run = bf.read_run_meta(f, str(out), version=fh.version, load_signals=False)
                corner_map[run.run_id] = run.corner_id
        assert corner_map == {"corner_ff_125c": "ff", "corner_ss_m40c": "ss"}

    def test_migrate_v7_rejects_non_v7_input(self, tmp_path: Path):
        # Feed it a v6 file (wrong version for migrate-v7).
        v6_path = tmp_path / "v6file.bin"
        # Build a trivial v6 file directly.
        t = np.linspace(0, 1e-6, 5)
        idxs = np.array([0, 4])
        vals = np.array([1.0, 2.0])
        with open(v6_path, "wb") as f:
            f.write(bf.MAGIC)
            f.write(struct.pack("<I", bf.VERSION_V6))
            f.write(struct.pack("<I", 1))  # nsig
            f.write(struct.pack("<I", len(t)))  # ntime
            f.write(np.ascontiguousarray(t, dtype=np.float64).tobytes())
            bf.write_pad8(f)
            bf.write_signal_block(f, "vout", idxs, vals, bf.ENC_FLOAT64, 0.0, 1.0, compress=True)

        out = tmp_path / "should_fail.blut"
        r = run_cli("migrate-v7", "--blut-v7", str(v6_path), "--out", str(out), cwd=tmp_path)
        assert r.returncode != 0
        assert "not a v7 BLUT file" in r.stderr

    def test_migrated_file_round_trips_signal_data(self, tmp_path: Path):
        """Signal data (idxs/vals) must survive migrate-v7 byte-identically,
        not just the run headers."""
        v7_path = tmp_path / "src3.blut"
        make_v7_fixture(v7_path, [("run_x", "corner=tt")])
        out = tmp_path / "migrated3.blut"
        r = run_cli(
            "migrate-v7", "--blut-v7", str(v7_path), "--out", str(out),
            "--corner-from-meta", cwd=tmp_path,
        )
        assert r.returncode == 0, r.stderr

        with open(out, "rb") as f:
            fh = bf.read_file_header(f, str(out))
            run = bf.read_run_meta(f, str(out), version=fh.version, load_signals=True)
        decoded = bf.decode_signal(run.signals["vout"], run.ntime)
        # Original fixture used idxs=[0,5,9], vals=[1.0,2.0,3.0] with ZOH.
        assert decoded[0] == 1.0
        assert decoded[5] == 2.0
        assert decoded[9] == 3.0


# ---------------------------------------------------------------------------
# Regression: existing run_id-only usage (no --corner-id) still works
# ---------------------------------------------------------------------------

class TestExistingBehaviorUnaffected:
    def test_plain_csv_run_id_no_corner_id(self, matrix_csv_dir: Path):
        """The pre-v8 CLI pattern (--csv, --run-id, no --corner-id) must
        behave identically: corner_id defaults to "" everywhere, and
        uniqueness reduces to run_id alone since all corner_id values are
        the same empty string."""
        out = matrix_csv_dir / "plain.blut"
        r = run_cli(
            "create", "--out", str(out),
            "--csv", "startup_ff_125c.csv", "--run-id", "solo",
            "--force", "--workers", "1",
            cwd=matrix_csv_dir,
        )
        assert r.returncode == 0, r.stderr
        with open(out, "rb") as f:
            fh = bf.read_file_header(f, str(out))
            run = bf.read_run_meta(f, str(out), version=fh.version, load_signals=False)
        assert run.run_id == "solo"
        assert run.corner_id == ""

    def test_duplicate_run_id_no_corner_still_blocked(self, matrix_csv_dir: Path):
        out = matrix_csv_dir / "plain_dup.blut"
        r = run_cli(
            "create", "--out", str(out),
            "--csv", "startup_ff_125c.csv", "--run-id", "solo",
            "--csv", "startup_tt_25c.csv", "--run-id", "solo",
            "--force", "--workers", "1",
            cwd=matrix_csv_dir,
        )
        assert r.returncode != 0
        assert "Duplicate (run_id, corner_id) pair" in r.stderr


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
