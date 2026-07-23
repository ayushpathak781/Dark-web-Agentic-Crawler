"""
Job Tracking Service for Dark Web Threat Intelligence System.

Manages lifecycle of workflow jobs including:
- Status tracking
- Result persistence
- Error tracking
- Retry management
- Job history
"""

from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from datetime import datetime, timedelta
from enum import Enum
import json
from abc import ABC, abstractmethod
import uuid


# ============================================================================
# Job Status Models
# ============================================================================

class JobStatus(str, Enum):
    """Status of a job."""
    QUEUED = "queued"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"  # Completed with some errors
    CANCELLED = "cancelled"
    RETRYING = "retrying"


class JobResult(BaseModel):
    """Result of a completed job."""
    job_id: str
    status: JobStatus
    
    # Lifecycle
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # Duration
    total_duration_ms: Optional[float] = None
    
    # Results
    result_data: Dict[str, Any] = Field(default_factory=dict)
    error_message: Optional[str] = None
    error_trace: Optional[str] = None
    
    # Retry tracking
    attempts: int = 1
    max_attempts: int = 3
    last_retry_at: Optional[datetime] = None
    
    # Metadata
    workflow_id: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    
    class Config:
        use_enum_values = True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = self.dict()
        data['created_at'] = self.created_at.isoformat()
        if self.started_at:
            data['started_at'] = self.started_at.isoformat()
        if self.completed_at:
            data['completed_at'] = self.completed_at.isoformat()
        if self.last_retry_at:
            data['last_retry_at'] = self.last_retry_at.isoformat()
        return data


class Job(BaseModel):
    """Active job in the system."""
    job_id: str
    workflow_id: str
    status: JobStatus
    
    # Input
    input_data: Dict[str, Any]
    
    # Execution context
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    
    # Progress
    current_node: Optional[str] = None
    completed_nodes: List[str] = Field(default_factory=list)
    
    # Error handling
    error_message: Optional[str] = None
    attempts: int = 1
    max_attempts: int = 3
    last_retry_at: Optional[datetime] = None
    
    # Metadata
    tags: List[str] = Field(default_factory=list)
    
    class Config:
        use_enum_values = True


# ============================================================================
# Job Storage Interface
# ============================================================================

class JobStorage(ABC):
    """Abstract base for job storage."""
    
    @abstractmethod
    async def create_job(self, job: Job) -> str:
        """
        Create a new job.
        
        Args:
            job: Job instance
        
        Returns:
            job_id
        """
        pass
    
    @abstractmethod
    async def get_job(self, job_id: str) -> Optional[Job]:
        """Get job by ID."""
        pass
    
    @abstractmethod
    async def update_job(self, job: Job) -> None:
        """Update job status."""
        pass
    
    @abstractmethod
    async def complete_job(self, job_id: str, result: JobResult) -> None:
        """Mark job as completed and store result."""
        pass
    
    @abstractmethod
    async def get_job_result(self, job_id: str) -> Optional[JobResult]:
        """Get completed job result."""
        pass
    
    @abstractmethod
    async def list_jobs(self, 
                       status: Optional[JobStatus] = None,
                       workflow_id: Optional[str] = None,
                       limit: int = 100) -> List[Job]:
        """List jobs with filters."""
        pass
    
    @abstractmethod
    async def list_results(self,
                          status: Optional[JobStatus] = None,
                          limit: int = 100) -> List[JobResult]:
        """List completed job results."""
        pass


# ============================================================================
# In-Memory Job Storage (for Phase 1)
# ============================================================================

class InMemoryJobStorage(JobStorage):
    """Simple in-memory job storage for testing."""
    
    def __init__(self):
        self.jobs: Dict[str, Job] = {}
        self.results: Dict[str, JobResult] = {}
    
    async def create_job(self, job: Job) -> str:
        """Create a new job."""
        self.jobs[job.job_id] = job
        return job.job_id
    
    async def get_job(self, job_id: str) -> Optional[Job]:
        """Get job by ID."""
        return self.jobs.get(job_id)
    
    async def update_job(self, job: Job) -> None:
        """Update job."""
        self.jobs[job.job_id] = job
    
    async def complete_job(self, job_id: str, result: JobResult) -> None:
        """Mark job as completed."""
        if job_id in self.jobs:
            del self.jobs[job_id]
        self.results[job_id] = result
    
    async def get_job_result(self, job_id: str) -> Optional[JobResult]:
        """Get job result."""
        return self.results.get(job_id)
    
    async def list_jobs(self,
                       status: Optional[JobStatus] = None,
                       workflow_id: Optional[str] = None,
                       limit: int = 100) -> List[Job]:
        """List jobs."""
        results = list(self.jobs.values())
        
        if status:
            results = [j for j in results if j.status == status]
        if workflow_id:
            results = [j for j in results if j.workflow_id == workflow_id]
        
        return results[:limit]
    
    async def list_results(self,
                          status: Optional[JobStatus] = None,
                          limit: int = 100) -> List[JobResult]:
        """List results."""
        results = list(self.results.values())
        
        if status:
            results = [r for r in results if r.status == status]
        
        # Sort by completed_at, newest first
        results.sort(key=lambda r: r.completed_at or datetime.min, reverse=True)
        
        return results[:limit]


# ============================================================================
# Job Tracker Service
# ============================================================================

class JobTracker:
    """Manages job lifecycle and tracking."""
    
    def __init__(self, storage: Optional[JobStorage] = None):
        self.storage = storage or InMemoryJobStorage()
    
    async def create_job(self, workflow_id: str, input_data: Dict[str, Any],
                        tags: Optional[List[str]] = None,
                        max_attempts: int = 3) -> str:
        """
        Create a new job.
        
        Args:
            workflow_id: Workflow ID for this job
            input_data: Input state for workflow
            tags: Optional tags for filtering
            max_attempts: Maximum retry attempts
        
        Returns:
            job_id
        """
        job_id = str(uuid.uuid4())
        job = Job(
            job_id=job_id,
            workflow_id=workflow_id,
            status=JobStatus.QUEUED,
            input_data=input_data,
            max_attempts=max_attempts,
            tags=tags or [],
        )
        return await self.storage.create_job(job)
    
    async def start_job(self, job_id: str) -> None:
        """Mark job as started."""
        job = await self.storage.get_job(job_id)
        if job:
            job.status = JobStatus.RUNNING
            job.started_at = datetime.utcnow()
            await self.storage.update_job(job)
    
    async def update_progress(self, job_id: str, current_node: str,
                             completed_nodes: Optional[List[str]] = None) -> None:
        """Update job progress."""
        job = await self.storage.get_job(job_id)
        if job:
            job.current_node = current_node
            if completed_nodes:
                job.completed_nodes = completed_nodes
            await self.storage.update_job(job)
    
    async def record_error(self, job_id: str, error_message: str,
                          error_trace: Optional[str] = None) -> None:
        """Record error in job."""
        job = await self.storage.get_job(job_id)
        if job:
            job.error_message = error_message
            await self.storage.update_job(job)
    
    async def retry_job(self, job_id: str) -> bool:
        """
        Attempt to retry a job.
        
        Args:
            job_id: Job to retry
        
        Returns:
            True if retry scheduled, False if max attempts exceeded
        """
        job = await self.storage.get_job(job_id)
        if not job:
            return False
        
        if job.attempts >= job.max_attempts:
            return False
        
        job.attempts += 1
        job.status = JobStatus.RETRYING
        job.last_retry_at = datetime.utcnow()
        job.error_message = None
        await self.storage.update_job(job)
        return True
    
    async def complete_job(self, job_id: str, success: bool = True,
                          result_data: Optional[Dict[str, Any]] = None,
                          error_message: Optional[str] = None,
                          error_trace: Optional[str] = None) -> JobResult:
        """
        Mark job as completed.
        
        Args:
            job_id: Job to complete
            success: Whether job succeeded
            result_data: Result data to store
            error_message: Error message if failed
            error_trace: Error trace if failed
        
        Returns:
            JobResult
        """
        job = await self.storage.get_job(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")
        
        completed_at = datetime.utcnow()
        total_duration_ms = (completed_at - job.created_at).total_seconds() * 1000 if job.created_at else None
        
        status = JobStatus.SUCCESS if success else JobStatus.FAILED
        
        result = JobResult(
            job_id=job_id,
            status=status,
            created_at=job.created_at,
            started_at=job.started_at,
            completed_at=completed_at,
            total_duration_ms=total_duration_ms,
            result_data=result_data or {},
            error_message=error_message,
            error_trace=error_trace,
            attempts=job.attempts,
            max_attempts=job.max_attempts,
            workflow_id=job.workflow_id,
            tags=job.tags,
        )
        
        await self.storage.complete_job(job_id, result)
        return result
    
    async def get_job(self, job_id: str) -> Optional[Job]:
        """Get job by ID."""
        return await self.storage.get_job(job_id)
    
    async def get_job_result(self, job_id: str) -> Optional[JobResult]:
        """Get completed job result."""
        return await self.storage.get_job_result(job_id)
    
    async def list_active_jobs(self, workflow_id: Optional[str] = None) -> List[Job]:
        """List active jobs."""
        return await self.storage.list_jobs(
            status=JobStatus.RUNNING,
            workflow_id=workflow_id
        )
    
    async def list_failed_jobs(self, limit: int = 100) -> List[JobResult]:
        """List failed jobs."""
        return await self.storage.list_results(
            status=JobStatus.FAILED,
            limit=limit
        )
    
    async def list_recent_results(self, limit: int = 100) -> List[JobResult]:
        """List recent job results."""
        return await self.storage.list_results(limit=limit)
    
    async def get_workflow_jobs(self, workflow_id: str) -> tuple[List[Job], List[JobResult]]:
        """Get all jobs and results for a workflow."""
        active = await self.storage.list_jobs(workflow_id=workflow_id)
        results = await self.storage.list_results()
        completed = [r for r in results if r.workflow_id == workflow_id]
        return active, completed
