"""Tests for the Phase 3 parser service."""

from __future__ import annotations

from datetime import datetime

from src.models.schemas import ParseStatus, RawPage
from src.services.parser import ParserService


def _raw_page(html: str, source_url: str = "https://test.onion/page1") -> RawPage:
    return RawPage(
        id="raw-page-fixed-id",
        source_url=source_url,
        crawl_timestamp=datetime(2026, 7, 23, 0, 0, 0),
        http_status=200,
        headers={"content-type": "text/html"},
        body_html=html,
        body_bytes_hash="abc123",
        crawl_duration_ms=42,
        user_agent="Mozilla/5.0",
        retry_count=0,
    )


def test_parse_html_extracts_title_text_links_and_metadata():
    parser = ParserService()
    html = """
    <html>
      <head><title>Sample Page</title></head>
      <body>
        <p>Hello world.</p>
        <p>Second paragraph.</p>
        <a href="https://example.com">Example</a>
        <img src="image.png" />
        <table><tr><td>Cell</td></tr></table>
        <pre>code</pre>
      </body>
    </html>
    """

    document = parser.parse_raw_page(_raw_page(html))

    assert document.title == "Sample Page"
    assert "Hello world." in document.text
    assert len(document.links) == 1
    assert document.links[0].href == "https://example.com"
    assert document.metadata.word_count > 0
    assert document.metadata.image_count == 1
    assert document.metadata.table_count == 1
    assert document.metadata.code_block_count == 1
    assert document.parse_status == ParseStatus.SUCCESS


def test_parse_html_falls_back_to_first_text_when_no_title():
    parser = ParserService()
    html = "<html><body><p>First line</p><p>Second line</p></body></html>"

    document = parser.parse_raw_page(_raw_page(html))

    assert document.title == "First line Second line"


def test_parse_empty_html_returns_failed_document():
    parser = ParserService()

    document = parser.parse_html(
        raw_page_id="raw-1",
        source_url="https://test.onion/page1",
        html="",
    )

    assert document.parse_status == ParseStatus.FAILED
    assert document.parse_error == "Empty HTML body"


def test_parse_batch_is_deterministic():
    parser = ParserService()
    pages = [_raw_page("<html><body><title>T</title><p>A</p></body></html>") for _ in range(2)]

    first = parser.parse_raw_pages(pages)
    second = parser.parse_raw_pages(pages)

    assert [doc.model_dump() for doc in first] == [doc.model_dump() for doc in second]