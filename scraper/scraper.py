"""
Autodesk Alias Python API Documentation Scraper

This scraper uses Playwright to navigate the JavaScript-rendered Autodesk help pages
and extract documentation content for the MCP server.
"""

import asyncio
import json
import re
import os
from pathlib import Path
from datetime import datetime
from playwright.async_api import async_playwright, Page, Browser

from .config import (
    BASE_URL,
    API_SECTION_GUID,
    OUTPUT_DIR,
    PAGE_LOAD_TIMEOUT,
    NAVIGATION_DELAY,
)


class AutodeskDocsScraper:
    """Scraper for Autodesk Alias Python API documentation."""

    def __init__(self, output_dir: str = OUTPUT_DIR):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.scraped_pages: list[dict] = []
        self.visited_guids: set[str] = set()

    async def run(self, test_mode: bool = False, headless: bool = False):
        """
        Main entry point to run the scraper.
        
        Args:
            test_mode: If True, only scrape a few pages for testing.
            headless: If False (default), runs browser in headed mode.
                      Headed mode is more reliable as it avoids anti-bot detection.
        """
        print("Starting Autodesk Alias documentation scraper...")
        print(f"Running in {'headless' if headless else 'headed'} mode")
        
        async with async_playwright() as p:
            # IMPORTANT: headless=False avoids anti-bot detection on Autodesk help site
            browser = await p.chromium.launch(headless=headless)
            context = await browser.new_context()
            page = await context.new_page()
            page.set_default_timeout(PAGE_LOAD_TIMEOUT)
            
            try:
                # Navigate to the API section
                start_url = f"{BASE_URL}?guid={API_SECTION_GUID}"
                print(f"Navigating to: {start_url}")
                await page.goto(start_url)
                await page.wait_for_load_state("networkidle")
                await asyncio.sleep(5)  # Wait for JS to render (5s needed for SPA content)
                
                # Expand the API section in navigation and discover all pages
                page_links = await self._discover_api_pages(page)
                print(f"Found {len(page_links)} documentation pages under API section")
                
                if test_mode:
                    page_links = page_links[:5]  # Only scrape 5 pages in test mode
                    print(f"Test mode: limiting to {len(page_links)} pages")
                
                # Scrape each page
                for i, link in enumerate(page_links):
                    print(f"Scraping page {i+1}/{len(page_links)}: {link.get('title', 'Unknown')}")
                    await self._scrape_page(page, link)
                    await asyncio.sleep(NAVIGATION_DELAY / 1000)  # Be nice to server
                
                # Save all scraped content
                self._save_results()
                print(f"Scraping complete! Saved {len(self.scraped_pages)} pages to {self.output_dir}")
                
            finally:
                await browser.close()

    async def _discover_api_pages(self, page: Page) -> list[dict]:
        """
        Discover all documentation pages under the API section.
        The navigation uses ul.node-tree with li.node-tree-item elements.
        We need to expand ALL nested sections to find all pages.
        """
        pages = []
        
        # Wait for navigation tree to load
        try:
            await page.wait_for_selector("ul.node-tree", timeout=15000)
        except:
            print("Warning: Could not find node-tree navigation, trying alternative selectors...")
        
        await asyncio.sleep(3)  # Extra wait for dynamic content
        
        # First, find and expand the "Alias Programmers' Interfaces (API)" section
        print("Looking for API section in navigation...")
        try:
            # Find the API section by its data-id attribute
            api_section = await page.query_selector('li.node-tree-item[data-id="Alias-API_id"]')
            if not api_section:
                # Fallback: search by text content
                api_section = await page.query_selector('li.node-tree-item:has(a:text("Alias Programmers"))')
            
            if api_section:
                print("Found API section, expanding it...")
                # Check if it's already expanded
                is_expanded = await api_section.get_attribute("aria-expanded")
                if is_expanded != "true":
                    expand_btn = await api_section.query_selector('span.expand-collapse')
                    if expand_btn:
                        await expand_btn.click()
                        await asyncio.sleep(2)
                
                # Now recursively expand ALL subsections under the API section
                await self._expand_all_api_subsections(page, api_section)
            else:
                print("Warning: Could not find API section, expanding all sections...")
                await self._expand_all_sections(page)
        except Exception as e:
            print(f"Error expanding API section: {e}")
            # Fallback to expanding everything
            await self._expand_all_sections(page)
        
        # Now collect all links with GUIDs from the API section
        # Use a more specific selector to get only API-related links
        api_section = await page.query_selector('li.node-tree-item[data-id="Alias-API_id"]')
        if api_section:
            links = await api_section.query_selector_all('a[href*="guid=GUID"]')
            print(f"Found {len(links)} links with GUIDs under API section")
        else:
            # Fallback: get all GUID links
            links = await page.query_selector_all('a[href*="guid=GUID"]')
            print(f"Found {len(links)} total links with GUIDs (fallback)")
        
        for link in links:
            try:
                href = await link.get_attribute("href")
                title = await link.inner_text()
                title = title.strip() if title else ""
                
                # Skip empty titles
                if not title:
                    continue
                
                # Extract GUID from URL
                guid_match = re.search(r'guid=(GUID-[A-F0-9a-f-]+)', href or "")
                if guid_match and guid_match.group(1) not in self.visited_guids:
                    guid = guid_match.group(1)
                    self.visited_guids.add(guid)
                    
                    # Build full URL
                    if href.startswith("http"):
                        full_url = href
                    else:
                        full_url = f"{BASE_URL}?guid={guid}"
                    
                    pages.append({
                        "url": full_url,
                        "title": title,
                        "guid": guid
                    })
            except Exception as e:
                print(f"Error processing link: {e}")
                continue
        
        return pages

    async def _expand_all_api_subsections(self, page: Page, api_section, max_depth: int = 20):
        """
        Recursively expand all subsections under the API section.
        This ensures we discover ALL pages including deeply nested ones like class references.
        """
        total_expanded = 0
        
        for depth in range(max_depth):
            # Find all collapsed items WITHIN the API section
            # Items are collapsed if they have aria-expanded="false" and have an expand button
            collapsed_items = await api_section.query_selector_all(
                'li.node-tree-item[aria-expanded="false"] > span.expand-collapse'
            )
            
            if not collapsed_items:
                print(f"No more collapsed sections to expand (depth {depth})")
                break
            
            print(f"Depth {depth}: Expanding {len(collapsed_items)} collapsed sections...")
            
            for btn in collapsed_items:
                try:
                    await btn.click()
                    total_expanded += 1
                    await asyncio.sleep(0.3)  # Small delay to allow content to load
                except Exception as e:
                    pass
            
            # Wait for new content to load
            await asyncio.sleep(1)
        
        print(f"Total sections expanded: {total_expanded}")

    async def _expand_all_sections(self, page: Page, max_iterations: int = 30):
        """Expand all collapsed sections in the navigation tree (fallback method)."""
        total_expanded = 0
        
        for i in range(max_iterations):
            # Find collapsed sections using aria-expanded attribute
            collapsed = await page.query_selector_all(
                'li.node-tree-item[aria-expanded="false"] > span.expand-collapse'
            )
            if not collapsed:
                break
            
            print(f"Expanding {len(collapsed)} collapsed sections (iteration {i+1})...")
            for btn in collapsed:
                try:
                    await btn.click()
                    total_expanded += 1
                    await asyncio.sleep(0.2)  # Small delay between clicks
                except:
                    pass
            
            await asyncio.sleep(1)  # Wait for expansion animation

    async def _scrape_page(self, page: Page, link_info: dict):
        """Scrape content from a single documentation page."""
        try:
            await page.goto(link_info["url"])
            await page.wait_for_load_state("networkidle")
            await asyncio.sleep(5)  # Wait for JS rendering (5s needed for SPA content)
            
            # Extract page content
            content = await self._extract_content(page)
            
            if content and len(content) > 50:  # Only save meaningful content
                self.scraped_pages.append({
                    "guid": link_info["guid"],
                    "title": link_info["title"],
                    "url": link_info["url"],
                    "content": content,
                    "scraped_at": datetime.now().isoformat()
                })
        except Exception as e:
            print(f"Error scraping {link_info['url']}: {e}")

    async def _extract_content(self, page: Page) -> str:
        """Extract the main content from the page."""
        # The main content is inside .body_content (discovered via debugging)
        # Other selectors are fallbacks
        selectors = [
            ".body_content",      # Primary - this is where the docs actually live
            "#body-content",       # Alternative ID selector
            ".caas_body",          # Fallback
            "article",             # Fallback
            "main",                # Fallback
        ]
        
        for selector in selectors:
            try:
                element = await page.query_selector(selector)
                if element:
                    # Get text content, cleaning up whitespace
                    text = await element.inner_text()
                    if text and len(text) > 100:  # Only accept meaningful content
                        # Clean up the text
                        text = re.sub(r'\n{3,}', '\n\n', text)
                        text = re.sub(r' {2,}', ' ', text)
                        return text.strip()
            except:
                continue
        
        # Fallback: try to get the main content area more broadly
        try:
            # Get everything except navigation - prioritize .body_content
            content = await page.evaluate('''() => {
                const main = document.querySelector('.body_content, #body-content, .caas_body, article, main');
                if (main) return main.innerText;
                
                // Fallback: get body but exclude nav
                const body = document.body.cloneNode(true);
                const navs = body.querySelectorAll('nav, .toc, .sidebar, .navigation, header, footer');
                navs.forEach(n => n.remove());
                return body.innerText;
            }''')
            if content:
                content = re.sub(r'\n{3,}', '\n\n', content)
                content = re.sub(r' {2,}', ' ', content)
                return content.strip()
        except:
            pass
        
        return ""

    def _save_results(self):
        """Save scraped pages to JSON files."""
        # Save individual page files
        for page_data in self.scraped_pages:
            filename = f"{page_data['guid']}.json"
            filepath = self.output_dir / filename
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(page_data, f, indent=2, ensure_ascii=False)
        
        # Save an index file with all pages
        index = {
            "total_pages": len(self.scraped_pages),
            "scraped_at": datetime.now().isoformat(),
            "pages": [
                {
                    "guid": p["guid"],
                    "title": p["title"],
                    "url": p["url"]
                }
                for p in self.scraped_pages
            ]
        }
        
        with open(self.output_dir / "index.json", 'w', encoding='utf-8') as f:
            json.dump(index, f, indent=2, ensure_ascii=False)


async def main(test_mode: bool = False, headless: bool = False):
    """Run the scraper."""
    scraper = AutodeskDocsScraper()
    await scraper.run(test_mode=test_mode, headless=headless)


if __name__ == "__main__":
    import sys
    test_mode = "--test" in sys.argv
    headless = "--headless" in sys.argv  # Add --headless flag to run without browser window
    asyncio.run(main(test_mode=test_mode, headless=headless))
