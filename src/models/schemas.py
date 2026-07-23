"""
Pydantic models for data schemas.
Validates and serializes all entities throughout the pipeline.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, validator
import uuid


# ============================================================================
# Enums for validated choices
# ============================================================================

class EntityType(str, Enum):
    """Supported entity types."""
    ORGANIZATION = "organization"
    MALWARE_FAMILY = "malware_family"
    RANSOMWARE_GROUP = "ransomware_group"
    CVE_ID = "cve_id"
    CRYPTO_ADDRESS = "crypto_address"
    EMAIL = "email"
    USERNAME = "username"
    DATE = "date"
    SOFTWARE = "software"


class SourceType(str, Enum):
    """Approved source content types."""
    FORUM = "forum"
    MARKETPLACE = "marketplace"
    NEWS = "news"
    RESEARCH = "research"
    TRACKER = "tracker"


class ParseStatus(str, Enum):
    """Document parsing status."""
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"


class ExtractionMethod(str, Enum):
    """Entity extraction method."""
    SPACY_NER = "spacy_ner"
    LLM_EXTRACTION = "llm_extraction"
    REGEX_PATTERN = "regex_pattern"


class ClassificationLabel(str, Enum):
    """Primary content classification."""
    MALWARE = "malware"
    LEAK = "leak"
    FORUM = "forum"
    RESEARCH = "research"
    NEWS = "news"
    MARKETPLACE = "marketplace"


class ThreatLevel(str, Enum):
    """Threat severity level."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFORMATIONAL = "informational"


class ApprovalStatus(str, Enum):
    """Approval workflow status."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    AUTO_APPROVED = "auto_approved"


class ActionType(str, Enum):
    """Audit log action types."""
    CRAWL_START = "crawl_start"
    CRAWL_COMPLETE = "crawl_complete"
    ENTITY_EXTRACT = "entity_extract"
    CLASSIFICATION = "classification"
    DATA_EXPORT = "data_export"
    CONFIG_CHANGE = "config_change"
    APPROVAL = "approval"
    REJECTION = "rejection"


# ============================================================================
# Raw Page Schema
# ============================================================================

class RawPage(BaseModel):
    """Unmodified crawled content with provenance."""
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_url: str
    crawl_timestamp: datetime
    http_status: int = Field(ge=100, le=599)
    headers: Dict[str, str]
    body_html: str = Field(max_length=52_428_800)  # 50MB
    body_bytes_hash: str
    crawl_duration_ms: int = Field(ge=0)
    tor_circuit_id: Optional[str] = None
    user_agent: str
    retry_count: int = Field(default=0, ge=0)
    error: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "uuid",
                "source_url": "https://example.onion/page",
                "crawl_timestamp": "2026-07-09T10:30:00Z",
                "http_status": 200,
            }
        }


# ============================================================================
# Parsed Document Schema
# ============================================================================

class LinkReference(BaseModel):
    """A link extracted from document."""
    href: str
    text: str
    context: Optional[str] = None


class DocumentMetadata(BaseModel):
    """Metadata about parsed document."""
    word_count: int = Field(ge=0)
    paragraph_count: int = Field(ge=0)
    image_count: int = Field(ge=0)
    table_count: int = Field(ge=0)
    code_block_count: int = Field(ge=0)


class ParsedDocument(BaseModel):
    """Normalized, extracted content from raw pages."""
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    raw_page_id: str
    source_url: str
    parsed_timestamp: datetime
    title: str = Field(max_length=500)
    language: str = Field(pattern=r"^[a-z]{2}$")  # ISO 639-1
    text: str = Field(max_length=1_048_576)  # 1MB
    links: List[LinkReference] = Field(max_items=500)
    metadata: DocumentMetadata
    parse_status: ParseStatus
    parse_error: Optional[str] = None
    schema_version: str = "2.0"
    
    @validator("language")
    def validate_language_code(cls, v):
        valid_codes = [
            "en", "es", "fr", "de", "it", "pt", "nl", "ru", "ja", "zh",
            "ar", "pl", "tr", "ko", "th", "vi", "id", "ms", "hi", "bn"
        ]
        if v not in valid_codes:
            raise ValueError(f"Unsupported language code: {v}")
        return v


# ============================================================================
# Entity Schema
# ============================================================================

class EntityMetadata(BaseModel):
    """Metadata about entity extraction."""
    spacy_label: Optional[str] = None
    llm_model: Optional[str] = None
    pattern_matched: Optional[str] = None


class Entity(BaseModel):
    """Structured entity extracted from document."""
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    parsed_document_id: str
    entity_type: EntityType
    entity_value: str = Field(max_length=1000)
    canonical_form: str = Field(max_length=1000)
    confidence_score: float = Field(ge=0.0, le=1.0)
    extraction_method: ExtractionMethod
    context: str = Field(max_length=2000)
    extraction_timestamp: datetime
    verified: bool = False
    metadata: EntityMetadata = Field(default_factory=EntityMetadata)
    
    @validator("confidence_score")
    def validate_confidence(cls, v):
        if not (0.0 <= v <= 1.0):
            raise ValueError("Confidence score must be between 0.0 and 1.0")
        return v
    
    @validator("verified")
    def validate_verified_requires_high_confidence(cls, v, values):
        if v and values.get("confidence_score", 0) < 0.95:
            raise ValueError("Verified=true requires confidence_score >= 0.95")
        return v


# ============================================================================
# Classification Schema
# ============================================================================

class ClassificationMetadata(BaseModel):
    """Metadata about classification."""
    keywords_matched: List[str] = Field(default_factory=list)
    rule_ids: List[str] = Field(default_factory=list)
    model_version: Optional[str] = None


class Classification(BaseModel):
    """Content classification and threat level."""
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    parsed_document_id: str
    primary_label: ClassificationLabel
    confidence_score: float = Field(ge=0.0, le=1.0)
    secondary_labels: List[str] = Field(default_factory=list, max_items=5)
    threat_level: ThreatLevel
    is_false_positive: bool = False
    classification_method: str
    classification_timestamp: datetime
    metadata: ClassificationMetadata = Field(default_factory=ClassificationMetadata)


# ============================================================================
# Report Schemas
# ============================================================================

class KeyFinding(BaseModel):
    """Key finding in a report."""
    finding: str = Field(max_length=500)
    threat_level: ThreatLevel
    sources: List[str]
    recommended_action: str = Field(max_length=500)


class EntityMentions(BaseModel):
    """Entity mention aggregation."""
    malware_families: List[Dict[str, Any]] = Field(default_factory=list)
    ransomware_groups: List[Dict[str, Any]] = Field(default_factory=list)
    organizations: List[Dict[str, Any]] = Field(default_factory=list)
    cves: List[Dict[str, Any]] = Field(default_factory=list)


class Alert(BaseModel):
    """Alert from report generation."""
    alert_id: str
    condition: str
    severity: ThreatLevel
    evidence_ids: List[str]


class ReportStatistics(BaseModel):
    """Statistics from report generation."""
    documents_processed: int = Field(ge=0)
    entities_extracted: int = Field(ge=0)
    new_entities: int = Field(ge=0)
    high_confidence_entities: int = Field(ge=0)


class Report(BaseModel):
    """Generated threat intelligence report."""
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    report_type: str
    generated_timestamp: datetime
    report_period_start: datetime
    report_period_end: datetime
    title: str = Field(max_length=300)
    summary: str = Field(max_length=2000)
    key_findings: List[KeyFinding] = Field(min_items=1, max_items=50)
    entity_mentions: EntityMentions = Field(default_factory=EntityMentions)
    statistics: ReportStatistics
    alerts: List[Alert] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


# ============================================================================
# Allowlist Source Schema
# ============================================================================

class RetryPolicy(BaseModel):
    """Retry configuration for source."""
    max_retries: int = Field(default=3, ge=0, le=10)
    backoff_seconds: int = Field(default=300, ge=0)


class RateLimit(BaseModel):
    """Rate limiting configuration."""
    requests_per_hour: int = Field(default=10, ge=1, le=60)


class AllowlistSourceMetadata(BaseModel):
    """Metadata for allowlist source."""
    expected_language: str = "en"
    estimated_page_count: int = Field(default=100, ge=0)
    notes: str = ""


class AllowlistSource(BaseModel):
    """Approved source registry."""
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    url: str
    source_type: SourceType
    approved_date: datetime
    approved_by: str
    is_active: bool = True
    description: str = Field(max_length=500)
    last_crawl_timestamp: Optional[datetime] = None
    next_scheduled_crawl: datetime
    crawl_frequency_hours: int = Field(default=24, ge=1, le=720)
    priority: int = Field(default=1, ge=1, le=10)
    retry_policy: RetryPolicy = Field(default_factory=RetryPolicy)
    rate_limit: RateLimit = Field(default_factory=RateLimit)
    metadata: AllowlistSourceMetadata = Field(default_factory=AllowlistSourceMetadata)


# ============================================================================
# Audit Log Schema
# ============================================================================

class AuditLogDetails(BaseModel):
    """Details of audit log action."""
    source_url: Optional[str] = None
    status: str = "success"
    error_message: Optional[str] = None
    duration_ms: Optional[int] = None


class AuditLog(BaseModel):
    """Immutable log of all actions."""
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime
    actor_id: str
    action_type: ActionType
    resource_type: str
    resource_id: str
    action_details: AuditLogDetails = Field(default_factory=AuditLogDetails)
    approval_status: ApprovalStatus = ApprovalStatus.AUTO_APPROVED
    requires_approval: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        frozen = True  # Immutable


if __name__ == "__main__":
    # Example: Create and validate a raw page
    page = RawPage(
        source_url="https://example.onion/test",
        crawl_timestamp=datetime.utcnow(),
        http_status=200,
        headers={"content-type": "text/html"},
        body_html="<html><body>Test</body></html>",
        body_bytes_hash="abc123",
        crawl_duration_ms=1000,
        user_agent="Mozilla/5.0",
    )
    
    print("Valid RawPage created:")
    print(page.json(indent=2))
