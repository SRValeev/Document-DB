"""
Main FastAPI application with enhanced architecture and security
"""
import time
import uuid
from contextual import asynccontextmanager
from typing import AsyncIterator
import asyncio

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

from app.core.config import settings
from app.core.logging import setup_logging, get_logger, metrics, request_id_ctx, user_id_ctx
from app.core.exceptions import (
    BaseAppException, 
    app_exception_handler, 
    http_exception_handler, 
    general_exception_handler
)
from app.core.security import rate_limiter
from app.services.document_processor import document_processor
from app.api.routes import api_router
from app.api.auth import auth_router

# Initialize logging
setup_logging()
logger = get_logger(__name__)


class RequestTrackingMiddleware:
    """Middleware for request tracking and metrics"""
    
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        request_id = str(uuid.uuid4())
        start_time = time.time()
        
        # Set context variables
        request_id_ctx.set(request_id)
        
        # Create request object to get details
        request = Request(scope, receive)
        
        # Track active connections
        metrics.increment_counter("active_connections")
        
        try:
            # Add request ID to scope
            scope["request_id"] = request_id
            
            # Call the app
            await self.app(scope, receive, send)
            
        finally:
            # Calculate response time
            response_time = time.time() - start_time
            
            # Record metrics
            metrics.increment_counter("requests_total", {
                "endpoint": request.url.path,
                "method": request.method
            })
            metrics.record_histogram("response_times", response_time)
            metrics.increment_counter("active_connections", -1)  # Decrement
            
            # Log request completion
            logger.info_ctx(
                "Request completed",
                request_id=request_id,
                method=request.method,
                path=request.url.path,
                response_time=response_time
            )


class RateLimitMiddleware:
    """Rate limiting middleware"""
    
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        request = Request(scope, receive)
        
        # Get client IP
        client_ip = request.client.host if request.client else "unknown"
        
        # Check rate limit for non-auth endpoints
        if not request.url.path.startswith("/auth/"):
            if not rate_limiter.check_rate_limit(client_ip, "api"):
                response = JSONResponse(
                    status_code=429,
                    content={
                        "error": {
                            "type": "RateLimitError",
                            "message": "Rate limit exceeded",
                            "details": {"retry_after": 60}
                        }
                    }
                )
                await response(scope, receive, send)
                return
        
        await self.app(scope, receive, send)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan manager"""
    
    # Startup
    logger.info("Starting RAG Document Assistant v2.0")
    
    try:
        # Initialize document processor
        logger.info("Initializing document processor...")
        # Document processor is already initialized globally
        
        # Initialize database connections
        logger.info("Initializing database connections...")
        # TODO: Initialize Qdrant and other databases
        
        # Start background tasks
        logger.info("Starting background tasks...")
        # TODO: Start background document processing tasks
        
        logger.info("Application startup complete")
        
        yield  # Application is running
        
    except Exception as e:
        logger.error(f"Startup failed: {e}", exc_info=True)
        raise
    
    finally:
        # Shutdown
        logger.info("Shutting down application...")
        
        # Cleanup resources
        try:
            await document_processor.cleanup_temp_files(settings.temp_dir)
        except Exception as e:
            logger.warning(f"Cleanup failed: {e}")
        
        logger.info("Application shutdown complete")


# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    description="Enhanced RAG Document Assistant with enterprise features",
    docs_url=settings.api.docs_url if not settings.testing else None,
    redoc_url=settings.api.redoc_url if not settings.testing else None,
    lifespan=lifespan,
    debug=settings.debug
)

# Add middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.api.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*"] if settings.debug else ["localhost", "127.0.0.1"]
)

# Add custom middleware
app.add_middleware(RequestTrackingMiddleware)
app.add_middleware(RateLimitMiddleware)

# Add exception handlers
app.add_exception_handler(BaseAppException, app_exception_handler)
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(Exception, general_exception_handler)

# Include routers
app.include_router(auth_router, prefix="/auth", tags=["Authentication"])
app.include_router(api_router, prefix="/api/v1", tags=["API"])

# Static files
try:
    app.mount("/static", StaticFiles(directory="frontend/static"), name="static")
except Exception as e:
    logger.warning(f"Static files not mounted: {e}")

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    from app.services.models import HealthStatus
    
    services = {}
    overall_status = "healthy"
    
    # Check document processor
    try:
        stats = document_processor.get_processing_stats()
        services["document_processor"] = "healthy"
    except Exception as e:
        services["document_processor"] = f"unhealthy: {e}"
        overall_status = "degraded"
    
    # Check database (Qdrant)
    try:
        # TODO: Add Qdrant health check
        services["database"] = "healthy"
    except Exception as e:
        services["database"] = f"unhealthy: {e}"
        overall_status = "unhealthy"
    
    return HealthStatus(
        status=overall_status,
        services=services,
        version=settings.version,
        uptime_seconds=metrics.get_metrics().get("uptime_seconds", 0)
    )


@app.get("/metrics")
async def get_metrics():
    """Get application metrics"""
    if not settings.monitoring.metrics_enabled:
        raise HTTPException(status_code=404, detail="Metrics not enabled")
    
    from app.services.models import SystemMetrics
    
    raw_metrics = metrics.get_metrics()
    
    return SystemMetrics(
        requests_total=raw_metrics.get("requests_total", 0),
        requests_by_endpoint=raw_metrics.get("requests_by_endpoint", {}),
        avg_response_time=raw_metrics.get("avg_response_time", 0.0),
        error_count=raw_metrics.get("error_count", 0),
        active_connections=raw_metrics.get("active_connections", 0),
        documents_processed=raw_metrics.get("documents_processed", 0),
        search_queries=raw_metrics.get("search_queries", 0),
        uptime_seconds=raw_metrics.get("uptime_seconds", 0.0)
    )


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": settings.app_name,
        "version": settings.version,
        "status": "running",
        "docs": settings.api.docs_url,
        "health": "/health",
        "metrics": "/metrics" if settings.monitoring.metrics_enabled else None,
        "api": "/api/v1",
        "auth": "/auth"
    }


# Request context middleware
@app.middleware("http")
async def add_request_context(request: Request, call_next):
    """Add request context for logging"""
    
    # Set request ID in state
    request_id = getattr(request.scope, 'request_id', str(uuid.uuid4()))
    request.state.request_id = request_id
    
    # Extract user ID from JWT token if present
    user_id = None
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        try:
            from app.core.security import verify_token
            token = auth_header.split(" ")[1]
            token_data = verify_token(token)
            user_id = token_data.user_id
            user_id_ctx.set(user_id)
        except Exception:
            pass  # Invalid token, continue without user context
    
    response = await call_next(request)
    return response


def create_app() -> FastAPI:
    """Application factory"""
    return app


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.api.host,
        port=settings.api.port,
        reload=settings.api.reload,
        workers=1,  # Use 1 worker for development
        log_level=settings.monitoring.log_level.lower(),
        access_log=False  # We handle access logging in middleware
    )