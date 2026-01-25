"""
Improved scraper for Autodesk Alias documentation.

Key findings:
- Page is an SPA that loads content via JavaScript
- Content lives inside .body_content / #body-content element
- Headless mode may trigger anti-bot detection, headed mode works
- Need to wait 5+ seconds for JavaScript to fully render
"""

import asyncio
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright


async def scrape_single_page(url: str, headless: bool = False):
    """
    Scrape a single Autodesk help page.
    
    Args:
        url: The URL to scrape
        headless: If False, opens browser window (more reliable but visible)
    """
    async with async_playwright() as p:
        # IMPORTANT: headless=False seems to avoid anti-bot detection
        browser = await p.chromium.launch(headless=headless)
        page = await browser.new_page()
        
        print(f"Navigating to: {url}")
        await page.goto(url, wait_until="networkidle")
        
        # Wait extra time for JavaScript to fully render the content
        print("Waiting for JavaScript to render content...")
        await asyncio.sleep(5)
        
        # Check if we got the real content or "Page Not Found"
        title = await page.title()
        print(f"Page title: {title}")
        
        if "Page Not Found" in title:
            print("⚠️  WARNING: Got 'Page Not Found' - try running with headless=False")
        
        # Get the HTML content of the page
        html = await page.content()
        
        await browser.close()
        
        return html


def extract_content(html: str) -> dict:
    """
    Extract structured content from Autodesk help page HTML.
    
    The key selector is .body_content which contains the main documentation.
    """
    soup = BeautifulSoup(html, "lxml")
    
    # The main content is in .body_content (discovered via debug)
    main_content = (
        soup.select_one(".body_content") or
        soup.select_one("#body-content") or
        soup.select_one(".caas_body") or
        soup.select_one("article") or
        soup.body
    )
    
    if not main_content:
        return {"error": "Could not find main content"}
    
    # Remove unnecessary elements
    for tag in main_content.select("script, style, noscript, .related-links"):
        tag.decompose()

    # Extract the page title (h1)
    h1 = main_content.select_one("h1")
    title = h1.get_text(strip=True) if h1 else ""
    
    # Extract headings (h2, h3, h4, etc.)
    headings = [h.get_text(strip=True) for h in main_content.find_all(["h2", "h3", "h4", "h5", "h6"])]
    
    # Extract paragraphs
    paragraphs = [p.get_text(strip=True) for p in main_content.find_all("p")]
    
    # Extract code blocks
    code_blocks = [code.get_text(strip=True) for code in main_content.find_all("pre")]

    # Extract the full text content (useful for search indexing)
    full_text = main_content.get_text(separator="\n", strip=True)

    # Extract tables (optional, if relevant)
    tables = []
    for table in main_content.find_all("table"):
        rows = []
        for tr in table.find_all("tr"):
            cells = [td.get_text(strip=True) for td in tr.find_all(["th", "td"])]
            rows.append(cells)
        tables.append(rows)

    return {
        "title": title,
        "headings": headings,
        "paragraphs": paragraphs,
        "code_blocks": code_blocks,
        "tables": tables,
        "full_text": full_text,
    }


if __name__ == "__main__":
    # Test URL
    url = "https://help.autodesk.com/view/ALIAS/2026/ENU/?guid=GUID-28B63BF1-7EDE-491E-9983-1F70AB0446A4"
    
    print("=" * 60)
    print("Testing Autodesk Alias Documentation Scraper")
    print("=" * 60)
    
    # Run with headed mode (headless=False) - more reliable
    html_content = asyncio.run(scrape_single_page(url, headless=False))
    
    # Extract content
    extracted = extract_content(html_content)
    
    # Print results
    print("\n" + "=" * 60)
    print("EXTRACTED CONTENT")
    print("=" * 60)
    print(f"\n📄 Title: {extracted.get('title', 'N/A')}")
    print(f"\n📋 Headings ({len(extracted.get('headings', []))}): {extracted.get('headings', [])}")
    print(f"\n📝 Paragraphs ({len(extracted.get('paragraphs', []))}):")
    for i, p in enumerate(extracted.get("paragraphs", [])[:5], 1):
        print(f"   {i}. {p[:100]}..." if len(p) > 100 else f"   {i}. {p}")
    if len(extracted.get("paragraphs", [])) > 5:
        print(f"   ... and {len(extracted.get('paragraphs', [])) - 5} more")
    
    print(f"\n💻 Code blocks: {len(extracted.get('code_blocks', []))}")
    print(f"📊 Tables: {len(extracted.get('tables', []))}")
    
    # Save to file
    import json
    with open("extracted_content.json", "w", encoding="utf-8") as f:
        json.dump(extracted, f, ensure_ascii=False, indent=4)
    
    print(f"\n✅ Content saved to extracted_content.json")
    print(f"   Full text length: {len(extracted.get('full_text', ''))} characters")
