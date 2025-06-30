"""Command-line interface commands."""

from pathlib import Path
import sys

import click
from loguru import logger

from ..core.processor import BibTeXProcessor
from ..core.validation import ValidationResult
from ..rules import get_registry


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
@click.option("--rules", help="Comma-separated list of rule IDs to run")
@click.option("--summary-only", is_flag=True, help="Show only validation summary")
@click.option("--show-info", is_flag=True, help="Show info-level violations")
@click.pass_context
def validate(
    ctx: click.Context,
    input_file: str | None,
    output: str | None,
    stdin: bool,
    rules: str | None,
    summary_only: bool,
    show_info: bool,
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

        # Parse rule filter
        rule_filter = None
        if rules:
            rule_filter = [r.strip() for r in rules.split(",")]

        # Run validation
        results = processor.validate_entries(rule_filter)

        # Display results
        _display_validation_results(results, summary_only, show_info)

        # Calculate exit code based on validation results
        has_errors = any(r.has_errors for r in results)

        # Output processed file if requested
        if output:
            processor.save_to_file(Path(output))
            click.echo(f"Output written to {output}")
        elif not summary_only and not has_errors:
            # Only output if not summary-only and no errors
            processor.save_to_stdout()

        # Exit with error code if validation failed
        if has_errors:
            sys.exit(1)

    except Exception as e:
        logger.error(f"Processing failed: {e}")
        sys.exit(1)


def _display_validation_results(
    results: list[ValidationResult], summary_only: bool, show_info: bool
) -> None:
    """Display validation results to the user."""
    # Calculate summary statistics
    total_entries = len(results)
    entries_with_errors = sum(1 for r in results if r.has_errors)
    entries_with_warnings = sum(1 for r in results if r.has_warnings)
    total_errors = sum(r.error_count for r in results)
    total_warnings = sum(r.warning_count for r in results)
    total_info = sum(r.info_count for r in results)

    # Display summary
    click.echo("\n" + "=" * 60)
    click.echo("VALIDATION SUMMARY")
    click.echo("=" * 60)
    click.echo(f"Total entries: {total_entries}")
    click.echo(f"Entries with errors: {entries_with_errors}")
    click.echo(f"Entries with warnings: {entries_with_warnings}")
    click.echo(
        f"Total violations: {total_errors} errors, {total_warnings} warnings, {total_info} info"
    )

    if summary_only:
        return

    # Display detailed results
    if total_errors > 0 or total_warnings > 0 or (show_info and total_info > 0):
        click.echo("\n" + "=" * 60)
        click.echo("DETAILED RESULTS")
        click.echo("=" * 60)

        for result in results:
            if not result.violations:
                continue

            # Filter violations based on show_info flag
            violations_to_show = [
                v
                for v in result.violations
                if v.severity in ["error", "warning"]
                or (show_info and v.severity == "info")
            ]

            if not violations_to_show:
                continue

            click.echo(f"\nEntry: {result.entry_key}")
            click.echo("-" * (len(result.entry_key) + 7))

            for violation in violations_to_show:
                severity_color = {
                    "error": "red",
                    "warning": "yellow",
                    "info": "blue",
                }.get(violation.severity, "white")

                click.echo(
                    f"  {click.style(violation.severity.upper(), fg=severity_color, bold=True)}: "
                    f"{violation.rule_id} - {violation.message}"
                )

                if violation.field:
                    click.echo(f"    Field: {violation.field}")

                if violation.suggested_fix:
                    click.echo(f"    Suggestion: {violation.suggested_fix}")

    # Final status
    click.echo("\n" + "=" * 60)
    if total_errors > 0:
        click.echo(click.style("VALIDATION FAILED", fg="red", bold=True))
    elif total_warnings > 0:
        click.echo(
            click.style("VALIDATION PASSED WITH WARNINGS", fg="yellow", bold=True)
        )
    else:
        click.echo(click.style("VALIDATION PASSED", fg="green", bold=True))
    click.echo("=" * 60)


@cli.command()
def info() -> None:
    """Show information about ReflInt."""
    click.echo("ReflInt: Comprehensive BibTeX Reference Checker and Fixer")
    click.echo("Phase 2 - Rule-Based Validation System")
    click.echo("Supports BibTeX validation with multiple rule types.")


@cli.command()
def rules() -> None:
    """List available validation rules."""
    registry = get_registry()
    stats = registry.get_statistics()

    click.echo("Available Validation Rules")
    click.echo("=" * 25)
    click.echo(f"Total rules: {stats['total_rules']}")
    click.echo(f"Fixable rules: {stats['fixable_rules']}")
    click.echo()

    # Group rules by category
    for category in stats["categories"]:
        rules_in_category = registry.get_rules_by_category(category)
        click.echo(f"{category.upper()} ({len(rules_in_category)} rules)")
        click.echo("-" * (len(category) + 10))

        for rule in rules_in_category:
            fixable = " [FIXABLE]" if rule.can_fix() else ""
            severity_color = {"error": "red", "warning": "yellow", "info": "blue"}.get(
                rule.severity, "white"
            )

            click.echo(
                f"  {rule.rule_id}: {rule.description}"
                f" ({click.style(rule.severity, fg=severity_color)}){fixable}"
            )
        click.echo()


if __name__ == "__main__":
    cli()
