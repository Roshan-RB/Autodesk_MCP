# Repository Guidelines

## Project Structure & Module Organization

This repository contains a Python MCP server for locally scraped Autodesk Alias Programmers' Interfaces documentation. Core server logic lives in `server/mcp_server.py`, with `run_server.py` as the runtime entry point. Regression checks are in `test_server.py`. The scraper lives in `scraper_tavily/tavily_scraper.py`; it reads the seed manifest at `data/docs/index.json` and writes generated documentation to `data/docs_tavily/`, which is intentionally ignored. The `.agent/skills/alias-plugin-dev/` skill is tracked. Local plug-in experiments, Autodesk source/reference dumps, and trash/archive folders should stay outside the repo; if folders such as `alias-plugin/`, `Autodesk_Original_Files/`, `experiments/`, or `old_trash_files/` appear locally, treat them as ignored non-release artifacts.

## Build, Test, and Development Commands

- `pip install -r requirements.txt`: install MCP, requests, and BM25 search dependencies.
- `python scraper_tavily/tavily_scraper.py --test`: run a small Tavily scrape before generating a full local corpus.
- `python scraper_tavily/tavily_scraper.py`: generate the local `data/docs_tavily/` dataset.
- `python run_server.py`: start the MCP server.
- `python test_server.py`: run the standalone regression suite.
- `npx @modelcontextprotocol/inspector --config .\inspector.json --server autodesk-alias-docs`: inspect the server with MCP Inspector.

## Coding Style & Naming Conventions

Use Python with 4-space indentation, type hints, and small focused functions. Follow the existing style: `snake_case` for functions and variables, uppercase constants such as `DOCS_DIR`, and explicit `Path` handling for repository-relative files. Keep tool-facing functions clear about their response formats, especially `markdown` versus `json`. No formatter is enforced in the repo, so preserve nearby style and avoid unrelated rewrites.

## Testing Guidelines

`test_server.py` is a direct script rather than a pytest suite. Add new checks as `test_*` functions and include them in `main()` so `python test_server.py` remains the canonical verification command. Tests expect a generated `data/docs_tavily/` corpus with the documented Alias pages available locally.

## Commit & Pull Request Guidelines

Recent history uses Conventional Commit-style subjects such as `feat: ...`, `docs(readme): ...`, and `refactor(server): ...`; follow that pattern with concise, imperative summaries. Pull requests should describe the behavior change, list verification commands run, note any documentation corpus assumptions, and link related issues when applicable. Include screenshots only for UI or inspector-facing changes.

## Security & Configuration Tips

Set `TAVILY_API_KEY` in the environment before scraping. Do not commit API keys, generated Autodesk documentation content, virtual environments, logs, or local experiment folders; `.gitignore` already excludes those paths.
