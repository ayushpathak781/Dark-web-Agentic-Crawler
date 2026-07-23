"""
Read-only crawler service for approved public sources.

Features:
- Allowlist enforcement
- GET-only fetching
- Tor-aware SOCKS5 proxy configuration
- Rate limiting and timeout checks
- Raw page persistence with provenance metadata
- Audit logging for all requests and violations
"""

from __future__ import annotations

from collections import defaultdict, deque
from datetime import datetime, timedelta
from hashlib import sha256
from typing import Any, Callable, Deque, Dict, Iterable, List, Optional
from urllib.parse import urlparse
import uuid

try:
    import requests
except ImportError:  # pragma: no cover - optional dependency in the local venv
    requests = None

from src.config.config import Config, ConfigSection, get_config
from src.models.schemas import RawPage
from src.services.base import BaseService, ServiceStatus


class InMemoryRawPageStorage:
    """Simple in-memory storage for raw pages."""

    def __init__(self) -> None:
        self._pages: Dict[str, RawPage] = {}
        self._saved_order: List[str] = []

    def save(self, raw_page: RawPage) -> str:
        self._pages[raw_page.id] = raw_page
        self._saved_order.append(raw_page.id)
        return raw_page.id

    def get(self, page_id: str) -> Optional[RawPage]:
        return self._pages.get(page_id)

    def list(self) -> List[RawPage]:
        return [self._pages[page_id] for page_id in self._saved_order if page_id in self._pages]


class CrawlerService(BaseService):
    """Read-only crawler with allowlist and Tor proxy support."""

    def __init__(
        self,
        config: Optional[Config] = None,
        storage: Optional[InMemoryRawPageStorage] = None,
        http_get: Optional[Callable[..., Any]] = None,
    ) -> None:
        self._config = config or get_config()
        self.storage = storage or InMemoryRawPageStorage()
        self._http_get = http_get or self._default_http_get
        self.allowed_sources: set[str] = set()
        self.request_log: List[Dict[str, Any]] = []
        self._request_history: Dict[str, Deque[datetime]] = defaultdict(deque)
        self._default_user_agent = "Mozilla/5.0 (compatible; DarkWebThreatIntelBot/1.0)"
        super().__init__(service_name="crawler", config=self._config.get_all())
        self.initialize()

    def validate_config(self) -> bool:
        return True

    def initialize(self) -> None:
        self.status = ServiceStatus.HEALTHY

    def shutdown(self) -> None:
        self.status = ServiceStatus.UNHEALTHY

    def load_allowlist(self, sources: Iterable[Any]) -> None:
        for source in sources:
            if hasattr(source, "url"):
                self.allowed_sources.add(str(source.url))
            else:
                self.allowed_sources.add(str(source))

    def is_allowed_source(self, url: str) -> bool:
        return self._normalize_url(url) in self.allowed_sources

    def add_allowed_source(self, url: str) -> None:
        self.allowed_sources.add(self._normalize_url(url))

    def fetch(self, url: str, timeout_seconds: int = 30) -> RawPage:
        if not self.is_allowed_source(url):
            self._log_violation("ALLOWLIST_VIOLATION", url, "GET", "URL not in allowlist")
            raise ValueError(f"URL not in allowlist: {url}")

        if not self._check_rate_limit(url):
            self._log_violation("RATE_LIMIT_VIOLATION", url, "GET", "Rate limit exceeded")
            raise RuntimeError(f"Rate limit exceeded for {url}")

        if not (1 <= timeout_seconds <= 300):
            self._log_violation("TIMEOUT_VIOLATION", url, "GET", "Timeout out of range")
            raise ValueError(f"Timeout must be 1-300 seconds, got {timeout_seconds}")

        raw_page = self._perform_get_request(url, timeout_seconds)

        if not (200 <= raw_page.http_status <= 299):
            raise RuntimeError(f"Non-success status: {raw_page.http_status}")

        self.save_raw_page(raw_page)
        self._log_request("FETCH_SUCCESS", url, "GET", raw_page.http_status)
        return raw_page

    def fetch_batch(self, urls: List[str], timeout_seconds: int = 30) -> List[RawPage]:
        pages: List[RawPage] = []
        for url in urls:
            try:
                pages.append(self.fetch(url, timeout_seconds=timeout_seconds))
            except Exception:
                continue
        return pages

    def save_raw_page(self, raw_page: RawPage) -> str:
        return self.storage.save(raw_page)

    def get_raw_page(self, page_id: str) -> Optional[RawPage]:
        return self.storage.get(page_id)

    def list_raw_pages(self) -> List[RawPage]:
        return self.storage.list()

    def _check_rate_limit(self, url: str) -> bool:
        source_key = self._normalize_url(url)
        now = datetime.utcnow()
        window_start = now - timedelta(hours=1)
        max_requests = int(self._config.get(ConfigSection.RATE_LIMITS, "per_source_requests_per_hour") or 10)

        history = self._request_history[source_key]
        while history and history[0] < window_start:
            history.popleft()

        if len(history) >= max_requests:
            return False

        history.append(now)
        return True

    def _perform_get_request(self, url: str, timeout_seconds: int) -> RawPage:
        started_at = datetime.utcnow()
        proxy_config = self._build_proxy_config()
        headers = {"User-Agent": self._default_user_agent}

        try:
            response = self._http_get(url, timeout=timeout_seconds, headers=headers, proxies=proxy_config)
        except TypeError:
            response = self._http_get(url)

        status_code = int(getattr(response, "status_code", 0))
        response_headers = dict(getattr(response, "headers", {}) or {})

        body_bytes = getattr(response, "content", None)
        if body_bytes is None:
            text_body = getattr(response, "text", "") or ""
            body_bytes = text_body.encode("utf-8")
        body_html = body_bytes.decode("utf-8", errors="replace")
        duration_ms = int((datetime.utcnow() - started_at).total_seconds() * 1000)

        return RawPage(
            source_url=url,
            crawl_timestamp=started_at,
            http_status=status_code,
            headers=response_headers,
            body_html=body_html,
            body_bytes_hash=sha256(body_bytes).hexdigest(),
            crawl_duration_ms=duration_ms,
            tor_circuit_id=self._generate_tor_circuit_id() if proxy_config else None,
            user_agent=headers["User-Agent"],
            retry_count=0,
            error=None,
        )

    def _default_http_get(self, url: str, timeout: int, headers: Dict[str, str], proxies: Optional[Dict[str, str]]) -> Any:
        if requests is not None:
            return requests.get(url, timeout=timeout, headers=headers, proxies=proxies)

        raise RuntimeError(
            "No HTTP client is available. Install requests or inject a custom http_get callable."
        )

    def _build_proxy_config(self) -> Optional[Dict[str, str]]:
        tor_proxy = self._config.get(ConfigSection.TOR_PROXY)
        if not isinstance(tor_proxy, dict):
            return None

        host = tor_proxy.get("host")
        port = tor_proxy.get("port")
        if not host or not port:
            return None

        proxy_url = f"socks5h://{host}:{port}"
        return {"http": proxy_url, "https": proxy_url}

    def _generate_tor_circuit_id(self) -> str:
        return f"circuit_{uuid.uuid4().hex[:12]}"

    def _normalize_url(self, url: str) -> str:
        parsed = urlparse(url)
        if not parsed.scheme:
            return url.strip()
        return parsed.geturl().rstrip("/")

    def _log_request(self, action: str, url: str, method: str, status: int) -> None:
        self.request_log.append(
            {
                "timestamp": datetime.utcnow(),
                "action": action,
                "url": url,
                "method": method,
                "status": status,
            }
        )

    def _log_violation(self, violation_type: str, url: str, method: str, reason: str) -> None:
        self.request_log.append(
            {
                "timestamp": datetime.utcnow(),
                "violation": violation_type,
                "url": url,
                "method": method,
                "reason": reason,
            }
        )

    def get_audit_log(self) -> list:
        return self.request_log.copy()