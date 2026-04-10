# Autodesk Alias API MCP Server

An MCP server that gives coding agents searchable access to the Autodesk Alias API documentation stored in `data/docs_tavily`.

This repo now has one active server:
- `C:\Thesis\Roshan_Projects\Autodesk_MCP\server\mcp_server.py`
- `C:\Thesis\Roshan_Projects\Autodesk_MCP\run_server.py`

Older server variants were moved out of the active path into `C:\Thesis\Roshan_Projects\Autodesk_MCP\old_trash_files`.

## What the server does

At startup the server:
- loads the Tavily-scraped Alias docs
- builds runtime section-aware chunks from each page
- derives metadata such as headings, code-block counts, and parent-page info
- builds a chunk-level BM25 index for retrieval

The goal is not generic docs hosting. The goal is to help coding agents retrieve the right Autodesk Alias API guidance and code examples while building plug-ins.

## Active tools

### `search_alias_docs(query, max_results=5, response_format="markdown")`

Search the Alias documentation with chunk-aware BM25 ranking.

Features:
- section-aware retrieval
- title and section boosts
- parent-page metadata in results
- markdown or JSON output

### `get_doc_by_title(title, response_format="markdown")`

Return the full content of a documentation page by title or partial title.

### `list_available_docs(response_format="markdown")`

List all available documentation pages grouped into:
- class reference
- guides and concepts

### `get_code_examples(topic, max_results=5, response_format="markdown")`

Search only code-bearing chunks and return code-centered excerpts. This is the most useful tool when the agent needs sample plug-in patterns.

## Data source

The active dataset is:
- `C:\Thesis\Roshan_Projects\Autodesk_MCP\data\docs_tavily`

## Quick start

1. Install dependencies

```bash
pip install -r requirements.txt
```

2. Run the server

```bash
python run_server.py
```

3. Test it locally

```bash
python test_server.py
```

4. Inspect it with MCP Inspector

```bash
npx @modelcontextprotocol/inspector --config .\\inspector.json --server autodesk-alias-docs
```

## MCP client config example

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

## Notes

- `search_alias_docs(..., response_format="json")` and the other tools support machine-friendly JSON output.
- The server is optimized for local use during Alias plug-in development.
- The current retrieval path is stronger than the archived V3 server because it uses section-aware chunking and code-safe chunk handling.

## License

This project provides tooling around Autodesk Alias documentation. The documentation content itself remains subject to Autodesk's terms.
