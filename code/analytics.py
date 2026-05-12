"""
analytics.py — Feature 8: Executive Analytics Dashboard & Report Generator

Generates two outputs after processing a batch of tickets:

  1. RICH TERMINAL DASHBOARD  — live tables, charts, and breakdowns
     rendered directly in the terminal with colour and box-drawing chars.

  2. analytics_report.csv — machine-readable row-level intelligence data
     (one row per ticket with all intelligence signals, suitable for BI tools)

Dashboard sections:
  A. Batch Overview        — total, replied vs escalated, avg confidence
  B. SLA Priority Heatmap  — tickets by P0/P1/P2/P3
  C. Sentiment Distribution — emotional tone breakdown
  D. Corpus Coverage        — gap rate, avg retrieval score
  E. VIP Signals           — high-value accounts flagged
  F. Incident Alerts       — outbreak clusters detected
  G. Knowledge Gap Report  — suggested articles to write
  H. Quality Scorecard     — avg quality score, low-quality tickets
  I. Language Signals      — multilingual / injection detections

The analytics module is purely observational — it never modifies results.
It reads the final results list and renders insights on top.
"""

from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path
from typing import List, Optional

from rich.columns import Columns
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

from models import (
    IncidentReport, Sentiment, SupportTicket,
    TicketStatus, TriageResult, UrgencyTier,
)

console = Console()

# ── Colour palette ────────────────────────────────────────────────
_TIER_STYLE = {
    UrgencyTier.P0_CRITICAL: "bold red",
    UrgencyTier.P1_HIGH:     "bold yellow",
    UrgencyTier.P2_MEDIUM:   "cyan",
    UrgencyTier.P3_LOW:      "dim",
}
_SENTIMENT_STYLE = {
    Sentiment.ANGRY:      "red",
    Sentiment.FRUSTRATED: "yellow",
    Sentiment.DISTRESSED: "magenta",
    Sentiment.NEUTRAL:    "white",
    Sentiment.POSITIVE:   "green",
}
_SENTIMENT_EMOJI = {
    Sentiment.ANGRY:      "😠",
    Sentiment.FRUSTRATED: "😤",
    Sentiment.DISTRESSED: "😰",
    Sentiment.NEUTRAL:    "😐",
    Sentiment.POSITIVE:   "😊",
}
_SEV_STYLE = {"SEV1": "bold red", "SEV2": "bold yellow", "SEV3": "cyan"}


# ══════════════════════════════════════════════════════════════════
# Section A — Batch Overview
# ══════════════════════════════════════════════════════════════════

def _panel_overview(tickets, results) -> Panel:
    total     = len(results)
    replied   = sum(1 for r in results if r.status == TicketStatus.REPLIED)
    escalated = total - replied
    avg_conf  = sum(r.confidence.score for r in results) / max(total, 1)
    avg_qual  = sum(r.quality.score    for r in results) / max(total, 1)
    vip_count = sum(1 for r in results if r.vip.is_vip)
    gap_count = sum(1 for r in results if r.corpus_gap.gap_detected)
    lang_count= sum(1 for r in results if r.language.is_multilingual)
    inj_count = sum(1 for r in results if r.language.injection_in_foreign)
    low_qual  = sum(1 for r in results if r.quality.score < 0.5)

    t = Table(show_header=False, box=None, padding=(0, 2))
    t.add_column("Metric", style="bold")
    t.add_column("Value")

    t.add_row("Total Tickets",        f"[white bold]{total}[/]")
    t.add_row("Replied",              f"[green]{replied}[/] ({100*replied//max(total,1)}%)")
    t.add_row("Escalated",            f"[red]{escalated}[/] ({100*escalated//max(total,1)}%)")
    t.add_row("Avg Confidence",       f"[cyan]{avg_conf:.2f}[/] / 1.00")
    t.add_row("Avg Quality Score",    f"[cyan]{avg_qual:.2f}[/] / 1.00")
    t.add_row("VIP Signals",          f"[yellow]{vip_count}[/] tickets")
    t.add_row("Corpus Gaps",          f"[magenta]{gap_count}[/] tickets ({100*gap_count//max(total,1)}%)")
    t.add_row("Multilingual",         f"[blue]{lang_count}[/] tickets")
    t.add_row("Injection Attempts",   f"[red bold]{inj_count}[/] tickets")
    t.add_row("Low Quality (<0.5)",   f"[red]{low_qual}[/] tickets flagged")

    return Panel(t, title="[bold cyan]📊 Batch Overview[/bold cyan]", border_style="cyan")


# ══════════════════════════════════════════════════════════════════
# Section B — SLA Priority Heatmap
# ══════════════════════════════════════════════════════════════════

def _panel_sla(tickets, results) -> Panel:
    tier_counts = Counter(r.urgency.tier for r in results)
    t = Table(show_header=True, box=None)
    t.add_column("Priority", style="bold", width=14)
    t.add_column("SLA",      width=8)
    t.add_column("Count",    width=6)
    t.add_column("Bar",      min_width=20)
    t.add_column("Ticket #s")

    tiers = [
        (UrgencyTier.P0_CRITICAL, "< 1h"),
        (UrgencyTier.P1_HIGH,     "< 4h"),
        (UrgencyTier.P2_MEDIUM,   "< 24h"),
        (UrgencyTier.P3_LOW,      "< 72h"),
    ]

    for tier, sla in tiers:
        count   = tier_counts.get(tier, 0)
        style   = _TIER_STYLE[tier]
        bar_len = int(count / max(len(results), 1) * 20)
        bar     = "█" * bar_len + "░" * (20 - bar_len)
        nums    = [str(i+1) for i, r in enumerate(results) if r.urgency.tier == tier]
        t.add_row(
            Text(tier.value, style=style),
            sla,
            str(count),
            Text(bar, style=style),
            ", ".join(nums[:8]) + ("…" if len(nums) > 8 else ""),
        )

    return Panel(t, title="[bold yellow]⏱  SLA Priority Queue[/bold yellow]", border_style="yellow")


# ══════════════════════════════════════════════════════════════════
# Section C — Sentiment Distribution
# ══════════════════════════════════════════════════════════════════

def _panel_sentiment(results) -> Panel:
    sent_counts = Counter(r.sentiment.sentiment for r in results)
    t = Table(show_header=True, box=None)
    t.add_column("Sentiment", style="bold", width=14)
    t.add_column("Count", width=6)
    t.add_column("Intensity (avg)", width=16)
    t.add_column("Bar", min_width=18)

    for sentiment in Sentiment:
        count = sent_counts.get(sentiment, 0)
        if count == 0:
            continue
        relevant = [r for r in results if r.sentiment.sentiment == sentiment]
        avg_int  = sum(r.sentiment.intensity for r in relevant) / max(len(relevant), 1)
        bar_len  = int(count / max(len(results), 1) * 18)
        emoji    = _SENTIMENT_EMOJI.get(sentiment, "")
        style    = _SENTIMENT_STYLE.get(sentiment, "white")
        bar      = "█" * bar_len + "░" * (18 - bar_len)
        t.add_row(
            Text(f"{emoji} {sentiment.value}", style=style),
            str(count),
            f"{avg_int:.2f}",
            Text(bar, style=style),
        )

    return Panel(t, title="[bold magenta]🎭 Sentiment Distribution[/bold magenta]", border_style="magenta")


# ══════════════════════════════════════════════════════════════════
# Section D — Corpus Coverage
# ══════════════════════════════════════════════════════════════════

def _panel_corpus(tickets, results) -> Panel:
    gap_results = [(i, r.corpus_gap) for i, r in enumerate(results) if r.corpus_gap.gap_detected]
    total       = len(results)
    gap_count   = len(gap_results)
    coverage    = 1 - gap_count / max(total, 1)
    avg_score   = sum(r.corpus_gap.max_retrieval_score for r in results) / max(total, 1)

    t = Table(show_header=False, box=None)
    t.add_column("Key",   style="bold", width=22)
    t.add_column("Value")

    bar_len = int(coverage * 20)
    bar     = "[green]" + "█" * bar_len + "[/][red]" + "░" * (20 - bar_len) + "[/]"
    t.add_row("Coverage Rate",     f"{coverage:.0%}  {bar}")
    t.add_row("Avg Retrieval Score", f"[cyan]{avg_score:.3f}[/]")
    t.add_row("Gaps Detected",      f"[red]{gap_count}[/] / {total}")

    if gap_results:
        t.add_row("", "")
        t.add_row("[bold]Suggested Articles[/]", "")
        suggested = list({
            r.corpus_gap.suggested_doc_title
            for _, gap in gap_results
            for r in [results[_]]
            if r.corpus_gap.suggested_doc_title
        })
        for s in suggested[:5]:
            t.add_row(" •", f"[dim]{s[:60]}[/]")

    return Panel(t, title="[bold blue]📚 Corpus Coverage[/bold blue]", border_style="blue")


# ══════════════════════════════════════════════════════════════════
# Section E — VIP Signals
# ══════════════════════════════════════════════════════════════════

def _panel_vip(tickets, results) -> Panel:
    vip_list = [(i, tickets[i], results[i]) for i in range(len(results))
                if results[i].vip.is_vip]

    if not vip_list:
        return Panel("[dim]No VIP signals detected in this batch.[/dim]",
                     title="[bold yellow]⭐ VIP Signals[/bold yellow]", border_style="yellow")

    t = Table(show_header=True, box=None)
    t.add_column("#", width=4)
    t.add_column("Company",  width=12)
    t.add_column("Signals",  width=28)
    t.add_column("Issue",    min_width=30)

    for i, ticket, result in vip_list:
        signals_str = ", ".join(result.vip.signals)
        issue_preview = ticket.issue[:50].replace("\n", " ") + "…"
        t.add_row(str(i+1), ticket.company, f"[yellow]{signals_str}[/]", issue_preview)

    return Panel(t, title="[bold yellow]⭐ VIP / High-Value Signals[/bold yellow]", border_style="yellow")


# ══════════════════════════════════════════════════════════════════
# Section F — Incident Alerts
# ══════════════════════════════════════════════════════════════════

def _panel_incidents(incidents: List[IncidentReport]) -> Panel:
    if not incidents:
        return Panel("[green]✓ No incident clusters detected.[/green]",
                     title="[bold red]🚨 Incident Outbreak Detector[/bold red]", border_style="red")

    t = Table(show_header=True, box=None)
    t.add_column("ID",         width=14, style="bold")
    t.add_column("Sev",        width=6)
    t.add_column("Company",    width=12)
    t.add_column("Area",       width=20)
    t.add_column("Tickets",    width=8)
    t.add_column("Ticket #s",  min_width=20)

    for inc in incidents:
        sev_style = _SEV_STYLE.get(inc.severity.value, "white")
        nums_str  = ", ".join(str(n) for n in inc.ticket_indices[:8])
        if len(inc.ticket_indices) > 8:
            nums_str += "…"
        t.add_row(
            inc.cluster_id,
            Text(inc.severity.value, style=sev_style),
            inc.company,
            inc.product_area[:20],
            str(inc.ticket_count),
            nums_str,
        )
    # Show recommended actions
    content = t
    extra   = "\n".join(f"  [bold]{inc.cluster_id}[/] → {inc.recommended_action}"
                        for inc in incidents)

    body = Table(show_header=False, box=None)
    body.add_column("x")
    body.add_row(t)
    body.add_row(Text("\n🔔 Recommended Actions:", style="bold"))
    for inc in incidents:
        sev_style = _SEV_STYLE.get(inc.severity.value, "white")
        body.add_row(f"  [{sev_style}]{inc.cluster_id}[/] → {inc.recommended_action}")

    return Panel(body, title="[bold red]🚨 Incident Outbreak Detector[/bold red]", border_style="red")


# ══════════════════════════════════════════════════════════════════
# Section G — Language & Security Signals
# ══════════════════════════════════════════════════════════════════

def _panel_language(results) -> Panel:
    multilingual = [(i, r) for i, r in enumerate(results) if r.language.is_multilingual]
    injections   = [(i, r) for i, r in enumerate(results) if r.language.injection_in_foreign]

    t = Table(show_header=False, box=None)
    t.add_column("Key",   style="bold", width=24)
    t.add_column("Value")

    lang_dist = Counter(r.language.detected for r in results)
    t.add_row("Language Distribution", str(dict(lang_dist.most_common(5))))
    t.add_row("Multilingual Tickets",  f"[blue]{len(multilingual)}[/]")
    t.add_row("Injection Attempts",    f"[red bold]{len(injections)}[/]")

    if injections:
        for i, r in injections:
            t.add_row(f"  Ticket #{i+1}", f"[red]{r.language.translation_hint or 'injection detected'}[/]")

    return Panel(t, title="[bold blue]🌍 Language & Security Signals[/bold blue]", border_style="blue")


# ══════════════════════════════════════════════════════════════════
# Section H — Quality Scorecard
# ══════════════════════════════════════════════════════════════════

def _panel_quality(tickets, results) -> Panel:
    avg_q   = sum(r.quality.score for r in results) / max(len(results), 1)
    low_q   = [(i, results[i]) for i in range(len(results)) if results[i].quality.score < 0.5]
    grounded= sum(1 for r in results if r.quality.is_grounded)
    answers = sum(1 for r in results if r.quality.answers_the_question)

    # Bucketed histogram
    buckets = {"0.0–0.4": 0, "0.4–0.6": 0, "0.6–0.8": 0, "0.8–1.0": 0}
    for r in results:
        q = r.quality.score
        if q < 0.4:
            buckets["0.0–0.4"] += 1
        elif q < 0.6:
            buckets["0.4–0.6"] += 1
        elif q < 0.8:
            buckets["0.6–0.8"] += 1
        else:
            buckets["0.8–1.0"] += 1

    t = Table(show_header=False, box=None)
    t.add_column("Key",   style="bold", width=28)
    t.add_column("Value")

    style_avg = "green" if avg_q >= 0.7 else "yellow" if avg_q >= 0.5 else "red"
    t.add_row("Avg Quality Score",      f"[{style_avg}]{avg_q:.3f}[/]")
    t.add_row("Grounded Responses",     f"{grounded} / {len(results)}")
    t.add_row("Questions Answered",     f"{answers} / {len(results)}")
    t.add_row("Distribution", "")
    for bucket, cnt in buckets.items():
        bar = "█" * int(cnt / max(len(results), 1) * 15)
        colour = "red" if bucket.startswith("0.0") else "yellow" if bucket.startswith("0.4") else "green"
        t.add_row(f"  {bucket}", f"[{colour}]{bar}[/] {cnt}")

    if low_q:
        t.add_row("Flagged Tickets", f"[red]{', '.join(str(i+1) for i, _ in low_q[:8])}[/]")

    return Panel(t, title="[bold green]✅ Response Quality Scorecard[/bold green]", border_style="green")


# ══════════════════════════════════════════════════════════════════
# Main dashboard renderer
# ══════════════════════════════════════════════════════════════════

def render_dashboard(
    tickets: List[SupportTicket],
    results: List[TriageResult],
    incidents: List[IncidentReport],
) -> None:
    """Print the full executive analytics dashboard to the terminal."""
    console.print()
    console.print(Rule("[bold cyan]  SUPPORT TRIAGE  ·  ANALYTICS DASHBOARD  [/bold cyan]"))

    # Row 1: Overview + SLA
    console.print(Columns([
        _panel_overview(tickets, results),
        _panel_sla(tickets, results),
    ]))

    # Row 2: Sentiment + Quality
    console.print(Columns([
        _panel_sentiment(results),
        _panel_quality(tickets, results),
    ]))

    # Row 3: Corpus + Language
    console.print(Columns([
        _panel_corpus(tickets, results),
        _panel_language(results),
    ]))

    # Row 4: Incidents (full width)
    console.print(_panel_incidents(incidents))

    # Row 5: VIP (full width)
    console.print(_panel_vip(tickets, results))

    console.print(Rule("[bold cyan]  END OF DASHBOARD  [/bold cyan]"))


# ══════════════════════════════════════════════════════════════════
# Analytics CSV export
# ══════════════════════════════════════════════════════════════════

def export_analytics_csv(
    tickets: List[SupportTicket],
    results: List[TriageResult],
    incidents: List[IncidentReport],
    output_path: Path,
) -> None:
    """
    Export row-level analytics data to CSV.
    Each row = one ticket with all intelligence signals.
    """
    fieldnames = [
        "ticket_num", "company", "status", "request_type", "product_area",
        # Urgency
        "urgency_tier", "sla_hours", "urgency_score", "urgency_triggers",
        # Sentiment
        "sentiment", "sentiment_intensity", "emotional_markers",
        # Confidence
        "confidence_score", "retrieval_quality", "classification_certainty", "confidence_reasoning",
        # Language
        "detected_language", "is_multilingual", "injection_in_foreign", "language_hint",
        # Corpus gap
        "corpus_gap", "max_retrieval_score", "gap_description", "suggested_article",
        # Quality
        "quality_score", "answers_question", "is_grounded", "quality_issues", "follow_up_questions",
        # VIP
        "is_vip", "vip_signals",
        # Incident
        "incident_cluster_id",
        # Issue preview
        "issue_preview",
    ]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        for i, (ticket, result) in enumerate(zip(tickets, results)):
            writer.writerow({
                "ticket_num":               i + 1,
                "company":                  ticket.company,
                "status":                   result.status.value,
                "request_type":             result.request_type.value,
                "product_area":             result.product_area,
                # Urgency
                "urgency_tier":             result.urgency.tier.value,
                "sla_hours":                result.urgency.sla_hours,
                "urgency_score":            result.urgency.urgency_score,
                "urgency_triggers":         "|".join(result.urgency.triggers),
                # Sentiment
                "sentiment":                result.sentiment.sentiment.value,
                "sentiment_intensity":      result.sentiment.intensity,
                "emotional_markers":        "|".join(result.sentiment.emotional_markers),
                # Confidence
                "confidence_score":         result.confidence.score,
                "retrieval_quality":        result.confidence.retrieval_quality,
                "classification_certainty": result.confidence.classification_certainty,
                "confidence_reasoning":     result.confidence.reasoning,
                # Language
                "detected_language":        result.language.detected,
                "is_multilingual":          result.language.is_multilingual,
                "injection_in_foreign":     result.language.injection_in_foreign,
                "language_hint":            result.language.translation_hint,
                # Corpus gap
                "corpus_gap":               result.corpus_gap.gap_detected,
                "max_retrieval_score":      result.corpus_gap.max_retrieval_score,
                "gap_description":          result.corpus_gap.gap_description,
                "suggested_article":        result.corpus_gap.suggested_doc_title,
                # Quality
                "quality_score":            result.quality.score,
                "answers_question":         result.quality.answers_the_question,
                "is_grounded":              result.quality.is_grounded,
                "quality_issues":           "|".join(result.quality.issues),
                "follow_up_questions":      "|".join(result.quality.follow_up_questions),
                # VIP
                "is_vip":                   result.vip.is_vip,
                "vip_signals":              "|".join(result.vip.signals),
                # Incident
                "incident_cluster_id":      result.incident_cluster_id or "",
                # Issue preview
                "issue_preview":            ticket.issue[:120].replace("\n", " "),
            })

    console.print(f"[green]✓ Analytics data → {output_path}[/green]")
