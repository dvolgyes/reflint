#!/usr/bin/env python3
"""
Simple test utility for DOI to title lookup.
Tests the ability to look up article metadata based on DOI.
"""

import asyncio
import sys
from reflint.sources.crossref import CrossRefSource
from reflint.sources.semantic_scholar import SemanticScholarSource
from reflint.sources.openalex import OpenAlexSource


async def lookup_doi(doi: str):
    """Look up a DOI across multiple sources and display results."""
    print(f"🔍 Looking up DOI: {doi}")
    print("=" * 50)

    sources = [
        ("CrossRef", CrossRefSource()),
        ("Semantic Scholar", SemanticScholarSource()),
        ("OpenAlex", OpenAlexSource()),
    ]

    results = {}

    try:
        for source_name, source in sources:
            try:
                print(f"\n📚 Checking {source_name}...")
                result = await source.lookup_by_doi(doi)

                if result.entry:
                    title = result.entry.get_field("title")
                    author = result.entry.get_field("author")
                    journal = result.entry.get_field("journal")
                    year = result.entry.get_field("year")

                    results[source_name] = {
                        "title": title,
                        "author": author,
                        "journal": journal,
                        "year": year,
                    }

                    print(f"  ✅ Found: {title}")
                    print(
                        f"     Authors: {author[:80]}..."
                        if len(author) > 80
                        else f"     Authors: {author}"
                    )
                    print(f"     Journal: {journal}")
                    print(f"     Year: {year}")
                else:
                    print("  ❌ Not found")
                    if result.metadata.error:
                        print(f"     Error: {result.metadata.error}")

            except Exception as e:
                print(f"  ⚠️  Error: {e}")

    finally:
        # Close all sources
        for _, source in sources:
            if hasattr(source, "close"):
                await source.close()

    # Summary
    print("\n" + "=" * 50)
    print("📊 SUMMARY")
    print("=" * 50)

    if results:
        # Check consistency across sources
        titles = {r["title"] for r in results.values() if r["title"]}
        if len(titles) == 1:
            print(f"✅ Consistent title found across {len(results)} sources")
            print(f"📄 Title: {list(titles)[0]}")
        elif len(titles) > 1:
            print("⚠️  Different titles found across sources:")
            for source, data in results.items():
                print(f"   {source}: {data['title']}")

        # Show first complete result
        for source, data in results.items():
            if data["title"] and data["author"]:
                print(f"\n📋 Complete metadata from {source}:")
                print(f"   Title: {data['title']}")
                print(f"   Authors: {data['author']}")
                print(f"   Journal: {data['journal']}")
                print(f"   Year: {data['year']}")
                break
    else:
        print("❌ No results found from any source")


async def main():
    """Main function to test DOI lookup."""
    if len(sys.argv) != 2:
        print("Usage: python test_doi_lookup.py <DOI>")
        print("\nExample DOIs to test:")
        print("  10.1038/nature12373")
        print("  10.1016/j.cell.2020.02.052")
        print("  10.1126/science.1234567")
        sys.exit(1)

    doi = sys.argv[1]
    await lookup_doi(doi)


if __name__ == "__main__":
    asyncio.run(main())
