"""
fcov_forge/generators/html_report.py
======================================
Generates an HTML coverage plan report from a FeatureModel.
The report shows the feature hierarchy with all covergroups, coverpoints,
bins, and cross definitions in a human-readable, navigable format.
"""

from __future__ import annotations
from pathlib import Path
from datetime import datetime
from core.model import FeatureModel, Feature, CoverGroup, CoverPoint, CoverBin, BinType


def _bin_badge(b: CoverBin) -> str:
    colors = {
        BinType.VALUES:     ("#2563eb", "VALUES"),
        BinType.RANGE:      ("#7c3aed", "RANGE"),
        BinType.TRANSITION: ("#db2777", "TRANS"),
        BinType.DEFAULT:    ("#6b7280", "DEFAULT"),
        BinType.IGNORE:     ("#d97706", "IGNORE"),
        BinType.ILLEGAL:    ("#dc2626", "ILLEGAL"),
        BinType.WILDCARD:   ("#059669", "WILD"),
        BinType.AUTO:       ("#0891b2", "AUTO"),
    }
    color, label = colors.get(b.bin_type, ("#374151", "?"))
    return f'<span style="background:{color};color:white;padding:2px 6px;border-radius:3px;font-size:11px;font-weight:600">{label}</span>'


def _bin_value_str(b: CoverBin) -> str:
    if b.bin_type == BinType.DEFAULT:
        return "<em>default</em>"
    if b.bin_type == BinType.WILDCARD:
        return f"<code>{b.wildcard_pattern}</code>"
    if b.bin_type == BinType.AUTO:
        return f"auto (max={b.auto_bin_max or 'default'})"
    if b.bin_type == BinType.TRANSITION:
        seqs = " | ".join(" → ".join(s) for s in b.transitions)
        return f"<code>{seqs}</code>"
    parts = []
    for v in b.values:
        parts.append(f"<code>{v}</code>")
    for lo, hi in b.ranges:
        parts.append(f"<code>[{lo}:{hi}]</code>")
    return ", ".join(parts) if parts else "<em>empty</em>"


def generate_html_report(model: FeatureModel, output: Path) -> None:
    """Generate full HTML coverage plan."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    total_cgs = sum(len(f.covergroups) for f in model.features)
    total_cps = sum(len(cg.coverpoints) for f in model.features for cg in f.covergroups)
    total_bins = sum(
        len(cp.bins) for f in model.features
        for cg in f.covergroups for cp in cg.coverpoints
    )

    # Build feature sections
    feature_html = ""
    for feat in model.features:
        cg_count = len(feat.covergroups)
        cp_count = sum(len(cg.coverpoints) for cg in feat.covergroups)
        bin_count = sum(len(cp.bins) for cg in feat.covergroups for cp in cg.coverpoints)

        tags_html = ""
        for tag in feat.tags:
            tags_html += f'<span class="tag">{tag}</span>'

        cg_html = ""
        for cg in feat.covergroups:
            cp_html = ""
            for cp in cg.coverpoints:
                bins_html = ""
                for b in cp.bins:
                    cmt = f' <span class="bin-comment">// {b.comment}</span>' if b.comment else ""
                    hits = f' min_hits={b.min_hits}' if b.min_hits > 1 else ""
                    bins_html += f"""
                    <tr>
                        <td><code class="bin-name">{b.name}</code></td>
                        <td>{_bin_badge(b)}</td>
                        <td>{_bin_value_str(b)}</td>
                        <td class="muted">{hits}{cmt}</td>
                    </tr>"""

                iff_str = f' <span class="iff">iff ({cp.condition})</span>' if cp.condition else ""
                cp_html += f"""
                <div class="coverpoint">
                    <div class="cp-header">
                        <span class="cp-name">{cp.name}</span>
                        <span class="muted"> coverpoint </span>
                        <code class="var">{cp.variable}</code>{iff_str}
                        {f'<span class="muted"> — {cp.comment}</span>' if cp.comment else ''}
                    </div>
                    <table class="bin-table">
                        <thead><tr><th>Bin</th><th>Type</th><th>Values</th><th>Notes</th></tr></thead>
                        <tbody>{bins_html}</tbody>
                    </table>
                </div>"""

            # CG-level crosses
            cg_cross_html = ""
            for cross in cg.crosses:
                cps = " × ".join(f"<code>{c}</code>" for c in cross.coverpoints)
                cg_cross_html += f"""
                <div class="cg-cross">
                    <span class="cross-icon">⊗</span> <strong>{cross.name}</strong>: {cps}
                    {f'<span class="muted"> — {cross.comment}</span>' if cross.comment else ''}
                </div>"""

            clock_str = f'@({cg.clock_event})' if cg.clock_event else ''
            cond_str = f'iff ({cg.sample_condition})' if cg.sample_condition else ''

            cg_html += f"""
            <div class="covergroup">
                <div class="cg-header" onclick="toggleCG(this)">
                    <span class="toggle-icon">▶</span>
                    <span class="cg-name">{cg.name}</span>
                    <span class="cg-meta">
                        {f'<code>{clock_str}</code>' if clock_str else ''}
                        {f'<code>{cond_str}</code>' if cond_str else ''}
                        <span class="badge">{len(cg.coverpoints)} CPs</span>
                        {f'<span class="badge goal">goal={cg.goal}%</span>' if cg.goal else ''}
                    </span>
                    {f'<span class="muted cg-comment"> — {cg.comment}</span>' if cg.comment else ''}
                </div>
                <div class="cg-body collapsed">
                    {cp_html}
                    {cg_cross_html}
                </div>
            </div>"""

        src = f'<span class="source">📄 {feat.source_doc}</span>' if feat.source_doc else ''
        feature_html += f"""
        <div class="feature-card" id="feat-{feat.name}">
            <div class="feature-header">
                <div class="feature-title">
                    <span class="feat-icon">◈</span>
                    <strong class="feat-name">{feat.name}</strong>
                    {tags_html}
                    {src}
                </div>
                <div class="feature-stats">
                    <span class="stat">{cg_count} CoverGroups</span>
                    <span class="stat">{cp_count} CoverPoints</span>
                    <span class="stat">{bin_count} Bins</span>
                </div>
            </div>
            {f'<div class="feat-desc">{feat.description}</div>' if feat.description else ''}
            <div class="cg-list">{cg_html}</div>
        </div>"""

    # Feature crosses section
    cross_html = ""
    for fc in model.feature_crosses:
        targets_html = " × ".join(
            f'<code class="cross-addr">{t.address}</code>' for t in fc.targets
        )
        cross_html += f"""
        <div class="feature-cross-card">
            <div class="fc-name"><span class="cross-icon">⊗</span> <strong>{fc.name}</strong></div>
            <div class="fc-targets">{targets_html}</div>
            {f'<div class="muted">{fc.comment}</div>' if fc.comment else ''}
            <div class="badge">goal={fc.goal}%</div>
        </div>"""

    if not cross_html:
        cross_html = '<div class="muted">No feature crosses defined.</div>'

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>FCovForge — {model.project_name} Coverage Plan</title>
<style>
  :root {{
    --bg: #0f1117; --surface: #1a1d27; --surface2: #22263a;
    --border: #2d3148; --text: #e2e8f0; --muted: #64748b;
    --accent: #6366f1; --accent2: #22d3ee; --green: #10b981;
    --font-mono: 'JetBrains Mono', 'Fira Code', monospace;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: var(--bg); color: var(--text); font-family: 'Inter', system-ui, sans-serif;
          font-size: 14px; line-height: 1.6; }}
  a {{ color: var(--accent2); text-decoration: none; }}
  code {{ font-family: var(--font-mono); font-size: 12px; color: var(--accent2);
          background: rgba(34,211,238,0.08); padding: 1px 5px; border-radius: 3px; }}

  /* Header */
  .header {{ background: linear-gradient(135deg, #1a1d27 0%, #0f1629 100%);
             border-bottom: 1px solid var(--border); padding: 24px 40px; }}
  .header h1 {{ font-size: 28px; font-weight: 700; color: var(--accent2);
                letter-spacing: -0.5px; }}
  .header .sub {{ color: var(--muted); font-size: 13px; margin-top: 4px; }}
  .stats-row {{ display: flex; gap: 24px; margin-top: 16px; }}
  .stat-card {{ background: var(--surface); border: 1px solid var(--border);
                border-radius: 8px; padding: 12px 20px; text-align: center; }}
  .stat-card .num {{ font-size: 28px; font-weight: 700; color: var(--accent); }}
  .stat-card .lbl {{ font-size: 11px; color: var(--muted); text-transform: uppercase; letter-spacing: 1px; }}

  /* Nav sidebar */
  .layout {{ display: flex; min-height: calc(100vh - 120px); }}
  .sidebar {{ width: 240px; background: var(--surface); border-right: 1px solid var(--border);
              padding: 16px; position: sticky; top: 0; height: 100vh; overflow-y: auto;
              flex-shrink: 0; }}
  .sidebar h3 {{ font-size: 11px; text-transform: uppercase; letter-spacing: 1px;
                 color: var(--muted); margin-bottom: 8px; }}
  .nav-item {{ display: block; padding: 6px 10px; border-radius: 5px; color: var(--text);
               font-size: 13px; cursor: pointer; transition: background 0.15s; }}
  .nav-item:hover {{ background: var(--surface2); }}

  /* Main */
  .main {{ flex: 1; padding: 32px 40px; max-width: 1200px; }}
  .section-title {{ font-size: 20px; font-weight: 700; margin-bottom: 16px;
                    color: var(--accent2); border-bottom: 1px solid var(--border);
                    padding-bottom: 8px; }}

  /* Feature cards */
  .feature-card {{ background: var(--surface); border: 1px solid var(--border);
                   border-radius: 12px; margin-bottom: 24px; overflow: hidden; }}
  .feature-header {{ padding: 16px 20px; display: flex; justify-content: space-between;
                     align-items: center; background: var(--surface2);
                     border-bottom: 1px solid var(--border); }}
  .feature-title {{ display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }}
  .feat-icon {{ color: var(--accent); font-size: 18px; }}
  .feat-name {{ font-size: 16px; color: var(--text); }}
  .feat-desc {{ padding: 10px 20px; color: var(--muted); font-size: 13px;
                border-bottom: 1px solid var(--border); }}
  .feature-stats {{ display: flex; gap: 12px; }}
  .stat {{ font-size: 12px; color: var(--muted); background: var(--bg);
           padding: 3px 10px; border-radius: 20px; border: 1px solid var(--border); }}
  .tag {{ font-size: 11px; background: rgba(99,102,241,0.15); color: var(--accent);
          padding: 2px 8px; border-radius: 20px; border: 1px solid rgba(99,102,241,0.3); }}
  .source {{ font-size: 11px; color: var(--muted); }}

  /* CoverGroup */
  .cg-list {{ padding: 12px 16px; }}
  .covergroup {{ margin-bottom: 10px; border: 1px solid var(--border);
                 border-radius: 8px; overflow: hidden; }}
  .cg-header {{ padding: 10px 14px; background: var(--bg); cursor: pointer;
                display: flex; align-items: center; gap: 10px; flex-wrap: wrap;
                transition: background 0.15s; user-select: none; }}
  .cg-header:hover {{ background: var(--surface2); }}
  .toggle-icon {{ color: var(--muted); font-size: 10px; transition: transform 0.2s; }}
  .cg-header.open .toggle-icon {{ transform: rotate(90deg); }}
  .cg-name {{ font-weight: 600; color: var(--accent2); font-family: var(--font-mono); }}
  .cg-meta {{ display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }}
  .cg-comment {{ font-size: 12px; }}
  .badge {{ font-size: 11px; background: var(--surface2); color: var(--muted);
            padding: 2px 8px; border-radius: 20px; border: 1px solid var(--border); }}
  .badge.goal {{ color: var(--green); border-color: rgba(16,185,129,0.3);
                 background: rgba(16,185,129,0.08); }}

  .cg-body {{ padding: 12px; background: var(--surface); }}
  .cg-body.collapsed {{ display: none; }}

  /* CoverPoint */
  .coverpoint {{ margin-bottom: 12px; background: var(--bg);
                 border: 1px solid var(--border); border-radius: 6px; overflow: hidden; }}
  .cp-header {{ padding: 8px 12px; font-family: var(--font-mono);
                font-size: 13px; border-bottom: 1px solid var(--border);
                background: rgba(99,102,241,0.04); }}
  .cp-name {{ color: #a5b4fc; font-weight: 600; }}
  .var {{ color: #34d399; }}
  .iff {{ color: #fbbf24; font-size: 12px; }}
  .muted {{ color: var(--muted); font-size: 12px; }}

  /* Bin table */
  .bin-table {{ width: 100%; border-collapse: collapse; font-size: 12px; }}
  .bin-table th {{ text-align: left; padding: 6px 12px; color: var(--muted);
                   font-weight: 500; border-bottom: 1px solid var(--border);
                   background: var(--surface); }}
  .bin-table td {{ padding: 5px 12px; border-bottom: 1px solid rgba(45,49,72,0.5); }}
  .bin-table tr:last-child td {{ border-bottom: none; }}
  .bin-name {{ color: #fcd34d; }}
  .bin-comment {{ color: var(--muted); }}

  /* CG Crosses */
  .cg-cross {{ padding: 8px 12px; font-size: 12px; background: rgba(219,39,119,0.05);
               border: 1px solid rgba(219,39,119,0.15); border-radius: 5px;
               margin-top: 8px; }}
  .cross-icon {{ color: #db2777; }}

  /* Feature Crosses section */
  .feature-cross-card {{ background: var(--surface); border: 1px solid rgba(99,102,241,0.3);
                         border-radius: 10px; padding: 16px 20px; margin-bottom: 12px; }}
  .fc-name {{ font-size: 15px; margin-bottom: 8px; }}
  .fc-targets {{ display: flex; gap: 12px; align-items: center; flex-wrap: wrap;
                 margin-bottom: 8px; font-size: 13px; }}
  .cross-addr {{ color: #c084fc; }}

  .section {{ margin-bottom: 48px; }}

  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;600&display=swap');
</style>
</head>
<body>

<div class="header">
  <h1>⬡ FCovForge Coverage Plan</h1>
  <div class="sub">Project: <strong>{model.project_name}</strong> &nbsp;·&nbsp; Generated: {now}</div>
  <div class="stats-row">
    <div class="stat-card"><div class="num">{len(model.features)}</div><div class="lbl">Features</div></div>
    <div class="stat-card"><div class="num">{total_cgs}</div><div class="lbl">CoverGroups</div></div>
    <div class="stat-card"><div class="num">{total_cps}</div><div class="lbl">CoverPoints</div></div>
    <div class="stat-card"><div class="num">{total_bins}</div><div class="lbl">Bins</div></div>
    <div class="stat-card"><div class="num">{len(model.feature_crosses)}</div><div class="lbl">Feature Crosses</div></div>
  </div>
</div>

<div class="layout">
  <div class="sidebar">
    <h3>Features</h3>
    {''.join(f'<a class="nav-item" href="#feat-{f.name}">◈ {f.name}</a>' for f in model.features)}
    <h3 style="margin-top:16px">Crosses</h3>
    {''.join(f'<a class="nav-item" href="#crosses">⊗ {fc.name}</a>' for fc in model.feature_crosses)}
  </div>

  <div class="main">
    <div class="section">
      <div class="section-title">Features & Coverage Definitions</div>
      {feature_html}
    </div>

    <div class="section" id="crosses">
      <div class="section-title">Feature-Level Crosses</div>
      {cross_html}
    </div>
  </div>
</div>

<script>
function toggleCG(header) {{
  header.classList.toggle('open');
  const body = header.nextElementSibling;
  body.classList.toggle('collapsed');
}}
</script>
</body>
</html>"""

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html, encoding="utf-8")
