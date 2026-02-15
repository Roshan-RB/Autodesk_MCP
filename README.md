# Autodesk Alias API - MCP Server

An MCP (Model Context Protocol) server that gives AI assistants searchable access to the **Autodesk Alias API** documentation — right inside tools like Claude Desktop, Cursor, or any MCP-compatible client.

> ⚠️ **Disclaimer:** This is an unofficial, community-built project. It is not affiliated with, endorsed by, or supported by Autodesk Inc.

---

## How It Works

The Autodesk Alias API documentation was scraped from the official Autodesk help site and stored locally as structured JSON files. At startup the server loads all **231 documentation pages**, strips unnecessary data to save memory, and builds a **BM25 search index** for fast, relevance-ranked retrieval.

---

## Available Tools

The server exposes **four tools**, all with Pydantic-validated inputs, tool annotations, and optional JSON output:

### `search_alias_docs(query, max_results, response_format)`

Search across all documentation using **BM25 (Okapi)** ranking. Results include relevance scores, matched terms, and content snippets. Heuristic boosts are applied for exact title matches and pages with code blocks.

```
Example: search_alias_docs("create NURBS surface")
Example: search_alias_docs("AlCurve", response_format="json")
```

### `get_doc_by_title(title)`

Retrieve the **full content** of a documentation page by its title (partial match supported). Returns title suggestions if no match is found.

```
Example: get_doc_by_title("AlCurve")
```

### `list_available_docs(limit, offset, category, response_format)`

Paginated listing of all documentation pages. Supports filtering by category (`class` for API reference, `guide` for tutorials/examples) and returns pagination metadata (`has_more`, `next_offset`).

```
Example: list_available_docs(category="class", limit=20)
Example: list_available_docs(offset=30, response_format="json")
```

### `get_code_examples(topic, max_results, response_format)`

Find documentation pages that contain **code examples** for a given topic. Filters search results to only pages with code blocks — ideal for finding sample plug-ins and API usage patterns.

```
Example: get_code_examples("plug-in")
Example: get_code_examples("NURBS", response_format="json")
```

---

## MCP Resources

Two read-only resources for lightweight programmatic access:

- **`docs://index`** — Full JSON index of all pages (title, GUID, URL, has_code, category)
- **`docs://stats`** — Corpus summary (total pages, class/guide/code counts)

---

## Quick Start

1. **Clone & install dependencies**

   ```bash
   git clone https://github.com/Roshan-RB/Autodesk_MCP.git
   cd Autodesk_MCP
   pip install -r requirements.txt
   ```

2. **Connect to your AI tool** — add the server to your MCP client config:

   ```json
   {
     "mcpServers": {
       "autodesk-alias-docs": {
         "command": "/path/to/Autodesk_MCP/venv/Scripts/python.exe",
         "args": ["/path/to/Autodesk_MCP/run_server_v3.py"]
       }
     }
   }
   ```

   Replace `/path/to/Autodesk_MCP` with your actual installation path.

---

## Documentation Coverage

The scraped dataset covers **231 pages** including:

- **Class Reference** — AlCurve, AlSurface, AlDagNode, AlUniverse, and 100+ more
- **Plugin Development** — Momentary, Continuous, and Command History plugins
- **API Examples** — Complete code examples with explanations
- **Implementation Guides** — Compiling, linking, and setting up plugins

---

## What's Next

- **Semantic Retrieval** — Augmenting BM25 with embedding-based search for better context-aware results
- **Context-Based Tool Selection** — Smarter query routing based on user intent
- **Plugin Development** — Building real Autodesk Alias plugins powered by this MCP server

Stay tuned — this repo is actively being developed. ⭐

---

## License

This project provides a tool to access Autodesk Alias documentation. The documentation content itself is © Autodesk Inc. Please refer to [Autodesk's terms of use](https://www.autodesk.com/company/legal-notices-trademarks) for documentation licensing.
