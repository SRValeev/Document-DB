"""
Enhanced logging system with structured logs and metrics
"""
import json
import logging
import sys
import time
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Dict, Optional
from contextvars import ContextVar

from app.core.config import settings

# Context variables for request tracking
request_id_ctx: ContextVar[Optional[str]] = ContextVar('request_id', default=None)
user_id_ctx: ContextVar[Optional[str]] = ContextVar('user_id', default=None)


class StructuredFormatter(logging.Formatter):
    """
    JSON formatter for structured logging
    """
    
    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Add context information
        if request_id := request_id_ctx.get():
            log_entry["request_id"] = request_id
        if user_id := user_id_ctx.get():
            log_entry["user_id"] = user_id
            
        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
            
        # Add extra fields
        if hasattr(record, 'extra_fields'):
            log_entry.update(record.extra_fields)
            
        return json.dumps(log_entry, ensure_ascii=False)


class MetricsCollector:
    """
    Simple metrics collector for monitoring
    """
    
    def __init__(self):
        self.metrics: Dict[str, Any] = {
            "requests_total": 0,
            "requests_by_endpoint": {},
            "response_times": [],
            "error_count": 0,
            "active_connections": 0,
            "documents_processed": 0,
            "search_queries": 0,
        }
        self.start_time = time.time()
    
    def increment_counter(self, metric: str, labels: Optional[Dict[str, str]] = None):
        """Increment a counter metric"""
        if metric not in self.metrics:
            self.metrics[metric] = 0
        self.metrics[metric] += 1
        
        if labels and metric == "requests_total":
            endpoint = labels.get("endpoint", "unknown")
            if endpoint not in self.metrics["requests_by_endpoint"]:
                self.metrics["requests_by_endpoint"][endpoint] = 0
            self.metrics["requests_by_endpoint"][endpoint] += 1
    
    def record_histogram(self, metric: str, value: float):
        """Record a histogram value"""
        if metric not in self.metrics:
            self.metrics[metric] = []
        self.metrics[metric].append(value)
        
        # Keep only last 1000 values
        if len(self.metrics[metric]) > 1000:
            self.metrics[metric] = self.metrics[metric][-1000:]
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get current metrics"""
        uptime = time.time() - self.start_time
        
        metrics = self.metrics.copy()
        metrics["uptime_seconds"] = uptime
        
        # Calculate response time stats
        if self.metrics["response_times"]:
            response_times = self.metrics["response_times"]
            metrics["avg_response_time"] = sum(response_times) / len(response_times)
            metrics["max_response_time"] = max(response_times)
            metrics["min_response_time"] = min(response_times)
        
        return metrics


# Global metrics instance
metrics = MetricsCollector()


def setup_logging():
    """
    Setup application logging
    """
    # Create logs directory
    log_dir = Path(settings.logs_dir)
    log_dir.mkdir(exist_ok=True)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.monitoring.log_level))
    
    # Clear existing handlers
    root_logger.handlers.clear()
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    if settings.monitoring.log_format == "json":
        console_handler.setFormatter(StructuredFormatter())
    else:
        console_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        console_handler.setFormatter(console_formatter)
    
    root_logger.addHandler(console_handler)
    
    # File handler with rotation
    file_handler = RotatingFileHandler(
        filename=log_dir / "app.log",
        maxBytes=settings.monitoring.max_log_size_mb * 1024 * 1024,
        backupCount=settings.monitoring.backup_count,
        encoding='utf-8'
    )
    
    if settings.monitoring.log_format == "json":
        file_handler.setFormatter(StructuredFormatter())
    else:
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(file_formatter)
    
    root_logger.addHandler(file_handler)
    
    # Separate error log
    error_handler = RotatingFileHandler(
        filename=log_dir / "error.log",
        maxBytes=settings.monitoring.max_log_size_mb * 1024 * 1024,
        backupCount=settings.monitoring.backup_count,
        encoding='utf-8'
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(StructuredFormatter() if settings.monitoring.log_format == "json" 
                              else file_formatter)
    
    root_logger.addHandler(error_handler)
    
    # Configure specific loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    
    logger = logging.getLogger(__name__)
    logger.info("Logging system initialized", extra={
        'extra_fields': {
            'log_level': settings.monitoring.log_level,
            'log_format': settings.monitoring.log_format
        }
    })


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with enhanced functionality
    """
    logger = logging.getLogger(name)
    
    # Add custom methods
    def log_with_context(level, message, **kwargs):
        extra_fields = kwargs.pop('extra_fields', {})
        extra_fields.update(kwargs)
        logger.log(level, message, extra={'extra_fields': extra_fields})
    
    def info_with_context(message, **kwargs):
        log_with_context(logging.INFO, message, **kwargs)
    
    def error_with_context(message, **kwargs):
        log_with_context(logging.ERROR, message, **kwargs)
    
    def warning_with_context(message, **kwargs):
        log_with_context(logging.WARNING, message, **kwargs)
    
    # Monkey patch methods
    logger.info_ctx = info_with_context
    logger.error_ctx = error_with_context
    logger.warning_ctx = warning_with_context
    
    return logger


def log_function_call(func_name: str, args: Dict[str, Any] = None, 
                     result: Any = None, duration: float = None):
    """
    Log function call with parameters and result
    """
    logger = get_logger("function_calls")
    
    log_data = {
        "function": func_name,
        "duration_ms": duration * 1000 if duration else None,
    }
    
    if args:
        # Don't log sensitive data
        safe_args = {k: v for k, v in args.items() 
                    if k not in ['password', 'token', 'secret']}
        log_data["args"] = safe_args
    
    if result is not None:
        log_data["result_type"] = type(result).__name__
        if hasattr(result, '__len__'):
            try:
                log_data["result_length"] = len(result)
            except:
                pass
    
    logger.info("Function call completed", extra={'extra_fields': log_data})