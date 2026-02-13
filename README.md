# Autodesk Alias API — MCP Server

An MCP (Model Context Protocol) server that gives AI assistants searchable access to the **Autodesk Alias API** documentation — right inside tools like Claude Desktop, Cursor, or any MCP-compatible client.

> ⚠️ **Disclaimer:** This is an unofficial, community-built project. It is not affiliated with, endorsed by, or supported by Autodesk Inc.

---

## How It Works

The Autodesk Alias Python API documentation was scraped from the official Autodesk help site and stored locally as structured JSON files. The MCP server loads these files at startup and exposes them through a set of tools that any MCP-compatible AI assistant can call.

---

## Available Tools

The server currently exposes **three tools**:

### `search_alias_docs(query, max_results)`

Search across all documentation pages using natural-language keywords. Results are ranked by a simple relevance score and returned with a snippet for quick context.

```
Example: search_alias_docs("create NURBS surface")
```

### `get_doc_by_title(title)`

Retrieve the **full content** of a specific documentation page by its title (partial match supported). Useful when you already know the class or topic you need.

```
Example: get_doc_by_title("AlCurve")
```

### `list_available_docs()`

Returns a list of all **225+ scraped documentation pages** with their titles and GUIDs — handy for browsing and discovering what's available.

---

## Quick Start

> This is an early-stage prototype — the setup is straightforward.

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
         "args": ["/path/to/Autodesk_MCP/run_server.py"]
       }
     }
   }
   ```

   Replace `/path/to/Autodesk_MCP` with your actual installation path.

---

## Documentation Coverage

The scraped dataset covers:

- **Class Reference** — AlCurve, AlSurface, AlDagNode, AlUniverse, and 100+ more
- **Plugin Development** — Momentary, Continuous, and Command History plugins
- **API Examples** — Complete code examples with explanations
- **Implementation Guides** — Compiling, linking, and setting up plugins

---

## What's Next

This project is in its early stages. Here's where the development is heading:

- **Hybrid / Semantic Retrieval** — Replacing the current keyword search with a hybrid or semantic retrieval strategy for more accurate, context-aware results.
- **Context-Based Tool Selection** — Exploring smarter ways to route queries to the right tool, based on the user's intent and context.
- **Plugin Development** — Building real Autodesk Alias plugins powered by this MCP server and testing whether an AI-assisted workflow actually works in practice.

Stay tuned — this repo is actively being developed. ⭐

---

## License

This project provides a tool to access Autodesk Alias documentation. The documentation content itself is © Autodesk Inc. Please refer to [Autodesk's terms of use](https://www.autodesk.com/company/legal-notices-trademarks) for documentation licensing.
