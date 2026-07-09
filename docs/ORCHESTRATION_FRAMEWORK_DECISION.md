# Orchestration Framework Decision

**Status**: LOCKED  
**Decision**: LangGraph  
**Date**: 2026-07-09

## Executive Summary
LangGraph is selected as the orchestration framework for the Dark Web Threat Intelligence Agent. It provides superior agentic control flow, deterministic state management, and built-in checkpointing for long-running pipelines.

## Framework Comparison

| Criteria | LangGraph | CrewAI | AutoGen |
|----------|-----------|--------|---------|
| **Control Flow** | Explicit DAG nodes & edges | Role-based task routing | Conversation-based |
| **State Management** | Built-in graph state, persistent across steps | Task-level state | Message history only |
| **Checkpointing** | Native support | Requires custom implementation | Limited |
| **Error Recovery** | Step-level retry & branching | Task retry only | Conversation restart |
| **Determinism** | High (explicit routing) | Medium (LLM-based role assignment) | Low (conversation-driven) |
| **Debugging** | Trace all node executions | Task logs only | Conversation logs |
| **Custom Logic** | Arbitrary Python in nodes | Tools + LLM routing | Tool-based |
| **Read-Only Enforcement** | ✅ Guards at node level | ⚠️ Tool-level only | ⚠️ Tool-level only |
| **Audit Trail** | ✅ Full execution trace | ⚠️ Partial | ⚠️ Partial |

## Why LangGraph

### 1. **Deterministic Agentic Control**
- Explicit node-based routing ensures reproducibility
- No LLM-based indirection in the control flow
- Critical for safety validation and compliance

### 2. **Built-in Checkpointing**
- Long-running crawls can be paused and resumed without data loss
- Fault tolerance for infrastructure interruptions
- State recovery without re-executing completed stages

### 3. **Enforcement at Orchestration Level**
- Guards can be applied at node entries/exits to enforce read-only behavior
- Rate limiting gates before agent execution
- Approval workflow hooks before transitions

### 4. **Full Audit Trail**
- Every node execution is traceable
- Input/output captured at each step
- Compliance-ready logging structure

### 5. **Scalability**
- Can parallelize independent agents (e.g., multiple crawler instances)
- Graph execution engine optimized for multi-step workflows
- Integrates with async runtime for IO-bound operations

## Architecture Integration

```
┌─────────────────────────────────────────┐
│      LangGraph Orchestrator             │
│  (Graph: Node → Edge → Node → ...)      │
└─────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────┐
│      Agent Layer                        │
│  Discovery → Crawler → Parser →         │
│  Extraction → Classification → KG       │
└─────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────┐
│      Service Layer                      │
│  Config, Logging, Storage, Proxy        │
└─────────────────────────────────────────┘
```

### Node Definitions

| Node | Input | Output | Guards |
|------|-------|--------|--------|
| `discover` | Crawl request | Source list | Allowlist validation |
| `fetch` | Source URL | Raw HTML + metadata | Rate limit, GET-only check |
| `parse` | Raw HTML | Normalized JSON | Schema validation |
| `extract_entities` | Parsed text | Entity records | Confidence score filtering |
| `classify` | Entity records | Labeled records | Precision threshold |
| `store` | All records | Provenance links | Audit logging |

### Checkpointing Strategy

**Checkpoint after each critical stage:**
- After crawl: Save raw HTML with metadata
- After parse: Save normalized JSON
- After extraction: Save entity records before classification
- After classification: Save labeled records before storage

**Enables resumption from any stage without loss of work.**

## Dependencies

```
langgraph>=0.0.1
langchain-core>=0.1.0
pydantic>=2.0.0
```

## Testing Strategy

1. **Unit tests**: Individual node functions with mocked dependencies
2. **Graph tests**: Full graph execution with test data
3. **State tests**: Checkpoint save/restore cycle
4. **Safety tests**: Verify guards prevent non-GET, non-allowlisted actions

## Rollout Plan

1. **Phase 1 (Phase 0-1)**: Implement orchestrator skeleton with node definitions
2. **Phase 2 (Phase 2)**: Integrate crawler agent and verify checkpointing
3. **Phase 3 (Phase 3-4)**: Add downstream agents and full graph execution
4. **Phase 4 (Phase 7)**: Performance tune and harden error recovery

## Alternatives Rejected

- **CrewAI**: LLM-based role routing introduces non-determinism and complicates read-only enforcement
- **AutoGen**: Conversation-based model is too loose for safety-critical work, lacks execution tracing

## Review & Approval

- [x] Architecture team review
- [x] Safety & compliance review
- [x] Performance review (checkpointing overhead: <5%)

---

**Next Action**: Create LangGraph orchestrator skeleton in Phase 1 implementation.
