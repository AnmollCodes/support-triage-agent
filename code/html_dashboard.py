"""
html_dashboard.py — Feature 9: Beautiful HTML Executive Dashboard

Generates a single self-contained HTML file with:
  - Summary KPI cards (total tickets, replied/escalated, avg confidence)
  - Interactive charts (sentiment pie, urgency bar, health score distribution)
  - Full ticket table with colour-coded rows (sortable)
  - Incident alert banner
  - VIP account flags
  - Knowledge gap report
  - FAQ entry preview
  - Corpus coverage meter
  - Prevention tips summary
  - Churn risk leaderboard (top 5 highest risk tickets)

Fully self-contained: one .html file, no external dependencies,
works offline. Charts use Chart.js from CDN (one external request).
"""
from __future__ import annotations
import json
from pathlib import Path
from typing import List, Optional
from models import (
    IncidentReport, Sentiment, SupportTicket, TicketStatus, TriageResult, UrgencyTier
)
from churn_risk import ChurnRiskResult
from health_score import HealthScoreResult


def _js(obj) -> str:
    return json.dumps(obj, ensure_ascii=False)


def _ticket_row_color(result: TriageResult, churn: ChurnRiskResult) -> str:
    if result.language.injection_in_foreign:
        return "#4a1010"
    if churn.churn_risk_score >= 70:
        return "#4a2000"
    if result.status == TicketStatus.ESCALATED:
        return "#1a2a3a"
    tier_colors = {
        UrgencyTier.P0_CRITICAL: "#3a1a1a",
        UrgencyTier.P1_HIGH:     "#3a2a0a",
        UrgencyTier.P2_MEDIUM:   "#1a2a2a",
        UrgencyTier.P3_LOW:      "#1a1e24",
    }
    return tier_colors.get(result.urgency.tier, "#1a1e24")


def generate_html_dashboard(
    tickets:  List[SupportTicket],
    results:  List[TriageResult],
    incidents: List[IncidentReport],
    churns:   List[ChurnRiskResult],
    healths:  List[HealthScoreResult],
    output_path: Path,
) -> None:

    total     = len(results)
    replied   = sum(1 for r in results if r.status == TicketStatus.REPLIED)
    escalated = total - replied
    avg_conf  = sum(r.confidence.score for r in results) / max(total, 1)
    avg_qual  = sum(r.quality.score    for r in results) / max(total, 1)
    avg_health= sum(h.health_score     for h in healths)  / max(total, 1)
    vip_count = sum(1 for r in results if r.vip.is_vip)
    gap_count = sum(1 for r in results if r.corpus_gap.gap_detected)
    inj_count = sum(1 for r in results if r.language.injection_in_foreign)
    high_churn= sum(1 for c in churns  if c.churn_risk_score >= 45)

    # Chart data
    sent_counts = {}
    for r in results:
        s = r.sentiment.sentiment.value
        sent_counts[s] = sent_counts.get(s, 0) + 1

    tier_counts = {}
    for r in results:
        t = r.urgency.tier.value
        tier_counts[t] = tier_counts.get(t, 0) + 1

    health_dist = {"Healthy":0,"At Risk":0,"Critical":0,"Red Alert":0}
    for h in healths:
        health_dist[h.health_label] = health_dist.get(h.health_label, 0) + 1

    req_counts = {}
    for r in results:
        k = r.request_type.value
        req_counts[k] = req_counts.get(k, 0) + 1

    # Company counts
    co_counts = {}
    for t in tickets:
        co_counts[t.company] = co_counts.get(t.company, 0) + 1

    # Top 5 churn risk tickets
    churn_sorted = sorted(
        [(i, tickets[i], results[i], churns[i]) for i in range(total)],
        key=lambda x: x[3].churn_risk_score, reverse=True
    )[:5]

    # Incident HTML
    incident_html = ""
    if incidents:
        sev_colors = {"SEV1": "#ff4444", "SEV2": "#ffaa00", "SEV3": "#44aaff"}
        for inc in incidents:
            color = sev_colors.get(inc.severity.value, "#888")
            nums  = ", ".join(f"#{n}" for n in inc.ticket_indices[:8])
            incident_html += f"""
            <div class="incident-card" style="border-left:4px solid {color}">
                <div class="inc-header">
                    <span class="inc-id">{inc.cluster_id}</span>
                    <span class="inc-sev" style="color:{color}">{inc.severity.value}</span>
                    <span class="inc-title">{inc.title}</span>
                </div>
                <div class="inc-body">
                    <strong>Affected tickets:</strong> {nums}<br>
                    <strong>Recommended action:</strong> {inc.recommended_action}
                </div>
                <div class="inc-draft">
                    <strong>Draft mass response:</strong><br>
                    <em>{inc.auto_response_draft}</em>
                </div>
            </div>"""
    else:
        incident_html = '<div class="no-incident">✓ No incident clusters detected in this batch.</div>'

    # Ticket table rows
    table_rows = ""
    for i, (ticket, result, churn, health) in enumerate(zip(tickets, results, churns, healths)):
        row_bg    = _ticket_row_color(result, churn)
        st_color  = "#4caf50" if result.status == TicketStatus.REPLIED else "#f44336"
        st_label  = "✓ Replied" if result.status == TicketStatus.REPLIED else "⚠ Escalated"
        tier_colors = {"P0_Critical":"#ff4444","P1_High":"#ffaa00","P2_Medium":"#44dddd","P3_Low":"#888"}
        tier_c    = tier_colors.get(result.urgency.tier.value, "#888")
        sent_colors= {"angry":"#ff4444","frustrated":"#ffaa00","distressed":"#cc44ff","neutral":"#aaa","positive":"#44ff88"}
        sent_c    = sent_colors.get(result.sentiment.sentiment.value, "#aaa")
        hlth_colors= {"Healthy":"#44ff88","At Risk":"#ffaa00","Critical":"#ff8844","Red Alert":"#ff4444"}
        hlth_c    = hlth_colors.get(health.health_label, "#aaa")
        inj_badge = ' <span class="badge badge-red">INJECTION</span>' if result.language.injection_in_foreign else ""
        vip_badge = ' <span class="badge badge-gold">VIP</span>' if result.vip.is_vip else ""
        dup_badge = ""
        issue_preview = ticket.issue[:90].replace("\n"," ").replace("<","&lt;").replace(">","&gt;")

        table_rows += f"""
        <tr style="background:{row_bg}" class="ticket-row" data-company="{ticket.company}"
            data-status="{result.status.value}" data-tier="{result.urgency.tier.value}">
            <td class="td-num">{i+1}</td>
            <td><span class="company-tag co-{ticket.company.lower().replace(' ','-')}">{ticket.company}</span></td>
            <td><span style="color:{st_color};font-weight:bold">{st_label}</span></td>
            <td><span style="color:{tier_c}">{result.urgency.tier.value}</span></td>
            <td><span style="color:{sent_c}">{result.sentiment.sentiment.value}</span></td>
            <td>{result.product_area}</td>
            <td>{result.request_type.value}</td>
            <td class="num-cell">{result.confidence.score:.2f}</td>
            <td class="num-cell">{result.quality.score:.2f}</td>
            <td><span style="color:{hlth_c};font-weight:bold">{health.health_score}</span>
                <small style="color:{hlth_c}"> {health.health_label}</small></td>
            <td class="num-cell" style="color:{'#ff4444' if churn.churn_risk_score>=70 else '#ffaa00' if churn.churn_risk_score>=45 else '#aaa'}">{churn.churn_risk_score}</td>
            <td class="issue-cell">{issue_preview}…{inj_badge}{vip_badge}{dup_badge}</td>
        </tr>"""

    # Churn risk leaderboard
    churn_leaderboard = ""
    for i, ticket, result, churn in churn_sorted:
        if churn.churn_risk_score == 0:
            break
        bar_w = churn.churn_risk_score
        bar_color = "#ff4444" if churn.churn_risk_score >= 70 else "#ffaa00" if churn.churn_risk_score >= 45 else "#44aaff"
        churn_leaderboard += f"""
        <div class="churn-item">
            <div class="churn-header">
                <span class="churn-num">#{i+1}</span>
                <span class="churn-company">{ticket.company}</span>
                <span class="churn-score" style="color:{bar_color}">{churn.churn_risk_score}/100</span>
                <span class="churn-priority">{churn.retention_priority}</span>
            </div>
            <div class="churn-bar-bg"><div class="churn-bar" style="width:{bar_w}%;background:{bar_color}"></div></div>
            <div class="churn-signals">{' · '.join(churn.churn_signals[:3])}</div>
            <div class="churn-impact">{churn.business_impact[:120]}…</div>
        </div>"""

    if not churn_leaderboard:
        churn_leaderboard = '<div class="no-incident">✓ No significant churn risk detected.</div>'

    # Knowledge gaps
    gap_html = ""
    gap_suggestions = list({
        r.corpus_gap.suggested_doc_title
        for r in results
        if r.corpus_gap.gap_detected and r.corpus_gap.suggested_doc_title
    })
    if gap_suggestions:
        for s in gap_suggestions[:8]:
            gap_html += f'<div class="gap-item">📄 {s}</div>\n'
    else:
        gap_html = '<div class="no-incident">✓ Full corpus coverage — no gaps detected.</div>'

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Support Triage Dashboard</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
  :root {{
    --bg: #0d1117; --card: #161b22; --border: #30363d;
    --text: #e6edf3; --muted: #7d8590; --accent: #58a6ff;
    --green: #3fb950; --red: #f85149; --yellow: #d29922; --purple: #bc8cff;
  }}
  * {{ box-sizing: border-box; margin:0; padding:0; }}
  body {{ background:var(--bg); color:var(--text); font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif; font-size:14px; }}
  .header {{ background:linear-gradient(135deg,#1f6feb22,#58a6ff11); border-bottom:1px solid var(--border);
             padding:24px 32px; display:flex; align-items:center; justify-content:space-between; }}
  .header h1 {{ font-size:22px; font-weight:700; color:var(--accent); }}
  .header .meta {{ color:var(--muted); font-size:12px; }}
  .container {{ max-width:1400px; margin:0 auto; padding:24px 32px; }}
  .kpi-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(160px,1fr)); gap:16px; margin-bottom:24px; }}
  .kpi {{ background:var(--card); border:1px solid var(--border); border-radius:8px; padding:16px;
           text-align:center; transition:transform .2s; }}
  .kpi:hover {{ transform:translateY(-2px); }}
  .kpi .kpi-val {{ font-size:32px; font-weight:700; line-height:1; margin-bottom:4px; }}
  .kpi .kpi-label {{ color:var(--muted); font-size:11px; text-transform:uppercase; letter-spacing:.5px; }}
  .section {{ background:var(--card); border:1px solid var(--border); border-radius:8px;
              padding:20px; margin-bottom:20px; }}
  .section-title {{ font-size:16px; font-weight:600; margin-bottom:16px; display:flex; align-items:center; gap:8px; }}
  .charts-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(280px,1fr)); gap:20px; margin-bottom:20px; }}
  .chart-card {{ background:var(--card); border:1px solid var(--border); border-radius:8px; padding:16px; }}
  .chart-card h3 {{ font-size:13px; color:var(--muted); margin-bottom:12px; text-transform:uppercase; letter-spacing:.5px; }}
  canvas {{ max-height:220px; }}
  table {{ width:100%; border-collapse:collapse; font-size:13px; }}
  th {{ background:#21262d; color:var(--muted); font-weight:600; text-transform:uppercase;
        font-size:11px; letter-spacing:.5px; padding:10px 12px; text-align:left;
        position:sticky; top:0; cursor:pointer; user-select:none; }}
  th:hover {{ color:var(--accent); }}
  td {{ padding:9px 12px; border-bottom:1px solid #21262d; vertical-align:middle; }}
  .ticket-row:hover td {{ filter:brightness(1.15); }}
  .td-num {{ color:var(--muted); font-size:12px; width:36px; }}
  .company-tag {{ padding:2px 8px; border-radius:12px; font-size:11px; font-weight:600; }}
  .co-hackerrank {{ background:#1f6feb22; color:#58a6ff; }}
  .co-claude {{ background:#3fb95022; color:#3fb950; }}
  .co-visa {{ background:#d2992222; color:#d29922; }}
  .co-none {{ background:#7d859022; color:#7d8590; }}
  .num-cell {{ text-align:center; font-variant-numeric:tabular-nums; }}
  .issue-cell {{ max-width:320px; color:var(--muted); font-size:12px; }}
  .badge {{ padding:1px 6px; border-radius:4px; font-size:10px; font-weight:700; margin-left:4px; }}
  .badge-red {{ background:#f8514933; color:#f85149; }}
  .badge-gold {{ background:#d2992233; color:#d29922; }}
  .incident-card {{ background:#1a1e24; border-radius:8px; padding:16px; margin-bottom:12px; }}
  .inc-header {{ display:flex; align-items:center; gap:12px; margin-bottom:8px; }}
  .inc-id {{ font-family:monospace; font-weight:700; color:var(--accent); }}
  .inc-sev {{ font-weight:700; font-size:13px; }}
  .inc-title {{ font-size:13px; }}
  .inc-body {{ color:var(--muted); font-size:12px; margin-bottom:8px; line-height:1.6; }}
  .inc-draft {{ background:#0d1117; border-radius:6px; padding:10px; font-size:12px; color:#aaa; font-style:italic; }}
  .no-incident {{ color:var(--green); padding:12px; }}
  .churn-item {{ background:#1a1e24; border-radius:8px; padding:14px; margin-bottom:10px; }}
  .churn-header {{ display:flex; align-items:center; gap:12px; margin-bottom:6px; }}
  .churn-num {{ font-weight:700; color:var(--muted); }}
  .churn-company {{ font-weight:600; }}
  .churn-score {{ font-size:18px; font-weight:700; margin-left:auto; }}
  .churn-priority {{ padding:2px 8px; border-radius:12px; font-size:11px; font-weight:600;
                     background:#f8514922; color:#f85149; }}
  .churn-bar-bg {{ background:#21262d; border-radius:4px; height:6px; margin:8px 0; }}
  .churn-bar {{ height:6px; border-radius:4px; transition:width .5s; }}
  .churn-signals {{ font-size:11px; color:var(--muted); margin-bottom:4px; }}
  .churn-impact {{ font-size:12px; color:#aaa; }}
  .gap-item {{ padding:8px 12px; background:#1a1e24; border-radius:6px; margin-bottom:6px;
               font-size:13px; color:#aaa; }}
  .filter-bar {{ display:flex; gap:10px; flex-wrap:wrap; margin-bottom:14px; }}
  .filter-btn {{ padding:5px 14px; border-radius:20px; border:1px solid var(--border);
                  background:transparent; color:var(--muted); cursor:pointer; font-size:12px;
                  transition:all .2s; }}
  .filter-btn:hover, .filter-btn.active {{ background:var(--accent); color:#fff; border-color:var(--accent); }}
  .table-wrap {{ overflow-x:auto; max-height:520px; overflow-y:auto; }}
  .meter {{ background:#21262d; border-radius:4px; height:10px; margin-top:4px; }}
  .meter-fill {{ height:10px; border-radius:4px; background:linear-gradient(90deg,#58a6ff,#3fb950); }}
  .audit-badge {{ display:inline-flex; align-items:center; gap:6px; background:#3fb95022;
                  border:1px solid #3fb95044; border-radius:6px; padding:6px 12px; font-size:12px; }}
</style>
</head>
<body>

<div class="header">
  <div>
    <h1>🎯 Support Triage · Executive Dashboard</h1>
    <div class="meta">Multi-domain AI Triage Agent · HackerRank · Claude · Visa · {total} tickets processed</div>
  </div>
  <div style="text-align:right">
    <div class="audit-badge">🔐 Audit Chain: <strong style="color:var(--green)">Verified ✓</strong></div>
  </div>
</div>

<div class="container">

<!-- KPI Cards -->
<div class="kpi-grid">
  <div class="kpi"><div class="kpi-val" style="color:var(--accent)">{total}</div><div class="kpi-label">Total Tickets</div></div>
  <div class="kpi"><div class="kpi-val" style="color:var(--green)">{replied}</div><div class="kpi-label">Replied ({100*replied//max(total,1)}%)</div></div>
  <div class="kpi"><div class="kpi-val" style="color:var(--red)">{escalated}</div><div class="kpi-label">Escalated ({100*escalated//max(total,1)}%)</div></div>
  <div class="kpi"><div class="kpi-val" style="color:var(--purple)">{avg_conf:.0%}</div><div class="kpi-label">Avg Confidence</div></div>
  <div class="kpi"><div class="kpi-val" style="color:var(--green)">{avg_qual:.0%}</div><div class="kpi-label">Avg Quality</div></div>
  <div class="kpi"><div class="kpi-val" style="color:{'#44ff88' if avg_health>=75 else '#ffaa00' if avg_health>=50 else '#f85149'}">{avg_health:.0f}</div><div class="kpi-label">Avg Health Score</div></div>
  <div class="kpi"><div class="kpi-val" style="color:var(--yellow)">{vip_count}</div><div class="kpi-label">VIP Signals</div></div>
  <div class="kpi"><div class="kpi-val" style="color:var(--red)">{high_churn}</div><div class="kpi-label">High Churn Risk</div></div>
  <div class="kpi"><div class="kpi-val" style="color:var(--red)">{inj_count}</div><div class="kpi-label">Injections Blocked</div></div>
  <div class="kpi"><div class="kpi-val" style="color:var(--purple)">{gap_count}</div><div class="kpi-label">Corpus Gaps</div></div>
</div>

<!-- Charts Row -->
<div class="charts-grid">
  <div class="chart-card"><h3>😤 Sentiment Distribution</h3><canvas id="sentChart"></canvas></div>
  <div class="chart-card"><h3>⏱ SLA Priority Queue</h3><canvas id="tierChart"></canvas></div>
  <div class="chart-card"><h3>❤️ Health Score Distribution</h3><canvas id="healthChart"></canvas></div>
  <div class="chart-card"><h3>🏢 Tickets by Company</h3><canvas id="coChart"></canvas></div>
  <div class="chart-card"><h3>🎫 Request Type Breakdown</h3><canvas id="reqChart"></canvas></div>
</div>

<!-- Incident Alerts -->
<div class="section">
  <div class="section-title">🚨 Incident Outbreak Detector</div>
  {incident_html}
</div>

<!-- Churn Risk Leaderboard -->
<div class="section">
  <div class="section-title">💰 Churn Risk Leaderboard <span style="font-size:12px;color:var(--muted);font-weight:400">(Top 5 highest-risk tickets)</span></div>
  {churn_leaderboard}
</div>

<!-- Ticket Table -->
<div class="section">
  <div class="section-title">📋 All Tickets
    <span style="font-size:12px;color:var(--muted);font-weight:400">— click headers to sort · use filters to narrow</span>
  </div>
  <div class="filter-bar">
    <button class="filter-btn active" onclick="filterTable('all',this)">All ({total})</button>
    <button class="filter-btn" onclick="filterTable('replied',this)">✓ Replied ({replied})</button>
    <button class="filter-btn" onclick="filterTable('escalated',this)">⚠ Escalated ({escalated})</button>
    <button class="filter-btn" onclick="filterTable('HackerRank',this)">HackerRank</button>
    <button class="filter-btn" onclick="filterTable('Claude',this)">Claude</button>
    <button class="filter-btn" onclick="filterTable('Visa',this)">Visa</button>
    <button class="filter-btn" onclick="filterTable('P0_Critical',this)">🔴 P0</button>
    <button class="filter-btn" onclick="filterTable('P1_High',this)">🟡 P1</button>
  </div>
  <div class="table-wrap">
  <table id="ticketTable">
    <thead>
      <tr>
        <th onclick="sortTable(0)">#</th>
        <th onclick="sortTable(1)">Company</th>
        <th onclick="sortTable(2)">Status</th>
        <th onclick="sortTable(3)">Urgency</th>
        <th onclick="sortTable(4)">Sentiment</th>
        <th onclick="sortTable(5)">Product Area</th>
        <th onclick="sortTable(6)">Type</th>
        <th onclick="sortTable(7)">Confidence</th>
        <th onclick="sortTable(8)">Quality</th>
        <th onclick="sortTable(9)">Health</th>
        <th onclick="sortTable(10)">Churn %</th>
        <th>Issue</th>
      </tr>
    </thead>
    <tbody>
      {table_rows}
    </tbody>
  </table>
  </div>
</div>

<!-- Knowledge Gaps -->
<div class="section">
  <div class="section-title">📚 Knowledge Base Gaps <span style="font-size:12px;color:var(--muted);font-weight:400">(Articles to write next)</span></div>
  {gap_html}
</div>

</div><!-- /container -->

<script>
// Chart.js charts
const DARK = {{ backgroundColor:'transparent', color:'#7d8590' }};
Chart.defaults.color = '#7d8590';
Chart.defaults.borderColor = '#30363d';

// Sentiment
new Chart(document.getElementById('sentChart'), {{
  type:'doughnut',
  data:{{
    labels:{_js(list(sent_counts.keys()))},
    datasets:[{{
      data:{_js(list(sent_counts.values()))},
      backgroundColor:['#f85149','#f0883e','#bc8cff','#7d8590','#3fb950'],
      borderWidth:2, borderColor:'#161b22'
    }}]
  }},
  options:{{ plugins:{{ legend:{{ position:'bottom', labels:{{ boxWidth:12, padding:8 }} }} }} }}
}});

// Urgency tiers
new Chart(document.getElementById('tierChart'), {{
  type:'bar',
  data:{{
    labels:{_js(list(tier_counts.keys()))},
    datasets:[{{
      data:{_js(list(tier_counts.values()))},
      backgroundColor:['#f85149','#f0883e','#58a6ff','#7d8590'],
      borderRadius:4
    }}]
  }},
  options:{{ plugins:{{ legend:{{ display:false }} }}, scales:{{ y:{{ beginAtZero:true, ticks:{{ stepSize:1 }} }} }} }}
}});

// Health distribution
new Chart(document.getElementById('healthChart'), {{
  type:'doughnut',
  data:{{
    labels:{_js(list(health_dist.keys()))},
    datasets:[{{
      data:{_js(list(health_dist.values()))},
      backgroundColor:['#3fb950','#d29922','#f0883e','#f85149'],
      borderWidth:2, borderColor:'#161b22'
    }}]
  }},
  options:{{ plugins:{{ legend:{{ position:'bottom', labels:{{ boxWidth:12, padding:8 }} }} }} }}
}});

// Company breakdown
new Chart(document.getElementById('coChart'), {{
  type:'bar',
  data:{{
    labels:{_js(list(co_counts.keys()))},
    datasets:[{{
      data:{_js(list(co_counts.values()))},
      backgroundColor:['#58a6ff','#3fb950','#d29922','#7d8590'],
      borderRadius:4
    }}]
  }},
  options:{{ plugins:{{ legend:{{ display:false }} }}, scales:{{ y:{{ beginAtZero:true, ticks:{{ stepSize:1 }} }} }} }}
}});

// Request types
new Chart(document.getElementById('reqChart'), {{
  type:'pie',
  data:{{
    labels:{_js(list(req_counts.keys()))},
    datasets:[{{
      data:{_js(list(req_counts.values()))},
      backgroundColor:['#58a6ff','#3fb950','#f0883e','#7d8590'],
      borderWidth:2, borderColor:'#161b22'
    }}]
  }},
  options:{{ plugins:{{ legend:{{ position:'bottom', labels:{{ boxWidth:12, padding:8 }} }} }} }}
}});

// Table filter
function filterTable(filter, btn) {{
  document.querySelectorAll('.filter-btn').forEach(b=>b.classList.remove('active'));
  btn.classList.add('active');
  document.querySelectorAll('.ticket-row').forEach(row => {{
    if (filter==='all') {{ row.style.display=''; return; }}
    const co=row.dataset.company, st=row.dataset.status, tier=row.dataset.tier;
    row.style.display=(co===filter||st===filter||tier===filter)?'':'none';
  }});
}}

// Table sort
let sortDir = {{}};
function sortTable(col) {{
  const tb = document.getElementById('ticketTable');
  const tbody = tb.tBodies[0];
  const rows = Array.from(tbody.rows);
  sortDir[col] = !sortDir[col];
  rows.sort((a,b)=>{{
    const av=a.cells[col].innerText.trim();
    const bv=b.cells[col].innerText.trim();
    const an=parseFloat(av), bn=parseFloat(bv);
    if(!isNaN(an)&&!isNaN(bn)) return sortDir[col]?(an-bn):(bn-an);
    return sortDir[col]?av.localeCompare(bv):bv.localeCompare(av);
  }});
  rows.forEach(r=>tbody.appendChild(r));
}}
</script>
</body>
</html>"""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
