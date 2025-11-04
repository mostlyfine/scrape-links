import os
import time
from pathlib import Path

import pytest

import scrape_links


def test_wait_before_request(monkeypatch):
    expected_delay = 2.5

    monkeypatch.setattr(scrape_links.random, "uniform", lambda start, end: expected_delay)

    captured = {}

    def fake_sleep(value):
        captured["value"] = value

    monkeypatch.setattr(scrape_links.time, "sleep", fake_sleep)

    scrape_links.wait_before_request(5.0)

    assert pytest.approx(captured["value"], rel=1e-6) == expected_delay


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://example.com/path/index.html#section", "https://example.com/path/index.html"),
        ("https://example.com/path/?a=1#b", "https://example.com/path/?a=1"),
    ],
)
def test_normalize_url(url, expected):
    assert scrape_links.normalize_url(url) == expected


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://example.com/docs/", "/docs/"),
        ("https://example.com/docs/page.html", "/docs/"),
        ("https://example.com/", "/"),
        ("https://example.com/page.html", "/"),
    ],
)
def test_get_base_path(url, expected):
    assert scrape_links.get_base_path(url) == expected


@pytest.mark.parametrize(
    "base,target,expected",
    [
        ("https://example.com/docs/", "https://example.com/docs/page.html", True),
        ("https://example.com/docs/", "https://example.com/docs/section/page.html", True),
        ("https://example.com/docs/", "https://example.com/blog/page.html", False),
        ("https://example.com/docs/", "https://other.com/docs/page.html", False),
    ],
)
def test_is_child_path(base, target, expected):
    assert scrape_links.is_child_path(base, target) is expected


@pytest.mark.parametrize(
    "base,target,expected",
    [
        ("https://example.com/docs/", "https://example.com/docs/", 0),
        ("https://example.com/docs/", "https://example.com/docs/page.html", 1),
        ("https://example.com/docs/", "https://example.com/docs/section/page.html", 2),
    ],
)
def test_calculate_depth(base, target, expected):
    assert scrape_links.calculate_depth(base, target) == expected


def test_url_to_filepath_appends_md():
    result = scrape_links.url_to_filepath("https://example.com/docs/page", "out")
    assert result == Path("out") / "example.com" / "docs" / "page.md"


def test_save_page_as_markdown_creates_file(tmp_path):
    html = """
    <html>
        <body>
            <h1>Sample Title</h1>
            <p>Example paragraph.</p>
        </body>
    </html>
    """
    scrape_links.save_page_as_markdown(
        "https://example.com/docs/page.html", html, output_dir=str(tmp_path)
    )

    saved = tmp_path / "example.com" / "docs" / "page.html.md"
    assert saved.exists()
    content = saved.read_text()
    assert "Sample Title" in content
    assert "https://example.com/docs/page.html" in content


def test_save_page_as_markdown_skip_existing(tmp_path):
    target = tmp_path / "example.com" / "docs" / "page.html.md"
    target.parent.mkdir(parents=True)
    target.write_text("existing")

    html = "<html><body><h1>New Title</h1></body></html>"
    scrape_links.save_page_as_markdown(
        "https://example.com/docs/page.html", html, output_dir=str(tmp_path)
    )

    assert target.read_text() == "existing"


def test_extract_page_title_prefers_h1():
    html = "<html><body><h1>Main</h1><title>Fallback</title></body></html>"
    assert scrape_links.extract_page_title(html) == "Main"


def test_extract_page_title_fallback_title():
    html = "<html><head><title>Fallback Title</title></head><body></body></html>"
    assert scrape_links.extract_page_title(html) == "Fallback Title"


def test_extract_page_title_default():
    html = "<html><body>No title</body></html>"
    assert scrape_links.extract_page_title(html) == "Untitled"


def test_extract_by_xpath_success():
    long_text = "Lorem ipsum " * 20
    html = f"<html><body><article>{long_text}</article></body></html>"
    result = scrape_links.extract_by_xpath(html)
    assert "article" in result


def test_extract_by_xpath_none():
    html = "<html><body><p>short</p></body></html>"
    assert scrape_links.extract_by_xpath(html) is None


def test_extract_by_readability_success():
    long_paragraph = "Lorem ipsum dolor sit amet, consectetur adipiscing elit. " * 5
    html = f"<html><body><div>{long_paragraph}</div></body></html>"
    result = scrape_links.extract_by_readability(html)
    assert result is not None
    assert "Lorem ipsum" in result


def test_extract_by_readability_short():
    html = "<html><body><div>Too short</div></body></html>"
    assert scrape_links.extract_by_readability(html) is None


def test_extract_by_readability_exception(monkeypatch):
    class FailingDocument:
        def __init__(self, *_args, **_kwargs):
            raise ValueError("boom")

    monkeypatch.setattr(scrape_links, "Document", FailingDocument)
    html = "<html><body><div>content</div></body></html>"
    assert scrape_links.extract_by_readability(html) is None


def test_extract_by_body_with_body():
    html = "<html><body><p>Hello</p></body></html>"
    result = scrape_links.extract_by_body(html)
    assert "<p>Hello</p>" in result


def test_extract_by_body_no_body():
    html = "<html>No body tag</html>"
    assert scrape_links.extract_by_body(html) == html


def test_extract_main_content_prioritises_readability(monkeypatch):
    monkeypatch.setattr(scrape_links, "extract_by_readability", lambda html: "readability")
    monkeypatch.setattr(scrape_links, "extract_by_xpath", lambda html: "xpath")
    monkeypatch.setattr(scrape_links, "extract_by_body", lambda html: "body")

    assert scrape_links.extract_main_content("html") == "readability"


def test_extract_main_content_fallback(monkeypatch):
    monkeypatch.setattr(scrape_links, "extract_by_readability", lambda html: None)
    monkeypatch.setattr(scrape_links, "extract_by_xpath", lambda html: None)
    monkeypatch.setattr(scrape_links, "extract_by_body", lambda html: "body")

    assert scrape_links.extract_main_content("html") == "body"


def test_html_to_markdown_contains_content(monkeypatch):
    html = "<html><body><h1>Heading</h1><p>Paragraph</p></body></html>"
    result = scrape_links.html_to_markdown(html, "https://example.com/page")
    assert "Heading" in result
    assert "Paragraph" in result


class DummyResponse:
    def __init__(self, text, status=200):
        self.text = text
        self.content = text.encode()
        self.status = status

    def raise_for_status(self):
        if self.status >= 400:
            raise scrape_links.requests.exceptions.HTTPError("error")


def test_fetch_links_from_page_returns_links(monkeypatch, tmp_path):
    html = """
    <html>
        <body>
            <a href="/docs/page1">Page 1</a>
            <a href="https://example.com/docs/page2">Page 2</a>
        </body>
    </html>
    """

    monkeypatch.setattr(scrape_links, "wait_before_request", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(scrape_links.requests, "get", lambda url, timeout=10: DummyResponse(html))

    result = scrape_links.fetch_links_from_page("https://example.com/docs/", output_dir=str(tmp_path))

    expected_file = tmp_path / "example.com" / "docs.md"
    assert expected_file.exists()
    assert result == {
        "https://example.com/docs/page1",
        "https://example.com/docs/page2",
    }


def test_fetch_links_from_page_request_error(monkeypatch):
    class Boom(scrape_links.requests.exceptions.RequestException):
        pass

    def failing_get(*_args, **_kwargs):
        raise Boom("boom")

    monkeypatch.setattr(scrape_links, "wait_before_request", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(scrape_links.requests, "get", failing_get)

    result = scrape_links.fetch_links_from_page("https://example.com")
    assert result == set()


def test_scrape_links_depth_zero(monkeypatch):
    calls = []

    def fake_fetch(url, output_dir=None):
        calls.append((url, output_dir))
        return {"https://example.com/docs/page1"}

    monkeypatch.setattr(scrape_links, "fetch_links_from_page", fake_fetch)

    result = scrape_links.scrape_links("https://example.com/docs/", max_depth=0, output_dir="out")

    assert result == {"https://example.com/docs/"}
    assert calls == [("https://example.com/docs/", "out")]


def test_scrape_links_depth_one(monkeypatch):
    responses = {
        "https://example.com/docs/": {"https://example.com/docs/page1"},
        "https://example.com/docs/page1": set(),
    }

    def fake_fetch(url, output_dir=None):
        return responses[url]

    monkeypatch.setattr(scrape_links, "fetch_links_from_page", fake_fetch)

    result = scrape_links.scrape_links("https://example.com/docs/", max_depth=1)

    assert result == {
        "https://example.com/docs/",
        "https://example.com/docs/page1",
    }


def test_scrape_links_unlimited_depth(monkeypatch):
    responses = {
        "https://example.com/docs/": {"https://example.com/docs/page1"},
        "https://example.com/docs/page1": {"https://example.com/docs/page2"},
        "https://example.com/docs/page2": set(),
    }

    def fake_fetch(url, output_dir=None):
        return responses[url]

    monkeypatch.setattr(scrape_links, "fetch_links_from_page", fake_fetch)

    result = scrape_links.scrape_links("https://example.com/docs/", max_depth=-1)

    assert result == {
        "https://example.com/docs/",
        "https://example.com/docs/page1",
        "https://example.com/docs/page2",
    }
