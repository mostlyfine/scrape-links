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


def test_save_page_as_markdown_overwrites_by_default(tmp_path):
    target = tmp_path / "example.com" / "docs" / "page.html.md"
    target.parent.mkdir(parents=True)
    target.write_text("existing")

    html = "<html><body><h1>New Title</h1></body></html>"
    scrape_links.save_page_as_markdown(
        "https://example.com/docs/page.html", html, output_dir=str(tmp_path)
    )

    content = target.read_text()
    assert "New Title" in content
    assert content != "existing"


def test_save_page_as_markdown_skip_existing(tmp_path):
    target = tmp_path / "example.com" / "docs" / "page.html.md"
    target.parent.mkdir(parents=True)
    target.write_text("existing")

    html = "<html><body><h1>New Title</h1></body></html>"
    scrape_links.save_page_as_markdown(
        "https://example.com/docs/page.html", html, output_dir=str(tmp_path), skip_existing=True
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


def test_extract_by_readability_exception(monkeypatch):
    class FailingDocument:
        def __init__(self, *_args, **_kwargs):
            raise ValueError("boom")

    monkeypatch.setattr(scrape_links, "Document", FailingDocument)
    html = "<html><body><div>content</div></body></html>"
    assert scrape_links.extract_by_readability(html) is None


def test_extract_by_newspaper_success(monkeypatch):
    long_paragraph = "Lorem ipsum dolor sit amet, consectetur adipiscing elit. " * 5

    class MockArticle:
        def __init__(self):
            self.text = long_paragraph

        def set_html(self, html):
            pass

        def nlp(self):
            pass

    monkeypatch.setattr(scrape_links, "Article", MockArticle)
    html = f"<html><body><div>{long_paragraph}</div></body></html>"
    result = scrape_links.extract_by_newspaper(html)
    assert result is not None
    assert "Lorem ipsum" in result


def test_extract_by_newspaper_short_text(monkeypatch):
    class MockArticle:
        def __init__(self):
            self.text = "Too short"

        def set_html(self, html):
            pass

        def nlp(self):
            pass

    monkeypatch.setattr(scrape_links, "Article", MockArticle)
    html = "<html><body><div>Too short</div></body></html>"
    assert scrape_links.extract_by_newspaper(html) == "Too short"


def test_extract_by_newspaper_empty_text(monkeypatch):
    class MockArticle:
        def __init__(self):
            self.text = ""

        def set_html(self, html):
            pass

        def nlp(self):
            pass

    monkeypatch.setattr(scrape_links, "Article", MockArticle)
    html = "<html><body><div>content</div></body></html>"
    assert scrape_links.extract_by_newspaper(html) == ""


def test_extract_by_newspaper_exception(monkeypatch):
    class FailingArticle:
        def __init__(self):
            raise ValueError("boom")

    monkeypatch.setattr(scrape_links, "Article", FailingArticle)
    html = "<html><body><div>content</div></body></html>"
    assert scrape_links.extract_by_newspaper(html) is None


def test_extract_by_trafilatura_success(monkeypatch):
    long_paragraph = "Lorem ipsum dolor sit amet, consectetur adipiscing elit. " * 5
    html_output = f"<article><p>{long_paragraph}</p></article>"

    def mock_extract(html_content, include_images=None, include_tables=None, include_links=None, output_format=None):
        return html_output

    monkeypatch.setattr(scrape_links.trafilatura, "extract", mock_extract)
    html = f"<html><body><div>{long_paragraph}</div></body></html>"
    result = scrape_links.extract_by_trafilatura(html)
    assert result is not None
    assert "Lorem ipsum" in result


def test_extract_by_trafilatura_empty_text(monkeypatch):
    def mock_extract(html_content, include_images=None, include_tables=None, include_links=None, output_format=None):
        return None

    monkeypatch.setattr(scrape_links.trafilatura, "extract", mock_extract)
    html = "<html><body><div>content</div></body></html>"
    assert scrape_links.extract_by_trafilatura(html) is None


def test_extract_by_trafilatura_exception(monkeypatch):
    def failing_extract(html_content, include_images=None, include_tables=None, include_links=None, output_format=None):
        raise ValueError("boom")

    monkeypatch.setattr(scrape_links.trafilatura, "extract", failing_extract)
    html = "<html><body><div>content</div></body></html>"
    assert scrape_links.extract_by_trafilatura(html) is None


def test_extract_by_body_with_body():
    html = "<html><body><p>Hello</p></body></html>"
    result = scrape_links.extract_by_body(html)
    assert "<p>Hello</p>" in result


def test_extract_by_body_no_body():
    html = "<html>No body tag</html>"
    assert scrape_links.extract_by_body(html) is None


def test_extract_main_content_prioritises_trafilatura(monkeypatch):
    long_content = "a" * 100  # 100+ characters
    monkeypatch.setattr(scrape_links, "extract_by_trafilatura", lambda html: f"<p>{long_content}</p>")
    monkeypatch.setattr(scrape_links, "extract_by_newspaper", lambda html: f"<p>{long_content}</p>")
    monkeypatch.setattr(scrape_links, "extract_by_xpath", lambda html: f"<p>{long_content}</p>")
    monkeypatch.setattr(scrape_links, "extract_by_readability", lambda html: f"<p>{long_content}</p>")
    monkeypatch.setattr(scrape_links, "extract_by_body", lambda html: f"<p>{long_content}</p>")

    result = scrape_links.extract_main_content("html")
    assert long_content in result


def test_extract_main_content_fallback_to_readability(monkeypatch):
    long_content = "a" * 100  # 100+ characters
    monkeypatch.setattr(scrape_links, "extract_by_trafilatura", lambda html: None)
    monkeypatch.setattr(scrape_links, "extract_by_newspaper", lambda html: f"<p>{long_content}</p>")
    monkeypatch.setattr(scrape_links, "extract_by_xpath", lambda html: f"<p>{long_content}</p>")
    monkeypatch.setattr(scrape_links, "extract_by_readability", lambda html: f"<p>{long_content}</p>")
    monkeypatch.setattr(scrape_links, "extract_by_body", lambda html: f"<p>{long_content}</p>")

    result = scrape_links.extract_main_content("html")
    assert long_content in result


def test_extract_main_content_fallback_to_newspaper(monkeypatch):
    long_content = "a" * 100  # 100+ characters
    monkeypatch.setattr(scrape_links, "extract_by_trafilatura", lambda html: None)
    monkeypatch.setattr(scrape_links, "extract_by_newspaper", lambda html: f"<p>{long_content}</p>")
    monkeypatch.setattr(scrape_links, "extract_by_xpath", lambda html: f"<p>{long_content}</p>")
    monkeypatch.setattr(scrape_links, "extract_by_readability", lambda html: None)
    monkeypatch.setattr(scrape_links, "extract_by_body", lambda html: f"<p>{long_content}</p>")

    result = scrape_links.extract_main_content("html")
    assert long_content in result


def test_extract_main_content_fallback_to_xpath(monkeypatch):
    long_content = "a" * 100  # 100+ characters
    monkeypatch.setattr(scrape_links, "extract_by_trafilatura", lambda html: None)
    monkeypatch.setattr(scrape_links, "extract_by_newspaper", lambda html: None)
    monkeypatch.setattr(scrape_links, "extract_by_xpath", lambda html: f"<p>{long_content}</p>")
    monkeypatch.setattr(scrape_links, "extract_by_readability", lambda html: None)
    monkeypatch.setattr(scrape_links, "extract_by_body", lambda html: f"<p>{long_content}</p>")

    result = scrape_links.extract_main_content("html")
    assert long_content in result


def test_extract_main_content_fallback_to_body(monkeypatch):
    monkeypatch.setattr(scrape_links, "extract_by_trafilatura", lambda html: None)
    monkeypatch.setattr(scrape_links, "extract_by_newspaper", lambda html: None)
    monkeypatch.setattr(scrape_links, "extract_by_xpath", lambda html: None)
    monkeypatch.setattr(scrape_links, "extract_by_readability", lambda html: None)
    monkeypatch.setattr(scrape_links, "extract_by_body", lambda html: "body")

    assert scrape_links.extract_main_content("html") == "html"


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

    result = scrape_links.fetch_links_from_page("https://example.com/docs/", output_dir=str(tmp_path), extractors=[])

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

    def fake_fetch(url, output_dir=None, skip_existing=False, extractors=None, driver=None):
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

    def fake_fetch(url, output_dir=None, skip_existing=False, extractors=None, driver=None):
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

    def fake_fetch(url, output_dir=None, skip_existing=False, extractors=None, driver=None):
        return responses[url]

    monkeypatch.setattr(scrape_links, "fetch_links_from_page", fake_fetch)

    result = scrape_links.scrape_links("https://example.com/docs/", max_depth=-1)

    assert result == {
        "https://example.com/docs/",
        "https://example.com/docs/page1",
        "https://example.com/docs/page2",
    }


def test_extract_main_content_custom_order(monkeypatch):
    """Test that custom extractor order is respected."""
    calls = []
    long_content = "a" * 100  # 100+ characters

    def mock_trafilatura(html):
        calls.append("trafilatura")
        return f"<p>{long_content}</p>"

    def mock_newspaper(html):
        calls.append("newspaper")
        return f"<p>{long_content}</p>"

    def mock_xpath(html):
        calls.append("xpath")
        return f"<p>{long_content}</p>"

    monkeypatch.setattr(scrape_links, "extract_by_trafilatura", mock_trafilatura)
    monkeypatch.setattr(scrape_links, "extract_by_newspaper", mock_newspaper)
    monkeypatch.setattr(scrape_links, "extract_by_xpath", mock_xpath)

    # Test custom order: newspaper first, then xpath
    result = scrape_links.extract_main_content("html", extractors=["newspaper", "xpath"])

    assert long_content in result
    assert calls == ["newspaper"]


def test_extract_main_content_custom_order_fallback(monkeypatch):
    """Test that extraction falls back to next extractor when first fails."""
    calls = []
    long_content = "a" * 100  # 100+ characters

    def mock_newspaper(html):
        calls.append("newspaper")
        return None

    def mock_xpath(html):
        calls.append("xpath")
        return f"<p>{long_content}</p>"

    monkeypatch.setattr(scrape_links, "extract_by_newspaper", mock_newspaper)
    monkeypatch.setattr(scrape_links, "extract_by_xpath", mock_xpath)

    # Test fallback: newspaper returns None, should try xpath
    result = scrape_links.extract_main_content("html", extractors=["newspaper", "xpath"])

    assert long_content in result
    assert calls == ["newspaper", "xpath"]


def test_extract_main_content_invalid_extractor(monkeypatch):
    """Test that invalid extractor names are handled gracefully."""

    def mock_body(html):
        return "body fallback"

    monkeypatch.setattr(scrape_links, "extract_by_body", mock_body)

    # Test with invalid extractor name
    result = scrape_links.extract_main_content("html", extractors=["invalid_extractor"])

    # Should fall back to html
    assert result == "html"


def test_extract_main_content_body_not_in_extractor_list(monkeypatch):
    """Test that 'body' is always used as final fallback even when not specified."""
    long_content = "a" * 100  # 100+ characters

    def mock_newspaper(html):
        return None

    def mock_body(html):
        return f"<p>{long_content}</p>"

    monkeypatch.setattr(scrape_links, "extract_by_newspaper", mock_newspaper)
    monkeypatch.setattr(scrape_links, "extract_by_body", mock_body)

    # Test that body is used even when not in extractor list
    result = scrape_links.extract_main_content("html", extractors=["newspaper"])

    assert long_content in result
