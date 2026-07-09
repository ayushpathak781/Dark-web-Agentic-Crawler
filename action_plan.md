# Dark Web Threat Intelligence Agent - Action Plan

## Scope
Build a strictly read-only threat-intelligence pipeline for publicly accessible Tor content. The plan keeps the system inside the documented safety boundaries: no exploitation, no credential use, no automated transactions, no login flows, and no expansion beyond approved sources.

## Phase 0: Project foundation
Goal: establish the product boundaries, runtime architecture, and delivery standards before any crawling or extraction work begins.

Deliverables:
- Finalize the approved source policy and safety checklist.
- Choose the orchestration framework among LangGraph, CrewAI, or AutoGen.
- Define the core service boundaries: discovery, crawl, parse, extraction, storage, search, reporting.
- Set up repository structure, configuration management, logging, and audit conventions.
- Define data schemas for raw pages, parsed documents, entities, classifications, and reports.

Acceptance criteria:
- Every agent has a documented responsibility and restriction set.
- The system has a clear read-only enforcement model.
- The data model is agreed before implementation starts.

## Phase 1: Core architecture
Goal: implement the orchestration layer and the shared service contracts.

Deliverables:
- Orchestrator service with dependency injection and workflow coordination.
- Agent interfaces for DiscoveryAgent, CrawlerAgent, ParserAgent, EntityExtractionAgent, ClassificationAgent, KnowledgeGraphAgent, and ReportingAgent.
- Central configuration for rate limiting, source allowlists, storage endpoints, and model settings.
- Audit logging and job tracking.

Acceptance criteria:
- The orchestrator can route a content item through the pipeline.
- Configuration changes require explicit human approval.
- All actions are traceable in logs.

## Phase 2: Discovery and crawling
Goal: collect only approved public content using read-only fetches.

Deliverables:
- Approved source registry with revisit scheduling.
- Tor-aware fetch layer via SOCKS5 proxy.
- Read-only crawler with GET-only behavior, rate limits, retries, and timeouts.
- Raw HTML and metadata persistence.

Acceptance criteria:
- The crawler cannot submit forms, log in, or interact beyond fetching pages.
- The crawler respects the source allowlist and rate limits.
- Raw captures are stored with provenance metadata.

## Phase 3: Parsing and extraction
Goal: convert raw pages into normalized content and structured signals.

Deliverables:
- HTML parsing with BeautifulSoup and lxml.
- Text extraction, link extraction, and language detection.
- OCR and PDF extraction where needed.
- Structured JSON output for title, language, text, links, and metadata.

Acceptance criteria:
- Parsed output is deterministic and schema-valid.
- Parser accuracy is measurable against a test corpus.
- Failed parses are captured with recoverable error metadata.

## Phase 4: Entity extraction and classification
Goal: transform parsed text into intelligence records and topical labels.

Deliverables:
- NER and LLM-assisted summarization pipeline.
- Entity schema for organizations, malware families, ransomware groups, CVE IDs, cryptocurrency addresses, emails, usernames, dates, and software.
- Content classification into Malware, Leak, Forum, Research, News, and Marketplace.
- Quality checks for precision, deduplication, and normalization.

Acceptance criteria:
- Entity output is valid JSON and linked back to source documents.
- Classification is reproducible and auditable.
- Precision targets are benchmarked on a labeled dataset.

## Phase 5: Storage, search, and knowledge graph
Goal: make the collected intelligence queryable and relational.

Deliverables:
- PostgreSQL for parsed JSON and operational metadata.
- Qdrant for embeddings.
- Neo4j for relationship graphs.
- OpenSearch or Elasticsearch for text search.
- Relationship mapping between sources, entities, and time-based events.

Acceptance criteria:
- Every stored record has a provenance path back to the source page.
- Search can retrieve documents by entity, label, and keyword.
- Graph queries can traverse relationships between entities and sources.

## Phase 6: Reporting and alerting
Goal: turn collected intelligence into operational outputs.

Deliverables:
- Daily and on-demand report generator.
- Trend analysis over time windows.
- Alerting rules for high-signal changes.
- Exportable summaries for analysts.

Acceptance criteria:
- Reports can be generated from stored data without manual intervention.
- Report latency stays within the target threshold for routine runs.
- Alerts include the evidence needed for analyst review.

## Phase 7: Testing and hardening
Goal: prove safety, reliability, and maintainability before release.

Deliverables:
- Unit tests for each module and schema.
- Integration tests for the end-to-end pipeline.
- Safety tests that verify read-only behavior and allowlist enforcement.
- Containerized deployment with isolated services.
- Observability via logs, metrics, and dashboards.

Acceptance criteria:
- Tests cover the critical path from discovery to reporting.
- No component can bypass the documented safety constraints.
- Deployment artifacts can be started reproducibly in Docker.

## Recommended Execution Order
1. Lock the safety model and schemas.
2. Implement the orchestrator and agent contracts.
3. Build the crawler with strict read-only enforcement.
4. Add parsing and extraction.
5. Add storage, search, and graph indexing.
6. Add reporting and alerting.
7. Finish with testing, observability, and deployment hardening.

## Immediate Next Steps
- Confirm the orchestration framework choice.
- Define the initial data schemas.
- Create the repository scaffold and service boundaries.
- Write the first unit tests for the read-only crawler contract.