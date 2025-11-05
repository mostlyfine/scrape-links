#!/usr/bin/env python3
"""Script to recursively extract page links under a specified base URL.

Features:
    * Breadth-first traversal with depth limit (or unlimited when -1)
    * Optional saving of each fetched page as GitHub Flavored Markdown
    * Five-stage content extraction (trafilatura > readability > newspaper3k > CSS selector > body fallback)
    * By default, overwrites existing markdown files; use --skip-existing to skip them
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
from newspaper import Article
import trafilatura

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


def save_page_as_markdown(url: str, html_content: str, output_dir: str = "output", skip_existing: bool = False, extractors: Optional[list[str]] = None) -> None:
    """Save a web page as markdown file.

    Args:
        url: The URL of the page to save
        html_content: The HTML content of the page
        output_dir: Directory to save the markdown file (default: "output")
        skip_existing: If True, skip saving if file already exists (default: False, overwrite)
        extractors: List of extractor names to try in order (optional)
    """
    filepath = url_to_filepath(url, output_dir)

    if skip_existing and filepath.exists():
        logger.debug(f"Skip (already exists): {filepath}")
        return

    try:
        page_title = extract_page_title(html_content)
        markdown_content = html_to_markdown(html_content, url, extractors)

        filepath.parent.mkdir(parents=True, exist_ok=True)

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(f"# [{page_title}]({url})\n\n")
            f.write(markdown_content)

        action = "Skipped and saved" if skip_existing and filepath.exists() else "Saved"
        logger.debug(f"{action} file: {filepath}")
    except Exception as e:
        logger.warning(f"Failed to save markdown for {url} - {e}")


def fetch_links_from_page(url: str, output_dir: Optional[str] = None, skip_existing: bool = False, extractors: Optional[list[str]] = None) -> Set[str]:
    """Extract absolute links from a single page and optionally save as markdown.

    Args:
        url: The URL to fetch
        output_dir: Directory to save the markdown file (optional)
        skip_existing: If True, skip saving if file already exists (default: False, overwrite)
        extractors: List of extractor names to try in order (optional)

    Returns:
        Set of absolute URLs found on the page
    """

    try:
        wait_before_request()
        response = requests.get(url, timeout=10)
        response.raise_for_status()

        # Save as markdown if an output directory is provided (before parsing to reuse content)
        if output_dir is not None:
            logger.debug(f"Saving page as markdown: {url}")
            save_page_as_markdown(url, response.text,
                                  output_dir, skip_existing, extractors)

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
            '#main',
            '.main',
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


def extract_by_trafilatura(html_content: str) -> Optional[str]:
    """Extract main content using trafilatura for text extraction."""
    try:
        extracted = trafilatura.extract(
            html_content, include_images=True, include_tables=True, output_format='html')

        if extracted:
            soup = BeautifulSoup(extracted, 'html.parser')
            text_length = len(soup.get_text(strip=True))
            if text_length >= 100:
                logger.debug(
                    f"Content extraction: trafilatura (length={text_length})")
                return extracted
            else:
                logger.debug(
                    f"Content extraction: trafilatura result too short (length={text_length})")
                return None
        else:
            logger.debug("Content extraction: trafilatura returned empty text")
            return None

    except Exception as e:
        logger.debug(f"Trafilatura extraction error: {e}")
        return None


def extract_by_newspaper(html_content: str) -> Optional[str]:
    """Extract main content using newspaper3k for article parsing."""
    try:
        article = Article()
        article.set_html(html_content)
        article.nlp()

        if article.text:
            text_length = len(article.text.strip())
            if text_length >= 100:
                logger.debug(
                    f"Content extraction: newspaper3k (length={text_length})")
                # Convert plain text to simple HTML for consistency with other methods
                html_output = f"<article>{article.text}</article>"
                return html_output
            else:
                logger.debug(
                    f"Content extraction: newspaper3k result too short (length={text_length})")
                return None
        else:
            logger.debug("Content extraction: newspaper3k returned empty text")
            return None

    except Exception as e:
        logger.debug(f"Newspaper3k extraction error: {e}")
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


def extract_main_content(html_content: str, extractors: Optional[list[str]] = None) -> str:
    """High-level main content extraction pipeline with configurable extractor order.

    Args:
        html_content: The HTML content to extract from
        extractors: List of extractor names to try in order (default: trafilatura > readability > newspaper3k > xpath)
                   Valid names: 'trafilatura', 'newspaper3k', 'xpath', 'readability'
                   Note: 'body' fallback is always used as the final fallback and cannot be specified

    Returns:
        Extracted content as HTML string
    """
    if extractors is None:
        extractors = ["trafilatura", "readability", "newspaper3k", "xpath"]

    # Map extractor names to functions (excluding 'body' which is always the final fallback)
    extractor_map = {
        "trafilatura": lambda: extract_by_trafilatura(html_content),
        "newspaper3k": lambda: extract_by_newspaper(html_content),
        "xpath": lambda: extract_by_xpath(html_content),
        "readability": lambda: extract_by_readability(html_content)
    }

    # Try extractors in specified order
    for extractor_name in extractors:
        if extractor_name in extractor_map:
            result = extractor_map[extractor_name]()
            if result:
                logger.debug(
                    f"Content extracted successfully using: {extractor_name}")
                return result
        else:
            logger.warning(f"Unknown extractor name: {extractor_name}")

    # Final fallback to body (always used when all other extractors fail)
    logger.debug("All extractors failed; using body fallback")
    return extract_by_body(html_content)


def html_to_markdown(html_content: str, url: str, extractors: Optional[list[str]] = None) -> str:
    """Convert HTML to Markdown (GFM style) using extracted main content only.

    Args:
        html_content: The HTML content to convert
        url: The URL of the page
        extractors: List of extractor names to try in order (optional)

    Returns:
        Markdown formatted text
    """
    main_content_html = extract_main_content(html_content, extractors)

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


def scrape_links(base_url: str, max_depth: int = 0, output_dir: Optional[str] = None, skip_existing: bool = False, extractors: Optional[list[str]] = None) -> Set[str]:
    """Recursively scrape links under the given base URL up to max_depth (-1 = unlimited).

    Args:
        base_url: The base URL to start scraping from
        max_depth: Maximum depth to scrape (0=this page only, -1=unlimited, default: 0)
        output_dir: Directory to save markdown files (optional)
        skip_existing: If True, skip saving if file already exists (default: False, overwrite)
        extractors: List of extractor names to try in order (optional)

    Returns:
        Set of all discovered URLs
    """
    visited = set()
    all_links = set()
    queue = deque([(base_url, 0)])

    # Treat -1 as unlimited depth
    is_unlimited = (max_depth == -1)

    logger.debug(f"Scraping start: {base_url}")
    logger.debug(f"Max depth: {'unlimited' if is_unlimited else max_depth}")
    if extractors:
        logger.debug(f"Extractors: {', '.join(extractors)}")

    while queue:
        current_url, current_depth = queue.popleft()

        if current_url in visited:
            continue

        visited.add(current_url)
        all_links.add(current_url)

        print(current_url)

        links = fetch_links_from_page(
            current_url, output_dir=output_dir, skip_existing=skip_existing, extractors=extractors)

        if not is_unlimited and current_depth >= max_depth:
            continue

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
  # Only the given page (show children links without saving)
  %(prog)s https://example.com/docs/

  # Save extracted pages as markdown
  %(prog)s -o saved_docs https://example.com/docs/

  # Depth 1 (immediate children)
  %(prog)s -d 1 -o saved_docs https://example.com/docs/

  # Full options (depth, output, skip existing, extractors, verbose)
  %(prog)s -d 2 -o saved_docs -s -e trafilatura,readability -v https://example.com/docs/
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
        nargs='?',
        const='output',
        metavar='DIR',
        help='Save extracted pages as markdown under DIR (default when omitted: output)'
    )
    parser.add_argument(
        '-e', '--extractors',
        type=str,
        metavar='EXTRACTORS',
        help='Comma-separated list of extractors to try in order (e.g., "trafilatura,newspaper,xpath"). '
             'Valid values: trafilatura, newspaper (or newspaper3k), xpath, readability. '
             'Default: trafilatura,readability,newspaper3k,xpath '
             '(Note: body fallback is always used as final fallback)'
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Show verbose (DEBUG level) logs'
    )
    parser.add_argument(
        '-s', '--skip-existing',
        action='store_true',
        help='Skip saving files that already exist (default: overwrite existing files)'
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

    # Parse extractors list if provided
    extractors_list = None
    if args.extractors:
        extractors_list = [e.strip() for e in args.extractors.split(',')]
        # Normalize 'newspaper' to 'newspaper3k'
        extractors_list = ['newspaper3k' if e ==
                           'newspaper' else e for e in extractors_list]
        valid_extractors = {'trafilatura',
                            'newspaper3k', 'xpath', 'readability'}
        invalid = [e for e in extractors_list if e not in valid_extractors]
        if invalid:
            logger.error(f"Invalid extractor names: {', '.join(invalid)}")
            logger.error(
                f"Valid extractors: {', '.join(sorted(valid_extractors))}")
            logger.error(
                "Note: 'newspaper' is also accepted as an alias for 'newspaper3k'")
            logger.error(
                "Note: 'body' fallback is always used as final fallback and cannot be specified")
            sys.exit(1)

    try:
        links = scrape_links(args.url, args.depth, output_dir=args.output,
                             skip_existing=args.skip_existing, extractors=extractors_list)
    except KeyboardInterrupt:
        logger.error("Interrupted")
        sys.exit(1)

    logger.debug(f"Discovered links: {len(links)}")

    if args.output:
        logger.debug(f"Pages saved to: {args.output.rstrip('/')}/")


if __name__ == "__main__":
    main()
