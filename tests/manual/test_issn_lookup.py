#!/usr/bin/env python3
"""
Test utility for ISSN lookup by journal name.
Tests the ability to look up ISSN information based on journal names.
"""

import asyncio
import sys
from reflint.utils.issn_lookup import lookup_journal_issn


async def test_journal_issn_lookup(journal_name: str):
    """Test ISSN lookup for a specific journal name."""
    print(f"🔍 Looking up ISSN for journal: '{journal_name}'")
    print("=" * 60)
    
    try:
        result = await lookup_journal_issn(journal_name)
        
        if result:
            print("✅ ISSN Information Found:")
            print(f"   Journal Name: {result.get('display_name', 'N/A')}")
            print(f"   ISSN-L (Linking): {result.get('issn_l', 'N/A')}")
            print(f"   Electronic ISSN: {result.get('eissn', 'N/A')}")
            print(f"   Print ISSN: {result.get('pissn', 'N/A')}")
            print(f"   All ISSNs: {result.get('issn', [])}")
            print(f"   Source: {result.get('source', 'N/A')}")
        else:
            print("❌ No ISSN information found")
            
    except Exception as e:
        print(f"⚠️  Error: {e}")


async def test_multiple_journals():
    """Test ISSN lookup for multiple well-known journals."""
    test_journals = [
        "Nature",
        "Science", 
        "Cell",
        "The Lancet",
        "Physical Review Letters",
        "Journal of the American Chemical Society",
        "Proceedings of the National Academy of Sciences",
        "Nature Biotechnology",
        "Invalid Journal Name That Should Not Exist",
        "IEEE Computer",
        "Nature Communications"
    ]
    
    print("🧪 Testing ISSN lookup for multiple journals")
    print("=" * 60)
    
    success_count = 0
    
    for journal in test_journals:
        print(f"\n🔍 Testing: {journal}")
        print("-" * 40)
        
        try:
            result = await lookup_journal_issn(journal)
            
            if result:
                print(f"✅ Found - ISSN-L: {result.get('issn_l', 'N/A')}, "
                      f"EISSN: {result.get('eissn', 'N/A')}")
                success_count += 1
            else:
                print("❌ Not found")
                
        except Exception as e:
            print(f"⚠️  Error: {e}")
    
    print(f"\n📊 Results: {success_count}/{len(test_journals)} journals found")


async def main():
    """Main function to test ISSN lookup."""
    if len(sys.argv) == 2:
        # Single journal test
        journal_name = sys.argv[1]
        await test_journal_issn_lookup(journal_name)
    else:
        # Multiple journal test
        await test_multiple_journals()


if __name__ == "__main__":
    if len(sys.argv) > 2:
        print("Usage: python test_issn_lookup.py [journal_name]")
        print("\nExamples:")
        print("  python test_issn_lookup.py                    # Test multiple journals")
        print("  python test_issn_lookup.py \"Nature\"            # Test specific journal")
        print("  python test_issn_lookup.py \"Physical Review Letters\"")
        sys.exit(1)
    
    asyncio.run(main())