# reflint

<p>
  <a href="https://github.com/dvolgyes/reflint/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/dvolgyes/reflint/actions/workflows/ci.yml/badge.svg" /></a>
  <a href="https://coveralls.io/github/dvolgyes/reflint?branch=master"><img alt="Coverage Status" src="https://coveralls.io/repos/github/dvolgyes/reflint/badge.svg?branch=master" /></a>
  <a href="https://gitlab.com/dvolgyes/reflint/-/pipelines"><img alt="GitLab pipeline" src="https://gitlab.com/dvolgyes/reflint/badges/master/pipeline.svg" /></a>
  <a href="https://gitlab.com/dvolgyes/reflint/-/commits/master"><img alt="GitLab coverage" src="https://gitlab.com/dvolgyes/reflint/badges/master/coverage.svg" /></a>
  &nbsp;&nbsp;&nbsp;&nbsp;
  <a href="https://pypi.org/project/reflint/"><img alt="Version: 0.1.0" src="https://img.shields.io/badge/version-0.1.0-orange.svg" /></a>
  <a href="https://pypi.org/project/reflint/"><img alt="Status: Alpha" src="https://img.shields.io/badge/status-alpha-yellow.svg" /></a>
  &nbsp;&nbsp;&nbsp;&nbsp;
  <a href="https://www.python.org/"><img alt="Python: >=3.12" src="https://img.shields.io/badge/python-%3E=3.12-blue.svg" /></a>
</p>

`reflint` is a BibTeX reference checker and fixer focused on three jobs:

1. validate entries against a rule registry
1. enrich entries from external bibliographic sources
1. check links and manage the API response cache

The codebase is organized around a small core processor, a rule system, and a set of lookup sources for DOI, arXiv, PubMed, CrossRef, OpenAlex, and Semantic Scholar.

## Features

- BibTeX parsing and rewriting
- Rule-based validation with categorized rule groups
- Optional auto-fix support where rules expose fixes
- External data enhancement with source selection and dry-run mode
- URL accessibility checking
- Response caching with stats, cleanup, and selective clearing
- Identifier utilities for DOI, PMID, arXiv ID, ISSN, and ISBN handling

## Installation

This project uses `uv`.

Run the CLI without installing it into your environment:

```bash
uvx reflint --help
```

## Usage

The CLI exposes one group with these commands:

- `validate`
- `enhance`
- `check-links`
- `cache stats`
- `cache clear`
- `cache cleanup`
- `rules`
- `info`

The top-level options are:

- `--logfile PATH`
- `--loglevel DEBUG|INFO|WARNING|ERROR`

Example validation run:

```bash
uvx reflint validate references.bib
```

Read from standard input and write to a file:

```bash
cat references.bib | uvx reflint validate --stdin --output fixed.bib
```

Enhance entries with selected sources:

```bash
uvx reflint enhance references.bib --sources crossref,openalex --output enhanced.bib
```

Check links:

```bash
uvx reflint check-links references.bib
```

Inspect cache usage:

```bash
uvx reflint cache stats
```

List validation rules:

```bash
uvx reflint rules
```

## Project layout

- `src/reflint/core` contains BibTeX loading, entry handling, and validation results
- `src/reflint/rules` contains the validation rule registry and rule implementations
- `src/reflint/sources` contains external lookup providers and reconciliation logic
- `src/reflint/utils` contains identifier parsing, cache helpers, network helpers, and lookup utilities
- `src/reflint/cli` contains the Click command-line interface

## Testing

The repository includes unit tests for core logic, rules, sources, and utilities, plus a small set of manual network tests under `tests/manual`.

Run the test suite with:

```bash
uv run pytest -n 8 --cov
```

## Notes

- The CLI writes user-facing status and errors through `loguru`; BibTeX content is written to standard output or a file.
- Some source lookups are network-backed and may require API keys or email addresses depending on the provider.
