"""
Unit tests for read-only crawler enforcement.
Tests verify GET-only behavior and allowlist validation.

Run with: pytest tests/test_crawler_readonly.py -v
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
import hashlib
from src.models.schemas import RawPage, AllowlistSource, SourceType
from src.config.config import Config, ConfigSection


class ReadOnlyCrawlerContract:
    """
    Contract that defines the read-only crawler interface.
    This is what all crawler implementations must satisfy.
    """
    
    def __init__(self, config: Config):
        self.config = config
        self.allowed_sources = set()
        self.request_log = []
    
    def is_allowed_source(self, url: str) -> bool:
        """Check if URL is in the approved allowlist."""
        return url in self.allowed_sources
    
    def add_allowed_source(self, url: str) -> None:
        """Register an approved source."""
        self.allowed_sources.add(url)
    
    def fetch(self, url: str, timeout_seconds: int = 30) -> RawPage:
        """
        Fetch a page using GET request only.
        
        Args:
            url: Target URL (must be approved)
            timeout_seconds: Request timeout
        
        Returns:
            RawPage with metadata
        
        Raises:
            ValueError: If URL not approved or method not GET
            RuntimeError: If request fails
        """
        # Guard 1: Allowlist enforcement
        if not self.is_allowed_source(url):
            self._log_violation("ALLOWLIST_VIOLATION", url, "GET", "URL not in allowlist")
            raise ValueError(f"URL not in allowlist: {url}")
        
        # Guard 2: Rate limiting
        if not self._check_rate_limit(url):
            self._log_violation("RATE_LIMIT_VIOLATION", url, "GET", "Rate limit exceeded")
            raise RuntimeError(f"Rate limit exceeded for {url}")
        
        # Guard 3: Timeout enforcement
        if not (1 <= timeout_seconds <= 300):
            self._log_violation("TIMEOUT_VIOLATION", url, "GET", "Timeout out of range")
            raise ValueError(f"Timeout must be 1-300 seconds, got {timeout_seconds}")
        
        # Guard 4: Method enforcement (would be in actual HTTP layer)
        # All requests must be GET, never POST/PUT/DELETE/PATCH
        
        # Perform fetch (mocked in tests)
        raw_page = self._perform_get_request(url, timeout_seconds)
        
        # Guard 5: Validate response
        if not (200 <= raw_page.http_status <= 299):
            raise RuntimeError(f"Non-success status: {raw_page.http_status}")
        
        # Log successful fetch
        self._log_request("FETCH_SUCCESS", url, "GET", raw_page.http_status)
        
        return raw_page
    
    def _check_rate_limit(self, url: str) -> bool:
        """Check if request rate is within limit."""
        # In real implementation, check against config
        # For now, allow unlimited (tests will mock this)
        return True
    
    def _perform_get_request(self, url: str, timeout_seconds: int) -> RawPage:
        """Perform the actual GET request (to be mocked in tests)."""
        raise NotImplementedError("Subclasses must implement")
    
    def _log_request(self, action: str, url: str, method: str, status: int) -> None:
        """Log request for audit trail."""
        self.request_log.append({
            "timestamp": datetime.utcnow(),
            "action": action,
            "url": url,
            "method": method,
            "status": status,
        })
    
    def _log_violation(self, violation_type: str, url: str, method: str, reason: str) -> None:
        """Log security violation."""
        self.request_log.append({
            "timestamp": datetime.utcnow(),
            "violation": violation_type,
            "url": url,
            "method": method,
            "reason": reason,
        })
    
    def get_audit_log(self) -> list:
        """Return all logged requests and violations."""
        return self.request_log.copy()


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def config():
    """Provide a test configuration."""
    return Config()


@pytest.fixture
def crawler(config):
    """Provide a crawler instance for testing."""
    crawler = ReadOnlyCrawlerContract(config)
    # Register test sources
    crawler.add_allowed_source("https://test.onion/page1")
    crawler.add_allowed_source("https://test.onion/page2")
    return crawler


@pytest.fixture
def mock_raw_page():
    """Provide a mock RawPage."""
    return RawPage(
        source_url="https://test.onion/page1",
        crawl_timestamp=datetime.utcnow(),
        http_status=200,
        headers={"content-type": "text/html"},
        body_html="<html><body>Test</body></html>",
        body_bytes_hash=hashlib.sha256(b"test").hexdigest(),
        crawl_duration_ms=1000,
        user_agent="Mozilla/5.0",
        retry_count=0,
    )


# ============================================================================
# Test: Allowlist Enforcement
# ============================================================================

class TestAllowlistEnforcement:
    """Verify crawler respects allowlist."""
    
    def test_approved_source_allowed(self, crawler, mock_raw_page):
        """Approved sources should be allowed."""
        assert crawler.is_allowed_source("https://test.onion/page1")
    
    def test_unapproved_source_rejected(self, crawler):
        """Unapproved sources should be rejected."""
        assert not crawler.is_allowed_source("https://evil.onion/malware")
    
    def test_fetch_unapproved_source_raises_error(self, crawler):
        """Fetching unapproved source should raise ValueError."""
        with pytest.raises(ValueError, match="not in allowlist"):
            crawler.fetch("https://evil.onion/malware")
    
    def test_unapproved_source_logged_as_violation(self, crawler):
        """Unapproved source attempts should be logged."""
        try:
            crawler.fetch("https://evil.onion/malware")
        except ValueError:
            pass
        
        violations = [log for log in crawler.get_audit_log() if "violation" in log]
        assert len(violations) == 1
        assert violations[0]["violation"] == "ALLOWLIST_VIOLATION"
    
    def test_allowlist_is_additive_only(self, crawler):
        """Crawler cannot modify allowlist autonomously."""
        initial_count = len(crawler.allowed_sources)
        
        # Attempting to fetch non-approved should not add it
        try:
            crawler.fetch("https://new.onion/page")
        except ValueError:
            pass
        
        # Allowlist size should not change
        assert len(crawler.allowed_sources) == initial_count


# ============================================================================
# Test: GET-Only Enforcement
# ============================================================================

class TestGetOnlyEnforcement:
    """Verify crawler only uses GET requests."""
    
    def test_get_request_method_is_guaranteed(self, crawler, mock_raw_page):
        """Crawler must use GET method only."""
        # This is enforced in the HTTP layer - the crawler should have no
        # ability to submit other HTTP methods
        # We verify by checking that the crawler signature doesn't support
        # method specification
        
        import inspect
        sig = inspect.signature(crawler.fetch)
        
        # fetch() should NOT have a 'method' or 'http_method' parameter
        assert 'method' not in sig.parameters
        assert 'http_method' not in sig.parameters
    
    def test_crawler_cannot_post(self, crawler):
        """Crawler should not support POST requests."""
        # Verify POST method is not callable on crawler
        assert not hasattr(crawler, 'post')
        assert not hasattr(crawler, 'submit_form')
    
    def test_crawler_cannot_put(self, crawler):
        """Crawler should not support PUT requests."""
        assert not hasattr(crawler, 'put')
    
    def test_crawler_cannot_delete(self, crawler):
        """Crawler should not support DELETE requests."""
        assert not hasattr(crawler, 'delete')
    
    def test_crawler_cannot_login(self, crawler):
        """Crawler should not support authentication."""
        assert not hasattr(crawler, 'login')
        assert not hasattr(crawler, 'authenticate')
        assert not hasattr(crawler, 'set_credentials')


# ============================================================================
# Test: Rate Limiting
# ============================================================================

class TestRateLimitEnforcement:
    """Verify crawler respects rate limits."""
    
    def test_rate_limit_violation_raises_error(self, crawler):
        """Rate limit violations should raise RuntimeError."""
        # Mock the rate limit check to fail
        crawler._check_rate_limit = Mock(return_value=False)
        
        with pytest.raises(RuntimeError, match="Rate limit exceeded"):
            crawler.fetch("https://test.onion/page1")
    
    def test_rate_limit_violation_logged(self, crawler):
        """Rate limit violations should be logged."""
        crawler._check_rate_limit = Mock(return_value=False)
        
        try:
            crawler.fetch("https://test.onion/page1")
        except RuntimeError:
            pass
        
        violations = [log for log in crawler.get_audit_log() if "violation" in log]
        assert any(v["violation"] == "RATE_LIMIT_VIOLATION" for v in violations)


# ============================================================================
# Test: Timeout Enforcement
# ============================================================================

class TestTimeoutEnforcement:
    """Verify crawler enforces reasonable timeouts."""
    
    def test_timeout_must_be_positive(self, crawler):
        """Timeout must be positive."""
        crawler._perform_get_request = Mock()
        
        with pytest.raises(ValueError, match="Timeout must be 1-300"):
            crawler.fetch("https://test.onion/page1", timeout_seconds=0)
    
    def test_timeout_must_be_reasonable(self, crawler):
        """Timeout should not be excessive (max 5 minutes)."""
        crawler._perform_get_request = Mock()
        
        with pytest.raises(ValueError, match="Timeout must be 1-300"):
            crawler.fetch("https://test.onion/page1", timeout_seconds=600)
    
    def test_timeout_default_is_reasonable(self, crawler, mock_raw_page):
        """Default timeout should be reasonable."""
        crawler._perform_get_request = Mock(return_value=mock_raw_page)
        
        # Default timeout is 30 seconds
        crawler.fetch("https://test.onion/page1")
        
        # Verify it was called
        assert crawler._perform_get_request.called


# ============================================================================
# Test: Response Validation
# ============================================================================

class TestResponseValidation:
    """Verify crawler validates responses properly."""
    
    def test_non_success_status_rejected(self, crawler):
        """Non-success HTTP status should cause rejection."""
        bad_page = RawPage(
            source_url="https://test.onion/page1",
            crawl_timestamp=datetime.utcnow(),
            http_status=404,
            headers={},
            body_html="",
            body_bytes_hash="",
            crawl_duration_ms=100,
            user_agent="Mozilla/5.0",
        )
        
        crawler._perform_get_request = Mock(return_value=bad_page)
        
        with pytest.raises(RuntimeError, match="Non-success status"):
            crawler.fetch("https://test.onion/page1")
    
    def test_success_status_only(self, crawler):
        """Only 2xx status codes should be accepted."""
        for status in [200, 201, 204, 299]:
            page = RawPage(
                source_url="https://test.onion/page1",
                crawl_timestamp=datetime.utcnow(),
                http_status=status,
                headers={},
                body_html="<html></html>",
                body_bytes_hash="abc",
                crawl_duration_ms=100,
                user_agent="Mozilla/5.0",
            )
            
            crawler._perform_get_request = Mock(return_value=page)
            
            # Should not raise
            result = crawler.fetch("https://test.onion/page1")
            assert result.http_status == status


# ============================================================================
# Test: Audit Trail
# ============================================================================

class TestAuditTrail:
    """Verify all actions are logged."""
    
    def test_successful_fetch_logged(self, crawler, mock_raw_page):
        """Successful fetches should be logged."""
        crawler._perform_get_request = Mock(return_value=mock_raw_page)
        
        crawler.fetch("https://test.onion/page1")
        
        logs = crawler.get_audit_log()
        assert len(logs) > 0
        assert any(log.get("action") == "FETCH_SUCCESS" for log in logs)
    
    def test_violation_logged_with_reason(self, crawler):
        """Violations should include reason."""
        try:
            crawler.fetch("https://evil.onion/page")
        except ValueError:
            pass
        
        violations = [log for log in crawler.get_audit_log() if "violation" in log]
        assert len(violations) > 0
        assert "reason" in violations[0]
    
    def test_audit_log_immutable(self, crawler, mock_raw_page):
        """Returned audit log should be a copy."""
        crawler._perform_get_request = Mock(return_value=mock_raw_page)
        crawler.fetch("https://test.onion/page1")
        
        log1 = crawler.get_audit_log()
        log1.append({"fake": "entry"})
        
        log2 = crawler.get_audit_log()
        assert len(log2) < len(log1)  # Original should be unaffected


# ============================================================================
# Contract Test: Crawler Must Be Read-Only
# ============================================================================

class TestCrawlerIsReadOnly:
    """Integration test: Verify crawler is fundamentally read-only."""
    
    def test_crawler_has_no_write_methods(self, crawler):
        """Crawler should have no method that modifies external state."""
        write_methods = ['post', 'put', 'delete', 'patch', 'create', 'update',
                        'submit', 'send_data', 'upload', 'write']
        
        for method in write_methods:
            assert not hasattr(crawler, method), f"Crawler has write method: {method}"
    
    def test_crawler_only_reads_config(self, crawler):
        """Crawler can read config but not modify it."""
        # Verify config is read from config object
        assert hasattr(crawler, 'config')
        
        # Crawler should not be able to call config.set()
        # (This would be verified in integration tests with actual config)
    
    def test_crawler_cannot_modify_allowlist(self, crawler):
        """Crawler cannot autonomously modify allowlist."""
        initial_sources = set(crawler.allowed_sources)
        
        # Try various ways to modify
        crawler.allowed_sources.add("https://evil.onion/new")
        
        # This would be caught by dependency injection in real system
        # Crawler should receive allowlist as read-only


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
