# Data Schemas - Dark Web Threat Intelligence Agent

**Version**: 1.0.0  
**Status**: LOCKED  
**Last Updated**: 2026-07-09

All data schemas are Pydantic V2 compatible and enforce type safety, validation, and serialization.

---

## 1. Raw Page Schema

**Purpose**: Store unmodified crawled content with provenance metadata.

```json
{
  "raw_page": {
    "id": "uuid (auto-generated)",
    "source_url": "https://example.onion/page",
    "crawl_timestamp": "ISO 8601 datetime",
    "http_status": 200,
    "headers": {
      "content-type": "text/html; charset=utf-8",
      "content-length": 12345
    },
    "body_html": "raw HTML content (unmodified)",
    "body_bytes_hash": "sha256 hex string",
    "crawl_duration_ms": 2345,
    "tor_circuit_id": "optional circuit identifier for audit",
    "user_agent": "Mozilla/5.0 ...",
    "retry_count": 0,
    "error": null
  }
}
```

**Validation Rules**:
- `http_status`: Must be 200-299 (success only)
- `body_html`: Max 50MB
- `source_url`: Must match approved source allowlist
- `crawl_timestamp`: Must be UTC

---

## 2. Parsed Document Schema

**Purpose**: Normalized, extracted content from raw pages.

```json
{
  "parsed_document": {
    "id": "uuid",
    "raw_page_id": "uuid (foreign key)",
    "source_url": "https://example.onion/page",
    "parsed_timestamp": "ISO 8601",
    "title": "Document title extracted from <title> or <h1>",
    "language": "en (ISO 639-1 code, detected by langdetect)",
    "text": "Plain text content (cleaned)",
    "links": [
      {
        "href": "https://example.onion/other",
        "text": "Link text",
        "context": "Sentence containing the link"
      }
    ],
    "metadata": {
      "word_count": 1234,
      "paragraph_count": 5,
      "image_count": 3,
      "table_count": 0,
      "code_block_count": 0
    },
    "parse_status": "success|partial|failed",
    "parse_error": null,
    "schema_version": "2.0"
  }
}
```

**Validation Rules**:
- `language`: ISO 639-1 code only
- `text`: UTF-8, max 1MB
- `links`: Max 500 links per document
- `parse_status`: One of allowed values
- Must link back to valid `raw_page_id`

---

## 3. Entity Schema

**Purpose**: Structured entities extracted from parsed documents.

```json
{
  "entity": {
    "id": "uuid",
    "parsed_document_id": "uuid (foreign key)",
    "entity_type": "organization|malware_family|ransomware_group|cve_id|crypto_address|email|username|date|software",
    "entity_value": "Extracted text (normalized)",
    "canonical_form": "Normalized form for deduplication",
    "confidence_score": 0.85,
    "extraction_method": "spacy_ner|llm_extraction|regex_pattern",
    "context": "Surrounding sentence or paragraph",
    "extraction_timestamp": "ISO 8601",
    "verified": false,
    "metadata": {
      "spacy_label": "ORG",
      "llm_model": "gpt-4",
      "pattern_matched": null
    }
  }
}
```

**Validation Rules**:
- `confidence_score`: Float 0.0-1.0
- `entity_type`: Must be in allowed list
- `canonical_form`: Lowercase, whitespace normalized
- `extraction_method`: One of specified methods
- `verified`: Only set to true after manual review or high-confidence threshold (>0.95)

---

## 4. Classification Schema

**Purpose**: Content category and threat level labels.

```json
{
  "classification": {
    "id": "uuid",
    "parsed_document_id": "uuid (foreign key)",
    "primary_label": "malware|leak|forum|research|news|marketplace",
    "confidence_score": 0.92,
    "secondary_labels": ["ransomware", "threat-report"],
    "threat_level": "critical|high|medium|low|informational",
    "is_false_positive": false,
    "classification_method": "llm_classification|rule_based|hybrid",
    "classification_timestamp": "ISO 8601",
    "metadata": {
      "keywords_matched": ["trojan", "ransomware"],
      "rule_ids": ["RULE_001"],
      "model_version": "gpt-4-20260701"
    }
  }
}
```

**Validation Rules**:
- `confidence_score`: Float 0.0-1.0
- `primary_label`: Exactly one
- `secondary_labels`: Max 5
- `threat_level`: One of allowed values
- Confidence <0.60 marked for manual review

---

## 5. Report Schema

**Purpose**: Aggregated threat intelligence summaries.

```json
{
  "report": {
    "id": "uuid",
    "report_type": "daily_summary|incident|entity_profile|trend_analysis",
    "generated_timestamp": "ISO 8601",
    "report_period_start": "ISO 8601",
    "report_period_end": "ISO 8601",
    "title": "Daily Dark Web Threat Summary - 2026-07-09",
    "summary": "Executive summary (2-3 sentences)",
    "key_findings": [
      {
        "finding": "New ransomware variant detected",
        "threat_level": "critical",
        "sources": ["malware_report_001", "forum_post_042"],
        "recommended_action": "Alert SOC and blocklist C2 IPs"
      }
    ],
    "entity_mentions": {
      "malware_families": [
        {
          "name": "Alphv",
          "mention_count": 3,
          "trend": "increasing"
        }
      ],
      "ransomware_groups": [],
      "organizations": [],
      "cves": []
    },
    "statistics": {
      "documents_processed": 145,
      "entities_extracted": 892,
      "new_entities": 67,
      "high_confidence_entities": 45
    },
    "alerts": [
      {
        "alert_id": "ALERT_001",
        "condition": "New C2 infrastructure for known APT",
        "severity": "critical",
        "evidence_ids": ["entity_123", "entity_456"]
      }
    ],
    "metadata": {
      "sources_crawled": 23,
      "generation_duration_ms": 3456
    }
  }
}
```

**Validation Rules**:
- `report_type`: One of allowed types
- `key_findings`: Min 1, max 50
- `statistics`: All counts >= 0
- `generation_duration_ms`: <= 3600000 (1 hour)

---

## 6. Allowlist Source Schema

**Purpose**: Approved sources registry with scheduling metadata.

```json
{
  "allowlist_source": {
    "id": "uuid",
    "url": "https://example.onion",
    "source_type": "forum|marketplace|news|research|tracker",
    "approved_date": "ISO 8601",
    "approved_by": "user_id",
    "is_active": true,
    "description": "Brief description of source content",
    "last_crawl_timestamp": "ISO 8601 or null",
    "next_scheduled_crawl": "ISO 8601",
    "crawl_frequency_hours": 24,
    "priority": 1,
    "retry_policy": {
      "max_retries": 3,
      "backoff_seconds": 300
    },
    "rate_limit": {
      "requests_per_hour": 10
    },
    "metadata": {
      "expected_language": "en",
      "estimated_page_count": 150,
      "notes": "Known malware distribution hub - research only"
    }
  }
}
```

**Validation Rules**:
- `url`: Valid Tor .onion URL only
- `is_active`: Cannot be changed without explicit approval
- `priority`: Int 1-10
- `crawl_frequency_hours`: 1-720 (1 hour to 30 days)
- `requests_per_hour`: 1-60

---

## 7. Audit Log Schema

**Purpose**: Immutable log of all actions for compliance and investigation.

```json
{
  "audit_log": {
    "id": "uuid",
    "timestamp": "ISO 8601",
    "actor_id": "user_id or system",
    "action_type": "crawl_start|crawl_complete|entity_extract|classification|data_export|config_change|approval|rejection",
    "resource_type": "source|document|entity|report|configuration",
    "resource_id": "uuid",
    "action_details": {
      "source_url": "optional context",
      "status": "success|failure",
      "error_message": null,
      "duration_ms": 1234
    },
    "approval_status": "pending|approved|rejected|auto_approved",
    "requires_approval": false,
    "metadata": {
      "ip_address": "127.0.0.1",
      "user_agent": "system/1.0",
      "audit_trail_version": "1.0"
    }
  }
}
```

**Validation Rules**:
- `action_type`: One of allowed values
- `timestamp`: Must be UTC
- `approval_status`: Tracks multi-step actions
- Records are immutable (no updates after creation)

---

## Relationship Model

```
raw_page (1) ─→ (N) parsed_document
           ↓
        (N) entity
           ↓
        (N) classification

allowlist_source (1) ─→ (N) raw_page

report (1) ─→ (N) key_findings
          ↓
       references entities & documents

audit_log (N) ─→ (1) resource (any above)
```

---

## Deduplication Rules

### Entity Canonical Forms

- **Organization**: Lowercase, spaces normalized, remove (TM), ®, (C)
- **Malware Family**: Exact match on lowercase, version suffix ignored
- **CVE ID**: Strict format CVE-YYYY-NNNNN
- **Email**: Lowercase, domain normalized
- **Crypto Address**: Exact match on address
- **Username**: Lowercase, platform context included

### Document Deduplication

- Hash `body_html` with SHA256
- If hash exists and http_status=200 within 7 days, mark as duplicate
- Still process for entity extraction (may have new context)

---

## Retention Policy

| Schema | Retention | Reason |
|--------|-----------|--------|
| raw_page | 90 days | Disk intensive, parsed doc sufficient |
| parsed_document | Indefinite | Core intelligence |
| entity | Indefinite | Historical tracking |
| classification | Indefinite | Audit trail |
| report | 1 year | Compliance & trend analysis |
| audit_log | 2 years | Legal/forensic requirement |
| allowlist_source | Indefinite | Source management |

---

## Next Steps

1. Generate Pydantic models from schemas
2. Create database migrations (PostgreSQL)
3. Write schema validation tests
4. Define serialization/deserialization logic
