"""
Data models for document processing services
"""
from datetime import datetime
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, validator
from uuid import uuid4


class DocumentMetadata(BaseModel):
    """Document metadata model"""
    document_id: str
    filename: str
    file_size: int
    file_hash: str
    content_type: Optional[str] = None
    user_id: Optional[str] = None
    processed_at: datetime
    tags: List[str] = Field(default_factory=list)
    custom_metadata: Dict[str, Any] = Field(default_factory=dict)
    
    @validator('file_size')
    def validate_file_size(cls, v):
        if v <= 0:
            raise ValueError('File size must be positive')
        return v


class DocumentChunk(BaseModel):
    """Document chunk model"""
    id: str
    text: str
    index: int
    document_id: str
    embedding: Optional[List[float]] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    @validator('text')
    def validate_text(cls, v):
        if not v or not v.strip():
            raise ValueError('Text cannot be empty')
        return v.strip()
    
    @validator('index')
    def validate_index(cls, v):
        if v < 0:
            raise ValueError('Index must be non-negative')
        return v


class ProcessingResult(BaseModel):
    """Result of document processing"""
    document_id: str
    metadata: DocumentMetadata
    chunks: List[DocumentChunk]
    processing_time: float
    chunk_count: int
    success: bool = True
    error_message: Optional[str] = None
    
    @validator('processing_time')
    def validate_processing_time(cls, v):
        if v < 0:
            raise ValueError('Processing time must be non-negative')
        return v
    
    @validator('chunk_count')
    def validate_chunk_count(cls, v, values):
        if 'chunks' in values and v != len(values['chunks']):
            raise ValueError('Chunk count must match actual chunks length')
        return v


class SearchQuery(BaseModel):
    """Search query model"""
    query: str
    filters: Dict[str, Any] = Field(default_factory=dict)
    limit: int = Field(default=10, ge=1, le=100)
    offset: int = Field(default=0, ge=0)
    user_id: Optional[str] = None
    include_metadata: bool = True
    min_relevance: float = Field(default=0.5, ge=0.0, le=1.0)
    
    @validator('query')
    def validate_query(cls, v):
        if not v or not v.strip():
            raise ValueError('Query cannot be empty')
        return v.strip()


class SearchResult(BaseModel):
    """Search result model"""
    chunk_id: str
    text: str
    relevance_score: float
    document_id: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    highlights: List[str] = Field(default_factory=list)
    
    @validator('relevance_score')
    def validate_relevance(cls, v):
        if not 0.0 <= v <= 1.0:
            raise ValueError('Relevance score must be between 0 and 1')
        return v


class SearchResponse(BaseModel):
    """Search response model"""
    query: str
    results: List[SearchResult]
    total_results: int
    processing_time: float
    offset: int
    limit: int
    
    @validator('total_results')
    def validate_total_results(cls, v):
        if v < 0:
            raise ValueError('Total results must be non-negative')
        return v


class ChatMessage(BaseModel):
    """Chat message model"""
    id: str = Field(default_factory=lambda: str(uuid4()))
    content: str
    role: str  # 'user' or 'assistant'
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    user_id: Optional[str] = None
    context_used: List[str] = Field(default_factory=list)  # chunk IDs used for context
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    @validator('content')
    def validate_content(cls, v):
        if not v or not v.strip():
            raise ValueError('Message content cannot be empty')
        return v.strip()
    
    @validator('role')
    def validate_role(cls, v):
        if v not in ['user', 'assistant']:
            raise ValueError('Role must be either "user" or "assistant"')
        return v


class ChatSession(BaseModel):
    """Chat session model"""
    id: str = Field(default_factory=lambda: str(uuid4()))
    user_id: str
    title: Optional[str] = None
    messages: List[ChatMessage] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    is_active: bool = True
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    def add_message(self, message: ChatMessage):
        """Add a message to the session"""
        self.messages.append(message)
        self.updated_at = datetime.utcnow()
        
        # Auto-generate title from first user message
        if not self.title and message.role == 'user' and len(self.messages) == 1:
            self.title = message.content[:50] + ('...' if len(message.content) > 50 else '')


class UploadRequest(BaseModel):
    """File upload request model"""
    filename: str
    content_type: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    @validator('filename')
    def validate_filename(cls, v):
        if not v or not v.strip():
            raise ValueError('Filename cannot be empty')
        return v.strip()


class UploadResponse(BaseModel):
    """File upload response model"""
    document_id: str
    filename: str
    status: str  # 'uploaded', 'processing', 'completed', 'failed'
    message: str
    upload_time: datetime = Field(default_factory=datetime.utcnow)
    processing_result: Optional[ProcessingResult] = None


class HealthStatus(BaseModel):
    """Health check status model"""
    status: str  # 'healthy', 'degraded', 'unhealthy'
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    services: Dict[str, str] = Field(default_factory=dict)
    version: str
    uptime_seconds: float
    
    @validator('status')
    def validate_status(cls, v):
        if v not in ['healthy', 'degraded', 'unhealthy']:
            raise ValueError('Status must be healthy, degraded, or unhealthy')
        return v


class SystemMetrics(BaseModel):
    """System metrics model"""
    requests_total: int = 0
    requests_by_endpoint: Dict[str, int] = Field(default_factory=dict)
    avg_response_time: float = 0.0
    error_count: int = 0
    active_connections: int = 0
    documents_processed: int = 0
    search_queries: int = 0
    uptime_seconds: float = 0.0
    memory_usage_mb: float = 0.0
    cpu_usage_percent: float = 0.0


class DocumentInfo(BaseModel):
    """Document information model"""
    document_id: str
    filename: str
    file_size: int
    chunk_count: int
    processed_at: datetime
    user_id: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    status: str = 'processed'  # 'processing', 'processed', 'failed'
    
    @validator('status')
    def validate_status(cls, v):
        if v not in ['processing', 'processed', 'failed']:
            raise ValueError('Status must be processing, processed, or failed')
        return v


class UserStats(BaseModel):
    """User statistics model"""
    user_id: str
    documents_uploaded: int = 0
    total_chunks: int = 0
    search_queries: int = 0
    chat_sessions: int = 0
    last_activity: Optional[datetime] = None
    storage_used_mb: float = 0.0


class ErrorResponse(BaseModel):
    """Standard error response model"""
    error: Dict[str, Any]
    request_id: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        schema_extra = {
            "example": {
                "error": {
                    "type": "ValidationError",
                    "message": "Invalid input data",
                    "details": {"field": "filename", "issue": "cannot be empty"}
                },
                "request_id": "req_123456",
                "timestamp": "2024-01-01T00:00:00Z"
            }
        }