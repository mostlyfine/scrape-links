#!/usr/bin/env python3
"""Script to recursively extract page links under a specified base URL.

Features:
    * Breadth-first traversal with depth limit (or unlimited when -1)
    * Optional saving of each fetched page as GitHub Flavored Markdown
    * Three–stage content extraction (CSS selector > readability > body fallback)
    * Skips already existing markdown files for incremental runs
"""

import argparse
import logging
import sys
import time
import random
from collections import deque
from pathlib import Path
from urllib.parse import urljoin, urlparse
from typing import Optional, Set

import requests
from bs4 import BeautifulSoup
import html2text
from readability import Document

logger = logging.getLogger(__name__)


def wait_before_request(max_delay: float = 3.0) -> None:
    """Wait for a random duration (1 to max_delay seconds) before making a request."""
    delay = random.uniform(1.0, max_delay)
    logger.debug(f"Waiting {delay:.2f} seconds before request...")
    time.sleep(delay)


def normalize_url(url: str) -> str:
    """Normalize a URL (removes fragment part)."""
    parsed = urlparse(url)
    clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    if parsed.query:
        clean_url += f"?{parsed.query}"
    return clean_url


def get_base_path(url: str) -> str:
    """Return the base path of a URL (for a page URL return its parent directory)."""
    parsed = urlparse(url)
    path = parsed.path

    if path.endswith('/'):
        return path

    path_parts = path.rstrip('/').split('/')
    if len(path_parts) > 1:
        path = '/'.join(path_parts[:-1]) + '/'
    else:
        path = '/'

    return path


def is_child_path(base_url: str, target_url: str) -> bool:
    """Check whether target_url is under the path scope of base_url (same domain + path prefix)."""
    base_parsed = urlparse(base_url)
    target_parsed = urlparse(target_url)

    if base_parsed.netloc != target_parsed.netloc:
        return False

    base_path = get_base_path(base_url)
    target_path = target_parsed.path

    return target_path.startswith(base_path)


def calculate_depth(base_url: str, target_url: str) -> int:
    """Calculate depth from base_url to target_url based on relative path segment count."""
    base_path = get_base_path(base_url)
    target_parsed = urlparse(target_url)
    target_path = target_parsed.path

    relative_path = target_path[len(base_path):]

    if not relative_path or relative_path == '/':
        return 0

    relative_path = relative_path.rstrip('/')
    return relative_path.count('/') + 1 if relative_path else 0


def save_page_as_markdown(url: str, html_content: str, output_dir: str = "output") -> None:
    """Save a web page as markdown file."""
    filepath = url_to_filepath(url, output_dir)
    if not filepath.exists():
        try:
            page_title = extract_page_title(html_content)
            markdown_content = html_to_markdown(html_content, url)

            filepath.parent.mkdir(parents=True, exist_ok=True)

            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(f"# [{page_title}]({url})\n\n")
                f.write(markdown_content)

            logger.debug(f"Saved file: {filepath}")
        except Exception as e:
            logger.warning(f"Failed to save markdown for {url} - {e}")
    else:
        logger.debug(f"Skip (already exists): {filepath}")


def fetch_links_from_page(url: str, save_markdown: bool = False, output_dir: str = "output") -> Set[str]:
    """Extract absolute links from a single page. Optionally save as markdown. Returns a set of normalized URLs."""

    try:
        wait_before_request()
        response = requests.get(url, timeout=10)
        response.raise_for_status()

        # Save as markdown if requested (before parsing, to use the same fetched content)
        if save_markdown:
            logger.debug(f"Saving page as markdown: {url}")
            save_page_as_markdown(url, response.text, output_dir)

        # Extract links from the same response
        soup = BeautifulSoup(response.content, 'html.parser')

        links = set()
        for anchor in soup.find_all('a', href=True):
            href = anchor['href']
            absolute_url = urljoin(url, href)
            normalized = normalize_url(absolute_url)
            links.add(normalized)

        return links

    except requests.exceptions.RequestException as e:
        logger.warning(f"Failed to fetch page: {url} - {e}")
        return set()
    except Exception as e:
        logger.warning(f"Unexpected error while processing {url} - {e}")
        return set()


def url_to_filepath(url: str, output_dir: str = "output") -> Path:
    """Convert URL to local markdown file path (organized by domain)."""
    parsed = urlparse(url)
    domain = parsed.netloc
    path = parsed.path.strip('/')

    if not path:
        path = 'index'

    if not path.endswith('.md'):
        path += '.md'

    return Path(output_dir) / domain / path


def extract_page_title(html_content: str) -> str:
    """Extract a page title from HTML content, preferring <h1> then <title>."""
    soup = BeautifulSoup(html_content, 'html.parser')

    # Try candidates in priority order
    title = None

    # Prefer first <h1>
    h1 = soup.find('h1')
    if h1:
        title = h1.get_text(strip=True)
        logger.debug(f"Title extracted via <h1>: {title}")
        return title

    # Fallback to <title>
    title_tag = soup.find('title')
    if title_tag:
        title = title_tag.get_text(strip=True)
        logger.debug(f"Title extracted via <title>: {title}")
        return title

    logger.warning("Page title not found; using 'Untitled'")
    return "Untitled"


def extract_by_xpath(html_content: str) -> Optional[str]:
    """Extract main content using common CSS selectors (simulating XPath intent)."""
    try:
        soup = BeautifulSoup(html_content, 'html.parser')

        # Common main-content selectors in priority order
        selectors = [
            'main',
            'article',
            '[role="main"]',
            '#content',
            '.content',
            '#contents',
            '.contents',
            '#main-content',
            '.main-content',
            '#mainContent',
            '.mainContent',
            '.post-content',
            '.article-content',
        ]

        for selector in selectors:
            element = soup.select_one(selector)
            if element:
                text_length = len(element.get_text(strip=True))
                if text_length >= 100:
                    logger.debug(
                        f"Content extraction: selector '{selector}' (length={text_length})")
                    return str(element)

        logger.debug("Content extraction: no suitable selector element found")
        return None

    except Exception as e:
        logger.debug(f"Selector-based extraction error: {e}")
        return None


def extract_by_readability(html_content: str) -> Optional[str]:
    """Extract main content using readability-lxml for heuristic-based extraction."""
    readability_logger = logging.getLogger('readability.readability')
    original_level = readability_logger.level
    readability_logger.setLevel(logging.WARNING)

    try:
        doc = Document(html_content)
        main_content = doc.summary()

        soup = BeautifulSoup(main_content, 'html.parser')
        text_length = len(soup.get_text(strip=True))

        if text_length >= 100:
            logger.debug(
                f"Content extraction: readability (length={text_length})")
            return main_content
        else:
            logger.debug(
                f"Content extraction: readability result too short (length={text_length})")
            return None

    except Exception as e:
        logger.debug(f"Readability extraction error: {e}")
        return None

    finally:
        readability_logger.setLevel(original_level)


def extract_by_body(html_content: str) -> str:
    """Return <body> element HTML as final fallback when other methods fail."""
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        body = soup.find('body')
        if body:
            logger.debug("Content extraction: body fallback")
            return str(body)
        else:
            logger.warning("Body element not found; using full HTML")
            return html_content
    except Exception as e:
        logger.warning(f"Body extraction error: {e}; using full HTML")
        return html_content


def extract_main_content(html_content: str) -> str:
    """High-level main content extraction pipeline (selector > readability > body fallback)."""
    # 1. Selector-based attempt
    result = extract_by_xpath(html_content)
    if result:
        return result
    # 2. Readability heuristic
    result = extract_by_readability(html_content)
    if result:
        return result
    # 3. Body fallback
    return extract_by_body(html_content)


def html_to_markdown(html_content: str, url: str) -> str:
    """Convert HTML to Markdown (GFM style) using extracted main content only."""
    main_content_html = extract_main_content(html_content)

    h = html2text.HTML2Text()
    h.ignore_links = False      # Preserve links
    h.ignore_images = False     # Preserve images
    h.body_width = 0            # No forced wrapping
    h.baseurl = url             # Base URL for relative references

    # GFM-style tweaks
    h.wrap_links = False        # Do not wrap links
    h.wrap_list_items = False   # Do not wrap list items
    h.unicode_snob = True       # Prefer Unicode
    h.escape_snob = True        # Minimize unnecessary escapes

    markdown = h.handle(main_content_html)
    return markdown


def scrape_links(base_url: str, max_depth: int = 0, save_markdown: bool = False, output_dir: str = "output") -> Set[str]:
    """Recursively scrape links under the given base URL up to max_depth (-1 = unlimited)."""
    visited = set()
    all_links = set()
    queue = deque([(base_url, 0)])

    # Treat -1 as unlimited depth
    is_unlimited = (max_depth == -1)

    logger.debug(f"Scraping start: {base_url}")
    logger.debug(f"Max depth: {'unlimited' if is_unlimited else max_depth}")

    while queue:
        current_url, current_depth = queue.popleft()

        if current_url in visited:
            continue

        visited.add(current_url)
        all_links.add(current_url)

        logger.debug(f"Fetching (depth {current_depth}): {current_url}")

        if not is_unlimited and current_depth >= max_depth:
            continue

        links = fetch_links_from_page(
            current_url, save_markdown=save_markdown, output_dir=output_dir)

        for link in links:
            if link not in visited and is_child_path(base_url, link):
                depth = calculate_depth(base_url, link)
                if is_unlimited or depth <= max_depth:
                    queue.append((link, depth))

    return all_links


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description='Recursively collect page links under the specified base URL.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # Only the given page (default depth 0)
  %(prog)s https://example.com/docs/

  # Depth 1 (immediate children)
  %(prog)s -d 1 https://example.com/docs/

  # Unlimited (all descendants)
  %(prog)s -d -1 https://example.com/docs/

  # Save extracted pages as markdown
  %(prog)s -d 1 -o https://example.com/docs/

  # Verbose logging + save
  %(prog)s -d -1 -o -v https://example.com/docs/
        '''
    )
    parser.add_argument('url', help='Base URL to scrape')
    parser.add_argument(
        '-d', '--depth',
        type=int,
        default=0,
        metavar='N',
        help='Maximum depth (default: 0=this page only, -1=unlimited)'
    )
    parser.add_argument(
        '-o', '--output',
        action='store_true',
        help='Save extracted pages as markdown under output/'
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Show verbose (DEBUG level) logs'
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format='%(levelname)s: %(message)s'
    )

    parsed = urlparse(args.url)
    if not parsed.scheme or not parsed.netloc:
        logger.error(
            "Please provide a valid URL (e.g., https://example.com/docs/)")
        sys.exit(1)

    if args.depth < -1:
        logger.error("Depth must be -1 (unlimited) or an integer >= 0")
        sys.exit(1)

    try:
        links = scrape_links(args.url, args.depth,
                             save_markdown=args.output, output_dir="output")
    except KeyboardInterrupt:
        logger.error("Interrupted")
        sys.exit(1)

    logger.info(f"Discovered links: {len(links)}")

    for link in sorted(links):
        print(link)

    if args.output:
        logger.info("Pages saved to: output/")


if __name__ == "__main__":
    main()
