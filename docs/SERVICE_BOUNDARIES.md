# Service Boundaries - Dark Web Threat Intelligence Agent

**Version**: 1.0.0  
**Status**: LOCKED  
**Last Updated**: 2026-07-09

This document defines the scope, responsibilities, and restrictions for each service in the platform.

---

## Service Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│              LangGraph Orchestrator                         │
│  (Routing, Checkpointing, State Management)                 │
└─────────────────────────────────────────────────────────────┘
    ↓ routes to ↓
┌─────────────────────────────────────────────────────────────┐
│                    Agent Layer                              │
├──────────────┬──────────────┬───────────────────────────────┤
│ Discovery    │ Crawler      │ Parser | Extract | Classify   │
│ Agent        │ Agent        │ Agents                        │
└──────────────┴──────────────┴───────────────────────────────┘
    ↓ uses ↓
┌─────────────────────────────────────────────────────────────┐
│                   Service Layer                             │
├──────────────┬──────────────┬────────────┬──────────────────┤
│ Config Mgmt  │ Storage      │ Proxy      │ Logging          │
│ Rate Limit   │ Retrieval    │ Connection │ Audit Trail      │
│ Approval     │ Query        │ Management │                  │
└──────────────┴──────────────┴────────────┴──────────────────┘
```

---

## 1. Discovery Service

**Responsibility**: Manage approved sources and crawl scheduling.

### Public Interface

```python
class DiscoveryService:
    def list_approved_sources() -> List[AllowlistSource]
    def get_source(source_id: str) -> AllowlistSource
    def request_new_source(url: str, reason: str) -> ApprovalTicket
    def get_next_scheduled_sources(count: int) -> List[AllowlistSource]
    def update_crawl_timestamp(source_id: str, success: bool)
```

### Restrictions

- ❌ Cannot approve sources directly (requires human approval)
- ❌ Cannot expand beyond allowlist
- ❌ Cannot scan for new sources autonomously
- ❌ Cannot modify source URLs without re-approval

### Data Ownership

- Reads: `allowlist_source` table
- Writes: Last crawl timestamp, next scheduled time
- Never modifies: Approved status, source URL

### Audit Requirements

- All approval requests logged
- Source activation/deactivation logged
- Crawl scheduling logged

---

## 2. Crawler Service

**Responsibility**: Fetch public pages via Tor with read-only enforcement.

### Public Interface

```python
class CrawlerService:
    def fetch(source_url: str, timeout_seconds: int = 30) -> RawPage
    def batch_fetch(sources: List[str]) -> List[RawPage]
    def is_allowed_source(url: str) -> bool
```

### Restrictions

- ✅ **GET requests only** - No POST, PUT, DELETE, PATCH
- ✅ **Allowlist validation** - Every URL checked before fetch
- ✅ **Rate limiting** - Per-source request rate enforced
- ✅ **Timeout enforcement** - Max 30 seconds per page
- ✅ **No form interaction** - Cannot submit forms or click links
- ✅ **No authentication** - No credentials stored or used
- ✅ **No cookie manipulation** - Accept cookies from responses only
- ❌ Cannot execute JavaScript
- ❌ Cannot interact with dynamic content
- ❌ Cannot bypass rate limits

### Tech Stack

- **HTTP Client**: `httpx` with SOCKS5 proxy
- **Proxy**: Tor SOCKS5 on localhost:9050
- **Retry Policy**: Exponential backoff, max 3 attempts
- **Circuit breaker**: Open after 10 consecutive failures per source

### Guard Enforcement

```python
@guard_read_only_enforcement
@guard_allowlist_check
@guard_rate_limit_check
def fetch(url: str) -> RawPage:
    # Implementation
    pass
```

### Audit Requirements

- Every fetch logged (success, failure, duration, status code)
- Rate limit violations logged
- Allowlist violations logged with block

### Data Ownership

- Writes: `raw_page` table
- Reads: `allowlist_source` table
- Never modifies: Configuration, other entities

---

## 3. Parser Service

**Responsibility**: Convert raw HTML into normalized documents.

### Public Interface

```python
class ParserService:
    def parse(raw_page_id: str) -> ParsedDocument
    def parse_batch(raw_page_ids: List[str]) -> List[ParsedDocument]
```

### Restrictions

- ✅ **Deterministic output** - Same input always produces same output
- ✅ **Schema compliance** - Output validates against `ParsedDocument`
- ✅ **Language detection** - ISO 639-1 codes only
- ❌ Cannot execute code or scripts
- ❌ Cannot make external requests
- ❌ Cannot modify source content

### Tech Stack

- **HTML Parsing**: BeautifulSoup4 + lxml
- **Language Detection**: `langdetect`
- **Link Extraction**: Regex + DOM traversal
- **Text Extraction**: Cleaned, whitespace normalized

### Handling Failures

- Partial parse: Return what can be extracted
- Full failure: Return null fields, set `parse_status: "failed"`
- Log all errors with raw_page_id for investigation

### Data Ownership

- Reads: `raw_page` table
- Writes: `parsed_document` table
- Links via: `raw_page_id` foreign key

---

## 4. Entity Extraction Service

**Responsibility**: Extract structured entities from parsed text.

### Public Interface

```python
class EntityExtractionService:
    def extract_entities(parsed_document_id: str) -> List[Entity]
    def extract_batch(parsed_document_ids: List[str]) -> List[Entity]
```

### Supported Entity Types

- Organization
- Malware Family
- Ransomware Group
- CVE ID
- Cryptocurrency Address
- Email
- Username
- Date
- Software

### Extraction Methods

1. **Regex Patterns** - Deterministic, high precision (CVE IDs, crypto addresses)
2. **spaCy NER** - Fast NLP model for common entities
3. **LLM Extraction** - Claude/GPT-4 for complex context (fallback)

### Restrictions

- ✅ **Confidence scoring** - All extractions scored 0.0-1.0
- ✅ **Context preservation** - Keep surrounding text for review
- ✅ **Canonical forms** - Normalized for deduplication
- ✅ **Verified flag** - Only true for high-confidence (>0.95) or manual review
- ❌ Cannot modify source text
- ❌ Cannot query external APIs for validation (except allowed knowledge bases)
- ❌ Cannot store false positives without review flags

### Guard Enforcement

```python
@guard_confidence_threshold(min_score=0.60)
@guard_manual_review_for_low_confidence
def extract_entities(document: ParsedDocument) -> List[Entity]:
    # Implementation
    pass
```

### LLM Configuration

- **Model**: gpt-4 (configurable via central config)
- **Temperature**: 0.2 (low variance, deterministic)
- **Max tokens**: 2000 per document
- **Fallback**: If LLM unavailable, use regex + spaCy only

### Data Ownership

- Reads: `parsed_document` table
- Writes: `entity` table
- Links via: `parsed_document_id` foreign key

---

## 5. Classification Service

**Responsibility**: Assign threat level and content labels.

### Public Interface

```python
class ClassificationService:
    def classify(parsed_document_id: str) -> Classification
    def classify_batch(parsed_document_ids: List[str]) -> List[Classification]
```

### Classification Labels

- **Primary**: Malware | Leak | Forum | Research | News | Marketplace
- **Threat Level**: Critical | High | Medium | Low | Informational
- **Secondary**: Tags for sub-categorization

### Restrictions

- ✅ **Confidence scoring** - 0.0-1.0 required
- ✅ **Audit trail** - Method and metadata captured
- ✅ **False positive marking** - Can be flagged for review
- ❌ Cannot modify source content
- ❌ Cannot call external threat feed APIs without approval
- ❌ Cannot update historical classifications retroactively

### Classification Methods

1. **Rule-based**: Keyword matching (deterministic)
2. **LLM Classification**: Claude/GPT-4 with structured output
3. **Hybrid**: Rules first, LLM for edge cases

### LLM Configuration

- **Model**: gpt-4
- **Temperature**: 0.3 (low but not zero for natural language)
- **Structured output**: JSON schema for consistency

### Quality Gates

- Confidence < 0.60: Flagged for manual review
- Ambiguous content: Secondary labels added
- Novel patterns: Escalated to analyst

### Data Ownership

- Reads: `parsed_document` table
- Writes: `classification` table
- Links via: `parsed_document_id` foreign key

---

## 6. Knowledge Graph Service

**Responsibility**: Build and maintain relationship graphs.

### Public Interface

```python
class KnowledgeGraphService:
    def add_entity_relationship(entity1_id: str, entity2_id: str, relation_type: str)
    def get_entity_network(entity_id: str, depth: int) -> Graph
    def query_relationships(entity_value: str) -> List[Relationship]
```

### Restrictions

- ✅ **Source-backed relationships** - Only from document analysis
- ✅ **Temporal tracking** - When each relationship was observed
- ❌ Cannot infer relationships without evidence
- ❌ Cannot create relationships from external data
- ❌ Cannot query external knowledge bases without approval

### Relationship Types

- `mentioned_in` (entity → document)
- `attributed_to` (malware → group)
- `targets` (malware → organization)
- `exploits` (group → CVE)
- `uses_infrastructure` (group → IP/domain)
- `collaborates_with` (group → group)

### Storage Backend

- **Primary**: Neo4j
- **Fallback**: PostgreSQL with JSON JSONB columns

### Data Ownership

- Reads: `entity` table
- Writes: `neo4j` graph
- Links: Entity relationships only

---

## 7. Storage Service

**Responsibility**: Persist all data with integrity checks.

### Public Interface

```python
class StorageService:
    def save(entity: Union[RawPage, ParsedDocument, Entity, Classification])
    def retrieve(entity_type: str, entity_id: str)
    def query(entity_type: str, filters: Dict)
    def delete(entity_id: str, reason: str)  # Soft delete only
```

### Restrictions

- ✅ **Append-only** - Historical records never deleted, soft-delete only
- ✅ **Integrity checks** - Foreign key constraints, schema validation
- ✅ **Provenance tracking** - Every record includes source_id and timestamp
- ✅ **Encryption at rest** - Sensitive fields encrypted
- ✅ **Backup consistency** - Point-in-time recovery available
- ❌ Cannot update historical records (immutable)
- ❌ Cannot bypass validation schemas
- ❌ Cannot directly modify audit logs

### Database Backends

- **Primary**: PostgreSQL (parsed docs, entities, classifications, audit logs)
- **Vector DB**: Qdrant (embeddings for semantic search)
- **Graph DB**: Neo4j (relationships)
- **Search**: OpenSearch/Elasticsearch (full-text indexing)

### Data Retention

| Table | Retention | Reason |
|-------|-----------|--------|
| raw_page | 90 days | High volume, parsed doc sufficient |
| parsed_document | Indefinite | Core intelligence |
| entity | Indefinite | Historical tracking |
| classification | Indefinite | Audit trail |
| audit_log | 2 years | Legal requirement |

### Data Ownership

- All writes go through Storage Service
- No direct database access from agents
- Centralized validation and audit logging

---

## 8. Configuration Service

**Responsibility**: Manage system configuration with approval workflow.

### Public Interface

```python
class ConfigService:
    def get_config(section: str) -> Dict
    def request_config_change(section: str, changes: Dict) -> ApprovalTicket
    def apply_config_change(ticket_id: str, approved: bool)
    def rollback_config(timestamp: str)
```

### Restrictions

- ✅ **Human approval required** - No automatic config changes
- ✅ **Versioned** - All versions stored, rollback available
- ✅ **Audit trail** - Who, what, when, why for all changes
- ❌ Cannot apply config changes without approval
- ❌ Cannot bypass validation schemas

### Configuration Sections

- `tor_proxy`: SOCKS5 address, port, rotation settings
- `rate_limits`: Per-source request rates, global limits
- `allowlist`: Approved sources registry
- `llm_models`: Model names, temperature, max tokens
- `storage`: Database connection strings (encrypted)
- `logging`: Log levels, retention policies

### Change Workflow

1. Operator requests change with justification
2. System validates change (schema, safety checks)
3. Approval queue (reviewer + security sign-off)
4. Apply change with rollback pointer
5. Log all actions with audit trail

### Data Ownership

- Reads: All services
- Writes: Authorized operators only, via approval workflow

---

## Service Communication

### Synchronous Call Pattern

```python
# Agent calls service directly
async def discover_agent():
    sources = discovery_service.list_approved_sources()
    for source in sources:
        page = crawler_service.fetch(source.url)
        # Pass to next stage
```

### Error Handling

- **Service unavailable**: Retry with exponential backoff
- **Validation failure**: Log error, skip record, continue
- **Rate limit**: Queue for later, respect backoff
- **Authorization failure**: Escalate to operator

### Observability

Every service logs:
- Input/output (sanitized)
- Duration
- Error code (if any)
- Trace ID for correlation

---

## Deployment Boundaries

- **Orchestrator**: Runs on control plane
- **Agents**: Stateless, can run on multiple replicas
- **Services**: Database connections shared, rate limiting global
- **Storage**: Centralized database layer
- **Configuration**: Single source of truth with caching

---

## Next Steps

1. Implement service base classes with standard interfaces
2. Create service factories with dependency injection
3. Write integration tests for service boundaries
4. Deploy with service-level observability and alerts
