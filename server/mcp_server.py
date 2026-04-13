"""
Autodesk Alias Programmers' Interfaces Documentation MCP Server

This MCP server provides search capabilities over the Tavily-scraped
Autodesk Alias Programmers' Interfaces documentation, which includes
properly formatted code blocks and cleaner content.

Data source: data/docs_tavily/
"""

import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Literal

from mcp.server.fastmcp import FastMCP

# Initialize the MCP server
mcp = FastMCP("autodesk-alias-docs")

# Path to Tavily-scraped documentation
DOCS_DIR = Path(__file__).parent.parent / "data" / "docs_tavily"

CHUNK_TARGET_SIZE = 1200
CHUNK_HARD_MAX_SIZE = 1800


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
                doc["chunks"] = build_doc_chunks(doc)
                enrich_doc_metadata(doc)
                docs.append(doc)
        except Exception as e:
            print(f"Error loading {json_file}: {e}")

    return docs


# Cache for loaded documentation
_docs_cache: list[dict] | None = None
_chunk_search_index_cache: dict | None = None


def get_docs() -> list[dict]:
    """Get cached documentation or load it."""
    global _docs_cache, _chunk_search_index_cache
    if _docs_cache is None:
        _docs_cache = load_documentation()
        _chunk_search_index_cache = build_chunk_search_index(_docs_cache)
    return _docs_cache


def get_chunk_search_index(docs: list[dict] | None = None) -> dict:
    """Get cached chunk search index or build it from the loaded docs."""
    global _chunk_search_index_cache
    if _chunk_search_index_cache is None:
        if docs is None:
            docs = get_docs()
        _chunk_search_index_cache = build_chunk_search_index(docs)
    return _chunk_search_index_cache


def build_doc_chunks(doc: dict) -> list[dict]:
    """
    Split a document into section-aware chunks for better search relevance.

    The Tavily content preserves Markdown headings, so chunking can be
    derived at load time without changing the on-disk dataset.
    """
    content = doc.get("content", "")
    title = doc.get("title", "").strip() or "Untitled"

    if not content.strip():
        return []

    lines = content.splitlines()
    chunks = []
    heading_stack: list[tuple[int, str]] = []
    current_section_title = title
    current_lines: list[str] = []
    chunk_counter = 1
    i = 0

    while i < len(lines):
        heading = _parse_heading(lines, i)
        if heading is not None:
            level, heading_text, consumed = heading

            if current_lines:
                chunk_counter = _append_section_chunks(
                    chunks,
                    doc,
                    heading_stack,
                    current_section_title,
                    current_lines,
                    chunk_counter,
                )
                current_lines = []

            heading_stack = _update_heading_stack(heading_stack, level, heading_text)
            current_section_title = heading_text
            i += consumed
            continue

        current_lines.append(lines[i])
        i += 1

    if current_lines:
        _append_section_chunks(
            chunks,
            doc,
            heading_stack,
            current_section_title,
            current_lines,
            chunk_counter,
        )

    if chunks:
        return chunks

    fallback_text = content.strip()
    return [{
        "chunk_id": f"{doc.get('guid')}#chunk-001",
        "section_title": title,
        "heading_path": [title],
        "text": fallback_text,
        "has_code": "```" in fallback_text,
    }]


def enrich_doc_metadata(doc: dict) -> None:
    """Attach derived metadata to a document and its chunks."""
    content = doc.get("content", "")
    raw_or_clean = doc.get("raw_content") or content
    category = "class" if doc.get("title", "").startswith("Al") else "guide"
    parent_page_title, parent_page_url = _extract_parent_page(content)

    doc["category"] = category
    doc["content_length"] = len(content)
    doc["code_block_count"] = _count_code_blocks(raw_or_clean)
    doc["parent_page_title"] = parent_page_title
    doc["parent_page_url"] = parent_page_url
    doc["chunk_count"] = len(doc.get("chunks", []))
    doc["headings"] = _collect_doc_headings(doc.get("chunks", []))

    for index, chunk in enumerate(doc.get("chunks", []), start=1):
        chunk["chunk_index"] = index
        chunk["char_length"] = len(chunk.get("text", ""))
        chunk["code_block_count"] = _count_code_blocks(chunk.get("text", ""))
        chunk["category"] = category
        chunk["parent_page_title"] = parent_page_title
        chunk["parent_page_url"] = parent_page_url
        chunk["heading_depth"] = len(chunk.get("heading_path", []))


def _extract_parent_page(content: str) -> tuple[str | None, str | None]:
    """Extract parent page metadata from the cleaned markdown content."""
    match = re.search(r"\*\*Parent page:\*\*\[(.+?)\]\((.+?)\)", content)
    if not match:
        return None, None
    return match.group(1).strip(), match.group(2).strip()


def _count_code_blocks(text: str) -> int:
    """Count fenced code blocks in markdown-like content."""
    if not text:
        return 0
    return len(re.findall(r"```", text)) // 2


def _collect_doc_headings(chunks: list[dict]) -> list[str]:
    """Collect unique heading labels from chunk metadata, preserving order."""
    seen = set()
    headings = []

    for chunk in chunks:
        for heading in chunk.get("heading_path", []):
            normalized = heading.strip()
            if normalized and normalized not in seen:
                seen.add(normalized)
                headings.append(normalized)

    return headings


def _parse_heading(lines: list[str], index: int) -> tuple[int, str, int] | None:
    """Parse ATX and setext-style Markdown headings."""
    line = lines[index].strip()
    if not line:
        return None

    atx_match = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
    if atx_match:
        return len(atx_match.group(1)), atx_match.group(2).strip(), 1

    if index + 1 >= len(lines):
        return None

    underline = lines[index + 1].strip()
    if re.fullmatch(r"={3,}", underline):
        return 1, line, 2
    if re.fullmatch(r"-{3,}", underline):
        return 2, line, 2

    return None


def _update_heading_stack(
    heading_stack: list[tuple[int, str]],
    level: int,
    heading_text: str,
) -> list[tuple[int, str]]:
    """Maintain the current heading ancestry for chunk metadata."""
    updated = [item for item in heading_stack if item[0] < level]
    updated.append((level, heading_text))
    return updated


def _append_section_chunks(
    chunks: list[dict],
    doc: dict,
    heading_stack: list[tuple[int, str]],
    section_title: str,
    section_lines: list[str],
    chunk_counter: int,
) -> int:
    """Convert one logical section into one or more bounded-size chunks."""
    section_text = "\n".join(section_lines).strip()
    if not section_text:
        return chunk_counter

    heading_path = [item[1] for item in heading_stack] or [doc.get("title", "Untitled")]

    for piece in _split_chunk_text(section_text):
        chunks.append({
            "chunk_id": f"{doc.get('guid')}#chunk-{chunk_counter:03d}",
            "section_title": section_title,
            "heading_path": heading_path,
            "text": piece,
            "has_code": "```" in piece,
        })
        chunk_counter += 1

    return chunk_counter


def _split_chunk_text(section_text: str) -> list[str]:
    """Split large sections by paragraph while keeping chunks reasonably sized."""
    if len(section_text) <= CHUNK_HARD_MAX_SIZE:
        return [section_text]

    segments = _split_section_segments(section_text)
    if len(segments) <= 1:
        return _hard_split_text(section_text)

    pieces: list[str] = []
    current = ""

    for segment in segments:
        if len(segment) > CHUNK_HARD_MAX_SIZE:
            if current:
                pieces.append(current.strip())
                current = ""
            if segment.lstrip().startswith("```"):
                pieces.append(segment.strip())
            else:
                pieces.extend(_hard_split_text(segment))
            continue

        candidate = segment if not current else f"{current}\n\n{segment}"
        if len(candidate) <= CHUNK_TARGET_SIZE:
            current = candidate
            continue

        if current:
            pieces.append(current.strip())
        current = segment

    if current:
        pieces.append(current.strip())

    return pieces or [section_text]


def _split_section_segments(section_text: str) -> list[str]:
    """Split a section on blank lines while preserving fenced code blocks intact."""
    segments = []
    current_lines: list[str] = []
    in_code_block = False

    for line in section_text.splitlines():
        stripped = line.strip()

        if stripped.startswith("```"):
            in_code_block = not in_code_block
            current_lines.append(line)
            continue

        if not in_code_block and not stripped:
            if current_lines:
                segment = "\n".join(current_lines).strip()
                if segment:
                    segments.append(segment)
                current_lines = []
            continue

        current_lines.append(line)

    if current_lines:
        segment = "\n".join(current_lines).strip()
        if segment:
            segments.append(segment)

    return segments


def _hard_split_text(text: str) -> list[str]:
    """Fallback split for very large paragraphs without clean boundaries."""
    pieces = []
    start = 0

    while start < len(text):
        end = min(len(text), start + CHUNK_TARGET_SIZE)
        pieces.append(text[start:end].strip())
        start = end

    return [piece for piece in pieces if piece]


# ---------------------------------------------------------------------------
# Search helpers
# ---------------------------------------------------------------------------

def build_chunk_search_index(docs: list[dict]) -> dict:
    """Build a lightweight BM25 index over document chunks."""
    records = []
    records_by_doc_id: dict[int, list[dict]] = {}
    document_frequencies = Counter()
    total_doc_len = 0

    for doc in docs:
        for chunk in doc.get("chunks", []):
            search_text = "\n".join([
                chunk.get("section_title", ""),
                " ".join(chunk.get("heading_path", [])),
                chunk.get("text", ""),
            ])
            tokens = _tokenize(search_text)
            token_counts = Counter(tokens)
            doc_len = len(tokens)

            records.append({
                "doc": doc,
                "chunk": chunk,
                "tokens": tokens,
                "token_counts": token_counts,
                "doc_len": doc_len,
            })
            records_by_doc_id.setdefault(id(doc), []).append(records[-1])

            if doc_len > 0:
                total_doc_len += doc_len
                document_frequencies.update(token_counts.keys())

    total_records = len(records)
    avg_doc_len = (total_doc_len / total_records) if total_records else 1.0
    idf = {
        term: math.log(1 + ((total_records - freq + 0.5) / (freq + 0.5)))
        for term, freq in document_frequencies.items()
    }

    return {
        "records": records,
        "records_by_doc_id": records_by_doc_id,
        "idf": idf,
        "avg_doc_len": avg_doc_len,
        "chunk_count": total_records,
    }


def _tokenize(text: str) -> list[str]:
    """Lowercase tokenizer for prose and API names."""
    if not text:
        return []
    return re.findall(r"[a-z0-9_]+", text.lower())


def _bm25_score(
    query_tokens: list[str],
    token_counts: Counter,
    doc_len: int,
    idf: dict[str, float],
    avg_doc_len: float,
    k1: float = 1.5,
    b: float = 0.75,
) -> float:
    """Compute BM25 score for one chunk."""
    if not query_tokens or not token_counts or doc_len <= 0:
        return 0.0

    score = 0.0
    normalization = k1 * (1 - b + b * (doc_len / max(avg_doc_len, 1.0)))

    for term in query_tokens:
        term_frequency = token_counts.get(term, 0)
        if term_frequency <= 0:
            continue

        numerator = term_frequency * (k1 + 1)
        denominator = term_frequency + normalization
        score += idf.get(term, 0.0) * (numerator / denominator)

    return score


def _has_token_sequence(tokens: list[str], query_tokens: list[str]) -> bool:
    """Return True when all query tokens appear contiguously in order."""
    if not tokens or not query_tokens or len(query_tokens) > len(tokens):
        return False

    window_size = len(query_tokens)
    for index in range(len(tokens) - window_size + 1):
        if tokens[index:index + window_size] == query_tokens:
            return True

    return False


def _is_example_like(text: str) -> bool:
    """Detect example-oriented labels such as example pages and code filenames."""
    if not text:
        return False

    text_lower = text.lower()
    return any(marker in text_lower for marker in (
        "example",
        "sample",
        ".cpp",
        ".c++",
        ".h",
        ".py",
    ))


def _score_chunk_result(
    query: str,
    query_lower: str,
    query_terms: list[str],
    doc: dict,
    record: dict,
    idf: dict[str, float],
    avg_doc_len: float,
    code_query: bool,
    require_code: bool = False,
    code_focus: bool = False,
) -> dict | None:
    """Score one chunk and return a result payload when it is relevant."""
    title = doc.get("title", "")
    title_lower = title.lower()
    parent_page_title = doc.get("parent_page_title") or ""
    parent_page_title_lower = parent_page_title.lower()
    doc_code_block_count = doc.get("code_block_count", 0)

    chunk = record["chunk"]
    if require_code and not chunk.get("has_code"):
        return None

    section_title = chunk.get("section_title", title)
    section_title_lower = section_title.lower()
    chunk_text = chunk.get("text", "")
    chunk_code_block_count = chunk.get("code_block_count", 0)

    score = _bm25_score(
        query_terms,
        record["token_counts"],
        record["doc_len"],
        idf,
        avg_doc_len,
    )
    matched_terms = []

    if query_lower == title_lower:
        score += 50
    if query_lower == section_title_lower:
        score += 25

    for term in query_terms:
        if term in title_lower:
            score += 10
            matched_terms.append(term)
        if term in section_title_lower:
            score += 8
            if term not in matched_terms:
                matched_terms.append(term)
        if term in parent_page_title_lower:
            score += 4
            if term not in matched_terms:
                matched_terms.append(term)
        if record["token_counts"].get(term, 0) > 0:
            if term not in matched_terms:
                matched_terms.append(term)

    if query_terms:
        coverage_ratio = len(matched_terms) / len(query_terms)
        if len(query_terms) > 1:
            score *= 0.25 + (0.75 * coverage_ratio)
            if coverage_ratio == 1.0:
                score += 3 * len(query_terms)
        if _has_token_sequence(record["tokens"], query_terms):
            score += 6

    if score <= 0:
        return None

    if code_query and (doc.get("has_code_blocks") or chunk.get("has_code")):
        code_boost = 1 + (min(doc_code_block_count + chunk_code_block_count, 4) * 0.05)
        score *= code_boost

    if code_focus:
        score += 6 + min(chunk_code_block_count, 3) * 2
        if doc.get("category") == "guide":
            score += 6
        if _is_example_like(title) or _is_example_like(section_title):
            score += 10
        if code_query and doc.get("category") == "class":
            score += 4

    snippet = extract_snippet(chunk_text, query_terms)
    code_snippet = extract_code_example(chunk_text, query_terms) if chunk.get("has_code") else None

    return {
        "guid": doc.get("guid"),
        "title": title,
        "url": doc.get("url"),
        "score": score,
        "matched_terms": matched_terms,
        "has_code": doc.get("has_code_blocks", False),
        "section_title": section_title,
        "parent_page_title": parent_page_title,
        "snippet": snippet,
        "code_snippet": code_snippet,
    }


def _search_chunks(
    query: str,
    docs: list[dict],
    max_results: int = 5,
    require_code: bool = False,
    code_focus: bool = False,
) -> list[dict]:
    """
    Search documentation with BM25 chunk ranking and field-level boosts.

    Scoring:
      - BM25 over chunk headings + content
      - Exact title match: +50
      - Exact section match: +25
      - Query term in title: +10 per term
      - Query term in section title: +8 per term
      - Query term in parent page title: +4 per term
      - Bonus for pages with code blocks when query looks code-related
    """
    query_lower = query.lower().strip()
    query_terms = list(dict.fromkeys(_tokenize(query)))
    if not query_terms and query_lower:
        query_terms = list(dict.fromkeys(query_lower.split()))

    # Heuristic: boost code pages when query looks like a class/method name
    code_query = bool(re.match(r"^Al[A-Z]", query)) or "::" in query

    search_index = get_chunk_search_index(docs)
    idf = search_index.get("idf", {})
    avg_doc_len = search_index.get("avg_doc_len", 1.0)
    results = []

    for doc in docs:
        if require_code and not doc.get("has_code_blocks"):
            continue

        best_result = None

        for record in search_index.get("records_by_doc_id", {}).get(id(doc), []):
            chunk_result = _score_chunk_result(
                query,
                query_lower,
                query_terms,
                doc,
                record,
                idf,
                avg_doc_len,
                code_query,
                require_code=require_code,
                code_focus=code_focus,
            )
            if chunk_result is None:
                continue

            if best_result is None or chunk_result["score"] > best_result["score"]:
                best_result = chunk_result

        if best_result is not None:
            results.append(best_result)

    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:max_results]


def search_docs(query: str, docs: list[dict], max_results: int = 5) -> list[dict]:
    """Search documentation with chunk-aware BM25 ranking."""
    return _search_chunks(query, docs, max_results=max_results)


def search_code_examples(topic: str, docs: list[dict], max_results: int = 5) -> list[dict]:
    """Search only code-bearing chunks and favor example-oriented pages."""
    return _search_chunks(
        topic,
        docs,
        max_results=max_results,
        require_code=True,
        code_focus=True,
    )


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


def _truncate_code_block(block: str, max_length: int = 700) -> str:
    """Trim a fenced code block while preserving valid fences."""
    if len(block) <= max_length:
        return block

    lines = block.splitlines()
    if len(lines) < 2:
        return block[:max_length] + "\n..."

    opening_fence = lines[0]
    closing_fence = "```"
    body = "\n".join(lines[1:-1]).strip()
    available = max_length - len(opening_fence) - len(closing_fence) - 8
    trimmed_body = body[:max(available, 0)].rstrip()
    return f"{opening_fence}\n{trimmed_body}\n...\n{closing_fence}"


def extract_code_example(content: str, query_terms: list[str]) -> str | None:
    """Extract a code-centered snippet with brief surrounding context."""
    if not content or "```" not in content:
        return None

    code_match = re.search(r"```[\s\S]*?```", content)
    if code_match:
        code_block = _truncate_code_block(code_match.group(0).strip())
        prefix = content[:code_match.start()].strip()
        if prefix:
            context = extract_snippet(prefix, query_terms, snippet_length=180)
            if context and "```" not in context:
                return f"{context}\n\n{code_block}"
        return code_block

    if content.count("```") == 1:
        start = content.find("```")
        trailing_block = f"{content[start:].strip()}\n```"
        return _truncate_code_block(trailing_block)

    return None


# ---------------------------------------------------------------------------
# Response formatting helpers
# ---------------------------------------------------------------------------

def _normalize_response_format(response_format: str) -> str | None:
    """Validate the requested response format."""
    normalized = response_format.strip().lower()
    if normalized in {"markdown", "json"}:
        return normalized
    return None


def _json_response(payload: dict | list) -> str:
    """Serialize structured payloads for MCP text responses."""
    return json.dumps(payload, indent=2, ensure_ascii=False)


def _serialize_search_result(result: dict) -> dict:
    """Select the stable search-result fields exposed through tool output."""
    return {
        "guid": result.get("guid"),
        "title": result.get("title"),
        "url": result.get("url"),
        "score": round(result.get("score", 0.0), 6),
        "matched_terms": result.get("matched_terms", []),
        "has_code": result.get("has_code", False),
        "section_title": result.get("section_title"),
        "parent_page_title": result.get("parent_page_title"),
        "snippet": result.get("snippet"),
        "code_snippet": result.get("code_snippet"),
    }


def _serialize_doc_summary(doc: dict) -> dict:
    """Select the stable summary fields for doc listings."""
    return {
        "guid": doc.get("guid"),
        "title": doc.get("title"),
        "url": doc.get("url"),
        "category": doc.get("category"),
        "has_code_blocks": doc.get("has_code_blocks", False),
        "code_block_count": doc.get("code_block_count", 0),
        "parent_page_title": doc.get("parent_page_title"),
        "parent_page_url": doc.get("parent_page_url"),
        "chunk_count": doc.get("chunk_count", 0),
    }


def _serialize_doc_detail(doc: dict) -> dict:
    """Return a structured full-document payload."""
    return {
        **_serialize_doc_summary(doc),
        "content_length": doc.get("content_length", len(doc.get("content", ""))),
        "headings": doc.get("headings", []),
        "content": doc.get("content", ""),
    }


def _format_search_results_markdown(query: str, results: list[dict]) -> str:
    """Render standard search results as markdown."""
    output = f"Found {len(results)} results for: {query}\n\n"

    for i, result in enumerate(results, 1):
        code_tag = " [code]" if result["has_code"] else ""
        output += f"## {i}. {result['title']}{code_tag}\n"
        output += f"**URL:** {result['url']}\n"
        if result.get("section_title") and result["section_title"] != result["title"]:
            output += f"**Section:** {result['section_title']}\n"
        if result.get("parent_page_title"):
            output += f"**Parent page:** {result['parent_page_title']}\n"
        output += f"**Matched terms:** {', '.join(result['matched_terms'])}\n"
        output += f"\n{result['snippet']}\n\n"
        output += "---\n\n"

    return output


def _format_code_results_markdown(topic: str, results: list[dict]) -> str:
    """Render code-example search results as markdown."""
    output = f"Found {len(results)} code example results for: {topic}\n\n"

    for i, result in enumerate(results, 1):
        output += f"## {i}. {result['title']} [code]\n"
        output += f"**URL:** {result['url']}\n"
        if result.get("section_title") and result["section_title"] != result["title"]:
            output += f"**Section:** {result['section_title']}\n"
        if result.get("parent_page_title"):
            output += f"**Parent page:** {result['parent_page_title']}\n"
        output += f"**Matched terms:** {', '.join(result['matched_terms'])}\n"

        snippet = result.get("code_snippet") or result.get("snippet") or ""
        output += f"\n{snippet}\n\n"
        output += "---\n\n"

    return output


def _format_doc_markdown(doc: dict) -> str:
    """Format a full document as markdown."""
    output = f"# {doc.get('title')}\n\n"
    output += f"**URL:** {doc.get('url')}\n"
    if doc.get("has_code_blocks"):
        output += "**Contains code examples:** Yes\n"
    output += "\n"
    output += doc.get("content", "No content available.")
    return output


def _invalid_response_format_message(response_format: str) -> str:
    """Return a stable validation message for tool callers."""
    return f"Invalid response_format: {response_format}. Use 'markdown' or 'json'."


# ---------------------------------------------------------------------------
# MCP Tools
# ---------------------------------------------------------------------------

@mcp.tool()
def search_alias_docs(
    query: str,
    max_results: int = 5,
    response_format: Literal["markdown", "json"] = "markdown",
) -> str:
    """
    Search the Autodesk Alias Programmers' Interfaces documentation.

    Args:
        query: The search query (e.g., "create NURBS surface", "AlCurve methods")
        max_results: Maximum number of results to return (default: 5)
        response_format: Output format, either "markdown" or "json" (default: "markdown")

    Returns:
        Matching documentation snippets with titles and links.
    """
    normalized_format = _normalize_response_format(response_format)
    if normalized_format is None:
        return _invalid_response_format_message(response_format)

    docs = get_docs()

    if not docs:
        message = "No documentation available. Ensure data/docs_tavily/ contains scraped JSON files."
        if normalized_format == "json":
            return _json_response({
                "query": query,
                "count": 0,
                "results": [],
                "error": message,
            })
        return message

    results = search_docs(query, docs, max_results)

    if not results:
        if normalized_format == "json":
            return _json_response({
                "query": query,
                "count": 0,
                "results": [],
            })
        return f"No results found for: {query}"

    if normalized_format == "json":
        return _json_response({
            "query": query,
            "max_results": max_results,
            "count": len(results),
            "results": [_serialize_search_result(result) for result in results],
        })

    return _format_search_results_markdown(query, results)


@mcp.tool()
def get_code_examples(
    topic: str,
    max_results: int = 5,
    response_format: Literal["markdown", "json"] = "markdown",
) -> str:
    """
    Find code-bearing documentation chunks for a topic.

    Args:
        topic: The topic to search for in code examples (e.g., "plug-in", "AlCurve")
        max_results: Maximum number of code example results to return (default: 5)
        response_format: Output format, either "markdown" or "json" (default: "markdown")

    Returns:
        Matching code examples with context and code excerpts.
    """
    normalized_format = _normalize_response_format(response_format)
    if normalized_format is None:
        return _invalid_response_format_message(response_format)

    docs = get_docs()

    if not docs:
        message = "No documentation available. Ensure data/docs_tavily/ contains scraped JSON files."
        if normalized_format == "json":
            return _json_response({
                "topic": topic,
                "count": 0,
                "results": [],
                "error": message,
            })
        return message

    results = search_code_examples(topic, docs, max_results)

    if not results:
        if normalized_format == "json":
            return _json_response({
                "topic": topic,
                "count": 0,
                "results": [],
            })
        return f"No code examples found for: {topic}"

    if normalized_format == "json":
        return _json_response({
            "topic": topic,
            "max_results": max_results,
            "count": len(results),
            "results": [_serialize_search_result(result) for result in results],
        })

    return _format_code_results_markdown(topic, results)


@mcp.tool()
def list_available_docs(response_format: Literal["markdown", "json"] = "markdown") -> str:
    """
    List all available documentation pages.

    Args:
        response_format: Output format, either "markdown" or "json" (default: "markdown")

    Returns:
        A list of all scraped documentation page titles and GUIDs.
    """
    normalized_format = _normalize_response_format(response_format)
    if normalized_format is None:
        return _invalid_response_format_message(response_format)

    docs = get_docs()

    if not docs:
        message = "No documentation available. Ensure data/docs_tavily/ contains scraped JSON files."
        if normalized_format == "json":
            return _json_response({
                "total_count": 0,
                "class_count": 0,
                "guide_count": 0,
                "docs": [],
                "error": message,
            })
        return message

    # Group by type
    class_docs = []
    guide_docs = []

    for doc in sorted(docs, key=lambda x: x.get("title", "")):
        if doc.get("category") == "class":
            class_docs.append(doc)
        else:
            guide_docs.append(doc)

    if normalized_format == "json":
        return _json_response({
            "total_count": len(docs),
            "class_count": len(class_docs),
            "guide_count": len(guide_docs),
            "docs": [_serialize_doc_summary(doc) for doc in sorted(docs, key=lambda x: x.get("title", ""))],
        })

    output = f"Available documentation pages ({len(docs)} total):\n\n"

    output += f"### Class Reference ({len(class_docs)} classes)\n"
    for doc in class_docs:
        code_tag = " [code]" if doc.get("has_code_blocks") else ""
        output += f"- **{doc.get('title')}**{code_tag}\n"

    output += f"\n### Guides & Concepts ({len(guide_docs)} pages)\n"
    for doc in guide_docs:
        code_tag = " [code]" if doc.get("has_code_blocks") else ""
        output += f"- **{doc.get('title')}**{code_tag}\n"

    return output


@mcp.tool()
def get_doc_by_title(
    title: str,
    response_format: Literal["markdown", "json"] = "markdown",
) -> str:
    """
    Get the full content of a documentation page by its title.

    Args:
        title: The title of the documentation page (partial match supported)
        response_format: Output format, either "markdown" or "json" (default: "markdown")

    Returns:
        The full content of the matching documentation page.
    """
    normalized_format = _normalize_response_format(response_format)
    if normalized_format is None:
        return _invalid_response_format_message(response_format)

    docs = get_docs()
    title_lower = title.lower()

    # Try exact match first, then partial
    for doc in docs:
        if title_lower == doc.get("title", "").lower():
            if normalized_format == "json":
                return _json_response({
                    "query": title,
                    "found": True,
                    "doc": _serialize_doc_detail(doc),
                })
            return _format_doc(doc)

    for doc in docs:
        if title_lower in doc.get("title", "").lower():
            if normalized_format == "json":
                return _json_response({
                    "query": title,
                    "found": True,
                    "doc": _serialize_doc_detail(doc),
                })
            return _format_doc(doc)

    if normalized_format == "json":
        return _json_response({
            "query": title,
            "found": False,
            "doc": None,
        })
    return f"No documentation found matching: {title}"


def _format_doc(doc: dict) -> str:
    """Format a document for output."""
    return _format_doc_markdown(doc)


# ---------------------------------------------------------------------------
# Server entry point
# ---------------------------------------------------------------------------

def run_server():
    """Run the MCP server."""
    print("Starting Autodesk Alias Documentation MCP Server...")
    print(f"Documentation directory: {DOCS_DIR}")

    docs = get_docs()
    code_count = sum(1 for d in docs if d.get("has_code_blocks"))
    print(f"Loaded {len(docs)} documentation pages ({code_count} with code blocks)")

    mcp.run()


if __name__ == "__main__":
    run_server()
