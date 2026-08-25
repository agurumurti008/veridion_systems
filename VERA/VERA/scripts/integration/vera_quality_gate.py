#!/usr/bin/env python3
"""
VERA — Verification Engine for Runtime & Autonomous Checking
FILE: scripts/integration/vera_quality_gate.py
DESC: Quality gate checker for CI/CD pipelines.
      Reads VERA JSON reports, enforces pass thresholds,
      generates JUnit XML for Jenkins/GitLab/GitHub Actions,
      posts Slack/Teams alerts on regressions, tracks trends.
VERSION: 1.0
"""

import json
import os
import sys
import glob
import yaml
import argparse
from datetime import datetime
from typing import Any, Dict, List, Optional
from xml.etree import ElementTree as ET


# =============================================================================
# Quality Gate Configuration
# =============================================================================
DEFAULT_GATE_CONFIG = {
    "max_failures":         0,       # zero tolerance
    "max_warnings":         10,
    "min_pass_rate_pct":    95.0,    # at least 95% checks pass
    "required_checkers":    [],      # checker names that MUST appear
    "blocked_checkers":     [],      # checker names that MUST NOT fail
    "severity_block": {
        "ERROR":   True,   # any ERROR → fail gate
        "WARNING": False   # warnings don't fail gate
    }
}


# =============================================================================
# VERA Quality Gate
# =============================================================================
class VERAQualityGate:

    def __init__(self, config: dict = None):
        self.config    = config or DEFAULT_GATE_CONFIG
        self.reports:  List[dict]  = []
        self.all_results: List[dict] = []

    def load_reports(self, report_paths: List[str]):
        for path in report_paths:
            try:
                with open(path) as f:
                    rpt = json.load(f)
                self.reports.append(rpt)
                rr = rpt.get("vera_report", rpt.get("vera_aggregate_report", {}))
                self.all_results.extend(rr.get("results", []))
            except Exception as e:
                print(f"  [VERA Gate] Warning: could not load {path}: {e}")

    @property
    def failures(self): return [r for r in self.all_results if r.get("status") == "FAIL"]
    @property
    def warnings(self): return [r for r in self.all_results if r.get("status") == "WARNING"]
    @property
    def passes(self):   return [r for r in self.all_results if r.get("status") == "PASS"]

    def evaluate(self) -> tuple:
        """Returns (passed: bool, violations: list of str)."""
        violations = []
        n_total    = len(self.all_results)
        n_fail     = len(self.failures)
        n_warn     = len(self.warnings)
        n_pass     = len(self.passes)
        pass_rate  = (n_pass / max(n_total, 1)) * 100.0

        # 1. Max failures
        max_fail = self.config.get("max_failures", 0)
        if n_fail > max_fail:
            violations.append(
                f"FAILURES: {n_fail} > allowed {max_fail}")

        # 2. Max warnings
        max_warn = self.config.get("max_warnings", 999)
        if n_warn > max_warn:
            violations.append(
                f"WARNINGS: {n_warn} > allowed {max_warn}")

        # 3. Minimum pass rate
        min_pass = self.config.get("min_pass_rate_pct", 0.0)
        if pass_rate < min_pass:
            violations.append(
                f"PASS_RATE: {pass_rate:.1f}% < required {min_pass:.1f}%")

        # 4. Required checkers must have run
        for req in self.config.get("required_checkers", []):
            ran = any(r.get("checker_name") == req for r in self.all_results)
            if not ran:
                violations.append(f"MISSING_CHECKER: {req} did not run")

        # 5. Blocked checkers must not fail
        for blocked in self.config.get("blocked_checkers", []):
            failed = any(r.get("checker_name") == blocked and
                         r.get("status") == "FAIL"
                         for r in self.all_results)
            if failed:
                violations.append(f"BLOCKED_CHECKER_FAILED: {blocked}")

        # 6. Severity-based blocking
        if self.config.get("severity_block", {}).get("ERROR", True):
            error_items = [r for r in self.failures
                           if r.get("severity") == "ERROR"]
            if error_items:
                worst = error_items[:3]
                for w in worst:
                    violations.append(
                        f"ERROR: {w.get('ip_name')} | {w.get('checker_name')} "
                        f"| {w.get('actual', '')}")

        gate_passed = (len(violations) == 0)
        return gate_passed, violations

    def print_summary(self):
        n_total   = len(self.all_results)
        n_fail    = len(self.failures)
        n_warn    = len(self.warnings)
        n_pass    = len(self.passes)
        pass_rate = (n_pass / max(n_total, 1)) * 100.0

        print(f"\n{'='*60}")
        print(f"  VERA QUALITY GATE EVALUATION")
        print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*60}")
        print(f"  Total Checks : {n_total}")
        print(f"  PASS         : {n_pass}  ({pass_rate:.1f}%)")
        print(f"  FAIL         : {n_fail}")
        print(f"  WARNING      : {n_warn}")

        if self.failures:
            print(f"\n  FAILURES:")
            for f in self.failures[:10]:
                print(f"    ✗ [{f.get('ip_name')}] {f.get('checker_name')}")
                print(f"      EXP: {f.get('expected','?')}  ACT: {f.get('actual','?')}")
                if f.get('recommendation'):
                    print(f"      → {f.get('recommendation')}")

    def write_junit_xml(self, output_path: str, suite_name: str = "VERA"):
        """Generate JUnit XML for Jenkins/GitLab CI."""
        root     = ET.Element("testsuites")
        suite    = ET.SubElement(root, "testsuite")
        suite.set("name",     suite_name)
        suite.set("tests",    str(len(self.all_results)))
        suite.set("failures", str(len(self.failures)))
        suite.set("warnings", str(len(self.warnings)))
        suite.set("timestamp", datetime.now().isoformat())

        for r in self.all_results:
            case = ET.SubElement(suite, "testcase")
            case.set("name",      r.get("checker_name", "unknown"))
            case.set("classname", r.get("ip_name", "unknown"))
            case.set("time",      "0")

            if r.get("status") == "FAIL":
                fail_el = ET.SubElement(case, "failure")
                fail_el.set("type", r.get("severity", "ERROR"))
                fail_el.set("message",
                    f"Expected: {r.get('expected','')} | Actual: {r.get('actual','')}")
                fail_el.text = (
                    f"IP: {r.get('ip_name','')}\n"
                    f"Checker: {r.get('checker_name','')}\n"
                    f"Expected: {r.get('expected','')}\n"
                    f"Actual: {r.get('actual','')}\n"
                    f"Margin: {r.get('margin','')}\n"
                    f"Signal: {r.get('debug_signal','')}\n"
                    f"Recommendation: {r.get('recommendation','')}"
                )
            elif r.get("status") == "WARNING":
                warn_el = ET.SubElement(case, "system-out")
                warn_el.text = f"WARNING: {r.get('context','')}"

        tree = ET.ElementTree(root)
        ET.indent(tree, space="  ")
        tree.write(output_path, encoding="utf-8", xml_declaration=True)
        print(f"  [VERA Gate] JUnit XML: {output_path}")

    def write_gate_report(self, output_path: str, gate_passed: bool, violations: List[str]):
        """Write quality gate result JSON."""
        report = {
            "vera_quality_gate": {
                "timestamp":    datetime.now().isoformat(),
                "result":       "PASS" if gate_passed else "FAIL",
                "violations":   violations,
                "summary": {
                    "total":    len(self.all_results),
                    "pass":     len(self.passes),
                    "fail":     len(self.failures),
                    "warning":  len(self.warnings),
                    "pass_rate": f"{(len(self.passes)/max(len(self.all_results),1))*100:.1f}%"
                },
                "top_failures": [
                    {
                        "ip":      r.get("ip_name"),
                        "checker": r.get("checker_name"),
                        "actual":  r.get("actual"),
                        "signal":  r.get("debug_signal")
                    }
                    for r in self.failures[:10]
                ]
            }
        }
        with open(output_path, "w") as f:
            json.dump(report, f, indent=2)
        print(f"  [VERA Gate] Gate report: {output_path}")


# =============================================================================
# Slack / Teams Alert (optional integration)
# =============================================================================
def send_slack_alert(webhook_url: str, gate_passed: bool,
                     violations: List[str], report_url: str = ""):
    """Post VERA quality gate result to Slack."""
    try:
        import urllib.request
        color  = "#2eb886" if gate_passed else "#e01e5a"
        status = "✅ PASSED" if gate_passed else "❌ FAILED"
        text   = f"*VERA Quality Gate: {status}*"
        if violations:
            text += "\n" + "\n".join(f"> {v}" for v in violations[:5])
        if report_url:
            text += f"\n<{report_url}|View VERA Dashboard>"
        payload = json.dumps({
            "attachments": [{
                "color":     color,
                "text":      text,
                "mrkdwn_in": ["text"]
            }]
        }).encode()
        req = urllib.request.Request(webhook_url,
                                     data=payload,
                                     headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=5)
        print("  [VERA Gate] Slack alert sent")
    except Exception as e:
        print(f"  [VERA Gate] Slack alert failed: {e}")


# =============================================================================
# GitHub Actions / GitLab CI summary writers
# =============================================================================
def write_github_summary(gate_passed: bool, failures: List[dict],
                         summary_file: str = None):
    """Write to GitHub Actions $GITHUB_STEP_SUMMARY."""
    out = summary_file or os.environ.get("GITHUB_STEP_SUMMARY", "/dev/null")
    try:
        with open(out, "a") as f:
            f.write(f"\n## VERA Quality Gate: {'✅ PASS' if gate_passed else '❌ FAIL'}\n\n")
            if failures:
                f.write("| IP | Checker | Expected | Actual | Signal |\n")
                f.write("|---|---|---|---|---|\n")
                for r in failures[:20]:
                    f.write(f"| {r.get('ip_name','')} "
                            f"| `{r.get('checker_name','')}` "
                            f"| {r.get('expected','')} "
                            f"| {r.get('actual','')} "
                            f"| `{r.get('debug_signal','')}` |\n")
            else:
                f.write("All VERA checks passed! 🎉\n")
        print(f"  [VERA Gate] GitHub summary written to {out}")
    except Exception as e:
        print(f"  [VERA Gate] GitHub summary failed: {e}")


# =============================================================================
# CLI
# =============================================================================
def main():
    parser = argparse.ArgumentParser(
        description="VERA Quality Gate — CI/CD integration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic gate check
  python3 vera_quality_gate.py --reports vera_reports/*.json

  # With JUnit XML for Jenkins
  python3 vera_quality_gate.py --reports vera_reports/*.json --junit vera_junit.xml

  # With gate config YAML
  python3 vera_quality_gate.py --reports vera_reports/*.json --config gate_config.yaml

  # With Slack notification
  python3 vera_quality_gate.py --reports vera_reports/*.json \\
    --slack https://hooks.slack.com/services/xxx
        """
    )
    parser.add_argument("--reports",    nargs="+", required=True, help="VERA JSON report files")
    parser.add_argument("--config",     help="Gate config YAML (optional)")
    parser.add_argument("--junit",      help="JUnit XML output path")
    parser.add_argument("--gate_report", default="vera_gate_result.json")
    parser.add_argument("--slack",      help="Slack webhook URL")
    parser.add_argument("--gh_summary", help="GitHub Actions summary file")
    args = parser.parse_args()

    # Load gate config
    config = DEFAULT_GATE_CONFIG.copy()
    if args.config and os.path.exists(args.config):
        with open(args.config) as f:
            config.update(yaml.safe_load(f) or {})

    # Run gate
    gate = VERAQualityGate(config)

    # Expand globs
    report_files = []
    for pattern in args.reports:
        expanded = glob.glob(pattern)
        report_files.extend(expanded if expanded else [pattern])

    gate.load_reports(report_files)
    gate_passed, violations = gate.evaluate()
    gate.print_summary()

    # Output artifacts
    if args.junit:
        gate.write_junit_xml(args.junit)

    gate.write_gate_report(args.gate_report, gate_passed, violations)

    if args.slack:
        send_slack_alert(args.slack, gate_passed, violations)

    if args.gh_summary:
        write_github_summary(gate_passed, gate.failures, args.gh_summary)

    print(f"\n  VERA Quality Gate: {'✅ PASSED' if gate_passed else '❌ FAILED'}")
    if violations:
        print(f"\n  Violations:")
        for v in violations:
            print(f"    • {v}")

    sys.exit(0 if gate_passed else 1)


if __name__ == "__main__":
    main()
