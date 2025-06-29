"""Main entry point for reflint."""


def main() -> None:
    """Main entry point."""
    from .cli.commands import cli

    cli()


if __name__ == "__main__":
    main()
