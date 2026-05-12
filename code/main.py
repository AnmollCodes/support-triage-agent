#!/usr/bin/env python3
"""
Support Triage Agent  — Main CLI Entry Point

Usage:
    python main.py [OPTIONS]

Options:
    --input   PATH   Input CSV (default: ../support_issues/support_issues.csv)
    --output  PATH   Output CSV (default: ../support_issues/output.csv)
    --sample         Run on sample_support_issues.csv instead
    --rebuild        Force re-scrape of the support corpus
    --dry-run        Print one ticket result; don't write CSV
    --ticket  N      Process only ticket N (0-indexed)
    --verbose        Show retrieved docs for each ticket

Examples:
    python main.py
    python main.py --rebuild --verbose
    python main.py --sample
    python main.py --dry-run --ticket 0
"""

from __future__ import annotations

import argparse
import csv
import sys
import time
from pathlib import Path
from typing import List, Optional

from rich.columns import Columns
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

# ── Project imports ───────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent))

from agent import TriageAgent
from config import INPUT_CSV, OUTPUT_CSV, SAMPLE_CSV, RETRIEVER_CFG
from corpus import load_or_build_corpus
from models import SupportTicket, TriageResult
from retriever import HybridRetriever

console = Console()


# ─────────────────────────────────────────────────────────────────
# CSV helpers
# ─────────────────────────────────────────────────────────────────


def read_tickets(path: Path) -> List[SupportTicket]:
    """Read support_issues CSV and return validated SupportTicket list."""
    tickets: List[SupportTicket] = []
    with open(path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Normalise column names (lowercase, strip)
            norm = {k.strip().lower(): v for k, v in row.items()}
            tickets.append(
                SupportTicket(
                    issue=norm.get("issue", ""),
                    subject=norm.get("subject", ""),
                    company=norm.get("company", "None"),
                )
            )
    return tickets


def write_results(results: List[TriageResult], path: Path) -> None:
    """Write results to output CSV."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["status", "product_area", "response", "justification", "request_type"]
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        for r in results:
            writer.writerow(
                {
                    "status": r.status.value,
                    "product_area": r.product_area,
                    "response": r.response,
                    "justification": r.justification,
                    "request_type": r.request_type.value,
                }
            )
    console.print(f"\n[green bold]✓ Output written to {path}[/green bold]")


# ─────────────────────────────────────────────────────────────────
# Display helpers
# ─────────────────────────────────────────────────────────────────

STATUS_STYLE = {
    "replied": "[green]✓ replied[/green]",
    "escalated": "[red]⚠ escalated[/red]",
}

REQTYPE_STYLE = {
    "product_issue": "[blue]product_issue[/blue]",
    "feature_request": "[cyan]feature_request[/cyan]",
    "bug": "[magenta]bug[/magenta]",
    "invalid": "[dim]invalid[/dim]",
}


def _ticket_panel(idx: int, ticket: SupportTicket) -> Panel:
    content = (
        f"[bold]Company:[/bold] {ticket.company}\n"
        f"[bold]Subject:[/bold] {ticket.subject or '(none)'}\n"
        f"[bold]Issue:[/bold]   {ticket.issue[:300]}" + ("…" if len(ticket.issue) > 300 else "")
    )
    return Panel(content, title=f"[bold]Ticket #{idx + 1}[/bold]", border_style="blue")


def _result_panel(result: TriageResult) -> Panel:
    status_str = STATUS_STYLE.get(result.status.value, result.status.value)
    reqtype_str = REQTYPE_STYLE.get(result.request_type.value, result.request_type.value)
    content = (
        f"  {status_str}  │  {reqtype_str}  │  "
        f"[bold]Area:[/bold] {result.product_area}\n\n"
        f"[bold]Response:[/bold]\n{result.response}\n\n"
        f"[dim][bold]Justification:[/bold] {result.justification}[/dim]"
    )
    return Panel(content, title="[bold green]Agent Decision[/bold green]", border_style="green")


def display_summary_table(
    tickets: List[SupportTicket],
    results: List[TriageResult],
) -> None:
    """Print a condensed summary table after processing all tickets."""
    table = Table(
        title="Triage Summary",
        show_header=True,
        header_style="bold",
        expand=True,
    )
    table.add_column("#", width=4, style="dim")
    table.add_column("Company", width=12)
    table.add_column("Status", width=12)
    table.add_column("Request Type", width=17)
    table.add_column("Product Area", width=22)
    table.add_column("Issue (truncated)", min_width=20)

    for i, (ticket, result) in enumerate(zip(tickets, results)):
        status_text = Text(result.status.value)
        status_text.stylize("green" if result.status.value == "replied" else "red")
        table.add_row(
            str(i + 1),
            ticket.company,
            status_text,
            result.request_type.value,
            result.product_area[:22],
            ticket.issue[:60] + ("…" if len(ticket.issue) > 60 else ""),
        )

    console.print(table)

    # Stats
    total = len(results)
    replied = sum(1 for r in results if r.status.value == "replied")
    escalated = total - replied
    types = {}
    for r in results:
        types[r.request_type.value] = types.get(r.request_type.value, 0) + 1

    console.print(
        f"\n[bold]Total:[/bold] {total}  "
        f"[green]Replied: {replied}[/green]  "
        f"[red]Escalated: {escalated}[/red]  │  " + "  ".join(f"{k}: {v}" for k, v in types.items())
    )


# ─────────────────────────────────────────────────────────────────
# Main processing loop
# ─────────────────────────────────────────────────────────────────


def process_tickets(
    agent: TriageAgent,
    tickets: List[SupportTicket],
    verbose: bool = False,
    dry_run: bool = False,
) -> List[TriageResult]:
    """Process all tickets with a rich progress bar."""
    results: List[TriageResult] = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
        console=console,
        refresh_per_second=4,
    ) as progress:
        task = progress.add_task("Triaging tickets…", total=len(tickets))

        for i, ticket in enumerate(tickets):
            progress.update(
                task,
                description=f"Ticket {i+1}/{len(tickets)} "
                f"[{ticket.company}] {ticket.issue[:40]}…",
            )

            if verbose:
                console.print(_ticket_panel(i, ticket))

            start = time.time()
            result = agent.triage(ticket)
            elapsed = time.time() - start

            results.append(result)

            if verbose:
                console.print(_result_panel(result))
                console.print(f"[dim]  (processed in {elapsed:.2f}s)[/dim]\n")
            else:
                status_icon = (
                    "[green]✓[/green]" if result.status.value == "replied" else "[red]⚠[/red]"
                )
                console.print(
                    f"  {i+1:>3}. {status_icon} "
                    f"[dim]{result.request_type.value:16}[/dim] "
                    f"{result.product_area[:30]}",
                    highlight=False,
                )

            progress.advance(task)

            if dry_run:
                break  # only one ticket in dry-run mode

    return results


# ─────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Multi-Domain Support Triage Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=None,
        help="Path to input CSV (default: support_issues/support_issues.csv)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=OUTPUT_CSV,
        help="Path for output CSV",
    )
    parser.add_argument(
        "--sample",
        action="store_true",
        help="Run on sample_support_issues.csv",
    )
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Force re-scrape of the support corpus",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Process only the first ticket; don't write CSV",
    )
    parser.add_argument(
        "--ticket",
        type=int,
        default=None,
        help="Process only ticket N (0-indexed)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show full ticket/result panels",
    )
    args = parser.parse_args()

    # ── Banner ────────────────────────────────────────────────────
    console.print(Rule("[bold cyan]Support Triage Agent[/bold cyan]"))
    console.print("[dim]Multi-domain triage: HackerRank · Claude · Visa[/dim]\n")

    # ── Determine input file ──────────────────────────────────────
    if args.input:
        input_path = args.input
    elif args.sample:
        input_path = SAMPLE_CSV
    else:
        input_path = INPUT_CSV

    if not input_path.exists():
        console.print(
            f"[red]Error: input file not found: {input_path}[/red]\n"
            "Place support_issues.csv in the support_issues/ directory."
        )
        sys.exit(1)

    # ── Build / load corpus ───────────────────────────────────────
    console.print("[bold]Step 1/3: Support Corpus[/bold]")
    chunks = load_or_build_corpus(force_scrape=args.rebuild)
    console.print(
        f"  Corpus: {len(chunks):,} chunks across "
        f"{len(set(c.source for c in chunks))} knowledge bases\n"
    )

    # ── Build retriever index ─────────────────────────────────────
    console.print("[bold]Step 2/3: Building Retrieval Index[/bold]")
    t0 = time.time()
    retriever = HybridRetriever(chunks, RETRIEVER_CFG)
    console.print(f"  Index built in {time.time()-t0:.2f}s\n")

    # ── Load tickets ──────────────────────────────────────────────
    console.print(f"[bold]Step 3/3: Processing Tickets[/bold] ({input_path.name})")
    tickets = read_tickets(input_path)

    if args.ticket is not None:
        tickets = [tickets[args.ticket]]
        console.print(f"  Running on ticket #{args.ticket} only\n")
    else:
        console.print(f"  Loaded {len(tickets)} tickets\n")

    # ── Instantiate agent ─────────────────────────────────────────
    agent = TriageAgent(retriever)

    # ── Process ───────────────────────────────────────────────────
    results = process_tickets(
        agent,
        tickets,
        verbose=args.verbose,
        dry_run=args.dry_run,
    )

    # ── Summary ───────────────────────────────────────────────────
    console.print()
    display_summary_table(tickets, results)

    # ── Write output ──────────────────────────────────────────────
    if not args.dry_run:
        write_results(results, args.output)
    else:
        console.print("\n[yellow]Dry run — output CSV not written.[/yellow]")

    console.print(Rule("[bold cyan]Done[/bold cyan]"))


if __name__ == "__main__":
    main()
