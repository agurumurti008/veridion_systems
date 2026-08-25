#!/usr/bin/env python3
"""
VERA — Verification Engine for Runtime & Autonomous Checking
FILE: automation/builder/vera_builder.py
DESC: Auto-Checker Builder — reads IP spec YAML and generates:
      - SVA assertion files (.sv)
      - Python post-sim checker config (.py)
      - SKILL checker script (.il)
      - UVM scoreboard bind file (.sv)
      - VERA configuration YAML
VERSION: 1.0
"""

import yaml
import os
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List, Optional


# =============================================================================
# Template Registry — maps IP type to checker strategies
# =============================================================================
IP_CHECKER_MAP = {
    "adc":        ["parametric", "dynamic_fft", "static_dnl_inl", "digital_if_sva"],
    "dac":        ["parametric", "dynamic_fft", "digital_if_sva"],
    "pll":        ["parametric", "lock_time", "jitter", "frequency", "digital_sva"],
    "ldo":        ["parametric", "load_transient", "psrr", "line_reg"],
    "opamp":      ["parametric", "ac_gain", "bandwidth", "phase_margin", "slew"],
    "comparator": ["parametric", "propagation_delay", "offset", "hysteresis"],
    "uart":       ["protocol_sva", "parametric"],
    "spi":        ["protocol_sva", "parametric"],
    "i2c":        ["protocol_sva", "parametric"],
    "axi4":       ["protocol_sva", "parametric"],
    "apb":        ["protocol_sva", "parametric"],
    "fifo":       ["structural_sva", "parametric"],
    "sram":       ["functional_uvm", "parametric"],
    "generic":    ["parametric"],
}

SEVERITY_MAP = {"error": "ERROR", "warning": "WARNING", "info": "INFO"}


# =============================================================================
# VERA Spec Loader & Validator
# =============================================================================
class VERASpecLoader:
    REQUIRED_FIELDS = ["ip_name", "ip_type", "environment"]

    def __init__(self, spec_path: str):
        with open(spec_path) as f:
            self.spec = yaml.safe_load(f)
        self._validate()
        self.ip_name = self.spec["ip_name"]
        self.ip_type = self.spec["ip_type"].lower()
        self.env     = self.spec["environment"].lower()  # "dms", "ams", "mixed"

    def _validate(self):
        missing = [f for f in self.REQUIRED_FIELDS if f not in self.spec]
        if missing:
            raise ValueError(f"VERA Spec missing required fields: {missing}")

    def get(self, *keys, default=None):
        d = self.spec
        for k in keys:
            if isinstance(d, dict) and k in d:
                d = d[k]
            else:
                return default
        return d


# =============================================================================
# SVA Generator — produces SystemVerilog assertion file
# =============================================================================
class VERASVAGenerator:

    def __init__(self, spec: VERASpecLoader, output_dir: str):
        self.spec       = spec
        self.output_dir = output_dir
        self.ip         = spec.ip_name
        self.ip_type    = spec.ip_type
        os.makedirs(output_dir, exist_ok=True)

    def generate(self) -> str:
        lines = [
            f"// {'='*72}",
            f"// VERA Auto-Generated SVA Checker",
            f"// IP: {self.ip}  Type: {self.ip_type.upper()}",
            f"// Generated: {datetime.now().isoformat()}",
            f"// DO NOT EDIT MANUALLY — Regenerate via vera_builder.py",
            f"// {'='*72}",
            "",
            f"`ifndef VERA_{self.ip.upper()}_SVA_SV",
            f"`define VERA_{self.ip.upper()}_SVA_SV",
            "",
            f"// Import VERA SVA Library",
            "`include \"vera_sva_library.sv\"",
            "",
        ]

        # Generate appropriate checker instantiation based on IP type
        if self.ip_type in ("uart",):
            lines += self._gen_uart_checker()
        elif self.ip_type in ("spi",):
            lines += self._gen_spi_checker()
        elif self.ip_type in ("fifo",):
            lines += self._gen_fifo_checker()
        elif self.ip_type in ("pll", "adc", "dac"):
            lines += self._gen_clk_checker()
        else:
            lines += self._gen_generic_checker()

        # Always add parametric bound assertions
        lines += self._gen_parametric_assertions()

        lines += ["", f"`endif // VERA_{self.ip.upper()}_SVA_SV", ""]

        out_path = os.path.join(self.output_dir, f"vera_{self.ip.lower()}_sva.sv")
        with open(out_path, "w") as f:
            f.write("\n".join(lines))
        print(f"  [VERA Builder] Generated SVA: {out_path}")
        return out_path

    def _gen_uart_checker(self) -> List[str]:
        baud_div   = self.spec.get("uart", "baud_div")   or 16
        data_bits  = self.spec.get("uart", "data_bits")  or 8
        stop_bits  = self.spec.get("uart", "stop_bits")  or 1
        parity     = self.spec.get("uart", "parity")     or "NONE"
        return [
            f"// UART Protocol Checker",
            f"vera_uart_checker #(",
            f"  .IP_NAME   (\"{self.ip}\"),",
            f"  .BAUD_DIV  ({baud_div}),",
            f"  .DATA_BITS ({data_bits}),",
            f"  .STOP_BITS ({stop_bits}),",
            f"  .PARITY    (\"{parity}\")",
            f") i_vera_uart_chk (",
            f"  .clk   (clk),",
            f"  .rst_n (rst_n),",
            f"  .rx    (uart_rx),",
            f"  .tx    (uart_tx)",
            f");",
            "",
        ]

    def _gen_spi_checker(self) -> List[str]:
        cpol       = self.spec.get("spi", "cpol") or 0
        cpha       = self.spec.get("spi", "cpha") or 0
        word_size  = self.spec.get("spi", "word_size") or 8
        return [
            f"// SPI Protocol Checker",
            f"vera_spi_checker #(",
            f"  .IP_NAME   (\"{self.ip}\"),",
            f"  .CPOL      ({cpol}),",
            f"  .CPHA      ({cpha}),",
            f"  .WORD_SIZE ({word_size})",
            f") i_vera_spi_chk (",
            f"  .sclk  (spi_sclk),",
            f"  .cs_n  (spi_cs_n),",
            f"  .mosi  (spi_mosi),",
            f"  .miso  (spi_miso),",
            f"  .rst_n (rst_n)",
            f");",
            "",
        ]

    def _gen_fifo_checker(self) -> List[str]:
        depth    = self.spec.get("fifo", "depth")    or 16
        hi_water = self.spec.get("fifo", "hi_water") or int(depth * 0.75)
        lo_water = self.spec.get("fifo", "lo_water") or int(depth * 0.25)
        return [
            f"// FIFO Structural Checker",
            f"vera_fifo_checker #(",
            f"  .IP_NAME  (\"{self.ip}\"),",
            f"  .DEPTH    ({depth}),",
            f"  .HI_WATER ({hi_water}),",
            f"  .LO_WATER ({lo_water})",
            f") i_vera_fifo_chk (",
            f"  .clk   (clk),",
            f"  .rst_n (rst_n),",
            f"  .push  (fifo_push),",
            f"  .pop   (fifo_pop),",
            f"  .full  (fifo_full),",
            f"  .empty (fifo_empty),",
            f"  .count (fifo_count)",
            f");",
            "",
        ]

    def _gen_clk_checker(self) -> List[str]:
        freq_mhz  = self.spec.get("clock", "freq_mhz") or 100.0
        period_ns = 1000.0 / freq_mhz
        freq_tol  = self.spec.get("clock", "freq_tol") or 0.05
        return [
            f"// Clock Checker",
            f"vera_clk_checker #(",
            f"  .IP_NAME    (\"{self.ip}\"),",
            f"  .CLK_PERIOD ({period_ns}),",
            f"  .FREQ_TOL   ({freq_tol})",
            f") i_vera_clk_chk (",
            f"  .clk    (clk_out),",
            f"  .rst_n  (rst_n),",
            f"  .enable (1'b1)",
            f");",
            "",
        ]

    def _gen_generic_checker(self) -> List[str]:
        return [
            f"// Generic Reset Checker",
            f"vera_reset_checker #(",
            f"  .IP_NAME       (\"{self.ip}\"),",
            f"  .MIN_RST_WIDTH (4)",
            f") i_vera_rst_chk (",
            f"  .clk (clk),",
            f"  .rst (rst_n)",
            f");",
            "",
        ]

    def _gen_parametric_assertions(self) -> List[str]:
        """Generate SVA assertions for digital parametric bounds."""
        lines = []
        bounds = self.spec.get("digital_bounds") or []
        if not bounds:
            return lines
        lines.append(f"// Auto-generated parametric assertions from spec")
        lines.append(f"module vera_{self.ip.lower()}_param_chk (")
        lines.append(f"  input logic clk,")
        lines.append(f"  input logic rst_n")
        # Add signals from bounds
        for b in bounds:
            sig = b.get("signal", "sig")
            w   = b.get("width", 1)
            lines.append(f"  , input logic [{w-1}:0] {sig}")
        lines.append(f");")
        lines.append("")
        for b in bounds:
            sig      = b.get("signal", "sig")
            min_val  = b.get("min")
            max_val  = b.get("max")
            chk_name = f"vera_{self.ip.lower()}_{sig}_range"
            if min_val is not None and max_val is not None:
                lines += [
                    f"  property p_{sig}_range;",
                    f"    @(posedge clk) disable iff (!rst_n)",
                    f"    {sig} inside {{[{min_val}:{max_val}]}};",
                    f"  endproperty",
                    f"  {chk_name.upper()}: assert property (p_{sig}_range)",
                    f"    else $error(\"VERA_FAIL | IP={self.ip} | CHECK={chk_name} | %s out of range [%0d,%0d] actual=%0d\",",
                    f"               \"{sig}\", {min_val}, {max_val}, {sig});",
                    "",
                ]
        lines += ["endmodule", ""]
        return lines


# =============================================================================
# Python Config Generator — produces spec YAML for post-sim checker
# =============================================================================
class VERAPythonConfigGenerator:

    def __init__(self, spec: VERASpecLoader, output_dir: str):
        self.spec       = spec
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def generate(self) -> str:
        config = {
            "ip_name":  self.spec.ip_name,
            "ip_type":  self.spec.ip_type,
        }
        # Copy IP-specific sections
        for section in ["adc", "pll", "ldo", "opamp", "parametric_checks"]:
            val = self.spec.get(section)
            if val:
                config[section] = val
        out_path = os.path.join(self.output_dir, f"vera_{self.spec.ip_name.lower()}_postsim.yaml")
        with open(out_path, "w") as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)
        print(f"  [VERA Builder] Generated Python config: {out_path}")
        return out_path


# =============================================================================
# SKILL Generator — produces OCEAN checker script
# =============================================================================
class VERASKILLGenerator:

    def __init__(self, spec: VERASpecLoader, output_dir: str):
        self.spec       = spec
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def generate(self) -> str:
        lines = [
            f"; {'='*72}",
            f"; VERA Auto-Generated SKILL Checker",
            f"; IP: {self.spec.ip_name}  Type: {self.spec.ip_type.upper()}",
            f"; Generated: {datetime.now().isoformat()}",
            f"; {'='*72}",
            "",
            f"; Load VERA SKILL library",
            f"load(\"vera_ams_checkers.il\")",
            "",
            f"veraSetIP(\"{self.spec.ip_name}\" \"auto_generated_checks\")",
            "",
        ]

        if self.spec.ip_type == "opamp":
            lines += self._gen_opamp_checks()
        elif self.spec.ip_type == "ldo":
            lines += self._gen_ldo_checks()
        elif self.spec.ip_type == "adc":
            lines += self._gen_adc_ams_checks()
        else:
            lines += self._gen_generic_ams_checks()

        lines += ["", f"veraWriteReport()", ""]

        out_path = os.path.join(self.output_dir, f"vera_{self.spec.ip_name.lower()}_ams.il")
        with open(out_path, "w") as f:
            f.write("\n".join(lines))
        print(f"  [VERA Builder] Generated SKILL: {out_path}")
        return out_path

    def _gen_opamp_checks(self) -> List[str]:
        s = self.spec.get("opamp") or {}
        return [
            f"; Op-Amp Checks",
            f"veraCheckAcGain(\"/vout\" \"/vin\" 1000 {s.get('gain_min_db', 60)} {s.get('gain_max_db', 200)})",
            f"veraCheckAcBW(\"/vout\" \"/vin\" {s.get('bw_min_hz', 1e6)} {s.get('bw_max_hz', 1e9)})",
            f"veraCheckDcVoltage(\"/vout\" {s.get('vout_min_v', 0)} {s.get('vout_max_v', 1.8)})",
            f"veraCheckSlew(\"/vout\" t {s.get('slew_min_vus', 1)} {s.get('slew_max_vus', 1000)})",
            "",
        ]

    def _gen_ldo_checks(self) -> List[str]:
        s = self.spec.get("ldo") or {}
        return [
            f"; LDO Checks",
            f"veraCheckDcVoltage(\"/vout\" {s.get('vout_min_v', 1.75)} {s.get('vout_max_v', 1.85)})",
            f"veraCheckPSRR(\"/vout\" \"/vdd\" 1000 {s.get('psrr_min_db', 40)})",
            "",
        ]

    def _gen_adc_ams_checks(self) -> List[str]:
        s = self.spec.get("adc") or {}
        return [
            f"; ADC AMS-level Checks",
            f"veraCheckDcVoltage(\"/vref\" {s.get('vref_min_v', 1.79)} {s.get('vref_max_v', 1.81)})",
            f"veraCheckParam(\"vera_adc_input_range\" value(getData(\"/vin\") 0) {s.get('vin_min_v', 0)} {s.get('vin_max_v', 1.8)} \"V\" \"/vin\" \"input range\")",
            "",
        ]

    def _gen_generic_ams_checks(self) -> List[str]:
        checks = self.spec.get("ams_checks") or []
        lines  = ["; Generic AMS Parametric Checks"]
        for c in checks:
            lines.append(
                f"veraCheckParam(\"{c.get('name')}\" value(getData(\"{c.get('signal')}\") 0) "
                f"{c.get('min')} {c.get('max')} \"{c.get('unit','')}\" "
                f"\"{c.get('signal')}\" \"{c.get('context','')}\")"
            )
        return lines


# =============================================================================
# VERA Builder — top-level orchestrator
# =============================================================================
class VERABuilder:

    def __init__(self, spec_path: str, output_dir: str, env: str = None):
        self.spec_loader = VERASpecLoader(spec_path)
        self.output_dir  = output_dir
        if env:
            self.spec_loader.spec["environment"] = env
        os.makedirs(output_dir, exist_ok=True)

    def build(self):
        spec    = self.spec_loader
        ip      = spec.ip_name
        ip_type = spec.ip_type
        env     = spec.env

        print(f"\n{'='*60}")
        print(f"  VERA Auto-Builder")
        print(f"  IP: {ip}  Type: {ip_type.upper()}  Env: {env.upper()}")
        print(f"  Output: {self.output_dir}")
        print(f"{'='*60}\n")

        generated = {}

        # SVA (for digital or mixed-signal digital interface)
        if env in ("dms", "mixed") or ip_type in VERA_DIGITAL_IPS():
            sva_dir = os.path.join(self.output_dir, "sva")
            gen = VERASVAGenerator(spec, sva_dir)
            generated["sva"] = gen.generate()

        # Python post-sim config
        if env in ("ams", "mixed") or ip_type in VERA_ANALOG_IPS():
            py_dir = os.path.join(self.output_dir, "python")
            gen    = VERAPythonConfigGenerator(spec, py_dir)
            generated["python_config"] = gen.generate()

        # SKILL AMS checker (Cadence only)
        if env in ("ams", "mixed"):
            sk_dir = os.path.join(self.output_dir, "skill")
            gen    = VERASKILLGenerator(spec, sk_dir)
            generated["skill"] = gen.generate()

        # Write build manifest
        manifest = {
            "vera_version":  "1.0",
            "build_time":    datetime.now().isoformat(),
            "ip_name":       ip,
            "ip_type":       ip_type,
            "environment":   env,
            "generated_files": generated
        }
        manifest_path = os.path.join(self.output_dir, "vera_build_manifest.json")
        with open(manifest_path, "w") as f:
            json.dump(manifest, f, indent=2)

        print(f"\n  VERA Build Complete!")
        print(f"  Files generated: {len(generated)}")
        print(f"  Manifest: {manifest_path}\n")
        return generated


def VERA_DIGITAL_IPS():
    return {"uart", "spi", "i2c", "axi4", "apb", "ahb", "fifo", "sram"}

def VERA_ANALOG_IPS():
    return {"adc", "dac", "pll", "ldo", "opamp", "comparator", "bandgap"}


# =============================================================================
# CLI Entry Point
# =============================================================================
def main():
    parser = argparse.ArgumentParser(
        description="VERA Auto-Builder: Generate checker suite from IP spec YAML",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 vera_builder.py --spec examples/adc/adc_spec.yaml --output output/adc/
  python3 vera_builder.py --spec examples/pll/pll_spec.yaml --env mixed --output output/pll/
  python3 vera_builder.py --spec examples/uart/uart_spec.yaml --env dms --output output/uart/
        """
    )
    parser.add_argument("--spec",    required=True, help="IP specification YAML file")
    parser.add_argument("--output",  required=True, help="Output directory for generated checkers")
    parser.add_argument("--env",     choices=["dms", "ams", "mixed"], help="Override environment")
    args = parser.parse_args()

    builder = VERABuilder(args.spec, args.output, args.env)
    builder.build()


if __name__ == "__main__":
    main()
