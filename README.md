# Autodesk Alias Programmers' Interfaces (API) MCP Server

An MCP (Model Context Protocol) server that gives AI assistants and coding agents searchable access to the **Autodesk Alias Programmers' Interfaces (API)** documentation. It can be used with **any MCP-compatible client**, including tools such as Codex, Cursor, Claude Code, and similar environments.

> ⚠️ **Disclaimer:** This is an unofficial, personal project. It is not affiliated with, endorsed by, or supported by Autodesk Inc.

---

> [!NOTE]
> **Not a developer? That's totally fine.**
> In short, this tool gives AI assistants (like Claude or Codex) a way to look up the real Autodesk Alias documentation on demand, so instead of guessing or making things up so when you ask them for help building Alias plug-ins, they can actually fetch the right answer in the moment. Think of it less like a textbook and more like giving the AI a direct line to the official docs whenever it needs one.

---

## What This Project Does

The Autodesk Alias Programmers' Interfaces documentation is scraped from the official Autodesk help site and stored locally as structured JSON files. At startup, the server loads the generated documentation pages, strips unnecessary data to save memory, builds runtime section-aware chunks, derives metadata, and creates a search index for fast relevance-ranked retrieval.

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

Recommended: copy the example environment file and add your Tavily API key.

```bash
cp .env.example .env
```

On Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Then edit `.env`:

```env
TAVILY_API_KEY=your_api_key_here
```

The scraper loads `.env` automatically. You can also set the variable directly in your shell instead.

Command Prompt:

```bat
set TAVILY_API_KEY=your_api_key_here
```

PowerShell:

```powershell
$env:TAVILY_API_KEY="your_api_key_here"
```

macOS/Linux:

```bash
export TAVILY_API_KEY=your_api_key_here
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
- a `failed_extractions.json` report listing any pages that Tavily could not extract or returned as empty

That generated folder is the dataset the MCP server reads at runtime.

### About the two index files

- `data/docs/index.json` is the committed seed manifest used by the scraper. It contains the page list, titles, GUIDs, and official Autodesk help URLs.
- `data/docs_tavily/index.json` is generated locally by the scraper. It is the runtime corpus index used by the MCP server and is not committed to the repository.

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

## Plug-in Build Requirements

Building real Alias `.plugin` files requires:

- Microsoft Visual Studio C++ build tools, including `nmake`, `cl.exe`, and `link.exe`
- access to Autodesk Alias API headers and libraries, typically provided by a local Autodesk Alias installation

This repository does **not** include Autodesk Alias SDK/ODS headers, libraries, or examples.

The MCP server can help coding agents write Alias plug-ins, but compiling those plug-ins requires the Alias API files to be available on the build machine.

For example, a local Alias installation may provide files such as:

- `C:\Program Files\Autodesk\AliasAutoStudio2025.0\ODS\Common\include`
- `C:\Program Files\Autodesk\AliasAutoStudio2025.0\lib\libAliasCore.lib`

Before compiling a plug-in, set `ALIAS_LOCATION` in the plug-in `Makefile` to your local Alias installation path:

```makefile
ALIAS_LOCATION=C:\Program Files\Autodesk\AliasAutoStudio2025.0
```

Do not copy Autodesk SDK/ODS files into this repository unless Autodesk's license explicitly allows redistribution.

---

## Available Tools

The current server exposes five main tools.

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

### `query_alias_docs_filesystem(command)`

Run safe read-only shell-like queries against the loaded Alias documentation corpus. This does not execute real shell commands; it only queries a virtual markdown filesystem built from the local docs dataset.

Supported commands:

- `ls`
- `find`
- `rg`
- `head`
- `tail`
- `cat`

Examples:

```text
query_alias_docs_filesystem("rg -n installOnMenu|installOnPalette /")
query_alias_docs_filesystem("head -40 /attaching-a-plug-in-to-a-menu-or-palette.md")
query_alias_docs_filesystem("cat /guid/GUID-7EAE78D4-BAF9-40D3-AB9F-ED238F4620B3.md")
```

---

> [!TIP]
> **Building a plug-in? Start with the included skill.**
> The `.agent/skills/alias-plugin-dev/SKILL.md` file contains a coding agent skill derived from analysing
> Autodesk's own official default plug-ins. It captures the standard structure,
> patterns, and conventions used in real Alias plug-ins, so your coding agent
> doesn't just know the API, it also knows how a well-built plug-in is supposed
> to look. If you're using an agent like Claude Code or Cursor, point it to this
> file before you start building.

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

3. Set your Tavily API key

```bash
cp .env.example .env
```

Then edit `.env` and set:

```env
TAVILY_API_KEY=your_api_key_here
```

4. Confirm the seed URL index exists at `data/docs/index.json`

5. Generate the local documentation dataset using the provided scraper

```bash
python scraper_tavily/tavily_scraper.py --test
python scraper_tavily/tavily_scraper.py
```

A successful full scrape should report roughly 232 scraped pages and 0 failed or empty pages.

6. Run the regression checks

```bash
python test_server.py
```

The tests expect the generated corpus at `data/docs_tavily/index.json`.

7. Run the MCP server

```bash
python run_server.py
```

8. Inspect the server locally with MCP Inspector

```bash
npx @modelcontextprotocol/inspector --config .\inspector.json --server autodesk-alias-docs
```

The provided `inspector.json` uses `python run_server.py` and assumes you run the command from the repository root with the required Python environment active. If you prefer using a specific virtual environment, edit `inspector.json` to point to that Python executable.

---

## MCP Client Config Example

```json
{
  "mcpServers": {
    "autodesk-alias-docs": {
      "command": "python",
      "args": ["run_server.py"]
    }
  }
}
```

Run this from the repository root, or replace `python` and `run_server.py` with absolute paths for your local setup.

---

## Notes

- The generated documentation dataset is local and not committed to the repository.
- The current implementation is optimized for local Alias plug-in development workflows.
- All main tools support machine-friendly JSON output through `response_format="json"`.

---

## License

This project provides tooling around Autodesk Alias documentation. The documentation content itself remains subject to Autodesk's terms of use and licensing.
