"""Command-line interface for automatic-movie-downloader.

Commands
--------
resolve      Navigate a URL through a workflow and print the final URL.
validate-config  Validate a workflow config file without opening a browser.
debug        Like ``resolve`` but opens a visible (non-headless) browser window.
export-sample-config  Write a sample workflow config to stdout or a file.
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Optional

import typer
import yaml
from rich.console import Console
from rich.table import Table

from src.config import SAMPLE_CONFIG, ConfigError, load_config, validate_config
from src.engine import WorkflowResult, run_workflow

app = typer.Typer(
    name="amd",
    help="Headless browser automation for authorized redirect navigation.",
    add_completion=False,
)
console = Console()
err_console = Console(stderr=True)


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )


def _print_result(result: WorkflowResult, output_format: str) -> None:
    """Print *result* in the requested format.

    Args:
        result: The workflow result to display.
        output_format: ``"json"`` or ``"human"``.
    """
    if output_format == "json":
        data = {
            "workflow_name": result.workflow_name,
            "success": result.success,
            "final_url": result.final_url,
            "page_title": result.page_title,
            "redirect_chain": result.redirect_chain,
            "extracted": result.extracted,
            "elapsed_seconds": round(result.elapsed_seconds, 3),
            "error": result.error,
        }
        console.print_json(json.dumps(data))
    else:
        if not result.success:
            err_console.print(f"[bold red]✗ Workflow failed:[/] {result.error}")
            return

        console.print(f"\n[bold green]✓ Workflow completed:[/] {result.workflow_name}")
        console.print(f"  [bold]Final URL:[/]  {result.final_url}")
        console.print(f"  [bold]Page title:[/] {result.page_title}")
        console.print(f"  [bold]Elapsed:[/]    {result.elapsed_seconds:.1f}s")

        if result.redirect_chain:
            console.print("\n  [bold]Redirect chain:[/]")
            for i, url in enumerate(result.redirect_chain, 1):
                console.print(f"    {i}. {url}")

        if result.extracted:
            tbl = Table("Key", "Value", show_header=True, header_style="bold cyan")
            for k, v in result.extracted.items():
                tbl.add_row(str(k), str(v))
            console.print("\n  [bold]Extracted values:[/]")
            console.print(tbl)


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


@app.command()
def resolve(
    url: str = typer.Argument(..., help="Starting URL for the workflow."),
    config: Path = typer.Option(
        ..., "--config", "-c", help="Path to a YAML or JSON workflow config file."
    ),
    output_format: Optional[str] = typer.Option(
        None,
        "--format",
        "-f",
        help="Output format: 'json' or 'human'. Overrides config setting.",
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable debug logging."),
) -> None:
    """Navigate *URL* through the steps defined in *CONFIG* and print the final URL."""
    _setup_logging(verbose)
    try:
        cfg = load_config(config)
    except (ConfigError, FileNotFoundError) as exc:
        err_console.print(f"[red]Config error:[/] {exc}")
        raise typer.Exit(code=1) from exc

    # Allow CLI to override the output format
    if output_format:
        cfg.output_format = output_format  # type: ignore[assignment]

    # If a URL is supplied on the CLI, prepend an open_url step
    if url != cfg.start_url:
        cfg.start_url = url

    result = run_workflow(cfg)
    _print_result(result, cfg.output_format)

    if not result.success:
        raise typer.Exit(code=1)


@app.command(name="validate-config")
def validate_config_cmd(
    config: Path = typer.Argument(..., help="Path to the workflow config file."),
) -> None:
    """Validate a workflow config file without opening a browser."""
    errors = validate_config(config)
    if errors:
        for err in errors:
            err_console.print(f"[red]✗[/] {err}")
        raise typer.Exit(code=1)
    console.print(f"[green]✓[/] Config [bold]{config}[/] is valid.")


@app.command()
def debug(
    url: str = typer.Argument(..., help="Starting URL for the workflow."),
    config: Path = typer.Option(
        ..., "--config", "-c", help="Path to a YAML or JSON workflow config file."
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable debug logging."),
) -> None:
    """Run a workflow with a *visible* (non-headless) browser window for debugging."""
    _setup_logging(verbose)
    try:
        cfg = load_config(config)
    except (ConfigError, FileNotFoundError) as exc:
        err_console.print(f"[red]Config error:[/] {exc}")
        raise typer.Exit(code=1) from exc

    cfg.headless = False
    if url != cfg.start_url:
        cfg.start_url = url

    result = run_workflow(cfg)
    _print_result(result, cfg.output_format)

    if not result.success:
        raise typer.Exit(code=1)


@app.command(name="export-sample-config")
def export_sample_config(
    output: Optional[Path] = typer.Option(
        None, "--output", "-o", help="Write to this file instead of stdout."
    ),
    fmt: str = typer.Option("yaml", "--format", "-f", help="Output format: 'yaml' or 'json'."),
) -> None:
    """Write a sample workflow config to stdout (or *OUTPUT*)."""
    if fmt == "json":
        text = json.dumps(SAMPLE_CONFIG, indent=2)
    else:
        text = yaml.dump(SAMPLE_CONFIG, sort_keys=False, allow_unicode=True)

    if output:
        output.write_text(text, encoding="utf-8")
        console.print(f"[green]✓[/] Sample config written to [bold]{output}[/]")
    else:
        sys.stdout.write(text)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Entry point used by the ``amd`` console script."""
    app()


if __name__ == "__main__":
    main()
