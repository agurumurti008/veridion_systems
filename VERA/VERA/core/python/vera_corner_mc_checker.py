#!/usr/bin/env python3
"""
VERA — Verification Engine for Runtime & Autonomous Checking
FILE: core/python/vera_corner_mc_checker.py
DESC: Corner sweep and Monte Carlo statistical checker.
      Aggregates results across PVT corners, computes worst-case,
      sigma margins, yield estimates, and generates corner heat maps.
      Produces VERA JSON report per corner + aggregate summary.
VERSION: 1.0
"""

import json
import os
import glob
import yaml
import numpy as np
from scipy import stats as sp_stats
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime
import sys

sys.path.insert(0, os.path.dirname(__file__))
from vera_postsim_engine import VERAResultItem, VERAReporter, VERAParametricChecker


# =============================================================================
# Corner Definition
# =============================================================================
@dataclass
class VERACorner:
    name:    str       # e.g. "tt_1v8_25c"
    process: str       # "tt", "ss", "ff", "sf", "fs"
    voltage: float     # supply voltage (V)
    temp:    float     # temperature (°C)
    data_file: str     # path to simulation CSV/RAW for this corner
    weight:  float = 1.0   # weight in yield calculation


STANDARD_CORNERS = [
    VERACorner("tt_1v8_25c",   "tt", 1.80, 25.0,   ""),
    VERACorner("ss_1v62_125c", "ss", 1.62, 125.0,  ""),
    VERACorner("ff_1v98_m40c", "ff", 1.98, -40.0,  ""),
    VERACorner("sf_1v98_125c", "sf", 1.98, 125.0,  ""),
    VERACorner("fs_1v62_m40c", "fs", 1.62, -40.0,  ""),
]


# =============================================================================
# VERA Corner Result — measurement at one corner
# =============================================================================
@dataclass
class VERACornerMeasurement:
    corner:      str
    process:     str
    voltage:     float
    temp:        float
    param_name:  str
    measured:    float
    unit:        str
    passed:      bool
    margin_lo:   float   # measured - spec_min
    margin_hi:   float   # spec_max - measured


# =============================================================================
# VERA Corner & Monte Carlo Checker
# =============================================================================
class VERACornerChecker:
    """
    Runs parametric checks across all PVT corners,
    computes worst-case margins, sigma analysis, and yield estimates.
    """

    def __init__(self, reporter: VERAReporter, ip_name: str):
        self.reporter     = reporter
        self.ip_name      = ip_name
        self.param_chk    = VERAParametricChecker(reporter, ip_name)
        self.corner_data:  Dict[str, Dict[str, float]] = {}   # {corner: {param: value}}
        self.spec:         Dict[str, Any] = {}

    def load_corner_results(self, results_dir: str, pattern: str = "*/vera_report.json"):
        """Load per-corner VERA JSON reports from a results directory."""
        for report_path in sorted(glob.glob(os.path.join(results_dir, pattern))):
            corner_name = os.path.basename(os.path.dirname(report_path))
            try:
                with open(report_path) as f:
                    rpt = json.load(f)
                results = rpt.get("vera_report", {}).get("results", [])
                self.corner_data[corner_name] = {}
                for r in results:
                    if r.get("status") in ("PASS", "FAIL"):
                        # Try to parse the actual value
                        try:
                            val_str = r.get("actual", "").split()[0]
                            self.corner_data[corner_name][r["checker_name"]] = float(val_str)
                        except (ValueError, IndexError):
                            pass
            except Exception as e:
                print(f"  [VERA Corner] Warning: could not load {report_path}: {e}")

    def load_from_dict(self, corner_name: str, measurements: Dict[str, float]):
        """Directly load corner measurements as a dict."""
        self.corner_data[corner_name] = measurements

    def analyze_corners(self, param_specs: Dict[str, Dict[str, Any]]) -> Dict[str, VERAResultItem]:
        """
        Analyze a parameter across all corners.
        param_specs: {param_name: {'min': x, 'max': y, 'unit': 'V', 'signal': '...'}}
        Returns: dict of VERA results per parameter (worst-case across corners)
        """
        results = {}

        for param_name, spec in param_specs.items():
            corner_results: List[VERACornerMeasurement] = []

            for corner_name, measurements in self.corner_data.items():
                if param_name not in measurements:
                    continue
                val    = measurements[param_name]
                vmin   = spec.get("min")
                vmax   = spec.get("max")
                passed = True
                mlo = val - vmin if vmin is not None else float('inf')
                mhi = vmax - val if vmax is not None else float('inf')
                if vmin is not None and val < vmin: passed = False
                if vmax is not None and val > vmax: passed = False

                corner_results.append(VERACornerMeasurement(
                    corner=corner_name, process=corner_name.split("_")[0],
                    voltage=0.0, temp=0.0,
                    param_name=param_name, measured=val,
                    unit=spec.get("unit", ""),
                    passed=passed, margin_lo=mlo, margin_hi=mhi
                ))

            if not corner_results:
                continue

            # Find worst-case corner
            worst = min(corner_results, key=lambda x: min(x.margin_lo, x.margin_hi))
            all_pass = all(c.passed for c in corner_results)
            all_vals = [c.measured for c in corner_results]
            fail_corners = [c.corner for c in corner_results if not c.passed]

            r = VERAResultItem(
                ip_name      = self.ip_name,
                checker_name = f"vera_corner_{param_name}",
                checker_type = "post_sim_python_corner",
                layer        = "parametric",
                status       = "PASS" if all_pass else "FAIL",
                severity     = "INFO" if all_pass else "ERROR",
                expected     = f"{spec.get('min','?')} to {spec.get('max','?')} {spec.get('unit','')}",
                actual       = f"worst={worst.measured:.4g} @ {worst.corner} | "
                               f"min={min(all_vals):.4g} max={max(all_vals):.4g}",
                margin       = f"worst_lo={worst.margin_lo:+.4g} worst_hi={worst.margin_hi:+.4g}",
                context      = f"N_corners={len(corner_results)} "
                               f"fail_corners=[{', '.join(fail_corners)}]",
                debug_signal = spec.get("signal", ""),
                recommendation = f"Fix failing corners: {fail_corners}" if not all_pass else ""
            )
            self.reporter.add(r)
            results[param_name] = r

            print(f"\n  Corner Analysis: {param_name}")
            print(f"    Corners checked: {len(corner_results)}")
            print(f"    Worst corner:    {worst.corner} ({worst.measured:.4g} {spec.get('unit','')})")
            print(f"    Status:          {'PASS' if all_pass else 'FAIL'}")
            if fail_corners:
                print(f"    Failed corners:  {fail_corners}")

        return results

    def analyze_monte_carlo(
        self,
        measurements: np.ndarray,    # array of Monte Carlo measurements
        param_name:   str,
        spec:         Dict[str, Any]
    ) -> VERAResultItem:
        """
        Statistical analysis of Monte Carlo simulation results.
        Computes mean, sigma, Cpk, yield estimate, and sigma margins.
        """
        n      = len(measurements)
        mean   = float(np.mean(measurements))
        sigma  = float(np.std(measurements))
        vmin   = spec.get("min")
        vmax   = spec.get("max")
        unit   = spec.get("unit", "")

        # Cpk (process capability index)
        if sigma > 0 and vmin is not None and vmax is not None:
            cpu  = (vmax - mean) / (3 * sigma)   # upper Cpk
            cpl  = (mean - vmin) / (3 * sigma)   # lower Cpk
            cpk  = min(cpu, cpl)
        else:
            cpk = float('nan')

        # Sigma margins
        if sigma > 0:
            sigma_hi = (vmax - mean) / sigma if vmax is not None else float('inf')
            sigma_lo = (mean - vmin) / sigma if vmin is not None else float('inf')
            sigma_margin = min(sigma_hi, sigma_lo)
        else:
            sigma_margin = float('inf')

        # Yield estimate (assuming Gaussian)
        if sigma > 0 and vmin is not None and vmax is not None:
            p_pass = sp_stats.norm.cdf(vmax, mean, sigma) - sp_stats.norm.cdf(vmin, mean, sigma)
            yield_pct = p_pass * 100.0
        else:
            yield_pct = 100.0

        # Pass criteria: Cpk >= 1.33 (6σ) AND mean within spec
        target_cpk  = spec.get("cpk_min", 1.0)
        target_sigma = spec.get("sigma_min", 3.0)
        in_spec_mean = (vmin is None or mean >= vmin) and (vmax is None or mean <= vmax)
        in_spec_cpk  = (not np.isnan(cpk)) and cpk >= target_cpk
        in_spec_sigma = sigma_margin >= target_sigma
        all_pass = in_spec_mean and in_spec_cpk and in_spec_sigma

        print(f"\n  Monte Carlo: {param_name} (N={n})")
        print(f"    Mean ± σ     = {mean:.4g} ± {sigma:.4g} {unit}")
        print(f"    Sigma margin = {sigma_margin:.2f}σ")
        print(f"    Cpk          = {cpk:.3f}")
        print(f"    Yield est.   = {yield_pct:.3f}%")

        r = VERAResultItem(
            ip_name      = self.ip_name,
            checker_name = f"vera_mc_{param_name}",
            checker_type = "post_sim_python_montecarlo",
            layer        = "statistical",
            status       = "PASS" if all_pass else "FAIL",
            severity     = "INFO" if all_pass else "WARNING",
            expected     = f"Cpk >= {target_cpk:.2f}, margin >= {target_sigma:.1f}σ",
            actual       = f"mean={mean:.4g} σ={sigma:.4g} Cpk={cpk:.3f} margin={sigma_margin:.2f}σ",
            margin       = f"yield={yield_pct:.3f}%",
            context      = f"N={n} min={float(np.min(measurements)):.4g} max={float(np.max(measurements)):.4g} {unit}",
            debug_signal = spec.get("signal", ""),
            recommendation = (
                f"Low Cpk={cpk:.2f} — check mismatch sources, process variation, or tighten spec margin"
                if not in_spec_cpk else
                f"Low sigma margin={sigma_margin:.2f}σ — improve circuit robustness"
                if not in_spec_sigma else ""
            )
        )
        self.reporter.add(r)
        return r

    def generate_corner_summary_table(self, param_name: str) -> str:
        """Generate ASCII table of corner results for a parameter."""
        if not self.corner_data:
            return "No corner data loaded."
        rows = []
        header = f"{'Corner':<20} {'Value':>12} {'Status':<8}"
        rows.append(header)
        rows.append("-" * len(header))
        for corner, meas in sorted(self.corner_data.items()):
            val = meas.get(param_name, float('nan'))
            rows.append(f"{corner:<20} {val:>12.4g}  {'—'}")
        return "\n".join(rows)


# =============================================================================
# VERA Yield Optimizer — finds spec margins that maximize yield
# =============================================================================
class VERAYieldAnalyzer:
    """
    Analyzes yield across process corners and Monte Carlo.
    Identifies dominant failure modes and suggests margin optimization.
    """

    def __init__(self, measurements: Dict[str, np.ndarray]):
        """
        measurements: {param_name: array_of_MC_values}
        """
        self.measurements = measurements

    def compute_sensitivity(self) -> Dict[str, float]:
        """
        Returns sigma_margin for each parameter.
        Smallest margin = most critical parameter for yield.
        """
        sensitivity = {}
        for name, vals in self.measurements.items():
            sensitivity[name] = float(np.std(vals)) / max(float(np.mean(vals)), 1e-30)
        return dict(sorted(sensitivity.items(), key=lambda x: -x[1]))

    def yield_vs_spec_tightening(
        self,
        param_name: str,
        center: float,
        sigma: float,
        nom_tol_pct: float,
        steps: int = 10
    ) -> List[Tuple[float, float]]:
        """
        Returns [(tolerance%, yield%)] for tightening spec from nominal.
        Useful for trading spec vs yield.
        """
        from scipy.special import erfc
        results = []
        for i in range(steps):
            tol = nom_tol_pct * (1.0 - i / steps)
            vmin = center * (1 - tol / 100)
            vmax = center * (1 + tol / 100)
            if sigma > 0:
                p = (sp_stats.norm.cdf(vmax, center, sigma) -
                     sp_stats.norm.cdf(vmin, center, sigma)) * 100
            else:
                p = 100.0
            results.append((tol, p))
        return results


# =============================================================================
# CLI entry point
# =============================================================================
def main():
    import argparse
    parser = argparse.ArgumentParser(description="VERA Corner & Monte Carlo Checker")
    parser.add_argument("--spec",       required=True, help="IP spec YAML with corner_checks")
    parser.add_argument("--results_dir", required=True, help="Directory with per-corner JSON reports")
    parser.add_argument("--report",     default="vera_corner_report.json")
    args = parser.parse_args()

    with open(args.spec) as f:
        spec = yaml.safe_load(f)

    reporter = VERAReporter(args.report)
    reporter.sim_meta = {
        "ip_name":     spec.get("ip_name", "UNKNOWN"),
        "analysis":    "corner_and_montecarlo",
        "results_dir": args.results_dir
    }

    chk = VERACornerChecker(reporter, spec.get("ip_name", "UNKNOWN"))
    chk.load_corner_results(args.results_dir)

    param_specs = spec.get("corner_checks", {})
    if param_specs:
        chk.analyze_corners(param_specs)

    reporter.write()


if __name__ == "__main__":
    main()
