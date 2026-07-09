"""
Base service classes for dependency injection and standardized interfaces.
All services inherit from these base classes to ensure consistency.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List
from datetime import datetime
from enum import Enum
import logging


class ServiceStatus(Enum):
    """Service health status."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class BaseService(ABC):
    """
    Abstract base class for all services.
    Provides common interface, logging, and error handling.
    """
    
    def __init__(self, service_name: str, config: Dict[str, Any] = None):
        self.service_name = service_name
        self.config = config or {}
        self.logger = logging.getLogger(self.service_name)
        self.status = ServiceStatus.HEALTHY
        self.created_at = datetime.utcnow()
        self.audit_log: List[Dict[str, Any]] = []
    
    @abstractmethod
    def validate_config(self) -> bool:
        """
        Validate configuration for this service.
        
        Returns:
            True if config is valid, raises Exception otherwise
        """
        pass
    
    @abstractmethod
    def initialize(self) -> None:
        """Initialize service resources and connections."""
        pass
    
    @abstractmethod
    def shutdown(self) -> None:
        """Clean up resources."""
        pass
    
    def get_status(self) -> ServiceStatus:
        """Get current service status."""
        return self.status
    
    def log_action(self, action: str, details: Dict[str, Any] = None) -> None:
        """Log an action for audit trail."""
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "action": action,
            "details": details or {},
        }
        self.audit_log.append(entry)
        self.logger.info(f"{action}: {details}")
    
    def log_error(self, error: str, exception: Exception = None) -> None:
        """Log an error."""
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "error": error,
            "exception": str(exception) if exception else None,
        }
        self.audit_log.append(entry)
        self.logger.error(f"{error}", exc_info=exception)
    
    def get_audit_log(self) -> List[Dict[str, Any]]:
        """Get audit log for this service."""
        return self.audit_log.copy()


class StorageService(BaseService):
    """Base class for data storage services."""
    
    def save(self, entity_id: str, data: Dict[str, Any]) -> None:
        """Save entity data."""
        raise NotImplementedError
    
    def retrieve(self, entity_id: str) -> Dict[str, Any]:
        """Retrieve entity data."""
        raise NotImplementedError
    
    def query(self, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Query entities by filters."""
        raise NotImplementedError
    
    def delete(self, entity_id: str, reason: str) -> None:
        """Soft delete entity."""
        raise NotImplementedError


class AgentService(BaseService):
    """Base class for agents in the pipeline."""
    
    def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process input data and return output."""
        raise NotImplementedError
    
    def validate_input(self, input_data: Dict[str, Any]) -> bool:
        """Validate input data."""
        raise NotImplementedError
    
    def validate_output(self, output_data: Dict[str, Any]) -> bool:
        """Validate output data."""
        raise NotImplementedError


class ServiceFactory:
    """Factory for creating and injecting services."""
    
    def __init__(self):
        self.services: Dict[str, BaseService] = {}
        self.config = {}
    
    def register_service(self, name: str, service: BaseService) -> None:
        """Register a service."""
        self.services[name] = service
        service.initialize()
    
    def get_service(self, name: str) -> BaseService:
        """Get a registered service."""
        if name not in self.services:
            raise ValueError(f"Service not found: {name}")
        return self.services[name]
    
    def shutdown_all(self) -> None:
        """Shutdown all services."""
        for service in self.services.values():
            try:
                service.shutdown()
            except Exception as e:
                logging.error(f"Error shutting down {service.service_name}: {e}")


if __name__ == "__main__":
    print("Base service classes defined successfully.")
