#!/usr/bin/env python3
"""
Support Triage Agent — World-Class Production Runner
=====================================================

Processes support_tickets.csv through an 18-feature AI triage pipeline
covering HackerRank, Claude, and Visa support domains.

Outputs (all written to output/ directory):
  output.csv            — submission-ready triage results
  analytics_report.csv  — 33-column per-ticket intelligence data
  audit_trail.csv       — SHA-256 chained compliance audit log
  dashboard.html        — visual executive dashboard (open in browser)
  faq/faq_draft.md      — auto-generated FAQ entries (markdown)
  faq/faq_entries.json  — machine-readable FAQ entries

Usage:
  python code/run_agent.py
  python code/run_agent.py --input path/to/tickets.csv
  python code/run_agent.py --verbose
  python code/run_agent.py --no-dashboard
  python code/run_agent.py --sample   (use sample_support_tickets.csv)
"""

import csv
import os
import sys
import time
from pathlib import Path
from typing import List

# ── Handle Windows UTF-8 encoding for Rich ────────────────────────────────
if sys.platform == "win32":
    # Force UTF-8 output on Windows to prevent Unicode errors with Rich
    import io

    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ── Path setup: works whether run from project root OR code/ directory ──────
_THIS_FILE = Path(__file__).resolve()
_CODE_DIR = _THIS_FILE.parent
_PROJ_ROOT = _CODE_DIR.parent
sys.path.insert(0, str(_CODE_DIR))

from rich.console import Console
from rich.rule import Rule
from rich.text import Text

# ── Core pipeline ─────────────────────────────────────────────────────────
from corpus import load_or_build_corpus
from retriever import HybridRetriever, RETRIEVER_CFG
from models import (
    SupportTicket,
    TriageResult,
    TicketStatus,
    RequestType,
    SentimentSignal,
    UrgencySignal,
    ConfidenceSignal,
    LanguageSignal,
    CorpusGapSignal,
    QualitySignal,
    VIPSignal,
)
from response_engine import GroundedResponseEngine
from agent import infer_company

# ── Intelligence features ──────────────────────────────────────────────────
from intelligence import (
    analyse_sentiment,
    compute_urgency,
    detect_vip,
    analyse_language,
    compute_confidence,
)
from corpus_gap_detector import detect_corpus_gap
from quality_validator import validate_response
from incident_detector import detect_incidents
from analytics import render_dashboard, export_analytics_csv

# ── Commercial features ────────────────────────────────────────────────────
from pii_redactor import redact as pii_redact
from churn_risk import score_churn_risk, ChurnRiskResult
from tone_personalizer import detect_tone_profile, personalize_response
from deduplicator import find_duplicates
from faq_builder import build_faq_entry, save_faq_entries
from audit_trail import AuditTrail
from prevention_advisor import generate_prevention_tip
from health_score import compute_health_score, HealthScoreResult
from html_dashboard import generate_html_dashboard

console = Console()

# Required output columns
OUTPUT_COLS = [
    "issue",
    "subject",
    "company",
    "response",
    "product_area",
    "status",
    "request_type",
    "justification",
]


# ─────────────────────────────────────────────────────────────────────────
# I/O
# ─────────────────────────────────────────────────────────────────────────


def read_tickets(path: Path) -> List[SupportTicket]:
    tickets: List[SupportTicket] = []
    with open(path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            norm = {k.strip().lower(): (v or "").strip() for k, v in row.items()}
            tickets.append(
                SupportTicket(
                    issue=norm.get("issue", ""),
                    subject=norm.get("subject", ""),
                    company=norm.get("company", "None"),
                )
            )
    return tickets


def write_output(tickets: List[SupportTicket], results: List[TriageResult], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_COLS, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        for ticket, result in zip(tickets, results):
            writer.writerow(
                {
                    "issue": ticket.issue,
                    "subject": ticket.subject,
                    "company": ticket.company,
                    "response": result.response,
                    "product_area": result.product_area,
                    "status": result.status.value.capitalize(),
                    "request_type": result.request_type.value,
                    "justification": result.justification,
                }
            )
    console.print(f"  [green]✓[/green] output.csv  →  {path}")


# ─────────────────────────────────────────────────────────────────────────
# Enrichment — attaches all intelligence signals
# ─────────────────────────────────────────────────────────────────────────


def enrich(ticket: SupportTicket, result: TriageResult, docs: list) -> TriageResult:
    """
    Pure enrichment pass: attaches 8 intelligence signals to a TriageResult.
    Never changes product_area or response — only adds signal fields.
    Auto-escalates if quality score is critically low.
    """
    retrieval_scores = [d.score for d in docs] if docs else []
    co = ticket.company if ticket.company not in ("None", "", None) else infer_company(ticket)

    result.sentiment = analyse_sentiment(ticket)
    result.language = analyse_language(ticket)
    result.corpus_gap = detect_corpus_gap(ticket, docs, co)
    result.confidence = compute_confidence(
        retrieval_scores=retrieval_scores,
        is_escalated=(result.status == TicketStatus.ESCALATED),
        corpus_gap=result.corpus_gap.gap_detected,
        language=result.language,
        ticket=ticket,
    )
    result.urgency = compute_urgency(
        ticket=ticket,
        sentiment=result.sentiment,
        is_escalated=(result.status == TicketStatus.ESCALATED),
    )
    result.vip = detect_vip(ticket)
    result.quality = validate_response(
        ticket=ticket,
        response=result.response,
        status=result.status.value,
        docs=docs,
    )

    # Auto-escalate critically low quality replied tickets
    if (
        result.quality.score < 0.4
        and result.status == TicketStatus.REPLIED
        and result.request_type != RequestType.INVALID
    ):
        result.status = TicketStatus.ESCALATED
        result.justification += " [AUTO-ESCALATED: quality validator score < 0.4]"

    return result


# ─────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────


def main() -> None:
    import argparse

    ISSUES_DIR = _PROJ_ROOT / "support_issues"
    OUTPUT_DIR = _PROJ_ROOT / "output"

    parser = argparse.ArgumentParser(
        description="Support Triage Agent — World-Class Edition",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--input", type=Path, default=ISSUES_DIR / "support_tickets.csv")
    parser.add_argument("--output", type=Path, default=OUTPUT_DIR / "output.csv")
    parser.add_argument("--sample", action="store_true", help="Run on sample_support_tickets.csv")
    parser.add_argument("--rebuild", action="store_true", help="Force re-scrape the support corpus")
    parser.add_argument(
        "--verbose", action="store_true", help="Show enrichment signals for each ticket"
    )
    parser.add_argument(
        "--no-dashboard", action="store_true", help="Skip the terminal analytics dashboard"
    )
    args = parser.parse_args()

    if args.sample:
        args.input = ISSUES_DIR / "sample_support_tickets.csv"

    out_dir = args.output.parent
    analytics_path = out_dir / "analytics_report.csv"
    audit_path = out_dir / "audit_trail.csv"
    faq_dir = out_dir / "faq"
    dashboard_path = out_dir / "dashboard.html"
    out_dir.mkdir(parents=True, exist_ok=True)

    # ── Banner ───────────────────────────────────────────────────────────
    console.print()
    console.print(Rule("[bold cyan]  Support Triage Agent  ·  World-Class Edition  [/bold cyan]"))
    console.print("[dim]  HackerRank · Claude · Visa  |  18 intelligence features[/dim]")
    console.print()

    # ═══════════════════════════════════════
    # STEP 1 — Corpus
    # ═══════════════════════════════════════
    console.print("[bold]1/5  Knowledge Corpus[/bold]")
    from scraper import build_corpus

    corpus = build_corpus(force=args.rebuild)
    companies = sorted(set(c.source for c in corpus))
    console.print(
        f"  [green]✓[/green] {len(corpus):,} chunks across "
        f"{len(companies)} knowledge bases: {', '.join(companies)}\n"
    )

    # ═══════════════════════════════════════
    # STEP 2 — Retrieval Index
    # ═══════════════════════════════════════
    console.print("[bold]2/5  Retrieval Index (BM25 + TF-IDF)[/bold]")
    t0 = time.time()
    retriever = HybridRetriever(corpus, RETRIEVER_CFG)
    console.print(f"  [green]✓[/green] Index ready in {time.time()-t0:.2f}s\n")

    # ═══════════════════════════════════════
    # STEP 3 — Load Tickets
    # ═══════════════════════════════════════
    console.print(f"[bold]3/5  Loading Tickets[/bold]  ({args.input.name})")
    if not args.input.exists():
        console.print(f"\n  [red]✗ File not found:[/red] {args.input}")
        console.print(
            "  Place your support_tickets.csv in the [bold]support_issues/[/bold] folder.\n"
        )
        sys.exit(1)
    tickets = read_tickets(args.input)
    console.print(f"  [green]✓[/green] {len(tickets)} tickets loaded\n")

    # ═══════════════════════════════════════
    # STEP 4 — Triage + Enrich
    # ═══════════════════════════════════════
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if api_key:
        from agent import TriageAgent

        engine = TriageAgent(retriever)
        run_one = engine.triage
        mode = "Claude Sonnet (LLM mode)"
    else:
        g_engine = GroundedResponseEngine(retriever)
        run_one = g_engine.process
        mode = "Grounded deterministic (no API key needed)"

    console.print(f"[bold]4/5  Triaging[/bold]  [cyan]{mode}[/cyan]\n")
    console.print(
        f"  [dim]{'#':>3}  {'Status':11} {'Priority':13} {'Sentiment':13}"
        f" {'Conf':6} {'Qual':6} {'Health':7} {'Churn':7}  Issue[/dim]"
    )
    console.print("  " + "─" * 98)

    results: List[TriageResult] = []
    all_docs: list = []
    churns: List[ChurnRiskResult] = []
    healths: List[HealthScoreResult] = []
    pii_risks: List[str] = []
    faq_entries: list = []
    audit = AuditTrail(audit_path)

    for i, ticket in enumerate(tickets, 1):
        try:
            # 4a. Base triage
            result = run_one(ticket)

            # 4b. Retrieve docs for enrichment
            co = (
                ticket.company
                if ticket.company not in ("None", "", None)
                else infer_company(ticket)
            )
            query = f"{ticket.subject} {ticket.issue}".strip()
            docs = retriever.retrieve(query, company=co, top_k=5)
            all_docs.append(docs)

            # 4c. Intelligence enrichment (8 signals)
            result = enrich(ticket, result, docs)

            # Feature 9: PII detection
            pii_report = pii_redact(ticket.issue)
            pii_risks.append(pii_report.risk_level)

            # Feature 10: Churn risk
            churn = score_churn_risk(ticket, result)
            churns.append(churn)

            # Feature 11: Tone personalization (safe — checks for duplicate openers)
            tone_profile = detect_tone_profile(ticket)
            result.response = personalize_response(
                response=result.response,
                profile=tone_profile,
                request_type=result.request_type.value,
                status=result.status.value,
            )

            # Feature 15: Prevention tip (appended only for replied tickets)
            if result.status == TicketStatus.REPLIED:
                tip = generate_prevention_tip(ticket, result)
                if tip:
                    result.response += f"\n\n{tip}"

            # Feature 16: Customer health score
            health = compute_health_score(ticket, result, churn)
            healths.append(health)

            # Feature 13: FAQ entry
            faq = build_faq_entry(ticket, result, i)
            if faq:
                faq_entries.append(faq)

            # Feature 14: Audit trail entry
            audit.record(
                ticket_num=i,
                ticket=ticket,
                result=result,
                pii_risk=pii_report.risk_level,
                churn_score=churn.churn_risk_score,
            )

            results.append(result)

            # Progress line
            st_style = "green" if result.status == TicketStatus.REPLIED else "red"
            st_label = "✓ replied   " if result.status == TicketStatus.REPLIED else "⚠ escalated "
            tier_style = {
                "P0_Critical": "bold red",
                "P1_High": "yellow",
                "P2_Medium": "cyan",
                "P3_Low": "dim",
            }.get(result.urgency.tier.value, "white")
            sent_style = {
                "angry": "red",
                "frustrated": "yellow",
                "distressed": "magenta",
                "neutral": "dim",
                "positive": "green",
            }.get(result.sentiment.sentiment.value, "white")
            conf_c = (
                "green"
                if result.confidence.score >= 0.7
                else "yellow" if result.confidence.score >= 0.4 else "red"
            )
            qual_c = (
                "green"
                if result.quality.score >= 0.7
                else "yellow" if result.quality.score >= 0.4 else "red"
            )
            hlth_c = (
                "green"
                if health.health_score >= 75
                else "yellow" if health.health_score >= 50 else "red"
            )
            chrn_c = (
                "red"
                if churn.churn_risk_score >= 70
                else "yellow" if churn.churn_risk_score >= 45 else "dim"
            )
            preview = ticket.issue[:34].replace("\n", " ")

            console.print(
                f"  {i:>3}  [{st_style}]{st_label}[/]"
                f"[{tier_style}]{result.urgency.tier.value:13}[/]"
                f"[{sent_style}]{result.sentiment.sentiment.value:13}[/]"
                f"[{conf_c}]{result.confidence.score:.2f}[/]  "
                f"[{qual_c}]{result.quality.score:.2f}[/]  "
                f"[{hlth_c}]{health.health_score:>3}[/]    "
                f"[{chrn_c}]{churn.churn_risk_score:>3}[/]  "
                f"[dim]{preview}…[/]",
                highlight=False,
            )

            if args.verbose:
                if result.vip.is_vip:
                    console.print(f"       [yellow]⭐ VIP: {', '.join(result.vip.signals)}[/]")
                if pii_report.pii_count:
                    console.print(
                        f"       [magenta]🔐 PII({pii_report.risk_level}): {', '.join(pii_report.pii_types_found)}[/]"
                    )
                if result.language.injection_in_foreign:
                    console.print(
                        f"       [red]🌍 INJECTION: {result.language.translation_hint}[/]"
                    )
                if result.corpus_gap.gap_detected:
                    console.print(
                        f"       [blue]📚 Gap: {result.corpus_gap.suggested_doc_title[:60]}[/]"
                    )
                if churn.churn_risk_score >= 45:
                    console.print(
                        f"       [red]💰 Churn {churn.churn_risk_score}/100 — {churn.retention_priority}[/]"
                    )

        except Exception as exc:
            console.print(f"  {i:>3}  [red]✗ ERROR: {exc}[/red]")
            if args.verbose:
                import traceback

                traceback.print_exc()
            fallback = TriageResult(
                status=TicketStatus.ESCALATED,
                product_area="general_support",
                response="An unexpected error occurred processing this ticket. A human agent will review it promptly.",
                justification=f"Processing error: {exc}",
                request_type=RequestType.PRODUCT_ISSUE,
            )
            results.append(fallback)
            all_docs.append([])
            churns.append(ChurnRiskResult())
            healths.append(HealthScoreResult())
            pii_risks.append("low")
            audit.record(i, ticket, fallback, pii_risk="low", churn_score=0)

    # ═══════════════════════════════════════
    # STEP 5 — Post-processing & Outputs
    # ═══════════════════════════════════════
    console.print(f"\n[bold]5/5  Post-Processing & Writing Outputs[/bold]\n")

    # Feature 7: Incident outbreak detection
    incidents, clusters = detect_incidents(tickets, results)
    for idx, cid in clusters.items():
        results[idx].incident_cluster_id = cid
    if incidents:
        for inc in incidents:
            sc = {"SEV1": "bold red", "SEV2": "bold yellow", "SEV3": "cyan"}.get(
                inc.severity.value, "white"
            )
            console.print(f"  [bold]🚨 Incident[/bold] [{sc}]{inc.cluster_id}[/]  {inc.title}")
    else:
        console.print("  [green]✓ No incident clusters detected[/green]")

    # Feature 12: Deduplication
    dedup_results, dup_groups = find_duplicates([t.issue for t in tickets])
    if dup_groups:
        for g in dup_groups:
            dups = ", ".join(f"#{d}" for d in g.duplicate_idxs)
            console.print(
                f"  [yellow]⚡ Duplicate group:[/yellow] "
                f"#{g.master_idx} ≈ {dups} "
                f"(sim={g.similarity:.0%}, topic: {g.shared_topic})"
            )
    else:
        console.print("  [green]✓ No duplicate tickets detected[/green]")

    console.print()

    # Write all outputs
    write_output(tickets, results, args.output)

    export_analytics_csv(tickets, results, incidents, analytics_path)
    console.print(f"  [green]✓[/green] analytics_report.csv  →  {analytics_path}")

    audit.save()
    console.print(f"  [green]✓[/green] audit_trail.csv  →  {audit_path}")
    console.print(f"       {audit.integrity_summary()}")

    if faq_entries:
        save_faq_entries(faq_entries, faq_dir)
        console.print(f"  [green]✓[/green] faq/ ({len(faq_entries)} entries)  →  {faq_dir}/")

    generate_html_dashboard(
        tickets=tickets,
        results=results,
        incidents=incidents,
        churns=churns,
        healths=healths,
        output_path=dashboard_path,
    )
    console.print(f"  [green]✓[/green] dashboard.html  →  {dashboard_path}")

    # Feature 8: Terminal dashboard
    if not args.no_dashboard:
        render_dashboard(tickets, results, incidents)

    # ── Summary ──────────────────────────────────────────────────────────
    total = len(results)
    replied = sum(1 for r in results if r.status == TicketStatus.REPLIED)
    p0_count = sum(1 for r in results if r.urgency.tier.value == "P0_Critical")
    vip_count = sum(1 for r in results if r.vip.is_vip)
    inj_count = sum(1 for r in results if r.language.injection_in_foreign)
    avg_qual = sum(r.quality.score for r in results) / max(total, 1)
    avg_hlth = sum(h.health_score for h in healths) / max(total, 1)
    hi_churn = sum(1 for c in churns if c.churn_risk_score >= 45)

    console.print()
    console.print(Rule("[bold cyan]  Run Complete  [/bold cyan]"))
    console.print(f"""
  [bold]Triage Summary[/bold]
  ├─ Total tickets:     {total}
  ├─ Replied:           [green]{replied}[/green] ({100*replied//max(total,1)}%)
  ├─ Escalated:         [red]{total-replied}[/red] ({100*(total-replied)//max(total,1)}%)
  ├─ P0 Critical:       [bold red]{p0_count}[/bold red]
  ├─ VIP signals:       [yellow]{vip_count}[/yellow]
  ├─ Injections blocked:[red]{inj_count}[/red]
  ├─ High churn risk:   [red]{hi_churn}[/red]
  ├─ Avg quality:       [cyan]{avg_qual:.0%}[/cyan]
  └─ Avg health score:  [cyan]{avg_hlth:.0f}/100[/cyan]

  [bold]Output files → {out_dir}/[/bold]
  ├─ 📄  output.csv            (submit this)
  ├─ 📊  analytics_report.csv  (33-column intelligence data)
  ├─ 🔐  audit_trail.csv       (SHA-256 compliance log)
  ├─ 📖  faq/faq_draft.md      (auto-generated FAQ)
  ├─ 📖  faq/faq_entries.json  (machine-readable FAQ)
  └─ 🌐  dashboard.html        (open in browser)
""")


if __name__ == "__main__":
    main()
