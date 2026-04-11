# Autodesk Alias API MCP Server

An MCP (Model Context Protocol) server that gives AI assistants and coding agents searchable access to the **Autodesk Alias API** documentation. It can be used with **any MCP-compatible client**, including tools such as Codex, Cursor, Claude Code, and similar environments.

> ⚠️ **Disclaimer:** This is an unofficial, personal project. It is not affiliated with, endorsed by, or supported by Autodesk Inc.

---

## What This Project Does

The Autodesk Alias API documentation is scraped from the official Autodesk help site and stored locally as structured JSON files. At startup, the server loads the generated documentation pages, strips unnecessary data to save memory, builds runtime section-aware chunks, derives metadata, and creates a search index for fast relevance-ranked retrieval.

The purpose of this project is straightforward:

- make Autodesk Alias documentation usable from MCP-compatible coding agents
- help those agents retrieve the right API references and code examples
- reduce hallucination while building Alias plug-ins

---

## Why The Docs Are Not Included In The Repo

This repository does **not** ship Autodesk documentation files directly.

Instead, the repo provides:

- the MCP server
- the scraping script
- the local workflow to generate your own documentation dataset

This keeps the project usable without republishing Autodesk documentation content in the GitHub repository.

---

## Documentation Generation

The repo includes a scraper script here:

- `scraper_tavily/tavily_scraper.py`

The current provided scraping workflow uses the Tavily Extract API to retrieve and clean Alias documentation pages.
It is the re-scraping step used in this project: it reads a seed index of documentation page URLs and writes the cleaned output dataset used by the server.

### Basic scrape flow

1. Install dependencies

```bash
pip install -r requirements.txt
```

2. Set your Tavily API key

```bash
set TAVILY_API_KEY=your_api_key_here
```

3. Use the provided seed index

The scraper reads its source page list from:

- `data/docs/index.json`

This file is a URL manifest only. It contains page GUIDs, titles, and official Autodesk help URLs, not the scraped documentation content.

4. Run a small test scrape first

```bash
python scraper_tavily/tavily_scraper.py --test
```

5. Run the full scrape

```bash
python scraper_tavily/tavily_scraper.py
```

### What the scraper produces

After the scrape completes, the generated dataset is written locally under:

- `data/docs_tavily/`

That folder will contain:

- one JSON file per documentation page
- an `index.json` summary file for the generated corpus

That generated folder is the dataset the MCP server reads at runtime.

---

## How The Server Works

Once the documentation has been generated locally, the server:

- loads the structured page JSON files
- builds runtime chunks from each page for better retrieval
- preserves code blocks for code-focused search
- derives metadata such as headings, parent-page context, and code-block counts
- builds a BM25-based search index over the chunked content

This makes it easier for coding agents to:

- search by API name
- search by concept
- fetch full pages
- retrieve code-bearing examples for implementation work

---

## Available Tools

The current server exposes four main tools.

### `search_alias_docs(query, max_results=5, response_format="markdown")`

Search the Alias documentation using section-aware BM25 ranking.

Examples:

```text
search_alias_docs("create NURBS surface")
search_alias_docs("AlCurve", response_format="json")
```

### `get_doc_by_title(title, response_format="markdown")`

Retrieve the full content of a documentation page by title or partial title.

Example:

```text
get_doc_by_title("AlCurve")
```

### `list_available_docs(response_format="markdown")`

List the available documentation pages grouped into class reference and guides/concepts.

Example:

```text
list_available_docs(response_format="json")
```

### `get_code_examples(topic, max_results=5, response_format="markdown")`

Search code-bearing chunks and return code-centered excerpts. This is especially useful for plug-in implementation work.

Examples:

```text
get_code_examples("plug-in")
get_code_examples("AlCurve", response_format="json")
```

---

## Quick Start

1. Clone the repository

```bash
git clone https://github.com/Roshan-RB/Autodesk_MCP.git
cd Autodesk_MCP
```

2. Install dependencies

```bash
pip install -r requirements.txt
```

3. Confirm the seed URL index exists at `data/docs/index.json`

4. Generate the local documentation dataset using the provided scraper

```bash
python scraper_tavily/tavily_scraper.py --test
python scraper_tavily/tavily_scraper.py
```

5. Run the MCP server

```bash
python run_server.py
```

6. Run the regression checks

```bash
python test_server.py
```

7. Inspect the server locally with MCP Inspector

```bash
npx @modelcontextprotocol/inspector --config .\inspector.json --server autodesk-alias-docs
```

---

## MCP Client Config Example

```json
{
  "mcpServers": {
    "autodesk-alias-docs": {
      "command": "/path/to/Autodesk_MCP/venv/Scripts/python.exe",
      "args": ["/path/to/Autodesk_MCP/run_server.py"]
    }
  }
}
```

Replace `/path/to/Autodesk_MCP` with your local installation path.

---

## Notes

- The generated documentation dataset is local and not committed to the repository.
- The current implementation is optimized for local Alias plug-in development workflows.
- All main tools support machine-friendly JSON output through `response_format="json"`.

---

## License

This project provides tooling around Autodesk Alias documentation. The documentation content itself remains subject to Autodesk's terms of use and licensing.
