"""
Agent Interface Definitions for Dark Web Threat Intelligence System.

Each agent has a defined input contract, output contract, and error handling strategy.
All agents inherit from AgentInterface base class.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Generic, TypeVar
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum


# ============================================================================
# Common Enums and Base Models
# ============================================================================

class AgentStatus(str, Enum):
    """Agent execution status."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    RETRYING = "retrying"


class AgentResult(BaseModel):
    """Base result schema for all agent outputs."""
    status: AgentStatus
    agent_id: str
    execution_time_ms: float
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    error_message: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3


InputType = TypeVar('InputType')
OutputType = TypeVar('OutputType')


# ============================================================================
# Base Agent Interface
# ============================================================================

class AgentInterface(ABC, Generic[InputType, OutputType]):
    """
    Abstract base class for all agents.
    
    Provides:
    - Input validation
    - Execution context
    - Error handling with retries
    - Audit logging interface
    - Result tracking
    """
    
    def __init__(self, agent_id: str, max_retries: int = 3):
        self.agent_id = agent_id
        self.max_retries = max_retries
        self.execution_count = 0
        self.last_error = None
        self.created_at = datetime.utcnow()
    
    @abstractmethod
    def validate_input(self, input_data: InputType) -> bool:
        """
        Validate that input_data conforms to expected schema.
        
        Args:
            input_data: Input to validate
        
        Returns:
            True if valid, False otherwise
        
        Raises:
            ValueError: If validation fails
        """
        pass
    
    @abstractmethod
    async def execute(self, input_data: InputType) -> OutputType:
        """
        Execute the agent's core logic.
        
        Args:
            input_data: Validated input data
        
        Returns:
            Output result
        
        Raises:
            Exception: On execution error
        """
        pass
    
    @abstractmethod
    def validate_output(self, output_data: OutputType) -> bool:
        """
        Validate that output_data conforms to expected schema.
        
        Args:
            output_data: Output to validate
        
        Returns:
            True if valid, False otherwise
        
        Raises:
            ValueError: If validation fails
        """
        pass
    
    async def run(self, input_data: InputType) -> AgentResult:
        """
        Run agent with retry logic and error handling.
        
        Args:
            input_data: Input data for execution
        
        Returns:
            AgentResult with status and metadata
        """
        self.execution_count += 1
        retry_count = 0
        start_time = datetime.utcnow()
        
        while retry_count <= self.max_retries:
            try:
                # Validate input
                if not self.validate_input(input_data):
                    raise ValueError("Input validation failed")
                
                # Execute
                output = await self.execute(input_data)
                
                # Validate output
                if not self.validate_output(output):
                    raise ValueError("Output validation failed")
                
                execution_time_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
                
                return AgentResult(
                    status=AgentStatus.SUCCESS,
                    agent_id=self.agent_id,
                    execution_time_ms=execution_time_ms,
                    retry_count=retry_count,
                    max_retries=self.max_retries,
                )
            
            except Exception as e:
                self.last_error = str(e)
                retry_count += 1
                
                if retry_count > self.max_retries:
                    execution_time_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
                    return AgentResult(
                        status=AgentStatus.FAILED,
                        agent_id=self.agent_id,
                        execution_time_ms=execution_time_ms,
                        error_message=self.last_error,
                        retry_count=retry_count - 1,
                        max_retries=self.max_retries,
                    )
        
        raise RuntimeError(f"Agent {self.agent_id} exhausted retries")


# ============================================================================
# 1. Discovery Agent Interface
# ============================================================================

class DiscoveryAgentInput(BaseModel):
    """Input for DiscoveryAgent."""
    filter_by_category: Optional[str] = None
    include_inactive: bool = False


class DiscoveryAgentOutput(BaseModel):
    """Output from DiscoveryAgent."""
    sources: List[Dict[str, Any]] = Field(default_factory=list)
    total_count: int = 0
    filtered_count: int = 0


class DiscoveryAgent(AgentInterface[DiscoveryAgentInput, DiscoveryAgentOutput]):
    """
    Discovery Agent: Returns list of approved sources from allowlist.
    
    Contract:
    - Input: Filtering criteria (optional)
    - Output: List of approved source URLs and metadata
    - Constraints: Read-only from allowlist service
    - No side effects
    """
    
    def validate_input(self, input_data: DiscoveryAgentInput) -> bool:
        """Validate discovery agent input."""
        return isinstance(input_data, DiscoveryAgentInput)
    
    async def execute(self, input_data: DiscoveryAgentInput) -> DiscoveryAgentOutput:
        """Query approved sources."""
        # TODO: Call AllowlistService to get approved sources
        return DiscoveryAgentOutput()
    
    def validate_output(self, output_data: DiscoveryAgentOutput) -> bool:
        """Validate discovery agent output."""
        return isinstance(output_data, DiscoveryAgentOutput)


# ============================================================================
# 2. Crawler Agent Interface
# ============================================================================

class CrawlerAgentInput(BaseModel):
    """Input for CrawlerAgent."""
    urls: List[str]
    follow_links: bool = False
    timeout_seconds: int = 30


class CrawlerAgentOutput(BaseModel):
    """Output from CrawlerAgent."""
    fetched_pages: List[Dict[str, Any]] = Field(default_factory=list)
    failed_urls: List[str] = Field(default_factory=list)
    total_fetched: int = 0
    total_failed: int = 0


class CrawlerAgent(AgentInterface[CrawlerAgentInput, CrawlerAgentOutput]):
    """
    Crawler Agent: Fetches pages using read-only HTTP GET.
    
    Contract:
    - Input: List of approved URLs
    - Output: RawPage objects with metadata
    - Constraints: GET-only, no forms, no login, rate limited, timeout enforced
    - No mutations on remote servers
    """
    
    def validate_input(self, input_data: CrawlerAgentInput) -> bool:
        """Validate crawler agent input."""
        if not isinstance(input_data, CrawlerAgentInput):
            return False
        if not input_data.urls:
            return False
        return len(input_data.urls) <= 1000  # Batch size limit
    
    async def execute(self, input_data: CrawlerAgentInput) -> CrawlerAgentOutput:
        """Fetch URLs via SOCKS5 proxy."""
        # TODO: Call CrawlerService to fetch pages
        return CrawlerAgentOutput()
    
    def validate_output(self, output_data: CrawlerAgentOutput) -> bool:
        """Validate crawler agent output."""
        return isinstance(output_data, CrawlerAgentOutput)


# ============================================================================
# 3. Parser Agent Interface
# ============================================================================

class ParserAgentInput(BaseModel):
    """Input for ParserAgent."""
    raw_pages: List[Dict[str, Any]]
    extract_links: bool = True
    extract_text: bool = True


class ParserAgentOutput(BaseModel):
    """Output from ParserAgent."""
    parsed_documents: List[Dict[str, Any]] = Field(default_factory=list)
    parsing_errors: List[Dict[str, Any]] = Field(default_factory=list)
    total_parsed: int = 0
    total_errors: int = 0


class ParserAgent(AgentInterface[ParserAgentInput, ParserAgentOutput]):
    """
    Parser Agent: Converts raw HTML to normalized ParsedDocument.
    
    Contract:
    - Input: RawPage objects
    - Output: ParsedDocument objects (text, links, metadata)
    - Constraints: Deterministic parsing, schema-valid output
    - Handles: HTML, PDF, OCR (where needed)
    """
    
    def validate_input(self, input_data: ParserAgentInput) -> bool:
        """Validate parser agent input."""
        if not isinstance(input_data, ParserAgentInput):
            return False
        return len(input_data.raw_pages) > 0
    
    async def execute(self, input_data: ParserAgentInput) -> ParserAgentOutput:
        """Parse HTML to normalized documents."""
        # TODO: Call ParserService to parse pages
        return ParserAgentOutput()
    
    def validate_output(self, output_data: ParserAgentOutput) -> bool:
        """Validate parser agent output."""
        return isinstance(output_data, ParserAgentOutput)


# ============================================================================
# 4. Entity Extraction Agent Interface
# ============================================================================

class EntityExtractionAgentInput(BaseModel):
    """Input for EntityExtractionAgent."""
    documents: List[Dict[str, Any]]
    entity_types: List[str] = Field(default_factory=lambda: [
        "organization", "malware", "ransomware_group", "cve",
        "cryptocurrency_address", "email", "username", "software"
    ])


class EntityExtractionAgentOutput(BaseModel):
    """Output from EntityExtractionAgent."""
    entities: List[Dict[str, Any]] = Field(default_factory=list)
    total_entities: int = 0
    entities_by_type: Dict[str, int] = Field(default_factory=dict)


class EntityExtractionAgent(AgentInterface[EntityExtractionAgentInput, EntityExtractionAgentOutput]):
    """
    Entity Extraction Agent: Uses NER and LLM to extract structured entities.
    
    Contract:
    - Input: ParsedDocument objects
    - Output: Entity objects with type, value, confidence
    - Constraints: Schema-valid, deduplicated, linked to source
    - Handles: Organizations, malware, ransomware, CVE, crypto, email, username, software
    """
    
    def validate_input(self, input_data: EntityExtractionAgentInput) -> bool:
        """Validate entity extraction input."""
        if not isinstance(input_data, EntityExtractionAgentInput):
            return False
        return len(input_data.documents) > 0
    
    async def execute(self, input_data: EntityExtractionAgentInput) -> EntityExtractionAgentOutput:
        """Extract entities from documents."""
        # TODO: Call EntityExtractionService to extract entities
        return EntityExtractionAgentOutput()
    
    def validate_output(self, output_data: EntityExtractionAgentOutput) -> bool:
        """Validate entity extraction output."""
        return isinstance(output_data, EntityExtractionAgentOutput)


# ============================================================================
# 5. Classification Agent Interface
# ============================================================================

class ClassificationAgentInput(BaseModel):
    """Input for ClassificationAgent."""
    documents: List[Dict[str, Any]]
    classification_types: List[str] = Field(default_factory=lambda: [
        "malware", "leak", "forum", "research", "news", "marketplace"
    ])


class ClassificationAgentOutput(BaseModel):
    """Output from ClassificationAgent."""
    classifications: List[Dict[str, Any]] = Field(default_factory=list)
    total_classified: int = 0
    classifications_by_type: Dict[str, int] = Field(default_factory=dict)


class ClassificationAgent(AgentInterface[ClassificationAgentInput, ClassificationAgentOutput]):
    """
    Classification Agent: Categorizes content into threat types.
    
    Contract:
    - Input: ParsedDocument objects
    - Output: Classification objects with label, confidence, evidence
    - Constraints: Reproducible, auditable, precision-tracked
    - Types: Malware, Leak, Forum, Research, News, Marketplace
    """
    
    def validate_input(self, input_data: ClassificationAgentInput) -> bool:
        """Validate classification input."""
        if not isinstance(input_data, ClassificationAgentInput):
            return False
        return len(input_data.documents) > 0
    
    async def execute(self, input_data: ClassificationAgentInput) -> ClassificationAgentOutput:
        """Classify documents."""
        # TODO: Call ClassificationService to classify content
        return ClassificationAgentOutput()
    
    def validate_output(self, output_data: ClassificationAgentOutput) -> bool:
        """Validate classification output."""
        return isinstance(output_data, ClassificationAgentOutput)


# ============================================================================
# 6. Knowledge Graph Agent Interface
# ============================================================================

class KnowledgeGraphAgentInput(BaseModel):
    """Input for KnowledgeGraphAgent."""
    entities: List[Dict[str, Any]]
    classifications: List[Dict[str, Any]]
    build_relationships: bool = True


class KnowledgeGraphAgentOutput(BaseModel):
    """Output from KnowledgeGraphAgent."""
    relationships: List[Dict[str, Any]] = Field(default_factory=list)
    graph_nodes: int = 0
    graph_edges: int = 0


class KnowledgeGraphAgent(AgentInterface[KnowledgeGraphAgentInput, KnowledgeGraphAgentOutput]):
    """
    Knowledge Graph Agent: Builds relationship graphs between entities.
    
    Contract:
    - Input: Entity and Classification objects
    - Output: Relationship objects with source, target, type, weight
    - Constraints: Neo4j schema-valid, provenance-linked
    - Handles: Co-occurrence, temporal, categorical relationships
    """
    
    def validate_input(self, input_data: KnowledgeGraphAgentInput) -> bool:
        """Validate knowledge graph input."""
        if not isinstance(input_data, KnowledgeGraphAgentInput):
            return False
        return len(input_data.entities) > 0
    
    async def execute(self, input_data: KnowledgeGraphAgentInput) -> KnowledgeGraphAgentOutput:
        """Build knowledge graph."""
        # TODO: Call KnowledgeGraphService to build relationships
        return KnowledgeGraphAgentOutput()
    
    def validate_output(self, output_data: KnowledgeGraphAgentOutput) -> bool:
        """Validate knowledge graph output."""
        return isinstance(output_data, KnowledgeGraphAgentOutput)


# ============================================================================
# 7. Reporting Agent Interface
# ============================================================================

class ReportingAgentInput(BaseModel):
    """Input for ReportingAgent."""
    entities: List[Dict[str, Any]]
    classifications: List[Dict[str, Any]]
    relationships: List[Dict[str, Any]]
    report_type: str = "daily"  # daily, weekly, on-demand
    include_trends: bool = True


class ReportingAgentOutput(BaseModel):
    """Output from ReportingAgent."""
    reports: List[Dict[str, Any]] = Field(default_factory=list)
    total_reports: int = 0
    report_size_bytes: int = 0


class ReportingAgent(AgentInterface[ReportingAgentInput, ReportingAgentOutput]):
    """
    Reporting Agent: Generates operational reports for analysts.
    
    Contract:
    - Input: All collected intelligence (entities, classifications, relationships)
    - Output: Report objects (PDF, JSON, HTML)
    - Constraints: Timely generation, analyst-ready summaries
    - Handles: Daily reports, trends, alerts, evidence trails
    """
    
    def validate_input(self, input_data: ReportingAgentInput) -> bool:
        """Validate reporting input."""
        if not isinstance(input_data, ReportingAgentInput):
            return False
        return len(input_data.entities) > 0
    
    async def execute(self, input_data: ReportingAgentInput) -> ReportingAgentOutput:
        """Generate reports."""
        # TODO: Call ReportingService to generate reports
        return ReportingAgentOutput()
    
    def validate_output(self, output_data: ReportingAgentOutput) -> bool:
        """Validate reporting output."""
        return isinstance(output_data, ReportingAgentOutput)


# ============================================================================
# Agent Registry
# ============================================================================

AGENT_REGISTRY = {
    "discovery": DiscoveryAgent,
    "crawler": CrawlerAgent,
    "parser": ParserAgent,
    "entity_extraction": EntityExtractionAgent,
    "classification": ClassificationAgent,
    "knowledge_graph": KnowledgeGraphAgent,
    "reporting": ReportingAgent,
}


def create_agent(agent_type: str, agent_id: str, **kwargs) -> AgentInterface:
    """
    Factory function to create agents by type.
    
    Args:
        agent_type: Type of agent to create
        agent_id: Unique ID for this agent instance
        **kwargs: Additional arguments to pass to agent constructor
    
    Returns:
        AgentInterface instance
    
    Raises:
        ValueError: If agent_type is not registered
    """
    if agent_type not in AGENT_REGISTRY:
        raise ValueError(f"Unknown agent type: {agent_type}")
    
    agent_class = AGENT_REGISTRY[agent_type]
    return agent_class(agent_id=agent_id, **kwargs)
