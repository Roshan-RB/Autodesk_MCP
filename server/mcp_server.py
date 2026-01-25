"""
Autodesk Alias Python API Documentation MCP Server

This MCP server provides search capabilities over the scraped Autodesk Alias
Python API documentation.
"""

import json
import os
from pathlib import Path
from mcp.server.fastmcp import FastMCP

# Initialize the MCP server
mcp = FastMCP("autodesk-alias-docs")

# Path to scraped documentation
DOCS_DIR = Path(__file__).parent.parent / "data" / "docs"


def load_documentation() -> list[dict]:
    """Load all scraped documentation from JSON files."""
    docs = []
    
    if not DOCS_DIR.exists():
        return docs
    
    for json_file in DOCS_DIR.glob("GUID-*.json"):
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                doc = json.load(f)
                docs.append(doc)
        except Exception as e:
            print(f"Error loading {json_file}: {e}")
    
    return docs


def search_docs(query: str, docs: list[dict], max_results: int = 5) -> list[dict]:
    """
    Simple keyword-based search over documentation.
    
    Returns matching documents with relevance scores.
    """
    query_terms = query.lower().split()
    results = []
    
    for doc in docs:
        title = doc.get("title", "").lower()
        content = doc.get("content", "").lower()
        
        # Calculate a simple relevance score
        score = 0
        matched_terms = []
        
        for term in query_terms:
            # Title matches are worth more
            if term in title:
                score += 10
                matched_terms.append(term)
            # Content matches
            if term in content:
                score += content.count(term)
                if term not in matched_terms:
                    matched_terms.append(term)
        
        if score > 0:
            # Extract a relevant snippet
            snippet = extract_snippet(content, query_terms)
            
            results.append({
                "guid": doc.get("guid"),
                "title": doc.get("title"),
                "url": doc.get("url"),
                "score": score,
                "matched_terms": matched_terms,
                "snippet": snippet
            })
    
    # Sort by score descending
    results.sort(key=lambda x: x["score"], reverse=True)
    
    return results[:max_results]


def extract_snippet(content: str, query_terms: list[str], snippet_length: int = 300) -> str:
    """Extract a relevant snippet from the content containing query terms."""
    content_lower = content.lower()
    
    # Find the first occurrence of any query term
    best_pos = len(content)
    for term in query_terms:
        pos = content_lower.find(term)
        if pos != -1 and pos < best_pos:
            best_pos = pos
    
    if best_pos == len(content):
        # No match found, return the beginning
        return content[:snippet_length] + "..." if len(content) > snippet_length else content
    
    # Extract snippet around the match
    start = max(0, best_pos - 50)
    end = min(len(content), start + snippet_length)
    
    snippet = content[start:end]
    
    # Add ellipsis if needed
    if start > 0:
        snippet = "..." + snippet
    if end < len(content):
        snippet = snippet + "..."
    
    return snippet


# Cache for loaded documentation
_docs_cache: list[dict] | None = None


def get_docs() -> list[dict]:
    """Get cached documentation or load it."""
    global _docs_cache
    if _docs_cache is None:
        _docs_cache = load_documentation()
    return _docs_cache


@mcp.tool()
def search_alias_docs(query: str, max_results: int = 5) -> str:
    """
    Search the Autodesk Alias Python API documentation.
    
    Args:
        query: The search query (e.g., "create NURBS surface", "AlCurve methods")
        max_results: Maximum number of results to return (default: 5)
    
    Returns:
        Matching documentation snippets with titles and links.
    """
    docs = get_docs()
    
    if not docs:
        return "No documentation available. Please run the scraper first: python -m scraper.scraper"
    
    results = search_docs(query, docs, max_results)
    
    if not results:
        return f"No results found for: {query}"
    
    # Format results
    output = f"Found {len(results)} results for: {query}\n\n"
    
    for i, result in enumerate(results, 1):
        output += f"## {i}. {result['title']}\n"
        output += f"**URL:** {result['url']}\n"
        output += f"**Matched terms:** {', '.join(result['matched_terms'])}\n"
        output += f"\n{result['snippet']}\n\n"
        output += "---\n\n"
    
    return output


@mcp.tool()
def list_available_docs() -> str:
    """
    List all available documentation pages.
    
    Returns:
        A list of all scraped documentation page titles and GUIDs.
    """
    docs = get_docs()
    
    if not docs:
        return "No documentation available. Please run the scraper first: python -m scraper.scraper"
    
    output = f"Available documentation pages ({len(docs)} total):\n\n"
    
    for doc in sorted(docs, key=lambda x: x.get("title", "")):
        output += f"- **{doc.get('title')}** (GUID: {doc.get('guid')})\n"
    
    return output


@mcp.tool()
def get_doc_by_title(title: str) -> str:
    """
    Get the full content of a documentation page by its title.
    
    Args:
        title: The title of the documentation page (partial match supported)
    
    Returns:
        The full content of the matching documentation page.
    """
    docs = get_docs()
    title_lower = title.lower()
    
    # Find matching document
    for doc in docs:
        if title_lower in doc.get("title", "").lower():
            output = f"# {doc.get('title')}\n\n"
            output += f"**URL:** {doc.get('url')}\n\n"
            output += doc.get("content", "No content available.")
            return output
    
    return f"No documentation found matching: {title}"


def run_server():
    """Run the MCP server."""
    print("Starting Autodesk Alias Documentation MCP Server...")
    print(f"Documentation directory: {DOCS_DIR}")
    
    docs = get_docs()
    print(f"Loaded {len(docs)} documentation pages")
    
    mcp.run()


if __name__ == "__main__":
    run_server()
