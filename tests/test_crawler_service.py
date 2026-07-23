"""Tests for the Phase 2 crawler service."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from src.config.config import Config, ConfigSection
from src.models.schemas import RawPage
from src.services.crawler import CrawlerService, InMemoryRawPageStorage


@dataclass
class FakeResponse:
    status_code: int = 200
    text: str = "<html><body>ok</body></html>"
    headers: dict | None = None

    def __post_init__(self) -> None:
        if self.headers is None:
            self.headers = {"content-type": "text/html"}

    @property
    def content(self) -> bytes:
        return self.text.encode("utf-8")


def _make_config() -> Config:
    config = Config()
    config.config[ConfigSection.RATE_LIMITS]["per_source_requests_per_hour"] = 10
    return config


@pytest.fixture
def crawler() -> CrawlerService:
    service = CrawlerService(
        config=_make_config(),
        storage=InMemoryRawPageStorage(),
        http_get=lambda *args, **kwargs: FakeResponse(),
    )
    service.add_allowed_source("https://test.onion/page1")
    return service


def test_fetch_persists_raw_page_and_logs_success(crawler: CrawlerService) -> None:
    page = crawler.fetch("https://test.onion/page1")

    assert isinstance(page, RawPage)
    assert crawler.get_raw_page(page.id) is not None
    assert any(entry.get("action") == "FETCH_SUCCESS" for entry in crawler.get_audit_log())


def test_fetch_uses_tor_proxy_settings() -> None:
    config = _make_config()
    config.config[ConfigSection.TOR_PROXY]["host"] = "127.0.0.1"
    config.config[ConfigSection.TOR_PROXY]["port"] = 9050

    captured: dict[str, object] = {}

    def fake_get(url, timeout=None, headers=None, proxies=None):
        captured["url"] = url
        captured["timeout"] = timeout
        captured["headers"] = headers
        captured["proxies"] = proxies
        return FakeResponse()

    service = CrawlerService(config=config, storage=InMemoryRawPageStorage(), http_get=fake_get)
    service.add_allowed_source("https://test.onion/page1")

    service.fetch("https://test.onion/page1", timeout_seconds=15)

    assert captured["proxies"]["http"].startswith("socks5h://127.0.0.1:9050")
    assert captured["headers"]["User-Agent"].startswith("Mozilla/5.0")
    assert captured["timeout"] == 15


def test_rate_limit_enforced() -> None:
    config = _make_config()
    config.config[ConfigSection.RATE_LIMITS]["per_source_requests_per_hour"] = 1
    service = CrawlerService(config=config, storage=InMemoryRawPageStorage(), http_get=lambda *args, **kwargs: FakeResponse())
    service.add_allowed_source("https://test.onion/page1")

    service.fetch("https://test.onion/page1")

    with pytest.raises(RuntimeError, match="Rate limit exceeded"):
        service.fetch("https://test.onion/page1")


def test_timeout_validation(crawler: CrawlerService) -> None:
    with pytest.raises(ValueError, match="Timeout must be 1-300"):
        crawler.fetch("https://test.onion/page1", timeout_seconds=0)


def test_non_success_status_rejected() -> None:
    config = _make_config()
    service = CrawlerService(
        config=config,
        storage=InMemoryRawPageStorage(),
        http_get=lambda *args, **kwargs: FakeResponse(status_code=404),
    )
    service.add_allowed_source("https://test.onion/page1")

    with pytest.raises(RuntimeError, match="Non-success status"):
        service.fetch("https://test.onion/page1")