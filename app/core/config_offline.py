"""
Offline configuration for RAG Document Assistant v2.0
Optimized for heavy models and Windows server deployment
"""
import os
import secrets
from typing import List, Optional
from pydantic import BaseSettings, validator, Field
from pydantic_settings import BaseSettings as PydanticBaseSettings


class OfflineProcessingSettings(BaseSettings):
    """Document processing configuration for offline mode with heavy models"""
    
    # Heavy model configuration
    embedding_model: str = Field(default="./models/embedding")  # Local path to e5-large
    spacy_model: str = Field(default="ru_core_news_lg")
    device: str = Field(default="cpu")  # CPU-only for most servers
    
    # Optimized for heavy models
    chunk_size: int = Field(default=1024, ge=512, le=2048)  # Larger chunks for better context
    chunk_overlap: int = Field(default=256, ge=0, le=512)
    min_chunk_size: int = Field(default=400, ge=100, le=800)
    vector_size: int = Field(default=1024)  # e5-large vector dimension
    
    # Conservative settings for heavy models
    batch_size: int = Field(default=16, ge=1, le=32)  # Smaller batches
    max_workers: int = Field(default=2, ge=1, le=4)   # Conservative CPU usage
    max_file_size_mb: int = Field(default=50, ge=1, le=200)
    
    # File format support
    supported_formats: List[str] = Field(default=[".pdf", ".docx", ".doc", ".txt", ".rtf"])
    
    # OCR settings (optional)
    ocr_enabled: bool = Field(default=True)
    ocr_languages: List[str] = Field(default=["rus", "eng"])
    ocr_timeout: int = Field(default=60)
    
    class Config:
        env_prefix = "PROCESSING_"


class OfflineDatabaseSettings(BaseSettings):
    """Qdrant database configuration for offline deployment"""
    host: str = Field(default="localhost", env="QDRANT_HOST")
    port: int = Field(default=6333, env="QDRANT_PORT")
    collection_name: str = Field(default="documents_offline_v2", env="QDRANT_COLLECTION")
    vector_size: int = Field(default=1024, env="QDRANT_VECTOR_SIZE")  # e5-large vectors
    timeout: int = Field(default=60, env="QDRANT_TIMEOUT")  # Longer timeout
    
    # Optimized search parameters
    search_limit: int = Field(default=20, ge=5, le=100)
    hnsw_ef: int = Field(default=128)  # Higher quality search
    hnsw_m: int = Field(default=16)    # Memory vs quality tradeoff
    
    class Config:
        env_prefix = "QDRANT_"


class OfflineSecuritySettings(BaseSettings):
    """Enhanced security for offline deployment"""
    secret_key: str = Field(default_factory=lambda: secrets.token_urlsafe(64))
    algorithm: str = Field(default="HS256")
    
    # Longer sessions for offline use
    access_token_expire_minutes: int = Field(default=60)
    refresh_token_expire_days: int = Field(default=30)
    
    # More permissive for isolated servers
    password_min_length: int = Field(default=8)
    max_login_attempts: int = Field(default=10)
    lockout_duration_minutes: int = Field(default=30)
    
    # Disable some online security features
    cors_origins: List[str] = Field(default=["*"])  # More permissive for internal use
    
    class Config:
        env_prefix = "SECURITY_"


class OfflineLLMSettings(BaseSettings):
    """LLM configuration for offline deployment"""
    api_url: str = Field(default="http://localhost:1234/v1", env="LLM_API_URL")
    model: str = Field(default="microsoft/DialoGPT-large", env="LLM_MODEL")  # Suggest offline model
    
    # Conservative parameters for stability
    temperature: float = Field(default=0.2, ge=0.0, le=1.0)  # More deterministic
    max_tokens: int = Field(default=800, ge=100, le=2048)
    timeout: int = Field(default=120, ge=30, le=300)  # Longer timeout
    retry_attempts: int = Field(default=2, ge=1, le=5)
    
    # Offline-specific settings
    cache_responses: bool = Field(default=True)
    fallback_enabled: bool = Field(default=True)
    fallback_message: str = Field(default="LLM service temporarily unavailable. Please try again later.")
    
    class Config:
        env_prefix = "LLM_"


class OfflineMonitoringSettings(BaseSettings):
    """Monitoring configuration for offline deployment"""
    log_level: str = Field(default="INFO")
    log_format: str = Field(default="json")
    max_log_size_mb: int = Field(default=50)  # Smaller logs for limited storage
    backup_count: int = Field(default=10)
    
    # Enhanced monitoring for offline troubleshooting
    metrics_enabled: bool = Field(default=True)
    detailed_logging: bool = Field(default=True)
    performance_monitoring: bool = Field(default=True)
    error_tracking: bool = Field(default=True)
    
    # Health check configuration
    health_check_interval: int = Field(default=60)
    dependency_checks: bool = Field(default=True)
    
    class Config:
        env_prefix = "MONITORING_"


class OfflineAPISettings(BaseSettings):
    """API configuration for offline deployment"""
    host: str = Field(default="0.0.0.0", env="API_HOST")
    port: int = Field(default=8000, env="API_PORT")
    workers: int = Field(default=1, ge=1, le=2)  # Conservative for single server
    reload: bool = Field(default=False)  # Disabled for production
    
    # Rate limiting (more permissive for internal use)
    rate_limit_per_minute: int = Field(default=300, ge=10, le=1000)
    
    # CORS settings for offline use
    cors_origins: List[str] = Field(default=["*"])
    docs_url: Optional[str] = Field(default="/docs")
    redoc_url: Optional[str] = Field(default="/redoc")
    
    class Config:
        env_prefix = "API_"


class OfflineSettings(PydanticBaseSettings):
    """Main offline application settings"""
    app_name: str = Field(default="RAG Document Assistant (Offline)")
    version: str = Field(default="2.0.0-offline")
    debug: bool = Field(default=False, env="DEBUG")
    testing: bool = Field(default=False, env="TESTING")
    offline_mode: bool = Field(default=True)
    
    # Component settings optimized for offline use
    database: OfflineDatabaseSettings = Field(default_factory=OfflineDatabaseSettings)
    security: OfflineSecuritySettings = Field(default_factory=OfflineSecuritySettings)
    processing: OfflineProcessingSettings = Field(default_factory=OfflineProcessingSettings)
    llm: OfflineLLMSettings = Field(default_factory=OfflineLLMSettings)
    monitoring: OfflineMonitoringSettings = Field(default_factory=OfflineMonitoringSettings)
    api: OfflineAPISettings = Field(default_factory=OfflineAPISettings)
    
    # Paths for Windows deployment
    data_dir: str = Field(default="C:/RAGAssistant/data")
    upload_dir: str = Field(default="C:/RAGAssistant/uploads")
    processed_dir: str = Field(default="C:/RAGAssistant/processed")
    logs_dir: str = Field(default="C:/RAGAssistant/logs")
    temp_dir: str = Field(default="C:/RAGAssistant/temp")
    models_dir: str = Field(default="C:/RAGAssistant/models")
    
    # Offline-specific settings
    auto_cleanup: bool = Field(default=True)
    cleanup_interval_hours: int = Field(default=24)
    max_storage_gb: float = Field(default=50.0)
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Ensure directories exist for Windows deployment
        import os
        try:
            for dir_path in [self.data_dir, self.upload_dir, self.processed_dir, 
                            self.logs_dir, self.temp_dir, self.models_dir]:
                os.makedirs(dir_path, exist_ok=True)
        except PermissionError as e:
            raise RuntimeError(f"Failed to create directories. Please run as Administrator: {e}")
        except Exception as e:
            raise RuntimeError(f"Failed to create directories: {e}")


# Global offline settings instance
offline_settings = OfflineSettings()


def get_offline_config() -> dict:
    """Get complete offline configuration as dictionary"""
    return {
        "app_name": offline_settings.app_name,
        "version": offline_settings.version,
        "offline_mode": offline_settings.offline_mode,
        
        "processing": {
            "embedding_model": offline_settings.processing.embedding_model,
            "spacy_model": offline_settings.processing.spacy_model,
            "device": offline_settings.processing.device,
            "chunk_size": offline_settings.processing.chunk_size,
            "vector_size": offline_settings.processing.vector_size,
            "batch_size": offline_settings.processing.batch_size,
            "max_workers": offline_settings.processing.max_workers,
            "supported_formats": offline_settings.processing.supported_formats
        },
        
        "database": {
            "host": offline_settings.database.host,
            "port": offline_settings.database.port,
            "collection_name": offline_settings.database.collection_name,
            "vector_size": offline_settings.database.vector_size,
            "search_limit": offline_settings.database.search_limit
        },
        
        "security": {
            "access_token_expire_minutes": offline_settings.security.access_token_expire_minutes,
            "max_login_attempts": offline_settings.security.max_login_attempts,
            "cors_origins": offline_settings.security.cors_origins
        },
        
        "api": {
            "host": offline_settings.api.host,
            "port": offline_settings.api.port,
            "rate_limit_per_minute": offline_settings.api.rate_limit_per_minute
        },
        
        "monitoring": {
            "log_level": offline_settings.monitoring.log_level,
            "metrics_enabled": offline_settings.monitoring.metrics_enabled,
            "detailed_logging": offline_settings.monitoring.detailed_logging
        },
        
        "paths": {
            "data_dir": offline_settings.data_dir,
            "upload_dir": offline_settings.upload_dir,
            "processed_dir": offline_settings.processed_dir,
            "logs_dir": offline_settings.logs_dir,
            "models_dir": offline_settings.models_dir
        }
    }