#!/usr/bin/env python3
"""
VERA — Verification Engine for Runtime & Autonomous Checking
FILE: core/python/vera_power_analysis.py
DESC: Post-simulation power and supply checker.
      Supports average/peak current, inrush, supply droop, ripple,
      power sequencing, and multi-rail analysis.
      Reads CSV/RAW simulation data, emits VERA JSON results.
VERSION: 1.0
"""

import numpy as np
import json
import os
import sys
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass

# Import VERA base engine
sys.path.insert(0, os.path.dirname(__file__))
from vera_postsim_engine import VERAResultItem, VERAReporter, VERAParametricChecker, VERASignalLoader


# =============================================================================
# VERA Power Supply Checker
# =============================================================================
class VERAPowerSupplyChecker:
    """Comprehensive power supply and current consumption checker."""

    def __init__(self, reporter: VERAReporter, ip_name: str):
        self.reporter  = reporter
        self.ip_name   = ip_name
        self.param_chk = VERAParametricChecker(reporter, ip_name)

    # -------------------------------------------------------------------------
    # Current checks: average, peak, RMS, inrush
    # -------------------------------------------------------------------------
    def check_current_full(
        self,
        current_a:  np.ndarray,
        time_s:     np.ndarray,
        spec:       Dict[str, Any],
        rail_name:  str = "VDD"
    ) -> Dict[str, VERAResultItem]:
        results = {}

        i_avg  = float(np.mean(current_a))
        i_peak = float(np.max(np.abs(current_a)))
        i_rms  = float(np.sqrt(np.mean(current_a**2)))
        i_min  = float(np.min(current_a))

        # Peak time for waveform anchor
        peak_idx  = int(np.argmax(np.abs(current_a)))
        peak_time = float(time_s[peak_idx]) * 1e9  # s → ns

        ctx = f"rail={rail_name} N={len(current_a)} dur={time_s[-1]*1e6:.1f}us"

        if "iavg_max_ua" in spec:
            results["iavg"] = self.param_chk.check(
                f"vera_{rail_name.lower()}_iavg",
                i_avg * 1e6,    # A → µA
                max_val=spec["iavg_max_ua"], unit="uA",
                signal=f"/{rail_name.lower()}_current", context=ctx,
                recommendation="Check always-on bias paths, leakage, or reference currents"
            )

        if "ipeak_max_ua" in spec:
            results["ipeak"] = self.param_chk.check(
                f"vera_{rail_name.lower()}_ipeak",
                i_peak * 1e6,
                max_val=spec["ipeak_max_ua"], unit="uA",
                signal=f"/{rail_name.lower()}_current", context=ctx,
                waveform_time=peak_time,
                recommendation="Check switching transients, capacitive load currents, or load steps"
            )

        if "irms_max_ua" in spec:
            results["irms"] = self.param_chk.check(
                f"vera_{rail_name.lower()}_irms",
                i_rms * 1e6,
                max_val=spec["irms_max_ua"], unit="uA",
                signal=f"/{rail_name.lower()}_current", context=ctx
            )

        # Inrush current check (first 1% of time window)
        inrush_window = max(1, len(current_a) // 100)
        i_inrush = float(np.max(np.abs(current_a[:inrush_window])))
        if "inrush_max_ma" in spec:
            results["inrush"] = self.param_chk.check(
                f"vera_{rail_name.lower()}_inrush",
                i_inrush * 1e3,    # A → mA
                max_val=spec["inrush_max_ma"], unit="mA",
                signal=f"/{rail_name.lower()}_current",
                context=f"{ctx} first={inrush_window} samples",
                recommendation="Check input capacitance, soft-start circuits, or in-rush limiters"
            )

        return results

    # -------------------------------------------------------------------------
    # Voltage supply checks: mean, droop, ripple
    # -------------------------------------------------------------------------
    def check_supply_voltage(
        self,
        voltage_v:  np.ndarray,
        time_s:     np.ndarray,
        spec:       Dict[str, Any],
        rail_name:  str = "VDD"
    ) -> Dict[str, VERAResultItem]:
        results = {}

        v_mean    = float(np.mean(voltage_v))
        v_min     = float(np.min(voltage_v))
        v_max     = float(np.max(voltage_v))
        v_droop   = v_mean - v_min   # worst-case droop from mean
        v_ripple  = v_max - v_min    # peak-to-peak ripple

        # Time of worst droop
        droop_idx  = int(np.argmin(voltage_v))
        droop_time = float(time_s[droop_idx]) * 1e9

        ctx = f"rail={rail_name} Vmean={v_mean:.3f}V"

        if "vnom_v" in spec and "vtol" in spec:
            vnom = spec["vnom_v"]
            vtol = spec["vtol"]
            results["vmean"] = self.param_chk.check(
                f"vera_{rail_name.lower()}_vmean",
                v_mean,
                min_val=vnom * (1 - vtol),
                max_val=vnom * (1 + vtol),
                unit="V",
                signal=f"/{rail_name.lower()}", context=ctx,
                recommendation="Check LDO regulation or DC-DC output setting"
            )

        if "vdroop_max_mv" in spec:
            results["vdroop"] = self.param_chk.check(
                f"vera_{rail_name.lower()}_droop",
                v_droop * 1e3,
                max_val=spec["vdroop_max_mv"], unit="mV",
                signal=f"/{rail_name.lower()}", context=ctx,
                waveform_time=droop_time,
                recommendation="Check decoupling capacitor placement, PDN impedance, or load regulation"
            )

        if "vripple_max_mv" in spec:
            results["vripple"] = self.param_chk.check(
                f"vera_{rail_name.lower()}_ripple",
                v_ripple * 1e3,
                max_val=spec["vripple_max_mv"], unit="mVpp",
                signal=f"/{rail_name.lower()}", context=ctx,
                recommendation="Check switching frequency, output capacitance, or ESR"
            )

        return results

    # -------------------------------------------------------------------------
    # Power sequencing checker
    # -------------------------------------------------------------------------
    def check_power_sequence(
        self,
        rails:    Dict[str, np.ndarray],  # {rail_name: voltage_array}
        time_s:   np.ndarray,
        sequence: List[Tuple[str, str]],  # [(rail_A, rail_B)]: A must ramp before B
        threshold_v: float = 0.5          # "on" threshold
    ) -> List[VERAResultItem]:
        """Check that power rails come up in the correct sequence."""
        results = []

        # Find ramp-up time for each rail
        ramp_times = {}
        for name, voltage in rails.items():
            above = np.where(voltage >= threshold_v)[0]
            if len(above) > 0:
                ramp_times[name] = float(time_s[above[0]]) * 1e9
            else:
                ramp_times[name] = float('inf')

        for (rail_a, rail_b) in sequence:
            if rail_a not in ramp_times or rail_b not in ramp_times:
                continue
            t_a = ramp_times[rail_a]
            t_b = ramp_times[rail_b]
            in_order = t_a < t_b
            margin_ns = t_b - t_a

            r = VERAResultItem(
                ip_name       = self.ip_name,
                checker_name  = f"vera_pwr_seq_{rail_a.lower()}_before_{rail_b.lower()}",
                checker_type  = "post_sim_python",
                layer         = "parametric",
                status        = "PASS" if in_order else "FAIL",
                severity      = "INFO" if in_order else "ERROR",
                expected      = f"{rail_a} ramps before {rail_b}",
                actual        = f"{rail_a}@{t_a:.1f}ns, {rail_b}@{t_b:.1f}ns",
                margin        = f"{margin_ns:+.1f}ns",
                context       = f"threshold={threshold_v}V",
                debug_signal  = f"/{rail_b.lower()}",
                waveform_anchor_time = t_b if not in_order else None,
                recommendation = f"Check power sequencer: {rail_a} must precede {rail_b}"
                                 if not in_order else ""
            )
            self.reporter.add(r)
            results.append(r)

        return results


# =============================================================================
# VERA Multi-Rail Power Checker
# =============================================================================
class VERAMultiRailChecker:
    """Checks a complete power management sub-system (multiple rails)."""

    def __init__(self, reporter: VERAReporter, ip_name: str):
        self.reporter = reporter
        self.ip_name  = ip_name
        self.pwr_chk  = VERAPowerSupplyChecker(reporter, ip_name)

    def run(self, data: Dict[str, np.ndarray], spec: Dict[str, Any]) -> bool:
        """
        data: dict with keys like 'vdd', 'vio', 'vcore', 'time'
              and current keys like 'idd', 'iio'
        spec: nested dict per rail:
              {
                'VDD':  {'vnom_v': 1.8, 'vtol': 0.05, 'iavg_max_ua': 500, ...},
                'VIO':  {'vnom_v': 3.3, 'vtol': 0.05, ...},
                'sequence': [('VDD', 'VIO')]   # VDD before VIO
              }
        """
        time_s = data.get("time", np.linspace(0, 1e-6, 100))

        print(f"\n  [VERA Power] Multi-Rail Analysis: {self.ip_name}")

        # Check each rail
        for rail_name, rail_spec in spec.items():
            if rail_name == "sequence":
                continue
            v_key = rail_name.lower()
            i_key = f"i{v_key}"
            if v_key in data:
                self.pwr_chk.check_supply_voltage(data[v_key], time_s, rail_spec, rail_name)
            if i_key in data:
                self.pwr_chk.check_current_full(data[i_key], time_s, rail_spec, rail_name)

        # Check power sequencing
        if "sequence" in spec:
            rails_v = {k: data[k.lower()] for k in spec
                       if k != "sequence" and k.lower() in data}
            self.pwr_chk.check_power_sequence(
                rails_v, time_s, spec["sequence"]
            )

        return self.reporter.write()


# =============================================================================
# VERA Oscillator / Clock Source Checker
# =============================================================================
class VERAOscillatorChecker:
    """Checks RC/crystal oscillator or ring oscillator performance."""

    def __init__(self, reporter: VERAReporter, ip_name: str):
        self.reporter  = reporter
        self.ip_name   = ip_name
        self.param_chk = VERAParametricChecker(reporter, ip_name)

    def check_from_edges(
        self,
        edge_times_ns: np.ndarray,
        spec: Dict[str, Any]
    ) -> Dict[str, VERAResultItem]:
        results = {}

        if len(edge_times_ns) < 4:
            return results

        periods     = np.diff(edge_times_ns)
        freq_hz     = 1e9 / np.mean(periods)     # mean period in ns → Hz
        freq_err_ppm = 0.0

        if "fnom_hz" in spec:
            freq_err_ppm = abs(freq_hz - spec["fnom_hz"]) / spec["fnom_hz"] * 1e6

        jitter_rms_ps = float(np.std(periods)) * 1000    # ns → ps
        duty_cycle    = None

        ctx = f"N_edges={len(edge_times_ns)} f={freq_hz/1e6:.3f}MHz"

        if "fnom_hz" in spec and "freq_tol_ppm" in spec:
            results["freq"] = self.param_chk.check(
                "vera_osc_frequency", freq_hz,
                min_val=spec["fnom_hz"] * (1 - spec["freq_tol_ppm"]*1e-6),
                max_val=spec["fnom_hz"] * (1 + spec["freq_tol_ppm"]*1e-6),
                unit="Hz", signal="osc_out", context=ctx,
                recommendation="Check RC trimming, capacitor tolerance, or temperature compensation"
            )

        if "jitter_rms_ps_max" in spec:
            results["jitter"] = self.param_chk.check(
                "vera_osc_jitter_rms", jitter_rms_ps,
                max_val=spec["jitter_rms_ps_max"],
                unit="ps_rms", signal="osc_out", context=ctx,
                recommendation="Check supply noise, substrate coupling, or bias current stability"
            )

        if "freq_err_ppm_max" in spec:
            results["freq_err"] = self.param_chk.check(
                "vera_osc_freq_error_ppm", freq_err_ppm,
                max_val=spec["freq_err_ppm_max"],
                unit="ppm", signal="osc_out", context=ctx
            )

        return results


# =============================================================================
# CLI entry point
# =============================================================================
def main():
    import argparse, yaml
    parser = argparse.ArgumentParser(description="VERA Power & Supply Checker")
    parser.add_argument("--spec",   required=True, help="Power spec YAML")
    parser.add_argument("--data",   required=True, help="Simulation CSV data")
    parser.add_argument("--report", default="vera_power_report.json")
    args = parser.parse_args()

    with open(args.spec) as f:
        spec = yaml.safe_load(f)

    from vera_postsim_engine import VERAReporter, VERASignalLoader
    reporter = VERAReporter(args.report)
    reporter.sim_meta = {"ip_name": spec.get("ip_name", "POWER"), "spec": args.spec}

    loader = VERASignalLoader()
    data   = loader.from_csv(args.data)

    chk = VERAMultiRailChecker(reporter, spec.get("ip_name", "POWER"))
    ok  = chk.run(data, spec.get("rails", {}))
    import sys; sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
