"""Command-line interface commands."""

from pathlib import Path
import sys

import click
from loguru import logger

from ..core.processor import BibTeXProcessor


@click.group()
@click.option("--logfile", type=click.Path(), help="Log file path")
@click.option(
    "--loglevel",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"], case_sensitive=False),
    default="INFO",
    help="Log level",
)
@click.pass_context
def cli(ctx: click.Context, logfile: str | None, loglevel: str) -> None:
    """ReflInt: Comprehensive BibTeX Reference Checker and Fixer."""
    # Configure logging
    logger.remove()  # Remove default handler

    # Add console handler
    logger.add(
        sys.stderr, level=loglevel.upper(), format="{time} | {level} | {message}"
    )

    # Add file handler if specified
    if logfile:
        logger.add(
            logfile,
            level=loglevel.upper(),
            format="{time} | {level} | {name} | {message}",
        )

    # Store context for subcommands
    ctx.ensure_object(dict)
    ctx.obj["loglevel"] = loglevel


@cli.command()
@click.argument("input_file", type=click.Path(exists=True), required=False)
@click.option("--output", "-o", type=click.Path(), help="Output file path")
@click.option("--stdin", is_flag=True, help="Read from stdin instead of file")
@click.pass_context
def validate(
    ctx: click.Context, input_file: str | None, output: str | None, stdin: bool
) -> None:
    """Validate BibTeX entries and optionally fix issues."""

    if stdin and input_file:
        click.echo("Error: Cannot specify both input file and --stdin", err=True)
        sys.exit(1)

    if not stdin and not input_file:
        click.echo("Error: Must specify either input file or --stdin", err=True)
        sys.exit(1)

    processor = BibTeXProcessor()

    try:
        # Load entries
        if stdin:
            processor.load_from_stdin()
        else:
            assert (
                input_file is not None
            )  # This should never be None due to our checks above
            processor.load_from_file(Path(input_file))

        logger.info(f"Loaded {processor.get_entry_count()} entries")

        # For now, just output the loaded entries
        if output:
            processor.save_to_file(Path(output))
            click.echo(f"Output written to {output}")
        else:
            processor.save_to_stdout()

    except Exception as e:
        logger.error(f"Processing failed: {e}")
        sys.exit(1)


@cli.command()
def info() -> None:
    """Show information about ReflInt."""
    click.echo("ReflInt: Comprehensive BibTeX Reference Checker and Fixer")
    click.echo("Phase 1 - Foundation and Basic Validation")
    click.echo("Currently supports basic BibTeX file loading and saving.")


if __name__ == "__main__":
    cli()
