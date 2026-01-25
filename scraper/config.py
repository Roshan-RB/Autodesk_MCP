"""
Configuration for Autodesk Alias documentation scraper.
"""

# Base URL for Autodesk Alias 2026 documentation
BASE_URL = "https://help.autodesk.com/view/ALIAS/2026/ENU/"

# Starting point - Alias Programmers' Interfaces (API) section
# This GUID points to the main API documentation section
API_SECTION_GUID = "GUID-0278C25C-730E-49AE-9125-EBCCA7434FF5"

# Sections to scrape (from the navigation sidebar)
# These are the main sections under "Alias Programmers' Interfaces (API)"
TARGET_SECTIONS = [
    "Adding your plug-in to the UI",
    "Building Options Boxes",
    "Building the included examples",
    "Class reference",  # Main Python API classes
    "Compiling and linking",
    "Implementation Details",
    "Introduction",
    "Plug-in API Examples",
    "Setting up plug-ins",
    "The universe and its objects",
    "Using OpenAlias",
    "Using the API",
    "Writing a plug-in",
]

# CSS Selectors for content extraction
SELECTORS = {
    # Navigation sidebar
    "nav_tree": ".toc-tree, .navigation-tree, [class*='nav'], [class*='toc']",
    "nav_item": "a[href*='guid=GUID']",
    
    # Main content area
    "content": ".help-content, .content-area, article, main, [class*='content']",
    "title": "h1, .page-title, [class*='title']",
    
    # Expandable sections
    "expand_button": "[class*='expand'], [class*='toggle'], .tree-toggle",
}

# Output configuration
OUTPUT_DIR = "data/docs"
OUTPUT_FORMAT = "json"  # json or markdown

# Scraping settings
PAGE_LOAD_TIMEOUT = 30000  # milliseconds
NAVIGATION_DELAY = 1000  # milliseconds between page loads (be nice to server)
