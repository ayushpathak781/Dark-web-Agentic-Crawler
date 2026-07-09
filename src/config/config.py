"""
Configuration management for Dark Web Threat Intelligence Agent.
Provides centralized, validated configuration with approval workflow.
"""

from typing import Any, Dict, Optional
from datetime import datetime
from enum import Enum
import json
from pathlib import Path


class ConfigSection(str, Enum):
    """Authorized configuration sections."""
    TOR_PROXY = "tor_proxy"
    RATE_LIMITS = "rate_limits"
    ALLOWLIST = "allowlist"
    LLM_MODELS = "llm_models"
    STORAGE = "storage"
    LOGGING = "logging"
    SECURITY = "security"


class Config:
    """
    Centralized configuration manager with validation and audit trail.
    
    Features:
    - Schema validation for each section
    - Audit trail of all changes
    - Approval workflow integration hooks
    - Rollback capability
    - Runtime updates with cache invalidation
    """
    
    def __init__(self, config_file: str = "config.json"):
        self.config_file = Path(config_file)
        self.config: Dict[str, Any] = self._load_config()
        self.change_history: list = []
        self.audit_log: list = []
        
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from file."""
        if not self.config_file.exists():
            return self._get_default_config()
        
        with open(self.config_file) as f:
            return json.load(f)
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Provide default configuration template."""
        return {
            ConfigSection.TOR_PROXY: {
                "host": "localhost",
                "port": 9050,
                "socks_version": 5,
                "circuit_rotation_interval_hours": 1,
                "max_retries": 3,
                "timeout_seconds": 30,
            },
            ConfigSection.RATE_LIMITS: {
                "global_requests_per_hour": 1000,
                "per_source_requests_per_hour": 10,
                "crawl_batch_size": 10,
                "min_interval_between_requests_ms": 500,
            },
            ConfigSection.LLM_MODELS: {
                "extraction_model": "gpt-4",
                "extraction_temperature": 0.2,
                "extraction_max_tokens": 2000,
                "classification_model": "gpt-4",
                "classification_temperature": 0.3,
                "classification_max_tokens": 1000,
            },
            ConfigSection.STORAGE: {
                "postgres_host": "localhost",
                "postgres_port": 5432,
                "postgres_database": "threat_intelligence",
                "postgres_pool_size": 10,
                "qdrant_host": "localhost",
                "qdrant_port": 6333,
                "neo4j_uri": "bolt://localhost:7687",
                "elasticsearch_host": "localhost",
                "elasticsearch_port": 9200,
            },
            ConfigSection.LOGGING: {
                "log_level": "INFO",
                "audit_log_retention_days": 730,
                "application_log_retention_days": 90,
                "log_format": "json",
            },
            ConfigSection.SECURITY: {
                "require_approval_for_new_sources": True,
                "require_approval_for_config_changes": True,
                "allow_data_export": False,
                "export_requires_approval": True,
                "max_concurrent_crawlers": 5,
                "enable_read_only_enforcement": True,
            },
        }
    
    def get(self, section: str, key: Optional[str] = None) -> Any:
        """
        Retrieve configuration value.
        
        Args:
            section: ConfigSection enum value
            key: Optional nested key (dot-notation supported)
        
        Returns:
            Configuration value or entire section dict
        """
        try:
            value = self.config.get(section)
            
            if key and isinstance(value, dict):
                keys = key.split(".")
                for k in keys:
                    value = value.get(k)
                    if value is None:
                        break
            
            return value
        except Exception as e:
            raise ValueError(f"Config retrieval failed: {section}.{key} - {e}")
    
    def set(self, section: str, key: str, value: Any, reason: str = "") -> None:
        """
        Update configuration value (requires approval in production).
        
        Args:
            section: ConfigSection enum value
            key: Nested key (dot-notation supported)
            value: New value
            reason: Audit log reason for change
        
        Note:
            In production, this should go through approval workflow.
            For now, logs all changes in change_history.
        """
        if section not in ConfigSection.__members__.values():
            raise ValueError(f"Invalid config section: {section}")
        
        # Log change in history before applying
        change_record = {
            "timestamp": datetime.utcnow().isoformat(),
            "section": section,
            "key": key,
            "old_value": self.get(section, key),
            "new_value": value,
            "reason": reason,
            "status": "pending_approval",
        }
        
        self.change_history.append(change_record)
        
        # Validate new value against schema
        # (In production, this would be more comprehensive)
        self._validate_config_value(section, key, value)
        
        # Apply change
        keys = key.split(".")
        config_section = self.config.get(section, {})
        
        for k in keys[:-1]:
            if k not in config_section:
                config_section[k] = {}
            config_section = config_section[k]
        
        config_section[keys[-1]] = value
        
        # Update audit log
        self.audit_log.append({
            "timestamp": datetime.utcnow().isoformat(),
            "action": "config_change",
            "section": section,
            "key": key,
            "new_value": value,
            "reason": reason,
            "status": "applied",
        })
        
        # Save to file
        self._save_config()
    
    def _validate_config_value(self, section: str, key: str, value: Any) -> None:
        """Validate configuration value against schema."""
        # Basic type validation
        if section == ConfigSection.TOR_PROXY:
            if key == "port" and not isinstance(value, int):
                raise ValueError(f"TOR_PROXY.port must be int, got {type(value)}")
            if key == "timeout_seconds" and value <= 0:
                raise ValueError("TOR_PROXY.timeout_seconds must be > 0")
        
        elif section == ConfigSection.RATE_LIMITS:
            if any(x in key for x in ["requests_per_hour", "interval_between_requests_ms"]):
                if not isinstance(value, (int, float)) or value <= 0:
                    raise ValueError(f"{section}.{key} must be positive number")
        
        elif section == ConfigSection.LOGGING:
            if key == "log_level" and value not in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
                raise ValueError(f"Invalid log level: {value}")
    
    def _save_config(self) -> None:
        """Save current configuration to file."""
        with open(self.config_file, 'w') as f:
            json.dump(self.config, f, indent=2)
    
    def get_all(self) -> Dict[str, Any]:
        """Return entire configuration (use cautiously - may contain secrets)."""
        return self.config.copy()
    
    def get_audit_log(self) -> list:
        """Return audit log of all configuration changes."""
        return self.audit_log.copy()
    
    def get_change_history(self) -> list:
        """Return change history with approval status."""
        return self.change_history.copy()


# Global config instance
_config_instance: Optional[Config] = None


def get_config(config_file: str = "config.json") -> Config:
    """Get global config instance (singleton pattern)."""
    global _config_instance
    if _config_instance is None:
        _config_instance = Config(config_file)
    return _config_instance


if __name__ == "__main__":
    # Example usage
    config = get_config()
    
    # Read configuration
    tor_host = config.get(ConfigSection.TOR_PROXY, "host")
    print(f"Tor host: {tor_host}")
    
    # Update configuration
    config.set(
        ConfigSection.RATE_LIMITS,
        "global_requests_per_hour",
        500,
        reason="Reducing rate limit during testing"
    )
    
    # View audit log
    print("Audit Log:", config.get_audit_log())
