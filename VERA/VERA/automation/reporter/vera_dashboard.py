#!/usr/bin/env python3
"""
VERA — Verification Engine for Runtime & Autonomous Checking
FILE: automation/reporter/vera_dashboard.py
DESC: VERA Report Engine — generates rich HTML dashboard from JSON reports.
      Also serves as a local HTTP dashboard server for live regression views.
VERSION: 1.0
"""

import json
import os
import sys
import argparse
import glob
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from typing import Any, Dict, List, Optional


# =============================================================================
# VERA HTML Report Generator
# =============================================================================
class VERAHTMLReporter:

    def __init__(self, report_data: dict):
        self.data    = report_data
        self.summary = report_data.get("vera_report", {}).get("summary", {})
        self.results = report_data.get("vera_report", {}).get("results", [])
        self.meta    = report_data.get("vera_report", {}).get("meta", {})

        self.failures = [r for r in self.results if r.get("status") == "FAIL"]
        self.warnings = [r for r in self.results if r.get("status") == "WARNING"]
        self.passes   = [r for r in self.results if r.get("status") == "PASS"]

    def generate(self, output_path: str):
        html = self._build_html()
        with open(output_path, "w") as f:
            f.write(html)
        print(f"  [VERA Reporter] HTML report: {output_path}")
        return output_path

    def _build_html(self) -> str:
        total     = self.summary.get("total", len(self.results))
        passes    = self.summary.get("pass", len(self.passes))
        fails     = self.summary.get("fail", len(self.failures))
        warns     = self.summary.get("warning", len(self.warnings))
        pass_rate = f"{100*passes/max(total,1):.1f}%"
        ip_name   = self.meta.get("ip_name", "UNKNOWN")
        ts        = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Group failures by IP and type
        by_type: Dict[str, List] = defaultdict(list)
        for r in self.failures:
            by_type[r.get("checker_type", "unknown")].append(r)

        # Build failure rows
        fail_rows = ""
        for r in self.failures:
            t_anchor = r.get("waveform_anchor_time") or r.get("time_ns", "")
            fail_rows += f"""
            <tr class="fail-row">
              <td><span class="badge fail">FAIL</span></td>
              <td><code>{r.get('ip_name','')}</code></td>
              <td><strong>{r.get('checker_name','')}</strong></td>
              <td><span class="tag">{r.get('checker_type','')}</span></td>
              <td>{r.get('expected','')}</td>
              <td class="actual-fail">{r.get('actual','')}</td>
              <td>{r.get('margin','')}</td>
              <td>{t_anchor}</td>
              <td><code class="signal">{r.get('debug_signal','')}</code></td>
              <td class="recommendation">{r.get('recommendation','')}</td>
            </tr>"""

        warn_rows = ""
        for r in self.warnings:
            warn_rows += f"""
            <tr class="warn-row">
              <td><span class="badge warn">WARN</span></td>
              <td><code>{r.get('ip_name','')}</code></td>
              <td>{r.get('checker_name','')}</td>
              <td><span class="tag">{r.get('checker_type','')}</span></td>
              <td>{r.get('expected','')}</td>
              <td>{r.get('actual','')}</td>
              <td colspan="4">{r.get('context','')}</td>
            </tr>"""

        pass_rows = ""
        for r in self.passes[:50]:  # Cap at 50 for HTML size
            pass_rows += f"""
            <tr class="pass-row">
              <td><span class="badge pass">PASS</span></td>
              <td><code>{r.get('ip_name','')}</code></td>
              <td>{r.get('checker_name','')}</td>
              <td><span class="tag">{r.get('checker_type','')}</span></td>
              <td>{r.get('expected','')}</td>
              <td>{r.get('actual','')}</td>
              <td colspan="4">{r.get('margin','')}</td>
            </tr>"""

        # Type distribution for chart
        type_counts = defaultdict(int)
        for r in self.results:
            type_counts[r.get("checker_type","unknown")] += 1
        type_labels = json.dumps(list(type_counts.keys()))
        type_data   = json.dumps(list(type_counts.values()))

        status_data = json.dumps([passes, fails, warns])

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>VERA Report — {ip_name}</title>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.0/chart.umd.min.js"></script>
  <style>
    :root {{
      --bg:        #0d1117;
      --bg2:       #161b22;
      --bg3:       #21262d;
      --border:    #30363d;
      --text:      #e6edf3;
      --text2:     #8b949e;
      --green:     #3fb950;
      --red:       #f85149;
      --yellow:    #d29922;
      --blue:      #58a6ff;
      --purple:    #bc8cff;
      --cyan:      #39d353;
      --font:      'Courier New', monospace;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      background: var(--bg);
      color: var(--text);
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      font-size: 14px;
      line-height: 1.5;
    }}
    /* Header */
    .vera-header {{
      background: linear-gradient(135deg, #161b22 0%, #0d1117 100%);
      border-bottom: 1px solid var(--border);
      padding: 24px 32px;
      display: flex;
      align-items: center;
      justify-content: space-between;
    }}
    .vera-logo {{
      display: flex;
      align-items: center;
      gap: 16px;
    }}
    .vera-logo-icon {{
      width: 48px; height: 48px;
      background: linear-gradient(135deg, #58a6ff, #bc8cff);
      border-radius: 12px;
      display: flex; align-items: center; justify-content: center;
      font-size: 24px; font-weight: 900; color: white;
    }}
    .vera-title {{ font-size: 22px; font-weight: 700; color: var(--text); }}
    .vera-subtitle {{ font-size: 12px; color: var(--text2); margin-top: 2px; }}
    .vera-meta {{ text-align: right; }}
    .vera-meta span {{ display: block; font-size: 12px; color: var(--text2); }}
    /* Layout */
    .container {{ max-width: 1600px; margin: 0 auto; padding: 24px 32px; }}
    /* Summary Cards */
    .summary-grid {{
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 16px;
      margin-bottom: 24px;
    }}
    .card {{
      background: var(--bg2);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 20px;
    }}
    .card-stat {{
      font-size: 36px;
      font-weight: 700;
      font-family: var(--font);
      margin-bottom: 4px;
    }}
    .card-label {{ font-size: 12px; color: var(--text2); text-transform: uppercase; letter-spacing: 1px; }}
    .stat-pass {{ color: var(--green); }}
    .stat-fail {{ color: var(--red); }}
    .stat-warn {{ color: var(--yellow); }}
    .stat-total {{ color: var(--blue); }}
    /* Charts row */
    .charts-row {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 16px;
      margin-bottom: 24px;
    }}
    .chart-card {{
      background: var(--bg2);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 20px;
    }}
    .chart-title {{
      font-size: 13px;
      font-weight: 600;
      color: var(--text2);
      text-transform: uppercase;
      letter-spacing: 1px;
      margin-bottom: 16px;
    }}
    .chart-container {{ height: 200px; position: relative; }}
    /* Tables */
    .section-title {{
      font-size: 16px; font-weight: 600;
      margin-bottom: 12px; margin-top: 24px;
      display: flex; align-items: center; gap: 8px;
    }}
    .section-title::before {{
      content: '';
      display: inline-block;
      width: 4px; height: 18px;
      border-radius: 2px;
    }}
    .failures-title::before {{ background: var(--red); }}
    .warnings-title::before {{ background: var(--yellow); }}
    .passes-title::before   {{ background: var(--green); }}
    .table-wrap {{
      background: var(--bg2);
      border: 1px solid var(--border);
      border-radius: 8px;
      overflow: hidden;
      margin-bottom: 24px;
      overflow-x: auto;
    }}
    table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
    th {{
      background: var(--bg3);
      border-bottom: 1px solid var(--border);
      padding: 10px 14px;
      text-align: left;
      font-weight: 600;
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      color: var(--text2);
      white-space: nowrap;
    }}
    td {{ padding: 10px 14px; border-bottom: 1px solid var(--border); vertical-align: top; }}
    tr:last-child td {{ border-bottom: none; }}
    .fail-row:hover {{ background: rgba(248,81,73,0.05); }}
    .warn-row:hover {{ background: rgba(210,153,34,0.05); }}
    .pass-row:hover {{ background: rgba(63,185,80,0.05); }}
    /* Badges */
    .badge {{
      display: inline-block;
      padding: 2px 8px;
      border-radius: 20px;
      font-size: 11px;
      font-weight: 700;
      letter-spacing: 0.5px;
    }}
    .badge.fail {{ background: rgba(248,81,73,0.15); color: var(--red); border: 1px solid rgba(248,81,73,0.3); }}
    .badge.warn {{ background: rgba(210,153,34,0.15); color: var(--yellow); border: 1px solid rgba(210,153,34,0.3); }}
    .badge.pass {{ background: rgba(63,185,80,0.15); color: var(--green); border: 1px solid rgba(63,185,80,0.3); }}
    .tag {{
      display: inline-block;
      padding: 1px 6px;
      border-radius: 4px;
      font-size: 10px;
      background: var(--bg3);
      color: var(--text2);
      border: 1px solid var(--border);
    }}
    code {{ font-family: var(--font); font-size: 12px; color: var(--cyan); }}
    .signal {{ color: var(--purple); }}
    .actual-fail {{ color: var(--red); font-family: var(--font); }};
    .recommendation {{ color: var(--yellow); font-size: 12px; font-style: italic; }}
    /* Pass rate bar */
    .passrate-bar {{
      height: 8px; border-radius: 4px;
      background: var(--bg3);
      margin-top: 8px;
      overflow: hidden;
    }}
    .passrate-fill {{
      height: 100%;
      background: linear-gradient(90deg, var(--green), #39d353);
      border-radius: 4px;
      width: {pass_rate};
      transition: width 1s ease;
    }}
    /* Footer */
    .vera-footer {{
      text-align: center;
      padding: 24px;
      color: var(--text2);
      font-size: 12px;
      border-top: 1px solid var(--border);
      margin-top: 32px;
    }}
    /* Collapse */
    .collapsible {{ cursor: pointer; user-select: none; }}
    .collapsible:hover {{ opacity: 0.8; }}
    .collapse-content {{ display: block; }}
    .collapse-content.hidden {{ display: none; }}
    /* Search */
    .search-bar {{
      width: 100%;
      background: var(--bg3);
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 8px 14px;
      color: var(--text);
      font-size: 13px;
      margin-bottom: 12px;
      outline: none;
    }}
    .search-bar:focus {{ border-color: var(--blue); }}
  </style>
</head>
<body>

<div class="vera-header">
  <div class="vera-logo">
    <div class="vera-logo-icon">V</div>
    <div>
      <div class="vera-title">VERA — Verification Engine for Runtime &amp; Autonomous Checking</div>
      <div class="vera-subtitle">Checker Network Intelligence Dashboard</div>
    </div>
  </div>
  <div class="vera-meta">
    <span>IP: <strong style="color:var(--blue)">{ip_name}</strong></span>
    <span>Generated: {ts}</span>
    <span>VERA v1.0</span>
  </div>
</div>

<div class="container">

  <!-- Summary Cards -->
  <div class="summary-grid">
    <div class="card">
      <div class="card-stat stat-total">{total}</div>
      <div class="card-label">Total Checks</div>
    </div>
    <div class="card">
      <div class="card-stat stat-pass">{passes}</div>
      <div class="card-label">Passed</div>
      <div class="passrate-bar"><div class="passrate-fill"></div></div>
    </div>
    <div class="card">
      <div class="card-stat stat-fail">{fails}</div>
      <div class="card-label">Failed</div>
    </div>
    <div class="card">
      <div class="card-stat stat-warn">{warns}</div>
      <div class="card-label">Warnings</div>
    </div>
  </div>

  <!-- Charts -->
  <div class="charts-row">
    <div class="chart-card">
      <div class="chart-title">Check Status Distribution</div>
      <div class="chart-container">
        <canvas id="statusChart"></canvas>
      </div>
    </div>
    <div class="chart-card">
      <div class="chart-title">Checks by Type</div>
      <div class="chart-container">
        <canvas id="typeChart"></canvas>
      </div>
    </div>
  </div>

  <!-- Failures Table -->
  <div class="section-title failures-title">
    &#x2717; Failures ({fails})
    <button onclick="toggleSection('failures')" style="margin-left:auto;background:none;border:1px solid var(--border);color:var(--text2);padding:4px 10px;border-radius:4px;cursor:pointer;font-size:12px;">Toggle</button>
  </div>
  <div id="failures" class="collapse-content">
    <input class="search-bar" id="failSearch" placeholder="Search failures..." onkeyup="filterTable('failTable', this.value)">
    <div class="table-wrap">
      <table id="failTable">
        <thead>
          <tr>
            <th>Status</th><th>IP</th><th>Checker</th><th>Type</th>
            <th>Expected</th><th>Actual</th><th>Margin</th>
            <th>Time(ns)</th><th>Signal</th><th>Recommendation</th>
          </tr>
        </thead>
        <tbody>{fail_rows}</tbody>
      </table>
    </div>
  </div>

  <!-- Warnings Table -->
  <div class="section-title warnings-title">
    &#x26A0; Warnings ({warns})
    <button onclick="toggleSection('warnings')" style="margin-left:auto;background:none;border:1px solid var(--border);color:var(--text2);padding:4px 10px;border-radius:4px;cursor:pointer;font-size:12px;">Toggle</button>
  </div>
  <div id="warnings" class="collapse-content">
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Status</th><th>IP</th><th>Checker</th><th>Type</th>
            <th>Expected</th><th>Actual</th><th colspan="4">Context</th>
          </tr>
        </thead>
        <tbody>{warn_rows}</tbody>
      </table>
    </div>
  </div>

  <!-- Passes Table -->
  <div class="section-title passes-title">
    &#x2713; Passed ({passes})
    <button onclick="toggleSection('passes')" style="margin-left:auto;background:none;border:1px solid var(--border);color:var(--text2);padding:4px 10px;border-radius:4px;cursor:pointer;font-size:12px;">Toggle</button>
  </div>
  <div id="passes" class="collapse-content hidden">
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Status</th><th>IP</th><th>Checker</th><th>Type</th>
            <th>Expected</th><th>Actual</th><th colspan="4">Margin</th>
          </tr>
        </thead>
        <tbody>{pass_rows}</tbody>
      </table>
    </div>
  </div>

</div>

<div class="vera-footer">
  VERA — Verification Engine for Runtime &amp; Autonomous Checking &nbsp;|&nbsp; v1.0
  &nbsp;|&nbsp; Report generated {ts}
</div>

<script>
// Status Donut
const statusCtx = document.getElementById('statusChart').getContext('2d');
new Chart(statusCtx, {{
  type: 'doughnut',
  data: {{
    labels: ['Pass', 'Fail', 'Warning'],
    datasets: [{{ data: {status_data},
      backgroundColor: ['#3fb950','#f85149','#d29922'],
      borderColor: '#161b22', borderWidth: 2 }}]
  }},
  options: {{
    responsive: true, maintainAspectRatio: false,
    plugins: {{ legend: {{ position: 'right', labels: {{ color: '#8b949e', font: {{size: 11}} }} }} }}
  }}
}});

// Type Bar
const typeCtx = document.getElementById('typeChart').getContext('2d');
new Chart(typeCtx, {{
  type: 'bar',
  data: {{
    labels: {type_labels},
    datasets: [{{ label: 'Checks', data: {type_data},
      backgroundColor: '#58a6ff88', borderColor: '#58a6ff', borderWidth: 1 }}]
  }},
  options: {{
    responsive: true, maintainAspectRatio: false,
    plugins: {{ legend: {{ display: false }} }},
    scales: {{
      x: {{ ticks: {{ color: '#8b949e', font: {{size: 10}} }}, grid: {{ color: '#30363d' }} }},
      y: {{ ticks: {{ color: '#8b949e' }}, grid: {{ color: '#30363d' }} }}
    }}
  }}
}});

// Toggle sections
function toggleSection(id) {{
  const el = document.getElementById(id);
  el.classList.toggle('hidden');
}}

// Table filter
function filterTable(tableId, query) {{
  const rows = document.getElementById(tableId).querySelectorAll('tbody tr');
  const q = query.toLowerCase();
  rows.forEach(r => {{
    r.style.display = r.textContent.toLowerCase().includes(q) ? '' : 'none';
  }});
}}
</script>
</body>
</html>"""


# =============================================================================
# Aggregate multiple JSON reports into one HTML
# =============================================================================
def aggregate_and_render(results_dir: str, output_path: str):
    json_files = sorted(glob.glob(os.path.join(results_dir, "**/*.json"), recursive=True))
    if not json_files:
        json_files = sorted(glob.glob(os.path.join(results_dir, "*.json")))

    all_results  = []
    total_pass = total_fail = total_warn = 0

    for jf in json_files:
        try:
            with open(jf) as f:
                rpt = json.load(f)
            rr = rpt.get("vera_report", rpt.get("vera_aggregate_report", {}))
            s  = rr.get("summary", {})
            total_pass += s.get("pass", 0)
            total_fail += s.get("fail", 0)
            total_warn += s.get("warning", 0)
            all_results.extend(rr.get("results", []))
        except Exception as e:
            print(f"  [VERA] Skipping {jf}: {e}")

    combined = {
        "vera_report": {
            "meta": {"ip_name": "VERA Aggregate", "results_dir": results_dir},
            "summary": {
                "total":   len(all_results),
                "pass":    total_pass,
                "fail":    total_fail,
                "warning": total_warn,
            },
            "results": all_results,
        }
    }
    reporter = VERAHTMLReporter(combined)
    reporter.generate(output_path)


# =============================================================================
# CLI / simple HTTP server
# =============================================================================
def main():
    parser = argparse.ArgumentParser(description="VERA Dashboard & Report Generator")
    parser.add_argument("--report",      help="Single VERA JSON report to render")
    parser.add_argument("--results_dir", help="Directory with multiple VERA JSON reports")
    parser.add_argument("--output",      default="vera_dashboard.html", help="HTML output path")
    parser.add_argument("--serve",       action="store_true", help="Serve dashboard via HTTP")
    parser.add_argument("--port",        type=int, default=8080, help="HTTP port")
    args = parser.parse_args()

    if args.report:
        with open(args.report) as f:
            data = json.load(f)
        reporter = VERAHTMLReporter(data)
        reporter.generate(args.output)

    elif args.results_dir:
        aggregate_and_render(args.results_dir, args.output)

    else:
        print("ERROR: Provide --report or --results_dir")
        sys.exit(1)

    if args.serve:
        import http.server, webbrowser, threading
        out_dir = str(Path(args.output).parent)
        os.chdir(out_dir)
        handler = http.server.SimpleHTTPRequestHandler
        httpd   = http.server.HTTPServer(("", args.port), handler)
        print(f"  [VERA] Dashboard: http://localhost:{args.port}/{Path(args.output).name}")
        threading.Timer(1, lambda: webbrowser.open(
            f"http://localhost:{args.port}/{Path(args.output).name}")).start()
        httpd.serve_forever()


if __name__ == "__main__":
    main()
