"""
Enhanced configuration management with Pydantic validation
"""
import os
import secrets
from typing import List, Optional, Union
from pydantic import BaseSettings, validator, Field
from pydantic_settings import BaseSettings as PydanticBaseSettings


class DatabaseSettings(BaseSettings):
    """Qdrant database configuration"""
    host: str = Field(default="localhost", env="QDRANT_HOST")
    port: int = Field(default=6333, env="QDRANT_PORT")
    collection_name: str = Field(default="document_chunks_v2", env="QDRANT_COLLECTION")
    vector_size: int = Field(default=768, env="QDRANT_VECTOR_SIZE")
    timeout: int = Field(default=30, env="QDRANT_TIMEOUT")
    
    class Config:
        env_prefix = "QDRANT_"


class SecuritySettings(BaseSettings):
    """Security configuration"""
    secret_key: str = Field(default_factory=lambda: secrets.token_urlsafe(32))
    algorithm: str = Field(default="HS256")
    access_token_expire_minutes: int = Field(default=30)
    refresh_token_expire_days: int = Field(default=7)
    password_min_length: int = Field(default=8)
    max_login_attempts: int = Field(default=5)
    lockout_duration_minutes: int = Field(default=15)
    
    class Config:
        env_prefix = "SECURITY_"


class ProcessingSettings(BaseSettings):
    """Document processing configuration"""
    chunk_size: int = Field(default=768, ge=100, le=2048)
    chunk_overlap: int = Field(default=200, ge=0, le=500)
    min_chunk_size: int = Field(default=300, ge=50, le=1000)
    max_file_size_mb: int = Field(default=50, ge=1, le=500)
    supported_formats: List[str] = Field(default=[".pdf", ".docx", ".doc", ".txt"])
    embedding_model: str = Field(default="sentence-transformers/paraphrase-multilingual-mpnet-base-v2")
    spacy_model: str = Field(default="ru_core_news_md")
    batch_size: int = Field(default=32, ge=1, le=128)
    max_workers: int = Field(default=4, ge=1, le=16)
    device: str = Field(default="cpu")
    
    @validator('device')
    def validate_device(cls, v):
        if v not in ['cpu', 'cuda', 'mps']:
            raise ValueError('Device must be cpu, cuda, or mps')
        return v
    
    class Config:
        env_prefix = "PROCESSING_"


class LLMSettings(BaseSettings):
    """LLM configuration"""
    api_url: str = Field(default="http://localhost:1234/v1", env="LLM_API_URL")
    model: str = Field(default="google/gemma-3-4b", env="LLM_MODEL")
    temperature: float = Field(default=0.3, ge=0.0, le=2.0)
    max_tokens: int = Field(default=1000, ge=1, le=4096)
    timeout: int = Field(default=60, ge=10, le=300)
    retry_attempts: int = Field(default=3, ge=1, le=10)
    cache_responses: bool = Field(default=True)
    
    class Config:
        env_prefix = "LLM_"


class MonitoringSettings(BaseSettings):
    """Monitoring and logging configuration"""
    log_level: str = Field(default="INFO")
    log_format: str = Field(default="json")
    max_log_size_mb: int = Field(default=100)
    backup_count: int = Field(default=5)
    metrics_enabled: bool = Field(default=True)
    health_check_interval: int = Field(default=30)
    
    @validator('log_level')
    def validate_log_level(cls, v):
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if v.upper() not in valid_levels:
            raise ValueError(f'Log level must be one of {valid_levels}')
        return v.upper()
    
    class Config:
        env_prefix = "MONITORING_"


class APISettings(BaseSettings):
    """API configuration"""
    host: str = Field(default="0.0.0.0", env="API_HOST")
    port: int = Field(default=8000, env="API_PORT")
    workers: int = Field(default=1, ge=1, le=8)
    reload: bool = Field(default=False)
    rate_limit_per_minute: int = Field(default=60, ge=1, le=1000)
    cors_origins: List[str] = Field(default=["*"])
    docs_url: Optional[str] = Field(default="/docs")
    redoc_url: Optional[str] = Field(default="/redoc")
    
    class Config:
        env_prefix = "API_"


class Settings(PydanticBaseSettings):
    """Main application settings"""
    app_name: str = Field(default="RAG Document Assistant")
    version: str = Field(default="2.0.0")
    debug: bool = Field(default=False, env="DEBUG")
    testing: bool = Field(default=False, env="TESTING")
    
    # Component settings
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    processing: ProcessingSettings = Field(default_factory=ProcessingSettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    monitoring: MonitoringSettings = Field(default_factory=MonitoringSettings)
    api: APISettings = Field(default_factory=APISettings)
    
    # Paths
    data_dir: str = Field(default="data")
    upload_dir: str = Field(default="uploads")
    processed_dir: str = Field(default="processed")
    logs_dir: str = Field(default="logs")
    temp_dir: str = Field(default="temp")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Create directories if they don't exist
        for dir_path in [self.data_dir, self.upload_dir, self.processed_dir, 
                        self.logs_dir, self.temp_dir]:
            os.makedirs(dir_path, exist_ok=True)


# Global settings instance
settings = Settings()