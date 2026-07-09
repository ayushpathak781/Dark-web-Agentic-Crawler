# Dark Web Threat Intelligence Agent

**Status**: Phase 0 - Foundation & Planning  
**Version**: 1.0.0  
**Purpose**: Build a read-only, agentic cybersecurity research platform that collects, extracts, classifies, and summarizes publicly accessible Tor content for defensive threat intelligence.

---

## 🎯 Project Overview

### What This Is

A strictly **read-only** intelligence pipeline that:
- ✅ Crawls publicly accessible Tor content from approved sources
- ✅ Extracts structured threat entities (malware, CVEs, ransomware groups, etc.)
- ✅ Classifies content by threat level and category
- ✅ Builds searchable knowledge graphs of relationships
- ✅ Generates threat reports and alerts
- ✅ Maintains complete audit trails for compliance

### What This Is NOT

- ❌ **Not an exploit platform** - No vulnerability scanning or exploitation
- ❌ **Not a credential stealer** - No credential collection or usage
- ❌ **Not a marketplace bot** - No automated marketplace interaction or purchases
- ❌ **Not invasive** - No fingerprinting, port scanning, or system exploitation
- ❌ **Not autonomous** - Human approval required for source expansion and major config changes

### Core Principles

1. **Read-Only Enforcement**: Every component can only perform GET requests
2. **Allowlist-Based Discovery**: Only approved sources are crawled
3. **Audit Everything**: Full trail of who did what, when, and why
4. **Fail Safe**: Errors are logged and escalated, never silently ignored
5. **Deterministic Processing**: Same input always produces same output (reproducibility)

---

## 📋 Project Structure

```
darkweb-agentic-crawler/
├── docs/
│   ├── ORCHESTRATION_FRAMEWORK_DECISION.md    (Framework choice: LangGraph)
│   ├── DATA_SCHEMAS.md                        (All entity schemas & relationships)
│   ├── SERVICE_BOUNDARIES.md                  (Service responsibilities & restrictions)
│   └── README.md                               (You are here)
├── src/
│   ├── __init__.py                            (Package initialization)
│   ├── config/
│   │   ├── __init__.py
│   │   └── config.py                          (Configuration management)
│   ├── models/
│   │   ├── __init__.py
│   │   └── schemas.py                         (Pydantic models for all entities)
│   ├── orchestrator/
│   │   ├── __init__.py
│   │   └── graph.py                           (LangGraph orchestration)
│   ├── agents/
│   │   └── __init__.py                        (Agent implementations)
│   └── services/
│       ├── __init__.py
│       └── base.py                            (Base service classes)
├── tests/
│   ├── __init__.py
│   └── test_crawler_readonly.py               (Read-only enforcement tests)
├── action_plan.md                             (7-phase implementation roadmap)
├── dark_web_threat_intelligence_agent_project.json
├── requirements.txt                           (Python dependencies)
└── README.md                                  (This file)
```

---

## 🚀 Quick Start

### 1. Prerequisites

- Python 3.10+
- Tor SOCKS5 proxy running on localhost:9050
- PostgreSQL 14+ (for production)
- Neo4j 5+ (for production)

### 2. Installation

```bash
# Clone repository
cd darkweb-agentic-crawler

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Download spaCy model
python -m spacy download en_core_web_sm
```

### 3. Configuration

```bash
# Copy default config template
cp config.example.json config.json

# Edit config.json with your settings:
# - Tor proxy address
# - Database credentials (encrypted)
# - Rate limits
# - Approved sources
```

### 4. Run Tests

```bash
# Run all unit tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=src --cov-report=html

# Run read-only enforcement tests specifically
pytest tests/test_crawler_readonly.py -v
```

---

## 📚 Key Documentation

### Orchestration Framework

**File**: [docs/ORCHESTRATION_FRAMEWORK_DECISION.md](docs/ORCHESTRATION_FRAMEWORK_DECISION.md)

- ✅ **Chosen**: LangGraph
- **Why**: Deterministic DAG execution, built-in checkpointing, full audit trails
- Comparison with CrewAI and AutoGen included

### Data Schemas

**File**: [docs/DATA_SCHEMAS.md](docs/DATA_SCHEMAS.md)

Defines all entity types:
- **RawPage**: Unmodified crawled HTML + metadata
- **ParsedDocument**: Normalized text extraction
- **Entity**: Structured threat entities with confidence scores
- **Classification**: Content labels and threat levels
- **Report**: Aggregated intelligence summaries
- **AllowlistSource**: Approved crawl targets
- **AuditLog**: Immutable action trails

### Service Boundaries

**File**: [docs/SERVICE_BOUNDARIES.md](docs/SERVICE_BOUNDARIES.md)

Defines 8 core services:
1. **Discovery** - Manage approved sources
2. **Crawler** - Fetch pages (GET-only, rate-limited)
3. **Parser** - HTML → normalized text
4. **Entity Extraction** - NER + LLM summarization
5. **Classification** - Content labels + threat levels
6. **Knowledge Graph** - Relationship mapping (Neo4j)
7. **Storage** - Multi-backend persistence (PostgreSQL, Qdrant, ES)
8. **Configuration** - Config management with approval workflows

---

## 🔐 Safety Architecture

### Read-Only Enforcement

Every component is **guaranteed read-only**:

```python
# ✅ Allowed
crawler.fetch("https://approved.onion/page")  # GET request

# ❌ Blocked at code level
crawler.post(url, data)       # ← Method doesn't exist
crawler.submit_form(form_id)  # ← Method doesn't exist
crawler.login(username, password)  # ← Method doesn't exist
```

**How it works:**
1. Crawler agent has no POST/PUT/DELETE methods (compile-time check)
2. HTTP client configured for GET-only
3. Guards validate every request before execution
4. Violations logged as security events

### Allowlist Enforcement

```python
# Only approved sources can be crawled
approved_sources = discovery_service.list_approved_sources()
# Returns: [source1.onion, source2.onion, ...]

# Attempting to crawl non-approved source raises error
crawler.fetch("https://random.onion/page")  # ValueError: URL not in allowlist
```

### Approval Workflow

```
Config Change Request
    ↓
System Validates (schema checks)
    ↓
Approval Queue (human review + security sign-off)
    ↓
Applied with Rollback Pointer
    ↓
Audit Logged
```

---

## 🏗️ Phase Roadmap

### Phase 0: Foundation (CURRENT)
- [x] Define safety boundaries
- [x] Choose orchestration framework
- [x] Design data schemas
- [x] Define service boundaries
- [ ] Set up repository
- [ ] Create initial tests

**Deliverables**:
- ✅ Orchestration framework decision
- ✅ Data schema documentation
- ✅ Service boundary definitions
- ✅ Read-only enforcement tests
- ✅ Configuration system

### Phase 1: Core Architecture (NEXT)
- Implement orchestrator with dependency injection
- Create agent base classes
- Set up central configuration
- Add audit logging framework

### Phase 2: Discovery & Crawling
- Build Tor-aware fetch layer
- Implement read-only crawler with guards
- Add rate limiting
- Create source registry

### Phase 3: Parsing & Extraction
- HTML parsing with BeautifulSoup
- Text extraction and link analysis
- OCR and PDF support
- Language detection

### Phase 4: Entity Extraction & Classification
- NER pipeline with spaCy
- LLM-assisted summarization
- Entity canonicalization
- Content classification

### Phase 5: Storage & Knowledge Graph
- PostgreSQL data persistence
- Qdrant vector embeddings
- Neo4j relationship mapping
- Full-text search (OpenSearch)

### Phase 6: Reporting & Alerting
- Report generation
- Trend analysis
- Alerting rules
- Export capabilities

### Phase 7: Testing & Hardening
- Comprehensive test coverage
- Safety validation
- Containerized deployment
- Observability dashboards

---

## 🧪 Testing Strategy

### Test Categories

1. **Unit Tests** (tests/unit/)
   - Individual function behavior
   - Schema validation
   - Config parsing

2. **Service Tests** (tests/service/)
   - Service initialization
   - Interface contracts
   - Error handling

3. **Integration Tests** (tests/integration/)
   - End-to-end workflow
   - Multi-service interactions
   - Checkpoint recovery

4. **Safety Tests** (tests/safety/)
   - Read-only enforcement ✅ (implemented)
   - Allowlist validation
   - Rate limit verification
   - Audit trail completeness

### Running Tests

```bash
# All tests
pytest tests/

# Specific category
pytest tests/test_crawler_readonly.py

# With coverage
pytest tests/ --cov=src --cov-report=term-missing

# Verbose output
pytest tests/ -v -s
```

---

## 📊 Key Classes & Interfaces

### Configuration

```python
from src.config.config import get_config, ConfigSection

config = get_config()
tor_host = config.get(ConfigSection.TOR_PROXY, "host")
config.set(
    ConfigSection.RATE_LIMITS,
    "global_requests_per_hour",
    500,
    reason="Testing"
)
```

### Data Models

```python
from src.models.schemas import (
    RawPage, ParsedDocument, Entity, Classification
)
from datetime import datetime

# Create a raw page
page = RawPage(
    source_url="https://example.onion",
    crawl_timestamp=datetime.utcnow(),
    http_status=200,
    headers={"content-type": "text/html"},
    body_html="<html>...</html>",
    body_bytes_hash="abc123",
    crawl_duration_ms=1500,
    user_agent="Mozilla/5.0"
)

# Pydantic validation happens automatically
assert page.http_status in range(200, 300)
```

### Orchestration

```python
from src.orchestrator.graph import OrchestrationGraph

graph = OrchestrationGraph(config)

# Execute workflow
state = graph.execute({
    "crawl_request": {...}
})

# Check results
print(f"Completed nodes: {state.completed_nodes}")
print(f"Checkpoints: {state.checkpoints.keys()}")
```

---

## 🔍 Audit & Compliance

### Audit Logging

Every action is logged:

```
timestamp: 2026-07-09T10:30:00Z
actor_id: system
action_type: crawl_start
resource_type: source
resource_id: source_001
action_details:
  source_url: https://example.onion
  status: success
  duration_ms: 1234
metadata:
  ip_address: 127.0.0.1
```

### Compliance Features

- ✅ Immutable audit logs (append-only)
- ✅ 2-year retention policy
- ✅ Role-based access control hooks
- ✅ Configuration change approval workflows
- ✅ Data retention policies by entity type
- ✅ Soft-delete (never hard-delete) with reasons

---

## 📈 Performance Targets

| Metric | Target | Notes |
|--------|--------|-------|
| Page crawl time | <2s | Per page (excluding network) |
| Parse latency | <500ms | Per document |
| Entity extraction | <1s | Per document |
| Daily crawl volume | 1000+ pages | With rate limiting |
| Report generation | <5min | Daily |
| Query latency | <500ms | P95 |

---

## 🛠️ Development Workflow

### Making Changes

1. **Create feature branch**
   ```bash
   git checkout -b feature/agent-x
   ```

2. **Write tests first** (TDD approach)
   ```bash
   pytest tests/test_new_feature.py -v
   ```

3. **Implement feature**
   ```python
   # src/agents/new_agent.py
   ```

4. **Run full test suite**
   ```bash
   pytest tests/ --cov=src
   ```

5. **Format & lint**
   ```bash
   black src/
   isort src/
   flake8 src/
   mypy src/
   ```

6. **Commit with message**
   ```bash
   git commit -m "feat: Add new agent with tests"
   ```

### Code Style

- **Formatter**: Black
- **Import sorting**: isort
- **Linter**: flake8 + pylint
- **Type checker**: mypy
- **Docstring style**: Google style

---

## 📝 Configuration Example

```json
{
  "tor_proxy": {
    "host": "localhost",
    "port": 9050,
    "socks_version": 5,
    "circuit_rotation_interval_hours": 1,
    "timeout_seconds": 30
  },
  "rate_limits": {
    "global_requests_per_hour": 1000,
    "per_source_requests_per_hour": 10
  },
  "llm_models": {
    "extraction_model": "gpt-4",
    "extraction_temperature": 0.2,
    "classification_model": "gpt-4"
  },
  "security": {
    "require_approval_for_new_sources": true,
    "require_approval_for_config_changes": true,
    "enable_read_only_enforcement": true
  }
}
```

---

## ❓ FAQ

**Q: Why read-only only?**  
A: Prevents accidental harm, simplifies safety validation, and meets legal/compliance requirements for threat intelligence work.

**Q: Why LangGraph?**  
A: Deterministic execution, native checkpointing, full audit trails, and superior control flow for agentic systems compared to alternatives.

**Q: Can I add new sources?**  
A: Yes, via the request workflow. Submit a request with justification → Security review → Approval → Added to allowlist.

**Q: What happens if crawling fails?**  
A: Error is logged with full context, workflow pauses, operator is alerted, and system can resume from checkpoint.

**Q: How are credentials handled?**  
A: They're not. System supports only public content. No credential storage, no auth flows, no password handling.

---

## 📞 Support & Escalation

### Issues & Bugs

1. Log to audit trail
2. Alert operator on-call
3. Check diagnostics dashboard
4. Review logs in `logs/` directory

### Configuration Changes

1. Submit change request via config service
2. Validation checks run automatically
3. Security team reviews (24h SLA)
4. Applied with automatic rollback pointer

### Emergency Stops

```bash
# Kill all crawlers (graceful shutdown)
pkill -SIGTERM crawler

# Rollback to previous config
config.rollback(timestamp="2026-07-09T10:00:00Z")
```

---

## 📄 License

This project is for authorized cybersecurity research only. Unauthorized access to computer systems is illegal.

---

## ✅ Immediate Next Steps

- [x] Lock orchestration framework (LangGraph)
- [x] Define data schemas
- [x] Define service boundaries
- [x] Create repository scaffold
- [x] Write read-only enforcement tests
- [ ] **NEXT**: Implement Phase 1 architecture
  - [ ] Orchestrator service with dependency injection
  - [ ] Agent base classes
  - [ ] Central configuration
  - [ ] Audit logging framework

---

**Last Updated**: 2026-07-09  
**Maintained By**: Threat Intelligence Team
