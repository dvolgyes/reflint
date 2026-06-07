"""Command-line interface commands."""

import asyncio
from pathlib import Path
import sys
from typing import TYPE_CHECKING

import click
from loguru import logger

if TYPE_CHECKING:
    from ..sources.registry import DataSourceRegistry
    from ..core.entry import BibTeXEntry

from ..core.processor import BibTeXProcessor
from ..core.validation import ValidationResult
from ..rules import get_registry
from ..sources.registry import get_registry as get_source_registry
from ..sources.crossref import CrossRefSource
from ..sources.semantic_scholar import SemanticScholarSource
from ..sources.arxiv import ArxivSource
from ..sources.pubmed import PubMedSource
from ..sources.openalex import OpenAlexSource
from ..sources.reconciliation import DataReconciler
from ..utils.enhanced_lookup import EnhancedLookupStrategy
from ..utils.cache import cleanup_cache, clear_cache, get_cache_statistics
from ..utils.network import LinkChecker


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
@click.argument("input_file", type=click.Path(exists=True), required=False)
@click.option("--output", "-o", type=click.Path(), help="Output file path")
@click.option("--stdin", is_flag=True, help="Read from stdin instead of file")
@click.option("--sources", help="Comma-separated list of data sources to use")
@click.option("--cache-ttl", type=int, default=86400, help="Cache TTL in seconds")
@click.option("--email", help="Email for API requests (recommended)")
@click.option("--api-key", help="API key for enhanced access")
@click.option(
    "--dry-run", is_flag=True, help="Show what would be enhanced without making changes"
)
@click.option(
    "--add-abstract", is_flag=True, help="Include abstracts when enhancing entries"
)
@click.option("--add-note", is_flag=True, help="Include notes when enhancing entries")
@click.option(
    "--add-eprint", is_flag=True, help="Include eprint/arXiv IDs when enhancing entries"
)
@click.option(
    "--add-pmid", is_flag=True, help="Include PubMed IDs when enhancing entries"
)
@click.option(
    "--add-keywords", is_flag=True, help="Include keywords when enhancing entries"
)
@click.pass_context
def enhance(
    ctx: click.Context,
    input_file: str | None,
    output: str | None,
    stdin: bool,
    sources: str | None,
    cache_ttl: int,
    email: str | None,
    api_key: str | None,
    dry_run: bool,
    add_abstract: bool,
    add_note: bool,
    add_eprint: bool,
    add_pmid: bool,
    add_keywords: bool,
) -> None:
    """Enhance BibTeX entries with external data sources."""

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
            assert input_file is not None
            processor.load_from_file(Path(input_file))

        logger.info(f"Loaded {processor.get_entry_count()} entries")

        # Initialize data sources
        source_registry = get_source_registry()

        # Register CrossRef
        crossref = CrossRefSource(email=email)
        source_registry.register_source(crossref)

        # Register Semantic Scholar
        s2 = SemanticScholarSource(api_key=api_key)
        source_registry.register_source(s2)

        # Register arXiv
        arxiv = ArxivSource(email=email)
        source_registry.register_source(arxiv)

        # Register PubMed
        pubmed = PubMedSource(email=email, api_key=api_key)
        source_registry.register_source(pubmed)

        # Register OpenAlex
        openalex = OpenAlexSource(email=email)
        source_registry.register_source(openalex)

        # Parse source filter
        source_filter = None
        if sources:
            source_filter = [s.strip() for s in sources.split(",")]

        # Run enhancement
        asyncio.run(
            _enhance_entries_async(
                processor,
                source_registry,
                source_filter,
                dry_run,
                add_abstract,
                add_note,
                add_eprint,
                add_pmid,
                add_keywords,
                email,
            )
        )

        # Output processed file if requested and not dry run
        if output and not dry_run:
            processor.save_to_file(Path(output))
            click.echo(f"Enhanced entries written to {output}")
        elif not dry_run:
            processor.save_to_stdout()

    except Exception as e:
        logger.error(f"Enhancement failed: {e}")
        sys.exit(1)


async def _enhance_entries_async(
    processor: BibTeXProcessor,
    source_registry: "DataSourceRegistry",
    source_filter: list[str] | None,
    dry_run: bool,
    add_abstract: bool,
    add_note: bool,
    add_eprint: bool,
    add_pmid: bool,
    add_keywords: bool,
    email: str | None = None,
) -> None:
    """Enhance entries asynchronously using enhanced lookup strategy."""
    enhanced_lookup = EnhancedLookupStrategy(source_registry)
    reconciler = DataReconciler(email=email)

    enhanced_count = 0
    total_entries = processor.get_entry_count()

    try:
        for entry in processor.entries:
            click.echo(f"Processing entry: {entry.key}")

            # Step 1: Resolve and prioritize identifiers
            resolved = enhanced_lookup.resolve_identifiers(entry)

            if resolved.is_web_only:
                click.echo("  Web/online-only entry, minimal enhancement")
                continue

            if not any(
                [
                    resolved.primary_doi,
                    resolved.primary_isbn,
                    resolved.arxiv_id,
                    resolved.pmid,
                ]
            ):
                click.echo("  No usable identifiers found, skipping")
                continue

            # Step 2: Try to resolve additional identifiers via Semantic Scholar
            if not resolved.skip_semantic_scholar:
                click.echo("  Resolving identifiers via Semantic Scholar...")
                try:
                    resolved = await enhanced_lookup.resolve_via_semantic_scholar(
                        resolved
                    )
                except Exception as e:
                    logger.warning(
                        f"Failed to resolve identifiers via Semantic Scholar: {e}"
                    )

            # Step 3: Determine optimal source strategy
            enhancement_sources = enhanced_lookup.get_enhancement_sources(resolved)
            if source_filter:
                # Filter to user-specified sources
                enhancement_sources = [
                    s for s in enhancement_sources if s in source_filter
                ]

            if not enhancement_sources:
                click.echo("  No suitable sources for enhancement")
                continue

            click.echo(f"  Using sources: {', '.join(enhancement_sources)}")

            # Display resolved identifiers
            id_info = []
            if resolved.primary_doi:
                id_info.append(f"DOI: {resolved.primary_doi}")
            if resolved.primary_isbn:
                id_info.append(f"ISBN: {resolved.primary_isbn}")
            if resolved.arxiv_id:
                id_info.append(f"arXiv: {resolved.arxiv_id}")
            if resolved.pmid:
                id_info.append(f"PMID: {resolved.pmid}")

            if id_info:
                click.echo(f"  Identifiers: {', '.join(id_info)}")

            # Step 4: Look up data from external sources using prioritized strategy
            all_results = await enhanced_lookup.get_lookup_results(
                resolved, enhancement_sources
            )

            if not all_results:
                click.echo("  No external data found")
                continue

            # Step 5: Reconcile data with ISSN lookup
            reconciled = await reconciler.reconcile_with_issn_lookup(
                all_results,
                entry,
                add_abstract,
                add_note,
                add_eprint,
                add_pmid,
                add_keywords,
            )

            click.echo(f"  Found data from {len(reconciled.sources_used)} sources")
            click.echo(f"  Confidence: {reconciled.confidence_score:.2f}")
            click.echo(f"  Completeness: {reconciled.completeness_score:.2f}")

            if reconciled.conflicts:
                click.echo(f"  Conflicts resolved: {len(reconciled.conflicts)}")

            # Step 6: Update identifiers in the enhanced entry
            enhanced_entry = reconciled.entry

            # Record additional identifiers found via Semantic Scholar
            if resolved.s2_doi and not enhanced_entry.has_field("doi"):
                enhanced_entry.set_field("doi", resolved.s2_doi)
            if resolved.s2_pmid and not enhanced_entry.has_field("pmid"):
                enhanced_entry.set_field("pmid", resolved.s2_pmid)
            if resolved.s2_isbn and not enhanced_entry.has_field("isbn"):
                enhanced_entry.set_field("isbn", resolved.s2_isbn)

            if dry_run:
                click.echo("  [DRY RUN] Would update entry")
            else:
                # Update the entry
                processor.entries[processor.entries.index(entry)] = enhanced_entry
                enhanced_count += 1

    finally:
        # Close sources
        for source in source_registry.get_all_sources():
            if hasattr(source, "close"):
                await source.close()

        # Close reconciler (ISSN lookup service)
        await reconciler.close()

    if not dry_run:
        click.echo(
            f"\nEnhancement complete: {enhanced_count}/{total_entries} entries updated"
        )
    else:
        click.echo(
            f"\nDry run complete: would update {enhanced_count}/{total_entries} entries"
        )


@cli.command()
@click.argument("input_file", type=click.Path(exists=True), required=False)
@click.option("--stdin", is_flag=True, help="Read from stdin instead of file")
@click.option(
    "--max-concurrent", type=int, default=10, help="Maximum concurrent requests"
)
@click.pass_context
def check_links(
    ctx: click.Context,
    input_file: str | None,
    stdin: bool,
    max_concurrent: int,
) -> None:
    """Check URL accessibility in BibTeX entries."""

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
            assert input_file is not None
            processor.load_from_file(Path(input_file))

        logger.info(f"Loaded {processor.get_entry_count()} entries")

        # Run link checking
        asyncio.run(_check_links_async(processor.entries, max_concurrent))

    except Exception as e:
        logger.error(f"Link checking failed: {e}")
        sys.exit(1)


async def _check_links_async(entries: list["BibTeXEntry"], max_concurrent: int) -> None:
    """Check links asynchronously."""
    link_checker = LinkChecker()

    try:
        report = await link_checker.get_broken_links_report(entries)

        click.echo("\n" + "=" * 60)
        click.echo("LINK CHECK REPORT")
        click.echo("=" * 60)
        click.echo(f"Total URLs checked: {report['total_urls_checked']}")
        click.echo(f"Broken links found: {report['broken_links_count']}")

        if report["broken_links"]:
            click.echo("\nBROKEN LINKS:")
            click.echo("-" * 15)

            for broken in report["broken_links"]:
                click.echo(f"Entry: {broken['entry_key']}")
                click.echo(f"  URL: {broken['url']}")
                click.echo(f"  Status: {click.style(broken['status'], fg='red')}")
                if broken["error"]:
                    click.echo(f"  Error: {broken['error']}")
                click.echo()

        # Summary
        if report["broken_links_count"] == 0:
            click.echo(click.style("All links are accessible!", fg="green", bold=True))
        else:
            click.echo(
                click.style(
                    f"{report['broken_links_count']} broken links found",
                    fg="red",
                    bold=True,
                )
            )

    finally:
        await link_checker.close()


@cli.group()
def cache() -> None:
    """Manage API response cache."""
    pass


@cache.command()
def stats() -> None:
    """Show cache statistics."""
    stats = get_cache_statistics()

    click.echo("Cache Statistics")
    click.echo("=" * 16)
    click.echo(f"Total entries: {stats['total_entries']}")
    click.echo(f"Total size: {stats['total_size_bytes']:,} bytes")
    click.echo(f"Average size: {stats.get('average_size_bytes', 0):.1f} bytes")
    click.echo(f"Expired entries: {stats['expired_entries']}")

    if stats["by_source"]:
        click.echo("\nBy Source:")
        click.echo("-" * 10)
        for source_stats in stats["by_source"]:
            click.echo(
                f"  {source_stats['source']}: {source_stats['count']} entries ({source_stats['total_size']:,} bytes)"
            )


@cache.command()
@click.option("--source", help="Clear cache for specific source only")
@click.confirmation_option(prompt="Are you sure you want to clear the cache?")
def clear(source: str | None) -> None:
    """Clear API response cache."""
    cleared = clear_cache(source)
    if source:
        click.echo(f"Cleared {cleared} cache entries for source: {source}")
    else:
        click.echo(f"Cleared {cleared} cache entries")


@cache.command()
def cleanup() -> None:
    """Remove expired cache entries."""
    cleaned = cleanup_cache()
    click.echo(f"Cleaned up {cleaned} expired cache entries")


@cli.command()
def info() -> None:
    """Show information about ReflInt."""
    click.echo("ReflInt: Comprehensive BibTeX Reference Checker and Fixer")
    click.echo("Phase 3 - External Data Integration")
    click.echo(
        "Supports BibTeX validation with multiple rule types and external data enhancement."
    )


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
