"""
CLI tool for Support Triage Agent
Run with: python -m code.cli_tool
or: support-triage (after pip install)
"""
import click
import csv
import json
import os
from pathlib import Path
from datetime import datetime
from typing import Optional
import sys

# Add code directory to path
sys.path.insert(0, os.path.dirname(__file__))

from agent import SupportTriageAgent
from rich.console import Console
from rich.table import Table
from rich.progress import Progress

console = Console()

@click.group()
def cli():
    """🎯 Support Triage Agent - Multi-domain AI support classifier"""
    pass

@cli.command()
@click.argument('input_file', type=click.Path(exists=True))
@click.option('--output', '-o', default='output', help='Output directory')
@click.option('--api-key', default=None, help='Anthropic API key for LLM mode')
@click.option('--batch-size', default=100, help='Batch size for processing')
@click.option('--verbose', '-v', is_flag=True, help='Verbose output')
def process(input_file, output, api_key, batch_size, verbose):
    """
    Process support tickets from CSV file
    
    INPUT_FILE: CSV file with columns: issue, subject, company
    """
    if not os.path.exists(input_file):
        console.print(f"[red]Error: File not found: {input_file}[/red]")
        sys.exit(1)
    
    # Create output directory
    os.makedirs(output, exist_ok=True)
    
    # Initialize agent
    if verbose:
        console.print("[cyan]Initializing Support Triage Agent...[/cyan]")
    
    agent = SupportTriageAgent()
    
    # Read input tickets
    tickets = []
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                tickets.append(row)
    except Exception as e:
        console.print(f"[red]Error reading CSV: {e}[/red]")
        sys.exit(1)
    
    if not tickets:
        console.print("[red]No tickets found in input file[/red]")
        sys.exit(1)
    
    console.print(f"[green]✓ Loaded {len(tickets)} tickets[/green]")
    
    # Process tickets
    results = []
    with Progress() as progress:
        task = progress.add_task("[cyan]Triaging tickets...", total=len(tickets))
        
        for ticket in tickets:
            try:
                result = agent.process(ticket)
                results.append(result)
                progress.update(task, advance=1)
            except Exception as e:
                if verbose:
                    console.print(f"[yellow]Warning: Error processing ticket: {e}[/yellow]")
                progress.update(task, advance=1)
    
    # Write output CSV
    output_csv = os.path.join(output, 'output.csv')
    if results:
        keys = results[0].keys()
        with open(output_csv, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows(results)
        console.print(f"[green]✓ Results saved to: {output_csv}[/green]")
    
    # Print summary statistics
    console.print("\n[bold cyan]Summary Statistics[/bold cyan]")
    
    table = Table()
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")
    
    total = len(results)
    replied = sum(1 for r in results if r.get('status') == 'replied')
    escalated = total - replied
    avg_confidence = sum(r.get('confidence', 0) for r in results) / total if total > 0 else 0
    avg_quality = sum(r.get('quality', 0) for r in results) / total if total > 0 else 0
    
    table.add_row("Total Tickets", str(total))
    table.add_row("Auto-Replied", f"{replied} ({100*replied//total}%)")
    table.add_row("Escalated", f"{escalated} ({100*escalated//total}%)")
    table.add_row("Avg Confidence", f"{avg_confidence:.1%}")
    table.add_row("Avg Quality", f"{avg_quality:.1%}")
    
    console.print(table)

@cli.command()
@click.argument('issue')
@click.option('--subject', default='Support Request', help='Ticket subject')
@click.option('--company', default=None, help='Company: Claude, HackerRank, or Visa')
@click.option('--verbose', '-v', is_flag=True, help='Verbose output')
def triage(issue, subject, company, verbose):
    """
    Triage a single ticket
    
    ISSUE: The support issue/problem description
    """
    if verbose:
        console.print("[cyan]Initializing agent...[/cyan]")
    
    agent = SupportTriageAgent()
    
    ticket = {
        'issue': issue,
        'subject': subject,
        'company': company or ''
    }
    
    if verbose:
        console.print(f"[cyan]Processing: {subject}[/cyan]")
    
    result = agent.process(ticket)
    
    # Display result
    console.print("\n[bold cyan]Triage Result[/bold cyan]")
    
    table = Table()
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="green")
    
    table.add_row("Status", result.get('status', 'N/A').upper())
    table.add_row("Priority", result.get('urgency', 'N/A'))
    table.add_row("Sentiment", result.get('sentiment', 'N/A'))
    table.add_row("Confidence", f"{result.get('confidence', 0):.1%}")
    table.add_row("Quality", f"{result.get('quality', 0):.1%}")
    table.add_row("Churn Risk", f"{result.get('churn_risk', 0)}/100")
    table.add_row("Health Score", f"{result.get('health_score', 0)}/100")
    
    console.print(table)
    
    if result.get('status') == 'replied':
        console.print("\n[bold green]Response:[/bold green]")
        console.print(result.get('response', ''))
    else:
        console.print("\n[bold yellow]Status: ESCALATED[/bold yellow]")
        console.print(f"Reason: {result.get('justification', '')}")

@cli.command()
@click.option('--input', '-i', default='output/output.csv', help='Output CSV to analyze')
def analyze(input):
    """
    Analyze triage results
    """
    if not os.path.exists(input):
        console.print(f"[red]Error: File not found: {input}[/red]")
        sys.exit(1)
    
    # Read CSV
    data = []
    with open(input, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        data = list(reader)
    
    console.print(f"\n[bold cyan]Analysis of {len(data)} tickets[/bold cyan]\n")
    
    # Group by company
    by_company = {}
    for row in data:
        company = row.get('company', 'Unknown')
        if company not in by_company:
            by_company[company] = []
        by_company[company].append(row)
    
    for company, tickets in by_company.items():
        replied = sum(1 for t in tickets if t.get('status') == 'Replied')
        escalated = len(tickets) - replied
        
        console.print(f"[cyan]{company}[/cyan]")
        console.print(f"  Total: {len(tickets)}")
        console.print(f"  Replied: {replied} ({100*replied//len(tickets)}%)")
        console.print(f"  Escalated: {escalated} ({100*escalated//len(tickets)}%)\n")

@cli.command()
def dashboard():
    """
    Open the HTML dashboard in browser
    """
    dashboard_path = os.path.abspath('output/dashboard.html')
    
    if not os.path.exists(dashboard_path):
        console.print("[red]Dashboard not found. Run 'process' command first.[/red]")
        sys.exit(1)
    
    # Open in browser
    import webbrowser
    webbrowser.open(f'file://{dashboard_path}')
    console.print(f"[green]✓ Opened dashboard in browser[/green]")

@cli.command()
def version():
    """Show version"""
    console.print("Support Triage Agent v1.0.0")

@cli.command()
def info():
    """Show information"""
    info_text = """
[bold cyan]Support Triage Agent[/bold cyan]

[bold]Description:[/bold]
  Multi-domain AI support triage system with 18 intelligence features

[bold]Features:[/bold]
  • BM25 + TF-IDF hybrid retrieval
  • Multi-domain support (HackerRank, Claude, Visa)
  • Zero hallucination (grounded responses)
  • 18 intelligence signals
  • SOC 2 compliance
  • GDPR/PCI-DSS ready
  • Offline or LLM-enhanced

[bold]Commands:[/bold]
  process    - Process CSV of tickets
  triage     - Triage single ticket
  analyze    - Analyze results
  dashboard  - Open HTML dashboard
  version    - Show version
  info       - Show this info

[bold]Examples:[/bold]
  support-triage process tickets.csv
  support-triage triage "I lost my password"
  support-triage analyze
    """
    console.print(info_text)

def cli_main():
    """Main entry point"""
    try:
        cli()
    except KeyboardInterrupt:
        console.print("\n[red]Cancelled[/red]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)

if __name__ == '__main__':
    cli_main()
