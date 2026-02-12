"""
Autodesk Alias API Documentation MCP Server (V2)

This MCP server provides search capabilities over the Tavily-scraped
Autodesk Alias API documentation, which includes properly formatted
code blocks and cleaner content.

Data source: data/docs_tavily/
"""

import json
import re
from pathlib import Path
from mcp.server.fastmcp import FastMCP

# Initialize the MCP server
mcp = FastMCP("autodesk-alias-docs")

# Path to Tavily-scraped documentation
DOCS_DIR = Path(__file__).parent.parent / "data" / "docs_tavily"


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_documentation() -> list[dict]:
    """Load all scraped documentation from JSON files."""
    docs = []

    if not DOCS_DIR.exists():
        return docs

    for json_file in DOCS_DIR.glob("*.json"):
        if json_file.name == "index.json":
            continue
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                doc = json.load(f)
                docs.append(doc)
        except Exception as e:
            print(f"Error loading {json_file}: {e}")

    return docs


# Cache for loaded documentation
_docs_cache: list[dict] | None = None


def get_docs() -> list[dict]:
    """Get cached documentation or load it."""
    global _docs_cache
    if _docs_cache is None:
        _docs_cache = load_documentation()
    return _docs_cache


# ---------------------------------------------------------------------------
# Search helpers
# ---------------------------------------------------------------------------

def search_docs(query: str, docs: list[dict], max_results: int = 5) -> list[dict]:
    """
    Keyword-based search over documentation with relevance scoring.

    Scoring:
      - Exact title match: +50
      - Query term in title: +10 per term
      - Query term in content: +1 per occurrence
      - Bonus for pages with code blocks when query looks code-related
    """
    query_lower = query.lower()
    query_terms = query_lower.split()

    # Heuristic: boost code pages when query looks like a class/method name
    code_query = bool(re.match(r"^Al[A-Z]", query)) or "::" in query

    results = []

    for doc in docs:
        title = doc.get("title", "")
        title_lower = title.lower()
        content = doc.get("content", "")
        content_lower = content.lower()

        score = 0
        matched_terms = []

        # Exact title match (case-insensitive)
        if query_lower == title_lower:
            score += 50

        for term in query_terms:
            if term in title_lower:
                score += 10
                matched_terms.append(term)
            count = content_lower.count(term)
            if count > 0:
                score += count
                if term not in matched_terms:
                    matched_terms.append(term)

        # Boost pages with code when query looks code-related
        if code_query and doc.get("has_code_blocks"):
            score = int(score * 1.2)

        if score > 0:
            snippet = extract_snippet(content, query_terms)
            results.append({
                "guid": doc.get("guid"),
                "title": title,
                "url": doc.get("url"),
                "score": score,
                "matched_terms": matched_terms,
                "has_code": doc.get("has_code_blocks", False),
                "snippet": snippet,
            })

    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:max_results]


def extract_snippet(content: str, query_terms: list[str], snippet_length: int = 500) -> str:
    """Extract a relevant snippet from the content containing query terms."""
    content_lower = content.lower()

    # Find the first occurrence of any query term
    best_pos = len(content)
    for term in query_terms:
        pos = content_lower.find(term)
        if pos != -1 and pos < best_pos:
            best_pos = pos

    if best_pos == len(content):
        # No positional match - return the beginning
        return content[:snippet_length] + ("..." if len(content) > snippet_length else "")

    # Extract snippet around the match
    start = max(0, best_pos - 80)
    end = min(len(content), start + snippet_length)

    snippet = content[start:end]

    if start > 0:
        snippet = "..." + snippet
    if end < len(content):
        snippet = snippet + "..."

    return snippet


# ---------------------------------------------------------------------------
# MCP Tools
# ---------------------------------------------------------------------------

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
        return "No documentation available. Ensure data/docs_tavily/ contains scraped JSON files."

    results = search_docs(query, docs, max_results)

    if not results:
        return f"No results found for: {query}"

    output = f"Found {len(results)} results for: {query}\n\n"

    for i, result in enumerate(results, 1):
        code_tag = " 📝" if result["has_code"] else ""
        output += f"## {i}. {result['title']}{code_tag}\n"
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
        return "No documentation available. Ensure data/docs_tavily/ contains scraped JSON files."

    # Group by type
    class_docs = []
    guide_docs = []

    for doc in sorted(docs, key=lambda x: x.get("title", "")):
        title = doc.get("title", "")
        if title.startswith("Al"):
            class_docs.append(doc)
        else:
            guide_docs.append(doc)

    output = f"Available documentation pages ({len(docs)} total):\n\n"

    output += f"### Class Reference ({len(class_docs)} classes)\n"
    for doc in class_docs:
        code_tag = " 📝" if doc.get("has_code_blocks") else ""
        output += f"- **{doc.get('title')}**{code_tag}\n"

    output += f"\n### Guides & Concepts ({len(guide_docs)} pages)\n"
    for doc in guide_docs:
        code_tag = " 📝" if doc.get("has_code_blocks") else ""
        output += f"- **{doc.get('title')}**{code_tag}\n"

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

    # Try exact match first, then partial
    for doc in docs:
        if title_lower == doc.get("title", "").lower():
            return _format_doc(doc)

    for doc in docs:
        if title_lower in doc.get("title", "").lower():
            return _format_doc(doc)

    return f"No documentation found matching: {title}"


def _format_doc(doc: dict) -> str:
    """Format a document for output."""
    output = f"# {doc.get('title')}\n\n"
    output += f"**URL:** {doc.get('url')}\n"
    if doc.get("has_code_blocks"):
        output += "**Contains code examples:** Yes\n"
    output += "\n"
    output += doc.get("content", "No content available.")
    return output


# ---------------------------------------------------------------------------
# Server entry point
# ---------------------------------------------------------------------------

def run_server():
    """Run the MCP server."""
    print("Starting Autodesk Alias Documentation MCP Server (V2 - Tavily)...")
    print(f"Documentation directory: {DOCS_DIR}")

    docs = get_docs()
    code_count = sum(1 for d in docs if d.get("has_code_blocks"))
    print(f"Loaded {len(docs)} documentation pages ({code_count} with code blocks)")

    mcp.run()


if __name__ == "__main__":
    run_server()
