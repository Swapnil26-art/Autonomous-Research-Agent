"""CLI interface for Autonomous Research Agent."""
import asyncio
import sys
from pathlib import Path
from typing import Optional
import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.markdown import Markdown
from rich.progress import Progress, SpinnerColumn, TextColumn
from loguru import logger

from src.agent import AutonomousResearchAgent, run_research
from src.models import SearchEngine, ExportFormat
from src.config import get_settings, reload_settings

app = typer.Typer(
    name="research-agent",
    help="Autonomous Research Agent - AI-powered research assistant",
    add_completion=False
)

console = Console()


def setup_logging(debug: bool = False):
    """Configure logging."""
    logger.remove()
    level = "DEBUG" if debug else "INFO"
    logger.add(
        sys.stderr,
        level=level,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
    )


@app.command()
def research(
    query: str = typer.Argument(..., help="Research query/topic"),
    engines: Optional[str] = typer.Option(None, "--engines", "-e", help="Comma-separated search engines (duckduckgo,google,bing,serper)"),
    max_results: int = typer.Option(10, "--max-results", "-n", help="Maximum results per engine"),
    no_auto: bool = typer.Option(False, "--no-auto", help="Disable automatic source selection"),
    export: Optional[str] = typer.Option(None, "--export", "-x", help="Export formats (markdown,pdf,json,html)"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output directory"),
    debug: bool = typer.Option(False, "--debug", help="Enable debug logging")
):
    """Perform autonomous research on a query."""
    setup_logging(debug)

    # Parse engines
    engine_list = None
    if engines:
        engine_list = [SearchEngine(e.strip().lower()) for e in engines.split(",")]

    # Parse export formats
    export_formats = None
    if export:
        export_formats = [ExportFormat(f.strip().lower()) for f in export.split(",")]

    # Override output dir if specified
    if output:
        settings = get_settings()
        settings.export.output_dir = output

    console.print(Panel.fit(f"[bold blue]Research Query:[/bold blue] {query}", border_style="blue"))

    async def run():
        agent = AutonomousResearchAgent()
        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
                transient=True
            ) as progress:
                task = progress.add_task("Researching...", total=None)
                session = await agent.research(
                    query=query,
                    engines=engine_list,
                    max_results=max_results,
                    auto_select_sources=not no_auto,
                    export_formats=export_formats
                )
                progress.update(task, description="Complete!")

            # Display summary
            summary = session.summary
            if summary:
                console.print("\n")
                console.print(Panel.fit(f"[bold green]Research Complete[/bold green] ({summary.processing_time:.2f}s)", border_style="green"))

                if summary.key_points:
                    console.print("\n[bold]Key Points:[/bold]")
                    for point in summary.key_points:
                        console.print(f"  • {point}")

                if summary.important_findings:
                    console.print("\n[bold]Important Findings:[/bold]")
                    for finding in summary.important_findings:
                        console.print(f"  • {finding}")

                if summary.actionable_insights:
                    console.print("\n[bold]Actionable Insights:[/bold]")
                    for insight in summary.actionable_insights:
                        console.print(f"  • {insight}")

                if session.exports:
                    console.print("\n[bold]Exports:[/bold]")
                    for exp in session.exports:
                        console.print(f"  📄 {exp}")

        finally:
            await agent.close()

    asyncio.run(run())


@app.command()
def quick(
    query: str = typer.Argument(..., help="Research query"),
    debug: bool = typer.Option(False, "--debug", help="Enable debug logging")
):
    """Quick research - just show summary."""
    setup_logging(debug)

    async def run():
        agent = AutonomousResearchAgent()
        try:
            with console.status("[bold blue]Researching..."):
                summary = await agent.quick_research(query)

            console.print(Panel.fit(f"[bold]Summary for:[/bold] {query}", border_style="blue"))

            if summary.key_points:
                console.print("\n[bold]Key Points:[/bold]")
                for point in summary.key_points:
                    console.print(f"  • {point}")

            if summary.important_findings:
                console.print("\n[bold]Important Findings:[/bold]")
                for finding in summary.important_findings:
                    console.print(f"  • {finding}")

            if summary.actionable_insights:
                console.print("\n[bold]Actionable Insights:[/bold]")
                for insight in summary.actionable_insights:
                    console.print(f"  • {insight}")

        finally:
            await agent.close()

    asyncio.run(run())


@app.command()
def history(
    limit: int = typer.Option(20, "--limit", "-l", help="Number of sessions to show"),
    search: Optional[str] = typer.Option(None, "--search", "-s", help="Search history by query"),
    debug: bool = typer.Option(False, "--debug", help="Enable debug logging")
):
    """Show research history."""
    setup_logging(debug)

    agent = AutonomousResearchAgent()

    if search:
        sessions = agent.search_history(search, limit)
        console.print(f"[bold]Search results for:[/bold] '{search}'")
    else:
        sessions = agent.get_history(limit)
        console.print("[bold]Recent Research Sessions:[/bold]")

    if not sessions:
        console.print("[yellow]No sessions found.[/yellow]")
        return

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("ID", style="dim", width=12)
    table.add_column("Query", min_width=30)
    table.add_column("Status", width=12)
    table.add_column("Date", width=20)

    for session in sessions:
        table.add_row(
            session.id[:8],
            session.query[:60] + ("..." if len(session.query) > 60 else ""),
            session.status,
            session.created_at.strftime("%Y-%m-%d %H:%M")
        )

    console.print(table)


@app.command()
def show(
    session_id: str = typer.Argument(..., help="Session ID to display"),
    debug: bool = typer.Option(False, "--debug", help="Enable debug logging")
):
    """Show details of a specific research session."""
    setup_logging(debug)

    agent = AutonomousResearchAgent()
    session = agent.load_session(session_id)

    if not session:
        console.print(f"[red]Session {session_id} not found.[/red]")
        return

    console.print(Panel.fit(f"[bold]Session:[/bold] {session.id}", border_style="blue"))
    console.print(f"[bold]Query:[/bold] {session.query.query}")
    console.print(f"[bold]Status:[/bold] {session.status}")
    console.print(f"[bold]Created:[/bold] {session.created_at}")
    console.print(f"[bold]Sources:[/bold] {len(session.search_results)} search results, {len([c for c in session.extracted_content if c.success])} extracted")

    if session.summary:
        summary = session.summary
        console.print(f"\n[bold]Summary ({summary.processing_time:.2f}s):[/bold]")

        if summary.key_points:
            console.print("\n[bold]Key Points:[/bold]")
            for point in summary.key_points:
                console.print(f"  • {point}")

        if summary.important_findings:
            console.print("\n[bold]Important Findings:[/bold]")
            for finding in summary.important_findings:
                console.print(f"  • {finding}")

        if summary.actionable_insights:
            console.print("\n[bold]Actionable Insights:[/bold]")
            for insight in summary.actionable_insights:
                console.print(f"  • {insight}")

        if summary.references:
            console.print(f"\n[bold]References ({len(summary.references)}):[/bold]")
            for i, ref in enumerate(summary.references[:10], 1):
                console.print(f"  {i}. {ref.title} - {ref.url}")

    if session.exports:
        console.print("\n[bold]Exports:[/bold]")
        for exp in session.exports:
            console.print(f"  📄 {exp}")


@app.command()
def export(
    session_id: str = typer.Argument(..., help="Session ID to export"),
    formats: str = typer.Option("markdown,pdf", "--formats", "-f", help="Comma-separated export formats"),
    debug: bool = typer.Option(False, "--debug", help="Enable debug logging")
):
    """Export a previous research session."""
    setup_logging(debug)

    format_list = [ExportFormat(f.strip().lower()) for f in formats.split(",")]

    agent = AutonomousResearchAgent()
    try:
        with console.status(f"[bold blue]Exporting to {formats}..."):
            results = agent.export_session(session_id, format_list)

        console.print("[green]Export complete:[/green]")
        for fmt, path in results.items():
            if path.startswith("Error"):
                console.print(f"  [red]{fmt.value}:[/red] {path}")
            else:
                console.print(f"  [green]{fmt.value}:[/green] {path}")
    except Exception as e:
        console.print(f"[red]Export failed:[/red] {e}")


@app.command()
def stats(debug: bool = typer.Option(False, "--debug", help="Enable debug logging")):
    """Show storage statistics."""
    setup_logging(debug)

    agent = AutonomousResearchAgent()
    stats = agent.get_stats()

    table = Table(title="Storage Statistics", show_header=True, header_style="bold magenta")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    for key, value in stats.items():
        table.add_row(key.replace("_", " ").title(), str(value))

    console.print(table)


@app.command()
def cleanup(
    days: int = typer.Option(90, "--days", "-d", help="Delete sessions older than N days"),
    debug: bool = typer.Option(False, "--debug", help="Enable debug logging")
):
    """Clean up old research sessions."""
    setup_logging(debug)

    agent = AutonomousResearchAgent()
    count = agent.memory.cleanup_old_sessions(days)
    console.print(f"[green]Cleaned up {count} sessions older than {days} days.[/green]")


@app.command()
def config(
    show: bool = typer.Option(False, "--show", help="Show current configuration"),
    debug: bool = typer.Option(False, "--debug", help="Enable debug logging")
):
    """Show or manage configuration."""
    setup_logging(debug)

    if show:
        settings = get_settings()
        console.print(Panel.fit("[bold]Current Configuration[/bold]", border_style="blue"))

        # Display key settings
        console.print(f"\n[bold]LLM:[/bold] {settings.llm.provider} / {settings.llm.model}")
        console.print(f"[bold]Search Engines:[/bold]")
        for name, config in settings.search.engines.items():
            enabled = config.get("enabled", False) if isinstance(config, dict) else config
            console.print(f"  • {name}: {'enabled' if enabled else 'disabled'}")

        console.print(f"[bold]Export Formats:[/bold] {', '.join(settings.export.formats)}")
        console.print(f"[bold]Output Directory:[/bold] {settings.export.output_dir}")
        console.print(f"[bold]Database:[/bold] {settings.memory.db_path}")


def main():
    """Entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()