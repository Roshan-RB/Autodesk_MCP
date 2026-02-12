"""
Tavily-based scraper for Autodesk Alias API documentation.

Uses the Tavily Extract API with advanced depth to re-scrape all pages
from the existing index, producing better-structured content with
properly delimited code blocks.

Usage:
    python scraper_tavily/tavily_scraper.py              # Scrape all pages
    python scraper_tavily/tavily_scraper.py --test        # Scrape 3 test pages
    python scraper_tavily/tavily_scraper.py --test -n 5   # Scrape 5 test pages
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

# ─── Configuration ───────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent.parent
INDEX_PATH = PROJECT_ROOT / "data" / "docs" / "index.json"
OUTPUT_DIR = PROJECT_ROOT / "data" / "docs_tavily"

TAVILY_EXTRACT_URL = "https://api.tavily.com/extract"
BATCH_SIZE = 5          # Tavily extract supports up to 5 URLs per call
DELAY_BETWEEN_BATCHES = 2  # seconds


# ─── Content Cleaning ───────────────────────────────────────────────────────

# Patterns that indicate navigation/sidebar content to strip
NAV_PATTERNS = [
    # Breadcrumb trails like "1.   Alias Programmers'..."
    r'^\d+\.\s+Alias Programmers.*$',
    r'^\d+\.\s+Adding your plug-in.*$',
    r'^\d+\.\s+[A-Z].*$',
    # Share links
    r'^Share\s*$',
    r'^\s*(Email|Facebook|Twitter|LinkedIn)\s*$',
    # Navigation sidebar items (indented with spaces, tree-like)
    r'^\s{2,}(Adding your plug-in|Building Options|Building the included|'
    r'Class reference|Compiling and linking|Implementation Details|'
    r'Introduction|Plug-in API Examples|Setting up plug-ins|'
    r'The universe and its objects|Using OpenAlias|Using the API|'
    r'Writing a plug-in|Alias Installation|Legacy Getting Started|'
    r'Alias What\'s New|What\'s New in|Alias Release Notes|'
    r'Tutorials|Interface Reference|Tool Palette Reference|'
    r'Menus Reference|File Format Reference|VRED Renderer|'
    r'Live Referencing|Alias Dynamo|Flow Production|'
    r'Form Explorer|NavPack Design|Environment Variables).*$',
    # Copyright / license notices
    r'^Except where otherwise noted.*Creative Commons.*$',
    r'^Please see the Autodesk Creative Commons.*$',
    # Page header boilerplate
    r'^Alias 2026 Help \|.*\| Autodesk\s*$',
    r'^Alias 2026 Help \|.*$',
    r'^\s*Help Home\s*$',
    r'^\s*Quick Links\s*$',
    r'^\s*Sign In\s*$',
    r'^\s*English \(US\)\s*$',
    r'^\s*简体中文\s*$',
    r'^\s*日本語\s*$',
    r'^\s*한국어\s*$',
    r'^Image \d+:.*$',
    # Sidebar section headers
    r'^\s*(Essential Skills|Essential Concepts|The Alias Workspace|'
    r'Keyboard Shortcuts|Subdivision Modeling).*$',
    r'^\s*What\'s New\s*$',
    r'^\s*Release Notes\s*$',
    # "Parent page:" lines (keep context but these are nav)
    # We keep these as they provide useful hierarchy info
]

# Compile nav patterns for performance
NAV_REGEX = [re.compile(p, re.MULTILINE) for p in NAV_PATTERNS]


def clean_content(raw_content: str, page_title: str) -> str:
    """
    Clean Tavily-extracted content by removing navigation sidebar noise
    while preserving the actual documentation content and code blocks.
    """
    if not raw_content:
        return ""

    lines = raw_content.split('\n')
    cleaned_lines = []
    in_code_block = False
    found_content_start = False

    for line in lines:
        # Track code blocks - never strip content inside them
        if line.strip().startswith('```'):
            in_code_block = not in_code_block
            if found_content_start:
                cleaned_lines.append(line)
            continue

        if in_code_block:
            if found_content_start:
                cleaned_lines.append(line)
            continue

        # Try to find the actual content start (the page title or first heading)
        if not found_content_start:
            stripped = line.strip()
            # Look for the page title as a heading or standalone text
            if stripped and (
                stripped == page_title
                or stripped == f"# {page_title}"
                or stripped == f"## {page_title}"
                or stripped == f"### {page_title}"
            ):
                found_content_start = True
                cleaned_lines.append(line)
                continue
            # Also match if we see a heading that looks like content
            if stripped.startswith('#') and not any(
                kw in stripped.lower() for kw in [
                    'help home', 'quick links', 'sign in', 'english'
                ]
            ):
                found_content_start = True
                cleaned_lines.append(line)
                continue
            # Skip everything before content starts
            continue

        # Once in content, filter out remaining nav noise
        should_skip = False
        for pattern in NAV_REGEX:
            if pattern.match(line):
                should_skip = True
                break

        if not should_skip:
            cleaned_lines.append(line)

    result = '\n'.join(cleaned_lines).strip()

    # If cleaning was too aggressive and removed everything,
    # fall back to a simpler approach
    if len(result) < 50 and len(raw_content) > 100:
        result = _simple_clean(raw_content)

    # Strip footer noise that appears at the end of every page
    result = _strip_footer(result)

    return result


def _strip_footer(content: str) -> str:
    """Remove footer boilerplate from the end of the content."""
    # Known footer markers - truncate at the first one found
    footer_markers = [
        "### Was this information helpful?",
        "Was this information helpful?",
        "Except where otherwise noted, this work is licensed",
        "[](https://creativecommons.org/",
        "Privacy Statement",
        "Legal Notices & Trademarks",
        "Report Noncompliance",
        "© 2025 Autodesk Inc.",
        "© 2024 Autodesk Inc.",
        "© 2026 Autodesk Inc.",
    ]
    for marker in footer_markers:
        idx = content.find(marker)
        if idx > 0:
            content = content[:idx].rstrip()
            break
    return content


def _simple_clean(raw_content: str) -> str:
    """
    Fallback cleaner: just remove the most obvious nav patterns.
    """
    lines = raw_content.split('\n')
    cleaned = []
    for line in lines:
        stripped = line.strip()
        # Skip obvious nav/boilerplate
        if any(kw in stripped for kw in [
            'Help Home', 'Quick Links', 'Sign In',
            'English (US)', '简体中文', '日本語', '한국어',
            'Creative Commons', 'Autodesk Creative Commons',
            'Image 2: Alias 2026',
        ]):
            continue
        if stripped in ('Share', 'Email', 'Facebook', 'Twitter', 'LinkedIn'):
            continue
        cleaned.append(line)
    return '\n'.join(cleaned).strip()


# ─── Tavily API ──────────────────────────────────────────────────────────────

def get_api_key() -> str:
    """Get Tavily API key from environment or MCP config."""
    # Check environment first
    key = os.environ.get("TAVILY_API_KEY")
    if key:
        return key

    # Try reading from MCP config
    mcp_config_paths = [
        Path.home() / ".gemini" / "antigravity" / "mcp_config.json",
    ]
    for config_path in mcp_config_paths:
        if config_path.exists():
            try:
                with open(config_path, 'r') as f:
                    config = json.load(f)
                tavily_cfg = config.get("mcpServers", {}).get("tavily", {})
                args = tavily_cfg.get("args", [])
                for arg in args:
                    if "tavilyApiKey=" in str(arg):
                        return str(arg).split("tavilyApiKey=")[1]
            except (json.JSONDecodeError, KeyError):
                pass

    print("ERROR: No Tavily API key found.")
    print("Set TAVILY_API_KEY environment variable or configure in mcp_config.json")
    sys.exit(1)


def extract_batch(urls: list[str], api_key: str) -> dict:
    """
    Call Tavily Extract API for a batch of URLs.
    Returns a dict mapping URL -> extracted content.
    """
    payload = {
        "api_key": api_key,
        "urls": urls,
        "extract_depth": "advanced",
    }

    try:
        resp = requests.post(TAVILY_EXTRACT_URL, json=payload, timeout=60)
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.RequestException as e:
        print(f"  ERROR: API request failed: {e}")
        return {}

    result = {}
    for item in data.get("results", []):
        result[item["url"]] = {
            "title": item.get("title", ""),
            "raw_content": item.get("raw_content", ""),
        }

    for item in data.get("failed_results", []):
        print(f"  WARN: Failed to extract {item.get('url')}: {item.get('error')}")

    return result


# ─── Main Scraper ────────────────────────────────────────────────────────────

def load_index() -> list[dict]:
    """Load the existing index.json with all page GUIDs."""
    with open(INDEX_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data.get("pages", [])


def save_page(page_data: dict):
    """Save a scraped page as JSON."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    filepath = OUTPUT_DIR / f"{page_data['guid']}.json"
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(page_data, f, indent=2, ensure_ascii=False)


def save_index(pages_scraped: list[dict], total_pages: int):
    """Save a new index.json for the Tavily-scraped data."""
    index = {
        "source": "tavily_extract_advanced",
        "total_pages": total_pages,
        "pages_scraped": len(pages_scraped),
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "pages": pages_scraped,
    }
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_DIR / "index.json", 'w', encoding='utf-8') as f:
        json.dump(index, f, indent=2, ensure_ascii=False)


def scrape(test_mode: bool = False, test_count: int = 3):
    """Main scraping function."""
    api_key = get_api_key()
    pages = load_index()
    total = len(pages)

    if test_mode:
        # Pick a diverse sample: one with code, one class ref, one intro
        test_guids = [
            "GUID-7EAE78D4-BAF9-40D3-AB9F-ED238F4620B3",  # Has code examples
            "GUID-47617202-4EC2-4BC1-8F72-84FAEF0BE054",  # AlSurface (large class)
            "GUID-28B63BF1-7EDE-491E-9983-1F70AB0446A4",  # Momentary/Continuous
        ]
        # Add more if requested
        if test_count > 3:
            extra = [p for p in pages if p["guid"] not in test_guids][:test_count - 3]
            test_guids.extend([p["guid"] for p in extra])

        pages = [p for p in pages if p["guid"] in test_guids]
        print(f"TEST MODE: Scraping {len(pages)} pages")
    else:
        print(f"Scraping all {total} pages...")

    # Check which pages already exist (resume support)
    existing = set()
    if OUTPUT_DIR.exists():
        for f in OUTPUT_DIR.glob("GUID-*.json"):
            existing.add(f.stem)

    pages_to_scrape = [p for p in pages if p["guid"] not in existing]
    skipped = len(pages) - len(pages_to_scrape)
    if skipped > 0:
        print(f"Skipping {skipped} already-scraped pages (resume mode)")

    if not pages_to_scrape:
        print("All pages already scraped!")
        return

    # Batch and scrape
    scraped_index = []
    total_batches = (len(pages_to_scrape) + BATCH_SIZE - 1) // BATCH_SIZE

    for batch_idx in range(0, len(pages_to_scrape), BATCH_SIZE):
        batch = pages_to_scrape[batch_idx:batch_idx + BATCH_SIZE]
        batch_num = batch_idx // BATCH_SIZE + 1
        urls = [p["url"] for p in batch]

        print(f"\n[Batch {batch_num}/{total_batches}] Extracting {len(batch)} pages...")
        for p in batch:
            print(f"  - {p['title']}")

        results = extract_batch(urls, api_key)

        for page in batch:
            url = page["url"]
            if url in results:
                extracted = results[url]
                raw = extracted.get("raw_content", "")
                cleaned = clean_content(raw, page["title"])
                has_code = "```" in raw

                page_data = {
                    "guid": page["guid"],
                    "title": page["title"],
                    "url": url,
                    "raw_content": raw,
                    "content": cleaned,
                    "has_code_blocks": has_code,
                    "scraped_at": datetime.now(timezone.utc).isoformat(),
                }
                save_page(page_data)

                scraped_index.append({
                    "guid": page["guid"],
                    "title": page["title"],
                    "url": url,
                    "has_code_blocks": has_code,
                    "content_length": len(cleaned),
                })

                status = "✓" if cleaned else "⚠ empty"
                code_tag = " [has code]" if has_code else ""
                print(f"  ✓ {page['title']} ({len(cleaned)} chars){code_tag}")
            else:
                print(f"  ✗ FAILED: {page['title']}")
                scraped_index.append({
                    "guid": page["guid"],
                    "title": page["title"],
                    "url": url,
                    "has_code_blocks": False,
                    "content_length": 0,
                    "error": "extraction_failed",
                })

        # Delay between batches (not after the last one)
        if batch_idx + BATCH_SIZE < len(pages_to_scrape):
            print(f"  Waiting {DELAY_BETWEEN_BATCHES}s before next batch...")
            time.sleep(DELAY_BETWEEN_BATCHES)

    # Also include previously scraped pages in index
    for f in OUTPUT_DIR.glob("GUID-*.json"):
        guid = f.stem
        if not any(p["guid"] == guid for p in scraped_index):
            try:
                with open(f, 'r', encoding='utf-8') as fh:
                    data = json.load(fh)
                scraped_index.append({
                    "guid": guid,
                    "title": data.get("title", ""),
                    "url": data.get("url", ""),
                    "has_code_blocks": data.get("has_code_blocks", False),
                    "content_length": len(data.get("content", "")),
                })
            except (json.JSONDecodeError, KeyError):
                pass

    save_index(scraped_index, total)

    # Summary
    success = sum(1 for p in scraped_index if p.get("content_length", 0) > 0)
    with_code = sum(1 for p in scraped_index if p.get("has_code_blocks"))
    failed = sum(1 for p in scraped_index if p.get("error"))
    print(f"\n{'='*60}")
    print(f"DONE: {success} scraped, {with_code} with code blocks, {failed} failed")
    print(f"Output: {OUTPUT_DIR}")
    print(f"Index:  {OUTPUT_DIR / 'index.json'}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Scrape Autodesk Alias API docs using Tavily Extract API"
    )
    parser.add_argument(
        "--test", action="store_true",
        help="Test mode: scrape only a few sample pages"
    )
    parser.add_argument(
        "-n", type=int, default=3,
        help="Number of pages to scrape in test mode (default: 3)"
    )
    args = parser.parse_args()
    scrape(test_mode=args.test, test_count=args.n)
