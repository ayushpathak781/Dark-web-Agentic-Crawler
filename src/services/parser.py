"""
Parsing service for normalized document extraction.

Parses raw HTML into ParsedDocument objects with:
- deterministic title/text extraction
- link extraction
- metadata generation
- language detection fallback
- recoverable error capture
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from html.parser import HTMLParser
from hashlib import sha256
import re
from typing import Any, Dict, List, Optional, Sequence

from src.models.schemas import DocumentMetadata, LinkReference, ParseStatus, ParsedDocument, RawPage

try:  # pragma: no cover - optional dependency
    from bs4 import BeautifulSoup
except ImportError:  # pragma: no cover
    BeautifulSoup = None

try:  # pragma: no cover - optional dependency
    from langdetect import detect as detect_language
except ImportError:  # pragma: no cover
    detect_language = None


class _FallbackHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title: str = ""
        self._title_depth = 0
        self._text_chunks: List[str] = []
        self._links: List[LinkReference] = []
        self._current_link_href: Optional[str] = None
        self._current_link_text: List[str] = []
        self._in_script = False
        self._in_style = False
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: List[tuple[str, Optional[str]]]) -> None:
        attr_map = {key.lower(): value for key, value in attrs if key}
        if tag == "script":
            self._in_script = True
        elif tag == "style":
            self._in_style = True
        elif tag == "title":
            self._in_title = True
            self._title_depth += 1
        elif tag == "a":
            self._current_link_href = (attr_map.get("href") or "").strip()
            self._current_link_text = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "script":
            self._in_script = False
        elif tag == "style":
            self._in_style = False
        elif tag == "title":
            self._in_title = False
            self._title_depth = max(0, self._title_depth - 1)
        elif tag == "a" and self._current_link_href:
            text = " ".join(part.strip() for part in self._current_link_text if part.strip())
            self._links.append(LinkReference(href=self._current_link_href, text=text))
            self._current_link_href = None
            self._current_link_text = []

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if not text or self._in_script or self._in_style:
            return
        if self._in_title:
            self.title = f"{self.title} {text}".strip()
        self._text_chunks.append(text)
        if self._current_link_href is not None:
            self._current_link_text.append(text)


@dataclass(frozen=True)
class ParsedResult:
    raw_page_id: str
    parsed_document: Optional[ParsedDocument]
    error: Optional[str]


class ParserService:
    """Deterministic parser for raw HTML pages."""

    def parse_raw_page(self, raw_page: RawPage | Dict[str, Any]) -> ParsedDocument:
        raw_model = self._coerce_raw_page(raw_page)
        return self.parse_html(
            raw_page_id=raw_model.id,
            source_url=raw_model.source_url,
            html=raw_model.body_html,
            fallback_language=self._guess_language(raw_model.body_html),
            parsed_timestamp=raw_model.crawl_timestamp,
        )

    def parse_raw_pages(self, raw_pages: Sequence[RawPage | Dict[str, Any]]) -> List[ParsedDocument]:
        documents: List[ParsedDocument] = []
        for raw_page in raw_pages:
            documents.append(self.parse_raw_page(raw_page))
        return documents

    def parse_html(
        self,
        raw_page_id: str,
        source_url: str,
        html: str,
        parsed_timestamp: Optional[datetime] = None,
        fallback_language: str = "en",
    ) -> ParsedDocument:
        parsed_timestamp = parsed_timestamp or datetime.utcnow()

        if not html:
            return self._failed_document(raw_page_id, source_url, parsed_timestamp, "Empty HTML body")

        title, text, links, metadata = self._extract_components(html)
        language = self._detect_language(text, fallback_language=fallback_language)
        stable_id = self._build_document_id(raw_page_id, source_url, title, text)

        return ParsedDocument(
            id=stable_id,
            raw_page_id=raw_page_id,
            source_url=source_url,
            parsed_timestamp=parsed_timestamp,
            title=title,
            language=language,
            text=text,
            links=links,
            metadata=metadata,
            parse_status=ParseStatus.SUCCESS,
            parse_error=None,
        )

    def _coerce_raw_page(self, raw_page: RawPage | Dict[str, Any]) -> RawPage:
        if isinstance(raw_page, RawPage):
            return raw_page
        return RawPage(**raw_page)

    def _extract_components(self, html: str) -> tuple[str, str, List[LinkReference], DocumentMetadata]:
        if BeautifulSoup is not None:
            return self._extract_with_bs4(html)
        return self._extract_with_fallback(html)

    def _extract_with_bs4(self, html: str) -> tuple[str, str, List[LinkReference], DocumentMetadata]:
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style"]):
            tag.decompose()

        title = self._clean_whitespace((soup.title.get_text(" ") if soup.title else "") or "")
        text = self._clean_whitespace(soup.get_text(" "))
        links = [
            LinkReference(
                href=(anchor.get("href") or "").strip(),
                text=self._clean_whitespace(anchor.get_text(" ")),
                context=None,
            )
            for anchor in soup.find_all("a", href=True)
        ]
        metadata = self._build_metadata(html=html, text=text)
        return self._normalize_title(title, text), text, links[:500], metadata

    def _extract_with_fallback(self, html: str) -> tuple[str, str, List[LinkReference], DocumentMetadata]:
        parser = _FallbackHTMLParser()
        parser.feed(html)
        title = self._clean_whitespace(parser.title)
        text = self._clean_whitespace(" ".join(parser._text_chunks))
        metadata = self._build_metadata(html=html, text=text)
        return self._normalize_title(title, text), text, parser._links[:500], metadata

    def _build_metadata(self, html: str, text: str) -> DocumentMetadata:
        paragraph_count = len([chunk for chunk in re.split(r"\n{2,}", text) if chunk.strip()])
        return DocumentMetadata(
            word_count=len(text.split()),
            paragraph_count=paragraph_count,
            image_count=len(re.findall(r"<img\b", html, flags=re.IGNORECASE)),
            table_count=len(re.findall(r"<table\b", html, flags=re.IGNORECASE)),
            code_block_count=len(re.findall(r"<(pre|code)\b", html, flags=re.IGNORECASE)),
        )

    def _detect_language(self, text: str, fallback_language: str = "en") -> str:
        if detect_language is not None and text.strip():
            try:
                detected = detect_language(text)
                return detected if detected in self._supported_languages() else fallback_language
            except Exception:
                pass
        return fallback_language

    def _guess_language(self, html: str) -> str:
        text = self._clean_whitespace(re.sub(r"<[^>]+>", " ", html))
        return self._detect_language(text or html)

    def _normalize_title(self, title: str, text: str) -> str:
        if title:
            return title[:500]
        first_line = text.split("\n", 1)[0].strip()
        return (first_line[:500] if first_line else "Untitled document")

    def _build_document_id(self, raw_page_id: str, source_url: str, title: str, text: str) -> str:
        digest = sha256("|".join([raw_page_id, source_url, title, text]).encode("utf-8")).hexdigest()
        return f"parsed-{digest[:24]}"

    def _failed_document(
        self,
        raw_page_id: str,
        source_url: str,
        parsed_timestamp: datetime,
        reason: str,
    ) -> ParsedDocument:
        return ParsedDocument(
            raw_page_id=raw_page_id,
            source_url=source_url,
            parsed_timestamp=parsed_timestamp,
            title="Untitled document",
            language="en",
            text="",
            links=[],
            metadata=DocumentMetadata(word_count=0, paragraph_count=0, image_count=0, table_count=0, code_block_count=0),
            parse_status=ParseStatus.FAILED,
            parse_error=reason,
        )

    def _clean_whitespace(self, value: str) -> str:
        return re.sub(r"\s+", " ", value or "").strip()

    def _supported_languages(self) -> set[str]:
        return {
            "en", "es", "fr", "de", "it", "pt", "nl", "ru", "ja", "zh",
            "ar", "pl", "tr", "ko", "th", "vi", "id", "ms", "hi", "bn",
        }