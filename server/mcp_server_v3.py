"""
Autodesk Alias API Documentation MCP Server (V3)

Improvements over V2:
  - Tool annotations (readOnlyHint, destructiveHint, etc.)
  - Pydantic input validation on all tools
  - Pagination for list_available_docs
  - All tools are async
  - BM25 (Okapi) ranking for search instead of naive keyword counting
  - Dual response format (JSON / Markdown)
  - Memory optimization (raw_content stripped on load)
  - Lifespan-managed initialization (docs + BM25 index)
  - New get_code_examples tool
  - Context-based structured logging (ctx.info / ctx.debug)
  - MCP Resource for documentation index
  - Actionable error messages with recovery hints

Data source: data/docs_tavily/
"""

import json
import re
from contextlib import asynccontextmanager
from enum import Enum
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict, field_validator
from mcp.server.fastmcp import FastMCP, Context
from rank_bm25 import BM25Okapi


# Path to Tavily-scraped documentation
DOCS_DIR = Path(__file__).parent.parent / "data" / "docs_tavily"


# ---------------------------------------------------------------------------
# Response format enum (shared across tools)
# ---------------------------------------------------------------------------

class ResponseFormat(str, Enum):
    MARKDOWN = "markdown"
    JSON = "json"


# ---------------------------------------------------------------------------
# Pydantic Input Models
# ---------------------------------------------------------------------------

class SearchInput(BaseModel):
    """Input model for searching Alias documentation."""

    model_config = ConfigDict(str_strip_whitespace=True)

    query: str = Field(
        ...,
        description=(
            "Search query — use class names (e.g. 'AlCurve'), "
            "method names (e.g. 'create'), or natural-language phrases "
            "(e.g. 'create NURBS surface')"
        ),
        min_length=1,
        max_length=500,
    )
    max_results: int = Field(
        default=5,
        description="Maximum number of results to return (1–20)",
        ge=1,
        le=20,
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format: 'markdown' (human-readable) or 'json' (machine-readable)",
    )

    @field_validator("query")
    @classmethod
    def validate_query(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Query cannot be empty or whitespace only")
        return v.strip()


class GetDocInput(BaseModel):
    """Input model for retrieving a single doc page by title."""

    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(
        ...,
        description=(
            "Title of the documentation page (partial match supported). "
            "Examples: 'AlCurve', 'Momentary', 'NURBS'"
        ),
        min_length=1,
        max_length=300,
    )

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Title cannot be empty or whitespace only")
        return v.strip()


class CategoryFilter(str, Enum):
    ALL = "all"
    CLASS = "class"
    GUIDE = "guide"


class ListDocsInput(BaseModel):
    """Input model for listing available documentation pages with pagination."""

    model_config = ConfigDict(str_strip_whitespace=True)

    limit: int = Field(
        default=30,
        description="Maximum number of pages to return per request (1–100)",
        ge=1,
        le=100,
    )
    offset: int = Field(
        default=0,
        description="Number of pages to skip (for pagination)",
        ge=0,
    )
    category: CategoryFilter = Field(
        default=CategoryFilter.ALL,
        description=(
            "Filter by category: 'all' (default), "
            "'class' for API class reference (titles starting with 'Al'), "
            "'guide' for conceptual guides and examples"
        ),
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format: 'markdown' (human-readable) or 'json' (machine-readable)",
    )


class CodeExamplesInput(BaseModel):
    """Input model for finding documentation pages with code examples."""

    model_config = ConfigDict(str_strip_whitespace=True)

    topic: str = Field(
        ...,
        description=(
            "Topic to find code examples for (e.g. 'NURBS', 'AlCurve', 'plug-in')"
        ),
        min_length=1,
        max_length=500,
    )
    max_results: int = Field(
        default=5,
        description="Maximum number of results to return (1–10)",
        ge=1,
        le=10,
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format: 'markdown' (human-readable) or 'json' (machine-readable)",
    )

    @field_validator("topic")
    @classmethod
    def validate_topic(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Topic cannot be empty or whitespace only")
        return v.strip()


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_documentation() -> list[dict]:
    """
    Load all scraped documentation from JSON files.

    Memory optimization: ``raw_content`` is stripped during loading because
    it duplicates ``content`` in a larger, uncleaned form (HTML with nav/
    footer junk).  This typically saves 5-20 MB across all docs.
    """
    docs = []

    if not DOCS_DIR.exists():
        return docs

    for json_file in DOCS_DIR.glob("*.json"):
        if json_file.name == "index.json":
            continue
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                doc = json.load(f)
                # Drop raw_content to save memory — content is the cleaned version
                doc.pop("raw_content", None)
                docs.append(doc)
        except Exception as e:
            print(f"Error loading {json_file}: {e}")

    return docs


# ---------------------------------------------------------------------------
# BM25 helpers
# ---------------------------------------------------------------------------

def _tokenize(text: str) -> list[str]:
    """Simple tokenizer: lowercase, split on non-alphanumeric, drop short tokens."""
    tokens = re.split(r"[^a-zA-Z0-9]+", text.lower())
    return [t for t in tokens if len(t) >= 2]


def _build_bm25_index(docs: list[dict]) -> tuple[BM25Okapi, list[list[str]]]:
    """Build a BM25 index over all document content (title + content)."""
    corpus = []
    for doc in docs:
        # Combine title (repeated for extra weight) and content
        title = doc.get("title", "")
        content = doc.get("content", "")
        text = f"{title} {title} {title} {content}"
        corpus.append(_tokenize(text))
    return BM25Okapi(corpus), corpus


# ---------------------------------------------------------------------------
# Lifespan management — initialize docs + BM25 once at server start
# ---------------------------------------------------------------------------

@asynccontextmanager
async def server_lifespan(server: FastMCP):
    """
    FastMCP lifespan handler.

    Loads documentation and builds the BM25 index once at startup,
    making them available via ``ctx.request_context.lifespan_state``.
    """
    docs = load_documentation()
    bm25_index, tokenized_corpus = _build_bm25_index(docs)
    code_count = sum(1 for d in docs if d.get("has_code_blocks"))

    print(f"Loaded {len(docs)} documentation pages ({code_count} with code blocks)")
    print("BM25 search index built successfully.")

    yield {
        "docs": docs,
        "bm25_index": bm25_index,
        "tokenized_corpus": tokenized_corpus,
    }


# Initialize the MCP server with lifespan
mcp = FastMCP("autodesk-alias-docs", lifespan=server_lifespan)


def _get_state(ctx: Context) -> dict:
    """Extract lifespan state from the MCP context."""
    return ctx.request_context.lifespan_state


# ---------------------------------------------------------------------------
# Search helpers
# ---------------------------------------------------------------------------

def search_docs(
    query: str,
    docs: list[dict],
    bm25: BM25Okapi,
    max_results: int = 5,
) -> list[dict]:
    """
    BM25-based search over documentation with additional heuristic boosts.

    Scoring:
      1. BM25 Okapi score (primary, corpus-aware TF-IDF ranking)
      2. Exact title match bonus: +50
      3. Query term in title: +10 per term
      4. Code-block boost: 1.2x when query looks like a class/method name
    """
    query_tokens = _tokenize(query)

    if not query_tokens:
        return []

    # Get BM25 scores for all documents
    bm25_scores = bm25.get_scores(query_tokens)

    query_lower = query.lower()
    query_terms = query_lower.split()
    code_query = bool(re.match(r"^Al[A-Z]", query)) or "::" in query

    results = []

    for idx, doc in enumerate(docs):
        bm25_score = float(bm25_scores[idx])
        if bm25_score <= 0:
            continue

        title = doc.get("title", "")
        title_lower = title.lower()
        content = doc.get("content", "")

        # Combine BM25 with heuristic boosts
        score = bm25_score
        matched_terms = []

        # Exact title match bonus
        if query_lower == title_lower:
            score += 50

        for term in query_terms:
            if term in title_lower:
                score += 10
                matched_terms.append(term)
            elif term in content.lower():
                if term not in matched_terms:
                    matched_terms.append(term)

        # Code-block boost
        if code_query and doc.get("has_code_blocks"):
            score *= 1.2

        snippet = extract_snippet(content, query_terms)
        results.append({
            "guid": doc.get("guid"),
            "title": title,
            "url": doc.get("url"),
            "score": round(score, 2),
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
        # No positional match — return the beginning
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
# Response formatters
# ---------------------------------------------------------------------------

def _format_search_results_md(results: list[dict], query: str) -> str:
    """Format search results as Markdown."""
    output = f"Found {len(results)} results for: {query}\n\n"
    for i, result in enumerate(results, 1):
        code_tag = " 📝" if result["has_code"] else ""
        output += f"## {i}. {result['title']}{code_tag}\n"
        output += f"**URL:** {result['url']}\n"
        output += f"**Matched terms:** {', '.join(result['matched_terms'])}\n"
        output += f"\n{result['snippet']}\n\n"
        output += "---\n\n"
    return output


def _format_search_results_json(results: list[dict], query: str) -> str:
    """Format search results as JSON."""
    payload = {
        "query": query,
        "total_results": len(results),
        "results": results,
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)


def _format_list_md(
    page: list[dict],
    total: int,
    offset: int,
    has_more: bool,
    next_offset: int | None,
    category_label: str,
) -> str:
    """Format paginated list as Markdown."""
    output = f"## {category_label} ({total} total)\n"
    output += f"Showing {offset + 1}–{offset + len(page)} of {total}\n\n"

    for doc in page:
        code_tag = " 📝" if doc.get("has_code_blocks") else ""
        output += f"- **{doc.get('title')}**{code_tag}\n"

    output += "\n---\n"
    output += f"**Total:** {total} | **Showing:** {len(page)} | **Offset:** {offset}\n"

    if has_more:
        output += f"**Has more:** Yes | **Next offset:** {next_offset}\n"
    else:
        output += "**Has more:** No\n"

    return output


def _format_list_json(
    page: list[dict],
    total: int,
    offset: int,
    has_more: bool,
    next_offset: int | None,
    category_label: str,
) -> str:
    """Format paginated list as JSON."""
    payload = {
        "category": category_label,
        "total": total,
        "offset": offset,
        "showing": len(page),
        "has_more": has_more,
        "next_offset": next_offset,
        "pages": [
            {
                "title": doc.get("title"),
                "guid": doc.get("guid"),
                "has_code": doc.get("has_code_blocks", False),
            }
            for doc in page
        ],
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# MCP Tools
# ---------------------------------------------------------------------------

@mcp.tool(
    name="search_alias_docs",
    annotations={
        "title": "Search Alias Documentation",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def search_alias_docs(params: SearchInput, ctx: Context = None) -> str:
    """
    Search the Autodesk Alias Python API documentation.

    Args:
        params (SearchInput): Validated input parameters containing:
            - query (str): Search string to match against titles and content
            - max_results (int): Maximum results to return (1–20, default 5)
            - response_format (str): 'markdown' or 'json' (default 'markdown')

    Returns:
        str: Search results in the requested format.
    """
    state = _get_state(ctx)
    docs = state["docs"]
    bm25 = state["bm25_index"]

    await ctx.info(f"Searching for '{params.query}' (max_results={params.max_results}, format={params.response_format.value})")

    if not docs:
        return (
            "No documentation available. "
            "The data/docs_tavily/ directory is empty or missing. "
            "Run the Tavily scraper first to populate documentation."
        )

    results = search_docs(params.query, docs, bm25, params.max_results)

    if not results:
        await ctx.debug(f"No results found for '{params.query}'")
        return (
            f"No results found for: '{params.query}'.\n\n"
            f"**Suggestions:**\n"
            f"- Try broader terms (e.g. 'surface' instead of 'create NURBS surface')\n"
            f"- Use API class names directly (e.g. 'AlCurve', 'AlSurface')\n"
            f"- Use `list_available_docs` to browse all {len(docs)} pages\n"
            f"- Use `get_code_examples` to find pages with code samples"
        )

    await ctx.debug(f"Found {len(results)} results for '{params.query}'")

    if params.response_format == ResponseFormat.JSON:
        return _format_search_results_json(results, params.query)
    return _format_search_results_md(results, params.query)


@mcp.tool(
    name="list_available_docs",
    annotations={
        "title": "List Available Documentation Pages",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def list_available_docs(params: ListDocsInput, ctx: Context = None) -> str:
    """
    List all available documentation pages with pagination support.

    Args:
        params (ListDocsInput): Validated input parameters containing:
            - limit (int): Max pages to return per request (1–100, default 30)
            - offset (int): Number of pages to skip for pagination (default 0)
            - category (str): Filter — 'all', 'class', or 'guide' (default 'all')
            - response_format (str): 'markdown' or 'json' (default 'markdown')

    Returns:
        str: Paginated list in the requested format.
    """
    state = _get_state(ctx)
    docs = state["docs"]

    await ctx.info(f"Listing docs (category={params.category.value}, offset={params.offset}, limit={params.limit})")

    if not docs:
        return (
            "No documentation available. "
            "The data/docs_tavily/ directory is empty or missing. "
            "Run the Tavily scraper first to populate documentation."
        )

    # Apply category filter
    if params.category == CategoryFilter.CLASS:
        filtered = [d for d in docs if d.get("title", "").startswith("Al")]
    elif params.category == CategoryFilter.GUIDE:
        filtered = [d for d in docs if not d.get("title", "").startswith("Al")]
    else:
        filtered = docs

    # Sort alphabetically by title
    filtered = sorted(filtered, key=lambda x: x.get("title", ""))
    total = len(filtered)

    # Apply pagination
    page = filtered[params.offset : params.offset + params.limit]

    if not page:
        return (
            f"No pages found at offset {params.offset}. "
            f"Total matching pages: {total}. "
            f"Try offset=0 or a smaller offset value."
        )

    has_more = (params.offset + params.limit) < total
    next_offset = params.offset + params.limit if has_more else None

    category_label = {
        CategoryFilter.ALL: "All",
        CategoryFilter.CLASS: "Class Reference",
        CategoryFilter.GUIDE: "Guides & Concepts",
    }[params.category]

    await ctx.debug(f"Returning {len(page)} of {total} pages (has_more={has_more})")

    if params.response_format == ResponseFormat.JSON:
        return _format_list_json(page, total, params.offset, has_more, next_offset, category_label)
    return _format_list_md(page, total, params.offset, has_more, next_offset, category_label)


@mcp.tool(
    name="get_doc_by_title",
    annotations={
        "title": "Get Documentation Page by Title",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def get_doc_by_title(params: GetDocInput, ctx: Context = None) -> str:
    """
    Get the full content of a documentation page by its title.

    Args:
        params (GetDocInput): Validated input parameters containing:
            - title (str): Title of the page (partial match supported)

    Returns:
        str: Full Markdown content of the matching documentation page,
             including title, URL, and whether it contains code examples.
    """
    state = _get_state(ctx)
    docs = state["docs"]
    title_lower = params.title.lower()

    await ctx.info(f"Looking up doc page: '{params.title}'")

    # Try exact match first, then partial
    for doc in docs:
        if title_lower == doc.get("title", "").lower():
            await ctx.debug(f"Exact match found: '{doc.get('title')}'")
            return _format_doc(doc)

    for doc in docs:
        if title_lower in doc.get("title", "").lower():
            await ctx.debug(f"Partial match found: '{doc.get('title')}'")
            return _format_doc(doc)

    # Build a helpful error with suggestions
    await ctx.debug(f"No match found for '{params.title}', generating suggestions")
    suggestions = _find_similar_titles(title_lower, docs, max_suggestions=3)
    msg = f"No documentation found matching: '{params.title}'."
    if suggestions:
        msg += "\n\n**Did you mean:**\n"
        for s in suggestions:
            msg += f"- {s}\n"
    msg += (
        "\n**Recovery options:**\n"
        "- Use `list_available_docs` to browse all pages\n"
        "- Use `search_alias_docs` to search by keyword\n"
        "- Try a shorter or more general title fragment"
    )
    return msg


@mcp.tool(
    name="get_code_examples",
    annotations={
        "title": "Find Code Examples",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def get_code_examples(params: CodeExamplesInput, ctx: Context = None) -> str:
    """
    Find documentation pages that contain code examples for a given topic.

    Only returns pages that have code blocks, making it ideal for finding
    implementation examples, sample plug-ins, and API usage patterns.

    Args:
        params (CodeExamplesInput): Validated input parameters containing:
            - topic (str): Topic to search for (e.g. 'NURBS', 'AlCurve', 'plug-in')
            - max_results (int): Maximum results to return (1–10, default 5)
            - response_format (str): 'markdown' or 'json' (default 'markdown')

    Returns:
        str: Documentation pages with code examples, in the requested format.
    """
    state = _get_state(ctx)
    docs = state["docs"]
    bm25 = state["bm25_index"]

    await ctx.info(f"Searching code examples for '{params.topic}' (max_results={params.max_results})")

    if not docs:
        return (
            "No documentation available. "
            "The data/docs_tavily/ directory is empty or missing. "
            "Run the Tavily scraper first to populate documentation."
        )

    # Filter to only docs with code blocks
    code_docs = [d for d in docs if d.get("has_code_blocks")]

    if not code_docs:
        return "No documentation pages with code examples found in the current dataset."

    # Search within the full corpus but filter results to code-only
    all_results = search_docs(params.topic, docs, bm25, max_results=50)
    code_results = [r for r in all_results if r["has_code"]][:params.max_results]

    if not code_results:
        await ctx.debug(f"No code results for '{params.topic}' (total code pages: {len(code_docs)})")
        return (
            f"No code examples found for: '{params.topic}'.\n\n"
            f"**Info:** There are {len(code_docs)} pages with code blocks in the dataset.\n\n"
            f"**Suggestions:**\n"
            f"- Try broader terms (e.g. 'plug-in' instead of 'momentary plug-in example')\n"
            f"- Use `search_alias_docs` to find related pages first\n"
            f"- Use `list_available_docs(category='guide')` to browse all guides"
        )

    await ctx.debug(f"Found {len(code_results)} code examples for '{params.topic}'")

    if params.response_format == ResponseFormat.JSON:
        return _format_search_results_json(code_results, params.topic)

    output = f"Found {len(code_results)} pages with code examples for: {params.topic}\n\n"
    for i, result in enumerate(code_results, 1):
        output += f"## {i}. {result['title']} 📝\n"
        output += f"**URL:** {result['url']}\n"
        output += f"**Matched terms:** {', '.join(result['matched_terms'])}\n"
        output += f"\n{result['snippet']}\n\n"
        output += "---\n\n"
    return output


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _format_doc(doc: dict) -> str:
    """Format a document for output."""
    output = f"# {doc.get('title')}\n\n"
    output += f"**URL:** {doc.get('url')}\n"
    if doc.get("has_code_blocks"):
        output += "**Contains code examples:** Yes\n"
    output += "\n"
    output += doc.get("content", "No content available.")
    return output


def _find_similar_titles(query: str, docs: list[dict], max_suggestions: int = 3) -> list[str]:
    """Find titles that partially overlap with the query for error suggestions."""
    query_terms = set(query.lower().split())
    scored = []

    for doc in docs:
        title = doc.get("title", "")
        title_terms = set(title.lower().split())
        overlap = len(query_terms & title_terms)
        if overlap > 0:
            scored.append((overlap, title))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [title for _, title in scored[:max_suggestions]]


# ---------------------------------------------------------------------------
# MCP Resources
# ---------------------------------------------------------------------------

@mcp.resource("docs://index")
async def docs_index(ctx: Context = None) -> str:
    """
    Documentation index resource.

    Returns a JSON summary of all available documentation pages, including
    title, GUID, URL, and whether each page contains code examples.
    More efficient than list_available_docs for programmatic access to
    the full index without pagination overhead.
    """
    state = _get_state(ctx)
    docs = state["docs"]

    index = {
        "total": len(docs),
        "code_pages": sum(1 for d in docs if d.get("has_code_blocks")),
        "pages": [
            {
                "title": doc.get("title"),
                "guid": doc.get("guid"),
                "url": doc.get("url"),
                "has_code": doc.get("has_code_blocks", False),
                "category": "class" if doc.get("title", "").startswith("Al") else "guide",
            }
            for doc in sorted(docs, key=lambda x: x.get("title", ""))
        ],
    }
    return json.dumps(index, indent=2, ensure_ascii=False)


@mcp.resource("docs://stats")
async def docs_stats(ctx: Context = None) -> str:
    """
    Documentation statistics resource.

    Returns a quick summary of the documentation corpus: total pages,
    class reference count, guide count, and pages with code examples.
    """
    state = _get_state(ctx)
    docs = state["docs"]

    class_count = sum(1 for d in docs if d.get("title", "").startswith("Al"))
    guide_count = len(docs) - class_count
    code_count = sum(1 for d in docs if d.get("has_code_blocks"))

    stats = {
        "total_pages": len(docs),
        "class_reference_pages": class_count,
        "guide_pages": guide_count,
        "pages_with_code": code_count,
    }
    return json.dumps(stats, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Server entry point
# ---------------------------------------------------------------------------

def run_server():
    """Run the MCP server."""
    print("Starting Autodesk Alias Documentation MCP Server (V3)...")
    print(f"Documentation directory: {DOCS_DIR}")
    mcp.run()


if __name__ == "__main__":
    run_server()
