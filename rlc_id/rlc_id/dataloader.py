"""Pluggable interface for real waveform data. CSV is implemented directly; FSDB
requires the vendor-specific reader (Verdi API) not available in this environment --
the interface documents the extension point rather than faking support. A minimal
VCD reader is included for basic single-signal extraction.
"""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np
import pandas as pd


@dataclass
class WaveformData:
    """Uniform container regardless of source. time_or_freq is either a uniform
    time vector (time-domain) or an angular-frequency vector (frequency-domain,
    is_frequency_domain=True)."""
    time_or_freq: np.ndarray
    u: np.ndarray | None       # input excitation (None for frequency-domain S/Y/Z data)
    y: np.ndarray              # output response (real for time-domain, complex for freq-domain)
    is_frequency_domain: bool = False
    metadata: dict | None = None


def load_csv(path: str, time_col: str = "time", input_col: str | None = "input",
             output_col: str = "output", freq_col: str | None = None,
             real_col: str | None = None, imag_col: str | None = None) -> WaveformData:
    """Load time-domain (time, input, output columns) or frequency-domain
    (freq, real, imag columns) waveform data from CSV."""
    df = pd.read_csv(path)
    if freq_col is not None:
        if freq_col not in df.columns:
            raise ValueError(f"freq_col '{freq_col}' not found in {path}; columns: {list(df.columns)}")
        w = df[freq_col].to_numpy(dtype=float)
        if real_col and imag_col:
            y = df[real_col].to_numpy(dtype=float) + 1j * df[imag_col].to_numpy(dtype=float)
        else:
            y = df[output_col].to_numpy(dtype=complex)
        return WaveformData(w, None, y, is_frequency_domain=True, metadata={"source": path})

    if time_col not in df.columns:
        raise ValueError(f"time_col '{time_col}' not found in {path}; columns: {list(df.columns)}")
    t = df[time_col].to_numpy(dtype=float)
    u = df[input_col].to_numpy(dtype=float) if input_col and input_col in df.columns else None
    if output_col not in df.columns:
        raise ValueError(f"output_col '{output_col}' not found in {path}; columns: {list(df.columns)}")
    y = df[output_col].to_numpy(dtype=float)
    return WaveformData(t, u, y, is_frequency_domain=False, metadata={"source": path})


def save_csv(data: WaveformData, path: str) -> str:
    if data.is_frequency_domain:
        df = pd.DataFrame({"freq": data.time_or_freq, "real": data.y.real, "imag": data.y.imag})
    else:
        cols = {"time": data.time_or_freq, "output": data.y}
        if data.u is not None:
            cols["input"] = data.u
        df = pd.DataFrame(cols)
    df.to_csv(path, index=False)
    return path


def load_fsdb(path: str, signal_name: str) -> WaveformData:
    """Extension point: FSDB (Verdi/Synopsys) reading requires the vendor's FSDB
    reader library, not available in this environment. Export to CSV via Verdi's
    'File > Export > CSV', or convert via fsdb2vcd + load_vcd(), as a workaround."""
    raise NotImplementedError(
        "FSDB reading requires the vendor FSDB reader (Synopsys Verdi API), which "
        "is not bundled here. Export the waveform to CSV from Verdi and use "
        "load_csv() instead, or convert via fsdb2vcd + load_vcd()."
    )


def load_vcd(path: str, signal_name: str) -> WaveformData:
    """Minimal VCD (Value Change Dump) reader for a single scalar signal's binary
    transitions. For large/multi-signal/multi-bit VCDs, prefer a dedicated parser
    (e.g. the vcdvcd package) and route the result through load_csv()."""
    import re
    times, values = [], []
    var_id = None
    timescale = 1e-9
    current_time = 0.0
    try:
        with open(path) as f:
            in_header = True
            for line in f:
                line = line.strip()
                if in_header:
                    if line.startswith("$timescale"):
                        m = re.search(r"(\d+)\s*(fs|ps|ns|us|ms|s)", line)
                        if m:
                            scale = {"fs": 1e-15, "ps": 1e-12, "ns": 1e-9,
                                     "us": 1e-6, "ms": 1e-3, "s": 1.0}[m.group(2)]
                            timescale = int(m.group(1)) * scale
                    if line.startswith("$var") and signal_name in line:
                        var_id = line.split()[3]
                    if line.startswith("$enddefinitions"):
                        in_header = False
                    continue
                if not line:
                    continue
                if line.startswith("#"):
                    current_time = int(line[1:]) * timescale
                elif var_id and (line[1:] == var_id or line.endswith(var_id)):
                    val_str = line[0]
                    if val_str in "01":
                        values.append(float(val_str))
                        times.append(current_time)
    except FileNotFoundError:
        raise FileNotFoundError(f"VCD file not found: {path}")
    if not times:
        raise ValueError(f"signal '{signal_name}' not found or has no transitions in {path}")
    return WaveformData(np.array(times), None, np.array(values), metadata={"source": path})
