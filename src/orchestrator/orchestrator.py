"""
Orchestrator Service for Dark Web Threat Intelligence System.

Main coordinator that:
- Manages dependency injection
- Routes work through pipeline
- Coordinates service calls
- Handles error recovery
- Maintains audit trail
- Tracks job execution
"""

from typing import Dict, Any, List, Optional, Callable
from datetime import datetime
import asyncio
import traceback
import logging

from src.orchestrator.graph import OrchestrationGraph, ExecutionState, NodeName
from src.agents.interfaces import (
    AgentInterface, DiscoveryAgent, CrawlerAgent, ParserAgent,
    EntityExtractionAgent, ClassificationAgent, KnowledgeGraphAgent,
    ReportingAgent, AgentResult, AgentStatus
)
from src.services.audit import AuditService, AuditSeverity, AuditActionType
from src.services.crawler import CrawlerService
from src.services.parser import ParserService
from src.services.job_tracker import JobTracker, JobStatus


logger = logging.getLogger(__name__)


# ============================================================================
# Service Container (Dependency Injection)
# ============================================================================

class ServiceContainer:
    """
    Manages all service instances.
    
    Provides:
    - Centralized service initialization
    - Dependency injection
    - Service lifecycle management
    """
    
    def __init__(self):
        self.services: Dict[str, Any] = {}
        self.agents: Dict[str, AgentInterface] = {}
        self.initialized = False
    
    def register_service(self, service_name: str, service: Any) -> None:
        """Register a service instance."""
        self.services[service_name] = service
        logger.info(f"Registered service: {service_name}")
    
    def get_service(self, service_name: str) -> Optional[Any]:
        """Get registered service."""
        return self.services.get(service_name)
    
    def register_agent(self, agent_name: str, agent: AgentInterface) -> None:
        """Register an agent."""
        self.agents[agent_name] = agent
        logger.info(f"Registered agent: {agent_name}")
    
    def get_agent(self, agent_name: str) -> Optional[AgentInterface]:
        """Get registered agent."""
        return self.agents.get(agent_name)
    
    def initialize_default_agents(self) -> None:
        """Initialize all default agents."""
        self.agents = {
            "discovery": DiscoveryAgent(agent_id="discovery_agent_001"),
            "crawler": CrawlerAgent(agent_id="crawler_agent_001"),
            "parser": ParserAgent(agent_id="parser_agent_001"),
            "entity_extraction": EntityExtractionAgent(agent_id="entity_extraction_agent_001"),
            "classification": ClassificationAgent(agent_id="classification_agent_001"),
            "knowledge_graph": KnowledgeGraphAgent(agent_id="knowledge_graph_agent_001"),
            "reporting": ReportingAgent(agent_id="reporting_agent_001"),
        }
        if "crawler_service" not in self.services:
            self.services["crawler_service"] = CrawlerService()
        if "parser_service" not in self.services:
            self.services["parser_service"] = ParserService()
        self.initialized = True
        logger.info("Initialized all default agents")


# ============================================================================
# Orchestrator Service
# ============================================================================

class OrchestratorService:
    """
    Main orchestrator service that coordinates the entire workflow.
    
    Responsibilities:
    - Service dependency injection
    - Workflow execution and routing
    - Agent coordination
    - Error handling and recovery
    - Audit trail maintenance
    - Job tracking
    """
    
    def __init__(self, 
                 service_container: Optional[ServiceContainer] = None,
                 audit_service: Optional[AuditService] = None,
                 job_tracker: Optional[JobTracker] = None):
        """
        Initialize orchestrator.
        
        Args:
            service_container: Service container (created if not provided)
            audit_service: Audit service (created if not provided)
            job_tracker: Job tracker (created if not provided)
        """
        self.service_container = service_container or ServiceContainer()
        self.audit_service = audit_service or AuditService()
        self.job_tracker = job_tracker or JobTracker()
        self.graph = OrchestrationGraph()
        
        # Initialize default agents if container not initialized
        if not self.service_container.initialized:
            self.service_container.initialize_default_agents()
        
        logger.info("Orchestrator service initialized")
    
    async def execute_workflow(self, input_data: Dict[str, Any],
                              tags: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Execute a complete workflow.
        
        Args:
            input_data: Initial state for workflow
            tags: Optional tags for tracking
        
        Returns:
            Workflow result
        """
        workflow_id = self._generate_workflow_id()
        job_id = None
        
        try:
            # Create job
            job_id = await self.job_tracker.create_job(
                workflow_id=workflow_id,
                input_data=input_data,
                tags=tags or []
            )
            
            # Log workflow start
            await self.audit_service.log_workflow_start(workflow_id, input_data)
            
            # Start job
            await self.job_tracker.start_job(job_id)
            
            # Execute workflow through graph
            execution_state = await self._execute_graph(workflow_id, input_data)
            
            # Log workflow end (success)
            await self.audit_service.log_workflow_end(
                workflow_id,
                execution_state.state_data,
                success=True
            )
            
            # Complete job
            await self.job_tracker.complete_job(
                job_id,
                success=True,
                result_data=execution_state.state_data
            )
            
            return {
                "workflow_id": workflow_id,
                "job_id": job_id,
                "status": "success",
                "data": execution_state.state_data,
                "completed_nodes": execution_state.completed_nodes,
                "checkpoints": len(execution_state.checkpoints),
            }
        
        except Exception as e:
            error_msg = str(e)
            error_trace = traceback.format_exc()
            
            # Log error
            await self.audit_service.log_error(workflow_id, None, error_msg, error_trace)
            
            # Complete job with error
            if job_id:
                await self.job_tracker.complete_job(
                    job_id,
                    success=False,
                    error_message=error_msg,
                    error_trace=error_trace
                )
            
            logger.error(f"Workflow {workflow_id} failed: {error_msg}")
            
            raise
    
    async def _execute_graph(self, workflow_id: str, 
                            input_data: Dict[str, Any]) -> ExecutionState:
        """
        Execute the orchestration graph.
        
        Args:
            workflow_id: Workflow identifier
            input_data: Initial state
        
        Returns:
            ExecutionState with results
        """
        state = ExecutionState()
        state.state_data = input_data
        state.workflow_id = workflow_id
        
        current_node = NodeName.DISCOVER
        
        while current_node:
            try:
                # Log node entry
                await self.audit_service.log_node_enter(workflow_id, current_node)
                
                state.enter_node(current_node)
                
                # Execute node with timing
                start_time = datetime.utcnow()
                output = await self._execute_node(current_node, state)
                duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
                
                # Save checkpoint
                state.save_checkpoint(current_node, output)
                state.state_data.update(output)
                
                # Log node exit (success)
                await self.audit_service.log_node_exit(
                    workflow_id,
                    current_node,
                    success=True,
                    duration_ms=duration_ms
                )
                
                # Find next node
                next_node = self._find_next_node(current_node)
                state.exit_node(current_node, success=True)
                current_node = next_node
                
            except Exception as e:
                error_msg = str(e)
                error_trace = traceback.format_exc()
                
                state.record_error(current_node, error_msg)
                state.exit_node(current_node, success=False)
                
                # Log node exit (failure)
                await self.audit_service.log_node_exit(
                    workflow_id,
                    current_node,
                    success=False,
                    error=error_msg
                )
                
                logger.error(f"Node {current_node} failed: {error_msg}")
                raise
        
        return state
    
    async def _execute_node(self, node_name: str, state: ExecutionState) -> Dict[str, Any]:
        """
        Execute a single graph node.
        
        Args:
            node_name: Name of node to execute
            state: Current execution state
        
        Returns:
            Node output
        """
        if node_name == NodeName.DISCOVER:
            return await self._node_discover(state)
        elif node_name == NodeName.FETCH:
            return await self._node_fetch(state)
        elif node_name == NodeName.PARSE:
            return await self._node_parse(state)
        elif node_name == NodeName.EXTRACT_ENTITIES:
            return await self._node_extract_entities(state)
        elif node_name == NodeName.CLASSIFY:
            return await self._node_classify(state)
        elif node_name == NodeName.STORE:
            return await self._node_store(state)
        elif node_name == NodeName.REPORT:
            return await self._node_report(state)
        else:
            raise ValueError(f"Unknown node: {node_name}")
    
    # ========================================================================
    # Node Implementations
    # ========================================================================
    
    async def _node_discover(self, state: ExecutionState) -> Dict[str, Any]:
        """Execute Discovery node: Get approved sources."""
        agent = self.service_container.get_agent("discovery")
        if not agent:
            raise RuntimeError("Discovery agent not initialized")
        
        agent_result = await agent.run(None)  # No input needed
        
        return {
            "discovered_sources": [],
            "discovery_timestamp": datetime.utcnow().isoformat(),
            "agent_result": agent_result.dict(),
        }
    
    async def _node_fetch(self, state: ExecutionState) -> Dict[str, Any]:
        """Execute Fetch node: Crawl approved sources."""
        crawler_service = self.service_container.get_service("crawler_service")
        if not crawler_service:
            raise RuntimeError("Crawler service not initialized")

        discovered_sources = state.state_data.get("discovered_sources", [])
        urls = []
        for source in discovered_sources:
            if isinstance(source, dict):
                url = source.get("url")
                if url:
                    urls.append(url)
            else:
                urls.append(str(source))

        raw_pages = crawler_service.fetch_batch(urls) if urls else []

        return {
            "raw_pages": [page.dict() for page in raw_pages],
            "fetch_timestamp": datetime.utcnow().isoformat(),
        }
    
    async def _node_parse(self, state: ExecutionState) -> Dict[str, Any]:
        """Execute Parse node: Parse HTML to documents."""
        parser_service = self.service_container.get_service("parser_service")
        if not parser_service:
            raise RuntimeError("Parser service not initialized")

        raw_pages = state.state_data.get("raw_pages", [])
        parsed_documents = parser_service.parse_raw_pages(raw_pages) if raw_pages else []

        return {
            "parsed_documents": [document.model_dump() for document in parsed_documents],
            "parse_timestamp": datetime.utcnow().isoformat(),
        }
    
    async def _node_extract_entities(self, state: ExecutionState) -> Dict[str, Any]:
        """Execute Entity Extraction node."""
        agent = self.service_container.get_agent("entity_extraction")
        if not agent:
            raise RuntimeError("Entity extraction agent not initialized")
        
        agent_result = await agent.run(None)  # Input from state
        
        return {
            "entities": [],
            "extraction_timestamp": datetime.utcnow().isoformat(),
            "agent_result": agent_result.dict(),
        }
    
    async def _node_classify(self, state: ExecutionState) -> Dict[str, Any]:
        """Execute Classification node."""
        agent = self.service_container.get_agent("classification")
        if not agent:
            raise RuntimeError("Classification agent not initialized")
        
        agent_result = await agent.run(None)  # Input from state
        
        return {
            "classifications": [],
            "classification_timestamp": datetime.utcnow().isoformat(),
            "agent_result": agent_result.dict(),
        }
    
    async def _node_store(self, state: ExecutionState) -> Dict[str, Any]:
        """Execute Storage node."""
        # This node doesn't use an agent, it directly calls storage
        return {
            "stored_records": 0,
            "storage_timestamp": datetime.utcnow().isoformat(),
        }
    
    async def _node_report(self, state: ExecutionState) -> Dict[str, Any]:
        """Execute Reporting node."""
        agent = self.service_container.get_agent("reporting")
        if not agent:
            raise RuntimeError("Reporting agent not initialized")
        
        agent_result = await agent.run(None)  # Input from state
        
        return {
            "reports_generated": 0,
            "report_timestamp": datetime.utcnow().isoformat(),
            "agent_result": agent_result.dict(),
        }
    
    # ========================================================================
    # Utility Methods
    # ========================================================================
    
    def _find_next_node(self, current_node: str) -> Optional[str]:
        """Find next node in graph."""
        node_sequence = [
            NodeName.DISCOVER,
            NodeName.FETCH,
            NodeName.PARSE,
            NodeName.EXTRACT_ENTITIES,
            NodeName.CLASSIFY,
            NodeName.STORE,
            NodeName.REPORT,
        ]
        
        try:
            current_idx = node_sequence.index(current_node)
            if current_idx < len(node_sequence) - 1:
                return node_sequence[current_idx + 1]
        except ValueError:
            pass
        
        return None
    
    def _generate_workflow_id(self) -> str:
        """Generate unique workflow ID."""
        import uuid
        return f"workflow_{uuid.uuid4().hex[:12]}"
    
    async def get_workflow_audit_trail(self, workflow_id: str) -> List[Dict[str, Any]]:
        """Get complete audit trail for workflow."""
        audit_logs = await self.audit_service.get_workflow_audit_trail(workflow_id)
        return [log.dict() for log in audit_logs]
    
    async def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get job status and result."""
        job = await self.job_tracker.get_job(job_id)
        if job:
            return job.dict()
        
        result = await self.job_tracker.get_job_result(job_id)
        if result:
            return result.dict()
        
        return None
    
    async def list_recent_jobs(self, limit: int = 100) -> List[Dict[str, Any]]:
        """List recent job results."""
        results = await self.job_tracker.list_recent_results(limit=limit)
        return [r.dict() for r in results]
