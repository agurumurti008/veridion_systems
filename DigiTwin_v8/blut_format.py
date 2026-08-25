#!/usr/bin/env python3
"""
blut_format.py — Shared binary format definitions for the digiTwin BLUT
container (v7), plus a v6-compatible read path.

This module is the single source of truth for the BLUT binary layout.
Both digitwin_blut_builder.py and digitwin_blut_reader.py import it rather
than re-implementing struct packing/unpacking independently. See
BLUT_FORMAT.md for the full human-readable spec this module implements.

Do not change struct formats here without updating BLUT_FORMAT.md in the
same change, and bumping VERSION if the layout is incompatible.
"""

from __future__ import annotations

import logging
import os
import struct
import zlib
from dataclasses import dataclass, field
from typing import BinaryIO, Optional

import numpy as np

log = logging.getLogger("digitwin.blut_format")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAGIC = b"BLUT"
RUN_MARKER = b"RUN\x00"
INDEX_MARKER = b"IDX\x00"

VERSION_V6 = 6
VERSION_V7 = 7
VERSION = 8  # current version written by this module

ENC_FLOAT64 = 0
ENC_FLOAT32 = 1
ENC_INT32 = 2
ENC_NAMES = {ENC_FLOAT64: "float64", ENC_FLOAT32: "float32", ENC_INT32: "int32"}
ENC_BY_NAME = {v: k for k, v in ENC_NAMES.items()}
ENC_DTYPE = {ENC_FLOAT64: np.float64, ENC_FLOAT32: np.float32, ENC_INT32: np.int32}

COMP_NONE = 0
COMP_ZLIB = 1

HOLD_ZOH = 0          # zero-order hold / forward-fill (default, correct for v6-equivalent behavior)
HOLD_LINEAR = 1        # linear interpolation between stored points (reserved, not yet implemented by reader)

INT32_MAX = 2_147_483_647
INT32_MIN = -2_147_483_648

FILE_HEADER_FLAG_HAS_INDEX = 0x1


class BlutFormatError(Exception):
    """Raised for any structurally invalid / truncated / inconsistent BLUT file."""


# ---------------------------------------------------------------------------
# Padding helpers
# ---------------------------------------------------------------------------

def pad_len(n: int) -> int:
    """Bytes of zero padding needed to bring n up to the next multiple of 8."""
    return (8 - (n % 8)) % 8


def write_pad8(f: BinaryIO) -> None:
    pad = pad_len(f.tell())
    if pad:
        f.write(b"\x00" * pad)


def seek_pad8(f: BinaryIO) -> None:
    """Skip padding when reading, without materializing the bytes."""
    pad = pad_len(f.tell())
    if pad:
        f.seek(pad, os.SEEK_CUR)


# ---------------------------------------------------------------------------
# Low-level read helpers with clear error context
# ---------------------------------------------------------------------------

def _read_exact(f: BinaryIO, n: int, what: str, path: str) -> bytes:
    data = f.read(n)
    if len(data) != n:
        raise BlutFormatError(
            f"{path}: truncated while reading {what} "
            f"(wanted {n} bytes, got {len(data)}) at offset {f.tell() - len(data)}"
        )
    return data


def _unpack(fmt: str, data: bytes, what: str, path: str):
    try:
        return struct.unpack(fmt, data)
    except struct.error as e:
        raise BlutFormatError(f"{path}: failed to parse {what}: {e}") from e


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class SignalBlockMeta:
    """Decoded signal block header (without the blob payload, unless loaded)."""
    name: str
    offset: float
    qstep: float
    encoding: int
    compressed: int
    hold_mode: int
    nchange: int
    enc_bytes: int
    raw_bytes: int
    file_offset: int  # absolute byte offset of this block's name_len field
    blob: Optional[bytes] = None  # populated only when explicitly loaded

    @property
    def encoding_name(self) -> str:
        return ENC_NAMES.get(self.encoding, f"unknown({self.encoding})")


@dataclass
class RunMeta:
    """Decoded run header (without signal blocks, unless loaded)."""
    run_number: int
    run_id: str
    meta: str
    ntime: int
    n_signals: int
    times: np.ndarray
    file_offset: int  # absolute byte offset of this run's run_marker field
    signals: dict = field(default_factory=dict)  # name -> SignalBlockMeta, populated on demand
    corner_id: str = ""  # PVT corner identifier; "" means no corner context
    # (v7 files and any run written without an explicit --corner-id). See
    # BLUT_FORMAT.md v8 addendum: the combined key for a run within a
    # container is (run_id, corner_id), enabling the same run_id to appear
    # under multiple corners and the same corner_id to appear under
    # multiple run_ids in one file.


# ---------------------------------------------------------------------------
# Signal block encode / decode
# ---------------------------------------------------------------------------

def quantize(
    vals: np.ndarray, encoding: int, offset: float, qstep: float
) -> np.ndarray:
    """Quantize float values into the storage dtype for `encoding`."""
    if encoding == ENC_FLOAT64:
        return np.asarray((vals - offset) / qstep, dtype=np.float64)
    if encoding == ENC_FLOAT32:
        return np.asarray((vals - offset) / qstep, dtype=np.float32)
    if encoding == ENC_INT32:
        q = np.rint((vals - offset) / qstep)
        if q.size and (q.max() > INT32_MAX or q.min() < INT32_MIN):
            raise BlutFormatError(
                f"int32 quantization overflow: range [{q.min()}, {q.max()}] "
                f"exceeds int32 bounds. qstep={qstep!r} is too small for this "
                f"signal's dynamic range; increase --qstep-abs or use "
                f"--qstep-rel / float32 / float64 encoding instead."
            )
        return q.astype(np.int32)
    raise BlutFormatError(f"Unknown encoding id {encoding}")


def dequantize(raw: np.ndarray, encoding: int, offset: float, qstep: float) -> np.ndarray:
    return offset + raw.astype(np.float64) * qstep


def build_signal_payload(
    idxs: np.ndarray, vals: np.ndarray, encoding: int, offset: float, qstep: float
) -> tuple[bytes, int]:
    """Pack (delta-encoded indices, quantized values) into the raw payload bytes."""
    nchange = idxs.size
    if nchange == 0:
        return b"", 0

    deltas = np.empty(nchange, dtype=np.uint32)
    deltas[0] = np.uint32(idxs[0])
    if nchange > 1:
        diffs = np.diff(idxs)
        if diffs.min() < 0:
            raise BlutFormatError("Transition indices must be strictly increasing")
        deltas[1:] = diffs.astype(np.uint32)

    q = quantize(vals, encoding, offset, qstep)
    payload = deltas.tobytes() + q.tobytes()
    return payload, len(payload)


def write_signal_block(
    f: BinaryIO,
    name: str,
    idxs: np.ndarray,
    vals: np.ndarray,
    encoding: int,
    offset: float,
    qstep: float,
    compress: bool,
    hold_mode: int = HOLD_ZOH,
) -> int:
    """Write one signal block to an already-open file handle. Returns bytes written."""
    start = f.tell()
    payload, raw_bytes = build_signal_payload(idxs, vals, encoding, offset, qstep)

    if compress and payload:
        blob = zlib.compress(payload, level=6)
        comp_flag = COMP_ZLIB
    else:
        blob = payload
        comp_flag = COMP_NONE
    enc_bytes = len(blob)

    name_b = name.encode("utf-8")
    if len(name_b) > 0xFFFF:
        raise BlutFormatError(f"Signal name too long ({len(name_b)} bytes): {name!r}")

    f.write(struct.pack("<H", len(name_b)))
    f.write(name_b)
    write_pad8(f)
    f.write(struct.pack("<2d", offset, qstep))
    f.write(struct.pack("<BBBB", encoding, comp_flag, hold_mode, 0))
    f.write(struct.pack("<III", idxs.size, enc_bytes, raw_bytes))
    f.write(blob)
    write_pad8(f)
    return f.tell() - start


def read_signal_block_meta(f: BinaryIO, path: str, load_blob: bool = False) -> SignalBlockMeta:
    """Read one signal block header (and optionally its blob) at the current
    file position. Leaves the file positioned just after the block (incl. padding)."""
    block_start = f.tell()
    name_len = _unpack("<H", _read_exact(f, 2, "signal name_len", path), "signal name_len", path)[0]
    name = _read_exact(f, name_len, "signal name", path).decode("utf-8")
    seek_pad8(f)

    offset, qstep = _unpack("<2d", _read_exact(f, 16, "signal offset/qstep", path), "signal offset/qstep", path)
    encoding, compressed, hold_mode, _reserved = _unpack(
        "<BBBB", _read_exact(f, 4, "signal flags", path), "signal flags", path
    )
    nchange, enc_bytes, raw_bytes = _unpack(
        "<III", _read_exact(f, 12, "signal sizes", path), "signal sizes", path
    )

    if encoding not in ENC_NAMES:
        raise BlutFormatError(f"{path}: signal '{name}' has unknown encoding id {encoding}")
    if compressed not in (COMP_NONE, COMP_ZLIB):
        raise BlutFormatError(f"{path}: signal '{name}' has unknown compression flag {compressed}")

    blob = None
    if load_blob:
        blob = _read_exact(f, enc_bytes, f"blob for signal '{name}'", path)
    else:
        f.seek(enc_bytes, os.SEEK_CUR)
    seek_pad8(f)

    return SignalBlockMeta(
        name=name,
        offset=offset,
        qstep=qstep,
        encoding=encoding,
        compressed=compressed,
        hold_mode=hold_mode,
        nchange=nchange,
        enc_bytes=enc_bytes,
        raw_bytes=raw_bytes,
        file_offset=block_start,
        blob=blob,
    )


def decode_signal(meta: SignalBlockMeta, ntime: int, blob: Optional[bytes] = None) -> np.ndarray:
    """Reconstruct a full-length sample array from a signal block's blob using
    zero-order hold (forward-fill). This is the v7-correct behavior; see
    BLUT_FORMAT.md sec 2 for why v6's zero-fill was a bug."""
    blob = blob if blob is not None else meta.blob
    if blob is None:
        raise BlutFormatError(f"Signal '{meta.name}': no blob loaded to decode")

    nchange = meta.nchange
    if nchange == 0:
        return np.full(ntime, np.nan, dtype=np.float64)

    if meta.compressed == COMP_ZLIB:
        try:
            payload = zlib.decompress(blob)
        except zlib.error as e:
            raise BlutFormatError(f"Signal '{meta.name}': zlib decompression failed: {e}") from e
    else:
        payload = blob

    if len(payload) != meta.raw_bytes:
        raise BlutFormatError(
            f"Signal '{meta.name}': decompressed size {len(payload)} != "
            f"recorded raw_bytes {meta.raw_bytes} (corrupt block?)"
        )

    delta_bytes = 4 * nchange
    if len(payload) < delta_bytes:
        raise BlutFormatError(
            f"Signal '{meta.name}': payload too short for {nchange} deltas "
            f"({len(payload)} < {delta_bytes} bytes)"
        )

    deltas = np.frombuffer(payload[:delta_bytes], dtype=np.uint32)
    raw_vals_bytes = payload[delta_bytes:]

    dtype = ENC_DTYPE[meta.encoding]
    itemsize = np.dtype(dtype).itemsize
    if len(raw_vals_bytes) != nchange * itemsize:
        raise BlutFormatError(
            f"Signal '{meta.name}': value buffer size {len(raw_vals_bytes)} does not "
            f"match nchange*itemsize ({nchange}*{itemsize}={nchange * itemsize})"
        )
    raw_vals = np.frombuffer(raw_vals_bytes, dtype=dtype)

    idxs = np.cumsum(deltas.astype(np.int64))
    if idxs.size and idxs[-1] >= ntime:
        raise BlutFormatError(
            f"Signal '{meta.name}': transition index {idxs[-1]} out of range for "
            f"ntime={ntime} (corrupt block or run/signal time-grid mismatch)"
        )

    vals = dequantize(raw_vals, meta.encoding, meta.offset, meta.qstep)

    full = np.empty(ntime, dtype=np.float64)
    full[:] = np.nan
    full[idxs] = vals

    if meta.hold_mode == HOLD_LINEAR:
        log.warning(
            "Signal '%s' requests hold_mode=LINEAR; reader currently only "
            "implements zero-order hold. Falling back to ZOH.",
            meta.name,
        )

    # Zero-order hold: forward-fill from each stored index to the next.
    # Vectorized via a "last valid index" mask rather than a Python loop.
    valid_mask = ~np.isnan(full)
    if not valid_mask[0]:
        # idxs always includes 0 by construction of the transition finder,
        # but guard defensively for hand-crafted / future files.
        full[0] = vals[0] if idxs[0] == 0 else np.nan
        valid_mask[0] = not np.isnan(full[0])
    last_valid_idx = np.where(valid_mask, np.arange(ntime), 0)
    np.maximum.accumulate(last_valid_idx, out=last_valid_idx)
    full = full[last_valid_idx]

    return full


# ---------------------------------------------------------------------------
# Run header read / write
# ---------------------------------------------------------------------------

def write_run_header(
    f: BinaryIO, run_number: int, run_id: str, meta: str, times: np.ndarray,
    corner_id: str = "",
) -> None:
    """Write a v8 run header. `corner_id` is a first-class field, peer to
    `run_id`: the combined (run_id, corner_id) pair is the uniqueness key
    for a run within a container (enforced by the builder, not here — this
    function just serializes whatever it's given).

    Binary layout (v8): identical to v7 up through `meta`, with
    `corner_id_len` (uint16) added to the length-field trio and `corner_id`
    bytes appended immediately after `meta` bytes, before the 8-byte pad
    that precedes `times[]`. No other field moves. `n_signals` and `ntime`
    remain at their original fixed offsets from `run_marker`, so
    patch_run_n_signals() is unaffected by this change.
    """
    run_id_b = run_id.encode("utf-8")
    meta_b = meta.encode("utf-8")
    corner_id_b = corner_id.encode("utf-8")
    if len(run_id_b) > 0xFFFF or len(meta_b) > 0xFFFF or len(corner_id_b) > 0xFFFF:
        raise BlutFormatError("run_id, meta, or corner_id string too long (max 65535 bytes)")

    f.write(RUN_MARKER)
    f.write(struct.pack("<I", run_number))
    # n_signals is written as a placeholder and patched after signals are
    # known; see patch_run_n_signals(). Its offset (run_header_offset + 8)
    # is fixed regardless of corner_id length, since corner_id is written
    # after this point in the stream.
    f.write(struct.pack("<I", 0))  # n_signals placeholder
    f.write(struct.pack("<I", len(times)))
    f.write(struct.pack("<HHH", len(run_id_b), len(meta_b), len(corner_id_b)))
    f.write(run_id_b)
    f.write(meta_b)
    f.write(corner_id_b)
    write_pad8(f)
    f.write(np.ascontiguousarray(times, dtype=np.float64).tobytes())
    write_pad8(f)


def patch_run_n_signals(f: BinaryIO, run_header_offset: int, n_signals: int) -> None:
    """Patch the n_signals field of an already-written run header in place.

    Offset is run_header_offset + 4 (run_marker) + 4 (run_number) = +8,
    unaffected by the v8 corner_id addition: corner_id is written further
    into the header (after run_id_len/meta_len/corner_id_len and after
    run_id/meta/corner_id bytes), never before n_signals.
    """
    cur = f.tell()
    f.seek(run_header_offset + 4 + 4)  # past run_marker(4) + run_number(4)
    f.write(struct.pack("<I", n_signals))
    f.seek(cur)


def read_run_meta(f: BinaryIO, path: str, version: int, load_signals: bool = False) -> RunMeta:
    """Read one run header (and walk its signal blocks). Leaves the file
    positioned just after the run's last signal block.

    `version` selects the run-header layout: v8 (current) has a third
    length field (corner_id_len) and trailing corner_id bytes after meta;
    v7 files do not have this field at all, so corner_id defaults to ""
    for them — this is the v7-compat path, exactly analogous to how v6
    files are handled via read_v6_as_run() rather than by branching here
    (v7's layout is close enough to v8's to share this function with a
    version-gated field, whereas v6's layout has no run wrapper at all).
    """
    run_start = f.tell()
    marker = _read_exact(f, 4, "run marker", path)
    if marker != RUN_MARKER:
        raise BlutFormatError(
            f"{path}: expected run marker {RUN_MARKER!r} at offset {run_start}, got {marker!r}"
        )
    run_number = _unpack("<I", _read_exact(f, 4, "run_number", path), "run_number", path)[0]
    n_signals = _unpack("<I", _read_exact(f, 4, "n_signals", path), "n_signals", path)[0]
    ntime = _unpack("<I", _read_exact(f, 4, "ntime", path), "ntime", path)[0]

    if version >= VERSION:  # v8+: run_id_len, meta_len, corner_id_len
        run_id_len, meta_len, corner_id_len = _unpack(
            "<HHH",
            _read_exact(f, 6, "run_id_len/meta_len/corner_id_len", path),
            "run_id_len/meta_len/corner_id_len", path,
        )
    else:  # v7: run_id_len, meta_len only; no corner_id field ever written
        run_id_len, meta_len = _unpack(
            "<HH", _read_exact(f, 4, "run_id_len/meta_len", path), "run_id_len/meta_len", path
        )
        corner_id_len = 0

    run_id = _read_exact(f, run_id_len, "run_id", path).decode("utf-8")
    meta = _read_exact(f, meta_len, "run meta", path).decode("utf-8")
    corner_id = _read_exact(f, corner_id_len, "corner_id", path).decode("utf-8")
    seek_pad8(f)
    times = np.frombuffer(_read_exact(f, 8 * ntime, "run times[]", path), dtype=np.float64).copy()
    seek_pad8(f)

    run = RunMeta(
        run_number=run_number,
        run_id=run_id,
        meta=meta,
        corner_id=corner_id,
        ntime=ntime,
        n_signals=n_signals,
        times=times,
        file_offset=run_start,
    )

    for _ in range(n_signals):
        sig = read_signal_block_meta(f, path, load_blob=load_signals)
        run.signals[sig.name] = sig

    return run


# ---------------------------------------------------------------------------
# File header read / write
# ---------------------------------------------------------------------------

def write_file_header(f: BinaryIO, n_runs: int, flags: int = 0) -> None:
    f.write(MAGIC)
    f.write(struct.pack("<I", VERSION))
    f.write(struct.pack("<I", n_runs))
    f.write(struct.pack("<I", flags))


def patch_file_header_counts(f: BinaryIO, n_runs: int, flags: Optional[int] = None) -> None:
    cur = f.tell()
    f.seek(4 + 4)  # past magic + version
    f.write(struct.pack("<I", n_runs))
    if flags is not None:
        f.write(struct.pack("<I", flags))
    f.seek(cur)


@dataclass
class FileHeader:
    version: int
    n_runs: int
    flags: int


def read_file_header(f: BinaryIO, path: str) -> FileHeader:
    magic = _read_exact(f, 4, "magic", path)
    if magic != MAGIC:
        raise BlutFormatError(f"{path}: not a BLUT file (bad magic {magic!r}, expected {MAGIC!r})")
    version = _unpack("<I", _read_exact(f, 4, "version", path), "version", path)[0]

    if version == VERSION_V6:
        # v6 layout diverges immediately: nsig/ntime/times follow directly,
        # no n_runs/flags fields. Caller handles this via read_v6_as_run().
        return FileHeader(version=VERSION_V6, n_runs=1, flags=0)

    if version not in (VERSION_V7, VERSION):
        raise BlutFormatError(
            f"{path}: unsupported BLUT version {version} (this reader supports "
            f"v{VERSION_V6}, v{VERSION_V7}, and v{VERSION})"
        )

    # File header layout (magic/version/n_runs/flags) is identical between
    # v7 and v8 — only the per-run header layout differs (corner_id
    # addition), which read_run_meta() branches on via this same `version`.
    n_runs = _unpack("<I", _read_exact(f, 4, "n_runs", path), "n_runs", path)[0]
    flags = _unpack("<I", _read_exact(f, 4, "flags", path), "flags", path)[0]
    return FileHeader(version=version, n_runs=n_runs, flags=flags)


# ---------------------------------------------------------------------------
# v6 compatibility read path
# ---------------------------------------------------------------------------

LEGACY_V6_RUN_ID = "legacy_v6"


def corner_id_from_meta(meta: str) -> str:
    """Best-effort extraction of a 'corner=X' key from a free-form run_meta
    string, using the 'key=value,key=value,...' convention already shown in
    the builder's --run-meta examples (e.g. 'corner=ff,temp=125'). Returns
    '' if no 'corner=' key is found or meta doesn't follow the convention.

    This is a migration aid only (see migrate-v7 --corner-from-meta) — it
    is not used by the normal write/read path, since corner_id is a
    first-class field in v8 and does not need to be parsed out of meta at
    all once a file has been migrated or created directly with --corner-id.
    """
    for part in meta.split(","):
        part = part.strip()
        if part.lower().startswith("corner="):
            return part.split("=", 1)[1].strip()
    return ""


def read_v6_as_run(f: BinaryIO, path: str, load_signals: bool = False) -> RunMeta:
    """Read a v6 file (file position must be just after the 8-byte
    magic+version already consumed by read_file_header) and present it as a
    single synthetic RunMeta, run_id='legacy_v6', run_number=0.

    v6 layout: magic(4) version(4) nsig(4) ntime(4) times[ntime] pad8
               then nsig signal blocks (no run wrapper).
    """
    nsig = _unpack("<I", _read_exact(f, 4, "v6 nsig", path), "v6 nsig", path)[0]
    ntime = _unpack("<I", _read_exact(f, 4, "v6 ntime", path), "v6 ntime", path)[0]
    times = np.frombuffer(_read_exact(f, 8 * ntime, "v6 times[]", path), dtype=np.float64).copy()
    seek_pad8(f)

    run = RunMeta(
        run_number=0,
        run_id=LEGACY_V6_RUN_ID,
        meta="migrated_from=v6",
        ntime=ntime,
        n_signals=nsig,
        times=times,
        file_offset=0,
    )
    for _ in range(nsig):
        sig = read_signal_block_meta(f, path, load_blob=load_signals)
        run.signals[sig.name] = sig
    return run
