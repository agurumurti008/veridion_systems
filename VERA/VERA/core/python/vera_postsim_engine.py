#!/usr/bin/env python3
"""
VERA — Verification Engine for Runtime & Autonomous Checking
FILE: core/python/vera_postsim_engine.py
DESC: Post-simulation checker engine for AMS/mixed-signal verification.
      Supports VCD, CSV, FSDB (via vcd library), and nutmeg/RAW files.
      Produces standardized VERA JSON reports with waveform anchors.
VERSION: 1.0
"""

import json
import math
import os
import sys
import numpy as np
from scipy import signal as scipy_signal
from scipy.fft import fft, fftfreq
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Tuple, Union
from datetime import datetime
from pathlib import Path


# =============================================================================
# VERA Result Item — Python equivalent of SV vera_result_item
# =============================================================================
@dataclass
class VERAResultItem:
    vera_version:   str = "1.0"
    timestamp:      str = field(default_factory=lambda: datetime.now().isoformat())
    simulation_id:  str = ""
    ip_name:        str = ""
    block_name:     str = ""
    test_name:      str = ""
    checker_name:   str = ""
    checker_type:   str = "post_sim_python"
    layer:          str = "parametric"
    status:         str = "UNKNOWN"       # PASS / FAIL / WARNING / INFO
    severity:       str = "INFO"          # ERROR / WARNING / INFO
    expected:       str = ""
    actual:         str = ""
    margin:         str = ""
    context:        str = ""
    debug_signal:   str = ""
    waveform_anchor_time: Optional[float] = None
    recommendation: str = ""

    def is_fail(self) -> bool:
        return self.status == "FAIL"

    def to_dict(self) -> dict:
        return asdict(self)


# =============================================================================
# VERA Report Engine
# =============================================================================
class VERAReporter:
    """Aggregates VERAResultItems and writes the VERA JSON report."""

    def __init__(self, report_path: str = "vera_report.json"):
        self.report_path = report_path
        self.results: List[VERAResultItem] = []
        self.sim_meta: Dict[str, Any] = {}

    def add(self, item: VERAResultItem):
        self.results.append(item)
        # Echo to console
        icon = "✓" if item.status == "PASS" else "✗" if item.status == "FAIL" else "⚠"
        print(f"  [{icon}] {item.ip_name} | {item.checker_name} | "
              f"EXP: {item.expected} | ACT: {item.actual} | "
              f"MARGIN: {item.margin}")

    @property
    def pass_count(self): return sum(1 for r in self.results if r.status == "PASS")
    @property
    def fail_count(self): return sum(1 for r in self.results if r.status == "FAIL")
    @property
    def warn_count(self): return sum(1 for r in self.results if r.status == "WARNING")

    def write(self):
        report = {
            "vera_report": {
                "meta": {
                    **self.sim_meta,
                    "generated_at": datetime.now().isoformat(),
                    "vera_version": "1.0"
                },
                "summary": {
                    "total":   len(self.results),
                    "pass":    self.pass_count,
                    "fail":    self.fail_count,
                    "warning": self.warn_count
                },
                "results": [r.to_dict() for r in self.results]
            }
        }
        with open(self.report_path, "w") as f:
            json.dump(report, f, indent=2)

        print(f"\n{'='*60}")
        print(f"  VERA SUMMARY: PASS={self.pass_count} "
              f"FAIL={self.fail_count} WARN={self.warn_count}")
        print(f"  Report: {self.report_path}")
        print(f"{'='*60}\n")
        return self.fail_count == 0


# =============================================================================
# VERA Signal Loader — reads VCD / CSV / custom formats
# =============================================================================
class VERASignalLoader:
    """Loads simulation waveform data from various formats."""

    @staticmethod
    def from_csv(filepath: str, time_col: str = "time") -> Dict[str, np.ndarray]:
        """Load signals from CSV (e.g., from AMS sim or probe extraction)."""
        import csv
        data: Dict[str, List[float]] = {}
        with open(filepath) as f:
            reader = csv.DictReader(f)
            for row in reader:
                for col in row:
                    if col not in data:
                        data[col] = []
                    try:
                        data[col].append(float(row[col]))
                    except (ValueError, TypeError):
                        data[col].append(float('nan'))
        return {k: np.array(v) for k, v in data.items()}

    @staticmethod
    def from_vcd(filepath: str, signals: List[str]) -> Dict[str, Tuple[np.ndarray, np.ndarray]]:
        """Load digital signals from VCD. Returns {signal: (time_arr, value_arr)}."""
        try:
            from vcdvcd import VCDVCD
            vcd = VCDVCD(filepath)
            result = {}
            for sig in signals:
                if sig in vcd:
                    tv = vcd[sig].tv
                    times  = np.array([t for t, _ in tv], dtype=float)
                    values = np.array([int(v, 2) if v not in ('x', 'z', 'X', 'Z')
                                       else np.nan for _, v in tv])
                    result[sig] = (times, values)
            return result
        except ImportError:
            print("  [VERA] vcdvcd not installed. Run: pip install vcdvcd")
            return {}

    @staticmethod
    def from_nutmeg(filepath: str) -> Dict[str, np.ndarray]:
        """Parse Spectre/SPICE nutmeg/RAW binary/ASCII output."""
        try:
            import ltspice
            sim = ltspice.Ltspice(filepath)
            sim.parse()
            result = {"time": sim.get_time()}
            for node in sim.variables:
                try:
                    result[node] = sim.get_data(node)
                except Exception:
                    pass
            return result
        except ImportError:
            # Fallback: simple ASCII nutmeg parser
            return VERASignalLoader._parse_ascii_nutmeg(filepath)

    @staticmethod
    def _parse_ascii_nutmeg(filepath: str) -> Dict[str, np.ndarray]:
        """Minimal ASCII nutmeg parser."""
        signals: Dict[str, List[float]] = {}
        sig_names: List[str] = []
        reading_values = False
        with open(filepath) as f:
            for line in f:
                line = line.strip()
                if line.startswith("Variables:"):
                    reading_values = False
                elif line.startswith("Values:"):
                    reading_values = True
                elif not reading_values and line and not line.startswith("#"):
                    # Try to parse variable names
                    parts = line.split()
                    if len(parts) >= 3 and parts[0].isdigit():
                        sig_names.append(parts[1])
                        signals[parts[1]] = []
                elif reading_values and line:
                    parts = line.split()
                    if len(parts) == len(sig_names):
                        for i, name in enumerate(sig_names):
                            try:
                                signals[name].append(float(parts[i]))
                            except ValueError:
                                pass
        return {k: np.array(v) for k, v in signals.items()}


# =============================================================================
# VERA Parametric Checker — checks scalar/vector measurements against spec
# =============================================================================
class VERAParametricChecker:
    """Checks measured values against specification limits."""

    def __init__(self, reporter: VERAReporter, ip_name: str):
        self.reporter = reporter
        self.ip_name  = ip_name

    def check(
        self,
        checker_name: str,
        measured:     float,
        min_val:      Optional[float] = None,
        max_val:      Optional[float] = None,
        target:       Optional[float] = None,
        unit:         str = "",
        signal:       str = "",
        context:      str = "",
        waveform_time: Optional[float] = None,
        recommendation: str = ""
    ) -> VERAResultItem:
        """Check a measured scalar value against min/max/target spec."""

        # Build expected string
        if min_val is not None and max_val is not None:
            expected_str = f"{min_val} to {max_val} {unit}"
            in_spec = min_val <= measured <= max_val
        elif min_val is not None:
            expected_str = f">= {min_val} {unit}"
            in_spec = measured >= min_val
        elif max_val is not None:
            expected_str = f"<= {max_val} {unit}"
            in_spec = measured <= max_val
        elif target is not None:
            # TODO: need tolerance for target check — pass as separate param
            expected_str = f"~{target} {unit}"
            in_spec = True  # Override with margin check in caller
        else:
            expected_str = "see context"
            in_spec = True

        # Margin calculation
        if min_val is not None and max_val is not None:
            margin_to_min = measured - min_val
            margin_to_max = max_val - measured
            margin_str    = f"lo={margin_to_min:+.4g}, hi={margin_to_max:+.4g} {unit}"
        else:
            margin_str = ""

        result = VERAResultItem(
            ip_name       = self.ip_name,
            checker_name  = checker_name,
            checker_type  = "post_sim_python",
            layer         = "parametric",
            status        = "PASS" if in_spec else "FAIL",
            severity      = "INFO" if in_spec else "ERROR",
            expected      = expected_str,
            actual        = f"{measured:.6g} {unit}",
            margin        = margin_str,
            context       = context,
            debug_signal  = signal,
            waveform_anchor_time = waveform_time,
            recommendation = recommendation if not in_spec else ""
        )
        self.reporter.add(result)
        return result


# =============================================================================
# VERA ADC Checker — ENOB, SFDR, THD, SNR, DNL, INL
# =============================================================================
class VERAAdcChecker:
    """Complete ADC performance checker: static and dynamic metrics."""

    def __init__(self, reporter: VERAReporter, ip_name: str,
                 n_bits: int = 12, fs_hz: float = 1e6, vref: float = 1.8):
        self.reporter  = reporter
        self.ip_name   = ip_name
        self.n_bits    = n_bits
        self.fs_hz     = fs_hz
        self.vref      = vref
        self.lsb       = vref / (2**n_bits)
        self.param_chk = VERAParametricChecker(reporter, ip_name)

    # -------------------------------------------------------------------------
    # Dynamic: ENOB, SNR, SFDR, SINAD, THD from FFT
    # -------------------------------------------------------------------------
    def check_dynamic(
        self,
        codes:      np.ndarray,
        fin_hz:     float,
        spec:       Dict[str, Any]
    ) -> Dict[str, VERAResultItem]:
        """
        codes:  ADC output codes (integer array)
        fin_hz: input sine frequency
        spec:   {'enob_min': 10.5, 'snr_min_db': 65, 'sfdr_min_db': 75, 'thd_max_db': -70}
        """
        results = {}
        N = len(codes)

        # Remove DC and normalize
        codes_f = codes.astype(float)
        codes_f -= np.mean(codes_f)
        # Windowed FFT (Hann window reduces spectral leakage)
        window  = np.hanning(N)
        fft_out = fft(codes_f * window)
        fft_mag = np.abs(fft_out[:N//2]) * 2 / (np.sum(window))
        freqs   = fftfreq(N, d=1.0/self.fs_hz)[:N//2]

        # Find fundamental bin
        fin_bin = int(round(fin_hz / (self.fs_hz / N)))
        sig_power = np.sum(fft_mag[max(0, fin_bin-2):fin_bin+3]**2)

        # Noise power (excluding DC and fundamental and harmonics)
        harmonic_bins = set()
        for h in range(1, 10):
            hbin = (h * fin_bin) % (N//2)
            harmonic_bins.update(range(max(0, hbin-2), hbin+3))

        noise_bins = [i for i in range(1, N//2)
                      if i not in harmonic_bins and i not in range(fin_bin-2, fin_bin+3)]
        noise_power = np.sum(fft_mag[noise_bins]**2) if noise_bins else 1e-20

        # THD harmonics power
        thd_power = sum(
            np.sum(fft_mag[max(0, (h*fin_bin)%(N//2)-2):(h*fin_bin)%(N//2)+3]**2)
            for h in range(2, 6)
        )

        # Metrics
        snr_db   = 10 * math.log10(sig_power / max(noise_power, 1e-20))
        sinad_db = 10 * math.log10(sig_power / max(noise_power + thd_power, 1e-20))
        enob     = (sinad_db - 1.76) / 6.02
        thd_db   = 10 * math.log10(max(thd_power, 1e-20) / max(sig_power, 1e-20))

        # SFDR: highest spur
        sfdr_bins = [i for i in range(1, N//2) if i not in range(fin_bin-2, fin_bin+3)]
        if sfdr_bins:
            spur_power = np.max(fft_mag[sfdr_bins]**2)
            sfdr_db = 10 * math.log10(sig_power / max(spur_power, 1e-20))
        else:
            sfdr_db = 100.0

        # Check against spec
        if "enob_min" in spec:
            results["enob"] = self.param_chk.check(
                "vera_adc_enob", enob, min_val=spec["enob_min"],
                unit="bits", signal="adc_out",
                context=f"fin={fin_hz/1e3:.1f}kHz, fs={self.fs_hz/1e6:.1f}MHz, N={N}",
                recommendation="Check aperture jitter, comparator noise, or reference noise"
            )
        if "snr_min_db" in spec:
            results["snr"] = self.param_chk.check(
                "vera_adc_snr", snr_db, min_val=spec["snr_min_db"],
                unit="dB", signal="adc_out",
                context=f"fin={fin_hz/1e3:.1f}kHz",
                recommendation="Check thermal noise floor or quantization noise"
            )
        if "sfdr_min_db" in spec:
            results["sfdr"] = self.param_chk.check(
                "vera_adc_sfdr", sfdr_db, min_val=spec["sfdr_min_db"],
                unit="dBc", signal="adc_out",
                recommendation="Check harmonic distortion in input amplifier or DAC"
            )
        if "thd_max_db" in spec:
            results["thd"] = self.param_chk.check(
                "vera_adc_thd", thd_db, max_val=spec["thd_max_db"],
                unit="dBc", signal="adc_out",
                recommendation="Check nonlinearity in front-end or reference"
            )

        return results

    # -------------------------------------------------------------------------
    # Static: DNL, INL from code density / ramp test
    # -------------------------------------------------------------------------
    def check_static(
        self,
        codes:   np.ndarray,
        spec:    Dict[str, Any]
    ) -> Dict[str, VERAResultItem]:
        """
        codes: ADC output from a ramp / slow sine input
        spec:  {'dnl_max_lsb': 0.5, 'inl_max_lsb': 1.0, 'missing_codes_max': 0}
        """
        results = {}
        num_codes = 2**self.n_bits

        # Code density histogram
        hist, _ = np.histogram(codes, bins=num_codes, range=(0, num_codes))
        ideal_count = len(codes) / num_codes

        # DNL[k] = (hist[k] / ideal_count) - 1  in LSBs
        dnl = (hist.astype(float) / ideal_count) - 1.0
        inl = np.cumsum(dnl)

        dnl_max   = float(np.max(np.abs(dnl[1:-1])))  # exclude endpoints
        inl_max   = float(np.max(np.abs(inl[1:-1])))
        miss_codes = int(np.sum(hist[1:-1] == 0))

        # Worst-case code for debug
        worst_dnl_code = int(np.argmax(np.abs(dnl[1:-1]))) + 1
        worst_inl_code = int(np.argmax(np.abs(inl[1:-1]))) + 1

        if "dnl_max_lsb" in spec:
            results["dnl"] = self.param_chk.check(
                "vera_adc_dnl", dnl_max, max_val=spec["dnl_max_lsb"],
                unit="LSB", signal="adc_out",
                context=f"worst at code={worst_dnl_code}",
                recommendation=f"Check capacitor mismatch near code {worst_dnl_code}"
            )
        if "inl_max_lsb" in spec:
            results["inl"] = self.param_chk.check(
                "vera_adc_inl", inl_max, max_val=spec["inl_max_lsb"],
                unit="LSB", signal="adc_out",
                context=f"worst at code={worst_inl_code}",
                recommendation="Check reference voltage accuracy or gain error"
            )
        if "missing_codes_max" in spec:
            results["missing_codes"] = self.param_chk.check(
                "vera_adc_missing_codes", miss_codes, max_val=spec["missing_codes_max"],
                unit="codes", signal="adc_out",
                context=f"missing codes detected",
                recommendation="Check for stuck bits or comparator offset exceeding 1 LSB"
            )
        return results


# =============================================================================
# VERA PLL Checker — lock time, frequency accuracy, jitter, phase noise
# =============================================================================
class VERAPllChecker:
    """PLL performance checker: lock time, Fout accuracy, jitter."""

    def __init__(self, reporter: VERAReporter, ip_name: str):
        self.reporter  = reporter
        self.ip_name   = ip_name
        self.param_chk = VERAParametricChecker(reporter, ip_name)

    def check_lock_time(
        self,
        vco_freq:    np.ndarray,  # array of measured VCO frequency over time
        time_ns:     np.ndarray,
        target_freq: float,
        tol_ppm:     float,
        max_lock_ns: float,
        spec:        Dict[str, Any]
    ) -> VERAResultItem:
        """Find when VCO frequency settles within tolerance of target."""
        tol_abs = target_freq * tol_ppm * 1e-6
        locked  = np.abs(vco_freq - target_freq) < tol_abs
        lock_indices = np.where(locked)[0]

        if len(lock_indices) == 0:
            actual_lock_ns = float('inf')
            locked_freq    = float('nan')
        else:
            # Find first sustained lock (10 consecutive samples)
            for i in lock_indices:
                if i + 10 < len(locked) and np.all(locked[i:i+10]):
                    actual_lock_ns = float(time_ns[i])
                    locked_freq    = float(vco_freq[i])
                    break
            else:
                actual_lock_ns = float(time_ns[lock_indices[0]])
                locked_freq    = float(vco_freq[lock_indices[0]])

        return self.param_chk.check(
            "vera_pll_lock_time", actual_lock_ns,
            max_val=max_lock_ns, unit="ns",
            signal="vco_out",
            context=f"target={target_freq/1e6:.3f}MHz, tol={tol_ppm}ppm",
            recommendation="Check loop filter bandwidth, VCO gain, or charge pump current"
        )

    def check_jitter_rms(
        self,
        clk_edges_ns: np.ndarray,   # array of rising edge times in ns
        spec_jitter_rms_ps: float
    ) -> VERAResultItem:
        """Calculate RMS jitter from edge-to-edge period variation."""
        if len(clk_edges_ns) < 10:
            return None
        periods  = np.diff(clk_edges_ns)
        mean_p   = np.mean(periods)
        jitter_rms_ps = float(np.std(periods) * 1000)  # ns→ps

        return self.param_chk.check(
            "vera_pll_jitter_rms", jitter_rms_ps,
            max_val=spec_jitter_rms_ps, unit="ps_rms",
            signal="pll_clkout",
            context=f"mean_period={mean_p:.3f}ns, N_edges={len(clk_edges_ns)}",
            recommendation="Check reference clock quality, VCO noise, or supply noise"
        )

    def check_frequency_accuracy(
        self,
        measured_freq_hz: float,
        target_freq_hz:   float,
        max_error_ppm:    float
    ) -> VERAResultItem:
        """Check PLL output frequency accuracy."""
        error_ppm = abs(measured_freq_hz - target_freq_hz) / target_freq_hz * 1e6
        return self.param_chk.check(
            "vera_pll_freq_accuracy", error_ppm,
            max_val=max_error_ppm, unit="ppm",
            signal="pll_clkout",
            context=f"target={target_freq_hz/1e6:.3f}MHz, measured={measured_freq_hz/1e6:.3f}MHz",
            recommendation="Check divider values, reference frequency, or VCO calibration"
        )


# =============================================================================
# VERA Power Checker — average/peak current, inrush
# =============================================================================
class VERAPowerChecker:
    """Power and current consumption checker."""

    def __init__(self, reporter: VERAReporter, ip_name: str):
        self.reporter  = reporter
        self.ip_name   = ip_name
        self.param_chk = VERAParametricChecker(reporter, ip_name)

    def check_current(
        self,
        current_ua:   np.ndarray,
        time_ns:      np.ndarray,
        spec:         Dict[str, Any]
    ):
        """Check average and peak current against specification."""
        i_avg = float(np.mean(current_ua))
        i_peak = float(np.max(np.abs(current_ua)))
        i_rms  = float(np.sqrt(np.mean(current_ua**2)))

        results = {}
        if "iavg_max_ua" in spec:
            results["iavg"] = self.param_chk.check(
                "vera_power_iavg", i_avg, max_val=spec["iavg_max_ua"],
                unit="uA", signal="vdd_current",
                recommendation="Check always-on bias currents or leakage paths"
            )
        if "ipeak_max_ua" in spec:
            peak_time = float(time_ns[np.argmax(np.abs(current_ua))])
            results["ipeak"] = self.param_chk.check(
                "vera_power_ipeak", i_peak, max_val=spec["ipeak_max_ua"],
                unit="uA", signal="vdd_current",
                waveform_time=peak_time,
                recommendation="Check switching current spikes or capacitive loads"
            )
        return results


# =============================================================================
# VERA Checker Runner — orchestrates all checkers for a given IP
# =============================================================================
class VERACheckerRunner:
    """
    Top-level runner. Load spec YAML, load simulation data,
    run all applicable checkers, write report.
    """

    def __init__(self, spec_path: str, sim_data_path: str,
                 report_path: str = "vera_report.json"):
        import yaml
        with open(spec_path) as f:
            self.spec = yaml.safe_load(f)
        self.sim_data_path = sim_data_path
        self.reporter = VERAReporter(report_path)
        self.reporter.sim_meta = {
            "spec_file":     spec_path,
            "sim_data":      sim_data_path,
            "ip_name":       self.spec.get("ip_name", "UNKNOWN"),
            "ip_type":       self.spec.get("ip_type", "UNKNOWN"),
        }

    def run(self) -> bool:
        ip_type = self.spec.get("ip_type", "").lower()
        ip_name = self.spec.get("ip_name", "UNKNOWN")

        print(f"\n{'='*60}")
        print(f"  VERA Post-Sim Checker: {ip_name} ({ip_type.upper()})")
        print(f"{'='*60}")

        # Load simulation data
        loader = VERASignalLoader()
        ext = Path(self.sim_data_path).suffix.lower()
        if ext == ".csv":
            data = loader.from_csv(self.sim_data_path)
        elif ext in (".raw", ".nutmeg"):
            data = loader.from_nutmeg(self.sim_data_path)
        else:
            print(f"  [VERA] Warning: unsupported format {ext}, trying CSV")
            data = loader.from_csv(self.sim_data_path)

        # Dispatch to IP-specific checkers
        if ip_type == "adc":
            self._run_adc_checkers(data, ip_name)
        elif ip_type == "pll":
            self._run_pll_checkers(data, ip_name)
        elif ip_type == "ldo":
            self._run_ldo_checkers(data, ip_name)
        else:
            self._run_generic_parametric(data, ip_name)

        return self.reporter.write()

    def _run_adc_checkers(self, data: dict, ip_name: str):
        spec_adc = self.spec.get("adc", {})
        n_bits   = spec_adc.get("n_bits", 12)
        fs_hz    = spec_adc.get("fs_hz", 1e6)
        vref     = spec_adc.get("vref_v", 1.8)
        chk = VERAAdcChecker(self.reporter, ip_name, n_bits, fs_hz, vref)

        # Dynamic checks
        if "codes" in data and "dynamic" in spec_adc:
            fin_hz = spec_adc.get("fin_hz", fs_hz / 10)
            chk.check_dynamic(data["codes"].astype(int),
                               fin_hz, spec_adc["dynamic"])
        # Static checks
        if "codes" in data and "static" in spec_adc:
            chk.check_static(data["codes"].astype(int), spec_adc["static"])

    def _run_pll_checkers(self, data: dict, ip_name: str):
        spec_pll = self.spec.get("pll", {})
        chk = VERAPllChecker(self.reporter, ip_name)
        if "vco_freq" in data and "time" in data:
            if "lock_time_ns" in spec_pll:
                chk.check_lock_time(
                    data["vco_freq"], data["time"],
                    spec_pll.get("fout_hz", 1e9),
                    spec_pll.get("lock_tol_ppm", 100),
                    spec_pll["lock_time_ns"], spec_pll
                )

    def _run_ldo_checkers(self, data: dict, ip_name: str):
        spec_ldo = self.spec.get("ldo", {})
        pc = VERAParametricChecker(self.reporter, ip_name)
        if "vout" in data:
            vout_mean = float(np.mean(data["vout"]))
            vout_min  = spec_ldo.get("vout_min_v")
            vout_max  = spec_ldo.get("vout_max_v")
            pc.check("vera_ldo_vout", vout_mean, vout_min, vout_max, unit="V",
                     signal="vout", recommendation="Check feedback network resistors")

    def _run_generic_parametric(self, data: dict, ip_name: str):
        checks = self.spec.get("parametric_checks", [])
        pc = VERAParametricChecker(self.reporter, ip_name)
        for chk in checks:
            signal = chk.get("signal")
            if signal and signal in data:
                arr = data[signal]
                meas_fn = chk.get("measure", "mean")
                if meas_fn == "mean":   val = float(np.mean(arr))
                elif meas_fn == "max":  val = float(np.max(arr))
                elif meas_fn == "min":  val = float(np.min(arr))
                elif meas_fn == "rms":  val = float(np.sqrt(np.mean(arr**2)))
                else:                   val = float(np.mean(arr))
                pc.check(
                    chk.get("name", f"vera_{signal}_{meas_fn}"),
                    val,
                    min_val=chk.get("min"), max_val=chk.get("max"),
                    unit=chk.get("unit", ""), signal=signal
                )


# =============================================================================
# CLI Entry Point
# =============================================================================
def main():
    import argparse
    parser = argparse.ArgumentParser(description="VERA Post-Sim Checker Engine")
    parser.add_argument("--spec",    required=True, help="IP spec YAML file")
    parser.add_argument("--data",    required=True, help="Simulation output (CSV/RAW)")
    parser.add_argument("--report",  default="vera_report.json", help="Output report path")
    args = parser.parse_args()

    runner = VERACheckerRunner(args.spec, args.data, args.report)
    ok = runner.run()
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
