"""
Custom exceptions and error handling
"""
from typing import Any, Dict, Optional
from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse
import logging

from app.core.logging import get_logger

logger = get_logger(__name__)


class BaseAppException(Exception):
    """Base application exception"""
    
    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        error_code: Optional[str] = None
    ):
        self.message = message
        self.details = details or {}
        self.error_code = error_code or self.__class__.__name__
        super().__init__(self.message)


class ValidationError(BaseAppException):
    """Validation error"""
    pass


class AuthenticationError(BaseAppException):
    """Authentication error"""
    pass


class AuthorizationError(BaseAppException):
    """Authorization error"""
    pass


class DocumentProcessingError(BaseAppException):
    """Document processing error"""
    pass


class DatabaseError(BaseAppException):
    """Database operation error"""
    pass


class LLMError(BaseAppException):
    """LLM API error"""
    pass


class RateLimitError(BaseAppException):
    """Rate limit exceeded error"""
    pass


class FileUploadError(BaseAppException):
    """File upload error"""
    pass


class ConfigurationError(BaseAppException):
    """Configuration error"""
    pass


class ExternalServiceError(BaseAppException):
    """External service error"""
    pass


# HTTP Exception mappings
EXCEPTION_STATUS_MAPPING = {
    ValidationError: status.HTTP_400_BAD_REQUEST,
    AuthenticationError: status.HTTP_401_UNAUTHORIZED,
    AuthorizationError: status.HTTP_403_FORBIDDEN,
    DocumentProcessingError: status.HTTP_422_UNPROCESSABLE_ENTITY,
    DatabaseError: status.HTTP_500_INTERNAL_SERVER_ERROR,
    LLMError: status.HTTP_502_BAD_GATEWAY,
    RateLimitError: status.HTTP_429_TOO_MANY_REQUESTS,
    FileUploadError: status.HTTP_400_BAD_REQUEST,
    ConfigurationError: status.HTTP_500_INTERNAL_SERVER_ERROR,
    ExternalServiceError: status.HTTP_502_BAD_GATEWAY,
}


async def app_exception_handler(request: Request, exc: BaseAppException) -> JSONResponse:
    """
    Global exception handler for application exceptions
    """
    status_code = EXCEPTION_STATUS_MAPPING.get(type(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    error_response = {
        "error": {
            "type": exc.error_code,
            "message": exc.message,
            "details": exc.details
        },
        "request_id": getattr(request.state, 'request_id', None),
        "timestamp": logger.handlers[0].formatter.formatTime(logger.makeRecord(
            name="", level=0, pathname="", lineno=0, msg="", args=(), exc_info=None
        )) if logger.handlers else None
    }
    
    # Log the error
    logger.error_ctx(
        f"Application error: {exc.message}",
        error_type=exc.error_code,
        status_code=status_code,
        details=exc.details,
        url=str(request.url),
        method=request.method
    )
    
    return JSONResponse(
        status_code=status_code,
        content=error_response
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """
    Global exception handler for HTTP exceptions
    """
    error_response = {
        "error": {
            "type": "HTTPException",
            "message": exc.detail,
            "status_code": exc.status_code
        },
        "request_id": getattr(request.state, 'request_id', None)
    }
    
    logger.warning_ctx(
        f"HTTP error: {exc.detail}",
        status_code=exc.status_code,
        url=str(request.url),
        method=request.method
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response
    )


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Global exception handler for unexpected exceptions
    """
    error_response = {
        "error": {
            "type": "InternalServerError",
            "message": "An unexpected error occurred",
            "details": {"error_type": type(exc).__name__}
        },
        "request_id": getattr(request.state, 'request_id', None)
    }
    
    logger.error(
        f"Unexpected error: {str(exc)}",
        extra={
            'extra_fields': {
                'error_type': type(exc).__name__,
                'url': str(request.url),
                'method': request.method
            }
        },
        exc_info=True
    )
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_response
    )


def handle_error_with_context(func):
    """
    Decorator to handle errors with context logging
    """
    async def async_wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except BaseAppException:
            raise
        except Exception as e:
            logger.error(
                f"Error in {func.__name__}: {str(e)}",
                extra={'extra_fields': {'function': func.__name__}},
                exc_info=True
            )
            raise BaseAppException(
                message=f"Error in {func.__name__}",
                details={"original_error": str(e)},
                error_code="InternalError"
            )
    
    def sync_wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except BaseAppException:
            raise
        except Exception as e:
            logger.error(
                f"Error in {func.__name__}: {str(e)}",
                extra={'extra_fields': {'function': func.__name__}},
                exc_info=True
            )
            raise BaseAppException(
                message=f"Error in {func.__name__}",
                details={"original_error": str(e)},
                error_code="InternalError"
            )
    
    # Return appropriate wrapper based on function type
    import asyncio
    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    else:
        return sync_wrapper