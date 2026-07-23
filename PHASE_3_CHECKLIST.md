# Phase 3 Implementation Checklist - Parsing and Extraction

**Status**: IN PROGRESS  
**Start Date**: 2026-07-23

---

## Phase 3 Goal

Convert raw crawled pages into normalized parsed documents with deterministic parsing, link extraction, metadata, and recoverable parse errors.

## Deliverables

- [ ] Parser service for HTML normalization
- [ ] Text extraction and title detection
- [ ] Link extraction and metadata generation
- [ ] Language detection with safe fallback
- [ ] Parse error capture and schema-valid output
- [ ] Orchestrator integration for parse step
- [ ] Parser-focused tests

## Acceptance Criteria

- [ ] Parsed output is deterministic and schema-valid
- [ ] Failed parses are captured with recoverable error metadata
- [ ] Orchestrator routes raw pages into parsed documents
- [ ] Tests cover success and failure paths
