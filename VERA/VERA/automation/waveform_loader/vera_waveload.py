#!/usr/bin/env python3
"""
VERA — Verification Engine for Runtime & Autonomous Checking
FILE: automation/waveform_loader/vera_waveload.py
DESC: Automated waveform loader generator.
      Reads VERA JSON report, finds failures, generates tool-specific
      waveform loading scripts (SimVision/nWave/GTKWave/DVE) with signals
      pre-loaded and anchored to failure times.
VERSION: 1.0
"""

import json
import os
import sys
import argparse
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime


# =============================================================================
# Tool-specific waveform script generators
# =============================================================================

class SimVisionLoader:
    """Generates Cadence SimVision (.tcl) waveform scripts."""

    def generate(self, failures: List[dict], fsdb_dir: str,
                 sim_id: str, output_path: str):
        lines = [
            f"# VERA Waveform Loader — SimVision",
            f"# Generated: {datetime.now().isoformat()}",
            f"# Failures: {len(failures)}",
            "",
            f"# Open waveform database",
            f"database open -shm {fsdb_dir}/{sim_id}.shm",
            "",
            f"# Create VERA failure windows",
        ]
        for i, fail in enumerate(failures):
            win_name = f"vera_fail_{i+1}_{fail.get('checker_name', 'unknown')[:30]}"
            t_anchor = fail.get("waveform_anchor_time") or fail.get("time_ns")
            signals  = self._extract_signals(fail)

            lines += [
                f"",
                f"# --- Failure {i+1}: {fail.get('checker_name')} ---",
                f"window new WaveWindow -name {{{win_name}}}",
                f"waveform add -signals {{",
            ]
            for sig in signals:
                lines.append(f"  {sig}")
            lines += [
                f"}}",
            ]
            if t_anchor:
                lines += [
                    f"# Anchor to failure time: {t_anchor} ns",
                    f"waveform cursor set -time {{{t_anchor}ns}}",
                    f"waveform zoom -around cursor -factor 10",
                ]
            lines += [
                f"# Context: {fail.get('context', '')}",
                f"# Expected: {fail.get('expected', '')}",
                f"# Actual: {fail.get('actual', '')}",
                f"# Recommendation: {fail.get('recommendation', '')}",
            ]

        lines += [
            "",
            f"# VERA Summary: {len(failures)} failures loaded",
            f"puts \"VERA: {len(failures)} failure(s) loaded. Check waveform windows above.\"",
        ]
        with open(output_path, "w") as f:
            f.write("\n".join(lines))
        return output_path

    def _extract_signals(self, fail: dict) -> List[str]:
        sigs = []
        if fail.get("debug_signal"):
            sigs.append(fail["debug_signal"])
        # Add related signals based on checker type
        chk = fail.get("checker_name", "")
        if "clk" in chk or "freq" in chk:
            sigs += ["/tb/clk", "/tb/rst_n"]
        elif "uart" in chk:
            sigs += ["/tb/dut/uart_rx", "/tb/dut/uart_tx", "/tb/clk"]
        elif "fifo" in chk:
            sigs += ["/tb/dut/fifo_push", "/tb/dut/fifo_pop",
                     "/tb/dut/fifo_full", "/tb/dut/fifo_empty",
                     "/tb/dut/fifo_count", "/tb/clk"]
        elif "axi" in chk:
            sigs += ["/tb/dut/awvalid", "/tb/dut/awready",
                     "/tb/dut/wvalid", "/tb/dut/wready",
                     "/tb/dut/bvalid", "/tb/dut/bready", "/tb/clk"]
        elif "adc" in chk:
            sigs += ["/tb/dut/adc_out", "/tb/dut/sample_clk",
                     "/tb/vin_analog"]
        elif "pll" in chk:
            sigs += ["/tb/dut/pll_clkout", "/tb/dut/pll_locked",
                     "/tb/dut/vco_ctrl"]
        if not sigs:
            sigs = ["/tb/clk", "/tb/rst_n"]
        return list(dict.fromkeys(sigs))  # dedup


class NWaveLoader:
    """Generates Novas/Verdi nWave (.rc) commands."""

    def generate(self, failures: List[dict], fsdb_dir: str,
                 sim_id: str, output_path: str):
        lines = [
            f"// VERA Waveform Loader — nWave/Verdi",
            f"// Generated: {datetime.now().isoformat()}",
            "",
            f"novas::open_database -design {fsdb_dir}/{sim_id}.fsdb",
            "",
        ]
        for i, fail in enumerate(failures):
            t_anchor = fail.get("waveform_anchor_time") or fail.get("time_ns")
            chk      = fail.get("checker_name", f"fail_{i+1}")
            sigs     = SimVisionLoader()._extract_signals(fail)

            lines += [
                f"// Failure {i+1}: {chk}",
                f"nWave::add_wave -signals {{{' '.join(sigs)}}}",
            ]
            if t_anchor:
                lines.append(f"nWave::goto_time -time {t_anchor}ns")
            lines.append(f"")

        with open(output_path, "w") as f:
            f.write("\n".join(lines))
        return output_path


class GTKWaveLoader:
    """Generates GTKWave save file (.gtkw) for open-source tools."""

    def generate(self, failures: List[dict], fsdb_dir: str,
                 sim_id: str, output_path: str):
        # GTKWave save file format
        lines = [
            f"[*] VERA GTKWave Loader",
            f"[*] Generated: {datetime.now().isoformat()}",
            f"[*] {len(failures)} failure(s)",
            f"[dumpfile] \"{fsdb_dir}/{sim_id}.vcd\"",
            f"[timestart] 0",
            "",
        ]
        for i, fail in enumerate(failures):
            t_anchor = fail.get("waveform_anchor_time") or fail.get("time_ns")
            sigs     = SimVisionLoader()._extract_signals(fail)
            lines.append(f"----- Failure {i+1}: {fail.get('checker_name', '')} -----")
            for sig in sigs:
                # GTKWave uses last component as signal name
                lines.append(sig.replace("/", ".").lstrip("."))
            if t_anchor:
                lines.append(f"[marker] {int(float(t_anchor) * 1000)}")  # ns→ps
            lines.append("")

        with open(output_path, "w") as f:
            f.write("\n".join(lines))
        return output_path


class DVELoader:
    """Generates Synopsys DVE/Verdi .tcl script."""

    def generate(self, failures: List[dict], fsdb_dir: str,
                 sim_id: str, output_path: str):
        lines = [
            f"# VERA Waveform Loader — DVE",
            f"# Generated: {datetime.now().isoformat()}",
            "",
            f"gui_open_db -file {fsdb_dir}/{sim_id}.vpd",
            "gui_list_create",
            "",
        ]
        for i, fail in enumerate(failures):
            t_anchor = fail.get("waveform_anchor_time") or fail.get("time_ns")
            sigs     = SimVisionLoader()._extract_signals(fail)
            lines.append(f"# Failure {i+1}: {fail.get('checker_name', '')}")
            for sig in sigs:
                lines.append(f"gui_wave_create -signals {{{sig}}}")
            if t_anchor:
                lines.append(f"gui_cursor_set -time {{{t_anchor}ns}}")
            lines.append("")

        with open(output_path, "w") as f:
            f.write("\n".join(lines))
        return output_path


# =============================================================================
# VERA Waveform Loader Orchestrator
# =============================================================================

TOOL_GENERATORS = {
    "simvision": (SimVisionLoader, "vera_waveload_simvision.tcl"),
    "nwave":     (NWaveLoader,     "vera_waveload_nwave.rc"),
    "verdi":     (NWaveLoader,     "vera_waveload_verdi.rc"),
    "gtkwave":   (GTKWaveLoader,   "vera_waveload.gtkw"),
    "dve":       (DVELoader,       "vera_waveload_dve.tcl"),
}


class VERAWaveformLoader:

    def __init__(self, report_path: str, fsdb_dir: str,
                 tool: str = "simvision", output_dir: str = "."):
        with open(report_path) as f:
            self.report = json.load(f)
        self.fsdb_dir   = fsdb_dir
        self.tool       = tool.lower()
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

        # Extract failures
        results = self.report.get("vera_report", {}).get("results", [])
        self.failures = [r for r in results if r.get("status") == "FAIL"]
        self.sim_id   = self.report.get("vera_report", {}).get(
            "meta", {}).get("simulation_id", "sim_run")

    def generate(self):
        if not self.failures:
            print("  [VERA Waveform Loader] No failures found in report.")
            return []

        print(f"\n  [VERA Waveform Loader] Found {len(self.failures)} failures")
        print(f"  Tool: {self.tool.upper()}")

        generated = []

        if self.tool == "all":
            tools = list(TOOL_GENERATORS.keys())
        else:
            tools = [self.tool]

        for tool in tools:
            if tool not in TOOL_GENERATORS:
                print(f"  [VERA] Unknown tool: {tool}. Options: {list(TOOL_GENERATORS.keys())}")
                continue
            gen_cls, filename = TOOL_GENERATORS[tool]
            gen  = gen_cls()
            path = os.path.join(self.output_dir, filename)
            out  = gen.generate(self.failures, self.fsdb_dir, self.sim_id, path)
            generated.append(out)
            print(f"  Generated: {out}")

        # Also write a human-readable failure summary
        summary_path = os.path.join(self.output_dir, "vera_failure_summary.txt")
        self._write_summary(summary_path)
        generated.append(summary_path)

        return generated

    def _write_summary(self, path: str):
        with open(path, "w") as f:
            f.write("=" * 70 + "\n")
            f.write("VERA FAILURE SUMMARY\n")
            f.write(f"Generated: {datetime.now().isoformat()}\n")
            f.write(f"Total Failures: {len(self.failures)}\n")
            f.write("=" * 70 + "\n\n")
            for i, fail in enumerate(self.failures, 1):
                f.write(f"[{i}] {fail.get('checker_name', 'unknown')}\n")
                f.write(f"     IP:         {fail.get('ip_name', '')}\n")
                f.write(f"     Type:       {fail.get('checker_type', '')}\n")
                f.write(f"     Expected:   {fail.get('expected', '')}\n")
                f.write(f"     Actual:     {fail.get('actual', '')}\n")
                f.write(f"     Margin:     {fail.get('margin', '')}\n")
                f.write(f"     Time(ns):   {fail.get('waveform_anchor_time') or fail.get('time_ns', 'N/A')}\n")
                f.write(f"     Signal:     {fail.get('debug_signal', '')}\n")
                f.write(f"     Context:    {fail.get('context', '')}\n")
                f.write(f"     Fix Hint:   {fail.get('recommendation', '')}\n")
                f.write("\n")


# =============================================================================
# CLI
# =============================================================================
def main():
    parser = argparse.ArgumentParser(description="VERA Waveform Loader Generator")
    parser.add_argument("--report",  required=True, help="VERA JSON report file")
    parser.add_argument("--fsdb_dir", default=".",  help="Directory with waveform databases")
    parser.add_argument("--tool",    default="simvision",
                        choices=["simvision", "nwave", "verdi", "gtkwave", "dve", "all"],
                        help="Target waveform viewer")
    parser.add_argument("--output",  default="vera_waveload_scripts",
                        help="Output directory for loader scripts")
    args = parser.parse_args()

    loader = VERAWaveformLoader(args.report, args.fsdb_dir, args.tool, args.output)
    scripts = loader.generate()
    print(f"\n  VERA Waveform Loader: {len(scripts)} script(s) generated")
    print(f"  Run the appropriate script in your waveform viewer to debug failures\n")


if __name__ == "__main__":
    main()
