"""
Main API routes for document processing, search, and chat
"""
import os
import tempfile
from typing import List, Optional
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status, BackgroundTasks
from fastapi.responses import JSONResponse
import aiofiles

from app.core.config import settings
from app.core.security import get_current_user, User
from app.core.exceptions import DocumentProcessingError, ValidationError
from app.core.logging import get_logger, metrics
from app.services.document_processor import document_processor
from app.services.models import (
    UploadResponse,
    SearchQuery,
    SearchResponse,
    ChatMessage,
    ChatSession,
    DocumentInfo,
    UserStats,
    ProcessingResult
)

logger = get_logger(__name__)
api_router = APIRouter()

# In-memory storage for demo (in production, use a database)
_document_storage = {}
_chat_sessions = {}


@api_router.post("/documents/upload", response_model=UploadResponse)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    """Upload and process a document"""
    
    try:
        # Validate file
        if not file.filename:
            raise ValidationError("Filename is required")
        
        # Check file size
        content = await file.read()
        file_size = len(content)
        
        if file_size > settings.processing.max_file_size_mb * 1024 * 1024:
            raise ValidationError(
                f"File size ({file_size / 1024 / 1024:.1f}MB) exceeds maximum allowed size ({settings.processing.max_file_size_mb}MB)"
            )
        
        # Create temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as temp_file:
            temp_file.write(content)
            temp_file_path = temp_file.name
        
        # Process document in background
        background_tasks.add_task(
            process_document_background,
            temp_file_path,
            file.filename,
            file.content_type,
            current_user.id
        )
        
        # Generate document ID
        import uuid
        document_id = str(uuid.uuid4())
        
        # Store document info
        _document_storage[document_id] = {
            "filename": file.filename,
            "user_id": current_user.id,
            "status": "processing",
            "file_size": file_size
        }
        
        logger.info_ctx(
            "Document upload initiated",
            document_id=document_id,
            filename=file.filename,
            user_id=current_user.id,
            file_size=file_size
        )
        
        return UploadResponse(
            document_id=document_id,
            filename=file.filename,
            status="uploaded",
            message="Document uploaded successfully. Processing started."
        )
        
    except Exception as e:
        if isinstance(e, (ValidationError, DocumentProcessingError)):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
        else:
            logger.error_ctx(f"Upload failed: {e}", user_id=current_user.id)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Upload failed"
            )


async def process_document_background(
    file_path: str,
    filename: str,
    content_type: Optional[str],
    user_id: str
):
    """Background task to process document"""
    try:
        result = await document_processor.process_file(
            file_path=file_path,
            filename=filename,
            content_type=content_type,
            user_id=user_id
        )
        
        # Update storage with success
        _document_storage[result.document_id].update({
            "status": "completed",
            "chunk_count": result.chunk_count,
            "processing_time": result.processing_time
        })
        
        # TODO: Store chunks in Qdrant database
        
        logger.info_ctx(
            "Document processing completed",
            document_id=result.document_id,
            filename=filename,
            chunks=result.chunk_count
        )
        
    except Exception as e:
        logger.error_ctx(f"Background processing failed: {e}", filename=filename)
        # Update storage with error status
        for doc_id, doc_info in _document_storage.items():
            if doc_info["filename"] == filename:
                doc_info["status"] = "failed"
                break
    
    finally:
        # Cleanup temp file
        try:
            os.unlink(file_path)
        except Exception:
            pass


@api_router.get("/documents", response_model=List[DocumentInfo])
async def list_documents(
    current_user: User = Depends(get_current_user),
    limit: int = 10,
    offset: int = 0
):
    """List user's documents"""
    
    user_documents = []
    for doc_id, doc_info in _document_storage.items():
        if doc_info["user_id"] == current_user.id:
            user_documents.append(DocumentInfo(
                document_id=doc_id,
                filename=doc_info["filename"],
                file_size=doc_info["file_size"],
                chunk_count=doc_info.get("chunk_count", 0),
                processed_at=doc_info.get("processed_at", ""),
                user_id=current_user.id,
                status=doc_info["status"]
            ))
    
    # Apply pagination
    start = offset
    end = offset + limit
    
    return user_documents[start:end]


@api_router.delete("/documents/{document_id}")
async def delete_document(
    document_id: str,
    current_user: User = Depends(get_current_user)
):
    """Delete a document"""
    
    if document_id not in _document_storage:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    
    doc_info = _document_storage[document_id]
    
    # Check ownership
    if doc_info["user_id"] != current_user.id and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this document"
        )
    
    # Delete from storage
    del _document_storage[document_id]
    
    # TODO: Delete from Qdrant database
    
    logger.info_ctx(
        "Document deleted",
        document_id=document_id,
        user_id=current_user.id
    )
    
    return {"message": "Document deleted successfully"}


@api_router.post("/search", response_model=SearchResponse)
async def search_documents(
    query: SearchQuery,
    current_user: User = Depends(get_current_user)
):
    """Search through documents"""
    
    start_time = time.time()
    
    try:
        # TODO: Implement actual vector search with Qdrant
        # For now, return mock results
        
        results = []
        
        # Mock search results
        from app.services.models import SearchResult
        results.append(SearchResult(
            chunk_id="mock_chunk_1",
            text=f"This is a mock search result for query: {query.query}",
            relevance_score=0.95,
            document_id="mock_doc_1",
            metadata={"filename": "example.pdf", "page": 1}
        ))
        
        processing_time = time.time() - start_time
        
        # Update metrics
        metrics.increment_counter("search_queries")
        
        logger.info_ctx(
            "Search completed",
            query=query.query,
            user_id=current_user.id,
            results_count=len(results),
            processing_time=processing_time
        )
        
        return SearchResponse(
            query=query.query,
            results=results,
            total_results=len(results),
            processing_time=processing_time,
            offset=query.offset,
            limit=query.limit
        )
        
    except Exception as e:
        logger.error_ctx(f"Search failed: {e}", query=query.query, user_id=current_user.id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Search failed"
        )


@api_router.post("/chat/sessions", response_model=ChatSession)
async def create_chat_session(
    current_user: User = Depends(get_current_user),
    title: Optional[str] = None
):
    """Create a new chat session"""
    
    session = ChatSession(
        user_id=current_user.id,
        title=title
    )
    
    _chat_sessions[session.id] = session
    
    logger.info_ctx(
        "Chat session created",
        session_id=session.id,
        user_id=current_user.id
    )
    
    return session


@api_router.get("/chat/sessions", response_model=List[ChatSession])
async def list_chat_sessions(
    current_user: User = Depends(get_current_user),
    limit: int = 10,
    offset: int = 0
):
    """List user's chat sessions"""
    
    user_sessions = []
    for session in _chat_sessions.values():
        if session.user_id == current_user.id and session.is_active:
            user_sessions.append(session)
    
    # Sort by updated_at desc
    user_sessions.sort(key=lambda x: x.updated_at, reverse=True)
    
    # Apply pagination
    start = offset
    end = offset + limit
    
    return user_sessions[start:end]


@api_router.post("/chat/sessions/{session_id}/messages", response_model=ChatMessage)
async def send_chat_message(
    session_id: str,
    message_content: str,
    current_user: User = Depends(get_current_user)
):
    """Send a message in a chat session"""
    
    if session_id not in _chat_sessions:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found"
        )
    
    session = _chat_sessions[session_id]
    
    # Check ownership
    if session.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this chat session"
        )
    
    # Create user message
    user_message = ChatMessage(
        content=message_content,
        role="user",
        user_id=current_user.id
    )
    
    session.add_message(user_message)
    
    # TODO: Generate AI response using RAG
    # For now, create a mock response
    ai_response = ChatMessage(
        content=f"This is a mock AI response to: {message_content}",
        role="assistant",
        context_used=["mock_chunk_1"]  # Mock context chunks
    )
    
    session.add_message(ai_response)
    
    logger.info_ctx(
        "Chat message sent",
        session_id=session_id,
        user_id=current_user.id,
        message_length=len(message_content)
    )
    
    return ai_response


@api_router.get("/chat/sessions/{session_id}", response_model=ChatSession)
async def get_chat_session(
    session_id: str,
    current_user: User = Depends(get_current_user)
):
    """Get a specific chat session"""
    
    if session_id not in _chat_sessions:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found"
        )
    
    session = _chat_sessions[session_id]
    
    # Check ownership
    if session.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this chat session"
        )
    
    return session


@api_router.delete("/chat/sessions/{session_id}")
async def delete_chat_session(
    session_id: str,
    current_user: User = Depends(get_current_user)
):
    """Delete a chat session"""
    
    if session_id not in _chat_sessions:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found"
        )
    
    session = _chat_sessions[session_id]
    
    # Check ownership
    if session.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this chat session"
        )
    
    # Mark as inactive instead of deleting
    session.is_active = False
    
    logger.info_ctx(
        "Chat session deleted",
        session_id=session_id,
        user_id=current_user.id
    )
    
    return {"message": "Chat session deleted successfully"}


@api_router.get("/stats", response_model=UserStats)
async def get_user_stats(current_user: User = Depends(get_current_user)):
    """Get user statistics"""
    
    # Count user's documents
    user_documents = [doc for doc in _document_storage.values() 
                     if doc["user_id"] == current_user.id]
    
    # Count user's chat sessions
    user_sessions = [session for session in _chat_sessions.values() 
                    if session.user_id == current_user.id and session.is_active]
    
    total_chunks = sum(doc.get("chunk_count", 0) for doc in user_documents)
    storage_used = sum(doc.get("file_size", 0) for doc in user_documents) / 1024 / 1024  # MB
    
    return UserStats(
        user_id=current_user.id,
        documents_uploaded=len(user_documents),
        total_chunks=total_chunks,
        search_queries=0,  # TODO: Track search queries
        chat_sessions=len(user_sessions),
        storage_used_mb=storage_used
    )