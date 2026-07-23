"""
Audit Logging Service for Dark Web Threat Intelligence System.

Provides:
- Immutable action logging
- Comprehensive audit trails
- Query and retrieval
- Retention policy enforcement
"""

from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from datetime import datetime, timedelta
from enum import Enum
import json
from abc import ABC, abstractmethod


# ============================================================================
# Audit Log Models
# ============================================================================

class AuditActionType(str, Enum):
    """Types of auditable actions."""
    WORKFLOW_START = "workflow_start"
    WORKFLOW_END = "workflow_end"
    NODE_ENTER = "node_enter"
    NODE_EXIT = "node_exit"
    AGENT_EXECUTE = "agent_execute"
    CONFIG_CHANGE = "config_change"
    CONFIG_APPROVE = "config_approve"
    DATA_STORE = "data_store"
    DATA_RETRIEVE = "data_retrieve"
    ERROR_OCCURRED = "error_occurred"
    CHECKPOINT_SAVE = "checkpoint_save"
    GUARD_CHECK = "guard_check"


class AuditSeverity(str, Enum):
    """Severity levels for audit events."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AuditLog(BaseModel):
    """Single audit log entry."""
    audit_id: str = Field(..., description="Unique audit entry ID")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="When event occurred")
    action_type: AuditActionType = Field(..., description="Type of action")
    severity: AuditSeverity = Field(default=AuditSeverity.INFO, description="Severity level")
    
    # Context
    workflow_id: Optional[str] = Field(None, description="Associated workflow ID")
    agent_id: Optional[str] = Field(None, description="Associated agent ID")
    node_name: Optional[str] = Field(None, description="Associated graph node")
    
    # User/System
    actor: str = Field(default="system", description="Who/what triggered action")
    actor_type: str = Field(default="system", description="Type of actor (user, agent, system)")
    
    # Action details
    action_details: Dict[str, Any] = Field(default_factory=dict, description="Detailed action data")
    input_data: Optional[Dict[str, Any]] = Field(None, description="Input to action")
    output_data: Optional[Dict[str, Any]] = Field(None, description="Output from action")
    
    # Status
    status: str = Field(default="success", description="Action outcome (success, failed, partial)")
    error_message: Optional[str] = Field(None, description="Error if status is failed")
    error_trace: Optional[str] = Field(None, description="Stack trace if available")
    
    # Metadata
    duration_ms: Optional[float] = Field(None, description="Action duration in milliseconds")
    tags: List[str] = Field(default_factory=list, description="Custom tags for filtering")
    
    class Config:
        use_enum_values = True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        data = self.dict()
        data['timestamp'] = self.timestamp.isoformat()
        return data


# ============================================================================
# Audit Log Storage Interface
# ============================================================================

class AuditStorage(ABC):
    """Abstract base for audit log storage."""
    
    @abstractmethod
    async def write(self, log: AuditLog) -> str:
        """
        Write audit log entry.
        
        Args:
            log: AuditLog entry
        
        Returns:
            audit_id of written entry
        """
        pass
    
    @abstractmethod
    async def read(self, audit_id: str) -> Optional[AuditLog]:
        """
        Read specific audit log entry.
        
        Args:
            audit_id: ID of audit entry to retrieve
        
        Returns:
            AuditLog or None if not found
        """
        pass
    
    @abstractmethod
    async def query(self, 
                   workflow_id: Optional[str] = None,
                   agent_id: Optional[str] = None,
                   action_type: Optional[AuditActionType] = None,
                   start_time: Optional[datetime] = None,
                   end_time: Optional[datetime] = None,
                   limit: int = 1000) -> List[AuditLog]:
        """
        Query audit logs with filters.
        
        Args:
            workflow_id: Filter by workflow
            agent_id: Filter by agent
            action_type: Filter by action type
            start_time: Query from this time
            end_time: Query until this time
            limit: Maximum results to return
        
        Returns:
            List of matching AuditLog entries
        """
        pass
    
    @abstractmethod
    async def cleanup_old_logs(self, retention_days: int = 90) -> int:
        """
        Remove logs older than retention period.
        
        Args:
            retention_days: Keep logs newer than this
        
        Returns:
            Number of logs deleted
        """
        pass


# ============================================================================
# In-Memory Audit Storage (for Phase 1)
# ============================================================================

class InMemoryAuditStorage(AuditStorage):
    """Simple in-memory audit storage for testing."""
    
    def __init__(self):
        self.logs: Dict[str, AuditLog] = {}
        self.log_counter = 0
    
    async def write(self, log: AuditLog) -> str:
        """Write audit log."""
        if not log.audit_id or log.audit_id == "":
            self.log_counter += 1
            log.audit_id = f"audit_{self.log_counter:010d}"
        
        self.logs[log.audit_id] = log
        return log.audit_id
    
    async def read(self, audit_id: str) -> Optional[AuditLog]:
        """Read audit log."""
        return self.logs.get(audit_id)
    
    async def query(self,
                   workflow_id: Optional[str] = None,
                   agent_id: Optional[str] = None,
                   action_type: Optional[AuditActionType] = None,
                   start_time: Optional[datetime] = None,
                   end_time: Optional[datetime] = None,
                   limit: int = 1000) -> List[AuditLog]:
        """Query audit logs."""
        results = list(self.logs.values())
        
        if workflow_id:
            results = [l for l in results if l.workflow_id == workflow_id]
        if agent_id:
            results = [l for l in results if l.agent_id == agent_id]
        if action_type:
            results = [l for l in results if l.action_type == action_type]
        if start_time:
            results = [l for l in results if l.timestamp >= start_time]
        if end_time:
            results = [l for l in results if l.timestamp <= end_time]
        
        # Sort by timestamp, newest first
        results.sort(key=lambda l: l.timestamp, reverse=True)
        
        return results[:limit]
    
    async def cleanup_old_logs(self, retention_days: int = 90) -> int:
        """Remove old logs."""
        cutoff_time = datetime.utcnow() - timedelta(days=retention_days)
        
        to_delete = [
            audit_id for audit_id, log in self.logs.items()
            if log.timestamp < cutoff_time
        ]
        
        for audit_id in to_delete:
            del self.logs[audit_id]
        
        return len(to_delete)
    
    def get_all_logs(self) -> List[AuditLog]:
        """Get all logs (for testing)."""
        return sorted(self.logs.values(), key=lambda l: l.timestamp)


# ============================================================================
# Audit Service
# ============================================================================

class AuditService:
    """Main service for audit logging operations."""
    
    def __init__(self, storage: Optional[AuditStorage] = None):
        self.storage = storage or InMemoryAuditStorage()
    
    async def log_workflow_start(self, workflow_id: str, initial_state: Dict[str, Any]) -> str:
        """Log workflow start."""
        log = AuditLog(
            audit_id="",
            action_type=AuditActionType.WORKFLOW_START,
            workflow_id=workflow_id,
            action_details={"initial_state_keys": list(initial_state.keys())},
            tags=["workflow"],
        )
        return await self.storage.write(log)
    
    async def log_workflow_end(self, workflow_id: str, final_state: Dict[str, Any], 
                              success: bool = True, error: Optional[str] = None) -> str:
        """Log workflow completion."""
        log = AuditLog(
            audit_id="",
            action_type=AuditActionType.WORKFLOW_END,
            severity=AuditSeverity.INFO if success else AuditSeverity.ERROR,
            workflow_id=workflow_id,
            status="success" if success else "failed",
            error_message=error,
            action_details={"final_state_keys": list(final_state.keys())},
            tags=["workflow"],
        )
        return await self.storage.write(log)
    
    async def log_node_enter(self, workflow_id: str, node_name: str) -> str:
        """Log entering a graph node."""
        log = AuditLog(
            audit_id="",
            action_type=AuditActionType.NODE_ENTER,
            workflow_id=workflow_id,
            node_name=node_name,
            action_details={"node": node_name},
            tags=["node", node_name],
        )
        return await self.storage.write(log)
    
    async def log_node_exit(self, workflow_id: str, node_name: str, 
                           success: bool = True, error: Optional[str] = None,
                           duration_ms: Optional[float] = None) -> str:
        """Log exiting a graph node."""
        log = AuditLog(
            audit_id="",
            action_type=AuditActionType.NODE_EXIT,
            severity=AuditSeverity.INFO if success else AuditSeverity.ERROR,
            workflow_id=workflow_id,
            node_name=node_name,
            status="success" if success else "failed",
            error_message=error,
            duration_ms=duration_ms,
            action_details={"node": node_name},
            tags=["node", node_name],
        )
        return await self.storage.write(log)
    
    async def log_agent_execute(self, workflow_id: str, agent_id: str, 
                               input_data: Dict[str, Any], output_data: Dict[str, Any],
                               success: bool = True, error: Optional[str] = None,
                               duration_ms: Optional[float] = None) -> str:
        """Log agent execution."""
        log = AuditLog(
            audit_id="",
            action_type=AuditActionType.AGENT_EXECUTE,
            severity=AuditSeverity.INFO if success else AuditSeverity.ERROR,
            workflow_id=workflow_id,
            agent_id=agent_id,
            status="success" if success else "failed",
            error_message=error,
            input_data=input_data,
            output_data=output_data,
            duration_ms=duration_ms,
            tags=["agent", agent_id],
        )
        return await self.storage.write(log)
    
    async def log_config_change(self, config_key: str, old_value: Any, new_value: Any,
                               actor: str = "unknown") -> str:
        """Log configuration change."""
        log = AuditLog(
            audit_id="",
            action_type=AuditActionType.CONFIG_CHANGE,
            severity=AuditSeverity.WARNING,
            actor=actor,
            action_details={
                "config_key": config_key,
                "old_value": str(old_value),
                "new_value": str(new_value),
            },
            tags=["config", config_key],
        )
        return await self.storage.write(log)
    
    async def log_config_approval(self, config_key: str, approved_by: str, 
                                 reason: Optional[str] = None) -> str:
        """Log configuration approval."""
        log = AuditLog(
            audit_id="",
            action_type=AuditActionType.CONFIG_APPROVE,
            actor=approved_by,
            action_details={
                "config_key": config_key,
                "reason": reason,
            },
            tags=["config", "approval", config_key],
        )
        return await self.storage.write(log)
    
    async def log_error(self, workflow_id: Optional[str], node_name: Optional[str],
                       error_message: str, error_trace: Optional[str] = None) -> str:
        """Log error occurrence."""
        log = AuditLog(
            audit_id="",
            action_type=AuditActionType.ERROR_OCCURRED,
            severity=AuditSeverity.ERROR,
            workflow_id=workflow_id,
            node_name=node_name,
            status="failed",
            error_message=error_message,
            error_trace=error_trace,
            tags=["error"],
        )
        return await self.storage.write(log)
    
    async def get_workflow_audit_trail(self, workflow_id: str) -> List[AuditLog]:
        """Get all audit logs for a workflow."""
        return await self.storage.query(workflow_id=workflow_id)
    
    async def get_agent_audit_trail(self, agent_id: str) -> List[AuditLog]:
        """Get all audit logs for an agent."""
        return await self.storage.query(agent_id=agent_id)
    
    async def cleanup_old_logs(self, retention_days: int = 90) -> int:
        """Clean up old audit logs."""
        return await self.storage.cleanup_old_logs(retention_days=retention_days)
