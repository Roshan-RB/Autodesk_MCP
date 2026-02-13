# Autodesk Alias API - MCP Server

An MCP (Model Context Protocol) server that provides AI assistants with searchable access to the Autodesk Alias Python API documentation.

> ⚠️ **Disclaimer:** This is an unofficial, community-built MCP server. It is not affiliated with, endorsed by, or supported by Autodesk Inc.

## Features

- 🔍 **Search documentation** - Find relevant API docs using natural language queries
- 📄 **Get full page content** - Retrieve complete documentation for any topic
- 📋 **List available docs** - Browse all 225+ API documentation pages

## Quick Start

### 1. Clone and Install

```bash
git clone https://github.com/Roshan-RB/Autodesk_MCP.git
cd Autodesk_MCP

# Create virtual environment
python -m venv venv

# Activate (Windows)
venv\Scripts\activate

# Activate (macOS/Linux)
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install Playwright browser (required for scraping)
playwright install chromium
```

### 2. Scrape Documentation (Required - One Time)

Before using the MCP server, you need to scrape the documentation from Autodesk's website:

```bash
python -m scraper.scraper
```

> **Note:** This will open a browser window and scrape ~225 documentation pages. The process takes approximately 20-25 minutes. The scraped data is saved locally to `data/docs/` and is not included in this repository.

### 3. Connect to Your AI Tool

Add the following to your MCP client configuration:

**For Claude Desktop / Cursor / Other MCP Clients:**

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

> **Note:** Replace `/path/to/Autodesk_MCP` with your actual installation path.

## Available Tools

Once connected, your AI assistant can use these tools:

| Tool | Description |
|------|-------------|
| `search_alias_docs(query)` | Search documentation using keywords |
| `get_doc_by_title(title)` | Get full content of a specific page |
| `list_available_docs()` | List all available documentation pages |

## Documentation Coverage

The scraper collects documentation for:

- **Class Reference** - AlCurve, AlSurface, AlDagNode, AlUniverse, and 100+ more
- **Plugin Development** - Momentary, Continuous, and Command History plugins
- **API Examples** - Complete code examples with explanations
- **Implementation Guides** - Compiling, linking, and setting up plugins

## Project Structure

```
Autodesk_MCP/
├── run_server.py       # MCP server entry point
├── requirements.txt    # Python dependencies
├── server/             # MCP server implementation
│   └── mcp_server.py
├── scraper/            # Documentation scraper
│   ├── config.py       # Scraper configuration
│   └── scraper.py      # Main scraper logic
└── data/docs/          # Scraped documentation (generated locally)
```

## Re-scraping Documentation

To update the documentation (e.g., for a newer Alias version):

```bash
# Delete existing docs
rm -rf data/docs/*

# Re-run scraper
python -m scraper.scraper
```

## License

This project provides a tool to access Autodesk Alias documentation. The documentation content itself is © Autodesk Inc. Please refer to [Autodesk's terms of use](https://www.autodesk.com/company/legal-notices-trademarks) for documentation licensing.
