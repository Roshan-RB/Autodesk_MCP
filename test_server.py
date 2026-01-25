"""Test script for the MCP server search functionality."""

from server.mcp_server import get_docs, search_docs

def main():
    # Load docs
    docs = get_docs()
    print(f"Loaded {len(docs)} documentation pages")
    
    if not docs:
        print("No docs found! Run the scraper first: python -m scraper.scraper")
        return
    
    # Test search
    print("\n--- Testing search for 'plug-in' ---")
    results = search_docs("plug-in", docs)
    print(f"Found {len(results)} results")
    for r in results[:3]:
        print(f"  - {r['title']}")
        print(f"    Snippet: {r['snippet'][:100]}...")
    
    print("\n--- Testing search for 'API' ---")
    results = search_docs("API", docs)
    print(f"Found {len(results)} results")
    for r in results[:3]:
        print(f"  - {r['title']}")
    
    print("\n--- Testing search for 'OpenAlias' ---")
    results = search_docs("OpenAlias", docs)
    print(f"Found {len(results)} results")
    for r in results[:3]:
        print(f"  - {r['title']}")
    
    print("\nMCP Server tests completed successfully!")

if __name__ == "__main__":
    main()
